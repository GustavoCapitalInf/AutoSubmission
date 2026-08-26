# BATCH 8 — CP-SECTIONED-SCAN adversarial review

Branch `wave8-cpscan`, tip `3fb5a62`, base `10cc722`. Worktree
`.claude/worktrees/mt8-cpscan`. Reviewer: independent Opus cell; the
implementing cell is gone and answered nothing.

## Verdict

**APPROVE WITH FINDINGS — 0 BLOCK, 2 MAJOR, 5 MINOR.**

Every substantive claim the branch makes reproduces under independent
measurement, most of it over a population larger than the cell's. The two
MAJORs are both privacy-rule findings and both must close before the train:
one line of a real archive document reached a new test fixture, and the
branch's own privacy instrument cannot see it.

The archive claim is CONFIRMED and is stronger than stated: base→branch moves
**0 documents and 0 leaves over 135 documents and 2,472,199 payload leaves** —
the complex's 59 plus the 80 pinned documents of the 109 that the run of
record covers, including all four pinned documents of this complex.

## 1. What the branch closed (the file list)

`git diff --stat 10cc722..wave8-cpscan` — nine files, 1,884 insertions / 28
deletions:

`analysis/core_processor_daily.py`, `analysis/core_processor_sectioned.py`,
`docs/moneythumb-replacement/W3_TRACKA_LOG.md`,
`tests/test_core_processor_daily.py`, `tests/test_core_processor_sectioned.py`,
`tools/cpscan_ceiling.py`, `tools/cpscan_census.py`, `tools/cpscan_mutate.py`,
`tools/cpscan_privacy_grep.py`.

Protected modules untouched, confirmed from that list: no `corpus_gate.py`
(neither modified nor additive), no `analysis/parser_registry*.py`, no
`tests/data/parser_expectations.json`, no `analysis/tables.py`, no
`analysis/date_tokens.py`, no `ANALYSIS_STAGE_VERSION` bump. Registry size
measured at **75 in both trees**, in one process, by my own replay.

## 2. Findings

### F1 — MAJOR — a printed line from a document of the cell's own named 19 entered a test fixture

**Claim under test:** W3 §CPS11.4, `"hits": 0` — "the privacy scan, over the
branch's whole diff".

**Evidence:** the shared instrument
`.claude/worktrees/mt-lead/tools/privacy_scan_branch.py`, run against the
committed diff at `--base 10cc722 --ref wave8-cpscan` with the population
scoped **to the cell's own 19 shas and nothing else**:

```
population 19 · documents_read 19 · added_lines 1884
hit_count 5 · MONEY 0 · DATES 0 · DIGITS 0 · WORDS 5
```

One of the five is `tests/test_core_processor_daily.py:375`. The new fixture
`split_card_date` prints a US city token and its state abbreviation
immediately before the masked-card token that already existed in that module
at base — and that exact adjacency is printed in one of the nineteen scanned
documents. The mask itself is inherited from the base tree and is not the
finding; the city is, and it appears nowhere in `analysis/` or `tests/` at
`10cc722`.

The cell knew the anonymised form: the same construction in the
`core_processor_daily._ROW_DATE` docstring on this very branch uses an
invented placeholder town and a zero-tailed mask. The fixture did not.

This is the standing rule as written on the card — "NO archive content may
enter tracked source … nor an 'example' block copied from a document;
fixtures are INVENTED". Graded MAJOR rather than BLOCK because the token
carries no figure, no date, no account number and no person, and the shared
instrument classes it in its weakest class; but it is BLOCK-adjacent and if
Ocean reads the standing rule categorically the grade converts.

**Closure (must land pre-merge):** replace the city/state token in that one
fixture with the invented placeholder the module docstring already uses, and
re-run the shared scan. The test asserts a transaction count and a
space-inside-a-card-date; the description token is inert to it.

