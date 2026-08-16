# Agent Handoff - FISERV-ISSUE3 (batch 6, card 6 - the third issue of the fiserv_premier template, +4)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** FISERV-ISSUE3 - read the third issue of the fiserv_premier
  template: four consecutive statements of one coastalstatesbank account,
  folder `Unidentified/`, prefix `d8ddb4db`. Detection already claims all
  four (score 0.5, summary identity closes to 0.0000); parse refuses on two
  named causes. +4 measured ceiling.

# Git ownership
- Base: main `eef77c6` - Branch: `wave6-fiserv3` - Worktree:
  `.claude/worktrees/mt6-fiserv3`. Own: the fiserv_premier module (or a
  sibling registration if coexistence measures cleaner - decide by the
  §SCANB sibling discipline), tests, W3 log (#FISERV3).

# The evidence base (read first: W3 §FISERVISS FI1-FI2 - every figure is a live replay)
The four content_sha256 (native-pdf-text, 8 pages, truncation 0):
`4D0EACF6D617...A29E` (April, 30d) · `4B37474294BF...0C1D` (May, 29d) ·
`8DB2CB78B67C...EA71` (May 30-Jun 30, 32d) · `E34083B2FED7...8513`
(Jul, 31d).
- **Cause 1 - the period wording.** All four print their period TWICE:
  `Statement of Account <Month DD, YYYY> thru <Month DD, YYYY>` in the
  masthead and `Activity Summary Days in the Statement Period:  N`.
  `_PERIOD_RE` reads neither ("the bank did not print it" was REFUTED -
  we do not read what the bank printed).
- **Cause 2 - the ledger vocabulary.** `_sections(...)` finds activity 0,
  credit 0, debit 0, daily 0: the third issue's section vocabulary is
  unread. §FI2.3: the ledger is reachable and the residual is ONE
  money-grammar rule for the embedded ledger - with a REAL hazard: a greedy
  lookahead reading a reference number as an amount. That lookahead is the
  thing your money-grammar rule must NOT simply relax - build the rule to
  refuse the reference-number shape and prove it on the attested rows.
- `_issuer` -> None with `_own_domain -> 'coastalstatesbank'`;
  decide honestly whether the document prints an issuer (bank=None doctrine
  applies if not - never infer from the domain alone unless the document
  prints it as issuer identity; state your evidence).

# The work
Second period wording + the third issue's section vocabulary + the one
money-grammar rule, under the module's existing oracles (summary identity
already closes; printed counts/totals gate the ledger read). Coexistence:
the first two issues' populations must be byte-identical before/after -
family sweep by live replay over all artifacts (never rows.csv parser_id).

# Expected archive movement
Exactly the 4 named shas failed -> validated IF every gate passes honestly;
fewer is acceptable with named reasons (claimed != validated). Zero movement
outside the 4.

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
Gate-by-gate before/after on all four; the reference-number refusal proof;
the issuer-evidence decision; the two-issue coexistence sweep; hunks
verbatim; proofs with exit codes; commits; risks.
