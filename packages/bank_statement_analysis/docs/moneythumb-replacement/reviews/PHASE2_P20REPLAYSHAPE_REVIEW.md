# Independent adversarial review — P20-REPLAY-SHAPE (`wave20-replayshape`, Phase 2.0 addendum cell E)

Reviewer: independent Opus agent. Did not write this code.
Review worktree: `.claude/worktrees/rev20-replayshape`, detached at the branch tip **`2021ca2`**.
Base: `train10` **`51692c3`** (the composed Phase 2.0 train).
Diff under review: `git diff 51692c3..2021ca2` — 3 files, 712 insertions, 30 deletions.
Run of record: `discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a`.
Cold cache: `.claude/recovery/webapp_data_train9_cold` (READ-ONLY; nothing written).
Host: idle (`tasklist | findstr python` empty before every measurement). Python 3.14.5.
Per the brief I did **not** re-run the 3,380-sha full-archive replay; §"What I substituted for the
full-archive run" says what I ran instead and what that does and does not cover.

**Verdict: APPROVE WITH FINDINGS.** The card's central deliverable is correct and I re-derived it
myself: `replay_one` now makes the runner's call, the 23 document-block documents go from
`changed` to `identical`, the population is exactly what the cell says it is, and every mutant the
card names is killed. Three MAJORs are about what the branch does **not** pin or **not** disclose,
not about a wrong answer, and all three are cheap to close.

---

## 1. Claim-by-claim — claimed vs measured

