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

## Re-review (closure 77f909a) — 2026-08-30

Second independent adversarial reviewer, not the author of the review above (that
session did not survive the context turnover). Base `train9` `8da8239`, reviewed tip
`7d96c64`, closure tip `77f909a`, worktree `.claude/worktrees/mt9-pagecov`. Run of
record `TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`, cold cache
`.claude/recovery/webapp_data_train8_cold` (read-only). **Every number below is one I
produced at the closure tree.** The cell's prose was read only to know what to attack;
where my instrument and the cell's disagree I say so. My instruments were written with a
file tool into the scratchpad (0 control bytes), never committed; the worktree was clean
before this commit and carries only it.

### Verdict

**CONFIRMED — COMPOSE.** All six findings closed, the floor reproduced at the closure
tree, no production reading change. Two items travel with it and neither is on this
branch: a register key union at composition (mechanical, set difference below), and an
amendment `docs/agent-handoffs/PAGECOV-IMAGE-SHEET.md` on train9 still owes — it carries
MAJOR-1's correction in its finding paragraph but **not** in the two sections a cell would
implement from.

### Per-finding

| # | finding | verdict | claimed | I measured |
|---|---|---|---|---|
| MAJOR-1 | the card's two named tests return 0 on all eight sheets | **CLOSED** | `get_images` 0 / `get_drawings` 0; one inline image at 99.5–100 % of the content stream; 279,848 B / 38,199 B; byte-identical within each issuer group; coverage 34.5 % / 12.2 % | `get_images(full=True)` **0 on all 8**; `get_drawings()` **0 on all 8**; extractable characters **0 on all 8**; exactly **1** inline image per sheet; **279,848 B** (share **100.0 %**, stream 279,959 B) and **38,199 B** (share **99.5 %**, stream 38,378 B); payload sha256 **1 distinct value per group** — byte-identical, not merely same-sized; coverage **34.5 %** / **12.2 %**, grey levels **175** / **239** |
| MAJOR-2 | the census walks both halves, per form | **CLOSED** | 3,380 · 29 · 1,425 · 1,926; as_shipped gains 50 (43 v / 7 f), RAISES 7 (3 v / 4 f); no-space alone 23 gains, 0/0; slash form alone 7 raises; all 7 one form | identical on every cell, and the three validated raises are `0A14AC169DEA62D4`, `9C5B7D628D7511EE`, `C067BE96F6B0BE0F`, all `symitar`; the `as_shipped` raised SET equals the `only:PAGE_N_SLASH_M` raised SET; `trusted_now`, `only:PAGE_N_OF_M_NO_SPACE` and `only:PAGE_N_OF_M_SPLIT_BY_CONTROL_BYTE` each change **0** decisions over 3,380 |
| MAJOR-3 | the probe is classified; the register goes green at the train | **CLOSED** | unclassified = the three L-1 probes alone; green under train9's fix; stale 0 | the test fails naming exactly `['tools/l1_design_payload_probe.py','tools/l1_design_reader_probe.py','tools/l1_design_skip_probe.py']`; stale **0**; nothing both declared and excused; UNION with train9's register → unclassified **[]** |
| MINOR-1 | the carried card is a pinned-surface ceremony | **CLOSED** | two pinned `review` verdicts, `AF6BD563A3D7165A` and `4C96DDA28A6728FB`; 102/3 → 103/2 | both hashes verified from the pinned files themselves; both pinned `review` on this flag alone with their notes; gate verdicts unchanged |
| MINOR-2 | the twenty spans two frames | **CLOSED** | 17 in the run of record's payloads (11 `review` + 6 `withheld`) + 3 only at this base | scanned the run of record's own 2,630 cached analysis payloads: **17** carry the flag, **11** as their only flag, **6** alongside others; the three movers are `failed` in that run and publish no payload |
| MINOR-3 | the census JSON backs its own headline table | **CLOSED** | every record + totals + candidate definitions | the artefact holds **3,351** records (3,380 − 29 no-text), `shas` / `no_cached_text` / `no_declaration`, `form_counts`, `form_counts_by_half` and `candidates`; I re-derived the form table, the gain table and the change table from the JSON alone |

### What I attacked, and what survived

