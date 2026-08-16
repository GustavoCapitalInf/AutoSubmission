# Agent Handoff - RBC-CAD (batch 6, card 13 - the APPROVED RBC currency ceremony + the pinned currency surface)

Ocean reviews and merges; you never merge or push.
**Protected ceremony cell. Pinned-diff discipline; Ocean forensic review at
merge. Gustavo's approval (2026-08-16) is quoted below and is binding
verbatim. Any additional unexpected pinned movement is a HARD STOP.**

# Identity
- **Agent:** RBC-CAD - implement the ratified RBC Canada jurisdiction
  default, execute the approved 151-document / 4-pinned ceremony, and
  build the pinned currency surface that ends currency's gate-invisibility.

# Git ownership
- Base: main (carries the doctrine + the measurement packet) - Branch:
  `wave6-rbccad` - Worktree: `.claude/worktrees/mt6-rbccad`. Own:
  analysis/rbc.py (jurisdiction default + header-anchor widening),
  corpus_gate.py + the audit-CSV currency surface + pinned expectations,
  tests, W3 log (#RBCCAD). Nobody else in batch 6 owns these files.

# Read first, in order
1. docs/moneythumb-replacement/CURRENCY_DOCTRINE.md (the ratified doctrine).
2. docs/moneythumb-replacement/RBC_CURRENCY_MEASUREMENT.md (the eight-proof
   packet: your populations, evidence classes J_ISSUER/J_SERVICE/J_ACCOUNT/
   J_BRANCH, the US discriminator, the 151 enumeration, risks R1-R6).
3. PROJECT_STATUS.md + the 08-16 batch-5 entry in WAVE2_EXECUTION_LOG.md.

# THE APPROVED CEREMONY (Gustavo, verbatim scope)
A. **151-document movement APPROVED**: `statement.currency` USD -> CAD,
   "specifically under the ratified native-currency doctrine. The
   justification is affirmative jurisdiction/account evidence, not absence
   of USD wording... proven RBC Canada account/product -> CAD native
   default unless explicit document evidence establishes another currency.
   Explicit currency evidence always has precedence. The 12 genuine RBC
   USD documents must remain USD and unchanged. Any conflicting evidence
   must fail closed rather than be forced to CAD."
B. **Four pinned English RBC statements APPROVED** USD -> CAD (the DEC/JAN/
   FEB/MAR chequing statements, shas in the packet's PROOF 4), "authorized
   only if the composed-tree proof continues to show: currency is the only
   audited/published field that moves; ADB unchanged; opening/ending
   balances unchanged; transaction ledger unchanged; credits/debits
   unchanged; revenue classifications unchanged; validation outcomes
   unchanged; no unrelated pinned movement. The pinned French RBC
   statement remains unchanged."
C. **Pinned currency surface REQUIRED IN THIS CARD**: "Currency is
   analyst-visible output and must no longer be gate-invisible. Add
   currency to the trusted regression surface in the same implementation
   card. Prefer a representation that makes currency an explicit audited
   field rather than indirectly testing rendered UI text. Pin the expected
   currency for all 109 trusted statements, not only the four RBC movers,
   after verifying the existing values before establishing the baseline...
   Do not use baseline generation to bless unexplained values. Enumerate
   and review any surprising currency encountered while establishing the
   109-document surface."

# The work
1. **The jurisdiction rule** in the rbc registration, with the evidence
   hierarchy EXPLICIT in code and tests (Gustavo: required now even though
   `currency_source` provenance is deferred):
   (1) explicit statement currency evidence;
   (2) proven account/jurisdiction native default;
   (3) otherwise unknown / fail closed.
   Order of evaluation per the packet's proven shape: US-institution
   discriminator FIRST (refuses the default), wide contrary-currency
   refusal SECOND, the CONJUNCTION of the four affirmative Canadian proofs
   THIRD; never an absence inference; `$` alone establishes nothing;
   filename/folder can affect nothing (carry both counterfeit-direction
   tests THROUGH admissible_text, per PROOF 8).
2. **Header-anchor widening in the same commit** (packet R4):
   `_MAILING_HEADER_RE` widens to both `RBBDA...` and `RBPDA...` prefixes
   so explicit wording keeps precedence on the personal layout too.
3. **The pinned currency surface**: an explicit audited currency field per
   pinned document (a currency column on the balance-metrics audit CSV or
   a field in the gate's verdict pins - your call, justified; NOT rendered
   UI text). Procedure: measure the current published currency of all 109
   on the UNCHANGED base tree first; enumerate that census in your report
   (any surprise -> STOP and report before pinning it); then pin all 109
   with exactly four intentional CAD entries for the RBC movers (the
   French RBC doc pins at its existing CAD). The gate goes RED on any
   future currency movement.
4. **Tests, at minimum (Gustavo's list, verbatim)**: proven RBC Canada +
   no contrary evidence -> CAD; proven RBC Canada + explicit U.S. Funds/
   USD evidence -> USD; RBC U.S. product -> Canadian default refused;
   hostile/mixed evidence -> fail closed; filename/folder placement cannot
   affect currency; `$` symbol alone cannot establish USD; the nine
   batch-5 CURRENCY-1 explicit-evidence corrections remain unchanged
   (named by sha in the packet's PROOF 7).
5. **Zero-activity RBC doc** `BFEB79B26E426C2FDA63DF0C1F422D95F4A8AF95319C03ADCA85D9560B6E58A3`:
   keep as the NAMED future mover; "do not weaken parser admission merely
   to include it" - a test or W3 note records it so its eventual movement
   is expected, not surprising.
6. `currency_source` provenance: NOT in this card (batch 7, additive).

# Expected archive movement (name every one)
Exactly the 151 shas of the packet's ceremony enumeration change
`statement.currency` USD -> CAD and NOTHING else - no amount, ADB, ledger,
classification, flag, note, risk, or outcome moves anywhere. The 12
explicit-USD stay USD; the 6 stated-CAD stay CAD; the 20 French stay CAD
byte-identical; the 9 CURRENCY-1 corrections byte-identical; the 16
no-artifact documents' terminal outcomes byte-identical. Reproduce the
packet's differential method (payload leaf-diff over the 236-doc set) on
YOUR implementation - the prototype's numbers do not transfer.

# Ceremony proof floor (cell-level; Gustavo's list minus the train items)
Full suite green; corpus-marked slice green; `python corpus_gate.py` GREEN
WITH the newly pinned currency surface live (106/3, verdicts 102/4/3,
currency pins all green); the exact enumeration of the four intentional
pinned movements in your report; the archive differential proving exactly
151 currency changes and zero unexpected financial/verdict movement; exit
codes verbatim. Ocean owns at the train: push, remote CI conclusion read,
the composed ANALYSIS_STAGE_VERSION bump, the authoritative cold run, and
the instrument vs `2e3ea385` with --fail-on-regression. This ceremony does
not alter the official batch-5 historical record - it is batch-6 work
measured against the batch-5 run of record.

# Standing wave rules (binding)
Base main (v13, OCR v3, registry 72, suite 4,511, corpus-marked 27). Run
of record: `discovery_reports/2026-08-16T000943.012887-0000-2e3ea385`
(validated 2,430 / review 15 / withheld 63 / failed 859 / deferred 13;
3,380 distinct shas). Archive + caches READ-ONLY; OCR artifacts by DIRECT
file path only (never the webapp_data sqlite index); $0 vendor; private
uniquely-named scratchpad subdir. Long background shells get killed - run
long proofs as SEQUENTIAL single commands; detached-process aliveness via
`tasklist`, never MSYS `kill -0`. Family populations by live detection
replay or artifact-store enumeration, NEVER rows.csv parser_id alone.
Guards + conformance cross-product (72x71). Exit codes verbatim; every
mover named by content_sha256 + field; claimed != validated; zero movement
outside the named populations; commit incrementally, clean tree; NEVER
merge or push - Ocean runs the train. ANALYSIS_STAGE_VERSION bump is
Ocean's at merge. Fail-closed everywhere. Machine shared with other cells.

# Final report to Ocean
The ceremony enumeration first (four pinned diffs); the 109-currency
census with any surprises flagged BEFORE pinning; the 151-differential
reproduction on the real implementation; the seven-test family; the
hierarchy-in-code demonstration; hunks verbatim; proofs with exit codes;
commits; risks.
