# Agent Handoff - PRIVACY-3 (batch 7, card 10 - the remaining exception-text boundaries, zero movement)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** PRIVACY-3 - the batch-6 privacy reviews' carried findings,
  bundled because each is a boundary of the same class (document-derived
  text leaving the process) and none moves an outcome:
  - APP-PRIVACY: `webapp/app.py:revenue_review` returns `str(exc)` as an
    HTTP body (404 and 400 arms) behind an `except` broader than the three
    fixed literals `analysis/revenue.py` raises; `parse_decimal` raises the
    document token. Fix shape: catch the three declared refusals by exact
    literal, reduce everything else to fixed vocabulary;
    `test_the_webapp_exception_ledger_is_complete` must fail the moment a
    third site appears.
  - RAISE-PRIVACY-2: six sibling `ValueError(value)` parser sites, twenty
    `strptime` sites, `ocr/availability.py:126` (`detail=str(exc)[:200]`),
    and the `AmountFormat`/`_compiled` lru_cache residency note (W3
    §MONEYPRIV MP-review) - census first, fix by MONEY-PRIVACY's pattern
    (one constructor, chain severed: raise outside the handler), AST
    chain-guard extended to the new sites.
  - PIPELINE-PARSEMODE: `analysis/pipeline.py:703` lacks a parse_mode
    clause - characterize what reaches it and close it fail-closed.
  - WORKER-PRIVACY m-7: `webapp/worker.py run_job` catches `Exception`, not
    `BaseException`; a BaseException in the queue thread kills the thread
    with a traceback on stderr and leaves the job stuck at `processing`
    with `error=None`. Fix: a `BaseException`/`finally` arm that marks the
    job failed with fixed vocabulary; record (don't decide) the stderr
    logging question for D-2b.
  - G7.3: the hardcode guard scans docstrings - make the guard's scan
    exclude docstrings/comments explicitly or prove it already does, so a
    documented example can never trip or hide a finding.

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave7-privacy3` -
  Worktree: `.claude/worktrees/mt7-privacy3`. Own: webapp/app.py,
  webapp/worker.py (the m-7 arm only), ocr/availability.py, the named
  parser raise sites (ONLY the raise expressions - the readers' logic is
  other cells' territory: huntington/chase (DECLINES-E), bmo_ca_business/
  capital_one/first_citizens (DECLINES-F), fiserv_premier/scotia/symitar/
  consumers (DECLINES-G), columbia_bank (REPAIR-DOCTRINE), the core
  processors (DESC-ATTRIB), scanned_small_bank/citizens (SCAN-FINISH): if a
  named site lives in one of those files, LIST it for Ocean instead of
  editing it), analysis/pipeline.py:703 only, the guard test, tests, W3 log
  (#PRIVACY3).

# The work
Census first (every site, before/after, by file:line); poisoned-input
tests proving no canary / no >=3-digit run survives into str(exc), the
chain, or a rendered traceback; mutation kill per site; caller census (who
catches what, nothing behavioural changes).

# Expected archive movement
ZERO on the 3,380 and ZERO pinned - prove structurally (deterministic path
never raises through these sites with document text) AND with the sweep.

# Report
The site census; hunks verbatim; the sites deferred to other cells' files;
poisoned-input proofs; mutation kills; the sweep; proofs with exit codes;
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
