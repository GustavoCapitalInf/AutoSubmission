# Phase 2.3 cell X (P23-AGREE) — independent adversarial review

```
REVIEWER: independent agent; wrote none of this code. Fresh detached worktree
          `.claude/worktrees/rev23-agree` at 1ee8b31, plus my own base worktree
          `.claude/worktrees/rev23-agree-base` at 26f94f5. The cell's own
          `mt23-agree*` worktrees, the main checkout, the archive and the caches
          were never written to.
BASE:     26f94f5
TIP:      1ee8b31   (tree fc05bf5; code tree 8e2f00b = 913e3f4^{tree} — the W3 commit is docs-only)
DIFF:     git diff 26f94f5...1ee8b31   (12 files, 3,031 insertions, 2 deletions)
VERDICT:  APPROVE WITH FINDINGS — one MAJOR (N-2's chain resolution is false on a real
          PDF, regresses against base on that shape, and its pin asserts a fabricated
          library contract), six MINORs, all latent with corpus population 0.
DATE:     2026-09-11
```

## Verdict

**APPROVE WITH FINDINGS.** The instrument is real and the numbers are real. Every figure in the
cell's synthetic pair table re-derived on my own fixtures to the last digit, including the 0.7017
IoU floor; every proof-floor number re-derived exactly; M1–M10 re-ran 10/10 in my worktree; the
geometry census re-derived page for page under an instrument I wrote independently of the code it
checks. I could not break the properties the CTRL calibration will rest on.

One half of N-2 does not do what the code, the W3 and a named test all say it does, and on
that shape the tip is strictly worse than the base. Archive population is 0, so it blocks
nothing that exists; it does block the *claim*, and it must be fixed — or the claim withdrawn
and the test replaced — before composition.

## Findings

### MAJOR-1 — N-2 does not follow an indirect `/Rotate` chain; it returns the intermediate xref NUMBER as the rotation, and the page is refused where base read every word

`_resolved_rotate_int` (`evidence/native.py`) follows a chain only when `xref_object` returns a
form ending in `" R"`. **Real PyMuPDF returns a bare indirect-reference object as the number
alone**, so the preceding branch — `if source.lstrip("+-").isdigit(): return int(source)` —
fires and hands back *the xref number of the next object* as if it were an angle. The
`endswith(" R")` branch, `_MAX_INDIRECT_HOPS` and the `seen` cycle guard are therefore all
unreachable on a real document.

```
$ C:/Python314/python.exe scratchpad/rev23agree_a4c_chain.py      # my instrument, real PDFs
### real PyMuPDF's xref_object contract for a bare indirect reference
  A=12 B=13   xref_object(A) = '13'   (the test's stub returns '13 0 R'; the real library returns the number alone)
  _resolved_rotate_int(doc, '12 0 R') = 13   <- the XREF NUMBER, not the rotation
### (1) chain -> a non-multiple-of-90 xref number: the page is REFUSED
  chain A=12 -> B=13 -> 270  _raw_rotate=13  (true angle 270) -> evidence = None (the document's whole native reading is LOST)
  chain A=12 -> B=13 -> 0    _raw_rotate=13  (true angle 0)   -> evidence = None
  ... the same for terminal 90 and 45
```

It is a **regression against base** on a legal PDF shape — the same bytes read by each
worktree's own module (`scratchpad/rev23agree_a4d_regress.py`):

```
BASE 26f94f5  chain -> /Rotate 0    _raw_rotate=None  rotation_deg=0  words=6  notes=()
BASE 26f94f5  chain -> /Rotate 270  _raw_rotate=None  rotation_deg=0  words=6  notes=()
TIP  1ee8b31  chain -> /Rotate 0    _raw_rotate=13    evidence = None  (NATIVE READING LOST)
TIP  1ee8b31  chain -> /Rotate 270  _raw_rotate=13    evidence = None  (NATIVE READING LOST)
```

`/Rotate 0` reached through a chain is exactly the archive's own indirect shape — all four
indirect objects resolve to 0. One such page would lose the document's entire native reading,
where base read every word.

**The pin cannot fail.** `test_an_indirect_rotate_reference_chain_is_followed_and_a_cycle_terminates`
drives a `_Stub` whose `xref_object` returns `"2 0 R"` — a contract PyMuPDF does not honour.
Its docstring justifies the stub by the *cycle* (MuPDF flattens a self-reference at write
time), which is true; it then uses the same stub for the plain **chain**, which I built as a
real PDF in four lines. The docstring's "a reference chain is followed to
`_MAX_INDIRECT_HOPS`" and the W3's "a bounded walk so a chain is followed and a cycle cannot
spin" are both false as shipped. The mutation table does not cover it either: M9 dies on the
*direct*-indirect tests, not on the chain.

