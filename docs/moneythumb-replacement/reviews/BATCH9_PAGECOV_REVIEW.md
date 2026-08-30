# BATCH9 PAGECOV — independent adversarial review of `wave9-pagecov`

Reviewer: independent Opus cell (the same one that reviewed HUNT9 and COMMSEC9). Base
`train9` at `8da8239`, tip `6c0f628`, worktree `.claude/worktrees/mt9-pagecov`. Run of
record `TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`, cold cache
`.claude/recovery/webapp_data_train8_cold` (read-only). Nothing was asked of the cell.
Beyond re-running its instruments I opened the ORIGINAL PDFs read-only — the one source
neither the probe nor the census can see — because the card's whole outcome turns on what
is physically on a sheet. My regex-bearing instruments were written with a file tool and
byte-checked (0 control bytes); the worktree was clean before and after.

## Verdict

**CONFIRMED WITH FINDINGS.** 0 BLOCK · 3 MAJOR · 3 MINOR.

`newly validated = 0` is correct and every one of the fourteen flags is correct — I
verified all four classes against the paper itself and could not overturn one. The
refusal to count a text-empty sheet is the right call under Gustavo's rule for this card.

But the sheet those eight documents are refused over is **not blank** — it is a fully
inked, supplied page — and two of the record's supporting claims do not survive
re-measurement: the census's "raises nothing anywhere" is measured over the wrong half of
the archive, and the branch adds an unclassified analysis caller of its own while
attributing the resulting failure entirely to its base.

## 1. Re-measurement table

| claim | re-measured | agrees |
|---|---|---|
| no production change | `git diff --stat 8da8239 6c0f628 -- analysis ocr webapp discovery telemetry benchmark corpus_gate.py` → **empty**; branch = W3 + two `tools/pagecov_*.py`, all owned | ✔ |
| instruments unwired | `grep pagecov_` over `analysis ocr webapp discovery telemetry benchmark tests corpus_gate.py`: **0** | ✔ |
| population is 14, not the card's 11 | the three CP-DECLINES movers do carry the flag at this base and not in the run of record (§4, MINOR-2) | ✔ |
| probe table: sheets / printed / declared / denominators / missing / unlabelled / tags / class | re-run at the tip: **reproduces the W3 table row for row, all 14** | ✔ |
| `TRACE-DISAGREES` 0 | probe re-run: `flag probe/published` **True/True on all 14** | ✔ |
| class split 4 / 8 / 1 / 1 | `a_SHEETS_GENUINELY_ABSENT` **4**, `a_DECLARED_SHEET_CARRIES_NO_TEXT` **8**, `a_LABEL_GLYPHS_DESTROYED` **1**, `b_DECLARATION_FORM_UNREAD` **1** | ✔ |
| (a) four uploads are genuinely partial | **from the PDFs**: declared 6 / carries 3 · declared 6 / carries 3 · declared 5 / carries 4 · declared 3 / carries 2 — short by 3, 3, 1, 1 physical pages. No reading can clear these | ✔ (independently) |
| (a″) the citizens label glyph is destroyed, not misread | **from the PDF**: 10 pages, **0 extractable characters on every one** — a pure image scan. Every digit is Tesseract's, so the loss is OCR, not the native-text rung and not the paper | ✔ (mechanism confirmed) |
| (b+c) the texas_first fix changes no decision | **from the PDF**: 11 pages, 0 extractable characters — also a pure scan. Reading the no-space form cannot clear it: the document supplies 11 sheets against a declared 14, so `len(printed_sheets) >= declared_total` fails whatever the labels say. `form_widened` and `majority_denominator` both clear **0** | ✔ |
| whole-archive census: 3,380 · 29 no text · 1,425 no declaration · 1,926 with | re-run: **identical**, all four numbers | ✔ |
| form counts 1926 / 1334 / 79 / 74 / 42 / 5 / 0 | re-run: **identical** | ✔ |
| `form_widened` cleared 0, RAISED 0 | re-run: **0 changes** — but see **MAJOR-2**: this is measured only over the 1,926 | ✖ incomplete |
| `majority_denominator` clears 1 `failed`, genuinely short | re-run: **1** — sheets 13, printed 4, declared 12, majority denominator 2. Refused on merit, correctly | ✔ |
| `blank_sheet_counted` clears 11 (5 review, 6 failed), raises 0 | re-run: **11 — 5 review + 6 failed**, 0 raised; the 8 of this population plus 3 others | ✔ |
| outcome counterfactual: 8 of 8 `review → validated`, 0 flags | re-run `--outcome-counterfactual`: **8 of 8 `validated/approved`, flags 0**. No other flag fires, so the posting-date and coverage checks really are satisfied | ✔ |
| preserved 128/128 identical across six readers | at the tip, one run: population 148, **preserved 128 of 128, payload identical 128**, changed 0, regressions 0, 20 unchanged non-validated — **EXIT=0**. The worktree's `cohort_replay` already carries the stricter empty-container flatten | ✔ |
| 26 assertions across 7 test files | counted: `test_analysis` 10 · `test_corpus_gate_outcomes` 6 · `test_filename_boundary` 5 · `test_diagnostics` 2 · `test_telemetry` 1 · `test_telemetry_corpus` 1 · `test_artifact_cache` 1 = **26**, files exactly as named; all pass but for the excused failure | ✔ |
| the pinned Columbia document is now a parser refusal | `PINNED_REFUSALS` carries it with "no deterministic parser matched this statement"; the gate comment says the finding "no longer has a published statement to sit on" | ✔ |
| canonical guards 255 | **255 passed — EXIT=0** | ✔ |
| canonical conformance 1,270 / 40 skipped | **1,270 passed, 40 skipped — EXIT=0** | ✔ |
| the single suite failure is the base's excused one | it fails, and it is excused — but at this tip it names **four** modules, one of them this branch's (**MAJOR-3**) | ✖ partly |
| privacy, added file lines | **hit_count 0, raw_hit_count 0** over **1,021** added lines, 20 documents, against 5,012 MONEY / 729 DIGITS / 318 DATES / 8,022 WORDS printed tokens — every number matches the record | ✔ |
| privacy, commit messages | **6 commits, MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0** — EXIT=0 | ✔ |
| W3 = base + one section | base is a **byte-exact prefix** of the tip; `# §` headings 96 → 97; the new one is §PAGECOV, last | ✔ |
| instruments carry no control byte | 0 on both | ✔ |

