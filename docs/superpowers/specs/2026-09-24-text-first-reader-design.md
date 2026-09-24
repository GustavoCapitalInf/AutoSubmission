# Text-first reader v1: design

Status: approved section by section by the owner on 2026-09-24. This spec is the single source for the
implementation plan. It was written from scratch: by the owner's ruling, the earlier structurer / geometry /
"Generalized Reconstruction" attempt (analysis/structurer/, experiments/w3_3a/, tools/measure_structurer.py,
evidence/native.py, ocr/column_grid.py, layout/, reconstruction_mode and their documents) is neither reused
nor used as evidence here, and implementers must not consult it.

## 1. Goal

Some digital bank statements come from banks no Phase 1 parser recognises; today they end as "no
deterministic parser matched this statement" or go to the visual pair (dots.mocr + Qwen on a GPU). The
text-first reader reads those statements straight from the PDF's own text layer — the characters and where
they sit on the page — and publishes an account only when the statement's own printed figures prove the
reading exactly. It calls no model, uses no GPU and sends nothing off the machine.

Success: zero wrong published statements against Phase 1's answers (including whole banks never seen during
development), then as much reach as that bar allows on statements no parser reads.

Non-goals for v1: scanned statements (they keep the visual pair); model-assisted column labelling (a plug
point exists, nothing is built); comma-decimal amounts; statements a parser claimed but did not validate;
the Fly demo host (out of scope entirely).

## 2. Owner decisions (binding)

1. Idea "the PDF reads itself", deterministic v1 (2026-09-23).
2. Order in **Auto**: Phase 1 bank parser → text-first → visual pair. **Deterministic only**: Phase 1 bank
   parser → text-first, never the visual pair or any other model; local Tesseract OCR stays for scans, and
   text-first never reads Tesseract text (2026-09-24).
3. Truth set: statements a Phase 1 parser already validates, read locally and read-only, compared field by
   field; then reach on U755 DEV/DEV2; the sealed set once as the final exam (2026-09-23).
4. Ship bar: **zero wrong**. Every published statement matches Phase 1 on every row amount, direction and
   date, the balances and the period; any reader-caused mismatch blocks shipping. Refusals are not errors.
   Phase 1's own errors are verified from the page and recorded (2026-09-23). Currency and currency source
   also block (part 4, 2026-09-24).
5. Partial accounts: Deterministic only shows the verified accounts and marks the rest "needs review"; Auto
   also runs the visual pair and keeps whichever reader verified more accounts, text-first winning ties;
   readers are never mixed within one statement (2026-09-23).
6. Design 2 of the design panel: a standalone package that proves before publishing (2026-09-24).
7. Licensing: the product may be licensed to other companies, so **no PyMuPDF** (AGPL or paid) in text-first
   or its tests; the reader uses **pypdfium2** (BSD-3 / Apache-2.0) (2026-09-24).
8. Fly is a demo host and is not a design constraint (2026-09-24).
9. Pictured-cheque pages must not hold an account when the ledger is proven complete across them (standing
   rule, applied here in §6 A10 and §7.6).
10. Publication by confidence level: A and B once every tier they use has at least 20 truth-set statements
    measured with 0 reader-caused mismatches; C only once its Wilson 95% lower bound reaches 0.99 (2026-09-24).
11. A document with any held account is graded **review**, not validated, for text-first and the visual pair
    alike (2026-09-24). This is a ruling, not a regression: comparisons report the movement under this ruling.
12. Moving Phase 1 itself off PyMuPDF (and reviewing pdf2image/poppler) is a separate project that starts
    after text-first's single-account slice passes zero wrong (2026-09-24).
13. Binding anti-optimizer rule (docs/moneythumb-replacement/PHASE2_RULINGS.md, "Anti-optimizer rule"):
    alternatives may be enumerated only to refuse, never to choose a reading.

## 3. Where it runs

### 3.1 Trigger — one predicate for every call site (`textfirst.should_run`)

Text-first runs only when all hold:
- `TEXT_FIRST_MODE` is not `off`;
- Phase 1 published nothing and the live dispatch outcome is `unclaimed` (no parser claimed; a parser that
  recognised the issuer and declined still counts; its identity is never passed to text-first);
- in the webapp, the job error is exactly "no deterministic parser matched this statement"
  (analysis/pipeline.py raises it only for an unclaimed dispatch in deterministic mode);
- the read is native text (`doc.model == 'native-pdf-text'` or starts with `'native-pdf-text+'`), never
  Tesseract;
- the profile is a valid, unencrypted PDF classified `digital` or `mixed` (ocr/inspect.py);
- the job is not Force visual OCR and not a research run.

Ambiguous dispatches, parser crashes and Q3 policy refusals never trigger it (analysis/pipeline.py: a Q3
refusal must never start an escalation).

### 3.2 One switch

`TEXT_FIRST_MODE=off|shadow|publish` (default `off`). `shadow` runs the reader and records its verdict in
telemetry and discovery rows but publishes nothing. Discovery takes the same values as `--text-first`.

