# Independent adversarial review — Phase 2.2 cell T (`P22-TRUTHTABLE`)

```
REVIEWER   REV22-TRUTHTABLE — independent; wrote none of this code
BASE       b7af37b   train12 0d2c99c + K + C + H composed + F closure-1 5c59524
TIP        01ab992   tree 45f4e2b765499d06c37ee478389d1981546cdd0f; 12 commits; 27 files, +5,294 / -57
WORKTREE   .claude/worktrees/rev22-truthtable  (fresh, detached at 01ab992)
LOCK       discovery_reports/train12-logs/HARNESS.lock  held 19:01:12 -> 19:54:16 (2026-09-10)
LOGS       discovery_reports/train12-logs/rev22-truthtable/  (MASTER.log + one log per step, each ending EXIT=)
VERDICT    APPROVE WITH FINDINGS  (7 MINOR; 0 BLOCK; 0 MAJOR)
```

## Verdict

**APPROVE WITH FINDINGS.** Every load-bearing property held under attack rather than
under reading: the classifier cannot reach a verdict; the research partition cannot
be selected by a production replay; the research trigger cannot be supplied outside
research mode by any shape I could construct; `refused` does not weaken the
validated-protection rule; both denominators print with the raw one first; the
taxonomy matches §D.4 code for code with drift guards that fire; the geometry seam
is inert when `off` **and** reachable when not; the union replay reproduces
payload-identically at my own hand. 17/17 of the cell's mutants die in my worktree
with the killers it names, and 8 of my 9 fresh mutants die. The seven findings are
all MINOR: five are mechanisms narrower than the prose describing them (zero
population today), one is a missing witness my fresh mutant N4 exposed, one is
documentation drift.

---

## Findings

### MINOR-1 — `refuse_production_data_dir` accepts a directory **inside** the live production cache

The docstring says the door refuses a `--data-dir` that "is (or is **inside**) a
production or historical cache" and lists "anything named `webapp_data` or
`webapp_data_train<N>_cold`, wherever it sits". Containment is enforced only for
`.claude/recovery/**`.

```
$ python <scratchpad>/probe_datadir.py       # cwd = the review worktree
  'webapp_data' / 'WEBAPP_DATA' / 'WebApp_Data'                            -> refused
  '.claude/recovery/webapp_data_train11_cold'  (fwd and back slash)        -> refused
  'D:/scratch/webapp_data_train9_cold'  (relocated cold cache)             -> refused
  '.claude/recovery/anything_else'                                         -> refused
  './webapp_data', 'some/../webapp_data', 'webapp_data/'                   -> refused
  --- INSIDE the live production cache ---   'webapp_data/research'        -> ACCEPTED
  --- deep inside the live cache ---         'webapp_data/ocr/partition_x' -> ACCEPTED
  --- inside a relocated cold cache ---      'D:/.../train9_cold/sub'      -> ACCEPTED
```

No exposure today: every cold cache on this host is under `.claude/recovery/`
(covered), and a research run is partition-keyed so it could not overwrite a
production entry. But the code delivers less than the docstring and the W3 claim.
Fix: one loop over `resolved.parents` applying `_PRODUCTION_DATA_DIR_NAMES`.

### MINOR-2 — `telemetry/report.py` never renders the `refused` class

`telemetry/report.py` is on the card's exact ownership list and was left untouched.
Its `render()` iterates a hardcoded five-key outcome block, so a `refused` record is
counted in `summary["outcome"]` and printed nowhere. Case 10 requires "`refused` in
every vocabulary".

```
$ python -c "<build_record(..., refused='not_a_statement'); render(summarize([r]),'r')>"
outcome: refused not_a_statement
summary[outcome]: {'refused': 1}
rendered outcome block: ['outcome', 'reason', '  not_a_statement  1  100.0%', 'source path   none 1']
the word refused appears in the report: False
```

Population 0 in 2.2 — the class is RESERVED and nothing produces it (the only
`refused=` producers in the tree are `ocr.escalation.Escalation.refused`, an
unrelated pre-existing field, and `tools/train/winrun.py`). One-token fix at
`telemetry/report.py:258`.

### MINOR-3 — the holdout-before-population ORDER is documented and unwitnessed (my fresh mutant **N4 SURVIVED**)

