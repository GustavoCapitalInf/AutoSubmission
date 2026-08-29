# Agent Handoff — CONS-HARDCODE (batch 9, correctness; the first pinned test case of the independent-account model)

Read `docs/agent-handoffs/BATCH9-RULES.md` first (the "Checkpoint rulings" section binds).
Ocean reviews and composes; you never merge or push. **This card does not start before
`L1-ARCH-DESIGN` is reviewed and its stage (a) has landed** — it is stage (d) of that design.

# Ruling (Gustavo, 2026-08-29)
`analysis/consumers.py:90` — a `flat.find(...)` literal carrying a product name AND an
account number, by which the reader publishes ONE of the three posting accounts of the
pinned document `05E246C0…` (CONS-L1 / CONS-HARDCODE, an open ruling since batch 7) — is a
CORRECTNESS hardcode and a statement-specific constant (the R-1 class). Card and fix it
before Consumers is widened. No arbitrary or memorised account selection under the new
model: the document publishes every posting account independently, or refuses.

# Method
1. Characterise the pinned document and the `DECL:consumers` documents (3) on the cached
   text: which accounts post, which sibling structure is printed, the roll-up if any — shapes
   only. (The L-1 packet's `l1_census.py` already classifies consumers' refusal gate.)
2. Remove the memorised selector; publish the document on the independent-account model per
   the design (each account reconstructed and validated by the unchanged validator; idle
   siblings only by explicit printed structure; transfers flagged internal).
3. The pinned document MOVES by definition (today it validates one memorised account). This is
   a truth-set ceremony: name the exact expected movement (which accounts validate, which
   withhold, the document outcome under the design's rule) BEFORE running the corpus gate;
   the gate's pinned expectations for that document are updated in the same commit with the
   ceremony's argument in W3; every other pinned document byte-identical.
4. Proofs per BATCH9-RULES: `cohort_replay --parser consumers --group DECL:consumers` at base
   and closure; the corpus gate with the ceremony's expected movement and nothing else; a
   mutation table for the new account partition gates; no statement-specific constant left
   (the canonical guards pass with the literal removed); privacy and message scans 0.

# Git ownership
Base `train9` at launch. Branch `wave9-conshc`, worktree `.claude/worktrees/mt9-conshc`. Own:
`analysis/consumers.py`, `tests/test_consumers*.py`, the pinned expectation entry for the
one document, `tools/conshc_*.py`, W3 `§CONSHC` (append-only).

# Report
BATCH9-RULES contract with the ceremony's movement table (pinned document: before / after,
per account), newly validated (the DECL:consumers documents that now publish), preserved,
regressions (the pinned movement is the APPROVED ceremony, named — nothing else).
