# Agent Handoff - WORKER-PRIVACY (batch 6, card 2 - str(e) never reaches the durable store)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** WORKER-PRIVACY - the webapp worker publishes raw exception
  text into the durable store. Statement content that survives any raise
  (see MONEY-PRIVACY, running in parallel) becomes a stored, user-visible
  job error. Store exception CLASS NAMES and named reasons only.

# Git ownership
- Base: main `eef77c6` - Branch: `wave6-workerpriv` - Worktree:
  `.claude/worktrees/mt6-workerpriv`. Own: webapp/worker.py's exception
  boundary, its store contract tests, W3 log (#WORKERPRIV).

# The evidence base
- `webapp/worker.py:94` - `return markdown, html, None, str(e)` (the
  analyze wrapper's error channel).
- `webapp/worker.py:335` - `store.set_error(job_id, str(e))` (the job-level
  boundary).
- `analysis/pipeline.py:608` carries the law as a comment already (the
  refusal-boundary hardening batch 4 landed) - your card extends that law to
  the worker's two sites. Read that comment and its tests before writing.
(Line numbers verified on `eef77c6`; re-verify on your base.)

# The work
1. Both sites publish `type(e).__name__` plus a named stage/reason - never
   `str(e)`. Keep the full exception in the process LOG (non-durable,
   operator-only) if the existing logging already does so; do not add new
   content sinks.
2. Contract test: a poisoned exception message (containing a sentinel
   "document" token) through both boundaries; assert the sentinel appears
   nowhere in the store. Mutation-kill.
3. Sweep webapp/ for any other `str(e)`/`repr(e)`/`f"{e}"` reaching
   store/state/HTTP responses; fix in-scope sites, ledger the rest.

# Expected archive movement
ZERO across the 3,380 (worker is the webapp path; discovery outcomes are
untouched by construction - state that and prove it with the standard
full-population sweep).

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-16 batch-5 entry in WAVE2_EXECUTION_LOG.md
first. Base main `eef77c6` (v13, OCR v3, registry 72, suite 4,511,
corpus-marked 27). Run of record:
`discovery_reports/2026-08-16T000943.012887-0000-2e3ea385` (validated 2,430 /
review 15 / withheld 63 / failed 859 / deferred 13; 3,380 distinct shas;
analysis regenerated cold at v13). Archive + caches READ-ONLY; OCR artifacts
by DIRECT file path only (never the webapp_data sqlite index); $0 vendor;
private uniquely-named scratchpad subdir. Long background shells get killed -
run long proofs as SEQUENTIAL single commands; detached-process aliveness via
`tasklist`, never MSYS `kill -0`. Family populations: derive by live
detection replay or artifact-store enumeration, NEVER from rows.csv parser_id
alone. Proof floor per branch: full default suite + corpus-marked slice +
`python corpus_gate.py` GREEN (106/3; verdicts 102 validated / 4 review / 3
withheld) + guards + conformance cross-product (72x71); exit codes verbatim;
every mover named by content_sha256 + outcome + field; claimed != validated;
zero movement outside your named populations; commit incrementally, clean
tree; NEVER merge or push - Ocean runs the train. ANALYSIS_STAGE_VERSION bump
is Ocean's at merge. Fail-closed everywhere.

# Final report to Ocean
The boundary census (every durable sink of exception text in webapp/, fixed
or ledgered); the sentinel proof; hunks verbatim; zero-movement sweep;
proofs with exit codes; commits; risks.