**The other four hits are not defects.** Two are a bigram the record's own
English prose forms at W3 §CPS7/§CPS10.3, where the card name CPS-AMOUNT is
followed by an ordinary modal verb and the pair collides with template
wording — a false positive of the bigram class. Two are the
platform's own no-deposits disclosure heading, quoted at §CPS10.1 item 2 and
§CPS10.7 to state a real finding about the ledger-section guard; that is
institution/template furniture, which the card admits — but the record does
not label it as furniture, and should.

### F2 — MAJOR — the branch's privacy headline does not reproduce, and the committed instrument is why

**Claim under test:** §CPS11.4's `hits: 0`, produced by
`tools/cpscan_privacy_grep.py`, and its self-defence "the instrument is not
blind".

**Evidence:** on the *identical* population (the 19) and the *identical*
committed diff (`added_diff_lines` 1884 in both tools), the cell's instrument
reports `hits: 0, hit_locations: []` (exit 0) and the shared instrument
reports 5 (exit 1). Two independent scans, one population, opposite answers.

**Root cause, demonstrated on a synthetic all-caps line (no archive text):**

* `cpscan_privacy_grep.NAME_PHRASE` is
  `\b[A-Z][A-Za-z&'.-]+(?: [A-Z][A-Za-z&'.-]+)+\b` — greedy. On an all-caps
  OCR run it returns ONE mega-token spanning the whole run, so no shorter
  fragment of that run is ever tested against a diff line;
* `LONG_WORD` has an 8-character floor, and a seven-letter place name falls
  under it.

The two classes therefore cannot see a short place name embedded in a longer
capitalised run — exactly the shape F1 leaked. The instrument's own leak-probe
self-check does not exercise that shape, so its "not blind" proof is
narrower than the claim it supports.

**Closure:** the shared instrument is the standing one from batch 8; the
record's privacy count must be ITS count, and `tools/cpscan_privacy_grep.py`
should be marked superseded (or its phrase class made non-greedy and its word
floor lowered) rather than left as a committed instrument producing a headline
number that the standing tool contradicts.

### F3 — MINOR — §CPS9's refusal-site arithmetic is wrong; its substance is right

**Claim under test:** "48 of the 49 traced sites shift by the constant offset
this branch's docstring edits add (+64 in the sectioned module, +27 in the
daily one)" and "`core_processor_sectioned:751 -> core_processor_sectioned:824`".

**Evidence:** the sectioned module grows by exactly **74** lines
(`git show 10cc722:… | wc -l` = 781, `git show wave8-cpscan:… | wc -l` = 855);
the daily module by 27. My own in-process tracer (the census's own
`RefusalTracer`, both trees loaded from git blobs in one process, all 59
documents) returns offsets `{74, 83}` for the sectioned module and `{27}` for
the daily one, over 49 differing sites:

| base site | branch site | offset | documents |
|---|---|---:|---:|
| `core_processor_sectioned:727` | `:801` | 74 | 8 |
| `core_processor_sectioned:751` | `:825` | 74 | 13 |
| `core_processor_sectioned:751` | `:834` | **83** | **1** |
| `core_processor_sectioned:762` | `:836` | 74 | 10 |
| `core_processor_daily:746` | `:773` | 27 | 4 |
| `core_processor_daily:765` | `:792` | 27 | 13 |

`+64` is wrong (it is `+74`), and `:824` was evidently derived as base 760 +
64 rather than read off the tracer: base line 760 is the grid gate's `return`
and its branch line is **834**. The SUBSTANCE reproduces exactly — 49 sites,
48 at the module's constant offset, and exactly one document changing gate:
`9AACD085` from the summary gate to `_matches_the_printed_grid`. The base
site counts also reproduce §CPS2's table (14 at `:751`, 8 at `:727`, 4 at
daily `:746`).

**Closure:** correct `+64` → `+74` and `:824` → `:834` in W3 §CPS9.