Corpus population **0** — my own census found 4 indirect `/Rotate` pages, **trail length 1**,
every one resolving to the integer 0 (`indirect_trail_lengths {"1": 4}`) — hence MAJOR, not BLOCK. Note the union replay **cannot**
see this defect: `tools/cohort_replay.py` re-analyses the run of record's CACHED text and never
calls the native reader, so its byte-identity at base and closure is not evidence about
`_resolved_rotate_int`. The only instrument that covers it is the corpus census, where the
population is 0. No STOP condition is touched: nothing validated regresses, and
`EXTRACTION_SCHEMA_VERSION` correctly stays at 3.

*Fix:* resolve with a call that is unambiguous about the distinction, or delete the
chain-following branch, answer `None` on anything that is not a first-hop integer, and correct
the docstring, the W3 and the test. Either way the stub must be replaced by a real-PDF pin —
`rev23agree_a4c_chain.py` builds one.

### MINOR-1 — three of my seven fresh mutants survive the cell's whole suite; one of them makes a debit agree with a credit

| mutant | result |
|---|---|
| **FR3** — the money comparison drops the SIGN (`abs(token.cents)`) | **NOT KILLED (0 failing)** |
| **FR4** — the skew statistic is the MEAN of the line slopes, not the median | **NOT KILLED (0 failing)** |
| **FR1** — the IoU threshold applied as `>` instead of `>=` | **NOT KILLED (0 failing)** |

FR3 is the material one. The synthetic ledger carries **no negative amount**
(`54 words, 16 with money, 0 with NEGATIVE money`), so nothing pins that `-12.00` must
disagree with `12.00`. The money agreement is the statistic 2.5 will use to decide whether
Paddle adds evidence on a bank statement; direction is the thing it must not be blind to. FR4
leaves the published statistic's definition unpinned — every skew fixture is *uniformly*
skewed, where mean and median coincide. FR1 leaves the `align` boundary unpinned (only
`box_iou`'s arithmetic is tested at exactly 0.5). Each needs one fixture.

### MINOR-2 — the pixel scale ignores the frame's own per-axis scales, so a legal frame reads as total reader disagreement with `frame_mismatch` False

`_points_scale` returns one `72/dpi` for both axes and never reads `PageFrame.scale_x` /
`scale_y`, which `evidence/canonical.py` computes per axis and validates only to within
`SCALE_TOLERANCE` (1 %). `display_frame_size` meanwhile compares `pdf_width_pt` /
`pdf_height_pt`, not `width × 72/dpi`, so the two checks cannot catch each other.

```
constructed legal frame: scale_x=4.166667 scale_y=4.127525 dpi/72=4.166667
frames_agree(pdf_point 612x792, this) = True
the same legal frame, words at the page FOOT: y error -7.139 pt
matched: 0 /4  matched_native: 0.0  char: None  amounts: None  frame_mismatch: False
```

A page both readers read perfectly records `agree_matched_native = 0.0` and
`agree_frame_mismatch = 0` — a measurement artefact reading as the two engines disagreeing
about everything. Population **0** with a real rasteriser (rounding ≤ 0.5 px). Fix: scale each
axis by its own `frame.scale_x` / `scale_y`.

### MINOR-3 — `frames_agree` never compares `rotation_deg`

```
SQUARE page rot 0 vs rot 90 frames_agree = True   <- rotation_deg is NOT compared
```
On a square page (and on any 0-vs-180 disagreement) a rotation mix-up between the two readers
is invisible as `frame_mismatch` and surfaces only as a low matched ratio — which the CTRL
calibration will read as reader disagreement rather than a frame problem. One conjunct closes
it; the W3 does not state the limit.

### MINOR-4 — the recorded skew limit is not the limit I measured, and the block case is unstated

The W3 records: *"a page skewed beyond roughly three quarters of a degree over a 500 pt line
produces fragments and the median then mixes them."* On my fixtures (20 rows, 12 pt pitch, 8 pt
words, 500 pt span) the failure past ~0.9° is the ONE grouping rule **over-merging** the page
into a single line, not fragmenting it — `0.75° → 20 lines, 0.75 measured; 0.90° → 1 line, 0.9;
2.00° → 1 line, 2.0` — and the statistic stays exact through it. Separately, the per-page
statistic is a plain median over line slopes, so a page with two differently-skewed blocks
reports an angle no block has (0° and 5° blocks → **2.5**; 2 flat rows against 4 skewed →
**5.0**). That is the limit 2.4 will meet on a real scan and it is not recorded. The measure
itself is sound — 0.6° recovered as 0.6207°, unskewed 0.00°.

