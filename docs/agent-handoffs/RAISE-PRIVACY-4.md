# Agent Handoff — RAISE-PRIVACY-4 (batch 9, 9A-0 card 2, hygiene, ZERO coverage movement)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Identity
The base-inherited `date()` call sites that ECHO a printed token when they raise, carried
from HYGIENE-8a: W3 §HYGIENE8 H14 ruled "the eight carried echoing sites are base-inherited,
reach no user-facing surface (the dispatch seam reduces a crash to its class;
`worker._stage_failure` withholds messages) and the census now guards against a ninth →
batch-9 card RAISE-PRIVACY-4 (three readers, the same funnel, the same drive)". Candidate
sites at `3311a8a` (census them — reconcile with H14's count of eight and explain any
difference): `analysis/bmo.py:70,71` (period bounds) and `:194` (transaction date);
`analysis/farmers_merchants.py:57,58` (period); `analysis/td_can.py:128,129` (period),
`:142` (a dates list), `:161` (`_native_date_to_iso`). A raw `date(year, month, day)` with an
out-of-range component raises `ValueError("day is out of range for month")` or, on Python
3.13+, a message that echoes the offending number; a huge year raises `OverflowError`. The
law: what this tree RAISES must not quote the printed cell.

# Precedent to copy (HYGIENE-8a closure, `wave8-hygiene8`)
`548e518` — the four remaining `date()` sites of the site-6 class funnelled through
`date_tokens` and refusing without the token; `c7a42c9` — one mutant per site, each reverting
it to the raw `date(...)` call, each killed by the drive; `f825a97` — every invented fixture
date on the 2031 convention; `1b2a2c1` / `063e877` — W3 §H14: the four sites driven on BOTH
trees (base echoes on `str` / `repr` / `args` / traceback / notes; branch refuses without the
token), the implicit-conversion census, the proof floor at the closure tree. The funnel is
`analysis/date_tokens.py`: `iso_or_none`, `iso_from_month_day`, `iso_from_month_day_strict`,
`iso_from_month_day_year`, `iso_from_named_month_day`, `parsed_datetime`, `date_refusal(reader,
token)`; `tests/test_privacy3_boundaries.py::CHAIN_GUARDED` already lists the three modules
with their declared refusal constructors.

# Rules of the reroute
- Refusal SEMANTICS are preserved exactly: a site that returned `None` keeps returning
  `None` on the same inputs; a site that raised keeps raising on the same inputs, now as
  `date_refusal(...)` (a `ValueError` whose message names the reader and a refusal CLASS and
  never the token); a site that let `OverflowError` escape follows the contract HYGIENE-8a
  closed (`c455de7`). No NEW refusal where none existed and no new acceptance — either would
  move outcomes, and this card moves none.
- No statement-specific constants; no registry change; no version bump; nothing outside the
  named lines and their imports.

# Proofs
1. **Structural census** in `tests/test_privacy3_boundaries.py`: extend the existing
   `date()` census so a raw `date(` / `datetime(` construction from parsed components in
   these three modules fails the guard (the ninth site H14 warned about); keep
   `CHAIN_GUARDED` truthful.
2. **Poisoned drives** through the real callables, `tests/test_raise_privacy4.py`: month /
   day / year out of range, junk, superscript digits (`str.isdigit()` admits them), huge
   years → the refusal carries no token on `str` / `repr` / `args` / `__notes__` / the rendered
   traceback; the same drives at BASE show the echo (record the base behaviour in the W3
   table, never the token).
3. **Mutation table** `tools/raisepriv4_mutation_table.py`: one mutant per site reverting it
   to the raw call; run WITHOUT `-x`; every killer named; harness restores with
   `git checkout --` on a CLEAN tree.
4. **Zero movement** with the committed instrument: `python -m tools.cohort_replay --parser
   bmo`, `--parser farmers_merchants`, `--parser td_canada --parser td_canada_native`, and
   `--group WH:bmo --group WH:farmers_merchants --group DECL:bmo_ca_business --group WH:td_us`
   at BASE with `--expect-identical` (fidelity) and at your tip: preserved = all, payload
   identical = all, every non-validated member unchanged with an identical payload.
5. **Privacy scan** of your added lines against the three readers' populations:
   `python tools/privacy_scan_branch.py --rows <run>/rows.csv --where
   parser_id=bmo,farmers_merchants,td_canada,td_canada_native --data-dir
   .claude/recovery/webapp_data_train8_cold --base <base> --ref wave9-raisepriv4` → 0.
6. Canonical guards + conformance + full suite at your tip (exit codes verbatim).

# Git ownership
Base `train9` at this handoff's commit. Branch `wave9-raisepriv4`, worktree
`.claude/worktrees/mt9-raisepriv4`. Own: `analysis/bmo.py`, `analysis/farmers_merchants.py`,
`analysis/td_can.py` (the named lines and their imports only), `tests/test_privacy3_boundaries.py`,
`tests/test_raise_privacy4.py` (new), `tools/raisepriv4_*.py`, W3 `§RAISEPRIV4` (append-only).
Touch NOTHING else — FIXTURE-PRIVACY sweeps `tests/` and `docs/` concurrently and owns every
other test file. The WH-ROW-CAPTURE (bmo) and WH-NO-PERIOD (farmers_merchants) coverage cells
start only after this card composes, so the readers' logic is yours alone for now — and you
change none of it.

# Report
W3 section `§RAISEPRIV4` and the final message, in the BATCH9-RULES contract: population
(the sites, with the H14 reconciliation), root cause, solution, newly validated = 0, other
ladder movement = 0, previously validated preserved = all (replay numbers per reader),
regressions = 0, correctness evidence (both-tree drive table, mutation table), generalization
evidence (the census guard); commits; proof-floor exits; privacy count; risks last.