### 3.3 Webapp (`webapp/worker.py::run_job`)

After the first analysis (the Auto first analysis is deterministic whenever the pair or text-first is on):

| Mode | Text-first result | What happens |
|---|---|---|
| Auto | every account verified | published; the pair is not called |
| Auto | partial, pair enabled | the pair runs; its whole payload is kept only if it published strictly more accounts; ties keep text-first |
| Auto | partial, pair raised | text-first is published |
| Auto | refused, pair enabled | the pair runs exactly as today |
| Auto | refused, pair disabled | today's behaviour (the legacy hosted call only behind its exact opt-in literal) |
| Deterministic only | any account verified | published; held accounts show "needs review" |
| Deterministic only | refused | the job keeps "no deterministic parser matched this statement"; reason codes go to telemetry |

Deterministic only never reaches the pair: the pair guard gains `parse_mode == 'auto'`, and the deterministic
cases of tests/test_visual_pair_worker.py flip to "no pair call". Force visual OCR never reaches text-first.
Results are never mixed across readers within one statement.

### 3.4 Discovery (the official number)

`DiscoveryRunner.process` calls the same predicate right after the Phase 1 analysis, with the bytes it
already holds. Rows gain `reader` (`parser` / `text_first` / empty), `text_first_outcome`,
`text_first_reason`, `text_first_level`, appended at the end of `ROW_FIELDS`. Upgrades and adoption never
replace a text-first payload. `classify_failure` receives the parser-claimed flag so a non-validated
text-first document grades B, not C. The report shows coverage by reader (Phase 1 only, and Phase 1 +
text-first), the refusal and hold histogram, tier usage and levels. The claim-rate and unknown-layout
rollups keep counting these documents as unclaimed, which is true. The cold run of record gains
`--text-first publish` only at the ship train (§9 stage 5).

## 4. Package and boundaries

### 4.1 Location

