# Agent Handoff — DISPATCH-REPORTING

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the 2026-08-13 coverage wave. Small, surgical, high-honesty
card: the discovery report collapses "a parser claimed this and declined"
into "no parser matched", hiding the wave's richest work queue.

# Identity
- **Agent:** DISPATCH-REPORTING · project `Dispatch.attempted` into
  discovery rows and split the failure-reason vocabulary.

# Git ownership
- **Base:** current main (record the SHA) · **Branch:**
  `wave3-dispatch-reporting` · **Worktree:** `.claude/worktrees/mt-dispatch`.

# The defect (scout-evidenced, three scouts independently)
`analysis/parser_registry.py:544-573` computes `Dispatch.attempted`
("Declined, rather than broke" — its own docstring calls the or-chain
invisibility a defect signal) and `telemetry/record.py:210` records it —
but `discovery/runner.py` never reads it: `:468-477` copies outcome,
parser_id, score, candidates, exceptions; `:592-595` maps every
statement-less unclaimed to `no_parser_matched`. 175 documents across the
archive are mis-reported; the 2026-08-13 Chase cell proved the class is
where the validated gain lives (Dispatch.attempted ranking is now the
phase's binding queue rule).

# Requirements
1. Carry `attempted` onto the discovery row (new column beside
   `candidates`, same "parser:score; …"-style or plain id list — match the
   file's conventions).
2. Split `_failure_reason`: unclaimed + non-empty attempted →
   `parser_declined`; `no_parser_matched` only when attempted is empty.
3. Surface `parser_declined × parser` as its own rollup bucket in
   `discovery/report.py` alongside the existing reason rollups.
4. Tests: both branches; row-schema addition; report rollup; and a
   compatibility note — `discovery/compare.py` must treat the reason
   rename correctly (a baseline row saying `no_parser_matched` and a
   candidate row saying `parser_declined` for the same doc must NOT count
   as movement — check how compare keys transitions and prove it with a
   test; if compare only ranks by outcome_class, say so and test that).
5. NO behavior change to dispatch, parsing, analysis, caching, or outcome
   classes. This is reporting only. ANALYSIS_STAGE_VERSION untouched
   (analysis payloads unchanged — state this explicitly in your report).

# Scope
- **Allowed:** `discovery/runner.py`, `discovery/report.py`,
  `discovery/compare.py` (only if req 4 demands it), `tests/test_discovery.py`,
  `W3_TRACKA_LOG.md` (append §DISPATCH-REPORTING).
- **Protected:** everything else, including parser_registry.py and
  telemetry/ (they already do their part).

# Validation
Full default suite; a `--dry-run` discovery run proving the pinned 109
reproduce with the new column present and canonical 100/6/3 outcomes; exit
codes verbatim. Corpus gate not required (no analysis change) but run it
if time allows; state either way.

# Final report to Ocean
Verbatim diffs; the dry-run row/rollup samples showing parser_declined in
action; compare-compatibility proof; test inventory; commits; risks.
