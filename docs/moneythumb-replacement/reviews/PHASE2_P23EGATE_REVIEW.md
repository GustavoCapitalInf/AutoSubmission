# Independent adversarial review — Phase 2.3 cell E (P23-EGATE)

| field | value |
|---|---|
| card | `docs/agent-handoffs/P23-EGATE.md` (umbrella `PHASE2-3-WAVE.md`, D7, cases 6/13/14) |
| branch / tip | `wave23-egate` @ **`e74428c`** · base **`26f94f5`** · 15 commits |
| diff under review | `git diff 26f94f5...e74428c` — 14 files, 3,886 insertions, 3 deletions |
| reviewer worktree | `.claude/worktrees/rev23-egate` (fresh, DETACHED at `e74428c`) |
| reviewer logs | `discovery_reports/train13-logs/rev23-egate/` (`MASTER.log`, `EXIT=` lines) |
| host | Windows 11 · `C:\Python314\python.exe` · `OCR_MAX_WORKERS=1` · no network |
| reviewer | independent; wrote none of this code |

## VERDICT: **APPROVE WITH FINDINGS** (2 MAJOR, 6 MINOR, 1 OPERATIONAL)

The cell's central claims hold and I could not break them: `ocr/escalation.py` is
byte-identical to its base content, no module of the router, the analysis layer or the
webapp names or reads an `eq_*` figure, the thirteen columns are appended at the end of
`ROW_FIELDS` in the module's own table order, the projection is empty on native-only
reads and never raises out of `_finish`, every unmeasured figure is `None` rather than a
measured zero, the census refuses the production and cold caches at cell T's door, and
the metrics reach nothing that decides anything. **Nothing in this cell can move a
verdict, a trigger or the floor**, which is why the findings below are MAJOR rather than
BLOCK: they are defects in what the metrics MEASURE and in what the tests PROVE about
the fold, not in what the engine does.

The two MAJORs are (1) an E3 criterion that fires on a perfectly clean two-column
statement page, and (2) a document-fold test that is vacuous for seven of the eleven
folded columns. Both matter because 2.5 calibrates production triggers from exactly
these numbers.

---

## Findings

### MAJOR-1 — the numeric right-edge residual fires E3 on a clean two-column statement page

`_right_edge_residual` takes **the last money token of each line** and measures the
dispersion of those right edges. On any layout where different lines end in different
money columns — withdrawals/deposits, debit/credit, an amount column with a running
balance printed on only some lines — the "column" it measures does not exist, and the
residual is the distance BETWEEN the columns rather than the wobble within one.

Reproduced on a synthetic page that is otherwise flawless: 12 transaction lines, every
token clean, every amount parsing, uniform line heights, lexicon rate 0.94 — odd lines
print a withdrawal (column ends x=400), even lines a deposit (column ends x=520).

```
$ C:/Python314/python.exe <scratch>/rev23egate_probe.py      # section A1
words=56 money_rate=0.4166666666666667 lexicon_rate=0.9375
right_edge_lines=10 residual=8.0 ceiling=1.5
line_height_cv=0.0  CLASSES=('E3',)  e_class='E3'
```

8.0 character widths against a 1.5 ceiling — five times over, on a page with no defect
at all. The module docstring claims each floor "is set where the SHAPE of a page stops
being a statement page at all"; that is not true of this one, and §"What these metrics
cannot say" names the missing skew estimate but not this. Every synthetic fixture is a
single-money-column ledger (`build_ledger_page` prints amount and balance, balance
always last), so the fixture set cannot see it.

**Why it matters despite admitting nothing.** E3 is one of the classes §H.4 says may
open an extractor fallback; the census over cell W's real partition — the deliverable
this instrument exists for — will report an E3 population dominated by a layout
artefact, and 2.5 recalibrates from that distribution. Cell B reads the same classes.

**Cheapest honest closure** (2.3 need not redesign the metric): cluster the edges and
measure within the rightmost cluster, OR record the behaviour in "what these metrics
cannot say" with a committed two-column fixture that pins it, so the census is read with
it in view. Either closes the finding; silently keeping the threshold does not.

### MAJOR-2 — the document fold is proven for 2 of 13 columns; min↔max swaps survive

`test_the_document_fold_names_the_worst_page_per_column` is the only test of the fold,
and its three-page fixture (clean ledger, noise page, blank page) makes the assertion
vacuous wherever the pages agree:

```
$ C:/Python314/python.exe <scratch>/rev23egate_probe2.py     # section B3
   garbage_rate           present=[0.0, 0.0, 0.0]  -> VACUOUS (min == max)
   money_rate             present=[0.5]            -> VACUOUS (min == max)
   line_height_cv         present=[0.0, 0.0]       -> VACUOUS (min == max)
   right_edge_residual    present=[0.0]            -> VACUOUS (min == max)
   rec_p10                present=[]               -> VACUOUS
   ink_outside_boxes      present=[]               -> VACUOUS
   orientation_share      present=[0.0, 0.0]       -> VACUOUS
```

