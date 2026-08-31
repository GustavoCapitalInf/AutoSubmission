# PHASE2_OCRAUDIT_REVIEW — adversarial review of `wave10-ocraudit`

**Verdict: CONFIRMED WITH FINDINGS — 1 BLOCK · 5 MAJOR · 5 MINOR.**

Branch `wave10-ocraudit`, base `main` = `c90154a`, tip `9882b06`, three commits, 1,285 insertions /
0 deletions, three owned files. Read-only: nothing under `analysis/`, `ocr/`, `webapp/`,
`discovery/`, `telemetry/` or `tests/` is touched, and I confirmed that by diff rather than by
assertion.

**What CONFIRMED means here.** The governing finding reproduces on all four numbers, on the batch-9
run of record as well as on the run the audit actually cited. The census reproduces exactly (447
modules, 142 reachable). The whole proof floor reproduces, including both privacy scans to the
digit. The unsafe reproductions all land. This is a real audit built on real instruments and it is
worth Gustavo's time.

**What the findings mean.** The one sentence Gustavo is most likely to act on — §5.7's *"all ten
share exactly one exposure … because it is the only place in the OCR path where a value is rewritten
rather than read. That is the whole safety delta, and it is one function"* — is false, and the
remedy the audit recommends for it in Open Question 1 makes the second site worse rather than
better. That is the BLOCK. Five further MAJORs are claims that do not reproduce as written or
components that are missing from a document whose whole purpose is completeness.

---

## 1. Claim-by-claim: claimed vs. measured

### 1.1 The governing finding (claim 1) — REPRODUCED, on both runs

Re-derived independently from the run's own `rows.csv` and from the cold cache's index, with my own
script, not the cell's:

| measurement | audit claims | I measured (run of record, TRAIN9 `91f5179a`) | I measured (TRAIN8 `cda8882d`, the run the audit cites) |
|---|---|---|---|
| `visual_rung = not_attempted` | 3,506 / 3,506 | **3,506 / 3,506** (sole value) | 3,506 / 3,506 |
| distinct OCR settings keys in the cold cache | 1 | **1** | *(same cache)* |
| which key | `ocr_settings_key(force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False)` | **confirmed, and uniquely**: I recomputed all **eight** boolean combinations at default dpi against the index's one distinct key; exactly one matches, and it is that one | *(same cache)* |
| `source_path` split | native 3,297 · local_tesseract 179 · none 30 · visual 0 | **native 3,297 · local_tesseract 179 · none 30 · visual 0** | identical |
| `source_model` split | nine values, `native-pdf-text` 2,871 … | **identical, all nine values** | identical |
| ocr stage / analysis stage | 3,364 / 3,364 / 1 / 0 multi; 2,630 / 2,630 / 1 / 0 multi | **3,364 / 3,364 / 1 / 0** and **2,630 / 2,630 / 1 / 0** | *(same cache)* |
| `cache_visual` | — | **`bypass` on 3,506 / 3,506** (a fifth independent witness the audit did not use) | identical |

The finding is real and it is the right finding. The visual rung has produced nothing.

I also confirmed the frozen baseline reconciles: distinct `content_sha256` = **3,380**, distinct
validated = **2,625** on the run of record (2,697 rows, 124 duplicate + 82 pinned-corpus-duplicate
rows above it). The audit's "2,625 validated documents" is right; the rows it read to get there were
not (see MAJOR-5).

### 1.2 Classification and reachability (claim 2) — REPRODUCED with one scope defect

`python tools/ocr_legacy_census.py --tree` at `9882b06`: **447 first-party modules, 142 reachable
from 8 production entry points** — exact match. Per-component LOC, last-commit date, commit count
and the production/test/tool importer split all reproduce; I spot-checked ten rows against
`git log --follow` and the census's own importer dump and found no drift.

Reachability spot-checks on the rows the brief names:

| row | label | audit's reachability claim | measured |
|---|---|---|---|
| #2 `ocr/config.py` | unsafe | reachable (read by `artifact_cache:589`) | **reach = yes**, 4 prod / 4 test / 0 tool importers, 4 commits, last 2026-07-28 — exact |
| #10 `ocr/ocr_client.py` | unsafe | reachable via the lazy import in the visual rung | **reach = yes**, 485 LOC, 16 commits — exact |
| #29 `tools/cohort_replay.py` | unsafe | — | **NOT IN THE CENSUS INVENTORY** (MINOR-2) |
| #30 `parse.py` | unsafe | a production entry point | **reach = yes**, 5 commits — exact |
| #11 `ocr/availability.py` | reusable | sole caller `discovery/cli.py:31`, never fired | **reach = yes**, 1 prod / 3 test importers — consistent |
| #15 `local_ocr_server.py` | reusable | "census reach = NO", 2 commits, last 2026-07-23 | **reach = NO**, 0 importers, 2 commits, 2026-07-23 — exact |
| #38 `analysis/structurer/geometry.py` | reusable, unwired | `geometry_from_pdf` called only by `tools/measure_structurer.py:117` and tests | **confirmed**: callers are `tools/measure_structurer.py:117` and `tests/test_structurer.py` only; `document_geometry=` appears solely as an internal pass-through at `analysis/pipeline.py:720,1169` — no production caller fills it |

Also reproduced: #31 `sweep_ocr.py` reach = NO / 0 importers / 1 commit 2026-07-24; #33
`coverage_audit.py` reach = NO; #34 `deterministic_coverage_audit.py` reach = NO; #21's generator
`build_corpus_cache.py` reach = NO / 5 commits; #1 `ocr/__init__.py` 26 production / 29 test / 38
tool importers, 1 commit 2026-07-21 — every one exact.

**No mislabelled `active` or `unsafe` found.** The four `unsafe` labels are all defensible and I
would not move any of them. The defect is not in the labels; it is in what is missing (MAJOR-3) and
in the claim that the labelling was uniformly instrument-backed (MINOR-2).

### 1.3 The four unsafe (claim 3) — ALL FOUR REPRODUCED

**(a) F-1 `collapse_repeated_amounts`, `ocr/ocr_client.py:63-82`.** REPRODUCED, and it is worse than
the audit demonstrated. Synthetic input only, at this tree:

