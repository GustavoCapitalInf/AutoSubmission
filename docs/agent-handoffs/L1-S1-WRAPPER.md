# Agent Handoff — L1-S1-WRAPPER (batch 9, L-1 stage 1: the DocumentReport wrapper + RULE S; ZERO movement)

Read `docs/agent-handoffs/BATCH9-RULES.md` first (its "Checkpoint rulings" section binds: Gustavo's
six L-1 conditions). Then the reviewed design `docs/moneythumb-replacement/L1_INDEPENDENT_ACCOUNT_DESIGN.md`
— §1 (data model), RULE S, §5 (surfaces), §6 (fail-closed conditions and the proof plan), §7 (staged
delivery, S1 row), and `reviews/BATCH9_L1DESIGN_REVIEW.md` (both passes). Ocean reviews and composes;
you never merge or push.

# Scope (exactly the design's S1)
Introduce the document object (`DocumentReport` carrying N account `Report`s plus the document's
printed facts: period, roll-up as ORACLE, omissions, boundary mechanism, internal transfers) at the
pipeline seam, with **RULE S**: a single-account document publishes today's payload with NO added key
of any kind. Nothing publishes multi-account yet (that is S4); no surface is taught (S3); no reader
changes (S2). `ANALYSIS_STAGE_VERSION` is NOT bumped (nothing a cache could serve differently).

# Proof (the design's own instruments, extended)
- RULE S at the PIPELINE seam (not the serialiser): `tools/l1_design_payload_probe.py`'s cohort —
  232 documents / 80 registrations — byte-identical payloads before and after, plus the integrity
  split preserved in order (the design measured naive concatenation one document from moving a
  gate-pinned tuple; the literal reading moves 3 of 232 — your change must move 0).
- `cohort_replay --parser <id> --expect-identical` for EVERY registration (the whole protected 2,615
  candidate set at the composed train — chunk it), with the fixed replay tool (empty containers are
  leaves); the archive sweep at your final tree over all 3,380 — 0 moved, 0 now-publishes, 0 raises
  (the only findings are the compositions already on train9, attributed at your base).
- The corpus gate GREEN with every pinned verdict unchanged; canonical guards + conformance + suite.
- Fail-closed fixtures owed by THIS card (a condition of closing, per the re-review): the design's
  C-conditions whose killer is the wrapper's own shape (an empty `accounts`; a document object built
  with two accounts sharing a content digest — refused by the arithmetic property; a per-document
  field holding one account's value — must be EMPTY with `account_count` carrying the fact).
- Mutation table over the wrapper (RULE S mutants: an added key, a reordered tuple, a leaked account
  value into a document field) — every mutant killed by the byte comparison.
- Privacy scan of added lines (0); commit-message scan (0).

# Git ownership
Base `train9` at launch (after the design composes). Branch `wave9-l1s1`, worktree
`.claude/worktrees/mt9-l1s1`. Own: `analysis/schema.py` (the new object; `Statement` unchanged),
`analysis/pipeline.py` (the seam), `analysis/serialization.py` (RULE S), their tests,
`tools/l1s1_*.py`, W3 `§L1S1`. Touch no reader, no surface, no version constant.

# Report
BATCH9-RULES contract: newly validated 0 · other movement 0 · preserved ALL, byte-identical ·
regressions 0 · correctness (RULE S at the pipeline seam, the integrity split, the mutants) ·
generalization (every registration, the whole archive).