## 2. The attack: what is actually on those eight sheets

The card's outcome rests on eight documents whose last declared sheet "extracts to ZERO
characters". Neither instrument can see past the text layer, so I opened the PDFs.

**They are not blank. They are the most heavily inked page in the document.**

| | rendered coverage of the last sheet | clearly-dark ink | grey levels | the statement page before it |
|---|---:|---:|---:|---|
| the four `linkbank` documents | **34.5%** | **16.6%** | 175 | 15.7-26.1% coverage |
| the four `core_processor_enclosures` documents | **12.2%** | **8.5%** | 239 | 4.0-12.7% coverage |

On `E002430E81CADFE7` and `68D4F9F06AA764D9` the "empty" sheet carries **more than twice**
the ink of the real statement page preceding it.

Structurally, each of those sheets is **one inline image occupying 99.5–100% of the page's
content stream** — 279,848 bytes on all four `linkbank` documents and 38,199 bytes on all
four `core_processor_enclosures` ones. Byte-identical within each group, across statements
of different months: this is the issuer's standard appended sheet reproduced in every
statement, not a month-specific page and not filler inserted per document.

So the finding is settled in the cell's favour on the fact that matters — **the sheet is
supplied, and it carries ink** — and `PAGECOV-IMAGE-SHEET` is a **real +8 candidate, not a
mirage**. It is also settled the other way round on Ocean's alternative hypothesis: this is
not a PDF whose declared last page went missing while the sheet count coincidentally
matched. The page is there.

**And the card as written would fail to find it.** See MAJOR-1.

## 3. Findings

### MAJOR-1 — `PAGECOV-IMAGE-SHEET`, as scoped, would measure zero ink on all eight and kill a real +8

The carried card says: *"a sheet that renders with ink — an embedded image or any drawing
operator — is a supplied page"*. Measured on the eight sheets it exists for:

| test | result on the eight |
|---|---|
| `page.get_images(full=True)` — embedded image XObjects | **0 on all eight** |
| `page.get_drawings()` — drawing operators | **0 on all eight** |
| rasterise and measure ink | **12.2-34.5% coverage on all eight** |
| inline-image payload share of the content stream | **99.5–100% on all eight** |

Both of the card's two named tests return zero, because the ink is an **inline image**
(`BI … ID … EI`), which is not an XObject and is not a drawing. A cell implementing the
card literally would conclude the sheets carry nothing, report the finding refuted, and
retire a genuine eight-document opportunity — the exact failure mode this review series
exists to catch, one card downstream.

The record's prose is also imprecise in a way that points the same wrong direction: §PAGECOV4
calls it "an image-only sheet … cheque images, or an appended notice". Substantively right
(it IS an image), but the natural implementation of "image" is `get_images()`, and that
returns 0.