A new top-level package `textfirst/`. Not `analysis/` (no bytes reach `analyze_document`; the escalation
tripwires forbid analysis → ocr imports), not a native-ladder rung (it runs before parser dispatch, so it
cannot express "Phase 1 first"), not `vlm/` (those files feed the pair manifest; text-first must not move
pair caches, and pair edits must not silently move text-first's measured results).

### 4.2 Modules

| Module | Role |
|---|---|
| `__init__.py` | public API: `mode()`, `should_run()`, `read_statement()`, `TextFirstOutcome` |
| `reasons.py` | closed refusal, hold, tier and evidence codes |
| `params.py` | frozen thresholds; `manifest()` |
| `glyphs.py` | the only pypdfium2 importer: fail-closed glyph census and visibility model, `selftest()` |
| `layout.py` | words, visual lines, cells, furniture, page sequence, visual-line page text |
| `tokens.py` | Decimal money and date grammar |
| `lexicon.py` | generic header, label and section vocabulary (no bank names, no values) |
| `currency.py` | printed currency, else the owner's USD/CAD rule |
| `tables.py` | headers, panels, columns, continuation; `ColumnLabeller` plug point |
| `rows.py` | row grammar, date binding, direction, order |
| `figures.py` | accounts, period, anchors, totals, counts, daily balances |
| `accounting.py` | every printed amount claimed exactly once; hidden figures |
| `proof.py` | the admission proof and the residual-alternative refusal |
| `confidence.py` + `calibration.json` | proof levels and measured bounds (counts only) |
| `publish.py` | the only analysis importer: Statement → reconcile → analyze_statement → payload |

### 4.3 Import boundary (pinned by an AST test)

- `pypdfium2` is imported only by `textfirst/glyphs.py`. `fitz` / `pymupdf` are forbidden everywhere in
  `textfirst/` and in its tests.
- Only `textfirst/publish.py` imports from `analysis`, and only the publication contract: `analysis.schema`,
  `analysis.reconcile.reconcile`, `analysis.pipeline.{analyze_statement, AccountRosterEntry, DocumentReport,
  identify_internal_transfers}`, `analysis.serialization.document_report_to_dict`, `analysis.config.Settings`,
  and `telemetry.record.classify_document`.
- Nothing else: no `vlm`, `ocr`, `evidence`, `layout`, parser registry, detection, extraction or bank module.
  The reader is bank-blind.
- Forbidden: `urllib`, `http`, `socket`, `requests`, `httpx`, `openai`, `google`, and the names
  `extract_statement`, `analyze_document`, `analyze_markdown`, `cached_analysis`, `VlmClient`.
- Nothing under `analysis/` or `ocr/` imports `textfirst`.
- Pure rules copied from `vlm/tables.HEADER_KEYWORDS`, `vlm.metadata` label sets and `vlm/currency.py`
  (`usd_default`) carry drift / parity tests that skip where `vlm` is absent.

### 4.4 Dependencies

`pypdfium2==5.8.0` is added, pinned, to requirements.txt (today it is only in requirements-vlm.txt). No other
new dependency. The pypdfium2 and pdfium versions enter every result's manifest.

## 5. Reading a statement

All money is `Decimal`; floats never carry money.

### 5.0 Preconditions
- `selftest()` passes (an in-memory fabricated page reproducing every probed visibility case); otherwise
  every call refuses `reader_unavailable`.
- Page count ≤ 500 (the upload maximum), else `too_many_pages`; a 60 s deadline checked per page, else
  `time_budget`.

### 5.1 Glyphs and visibility (`glyphs.py`, one page at a time)

Sources, per page:
- The text page: per character its unicode, box (`FPDFText_GetCharBox` / loose box), font size, matrix
  (direction), `FPDFText_IsGenerated`, `FPDFText_HasUnicodeMapError`, and its owning text object
  (`FPDFText_GetTextObject`).
- The owning text object: render mode (`FPDFTextObj_GetTextRenderMode`), fill and stroke RGBA
  (`FPDFPageObj_GetFillColor` / `GetStrokeColor`; alpha carries opacity), `FPDFPageObj_HasTransparency`,
  clip path (`FPDFPageObj_GetClipPath`).
- Paint order: every page object in content order (`FPDFPage_CountObjects` / `FPDFPage_GetObject`), form
  XObjects flattened recursively with their matrices; for paths the fill colour, draw mode and bounds; for
  images and shadings their bounds.

A glyph is **ink** only when all hold:
- render mode in {0 fill, 1 stroke, 2 fill+stroke} (the colour judged is the fill for 0/2, the stroke for 1);
- size ≥ 3 pt; centre inside the page's crop box; direction horizontal (matrix snaps to (1, 0));
- not a generated character; no unicode-map error on a money or date token (else `text_layer_unreadable`);
- contrast: `alpha × |L(text) − L(bg)| ≥ 0.15`, L = 0.2126R + 0.7152G + 0.0722B; `bg` is the last opaque
  (alpha ≥ 0.99) filled path painted before the glyph's text object that contains the glyph centre, else
  white; over an image painted before it, dark text (L < 0.6) is ink and light text is not;
- not covered: no opaque filled path, image or shading painted after it contains the glyph box shrunk by 0.5 pt;
- clip: a rectangular clip that excludes the glyph centre makes it not ink; a non-rectangular clip on a money
  or date token refuses `hidden_figures`;
- a money or date glyph whose text object reports transparency with an alpha that is not opaque is not ink.

Duplicates: the pdfium text page already emits text drawn twice (fake bold, exact double) once (probed
2026-09-24 on a fabricated page). As a second guard, a glyph with the same character within 0.2 × size in x
and y of an earlier ink glyph is dropped.

Figure-shaped runs of non-ink glyphs (money or date tokens) become `HiddenMark(page, bbox, kind)` with no
text; §5.8 judges them. Other document refusals: `rotated_figures` (a money or date token not horizontal);
`ocr_text_layer` (≥ 80% of a page's glyphs not ink and images cover ≥ 50% of it; Auto sends it to the pair);
`text_layer_unreadable` (any pdfium error; the reader never keeps a partial read). An image page has no ink
and images cover ≥ 50% of it. Only the current page's glyphs are held in memory.

### 5.2 Words, lines, cells, furniture (`layout.py`)
- Words: glyphs on one baseline band sorted by x, broken at a space or a gap > 0.25 × size.
- Lines: a word joins a line when vertical overlap ≥ 50% of the smaller height — lines follow the page, not
  the content stream. A money or date word overlapping two lines by ≥ 30% each refuses
  `line_assignment_ambiguous`.
- Cells split at gaps ≥ 1 em; header labels at gaps ≥ 0.6 × size.
- Furniture: digit-normalised text recurring within ±2 pt in the top or bottom 12% of the page on at least
  50% of pages (minimum 2). A line carrying money is never furniture.
- Page sequence: every printed "Page n of M" must match the physical page count and position, else
  `page_sequence_incomplete`.
- Page text: visual lines joined by newlines, one line per printed row. It is the markdown and the sheets
  handed to analysis, and the input to currency and period detection.

### 5.3 Accounts and document facts (`figures.account_sections`, `currency.py`)
- Account keys: the last 4 digits on account-label lines. One key or none: one section. Two or more (slice
  B; slice A refuses them): a key's section starts at its first label line followed, before any other key's
  label line, by an opening or closing label or a ledger header; earlier lines form the preamble; a preamble
  summary line carrying a key feeds that account's candidates, which must agree; a key seen only in the
  preamble goes on the roster held `no_rows`; interleaved sections refuse `account_sections_ambiguous`.
- Non-deposit markers (minimum payment due, payment due date, APR, credit limit with new balance) hold that
  section `not_a_deposit_account`; if no deposit section remains, the document is refused.
- Comma-decimal amounts in money columns refuse `unsupported_number_format`.
- Currency, resolved before dates: printed ISO codes or a denomination line (all must agree, `printed`);
  otherwise the owner's USD/CAD rule applied to institution lines (non-row, non-prose lines in page 1's top
  band or furniture that contain an institution word; row descriptions never count); Canadian evidence
  without a Canadian bank name gives `currency_unproven`; conflicts give `currency_conflict`.

### 5.4 Tables and columns (`tables.py`)
- Header: a line (or two stacked lines ≤ 1.3 line-heights apart, the second made only of lexicon words)
  with no money or date token, every cell ≤ 4 words, at least one cell mapping to `date` and one to a money
  role (debit, credit, amount, balance). Unknown cells map to `other`. A table without a qualifying header is
  never read; no headerless column guess is ever made.
- k-up panels: when the header's role sequence repeats k ≥ 2 times on one line, the table is split at the
  midpoints between groups; each panel is read alone and dates never cross panels.
- Two date columns: the one labelled post / posted / posting is the row date (tier `two_date_columns`);
  otherwise the account is held `date_column_ambiguous`.
- Section heading: the nearest non-furniture, money-free line at most 3 lines above the header (x-overlap for
  panels) and after the previous table; only credit words → credit table; only debit words (cheques
  included) → debit table; otherwise undirected.
- Body: from the header to the first of a "Total …" line with no date cell (a subtotal that must equal its
  column's rows since the previous total to the cent, else `section_total_mismatch`), a closing-label line,
  another header or heading, a gap > 3 × the median row pitch, or the page end.
- Continuation onto the next page: the next page's first non-furniture lines join the open table when the
  header repeats with the same role sequence and positions within ±3 pt (`continued_headered`), or every money
  token aligns with the open table's money columns within ±3 pt and no heading intervenes (tier
  `continued_aligned`); otherwise money accounting judges them.
- Columns: body money tokens clustered by right edge at 2.0 pt; each cluster maps to exactly one money label
  whose [x0 − 0.5 em, x1 + 1.5 em] holds its right edge; none → `money_column_unlabelled`, two →
  `money_column_ambiguous`; money in an `other` column → `money_column_unlabelled`. The date band is the date
  label widened to the date tokens at its left; the description band lies between the date band and the first
  money column (money in it is description money). Words outside [first.x0 − 1.5 em, last.x1 + 1.5 em] form
  side blocks (two-column pages).
- Figure grids: consecutive non-table lines with ≥ 2 aligned cells become label-over-value grids (horizontal
  summaries). A grid with only date and balance roles, or captioned as daily balances, is a daily-balance
  table (k-up allowed).
- `ColumnLabeller` plug point: v1 ships `LexiconLabeller` only. A later model labeller may only propose roles
  for `other` cells, the proofs stay unchanged, and Deterministic only pins `LexiconLabeller`.

### 5.5 Rows (`rows.py`), per table and panel
- Line classes: DM (a date cell and one amount cell), M (one amount cell), D (a date cell only), T (text only),
  ANCHOR (an opening, closing or carry-forward label with money only in the balance or amount column), X
  (anything else carrying money in money columns, including two amounts on one line and an unlabelled
  balance-only line; X holds the account `rows_unplaced`).
- Date binding, each row records its tier:
  - `own_cell` (DM);
  - `date_above`: a D must be followed by at least one M before the next D or DM; each M takes the nearest D
    above. Refused as `date_unparsed`: a D followed directly by a D, a D left at a table's end (catches
    date-below layouts), an M before any date in a table;
  - `same_day`: an M takes the date of the nearest DM above, in date-monotonic tables only, and only with a
    binding witness ruling out the mirror layout: (w1) the table, through its proven continuations, ends with
    at least one undated M after its last dated line; (w2) printed balances fall exactly on the last row of
    every day group under this binding; (w3) a printed daily-balance table equals the rebuilt end-of-day
    balance on every printed day. Otherwise held `date_binding_unwitnessed`. When every row prints a balance,
    only (w1) or (w3) can witness;
  - `same_day_across_page`: the first row of a continued page takes the previous page's last date, only under
    a proven continuation.