### F4 — MINOR — the leading-zero class's positional argument is stronger in the record than in the code

**Claim under test:** "`_LEADING_ZERO` is admitted ONLY in the leading
position of a two-character month or day, and that restriction is what makes
this a reading rather than a repair."

The positional restriction is real and correctly implemented — `1o/12`,
`o0/12`, `oO/12`, `03/o0` are all refused, and the substitution table is
value-total over the tokens the class can produce. What the record's argument
does NOT establish is that the admitted position can only hold a digit.
`_TOKEN_START` refuses only `[0-9A-Za-z.,/|]` before the token, so a
**word-initial** zero-shaped letter is admitted. Adversarial probes at the
branch tip, refused at base, matched by `_ROW_RE` in full:

| synthetic text | base `_ROW_RE` | branch `_ROW_RE` |
|---|---|---|
| a capital-O initial then digit/slash/digit then a cents figure | no match | **matched as a row** |
| an all-caps word ending in a capital O, spaced, then the same shape | no match | **matched as a row** |
| the same shape with a lower-case glyph | no match | **matched as a row** |

Intra-word cases (`…Oo3/12`, `NO3/12`, `AUTO3/12`) are correctly refused —
the boundary holds there.

So what actually prevents an invented row is not positional exclusivity: it
is the row grammar (whitespace then a cents-bearing figure, inside a named
ledger section) plus the five printed checks, where an invented row shows up
as a POSITIVE count delta and the document refuses. That is fail-closed and
adequate — but it is defence in depth, not the bound the record claims, and
the module docstring should say so.

**Reachability, measured over all 39 documents of the template:** 154
admitted tokens, 0 elsewhere — see §3. No published document carries one.

**Closure:** restate the bound honestly in the module docstring (the mark is
read as a zero on the assumption that it IS one; the printed count check is
the guard against the assumption being wrong), or additionally require
whitespace/line-start before the glyph.

### F5 — MINOR — the vertical-bar exclusion narrows more than the record says

`_TOKEN_START` is shared by `_DATE_TOKEN`, `_FIGURE_TOKEN`, both
`_balance_row` patterns and the **optional count prefix** of `_count_row`.
Adding `|` therefore also refuses a summary figure or a summary count printed
against a bar. §CPS6 describes the change only as a date-boundary closure.

Every reachable consequence is conservative: a lost row goes invisible and the
count check refuses; a lost count makes the count absent, and `_counts` admits
an absent count only against a zero total, so the document refuses. There is
no construction where the bar exclusion publishes something wrong.

**Reachability, my own measurement over all 39 sectioned documents:** **0**
date tokens and **0** figure tokens preceded by `|`, `I`, `l` or `!`. This
independently confirms §CPS6's "0 of 4,123" and "0 of 5,849".

**Closure:** one sentence in §CPS6 naming the other three patterns the class
feeds.

### F6 — MINOR — two mutants in the table do not isolate what they are named after

`M04_sectioned_month_bound_removed` replaces `_ROW_MONTH` with `[0-9]{1,2}`
and `M05` does the same to `_ROW_DAY`. That drops `_LEADING_ZERO` from the
field as well as the calendar bound, so neither mutant tests the bound alone —
the record's own kill list shows it ("and both glyph cases"). The isolated
mutant, glyph KEPT and bound removed, is not in the table.

I built it as an ablation and ran it over the full 135-document population:
**0 documents moved, 0 leaves moved**. Nothing is hidden behind the imprecision
on today's archive; the table simply over-claims coverage of the bound.
(The suite does cover it: `test_a_token_no_calendar_can_hold_is_not_a_date`
with an impossible month would fail under the isolated mutant.)

**Closure:** add the isolated mutant, or rename M04/M05 to say they are
compound.

### F7 — MINOR — the two sibling readers now disagree about the same glyph, with nothing pinning the divergence

