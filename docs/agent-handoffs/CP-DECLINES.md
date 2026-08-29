# Agent Handoff — CP-DECLINES (batch 9, 9A-1 card 2, coverage; native subset first)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Identity
The 38 documents that one of the four core-processor TEMPLATE readers recognises with an
EXCLUSIVE marker (dispatch candidate score 1.0) and then declines in `parse`
(`failed / parser_declined`): `DECL:core_processor_sectioned` 22 (14 Tesseract / 8 native;
already declined in the batch-7 control run), `DECL:core_processor_enclosures` 9 (6 native /
3 Tesseract; CORE-ENCLOSURES' batch-8 residual — these were `no_parser_matched` before),
`DECL:core_processor_daily` 4 (Tesseract, `City Bank` folder; pre-existing),
`DECL:category_partition` 3 (native; GLANCE's batch-8 residual). Every one filed under
`Unidentified` except the four City Bank and two Community Bank documents. Baseline cohorts
protected: core_processor_sectioned 10 validated · core_processor_enclosures 46 validated /
1 review / 1 withheld · core_processor_daily 13 validated · category_partition 5 validated.
Readers: `analysis/core_processor_sectioned.py` (885 lines), `core_processor_enclosures.py`
(913), `core_processor_daily.py` (811), `category_partition.py` (1,013).

# Sub-card A — the declines (native 17 first, Tesseract 21 second)
1. **Decline probe** per reader (commit as `tools/cpdecl_decline_probe.py`): for each of
   the 38, run the reader's stages on the cached text and record which gate declined — a
   table of gate NAMES per sha (no values), split native / Tesseract. Classify: (a) an
   honest refusal the doctrine requires (L-1 multi-account; a document whose own printed
   identities do not close; a truncated document) → stays declined, named; (b) a grammar gap
   on a shape ≥ 2 documents share → widen; (c) Tesseract damage of a token the grammar needs
   → widen ONLY with OCR-tolerant structure (CP-SECTIONED-SCAN's precedent: tolerance in
   the token shape, never a per-document repair), and only when the native subset's widening
   is closed first.
2. **Widen the shared shapes** as structural capability; the template's printed identities
   (summary equation, per-direction counts and totals, the daily grid where printed) stay
   mandatory. No literal that names a customer, an amount, a date, an account, a bank.
3. Proofs per BATCH9-RULES: `cohort_replay --group DECL:core_processor_sectioned --group
   DECL:core_processor_enclosures --group DECL:core_processor_daily --group DECL:category_partition`
   (target) and `--parser` for each of the four readers (the 76 protected) at base
   (`--expect-identical`) and at every closure; a mutation table per touched grammar
   (`tools/cpdecl_mutation_table.py`); privacy scan of added lines against the 114-document
   population (0); guards, conformance, suite, corpus gate; the archive sweep at your final
   tree — a template reader change reaches every document it claims.

# Sub-card B — WELCH-PRINTED-ROWS, folded (the general question, not the one document)
Batch 8's OCR-v4 / DESC-COLUMNS change (`ocr/native_text.py`) rotates printed rows in the
NATIVE text some readers see; on `361167E3` it broke `welch_state_bank`'s detection
(control: `no_parser_matched`; now `parser_declined`; accepted at the train as a named
cross-cell interaction, not a regression). Ask the general question with an instrument, not
a fix for one sha: over the whole non-validated population with native text (`per_sha.csv`,
`text_route = native`), which registrations' detection or parse outcome DIFFERS between the
rotated and the un-rotated text (`ocr/native_text.py` exposes the rotation; run detection on
both forms, count by registration and outcome)? Report the table. Where a registration's
markers or grammar assume the un-rotated form and ≥ 2 documents are affected, make the
marker/grammar rotation-tolerant as structural capability (never by reading the file name,
never by special-casing a document). `361167E3` is the named instance; if it is the ONLY
affected document, record that and leave it — one document is not a rule.

# Expected movement
Newly validated ≥ 1 from sub-card A (estimate 10–22 before the honest-refusal split; report
the measured split by class); every named refusal stays declined; the 76 protected preserved
with identical payloads or a named, proven-correct leaf change; `regressions = 0`.

# Git ownership
Base `train9` at launch (Ocean names the commit). Branch `wave9-cpdecl`, worktree
`.claude/worktrees/mt9-cpdecl`. Own: the four readers, `ocr/native_text.py` ONLY if sub-card
B proves a rotation defect (say so; DESC-COLUMNS' tests must keep passing byte-identical
on its own fixtures), `analysis/welch_state_bank.py` ONLY for a rotation-tolerant marker,
`tests/test_core_processor_*.py`, `tests/test_category_partition*.py`, `tests/test_welch*.py`,
`tools/cpdecl_*.py`, W3 `§CPDECL` (append-only). No version bump; registry pins in the same
commit as any registration change.

# Report
BATCH9-RULES contract, with the gate table by class and route, the rotation table of
sub-card B, and per-reader preserved counts (10/10, 46/46 + 1 + 1, 13/13, 5/5).