### MINOR-5 — the mutation harness's M6 row reports KILLED whenever the agreement suite is green

`tools/agree_mutation_table.py` scores the in-process mutant as
`"KILLED (in-process, tree untouched)" if code == 0 and not named else "NOT KILLED"`. Proven
with the tree clean, by running the harness's own scorer with the killer test deselected —
which is exactly what a renamed, deleted or never-collected killer looks like to it:

```
  control (the killer collected)     pytest exit=0  named killers=[]  -> row says: KILLED (in-process, tree untouched)
  the killer NOT collected           pytest exit=0  named killers=[]  -> row says: KILLED (in-process, tree untouched)
  tree state: (clean)
```

The row is scoring "the agreement suite is green", not "the mutant died". It should assert the
killer was *collected and passed*. (The guard itself is genuinely effective — see attack 7.)

### MINOR-6 — `_project_agreement`'s guard does not cover the two attribute reads

The `try/except Exception` wraps only `agreement_row_columns(document_agreement(...))`, so a
`document` whose `native_evidence` or `evidence` attribute *raises* anything but
`AttributeError` propagates out of `_project_agreement` and out of `_finish`
(`a raising document PROPAGATED: RuntimeError reader exploded`). This contradicts the
docstring's *"a defect here is a FINDING (empty columns) rather than a lost document — a
reporting consumer must never fail a run."* Population 0 today (`StatementMarkdown` carries
plain attributes). Move the two `getattr` calls inside the `try`.

## The attack list, item by item

| # | attack | result |
|---|---|---|
| 1 | frame normalisation | `pixel` at 96 / 150 / 203 / 600 dpi against the same `pdf_point` page: `frames_agree` True, 4/4 matched, char 1.0 at every dpi. Rotated pair: display-vs-display agrees; display-vs-unrotated and unrotated-vs-display both fire `frame_mismatch`. **Broke it twice** (MINOR-2, MINOR-3). |
| 2 | alignment | IoU **exactly** 0.5 matches (`>=`); 0.4999 does not. Ties broken by `(-iou, i, j)` — identical over 200 calls. Duplicate boxes on either side → one pair (never spent twice). Zero words one side → `matched_extractor`/`char`/`density` all `None`; both empty → all `None`. Zero-area, zero-width and nested boxes → the true IoU, never a division. **Not broken.** |
| 3 | statistics | NBSP collapsed by `\s+`; unicode dashes preserved (the normaliser erases nothing). Eight money shapes — `1,234.56`, `-12.00`, `(12.00)`, `$1,234.56`, `1 234,56`, `1.234,56`, `12.00-`, `1,234.56cr` — all resolve through the closed grammar; EN/FR/ES dates resolve to the same `(y,m,d)`. Candidate-table region: ONE money shape forms **no** band; two form one. **Not broken**; the skew limit is mis-recorded (MINOR-4), the sign untested (MINOR-1). |
| 4 | N-1 / N-2 | N-1 attacked with shapes the cell never pinned — a one-sided overhang (left −30, top −50), a CropBox **inside** the MediaBox but offset from the origin, a MediaBox with a **non-zero origin** plus `/Rotate`, and three non-integral page sizes, each at all four angles. The note fires exactly where PyMuPDF's matrix and the rect-derived one disagree and nowhere else, and the ink fraction over the 72-dpi raster is **1.000** every time; the odd sizes give `max|matrix − derived| = 0.000e+00`, so the 1e-6 tolerance is not load-bearing. N-2: indirect 45 / 135 / real 45.0 refused by name; 270 / −90 / 360 resolved and read; a name, a dict and a missing xref answer "no value" and fall back to PyMuPDF as base did; `/Pages`-inherited indirect 45 refused, 90 rotated. **Broke the chain (MAJOR-1).** |
| 5 | the zero-sha-moved claim | Re-derived with my own instrument — see the heavy-proof table. |
| 6 | the projection | Exactly the "both" case fills the columns. `ROW_FIELDS` 77 → 89, the 77-name prefix **identical**, the tail the card's order exactly, no duplicates; `as_dict` covers every field, all twelve default `""`. AST diff of `discovery/runner.py` vs base: `_project_agreement` **added**, `_finish` changed (the one call), **every other function byte-identical** — the analysis call and outcome classifier untouched. **Not broken** except MINOR-6. |
| 7 | never a verdict / never a trigger | The module imports `__future__`, `dataclasses`, `difflib`, `math`, `re`, `evidence`, `layout` and nothing else, and no identifier in it carries `trigger` / `escalat` / `verdict` / `validated` / `refuse` / `route` / `admit`. Only `discovery/report.py`, `discovery/runner.py`, `layout/agreement.py`, `tools/agree*.py` and two tests name a column; nothing under `ocr/` or `analysis/` does. `ocr/escalation.py` blob `bbb847f…` identical at base and tip; the `ocr/`, `analysis/` and `telemetry/` trees byte-identical, as is `layout/signals.py`. Planting `import analysis.pipeline` in my worktree's copy fired **three** boundary tests; tree restored clean. **Not broken.** |
| 8 | ownership | Below. |
| 9 | mutation table | Below. |
| 10 | scans and trailers | Below. |
| 11 | heavy proofs | Below. |