`core_processor_sectioned` reads `o`/`O` as a leading zero;
`core_processor_daily` deliberately refuses it, on the measured ground that
its own 20 documents print none. Both docstrings say so, which is good — but
no test in either module asserts the divergence, so a future edit to either
reader can silently converge them, and the daily module's own
`test_a_letter_look_alike_in_a_date_is_refused_rather_than_absorbed`
docstring still names the lower-case leading-zero glyph as something it
refuses without pointing at the sibling that no longer does.

**Closure:** one grammar-level test per module asserting the other's choice,
or a shared comment naming the sibling.

## 3. Blast radius, per hunk

Population: **135 documents** — every document the run of record dispatches or
attempts to `core_processor_sectioned`, `core_processor_daily` or their
superseding siblings `first_farmers` / `b1` (**59**, derived independently from
the run's own `parser_id` + `attempted` columns: 39 sectioned-side, 20
daily-side, overlap 0), plus the **80** pinned documents of the 109 that the run
of record covers — which include **all four** pinned documents of this complex
(1 `first_farmers` scanned/local_ocr, 3 `b1` digital/native). Text resolved once
per document by the census's own proven-artifact rule: 135/135 resolved, 0 with
no OCR artifact, 0 with an unproven text choice. Payload =
`analysis.pipeline.analyze_markdown(..., parse_mode="deterministic", sheets=…)`
→ `report_to_dict`, compared leaf for leaf.

| hunk | ablation applied to the branch tree | documents moved | leaves moved | exception changes |
|---|---|---:|---:|---:|
| H1 the leading-zero glyph | `_LEADING_ZERO` → `[0]` | **0** | **0** | 0 |
| H2s the sectioned calendar bound | month/day bound removed, glyph kept | **0** | **0** | 0 |
| H2d the daily calendar bound | `_ROW_DATE` → the base blob's form | **0** | **0** | 0 |
| H3 the vertical bar | `_TOKEN_START` → the base blob's class | **0** | **0** | 0 |
| all three (base blobs) | base vs branch | **0** | **0** | 0 |

2,472,199 leaves compared per pair. Reproduced twice, in two independent
processes, on two different host loads.

**Detection cannot move, structurally.** Neither module's `DETECTION_MARKERS`
references a changed constant: the sectioned detector is `_PERIOD_RE` (built
from the untouched `_SHORT_DATE`, and carrying no `_TOKEN_START`) plus two
literal labels; the daily detector is the untouched `_LONG_DATE` label
patterns. So the claimed-by population is fixed by construction, and measured:
**59/59 identical in `claimed_by`, `dispatch_outcome`, `dispatch_parser_id`,
`dispatch_attempted` and `dispatch_crashed`**, base vs branch, one process,
base modules from git blobs.

**Where the 154 rows live, and why nothing publishes.** Measured with my own
token instrument over the section runs `_sections` returns, on all 39
sectioned-side documents:

* **154 `_ROW_RE` matches carrying a zero-shaped letter, on exactly 10
  documents** — reproducing §CPS4's headline to the row;
* **0 rows matched at base and lost at branch** on any of the 39, which is
  §CPS4's "no row or grid cell matched under the old form and fails under the
  new one";
* every one of the 10 is `failed` in the run of record and `unclaimed` at the
  branch tip. Nine of the ten are inside the named 19
  (`0808DD1E` 1, `337FE9AA` 49, `3E907CEF` 30, `627D9AE3` 6, `8AD19431` 11,
  `8CC3F492` 1, `9AACD085` 3, `9FD4C16E` 18, `DCF3A85E` 34); the tenth,
  `586B9481` (1 row), is the digital document the record itself names in risk
  2. **None of the 29 documents this registration and its superseding sibling
  publish carries one.**

That is the answer to the review's own question: the rows the base reader was
dropping live entirely on documents that decline for other printed reasons,
so no published payload can change — and `9AACD085` is the proof, because
with its three glyph rows read the printed credit count, debit count, credit
total and debit total all close and only the grid disagrees (§4 below).

