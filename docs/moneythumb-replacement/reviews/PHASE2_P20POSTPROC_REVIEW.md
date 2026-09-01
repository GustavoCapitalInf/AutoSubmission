# PHASE2_P20POSTPROC_REVIEW — independent adversarial review of `wave20-postprocess`

```
CARD:      docs/agent-handoffs/P20-POSTPROCESS.md (Phase 2.0 cell B1)
BRANCH:    wave20-postprocess @ daa5988   BASE: train10 @ bea06bc   DIFF: 63 files
WORKTREE:  .claude/worktrees/rev20-postprocess (detached at daa5988), never committed
HOST:      Python 3.14.5 (CI pins 3.12 — checked, no 3.13+-only API introduced)
RUN OF RECORD: discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a
COLD CACHE:    .claude/recovery/webapp_data_train9_cold (read-only, mode=ro)
REVIEWER:  independent agent; did not write this code
VERDICT:   APPROVE WITH FINDINGS (5 MAJOR, 6 MINOR — all additive, none blocks the
           quarantine itself; MAJOR-1/2/3/4/5 should close before Ocean composes)
```

Every finding below was **reproduced at this tree**, not inferred. Every mutant was applied to
the **real committed file** and reverted with `git checkout --` in a `finally`;
`git status --porcelain` was verified empty after every mutant and at the end of the campaign.

---

## 0. Executive summary

The cell's central deliverables are real and reproduce exactly:

* The nine-function chain is quarantined on **both** paths. `git grep` over the whole tree
  finds `postprocess` with **one definition and zero callers**; `embed_image_regions` with
  **zero callers**. `ocr_page` returns `PageText(apply_admitted(raw), …)` from its single
  return site (`ocr/ocr_client.py:595`), covering both the streamed and non-streamed branches.
  `apply_admitted` is a verified no-op on the empty tuple.
* The census is executable, and its numeric-token deltas are genuinely **recomputed
  mechanically** from `input.md`/`expected.md` — never trusted from `case.json`.
* F-1 (`[a,a,a,b,c] → [a]`), F-11, and the cell's headline new finding (the
  debit/credit/balance fold in `repair_fused_amount_table`) all reproduce from the fixtures
  **and** from inputs I constructed independently. The fold is genuinely settled by
  construction; the audit's "explicitly UNPROVEN" is now proven, and the cell's reasoning about
  the gate (first and last fused header cell only, middle cells never inspected) is correct.
* All **eight** mutants in the card's mutation table are killed by the named killers.
* Cohort replay at the tip over the 179 Tesseract shas: **179/179 replayed, 36/36 previously
  validated preserved payload-identical, 0 newly validated, 0 ladder movement up or down,
  exit 0.** `tests/corpus_cache` byte-identical. `newly validated = 0` holds.

What is wrong is not the wiring — it is **the census's safety narrative and the OQ2 guard's
reach**, and both matter more than usual here because OQ1 = C makes this census *the
re-admission gate*:

* Four of the nine rows carry **absolute** claims ("a money token can never sit inside the
  removed span", "no digit is deleted") that I falsified with constructed inputs, three of them
  on the four members the census names as first in line for re-admission (MAJOR-1).
* The OQ2 issuer guard is scoped to 3 files when the card says layer-wide, and the stated
  reason for the narrowing does not hold — extending it costs **0 offenders today** (MAJOR-2).
* A registered regex name is a blanket licence: widening `_TD_MARKERS_RE` to a second issuer
  passes the whole suite (MAJOR-3).
* The register omits the two behaviors that actually pick between candidate reads by document
  content, and understates the scope of the two it does declare (MAJOR-4).
* Five base behavioral pins were deleted without a census fixture replacement, and three
  mutants on live code survive because of it — including widening F-1's own destruction rule
  from `count >= 3` to `count >= 2` (MAJOR-5).

---

## 1. Claim-by-claim: claimed vs. measured

| # | claim (W3 §P20POSTPROC / census doc / card) | measured at `daa5988` | verdict |
|---|---|---|---|
| 1 | chain quarantined on the analysis path; `ocr_page` returns raw through `apply_admitted` | `ocr/ocr_client.py:595` single return site, both branches; `apply_admitted` identity on the empty tuple (probe) | **CONFIRMED** |
| 2 | `postprocess` called by nothing | `git grep postprocess -- '*.py'`: def at `:514`; the only other code reference is inside `postprocess` itself. `ocr/render.py:179,194` are comments. Remaining hits: census tool/tests, `ocr/truncation.py:28` docstring, `triage_scan.py:2` prose | **CONFIRMED** |
| 3 | `embed_image_regions` not on the analysis path; F-2 closed | `git grep embed_image_regions`: def at `:344`, docstring at `:533`, `local_ocr_server.py:110` comment. **Zero callers.** Mutant E killed | **CONFIRMED** |
| 4 | display path renders raw; `render_boxed` never re-enters the chain | `ocr/render.py:186-187,203` render `content`/`raw`; mutant B killed by `test_render_boxed_never_calls_the_quarantined_postprocess_chain` | **CONFIRMED** |
| 5 | `ADMITTED_POSTPROCESS = ()`, `POSTPROCESS_STATE = "quarantined"`, both exported under those names | verified by import; mutants C and D killed | **CONFIRMED** |
| 6 | `apply_admitted` applies members "in the order they appear" in the tuple | order is **not** pinned — mutant P (iterate `_POSTPROCESS_MEMBERS`, filter by membership) SURVIVED, exit 0 | **MINOR-1** |
| 7 | F-1 `[a,a,a,b,c] → [a]` reproduced | reproduced from the fixture and from my own input; money `['$50.00'×3,'$75.00','$60.00'] → ['$50.00']` | **CONFIRMED** |
| 8 | F-11 reproduced | reproduced on my own `1,000.00 234.56` fused Amount cell | **CONFIRMED** |
| 9 | the debit/credit/balance fold is settled by construction | reproduced independently; the gate reads only `fc[0]`/`fc[-1]` (`ocr/ocr_client.py:291-294`), middle cells never inspected; a 5-cell row folds to 3 with debit+credit in free text and the balance in the amount column | **CONFIRMED — and it is the cell's own new evidence, correctly reasoned** |
| 10 | census recomputes deltas mechanically, never trusts `case.json` | `_mechanical_delta` (`tests/test_ocr_postprocess_census.py:37-46`) Counter-diffs tokens re-extracted from the fixture files; `test_recorded_numeric_tokens_match_measured_tokens` re-measures both multisets; mutant H killed by 2 tests | **CONFIRMED** |
| 11 | classifications "never forced into a label the evidence contradicts" | four rows carry absolute claims I falsified by construction (see MAJOR-1); the labels are *directionally* right but the supporting sentences are not true as written | **PARTLY FALSE — MAJOR-1** |
| 12 | each function has a worst input and a harmless input | `strip_det_tags`, `strip_refusal_commentary`, `strip_placeholder_markers`, `strip_oversized_embedded_images` have **one fixture each** (worst only); `collapse_repeated_amounts`' declared harmless input ("a run with no value repeating 3+ times") has **no fixture** | **PARTLY FALSE — MAJOR-5** |
| 13 | OQ2 blast radius: 5 classes 0 hits, `AMOUNT_RE` 6 hits / 2 files | re-measured layer-wide over all 13 `ocr/*.py`: REMOVED_LITERALS 0, YEAR_RE 0, ACCOUNT_RE 0, MOJIBAKE_RE 0, CALENDAR_RE 0; AMOUNT_RE **6** hits in **2** files (`column_grid.py:207`; `render.py:83,85,87,89,114`) | **CONFIRMED, exactly** |
| 14 | `OCR_AMOUNT_BASELINE` entries are furniture | verified by reading each of the 6 sites: one geometry ratio (`reach = pitch * 1.25`) and five CSS `line-height`/`font-size` values in a stylesheet constant. **Genuine furniture, not a statement value.** Ratchet is shrink-only and pinned | **CONFIRMED** |
| 15 | the five/six pattern-class scans are layer-wide over `ocr/*.py` | `_ocr_modules()` = `OCR_DIR.glob("*.py")` → all 13 files (`ocr/` is flat). **Yes, layer-wide** | **CONFIRMED** |
| 16 | the issuer-marker register guard covers only the 3 files the card owns | true, and it is declared — but a layer-wide scan yields **0 offenders at this tree**, so the narrowing buys nothing and leaves 10 files unguarded. Mutants I and J SURVIVED | **MAJOR-2** |
| 17 | "`INTAKE_FURNITURE` is the ONLY sanctioned home for issuer-named intake behavior" | enforced for the *name*, not the *content*: mutant K (`_TD_MARKERS_RE` widened with a second issuer) SURVIVED, exit 0 | **MAJOR-3** |
| 18 | every register entry is page-selection only, no read/write of a value | true for `_mask_qr` (pixels only, signature-pinned) and `_TD_MARKERS_RE`/`_TD_RECOVERY_VARIANTS`. But `is_td_statement`, `looks_truncated_td` and `recover_truncated_td_page` — all three named by the card — are **absent from the register**, and they are exactly the pair that selects among five candidate reads on a printed section caption | **MAJOR-4** |
| 19 | truncation stays flag-only; `tests/test_truncation.py:194-207` green | green (verified), `ocr/truncation.py` byte-unchanged, `assess_pages` unchanged, nothing re-OCRs on a flag. But the test still calls `postprocess` directly — a path nothing reaches now | **CONFIRMED with MINOR-5** |
| 20 | cohort replay 179/179, 36/36 preserved identical, exit 0 | reproduced exactly: 36 preserved payload-identical, 143 unchanged non-validated, 0 newly validated, 0 up, 0 down, exit 0, 49s | **CONFIRMED** |
| 21 | the 179 Tesseract shas contain all 6 committed corpus-artifact shas (union 179) | verified case-insensitively: subset True, union 179; all 6 have `source_path = local_tesseract` | **CONFIRMED** |
| 22 | `tests/corpus_cache` byte-identical | `git diff --stat bea06bc..daa5988 -- tests/corpus_cache` → empty | **CONFIRMED** |
| 23 | suite 7,892/45/35 = 7,815/44/35 + 77 passed + 1 skipped | reconciled without running the full suite: +72 census (1 skipped) +8 furniture +9 guard −12 (`test_ocr_client` 38→26) +1 (`test_render` 14→15) = **+78 collected, +77 passed, +1 skipped** | **CONFIRMED arithmetically** |
| 24 | corpus-marked slice 30→31 is NOT attributable to this cell | the `@pytest.mark.corpus` source is byte-identical at `7b25d70`, `bea06bc` and `daa5988` (20 occurrences, same 9 files); `pytest.ini`/`conftest.py` unchanged `7b25d70..daa5988`. So the slice is 31 at **all three** trees and the recorded 30 is a stale baseline record, not a movement | **CONFIRMED — and now mechanically explained** |
| 25 | 5 canonical guards = 264 | measured **264 passed**, exit 0; `test_no_statement_hardcodes.py` collects **60** | **CONFIRMED** |
| 26 | tests moved from `test_ocr_client.py` (38→26), none deleted | 5 base pins have **no census-fixture equivalent anywhere in the tree**, and three mutants survive because of it | **FALSE — MAJOR-5** |
| 27 | `_build_client` byte-identical (B2 owns it) | sha256 of the function body identical base vs tip (`a6d85cb82c933364…`) | **CONFIRMED** |
| 28 | `ocr/config.py`, `ocr/document.py`, `ocr/availability.py`, `analysis/*` untouched | not in `git diff --name-only`; `ocr/pipeline.py` and `ocr/truncation.py` also untouched | **CONFIRMED** |
| 29 | ownership: only card-owned files edited | 10 files; **`tests/test_render.py` is not in the card's Ownership list** although the W3 lists it as owned. `tests/test_pipeline.py` IS in the list and was not edited (explained) | **MINOR-6** |
| 30 | privacy 0 / message 0 | re-run at the tip: privacy `hit_count 0` (added_lines 1,721; raw 3, all `words_class`); message `hit_count 0`, 5 commits. Cell's 1,552/2/4 were measured at `a68e4be`, before the docs commit | **CONFIRMED (restate at tip)** |
| 31 | the long-path fixture rename is content-identical | the rename predates every commit, so git holds no evidence either way; internal consistency verified (`case.json`'s `case` field, the census doc and the fixture dir all read `oversized_dropped`; the only surviving reference to the long name is the W3 host note) | **UNVERIFIABLE, consistent** |
| 32 | nothing makes a network call; nothing PaddleOCR; no re-admission | verified by reading the diff and by import | **CONFIRMED** |

---

## 2. Findings

### MAJOR-1 — four of the nine census rows carry an ABSOLUTE "cannot touch a financial value" claim that is false by construction; three of the four are the members earmarked for first re-admission

This is the most important finding, because OQ1 = C makes this census the gate: *"re-admit functions
individually only after their own census + synthetic fixtures establish exactly what they change."*
The census's own "Quarantine mechanics" says a later phase re-admits **rows 1–4** on this census's
evidence. Rows 1, 3 and 4 are three of the four counterexamples below.

**(a) `strip_det_tags` deletes a money token — two independent shapes.**
`ocr/ocr_client.py:13` `_DET_PAIR_RE = <\|det\|>.*?<\|/det\|>` and `:15`
`_DET_ORPHAN_RE = <\|det\|>\s*\w+\s*\[[^\]\n]*\]+`.
Census row 1 and `tools/ocr_postprocess_census.py:CLASSIFICATION["strip_det_tags"]`:
*"the tag grammar only holds a label word and four bare integers"*, `semantics_can_change: no`.
Neither regex enforces that grammar.

```
# orphan form: the bracket content is [^\]\n]* — anything at all
in : 'Beginning balance\n<|det|>total [$5,000.00]\nEnding balance $10.00'
out: 'Beginning balance\n\nEnding balance $10.00'          # $5,000.00 deleted

# pair form: .*? spans from an ORPHAN opening tag to the NEXT region's closing tag
in : '<|det|>footer [1, 2, 3, 4] Balance $5,000.00 <|det|>text [5,6,7,8]<|/det|>More'
out: 'More'                                                # $5,000.00 deleted
     # identical through the full postprocess() chain
```

The orphan-plus-later-close shape is not exotic: the function's own docstring (`:32-33`) says the
model emits unclosed tags around footers, and two regions on one line is exactly what an
un-newlined completion looks like.

**(b) `strip_oversized_embedded_images` deletes an `alt` attribute's tokens, at the PRODUCTION
threshold.** `_DATA_IMG_RE` (`:342`) is `<img\b[^>]*src="data:image/[^"]+"[^>]*>` — the trailing
`[^>]*` covers `alt=`. Census row 4: *"the regex only ever matches `<img src="data:image/…">`
markup"*, *"which never overlaps a money- or date-shaped printed token"*.

```
in : 'x <img src="data:image/png;base64,<26,000 chars>" alt="check total $5,000.00" /> y'
out: 'x  y'   # at the default max_len=25_000 — the alt text and its money token go with it
```

**(c) `split_fused_header_row` deletes text between cells in the row it rebuilds.** `:189-192`
rebuilds row 0 from `_CELL_RE.findall` only; anything in that `<tr>` outside a `<td>` is discarded.
Census row 7: *"no digit is invented, deleted, or moved to a different column"*,
`semantics_can_change: no`.

```
in : '<table><tr><td>DATE01/05</td>STRAY Total $9,999.00<td>AMOUNT$1,200.00</td></tr>…'
out: '<table><tr><td>DATE</td><td>AMOUNT</td></tr><tr><td>01/05</td><td>$1,200.00</td></tr>…'
     # money $9,999.00 deleted; identical through the full chain
```

**(d) `fix_amount_column_bleed` and `repair_fused_amount_table` delete any non-`<tr>` table
content whenever they fire.** `:167` and `:315` both re-emit `"<table>" + rows + "</table>"` from
`re.findall(r"<tr>.*?</tr>")`. Census row 9: *"no digit deleted — both values survive, one
relocated"*; row 8: *"no digit is deleted or invented — token-preserving in the strict digit
sense"*.

```
fix_amount_column_bleed:   '<table><caption>Total fees $4,321.00</caption>…'   → $4,321.00 deleted
repair_fused_amount_table: '<table><caption>Carried forward $7,777.00</caption>…' → $7,777.00 deleted
     # both identical through the full chain
```

**Why this is MAJOR and not BLOCK.** Nothing on the analysis or display path can reach any of
these functions at this tree, and coverage is provably +0. But the census is the artifact a
future reviewer will read to re-admit rows 1–4, and on three of those four rows it currently
says, categorically, that the member cannot touch a financial value. It can.

**Fix I would accept.**
1. Correct the four rows in `OCR_POSTPROCESS_CENSUS.md` and the matching
   `CLASSIFICATION` strings in `tools/ocr_postprocess_census.py`: the honest statement is
   *"removes a markup span whose content is unconstrained by the pattern — a money-shaped token
   inside a det-tag bracket, inside an `alt` attribute, or between `<td>`/`<tr>` elements is
   removed with it"*. Keep the labels (they are still the right coarse labels); fix the reasons.
2. Add one fixture per counterexample (four fixtures).
3. Add the invariant that makes the label enforceable rather than prose: for every function whose
   `CLASSIFICATION` starts `reads/removes metadata-only content`, assert
   `money.disappeared is False and date.disappeared is False` across **all** its fixtures. Without
   it, a member can be relabelled or mutated into a value-deleter and the census suite stays green
   (I confirmed there is no such cross-check: `test_classification_never_uses_a_bare_misleading_label`
   only substring-matches the label strings).

---

### MAJOR-2 — the OQ2 issuer-marker guard is scoped to 3 files where the card says layer-wide, the stated reason does not hold, and two mutants survive

Card item 5: *"the guard asserts every issuer-named regex in `ocr/` is registered there."*
Implemented scope: `ISSUER_MARKER_SCAN_FILES = ("ocr_client.py", "pipeline.py", "render.py")`
(`tests/test_no_statement_hardcodes.py:900`). The declared reason (comment at `:872-882`,
census doc, W3) is that `ocr/native_text.py` carries pre-existing per-issuer constants.

**Measured: extending the same scan layer-wide over all 13 `ocr/*.py` yields 0 offenders at this
tree.** `_compiled_regex_assignments` only matches module-level `NAME = re.compile(<str literal>)`;
`native_text.py` has 9 such assignments and **none** contains an issuer-lexicon hit. Its issuer
names (measured: `woodforest` ×17, `desjardins` ×7, `navy federal` ×4, `first citizens` ×3,
`wells fargo` ×1; plus `woodforest` ×3 in `column_grid.py`) live in other syntactic forms the
scanner cannot see. So the narrowing costs nothing today and buys nothing — while leaving 10 of
13 files permanently unguarded.

Two mutants applied to the real files, both **SURVIVED** (262 passed, exit 0):

| mutant | file | result |
|---|---|---|
| **J** — `_NEW_ISSUER_RE = re.compile(r"wells fargo", re.IGNORECASE)` appended | `ocr/native_text.py` | **SURVIVED** (outside the 3-file scope) |
| **I** — `def _is_wf_statement(text): return bool(re.search(r"wells fargo", text, re.I))` appended | `ocr/pipeline.py` (**a scanned file**) | **SURVIVED** (not a module-level `re.compile` assignment) |

Mutant I is the more serious of the two: the guard is blind to the same hardcode written as an
inline `re.search`, a bare string constant, or a tuple of markers — inside a file it *does* scan.
The card's own mutant (F, the `re.compile` form in `pipeline.py`) is killed, so the guard is not
vacuous; it is just narrow in a way the card's wording does not license.

**Fix I would accept.**
1. Iterate `_ocr_modules()` instead of `ISSUER_MARKER_SCAN_FILES` — measured to add **0**
   offenders now, so it is free, and it makes mutant J die.
2. Widen the detector from `re.compile` assignments to every `ast.Constant` of type `str` in the
   module (which is what actually catches mutant I), **measure that blast radius, and ratchet it**
   exactly as the card instructs for pre-existing furniture: `native_text.py` (5 issuers, 32
   occurrences) and `column_grid.py` (1 issuer, 3 occurrences) become a named, shrink-only
   `OCR_ISSUER_STRING_BASELINE` with the reason recorded. That is an honest ratchet; declaring the
   module "out of scope" is not, because it leaves the next cell to rediscover the same facts.
3. Keep the honest measurement the cell already published — it is good, and it is what let me
   check this in one command.

---

### MAJOR-3 — a registered regex NAME is a blanket licence for every other issuer

`ocr/ocr_client.py:222` `_TD_MARKERS_RE` is registered in `INTAKE_FURNITURE` with
`"issuer": "TD"`. The guard (`test_every_issuer_named_regex_in_ocr_is_registered`) checks only
that the assignment's **name** is a key of the register; nothing ties the registered entry's
declared issuer to the pattern's content.

**Mutant K** — `_TD_MARKERS_RE` widened from
`most convenient bank|td business|\btd bank\b` to
`most convenient bank|td business|\btd bank\b|wells fargo`, applied to the real file:
**SURVIVED, 262 passed, exit 0.** `test_td_markers_detect_only_named_printed_furniture` only
asserts that a Chase string does not match, so a second issuer smuggled into an already-registered
pattern passes every test in the tree. The card's *"the register is the ONLY sanctioned home for
issuer-named intake behavior"* is therefore enforced for the door, not for what walks through it.

**Fix I would accept** (one assertion, in `tests/test_ocr_intake_furniture.py`): for every
register entry whose subject is a compiled regex with a non-`None` `issuer`, assert the pattern
text contains the declared issuer's marker **and** contains no marker from `ISSUER_NAME_LEXICON`
belonging to a different institution. That kills mutant K and costs nothing today.

---

### MAJOR-4 — the register omits the two behaviors that select between candidate reads by content, and understates the scope of the two it declares

The card names seven behaviors: `_TD_MARKERS_RE`, `is_td_statement`, `looks_truncated_td`,
`_mask_qr`, `_TD_RECOVERY_VARIANTS`, `recover_truncated_td_page`, and `looks_missegmented`.
`INTAKE_FURNITURE` registers **four**; `is_td_statement` (`:225`), `looks_truncated_td`
(`:229-235`) and `recover_truncated_td_page` (`:255-264`) are absent — and
`test_intake_furniture_covers_every_declared_behavior` pins the register to exactly those four,
freezing the omission.

The three omitted are precisely the content-keyed half:

```
ocr/ocr_client.py:259-263   for dpi, mask in _TD_RECOVERY_VARIANTS: … out = ocr_page(img, …)
                            if not looks_truncated_td(out) and "account summary" in out.lower():
                                return out
ocr/pipeline.py:113-119     if fallback_dpi and looks_missegmented(out): … alt = ocr_page(alt_img,…)
                            if not looks_missegmented(alt): return use_alt(page_index, alt)
```

Both loops **choose which of two-to-five candidate OCR reads is kept, on what the document
prints**. I am *not* claiming a financial-value hazard: the discriminator is a structural section
caption and a table-shape signature, never a figure, and `_mask_qr`'s signature proof
(`test_mask_qr_cannot_depend_on_a_printed_figure_by_signature`) is a good, real structural
argument. But `"scope": "render variant (dpi, mask flag) selection only"` and
`"scope": "render DPI selection only"` are not accurate descriptions of "keep whichever read
contains the ACCOUNT SUMMARY caption", and PHASE2_RULINGS' *"no candidate auto-adoption in Phase
2.0"* makes accuracy here the whole point of a declared register.

**Fix I would accept.** Register `is_td_statement`, `looks_truncated_td` and
`recover_truncated_td_page` (update the exact-set test to seven), and amend the two `scope`
strings to say, in the register itself, *"…and selects which of N candidate reads is kept, keyed
on a printed structural section caption / a table-shape signature, never on a printed figure"*.
Nothing about the code needs to change; the declaration does.

---

### MAJOR-5 — five behavioral pins were deleted, not moved to the census; three mutants on live code survive as a result

W3: *"`tests/test_ocr_client.py` rewritten (38 → 26 tests: 22 per-function behavior tests moved to
the executable census)."* Measured: five base tests have **no census-fixture equivalent anywhere
in the tree**.

| deleted base test (`git show bea06bc:tests/test_ocr_client.py`) | what it pinned | replacement |
|---|---|---|
| `test_strip_det_tags_removes_orphan_footer_tags` (`:214`) | `_DET_ORPHAN_RE` **and** `_DET_BARE_RE` | **none** — the single `strip_det_tags` fixture is a well-formed pair, so 2 of the function's 3 branches are unpinned |
| `test_collapse_repeated_amounts_leaves_distinct_amounts` (`:142`) | the `count >= 3` threshold | **none** |
| `test_strip_placeholder_markers_preserves_bracketed_content` (`:96`) | `[Continued]` / `[image]` untouched | **none** (named in the census prose as the harmless input) |
| `test_strip_refusal_commentary_leaves_normal_text_alone` (`:242`) | the harmless input | **none** |
| `test_split_fused_header_row_leaves_label_value_summary_untouched` (`:279`) | a label/value summary row untouched | **none** |

Mutants applied to the real `ocr/ocr_client.py`, all **SURVIVED** (262 passed, exit 0):

| mutant | change | result |
|---|---|---|
| **L** | delete `text = _DET_ORPHAN_RE.sub("", text)` from `strip_det_tags` | **SURVIVED** |
| **M** | delete `text = _DET_BARE_RE.sub("", text)` from `strip_det_tags` | **SURVIVED** |
| **N** | `collapse_repeated_amounts`: `count >= 3` → `count >= 2` (widen F-1's destruction) | **SURVIVED** |

Mutant N is the one that should worry Ocean: the boundary of the single most destructive member in
the chain — the one the whole quarantine exists for — can be widened and the suite stays green,
because the fixture that constrained it was deleted and the three committed fixtures do not
discriminate `>= 3` from `>= 2`.

This also means the card's per-function requirement is not met: `strip_det_tags`,
`strip_refusal_commentary`, `strip_placeholder_markers` and `strip_oversized_embedded_images` have
**one fixture each** (the worst input), with the harmless input asserted only in prose — and those
four are exactly the members the census nominates for first re-admission.

**Fix I would accept.** Add the five missing cases as fixtures (one each): an orphan-tag case and a
bare-`<|/det|>` case for `strip_det_tags`, `$100.00 $200.00 $300.00` for `collapse_repeated_amounts`,
`[Continued] see page 2` for `strip_placeholder_markers`, ordinary text for
`strip_refusal_commentary`, and the label/value summary row for `split_fused_header_row`. Then
re-run mutants L, M and N — all three must die.

---

## 3. Minor findings

### MINOR-1 — `apply_admitted` does not actually pin ORDER
`tests/test_ocr_client.py:141-151` uses `("strip_det_tags", "collapse_repeated_amounts")`, which is
also their relative order in `_POSTPROCESS_MEMBERS` (`ocr/ocr_client.py:401-411`), so the test
cannot tell "tuple order" from "declaration order". **Mutant P** (iterate `_POSTPROCESS_MEMBERS`,
filter by membership) **SURVIVED**, exit 0. This matters because cell C keys the cache on the tuple
*and* its order and the docstring promises "in the order they appear there".
**Fix (verified at this tree):** assert the reverse order too, on an order-sensitive input —
with `raw = '$50.00 <|det|>x [1,2,3,4]<|/det|> $50.00 $50.00'`,
`("strip_det_tags","collapse_repeated_amounts")` → `'$50.00'` while
`("collapse_repeated_amounts","strip_det_tags")` → `'$50.00  $50.00 $50.00'`. Adding that
assertion kills mutant P.

### MINOR-2 — `collapse_repeated_page_numbers`: "always an exact copy of a surviving token" is false
Census row 6 and the `CLASSIFICATION` string claim the disappearing digit runs are *always* exact
copies of a survivor, so *"no distinct information is lost"*.
```
in : 'Page 12 of 34 Page 12 of 345'   out: 'Page 12 of 345'
digit_run ['12','34','12','345'] -> ['12','345']        # the footer 'Page 12 of 34' is deleted
```
Page furniture only, never a financial value — but the claim is absolute and measurably wrong.
**Fix:** replace *"always"* with *"in the exact-repeat case"*, and add this as a third fixture.

### MINOR-3 — `strip_placeholder_markers` rewrites whitespace unconditionally
`ocr/ocr_client.py:55-60` does `text.splitlines()` + `"\n".join(...)`. On input containing **no
placeholder at all**: CRLF → LF, form feed → LF, and a **trailing newline is dropped** (measured).
Not a financial change, but the row describes the function as dropping placeholder lines/spans, and
if it is re-admitted first (rows 1–4 are the stated candidates) it silently changes the bytes of
every page — and therefore any hash taken over them.
**Fix:** state it in the row; add a placeholder-free fixture showing the normalization.

### MINOR-4 — the quarantine changes when the DPI fallback fires, undeclared
`ocr/pipeline.py:113-119` now calls `looks_missegmented` / `looks_truncated_td` on the **raw**
completion instead of the postprocessed text. `_ORPHAN_AMOUNT_TABLE_RE` (`:196-200`) tolerates only
`\s*` between `<table>` and `<tr>`, so:
```
raw   = '<table>\n[Non-Text]\n<tr><td>AMOUNT($)</td></tr><tr><td>1.00</td></tr><tr><td>2.00</td></tr></table>'
looks_missegmented(raw)              -> False
looks_missegmented(postprocess(raw)) -> True      # same with a <|det|> tag in place of [Non-Text]
```
So the fallback re-OCR fires **strictly less often** under the quarantine on constructible shapes.
Zero production impact (`visual_rung = not_attempted` 3,506/3,506), but it is a real intake-behavior
delta and the card's "state each change" contract asks for it. `looks_truncated_td` is unaffected
(its two substrings are never removed by the chain). **Fix:** one paragraph under "Quarantine
mechanics" plus a fixture pinning `looks_missegmented` on the raw shape.

### MINOR-5 — `tests/test_truncation.py:194-207` now pins a dead path
`test_postprocess_of_a_full_read_never_manufactures_a_signal` calls `postprocess(raw)` directly.
Green (verified), `ocr/truncation.py` byte-unchanged, `assess_pages` unchanged, nothing re-OCRs on
a flag — but the flag-only property is no longer proven on the text `assess_pages` actually sees.
The card said *"keep it green on raw text"*. I could not construct a shape where
`structural_tail_signals` differs between raw and cleaned (tried the test's own fixture and an
unbalanced-tail table; identical both ways), so this is a coverage gap, not a hazard.
**Fix (one line, verified to pass):** add `assert structural_tail_signals(raw) == []` beside the
existing assertion.

### MINOR-6 — ownership and counting nits
* `tests/test_render.py` is edited but is **not** in the card's Ownership list; the W3's *"Only
  files this card owns were edited"* lists it as owned. It is the natural home of the card's own
  display-path mutant killer, so I would accept the edit — but Ocean should record the one-file
  extension rather than let the W3 assert it was already granted. (`tests/test_pipeline.py` IS in
  the list and was correctly left unedited, with the reason stated.)
* W3 says the OCR_DIR scan reuses *"the same five pattern classes"*; **six** are implemented
  (`REMOVED_LITERALS`, `YEAR_RE`, `ACCOUNT_RE`, `AMOUNT_RE`, `CALENDAR_RE`, `MOJIBAKE_RE`). The
  census doc lists six correctly. One-word correction.
* The privacy/message scan figures in the W3 (`added_lines 1,552`, 2 `words_class` exclusions, 4
  commits) were measured at `a68e4be`, before the docs commit. At the tip: 1,721 added lines, 3
  `words_class` exclusions, 5 commits — **`hit_count 0` in both scans either way**. Restate at the
  tip so the numbers match the composed commit.

---

## 4. What I did NOT find

* **No path from any of the nine functions, or from `embed_image_regions`, to admissible
  evidence.** `git grep` over the whole tree (including `tools/`, `webapp/`, `tests/`,
  `build_corpus_cache.py`, `local_ocr_server.py`): `postprocess` has one definition and zero
  callers; `embed_image_regions` has zero callers; `apply_admitted` is called from exactly one site.
  `webapp/` contains no reference to any of them. `local_ocr_server.py:110` and
  `ocr/truncation.py:28` are comments; `triage_scan.py:2` is the English word.
* **`apply_admitted` is a verified no-op** on the empty tuple, on both the streamed and the
  non-streamed branch (single return site, `ocr/ocr_client.py:595`) — and nothing else transforms
  the raw completion between `ocr_page` and `StatementMarkdown.pages` (`ocr/pipeline.py:150-152`
  does `str(r)`; `ocr/document.py` is untouched and still carries its "must not add a byte" pin).
* **The display path for picture regions:** unchanged where it matters. With `page_images` (the
  final render) `_region_html` still shows the **actual cropped page pixels** via
  `_image_region_html` → `_crop_data_uri` (`ocr/render.py:167-174`); without them (the live stream)
  it now shows the model's **raw** region text instead of the postprocessed text. That crop never
  reaches `StatementMarkdown` — `render_boxed` is consumed only by `webapp/app.py:2000`'s JSON
  fragment. F-2 is genuinely closed on the analysis path.
* **The streaming `on_page_delta` live buffer** was already raw chunks and is unchanged
  (`ocr/pipeline.py:107-111`, `ocr/ocr_client.py:588-591`).
* **No regression.** Cohort replay at the tip: 179/179, 36/36 preserved payload-identical, 0 newly
  validated, 0 up, 0 down, exit 0. `tests/corpus_cache` byte-identical. `newly validated = 0`.
* **The census tool is not a rubber stamp.** `_mechanical_delta` Counter-diffs tokens re-extracted
  from the fixture files and compares against `case.json`; a wrong record fails (mutant H, killed by
  2 tests). Every `expected.md` **is** the function's own output — test 1 enforces it, so all 17 are
  snapshots — but the annotations layered on top are independently recomputed, which is the correct
  shape for a *census* (a descriptive instrument), not a specification. I do not count that as a
  defect.
* **The debit/credit/balance fold is honestly reported.** I constructed it independently and reached
  the same conclusion by the same route (the gate at `:291-294` reads `fc[0]` and `fc[-1]` only).
  The cell's "narrower than it first appears, but real" framing is accurate, and its date/digit-run
  reclassification note is a genuine measurement artifact of the census's own extractor, correctly
  explained rather than glossed.
* **The `OCR_AMOUNT_BASELINE` entries are furniture, not statement values** — I read all six sites.
  The ratchet is shrink-only and pinned by `test_ocr_amount_baseline_still_describes_real_offenders`.
* **`_mask_qr` cannot be reached by a printed figure.** Mutant G (adding a text parameter) is killed
  by the signature test, and the masked rectangle is content-independent (two differently coloured
  images of the same size mask identically). This is a real structural proof, not a promise.
* **No register entry naming a behavior that does not exist survives** — mutant O (a bogus
  `_BOFA_MARKERS_RE` entry) is killed by the exact-set test.
* **No 3.13+-only API** in any added or modified file; no network call; no PaddleOCR; no
  re-admission; `ADMITTED_POSTPROCESS == ()`; `POSTPROCESS_STATE == "quarantined"`.
* **Privacy 0 / message 0** at the tip over the 179 Tesseract shas.
* `git status --porcelain` empty before, between every mutant, and after the campaign. Nothing was
  committed or pushed. The cold caches were opened read-only by the replay tool only.

---

## 5. Mutation table (all applied to the REAL committed files, then `git checkout --`)

Baseline for the campaign: `tests/test_ocr_client.py tests/test_render.py
tests/test_ocr_postprocess_census.py tests/test_ocr_intake_furniture.py
tests/test_no_statement_hardcodes.py tests/test_pipeline.py tests/test_truncation.py
tests/test_visual_rung.py` → **262 passed, 1 skipped, 1 deselected, exit 0**.

| # | mutant | expected killer | result |
|---|---|---|---|
| A | `ocr_page` calls `postprocess` again | raw-return tests | **KILLED** (5 failed: `test_ocr_page_returns_raw_det_tags_unremoved`, `…does_not_collapse_repeated_amounts`, `…does_not_fix_amount_column_bleed`, `…does_not_strip_refusal_placeholder_or_oversized_image`, `…does_not_embed_image_regions`) |
| B | `_region_html` re-enters `postprocess` | display-path test | **KILLED** (`test_render_boxed_never_calls_the_quarantined_postprocess_chain`) |
| C | `ADMITTED_POSTPROCESS = ("strip_det_tags",)` | empty-admission pin | **KILLED** (4 failed, incl. `test_admitted_postprocess_is_empty_in_phase_2_0`) |
| D | `apply_admitted` applies a non-admitted member | chain-order tests | **KILLED** (3 failed, incl. `test_apply_admitted_never_applies_an_unlisted_member`) |
| E | `embed_image_regions` wired back onto the analysis path | no-base64 test | **KILLED** (`test_ocr_page_does_not_embed_image_regions`) |
| F | unregistered issuer `re.compile` in `ocr/pipeline.py` | OQ2 register guard | **KILLED** (`test_every_issuer_named_regex_in_ocr_is_registered`) |
| G | `_mask_qr` gains a text parameter | furniture signature test | **KILLED** (`test_mask_qr_cannot_depend_on_a_printed_figure_by_signature`) |
| H | F-1 fixture records `money.disappeared = false` | census test | **KILLED** (2 failed: `test_f1_distinct_adjacent_amounts_are_recorded_as_disappeared`, `test_recorded_token_delta_matches_mechanical_diff[…]`) |
| **I** | issuer marker in `ocr/pipeline.py` as an **inline `re.search`** | — | **SURVIVED → MAJOR-2** |
| **J** | issuer `re.compile` in `ocr/native_text.py` | — | **SURVIVED → MAJOR-2** |
| **K** | `_TD_MARKERS_RE` widened to a **second issuer** | — | **SURVIVED → MAJOR-3** |
| **L** | `strip_det_tags` drops the `_DET_ORPHAN_RE` branch | — | **SURVIVED → MAJOR-5** |
| **M** | `strip_det_tags` drops the `_DET_BARE_RE` branch | — | **SURVIVED → MAJOR-5** |
| **N** | `collapse_repeated_amounts` `count >= 3` → `count >= 2` | — | **SURVIVED → MAJOR-5** |
| O | `INTAKE_FURNITURE` gains an entry for a behavior not in the file | register exact-set test | **KILLED** (`test_intake_furniture_covers_every_declared_behavior`) |
| **P** | `apply_admitted` ignores the tuple's order (fixed chain order) | — | **SURVIVED → MINOR-1** |
| Q | `strip_placeholder_markers` drops any line *containing* the placeholder | census fixture pin | **KILLED** (2 failed on `strip_placeholder_markers/line_and_inline_with_money`) |

**8/8 of the card's mutants killed by the named killers. 6 of my 9 additional mutants survived.**
`git status --porcelain` empty after every restore and after the campaign.

---

## 6. Reproduction

```bash
cd ".claude/worktrees/rev20-postprocess"          # detached at daa5988

# --- ownership / integrity ---
git diff --stat bea06bc..daa5988 -- tests/corpus_cache          # empty = byte-identical
git diff --name-only bea06bc..daa5988 | grep -v '^tests/fixtures/ocr_postprocess/'
git show bea06bc:ocr/ocr_client.py | sed -n '/^def _build_client/,/^$/p' | sha256sum
sed -n '/^def _build_client/,/^$/p' ocr/ocr_client.py | sha256sum   # a6d85cb82c933364…

# --- reachability (item 1) ---
for f in strip_det_tags strip_refusal_commentary strip_placeholder_markers \
         strip_oversized_embedded_images collapse_repeated_amounts \
         collapse_repeated_page_numbers split_fused_header_row \
         repair_fused_amount_table fix_amount_column_bleed \
         postprocess embed_image_regions apply_admitted; do
  echo "== $f"; git grep -n "$f" -- '*.py'; done

# --- proof floor (item 9) ---
python -m pytest tests/test_ocr_postprocess_census.py tests/test_ocr_intake_furniture.py \
  tests/test_ocr_client.py tests/test_pipeline.py tests/test_render.py \
  tests/test_truncation.py tests/test_visual_rung.py -q      # 202 passed, 1 skipped, 1 deselected
python -m pytest tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py \
  tests/test_r1_hardcodes.py tests/test_experiments_are_not_wired.py \
  tests/test_filename_boundary.py -q                          # 264 passed, exit 0
python -m tools.ocr_postprocess_census                        # 9 rows, all pass, exit 0

# --- census counterexamples (MAJOR-1, MINOR-2/3) ---
PYTHONPATH="$PWD" python <scratch>/probe1.py

# --- OQ2 blast radius + layer-wide issuer scan (MAJOR-2) ---
PYTHONPATH="$PWD" python <scratch>/probe2.py
#   AMOUNT_RE 6 hits / 2 files; other five classes 0; layer-wide issuer scan 0 offenders

# --- mutation campaign (17 mutants, real files, restored in finally) ---
PYTHONPATH="$PWD" python <scratch>/mutants.py

# --- cohort replay (item 6) ---
#   cohort derived from the run of record: distinct content_sha256 where
#   source_path == 'local_tesseract'  -> 179 shas (sha16 of the sorted list: 5f05781ff8294b86)
python -m tools.cohort_replay \
  --run   "<repo>/discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a" \
  --data-dir "<repo>/.claude/recovery/webapp_data_train9_cold" \
  --shas  "<scratch>/tess179.shas" --expect-identical
#   179 replayed · 36 preserved payload-identical · 0 newly validated · 0 up · 0 down · EXIT=0

# --- scans at the tip ---
python -m tools.privacy_scan_branch --base bea06bc --ref HEAD --shas <scratch>/tess179.shas \
  --data-dir "<repo>/.claude/recovery/webapp_data_train9_cold"     # hit_count 0
python -m tools.huntington_msg_privacy_scan --base bea06bc --ref HEAD \
  --shas <scratch>/tess179.shas \
  --data-dir "<repo>/.claude/recovery/webapp_data_train9_cold"     # hit_count 0, 5 commits

# --- corpus-marked slice reconciliation (item 7) ---
git grep -h "pytest.mark.corpus" 7b25d70 -- tests/ | wc -l   # 20
git grep -h "pytest.mark.corpus" bea06bc -- tests/ | wc -l   # 20
git grep -h "pytest.mark.corpus" daa5988 -- tests/ | wc -l   # 20
git diff --name-only 7b25d70..daa5988 -- pytest.ini conftest.py tests/conftest.py  # empty
python -m pytest -m corpus -q --collect-only | grep -c '::'  # 31
```

The full suite and `corpus_gate.py` were **not** run (host shared; `tasklist | findstr python`
checked first — one unrelated ~136 MB `python.exe` resident, no concurrent proof launched). The
suite delta was reconciled arithmetically instead (claim 23) and the guards/targeted slices were
run directly.

---

## 7. Verdict

**APPROVE WITH FINDINGS.**

The quarantine itself is sound and structurally proven: nine functions, zero callers on either
path, an empty admission gate that a mutant cannot open silently, `embed_image_regions` unwired,
`newly validated = 0`, 36/36 preserved payload-identical, corpus artifacts byte-identical, all
eight of the card's mutants killed by their named killers. The debit/credit/balance fold is a
genuine new result, correctly derived, and it strengthens rather than reopens Gustavo's OQ1 = C
ruling. The blast-radius measurement is exact. The cell's honesty about what it did not own
(`native_text.py`), about the corpus-slice discrepancy, and about the census's own token-extractor
artifact is the kind of reporting that made this review possible in a day.

What must close before compose is the gap between the **wiring** (which is right) and the
**gate** (which is not yet trustworthy enough to re-admit anything on):

* **MAJOR-1** — four rows claim categorically that a member cannot touch a financial value; all
  four are falsified by construction, three of them on the members the census nominates for first
  re-admission. Correct the reasons, add the four fixtures, and add the label-to-delta invariant
  that makes the classification enforceable.
* **MAJOR-2** — extend the issuer scan to `ocr/*.py` (free: 0 offenders today) and widen the
  detector past `re.compile` assignments, ratcheting `native_text.py`/`column_grid.py` by name.
* **MAJOR-3** — pin a registered regex's declared issuer against its own pattern.
* **MAJOR-4** — register the three omitted TD behaviors and say plainly, in the register, that two
  of them select among candidate reads on a printed structural caption.
* **MAJOR-5** — restore the five deleted pins as fixtures; mutants L, M and N must die.

None of these is a BLOCK: nothing on the analysis or display path can reach the chain at this tree,
coverage movement is provably +0, and every finding is closed by an additive edit to the census,
the register, or the fixtures — no change to the quarantine wiring, and no re-decision of anything
Gustavo ruled. The six MINOR items are corrections of record.

Re-review should re-run the mutation campaign (I, J, K, L, M, N, P must all become KILLED) and
re-check the four corrected census rows against the same constructed inputs.