| # | Claim (card / W3 `§P20REPLAYSHAPE`) | Measured by me | Verdict |
|---|---|---|---|
| 1 | The population is **23** of 2,656 train9-cold analysis payloads carrying a top-level `document` block | Independent read-only scan of all 3,380 shas of `rows.csv` through `ColdCache.text` + `ColdCache.baseline_payload`, plus a direct `rglob` over `artifacts/analysis`: **2,656** artifact files on disk, **23** carrying a `document` block; 3,351 shas resolve text, 2,695 resolve an analysis payload, 656 resolve text with no analysis artifact, **29** resolve nothing | **CONFIRMED** |
| 2 | The 23 sha16s, named in the W3 | My scan produced the identical 23-element list, in the same order | **CONFIRMED, byte-for-byte** |
| 3 | 2 of the 23 are genuinely multi-account (`accounts` present): `7C7956EB5E93DB1D`, `E38FA786106F752E` | Same two, and only those two | **CONFIRMED** |
| 4 | The 23 decompose as 15 L1-S2 protected carriers + 8 `guardian_cu`, disjoint | `tests/test_l1s2_protected_carriers.py::CARRIERS` = 15, all inside the 23; the remaining 8 are the `guardian_cu` group | **CONFIRMED** |
| 5 | At BASE the 23 are `changed` and `--expect-identical` exits 3 | Ran `51692c3`'s own `tools/cohort_replay.py` (extracted with `git show`, run out of the scratchpad against this worktree's `PYTHONPATH`; no second worktree, no stash): population 23, **payload identical 0, payload changed 23, EXIT=3** | **CONFIRMED** |
| 6 | At TIP the 23 are `identical`, `--expect-identical` exits 0 | `--shas <the 23> --expect-identical`: population 23, replayed 23, newly validated 0, preserved **23 of 23**, **payload identical 23**, regressions 0, **EXIT=0** | **CONFIRMED** |
| 7 | Each of the 23's `after` equals the run-of-record `outcome_class` | Per-sha from the `--json` table: all 23 `validated/approved → validated/approved`, `payload: identical`, reader unchanged (`before_parser == after_parser`). 0 mismatches | **CONFIRMED** |
| 8 | `--account-shape` is exactly the pre-fix seam | `--account-shape` at the tip over the 23 vs the base instrument over the 23: the two `--json` tables compare **equal on every field including `changed_paths`**; both EXIT=3 | **CONFIRMED** |
| 9 | guardian_cu at tip: EXIT=0, 8/8 preserved identical | population 8, replayed 8, preserved 8 of 8, payload identical 8, **EXIT=0** | **CONFIRMED** |
| 10 | huntington at tip: EXIT=0, population 54, 41/41 preserved identical, 0 regressions | population 54, replayed 54, preserved **41 of 41**, payload identical 41, unchanged non-validated 13 (payload changed on 0), **EXIT=0** | **CONFIRMED** |
| 11 | `tests/test_cohort_replay_shape.py` 7 passed; the three unowned files 110 passed | The four files together: **117 passed**, EXIT=0 | **CONFIRMED** |
| 12 | 5 canonical guards: 267 passed | **267 passed**, EXIT=0 | **CONFIRMED** |
| 13 | The full archive has 29 shas with no OCR text, `source_path = none` | My own scan: **29** distinct shas / **30** `rows.csv` rows, **all** `source_path = none`; by outcome, 17 rows `failed/invalid_pdf` + 13 rows `deferred/deferred_visual_ocr`; `visual_rung = not_attempted` on all 30 | **CONFIRMED — and the 13 are the R-trigger population, which never reaches `_analyse` at all** |
| 14 | The new `replayed < population` refusal exits 3 and `--allow-unresolved` turns it into 0 | 23 real + 5 real never-resolving shas: **EXIT=3**, `replayed 23 of population 28`, the 5 sha16s named; the same cohort with `--allow-unresolved`: **EXIT=0** | **CONFIRMED** |
| 15 | The new guard does not collide with the pre-existing exactly-zero refusal | 6-sha all-unresolved cohort **with** `--allow-unresolved`: **EXIT=3** and the original message verbatim (`0 of 6 shas resolved any cached text — the run's partitions do not describe this data directory`). The zero guard is not relaxable by the new flag | **CONFIRMED** |
| 16 | `--allow-unresolved` "does not relax the drift check" (help text) | 23 + 5 with `--account-shape --allow-unresolved`: **EXIT=3**, `BASELINE FIDELITY FAILED on 23 shas` | **CONFIRMED** |
| 17 | The Q3 gate is observable through the default path and not through `--account-shape` | Direct against `replay_one`: default → `payload is None`, `failed/q3_provenance_refused`; `account_shape=True` → payload present, `validated/approved` | **CONFIRMED** |
| 18 | `replay_one` now calls "the runner's EXACT call" | Transcribed an oracle from `discovery/runner.py:682-695` + `:1017` + `:1029-1033` (from the runner's source, not from `cohort_replay.py`) and compared it to `replay_one` on 8 constructed documents + 4 injected exception classes: **agreement on class, reason and canonicalised payload in all 12** (see §3) | **CONFIRMED behaviourally; see MAJOR-2 for what is not PINNED** |
| 19 | The four remaining `replay_one` callers keep the flag they need | All four call `replay_one(markdown, pages)` with **no** `account_shape=`, i.e. they take the NEW default; the flag has **zero** non-test callers | **NOT AS DESCRIBED — MINOR-1** (behaviour on their cohorts is nevertheless unchanged; measured) |
| 20 | Ownership: `tools/cohort_replay.py`, the new test file, the W3 | `git diff --stat 51692c3..2021ca2` = exactly those three paths | **CONFIRMED** |
| 21 | Written for CI's 3.12 | Both changed files parse under `ast.parse(..., feature_version=(3,12))`; no 3.13+ API in the added lines | **CONFIRMED** |

---

## 2. Findings

### MAJOR-1 — `--account-shape` is accepted together with `--expect-identical`, and nothing in the report, the header or the `--json` says which shape ran

**Where.** `tools/cohort_replay.py:407-413` (the flag, whose own help text says *"never as a fidelity
gate"*), `:490` (the `selectors:` line, which prints `shas/group/family/parser/folder/slice` and
nothing about the shape), `:546` (the JSON, `{"tree", "run", "rows"}` — no shape field), `:566-583`
(`--expect-identical`, which never asks what shape produced `table`).

**Reproduction** (this worktree, tip `2021ca2`):

```
python -m tools.cohort_replay --run <TRAIN9 run> --data-dir <train9 cold> \
    --folder "Huntington Bank" --expect-identical --account-shape
EXIT=0
| population | 54 |     | … payload identical | 41 |
# cohort replay — unlabelled — tree `2021ca2` — run `2026-08-31T185527...`
```

Byte-for-byte the same table, the same header and the same exit code as the genuine fidelity proof
in claim 10 above — produced by the seam the branch's own docstring calls *"HISTORICAL"* and
*"does NOT reproduce the run of record"*. A W3 section, a review, or `tools/l1s3_sweep_attribution.py`
(`--replay-base` / `--replay-tip`, which consumes exactly this JSON) cannot tell the two apart. The
brief I was given says "exit codes verbatim"; an exit code cannot carry this.

This is the same class of defect the card exists to fix: MAJOR-3 in `PHASE2_P20ARTIFACTS_REVIEW.md`
became folklore because two cells reported an exit code without the shape behind it. Re-opening the
possibility one flag away, with only help text in front of it, is the thing PHASE2-RULES rules out:
*"architectural tripwires … because comments and discipline do not count as enforcement."*

**Exact fix I would accept.** Refuse the combination:

```python
if args.account_shape and args.expect_identical:
    print("--account-shape is the HISTORICAL single-account seam and does not reproduce the "
          "run of record; it may not be combined with --expect-identical")
    return 3
```

plus (cheap, and worth having anyway) `shape=account|document` in the `selectors:` line and a
`"shape"` key in the `--json` payload, so an archived JSON can always name its own instrument. A
test in `tests/test_cohort_replay_shape.py` pinning the refusal. If Ocean would rather keep the
combination legal for a historical re-measurement, then the header **must** carry the disclaimer
line and the JSON the shape key — but I would take the refusal, because the reason to run
`--account-shape` at all is never a fidelity claim.

---

### MAJOR-2 — two of the four elements of "the runner's EXACT call" are unpinned, and both surviving mutants are non-equivalent; one of them silently removes the deterministic-mode offline guarantee

**Where.** `tools/cohort_replay.py:288-291`:

```python
payload = document_report_to_dict(analyze_document(
    markdown, parse_mode="deterministic", on_dispatch=collector, sheets=pages))
```

The card's design point 1 names all four elements. `analyze_document` / `document_report_to_dict`
are pinned (M1, M2, M8 below all die) and `on_dispatch` is pinned (M6 dies on the Q3 test).
`parse_mode="deterministic"` and `sheets=pages` are pinned by **nothing** in the branch's proof
floor.

**Reproduction.** Each mutant applied to `tools/cohort_replay.py`, `tests/test_cohort_replay_shape.py
+ tests/test_cohort_replay_selection.py` (32 tests) run, mutant restored in a `finally` with
`git checkout --`; `git status --porcelain` empty afterwards.

```
M7  drop `sheets=pages`            SURVIVED  (32 passed)
M11 drop `parse_mode="deterministic"`  SURVIVED  (32 passed)
```

Both are **non-equivalent**:

* **M7** against the archive: `--folder "Huntington Bank" --expect-identical` → **EXIT=2** (a
  BLOCKING validated regression), preserved-identical falls 41 → 38. So dropping the page partition
  changes the answer on real documents and only an archive cohort catches it. `corpus_gate.py:827-830`
  excuses `tools/cohort_replay.py` from the statement-hardcode guard *on the explicit ground that it
  "DOES supply the reconstructed page partition as `sheets`"* — the property the gate's own exemption
  rests on has no test.
* **M11** is worse than a fidelity bug. `analysis/pipeline.py:1150` defaults `parse_mode="auto"`, and
  `:986-990` gates the hosted-model escalation on `parse_mode != "deterministic"`; `:947-949` is the
  deterministic refusal that stops an unclaimed document ever reaching `extract_statement`. Proven
  hermetically (`analysis.pipeline.extract_statement` monkeypatched to a sentinel, no network):

  ```
  parse_mode='deterministic'  -> RuntimeError (the deterministic refusal)
  parse_mode=<default>        -> REACHED extract_statement (the hosted-model seam)
  ```

  And it stays **green**. On six real unclaimed `native` shas of the run of record
  (`AE0581F138F4356A 18A524AD4D6AAF89 6B8B49B0C190146F 2C0A230A83A11FA7 86355161E964F37A
  4C4EAE7A79B5583C`), the mutant reached the model seam 6/6 times and returned
  `('failed','no_parser_matched')` — **identical to the baseline row on all six** — because
  `_failure_reason` reads the `unclaimed` dispatch, not the mode. A full-archive `--expect-identical`
  would therefore exit 0 while the instrument had lost the `$0 vendor … no hosted model call
  anywhere` guarantee PHASE2-RULES makes binding. There are 726 unchanged-non-validated documents and
  656 text-resolving documents with no analysis payload in this archive; that is the blast radius.

**Exact fix I would accept.** One test in `tests/test_cohort_replay_shape.py`, no production change:

```python
def test_replay_one_makes_the_runners_exact_call(monkeypatch):
    seen = {}
    import analysis.pipeline as pipeline
    real = pipeline.analyze_document
    def spy(markdown, **kw):
        seen.update(kw)
        return real(markdown, **kw)
    monkeypatch.setattr(pipeline, "analyze_document", spy)
    markdown, pages = _multi_account_markdown()
    replay_one(markdown, pages)
    assert seen["parse_mode"] == "deterministic"   # the offline guarantee
    assert seen["sheets"] == pages                 # the analysis input hash
    assert seen["on_dispatch"] is not None         # the omission collector / _failure_reason
```

An AST guard over the call site would be equally acceptable and stronger. Either way the four
elements the card enumerates should be four assertions, not one.

---

### MAJOR-3 — `--allow-unresolved` reopens MINOR-8 exactly where the guard matters, and the phase's own full-archive proof must pass it

**Where.** `tools/cohort_replay.py:404-406` and `:572-577`. The flag is all-or-nothing: it turns off
the `replayed < population` refusal at every ratio strictly between 0 and 100 %.

**Reproduction** (real shas, this cache): 1 resolving sha + all 29 permanently-unresolvable ones:

```
python -m tools.cohort_replay --run <TRAIN9 run> --data-dir <train9 cold> \
    --shas <1 real + the 29> --expect-identical --allow-unresolved
| population | 30 |   | replayed (text available) | 1 |   | no text / absent | 29 |
EXIT=0        (no BASELINE FIDELITY line)
```

One of thirty replayed, green. That is the P20-ARTIFACTS re-review's MINOR-8 verbatim ("replayed 2 /
population 10", exit 0), restored by the flag this card added to close it. And this is not
hypothetical: the archive contains **29** structurally unreadable shas, so **every** full-archive
`--expect-identical` from now on must pass `--allow-unresolved` — the cell's own closure does. The
guard is therefore live only on cohorts that never needed it and off on the one cohort the phase's
headline proof uses.

**Judgement on the card's question (keep the refusal, or exclude `source_path = none` by default).**
**Keep the refusal — do not exclude by default.** An automatic exclusion keyed on
`rows.csv:source_path` would let the run under test decide which of its own members it is excused
from reproducing, and the population printed would stop being the cohort the caller named; that is
the silent-narrowing class MINOR-8 objected to, moved one level down. The 29 being "structurally
unreadable rather than unresolved by the instrument" is true today and is a fact about *this* run —
`source_path` is a claim in the artifact under review, not an independent one.

**Exact fix I would accept** — make the opt-out quantitative instead of binary:

```
--expect-unresolved N     # refuse unless exactly N members did not resolve
```

The full-archive proof then reads `--expect-unresolved 29` and refuses at 28 or 30, so a cache
mis-partition that loses 400 documents is still an exit 3 while the 29 known-unreadable ones are a
declared, reviewable constant. `--allow-unresolved` may stay as the loose form for exploratory runs,
but it should not be what a fidelity proof is allowed to use. Whichever Ocean picks, the W3's
full-archive closure must state the exact unresolved count as part of the claim rather than as a
footnote to a flag.

---

### MINOR-1 — the W3's account of why `--account-shape` exists is not what the code does; the flag has no non-test caller

**Where.** W3 `§P20REPLAYSHAPE`: *"kept for the four existing callers with old-signature
`replay_one(markdown, pages)` calls (`tools/commsec_identity_ceiling.py`,
`tools/cpdecl_rotation_table.py`, `tools/huntington_identity_ceiling.py`,
`tools/pnc_identity_ceiling.py`) … rather than deleted."*

**Reproduction.** `grep -rn "replay_one(" tools/` returns exactly four call sites —
`commsec_identity_ceiling.py:476`, `cpdecl_rotation_table.py:107`,
`huntington_identity_ceiling.py:206`, `pnc_identity_ceiling.py:176` — and **every one** passes
`(markdown, pages)` only. None passes `account_shape=True`. All four therefore take the NEW
document-shaped default; the flag is used by nothing outside `tests/test_cohort_replay_shape.py`.
The sentence describes an intent that was not implemented.

The *safety* half of the claim does hold, and I measured it rather than accepting it:

* the default flip changes an answer only on a document publishing a `document` block, and that
  population is exactly the 23 (independently derived, claim 1);
* the 23 are parsers `member_statement_rollup` 8 / `symitar` 7 / `community_section` 5 /
  `dakota_west` 2 / `zions` 1, folders `Unidentified` 21 / `Rogue Credit Union` 1 / `Zions Bank` 1 —
  **zero** overlap with commsec, cpdecl, huntington or pnc;
* none of the four is on any proof floor: no reference to them anywhere outside `tools/`
  (CI workflows, `corpus_gate.py`, `tests/` all clean).

One live edge worth a sentence: `tools/commsec_identity_ceiling.py:479-489` reads
`payload["metrics"]`, `payload["statement"]["transactions"]` and `payload["integrity"]`, none of
which exists in the multi-account shape, and that tool takes a caller-supplied `--shas`
(`:509`). Pointed at `7C7956EB5E93DB1D` or `E38FA786106F752E` it now reports zeros instead of the
old single-account projection. Not reachable from its own cohort; reachable by an operator.

**Fix I would accept:** either pass `account_shape=True` at those four call sites (which is what the
card literally asked for and preserves their historical seam exactly), **or** replace the W3 sentence
with the truth — the four callers now take the document shape, here is the disjointness measurement
that makes it safe, and the flag's only consumer today is the mutation test. Not both stories.

---

### MINOR-2 — "`classify_document` called UNCONDITIONALLY on the exception path" is an equivalent mutant at this tree, and the W3 presents it as a fidelity improvement

**Where.** `tools/cohort_replay.py:296-306`; W3 *"called UNCONDITIONALLY whether `payload` is `None`
or not — `replay_one` now does the same, rather than special-casing the exception branch with a
hardcoded `"failed"`."*

**Reproduction.** Mutant M5 restores the special case —
`if error_type is not None: return None, "failed", reason_hint or "exception", _claimed(collector)`
— and **survives all 32 owned tests**. It survives because it is behaviourally identical: for
`payload is None`, `classify_document` falls straight through
`telemetry/record.py:634` to `classify_outcome`, which returns
`("failed", error_reason or ("exception" if error_type else "no_analysis"))`. Verified over six
`(error_type, error_reason)` pairs including `parser_exception`, `parser_ambiguous`,
`q3_provenance_refused`, `no_parser_matched`, `parser_declined` and `None`: identical in all six.

So the change is a **structural** fidelity improvement, not a behavioural one — correctly done, but
the W3 sentence reads as though it fixed something the replay was getting wrong. It would stop being
equivalent the moment `classify_document` grows an `error_type`-driven document override (an entirely
plausible Phase 2.1 edit), and nothing in the branch would catch the divergence.

**Fix I would accept:** either one assertion pinning `replay_one(...) == classify_document(None,
error_type=…, error_reason=…)` on the exception path, or one honest sentence in the W3 saying the
property is structural and equivalent today.

---

### MINOR-3 — the new refusal message conflates "the run named this sha and no artifact answers" with "this sha is not in the run at all"

**Where.** `tools/cohort_replay.py:486` (`no_text = [e for e in table if e["after"] in ("no_text",
"absent")]`) and `:574-577` (`"{len(no_text)} sha(s) did not resolve any cached text"`).

`absent` means the sha is not in the run's `rows.csv` — a stale or wrong cohort file, a different
defect from a cache that does not answer for a sha the run does name. The report body already keeps
them apart (`after = "absent"` vs `after = "no_text"`); the refusal line, which is the only thing a
reader sees when the run exits 3 with `--out`, does not. Reproduced implicitly in every run above
(the 23+5 refusal names five `no_text` shas under a message that would read identically for five
`absent` ones).

**Fix I would accept:** one f-string — `"{a} not in the run, {b} with no cached text"` — and the two
lists named separately.

---

### Observation — the `classify_document` fold has no constructible mixed-outcome witness at this tree

The brief asked for "a document with two accounts where one validates and one fails". I could not
build one, and the reason is worth recording. Over nine constructions from `tests/l1s4_pages.py`
(three accounts; `drop_row_figure`; `opening_override`; `closing_override`; `total_override`;
`repeat_section`; `movement_override`; `extra_lines`; idle + two posting), every *inconsistent*
document makes `member_statement_rollup` decline the whole document
(`failed/parser_declined`, payload `None`) and every *consistent* one folds
`validated/approved` on every account. The "weakest account" branch of
`telemetry/record.py::classify_document` is therefore dark at this tree — in the replay and in the
runner alike, so replay fidelity is unaffected — and no test in this branch or any other exercises
it. Not a finding against the cell; a note for whoever owns the fold next.

What the fix *does* buy on the real archive, measured: on the two multi-account payloads
`classify_outcome` **raises** `PayloadShapeError` (`analysis/payload_shape.py:168-174`) where
`classify_document` answers `validated/approved`. So the "classify with `classify_outcome`" mutant is
killed loudly rather than silently on the real data, which is the right failure mode.

---

## 3. What I did NOT find

* **No fidelity difference between `replay_one` and the runner.** I transcribed an oracle from
  `discovery/runner.py:682-695` (`_analyse`), `:1017` (`dispatch = collector.dispatch`) and
  `:1029-1033` (`classify_document(payload, error_type=…, error_reason=_failure_reason(error_type,
  dispatch))`) — from the runner's source, never from `cohort_replay.py` — and compared class, reason
  and canonicalised payload against `replay_one` on: a headerless markdown; an empty markdown; an
  empty markdown with pages declared; a single-account document that establishes a document-level
  fact (the `document`-block branch); the same document attributed to `local-tesseract-ocr` (the Q3
  refusal); a genuine two-account document; the same with `sheets=None`; the same with sheets that do
  not match the markdown. **All eight agree**, payloads byte-identical after canonicalisation. Four
  injected exception classes (`AmbiguousParserError` → `parser_ambiguous`, `RuntimeError`, `KeyError`,
  `MemoryError` → `exception`) also agree.
* **`collector.dispatch` vs the old `collector.dispatch if collector.seen else None` is a no-op.**
  `telemetry/collect.py:50-52` defines `seen` as `self.dispatch is not None`.
* **No hidden re-baselining.** The 23 are the only documents whose payload disposition moves, and I
  derived that population from the cache independently of the tool.
* **No ownership violation.** `git diff --stat 51692c3..2021ca2` touches
  `tools/cohort_replay.py`, `tests/test_cohort_replay_shape.py` and
  `docs/moneythumb-replacement/W3_TRACKA_LOG.md`, and nothing else. No `analysis/`, `discovery/`,
  `telemetry/`, `ocr/`, `webapp/` change.
* **No cache writes, no worktree pollution.** Both cold caches untouched; the base-instrument
  measurement was made by `git show 51692c3:tools/cohort_replay.py` into the scratchpad (no second
  worktree, no `git stash`); `git status --porcelain` empty before the review, after every mutant
  restore, and at the end.
* **No 3.13+-only API**, and both changed files parse under `feature_version=(3,12)`.
* **`tests/test_l1s2_protected_carriers.py`** (which imports `ColdCache`/`leaf_diff` from this tool
  and names 15 of the 23) still passes under `-m corpus`: **1 passed**.
* **No vacuous green in the new tests.** The correspondence padding in
  `_seed_correspondence_padding` is the same isolation technique the pre-existing selection test
  uses, and I confirmed the two refusal branches fire independently and in the documented order.

---

## 4. Mutation table (mine — every mutant applied, run, and restored)

Suite = `tests/test_cohort_replay_shape.py tests/test_cohort_replay_selection.py` (32 tests).

| mutant | result | killer(s) |
|---|---|---|
| M1 default reverted to `report_to_dict(analyze_markdown(...))` | **KILLED** | `test_a_document_shaped_multi_account_baseline_reproduces_identical`, `test_replay_one_default_and_account_shape_disagree_on_the_multi_account_fixture`, `test_the_q3_gate_is_observable_through_the_default_document_shaped_replay`, `test_expect_identical_refuses_a_partial_resolution_without_allow_unresolved` (**4 killers** — the card's "killed two ways" is met four times over) |
| M2 classify with `classify_outcome` instead of `classify_document` | **KILLED** | 3 killers; and on the real archive it raises `PayloadShapeError` on the 2 multi-account payloads |
| M3 the `replayed < population` refusal dropped | **KILLED** | `test_expect_identical_refuses_a_partial_resolution_without_allow_unresolved` |
| M4 `--allow-unresolved` made the default | **KILLED** | same |
| M5 hardcoded `failed` restored on the exception path | **SURVIVED** | equivalent mutant — see MINOR-2 (derivation included) |
| M6 `on_dispatch=collector` dropped from the document call | **KILLED** | `test_the_q3_gate_is_observable_through_the_default_document_shaped_replay` |
| M7 `sheets=pages` dropped from the document call | **SURVIVED** | **non-equivalent** — huntington cohort EXIT=2, 41 → 38 preserved-identical. **MAJOR-2** |
| M8 `--account-shape` becomes the effective default (`account_shape=True` at the call site) | **KILLED** | 2 killers |
| M9 the exactly-zero refusal branch deleted (the partial guard "covers" it) | **KILLED** | `test_expect_identical_still_refuses_the_exactly_zero_case_with_its_own_message` + the pre-existing `test_expect_identical_refuses_a_vacuous_zero_resolution_on_the_selected_cohort` |
| M10 the refusal message loses its `replayed X of population Y` counts | **KILLED** | `test_expect_identical_refuses_a_partial_resolution_without_allow_unresolved` |
| M11 `parse_mode="deterministic"` dropped from the document call | **SURVIVED** | **non-equivalent** — reaches `extract_statement` (hosted-model seam) on 6/6 real unclaimed documents while returning the identical class/reason. **MAJOR-2** |
| M12 the JSON canonicalisation (`json.loads(json.dumps(...))`) removed | **KILLED** | 2 killers |
| M13 `--account-shape`'s help text loses its `HISTORICAL:` disclaimer | **SURVIVED** | expected — help text is not enforcement; this is the argument of **MAJOR-1** |

`git status --porcelain` empty after the table.

---

## 5. What I substituted for the full-archive run

Per the brief I did not run the 3,380-sha replay. In its place:

* I derived the **population** (23 document-block payloads, 2 multi-account, 29 unresolvable) from
  the cache directly rather than from any replay report, so the cell's base-run "the 23 changed shas
  equal the document-block population" is corroborated from the other side of the equation.
* I ran the base instrument and the tip instrument over a `--shas` cohort containing **all 23** and
  got exactly the claimed 23-changed → 23-identical transition with the claimed exit codes.
* I ran guardian_cu (8) and huntington (54) at the tip, matching the W3 line for line.

**What that does not cover, and what the cold run must:** the cell's claim that *nothing outside the
23 moved* over the full 3,380 (base 2,602 identical + 23 changed → tip 2,625 identical) rests on the
cell's own two 38-minute runs. I sampled it (23 + 8 + 54 + 6 injected-mutant documents, all
consistent) but did not re-derive it. The `preserved 2,625 of 2,625` and `unchanged non-validated 726
(payload changed on 0)` lines are the two the composed train should re-read.

---

## 6. Reproduction commands

All from the review worktree; `RUN` = the TRAIN9 run of record, `DD` = `.claude/recovery/webapp_data_train9_cold`.

```
# proof floor
python -m pytest -q -p no:randomly tests/test_cohort_replay_shape.py \
    tests/test_cohort_replay_selection.py tests/test_run_of_record.py tests/test_q3_native_only.py
    -> 117 passed, EXIT=0
python -m pytest -q -p no:randomly tests/test_no_statement_hardcodes.py \
    tests/test_no_parser_helper_clones.py tests/test_r1_hardcodes.py \
    tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py
    -> 267 passed, EXIT=0
python -m pytest -q -p no:randomly -m corpus tests/test_l1s2_protected_carriers.py
    -> 1 passed, EXIT=0

# the 23, at the tip and at the base instrument
python -m tools.cohort_replay --run $RUN --data-dir $DD --shas shas23.txt --expect-identical
    -> population 23, replayed 23, preserved 23/23, payload identical 23, EXIT=0
git show 51692c3:tools/cohort_replay.py > <scratch>/cohort_replay_base.py
PYTHONPATH=<worktree> python <scratch>/cohort_replay_base.py --run $RUN --data-dir $DD \
    --shas shas23.txt --expect-identical
    -> population 23, payload identical 0, payload changed 23, EXIT=3

# the named cohorts
python -m tools.cohort_replay --run $RUN --data-dir $DD \
    --group FAM:guardian_cu_statement_summary --expect-identical      -> EXIT=0 (8/8 identical)
python -m tools.cohort_replay --run $RUN --data-dir $DD \
    --folder "Huntington Bank" --expect-identical                     -> EXIT=0 (41/41 identical)

# the refusal, and its holes
python -m tools.cohort_replay ... --shas <23 + 5 unresolvable> --expect-identical
    -> EXIT=3  "replayed 23 of population 28"
python -m tools.cohort_replay ... --shas <23 + 5 unresolvable> --expect-identical --allow-unresolved
    -> EXIT=0
python -m tools.cohort_replay ... --shas <1 real + the 29> --expect-identical --allow-unresolved
    -> EXIT=0  "replayed 1 / population 30"                            # MAJOR-3
python -m tools.cohort_replay ... --shas <6 unresolvable> --expect-identical --allow-unresolved
    -> EXIT=3  the ORIGINAL exactly-zero message                       # the two guards do not collide
python -m tools.cohort_replay ... --folder "Huntington Bank" --expect-identical --account-shape
    -> EXIT=0, report indistinguishable from a real fidelity proof     # MAJOR-1
```

The population scan, the runner-fidelity oracle and the mutation runner are three small scratchpad
scripts; each is a read of the cache or a `git checkout --`-restored edit, and none is committed.

---

## 7. Verdict

**APPROVE WITH FINDINGS.**

The card's deliverable is right, and it is right for the reason it claims: `replay_one` makes the
runner's call, `classify_document` is the runner's fold, the 23 document-block documents reproduce
byte-identically at an unchanged analysis tree, the `--account-shape` path preserves the historical
seam exactly, and the Q3 gate is observable through the replay for the first time. `newly validated =
0` and `previously validated preserved = all, payload identical` on every cohort I ran. I found no
wrong answer anywhere in the instrument.

The three MAJORs are all *absence* findings on an instrument the whole phase's fidelity claims rest
on, and each has a fix measured in lines:

* **MAJOR-1** — refuse `--account-shape` with `--expect-identical`, and stamp the shape into the
  report and the JSON. I would want this before composition: it is the same failure mode the card was
  cut to fix, and help text is not a guard.
* **MAJOR-2** — three assertions pinning `parse_mode="deterministic"`, `sheets=pages` and
  `on_dispatch`. The `parse_mode` one is a doctrine guarantee (`$0 vendor … no hosted model call
  anywhere`), not a nicety, and its mutant stays green on the archive.
* **MAJOR-3** — the `--allow-unresolved` opt-out should be an exact count, not a switch, because the
  full-archive proof is obliged to pass it. Keep the refusal as the default; do not exclude
  `source_path = none` automatically.

MINOR-1 asks for one W3 sentence to match the code (or four call sites to match the W3); MINOR-2 and
MINOR-3 are one assertion and one f-string. None of the five blocks the cold run, and none of them
changes a number in the closure.