**The 4 daily fragments:** 4 date tokens matched at base and refused at
branch, on 2 of the 20 daily documents (`0FFA1DA3` 1, `DE92B503` 3), both
`failed`; 0 tokens gained. Reproduces §CPS5.

**The bar:** 0 of 39 documents carry a date or figure token preceded by
`|`, `I`, `l` or `!`.

**Does the calendar bound drop a real posting date?** No, and it cannot hide
a missing page. `posting_dates_cover_source` in `analysis/adb.py:741` is
`not (source_dates - parsed_dates)`, and `source_dates` comes from
`analysis/dates.py`'s own digit-only token grammar, independent of either
reader. A reader that parses FEWER dates can only grow the missing set — the
check goes from passing to failing, never the reverse. Measured: 0 real
calendar fields lost on either template (every `mm/dd` and `mm-dd` matched at
base is matched at branch).

## 4. The nineteen, and the ceiling

`python -m tools.cpscan_ceiling` at the branch tip over the 19 — **exit 0,
`documents 19`**. The 19 reproduce sha-prefix for sha-prefix against §CPS3.1
and §CPS3.2, derived independently from the run's own columns (the 27 refused
documents of the complex, restricted to non-digital: 18 scanned + 1 mixed).
All nineteen are `unclaimed` at the branch tip with an empty `crashed` list —
**ceiling 0 of 19 confirmed** — and each carries at least one named printed
check that disagrees:

| document | template | printed checks that disagree at the branch tip |
|---|---|---|
| `0808DD1E` | sectioned | debit total, grid |
| `0FFA1DA3` | daily | unreadable section, credit total |
| `2FC2A756` | daily | unreadable section, credit total |
| `337FE9AA` | sectioned | credit count, debit count, both totals, grid, grid missing |
| `3E1F4145` | sectioned | debit total, grid |
| `3E907CEF` | sectioned | credit count, debit count, both totals, grid, grid missing |
| `627D9AE3` | sectioned | credit total, grid |
| `7088F591` | sectioned | credit count, debit count, both totals, grid missing |
| `790B4EA8` | daily | unreadable section, credit total |
| `8035EE1A` | sectioned | summary unread (the `first_farmers` running-balance refusal) |
| `8AD19431` | sectioned | debit count, debit total, grid, grid missing |
| `8CC1F233` | sectioned | debit total, grid |
| `8CC3F492` | sectioned | credit count, debit count, both totals, grid, grid missing |
| `95246AAF` | sectioned | credit total, grid |
| `9AACD085` | sectioned | **grid and grid missing only** |
| `9FD4C16E` | sectioned | credit count, debit count, both totals, grid, grid missing |
| `DCF3A85E` | sectioned | credit count, debit count, both totals, grid, grid missing |
| `DE92B503` | daily | unreadable section, both totals |
| `EF1C5806` | sectioned | summary unread (CPS-ZEROTOTAL) |

`9AACD085` is the one row that carries the branch's whole argument, and it
holds: with the glyph rows read, all four printed summary checks close and
only the grid disagrees. That is §CPS4's proof, re-measured.

**Privacy of the instrument:** its JSON output was scanned for archive
literals — **0 money-shaped tokens, 0 date-shaped tokens, and 0 digit runs of
five or more once the `content_sha256` values are excluded**. It DOES report
row counts and grid-day counts, deliberately and with an explicit docstring
justification; the review brief's "no row-count" is stricter than both the
wave's standing rule and the record's own §CPS3 tables, and I record the
difference rather than scoring the tool for it.

## 5. Mutation

`python tools/cpscan_mutate.py .` at the tip — **exit 0, `BASELINE failures:
[]`, 18 mutants, 18 KILLED, 0 SURVIVED**, run without `-x`, every killer named.
`git status --porcelain` empty immediately afterwards inside the harness's own
subshell and again after.

