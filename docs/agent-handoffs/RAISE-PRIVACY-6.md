# Agent Handoff — RAISE-PRIVACY-6 (batch 9, hygiene PROPOSAL — needs Gustavo's ruling before launch)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Why (the RAISE-PRIVACY-5 review's ruling question)
The three censuses that now guard "what this tree RAISES must not quote the printed cell" —
the raw-`date()` census, the money/date refusal-constructor census (`CHAIN_GUARDED`) and the
new LOOKUP census (§4c) — cover THREE NAMED READERS (`bmo`, `farmers_merchants`, `td_can`)
plus the RAISE-PRIVACY-3 modules for the constructor rule. A `_MONTHS`-shaped subscript, a raw
`date(...)` from parsed components or an echoing `KeyError` in any OTHER reader is uncovered
today. The RP-5 review also found the LOOKUP census's allowlist is keyed to the LINE, not to
the guard that makes the site safe (deleting `if mon not in _MONTHS: continue` still passes
the census; only a mutant and its drives catch it), and that four measured lookup shapes
(a local alias, `operator.getitem`, `__getitem__`, a helper outside the census modules) are
reported only by drives at existing sites.

# Proposal (ruling wanted)
1. Graduate all three censuses from "three named readers" to **every module in
   `CHAIN_GUARDED`** (and measure what a whole-`analysis/` sweep would report, as a table —
   count, don't fix — so Gustavo can decide whether the census population is the guarded
   set or the whole package).
2. Make the lookup allowlist GUARD-AWARE: an allowlisted subscript is accepted only while
   the census can see its guard (`if <key> not in <table>` / `.get`) in the same function.
3. Report the four measured shapes, with the same allowlist discipline.
Each step: both-tree drives for every newly reported site (base echoes → tip refuses,
class-preserving, no new refusal, no new acceptance), one mutant per site, `cohort_replay
--parser` for every registration of every touched module (preserved, identical), privacy and
message scans 0, guards, conformance, gate, suite. Zero coverage movement.

# Git ownership (if ruled)
Base `train9` at launch. Branch `wave9-raisepriv6`, worktree `.claude/worktrees/mt9-raisepriv6`.
Own: the named raise/lookup sites in the modules the census reports (a list fixed at launch),
`tests/test_privacy3_boundaries.py`, `tests/test_raise_privacy6.py`, `tools/raisepriv6_*.py`,
W3 `§RAISEPRIV6`.
