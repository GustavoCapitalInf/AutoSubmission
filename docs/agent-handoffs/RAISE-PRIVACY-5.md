# Agent Handoff — RAISE-PRIVACY-5 (batch 9, 9A-0 card 2b, hygiene, ZERO coverage movement)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Identity
The RAISE-PRIVACY-4 review (`reviews/BATCH9_RAISEPRIV4_REVIEW.md`, APPROVE WITH FINDINGS)
confirmed one document-reachable echo the cell disclosed and did not close: `analysis/td_can.py`
`_parse_period`'s `_MONTHS[sm]` / `_MONTHS[em]` raise `KeyError('<the printed word>')` on a
three-letter token that is not a month (and `_native_date_to_iso`'s `_MONTHS[...]`, which is
caller-guarded today). It echoes identically at base and tip. The reviewer showed it IS
closable class-preserving: `_MONTHS.get(...)` and a fixed-text `KeyError` raised OUTSIDE any
handler (no `from exc`, no implicit `__context__`), so the raised class, the outcome and every
published field stay exactly as they are and only the message stops carrying the token. No
census in this tree reports subscripts — add one.

# Also in scope (the review's MINORs on the composed train, all non-behavioural)
`tests/test_raise_privacy4.py:237` says "sixteen" where `len(CELLS)` is nineteen; the raw-`date()`
census claim is wider than its AST coverage (module scope / lambdas) — widen the census or
narrow the claim; the "no decimal digit at all" assertion is stronger than `_refusal_class`
guarantees — assert what the class guarantees.

# Rules
Refusal semantics preserved exactly (same class, same outcome, same fields; the only change
is the message); no new refusal, no new acceptance; the reader-name rule and the
`date_refusal` `CHAIN_GUARDED` registration for `td_can` survive; every fixture invented.

# Proofs
Both-tree drive (base echoes the token in `str`/`repr`/`args`/traceback; tip does not; class
identical); a structural census for subscript lookups on parsed tokens in the three
RAISE-PRIVACY modules (`_MONTHS[...]`-shaped) registered like the `date()` census; one mutant
reverting to the raw subscript, killed by the drive; `cohort_replay --parser td_canada_native
--parser td_canada --group WH:td_us --expect-identical` at base and at tip (73/73 identical);
privacy scan of added lines (0); canonical guards + conformance; the corpus gate; the suite.

# Git ownership
Base `train9` at launch (after 9A-0 composes). Branch `wave9-raisepriv5`, worktree
`.claude/worktrees/mt9-raisepriv5`. Own: `analysis/td_can.py` (the named lines),
`tests/test_raise_privacy4.py`, `tests/test_privacy3_boundaries.py` (the census),
`tools/raisepriv5_*.py`, W3 `§RAISEPRIV5` (append-only).

# Report
BATCH9-RULES contract; newly validated 0, preserved 73/73 identical, regressions 0.