Every mutant was read against its documented description; all eighteen apply
what they say (F6 is the one imprecision). Four hand-checked to the reason
their row states:

* **M02** (the boundary hole) — widens `_LEADING_ZERO` to `[0oOlI|]`. Killed by
  the three grammar cases of `…one_shaped_letter_is_not_admitted_by_the_zero_class`
  **and** by `…pattern_and_the_reading_admit_exactly_the_same_letters`. Both
  are the stated reason: the pattern would admit a one-shaped mark (a December
  row read in February) and the pattern would drift apart from the translation
  table. Verified against the grammar directly: with `l` in the class,
  `_DATE_TOKEN` matches a space-preceded `l2/12`.
* **M17** (bar back out) — killed by exactly ONE case, the bar case, and by
  nothing else. The letter cases still die on the letter class. A single-cause
  kill is the strongest evidence the test tests the bar.
* **M18** (asterisk added) — killed by exactly the serial-gap test and nothing
  else: with `*` in the class the platform's own sequence-gap cheque row goes
  invisible and the count check refuses, so `parse` returns None.
* **M14** (normalisation removed, `return token`) — killed by exactly the two
  glyph cases and NOT by the pattern/reading-equality test, which is correct:
  the class is unchanged, and the failure is one layer down in
  `iso_within_period`, which splits on `/` and requires digits.

M02's first-run survival is recorded honestly in §CPS6 and the harness's own
comment, and the lesson (a behavioural test firing through the translation
table instead of through the class) is the wave's standing one.

## 6. Record accuracy

Verified, independently:

* **59 = 39 + 20, overlap 0**, and 32 published (10 sectioned + 6
  `first_farmers` + 13 daily + 3 `b1`) / 27 refused — all from the run's own
  `parser_id` and `attempted` columns, matching §CPS2 exactly;
* **the 19**, sha-for-sha against §CPS3.1/§CPS3.2, all `failed` in the run;
* **the 154 on 10 documents**, and **0 rows lost** — reproduced to the row;
* **the 4 fragments on 2 documents** — reproduced;
* **the 1,808**: `python -m tools.descattrib_movement` over the 59 at the
  branch tip — `documents 32, rows 1808, moved_descriptions 0, shortened 0,
  lengthened 0, replaced 0, other_movement 0, no_payload 27`, **EXIT=1**. The
  exit code is the tool's own `1 if other_movement or no_payload` contract
  firing on the `no_payload` arm (the 27 refused documents have no stored
  payload), exactly as §CPS9 explains; `other_movement` is 0;
* **the suite count**: 5,857 + 37 = 5,894, and the diff adds exactly 37 net
  test cases (daily +12; sectioned +26 added, 1 removed). The void run's
  `3 failed, 5891 passed` sums to the same 5,894, so §CPS11.5's void run is
  honestly recorded and internally consistent;
* **the five sweep chunks add**: 700+700+700+700+580 = 3,380 documents with
  contiguous non-overlapping ranges; 523+531+529+531+444 = 2,558 compared and
  identical; 172+164+165+163+129 = 793 refused-again; 5+5+6+6+7 = 29 with no
  OCR artifact; 2,558 + 793 + 29 = 3,380; 13+18+16+16+11 = 74
  multi-artifact; seconds 7,126.2. And 2,558 = the run's 2,469 validated + 17
  review + 72 withheld; 793 + 29 = its 809 failed + 13 deferred. Arithmetic
  only — I did not re-run the sweep;
* **the guard set**: 252 passed, exit 0, re-run;
* **registry 75**, unchanged, measured in both trees.

Wrong: §CPS9's `+64` and `:824` (F3). Not labelled: the furniture bigrams (F1).

## 7. Re-run table

Run from `.claude/worktrees/mt8-cpscan` unless noted; archive and run of
record read-only by absolute path in the main checkout; `parse_mode
="deterministic"` throughout; no OCR, no sqlite index, no hosted model, $0.

