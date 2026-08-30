# Agent Handoff — PAGECOV-IMAGE-SHEET (batch 9, intake-layer capability + ruling; carried from RV-PAGE-COVERAGE)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds (never weaken a completeness rule
because reconciliation succeeds; a parser never invents; fail closed). Ocean reviews and composes;
you never merge or push. **Needs Gustavo's ruling before launch** (see the question).

# Finding (W3 §PAGECOV)
Eight review documents (`linkbank` 4, `core_processor_enclosures` 4) declare N pages, supply
N sheets, and the LAST sheet carries ZERO TEXT in the OCR-v4 artifact. The page-declaration
check counts a sheet as present only if it prints; a text-empty sheet is the padding the
exclusion exists to refuse, so `missing_declared_statement_page` stands and the eight stay
`review`. A counterfactual measured by the probe (`--outcome-counterfactual`, expressed only in
the `sheets` argument): if those sheets counted, **8 of 8 would go review → validated with 0
flags**. The candidate +8 is refused on doctrine; the non-weakening path is to PROVE the sheet
is a real page.

# Measured by the review (BATCH9_PAGECOV_REVIEW, 2026-08-30) — the +8 is REAL, and it is a CEREMONY
The eight sheets are the most heavily inked pages in their documents: rendered pixel coverage
12.2–34.5 % (on two documents more than twice the ink of the statement page before them); each
is a single INLINE image filling 99.5–100 % of its content stream, byte-identical within each
issuer group (the issuer's standard appended sheet). **Detection must be by inline-image /
content-stream operators or rendered ink coverage — `get_images()` (XObjects) and
`get_drawings()` both return 0 on all eight.** One of the eight, `AF6BD563A3D7165A`, is a
PINNED corpus document whose `review` verdict is pinned in `corpus_gate.py`: this card is a
pinned-surface ceremony (verdicts 102 validated / 3 review → 103 / 2), executed only with the
exact expected movement named and Gustavo's approval, like the batch-7 REPAIR-DOCTRINE ceremony.
Also measured: a (b)-class widening of the declaration reader is NOT inert — over the 1,425
documents where the check finds no declaration today, 50 would gain one and the flag would be
RAISED on 7, three of them validated (symitar) — so no widening of the reader rides with this card.

# The question for Gustavo
May a declared sheet that prints no text count as PRESENT when the PDF proves it carries INK —
an embedded image XObject or drawing operators covering a page-sized area (a scanned notice, a
signature page, a marketing insert) — deterministically, locally, at $0, with the proof recorded
in the payload (`sheet_evidence: text | image | blank`)? A truly blank sheet (no text, no image,
no drawing) stays absent. Nothing about the CHECK changes; only what "present" is evidenced by.

# Method (if ruled)
1. Intake: extend the intake object with per-sheet structure evidence (`ocr/inspect.py` /
   `ocr/pipeline.py` — read-only over the PDF page objects: text operators, image XObjects,
   drawing operators, bounding coverage) — never text content; OCR_STAGE_VERSION bump is Ocean's.
2. The check consumes the evidence: a sheet with no text but page-sized ink counts as present
   and labelled-unknown; the asymmetry stays (this can only ever ADD a present sheet, and only
   with proof; the pinned Columbia refusal — 5 declared / 4 supplied — is unaffected; the
   synthetic Wells fixture behind FILENAME-BOUNDARY unaffected).
3. Proofs: `cohort_replay` over the 20 flag carriers (8 expected to validate; the 4 short PDFs,
   the glyph case and the no-space case unchanged) and `--parser` for the six readers;
   the whole-archive sweep (an intake change reaches every document); mutation table (a blank
   sheet counted; an image below page size counted); privacy and message scans; the OCR
   parity tests (`tests/test_native_rung_parity.py`) byte-identical on their fixtures.

# Also carried (P3, measured inert)
`PAGECOV-NO-SPACE-FORM` (`Page Nof M`, 5 documents, changes no decision) and
`PAGECOV-GLYPH-ORDINAL` (a destroyed label glyph — an OCR question).

# Git ownership (if ruled)
Base `train9` at launch. Branch `wave9-pagecovimg`, worktree `.claude/worktrees/mt9-pagecovimg`.
Own: `ocr/inspect.py` / `ocr/pipeline.py` (the per-sheet evidence), `analysis/pipeline.py` (the
check's consumption of it), their tests, `tools/pagecovimg_*.py`, W3 `§PAGECOVIMG`.
