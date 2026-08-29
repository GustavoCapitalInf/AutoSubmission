# Agent Handoff — RV-PAGE-COVERAGE (batch 9, 9A-1 card 6, PROBE FIRST — read-only until the probe is closed)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Identity
11 documents in `review / integrity_flags` carrying exactly one flag,
`missing_declared_statement_page`, with reconciliation OK on every one: `RV:linkbank` 4,
`RV:community_section` 2, `RV:southside_scanned` 2 (Tesseract), `RV:citizens` 1 (Tesseract),
`RV:core_processor_enclosures` 1, `RV:texas_first_scanned` 1 (Tesseract). The check
(`analysis/pipeline.py` ≈ 440–485): the document declares N bank pages (largest declared
denominator), the supplied sheets are counted from the intake object, a sheet counts as
labelled if it carries any declaration; the flag stands when a declared page label is absent
and cannot be accounted for by an unlabelled sheet. It is fraud-relevant and deliberately
asymmetric; it can only ever be weakened by proving structure, never by silence.

# Gustavo's rule for this card (verbatim in spirit)
Do NOT weaken `missing_declared_statement_page` or any completeness / integrity rule merely
because reconciliation succeeds. A genuinely partial upload stays `review`. The only
admissible fix is a PROVEN misread of the declaration — a page-declaration form the regex
does not read (so a present, labelled sheet is counted as unlabelled or absent), or a
declared total taken from a denominator that is not a page count.

# Method
1. **Probe, read-only, committed as `tools/pagecov_probe.py`**: for each of the 11, from the
   cached text: the declared total the check derived, the declaration forms found per sheet
   (as SHAPES — `Page N of M`, `N/M`, `Page N` without a denominator, none), the sheet count
   (`ocr_pages` in `per_sha.csv`), which page labels are missing, whether an unlabelled
   sheet exists. Table by sha (shapes and counts only). Classify: (a) sheets genuinely
   absent → correct flag, stays review, named; (b) a declaration form present on the sheet
   that `_PAGE_DECLARATION_RE` does not read → a misread; (c) a denominator that is not a
   page count (a statement-count, a sequence number) → a misread of the total.
2. **Only for (b)/(c)**: extend the declaration reading as structural capability, with the
   asymmetry preserved (the change can clear a flag only where a present sheet is proven
   labelled). Every fixture invented; the pinned Columbia refusal (declares 5, supplies 4,
   labels 4) must stay byte-identical — it is the check's anchor.
3. Proofs per BATCH9-RULES: `cohort_replay --group RV:linkbank --group RV:community_section
   --group RV:southside_scanned --group RV:citizens --group RV:core_processor_enclosures
   --group RV:texas_first_scanned` (target 11) and, because the check is SHARED, the whole
   protected population that carries any page declaration is the regression surface: run
   `cohort_replay --parser <id>` for the six readers involved AND the archive sweep at your
   final tree with zero movers outside the 11; mutation table for the declaration reader
   (`tools/pagecov_mutation_table.py`); privacy scan (0); guards, conformance, suite, corpus
   gate (the pinned refusal 1/1 unchanged).

# Expected movement
Unknown until the probe closes — the honest deliverable may be the probe and `newly
validated = 0`. Report the (a)/(b)/(c) split first, then proceed only on (b)/(c).
`regressions = 0`; the corpus gate's REFUSED 1 unchanged.

# Git ownership
Base `train9` at launch (Ocean names the commit). Branch `wave9-pagecov`, worktree
`.claude/worktrees/mt9-pagecov`. Own: `analysis/pipeline.py` (the declaration reader only —
say every line), `tests/test_pipeline*.py` for that check, `tools/pagecov_*.py`, W3 `§PAGECOV`
(append-only). Do not touch any reader.

# Report
BATCH9-RULES contract; the probe table by class is the primary deliverable.