**MAJOR-1 — the eight sheets, opened again from the paper.** I did not take the
review's figures. My own instrument (PyMuPDF, read-only; `get_text("dict")`,
`read_contents()`, `get_pixmap()`, and a `BI … ID … EI` scanner of my own) over the eight
PDFs, each located by hashing the file and matching `content_sha256` — all eight hashes
verified:

| | last sheet chars | `get_images` | `get_drawings` | content stream | inline images | inline bytes | share | coverage | grey levels |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| the four `linkbank` | 0 | 0 | 0 | 279,959 B | 1 | 279,848 | 100.0 % | 34.5 % | 175 |
| the four `core_processor_enclosures` | 0 | 0 | 0 | 38,378 B | 1 | 38,199 | 99.5 % | 12.2 % | 239 |

Stronger than the record claims on one point: I hashed the inline payloads and each issuer
group has **exactly one distinct sha256** across its four documents, so "byte-identical
within each group" is proved rather than inferred from equal lengths. The record's coverage
figures reproduce **exactly** once the method is recovered — a grayscale page pixmap at
**dpi 50**, any pixel below 255 counted as ink; the grey-level counts (175 / 239) reproduce
at the same setting, which is what identifies the method. **The method is not written
down anywhere**, and I had to sweep dpi × threshold to find it (at 72 dpi the same sheets
measure 22.8 % / 8.7 %). See the record note below.

The closure's substantive conclusion holds in every direction: the sheet is a supplied,
fully inked page; both of the tests the card first named report nothing on it; and the
flag is still correct today because the check counts text and there is none.

**MAJOR-2 — the census, re-run whole.** One foreground run over all 3,380 shas from the
run of record's own cached text, the branch's own instrument at the closure tree
(`python -m tools.pagecov_form_census --rows <run>/rows.csv --data-dir <cold cache> --json
<private>.json`, **EXIT=0**). Every cell of both W3 tables reproduced: the population line
(3,380 · 29 · 1,425 · 1,926), all seven rows of the form table in both halves, all six
candidate rows of the change table. The decomposition is real and I checked it as a set
identity, not as a count: the documents `as_shipped` raises are *the same documents*
`only:PAGE_N_SLASH_M` raises, and the two remaining trusted forms raise and clear nothing
anywhere in the archive.

The mechanism is measured, not asserted. On the three previously `validated` documents the
widened denominator is **1** against **4, 5 and 5** supplied sheets — exactly the
"ordinal over a denominator of one" the record describes — and on the four `failed` ones it
is 29, 30, 31 and 2, which are day-of-month values. Every one is a date read as a page
declaration.

I also checked the direction this could have gone wrong in silence: `_TRUSTED` feeds the
probe's `FORM_UNREAD_ON_SHEET` tag as well as its counterfactual, so dropping a form from
it *could* have moved a document's class. The `PAGE_N_SLASH_M` regex is byte-identical
across the closure (only its `supplies` flag changed True → False), the census pins the
reviewed set in its own `AS_SHIPPED` constant, and the probe's class table is unchanged —
verified below.

**MAJOR-3 — the register, and what composition will do.** The excuse text is TRUE: I read
the probe. `published_flags()` and the `actual` arm of `blank_sheet_counterfactual()` pass
the reconstructed page list; the second arm passes `[sheet if sheet.strip() else "." for
sheet in sheets]` — a deliberately substituted partition. The probe publishes no verdict
and writes nothing but stdout and an optional private JSON. Excusing it rather than
declaring it is the correct call, and the reason says so in the one place it differs from
every entry above it.

The composition arithmetic, since Ocean will need it:

| register | tip `77f909a` | train9 `d18a5e4` | tip − train9 | train9 − tip |
|---|---:|---:|---|---|
| `EXCLUDED_ANALYSIS_CALLERS` | 30 | 33 | `tools/pagecov_probe.py` | the three L-1 design probes, `tools/l1s1_seam_probe.py` |
| `ANALYSIS_CALL_SITES` | 3 | 4 | — | `('analysis/pipeline.py', 'analyze_document')` |

