# Agent Handoff — PROD-RESIDUE-CLASSIFY (batch 9, READ-ONLY privacy classification; no production change)

Read `docs/agent-handoffs/BATCH9-RULES.md` first (the "Checkpoint rulings" section binds).
Ocean reviews and composes; you never merge or push.

# Ruling (Gustavo, 2026-08-29)
Do not blindly rewrite the inherited production residue; CLASSIFY it first. The FIXTURE-PRIVACY
tree scan measured **414 residue sites in 62 production files** (the whole-tree scan at the
composed train with the committed exclusion table — re-measure at your base; the number moves
with the table), some in CODE: `analysis/consumers.py:90` (a correctness hardcode — its own
card, `CONS-HARDCODE`), `analysis/classification_registry.py:36,45`, `analysis/cibc.py:93`,
`analysis/core_processor_sectioned.py:392–405`.

# Deliverable — `docs/moneythumb-replacement/PROD_RESIDUE_CLASSIFICATION.md`
One committed instrument (`tools/prodres_classify.py`, read-only) that, for every production
residue site (`analysis/ ocr/ webapp/ discovery/ telemetry/ benchmark/ *.py` at the root),
records: file:line class (MONEY / DIGITS / DATES); POSITION class by AST — docstring,
comment, string literal in code, numeric literal in code, regex literal, test-shaped
fixture inside production, data table; whether the literal is REACHED by production
behaviour (used in a comparison, a lookup, a match) or is prose; the scanner rule that would
have excused it and why it did not; and a proposed disposition per site: (a) prose → rewrite
to a class ("a six-figure amount") in a hygiene card; (b) a code constant that merely looks
like an archive figure (a tolerance, a bound) → a documented exclusion rule by SHAPE; (c) a
statement-specific literal reached by behaviour → a CORRECTNESS card (R-1 class; name it);
(d) institution furniture (routing number, phone ladder, PO box, domain) → justified
furniture, excused by rule. Counts by disposition, by module, by class. Names never
copied into the document — the hit list stays private; the document carries file:line,
classes, dispositions and counts only.

# Proofs
The instrument re-run reproduces every count; privacy scan of added lines 0; message scan 0;
guards 255; no production file differs from base.

# Git ownership
Base `train9` at launch. Branch `wave9-prodres`, worktree `.claude/worktrees/mt9-prodres`.
Own: the document, `tools/prodres_classify.py`, W3 `§PRODRES` (append-only).

# Report
Status; commit range; the disposition table; the correctness cards it proposes (each with the
file:line and the behaviour it reaches); privacy and message-scan counts.