* three identical money tokens on three consecutive lines → **one token**. Confirmed.
* the same three inside `<td>` cells → **unchanged**. Confirmed.
* three *distinct* amounts on consecutive lines → **unchanged**. Confirmed.
* **not in the audit:** a bare amount column of `[a, a, a, b, c]` on five consecutive lines — three
  identical fees followed by two unrelated amounts — returns **`[a]`**. `_MONEY_RUN_RE` consumes the
  whole whitespace-separated run and `repl` replaces the *entire match* with the dominant value, so
  every distinct amount that happens to sit adjacent in the same run is **deleted**, not merely
  deduplicated. The audit's "three identical fees become one fee" understates the blast radius: the
  function can delete amounts it never saw repeat.
* the effect survives the full chain: `postprocess()` on the three-line input returns the single
  token.

**(b) F-2 `embed_image_regions`, `ocr/ocr_client.py:344-374`.** REPRODUCED by reading the code path.
`ocr_page` applies `embed_image_regions(raw, image)` at `:479` and `postprocess(raw)` at `:480`, so
the `<img src="data:image/png;base64,…">` is inside the string that becomes `PageText` →
`StatementMarkdown.pages` → the cached artifact and `analysis_input_sha`. The per-region cap is
`len(uri) > 25_000` at `:371`, and `strip_oversized_embedded_images` re-checks the whole tag at
`:377-382`, so the effective ceiling is ~24,960 base64 characters ≈ **18.7 KB of document imagery per
region** — the audit's "~18 KB" is right. The scanner grammar claim is right too: the branch
scanner's classes are `MONEY_RE`, `NUMERIC_DATE_RE`, `SPELLED_DATE_RE`, `WORD_RE` (`[A-Z]{4,}`) and
`HEX_RUN_RE` (`tools/privacy_scan_branch.py:208-289`) — all printed-token matchers, none of which
can see a value rendered as pixels. See MINOR-5 for where the argument is under-built.

**(c) F-9 `tools/cohort_replay.py:119-129`.** REPRODUCED exactly, line for line: `SELECT
artifact_path FROM artifact_cache WHERE stage = ? AND input_sha256 = ?` then `rows[0][0]`. No
`ORDER BY`, no `settings_key` predicate. And the safety-by-population measurement holds: **0 inputs
hold more than one artifact** in either stage of the cold cache. The finding is correct and its
"correct today by accident of the population" framing is exactly right. See MINOR-4 for what it
misses and MAJOR-3 for the fix that already exists in the tree.

**(d) F-4 `ocr/config.py:26-42`.** REPRODUCED. `base_url`, `model` and `api_key` are bare
`os.environ.get` reads with no allowlist (`:27-30`); `ocr/availability.py:5-6` asserts the invariant
nothing enforces. **The three entry points defaulting `allow_visual_ocr=True`, named independently:**
I enumerated every `parse_statement(` call site in the tree and checked each one's flags. There are
**four**, not three — `parse.py:30`, `batch.py:73`, `coverage_audit.py:178` and **`sweep_ocr.py:52`**
(MINOR-3). Every other caller — `corpus_gate.py:1718`, `webapp/artifact_cache.py:204`,
`webapp/worker.py:321`, `discovery/runner.py:402`, `experiments/w3_3a/evaluate.py:66`,
`tools/measure_structurer.py:62`, `tools/desccols_proofs.py:250`, `tools/hygiene8_pinned_replay.py:99`,
`tools/scanhyg_pinned_replay.py:92` — passes `allow_visual_ocr=False` explicitly, and
`discovery/runner.py:458` is the deliberate visual rung. The audit's read of the shape is right; its
count is one short, and the one it dropped is a script that writes full OCR'd statement text to disk.

### 1.4 The architecture (claim 4)

**Trigger counts, re-derived from the run of record:**

| trigger | audit | measured on TRAIN9 `91f5179a` (the run of record) | measured on TRAIN8 `cda8882d` (the run the audit cited) |
|---|---|---|---|
| R — `outcome_reason = deferred_visual_ocr` | 13 | **13** (13 distinct shas; all `source_path = none`, all `outcome_class = deferred`) | 13 |
| U — Tesseract read the dispatch did not claim | ≤ 122 | **123** (123 distinct shas; all `dispatch_outcome = unclaimed`, all `outcome_class = failed`) | 122 |
| R ∪ U | ≤ 135 / 3,506 = 3.8 % | **136 / 3,506, i.e. just under 4 %** (overlap 0) | 135 / 3,506 |

R reproduces. U does not, because the audit measured the wrong run (MAJOR-5). I also derived U two
ways — `outcome_class = failed` and `dispatch_outcome != claimed` — and they agree at 123 on the run
of record, so the audit's definition is sound even though its number is stale.

**The non-escalation property — INDEPENDENTLY CONFIRMED, and stronger than asserted.** The audit
argues from code that no previously validated document can reach either trigger. I measured it
instead: the intersection of the validated sha set with R ∪ U is **0** on the run of record. The
property is true by construction *and* true by measurement.

**"A validator verdict is NOT a trigger anywhere" — CONFIRMED.** `_needs_visual_upgrade`
(`discovery/runner.py:521-541`) tests exactly three things: `source_path_for(model) ==
"local_tesseract"`, `collector.dispatch.outcome != "claimed"` when a dispatch was seen, and
`payload is None` otherwise. No reconciliation result, no ADB state, no integrity flag, no coverage
ratio is consulted anywhere on the escalation path.

**`discovery/runner.py:438-670` — every property verified by reading it:**

| property | verified |
|---|---|
| recovery | yes — `:606`, gated on `markdown is None`, only in a mode that enables the rung |
| upgrade | yes — `_needs_visual_upgrade` at `:521-541`, narrow in the three ways its docstring claims |
| disjoint cache partition | yes — `_read_visual` calls `parse_statement(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True)` at `:458-465`; three of the settings key's fields differ from the offline call at `:402-409`, so the partition is disjoint by key construction, not by convention |
| the SAME validator | yes — both paths reach `self._analyse` → `analyze_markdown(..., parse_mode="deterministic", sheets=sheets)`; there is no second analysis entry point on the branch |
| fail-closed on endpoint death | yes — `:620-621`, `visual_rung = failed`, `outcome_class/outcome_reason = failed / ocr_failed`, `source_path = none`; the document becomes terminal rather than silently deferring |
| adoption test | yes — `if visual_payload is not None` at `:655-660`; the visual read is adopted only when the deterministic validator produced a payload |

