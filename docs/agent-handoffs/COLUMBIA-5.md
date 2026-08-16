# Agent Handoff - COLUMBIA-5 (batch 6, card 8 - the fifth grammar: Columbia's 3-document cohort)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** COLUMBIA-5 - the fifth summary grammar of the core-processor
  complex: 3 documents printing the sentence-case period PAIR with
  `Beginning balance $` / `Ending balance $` and NO `Total days in
  statement period` line. Two are unclaimed; one is claimed by
  `columbia_bank` - the coexistence question is half the card.

# Git ownership
- Base: main `eef77c6` - Branch: `wave6-columbia5` - Worktree:
  `.claude/worktrees/mt6-columbia5`. Own: the new registration or a
  measured extension of `columbia_bank` (DECIDE BY MEASUREMENT - see below),
  tests, W3 log (#COLUMBIA5).

# The evidence base (read first: W3 §LCPERIOD L7, the "FOURTH arrangement" block)
- The 3: `2E667295DFCB16BA...` (unclaimed), `88AAC06119FC0B7D...`
  (unclaimed), `0CBD2AD897B90137...` (claimed by columbia_bank). Re-derive
  full shas by live replay.
- The summary block (attested):
  `Account number XXXXXX4166  Beginning balance $59,347.32` /
  `Low balance` `Average balance` `Interest earned` in the left column,
  `Deposits/Additions` `Withdrawals/Subtractions` `Ending balance` right.
- Sections `Deposits/Additions` and `ACH and Electronic Payments/
  Subtractions`, each closed by its own `Total Additions $...` row - the
  per-section totals are your ledger oracle.
- Known family hazard (W3 §COUNTSP3 record): `88AAC06119FC` previously
  read `03-16 — 39,692.35` - a PLACEHOLDER in a daily-balance grid - as a
  transaction; the amount is a positive BALANCE. Whatever reads the daily
  grid must refuse placeholder rows; prove it on that exact printing.

# The decision this card owns
Is this a fifth-grammar SIBLING registration (coexisting with
columbia_bank, supersedes edge over the one claimed doc if the new reader
is strictly better - prove field-by-field) or an extension of
columbia_bank itself? Decide by the same measurement discipline LC-PERIOD
used (registration-vs-widening: a detector must not claim what its parser
cannot read). The claimed document's CURRENT published output is the
baseline: no field may silently change without being named as a mover.

# Expected archive movement
Up to 2 unclaimed shas failed -> validated; the claimed sha only moves
(any field) if you name it as a mover with field-level before/after and
the reason the new read is more faithful to the printing. Zero movement
outside the 3. If the claimed doc is pinned in the 109 - check first -
any pinned movement means STOP and report to Ocean (truth-set ceremony
territory, Gustavo's).

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
withheld) + guards + conformance cross-product (updated if a registration is
added, pins in the SAME commit); exit codes verbatim; every mover named by
content_sha256 + outcome + field; claimed != validated; zero movement
outside your named populations; commit incrementally, clean tree; NEVER
merge or push - Ocean runs the train. ANALYSIS_STAGE_VERSION bump is Ocean's
at merge. Fail-closed everywhere.

# Final report to Ocean
The sibling-vs-extension decision with measurement; the placeholder-refusal
proof on the attested printing; the claimed-doc field diff (or its
byte-identity); population sweep; hunks verbatim; proofs with exit codes;
commits; risks.
