# Agent Handoff — FIXTURE-PRIVACY (batch 9, 9A-0 card 1, P0 hygiene, ZERO coverage movement)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Identity
The sweep of ARCHIVE TOKENS that sit in tracked source since before batch 8. The batch-8
train's root-base tree scan (`BATCH8_TRANSITION.md`, entry "root-base tree scans", 2026-08-28)
measured, over the whole run-of-record population (3,351 documents with text) and after the
standing exclusions (WORDS, round `.00`, `tests/corpus_cache/`): **11,678 candidates in 251
files** at `99df4a8` — **10,884 in 221 files inherited** from before batch 8 (this card's
population) and 794 on batch-8-added lines (tests 459, docs/records 267, tools 47 — 26 of
them digit substrings of hex shas — and **21 in production files**, all docstring examples or
constants). Named production sites: `analysis/lili.py:15–24` (an invented example statement
that collides with the archive by density), `analysis/core_processor_signed_counts.py:173–241`
(docstring figures), `analysis/bank_ozk.py:62,126` (comment tokens), and the `0.01` cent
tolerance constants at `citizens.py:489` and `scanned_small_bank.py:693,816` (code constants
— adjudicate as such). Also carried since batch 5: a REAL account number has sat in
`tests/test_analysis.py` since the file was written. Batch-8 memory: `redaction` at `cc64232`
/ `bbeeb5c` was a regex sweep that damaged sha strings — do better: exclusions by RULE,
replacements by CONVENTION, and the scanner proves the result.

# Goal (definition of done)
A tree where `tools/privacy_scan_branch.py --include-tree --base <root commit>` over the
whole run-of-record population reports **0 MONEY / DIGITS / DATES hits** in production,
tests, tools and docs OUTSIDE a committed, documented exclusion table — and every replacement
follows the invented-shape convention (dates in 2031; figures/ids that the scan proves do not
collide with the token universe — verified by the scan, never by eye). No production
behaviour change of any kind.

# Method
1. **Baseline scan at your base**, whole population, root base:
   `python tools/privacy_scan_branch.py --rows <run>/rows.csv --data-dir
   .claude/recovery/webapp_data_train8_cold --base "$(git rev-list --max-parents=0 HEAD)"
   --ref HEAD --include-tree --out <private>/tree_scan_base.json` (the scanner imports the
   cache module from its own tree; this tree is OCR v4 and the cold cache is v4 — assert it
   read ~3,35x documents, never 0; a scan that reads 0 documents is vacuous and worthless).
   Record counts by class × top-level directory. The hit list is PRIVATE (it is a list of
   archive tokens) — it never enters a commit, a W3 section or your report.
2. **Adjudicate by CLASS with committed rules**, never token by token:
   - **production** (`analysis/ ocr/ webapp/ discovery/ telemetry/ *.py` at the root): 0
     tolerated. Docstring / comment examples move to the invented-shape convention. Code
     constants that merely LOOK like archive figures (`0.01`, `100.00`-style bounds) are
     excluded by a rule that names the shape, not the file. NO code change: prove every
     touched production module AST-identical modulo docstrings/comments, base vs branch,
     with a small committed tool (`tools/fixpriv_ast_identity.py`: `ast.dump` after stripping
     docstrings and comments; exit non-zero on any difference).
   - **tests/**: every colliding fixture figure / date / id replaced with an invented shape;
     `tests/corpus_cache/` is archive text by design (standing exclusion — state it). The
     real account number in `tests/test_analysis.py`: replace it AND show the test still tests
     what it tested (what the assertion is about; the invented id keeps the shape the test
     needs). A fixture change that changes a test's meaning is a finding, not a fix.
   - **tools/**: hex-sha substrings are shas, not tokens — add an exclusion RULE for
     sha-shaped tokens (`[0-9A-F]{16,64}` contexts) to the scanner; adjudicate the rest.
   - **docs/** (`W3_TRACKA_LOG.md`, `BATCH*`, `CENSUS*`, `reviews/`, `agent-handoffs/`,
     `WAVE*`, `PROJECT_STATUS.md`): DIGITS ≥ 5 that are neither shas nor dates → redact to a
     class band (`bbeeb5c` precedent); MONEY with cents → classes/bands (the orchestrator's
     rule: magnitudes as classes, never exact archive figures); DATES: the program's own
     session dates are not document dates — exclude by an explicit rule (e.g. ISO dates on or
     after 2026-07-01 inside `docs/`), record the rule, redact any other fully-qualified date
     that matches a document token. **`W3_TRACKA_LOG.md` is NOT edited on your branch**: the
     train helper requires a branch's W3 to be the base log plus ONE appended section.
     Instead commit `tools/fixpriv_w3_redact.py` — pattern/class-driven (never a token list),
     idempotent, byte-minimal, with a dry-run that prints counts by class and line — and
     record its dry-run counts; Ocean runs it on the composed train and re-scans.
   - **WORDS** class: standing exclusion (institution and template vocabulary), as at the train.
3. **Extend the scanner** (`tools/privacy_scan_branch.py`) with the exclusion rules you commit
   (options + one documented exclusion table in its docstring), keep its import-time
   self-check, and add a test that each exclusion matches exactly the shape its rule names
   and nothing wider (an exclusion that silences a real account number is a BLOCK).
4. **Final scan at your tip**, same command: counts by class × directory before / after;
   0 outside the committed exclusions (W3's residue listed separately with the redactor's
   dry-run counts).

# Expected coverage movement
ZERO. Prove it two ways: `tools/fixpriv_ast_identity.py` over every touched production
module, AND `python -m tools.cohort_replay --parser <id>` for every registration of every
touched production module at your tip (`preserved = all, payload identical = all`; run
`--expect-identical` at base first). The canonical guard and conformance sets and the full
suite at your tip.

# Git ownership
Base `train9` at this handoff's commit. Branch `wave9-fixpriv`, worktree
`.claude/worktrees/mt9-fixpriv`. Own: `tests/` (all files EXCEPT `tests/test_privacy3_boundaries.py`
and `tests/test_raise_privacy4.py`, which RAISE-PRIVACY-4 owns concurrently), `docs/` (redactions
only; never rewrite meaning; W3 untouched — the redactor tool instead), `tools/privacy_scan_branch.py`,
new `tools/fixpriv_*.py`, and the docstrings/comments ONLY of `analysis/lili.py`,
`analysis/core_processor_signed_counts.py`, `analysis/bank_ozk.py`, `analysis/citizens.py`,
`analysis/scanned_small_bank.py`. **Do NOT touch `analysis/bmo.py`, `analysis/farmers_merchants.py`,
`analysis/td_can.py`** (RAISE-PRIVACY-4 runs concurrently on them). No registry change, no
version bump, no production code.

# Report
W3 section `§FIXPRIV` (append-only) and the final message, in the BATCH9-RULES contract:
population (counts by class × directory, before/after), root cause, solution (the exclusion
table and the convention), newly validated = 0, other ladder movement = 0, previously validated
preserved = all (the replay numbers), regressions = 0, correctness evidence (AST identity,
the test-meaning check for every changed fixture), generalization evidence (the rules are
shapes, not files); commits; proof-floor exits; the final scan count; risks last.