**F-7 provenance fallthrough — CONFIRMED.** `telemetry/record.py:119-133`: after `native-pdf-text*`,
`local-tesseract-ocr` and `deterministic-native-preflight`, the final statement is literally
`return "visual"`. Any unrecognised model string is reported as the GPU path. `SOURCE_PATHS` at `:66`
is the closed four-member tuple the audit describes.

**Confidence plumbing — the substance holds, the number does not.** See MAJOR-4.

**Cost bound ≤135 / 3,506 = 3.8 %** — becomes **≤136 / 3,506, just under 4 %**, on the run of record.

### 1.5 Check-by-check (claim 5)

The structural spine of §5.7 is sound: the extractors produce a `StatementMarkdown`, the validator's
entry point takes a markdown string and a page list, and the failure direction of a degraded read is
safe on reconciliation, ledger identity, coverage, period, currency and ADB. The **page-completeness
"strictly stronger" argument is correct** — the OCR rung rasterizes every page
(`ocr/pipeline.py:131` → `ocr/rasterize.py:12`), so `len(pages)` is the PDF's true page count rather
than whatever MuPDF produced, and `corpus_gate.py:725-772` polices that production callers supply
`sheets`.

Two protections are reachable by an extractor in ways the audit denies. Both are reproduced below as
BLOCK-1 and MAJOR-2.

### 1.6 Proof floor (claim 6) — FULLY REPRODUCED

| floor item | claimed | I ran it |
|---|---|---|
| canonical guards (7 files) | GREEN, exit 0 | **316 passed, 10 deselected**, exit 0 — exact |
| `tools/privacy_scan_branch.py --data-dir <cold> --base main --ref HEAD --rows <run>/rows.csv` | hit_count 0; raw 26, all `words_class`; population 3,380; documents_read 3,351 | **hit_count 0**, `hits_by_class` MONEY 0 · DIGITS 0 · DATES 0 · WORDS 0, **raw_hit_count 26**, `excluded_by_rule.words_class 26` and every other rule 0, population 3,380, documents_read 3,351, added_lines 1,285, exit 0 — **exact to the digit** |
| `tools/huntington_msg_privacy_scan.py --data-dir <cold> --base main --rows <run>/rows.csv` | hit_count 0 across four classes, 3 commits, exit 0 | **hit_count 0**, all four classes 0, commits_scanned 3, exit 0 — exact |
| W3 append-only | byte-verified | **verified**: the tip's W3 blob starts with the base blob byte-for-byte; 3,929,005 → 3,946,869 bytes, 17,864 appended |
| headings 103 → 104 | | **verified**: `# §` sections 103 → 104 (h1 total 406 → 407) |
| heading on the first appended line | | **verified**: the first appended byte begins `# §OCRAUDIT — the legacy OCR audit …` |
| message reword, trees byte-identical | "an empty `git diff` between the pre- and post-reword tips" | **verified from the reflog**: pre-reword tip `47981ae` and post-reword `d8ac8a8` have the *same tree object* (`42a53a3`), and `git diff` between them is empty. The two later amends (`d8ac8a8` → `b3948f7` → `9882b06`) do change the tree, but only `W3_TRACKA_LOG.md`, and only to replace two one-line floor entries with the fuller proof-floor record now in the section — I read that diff in full; it contains no document content |

I ran both scans against the **batch-9** run of record rather than the batch-8 rows the cell used;
the population (3,380) and documents_read (3,351) are identical either way, so the floor is
unaffected by MAJOR-5.

The scans' `no_cached_text` list (29 shas with no cached text in the cold cache) is unremarked in the
W3. It is not a defect — those documents have no cached artifact to scan — but a floor that reports
"3,351 read of 3,380" should say what the other 29 are, because a silent shortfall and a scanner
that cannot reach a document look identical in the JSON.

### 1.7 Completeness (claim 7) — two independent components, one absent entirely

I built my own inventory rather than reading the audit's: every non-test first-party module matching
`from ocr\.|import ocr|ocr_client|rasterize|tesseract|OCR_STAGE_VERSION|cached_ocr|ocr_settings_key`,
then checked each against the 45 rows.

**Component A — `telemetry/stated_counts.py::CachedArtifacts` (~`:820-940`). NOT IN THE TABLE — zero
mentions anywhere in the audit.** This is MAJOR-3 and it is the most consequential omission.

**Component B — `webapp/app.py`. Not a classified row.** It appears only inside the evidence cells of
#9 and #14 and is not in the census inventory, yet it is one of the eight declared production entry
points, it imports `ocr.inspect`, `ocr.rasterize` and `ocr.render` at `:17-19`, and at `:1996`
(`dpi=200`) and `:2234` (`dpi=100`) it **rasterizes archive document pages and serves the images over
HTTP**. It is the largest document-pixel egress surface in the OCR path — F-2's mirror image, pixels
*out* rather than pixels *in* — and it is the surface through which `render_boxed` re-enters
`ocr_client.postprocess` (`ocr/render.py:179,192`), so F-1's rewrite reaches what an operator reads on
screen. The audit notes that last point under #14 but never classifies the module that does it.
Severity MAJOR by the brief's rule; I am folding it into MAJOR-3 rather than counting it twice,
because the remedy is the same: the inventory needs a completeness pass, not a patch.

---

## 2. Findings

### BLOCK-1 — F-1 is not the only value rewrite, and the audit's recommended fix moves the collapse *into* the second one

`ocr/ocr_client.py:129-171`, `fix_amount_column_bleed`, with `_AMOUNT_BLEED_RE` at `:126` =
`^(.+?)\s+(-?\$?[\d,]+\.\d{2})$`. The "prefix" group is `(.+?)` — **anything, a money token
included**. Reproduced on synthetic input at this tree:

```
in : <td>Date</td><td>Description</td><td>Amount</td> | <td>01/02</td><td>ACH DEBIT</td><td>1,000.00 234.56</td>
out: <td>Date</td><td>Description</td><td>Amount</td> | <td>01/02</td><td>ACH DEBIT 1,000.00</td><td>234.56</td>
```

An Amount cell the model rendered as two fused money values — the exact fusion class the three
sibling repair functions exist to handle — has its **leading amount moved into the description and
its trailing amount promoted to the transaction's amount**. The parser that reads that table now
reads `234.56` where the page said `1,000.00`. By the audit's own standard ("an extractor that
rewrites a source value to a different value is not a repair, it is the thing the repair doctrine
forbids arriving one layer upstream of the parser"), this is the same class of defect as F-1, and it
reaches reconciliation, ledger identity, transaction coverage and ADB by exactly the same route.

