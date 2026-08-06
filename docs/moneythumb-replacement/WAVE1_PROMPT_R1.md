# Wave 1 — Agent A Implementation Prompt: R-1 Statement-Specific Hardcode Purge

Issued by Ocean (Lead Architect), 2026-08-06. H-2 is completed, reviewed, and
APPROVED (commits a6a045e..6ac3945). R-1 is now authorized. You remain Agent A.
This is the wave's highest-priority and highest-risk task — work deliberately.

## Where you work

- Same worktree (`mt-benchmark`), same branch `wave1-benchmark-parsers`, building on
  top of your H-2 commits. Commit prefix changes to `R-1:` (Ocean merges the H-2
  boundary separately; wave merge order H-2 → D-1 → R-1 → O-1 is unchanged).
- Python: `C:/Python314/python.exe`. Corpus gate: `C:/Python314/python.exe corpus_gate.py`.
- Commit incrementally — one commit per inventory item (or small coherent group) so
  any item can be reverted alone.

## Objective

Eliminate every statement-, customer-, date-, amount-, and year-specific constant
from parsers and repairs. A repair survives only as a generic, evidence-based,
regression-tested rule. Anything that cannot be defensibly generalized converts the
affected result to explicit review/withholding — NEVER fabricated correctness. The
corpus gate stays GREEN throughout (see the status-change protocol below — you never
re-baseline on your own).

## The inventory (work through ALL 12; log each in R1_HARDCODE_LOG.md)

1. `analysis/scanned_small_bank.py:300-321` — repair keyed to literal date
   "2026-06-18" + "Check 1944" + amount −4500.00→−1500.00.
2. `analysis/scanned_small_bank.py:214-216, 338` — literal holders "THE GRANITE
   GIRLS, LLC", "KLR ENTERPRISES" as parser gates.
3. `analysis/scanned_small_bank.py:418-419` — `len(txns) < 20` magic threshold.
4. `analysis/community_section.py:29` — literal "GREEN CONVERGENCE" / "FIELD
   TRUCKING LLC" scrub list.
5. `analysis/community_section.py:226` — Dakota West gate on literal account
   `35127380`.
6. `analysis/bank_repairs.py:115-134` — Chase repair firing only on exactly
   −1000.00 with a 1000–2000 Remote Online Deposit.
7. `analysis/rbc.py:47-64` — counterparties "FUNDIFI CANADA", "2313833 ONTARIO"
   inside sign heuristics; `:235-241, 288-291` — French parser Dec/Jan-only,
   hardcoded period start, default years (2025, 2026); `:246` mojibake regex.
8. `analysis/td_can.py:153-174` — merchant-name sign lists (DANNY, PIZZ, PHO,
   FRESHCO, CASH 4 YOU, LIGHTSPEED, CANACAP CLN).
9. `analysis/wells.py:20-22` — `_infer_year` defaulting to 2026.
10. `analysis/wilson_muir.py:152` — `days_in_period=30` guess.
11. Mojibake regexes: `scanned_small_bank.py:146, 211` (+ rbc item 7) — normalize
    encoding first, match real characters.
12. Registry counterparty entries: (a) PRE-APPROVED BY OCEAN — ADD as confirmed
    lenders with fixture tests: "AFC FUNDING CORP" (aliases incl. "AFC FUNDING CORP
    XPRESS PAY") and "INTUIT FINANCING" (aliases incl. "INTUIT FINANCING QBC_PMTS";
    must NOT match ordinary Intuit/QuickBooks software charges — your H-2 evidence:
    the $37.10 QBooks purchase must stay non-lender). (b) PROPOSE-ONLY — do NOT
    change without a ruling: disposition for `classification_registry.py:143`
    ("11-101 Signal R" as operating source), `:42` ("3329001101"), `:33-34`
    ("MC 844 662 3467"). Put your analysis and recommendation per entry in the
    handoff; Ocean rules.

Remediation menu, in preference order:
(a) generalize into an evidence-gated rule (year inference from statement period
    metadata; sign resolution from printed balances via the existing solver;
    scrub/repair rules driven by structural markers, not names or exact values);
(b) move genuine counterparty knowledge into the registry WITH fixture tests, per
    the documented contract in docs/transaction-classification.md;
(c) fail closed — the affected statement becomes review/withheld, with an evidence
    dossier (see status-change protocol).

## Status-change protocol (hard rule)