`process()` checks the holdout cage before population membership, and says why: "a
holdout sha that also happens to be outside the population must still be refused as
a holdout rather than dismissed as an omission". The only test of that branch builds
a runner whose sha is in **both** sets, so swapping the two blocks changes nothing it
observes.

```
N4: SURVIVED - killers (none) (0 failing, exit 0)
    mutant: the two per-document research doors swapped in discovery/runner.py
    log: discovery_reports/train12-logs/rev22-truthtable/rev22-freshmutants.log
```

This matters more than "population zero" suggests: the CLI refuses any population
intersecting the holdout digest **at the door** (exit 2), so the only way the
runner's holdout branch is reached in a real run is with a sha *outside* the
population — exactly the case the order protects and the suite does not witness. A
one-line fixture change closes it.

### MINOR-4 — "L6 UNKNOWN … never nulled" is not enforced by construction

`diagnose_unresolved` can return a diagnosis with all seven layers empty and an
empty primary pair, for a non-validated row whose outcome reason maps to `None` and
whose class is outside `DIAGNOSABLE_CLASSES` (`('withheld','review')`):

```
NULLED primary (no layer at all) for 20 pairs, e.g.
  ('failed','withheld_adb'), ('failed','approved'), ('deferred','quality_needs_review'),
  ('refused','approved'), ('unknown','integrity_flags'), ...
```

Population 0 and unreachable today — `classify_outcome` pairs each of those five
reasons with a diagnosable class, and my measurement shows all 755 with a non-empty
primary layer. But the module's stated property rests on a coincidence in
`telemetry/record.py` rather than on a closing
`if not primary_layer: codes["l6"] = UNMAPPED`.

### MINOR-5 — `stage_extract` folds "nothing was attempted" into `none`

