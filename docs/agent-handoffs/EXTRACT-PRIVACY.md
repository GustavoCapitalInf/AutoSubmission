# Agent Handoff - EXTRACT-PRIVACY (batch 6, micro-card 14 - the LLM branch stops quoting the transcription)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** EXTRACT-PRIVACY - `analysis/extract.py:96` raises
  `RuntimeError(f"extraction did not return a Statement: {resp.text[:300]!r}")`
  - 300 characters of the model's transcription of the document, on the
  LLM branch, which `analyze_markdown` does NOT guard (measured by
  MONEY-PRIVACY, verified by its reviewer). WORKER-PRIVACY's boundary makes
  the message unpublished at the durable job store, but the exception still
  carries document-derived text into any log, traceback, or future
  consumer. Close it at the source.

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave6-extractpriv` -
  Worktree: `.claude/worktrees/mt6-extractpriv` (created for you). Own:
  analysis/extract.py, its tests, W3 log (#EXTRACTPRIV). Nobody else in
  batch 6 owns extract.py. Do NOT touch analysis/money.py (MONEY-PRIVACY,
  complete), webapp/worker.py (WORKER-PRIVACY, complete), or any parser.

# The work
1. MEASURE FIRST: census every raise/exception path in analysis/extract.py
   (and any helper it owns) for document-derived or model-derived text:
   message, args, __cause__, __context__, rendered traceback. MONEY-PRIVACY
   found :96; verify whether siblings exist in this file.
2. Replace the quoting message with fixed vocabulary that never embeds
   resp.text or any transcription fragment. Preserve the exception CLASS
   and the control flow exactly - callers that catch RuntimeError must be
   unaffected. A short structural description is fine ("extraction did not
   return a Statement (response length N, stop_reason=...)") ONLY if every
   interpolated value is provably content-free (lengths, enum vocabulary,
   booleans); when in doubt, constants only. Sever any chain that would
   carry the text via __cause__/__context__ (MONEY-PRIVACY's pattern:
   raise OUTSIDE the except handler; `from None` clears __cause__ but
   leaves __context__).
3. Tests: a poisoned-response test proving no canary / no >=3-digit run
   survives into str(exc), the chain, or a rendered traceback; a mutation
   kill (revert to the f-string -> a test fails); an AST or vocabulary
   guard if the file has more than one raise.
4. Census the CALLERS of this exception (who catches RuntimeError from
   extract?) and state in your report what each does with the message -
   no caller behaviour may change.

# Expected archive movement
ZERO on the 3,380. The discovery run of record is deterministic
(parse_mode="deterministic"); the LLM branch is never taken in archive
replay. Prove the claim structurally (grep the deterministic path) rather
than by a full sweep - a full-population replay is NOT required for this
card. The corpus gate makes no model calls (ocr_coverage proves it), so
the pinned 109 cannot move.

# Proof floor (cell-level)
Full default suite green; corpus-marked slice green; `python
corpus_gate.py` GREEN (106/3; verdicts 102 validated / 4 review / 3
withheld); guards + conformance cross-product; your poisoned-response
tests; the mutation kill; exit codes verbatim.

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-16 batch-5 entry in WAVE2_EXECUTION_LOG.md
first. Base main carries v13, OCR v3, registry 72 ON MAIN (sibling
branches not yet merged may add registrations - yours must not). Run of
record: `discovery_reports/2026-08-16T000943.012887-0000-2e3ea385`.
Archive + caches READ-ONLY; OCR artifacts by direct file path only (never
the webapp_data sqlite index); $0 vendor - your tests MUST NOT call any
hosted model; private uniquely-named scratchpad subdir; long proofs as
SEQUENTIAL single commands or detached processes tracked via `tasklist`
(never MSYS `kill -0`); a completion signal must be producible only by
completion (append your own EXIT= terminator lines to durable logs). The
machine is shared with other cells - keep probes light. Exit codes
verbatim; claimed != validated; zero movement anywhere; commit
incrementally, clean tree; NEVER merge or push - Ocean runs the train.
Fail-closed everywhere.

# Final report to Ocean
The raise-site census of extract.py; the hunk verbatim; the caller
census; the poisoned-response proof; the mutation kill; proofs with exit
codes; commits; risks.
