# Agent Handoff — FIXTURE-PRIVACY-2 (batch 9, 9A-0 card 1b, P0 hygiene continued, ZERO coverage movement)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Identity
FIXTURE-PRIVACY (card 1, `wave9-fixpriv`) moved the adjudication of archive tokens INTO the
scanner (seven shape rules, per-rule counts, `fixpriv_invent --scale-search`,
`fixpriv_ast_identity`, a mutation harness) and cleared six files — the worked example is
`tests/test_lili.py` 138 → 0 by an exact ×428 cents scale. It did NOT clear the P0 item:
`tests/test_analysis.py` carries 822 residue sites INCLUDING a real account number, and
`tests/` overall carries ≈ 4,032 sites in ≈ 140 files. This card finishes the tests sweep with
the proven technique, file by file, the real-account-number file FIRST, and widens the
scanner to the tracked text it has never audited.

# Goal (definition of done)
1. `tests/test_analysis.py` → 0 residue (the real account number gone first, in its own
   commit, with the test's meaning shown intact).
2. Every other `tests/*.py` file → 0 residue, or a named, class-based reason it stays
   (`tests/corpus_cache/` is archive text by design and stays excluded by rule).
3. `tools/privacy_scan_branch.py` `TEXT_SUFFIXES` widened to `.log`, `.shas`, `.ps1`, `.csv`
   (the three `docs/*-audit-results.csv` truth files are reported as their own class,
   `benchmark_truth_csv`, excluded ONLY if Gustavo's ruling R3 says so — until then they are
   COUNTED and named; `discovery_v12_run.log` / `.err.log` at the root are tracked and have
   never been scanned: report them and clear or delete-with-reason).
4. Whole-tree scan before / after, counts by class × directory; no file gains residue; no new
   token; the exclusion table unchanged unless a new rule is a SHAPE with tests and a
   mutation entry.

# Method
- Per test file: `fixpriv_invent` classifies every candidate replacement against the universe
  and `--scale-search` finds an exact integer scale on cents where the fixture is a closed
  arithmetic system; where it is not (ids, dates, masks), replace with the invented-shape
  convention (2031 dates; ids that the scan proves do not collide) and show each assertion
  still tests the same relation. A fixture change that changes a test's meaning is a
  finding, not a fix — stop and say so.
- Zero movement: `fixpriv_ast_identity` over any touched production module (there should be
  none); the full suite; canonical guards + conformance; the corpus gate; `cohort_replay
  --expect-identical` is not needed unless production changes (then it is).
- Ownership: `tests/` (all except `tests/test_privacy3_boundaries.py` and
  `tests/test_raise_privacy4.py` if RAISE-PRIVACY-4 is not yet composed — Ocean says at
  launch), `tools/privacy_scan_branch.py` (suffix widening + the truth-csv class),
  `tools/fixpriv_*.py`, the two root logs (delete with reason or scrub), W3 `§FIXPRIV2`
  (append-only). No production code; no docs redaction (that is Ocean's on the train, per
  ruling R2).

# Report
BATCH9-RULES contract: population (files × sites before/after by class), root cause,
solution, newly validated 0, other movement 0, preserved = all (suite + gate), regressions
0, correctness evidence (test-meaning check per file, AST identity), generalization evidence
(the technique, the widened scanner); commits; proof-floor exits; the final scan count; risks.