Three consequences:

1. **§5.7's summary is false.** *"All ten share exactly one exposure … because it is the only place
   in the OCR path where a value is rewritten rather than read. That is the whole safety delta, and
   it is one function."* There are at least two functions, and the safety delta is not one function.
   The same sentence appears in W3 §OCRAUDIT and must be corrected in both.
2. **Open Question 1's recommendation is unsafe as written.** The audit recommends option (b) —
   restrict `collapse_repeated_amounts` to run "only *inside* `<td>` cells, where the docstring's
   safety argument is actually true". `fix_amount_column_bleed` operates **only** inside `<td>`
   cells. Table cells are not a safe harbour; they are where the other rewrite already lives.
   Gustavo cannot be asked to rule on option (b) on the current text.
3. **The cleanup chain needs a rewrite census, not a spot fix.** `postprocess` (`:409-416`) is six
   functions deep and at least two of them write values. `split_fused_header_row` (`:174`) and
   `repair_fused_amount_table` (`:273`) restructure rows and re-emit cells; I could not construct a
   value-losing input for `repair_fused_amount_table` (its `_FUSED_HEADER_CELL_RE` guard at `:269` is
   tight), but its per-row loop collapses every `len(cells) >= 3` row whose last cell is money into
   three columns by joining `cells[1:-1]` into the description — a shape that on a
   debit/credit/balance table would fold two money columns into the description. That is unproven and
   I do not claim it; it is exactly what a per-function rewrite census must settle.

**Required before Gustavo reads the audit:** correct §5.7's summary and F-1's "single change"
framing, add `fix_amount_column_bleed` as a finding in its own right, and re-pose Open Question 1
with the `<td>` option's premise removed.

### MAJOR-1 — the audit measured the batch-8 run and presents it as the frozen batch-9 baseline

The audit's §1 evidence column and §7 both cite `discovery_reports/TRAIN8-7185633/
2026-08-28T224640.553059-0000-cda8882d`. The frozen deterministic-v1 / multi-account-v1 baseline the
audit says it is auditing (`819d97d`, tag `batch9-final`, 2,625/3,380) was measured as
`discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a`. The document names the
batch-9 baseline in its header and reads the batch-8 rows.

Almost everything survives — I measured both runs and the entire intake-provenance surface is
byte-for-byte identical (`visual_rung`, `source_path`, `source_model`, `cache_visual`, 3,506 rows,
3,380 distinct shas), because nothing in batch 9 touched the intake ladder. Three numbers do not:

| | audit (batch-8 rows) | run of record (batch-9) |
|---|---|---|
| U trigger | ≤ 122 | **123** |
| cost bound | ≤ 135 / 3,506 = 3.8 % | **≤ 136 / 3,506, just under 4 %** |
| #8's Tesseract outcome split | 36 validated / 16 withheld / 5 review / 122 failed | **36 / 15 / 5 / 123** |

The correction is small; the provenance error is not, because §5.4 turns the bound into a proposed
runtime refusal ("the runner should refuse to escalate more documents than the triggers named"). A
runner built to a stale trigger population refuses the 123rd document.

### MAJOR-2 — the seam is not two values: the extractor's model string reaches the admissible analysis text, and it is environment-controlled

§2.3 #23 states: *"The seam is exactly **two values** … There is no third channel and no per-field
provenance."* §5.7 builds its whole structural argument on that. It is not accurate.

`StatementMarkdown.to_markdown()` (`ocr/document.py:33-49`) emits, as the first line of the analysis
input:

```
<!-- source: {source_file} | pages: {n} | model: {self.model} | empty: {k} -->
```

The extractor writes `model` — so the extractor writes a string into the document the validator
reads. What actually closes the channel is a guard the audit never names: `admissible_text`
(`analysis/parser_registry.py:197-215`) strips that comment via `SOURCE_COMMENT_RE` (`:194`), applied
centrally at `analyze_markdown`'s single parse seam since W3 FILENAME-BOUNDARY, and pinned by
`tests/test_filename_boundary.py`. The safety argument is *true*, but for a reason §5.7 does not
give, and the reason is escapable:

* `SOURCE_COMMENT_RE` is `^<!--\s*SOURCE:.*?-->\s*$` with `MULTILINE` and **without** `DOTALL`. A
  model string containing `-->` does **not** escape (I tested it; backtracking consumes to the last
  `-->` on the line). A model string containing a **newline** does.
* Reproduced end-to-end at this tree: with `OCR_MODEL` set to a two-line value, the second line —
  including an injected money token — appears in `admissible_text(document.to_markdown())`. Both the
  marker text and the money token reach the text every parser's detection markers scan and every text
  metric runs over.
* `ocr/pipeline.py:149` stamps `model=settings.model` onto the visual rung's `StatementMarkdown`, and
  `settings.model` is `os.environ.get("OCR_MODEL", …)` (`ocr/config.py:29`) — the same unvalidated env
  read F-4 already flags.

This upgrades F-4 from an *egress* finding to a **content-injection** finding: `OCR_MODEL` is not
only "which host gets the pixels", it is "arbitrary text in the analysis input of every document the
visual rung reads". Unreachable today (zero visual reads) and reachable the day Phase 2 enables the
rung — and §5.5 item 2 proposes *new* extractor-authored model-string conventions
(`unlimited-ocr+…`, `paddle+…`) that go straight into that header.

**The architecture proposal must add:** the seam is three values (`markdown`, `sheets`, `model`), the
third is neutralised by `admissible_text` and not by the seam's shape, and any new extractor's model
token must be validated against a closed character class in the same commit that adds it.

### MAJOR-3 — an OCR-artifact-cache reader is missing from the 45, and it already implements F-9's fix

`telemetry/stated_counts.py::CachedArtifacts` (~`:820-940`) has **zero mentions** in the audit. It:

* opens the same `webapp.db` `artifact_cache` index, `mode=ro`, and reads the same `ocr` and
  `analysis` stages `tools/cohort_replay.py` reads (with a documented reason for not using
  `webapp.storage.Storage`: `_ensure_schema` writes, and "an observer that can write to the thing it
  observes is not an observer");
* indexes `input_sha → {settings_key: path}` and **selects deterministically from a declared, ordered
  `_ocr_keys` list** — which is precisely the "settings-key argument and a total order" that §5.6
  calls the single blocking prerequisite and treats as new work. **The fix is already written in this
  tree, by an earlier wave, twenty lines long.**
* filters the analysis stage by `settings_key == self._analysis_key` — the predicate `_payload` lacks;
* and its `_ocr_keys` list **already enumerates the visual partition**
  `(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True)` as its third entry. In-tree code
  already anticipates the multi-partition world the audit says does not exist yet.

That last point carries a policy consequence the audit cannot flag because it does not know the module
exists: `_ocr_keys` puts the two offline partitions **first** and the visual partition **last**. The
day a document holds both, this observer silently keeps reading the offline read. That is a defensible
default and it is also an unratified ranking of extractors, sitting in an unclassified module, that
Phase 2 would inherit by omission.

`webapp/app.py` is the second missing component (§1.7 above). Both belong in the table with labels and
evidence, and the reuse plan needs a line naming `CachedArtifacts` as the prior art for F-9.

### MAJOR-4 — §2.7's headline number is false as written, and it misses a user-facing "OCR confidence"

The audit claims: *"A case-insensitive search for `confidence` / `conf_score` / `ocr_score` across
`ocr/`, `webapp/`, `telemetry/`, `analysis/schema.py`, `analysis/pipeline.py` and
`analysis/serialization.py` returns **0 hits**."*

Run over exactly those paths, it returns **14 hits**, all under `webapp/`. Restricted to `*.py` it
returns 0 — the audit's search was silently Python-only, and the paper says "across `webapp/`".

The substance survives: no extractor emits a score, no record carries one, the validator has no
parameter that reads one. But what the search missed is directly on the card's list ("evidence /
confidence plumbing") and is not cosmetic:

* `webapp/static/app.js:594-601` `confidenceFrom(report)` returns a **hard-coded 98 / 94 / 80 / 72**
  from the validator's own `quality` verdict, and `:1146,1159` render it to the operator as
  `"OCR confidence"` and a percentage in the completion banner and the results table
  (`webapp/templates/index.html:1010` is the banner slot).
* It is not an OCR measurement at all — it is a re-encoding of a deterministic verdict under an OCR
  label, and there is a second one, `packageConfidence` (`:604-609`), for packages.

For Phase 2 this matters more than it does today: the moment a second extractor exists, an operator
reading "OCR confidence 94%" beside an OCR-fed document will reasonably believe the number describes
the OCR read. It describes the validator. §2.7's conclusion ("an extractor literally has no channel
through which to argue for its own output") is right about the Python; the UI already shows a number
that looks exactly like the channel the doctrine forbids. Fix the claim, and add the surface to the
open questions: rename it, or derive it from something real, before an extractor lands behind it.

### MAJOR-5 — #45's "zero hits" is false, and there IS PaddleOCR prior art in the tree

The audit's only row about the net-new extractor says: *"`grep -riE "paddle\|easyocr\|textract\|donut\|
trocr\|surya"` over the tree returns **zero** hits. PaddleOCR is entirely net-new; there is no legacy
to reuse and no adapter interface to fit it into."*

