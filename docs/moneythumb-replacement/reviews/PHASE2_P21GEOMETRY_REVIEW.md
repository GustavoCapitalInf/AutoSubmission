# PHASE 2.1 P21-GEOMETRY — independent adversarial review

```
BRANCH        wave21-geometry @ dbad83f   (reviewed detached in .claude/worktrees/rev21-geometry)
BASE          888fb1c
DIFF          git diff 888fb1c..dbad83f   (3 files, +1199 / -55)
              analysis/structurer/geometry.py · tests/test_geometry_frames.py · W3 §P21GEOMETRY
REVIEWER      independent agent; did not write this code
HOST          Python 3.14.5, PyMuPDF 1.27.2.3, pytest 9.1.1 (CI pins 3.12); `tasklist | findstr
              python` clean before every heavy proof; one harness at a time
VERDICT       BLOCK
```

Every number below is one this reviewer measured in this worktree. The tree was clean
(`git status --porcelain` empty) before and after every mutant and at the end of the run;
the mutation harness refuses to start on a dirty tree, restores in a `finally`, and
re-verifies. Nothing was merged, rebased, pushed or committed. The corpus and the cold
caches were opened read-only. No file name, no printed value and no archive token from any
customer document appears in this review.

**The shipped production code is correct as far as I could measure it.** The block is not a
defect in `geometry.py`; it is that two of the card's own nine mutants SURVIVE when applied
as the card words them, while the W3 records "M1–M9 · 9/9 KILLED", and the surviving pair
covers the single property this cell exists to guarantee (per-axis pixel→point scale) and
the single guard the card explicitly ordered a test for (`geometry_from_evidence` never
raises). Under BATCH9-RULES' proof floor — *"every mutant applied exactly as documented …
a test named after a gate is not a test of that gate"* and *"`claimed != validated`"* — a
durable record asserting 9/9 when 2 survive cannot compose. **No production change is
required to close this; three tests and a W3 correction are.**

---

## 1. Claim-by-claim (claimed → what I measured)

