# Agent Handoff — P20-POSTPROCESS (Phase 2.0 cell B1: the nine-function census, the whole-chain quarantine, the no-hardcodes guard into `ocr/`)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (OQ1 = C, OQ2 = YES), then `OCR_LEGACY_AUDIT.md`
F-1 / F-11 / F-3 / §5.7 and the review's BLOCK-1 / MINOR-6, then `PHASE2_ARCHITECTURE_PLAN.md` §8,
then the umbrella `PHASE2-0-SAFETY.md`. Ocean reviews and composes; you never merge or push.
**Hygiene card: `newly validated = 0`; previously validated preserved, payload identical.** Nothing
makes a network call; the chain you are quarantining has never run on a real page.

# Why
`ocr/ocr_client.py::postprocess` (`:409-416`) runs NINE functions on every visual read before the
validator sees it. Two provably rewrite ledger values in complementary scopes (`collapse_repeated_amounts`
outside `<td>`, `fix_amount_column_bleed` inside); two restructure rows and re-emit cells with an
UNPROVEN value-loss shape; three delete text; one deletes embedded images; one collapses repeated page
numbers. Gustavo ruled OQ1 = C: quarantine the entire chain; the default is raw evidence; re-admission
is per function, on that function's own census + synthetic fixtures, after independent review.

# Design (ruled — do not re-decide)
1. **Census of all NINE** (`strip_det_tags`, `strip_refusal_commentary`, `strip_placeholder_markers`,
   `strip_oversized_embedded_images`, `collapse_repeated_amounts`, `collapse_repeated_page_numbers`,
   `split_fused_header_row`, `repair_fused_amount_table`, `fix_amount_column_bleed`), as
   `tools/ocr_postprocess_census.py` (read-only over the tree; imports the functions; runs the
   committed fixtures; prints a table) and `docs/moneythumb-replacement/OCR_POSTPROCESS_CENSUS.md`.
   For each function record: **classification** — as precise as the source supports, at minimum one
   of `reads/removes metadata-only content` · `restructures without inventing/replacing financial
   values` · `writes/deletes/reassigns financial-value meaning`, refined where the evidence demands
   (e.g. "deletes text that can contain numeric tokens", "reassigns a money token to a different
   column", "deletes distinct adjacent amounts") — never forced into a label the evidence
   contradicts; **numeric-token accounting** — for every fixture, the multiset of money-shaped,
   digit-run and date-shaped tokens before and after, and whether any moved, disappeared, changed, or
   changed cell/column; **transaction-semantics** — can a row's amount, sign, date, description or
   column role change; **the worst input you could construct** and the input on which the function is
   harmless. Pay special attention to `collapse_repeated_amounts` (reproduce F-1 incl. `[a,a,a,b,c]` →
   `[a]`), `fix_amount_column_bleed` (reproduce F-11), `repair_fused_amount_table` (settle the
   UNPROVEN debit/credit/balance fold — construct it or prove it cannot occur), `split_fused_header_row`.
2. **Synthetic fixtures**, one directory per function under `tests/fixtures/ocr_postprocess/<fn>/`,
   each case as `input.md` + `expected.md` + `case.json` (`what_changes`, `what_does_not_change`,
   `numeric_tokens_before/after`, `numeric_tokens_moved/disappeared/changed`, `semantics_can_change`).
   SYNTHETIC only: no archive text, no fixture token that could be a real statement's (privacy scan
   0 — run `tools/privacy_scan_branch.py` over your ADDED lines against the 179 Tesseract shas AND
   the 6 committed corpus artifacts' universe). `tests/test_ocr_postprocess_census.py` runs every
   fixture through its function and through the FULL chain and asserts the recorded deltas, so the
   census is executable, not prose.
3. **Quarantine on every path.** `ocr_client.ocr_page` returns `PageText(raw, …)` — the model's
   completion string as received (det tags, refusal prose, placeholders included); `embed_image_regions`
   is NOT applied on the analysis path (pixels never enter the text the validator reads — F-2; keep
   the function, unwired, for a future display-only use); `postprocess` remains importable but is
   called by NOTHING on the analysis path and NOTHING on the display path (`ocr/render.py:179,192`
   render raw content). A module constant `POSTPROCESS_STATE = "quarantined"` and an EMPTY
   `ADMITTED_POSTPROCESS: tuple[str, ...] = ()` are the re-admission mechanism: `apply_admitted(text)`
   applies exactly the admitted members in chain order and is what the analysis path calls (today a
   no-op). Cell C keys the cache on `POSTPROCESS_STATE` + the admitted tuple — export both from
   `ocr/ocr_client.py` under those exact names. Re-admitting a member in Phase 2.0 is NOT authorized
   (nothing OCR-fed is validated in 2.0, so nothing is lost); the mechanism exists so that Phase 2.3
   can re-admit the metadata-only members on the census evidence after review.
4. **Named intake behavior (OQ2).** `looks_missegmented` + the fallback-DPI re-read, and the TD page-1
   recovery (`_TD_MARKERS_RE`, `is_td_statement`, `looks_truncated_td`, `_mask_qr`,
   `_TD_RECOVERY_VARIANTS`, `recover_truncated_td_page`) choose WHICH PIXELS ARE READ, never what a
   value means. They stay, DECLARED: a module-level `INTAKE_FURNITURE` register in `ocr/ocr_client.py`
   naming each behavior, its structural justification (a QR region derails generation; an orphan
   amount-only table is a segmentation signature), its scope (page selection / render variant only),
   and the fixture that pins it (`tests/test_ocr_intake_furniture.py`: the masked rectangle is a
   fixed fraction of the page, the variants are `(dpi, mask)` pairs, neither reads or writes a money
   token; a mutant that makes `_mask_qr` depend on a printed figure is killed). The register is the
   ONLY sanctioned home for issuer-named intake behavior.
5. **The guard extends into `ocr/` (OQ2).** `tests/test_no_statement_hardcodes.py` gains an `OCR_DIR`
   scan with the same pattern classes (removed literals, years, account-number runs, exact-cent
   amounts, calendar literals, mojibake) over `ocr/*.py`. Measure the blast radius FIRST and record
   it; declare a ratchet baseline like `CALENDAR_BASELINE` for anything pre-existing that is furniture
   (e.g. the Poppler path in `ocr/rasterize.py:7-10` is a toolchain path, not a statement literal —
   exempt it by name with the reason). The TD markers are admitted ONLY through the
   `INTAKE_FURNITURE` register: the guard asserts every issuer-named regex in `ocr/` is registered
   there (a mutant that adds an unregistered issuer marker to `ocr/pipeline.py` is killed). Nothing
   customer-, account-, SHA-, benchmark- or statement-specific may appear in `ocr/`.
6. **Truncation stays flag-only.** `tests/test_truncation.py:194-207` proves the chain cannot
   manufacture a signal; keep it green on raw text (the quarantine removes inputs to it, never adds).

# What must NOT change
The offline rungs (`ocr/native_text.py`, `ocr/local_tesseract.py`) and `parse_statement`'s ladder
order; `StatementMarkdown.to_markdown()` (pinned "must not add a byte"); the committed corpus
artifacts; anything under `analysis/`. `tests/test_ocr_client.py`'s 38 tests: those that pin the
functions' behavior move to the census fixtures; those that pin `ocr_page`'s cleaned output are
rewritten to pin the RAW output (state each change in your W3 section).

# Mutation table (minimum)
| mutant | killer |
|---|---|
| `ocr_page` calls `postprocess` again | the raw-return test (det tag survives) |
| `render_boxed` calls `postprocess` | the display-path test |
| `ADMITTED_POSTPROCESS = ("strip_det_tags",)` | the empty-admission pin (2.0) |
| `apply_admitted` applies a non-admitted member | the chain-order test |
| `embed_image_regions` wired on the analysis path | the no-base64-in-pages test |
| an issuer marker added outside `INTAKE_FURNITURE` | the OQ2 register guard |
| `_mask_qr` reads a money token | the furniture fixture |
| a census fixture's `numeric_tokens_disappeared` recorded as 0 for F-1's `[a,a,a,b,c]` | the census test |

# Measurements to report
The nine-row census table (classification · fixtures · numeric-token deltas · semantics) · OQ2 blast
radius and baseline · cohort replay at base (`--expect-identical`) and at closure over the 179
Tesseract shas + the 6 committed corpus artifacts' shas + the visual-rung test families (exit 0; 0
newly validated; preserved identical — the offline partition never touched `postprocess`, so the
replay proves the seam, not the chain) · mutation table · privacy 0 · tests added · targeted suite ·
guards (the extended guard included).