No key collides. Swept callers at the tip: 36. Unclassified with the tip's register = the
three L-1 probes; with train9's register = `tools/pagecov_probe.py`; **with the union =
`[]`**. The conflict at composition is a pure append-union of disjoint keys.

### The headline claim, and the sweep

The W3 opening now says **"No production READING changes"** where it said "no production
file changes". The diff supports the corrected wording exactly and would not support the
old one. `git diff --name-only 8da8239..77f909a` = `corpus_gate.py`, the W3 log, the review
file, and the two `tools/pagecov_*.py`. `git diff --quiet 8da8239..77f909a --
analysis/pipeline.py` → **identical**; `analysis/ ocr/ webapp/ discovery/` show no change at
all; the whole of `corpus_gate.py`'s diff is one key and its comment in
`EXCLUDED_ANALYSIS_CALLERS`.

**I agree no whole-archive sweep is owed**, and on a stronger ground than "no analysis file
changed". `corpus_gate.py` IS imported by production — `discovery/inventory.py:14` — so
"nothing production imports changed" would have been false. But that importer uses only
`manifest_paths`, `read_csv` and `BALANCE_CSV`; `EXCLUDED_ANALYSIS_CALLERS` is read by
`tests/test_corpus_gate_outcomes.py` and by nothing else in the tree. A key added to a dict
that no analysis path reads cannot move a document, so the sweep would replay the base
against itself. Ocean's standing ruling holds.

Append-only holds too: the base W3 blob is a **byte-exact prefix** of the tip blob,
`# §` headings 96 → 97, exactly one `# §PAGECOV` and it is the last section. The closure
did not touch the review file above. Both instruments carry **0** control bytes.

### The one thing that still owes: `PAGECOV-IMAGE-SHEET` on train9

MAJOR-1 is closed *on this branch*. It is **not** closed in the card the finding exists to
protect. `docs/agent-handoffs/PAGECOV-IMAGE-SHEET.md` at train9 `d18a5e4` carries the
correction in its "Measured by the review" paragraph — "`get_images()` (XObjects) and
`get_drawings()` both return 0 on all eight" — and then, in the two sections a cell would
actually implement from, still names those tests:

* **The question put to Gustavo**: "when the PDF proves it carries INK — *an embedded image
  XObject or drawing operators* covering a page-sized area".
* **Method step 1**: "read-only over the PDF page objects: text operators, *image XObjects*,
  drawing operators, bounding coverage".

Both measure **0 on all eight documents**, which I reproduced. A cell that reads the card
top-to-bottom and implements the Method would land in exactly the failure MAJOR-1 was
raised to prevent, and Gustavo would be ruling on a capability that cannot detect the eight
sheets the ruling is about. **Ocean must amend both lines to rendering / marking-operator
counting with inline images included, before that card launches.** Not blocking this
branch's composition; blocking the next one.

Two smaller divergences in the same file, both in the direction of the card being staler
than the branch:

* the card's carried P3 line still reads "`PAGECOV-NO-SPACE-FORM` (`Page Nof M`, **5
  documents**, changes no decision)" — the pre-MAJOR-2 figure. Measured at this tree the
  form is printed by **28** documents and would hand **23** a declared total for the first
  time, still changing no decision on any of the 3,380. The card also does not carry W3's
  "**it must never be implemented as 'the alternative forms'**", which is the operative
  warning: the aggregate that reads safely in the card is the one that raises 7.
* the card says the widening "would RAISE the flag on 7, three of them validated" without
  the decomposition. That is conservative and therefore safe, but a cell reading it cannot
  tell that the form the card itself carries is not one of the seven.

### Record notes (no finding; nothing blocks)

1. **The rendering method is not recorded.** The coverage figures 34.5 % / 12.2 % and the
   grey-level counts 175 / 239 reproduce only at a grayscale page pixmap at **dpi 50**
   counting every pixel below 255. Nothing in the W3, the review above or the card says
   dpi, colour space or threshold, and the same sheets measure 22.8 % / 8.7 % at 72 dpi.
   A follow-on cell measuring "ink coverage" will get a different number and think the
   record wrong. One clause naming the render settings fixes it.