## Ownership (the four disclosed deviations, judged)

`git diff --name-only 26f94f5...1ee8b31` is exactly the card's list plus `discovery/report.py`,
`tools/agree_native_census.py` and `tools/agree_mutation_table.py`. `git diff --numstat` shows
**zero deletions** in every file except `evidence/native.py` (2, the lines the fix replaces).
`tests/test_native_evidence.py` is +232/−0 and no base test function was removed;
`tests/test_two_denominators.py` is +5/−0 (the twelve names and a comment);
`test_no_statement_hardcodes.py` is a roots append plus its own existence guard.
`layout/document_class.py`, `layout/signals.py`, `ocr/**`, `analysis/**`, `telemetry/**` and
`webapp/**` are untouched.

1. **`ROW_FIELDS` in `discovery/report.py`, not the runner** — correct and necessary; the list
   is there and the card mis-attributed it. Nothing else in that file moved. **Accept.**
2. **The row-shape test is cell T's `tests/test_two_denominators.py`** — where the pin lives;
   twelve names appended to the expected tail, nothing else. The composition collision with
   cells E and W on this test, on `ROW_FIELDS` and on `DocumentRow` is expected and is Ocean's;
   every block is a pure append at the end. **Accept.**
3. **Two extra `tools/`** — the N-1/N-2 census (it produces headline numbers, which the standing
   rules require to be a committed instrument) and the mutation harness (the card's own
   sequence). Both joined the OQ2 roots with an existence guard; I confirmed all four new
   modules are actually scanned. Minimal. **Accept.**
4. **A base worktree** at 26f94f5 for the base replay — the 2.2 precedent; I made my own for
   the same reason. **Accept.**

## The mutation table, re-run in MY worktree

The harness mutates CODE (`layout/agreement.py`, `evidence/native.py`, `discovery/runner.py`,
`tools/agreement_census.py`) and never a test; it refuses a dirty tree; the tree was clean after
every row.

**M1–M10: 10 of 10 KILLED**, `unkilled: none`, `tree clean after every mutant: yes` — the cell's
result reproduced exactly, with the same killers named (M1 the threshold pin + the shifted pair;
M2 the one-use test; M3 the identical + real pairs, 16 failing; M4 the case/whitespace synthetic;
M5 the shifted pair's money denominator; M6 the AST guard; M7 the empty-projection test; M8 the
overhanging-CropBox pin, 3 failing; M9 the two indirect pins, 4 failing; M10 the census
output-shape test).

**My seven fresh mutants: 4 killed, 3 not** (`unkilled: FR1, FR3, FR4`; tree clean at the end):

| # | mutant | killer(s) | result |
|---|---|---|---|
| FR1 | IoU threshold applied as `>` not `>=` | (none) | **NOT KILLED** (MINOR-1) |
| FR2 | the pixel scale applied to X only | the shift, rotation, date and frame-mismatch tests | KILLED (16 failing) |
| FR3 | the money comparison drops the SIGN | (none) | **NOT KILLED** (MINOR-1) |
| FR4 | the skew statistic is the MEAN, not the median | (none) | **NOT KILLED** (MINOR-1) |
| FR5 | frame tolerance 1 % → 10 % | `test_the_versions_and_thresholds_are_pinned`, `test_two_frames_describing_one_rectangle_agree_and_a_mismatch_is_recorded` | KILLED (2) |
| FR6 | an unmeasured ratio reads as 0.0 not `None` | the shifted pair, the table-region test | KILLED (2) |
| FR7 | N-2's resolver returns the first hop's xref number | the chain stub test, `test_an_indirect_valid_rotate_is_resolved_and_read` | KILLED (3) — note the stub test kills the *mutant* while missing the *real* defect (MAJOR-1) |

## Heavy proofs (all under `discovery_reports/train13-logs/HARNESS.lock`, `holder.txt` = REV23-AGREE)