**Correction:** re-scope `PAGECOV-IMAGE-SHEET` to say the test is *rendering* (or
counting marking operators in the content stream, inline images included), and record the
measured coverage numbers above so the follow-on cell starts from evidence rather than from
a hypothesis. The intake-layer capability it needs is unchanged; only the test is wrong.

### MAJOR-2 — the census's "RAISED 0" is measured over the half of the archive where a raise is impossible

`pagecov_form_census.reading()` returns `None` whenever the CHECK's own pattern finds no
declaration, and such a document is counted as "no page declaration" and enters **neither**
the form table **nor** the `form_widened` counterfactual. That is **1,425 documents** — 42%
of the archive.

Those are precisely the documents a form widening is dangerous on. Today they have no
`declared_total`, so `missing_declared_statement_page` **cannot** fire; after the widening
they would have one for the first time, and it can. The census is built to catch exactly
this ("a form the check newly reads can INCREASE the declared total and manufacture a flag
on a document that did not carry one") — it is simply not pointed at the population where
it happens.

Measured over those 1,425 with the cell's own `forms_on`, its own `_TRUSTED`
(`PAGE_N_OF_M_NO_SPACE`, `PAGE_N_OF_M_SPLIT_BY_CONTROL_BYTE`, `PAGE_N_SLASH_M` — the three
the record names as the (b) fix) and its own `_decide`:

| | documents |
|---|---:|
| read no declaration today — invisible to the census | **1,425** |
| … of which would GAIN a declaration from the trusted forms | **50** (43 `validated`, 7 `failed`) |
| … of which the widened reading RAISES the flag on | **7** |
| … of those, baseline **`validated`** | **3** — `0A14AC169DEA62D4`, `9C5B7D628D7511EE`, `C067BE96F6B0BE0F`, all `symitar` |

So *"reading it changes NO document's decision in either direction"* is false as a
whole-archive claim, and **"the (b) fix is inert" is the wrong conclusion** — it is not
inert, it is a three-document `validated → review` regression, which BATCH9-RULES calls
BLOCKING. On the three `symitar` documents the widened reading finds a declaration with a
denominator of 1 against 4–5 supplied sheets and manufactures a missing page 1 — the same
class of nonsense that makes `N_SLASH_M_BARE` untrusted, arriving through a form that *is*
trusted.

Nothing shipped, so this is not a regression in the branch: it is a false safety claim in
the record and a live trap in `PAGECOV-NO-SPACE-FORM`. **Correction:** extend
`reading()` to evaluate the widened arithmetic on documents with no current declaration
(returning a record rather than `None` once a trusted form supplies one), re-run, and carry
the measured raise count in the card. The card's priority should move from P3-inert to
"refused on measurement", which is a stronger result than the one claimed.

### MAJOR-3 — the branch adds a fourth unclassified analysis caller; the record blames only the base

The excused suite failure at this tip names **four** modules:

`tools/l1_design_payload_probe.py`, `tools/l1_design_reader_probe.py`,
`tools/l1_design_skip_probe.py`, **`tools/pagecov_probe.py`**.

`473be2c` on `train9` classifies **only the three L-1 probes**; `tools/pagecov_probe.py` is
in neither `ANALYSIS_CALL_SITES` nor `EXCLUDED_ANALYSIS_CALLERS` on `train9`. So composing
this branch leaves `test_every_production_caller_of_the_analysis_is_classified` **RED on
this cell's own instrument**, after the fix Ocean is relying on has landed.

The record states the failure is "the base's own excused
`test_every_production_caller_of_the_analysis_is_classified` (three L-1 design probes
unclassified; Ocean's composition miss)". True of the base; not true of this tip.

The fix is data-only and precedented twice over — `473be2c` did it for the L-1 probes, and
the W3 section immediately above §PAGECOV records another cell adding three
`EXCLUDED_ANALYSIS_CALLERS` entries for the same reason, noting the guard "requires a
decision for every new caller and refuses to pass without one". `corpus_gate.py` is outside
this card's ownership, so **Ocean must add the entry at composition** (or ask the cell to,
with ownership extended). Flagged because a green train depends on it.

### MINOR-1 — one of the eight is a PINNED corpus document, so the carried card is a ceremony

`Bank Statements/Misc/Link Bank April statement.pdf` hashes to **`AF6BD563A3D7165A`** — one
of the (a′) eight — and `corpus_gate.py` pins its verdict as `review` with this exact flag
and a pinned note quoting the declared total and the absent label. A second pinned document
carries a pinned verdict for the flag too (declares 5, labels 1, 2, 3 absent — the
class-(a) shape).

The record's anchor paragraph says "the anchor that is still live is the synthetic Wells
fixture behind the FILENAME-BOUNDARY suppression test". That understates the protection
(two real documents are pinned as well, which is a stronger anchor), and — the part that
matters — it omits the consequence: implementing `PAGECOV-IMAGE-SHEET` would move a **pinned
corpus verdict** from `review` to `validated`, changing the gate's pinned counts from
102 validated / 3 review to 103 / 2. Under BATCH9-RULES that is truth-set movement and needs
an **approved ceremony**, not merely "a ruling AND intake structure". Add that to the card so
its cost is not discovered late.

### MINOR-2 — "all twenty documents in the run of record" conflates two frames

Independently scanned, the run of record's own cached payloads carry
`missing_declared_statement_page` on **17** documents: **11 `review`** (each carrying it as
its only flag — the card's original eleven) and **6 `withheld`**. The other three of the
twenty are the CP-DECLINES movers, which are `failed` in the run of record and publish no
payload there; they carry the flag only at this branch's base. §PAGECOV2's "ALL TWENTY
documents in the run of record that carry the flag at all" is therefore loosely worded. The
population and the `TRACE-DISAGREES` 0 are right; only the frame is mixed.

### MINOR-3 — the census's JSON cannot reproduce the census's headline table

`--json` writes `records`, and a record is appended only when `record.get("changes")` — so
the artefact holds the 12 movers and nothing else. The form counts (1,926 / 1,334 / 79 / 74
/ 42 / 5) and the "no declaration 1,425" line cannot be re-derived from it, and I had to
rebuild the form population with a separate scan to name the five no-space documents. Emit
every record (or a per-form sha list) so the committed artefact backs the committed numbers.

## 4. Explicit answers

| question | answer |
|---|---|
| newly validated 0 confirmed? | **YES.** No production file changed, all six reader cohorts replay identical, and the only candidate that moves anything is the one the card refuses. |
| are the 14 flags correct? | **YES — all fourteen, verified against the paper.** (a) four PDFs are physically short by 3, 3, 1 and 1 pages. (a′) eight supply every declared sheet, and the last is an inked, supplied page with no text layer — the flag is correct *today* because the check counts text, and the honest fix is the carried card, not a weakening. (a″) one is a pure image scan with zero extractable characters, so the lost ordinal is OCR damage no reading can recover. (b+c) one is short by three sheets, so no label reading can clear it — reproduced. |
| preserved 128/128 identical? | **YES.** One run over all six readers: population 148, preserved **128 of 128**, payload identical **128**, 0 changed, 0 regressions, EXIT=0, under the stricter empty-container comparison. |
| privacy 0? | **YES** on both surfaces: added lines **hit_count 0, raw 0** over 1,021 lines / 20 documents; commit messages **0** in all four classes over 6 commits. |
| is `PAGECOV-IMAGE-SHEET` real or a mirage? | **REAL** — decisively. Every one of the eight sheets renders with 12.2-34.5% ink coverage and is a single inline image filling its content stream. But the card's own two tests (`get_images`, `get_drawings`) return **0 on all eight**; re-scope it to rendering before anyone measures it (MAJOR-1), and budget it as a pinned-surface ceremony (MINOR-1). |
| does the RV-PAGE-COVERAGE estimate retire to 0? | **YES for this card**, and correctly: 13 of 14 are the upload or the scan, and the 14th is a misread that clears nothing. The +8 does not retire — it moves to `PAGECOV-IMAGE-SHEET` with its evidence now measured rather than hypothesised. |

## 5. Recommendation to Ocean

Accept the branch. The probe-first card did what a probe-first card should: it re-derived
its own population, classified every member against measurement, priced the one change that
would move the number, and refused it under the rule it was given rather than under an
impression. Gustavo's rule — never weaken a completeness rule because reconciliation
succeeds — is honoured exactly.

Three things must not travel with it unchanged. **MAJOR-3 is composition-blocking in
practice**: add `tools/pagecov_probe.py` to `EXCLUDED_ANALYSIS_CALLERS` at the train, or the
caller-register test stays red after `473be2c`. **MAJOR-2 must be corrected in the record
before anyone reads "the (b) fix is inert"** — measured over the population the census skips,
it raises the flag on 7 documents, 3 of them validated. **MAJOR-1 must be corrected in the
carried card**, or the +8 it carries will be measured with two tests that return zero on all
eight documents.

The eight sheets are real pages with real ink. The flag on them is correct today and the
refusal is right; the opportunity is real too, and it is now measured.