Only `word_count_min` (0 / 126 / 138) and `density_min` discriminate. Card deliverable 2
requires the fold per column to be stated AND pinned; seven folds are stated and not
pinned. Proven by mutation below (fresh mutants F2–F4: all NOT KILLED).

### MINOR-1 — the garbage rate has no minimum-denominator guard, and masked account numbers are garbage

Its two sibling rates carry denominator guards (`money_rate_min_numeric_tokens` 20,
`lexicon_rate_min_alphabetic_tokens` 30); the garbage rate has none beyond
`min_words_for_page_metrics` 12. So a legitimate sparse page — a continuation page, a
summary page, a "page 2 of 4" header — is classified on a rate over as few as twelve
tokens:

```
# probe A2: 15 words, a masked account number and a statement URL
words=15 garbage_rate=0.13333333333333333 ceiling=0.05
CLASSES=('E2',)  e_class='E2'
# probe B7, _is_garbage_token on ordinary statement tokens:
   'XXXXXXXX4821'            garbage=True     # masked account number
   'XXXX'                    garbage=True
   'GB29NWBK60161331926819'  garbage=True     # IBAN
   'HTTPS://WWW...STATEMENTS' garbage=True    # footer URL
   '****1234'  '-----------'  '00000000'      garbage=False   (correctly)
```

The letters-only repeat regex is doing real work (rules of dashes and padded zeros are
correctly not garbage), but `XXXX`-masking is statement furniture on most real
statements, and an IBAN and a URL are legitimate long tokens. Recommend a
`garbage_rate_min_tokens` guard in the same table, or the limitation recorded.

### MINOR-2 — E3's orientation criterion is literally unanimous, and never reads the frame

`orientation_unanimous_share: 1.0` with `vertical_share >= 1.0` means one horizontal box
disarms the criterion completely:

```
# probe B2 — a page whose ONLY defect is a quarter turn
  wide boxes=0: votes=(h=0, v=12, i=0)  share=1.0    sub={'orientation': True,  ...} classes=('E3',)
  wide boxes=1: votes=(h=1, v=12, i=0)  share=0.923  sub={'orientation': False, ...} classes=()
```

Faithful to §H.4's word "unanimous", but a real rotated page carrying one wide artefact
box (a page number, a rule fragment, a stamp) will not fire it — the census will read
near-zero orientation-E3. Separately, `_with_classes` reads no frame attribute at all
(probe A5 lists every attribute it reads), so §H.4's "unanimous orientation votes
disagree with **the frame**" is implemented as "votes are unanimously vertical"; a 180°
page is invisible to it. Neither limit is in "what these metrics cannot say".

### MINOR-3 — E1's ceiling is a share of INK, so ordinary non-text ink dominates it

Adding one solid block to the clean ledger's own raster — a logo, a shaded header band, a
signature panel: ink that carries no word box on every real statement:

```
# probe A3, clean ledger at 100 dpi, ink_share 0.0113
  clean : outside=0.000000 classes=()        logo  90x90 px : outside=0.432993 classes=('E1',)
  logo 60x60 px : outside=0.253396 classes=() logo 150x150 px: outside=0.607219 classes=('E1',)
```

A 0.9-inch square of solid ink is 43 % of a text page's total ink. On denser pages the
share falls, but ruled borders and shaded bands scale with the table. A calibration risk
to carry into the owed real-evidence census, not a code defect.

### MINOR-4 — the coarse "who names a column" net does not cover the repository root

`test_the_report_is_the_only_thing_outside_the_module_that_names_the_columns` globs
`ROOT.glob("*/*.py") + ROOT.glob("*/*/*.py")`; the 11 repository-root modules are outside
it (`corpus_gate.py`, `parse.py`, `analyze.py`, `batch.py`, `build_corpus_cache.py`,
`local_ocr_server.py`, `corpus_artifacts.py`, `conftest.py`, the three audit scripts —
probe B6). The AST guard over `ocr/escalation.py`, `analysis/` and `webapp/` is the pin
that matters and it is sound; this is the second, coarser net only. One-line fix:
`+ sorted(ROOT.glob("*.py"))`.

### MINOR-5 — the census's production-cache refusal escapes as an unhandled traceback

Every other refusal in `tools/extraction_quality_census.py` is a clean `SystemExit`
message; T's door raises `ValueError` and `census()` does not translate it:

```
$ python -m tools.extraction_quality_census --data-dir "../../recovery/webapp_data_train12_cold" \
      --research-partition paddle-v5-prod        # ...traceback...
ValueError: --data-dir ... names a production or historical cache (webapp_data_train12_cold)
rc=1
```

