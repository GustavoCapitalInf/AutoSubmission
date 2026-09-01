# OCR postprocess census — the nine-function chain (Phase 2.0, cell B1, OQ1 = C)

```
CARD: P20-POSTPROCESS
RULING EXECUTED: PHASE2_RULINGS.md OQ1 = C (quarantine the entire chain; re-admit per
  function, on that function's own census + synthetic fixtures, after independent review)
  and OQ2 = YES (the no-statement-hardcodes guard extends into ocr/)
INSTRUMENT: tools/ocr_postprocess_census.py (read-only; imports the nine functions and runs
  the committed fixtures under tests/fixtures/ocr_postprocess/)
EXECUTABLE PROOF: tests/test_ocr_postprocess_census.py (every classification claim below
  traces to a fixture asserted there, including an independently recomputed
  numeric-token-delta cross-check — a wrong record in either direction fails the test, not
  just the prose)
STATUS: chain quarantined on every path (analysis AND display); ADMITTED_POSTPROCESS = ()
  (nothing re-admitted in Phase 2.0)
```

## Why nine, not six (MINOR-6)

`OCR_LEGACY_AUDIT.md` §5.7 and the original Open Question 1 both said `postprocess` was "six
functions deep". The adversarial review's MINOR-6 finding corrected this: `ocr/ocr_client.py`
`postprocess()` (`:409-416`, unchanged by this card except that nothing calls it any more)
composes **nine** distinct functions. The three missed were the three nested inside the first
line — `strip_placeholder_markers(strip_refusal_commentary(strip_det_tags(raw)))` — and all
three **delete text**, which is exactly the shape a scoping defect in this census would have
kept invisible. This document and its instrument cover all nine.

## The census (measured, not asserted)

For every row: **classification** as precise as the source supports (never forced into a
coarser or more alarming label than the evidence justifies); the **worst input** this census
could construct and the **harmless input** on which the function is a no-op; **numeric-token
accounting** (money-shaped / date-shaped / bare digit-run tokens, before vs. after); whether
**transaction semantics** (which column is the amount, which row a value belongs to, its sign)
can change. Fixtures live at `tests/fixtures/ocr_postprocess/<function>/<case>/`.