| # | what | exit | wall |
|---|---|---:|---|
| a | `python -m pytest -q tests/test_core_processor_sectioned.py tests/test_core_processor_daily.py` — 229 passed | 0 | 0.9 s |
| b | A/B replay, 6 variants × 135 documents, one process, base modules from git blobs (own instrument) | 0 | 990.3 s (183.8 / 165.8 / 178.0 / 151.0 / 158.8 / 152.9) |
| b2 | the corrected calendar-bound ablation, 3 variants × 135 (re-run after my first ablation was found malformed) | 0 | 239.7 s |
| b3 | dispatch + refusal sites, base vs branch, 59 documents, one process (census `RefusalTracer`) | 0 | < 45 s with b4 |
| b4 | token measurement over the 59 (the 154, the 4, the bar) | 0 | < 45 s with b3 |
| c | `python -m tools.cpscan_ceiling … --sha-file <19>` — `documents 19` | 0 | 1 s (warm) |
| d | `python tools/cpscan_mutate.py .` — 18 KILLED / 0 SURVIVED, tree clean after | 0 | ~95 s |
| e | `python -m pytest -q` over the 5 canonical guard files — 252 passed | 0 | 11.8 s |
| e2 | `python -m tools.descattrib_movement … --sha-file <59>` — 32 / 1,808 / 0 moved / 27 no_payload | 1 (contract) | 16.8 s |
| f | `tools/privacy_scan_branch.py --rows … --where parser_id=core_processor_sectioned,core_processor_daily --shas <19> --base 10cc722 --ref wave8-cpscan` — population 42, 5 hits | 1 | ~40 s |
| f2 | the same, population scoped to the 19 only — the same 5 hits | 1 | ~30 s |
| f3 | `python -m tools.cpscan_privacy_grep …` on the same 19 and the same committed diff — `hits: 0` | 0 | ~35 s |

`git status --porcelain` empty before and after every run, including after the
mutation harness. Nothing was written to the archive, no artifact was created,
no OCR ran, no hosted model was called.

**One measurement of mine was wrong and is withdrawn:** my first
"calendar bound removed" ablation was malformed (it also restricted the day
field to a leading-glyph form), and it reported nine documents raising. Rebuilt
correctly (row b2) it moves nothing, and `iso_within_period` returns `None`
rather than raising on every impossible field I probed. The nine-raise result
is an artifact of my patch and says nothing about the branch.

## 8. Privacy re-measurement (mine)

* The shared instrument over the branch's committed diff, population 42 (the
  23 documents the two readers publish plus the named 19) and again over the
  19 alone: **MONEY 0 · DATES 0 · DIGITS 0 · WORDS 5**. Four of the five are
  prose/furniture collisions (F1); one is the fixture leak (F1, MAJOR).
* `tools/cpscan_ceiling.py`'s own JSON output: 0 money-shaped tokens, 0
  date-shaped tokens, 0 digit runs ≥ 5 excluding `content_sha256` values.
* **This review file:** contains no amount, no balance, no date, no account or
  reference number, no merchant, customer, city or institution name, and no
  archive-sourced literal of any kind. Documents are named by 8- and
  12-character `content_sha256` prefixes; magnitudes are counts. The leaked
  fixture token in F1 is described, never quoted. Measured: the shared
  instrument re-run with `--ref` at this review's own commit adds **0 hits**
  in every class from this file (an earlier draft added two of the same prose
  bigram as the record's, and was reworded).

## 9. Claims I could not verify

Out of scope for a light review, taken on the record's own logs:

* the full default suite (`5894 passed, 35 skipped, 34 deselected`, 294.89 s,
  exit 0) — the +37 arithmetic checks out and the void run's numbers are
  internally consistent, but I did not run it;
* the corpus-marked slice (30 passed, 3,553.97 s, exit 0);
* `python corpus_gate.py` GREEN 105 PASS / 3 WITHHELD / 1 REFUSED with the
  currency and provenance surfaces — I replayed the pinned documents
  read-only instead (row b), which moves nothing, but that is not the gate;
* the canonical conformance set (1,164 passed);
* the whole-archive 5-chunk sweep — arithmetic checked line by line, not re-run;
* `tools/cpscan_census.py`'s whole-archive figures (3,380 documents, 29 with
  no OCR artifact, 0 unproven text choices). Over my 135 the same rule gives 0
  unproven and 0 missing, and the 59 membership reproduces from the run's own
  columns, but I did not replay detection over all 3,380.