The door works (`webapp_data` refused likewise, rc=1) — this is presentation only.

### MINOR-6 — ownership: six files outside the card's "exact; nothing else" list

`git diff --name-only 26f94f5...e74428c` against the card: `discovery/report.py` (where
`ROW_FIELDS` actually lives — the cell-X finding, unavoidable and correct),
`tests/test_extraction_quality_admission.py`, `tests/test_extraction_quality_census.py`,
`tools/p23egate_fake_partition.py`, `tools/p23egate_mutation_table.py`,
`tools/p23egate_synthetic_table.py`. All are proof instruments or extra test files; none
collides with any other Phase 2.3 cell's named files. Recorded as a deviation for Ocean,
not a defect.

### OPERATIONAL-1 — the stale-lock helper would have run two drivers concurrently

`discovery_reports/train13-logs/p23egate/scripts/p23egate_lock.py` lines 47–49 and 54–56:
a waiter that finds the lock held by a holder whose name **starts with its own** prints
"already held" and **returns 0**. A resumed P23-EGATE session, or a second window opened
while the first still ran, both receive success and both proceed to run a driver. The
release path has the same root cause: it would remove a lock a live sibling holds.

**It is a real defect, and it is NOT in a committed tool.** The file is gitignored
(`git check-ignore` → `.gitignore:23:discovery_reports/`; `git ls-files --error-unmatch`
fails), and no tracked `.py` or `.sh` in the tree references `HARNESS.lock` at all. It is
a cell-scratch helper — but every cell copies this idiom, so Ocean should carry the fix
into the shared discipline: compare the recorded pid and refuse when it differs, or
require an explicit adopt flag. My own helper refuses in that branch by construction.

---

## The attack list, item by item

| # | attack | result |
|---|---|---|
| 1 | E-class semantics vs §H.4 | vocabulary exact (`('', E0, E1, E2, E3, E5)`, probe A8); `E4` does not occur in the module source; precedence documented (`E_CLASS_PRIORITY`) and deterministic — `classes` keeps every class that fired and `e_class` reports the first by priority; a page firing E0+E1 reports E0 (their own test). **False positives found on a normal page: MAJOR-1 (E3), MINOR-1 (E2), MINOR-3 (E1).** E0 is derivable here only from an empty word list, which the module states. |
| 2 | cross-configuration rec-score comparison | **no path found.** The folds stay within one document; the census groups by `configuration_of(evidence)`, built from the extractor's own recorded runtime, so two configurations are two tables by construction; nothing is thresholded on the rec score. Rows carry `source_model`, `escalation_extractor` and `research_partition` (probe B5), so a row's configuration is identifiable. |
| 3 | metric arithmetic at the edges | all correct (probe A6): zero numeric → `money_rate=None`; zero alphabetic → `lexicon_rate=None`; one line → both box-regularity figures `None`; no raster → both ink figures `None`; no words → `orientation_votes=None`; one aligned money column → residual 0.0 over 5 lines. A zero-area frame is **unreachable** (`PageFrame` refuses non-positive dimensions, probe B4), so `density`'s `0.0` fallback is dead defence. FR/ES accents and case fold correctly (probe A7: `relevé`→`releve`, `dépôt`→`depot`, `período`→`periodo`, all in the vocabulary). Long legitimate tokens → MINOR-1. |
| 4 | the projection | native-only rows empty, and each half of the guard holds alone (their test, re-run); a malformed evidence raises nothing out of `_finish` (their `_Exploding` test, re-run); `eq_class` outside `E_CLASSES` is refused in `as_dict`; the fold per column is stated in `EQ_ROW_COLUMNS` — **but only 2 of 13 are pinned: MAJOR-2**, proven by fresh mutants F2–F4. |
| 5 | never a trigger | `ocr/escalation.py` byte-identical: `git show 26f94f5:ocr/escalation.py \| tr -d '\r' \| sha256sum` = `e8367533…4384ec` = the tip's. `git diff --stat 26f94f5...e74428c -- ocr/escalation.py evidence/ layout/ analysis/ telemetry/ webapp/ tools/paddle_wave.py` is **empty**. Their four planted scratch-copy mutants all caught; I added two more (F5, F6 below). `ADMITTED_TRIGGERS`, `EXTRACTOR_ORDER` and `RouterInputs`'s six fields unchanged. |
| 6 | the census tool | refuses the live cache and the read-only cold cache at T's door (rc=1, both); refuses a non-ignored `--out`; `--help` exposes no verbose/text flag; `render` emits counts and percentiles only. Re-run on the fake-worker partition below. Presentation defect MINOR-5. |
| 7 | mutation table | re-run in my worktree — see below. |
| 8 | ownership | MINOR-6; the six untouched trees verified empty. |
| 9 | the privacy hit | re-derived — see below. |
| 10 | scans and trailers | privacy `--base 26f94f5 --ref e74428c` reproduces `hit_count 1` (the same DIGITS token, MONEY/DATES/WORDS 0); message scan 15 commits → `hit_count 0`; `Co-Authored-By` and `Claude-Session` trailers present on all 15; the two rewords verified byte-identical by TREE (below); no host, port, user or token value in any added line. |
| 11 | heavy proofs, judged | below. |