Window 1: **acquired 11:47:50Z after a 6,610 s unbounded poll** (P23-EGATE held it throughout),
**released 12:08:19Z, directory confirmed gone**. Window 2: **acquired 13:55:14Z after a further
6,410 s poll** (P23-PRECISION), **released 13:56:20Z, gone**. Window 3 was queued behind P23-WAVE
and retired unacquired. Acquired only with `mkdir`; `holder.txt` naming REV23-AGREE; unbounded
python poll (never a shell sleep); released only while `holder.txt` named me; the directory
confirmed gone both times. I never wrote into, nor removed, another holder's lock. Logs under
`discovery_reports/train13-logs/rev23-agree/` with a `MASTER.log`; every log ends `EXIT=`.

| step | mine | the cell's | EXIT |
|---|---|---|---|
| full default suite | **9,877 passed / 48 skipped / 39 deselected / 0 failed** (529 s) | 9,877 / 48 / 39 / 0 (616 s) | 0 |
| canonical guards (5 files) | **277 passed** | 277 | 0 |
| canonical conformance (7 files) | **1,282 passed / 41 skipped** | 1,282 / 41 | 0 |
| `python corpus_gate.py` | **GREEN — 105 PASS / 3 WITHHELD / 1 REFUSED** (433 s) | GREEN 105/3/1 | 0 |
| mutation table M1–M10 | **10/10 KILLED, unkilled none, tree clean** | 10/10 | 0 |
| my 7 fresh mutants | **4 KILLED / 3 NOT (FR1, FR3, FR4)**, tree clean | — | 0 |
| M6 scoring probe | **row says KILLED with the killer deselected** | — | 0 |
| privacy scan (`--base 26f94f5 --ref 1ee8b31`) | **added_lines 3,031 · hit_count 0 · residue_sites 0 · raw 23, all `words_class` · MONEY/DIGITS/DATES/WORDS 0 · documents_read 3,351 of 3,380** | identical | 0 |
| message scan | **commits_scanned 5 · hit_count 0 · MONEY/DIGITS/DATES/WORDS 0** | 5 / 0 | 0 |
| my own N-1/N-2 structural census over the 3,380 | **3,380 documents, 0 missing, 0 unreadable · 25,528 pages, 12 unreadable · rotated 82 (270°: 63, 90°: 19) · overhanging CropBox 7 · matrix disagreements 0 · indirect `/Rotate` 4, trail length 1, all resolving to 0 · resolved non-multiple-of-90: 0** | 3,380 / 25,516 + 12 · 82 · 7 · 0 · 4 · 0 | 0 |
| evidence-sha re-derivation, my BASE worktree's module vs my TIP worktree's, same bytes | **174 documents · shas MOVED: 0 · `evidence None` 22 at base and 22 at tip** (the sample = all 24 documents carrying every rotated page, overhanging CropBox, indirect `/Rotate` and matrix disagreement, plus 150 random) | 3,380 byte-verified, 0 moved (via monkeypatched suppression) | 0 |
| `EXTRACTION_SCHEMA_VERSION` | **reads 3, pinned by `test_artifact_cache.py:485` and `test_run_of_record.py:1113`, both pass; the whole `ocr/` tree is byte-identical at base and tip** | stays at 3 | 0 |
| union replay chunk 01 at the tip | **NOT RUN BY ME** — queued as window 3, retired unacquired after P23-WAVE held the lock a further ~50 min; I killed my own poller rather than leave a process that could orphan the lock. Per MAJOR-1 the replay reads CACHED text and never calls the native reader, so it cannot cover the one defect I found. | 7 chunks × 2 trees, 2,695 replayed at each, 2,625 of 2,625 preserved payload-identical, 0 regressions, every chunk `EXIT=0` | — |

The census numbers were produced by an instrument I wrote myself (`rev23agree_census.py`) that
derives the display matrix from the page rectangle and resolves indirect references with its
own code, so it does not inherit the module it is checking.

## Two observations for Ocean (not findings against this cell)

* **The census's door holds and I could not get past it.** Against the production run of record
  it refuses by recorded partition; with no `--run` and no `--settings-key` over the production
  cold cache the last-resort scan refuses by count (`0 of the cache's 1 OCR keys carry extractor
  evidence`). Both name the reason.
