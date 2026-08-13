# Agent Handoff — BOFA-COUNTS

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the 2026-08-13 coverage wave. **Priority 1: this is the
wave's only wrong-data-while-trusted card.**

# Identity
- **Agent:** BOFA-COUNTS · make bank_of_america's three summary readers
  agree on one DOCUMENTED per-layout scope for the stated debit count.

# Git ownership
- **Base:** current main (record the SHA) · **Branch:** `wave3-bofa-counts`
  · **Worktree:** `.claude/worktrees/mt-bofa`.

# The defect (measured, COUNTS_P1_MEASUREMENT.md §3.1 — read it first)
BofA prints `# of withdrawals/debits` and separately `Total # of checks`;
the Checks section's rows are captured as debits. Three readers disagree
about what `stated_debit_count` means: native summary (`analysis/bofa.py`
≈:391-393) and table summary (≈:515-516) store the RAW printed figure; the
repair path (≈:589) stores `debit_count + (check_count or 0)`. The payload
does not record which ran. Counterfactuals over 344 debit-count-printing
docs: raw ⇒ 237 match / 107 mismatch; `+check_count` ⇒ 153 / 191. One
bank, one field, two meanings — on ~360 trusted documents.

# Requirements
1. **Characterize BEFORE code** from real documents (archive/cache
   read-only): per LAYOUT (native-summary docs vs table-summary docs vs
   repair-path docs), does that layout's printed `# of withdrawals/debits`
   include cheques or not? Prove it per layout with printed evidence
   (column sums, the checks section's own printed count/total, running
   balance) on a stated sample size. The answer may differ by layout —
   that is allowed and must be documented per reader.
2. **Align each reader with what ITS layout actually prints.** The
   expected side is INDEPENDENT printed evidence only: combining two
   PRINTED figures (debits + checks counts) is legitimate; deriving the
   expected side from captured rows is FORBIDDEN (the D5 independence
   rule). Record which reader ran if that is needed to make the field's
   meaning stable — as data, not behavior change.
3. **count_semantics:** `bank_of_america:debit` is currently incomparable
   (`cheques_excluded_from_printed_debits`). If your fix makes the
   semantics provably comparable, flip the entry WITH a fresh counterfactual
   measured over all BofA docs at your tree (expect ≈344 match / ~0
   mismatch; every remaining mismatch individually explained), update the
   pinned equality test as the deliberate act it is designed to be, and
   write provenance + falsifier in the first_community entry's idiom. If
   not proven for any reader/layout, leave that scope incomparable with
   updated provenance. A flip that would manufacture validated→review
   movers is a STOP, not a flip.
4. **Zero outcome movement expected.** Stated counts gate nothing except
   the (currently silent for bofa) flags; reconciliation math untouched.
   Before/after over ALL ~360 claimed BofA docs: outcome class, reason,
   flags, every field byte-identical EXCEPT `stated_debit_count` (and its
   two recon count fields) where the scope correction legitimately changes
   the value. Any other field moving = defect in your change.
5. **Pinned corpus:** 6 BofA pinned PASS docs. Audit CSVs carry no
   per-direction count column, so the gate should stay GREEN byte-identical
   — prove it; if ANY audited field moves, STOP (ceremony is Gustavo's).
6. Synthetic fixtures per reader/layout incl. the cheques-folded and
   cheques-separate shapes, and a zero-checks statement.

# Scope
- **Allowed:** `analysis/bofa.py`, `analysis/count_semantics.py`
  (bank_of_america entries only), tests (`tests/test_bofa_variants.py`
  additions; `tests/test_count_semantics.py` ONLY the deliberate pinned-set
  edit + its provenance test), `W3_TRACKA_LOG.md` (append §BOFA-COUNTS).
- **Protected:** everything else. reconcile/pipeline/telemetry are NOT
  yours — the flag machinery is already correct; you are fixing what the
  parser feeds it. Archive read-only; $0 vendor.

# Validation
Full default suite; corpus-marked; `corpus_gate.py` GREEN 106/3
byte-identical; guards; conformance cross-product zero; the 360-doc sweep
(req 4); the fresh counterfactual (req 3). Exit codes verbatim.
ANALYSIS_STAGE_VERSION bump is Ocean's at merge.

# Stop conditions
Any audited field moving on pinned docs; any validated→review mover in
your preview; expected-side derivation from captured rows; needs outside
Allowed; layout evidence too thin to prove a scope (leave incomparable and
say so).

# Final report to Ocean
Per-layout characterization table with printed evidence first; verbatim
diffs; the 360-doc field-level sweep summary; fresh counterfactual; flip
decision + provenance; proofs with exit codes; commit list; risks;
unresolved questions.
