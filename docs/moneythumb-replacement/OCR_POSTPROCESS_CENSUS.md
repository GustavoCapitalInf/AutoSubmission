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

**Corrected after adversarial review** (`docs/moneythumb-replacement/reviews/
PHASE2_P20POSTPROC_REVIEW.md`, MAJOR-1, MINOR-2, MINOR-3): rows 1, 4, 6, 7, 8 and 9 below carried
an absolute "cannot touch a financial/distinct value" claim the reviewer falsified by
construction. The labels for rows 1 and 4 changed (they no longer qualify for
`METADATA_ONLY_LABEL` — see `tools/ocr_postprocess_census.py`); rows 6, 7, 8 and 9 keep their
coarse label with the reason corrected. `tests/test_ocr_postprocess_census.py::
test_metadata_only_classification_never_deletes_a_financial_token` makes the label enforceable:
a function may claim it only if EVERY one of its fixtures shows no money/date token
disappearing.

| # | function | classification | worst input (fixture) | harmless input (fixture) | numeric tokens | semantics can change |
|---|---|---|---|---|---|---|
| 1 | `strip_det_tags` | **removes a markup span whose content is UNCONSTRAINED by the pattern** (no longer metadata-only-unconditional) | a well-formed tag glued to money (`tag_and_money_adjacent`); an orphan tag whose OWN bracket holds a money token, deleted with it (`orphan_bracket_contains_money`); the well-formed-pair pattern spanning from an orphan opening tag to the NEXT region's close, deleting printed money between them (`pair_spans_to_next_close`) | two orphan-shaped tags around a real degenerate footer, with the money and page number outside every bracket (`orphan_and_bare_tags_preserve_adjacent_text`) | bounding-box coordinate digits disappear in the safe shapes; in the two worst-case fixtures a money token is genuinely destroyed | **yes** — a money token written inside an orphan's brackets, or between an orphan open and the next tag's close, is deleted |
| 2 | `strip_refusal_commentary` | reads/removes metadata-only content | the refusal template immediately followed by a money token, no separator (`refusal_adjacent_to_money`) | ordinary statement text with no refusal template (`leaves_normal_text_alone`) | none — the anchored three-sentence template carries no digits and cannot over-consume | **no** |
| 3 | `strip_placeholder_markers` | reads/removes metadata-only content re: money/date; MINOR-3: an unconditional non-financial byte rewrite | `[Non-Text]` inline beside a money token on the same line (`line_and_inline_with_money`) | a bracketed token that is not the placeholder shape (`preserves_bracketed_content`); a placeholder-free page, which still gets CRLF/trailing-newline normalized away (`placeholder_free_normalizes_ws`) | none financial — a line carrying any content besides the placeholder fails the line-drop `fullmatch` guard; but every page's line endings are rejoined with a bare `\n` regardless of whether a placeholder was present | **no** (money/date only — the function is NOT byte-identity-preserving in general) |
| 4 | `strip_oversized_embedded_images` | **removes a markup span whose content is UNCONSTRAINED by the pattern** (no longer metadata-only-unconditional) | an over-threshold base64 `<img>` beside a money token and a small (kept) image (`oversized_dropped`, isolated-call demo); a money token inside the removed image's OWN `alt` attribute, at the PRODUCTION default threshold (`alt_attribute_money_dropped`) | any image under the length threshold | none in the isolated-demo fixture; in the worst-case fixture the `alt` text's money token is genuinely destroyed | **yes** — `_DATA_IMG_RE`'s trailing `[^>]*` covers `alt`, not only `src` |
| 5 | `collapse_repeated_amounts` (**F-1**) | **writes/deletes financial-value meaning: deletes distinct adjacent amounts** | `[a,a,a,b,c]` on one whitespace-separated run → `[a]` — two DISTINCT amounts ($75.00, $60.00) destroyed even though neither ever repeated (`distinct_adjacent_deleted`) | the same values inside `<td>` cells (`table_cells_untouched`); a value repeating only TWICE beside a distinct amount, below the destruction threshold (`two_repeats_untouched`) | money tokens genuinely **disappear** (not merely deduplicated) — mechanically confirmed by the census test's independent Counter-diff | **yes** — a legitimate, distinct transaction amount can be erased entirely |
| 6 | `collapse_repeated_page_numbers` | restructures without inventing a FINANCIAL value; MINOR-2: not every disappearance is an exact-duplicate loss | an exact triple-repeated `Page 4 of 10` footer (`exact_duplicate_collapsed`); a shorter footer that is a textual PREFIX of a longer one sharing the same page number, partially and destructively collapsed (`prefix_footer_collapsed`) | two wholly distinct page footers (`distinct_pages_untouched`) | never money/date-shaped; digit-run page furniture can be a genuine, non-duplicate loss (the prefix case) as well as a harmless duplicate loss (the exact-repeat case) | **no** (never a financial value — the function is exempt from `METADATA_ONLY_LABEL`'s money/date invariant only because it was never claimed to carry that label) |
| 7 | `split_fused_header_row` | restructures without inventing/replacing financial values WITHIN `<td>` cells, but NOT metadata-only at the row level | every first-row cell fused header+value (`all_cells_fused_split`); text sitting in the fused `<tr>` OUTSIDE any `<td>`, discarded with its money token when the row is rebuilt (`stray_text_between_cells_deleted`) | an already-clean header row (`clean_header_untouched`); a label/value summary row with no fused cell (`leaves_label_value_summary_untouched`) | values inside `<td>` cells: none invented/deleted/moved to a different column (plus the date/digit-run word-boundary reclassification artifact, see note below); stray text outside every `<td>`: genuinely deleted | **yes** — money-shaped text sitting outside every `<td>` in the fused row is discarded, not merely relocated |
| 8 | `repair_fused_amount_table` | **writes/reassigns financial-value meaning, CONDITIONALLY — SETTLED BY CONSTRUCTION** (see below); also drops non-row table content when it fires | a fused DATE...AMOUNT header (with an unrecognized middle cell, so `split_fused_header_row` does not intercept first) above a genuine 5-cell debit/credit/balance row → the debit AND credit values are folded into free-text description, and the running balance is relabeled as the row's "amount" (`debit_credit_balance_folded`); a `<caption>` outside every `<tr>`, discarded with its money token whenever the table is rewritten at all (`caption_dropped_when_fires`) | a fused header whose last cell honestly reads `BALANCE` (not `AMOUNT`) — the gate never opens, whole table untouched (`balance_labeled_header_untouched`); a genuine single-money-column table with a spilled description column reconstructs safely (`partial_fusion_reconstructed`) | no digit inside a `<tr>` row is deleted or invented — token-preserving in that strict sense; a caption's money token IS deleted (not merely relocated) whenever the table is rewritten | **yes** — which column is "the amount" changes; an independent financial column (debit/credit) becomes unparseable free text; a caption's money value is destroyed outright |
| 9 | `fix_amount_column_bleed` (**F-11**) | **writes/reassigns financial-value meaning**; also drops non-row table content when it fires | a two-money `Amount` cell: the leading value is moved into the description, the trailing value promoted to the row's amount (`bleed_reassigned`); a `<caption>` outside every `<tr>`, discarded with its money token whenever any row in the table bleeds (`caption_dropped_when_fires`) | a money-only `Amount` cell (`clean_cell_untouched`); a table with no `Amount` header at all (`no_amount_header_untouched`) | inside `<tr>` rows: no digit deleted — both values survive, one relocated; a caption's money token IS deleted outright whenever the table is rewritten | **yes** — the function decides purely from cell SHAPE (a trailing money-shaped value), never from which figure the page actually printed as the amount; a caption's money value can be destroyed outright, not merely relocated |

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
  Phase 2.0 — the mechanism exists so a later phase can re-admit a member on this census's own
  evidence, after independent review. After the review's MAJOR-1 correction, only rows 2
  (`strip_refusal_commentary`) and 3 (`strip_placeholder_markers`) carry the unconditional
  `METADATA_ONLY_LABEL` — the label `tests/test_ocr_postprocess_census.py::
  test_metadata_only_classification_never_deletes_a_financial_token` enforces mechanically.
  Rows 1 and 4 no longer make that claim (their own worst-case fixtures show a money token
  disappearing); rows 5, 7, 8 and 9 never made it.
- `embed_image_regions` (F-2: document pixels into the canonical text) is likewise not called
  from `ocr_page`. It stays importable, unwired, for a possible future display-only use.
- `ocr/render.py`'s `_region_html` / `_render_boxed_page` render raw content directly; neither
  calls `postprocess` or `apply_admitted`. The display path never re-enters the chain.
- **The quarantine changes WHEN the DPI fallback fires** (`PHASE2_P20POSTPROC_REVIEW.md`
  MINOR-4). `ocr/pipeline.py`'s mis-segmentation fallback now
  calls `looks_missegmented` on the RAW completion instead of the postprocessed text —
  `_ORPHAN_AMOUNT_TABLE_RE` tolerates only `\s*` between `<table>` and its first `<tr>`, so a raw
  page still carrying a stripped-metadata construct there (a `[Non-Text]` placeholder, a
  `<|det|>` tag) defeats the match where postprocessed text would have matched. The fallback
  re-OCR therefore fires **strictly less often** on this constructible shape under the
  quarantine — never more often. Zero production impact (`visual_rung = not_attempted`
  3,506/3,506), pinned by `tests/test_ocr_client.py::
  test_looks_missegmented_fires_strictly_less_often_on_raw_text`. `looks_truncated_td` is
  unaffected: its two substrings ("statement of account", "account summary") are never removed
  by any postprocess member.

## OQ2: the no-statement-hardcodes guard extended into `ocr/`

`tests/test_no_statement_hardcodes.py` gained an `OCR_DIR` scan reusing the SAME six pattern
classes already enforced over `analysis/` (removed literals, literal years, account-number
digit runs, exact-cent amounts, calendar literals pinned into patterns, raw mojibake), plus a
register-driven guard specific to `ocr/`: every issuer-named string in `ocr/` (widened past
`re.compile` assignments to every `str` `ast.Constant`, review MAJOR-2) must be named in
`ocr.ocr_client.INTAKE_FURNITURE`, layer-wide over all 13 files (not scoped to the 3 this card
owns — the original narrowing bought nothing, see below).

**Blast radius, measured before any test was written:**
- `REMOVED_LITERALS`, `YEAR_RE`, `ACCOUNT_RE`, `MOJIBAKE_RE`, `CALENDAR_RE`: **0 hits** across
  every file in `ocr/`.
- `AMOUNT_RE`: 6 hits across 2 files, both non-statement furniture — a geometry ratio constant
  (`ocr/column_grid.py:207`, `reach = pitch * 1.25`) and five CSS `line-height`/`font-size`
  values inside `ocr/render.py`'s page-rendering stylesheet constant. Ratcheted as
  `OCR_AMOUNT_BASELINE = {"column_grid.py", "render.py"}` (shrink-only, pinned by
  `test_ocr_amount_baseline_still_describes_real_offenders`).
- Issuer-named string, layer-wide: **exactly one** outside the two ratcheted files —
  `ocr_client._TD_MARKERS_RE`, already registered in `INTAKE_FURNITURE`.

**`ocr/native_text.py` and `ocr/column_grid.py` carry a NAMED, COUNTED, shrink-only ratchet —
not a scope exclusion** (corrected after adversarial review, MAJOR-2: the original "out of
scope" framing left 10 of 13 files unguarded for no measured benefit, and a per-file skip would
have let a NEW issuer marker added to either file pass silently — the review's mutant J). Both
are pre-existing, not owned by this card, and hold genuine per-issuer structural PDF-parsing
constants — `native_text.py`'s own native-text column/layout readers for five issuers
(`parse_native_woodforest`, `parse_native_navy_federal`, `parse_native_desjardins`, the First
Citizens description-column reader, the Wells Fargo summary reader) and `column_grid.py`'s
Woodforest-specific geometry helpers — structurally analogous to `analysis/`'s per-bank parsers,
not the postprocess/intake-furniture surface OQ1/OQ2 govern. `OCR_ISSUER_STRING_BASELINE`
records the exact measured count for each (summed over every marker occurrence inside every
`str` `ast.Constant` in the module — module/function docstrings included, bare identifiers like
the function name `parse_native_woodforest` excluded, since a name is not a string value):

| file | issuers | occurrences | ratchet |
|---|---|---|---|
| `ocr/native_text.py` | 5 (woodforest, navy federal, first citizens, desjardins, wells fargo) | 25 | `OCR_ISSUER_STRING_BASELINE["native_text.py"] = 25` |
| `ocr/column_grid.py` | 1 (woodforest) | 3 | `OCR_ISSUER_STRING_BASELINE["column_grid.py"] = 3` |

`test_ocr_issuer_string_baseline_is_not_exceeded` fails if either count grows OR shrinks without
the baseline being retightened — the same shrink-only property as `CALENDAR_BASELINE` and
`OCR_AMOUNT_BASELINE`, but count-based rather than file-skip-based so growth inside a ratcheted
file is still caught.

### `INTAKE_FURNITURE` — the declared register

**Seven entries** (corrected after review, MAJOR-4: the original four omitted the two TD
functions that actually SELECT among candidate reads by document content —
`is_td_statement` / `looks_truncated_td` are the text-side detection pair, and
`recover_truncated_td_page` is what `_TD_RECOVERY_VARIANTS` feeds). Six tied to TD (the
QR-derailment recovery: `_TD_MARKERS_RE` and `is_td_statement` detection, `looks_truncated_td`
the truncation signature, `_TD_RECOVERY_VARIANTS` the render-variant list,
`recover_truncated_td_page` the candidate-read selector, `_mask_qr` pixel masking) and one
structural (`looks_missegmented`, tied to no issuer). Each names its issuer (or `None`),
behavior, structural justification, scope, and the test that pins it
(`tests/test_ocr_intake_furniture.py`): the masked rectangle is a fixed 60-100% width x 0-12%
height fraction regardless of page content; `_mask_qr` takes only an image (no text channel
through which a printed figure could reach a masking decision, proven by signature inspection);
the render variants are `(dpi: int, mask: bool)` pairs. None reads or writes a money token.

**`_TD_RECOVERY_VARIANTS` and `looks_missegmented`'s `scope` strings now say plainly** (review
MAJOR-4) that they also select which of several candidate OCR reads survives — keyed on a
printed structural section caption (`recover_truncated_td_page`'s "ACCOUNT SUMMARY" test) or a
table-shape signature (`looks_missegmented`'s orphan-amount-table test), never on a printed
figure. Proven directly: `test_recover_truncated_td_page_selects_by_caption_not_by_figure`
constructs candidate reads where the WRONG (still-truncated) variants print an implausibly
large balance and the recovered variant prints a much smaller one — selection follows the
caption regardless.

**A registered name is not a blanket licence for every issuer (review MAJOR-3).** For every
register entry whose subject is a compiled regex with a non-`None` issuer,
`test_registered_regex_pattern_matches_its_declared_issuer_and_no_other` asserts the pattern
text contains that issuer's own marker AND no marker belonging to a different institution —
proven against the real `_TD_MARKERS_RE` object and against a constructed widening
(`test_registered_regex_check_actually_catches_a_second_issuer`).

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

`tests/test_ocr_postprocess_census.py` — 31 fixtures across the 9 functions (130 collected test
cases), each function's output pinned exactly, each fixture also run through the full
`postprocess()` chain (proving no undocumented cross-function interaction), every recorded
numeric-token count independently re-measured, and every disappeared/appeared claim
independently recomputed from a raw Counter-diff (not merely trusted from `case.json`).
`EXPECTED_FIXTURE_COUNT` pins the exact fixture count per function (review MINOR-R3: a bare
`>= 17` floor stayed satisfied all the way down to 17, so deleting any of the 14 fixtures added
after the first adversarial review — including the one fixture that is F-1's `count >= 3`
threshold's only killer — went unnoticed by the suite; an exact per-function count names a
deletion immediately, by function). `python -m tools.ocr_postprocess_census` reproduces the same
9-row pass/fail table read-only from the command line.

**A precision note on `strip_placeholder_markers`'s whitespace claims (review MINOR-3
closure).** The `placeholder_free_normalizes_ws` fixture proves the trailing-newline drop; the
CRLF-to-LF and form-feed-to-LF claims are true by direct measurement on the function in isolation,
but are NOT provable through this fixture harness, because `Path.read_text()` (used to load
`input.md`) universal-newline-translates CRLF and form-feed to LF before the function ever sees
them — a fixture file cannot carry a raw CRLF byte sequence into the test through this loader.
