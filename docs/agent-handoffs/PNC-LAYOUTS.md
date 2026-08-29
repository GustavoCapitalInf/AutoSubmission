# Agent Handoff — PNC-LAYOUTS (batch 9, 9A-1 card 3, coverage: FAM-PNC-LAYOUTS + WH:pnc)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Identity
PNC is a 17-document institution in the census: three PNC product layouts the `pnc` reader
(`analysis/pnc.py`, 331 lines, registration `pnc` / "PNC Bank") does not claim —
`FAM:pnc_core_commercial_checking` 4, `FAM:pnc_treasury_enterprise_plan` 4,
`FAM:pnc_virtual_wallet_performance_spend` 4 (batch-8 census families, conf 0.7–0.8, oracle
present: printed period totals and a daily-balance grid) — plus `WH:pnc` 4 withheld with
detail coverage 0 / 0.24 (rows NOT captured: the ledger cannot close because the reader
published a summary with almost no rows; codes A and A+C) and `DECL:pnc` 1. Baseline cohort
protected: 41 validated. Every document native.

# Method
1. **Characterise** the three families from the cached text (`cohort_replay`'s cache access;
   text never leaves your tools): masthead/furniture, summary grammar, row grammar, the daily
   grid — as SHAPES; and the four withheld: which row grammar misses their rows (a row shape
   the reader does not know? a section it skips? a page form?). Commit the probe
   (`tools/pnc_layout_probe.py`; gate/shape names only).
2. **One reader, several layouts** — widen `pnc`'s markers and grammars to the shared shapes
   (one product family may need its own registration only if its identities differ; then
   registry pins in the same commit and a stratified non-target probe ≥ 400 documents).
   The reader's printed identities stay mandatory: period totals, counts where printed, the
   daily grid as the ADB oracle. WH:pnc must close by capturing the rows the paper prints —
   coverage → 1.0, breaks → 0 — never by loosening the closing check.
3. Proofs per BATCH9-RULES: `cohort_replay --family pnc_core_commercial_checking --family
   pnc_treasury_enterprise_plan --family pnc_virtual_wallet_performance_spend --group WH:pnc
   --group DECL:pnc` (target 17) and `--parser pnc` (41 protected) at base (`--expect-identical`)
   and at closure; mutation table (`tools/pnc_mutation_table.py`); privacy scan against the
   58-document population (0); guards, conformance, suite, corpus gate; the archive sweep at
   your final tree.

# Expected movement
Newly validated ≥ 1 (estimate 6–11 + up to 4 from WH:pnc); the 41 protected preserved with
identical payloads or a named, proven-correct leaf change; `regressions = 0`. Currency:
USD schema default is the doctrine for these; publish nothing else.

# Git ownership
Base `train9` at launch (Ocean names the commit). Branch `wave9-pnc`, worktree
`.claude/worktrees/mt9-pnc`. Own: `analysis/pnc.py`, `tests/test_pnc*.py`, `tools/pnc_*.py`,
W3 `§PNC9` (append-only). WH-ROW-CAPTURE does NOT touch `pnc.py` (this card owns WH:pnc).

# Report
BATCH9-RULES contract with per-family and per-withheld outcomes by sha, the shape table,
preserved 41/41, the mutation table, the privacy count.