## 10. The cell's own findings and risks, relayed

**Findings for Ocean (§CPS10).** *CPS-ZEROTOTAL* (Gustavo's call): one mixed
document prints a zero-activity statement whose two count rows carry a total
with no decimal point; the archive attests the platform's zero form WITH the
point on two other documents, so reading it is a repair and the cell did not
make one — bundled with two further questions, whether a statement may publish
with no ledger section, and what the ADB doctrine says about a period with no
transactions and no grid. *CPS10.7*, its sibling: `parse`'s ledger-section
guard is satisfied by a section name printed inside a disclosure, so the guard
is weaker than it reads (no document publishes through it today).
*FF-SCAN-BALANCE* (card): one `first_farmers` document refuses because the
scan rendered a running-balance cell as letters; the reader is right and the
module is not this card's. *closing CPS-AMOUNT as not-doable*
(ruling requested): the printed summary, counts and grid do localise every
discrepancy to one row on one day, and on one document the section's own
ascending sort names the row outright — but proving the scan is wrong is not
knowing what the bank printed, and acting on it means writing an amount, which
the repair doctrine forbids. *CPS-SERIAL* (card): the sectioned reader's
cheque-serial read is the end-anchored defect `core_processor_daily` already
closed in §GRAM4; unreachable on today's ten published documents but reachable
on a refused one, and the honest fix lifts a helper into `analysis/tables.py`,
which DESC-COLUMNS owns this batch. *SN3 row 7's ceiling is 0, not ≤4*
(roadmap correction): three of the four `lake_city` scans print no readable
daily-balance heading and this template requires the grid, so no date-grammar
change can publish them. *CPS10.6*: `date_tokens.iso_within_period` admits on
`str.isdigit()` then calls `int()` — the standing fail-open shape — measured
unreachable from either of this card's modules, recorded for whoever owns that
file next.

**Risks carried (§CPS13).** The glyph class is a widening that moves nothing
today and is a two-line revert if a reviewer wants it out. One DIGITAL
document outside the named population (`586B9481`) changes measured state but
not outcome, named so CORE-ISSUES-2 is not surprised. Both files are shared
with CORE-ISSUES-2 and DESC-COLUMNS, so if the train orders `tables.py` work
first the family replay should be re-run rather than assumed. The refusal-site
tracer is a diagnostic, not a contract — line numbers move whenever a
docstring does (F3 is that risk realised in the record's own text). And the
ceiling of 0 is a statement about today's OCR rather than about the documents:
eleven of the fifteen sectioned refusals would publish from a better scan.

I agree with all five risks as stated, and I would add F4 as a sixth: the
glyph class's safety rests on the printed count check, not on the position
alone, so any future change that weakens the count check weakens the class.

## 11. What must happen before the train

1. **F1** — the fixture literal replaced with the invented placeholder, and the
   shared scan re-run.
2. **F2** — the record's privacy count restated from the shared instrument, and
   `tools/cpscan_privacy_grep.py` fixed or marked superseded.
3. **F3, F5, F6** — three corrections to the record's text; no code change.
4. **F4, F7** — one docstring sentence each; no behaviour change.

Nothing in this branch moves the archive, and I found no defect that could.