- Anchor lines' dates never date rows. Date tokens in the description band are description text.
- Exact coverage: every date cell in a ledger date column is the source of one contiguous row group or is an
  anchor's date; an unused date cell holds `posting_dates_uncovered`.
- Order and year: a component > 12 fixes MDY or DMY for the document; both fixed, or neither fixed with both
  orders placing every date inside the period → `date_order_ambiguous`. The year is the unique one placing the
  date inside [start, end]; none → `period_mismatch`.
- Direction, in precedence: a labelled debit or credit column; a printed sign in an amount column (leading or
  trailing minus, parentheses, CR/DR; negative means debit); the section heading (any printed sign must agree;
  a cheque-number table is debit, tier `direction_checks_table`); the balance delta only when every row prints
  a balance and |Δ| equals the amount exactly (its own tier, carrying R14's chain-derived-direction flag).
  Otherwise `direction_unknown`.
- Descriptions: a T line attaches to the row above; T lines before a group's first M attach to that M.
  Descriptions are outside the ship bar.
- Printed order: a table with running balances keeps printed order; dates never increasing and sometimes
  decreasing → newest-first, reversed; both → `date_order_break`. A table without balances is stable-sorted by
  date and may not use `same_day`. The account ledger is one running-balance table as printed, or sectioned
  tables stably merged by (date, printed position).

### 5.6 Printed figures (`figures.py`, non-row lines only)
- Period: ranges on lines with period context words or in the top 30% of page 1, and "Beginning/Ending
  balance on <date>" pairs. A range labelled "statement period" takes precedence; disagreeing labelled ranges,
  or disagreeing unlabelled ranges without a label, refuse `period_ambiguous`. Span 1–100 days. A section that
  prints its own range uses it. Two periods or two "Page 1 of N" runs in one scope refuse `multiple_statements`.
- Opening and closing: label-bound (the one money token right of the label on the same line, or the aligned
  cell under it in a grid); every occurrence agrees to the cent; the opening only from the section's first page
  or the ledger's first anchor; later "balance forward" lines are continuity checks; no anchor is ever derived.
- Totals and counts: label-bound direction totals with optional counts; category totals map to the section
  whose heading matches after normalisation; unmappable totals are never used (money accounting still claims
  them).
- Evidence-only figures (average, available or minimum balance, YTD, interest rate, APY, overdraft limit,
  per-item fee) are recorded, never used; the bank's average balance is evidence only (ADB doctrine).
- Daily balances from daily-balance tables, dated the same way as rows.
- Idle account: opening and closing printed and equal, no rows, no dated money line.

### 5.7 Chronological statement
Each proven ledger becomes a `Statement` in `publish.py` (§7).

### 5.8 Money accounting and hidden figures (`accounting.py`)
Every money token on every non-furniture line is claimed exactly once, by: a row amount or balance; an
anchor; a label-bound total, subtotal, count or grid cell; a daily-balance cell; an evidence-only figure;
description money; or prose money (the line has ≥ 5 words with ≥ 3 lower case, does not start with a date
token, lies outside every table's vertical extent, and the money token is followed by ≥ 2 words on the same
line). Unclaimed inside a section holds that account `unaccounted_money`; in the preamble it refuses the
document. A HiddenMark intersecting a table region or a figure line refuses the document `hidden_figures`.

## 6. Admission proof (`proof.py`)

An account publishes only if all hold. Money is Decimal and every tolerance is zero.

- **A1 Document**: no document refusal (§5.0–5.3, `hidden_figures`).
- **A2 Period**: exactly one printed period; every row date in [start, end] with no grace; printed label
  dates agree with it.
- **A3 Anchors**: label-bound opening and closing, every candidate equal, none derived. Recorded anchor tier:
  `chain` (first balance − first signed amount = opening and last balance = closing), `two_places`, `box`
  (printed opening, credits, debits, closing identity) or `label_only`. Both anchors `label_only` is its own
  tier `anchors_label_only`, disabled on any reader-caused mismatch. (Nothing downstream compares the opening
  with the page; this is where it is proven.)
- **A4 Sum identity**: opening + Σ signed amounts = closing, to 0.00 (stricter than reconcile's 0.01).
- **A5 Continuity**: every printed running balance, carry-forward and mid-ledger balance equals the cumulative
  sum exactly, checked at the last printed balance of each same-day group.
- **A6 Printed totals and counts**: every mapped direction, category or section total equals its rows
  (`totals_mismatch`); every mapped count equals the row count (`count_mismatch`).
- **A7 Independent evidence**: at least one of `running_balances` (every date group ends with a printed
  balance and A5 holds), `direction_totals` (both printed and matched), `daily_balances` (every printed day
  matches), `section_totals` (every row in a section whose total matched; amount evidence only). Otherwise
  `evidence_insufficient`. The sum identity alone never publishes.
- **A8 Direction**: every row's direction comes from a §5.5 source. Zero-sum-flip refusal: label-derived
  directions can only be wrong as whole groups; if any non-empty subset of at most 12 such groups sums to zero,
  the account is held `direction_underdetermined` unless every row in those groups prints a running balance
  proving its sign; more than 12 groups also holds.
- **A9 Posting days**: every row dated by `own_cell`, `date_above` or a witnessed `same_day`; exact date-cell
  coverage; no dangling D; tables inheriting dates are date-monotonic.
- **A10 Completeness**: money accounting passes and the page sequence is complete. An image-only page inside
  the account's page span (for example pictured cheques) is allowed when the running-balance chain crosses it
  unbroken, or both direction totals and both counts match; otherwise `image_page_unproven`. Such a proven
  page is passed to analysis as physically present (§7.6).
- **A11 Uniqueness and residual alternatives**: every choice point has exactly one candidate. A closed list of
  residual alternatives is checked — the mirror date binding, a flipped zero-sum group set, the other numeric
  date order, the other of two date columns — and if one is well-formed and would also pass A2–A10, the account
  is held `ambiguous_reading`. Alternatives are enumerated only to refuse, never to choose.
- **A12 Tiers and level**: every tier used is enabled (≥ 20 truth-set statements, 0 reader-caused
  mismatches, else `tier_disabled`), and the account's level is publishable (§8).
- **A13 Downstream, independent**: `reconcile(stmt).ok` with `summary_ok` and count matches not False;
  `analyze_statement` succeeds with `metrics.adb_ok is True`; `classify_document` of the one-account payload is
  `validated`. Otherwise `downstream_not_validated`.

Posting dates are proven from the print by geometric binding, exact date-cell coverage and the binding
witness; in addition `analyze_statement` receives the visual-line page text as markdown so
`posting_dates_cover_source` sees real posting rows. No SOURCE_POSTING_DATES block is ever emitted.

Document result: `published` (every account proven and published, or idle), `partial` (at least one
published, some held), `refused` (a document refusal, or `no_account_verified`). Text-first never emits a
statement-contradiction verdict; a held account is simply held. A refusal never quotes document text.

## 7. Output and product surface

### 7.1 Result
`TextFirstOutcome`: `status` (published | partial | refused), `reason` (closed code), `payload`
(`document_report_to_dict(DocumentReport)`; one account → today's shape; several → a `document` block with
`account_roster`, every printed account published, idle with its printed balance, or held with codes and no
unproven figure), `verified_accounts`, `account_count`, `fully_verified`, `accounts` (codes only), `audit`
(counts, tier usage, page holds, timings; never text or values), `manifest`.

### 7.2 Labels
Every published account: `model_used = 'text-first-v1'`, `escalated = False`, `bank = None` (no parser's
knowledge is borrowed), analysed with `dispatch=None`. `doc.model` stays the native token, so the source path
stays `native` and the cost $0. The dashboard's "Parser used" shows **Text-first reader v1**.

### 7.3 Served annotation and confidence
`analysis['text_first'] = {version, status, reason, accounts: [{index, status, level, reasons}], manifest}`,
stamped when served. Each published account carries `text_first_confidence` (§8). New hold codes get
plain-English dashboard labels; a "Verified by" row lists the evidence and the level with its measured bound.

### 7.4 Telemetry
The inline non-model label set in telemetry/record.py becomes a named `NON_MODEL_ANALYSIS_LABELS` including
`text-first-v1` (a test holds it equal to `textfirst.MODEL_USED`), so a text-first payload is never billed as
a model call. The label deliberately lacks the `-deterministic` suffix so `reconstructed_claim` never names a
parser that declined. The record gains a closed `text_first` section and a `text_first` timer stage. No cache
in v1 (the reader is milliseconds per page); the manifest hash is ready to serve as a future key.

### 7.5 Document grading (owner ruling 11)
`classify_document` grades a document with any held roster account `review` (reason `account_held`), for
text-first and the visual pair alike. Comparisons and the cold run report this movement explicitly as the
2026-09-24 ruling.

### 7.6 Missing-page check (owner ruling 9)
`analysis.pipeline.assess_document_integrity` gains an optional `proven_present_pages: frozenset[int] | None`
(default `None`, threaded through `analyze_statement`). Pages in it count as physically present for
`missing_declared_statement_page`. Only `textfirst/publish.py` passes it, and only for image-only pages proven
under A10. Every Phase 1 caller is unchanged and byte-identical; a genuinely absent page still flags.

## 8. Confidence

- **Level A**: running or daily balances on every posting day, plus direction totals or a proven summary box.
- **Level B**: running or daily balances on every posting day, or both direction totals and both counts.
- **Level C**: any other combination satisfying A7.

`calibration.json` (counts only, per `TEXT_FIRST_VERSION` and manifest) holds each level's measured
publications and reader-caused mismatches. The dashboard shows the level, its evidence and "measured 0 wrong in
N (95% lower bound x)" from the Wilson bound. Publication (owner ruling 10): A and B once every tier they use
has ≥ 20 truth-set statements at 0 wrong; C only once its Wilson 95% lower bound ≥ 0.99 (about 381
publications at 0 wrong). A result whose manifest differs from the calibrated one has no bound and is not
publishable until the bench is re-run. It is a measure of proof, not a probability.

## 9. Measurement

Privacy throughout: statements are read locally and read-only; public outputs carry counts and digests only;
value-level detail and paths live in `*.private.json` files outside the checkout; tests, code and commit
messages never carry real statement values; tests use hand-written fabricated PDFs only (no PyMuPDF).

- **Stage 0 — floor**: settle the test floor (the two red guard tests; the tests/test_escalation_router.py
  collection error; the modules that need pypdfium2, fixed by the requirements pin); freeze the manifest for
  every measurement run.
- **Stage 1 — fabricated suite (CI, every commit)**: positive layouts match their truth files field by field
  (the layouts of tools/phase3_pair/synthetic_statements.py — running-balance, newest-first, end-of-day,
  category sections, a pictured-cheque page, and its sum and missing-page negative controls — ported into the
  PyMuPDF-free builder `tests/textfirst_fabricated.py`, because that module imports fitz at load; plus new
  builders: k-up cheques, two-line headers, date once per day with and without a witness,
  date above, date below (must refuse), two date columns, a continued table, a daily-balance grid, subtotal
  sections, multi-account with idle and held accounts, a CAD statement, a two-column page, a pictured-cheque
  page proven by the chain). Adversarial controls must be refused or held: hidden figures (render mode 3,
  opacity 0, black on black, pale grey, covered, clipped, off-crop), fake bold, an OCR text layer, a net-zero
  column swap, compensating flips, a "Total" merchant, a credit-card look-alike, a missing page, a stray
  undated amount. Every refusal, hold and tier code has at least one fixture. Also: the AST boundary, a socket
  tripwire (`run_job(parse_mode='deterministic')` on a fabricated unclaimed PDF with the pair and the hosted
  opt-in set, while network connects raise, must finish with a text-first payload and no analysis model call),
  worker routing in both modes, discovery columns, the telemetry label, lexicon drift, currency parity, and a
  privacy canary proving refusals never quote text.
- **Stage 2 — Phase 1 truth set (development)**: the 2,661 digital Phase-1-validated statements of the run of
  record (72 parsers, 43 bank folders), kept only while Phase 1 still validates them at the bench tag.
  `tools/textfirst/split.py` (seed `textfirst-v1-banks`) splits whole bank folders about 60% TUNE / 25%
  BANK-HOLDOUT / 15% FINAL-BANKS (sealed), with at least one top-5 bank in each held split and the two
  multi-account statements placed by recorded override (one TUNE, one BANK-HOLDOUT). Reach metrics cap each
  parser at 25 statements per split; the wrong count is uncapped. `tools/textfirst/bench.py` recomputes Phase 1
  live exactly as discovery does, runs `read_statement` on the same bytes with the trigger bypassed, and
  compares: blocking — period, opening and closing, the multiset of (date, cents, direction) and the row count,
  running balances where both print one, the ADB and daily ledger recomputed on both sides, currency and
  currency source; reported only — stated totals and counts, descriptions, account key. Verdicts: MATCH,
  READER_MISMATCH, PHASE1_MISMATCH (adjudicated from the page), REFUSED(code), HELD(code), PARTIAL. Every
  published mismatch is opened from the page and recorded privately (sha16, field class, verdict; no values). A
  reader error blocks shipping until the rule is fixed with a fabricated reproduction, or its tier is disabled.
  BANK-HOLDOUT is looked at no more than 3 times; a bank whose failure drove a code change is burned (moved to
  TUNE) and recorded. During stages 2–3 the pair's sealed sets (EVAL2 and other holdouts) are refused by
  `vlm/partitions.refuse_holdout`; stage 4 opens EVAL2 once, through an explicit exam flag recorded in the
  run's receipt.
- **Stage 3 — reach on no-parser statements**: the production trigger path on U755 DEV, then (only once DEV is
  clean) DEV2. Every publication is checked against the page; where the visual pair also verified an account,
  every row is cross-checked. Zero wrong is required. Reported: reach against the pair's current results,
  refusal and hold reasons, how often Auto would keep each reader. No tuning after DEV2 is opened except fixes
  that change no DEV2 verdict.
- **Stage 4 — sealed exam, once**: on the final tagged code, FINAL-BANKS against Phase 1 and the sealed EVAL2.
  Pass: zero reader-caused mismatches in both; refusals allowed. `calibration.json` is then frozen.
- **Stage 5 — official number**: two cold runs on one tree, `--text-first off` and `--text-first publish`. The
  `off` run reproduces today's rows byte for byte apart from the new columns (and apart from the ruling-11
  grading movement, reported separately). Coverage is reported with and without text-first, split by reader.

Reported each run (counts only): published / eligible (raw and parser-capped); matches / published (must be
100%); Phase 1 errors adjudicated; refusal and hold histograms; per-tier results; per-level counts with Wilson
and rule-of-three bounds; reach per bank bucket and parser; p50 / p95 / max time per page and document; peak
memory.

## 10. Slices and rollout

| Slice | Delivers | Rough size |
|---|---|---|
| 0 | test floor, pypdfium2 pin, the PyMuPDF-free fabricated-PDF builder (hand-written PDF bytes: text with render mode, colour, opacity, fills, images, clips, forms) with the ported synthetic layouts, `selftest()` and its golden test | ~2 days |
| A | the reader, proofs and single-account publication; worker wiring in both modes behind `TEXT_FIRST_MODE` (pair guard gated by parse_mode, test flip); discovery flag and columns; telemetry label; dashboard name; the AST boundary, socket tripwire and guard roots; the missing-page parameter; split + bench; TUNE and the first BANK-HOLDOUT look. Documents with two or more accounts refuse | ~12–14 days |
| B | multi-account roster (published / idle / held), per-section non-deposit holds, the Auto partial and tie rule, ruling-11 grading, the second BANK-HOLDOUT look | ~5–6 days |
| C | calibration and the dashboard confidence display, U755 DEV then DEV2, the FINAL-BANKS + EVAL2 exam, the cold run with `--text-first publish` | ~5–6 days |

The first implementation plan covers slices 0 and A; slices B and C each get their own plan after A's
zero-wrong checkpoint, so they can use what A measured. Each slice gets an independent adversarial review
before it is merged; the owner merges. Rollout: `shadow`
locally → `publish` locally after TUNE and BANK-HOLDOUT show zero reader-caused mismatches → `publish`
everywhere after the exam. After slice A passes, the separate Phase 1 PyMuPDF migration may start.

## 11. Existing code touched

- `webapp/worker.py`: the text-first block after the first analysis; the pair guard gains `parse_mode ==
  'auto'`; the partial comparison and tie rule; text-first survives when the pair raises; the served
  annotation.
- `tests/test_visual_pair_worker.py`: the deterministic cases flip to "no pair call".
- `discovery/runner.py`, `discovery/cli.py`, `discovery/report.py`, `tools/train/coldrun.sh`: the hook, flag,
  columns, reports; row-field pin tests updated.
- `telemetry/record.py`: `NON_MODEL_ANALYSIS_LABELS`, the `text_first` section, ruling-11 grading.
- `analysis/pipeline.py`: the optional `proven_present_pages` parameter (default off).
- `webapp/static/app.js`: reader display name, hold-code labels, "Verified by" row.
- Guard tests: `textfirst` joins the truth-firewall roots, the hardcode and fail-open-money scans, currency
  provenance modules, and the corpus gate's excluded callers; the `decide()` call-site pin is unchanged.
- `requirements.txt`: `pypdfium2==5.8.0`.

Unchanged: Phase 1 payloads, `ANALYSIS_STAGE_VERSION`, the pair manifest and caches, declared refusal
literals.

## 12. Risks

- Reach may start modest: strict rules (headers required, money accounting, witnessed date binding, hidden
  figures, single-account in slice A). Measured by the refusal histogram; each relaxation needs measured
  zero-wrong evidence.
- Visibility edge cases (soft masks, blend modes, unusual clips): handled conservatively on money and date
  tokens; the arithmetic and money accounting remain the net; fabricated fixtures cover each case.
- An unforeseen date layout could pass the grammar; a fold into a day that keeps another row is invisible to
  arithmetic. Mitigated by the witness, exact coverage, monotonicity, visual-line markdown, the tier gate and
  whole-bank holdouts.
- A wrong printed range taken as the period: context words, uniqueness, the 100-day limit, label-date checks.
- Phase 1 and text-first can both be plausible and disagree (posted vs transaction date columns): each case
  blocks until adjudicated from the page.
- The balance-delta direction tier can mislead when a balance-looking column is not a running balance: its
  own tier, R14's flag, disabled on any mismatch.
- Copied helpers drift: drift and parity tests.
- Overfitting or burning holdout banks: whole-bank splits, per-parser caps, the look budget, recorded burns.
- The test floor is not green at HEAD; new failures must be told apart from the recorded baseline.
- Ruling 11 moves some visual-pair documents from validated to review; reported as the ruling's effect.

## 13. Closed vocabularies (initial)

Refusals: `reader_unavailable`, `reader_error`, `text_layer_unreadable`, `too_many_pages`, `time_budget`,
`no_visible_text`, `ocr_text_layer`, `rotated_figures`, `line_assignment_ambiguous`, `hidden_figures`,
`page_sequence_incomplete`, `multiple_statements`, `unsupported_number_format`, `not_a_deposit_account`,
`currency_conflict`, `currency_unproven`, `period_not_printed`, `period_ambiguous`, `period_unsupported`,
`no_ledger_table`, `account_sections_ambiguous`, `unaccounted_money`, `no_account_verified`.

Holds: `anchors_underdetermined`, `anchor_disagreement`, `no_rows`, `rows_unplaced`,
`money_column_unlabelled`, `money_column_ambiguous`, `date_unparsed`, `date_order_ambiguous`,
`date_column_ambiguous`, `date_binding_unwitnessed`, `posting_dates_uncovered`, `period_mismatch`,
`direction_unknown`, `direction_underdetermined`, `ambiguous_reading`, `sum_mismatch`, `continuity_break`,
`totals_mismatch`, `count_mismatch`, `section_total_mismatch`, `evidence_insufficient`, `unaccounted_money`,
`image_page_unproven`, `not_a_deposit_account`, `tier_disabled`, `downstream_not_validated`,
`date_order_break`.

Tiers: `own_cell`, `date_above`, `same_day`, `same_day_across_page`, `two_date_columns`, `kup_panel`,
`continued_aligned`, `direction_column`, `direction_sign`, `direction_section`, `direction_checks_table`,
`direction_balance_delta`, `anchors_label_only`, `image_page_proven`, `currency_jurisdiction_default`,
`multi_account`.

Evidence: `running_balances`, `direction_totals`, `daily_balances`, `section_totals`, `counts`.

## 14. Later (not v1)

A model column labeller behind `ColumnLabeller` (Auto only); statements a parser claimed but did not validate;
comma-decimal amounts; headerless tables; Phase 1's PyMuPDF migration and the poppler review (separate
project, owner ruling 12).
