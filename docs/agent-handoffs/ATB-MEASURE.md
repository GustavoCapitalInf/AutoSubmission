# Agent Handoff - ATB-MEASURE (batch 7, card 3 - READ-ONLY: the ATB Financial currency measurement packet)

Ocean reviews; you never merge or push.
**You change NOTHING in the repo: no code edits, no expectation edits, no
cache writes; your branch carries the packet document and your W3 section
only. Prototype probes live in your private scratchpad subdir. Gustavo's
ruling (2026-08-21): "ATB gets the full eight-proof measurement packet only;
no movement until reviewed."**

# Identity
- **Agent:** ATB-MEASURE - produce the eight-proof packet for ATB Financial
  (Alberta Treasury Branches - a Canadian provincial Crown corporation)
  whose published currency today is the schema default USD. Model:
  docs/moneythumb-replacement/RBC_CURRENCY_MEASUREMENT.md (the accepted RBC
  packet - same sections, same proof order, same discipline) and
  CURRENCY_DOCTRINE.md §B/§C verbatim.

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave7-atbmeasure` -
  Worktree: `.claude/worktrees/mt7-atbmeasure`. Own:
  docs/moneythumb-replacement/ATB_CURRENCY_MEASUREMENT.md on the branch, W3
  log (#ATBMEASURE). NOTHING else.

# The population (re-derive; do not trust these counts)
- Five PINNED `ATB/*.pdf` documents published by the `atb` registration
  (analysis/atb.py - `ATB Financial` + `Deposit Account Statement`
  markers; `Statement(bank="ATB Financial", ...)` never sets currency);
  pinned USD in corpus_gate.py `PINNED_CURRENCY` with the comment that they
  are named future movers.
- Two archive documents the same registration publishes as
  `withheld/withheld_adb`.
- Four UNCLAIMED 2026 documents whose filenames say `ATB Chequing Account`
  (`284B775D...`, `EE09ADA6...`, `745B2968...`, `F1DA262D...`;
  failed/no_parser_matched) - a different ATB product printing no reader
  claims. They publish no currency today, so they are not movers; the
  packet must still characterize them (is it ATB? which product? what does
  it print about currency?) because any future reader for them must be born
  on the right default.
- Anything else ATB by live detection replay / artifact text census
  (`ATB Financial`, `atb.com`, Alberta transit shapes) - never by filename.

# The eight proofs (all must land; quote the doctrine item you satisfy)
1. Every affected document is an ATB (Alberta, Canada) account/product for
   which CAD is the correct native default - structural evidence per
   document class (institution identity, product wording, transit /
   institution-number shapes (ATB is institution 219), Alberta postal codes
   and addresses, atb.com furniture - whatever the documents actually
   print; enumerate the evidence classes used).
2. None contains explicit USD or other contrary currency evidence (`U.S.
   Funds`, `US Dollar`, a USD account designation or equivalent). Detector
   text and its hit census over the whole population.
3. ATB has no US institution, but US-DOLLAR PRODUCTS exist at Canadian
   banks: show the discriminator that refuses the default on a USD-product
   printing (prove it on any such archive document; if none, on synthetic
   printings, and say so).
4. The five pinned documents individually enumerated: path, sha, current
   pinned expectations (verdict, currency USD), proposed movement.
5. Exact before/after currency values for every document in the packet.
6. Currency label movement ONLY: no amount, ADB, ledger, classification or
   outcome changes - prototype the default in your scratchpad, replay,
   field-diff the full published block per document (read-only; private
   cache namespace if any caching at all).
7. The pinned currency surface's other 104 entries, the 151 RBC movers and
   the nine CURRENCY-1 corrections remain byte-identical under the
   prototype (name the nine by sha).
8. The rule as implemented-to-be is structural (institution / product /
   jurisdiction evidence), never filename/folder. The prototype must not
   read paths; carry a counterfeit-direction test through admissible text.
Also: every document with conflicting or uncertain evidence leaves the
packet and is named separately (fail closed / preserve uncertainty).

# Output
The packet document + the ceremony-ready enumeration (five pinned
expectation diffs + the exact N-document movement list) IF AND ONLY IF all
eight prove clean; otherwise the honest failure. Do not weaken a check to
make a ceremony pass. The packet also states, for CURRENCY-SOURCE's
provenance vocabulary, which source class an ATB default would be
(`jurisdiction_default` vs `institution_default`) and why.

# Report
The eight proofs in order, each with census and method; the exclusions; the
ceremony-ready enumeration or the honest failure; the four unclaimed
chequing documents characterized; risks.

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