| # | claim (W3 `§P21GEOMETRY` / cell report) | what I measured, independently | verdict |
|---|---|---|---|
| 1 | legacy-copy equivalence, 0 mismatches, 3 fixtures + 12 pinned corpus PDFs | I wrote my OWN legacy copy from `git show 888fb1c:analysis/structurer/geometry.py` (byte-verbatim, md5 `1d9c30fd51b737fd85247acc1c49c91f`) and compared `geometry_from_pdf` against it on **all 109** manifest documents (`docs/balance-metrics-audit-results.csv`, the enumerator `corpus_gate.manifest_paths` uses): `manifest_paths=109 · missing_on_disk=0 · compared=109 · both_none=6 · mismatched_documents=0`. My comparison is a **superset** of the cell's: it also compares `GeoLine.page`, which `_assert_geometry_equal` omits. Still 0. | **confirmed, and stronger than claimed** |
| 2 | during development, the full 109-PDF / 830-page corpus | independent census straight from PyMuPDF over the 109 manifest PDFs: `documents=109 · pages_total=830 · native_words_total=261526` | **confirmed exactly** |
| 3 | 0 rotated pages in the corpus | `rotated_pages=0`, `rotation_histogram={0: 830}` — counted over **all** 830 pages including the 6 documents whose native evidence is `None` (the cell's committed test only walks pages of documents whose evidence is non-`None`, over 12 PDFs) | **confirmed** |
| 4 | 0 degenerate PyMuPDF word boxes among 261,526 words | `degenerate_word_boxes=0`, `inverted_word_boxes=0` out of `native_words_total=261526` | **confirmed exactly** |
| 5 | pixel round-trip exact to 1e-6 | re-measured worst per-corner round-trip error over the fixture rows: **0.000e+00 px** | **confirmed** |
| 6 | max native-vs-pixel delta 0.6002 pt | re-measured from the branch's own code path: **0.6002 pt** | **confirmed exactly** |
| 7 | mutation table M1–M9, all killed | 14 mutants applied by me. **KILLED: M1, M2(PageGeometry site), M3, M4, M5, M7, M8, M9(the W3's own narrower variant).** **SURVIVED: M2 at the `GeoLine` site (F-2), M6 as the card words it (F-1), M9 as the card words it (BLOCK-1), plus two reviewer variants (F-3, F-1).** | **NOT confirmed — see BLOCK-1, F-1, F-2** |
| 8 | 5 canonical guards, 267 | `pytest tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py tests/test_r1_hardcodes.py tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py -q` → **267 passed, exit 0** | **confirmed** |
| 9 | analysis→ocr allowlist EMPTY; `evidence/` standard-library-only | `pytest tests/test_escalation_tripwires.py tests/test_evidence_boundary.py -q` → **11 passed, exit 0**; `ANALYSIS_TO_OCR_ALLOWLIST = frozenset()` at `tests/test_escalation_tripwires.py:49` | **confirmed** |
| 10 | `tests/test_geometry_frames.py` 30 passed | `pytest tests/test_geometry_frames.py tests/test_structurer.py tests/test_evidence_canonical.py tests/test_evidence_boundary.py -q` → **147 passed, exit 0** | **confirmed** |
| 11 | privacy scan 0 | `tools/privacy_scan_branch.py --base 888fb1c --ref dbad83f --data-dir <train10 cold> --rows <TRAIN10-941918f run>/rows.csv`: **`hit_count 0`** (`raw_hit_count 15`, all attributed to the documented exclusion table: 1 `hex_sha_substring`, 2 `round_money`, 12 `words_class`); `population 3380 · documents_read 3351 · added_lines 1199` | **confirmed** |
| 12 | no file outside the card's ownership touched; no `ocr`/network import | `git diff --name-only 888fb1c..dbad83f` = exactly `analysis/structurer/geometry.py`, `tests/test_geometry_frames.py`, `docs/moneythumb-replacement/W3_TRACKA_LOG.md`. No added line imports `ocr`, `requests`, `urllib`, `http` or `socket`. `rows.py` / `core.py` / `grounding.py` untouched. W3 diff is append-only (0 deleted content lines) and opens with its own `# §P21GEOMETRY — …` heading. | **confirmed** |
| 13 | 12 pinned corpus PDFs "spread across 12 different institution folders" | all 12 relative paths are in the manifest (`not-in-manifest=0`), and all 12 are already literal in tracked `corpus_gate.py`, so no new name is exposed — but they span **10 distinct top-level folders / 11 distinct folder prefixes**, not 12 | **minor overstatement — F-6** |
| 14 | rotation "record, don't fix, note it"; note actually emitted | I built rotated synthetic PDFs at 90/180/270: frame records `page.rect` (the ROTATED display rect: 792.0×612.0 at 90°), `rotation_deg` is the real rotation, `notes=('native_words_unrotated_space',)` is emitted for every non-zero rotation and absent at 0, and legacy == new on all four rotations. On a rotated page a real footer word lands **151.0 pt below the frame's declared height** and is accepted (a `pdf_point` frame carries no bounds check) — exactly the mismatch the W3 names as the Phase-2.2 prerequisite | **confirmed and honestly recorded** |
| 15 | full suite 8,451 / conformance 1,282 / corpus_gate 105-3-1 / `-m corpus` 34 / cohort replay 39/39 + 159/159 | **NOT re-run** — the brief and the one-harness-per-host rule exclude them, and nothing I found required them | not re-verified |

---

## 2. Findings

### BLOCK-1 — the card's M9 survives: no committed test can tell `scale_x` from `scale_y`

**File:** `analysis/structurer/geometry.py:324-325` (the conversion); `tests/test_geometry_frames.py:384-390` (`_pixel_frame`, the only pixel-frame factory in the suite).

The card's M9 is *"scale applied on one axis only → the round-trip on a non-square page."* A
non-square page does **not** produce different per-axis scales. Every pixel frame the suite
builds derives both scales from the same `dpi/72`:

```
the cell's _pixel_frame(dpi=150.0): scale_x=2.0833333333333335 scale_y=2.0833333333333335 equal=True
the cell's _pixel_frame(dpi=300.0): scale_x=4.166666666666667  scale_y=4.166666666666667  equal=True
```

So any mutant that uses one axis' scale for both axes is invisible. Reproduced, mutants
applied one at a time with `git checkout --` restore and a clean-tree re-check:

* **M9-reviewer** — `y` divided by `frame.scale_x` instead of `frame.scale_y` (x still
  correct): `pytest tests/test_geometry_frames.py tests/test_structurer.py
  tests/test_evidence_canonical.py tests/test_evidence_boundary.py -q` → **exit 0,
  SURVIVED**.
* **M9-rev2** — BOTH axes divided by `frame.scale_x`: → **exit 0, SURVIVED**.
* **M9-cell** — the W3's own narrower wording ("x left unconverted, y scaled") → exit 1,
  KILLED by `test_a_pixel_evidence_round_trips_through_geometry_within_1e6_points` and
  `test_a_native_read_and_an_independently_authored_pixel_read_of_the_same_rows_agree_within_1_5pt`.

The property is not untestable — a frame with distinguishable per-axis scales is legal
under `evidence/canonical.py`'s own validation (both scales within 1 % of `dpi/72`, each
within 1 % of its own raster/pdf ratio), which is what a rasteriser that rounds one
dimension produces:

```
PageFrame.pixel(page_index=0, raster_width_px=2550, raster_height_px=3320,
                dpi=300.0, pdf_width_pt=612.0, pdf_height_pt=792.0)
  -> built OK: scale_x=4.166667 scale_y=4.191919 (ratio 1.006061)
  branch y0 = 238.554217 pt   correct (scale_y) = 238.554217   M9-reviewer (scale_x) = 240.000000
  undetected error = 1.4458 pt
```

The branch is **correct** — it produces 238.554217. Nothing proves it stays correct. This
is the exact failure mode the card's own "Why" section names ("if PDF points and pixels can
be confused, every later column decision is wrong by a factor of dpi/72"), one axis at a
time, and it is the property the Paddle consumer in cell P will inherit.

**Fix required:** add one pixel-frame case whose `scale_x != scale_y` (e.g. the
`2550 × 3320 @ 300 dpi` frame above) to
`test_a_pixel_evidence_round_trips_through_geometry_within_1e6_points`, asserting the
converted point value against the **authored** point coordinate (not against
`to_pixels`-of-itself, which is symmetric under a single-scale bug on a square-scaled
frame). Correct the W3's M9 row to state the variant actually applied and that the
per-axis case is now covered.

### BLOCK-2 — the W3's mutation table records 9/9 KILLED; 2 of 9 survive as documented

**File:** `docs/moneythumb-replacement/W3_TRACKA_LOG.md`, `§P21GEOMETRY` → "Mutation table —
every mutant killed", rows M6 and M9.

BLOCK-1 is M9. M6 is F-1 below. Both are the card's own mutants, applied as the card words
them, run without `-x`. The W3 is a durable record and the report contract is explicit that
`claimed != validated`; the table must be corrected to name the variant actually applied per
row, and the killers must exist before the row can read KILLED.

**Fix required:** correct the M6 and M9 rows in the W3 after the two tests below exist, and
re-report the table with each mutant's exact substitution named.

### MAJOR F-1 — M6 survives: the `except Exception → None` guard is never exercised

**File:** `analysis/structurer/geometry.py:341-342`; test
`tests/test_geometry_frames.py:586-604`.

Mutant applied: `except Exception:\n        return None` → `except Exception:\n        raise`
(the faithful reading of the card's *"M6 `geometry_from_evidence` raises on a hostile page →
the never-raises test"*). Result: **exit 0, SURVIVED**.

Root cause: both hostile objects in the named killer test are stopped by the *explicit*
`isinstance` guards (`geometry.py:318` for the frame, `:322` for the word), which `return
None` on their own path and never enter the `except`. The broad guard is therefore untested
— yet it is load-bearing. I reached it with two objects the card's own wording describes:

```
dangling-word-id evidence (real WordBox + a real LineBox naming a word the page lacks)
    -> None                     (KeyError raised at geometry.py:331, caught by the guard)
no-notes-attribute evidence
    -> None                     (AttributeError raised at geometry.py:335, caught by the guard)
```

Both are answered correctly today. Neither is asserted anywhere, so the guard can be
deleted without a red test.

**Fix required:** extend
`test_geometry_from_evidence_never_raises_on_a_hostile_duck_typed_object` with at least one
object that reaches the `except` — the dangling-`word_ids` `LineBox` case is the one the
card describes ("whose `lines` reference a word id its page lacks") and is currently only
asserted at the `evidence/` construction boundary, never at `geometry_from_evidence`.

### MAJOR F-2 — M2 survives on the `GeoLine.page` site, which production consumes

**File:** `analysis/structurer/geometry.py:333`
(`lines.append(GeoLine(page.page_index + 1, row, text, spans))`); the equivalence assertion
at `tests/test_geometry_frames.py:191-206`.

`geometry_from_evidence` writes the 1-based page number in **two** places — `GeoLine`
(`:333`) and `PageGeometry` (`:338`). The card's M2 (`page = page_index`, the 0-based leak)
is pinned on only one of them:

* mutant at `:338` (`PageGeometry`) → exit 1, **KILLED** by 18 tests (the whole equivalence
  pin plus `test_page_geometry_page_is_frame_page_index_plus_one_including_an_empty_middle_page`);
* mutant at `:333` (`GeoLine`) → **exit 0, SURVIVED** across
  `test_geometry_frames.py + test_structurer.py + test_evidence_canonical.py +
  test_evidence_boundary.py`.

It survives because `_assert_geometry_equal` compares `ll.text`, `ll.spans` and each word's
box but **not** `ll.page` (`tests/test_geometry_frames.py:202-206`), and no other test reads
a `GeoLine.page` produced by `geometry_from_evidence`. `GeoLine.page` is not decorative:
`analysis/structurer/rows.py:158` does `SourceLine(line.page, line.text, index, line)`, and
that page number flows into `rows.py:322`, `rows.py:433`, `summary.py:110/216/231` and
`grounding.py:182/213`'s per-page text lookup. A 0-based leak here would silently misground
every row by one page the moment Phase 2.2 wires the structurer on.

The branch is **correct** today: my full-corpus comparison DID compare `GeoLine.page` across
all 109 documents and found 0 mismatches. The gap is in the pin, not the code.

**Fix required:** add `assert ll.page == nl.page` to `_assert_geometry_equal`
(`tests/test_geometry_frames.py:202`) — one line, and it re-kills M2 at both sites.

### MINOR F-3 — the M4 AST guard is narrower than its own docstring

**File:** `tests/test_geometry_frames.py:349-361`.

The guard collects only `ast.Call` nodes whose `func` is the bare `Name` `median`, plus a
string check for `"import median"` / `"from statistics"`. The card's M4 (`median(...) * 0.5`)
is duly **KILLED**. A hand-rolled median is not:

* mutant M4b — `_heights = sorted(w.height for w in words); _tolerance =
  max(1.0, _heights[len(_heights)//2] * 0.5)` passed to `_canonical_group_lines(boxes,
  tolerance=_tolerance)` → **exit 0, SURVIVED**.

The docstring claims the guard catches "any tolerance arithmetic". It catches one spelling.
Impact is bounded: `_group_lines` has **no production caller at all** on this branch
(`native_evidence_from_pdf` relies on `PageEvidence`'s own auto-grouping; `geometry_from_evidence`
never regroups), so M4b changes nothing a consumer sees — but the guard is the cell's only
stated defence of "ONE grouping rule".

**Fix suggested:** also fail on any `tolerance=` keyword argument passed to
`_canonical_group_lines` from `geometry.py` (the delegation is meant to be unparameterised),
or soften the docstring to what the guard actually enforces.

### MINOR F-4 — the "`x_at` returns points" assertion is self-referential

**File:** `tests/test_geometry_frames.py:454` —
`assert first_line.x_at(0) == pytest.approx(first_line.words[0].x0)`.

The card requires "`GeoLine.x_at(offset)` returns the word's x0 in **POINTS**". The
assertion compares `x_at(0)` to the same `Word`'s `x0`, so it holds in any unit. Measured on
the fixture's first word, authored at 40.0 pt and stored as a 166.667 px box:

```
x_at(0) = 40.00008   words[0].x0 = 40.00008
```

The behaviour is right; the assertion cannot detect a unit error (M1 is caught elsewhere, by
the round-trip). **Fix suggested:** compare `x_at(0)` against the authored point value.

### MINOR F-5 — a per-word validation failure now destroys a whole page (behaviour divergence)

**File:** `analysis/structurer/geometry.py:261-265` (the `WordBox` construction) inside the
per-page `try` at `:250-270`.

`WordBox.__post_init__` refuses a box that is not strictly `x0 < x1 and y0 < y1`
(`evidence/canonical.py`). That refusal is raised inside the per-page `try`, so **one** odd
word box turns the entire page into an empty `native_page_unreadable` placeholder — a note
that says the page could not be read when in fact it read fine. Phase 2.0 kept every word.
Reproduced by injecting a zero-height box into the first word of a one-page synthetic PDF
(`fitz.Page.get_text` monkeypatched, restored in a `finally`):

```
legacy: pages=1 word_count=9 page1=(612.0x792.0) lines=3
new   : None                       (the placeholder has 0 words, so word_count==0 -> None)
evidence page notes = evidence is None
```

The same shape appears for a zero-area `page.rect`: legacy keeps 9 words at `0.0 x 0.0`, the
branch returns `None`.

**I could not reproduce this from a real PDF.** I tried a zero-scale text matrix and a
mirrored text matrix in a hand-written content stream (PyMuPDF normalises the box), and
`insert_text` at fontsize 0.0 / 0.001 / 0.01 (0 words, or a valid sub-point box). Corpus
evidence: **0 degenerate and 0 inverted boxes out of 261,526 words**. So this is a latent
divergence, not a live one, and the module is dormant — hence MINOR rather than MAJOR. It
is worth a line in the W3's risks (the failure is page-wide and mislabelled) because the
Paddle adapter will feed the same constructor with boxes that are far less well-behaved than
PyMuPDF's.

Related, same class: `_group_lines` (`geometry.py:188-208`) now **raises**
`MalformedGeometry` on an inverted `Word` where the Phase-2.0 `_group_lines` returned a line
(`legacy: ['A B']` vs `new raised MalformedGeometry: inverted or degenerate box for
p0.l-.w0`). `_group_lines` has no production caller, but `tests/test_evidence_canonical.py:284`
imports it, so the total-function contract it used to have is gone silently.

### MINOR F-6 — three small inaccuracies in the durable W3 record

1. "12 pinned corpus PDFs … spread across **12 different institution folders**": measured
   **10 distinct top-level folders / 11 distinct folder prefixes** (one folder contributes
   two files, and one top-level folder contributes two sub-folders). All 12 are in the
   manifest and all 12 paths are already literal in tracked `corpus_gate.py`, so there is no
   exposure issue — only a wrong count in a record that is supposed to be measured.
2. The M6 and M9 rows (BLOCK-2).
3. "the earlier figure is deliberately not restated here" — true of the W3, but commit
   `88c09cb`'s **diff** still carries the coincidentally-matching literal on its `-` line, so
   the instance is one `git show` away in the branch history Ocean is about to compose. The
   privacy scanner only reads ADDED lines, which is why it reports 0. The branch is unpushed,
   so the cheap remedy is to squash `88c09cb` into `0d26bcf` before composition (trees
   byte-identical, one fewer commit); a token in a pushed history is not cheap. Reported as
   a class, not an instance, per the rules.

### MINOR F-7 — `geometry_from_pdf` is 2.69× slower, half of it a hash nothing reads

**File:** `analysis/structurer/geometry.py:283-286`.

`ExtractionEvidence.__post_init__` canonical-JSON-serialises and SHA-256s **every word of
every page** to derive `evidence_sha256`. `geometry_from_pdf` pays that on every call and
then throws the digest away — nothing in `DocumentGeometry` carries it. Measured over the
109 manifest PDFs, same process, same order:

```
phase_2_0_total_s = 2.57      branch_total_s = 6.92      ratio = 2.69x
  native_evidence_from_pdf  6.11 s
  geometry_from_evidence    0.63 s
  document canonical-JSON + sha alone   2.24 s   (~51 % of the added cost)
```

Dormant today, so not a regression anyone feels; worth naming as a Phase-2.2 prerequisite
alongside rotation, since Phase 2.2 is where this runs per document at scale. A lazily
computed `evidence_sha256` (or an opt-out for the native reader, which never serialises its
evidence) would recover it — but `evidence/canonical.py` is Ocean's file, so this is a
**report, not an edit**, exactly as the card instructs.

### MINOR F-8 — a source-specific note is interpreted in the source-neutral path

**File:** `analysis/structurer/geometry.py:335-336`.

`geometry_from_evidence` — the ONE path for *any* extractor — special-cases the string
`UNREADABLE_PAGE_NOTE` (`"native_page_unreadable"`, a native-reader concept) to force
`width, height = 0.0, 0.0`. It is the only place the "one path regardless of source" claim
leaks a source-specific fact, and a future adapter that emitted the same note string would
silently zero its page dimensions. It is the honest way to preserve Phase 2.0's byte-identity
and I am not asking for it to change in this cell; it should be named in the W3 as a
Phase-2.2 clean-up so the next cell does not discover it.

---

## 3. What I attacked and could not break

* **The equivalence pin itself.** Re-derived from my own verbatim copy of `888fb1c`'s
  `geometry.py`, over **109/109** manifest documents (not 12), with a comparison that adds
  `GeoLine.page` to the cell's field set: **0 mismatches**, `both_none=6`. The re-homing is
  genuinely behaviour-preserving on this corpus.
* **Word ordering and tie-breaking.** `group_lines` sorts by `(round(mid_y, 1), x0)` and
  each row by `x0`; `sorted`/`list.sort` are stable in both the legacy and the new path, and
  the new path's word ids are unique per page (`enumerate` runs over the *unfiltered* PyMuPDF
  list, so blanks do not collapse indices). 261,526 words reproduce exactly. M7 (re-sort by
  text) is killed by 17 tests.
* **Empty pages.** M3 (drop them) is killed by four tests; the 3-page empty-middle-page pin
  and the page-number pin both bite.
* **Mixed-space documents.** Page 0 `pixel` / page 1 `pdf_point` converts per page; the
  `pdf_point` page's box is exact identity. I additionally built a mixed document whose pixel
  page has `scale_x != scale_y` and the conversion was correct.
* **Rotation.** Recorded, never corrected, on 90/180/270; the note IS emitted (and absent at
  0); legacy == new on all four; the 151.0 pt frame/word mismatch on a rotated page is real,
  accepted without a bounds check (`pdf_point` frames carry none), and honestly named as the
  Phase-2.2 prerequisite rather than silently fixed. 0/830 corpus pages are rotated, so
  nothing is live.
* **Malformed geometry reaching the consumer.** Inverted boxes, boxes outside their raster,
  a dpi/scale disagreement and a dangling `word_ids` reference all refuse at `evidence/`
  construction; I could not build an `ExtractionEvidence` carrying any of them.
* **`geometry_from_evidence` raising.** Despite F-1, I could not make the shipped function
  raise: dangling word ids, a missing `notes` attribute, a non-`PageFrame` frame, non-`WordBox`
  words, non-`LineBox` lines and `None` all return `None`.
* **Ownership and exclusions.** Exactly the three files the card names; `rows.py`, `core.py`,
  `grounding.py`, `ocr/`, `discovery/`, `webapp/`, `telemetry/` untouched; no `ocr` import, no
  network import, no Paddle code, no `evidence_refs[]`, no page-level routing, no rotation
  fix, no `evidence/canonical.py` edit. `GENERIC_STRUCTURER_ENABLED` stays unset and is pinned.
  The analysis→ocr allowlist is still `frozenset()`.
* **Hardcodes.** The 5 canonical guards pass at 267 including the layer-wide
  `tests/test_no_statement_hardcodes.py`; nothing statement- or bank-specific in
  `geometry.py`; every fixture string is synthetic (2054-dated).
* **Synthetic fixtures encoding real values.** The privacy scanner over the branch's 1,199
  added lines against 3,351 cached documents: `hit_count 0` (15 raw hits, all attributed to
  the documented exclusion table). The one replaced fixture amount is genuinely replaced in
  the tree; my only issue with it is where the old one still lives (F-6.3).
* **CI availability of the 12 corpus PDFs.** I suspected the new unmarked corpus-reading tests
  would fail in CI because `.gitignore` carries `Bank Statements/**` — they will not: all 109
  corpus PDFs are **tracked** (`git ls-files "Bank Statements" | wc -l` = 109) and the ignore
  comment says so explicitly. Dismissed.
* **Vacuous corpus tests.** `test_no_page_in_the_pinned_corpus_sample_is_rotated` guards
  itself with `assert total_pages > 0`; the sha16 pin fails rather than skips on a changed
  file. Both fine.
* **W3 hygiene.** Append-only, own `# §P21GEOMETRY — …` heading on the first appended line,
  no other section edited. All four commit messages state classes, never instances.

---

## 4. What closing this looks like

No change to `analysis/structurer/geometry.py` is required. Three test edits and a W3
correction:

1. `tests/test_geometry_frames.py:202` — add `assert ll.page == nl.page` (closes F-2 / re-kills M2).
2. `tests/test_geometry_frames.py:407-454` — add a pixel frame with `scale_x != scale_y`
   (e.g. `raster 2550 × 3320 @ 300 dpi` on a 612 × 792 pt page) and assert converted points
   against the **authored** point coordinates (closes BLOCK-1 / kills M9 as documented).
   Optionally fix `:454` to compare against the authored value too (closes F-4).
3. `tests/test_geometry_frames.py:586-604` — add a hostile object that reaches the
   `except` (a real `LineBox` whose `word_ids` name a word the page lacks) and assert `None`
   (closes F-1 / kills M6 as documented).
4. W3 `§P21GEOMETRY` — correct the M6 and M9 rows with the exact substitutions applied, fix
   the folder count, and add F-5 / F-7 / F-8 to the risks (closes BLOCK-2 / F-6).
5. Squash `88c09cb` into `0d26bcf` before composition (F-6.3).

Re-run after the edits: `pytest tests/test_geometry_frames.py tests/test_structurer.py
tests/test_evidence_canonical.py tests/test_evidence_boundary.py -q` and the mutation table
with M2 applied at BOTH page-number sites, M6 as `except → raise`, and M9 as "one axis' scale
used for both axes". Re-review is then a short pass over the four diffs.

---

# Re-review

```
BRANCH        wave21-geometry @ 1993fda   (reviewed detached in .claude/worktrees/rev21-geometry)
BASE          888fb1c
REWRITE       0d26bcf+88c09cb -> feff4dd · 5d2769e -> 391e74b · dbad83f -> b4dc5eb
CLOSURE       eee66b3 (BLOCK-1, F-1, F-2, F-4, F-5, F-8) · 5f2adce (F-3) · 46256a5 · 1993fda (docs)
DIFF          git diff 888fb1c..1993fda   (3 files, +1614 / -54)
VERDICT       APPROVE WITH FINDINGS   (was BLOCK)
```

Every number below is one I measured at `1993fda` in this worktree, with my own instruments — the
same verbatim `888fb1c` legacy copy (md5 `1d9c30fd51b737fd85247acc1c49c91f`), my own mutation
harness, my own probes. `tasklist | findstr python` was clean before every run; one harness at a
time; the harness refuses a dirty tree, restores in a `finally`, and re-verifies. Nothing was
merged, rebased, pushed or committed by me. `corpus_gate.py`, `pytest -m corpus`, the full suite and
the cohort replays were **not** re-run (host-sharing rule; no finding required them).

## RR-1 — the history rewrite

| check | measured |
|---|---|
| `git rev-parse 88c09cb^{tree}` vs `feff4dd^{tree}` | both `7e083f33c08bb2e02133429a0c82ff484119ac03` — identical |
| `git rev-parse dbad83f^{tree}` vs `b4dc5eb^{tree}` | both `fca8bd46b63a4bf3f4f3c94da2496c3362436c58` — identical |
| `git diff 88c09cb feff4dd` / `git diff dbad83f b4dc5eb` | both empty |
| `git branch -a --contains 88c09cb` | empty — the pre-rewrite commits are dangling (reflog only), reachable from no ref |
| the coincidentally-matching literal anywhere in `git log -p 888fb1c..HEAD` | **0 occurrences** (both spellings) |

The squash is exactly what it claims: byte-identical trees, and F-6.3's instance is out of the
history Ocean will compose. **Closed.**

## RR-2 — claim-by-claim on the closure

| # | closure claim | what I measured | verdict |
|---|---|---|---|
| 1 | BLOCK-1 closed; both M9 variants killed | I re-applied **four** distinct per-axis mutants at `geometry.py:367-368`: y÷`scale_x`, both÷`scale_x`, both÷`scale_y`, and x/y scales swapped. **All four exit 1, KILLED**, each by `test_a_pixel_evidence_with_distinct_per_axis_scale_converts_each_axis_correctly`. The two that survived my first review are dead. | **closed, and wider than claimed** |
| 2 | F-1 closed (dangling-word-id `LineBox` + a mid-iteration raise) | `except Exception: return None` → `raise` at `geometry.py:389`: **exit 1, KILLED** by `test_geometry_from_evidence_never_raises_on_a_hostile_duck_typed_object`. I then invented five further hostile shapes not in the suite — a `pages` iterator that raises, a `page_index` property that raises, a missing `extractor_id`, a `lines` tuple holding a bare `object()`, and a `words` tuple holding a `bool` — **all five return `None`, none raises**. | **closed** |
| 3 | F-2 `GeoLine.page` compared | `GeoLine(page.page_index, …)` at `geometry.py:376`: **exit 1, KILLED** by the equivalence pin (synthetic fixtures + empty-middle-page + all 12 pinned corpus PDFs). The new `assert ll.page == nl.page` is at `tests/test_geometry_frames.py:203`. | **closed** |
| 4 | F-3 the AST guard refuses `statistics`, `sorted(`, `0.6` | the `sorted()`-based hand-rolled median (my original M4b): **exit 1, KILLED**. A `list.sort()`-based one: **exit 0, SURVIVED** — see **RR-3 (R-1)**. | **partially closed** |
| 5 | F-4 independent point value | `tests/test_geometry_frames.py` now compares `x_at(0)` against `first_word_px.x0 / frame.scale_x`, derived from the ORIGINAL pixel box | **closed** |
| 6 | F-5 split into two notes, page still fail-closed, real dimensions | reproduced both branches on a 2-page synthetic document: page-read throws → `notes=('native_page_unreadable',)`, 0 words, dims `(1.0, 1.0)`; one word box refused → `notes=('native_page_word_refused',)`, 0 words, dims `(612.0, 792.0)` — the REAL page — while legacy kept 6 words. The sibling page is unaffected in both (`612.0×792.0`, 1 line). Three mutants — the two notes swapped, the refused page given a 1×1 placeholder, and "drop only the offending word" — **all exit 1, KILLED** by `test_a_page_with_one_refused_word_reports_its_real_dimensions_not_unreadable`. | **closed** |
| 7 | F-6 folder count corrected | my recount stands: **10 distinct top-level folders / 11 distinct folder prefixes**, exactly as the closure section now records | **closed** |
| 8 | F-7 reported, `evidence/canonical.py` untouched | `git diff --name-only 888fb1c..1993fda` = the same 3 files; `evidence/canonical.py` is not among them | **closed** |
| 9 | F-8 note branch removed; documented 1.0×1.0 consequence | reproduced (row 6 above). Putting the note branch back: **exit 1, KILLED** by `test_the_unreadable_native_page_placeholder_reports_its_own_frame_dimensions` — so the divergence is pinned in BOTH directions. | **closed; see RR-3 (R-2)** |
| 10 | corrected mutation table 12/12 killed | 11 of my 12 re-review mutants killed; the single survivor is a **13th** variant the table does not claim (RR-3, R-1). The table's own 12 rows are accurate. | **confirmed** |
| 11 | 0 mismatches re-verified, 109 PDFs / 830 pages | my own harness against the closure tree: `manifest_paths=109 · missing_on_disk=0 · compared=109 · both_none=6 · mismatched_documents=0`, comparing `GeoLine.page` as well; rotation census `pages_total=830 · rotated_pages=0` | **confirmed** |
| 12 | targeted 157 · guards 267 · tripwires+boundary 11 | `157 passed` (5 files), `149 passed` (the closure's own 4-file set), `test_geometry_frames.py` alone `32 passed`; guards **267 passed**; `test_escalation_tripwires.py + test_evidence_boundary.py` **11 passed** — all exit 0 | **confirmed** |
| 13 | privacy 0 | `privacy_scan_branch.py --base 888fb1c --ref 1993fda`: **`hit_count 0`** (`raw_hit_count 23`, all attributed to the documented exclusion table: 1 `hex_sha_substring`, 2 `round_money`, 20 `words_class`); `added_lines 1614 · population 3380 · documents_read 3351 · residue_sites 0` | **confirmed** |
| 14 | ownership; W3 append-only | 3 files only; W3 diff has **0 deleted content lines** and the closure section opens with its own `# §P21GEOMETRY-CLOSURE — …` heading; the prior `§P21GEOMETRY` section is untouched | **confirmed** |
| 15 | `geometry_from_pdf` byte-identical on every readable page | row 11 plus rotation at 0/90/180/270: `rotation_deg` recorded, `native_words_unrotated_space` emitted for each non-zero rotation and absent at 0, `legacy_equals_new=True` at all four | **confirmed** |
| 16 | full suite 8,453 / 45 / 38; message scan 0 | **not re-run** (host-sharing rule) | not re-verified |

## RR-3 — residual findings (all MINOR; none blocks composition)

### R-1 (MINOR, residual of F-3) — the widened AST guard still admits one spelling

**File:** `tests/test_geometry_frames.py:351-393`.

The guard now refuses `median` calls (Name and Attribute), any `statistics` import, any `sorted(`
call and the float literal `0.6`. Its docstring claims a tolerance computation "however spelled" is
caught. One spelling is not:

```
mutant R8: _h = [w.height for w in words]; _h.sort()
           _tol = max(1.0, _h[len(_h)//2] * 0.5)
           _canonical_group_lines(boxes, tolerance=_tol)
  -> pytest tests/test_geometry_frames.py tests/test_structurer.py
            tests/test_evidence_canonical.py tests/test_evidence_boundary.py -q
  -> exit 0, SURVIVED
```

`list.sort()` is an `ast.Attribute` call, not the `sorted` `ast.Name` the guard looks for, and `0.5`
is not `0.6`. Impact today is nil: `_group_lines` has **no production caller** anywhere
(`grep -rn "_group_lines" analysis/ webapp/ discovery/ ocr/ telemetry/ tools/` returns only
`geometry.py`'s own definition and docstrings), and `geometry_from_evidence` never regroups.

**Fix suggested (not required to compose):** the mechanism every grouping mutant needs is passing a
`tolerance=` keyword to `_canonical_group_lines` — both R7 (killed) and R8 (surviving) do it. An AST
assertion that `geometry.py` passes **no keyword argument** to `_canonical_group_lines` kills the
whole class independently of how the median is spelled; adding `.sort(` to the banned-call set closes
the inline-regrouping variant too. Alternatively, soften the docstring to what the guard enforces.

### R-2 (MINOR, registration) — F-8's accepted consequence is a named exception to a ruled card deliverable

**File:** `analysis/structurer/geometry.py:378-387`; pin at
`tests/test_geometry_frames.py::test_the_unreadable_native_page_placeholder_reports_its_own_frame_dimensions`.

Card item 3 is ruled ("do not re-decide"): `geometry_from_pdf` must be
`geometry_from_evidence(native_evidence_from_pdf(…))` **with BYTE-IDENTICAL output**. After F-8, an
`UNREADABLE_PAGE_NOTE` page reports `1.0 × 1.0` where Phase 2.0 reported `0.0 × 0.0`. Reproduced:

```
page-read throws:  new p0 dims=(1.0, 1.0)   legacy p0 dims=(0.0, 0.0)
```

I record it as a finding for Ocean's *composition* record, not as a defect, because: the change was
made on Ocean's ruling, which explicitly overrode my own recommendation to leave it documented; it is
**forced** — `PageFrame` refuses non-positive dimensions, so a `0.0 × 0.0` frame is unconstructible,
and "no note branch in the neutral path" and "byte-identical on this page" are mutually exclusive;
it is **untriggered** (0/109 PDFs, 0/830 pages); it is **inert** — I found **no consumer of
`PageGeometry.width`/`.height` anywhere** outside `geometry.py` itself; and it is pinned in both
directions (re-adding the branch is KILLED). The only thing owed is that a ruled deliverable's
exception belongs in the composition record, not only in the cell's own W3.

### R-3 (MINOR, wording) — one sub-case is filed under a note whose docstring names a narrower cause

**File:** `analysis/structurer/geometry.py:78-88` (the `UNREADABLE_PAGE_NOTE` docstring) and
`:294-296` (the catch).

The first `try` now spans `get_text` / `page.rect` **and** `PageFrame.pdf_points(...)`. A page whose
read succeeds but whose *frame* `evidence/` refuses — a zero-area rect being the reachable shape —
is therefore filed as `native_page_unreadable`, although nothing threw during the read. Reproduced:

```
zero-area page rect:  notes(p0)=('native_page_unreadable',)  words(p0)=0
                      new p0 dims=(1.0, 1.0)    legacy p0 dims=(0.0, 0.0), 6 words kept
```

The classification is defensible — the note's operative meaning ("there is never a real `page.rect`
to report") does hold, since no representable dimensions exist — but the docstring states the cause
as "this page's own `get_text`/`rect` read **threw**", which is narrower than what the block catches.
0/109 incidence. **Fix suggested:** one docstring clause ("…threw, or produced a rect this contract
cannot represent"), or move the frame construction into the second `try` if the intent is that a
refused frame be a word-class failure.

## RR-4 — what I attacked in the closure and could not break

* **The per-axis conversion.** Four distinct scale-confusion mutants, all killed. The new test's
  frame really does have `scale_x != scale_y` and it asserts against authored point values, so it
  is not symmetric under the bug the way a same-scale round-trip is.
* **The exception guard.** Killed by the new cases, and five further hostile shapes I invented all
  return `None` without raising. I could not make `geometry_from_evidence` raise.
* **The F-5 split.** Three mutants (notes swapped, placeholder frame for the refused page, keep-the-
  good-words) all killed; the fail-closed direction and the real-dimension reporting are both pinned.
* **The F-8 removal.** Pinned in both directions; re-adding the note branch is killed.
* **Equivalence.** 109/109 documents, 0 mismatches, including `GeoLine.page`; 830 pages; 0 rotated;
  rotation still recorded, noted and byte-identical at all four rotations.
* **Scope.** Still exactly 3 files; `evidence/canonical.py` untouched as instructed; no `ocr`,
  network or Paddle import; `rows.py` / `core.py` / `grounding.py` untouched; guards 267 and the
  boundary/tripwire tests green; the analysis→ocr allowlist still `frozenset()`.
* **Privacy.** 0 hits over 1,614 added lines against 3,351 cached documents; the reworded W3 figures
  and the squash both hold up.
* **The corrected mutation table.** Every one of its 12 rows reproduces; my only survivor is a
  variant it does not claim.

**Verdict: APPROVE WITH FINDINGS.** Both BLOCKs and all six MINOR/MAJOR findings from the first
review are closed and independently re-killed. The three residuals above are MINOR, none is a
correctness defect, and none needs to hold up composition: R-1 is a guard-completeness gap on
production-dead code, R-2 is a registration item for Ocean's composition record, R-3 is a one-clause
docstring correction.
