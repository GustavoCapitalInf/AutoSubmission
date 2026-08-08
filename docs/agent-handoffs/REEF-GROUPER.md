# Agent Handoff — REEF-GROUPER

Complete self-contained brief; read fully before acting. Ocean reviews and
merges; you never merge or push.

# Identity
- **Agent:** REEF-GROUPER · row-grouper promotion (Wave 3, Ocean ruling 2 of 2026-08-08)
- **Task:** promote the row-grouping capability proven in Chase/TD/RBC into `analysis/tables.py` as a shared primitive.

# Git ownership
- **Base:** `e614fcc` · **Branch:** `wave3-grouper-promotion` · **Worktree:** `.claude/worktrees/mt-grouper` (you are inside it). Commit only to this branch; never merge to main; never push.

# Context
Read in-tree: `WAVE2_EXECUTION_LOG.md` (2026-08-08 entry — your ruling and its constraints), `W3_TRACKA_LOG.md` §1 (Chase grouper), §TD, §5 (RBC — esp. §5.7's promotable-form finding). The three parsers now carry three sibling implementations of row grouping. The approved generalized rule set:
1. a row starts at a date-shaped token opening a physical line;
2. wrapped lines continue the row;
3. **a lone money cell is an amount; adjacent money cells are (amount, balance) in printed column order** — this degrades exactly to Chase's rightmost-cell rule on layouts without a balance column.
Explicitly NOT in scope (Ocean ruling 1): the balance-based sign/direction solvers (TD subset-split, RBC chain walk) stay parser-local.

# Scope
- **Allowed:** `analysis/tables.py` (the new primitive), `analysis/chase.py`, `analysis/td_can.py`, `analysis/rbc.py` (refactor onto the primitive — mechanical consumption, no behavior change), their test modules + a new `tests/test_row_grouping.py`, `W3_TRACKA_LOG.md` (append §GROUPER record).
- **Protected:** everything else — money.py/date_tokens.py behavior, all other parsers, pipeline/registry, financial core, ocr/, webapp/, discovery/, telemetry/, corpus assets, audit CSVs.

# Engineering requirements
- **This is a pure refactor with the R-2 differential-equivalence standard:** for EACH of the three parsers, freeze the current grouping behavior as an oracle and prove the promoted primitive produces identical groupings over an adversarial input matrix (Chase shapes incl. its 12 §1 families; TD dual-column shapes; RBC three-money-cell/French shapes; plus the negative fixtures already in their suites). Each parser's fail-closed behavior preserved exactly.
- Zero statement-specific constants; guards green.
- Corpus gate must be **byte-identical** — this change may not move any output of any document.
- No stage-version bump needed IF truly byte-identical on all outputs (state this verification in your report; if ANY archive document's output would change, STOP — that means the refactor is not pure and needs Ocean review).

# Validation
- Differential oracle tests per parser; full default suite; `set -o pipefail; python -m pytest -m corpus -q` green; `python corpus_gate.py` GREEN byte-identical. Exit codes pasted verbatim.
- Read-only archive spot-verification: re-run ≥30 documents per family (Chase/TD/RBC validated sets) through `analyze_markdown` and assert identical payloads before/after (hash comparison).

# Stop conditions
Any behavioral divergence the differential proof cannot eliminate; any temptation to "improve" grouping while moving it (report the idea, don't do it); any parser outside the three needing edits; anything touching the sign solvers.

# Definition of done
One primitive in tables.py; three parsers consuming it; all differential proofs + suite + corpus-marked + gate green; archive spot-verification clean; §GROUPER log record; clean tree at final commit.

# Final report to Ocean
Primitive API; per-parser refactor summary; differential-proof description + results; verbatim proof tails with exit codes; archive spot-verification result; commit list; risks; unresolved questions.
