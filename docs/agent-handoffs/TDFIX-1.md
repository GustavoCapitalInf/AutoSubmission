# Agent Handoff — TDFIX-1

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the 2026-08-13/14 coverage wave. Three scout-measured,
execution-verified parser-local cards (SC-TDCAN report; the scout's scratch
prototypes live in `<session scratchpad>/sc_tdcan/` — read its diagnostics,
verify its numbers yourself).

# Identity
- **Agent:** TDFIX-1 · td_us overdrawn-opening + section softening; td_can
  credit-code vocabulary.

# Git ownership
- **Base:** current main (record the SHA) · **Branch:** `wave3-tdfix-1` ·
  **Worktree:** `.claude/worktrees/mt-tdfix`.

# Card U1 — td_us: overdrawn beginning balance (measured +6 / 0 regressions)
`analysis/td_us.py:38` lacks `-?` that line 41 (ending) has; line 39
(stated_average_balance) has the same gap. 7 of the 10 class-1 declines
print a negative opening; the miss nulls beginning_balance and `:196-197`
declines the document. Scout-verified fix: add `-?` to :38 and :39 →
**6 of 10 declines validate with sum_delta 0.00 and summary_ok True, 0
regressions across all 28 validated td_us docs**, and line 39 additionally
stops silently dropping negative ADBs on documents that already validate
(e.g. CEA1C7496377 — that is a value change on a validated doc: name every
such mover in your sweep and verify the new stated_average_balance against
the printed figure). The chase §C6.1 sign fix is your template: minimal
diff, in-process pre-fix regression fixture, detection invariance.

# Card U2 — td_us: a section subtotal mismatch discards the document
`analysis/td_us.py:213-214` hard-declines on one section mismatch,
discarding complete self-consistent summaries (2 scanned docs: 43 and 58
good rows, Tesseract dropped rows worth 394.71/307.18). Soften to
per-section failure so the document reaches reconcile and fails CLOSED
there (withheld/review with summary_ok=True, coverage ~93-97%) — the
pipeline's own convention; sibling withheld docs D3396D14/BDA1DE2F prove
the downstream handles it. Claimed-but-not-validated is not success:
expect +2 claimed, 0 validated, both withheld with honest diagnoses. Must
NOT let a section-mismatched document publish validated.

# Card C1 — td_canada_native: three additive credit codes (measured +4 / 0)
`analysis/td_can.py:200-217` `_native_credit_like` misses three of TD's own
structural codes: `E-TFR ` (only E-TRANSFER matched), `TD ATM DEP <n>`,
`GC <n>-DEPOSIT`. Scout ablation: +3/+1/+0-but-needed → **63/73 → 67/73
exact, 0 regressions**; 4 documents leave withheld. R-1 item 8 compliant
(bank's own codes, not counterparty knowledge). Do NOT remove `PAY`
(unsound but net-neutral — record it as a residual instead). Caveat to
verify and record: EA5C61862BB8 drifts +600.72 → +1000.72 under the patch
but stays withheld either way.

# NOT yours (recorded as separate cards)
- D5: td_can never populates running_balance (continuity inert on 73 docs)
  — a scotia-class card needing pinned-first treatment; do not touch.
- The French layout family (TD-FRENCH cell, parallel worktree, creates a
  NEW module and registry entry; consumes td_can helpers read-only). You
  own `analysis/td_can.py` edits this cycle; TD-FRENCH owns
  `analysis/td_canada_french.py` + registry entries. No overlap.

# Scope
- **Allowed:** `analysis/td_us.py` (cards U1/U2 only), `analysis/td_can.py`
  (card C1 lines only), tests (`tests/test_td_us_variants.py` additions or
  new, `tests/test_td_can_native_variants.py` additions),
  `W3_TRACKA_LOG.md` (append §TDFIX-1).
- **Protected:** everything else. Registry entries file is TD-FRENCH's this
  cycle — if you think you need it, STOP.

# Validation
Full default suite; corpus-marked; corpus_gate.py GREEN 106/3 (pinned TD
docs must stay byte-identical — if any audited field moves, STOP);
guards; conformance; before/after sweeps over the ENTIRE td_us (28
validated + 10 declines + 2 withheld) and td_canada_native (73) populations
with every mover named and classified. NOTE: a full archive discovery run
may be executing on this machine — do not touch webapp_data beyond
read-only artifact paths (never the sqlite index), and expect proof
timings under load. Exit codes verbatim. Stage bump is Ocean's.

# Final report to Ocean
Per card: verbatim diff, pre-fix-failure fixtures, sweep with named movers
(including the negative-ADB value movers on validated docs), proofs with
exit codes, commits, risks, unresolved questions.
