# Agent Handoff — DESC-ROTATION (batch 9, the general printed-row rung question; carries the WELCH finding)

Read `docs/agent-handoffs/BATCH9-RULES.md` first (the "Checkpoint rulings" section binds).
Ocean reviews and composes; you never merge or push.

# Ruling (Gustavo, 2026-08-29)
WELCH `361167E3` stays under the general DESC-COLUMNS / printed-row rung; no statement-specific
fix, ever. CP-DECLINES sub-card B measured the rung over every native document: of 3,208, 83
are rotated-comparable and **2 differ** — `361167E3` (`welch_state_bank` claims both forms;
un-rotated publishes 193 postings matching both printed counts and VALIDATES; rotated is
declined — the rung re-serialises the member's deposit block and the reader's region walk
drops 12 of 193 postings, all credits) and `01B82FEC` (`community_section`, routing only, no
ladder effect). The rotation costs exactly one validated document and the owner is the rung
(`ocr/native_text.py`, batch-8 DESC-COLUMNS), not the reader.

# Question (general, not the document)
When the printed-row rotation re-serialises a block, what invariant should the rung
guarantee so that a reader's region walk sees every printed row exactly once? The measured
shape: a deposit block whose credit rows are dropped after rotation while the debit rows and
the snapshot count survive. Characterise the rotation's effect on that block CLASS (the
block's printed geometry, the tokens that anchor the region walk, what the rotation moves
across the anchor) with a committed instrument over the cached text — the un-rotated and the
rotated forms are both in the cache at OCR v4 — and over every native document, not one.
If the invariant fails only on `361167E3`, the honest deliverable is the measurement and a
recorded finding; a rung change is warranted only when the invariant is a property of the
block class (≥ 2 documents, or a fixture family the rung's own tests cover) and every
DESC-COLUMNS mover stays byte-identical.

# Proofs (if the rung changes)
`cohort_replay` over every DESC-COLUMNS mover of batch 8 (from `train8_compare.md`) and over
every native-route validated document the rung fires on (the rotation table's 83) — preserved
with identical payloads; `--group DECL:welch_state_bank`; the OCR-stage tests byte-identical on
the rung's own fixtures; mutation table; privacy and message scans 0; the archive sweep at the
final tree (a rung change reaches every native document); `OCR_STAGE_VERSION` bump is Ocean's.

# Git ownership
Base `train9` at launch. Branch `wave9-descrot`, worktree `.claude/worktrees/mt9-descrot`. Own:
`ocr/native_text.py` (only if the invariant is a block-class property), its tests,
`tools/descrot_*.py`, W3 `§DESCROT` (append-only). `analysis/welch_state_bank.py` is NOT touched.

# Report
BATCH9-RULES contract; the invariant and the block-class measurement; newly validated (0 or
the documents the invariant recovers, by sha16); preserved; regressions 0.