Target: zero corpus outcome changes. If a remediation turns the gate red and the
honest resolution appears to be a status change (a memorized-constant "pass"
becoming review/withheld), you do NOT regenerate the audit CSVs and do NOT touch
`corpus_gate.py` expectations. Instead: revert that item's change on the branch,
record the full proposal (what the hardcode did, why it cannot be generalized, what
the honest status would be, evidence) in R1_HARDCODE_LOG.md and your handoff, and
continue with the other items. Ocean will rule on each proposal; approved
re-baselines happen as a separate deliberate act after your handoff. An unexplained
red gate is a stop-the-line event: stop and report rather than iterating blindly.

## H-2 baselines you must not regress (your own audited evidence)

- KLR / `scanned_small_bank` (audited PASS): Apex Bank, 2026-05-01→31, opening
  14,341.03 → ending 1,388.55, ADB 2,785.53, 81 transactions, NSF 1, SBA 1×1,116.00.
- Field Trucking / `community_section` (audited PASS except no regression allowed
  anywhere): lenders Everest/EBF 20×11,166.60, Eminent 17×6,374.36, CFG 3×5,025.00,
  Affirm 1×549.62, SNAP Finance potential 8×246.28.
- The corpus gate enforces every other audited field; run it after every 2-3 items,
  not only at the end.

## File allowlist (exhaustive — nothing else)

1. `analysis/scanned_small_bank.py`, `analysis/community_section.py`,
   `analysis/bank_repairs.py`, `analysis/rbc.py`, `analysis/td_can.py`,
   `analysis/wells.py`, `analysis/wilson_muir.py`
2. `analysis/classification_registry.py` — ONLY the two pre-approved entries (item
   12a); nothing else
3. `tests/test_analysis.py` and/or new test modules `tests/test_r1_*.py` — fixture
   tests per remediation (positive AND negative: the generalized rule fires on
   structural evidence, not on the memorized instance) + the two registry fixtures
4. New `tests/test_no_statement_hardcodes.py` — the guard test: scans the seven
   parser files (and `bank_repairs.py`) for the removed literals and for
   forbidden-pattern classes (4-digit-year constants outside date-parsing context,
   literal customer names — maintain the list in the test) and fails on
   reintroduction
5. New `docs/moneythumb-replacement/R1_HARDCODE_LOG.md` — one entry per inventory
   item: what it was, ruling (generalized / registry / fail-closed-proposed /
   kept-with-justification), evidence, tests added
6. `README.md` — only if run instructions change (unlikely)

## Protected (do not touch; stop-and-ask via your handoff)

Everything else. Explicitly: `analysis/adb.py`, `reconcile.py`, `metrics.py`,
`transaction_classifier.py` (code — registry data file is item 12 only),
`serialization.py`, `analysis/pipeline.py` (orchestrator cleanup is R-8, a later
wave), ALL other parsers, `ocr/`, `webapp/`, `benchmark/` (your own H-2 code is
frozen during R-1 except a bugfix commit clearly labeled `H-2-fix:` if you find a
harness defect), corpus PDFs, both audit CSVs, `corpus_gate.py`, audit scripts,
`tests/corpus_cache/`, `conftest.py`, `pytest.ini`, `.github/`.

## Acceptance criteria

1. All 12 inventory items dispositioned and logged; zero literal customer names,
   account numbers, single dates, exact amounts, or hardcoded years remain in the
   seven files (guard test proves it and prevents reintroduction).
2. Corpus gate GREEN with ZERO outcome changes (109/109, 106/3, field-identical) —
   status-change proposals, if any, are queued per the protocol, not applied.
3. Every remediation has positive + negative fixture tests.
4. The two pre-approved registry entries added with fixtures (incl. the Intuit
   software-purchase negative case); the three propose-only entries analyzed in the
   handoff with recommendations, untouched in code.
5. Full default suite green. H-2 harness re-run afterwards: attach the new rollup
   and call out any comparison deltas for KLR / Field Trucking / the Chase sets
   (expected: none, or strictly-better).
6. R1_HARDCODE_LOG.md complete.

## Commit / handoff / conduct

Commits only on `wave1-benchmark-parsers`, prefix `R-1:` (one item or small group
per commit), Co-Authored-By trailer, NEVER merge or push, stop-and-ask (in the
handoff) for any non-allowlisted file. Handoff report: commit list; per-item
disposition table (item → ruling → mechanism → tests); guard-test description;
corpus-gate tail (final run); full-suite tail; H-2 re-run rollup + deltas; the
three registry proposals with recommendations; any fail-closed proposals queued
under the status-change protocol; deviations/questions. Do not start any other
task. This completes your Wave 1 track.