# Ownership
`ocr/ocr_client.py`, `ocr/pipeline.py` (ONLY the raw/`apply_admitted` return path — nothing in the
ladder order, flags or `StatementMarkdown` construction), `ocr/render.py`,
`tools/ocr_postprocess_census.py` (new), `docs/moneythumb-replacement/OCR_POSTPROCESS_CENSUS.md` (new),
`tests/fixtures/ocr_postprocess/` (new), `tests/test_ocr_postprocess_census.py` (new),
`tests/test_ocr_intake_furniture.py` (new), `tests/test_ocr_client.py`, `tests/test_pipeline.py`
(raw-output pins), `tests/test_no_statement_hardcodes.py` (the `ocr/` extension), W3 `§P20POSTPROC`.
NOT yours: `ocr/config.py`, `ocr/document.py`, `ocr/availability.py` (B2); `discovery/*`,
`webapp/*`, `telemetry/*` (A, C, D); `analysis/*`.

# Exclusions
No re-admission of any member. No candidate/alternate-hypothesis machinery (§8's `raw/candidate/
transformation/provenance` record is Phase 2.3, not 2.0). No change to what the offline partition
produces. No PaddleOCR.

# Git
Base `train10` at your handoff's commit. Branch `wave20-postprocess`, worktree
`.claude/worktrees/mt20-postprocess`.