2. **Two decorative figures in the same table did not reproduce.** At the recovered method
   the "clearly-dark ink" column measures **15.9 %** (record: 16.6 %) on the `linkbank`
   sheets and **8.5 %** (record: 8.5 %) on the others — the second is exact, the first is
   0.7 pp out, so the dark threshold is near but not exactly the one I used. And the
   `linkbank` "statement page before it" range reads **15.7–34.9 %**, not the recorded
   15.7–26.1 %: two of the four preceding pages measure 33.0 % and 34.9 %. Both numbers
   came from the review above rather than from the cell's instruments, and neither is
   load-bearing — the claim they support, "on `E002430E81CADFE7` and `68D4F9F06AA764D9`
   the sheet carries more than twice the ink of the page before it", reproduces (34.5 vs
   15.7 = 2.2×; 12.2 vs 4.0 = 3.1×).

### The probe table, re-run at the closure tree

I re-ran the probe because `PAGE_N_SLASH_M` leaving `_TRUSTED` also feeds the
`FORM_UNREAD_ON_SHEET` tag, which feeds the CLASS — a trust change could have moved a
document's class in silence. It did not:

`PYTHONPATH=. python -m tools.pagecov_probe --shas <the 14> --data-dir <cold cache>` →
the PAGECOV3 table row for row, all 14 · `flag probe/published` **True/True on all 14** ·
**TRACE-DISAGREES 0** · classes `a_SHEETS_GENUINELY_ABSENT` **4**,
`a_DECLARED_SHEET_CARRIES_NO_TEXT` **8**, `a_LABEL_GLYPHS_DESTROYED` **1**,
`b_DECLARATION_FORM_UNREAD` **1** · counterfactuals `form_widened` **0**,
`majority_denominator` **0**, `blank_sheet_counted` **8**, `all_three` **8** — **EXIT=0**.
`A20AACF22B6A475A` keeps class **b**, so the form the closure distrusted was never what
made that document a (b).

`--outcome-counterfactual` over the same population: the eight text-empty-sheet documents,
each replayed twice, **8 of 8 `review / integrity_flags` → `validated / approved`, 0 flags**
— **EXIT=0**. The size of what the card refuses is unchanged.

PAGECOV1 reproduces too, and its lesson with it: `cohort_replay --shas` over the eleven
with `--expect-identical` → population 11, **11 unchanged non-validated, payload changed 0,
EXIT=0**; over the three CP-DECLINES movers → population 3, **3 improved (other ladder
movement up), newly validated 0, regressions 0, EXIT=0**. The population at this base
really is 14.

### Proof floor, re-run at 77f909a

| proof | claimed | I measured |
|---|---|---|
| canonical guards (5 files) | 255 | **255 passed — EXIT=0** |
| canonical conformance (7 files) | 1,270 + 40 skipped | **1,270 passed, 40 skipped — EXIT=0** |
| `python corpus_gate.py` | GREEN 105 PASS / 3 WITHHELD / 1 REFUSED; verdicts 1/3/102/3 | **RESULT: GREEN — EXIT=0.** 109 pinned PDFs (103 native, 6 committed OCR), 0 exclusions, **Outcomes 105 PASS / 3 WITHHELD / 1 REFUSED**, **Verdicts 1 refused / 3 review / 102 validated / 3 withheld**, all 15 checks PASS (runtime 794.8 s) |
| six reader cohorts, `--expect-identical` | 128/128 preserved, payload identical | populations 4 / 61 / 9 / 21 / 48 / 5 = 148; preserved **0+59+2+17+46+4 = 128 of 128**, payload identical **128**, payload changed **0**, validated regressions **0**, other ladder regressions **0** — **EXIT=0 on all six** |
| `tests/test_corpus_gate_outcomes.py` register test | fails only on the three L-1 design probes | **1 failed, 23 passed**; the assertion names exactly `['tools/l1_design_payload_probe.py', 'tools/l1_design_reader_probe.py', 'tools/l1_design_skip_probe.py']` — the branch's own probe is gone from it; stale **0** |
| `tools/pagecov_form_census.py` over 3,380, both halves, per form | the two tables | **every cell reproduced — EXIT=0** |
| `tools/pagecov_probe.py` over the 14 / the 20 | TRACE-DISAGREES 0 | **0 on both — EXIT=0** |
| privacy, added lines | 1,597 added lines, hits 0 / raw 0, against 5,012 MONEY / 729 DIGITS / 318 DATES / 8,022 WORDS | **added_lines 1,597 · hit_count 0 · raw_hit_count 0 · printed_tokens 5,012 / 729 / 318 / 8,022 · population 20, documents_read 20 — EXIT=0** |
| privacy, commit messages | 0 in all four classes | **15 commits scanned, MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0**, raw identical — **EXIT=0** |
| the 26 assertions pinning the flag across 7 test files | 26 | **26**, and the per-file split matches (`test_analysis` 10 · `test_corpus_gate_outcomes` 6 · `test_filename_boundary` 5 · `test_diagnostics` 2 · `test_telemetry` 1 · `test_telemetry_corpus` 1 · `test_artifact_cache` 1) |
| corpus-marked slice (`pytest -m corpus`, from this worktree beneath the repository) | 30 | **30 passed**, 7,503 deselected — **EXIT=0** (1,973 s under the host contention below) |
| full default suite | 7,455 passed / 43 skipped / 1 failed (the register) | **1 failed, 7,455 passed, 43 skipped** — **EXIT=1**, the single failure being `test_corpus_gate_outcomes.py::test_every_production_caller_of_the_analysis_is_classified`, naming the three L-1 probes and nothing else |

