# Agent Handoff — L1-S2-SIBLING-OMISSION (batch 9, L-1 stage 2: SIBLING-OMISSION-SURFACE on the document object; ZERO newly validated)

Read `docs/agent-handoffs/BATCH9-RULES.md` first (Gustavo's six L-1 conditions bind — an idle
sibling is admitted ONLY when explicit statement structure establishes the sibling AND its
empty/silent state). Then the reviewed design `docs/moneythumb-replacement/L1_INDEPENDENT_ACCOUNT_DESIGN.md`
— §1.5 (the omission record), L1-C17 (the four evidence classes: the printed dormancy declaration;
a section printing its own opening, a closing coinciding to the cent, zero credit and debit totals
and zero credit and debit counts; the zero-summary class; a second declaration wording — closed
against ABSENCE, open to evidence, wording-independent), §6 (S2 row: 0 lost / 12 re-founded / 16
surfaced), and `reviews/BATCH9_L1DESIGN_REVIEW.md` (the Q8 tables: 12 validated documents / 16
sections / 16 with evidence / 0 without, per registration and per site). Requires S1 composed.
Ocean reviews and composes; you never merge or push.

# Scope (exactly the design's S2)
Replace the ABSENCE-based skips with EVIDENCE-based admission at the skip SITES the design measured
— `analysis/symitar.py:419–420` (7 sections; the ratified `_DORMANT_RE` is dead code today: wire it
as one of the evidence classes), `analysis/community_section.py:621–622` (8 sections; the `:984`
clause drops 0), `analysis/zions.py` (`_inert`, 1 section; `_NO_ACTIVITY_RE` as a second wording)
— and write the omission record INSIDE the callee onto the document object (S1's field), never
onto `Statement` (RULE S). A sibling whose section prints NONE of the four evidence classes is no
longer skipped: the document is REFUSED (L-1 stands until S4). `dakota_west`'s derived selection
("the section with the most transactions", F4) is a DIFFERENT defect: name the pinned document it
touches; do not change it here (it is S4/S5 territory under a ceremony) — unless the design's S2 row
says otherwise, in which case follow the design.

# Expected movement (measured by the design and its review)
Newly validated 0. Of the 12 validated documents whose skip fires today, ALL 16 skipped sections
print evidence → 12 re-founded, 16 omissions SURFACED (a payload change on those 12 protected
documents — the omission field — and on NO other document). Any validated document that would be
refused is a STOP: it means the evidence classes are narrower than the paper, not that the paper
lacks evidence. `ANALYSIS_STAGE_VERSION` bump is Ocean's at the train.

# Proof
- `cohort_replay --parser symitar --parser community_section --parser dakota_west --parser
  mission_valley --parser zions` at base (`--expect-identical`) and at closure: preserved ALL;
  payload changed on exactly the 12 named documents and ONLY by the omission field (classify every
  leaf); every other document byte-identical; the pinned corpus verdicts unchanged (gate GREEN).
- The design's skip probe re-run: 12 / 16 / 16 / 0 at base; at closure every one of the 16
  admitted by a NAMED evidence class, and a constructed absence-only fixture REFUSED (the re-review's
  nine fixtures are the seed — reuse them).
- Mutation table: one mutant per evidence class (drop it → the section is refused, killed by the
  12), one mutant restoring the absence skip (killed by the absence-only fixture), one writing the
  omission onto `Statement` (killed by RULE S's byte comparison).
- The archive sweep at the final tree: movers = exactly the 12; privacy and message scans 0;
  guards, conformance, suite, corpus gate.

# Git ownership
Base `train9` after S1 composes. Branch `wave9-l1s2`, worktree `.claude/worktrees/mt9-l1s2`. Own:
the three skip sites named above, their tests, `tools/l1s2_*.py`, W3 `§L1S2`. No other reader.

# Findings from S1 that bind this card
- `Statement`'s class docstring is published by pydantic as the extraction call's
  `response_schema` description — a MODEL PROMPT. Never edit it to document the model; use
  comments. The same applies to any field description on `Statement`.
- `DocumentReport` carries a pinned field-set test: a new document-level field (the omission
  record lives on the document object, not on `Statement`) must come with its RULE S clause and
  the test updated in the same commit, or the suite is red by design.
- RULE S was proven at the pipeline seam over 232 documents / 80 registrations; your change must
  keep every single-account payload byte-identical EXCEPT the 12 re-founded documents, whose
  only changed leaf is the omission record.

# Report
BATCH9-RULES contract with the per-registration table (validated read / skip fires / sections /
evidence class per section), newly validated 0, preserved ALL with the 12 leaf changes classified,
regressions 0, the pinned dakota_west document named.