| # | function | classification | worst input (fixture) | harmless input (fixture) | numeric tokens | semantics can change |
|---|---|---|---|---|---|---|
| 1 | `strip_det_tags` | reads/removes metadata-only content | a `<\|det\|>` region tag glued directly onto a money token, no separator (`tag_and_money_adjacent`) | any well-formed tag around plain text | bounding-box coordinate digits (bare integers) disappear; money and date tokens never sit inside the tag grammar, so neither can ever be touched | **no** |
| 2 | `strip_refusal_commentary` | reads/removes metadata-only content | the refusal template immediately followed by a money token, no separator (`refusal_adjacent_to_money`) | ordinary statement text (no refusal template present) | none — the anchored three-sentence template carries no digits and cannot over-consume | **no** |
| 3 | `strip_placeholder_markers` | reads/removes metadata-only content | `[Non-Text]` inline beside a money token on the same line (`line_and_inline_with_money`) | a bracketed token that is not the placeholder shape (e.g. `[Continued]`) | none — a line carrying any content besides the placeholder fails the line-drop `fullmatch` guard, so a numeric token is never dropped | **no** |
| 4 | `strip_oversized_embedded_images` | reads/removes metadata-only content | an over-threshold base64 `<img>` beside a money token and a small (kept) image (`oversized_dropped`) | any image under the length threshold | none in the financial sense — the regex only ever matches `<img src="data:image/...">` markup | **no** |
| 5 | `collapse_repeated_amounts` (**F-1**) | **writes/deletes financial-value meaning: deletes distinct adjacent amounts** | `[a,a,a,b,c]` on one whitespace-separated run → `[a]` — two DISTINCT amounts ($75.00, $60.00) destroyed even though neither ever repeated (`distinct_adjacent_deleted`) | the same values inside `<td>` cells (`table_cells_untouched`); a run with no value repeating 3+ times | money tokens genuinely **disappear** (not merely deduplicated) — mechanically confirmed by the census test's independent Counter-diff | **yes** — a legitimate, distinct transaction amount can be erased entirely |
| 6 | `collapse_repeated_page_numbers` | restructures without inventing financial values | an exact triple-repeated `Page 4 of 10` footer (`exact_duplicate_collapsed`) | two distinct page footers (`distinct_pages_untouched`) | digit-run tokens (page/count numbers, never a financial value) DO disappear in count, but every disappearing copy is an EXACT duplicate of a token that survives — no distinct information lost | **no** |
| 7 | `split_fused_header_row` | restructures without inventing/replacing financial values | every first-row cell fused header+value (`all_cells_fused_split`) | an already-clean header row (`clean_header_untouched`) | none invented/deleted/moved to a different column; a date/digit-run reclassification appears in this census's own token extractor purely from a word-boundary shift (see note below) — not new data | **no** |
| 8 | `repair_fused_amount_table` | **writes/reassigns financial-value meaning, CONDITIONALLY — SETTLED BY CONSTRUCTION** (see below) | a fused DATE...AMOUNT header (with an unrecognized middle cell, so `split_fused_header_row` does not intercept first) above a genuine 5-cell debit/credit/balance row → the debit AND credit values are folded into free-text description, and the running balance is relabeled as the row's "amount" (`debit_credit_balance_folded`) | a fused header whose last cell honestly reads `BALANCE` (not `AMOUNT`) — the gate never opens, whole table untouched (`balance_labeled_header_untouched`); a genuine single-money-column table with a spilled description column reconstructs safely (`partial_fusion_reconstructed`) | no digit is deleted or invented — token-preserving in the strict digit sense | **yes** — which column is "the amount" changes, and an independent financial column (debit/credit) becomes unparseable free text |
| 9 | `fix_amount_column_bleed` (**F-11**) | **writes/reassigns financial-value meaning** | a two-money `Amount` cell: the leading value is moved into the description, the trailing value promoted to the row's amount (`bleed_reassigned`) | a money-only `Amount` cell (`clean_cell_untouched`); a table with no `Amount` header at all (`no_amount_header_untouched`) | no digit deleted — both values survive, one relocated | **yes** — the function decides purely from cell SHAPE (a trailing money-shaped value), never from which figure the page actually printed as the amount |

## The two proven value-rewrite sites (F-1, F-11) — reconfirmed at this tree

- **F-1** (`collapse_repeated_amounts`, `ocr/ocr_client.py:68-82`): reproduced exactly,
  including the `[a,a,a,b,c] -> [a]` strengthening from the adversarial review. `tests/
  test_ocr_postprocess_census.py::test_f1_distinct_adjacent_amounts_are_recorded_as_disappeared`
  pins that `$75.00` and `$60.00` are destroyed, not deduplicated.
- **F-11** (`fix_amount_column_bleed`, `ocr/ocr_client.py:129-171`): reproduced exactly. The
  function's decision is shape-only (which of the two money values in a fused cell sits last),
  never printed-position-aware, so it can promote the wrong figure whenever the page printed the
  true amount first and a coincidentally money-shaped reference number second.

## The settled question: does `repair_fused_amount_table` ever fold a debit/credit/balance row?

`OCR_LEGACY_AUDIT.md` F-11 item 3 left this **explicitly UNPROVEN**: "neither the review nor
this audit could construct a value-losing input for the latter [`repair_fused_amount_table`]
... but its per-row loop folds every `len(cells) >= 3` row whose last cell is money into three
columns by joining `cells[1:-1]` into the description, a shape that on a debit/credit/balance
table would fold two money columns into the description."