Two notes on running the floor rather than on its results.

* **The commit-message scan is vacuous without a population.** Run exactly as the closure
  brief records it — `--data-dir … --base 8da8239` — it reports `population 0`,
  `documents_read 0` and an empty token universe, so its four zeros mean nothing. With
  `--shas <the 20>` it reads 20 documents against 5,012 / 729 / 318 / 8,022 printed tokens
  and is still 0 in every class. The zeros are real; **the recorded command should name the
  population** so the next reader does not reproduce the empty form of it.
* **Four other harnesses from other sessions ran on this host while I measured** — two
  `pytest -m corpus`, a full suite, a second `corpus_gate.py` and a
  `regfp_zero_movement_sweep`, under different task parents. Nothing here mutates a tree,
  so the results stand, but the gate took 794.8 s and BATCH9-RULES' one-harness-per-host
  rule was not being honoured by whoever else was running.

### Nothing was weakened

The closure's whole non-documentary surface is three things, and none of them can move a
document:

1. one key in `EXCLUDED_ANALYSIS_CALLERS`, read by `tests/test_corpus_gate_outcomes.py`
   and by nothing else in the tree — the classification is honest and I read the probe to
   check it;
2. `PAGE_N_SLASH_M`'s `supplies` flag in the probe, True → False, which makes the probe's
   counterfactual strictly MORE conservative and whose regex is byte-identical either way;
3. the census rewritten to measure more of the archive, not less.

Neither instrument is imported by anything (`grep pagecov_` over the tree hits only the two
tools and the register string), both open the cold cache `mode=ro`, and neither writes
anywhere but its explicit `--json`. `missing_declared_statement_page` is untouched: the
production check is byte-identical, the 26 assertions pinning it pass, the gate's two
pinned `review` verdicts on it still hold, and the eight documents the card refuses are
still refused.

### Recommendation

**Compose.** The cell did the harder version of a closure: it corrected the record in the
direction that made its own earlier claim weaker (the census), corrected a claim in the
direction that made it stronger (the anchors), and corrected the headline sentence that
stopped being true rather than letting the phrase cover the new commit. Every number it
put in the record reproduces at the tree, including the two I expected to fail — the
inline-image byte counts, which are byte-identical and not merely equal-length, and the
probe's class table, which the trust change could have moved and did not.

Two things must travel with it, neither on this branch:

1. **At composition** — union the register. `tools/pagecov_probe.py` is the branch's only
   addition and collides with nothing; the union is green.
2. **Before `PAGECOV-IMAGE-SHEET` launches** — amend the card's *question* and *Method
   step 1* to name rendering or marking-operator counting with inline images. They still
   name `image XObjects` and `drawing operators`, which measure **0 on all eight documents
   the card exists for**. MAJOR-1 is closed in the record and open in the artefact the
   record was written to protect.
