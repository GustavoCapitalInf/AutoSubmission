# Agent Handoff - WOODFOREST-INIT (batch 4, card 3)
Ocean reviews and merges; you never merge or push.
**Narrow ruling (Gustavo 2026-08-14, verbatim constraints): do NOT create
a generic rule permitting transactions outside a statement period. Design
a narrow account-opening/initial-funding exception. A pre-period
transaction may be treated as an INITIALIZATION EVENT only when printed
statement evidence supports that interpretation and the ledger
independently confirms it. If those conditions cannot be proven
generically from the document, keep the two statements withheld. No
customer/date/amount-specific exception.**

# Identity
- **Agent:** WOODFOREST-INIT - the two Woodforest mid-cycle account
  openings (W3 #UNID-A UA4.1): opening deposit posts the day before the
  printed period, every printed total matches the ledger exactly,
  withheld today by the transactions_within_period requirement.

# Git ownership
- Base: main `ea8d8e8` - Branch: `wave4-wfinit` - Worktree:
  `.claude/worktrees/mt4-wfinit`. Own: analysis/woodforest.py, tests,
  W3 log (#WFINIT). If the mechanism REQUIRES touching analysis/adb.py
  (protected, MASTER_PLAN 4): STOP after characterization, report the
  minimal pinned diff you would make, and wait for Ocean's ruling before
  editing it. Prefer a design that does not touch it.

# Required evidence gates (ALL, from the ruling)
1. the transaction is associated with account opening / initial funding
   BY PRINTED EVIDENCE (characterize what the two documents actually
   print: opening-deposit wording? BALANCE FORWARD 0.00? first-statement
   furniture? - report the printed shape verbatim);
2. it occurs immediately before the printed activity period;
3. it is REQUIRED to establish the statement's opening balance or first
   printed balance checkpoint (the ledger does not close without it);
4. the full ledger then reconciles exactly;
5. stated totals/counts remain independently satisfied;
6. NO unrelated out-of-period transaction is admitted (adversarial
   fixture: a stray dated row outside the period that is NOT the
   initialization event must still withhold).
Treat the event as initialization CONTEXT, not an ordinary in-period
transaction - characterize what that means for published fields (does it
enter transactions? period? ADB day-count? State the design and its
consequences BEFORE implementing; the ADB basis must remain the printed
period).

# Hard rules
The other 18 Woodforest docs byte-identical (full family sweep). If the
generic evidence gates cannot be met on BOTH documents, ship the
characterization + fixtures proving the gates fail closed, keep them
withheld, and say so - that is a valid, complete outcome.

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-14 batch-3 entry in WAVE2_EXECUTION_LOG.md
first. Base main `ea8d8e8` (v11, registry 68, suite 3,769). Run of record:
`discovery_reports/2026-08-14T214345.671986-0000-d5c75ff6` (validated 2,357 /
review 22 / withheld 69 / failed 919 / deferred 13; 3,380 distinct shas).
Archive + caches READ-ONLY; OCR artifacts by DIRECT file path only (never
open the webapp_data sqlite index - it writes on read); $0 vendor spend;
private uniquely-named scratchpad subdir (cells have collided on the shared
top level). Long background shells get killed - run long proofs as
SEQUENTIAL single commands. Proof floor per branch: full default suite +
corpus-marked slice (MANDATORY - the corpus gate is structurally blind to
review<->validated movement inside its PASS bucket; proven in batch 3) +
`python corpus_gate.py` GREEN 106/3 + guards + conformance cross-product;
exit codes verbatim; every mover named by content_sha256 + outcome + field;
claimed != validated; zero movement outside your named populations; commit
incrementally with clean tree at the end; NEVER merge or push - Ocean runs
the train. ANALYSIS_STAGE_VERSION bump is Ocean's at merge. Fail-closed
everywhere: a document you cannot prove publishes nothing.

# Final report to Ocean
Printed-evidence characterization first; design + consequences; diffs;
family sweep; proofs; commits; risks.