* **Partition-id naming.** `PHASE2-3-WAVE.md` writes the partitions as `research/paddle-v5-prod`;
  K's partition-id shape — which this census enforces with `fullmatch` — forbids `/`
  (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`), so `--research-partition research/paddle-v5-prod` is
  refused outright. The cell is right to enforce K's shape; cell W and the umbrella card need
  to agree on the literal id before the CTRL run.

## The W3 numbers re-derived versus claimed

| item | claimed | I measured |
|---|---|---|
| identical pair @ 300 dpi | 54/54 each way, char 1.0, money 16/16, dates 8/8, density 0.0, frames agree | **identical** |
| shifted by 2.5 char widths | 19 of 54; money `None`; dates 8/8 | **19/54; money 0 pairs → `None`; dates 8/8** — my own box arithmetic (`w ≥ 3dx`) independently predicts **19** |
| two perturbed amounts | money 14/16, dates 1.0, still 54/54 matched | **14/16, dates 8/8, 54/54** |
| four rotations | 54/54 at each angle | **54/54 at 0/90/180/270** |
| skew 0.6° | within 0.05° | **0.6207°** (unskewed 0.00°) |
| the real native-vs-fake-worker pair | 54/54, char / money / dates 1.0, **min IoU 0.7017** | **54/54, 1.0 / 16/16 / 8/8, min IoU 0.7017**, median 0.7038, max 0.7057 |
| suite delta "+50 are this cell's" | +50 | **exactly +50** (the three touched test files collect 150 at tip, 100 at base) |
| `ROW_FIELDS` append | 12 columns at the end, card order | **77 → 89, prefix identical, tail = `AGREE_COLUMNS`** |
| the reword's tree identity | `053717a` → `913e3f4`, tree `8e2f00b` byte-identical | **both trees `8e2f00b06ac7…`** — verified |
| E4 population 0 on the run of record | no production row carries both readings | **true, and structurally so** — the run of record's `rows.csv` has no `agree_*`/`geom_*` column at all and no production partition holds extractor evidence; the claim is by construction, not by a measurement on that run |

## Scans and secrets

No host, port, IP, token, credential or `.env` value appears in any added line (grep over
`git diff 26f94f5...1ee8b31 -- . ':!docs'` for `http(s)://`, dotted quads, `localhost:`,
`127.0.0.1`, `8765`, `18765`, `api_key`, `token=`, `passw`, `secret`, `vast.ai`, `ssh ` returns
only the identifier `model_token=` and a PyMuPDF version in a comment). D5: no `cost` / `price`
/ `usd` / `billing` / rate literal anywhere in the diff except the comment saying there is none.
Privacy 0 hits / 0 residue over 3,031 added lines; message scan 0 over 5 commits.

## Properties I attacked and could not break

The greedy one-to-one alignment (each box used once, deterministic under ties, `>=` at exactly
the threshold, never a division by zero) · `_ratio`'s refusal to manufacture a measurement
(every unmeasured statistic `None`, projecting `""`, on page and document fold) · the
sum-over-sum document fold, never the mean of per-page ratios · money and date agreement over
MATCHED pairs only, through the closed grammars, never re-implemented · the candidate-table
region's one parameter · **N-1's rect-derived transform**, under six shapes the cell never
pinned, the note firing exactly where the two matrices disagree and every word landing on the
raster's ink · the both-readings rule at the row's single exit, and the column order and
position · the module's import boundary and the AST guard over decision packages · the census's
door (refusals that name the reason) and its output shape (counts, means, nearest-rank
percentiles only).

## My instruments (scratchpad, namespaced `rev23agree_*`)

`rev23agree_a1_frames.py` · `rev23agree_a23_align_stats.py` · `rev23agree_a4_native.py` ·
`rev23agree_a4b_n2.py` · `rev23agree_a4c_chain.py` · `rev23agree_a4d_regress.py` ·
`rev23agree_a67_proj_boundary.py` · `rev23agree_pairtable.py` · `rev23agree_census.py` ·
`rev23agree_fresh_mutants.py` · `rev23agree_m6_check2.py` · `rev23agree_lock.py` ·
`rev23agree_heavy.sh` / `_heavy2.sh` / `_heavy3.sh`.

# Closure re-review — original findings and real agreement census

Review status: **APPROVE** at final cell tip
`f1276b5851e3e1e81b5183a3272380be38b79365`. No remaining actionable finding
against this measurement-only closure. The composed-tree checks remain a
separate train requirement.

The closure reviewer implemented cell E and wrote none of cell X's source or
tests. The independent detached review advanced through `521642d`, `43958ab`,
`9b10d8c` and the fixture-only `cfb4943`. The historical review above remains
unchanged. Its original findings are resolved as follows.

