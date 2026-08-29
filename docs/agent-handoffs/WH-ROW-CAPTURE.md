# Agent Handoff — WH-ROW-CAPTURE (batch 9, 9A-1 card 5, coverage: withheld with a row-capture signature)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Identity
18 withheld documents whose OWN payload in the run of record carries an extraction signature
— the reader's row set is wrong, so the ledger cannot close — as measured by the census from
the cached analysis artifacts (`per_sha.csv`: `credit_coverage`, `debit_coverage`,
`continuity_breaks`, `adb_checks_failed`):
- `WH:rbc` 6 — codes A+B (one A+B+C): credit coverage 0.46–0.86, 5–14 continuity breaks →
  rows MISSED. Reader `analysis/rbc.py` (1,015 lines); baseline 159 validated protected;
  CAD-pinned surface (`PINNED_CURRENCY`, currency doctrine: native currency canonical,
  provenance unchanged).
- `WH:bmo` 4 — A+B ×3 (coverage 0.87 / 1.77 / 1.77 — rows DUPLICATED on two) and A ×1
  (coverage 1.72). Reader `analysis/bmo.py` (274 lines); baseline: 0 validated, 4 withheld —
  the whole cohort is this card's population. RAISE-PRIVACY-4 (9A-0) funnelled its `date()`
  sites first; build on the composed train.
- `WH:wells_fargo` 4 — A ×2 (coverage 0.96 / 1.0, 0 breaks), A+B ×1 (2 breaks), B+F ×1
  (8 breaks, no coverage). Reader `analysis/wells.py` (277 lines); baseline 217 validated
  protected — the largest protected cohort of the wave.
- `WH:scotiabank` 3 — A+B ×2 (coverage ≈1.0, 3–5 breaks), A ×1 (2 breaks). Reader
  `analysis/scotia.py` (331 lines); baseline 78 validated; CAD-pinned surface.
- `WH:ibc` 1 — A, 1 break, 21 stated daily balances. Reader `analysis/ibc.py`; baseline: 0
  validated, 1 withheld.
`WH:pnc` belongs to PNC-LAYOUTS; `WH:atb` is ceremony-gated (do not touch `atb.py`);
`WH:frost` is ruling-gated (do not touch `frost.py`).

# Method (per reader, one at a time; commit per reader)
1. **Signature probe** (`tools/rowcap_probe.py`, committed; names of shapes only): for each
   withheld sha, which printed rows the reader did not capture (row shape / page form /
   section) or captured twice (duplicate shape) — measured by re-running the reader's row
   grammar over the cached text and comparing captured rows to the printed section
   subtotals and to the running balance where printed. Classify: a row SHAPE the grammar
   does not know (widen), a continuation form (widen), a duplication from a repeated header
   or page overlap (fix the dedupe structurally), or a document whose printed rows genuinely
   do not close (stays withheld, named).
2. **Fix by capturing the paper's rows** — never by loosening `ledger_reconciles_to_closing`,
   `running_balances_support_daily_ledger` or any check in `adb.py` / the reconciler (do not
   touch them). Measured success per sha: coverage → 1.0, breaks → 0, the ADB checks pass —
   or the document stays withheld and you say why.
3. Proofs per BATCH9-RULES: `cohort_replay --group WH:rbc --group WH:bmo --group WH:wells_fargo
   --group WH:scotiabank --group WH:ibc` (target 18) and `--parser rbc`, `--parser bmo`,
   `--parser wells_fargo`, `--parser scotiabank`, `--parser ibc` (the protected 454) at base
   (`--expect-identical`) and at every closure — preserved with identical payloads, or a
   named, proven-correct leaf change; `PINNED_CURRENCY` and the provenance surface must
   not move (corpus gate GREEN, currency 108/108); mutation table per touched grammar
   (`tools/rowcap_mutation_table.py`); privacy scan of added lines against the 472-document
   population (0); guards, conformance, suite, corpus gate; the archive sweep at your final
   tree.

# Expected movement
Newly validated ≥ 1 (estimate 8–16); every non-closing document stays withheld and is named;
`previously validated preserved = 454/454`; `regressions = 0`; no currency / provenance
movement.

# Git ownership
Base `train9` at launch (Ocean names the commit, after 9A-0 composes). Branch `wave9-rowcap`,
worktree `.claude/worktrees/mt9-rowcap`. Own: `analysis/rbc.py`, `analysis/bmo.py`,
`analysis/wells.py`, `analysis/scotia.py`, `analysis/ibc.py`, their tests
(`tests/test_rbc*.py`, `test_bmo*.py`, `test_wells*.py`, `test_scotia*.py`, `test_ibc*.py`),
`tools/rowcap_*.py`, W3 `§ROWCAP` (append-only). Do NOT touch `adb.py`, the reconciler,
`pnc.py`, `atb.py`, `frost.py`.

# Report
BATCH9-RULES contract per reader: signature table by class, per-sha before/after coverage
and breaks (ratios and counts, never amounts), preserved n/n per reader, mutation table,
privacy count.