### The rewords, verified by tree

`git reflog show wave23-egate` records two `filter-branch: rewrite` entries. The
pre-reword chain (`4a26892…e8b142d`) and the current chain (`d232520…1fb8cf3`) carry the
**same fourteen tree objects in the same order** (`570212d6…`, `d147a06e…`, `2e75de43…`,
`22d155da…`, `2e2bc98c…`, `ecd16c7a…`, `4f78e1f6…`, `beaeef11…`, `87b01322…`, `56657355…`,
`e6460398…`, `df6a742d…`, `f2f1d178…`, `3b55e704…`). Only the fifteenth (the W3-2 doc
commit) differs, because it was amended to record the second remap. **The rewords
changed messages only.**

### The "do not re-run the replay" ground — VERIFIED

```
$ git diff 342c7d9 HEAD -- . ':!tests' ':!tools' ':!docs'     # (empty)
$ git diff --name-only 342c7d9 HEAD
docs/moneythumb-replacement/W3_TRACKA_LOG.md
tests/test_extraction_quality_admission.py
tools/p23egate_mutation_table.py
$ git diff --name-only d232520 HEAD
docs/moneythumb-replacement/W3_TRACKA_LOG.md
```

The ground holds: after `342c7d9` only a test, a proof tool and the W3 moved, none of
which is on the replay path. The suite log at `dff4223` (= `d232520`'s tree) is therefore
a suite result for the tip's code; `d232520..HEAD` is docs-only.

---

## MAJOR-3 — the W3's census table mis-transcribes the `ink_outside_boxes` row

I rebuilt the fake-worker partition with the cell's OWN committed instrument in MY
worktree and re-ran the census. **Every one of the eleven metric rows reproduces the
cell's own `p23egate-census-fakeworker.log` exactly** — and ten of the eleven match the
W3. The eleventh does not:

```
W3    ink_outside_boxes -> ['7','0','0','0.0160785','0.35497','0.744944','0.744944','0.744944']
log   ink_outside_boxes -> ['7','0','0','0',        '0.0160785','0.35497','0.744944','0.744944']
mine  ink_outside_boxes -> ['7','0','0','0',        '0.0160785','0.35497','0.744944','0.744944']
header:                      measured min p05 p25 p50 p75 p95 max
```

The W3 dropped the `p25` zero and duplicated `0.744944` to refill the row, so **p25, p50,
p75 and p95 each sit under the wrong heading**. Consequently `0.35497` — the very figure
Ocean is asked to adjudicate — is the **p75**, not "the median" the W3's prose calls it.
Every other row, the E-class tables and the per-row `eq_class` list (`"" / "" / E2 / E3 /
E2 / E2 / E2`, `eq_ink_outside_boxes` empty on all seven) reproduce exactly. One-line fix
to the record; the measurement itself is correct.

## Attack 9 — the privacy hit, re-derived: **the adjudication HOLDS**

```
$ rm -rf <scratch>/rev23egate_fakepart
$ OCR_MAX_WORKERS=1 python tools/p23egate_fake_partition.py <scratch>/rev23egate_fakepart
  ... EXIT=0
$ grep -c "35497" discovery_reports/train13-logs/rev23-egate/rev23-fakepartition.log
1
$ grep -o "0\.35497" .../rev23-fakepartition.log
0.35497
```

`0.35497` is produced, verbatim and exactly once, by the committed instrument from the
seven committed synthetic fixtures — seven PDFs rendered from literal strings by
`tests/paddle_synthetic.py`, read by the in-process `FakeWorker`, rasterised by
`ocr.rasterize`. **No document was read in the derivation.** Ocean's provisional ruling's
condition is met: the token has adjudicated non-document provenance, and the hit is
closed. (The scan itself reproduces: `added_lines 3886`, `hit_count 1`,
`hits_by_class {DATES 0, DIGITS 1, MONEY 0, WORDS 0}`, `documents_read 3351` — identical
to the cell's `p23egate-privacy-final2.log`.)

## Mutation — the cell's table, and my fresh mutants

**The cell's M1–M10 re-run is QUEUED, not run** (see the lock window below); its harness
edits the working tree and runs pytest, which is a heavy proof. I instead attacked the
same properties the way the cell proves M6 — the mutant planted in a **scratch copy**,
exec'd as a fresh module, with the killer run in process and the tree never touched. That
is strictly stronger than a tree edit (it cannot leave a mutant behind) and needs no lock.

| # | fresh mutant (scratch copy; tree untouched) | result |
|---|---|---|
| F2 | the `garbage_rate_max` fold replaced by `min` | **NOT KILLED** |
| F3 | the `line_height_cv_max` fold replaced by `min` | **NOT KILLED** |
| F4 | the `money_rate_min` fold replaced by `max` | **NOT KILLED** |
| F5 | the `right_edge_residual_max` fold replaced by `min` | **NOT KILLED** |
| F6 | the orientation-share fold replaced by `min` | **NOT KILLED** |
| F7 | the worst-page E-class fold replaced by the FIRST page's class | KILLED |
| F8 | the `ink_outside_boxes_max` fold replaced by `min` | **NOT KILLED** |
| F9 | a threshold moved **with its test literal**, `EXTRACTION_QUALITY_VERSION` left at 1 | **NOT KILLED** |

Control: the unmutated module passes the killer (`the UNMUTATED module passes the killer:
True`), so the table is not vacuous. F2–F6 and F8 are MAJOR-2's proof. F9 is an honest
limit rather than a defect: their M1 (which edits the module only) IS killed by the pin,
but nothing computes a digest of `THRESHOLDS` and compares it to the version, so the
"a threshold cannot move without a reviewed version edit" claim rests on a test literal,
not on a structure. A one-line `assert sha256(repr(sorted(THRESHOLDS.items())))` pinned
beside the version would make the prose true.

**M6's fix, verified independently** (`rev23-ast-attacks.log`, section C4):

```
  the real killer                    exit=0 failures=0 passed=4 -> harness reports KILLED
  the killer DESELECTED / renamed    exit=4 failures=0 passed=0 -> harness reports NOT KILLED
```

The `passed > 0` condition does exactly what the cell says: a row whose killer selects
nothing reads NOT KILLED. Their four planted router mutants are all caught, and I planted
five shapes of my own in scratch copies of `ocr/escalation.py`, `analysis/pipeline.py`,
`analysis/money.py` and `webapp/app.py` — **all twenty caught**, every guarded file clean
on the real tree (114 modules scanned, `offences == []`). The guard cannot see
`getattr(row, 'eq_' + 'class')` or a `startswith('eq_')` prefix scan; adjacent-string
concatenation IS caught. That is the normal limit of an AST guard and the cell does not
claim otherwise.

## Heavy proofs — mine vs the cell's, and the lock window

| proof | the cell | me |
|---|---|---|
| full default suite | `p23egate-suite-2.log` **EXIT=0**, `9890 passed, 48 skipped, 39 deselected` at tree `dff4223` = `d232520`'s tree | judged sufficient: `git diff --name-only d232520 HEAD` is the W3 only |
| the five guards / seven conformance files | `p23egate-guards.log`, `p23egate-conformance.log` **EXIT=0** | accepted on the same ground |
| `corpus_gate.py` GREEN 105/3/1 | `p23egate-gate.log` **EXIT=0** | queued; accepted on the same ground |
| `pytest -m corpus` | `p23egate-corpus.log` **EXIT=0** | queued; accepted on the same ground |
| union replay, 4 chunks at base + 4 at closure, `--expect-identical` | 8 logs, all **EXIT=0** | queued; their "not re-run after the last code commits" ground VERIFIED above — the only production change in the whole cell is the runner's projection plus the `ROW_FIELDS` append, and the projection returns before touching a native row |
| the cell's M1–M10 mutation table | `p23egate-mutants-2.log` **EXIT=0**, 12/12 killed, `p23egate-mutation-table.md` | **QUEUED — not run.** Replaced by 8 fresh scratch-copy mutants above |
| the eq_/row/census/hardcode test files | green in their suite | **re-run in my worktree: `159 passed`, EXIT=0** (`rev23-targeted-tests.log`) |
| branch privacy scan | `hit_count 1` | **re-run: identical** (`rev23-privacy.log`) |
| commit-message scan | `hit_count 0`, 15 commits | **re-run: identical** (`rev23-msgscan.log`) |
| the fake-worker census | `p23egate-census-fakeworker.log` **EXIT=0** | **re-run: reproduces their log exactly** (`rev23-fakepartition.log`, EXIT=0) |

**Lock window.** `discovery_reports/train13-logs/HARNESS.lock` was held by **P23-WAVE**
(`acquired 2026-09-11T21:34:59Z`, pid 44772) continuously from my first poll at
**22:05:44Z** through my last at **01:02:28Z** — **seventeen bounded foreground polls at
a 1-second interval, ~2 h 57 m, never acquired**. I never held the lock, never removed
another holder's, and ran no tree-editing harness. Everything above was completed
lock-free: read-only scans, in-process scratch-copy mutants, targeted test files, and a
synthetic seven-page partition. The two genuinely lock-bound proofs (their M1–M10 table,
a replay chunk at the tip) are recorded as queued, and neither is load-bearing for this
verdict: 12/12 is corroborated by their own `EXIT=0` log at a tree that differs from the
tip by docs, a test and a proof tool only, and the replay's ground is verified by diff.

## The W3 numbers, re-derived vs claimed

| claim | verdict |
|---|---|
| suite 9,890 / 48 / 39 / 0 | **matches** their log; the tree it ran at differs from the tip by the W3 only |
| guards, conformance, gate GREEN 105/3/1, corpus slice — `EXIT=0` | **matches** every named log |
| 8 replay chunks `EXIT=0`; not re-run after `342c7d9` because the non-test/tool/doc diff is empty | **ground verified** (`git diff 342c7d9 HEAD -- . ':!tests' ':!tools' ':!docs'` is empty) |
| privacy 3,886 added lines, `hit_count 1`, MONEY/DATES/WORDS 0 | **reproduced exactly** |
| message scan 0 over 15 commits after the rewords | **reproduced exactly**; trailers on all 15; the rewords verified byte-identical by TREE |
| the fake-worker census: 1 configuration, 7 documents / 7 pages, 7 cached negatives | **reproduced exactly** |
| the per-page E-class counts: `(none)` 1 · E1 2 · E2 4; every class: E1 2 · E2 4 · E3 1 | **reproduced exactly** |
| the seven rows' `eq_class` `"" / "" / E2 / E3 / E2 / E2 / E2`, ink columns empty | **reproduced exactly** |
| the `ink_outside_boxes` percentile row | **DOES NOT reproduce — MAJOR-3** |
| mutation 12/12 after the M6 fix | corroborated by their log and by my independent M6 verification; the table itself queued |
| `ocr/escalation.py` byte-identical; no `eq_*` reader outside the report | **verified by blob, by AST over 114 modules, and by 20 planted mutants** |
| newly validated 0 · ladder movement 0 · regressions 0 | consistent: the projection cannot run on a production row (no production partition carries extractor evidence) and writes only to the row |

## Properties I attacked and could not break

`ocr/escalation.py` byte-identical (sha over LF-normalised bytes, both ends); the six
untouched trees genuinely untouched; `ADMITTED_TRIGGERS`, `EXTRACTOR_ORDER` and
`RouterInputs`'s six fields unchanged; no guarded module names or reads an `eq_*` figure,
and five plant shapes are caught in each of four scratch copies; the module imports only
the standard library, `evidence` and `layout.signals`; `E_CLASSES` is §H.4's vocabulary
exactly, `E4` absent, the precedence documented, deterministic and non-discarding; the rec
score is thresholded nowhere; the thirteen columns are the module's own table in its own
order at the very end of `ROW_FIELDS`; `eq_class` outside the vocabulary is refused in
`as_dict`; the projection is empty on native-only reads (each half of its guard holds
alone), empty with no read, and swallows a raising evidence without failing the run;
unmeasured is `None` and renders `""` at every edge I could construct; the metrics are
deterministic; the census refuses the live cache, the cold cache and a tracked `--out`,
exposes no verbose flag, and prints no text, sha, path or verdict; the `rate` exemption in
the cost grep is derived from the module's own table and lifts only that one word.

## My instruments (session scratchpad; none committed)

`rev23egate_probe.py` (A1–A8), `rev23egate_probe2.py` (B1–B7), `rev23egate_probe3.py`
(C1–C4: the AST guard, 20 planted mutants, the M6 harness fix), `rev23egate_foldmutants.py`
(F2–F9), `rev23egate_lock.py` (mkdir-only, bounded poll, own-holder release — and it
REFUSES the same-name branch OPERATIONAL-1 is about). Logs under
`discovery_reports/train13-logs/rev23-egate/` with `EXIT=` lines and `MASTER.log`.

## What Ocean should require before composing

1. **MAJOR-1** — close the two-column right-edge residual: cluster the edges, or record
   the limitation in the module's "what these metrics cannot say" with a committed
   two-column fixture that pins the behaviour.
2. **MAJOR-2** — make the fold fixture discriminating (pages whose garbage rate, line-height
   CV, orientation share, money rate, right-edge residual and ink share actually differ),
   so the six surviving mutants die.
3. **MAJOR-3** — correct the `ink_outside_boxes` row in `§P23EGATE` and the prose that
   calls `0.35497` the median; it is the p75.
4. MINOR-1..6 and OPERATIONAL-1 are cheap or carryable; MINOR-4 is a one-line glob fix.
5. The real-evidence census remains **OWED** — the cell says so itself, and MAJOR-1 and
   MINOR-1/2/3 are precisely the reasons that census must be read with care when it lands.


# Closure re-review — measured quality, recorded identities and final proofs

**APPROVE** at final cell tip `f8c9257f30d0963e9557ae1fa3884ef998f6b02a`.
The root orchestrator wrote none of E's implementation, tests or W3 sections.
Independent source probes ran in the clean detached `rev23-egate-closure`
worktree, most recently at `b70cbc3`. The final tip changes only documentation.
The historical review and every failed or interrupted attempt remain preserved.
The train's composed-tree floor is still a separate requirement.

## Original findings and additional closures

| finding | closure and independent evidence |
|---|---|
| MAJOR-1, multiple money columns | Residuals are measured within columns and the worst column is reported; the clean withdrawal/deposit fixture no longer measures the distance between columns as an error. |
| MAJOR-2, vacuous folds | The fixture's protected page values disagree, making each fold discriminating. Version 2 and its recorded calibration digest bind the changed thresholds and furniture predicates. |
| MAJOR-3, percentile transcription | The historical median/p75 error has an append-only correction. The current fake partition is separately identified as a new version-2 measurement. |
| MINOR-1, furniture and small denominators | Masked fields, IBANs and footer URLs have named generic shapes; the versioned minimum denominator is explicit and tested. |
| MINOR-2/3, orientation and non-text ink | Frame-aware orientation and its versioned majority are pinned. The remaining 180-degree limitation and logo-driven ink false positive are explicitly retained. |
| MINOR-4/5, readers and refusal presentation | The census of readers covers every tracked Python file; the protected source boundaries remain enforced. Cache-door failures are named refusals. |
| MINOR-6, ownership | The actual row-field module and necessary proof instruments were ratified in the handoff. No production routing ownership was acquired. |
| OPERATIONAL-1, lock ownership | Closure drivers use the committed root helper and exact own-holder release, with one heavy process window. The unsafe historical private helper is not used. |

Independent re-review also reproduced and closed three new defects. Retained
rasters must match the frame's hash before their pixels can affect a metric;
a same-sized replacement is unmeasured. Duplicate artifacts must agree on both
canonical evidence and normalized effective truncation flags, in either traversal
order. Census output cannot target the source cache or raster directory, including
resolved aliases; a sibling directory with a shared textual prefix is allowed.
The direct containment tests run; the symlink-specific test has an explicit
Windows capability skip. The independent reproduction and closure logs are in
`discovery_reports/train13-logs/rev23-egate/`.

## The original runtime and exact recorded key

The first U755 census refused one conflicting group rather than choosing an
artifact. Independent inspection found two individually indexed readings under
different keys: four complete page objects, raster hashes and effective truncation
sets were identical, while GPU/Python provenance and the canonical evidence hash
differed. The earlier configuration label collapsed those runtime distinctions.
Both artifacts and the failed census remain preserved.

At `9371781`, explicit key selection uses read-only SQLite and the existing
exact-tuple selector. Duplicate tuples, wrong envelopes, conflicting canonical
document identities, native evidence in the extractor slot and path escapes refuse
without revealing values. Configuration grouping includes every closed runtime
field; arbitrary extra fields do not create configurations. Empty canonical-page
censuses refuse. The whole-JSON audit remains an explicitly different mode.
Metric formulas, thresholds and quality version did not change in this closure.

The private binder associates the original five CTRL sessions and eight U755
sessions with one exact key through recorded evidence hashes and indexed canonical
artifacts. It does not choose a key by date, filename or current environment.
Each corrected census rechecks those source rows and artifact bytes. Later SLICE
provenance stays separate. My independent 19-check indexed-reader probe passed,
including both duplicate insertion orders, mixed valid/conflicting records,
read-only bytes, missing readings, containment and full-runtime grouping.
See `verify_runtime_pair.log` and `indexed_reader_review.log` with their scripts.

## Completed proof scope

| proof | actual result and scope |
|---|---|
| affected quality/census tests | 136 passed, one Windows symlink skip, exit zero at `9371781` |
| synthetic defect table and fake partition | Exit zero; seven measured fake pages with all retained rasters hash-verified; the known logo false positive remains |
| mutation closure | 49 distinct kills: 35 unaffected original rows, changed C2 plus nine new reader rows, then four new guard rows; all restorations clean |
| full default suite | At `9371781`: 9,939 passed, one failed, 49 skipped, 39 deselected, **exit one**; 518.3 seconds, 3,009.5 MiB peak |
| narrow guard closure | At `b70cbc3`: all five canonical guard files, including nine new self-test cases, pass 286 tests, exit zero; C20–C23 all killed, exit zero |
| conformance and corpus | Preserved 1,282 passed / 41 skipped conformance and 34 corpus-marked tests, both exit zero; gate and original production replay retain their verified unchanged-source scope |

The suite failure was the account-literal guard matching digits inside the
recorded calibration checksum. The checksum must stay recorded, not split or
replaced by an automatically changing value. The test-only correction masks just
the active, recomputed checksum's AST string span in its exact named module and
assignment. Its account-number pattern is unchanged. Other values and neighboring
code remain scanned, including after multibyte source text.

I independently recomputed the digest from both calibration tables, verified that
the production `ocr`, `discovery` and `analysis` paths did not change, and passed
22 synthetic attacks on the actual correction. These include forged and malformed
values, extra/inactive/duplicate versions, wrong locations and constructors,
dictionary unpacking, duplicate assignments, adjacent literals, Unicode prefixes
and multiline joined strings. See `calibration_guard_review.py/.log`, exit zero.
The 9,939 passing suite cases keep their scope; the failed suite is not relabeled
green or repeated after a test-only correction. The changed checks close that
specific failure. The final composed train still requires its full suite.

## Real measurements and transcription verification

| population | selected | measured documents | without measurable evidence | measured pages | hash-verified rasters | absent rasters |
|---|---|---|---|---|---|---|
| CTRL | 114 | 90 | 24 | 668 | 664 | 4 |
| U755 | 755 | 341 | 414 | 2,331 | 2,331 | 0 |

Both corrected censuses exit zero. My independent log-only comparison found all
64 numerical CTRL table/header/count rows exactly equal to the preserved earlier
CTRL result. Global skipped counters and the expanded runtime label changed with
explicit selection; they are not included in that identity claim.

I read the final W3 narrative and verified its 439-line LF append against the
prior Git blob. Separate independent log-only checks matched all 52 page/document
metric rows, 12 raster-count rows, 36 E-class count/share rows and 49 named mutation
rows to their actual source logs. Both precedence totals match the stated page and
document populations. Overlapping classes are never summed; the one U755 E5
overlap is outranked in the precedence table. See `ctrl-table-identity.log`,
`census_table_review.py/.log` and `class_table_review.py/.log`, all exit zero.

Per-metric denominators remain visible. Missing pixels, insufficient tokens or
undefined geometry remain unmeasured, not zero. These observations do not establish
word truth, financial correctness or a new production trigger.

## Final scanner results and explicit provenance attribution

The exact final documentation tip was scanned against the frozen 3,380-document
population; 3,351 cached texts were readable.

| scanner | observed result | actual exit |
|---|---|---|
| added lines | 6,337 lines; 52 raw candidates; 40 excluded by the existing words-class rule and one by the hex rule; 11 retained W3 matches: three DIGITS and eight MONEY | 1 |
| actual commit messages | 30 commits; eight WORDS matches; MONEY/DIGITS/DATES all zero | 1 |

The two historical DIGITS occurrences are the previously reviewed synthetic
calibration value and its transcription erratum. The nine new matches belong to
technical aggregate cells: seven scientific-notation coefficients for density or
minimum density, one garbage-token fraction and one line-height dispersion.
I reviewed each metric/column/denominator mapping and the source formulas; these
cells are within the 52 independently verified rows above. They are computed
token/geometry measurements, not reused customer financial literals. Their exact
values and source mapping remain in the private `final-privacy-mapping-private.json`
and its aggregate-only log. This attribution preserves measured provenance; it
does not modify the scanner or pretend that its retained count is zero.

I also read the six historical technical commit contexts carrying the eight WORDS
matches. They describe synthetic folds, source-reader guards, fixture pages,
furniture predicates, orientation votes and column residuals. Exact word and
word-pair membership is checked with the scanner's original tokenization, excluding
author/session metadata. The handoff's ordinary-English ruling applies. The eight
matches and exit one remain explicit; no history rewrite is needed.

The underlying logs are `p23egate/closure-20260915-privacy.log` and
`closure-20260915-messages.log`; the private attribution records are beside them.
The driver released its holder at 19:24:00Z and exited; no E waiter remains.
No scan was repeated simply to include its result in an earlier W3 commit.

## Limits and verdict

Recognition scores remain configuration-specific. Word-box geometry cannot prove
a page is upright at 180 degrees, and a logo can trigger the ink-coverage metric.
E-classes are observational; no metric reaches a route, trigger, financial verdict
or admission decision. The original protected production payloads retain their
zero-change proof; newly validated and ladder movement remain zero.

**APPROVE.** The original and additional source findings are closed. Actual
measurements, discriminating mutations, independent probes and precise retained
proof scopes support this closure. The non-document scanner matches are explicitly
attributed above, with all raw counts and exits preserved. Composition and the
full train floor remain the root orchestrator's next gates.