| historical finding | closure and independent check |
|---|---|
| MAJOR-1, indirect Rotate | The reader uses one actual library xref-object read and corroborates right-angle results against the page rotation; it does not interpret an intermediate xref number as an angle. Independently generated raw indirect-reference PDFs cover own and inherited chains, including invalid angles with a readable sibling. The renderer-disagreement limitation below remains explicit. |
| MINOR-1, surviving numerical mutants | Exact inclusive IoU, signed money and unequal-block median have discriminating pins. Independent controls distinguish each former mutant. |
| MINOR-2, per-axis scales | Word boxes, line bands and skew normalize with both declared axis scales; independent anisotropic controls pass. |
| MINOR-3, rotation agreement | Frame agreement now includes rotation, including square-frame and 180-degree disagreement. |
| MINOR-4, skew limits | Documentation records the measured splitting/overmerging behavior and equal-weight block-median limit. No unproved general skew bound is substituted. |
| MINOR-5, M6 scorer | Its named killer must be collected and pass. A renamed/missing killer cannot inherit unrelated green tests; the independent negative and positive controls pass. |
| MINOR-6, projection | The document lookup and both evidence attribute reads are inside the nonfatal guard. Independent probes of the actual committed AST method exercise all three throwing accessors and leave the row untouched. |

## Additional selection defects closed

The first research census fallback selected an unrelated key and emitted empty
reports with exit zero. Those reports are retained as invalid calibration. The
final reader requires an explicitly supplied or recorded Paddle key, refuses an
empty canonical-page population, checks document and native/extractor identity,
and examines every canonical extractor candidate when key discovery is needed.
It does not fall back to the offline key or stop after the first 25 artifacts.

Independent mixed-population reproduction found that treating a conflicting
envelope as merely unreadable could still produce a successful partial census.
At `43958ab`, input/key/stage conflicts raise a value-free whole-census refusal,
even with a valid companion record. Missing or unreadable records retain their
separate availability count. The independent reproduction and closure logs are
both preserved.

The implementer also identified that the index primary key does not enforce a
unique selection tuple. At `9b10d8c`, the reader reuses canonical `select_artifact`
instead of `fetchone`. Two indexed candidates refuse in both insertion orders;
unique and absent controls work, source bytes stay identical, the SQLite
connection is read-only, and the refusal suppresses key/document values and its
original exception context. This is an independently verified synthetic boundary
issue; no actual X corpus ambiguity failure is claimed.

The three `cfb4943` fixture changes clear a stale evidence hash before replacing
runtime, page population or document identity. They let canonical construction
rehash the modified fixture before the census is exercised. The preceding
123-passed/three-fixture-failure attempt is preserved and counts as no mutation
kill. Production source is unchanged by that correction.

## Independent proof scope

Ninety-eight independently specified assertions passed in the clean detached
review: 40 metric/native-reader checks, 40 census checks, four actual-method
projection checks and 14 exact-index-tuple checks. The mixed-envelope refusal
also passed its separate reproduction/closure probe. Durable instruments and
logs are under `discovery_reports/train13-logs/rev23-agree-closure/`:
`metrics-probe-attempt3.log`, `census-probe-final.log`, `projection-probe.log`,
`exact-tuple-probe-attempt2.log`, and the mixed-envelope logs. Initial private
probe failures were fixture/cleanup errors, remain archived, and are not source
failures or mutation kills. These bounded synthetic probes read no customer
cache and repeat no completed native/corpus/cohort proof.

The actual completed implementer logs were inspected directly:

| proof | source scope | observed result |
|---|---|---|
| full default suite | `f969079`, preserved before the later tool/test closure | 9,911 passed, 48 skipped, 39 deselected, exit zero |
| native re-derivation against the actual `d84af95` baseline module | `f969079`, native reader unchanged afterward | 3,380 documents byte-verified, zero changed; 25,516 readable and 12 unreadable pages; exit zero |
| affected tests | `cfb4943` | 126 passed, exit zero |
| affected mutations | `cfb4943` | all 11 selected rows killed by named tests, clean restoration after every row; 28 distinct rows with retained original proofs |
| five canonical guards | `cfb4943` | 277 passed, exit zero |
| recorded-key CTRL and U755 census | `cfb4943` | both exit zero; availability and measurement counts below |

These are `resume-suite.log`, `resume-native-census.log`,
`resume-fix-targeted-after-fixtures.log`, `resume-fix-mutations.log`,
`resume-guards.log` and `resume-fix-census-{CTRL,U755}.log` in the private
`p23agree/closure/` folder. Heavy runs retain the shared committed lock, one OCR
worker, 1.5 GiB start floor and 4 GiB job cap. The preserved full suite is not
claimed to have run at the later reader tip; its unchanged source scope is
composed with the affected checks. The original zero-change production replay,
gate and conformance evidence keep their recorded scope and were not repeated.