**Settled by construction, this census** (`tests/fixtures/ocr_postprocess/
repair_fused_amount_table/debit_credit_balance_folded/`): the function's own gate inspects
**only the first and last cell** of a fused header row (`h0.group(1) == "DATE"` and
`hL.group(1) == "AMOUNT"`) and ignores every middle cell entirely. When a middle header cell is
not one of the four recognized words (`DATE`/`AMOUNT`/`BALANCE`/`DESCRIPTION`),
`split_fused_header_row` — which requires *every* cell to be recognized — does not intercept the
table first, and `repair_fused_amount_table` runs on the original structure. Any later row with
`>= 3` cells and a bare-money last cell is then folded to three columns regardless of what its
middle cells represent. Demonstrated: a genuine 5-cell row (date, description, debit=10.00,
credit=25.00, balance=105.00) folds to `(date, "description 10.00 25.00", 105.00)` — the debit
and credit values become unparseable free text, and the running balance is relabeled as the
transaction "amount". **No digit is deleted** (all three values still appear as text somewhere
in the output), so this is not the same failure shape as F-1 — but transaction semantics
(which column is the amount) are destroyed exactly as the audit worried, which is why this
census classifies the function as **conditionally** hazardous rather than as a safe
restructuring, and why OQ1's whole-chain quarantine is the correct disposition for it too.

The condition is narrow (the table's *own* fused header must literally read `AMOUNT`, not
`BALANCE`, as its last word) but constructible — an OCR misread of a header word, or a genuine
running-total column honestly labeled `AMOUNT` beside an independent `DEBIT`/`CREDIT` column —
and nothing in the function checks for it.

## A note on the date/digit-run reclassification (`split_fused_header_row`, `repair_fused_amount_table`)

Two fixtures show a date token "appearing" and digit-run tokens "disappearing" across the
transformation even on their SAFE/harmless-shaped inputs. This is an artifact of this census's
own token extractor, not invented data: `tools.ocr_postprocess_census.extract_tokens`'s date
pattern requires a word boundary before its first digit, and `"DATE04/06"` has none (both `E`
and `0` are word characters). Once the same digits are relocated into their own `<td>` cell by
the transformation, the boundary exists and the extractor now recognizes the date shape it could
not see before. No digit's value changes and no digit moves to a different column — only which
category this measurement tool's own regex sorts it into. Recorded plainly here because the
rule is "classified as precisely as the source supports, never forced into a misleading label",
and glossing over a measurement artifact would itself be a misleading label.

## Quarantine mechanics

- `ocr_client.postprocess(raw)` — the nine-function chain — is unchanged and remains
  importable (the census and its tests call it directly), but is called by **nothing** on the
  analysis path (`ocr_client.ocr_page`) or the display path (`ocr/render.py`).
- `ocr_page` returns `PageText(apply_admitted(raw), ...)` — the model's raw completion string
  (det tags, refusal prose, placeholders, degenerate repeats and fused cells all included),
  passed only through `apply_admitted`.
- `POSTPROCESS_STATE = "quarantined"` and `ADMITTED_POSTPROCESS: tuple[str, ...] = ()` are
  exported from `ocr/ocr_client.py` under exactly those names (cell C keys the cache on them).
  `apply_admitted(text)` applies exactly the members named in `ADMITTED_POSTPROCESS`, in the
  order they appear there; with the tuple empty, it is a no-op. Nothing is re-admitted in
  Phase 2.0 — the mechanism exists so a later phase can re-admit the metadata-only members
  (rows 1-4 above) on this census's own evidence, after independent review, without reviving
  rows 5, 7, 8 or 9.
- `embed_image_regions` (F-2: document pixels into the canonical text) is likewise not called
  from `ocr_page`. It stays importable, unwired, for a possible future display-only use.
- `ocr/render.py`'s `_region_html` / `_render_boxed_page` render raw content directly; neither
  calls `postprocess` or `apply_admitted`. The display path never re-enters the chain.

## OQ2: the no-statement-hardcodes guard extended into `ocr/`