`STAGE_VOCABULARY["stage_extract"]` declares both `not_attempted` and `none`, and
`_project_funnel`'s docstring says `not_attempted` "is never overwritten by a guess
… 'no reader was asked' and 'readers were asked and none claimed' are the two facts
this funnel exists to keep apart." For extraction it does not: `DocumentRow.
source_path` defaults to the literal `"none"`, so `not_attempted` is unreachable on
that column once `_project_funnel` runs (a profile-only row records `none`).
Measured, the funnel's `none 29` decomposes as:

```
('deferred','deferred_visual_ocr') 13   <- the ladder ran and produced nothing: 'none' is right
('failed','invalid_pdf')           16   <- refused before any read: 'not_attempted' is honest
```

16 of the 29 are mislabelled, and every row of a `--profile-only` run would be.
`stage_evidence` gets the same distinction right.

### MINOR-6 — the `psutil` branch of `peak_rss_mb` is dead in every environment that exists

`requirements-local.txt`'s own comment says "both branches are tested". `psutil` is
neither installed on this host nor in `requirements.txt` (so not in CI):

```
$ C:/Python314/python.exe -c "import psutil"    ->  No module named 'psutil'
$ peak_rss_mb()                                 ->  'not measured'
```

The degraded value is honest and the test handles both arms conditionally, but the
measuring arm has never executed anywhere, and case 25's per-document memory column
ships inert — including on the next cold run. Separately: the column is named
`peak_rss_mb` (the card's name) while the code reads the process's *current* RSS at
`_finish`, not a per-document peak; the docstring says so, the column name does not.

### MINOR-7 — three documentation / number drifts

* `tools/truth_report.py`'s usage block documents a `--digest <MANIFEST_DIGEST>`
  option the parser does not define (only `--rows` and `--out` exist).
* The W3 §Risks says "the **656** documents at `B0_no_reader_claimed`". The
  measurement it cites gives that code **223** as a primary and **537** as an l3
  occupancy; **656** is `stage_candidate unclaimed` / failure class B over the whole
  archive. Three populations, one number.
* The W3 proof-floor table reports **9,799 passed**. That run
  (`p22truthtable-proofs.log`, ~16:35) predates the cell's own last code commit
  `60617bd` (16:45, the M11 test fix: a 2-value parametrize dimension over 5 modes =
  +5 cases). At the actual tip the figure is **9,804 passed / 0 failed** (my re-run).
  The gate, corpus slice, guards and conformance were taken at the same superseded
  tree; `60617bd` touches only `tests/test_research_mode.py`, so none can move, and I
  re-ran the gate and the guards at the tip to confirm.

---

## The attack list, item by item

**1 — a classification label reaching a financial verdict. HELD.** I grepped every
`analyze_document` / `cached_analysis` site under `discovery/` and every read of
`document_class` / `class_*` / `completeness_findings` / `reason_l*`: the nine
classifier columns are written in `_project_classification` and read by nothing.
The guarantee is structurally stronger than the card asked for — `_finish` runs at
the row's single exit, *after* `analyze_document` has returned. The cell's identity
test spies on the real `analyze_document` (recording the entry *before* the call, so
a raising analysis is still compared) and asserts
`kwargs == ["on_dispatch","parse_mode","sheets"]` with the classifier live and with
it stubbed to raise. M6 dies.

**2 — the research partition selectable by a production replay. HELD.** I
re-derived the OCR settings key at the tip for three production shapes; in each, the
field ABSENT and the field EMPTY give the same key (`3B7EC879…`, `5DB76E4E…`,
`F968473B…`) and a partition changes it. The production call is byte-identical to
one that never heard of the field — which is why the union replay is identical.
`telemetry/run_of_record.py` is untouched; its refusal is cell K's and is exercised
end to end by `test_cli_end_to_end_writes_a_research_run_that_run_of_record_refuses`.

**3 — the research trigger startable outside research mode or by a verdict. HELD.**
`RESEARCH_TRIGGERS` is a module-level `frozenset` of one, assigned once, pinned
three ways (constant shape; single `ast.Name` use; no `decide(` site naming it
inline) plus a tree-wide scan asserting only `discovery/runner.py` and
`telemetry/record.py` spell the trigger at all. M10 and M11 die. I wrote **N9**, a
fresh shape built to slip both `ast.Name` pins — the trigger assembled from a
*string literal* at a second site inside the allowed module, admitted in
`--scanned-paddle`. It does escape both AST pins, and is killed by the behavioural
pin `test_no_other_mode_can_supply_the_research_trigger`. A second *module*, or the
constant shadowed elsewhere, is caught by `_research_trigger_mentions()`. No verdict
or failure class feeds the trigger: `self.research` is a mode attribute set in
`__init__`.

**4 — the four doors of research mode. HELD except MINOR-1.** Both literals are
checked FIRST — before the required-argument check, the data-dir check, the
population read, corpus enumeration and the toolchain probes — and the refusal
prints the variable NAMES, never their values. A missing population, a malformed
partition, a production `--data-dir` and a population intersecting the holdout
digest each exit 2; the holdout refusal prints only the COUNT. Per document, both
doors precede any read (`_read` / `_read_paddle` monkeypatched to raise). Test
hermeticity is real: `_unconfigure_paddle` blanks every `PADDLE_*` name in
`os.environ` plus a fixed list, so the checkout's gitignored `.env` cannot leak in,
and the subprocess test builds its env from scratch. The synthetic end-to-end proof
is genuinely in-process and network-free: `tests/paddle_fake_worker.FakeWorker`
binds loopback, the run makes exactly 2 requests for 2 one-page population
documents, rows carry the partition, a second pass is served from the partition's
own cache, and `run_of_record` refuses the finished run. My 14-spelling
`--data-dir` attack found only MINOR-1.

**5 — `refused` weakening the validated-protection rule. HELD.**

```
validated -> refused/deferred/unknown/failed/withheld/review  = regressed (all six)
failed/withheld/review  <->  refused                          = unranked  (both directions)
LADDER ('failed','withheld','review','validated') unchanged; UNRANKED ('deferred','unknown','refused')
matrix: every row has every column, zeros included; an outside class raises ValueError
```

`RawDenominatorMismatch` compares `len(Run)` = **distinct content shas** (verified:
`Run.__len__` returns `len(self.documents)`, keyed by content sha) and exits **3**,
distinct from the regression exit 2, in both `discovery/compare.py` and
`tools/train8_compare.py`; both print the matrix and both denominators.
`classify_failure`'s vocabulary is untouched; `REFUSED_REASONS` is closed with no
producer anywhere in the tree; zero `refused` rows on the run of record (measured).
M3, M4, M5 die, as do my fresh N1 (drop the `unknown` **row**) and N6 (`refused`
ranked into the ladder).

**6 — two denominators (R11/R12). HELD.** The firewall grep over
`analysis/ layout/ ocr/ evidence/ discovery/ webapp/ telemetry/` for
`SEALED_TRUTH_DIR` / `tools.holdout` returns nothing. The runner names
`ccl_adjudicated: not available in this process` rather than printing a proxy; `raw
coverage` precedes both CCL lines (asserted by line index; my fresh N7, moving the
ccl line above it, dies). `tools/truth_report.py` does the join, labels every
document `adjudicated` or `classifier_proposed`, prints aggregates only, and refuses
a non-git-ignored `--out` (`docs/**` and `README_leak.md` both refused). I attacked
the exception-message route: every `raise` in `tools/holdout/store.py` names a record
**index**, a field **name** or a path — never a sha with a verdict — so
`read_store()`'s `f"...{exc}"` note cannot leak one. Card / loan / brokerage are
separate rows in both instruments. M8, M17 and my fresh N2 (raw denominator counting
rows) die.

**7 — the taxonomy. HELD, with MINOR-4.** Compared member by member against
PHASE2_REMAINDER_PLAN §D.4: L0, L1, L2 (E0–E5) and L5 verbatim; L3 is B1–B8 plus two
declared `B0_*` facts that exist today; L6 three declared facts plus `unmapped`.
`L4_CODES is CLASS_PRECEDENCE` — identity, not a copy. Every layer closed with
`unmapped`; every `REASON_LAYER` target lies in its layer's vocabulary; the docstring
precedence table is asserted equal to `LAYER_PRECEDENCE` / `LAYER_NAMES`. I planted a
new reason in a **scratch copy** (M2) and confirmed all three halves:

```
literals found in the clean tree : 25    literals NOT in REASON_LAYER : []  (no stale entries either)
planted reason seen by the guard : True  runtime landing : l6='unmapped'  primary=('l6','unmapped')
working tree untouched           : True
```

L2 is populated only from the gate's own reasons plus `truncated_pages` (or
`unmapped`, never a guess); L3 only through `REASON_LAYER` from `outcome_reason`.
Nothing is inferred from a kind or an outcome. `UNRESOLVED_TAXONOMY_VERSION = 1`
travels in every diagnosis including the empty one, and the report warns on mixed
versions. My fresh N8 (L2 picking the most *downstream* E-code) dies.

**8 — funnel + technical telemetry (case 25). HELD, with MINOR-5 / MINOR-6.**

```
base ROW_FIELDS 46 -> tip 77;  PREFIX PRESERVED IN ORDER: True
DocumentRow field order == ROW_FIELDS: True (nothing in one and not the other)
cost|price|rate|usd|billing in ROW_FIELDS: []   and none anywhere in the +5,294 lines
psutil: requirements-local.txt only, not requirements.txt, no module-level import anywhere
```

M9 and M16 die; vocabularies are closed and enforced at `as_dict()`.

**9 — the geometry seam. HELD.** At `reconstruction_mode == "off"` the mode is read
first, so no evidence is touched, no sha computed, and `analysis.structurer.geometry`
is not imported; `_analyse` then makes exactly the two pre-cell calls with the
pre-cell argument sets. The other half is proven too (mode `research` →
`document_geometry` appears), so inertness is a property of the MODE, not a dead
branch. No import tripwire forbids `discovery` → `analysis.structurer.geometry` or
`discovery` → `layout` (`test_layout_boundary.py`, `test_evidence_boundary.py` and
`test_truth_firewall.py` all constrain the *imported* package, not `discovery`). I
attacked the under-partitioning direction — geometry non-`None` while `evidence_sha`
is `None`, which would cache a geometry-fed payload under a geometry-blind key — and
it is unreachable: `ExtractionEvidence.evidence_sha256` is filled in `__post_init__`,
so the only reachable asymmetry over-partitions, which is safe. M15 dies.

**10 — the diagnostics guard. HELD.**

```
DIAGNOSTICS_VERSION = 5    reconcile.py issues.append( = 6 == len(LIVE_RECON_ISSUE_ANCHORS) = 6
pipeline.py issues.append( = 0  (pinned in its own right, not folded into a total)
RETIRED = ['recon:escalation_extraction_failed'] <= RECON_ISSUE_ANCHORS and <= CLASS_OF
a v4-shaped record still classifies -> primary_class 'extraction_failure'
```

The §11 v5 entry in `W3_2_TAXONOMY.md` is complete and states the blast radius.

**11 — ownership. HELD.** Nothing under `layout/`, `evidence/`, `webapp/**`,
`analysis/**`, nor `telemetry/run_of_record.py` is touched; `webapp/worker.py` is
untouched (K's W3 said so, and a test pins it). The four deviations, judged:

| deviation | judgement |
|---|---|
| `tests/test_escalation_router.py` | **minimal** — the trigger tuple is pinned member by member, so appending to a module the card DOES own necessarily fails it; one member inserted in the pinned position plus a comment. |
| `tests/test_adjudication.py` | **minimal** — one parametrize row `validated→deferred` flipped to `regressed` with R11 named; the "deferred is outside the ladder" assertion below is untouched. |
| `tests/test_repair_guard.py` | **minimal** — `4 -> 5` in one tuple; the other four members (60/53/7/2) unchanged, which is the correct signal that no code was added or re-classed. |
| `tests/test_visual_rung.py` | **minimal and an improvement** — three slices re-anchored on `ROW_FIELDS.index("failure_class")`, stating contiguity-and-order exactly rather than by position from the end. |

A fifth file outside the list, `tests/test_no_statement_hardcodes.py`, is authorized
by card item 10 and declared in the W3's deviation §4; the two committed instruments
`tools/p22truthtable_{measure,mutation_table}.py` are anticipated by §9 and named in
Ocean's brief. Recorded, not faulted.

**12 — no hardcodes (case 24). HELD.** The roots append cleanly extends cell C's, with
a self-check that the named files exist and are actually scanned — the failure mode of
every allowlist, closed. The decision NOT to add `discovery/` and `telemetry/`
wholesale is written into the roots and reported rather than taken silently; I agree it
is out of scope here. Canonical guards: **276 passed**.

**13 — the run-of-record measurement. REPRODUCED EXACTLY** (table below). The
instrument analyses nothing: it reads `rows.csv`, `telemetry.jsonl` and the census CSV,
and never names `analyze_document`, `cached_analysis` or `reconstruction_mode`. One
caveat on its docstring: the taxonomy IS the shipping code, but the funnel is
re-derived locally in `_funnel` rather than by `_project_funnel` — the two agree on this
run, but "every derived value is computed by the SHIPPING code" holds for the taxonomy,
not the funnel.

**14 — mutation table. 17/17 + 8/9 fresh** (tables below). The harness applies every
mutant as a real textual edit to a **code** file — never to a test — refuses a dirty
tree, restores in `finally`, and asserts the tree clean after each; M2 is the one
in-process exception and is honestly labelled. **The M11 fix is in the TEST, not the
code** (`60617bd` touches `tests/test_research_mode.py` only, 19+/3−), and the mutant
now dies for the right reason: the added `_OFFLINE_READS` dimension drives each mode
through the *upgrade* path where the mutated expression lives, not only recovery.

**15 — privacy / message / secrets. REPRODUCED** (table below). I parsed the gitignored
`.env` and grepped every added line for its VALUES (never printing them):
`PADDLE_VAST_HOST` and `PADDLE_VAST_SSH_PORT` — the only secret-shaped values — appear
**0** times. Three keys matched, all non-secrets or collisions: `PADDLE_PROVIDER` /
`PADDLE_EXECUTION_CLASS` are the public classification tokens the rulings name openly,
and `PADDLE_VAST_SSH_USER` is a 4-letter word whose 65 "hits" are ordinary English
("temp **root**", "scan **root**s"). All 12 commits carry `Co-Authored-By: Claude Fable
5.1` and a `Claude-Session:` line, and every message speaks in classes, never instances.

**16 — heavy proofs.** Table below; every step under my own lock window, one at a time,
each log ending `EXIT=`.

---

## Mutation table — my independent re-run

`python tools/p22truthtable_mutation_table.py` in **my** worktree (never the cell's):
**17/17 KILLED, unkilled: none, tree clean after every mutant.** Every killer is
exactly the one the cell names — I agree with all seventeen rows:

| # | killer I observed (failing count) |
|---|---|
| M1 | `test_the_primary_reason_is_the_most_upstream_non_empty_layer` (2) |
| M2 | in-process, tree untouched |
| M3 | `test_every_exit_from_validated_is_a_regression`, `test_validated_to_refused_fails_the_build_with_exit_2` (6) |
| M4 | `test_the_transition_matrix_names_every_class_pair_with_a_count` (4) |
| M5 | `test_differing_raw_denominators_are_refused_by_name` (1) |
| M6 | `test_the_classifier_is_never_passed_to_the_analysis_and_changes_no_payload` (2) |
| M7 | `test_a_row_cannot_carry_two_kinds` (1) |
| M8 | `test_diagnostic_labels_overlap_and_are_never_summed_into_the_primary_table` (1) |
| M9 | `test_no_cost_price_rate_usd_or_billing_key_anywhere` (1) |
| M10 | `test_every_enabled_argument_is_a_mode_fact_never_a_per_document_expression` (1) |
| M11 | `test_no_other_mode_can_supply_the_research_trigger` (1) |
| M12 | `test_research_mode_refuses_{a_wrong_literal_value,without_both_literals}` (2) |
| M13 | `test_a_production_data_dir_is_refused` (2) |
| M14 | `test_the_runner_refuses_a_holdout_sha_before_any_read` (1) |
| M15 | `test_the_geometry_seam_passes_nothing_while_the_reconstruction_mode_is_off` (2) |
| M16 | `test_the_new_columns_are_appended_at_the_end_of_row_fields_in_the_card_order` (1) |
| M17 | `test_raw_coverage_is_validated_over_distinct_shas_and_is_printed_first` (1) |

### My own fresh mutants (N1–N9) — 8 killed, 1 survived

| # | mutant | file | killer | result |
|---|---|---|---|---|
| N1 | the transition matrix drops the `unknown` **row** (M4 drops a column) | `discovery/compare.py` | `test_the_transition_matrix_names_every_class_pair_with_a_count` | KILLED (4) |
| N2 | the raw denominator counts **rows**, not distinct content shas | `discovery/report.py` | `test_raw_coverage_is_validated_over_distinct_shas_and_is_printed_first` | KILLED (4) |
| N3 | a research partition accepted on a **production** runner | `discovery/runner.py` | `test_a_partition_or_a_population_outside_research_mode_is_refused` | KILLED (6) |
| N4 | the holdout refusal applied **after** the population check | `discovery/runner.py` | (none) | **SURVIVED** → MINOR-3 |
| N5 | the `--data-dir` check compares the **raw spelling**, not the resolved path | `discovery/runner.py` | `test_a_production_data_dir_is_refused` | KILLED (2) |
| N6 | `refused` ranked into the ladder, above `failed` | `discovery/compare.py` | `test_the_ladders_are_unchanged_and_refused_is_not_a_rung`, `test_refused_is_unranked_against_the_terminal_classes` | KILLED (6) |
| N7 | the CCL line printed **before** the raw denominator | `discovery/report.py` | `test_raw_coverage_is_validated_over_distinct_shas_and_is_printed_first` | KILLED (1) |
| N8 | L2 picks the most **downstream** E-code | `telemetry/unresolved_taxonomy.py` | `test_l2_is_populated_from_the_gate_reasons_and_the_truncation_fact_only` | KILLED (1) |
| N9 | the research trigger at a **second site** in the runner as a **string literal** (escapes both `ast.Name` pins) | `discovery/runner.py` | `test_no_other_mode_can_supply_the_research_trigger` | KILLED (1) |

Tree clean after every one of the 26 mutants.

---

## Heavy proofs — mine versus the cell's

Lock window **19:01:12 → 19:54:16**, one step at a time, `MASTER.log` recording every
boundary.

| step | my result | the cell's | EXIT |
|---|---|---|---|
| full default suite (tip) | **9,804 passed / 48 skipped / 39 deselected / 0 failed** (498s) | 9,799 / 48 / 39 / 0 (pre-`60617bd` tree) | 0 |
| canonical guards (5 files) | **276 passed** | 276 | 0 |
| canonical conformance (7 files) | covered by the green full suite | 1,282 passed / 41 skipped | 0 |
| `python corpus_gate.py` | **GREEN — 105 PASS / 3 WITHHELD / 1 REFUSED** | GREEN 105/3/1 | 0 |
| `pytest -m corpus` | not re-run (24 min; the suite and the gate cover the seam) | 34 passed | — |
| mutation table M1–M17 | **17/17 killed, tree clean** | 17/17 | 0 |
| fresh mutants N1–N9 (mine) | **8 killed, N4 survived** | n/a | 0 |
| union replay chunk 01 (`--parser chase`) | **504 pop · 0 newly validated · 504 of 504 preserved · 504 payload identical · 0 changed · 0 regressions** | identical | 0 |
| no-parser replay | **685 pop · 656 replayed · 0 newly validated · 656 unchanged non-validated · 0 payload changed · 0 regressions** (`--expect-unresolved 29`) | identical | 0 |
| classify_census over 3,380 (read-only, cold cache) | 3,380 == 3,380 OK · 755 == 755 OK · 431 exceptions | identical | 0 |
| run-of-record measurement | every number below | identical | 0 |
| branch privacy scan | **hit 0 / residue 0** over 5,294 added lines, 3,351 documents read | hit 0 / residue 0 | 0 |
| commit-message scan | **MONEY 0 / DIGITS 0 / DATES 0 / WORDS 4**, 12 commits | same 4 | 1 (WORDS) |

I did not re-run the base-tree replay or the other six chunks: the cell's 14 chunk
logs are internally consistent (populations sum to **2,695**: 504+427+412+418+426+418+90;
preserved sum to **2,625**: 504+425+402+409+423+394+68), chunk 01 is the largest and
exercises the changed analysis call most heavily, and it reproduces bit for bit at my
hand.

**The four WORDS hits, attributed.** Each is an ordinary-English collision inside the
cell's own commit prose, not a document token; I located the source phrase for each:
`AUTHORIZED MAKE` and `CARD AUTHORIZED` from one line of `4e5358d` ("a change this
**card is authorized to make**"); `CALLS STATE` from the same commit ("docstring
**calls** out: the new **state** fires on zero documents"); `PREMISES` from `7b0926b`
("Two test **premises** corrected and named"). The only URL literal in the whole diff
is `http://127.0.0.1:1` — a deliberately dead loopback port; the fake worker binds
`127.0.0.1:0` in-process. No network, no real endpoint.

---

## The W3's numbers, re-derived

From **my** re-run of `tools/classify_census.py` + `tools/p22truthtable_measure.py`
over the run of record's cold cache, read-only.

| measure | mine | the W3's | agree |
|---|---|---|---|
| documents / validated / unresolved | 3,380 / 2,625 / 755 | same | yes |
| disjoint sum, archive / unresolved | 3,380 == 3,380 OK · 755 == 755 OK | same | yes |
| primary kind over the 755 | COMPLETE 324 · PARTIAL 217 · UNCERTAIN 161 · NOT_A_STATEMENT 22 · FILE_INVALID 16 · ACTIVITY_EXPORT 15 | same | yes |
| primary LAYER over the 755 | l1 415 · l3 223 · l5 65 · l4 35 · l0 16 · l2 1 (= 755) | same | yes |
| layers PRESENT | l3 537 · l1 415 · l5 126 · l4 70 · l0 16 · l2 15 (= 1,179) | same | yes |
| leading codes | `B0_no_reader_claimed` 223 · `KIND_UNCERTAIN` 161 · `declined_by_claiming_reader` 65 | same | yes |
| diagnostic labels | R 13 · U 123 · A 0 / B 656 / C 70 · truncation 4 · refused 0 | same | yes |
| funnel `stage_extract` | native 3,172 · local_tesseract 179 · none 29 | same | yes |
| validated exceptions | 431 of 2,625 — PARTIAL 364 · UNCERTAIN 66 · NOT_A_STATEMENT 1 | same | yes |
| archive kinds | COMPLETE 2,518 · PARTIAL 581 · UNCERTAIN 227 · NOT_A_STATEMENT 23 · FILE_INVALID 16 · ACTIVITY_EXPORT 15 | same (the 2,518-vs-2,534 divergence from cell C is the declared evidence-source mode; disjointness and the sums are the property) | yes |
| **discrepancy** | `B0_no_reader_claimed` = **223** primary / **537** present | W3 §Risks says **656** | **no** → MINOR-7 |
| **discrepancy** | full suite at the tip = **9,804** | W3 says **9,799** | **no** → MINOR-7 |

The 431 exceptions are correctly reported as a **classifier** finding, never as a
coverage change — no classification touches any verdict, which the payload-identity
test and the union replay establish independently. The count agrees with cell C's
cache census (431).

The cell's STOP is honest: `bytes_up` / `bytes_down` / `inference_ms` / `vram_mb` are
declared and permanently empty because the Paddle rung's per-request telemetry stops
at `ocr/paddle_rung.py::PaddleRead.telemetry` and never reaches `StatementMarkdown` —
a field on `ocr/document.py` and a line in `ocr/pipeline.py`, neither owned by this
card. Correctly named for 2.3. Likewise the pre-existing defect: `python -m discovery`
builds a job store at import time via `inventory → corpus_gate → adb_forensic_audit →
webapp.app`. I confirmed it is **pre-existing at `b7af37b`** (this cell touches none
of those four modules) and that it affects the filesystem footprint only, never the
artifacts.

---

## Properties I attacked and could not break

The classifier's byte-identity with the analysis (spied, stubbed, mutated) · the
production OCR key's equality across the cell · the mode-only reachability of
`operator_forced_paddle` (three AST pins, a tree-wide scan, a behavioural pin, and my
literal-spelling mutant) · the both-literals preflight ordering and its
name-not-value refusals · both per-document research doors preceding any read · the
`validated`-exit regression rule across all six targets · the matrix's closed shape ·
the raw-denominator refusal on distinct shas with its own exit code · the
raw-before-CCL print order · the leakage firewall · `truth_report.py`'s refusal of a
tracked `--out` and its inability to print a sha with a verdict · the L0–L6
vocabulary against §D.4 · the doc/code precedence pin · all four drift guards,
including a reason planted in a scratch copy with the tree left byte-identical ·
`L4_CODES is CLASS_PRECEDENCE` · the append-only `ROW_FIELDS` prefix · the absence of
any cost name in 5,294 added lines · the geometry seam's inertness at `off` and
reachability when not, including the cache-key under-partitioning direction · the
diagnostics live-anchor count with `pipeline.py` pinned at zero · the untouched state
of `layout/`, `evidence/`, `webapp/**`, `analysis/**` and
`telemetry/run_of_record.py` · the union replay's payload identity on 504 documents ·
the absence of any secret value in any added line.

## My instruments (scratchpad)

```
<scratchpad>/probe_rowfields.py          ROW_FIELDS append-only + DocumentRow order + cost grep
<scratchpad>/probe_keys_and_compare.py   OCR/analysis keys; direction/matrix; taxonomy vs D.4; geometry seam
<scratchpad>/probe_datadir.py            the 14-spelling --data-dir attack
<scratchpad>/probe_misc.py               psutil degradation; M2 in a scratch copy; --out refusal; diagnostics guard
<scratchpad>/rev22_fresh_mutants.py      my nine fresh mutants (reuses the committed harness's discipline)
<scratchpad>/lock_acquire.py             unbounded lock poll      <scratchpad>/heavy.sh  one heavy step per call
discovery_reports/train12-logs/rev22-truthtable/   all my logs + rev22-{mutation-table,fresh-mutants}.md
.claude/worktrees/rev22-truthtable/discovery_reports/rev22/   my private census CSV and exceptions table (git-ignored)
```

## Recommendation

Compose. The seven MINORs are zero-population today and none touches the 2,625 floor,
the validator, the privacy boundary or the run of record. I would ask the cell to
close **MINOR-2** (one token) and **MINOR-3** (one fixture line) before composition —
both are cheap and both are named deliverables of this card. **MINOR-1**, **MINOR-4**
and **MINOR-5** are one-line hardenings Ocean may reasonably carry to the 2.3 wave
cell as recorded latents. **MINOR-6** and **MINOR-7** are corrections to the durable
record: the W3's `656` and `9,799` should be fixed in place.
