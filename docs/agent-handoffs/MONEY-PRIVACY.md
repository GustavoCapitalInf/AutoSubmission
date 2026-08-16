# Agent Handoff - MONEY-PRIVACY (batch 6, card 1 - the raising family stops quoting the document)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** MONEY-PRIVACY - close the exception boundary one layer below
  batch-4's `read_money` law: the money-grammar raising family carries the
  printed token in `ValueError(value)`, and `webapp/worker.py` publishes
  `str(exc)` as the job error, so statement content can cross into the
  durable store.

# Git ownership
- Base: main `eef77c6` - Branch: `wave6-moneypriv` - Worktree:
  `.claude/worktrees/mt6-moneypriv`. Own: the shared money-grammar module
  (the raising family), its callers' expectations on exception text, tests,
  W3 log (#MONEYPRIV).

# The evidence base (read first: W3 §MGD10 finding 6 - MGD-C1)
`parse_decimal`, `parse_decimal_mixed_separator`, `parse_grouped_float`,
`parse_trailing_minus_dropped`, `parse_french_amount` all
`raise ValueError(value)` with the printed token as the message. Batch 4
closed this law for `read_money` (§MG-C2 D1: a refusal never quotes the
cell); the same module still quotes one layer down. **MG-D WIDENED the
exposure**: before `wave5-mgd`, `parse_signed_decimal("—$500.00")` returned a
number; now it raises `ValueError("— 500.00")` - a dormant boundary defect
acquired a live caller. Nothing leaks on today's archive (the em-dash path is
unreachable), which is exactly why the card is taken now, not after it
becomes reachable.

# The work
1. Sweep the module for every `raise` whose message embeds `value`/token
   text; replace with named-reason messages (reason vocabulary, not
   content). Follow the §MG-C2 refusal-reason pattern already in the module.
2. Repo-wide caller sweep: any test or caller matching on the old messages;
   any OTHER raise site in analysis/ that quotes document text into an
   exception that can reach `str(e)` boundaries - report what you find, fix
   only your module's family (name the rest for the ledger).
3. Prove the boundary: a test family that feeds a poisoned token through
   each raising function and asserts the printed token appears in NO
   exception message (mutation-kill each).
4. MGD-C2 (fintech row grammars absorbing sign glyphs; the zero-amount
   hole) is adjacent but NOT yours - different owner, different fix shape.

# Expected archive movement
ZERO. This is an exception-message card; no outcome, flag, note, or
published field may move on any of the 3,380. Full-population before/after
required; any mover is a defect in the card.

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
The raise-site census (before/after messages side by side); the poisoned-
token proof; the zero-movement sweep; hunks verbatim; proofs with exit
codes; commits; risks; the ledger of quoted-text raise sites you found but
did not own.