That grep returns **ten files**. Two are substantive prior art:

* `docs/superpowers/specs/2026-07-21-paddleocr-bank-statement-parser-design.md` — 192 lines, dated
  2026-07-21, **"Status: Approved (pending written-spec review)"**: a full design for a PaddleOCR
  bank-statement parser. PP-OCR text + bounding boxes with **custom bbox-based row/column
  reconstruction**, per-bank profiles with a generic fallback, `python parse.py <statement.pdf>` as
  the interface, structured JSON out.
* `docs/superpowers/specs/2026-07-22-nanonets-vlm-bank-statement-parser-design.md` — 184 lines, a
  second pre-deterministic extractor design.

The audit's *code* claim is right — there is no PaddleOCR code. Its stated claim is wrong, and the
gap is material in three ways: the bbox row/column reconstruction that spec designs is exactly the
OCR word-box geometry §5.5 item 3 wants for `document_geometry` (#38); the spec's front door is
`parse.py`, the audit's `unsafe` #30; and an "Approved" design document for the extractor Phase 2 is
about to build has to be superseded on the record, not discovered later. §0 says the legacy "was
found by content instead" of by filename — `docs/superpowers/specs/` was not searched by content
either, and the audit's own grep would have found it.

---

## 3. Minor findings

**MINOR-1 — the census tool's read-only argument contains a false statement.**
`tools/ocr_legacy_census.py:12-14`: *"It has no `open(..., "w")`, no `Path.write_*`, no `os.replace`,
no `shutil`, no `subprocess`, no network client."* The module imports `subprocess` at `:72` and calls
`subprocess.run` at `:250` (`git log --follow`, `git rev-parse`). The substance is unaffected — those
are read-only git invocations and I verified there is no write path anywhere in the module — but the
audit's §0 cites that docstring as the authority for the tool's read-only-ness ("its docstring's
`READ-ONLY BY CONSTRUCTION` section states how"), so the one sentence carrying the guarantee is
inaccurate. W3 §OCRAUDIT states it correctly ("no `subprocess` write path"); the tool should say what
the W3 says.

**MINOR-2 — "every component's reachability was computed" overstates the instrument's coverage.**
§2.6 attributes the empty `unknown` bucket to a computed transitive walk over all 45 rows. The
census's `COMPONENTS` tuple holds **27 paths**, two of the 45 rows are not code (#16 the README
surface, #22 the cache directory), and roughly 16 rows never went through the instrument at all —
including `telemetry/prices.py` (#17), `telemetry/record.py` (#27, #28), **`tools/cohort_replay.py`
(#29, an `unsafe` row and one of the audit's own five most consequential)**, `analyze.py` (#36), the
three forensic oracles (#37), `experiments/w3_3a/evaluate.py` (#39) and the five test/fixture rows
(#40–#44). The labels are still defensible; the claim that they were uniformly instrument-backed is
not. Either extend `COMPONENTS` to the full inventory (cheap — it is a tuple) or say which rows were
resolved by reading.

**MINOR-3 — F-4 names three default-`allow_visual_ocr=True` entry points; there are four.**
`sweep_ocr.py:52` is the fourth. The audit's own #31 describes it writing full OCR'd statement text
to `output/`, so the omission is an enumeration slip rather than a miss — but F-4 excludes it while
including `coverage_audit.py:178`, which is `obsolete` and `reach = NO` on the same terms.

**MINOR-4 — F-9's exposure is larger than the OCR stage.** `ColdCache._payload` is called for both
stages: `text()` → `_payload("ocr", …)` and `baseline_payload()` → `_payload("analysis", …)`. F-9,
§2.3 #29 and §5.6 discuss only the OCR partition. The **analysis** settings key includes the parser
registry fingerprint (`webapp/artifact_cache.analysis_settings_key`), which changes at essentially
every wave — so a data directory reused across two registry versions holds two analysis partitions per
input long before it holds two OCR partitions. Measured 0 today (2,630 / 2,630 / 1 key), but the
hazard is nearer on the analysis stage than on the one the finding is written about, and
`CachedArtifacts` already filters it (MAJOR-3).

**MINOR-5 — F-2's scanner argument needs its concrete case.** "The scanners cannot see base64" is
right about the grammar, but the branch scanner reads *diffs*, and OCR artifacts are never committed —
so as written the claim is about a scanner that would never have looked. The concrete case that makes
F-2 bite is the **committed** OCR fixtures (`tests/corpus_cache/ocr/<SHA>.md`, the audit's own #43):
an Unlimited-OCR read committed there would carry inlined document imagery into the repository, and
`tools/privacy_scan_branch.py:467` excludes everything under `tests/corpus_cache/` wholesale via the
`corpus_cache` rule. That is the shape worth stating: a committed fixture, invisible content, and an
exclusion that already blankets the directory.

---

## 4. What the architecture proposal must add before Gustavo reads it

1. **Correct the safety delta.** It is not one function. Add `fix_amount_column_bleed` as a finding,
   re-pose Open Question 1 without the `<td>`-cells premise, and commit to a per-function rewrite
   census of `postprocess`'s six-function chain (`ocr/ocr_client.py:409-416`) as a Phase-2 deliverable.
   Until that census exists, no OCR-fed document should be validated — which is the audit's own
   position, correctly reached, on an incomplete inventory of the reason.
2. **Re-measure the triggers on the batch-9 run of record** and restate U as 123 and the bound as
   ≤136 / 3,506 (just under 4 %), with the run path corrected throughout §1 and §7.
3. **Restate the seam as three values.** Name `admissible_text` / `SOURCE_COMMENT_RE` /
   `tests/test_filename_boundary.py` as the guard that closes the model channel, and require a closed
   character class on any new extractor's model token in the commit that adds it. Fold the injection
   route into F-4, which is currently an egress-only finding.
4. **Classify `telemetry/stated_counts.py::CachedArtifacts` and `webapp/app.py`**, and rewrite F-9's
   remedy as "adopt the ordered-key selection `CachedArtifacts` already implements" rather than as
   new design. Ask Gustavo to ratify `_ocr_keys`'s ordering explicitly, since it is a silent policy
   about which extractor's read an observer prefers.
5. **Fix §2.7's number and add the UI surface.** Say "0 hits in Python across those paths", and add a
   ninth open question: the webapp shows a fabricated `"OCR confidence"` percentage derived from the
   validator's verdict; rename it or derive it, before an extractor lands behind the label.
6. **Reconcile the PaddleOCR spec.** #45 must cite
   `docs/superpowers/specs/2026-07-21-paddleocr-bank-statement-parser-design.md`, say whether Phase 2
   supersedes or inherits it, and note that its bbox row/column reconstruction is the natural filling
   for `document_geometry` (#38) — which turns §5.5 item 3 from "later" into "there is already a
   design for this".
7. **Extend the census inventory** to the rows it does not currently cover, or state which labels were
   resolved by reading rather than by the instrument (MINOR-2), and fix the tool's own `subprocess`
   sentence (MINOR-1).

---

## 5. What I did not find

* No mislabelled `active` or `unsafe` row. I tried to move all four `unsafe` labels and could not.
* No fabricated number in the proof floor. Every floor figure reproduces, two of them to the digit.
* No document content, archive filename or content sha in the branch's added lines or its three
  commit messages — I scanned all 1,285 added lines and ran both scanners myself.
* No write path in `tools/ocr_legacy_census.py`, and no analysis entry point called by it. Its
  exclusion from `corpus_gate.EXCLUDED_ANALYSIS_CALLERS` is correctly argued.
* No evidence that the audit read an archive document. The cache work is index-only and I confirmed
  the queries.

---

## 6. Reproduction

```
python <scratch>/measure_rows.py <TRAIN9 run>/rows.csv <TRAIN8 run>/rows.csv
python tools/ocr_legacy_census.py --tree
python tools/ocr_legacy_census.py --cache-index .claude/recovery/webapp_data_train8_cold
python -m pytest -q tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py \
    tests/test_r1_hardcodes.py tests/test_experiments_are_not_wired.py \
    tests/test_filename_boundary.py tests/test_corpus_gate_outcomes.py tests/test_currency_source.py
python tools/privacy_scan_branch.py --data-dir .claude/recovery/webapp_data_train8_cold \
    --base main --ref HEAD --rows <TRAIN9 run>/rows.csv
python tools/huntington_msg_privacy_scan.py --data-dir .claude/recovery/webapp_data_train8_cold \
    --base main --rows <TRAIN9 run>/rows.csv
```

The settings-key identification, the F-1 five-token collapse, the BLOCK-1 amount-bleed rewrite and
the MAJOR-2 model-string injection were each reproduced with a few lines of synthetic input against
the tree's own functions; no document was opened at any point in this review.

---

## Re-review (closure 9b7efb6)

**Verdict: CONFIRMED — READY FOR GUSTAVO.** One MINOR recorded below; it does not stop the ruling.

Bounded to the eleven closures. Closure tip `9b7efb6`, nine commits over my `15e9535`, scope held to
the audit's three files — I confirmed by diff that nothing outside `OCR_LEGACY_AUDIT.md`,
`W3_TRACKA_LOG.md` and `tools/ocr_legacy_census.py` moved, and that my review file is
**byte-identical** at `HEAD` (`git diff 15e9535 HEAD -- <review>` is empty).

### Integrity of the history rewrite — VERIFIED

Two `git filter-branch --msg-filter` passes ran over `15e9535..HEAD`. I compared the **tree objects**
commit-by-commit across all three generations (`a3f747b` → `206f2af` → `754e39c`, the pre-rewrite tip
and both rewrites; `refs/original` is still present):

* all eight commits appear in all three generations, **in the same order, carrying the same eight
  tree object ids in the same positions** — the rewrite touched messages and nothing else;
* `15e9535` is the rewrite's base, lies outside the range, and **still carries its original sha**;
* every sha after it moved, as the coordinator said.

The reword count is recorded honestly in W3 (four in total: two in the original round by amend, two
by `--msg-filter`), and that matches the reflog exactly.

### Per-finding verdicts

| finding | verdict | what I checked |
|---|---|---|
| **BLOCK-1** | **CLOSED** | §5.7 now carries a two-row PROVEN table (F-1 outside cells / F-11 inside cells) with the complementary-scope argument stated as the reason cells are not a safe harbour; two further chain members are declared **explicitly unproven**, with "neither claims one exists"; the per-function census is an owed Phase-2 deliverable and the whole chain is to be treated as value-writing until it lands. F-11 is a finding in its own right with the review credited, and its fused-cell reproduction is the one I ran. F-1 carries the `[a,a,a,b,c]` → `[a]` strengthening with "deleted, not deduplicated". OQ1 adjudicated separately below. |
| **MAJOR-1** | **CLOSED** | Every table now names its run. Spot-checked against the batch-9 run of record myself: **U = 123** by both derivations independently (`local_tesseract` and `dispatch_outcome != claimed`; `local_tesseract` and `outcome_class = failed`) — they agree exactly; **R = 13**; **R ∪ U = 136 with overlap 0**; **validated ∩ (R ∪ U) = 0**; #8's Tesseract split now reads **36 validated / 15 withheld / 5 review / 123 failed**, with the batch-8 split (36 / 16 / 5 / 122) kept beside it. The bound is stated as a fraction of 3,506 rather than as a decimal percentage, which also keeps it out of the MONEY grammar. |
| **MAJOR-2** | **CLOSED** | The seam is restated as three values and the "no third channel" claim is explicitly retracted; the guard is named (`admissible_text` / `SOURCE_COMMENT_RE`, `analysis/parser_registry.py:194,197-215`, pinned by `tests/test_filename_boundary.py`); the newline escape is recorded as F-4(b) **together with the `-->` non-escape** and the `MULTILINE`-not-`DOTALL` reason, which is the honest pair; the closed-character-class requirement is stated as owed in the commit that introduces any new extractor's model token. The distinction that mattered — a guard can be escaped where a missing channel cannot — is made in the text. |
| **MAJOR-3** | **CLOSED** | Rows **#46** (`telemetry/stated_counts.py::CachedArtifacts`) and **#47** (`webapp/app.py`) added. Census figures verified by re-running `--tree`: #46 **1,049 LOC, 15 commits, last 2026-08-30, 0 production importers, reach = NO** — exact; #47 **2,304 LOC, 36 commits, last 2026-08-30, reach = yes** — exact. F-9's remedy is reframed as **adoption** of #46's ordered selection rather than new design, and OQ8 says so. The visual-last ordering is correctly raised rather than settled — **Risk 7 + OQ10** — which is the right disposition for a policy that was never ratified. |
| **MAJOR-4** | **CLOSED** | §2.7 now reads "**0 hits in `*.py`** and **14 hits overall**", with the earlier draft's silent language-scoping confessed. The fabricated `"OCR confidence"` is described accurately (hard-coded 98 / 94 / 80 / 72 selected from the validator's `quality` verdict, rendered at `:1139` and `:1159`, with `packageConfidence` named as the second one) and carried as **Risk 8 + OQ9**. The architectural conclusion is retained and is still correct. |
| **MAJOR-5** | **CLOSED** | Row #45 corrected to **"obsolete (as a design), absent (as code)"** — a label that says exactly the right two things. Both specs are cited with line counts and the PaddleOCR one's "Approved" status; the three consequences are drawn (its bbox reconstruction is the `document_geometry` filling; its front door is `unsafe` #30; an Approved design must be superseded on the record). Folded into the reuse plan and §5.5, carried as **Risk 9 + OQ11**. The §0 search-scope confession ("my own §0 grep excluded `docs/`") is recorded — that is the right sentence to have written. |
| **MINOR-1** | **CLOSED** | The census docstring now states that it **does** import and call `subprocess`, names the two read-only git commands, states there is no subprocess write path, and flags that the earlier "no `subprocess`" wording was false and was the one sentence the audit cited as its authority. |
| **MINOR-2** | **CLOSED** | The overstatement is retracted with the real figure (27 paths against 45 rows; roughly sixteen labels resolved by reading, `tools/cohort_replay.py` named as one of them). `COMPONENTS` is extended to **every row that is a Python module (44 of 47)**, and the four non-module rows are declared in the tool as `NON_CODE_ROWS` and **printed by `--tree`** — I ran it and saw #16, #22, #43 and #45 emitted with their reasons. The coverage claim is now checkable rather than assumed. |
| **MINOR-3** | **CLOSED** | `sweep_ocr.py:52` named in F-4 as the fourth default-flag caller, with the observation that it is also the script that writes OCR'd statement text to disk. |
| **MINOR-4** | **CLOSED** | Folded into F-9 and into #29's evidence cell — the analysis stage is named as reaching the hazard *sooner* than the OCR stage, which is the point. |
| **MINOR-5** | **CLOSED** | F-2 now carries the concrete case: a committed OCR fixture would carry inlined imagery into the repository, and `tools/privacy_scan_branch.py:467` (`_corpus_cache`) excludes everything under `tests/corpus_cache/` wholesale. The 29 `no_cached_text` shas are recorded as the scan population shortfall. |

### Totals — reconciled against my own count

I parsed the table rather than reading its summary: **47 component rows, numbered 1–47, no gaps and
no duplicates**. Label counts from the parsed rows: **active 27 · reusable 10** (nine plain, plus
#25's "reusable — the Phase-2 architecture, already written") **· obsolete 4 · duplicate 1 · unsafe 4
· unknown 0 · PaddleOCR 1** = 47. Matches the audit's stated totals exactly.

### Floor — reproduced

| item | claimed | measured |
|---|---|---|
| canonical guards | 316 | **316 passed, 10 deselected**, exit 0 |
| branch privacy scan | 0, raw 48 all `words_class` | **hit_count 0**, all four classes 0, **raw 48**, `words_class` 48 with every other rule 0, added_lines 2,260, population 3,380, read 3,351, exit 0 |
| commit-message scan | 0 over 13 commits | **hit_count 0** across all four classes, **13 commits**, exit 0 (`git rev-list --count main..HEAD` = 13) |
| W3 append-only | byte-verified, 104 sections | **verified against the base**: the tip's W3 blob starts with `c90154a`'s byte-for-byte, so every section predating this branch is intact; `# §` sections **103 → 104** |

A precision worth stating, because it is the sort of thing that reads as a discrepancy later: the W3
is append-only **against the base**, not against the branch's own previous tip. Commit `754e39c`
edited §OCRAUDIT **in place** to correct the false claims, which is what its message says it did and
is the right call — leaving a known-false sentence standing in the ledger would be worse than
rewriting it. The property that matters holds: nothing written before this branch's own section was
touched.

**The 48 discards, judged.** `_words_class` (`tools/privacy_scan_branch.py:543`) is a blanket rule —
`return cls == "WORDS"` — so the WORDS class is discarded unconditionally by standing scanner policy,
not by anything this branch chose; the same rule absorbed 26 discards on the original audit and 39 on
my own review. I re-ran with `--no-exclusions` and read all 48: every one is an ordinary English word
caught by `WORD_RE`'s `[A-Z]{4,}` inside emphasised prose (ENABLES, SALVAGE, HARBOUR, TRAFFIC,
REASONABLY, RELIANCE, ARBITRATION and the like; DONUT is a member of row #45's own OCR-alternatives
grep list, not a merchant). **Not one is an institution, a customer, or anything document-shaped.**
The discards are legitimate, and the growth 26 → 39 → 48 tracks prose volume, which is what a blanket
WORDS rule does.

### The OQ1 adjudication

**Is OQ1 now fit for Gustavo to rule on? YES.** It states both proven sites with anchors and exact
behaviour; it says in its own opening line that the question was re-posed and why the old
recommendation was unsafe; the three options are genuinely distinct and exhaustive over the decision
space (remove / admit-with-evidence / quarantine-and-re-admit); each option's cost is stated honestly,
including the one that cannot be quantified — option (a) "costs whatever recall the two repairs would
genuinely have won — an amount nobody has measured, because the rung has never run", which is the crux
and is not hidden; the gate is explicit ("no OCR-fed document may be validated until this pair is
ruled"); and the ruling is tied to a deliverable that makes it actionable rather than to a promise. A
reader who has never seen this branch can rule on it from the question alone.

**Is (c) the fail-closed-consistent recommendation? YES**, and it is the only one of the three that
is. The test is what each option's *default state* does about the part of the chain nobody has
characterised:

* **(a)** is fail-closed on values, but it forecloses a decision evidence could later inform and never
  measures what it gave up.
* **(b)** scopes the two *proven* rewrites behind a flag and leaves the two declared-unknown members
  running by default. A gate that covers the known sites but not the unknown ones is not fail-closed;
  it is closed against what has already been found, which is the weaker property and the one that
  lets the next F-11 through.
* **(c)** quarantines everything and re-admits per function on that function's own evidence. Its
  default state covers the declared unknown, it makes the census's *completion* the gate rather than
  its promise, and every re-admission is a separate evidenced decision that is monotone and
  reversible. That is the same shape as this program's other conservative gates — §5.8's own "until
  that table exists, an OCR-fed section falls outside the class and fail-closes", and Q10's
  fail-close on ambiguity.

Recommending **(c) as the default with (b) as the exit path** is therefore right, and the sequencing
matters: (b) is what (c) converges to once each function has its fixture, so the pair is a trajectory
rather than a fork. I would not change the recommendation.

One consequence belongs in the Phase-2 card rather than in the ruling: quarantining the chain also
suspends the strip-only members, and suspending those *adds* content to the analysis input — raw
`<|det|>` region tags, the model's refusal prose, `[Non-Text]` placeholder lines, and the second
oversize-image net. The per-region base64 bound survives regardless, because `embed_image_regions`
enforces its own cap at `ocr/ocr_client.py:371`, outside `postprocess`. This is small and it points
the opposite way from the rewrites, and option (c)'s own wording already accommodates it: the
strip-only members are the ones the census will clear first.

### MINOR-6 (new, does not block) — the owed census is scoped to six members; the chain has nine

§5.7's deliverable and F-11's third consequence both say `postprocess` is "six functions deep" and
scope the census to "all six members". Parsed from the source, `ocr/ocr_client.py:409-416` calls
**nine** distinct functions: `strip_det_tags`, `strip_refusal_commentary`,
`strip_placeholder_markers`, `strip_oversized_embedded_images`, `collapse_repeated_amounts`,
`collapse_repeated_page_numbers`, `split_fused_header_row`, `repair_fused_amount_table`,
`fix_amount_column_bleed`. The three missed are the three nested on the first line, and all three
**delete text**: `strip_placeholder_markers` drops whole lines, `strip_det_tags` removes a tag plus a
following token in its orphan form, and `strip_refusal_commentary` removes model prose.

Since the census is the gate for OQ1's option (c), a census scoped to six of nine members is a gate
with three holes. I probed all three and none is a value rewrite on any input I could construct
(`_REFUSAL_RE` at `:18-23` is a tightly anchored three-sentence template and leaves an adjacent money
token alone; the placeholder regex matches only the placeholder), so this is a **scoping defect, not a
demonstrated hazard** — which is precisely why it belongs inside the census rather than outside it.
The fix is to say nine and name the three. It does not stop Gustavo ruling: option (c) already reads
"re-admitted function by function only as the rewrite census in §5.7 clears each one", and "each one"
is recoverable from three lines of code.

### Verdict

**CONFIRMED — READY FOR GUSTAVO.** Eleven findings closed, each verified by re-measurement rather than
by reading the closure's claim: the trigger counts re-derived two ways, the census figures for both
new rows re-run, the table re-parsed to 47, the guards and both scans re-executed, the 48 discards
individually read, the W3 append-only property re-verified against the base, and the `filter-branch`
rewrite proven message-only by tree-object comparison across all three generations.

The closure is honest about what it got wrong, credits the review where a finding came from the
review, and — in the three places where the correct answer was "raise it, do not settle it" (the
`_ocr_keys` ordering, the fabricated confidence label, the Approved spec) — raises it as a risk and an
open question instead of quietly resolving it. That instinct is what makes the document safe to hand
over. MINOR-6 is a one-word correction to an owed deliverable's scope and belongs in the Phase-2 card.