## First real agreement measurements

The exact original settings key is bound by archived row evidence identity and
indexed canonical artifact identity, not by date or current environment. The
binder covers all five CTRL sessions and eight U755 sessions: 90 and 341 distinct
recorded Paddle documents respectively, with one exact match each under one
shared recorded key. Each final census rechecks those source rows, mappings and
artifact bytes. Later SLICE provenance remains separate.

| population | selected | both readings | one reading | unavailable | pages compared | native geometry pages | extractor geometry pages | frame mismatches |
|---|---|---|---|---|---|---|---|---|
| CTRL | 114 | 72 | 18 | 24 | 535 | 535 | 668 | 0 |
| U755 | 755 | 281 | 60 | 414 | 2,124 | 2,124 | 2,331 | 0 |

The availability columns sum to each selected population. One-reading and
unavailable documents contribute no paired agreement measurement. Geometry
counts are per available reading, so they need not equal paired counts. Each
individual statistic has its own measured count; empty denominators remain
unmeasured rather than becoming zero. For example, exact money agreement has
463 measured CTRL pages and 1,831 measured U755 pages, while dates have 30 and
239. These are research calibration observations, never truth labels or grounds
for validation.

## Final documentation and privacy verification

The detached review advanced cleanly to `f1276b5`. All 300 W3 appended lines were
read; the prior document blob is a byte-for-byte prefix and no other file changed
from `cfb4943`. A separate log-only verifier matched all 34 published numeric
distribution rows and 28 named mutation rows to their cited durable logs
(`final-tables-review-attempt2.log`, exit zero). Its first path-lookup error is
retained separately; no proof was claimed from that attempt.

Final scans were inspected at the exact documentation tip, over the 3,380-document
population with 3,351 cached-text records read:

| scanner | observed result | actual exit |
|---|---|---|
| added lines | 4,477 lines; 40 raw candidates, all excluded by the existing words-class rule; zero retained hits and zero residue sites | 0 |
| real commit messages | 20 commits; four retained WORDS hits, MONEY/DIGITS/DATES all zero | 1 |

The four message hits are independently attributable to ordinary source-description
prose: three at `77d88bd` in its library-contract/PDF-reference explanation and one
at `43958ab` in its census-selection description. Exact alphabetic values were
checked against the recorded technical prose, excluding author/session metadata;
no token value is reproduced here. The existing handoff §4 item 6 accepts this
attribution without rewording history. The count four and exit one remain explicit;
the message scan is not relabeled zero. This is recorded in
`message-attribution-review.log`, exit zero. The underlying final scanner logs are
`p23agree/closure/resume-final-privacy.log` and `resume-final-messages.log`.

The own-holder release completed at 19:17:52Z, driver 5484 exited, and no X waiter
remained. No final scan was repeated merely to put its result into an earlier
documentation commit.

## Residual limits and verdict

The native archive has zero observed genuine indirect-chain pages, so its
zero-change result cannot establish correctness for every malformed PDF. Genuine
right-angle indirect references can disagree with the renderer's page geometry;
that pre-existing library limitation remains documented and is not hidden by a
cached replay. Skew can split lines or merge nearby blocks, and an equal-weight
median over blocks is not a general deskew guarantee. Two readers can agree on
wrong text. Agreement and geometry remain measurement-only: no route, trigger,
validation or admission policy changes.

**APPROVE.** Original MAJOR/MINOR findings and the additional census-selection
findings are closed with source, discriminating tests, actual mutation kills and
independent probes. The historical review and unsuccessful attempts remain intact.
The measurements support this instrument's stated scope; they do not approve a
new production admission rule or substitute for the train's composed-tree floor.

## Attribution-method clarification: exact word-pair membership

The follow-up source-only attribution check consumes the complete printed
Python-literal subject before reading the exact token. It uses the original
scanner's `tokens_of` function to verify full token membership in each recorded
technical message, excluding author/session metadata. This explicitly covers
two single words and two two-word tokens among X's four retained WORDS hits;
it does not reduce a pair to its final word.

`rev23-agree-closure/final-message-attribution.log` records the value-free result,
exit zero, with exact values and paragraph contexts retained privately in
`message-attribution-private.json`. The attribution remains three hits at
`77d88bd` and one at `43958ab`, all ordinary technical prose under handoff §4
item 6. MONEY/DIGITS/DATES remain zero and the actual message-scan exit remains
one. No scanner or corpus proof was rerun. The APPROVE verdict and its stated
measurement-only scope are unchanged.