`tests/test_no_statement_hardcodes.py` gained an `OCR_DIR` scan reusing the SAME pattern
classes already enforced over `analysis/` (removed literals, literal years, account-number
digit runs, exact-cent amounts, calendar literals pinned into patterns, raw mojibake), plus a
register-driven guard specific to `ocr/`: every issuer-named regex in `ocr/ocr_client.py`,
`ocr/pipeline.py` and `ocr/render.py` must be named in `ocr.ocr_client.INTAKE_FURNITURE`.

**Blast radius, measured before any test was written:**
- `REMOVED_LITERALS`, `YEAR_RE`, `ACCOUNT_RE`, `MOJIBAKE_RE`, `CALENDAR_RE`: **0 hits** across
  every file in `ocr/`.
- `AMOUNT_RE`: 6 hits across 2 files, both non-statement furniture — a geometry ratio constant
  (`ocr/column_grid.py:207`, `reach = pitch * 1.25`) and five CSS `line-height`/`font-size`
  values inside `ocr/render.py`'s page-rendering stylesheet constant. Ratcheted as
  `OCR_AMOUNT_BASELINE = {"column_grid.py", "render.py"}` (shrink-only, pinned by
  `test_ocr_amount_baseline_still_describes_real_offenders`).
- Issuer-named regex: **exactly one**, `ocr_client._TD_MARKERS_RE`, already registered in
  `INTAKE_FURNITURE`.

**`ocr/native_text.py` is out of scope for this card.** It is a much larger, pre-existing
module (not owned by P20-POSTPROCESS) carrying its own per-issuer structural PDF-column
constants (Woodforest, Navy Federal, Wells Fargo, Desjardins, First Citizens layout markers).
The issuer-marker guard is deliberately scoped to the three files this card owns — the register
it enforces (`INTAKE_FURNITURE`) lives in, and only governs, `ocr/ocr_client.py`,
`ocr/pipeline.py` and `ocr/render.py`. `native_text.py`'s issuer-specific constants are a
measured fact for whichever future card owns that module's hygiene, recorded here rather than
silently absorbed into this card's blast-radius numbers.

### `INTAKE_FURNITURE` — the declared register

Four entries, three tied to TD (the QR-derailment recovery: `_TD_MARKERS_RE` detection,
`_TD_RECOVERY_VARIANTS` render-variant list, `_mask_qr` pixel masking) and one structural
(`looks_missegmented`, tied to no issuer). Each names its issuer (or `None`), behavior,
structural justification, scope, and the test that pins it
(`tests/test_ocr_intake_furniture.py`): the masked rectangle is a fixed 60-100% width x 0-12%
height fraction regardless of page content; `_mask_qr` takes only an image (no text channel
through which a printed figure could reach a masking decision, proven by signature inspection);
the render variants are `(dpi: int, mask: bool)` pairs. None reads or writes a money token.

## Truncation stays flag-only

`ocr/truncation.py` is unchanged. `structural_tail_signals` only ever inspects the LAST open
vs. last close tag position for `<table>`/`<tr>`/`<td>`; none of the nine postprocess functions
can affect that check, because every table-restructuring member (`split_fused_header_row`,
`repair_fused_amount_table`, `fix_amount_column_bleed`) matches via `_TABLE_RE`
(`<table>.*?</table>`), which requires the closing tag to already be present — a genuinely
truncated (unclosed) table is never matched, so these functions were always a no-op on the
exact input shape truncation detection cares about, both before and after this card's changes.
`tests/test_truncation.py` (194-207 and the full file) is green unchanged.

## Proof

`tests/test_ocr_postprocess_census.py` — 17 fixtures across the 9 functions, each function's
output pinned exactly, each fixture also run through the full `postprocess()` chain (proving no
undocumented cross-function interaction), every recorded numeric-token count independently
re-measured, and every disappeared/appeared claim independently recomputed from a raw
Counter-diff (not merely trusted from `case.json`). `python -m tools.ocr_postprocess_census`
reproduces the same 9-row pass/fail table read-only from the command line.
