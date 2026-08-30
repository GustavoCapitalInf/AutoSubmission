# BATCH9 — L1-S2-SIBLING-OMISSION, independent adversarial review

**APPROVE WITH FINDINGS — 0 BLOCK, 1 MAJOR, 5 MINOR.**

Branch `wave9-l1s2`, base `train9` `fea0bd2`, tip `12bb0cf` (13 commits), worktree
`.claude/worktrees/mt9-l1s2`. Reviewed against `docs/agent-handoffs/BATCH9-RULES.md`
(Gustavo's six L-1 conditions, RULE S, fail closed, no statement-specific hardcodes),
`docs/agent-handoffs/L1-S2-SIBLING-OMISSION.md`, the reviewed design
`L1_INDEPENDENT_ACCOUNT_DESIGN.md` §1.5 / §2.3 / §2.7 / L1-C17 / §6 S2, and
`reviews/BATCH9_L1DESIGN_REVIEW.md` (Q8).

Every number in the cell's report was re-measured at the tip on this host unless the
"skipped" column says otherwise, and every measurement below is the reviewer's own run.

* **MAJOR-1** — S2's population is **15 documents / 19 sections**, not the card's and the
  design's **12 / 16**. The three extra sections are `symitar._yield_only`, a skip site
  neither the card's Scope paragraph nor the design's §6 S2 row names. The EVIDENCE is
  legitimate (measured, §3); the SCOPE decision enlarges S3's eventual
  `validated -> review` fold from 12 to **15 protected batch-8 shas** and was taken by the
  cell alone. Needs Ocean's explicit acceptance and an amendment to the design's §6 S2 row
  and §7 staging table before S3 prices it. **No code change is asked for.**
* **MINOR-1** — `tools/l1_design_skip_probe.py` is left permanently `exit 3` on `train9`
  after composition. Re-anchor or retire it (§7).
* **MINOR-2** — three record inaccuracies in W3 §L1S2's provenance paragraph and its
  commit-message count (§8). Every affected number re-measured at the true tip is
  unchanged except the two that move with the two doc-only commits.
* **MINOR-3** — the shared callee `_parse_sectioned_statement` has three other `None`
  exits that bypass the ledger, so "admitted on printed evidence or the document is
  refused" is a property of the `not txns` SITE, not of the function. **Measured archive
  population: 0** (§5). Reachable by construction. Carry to S3/S4.
* **MINOR-4** — `tools/l1s2_mutation_table.py`'s docstring claims a concurrency refusal
  that `main()` does not implement.
* **MINOR-5** — `tools/l1s2_sweep_diff.py`'s `--base` / `--tip` are `nargs="+"`; repeating
  the flag silently discards the earlier values and prints a confident wrong headline. The
  reviewer hit this on the first run (§4).

Nothing found is a regression, an absence-based admission, a weakened check, an edit to
the `Statement` prompt surface, or a validated document refused.

---

## 1. Per-claim table — claimed vs measured

`RUN` = `discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`,
`DATA` = `.claude/recovery/webapp_data_train8_cold`. All commands run from
`.claude/worktrees/mt9-l1s2` at `12bb0cf` unless a base tree is named.

| # | claim | cell | **reviewer measured** | command |
|---|---|---|---|---|
| 1 | skip probe at a PRISTINE base | 117 / 12 / 16 / 0 | **117 read / 12 documents / 16 sections / 0 `no_printed_evidence`; 8 declaration + 8 zero-summary; every one of the seven clauses 8 of 8** — exit 0 | `python -m tools.l1_design_skip_probe --run RUN --data-dir DATA` in a fresh detached worktree at `fea0bd2` |
| 2 | admission probe at the tip | 117 / 15 / 19 / 0 refused; 8+8+3; account block 15/15 identical | **identical, row for row** — exit 0 | `python -m tools.l1s2_admission_probe --run RUN --data-dir DATA` |
| 3 | closure cohort replay | 120 population, 117/117 preserved, 117 identical, 0 changed, 0 regressions, 0 newly validated | **exit 0 under `--expect-identical`** (stricter than the cell's run): 117 payload-identical, 0 changed, 0 validated regressions, 3 unchanged non-validated, runtime 164 s | `python -m tools.cohort_replay --run RUN --data-dir DATA --parser symitar --parser community_section --parser dakota_west --parser mission_valley --parser zions --expect-identical` |
| 4 | control replay at base | exit 0, 117/117 identical | **not re-run** — the cell's `base_control.log` carries `EXIT=0` at `fea0bd2`, and claim 1 re-establishes the base tree independently. The tip replay under `--expect-identical` is the load-bearing half and it is reproduced | — |
| 5 | seam probe base -> tip | account seam 232/232 identical; document seam 226 / 6 moved; exit 2 | **232 documents / 80 registrations; account seam 232/232 byte-identical; integrity flags and ORDER 232/232; ladder outcome 232/232; document seam 226 identical / 6 moved; exit 2** — same six shas | `PYTHONHASHSEED=0 python -m tools.l1s1_seam_probe … --capture … --baseline …`, base capture taken in the pristine `fea0bd2` worktree |
| 6 | mutation table | 6 mutants / 6 killed / 0 survived | **6 / 6 / 0**, every killer's exit code identical to the cell's; tree verified clean before and after each half | `python -m tools.l1s2_mutation_table --run RUN --data-dir DATA --only …` (run in two halves) |
| 7 | archive sweep, differenced | 3,380 documents, aggregates identical, 70 inherited / 0 movers / 0 removed, exit 0 | **3,380 / 2,669 compared / 2,620 identical / 46 moved / 21 `no_payload_now_publishes` / 3 `payload_now_raises` / 661 `no_payload_raises_again` / 29 no artifact — identical at both trees; 70 inherited, 0 movers, 0 removed, exit 0** | `python -m tools.l1s2_sweep_diff --base <4 base chunks> --tip <4 tip chunks>` over the cell's stored JSONs. The two 50-minute archive sweeps were **not** re-run: both logs carry per-chunk `CHUNK_EXIT_*` lines and a `SWEEP_DONE` / `SWEEP_BASE_DONE` terminator, the tip sweep at `ce67cdd` and the base at `fea0bd2` |
| 8 | canonical guards | 255 | **255 passed** — exit 0 | the five canonical files |
| 9 | canonical conformance | 1,270 | **1,270 passed, 40 skipped** — exit 0 | the seven canonical files |
| 10 | full default suite | 7,527 / 43 skipped | **7,527 passed, 43 skipped, 34 deselected** — exit 0, at the TIP (the cell's run was at `4b0a4c2`) | `python -m pytest -q -p no:cacheprovider` |
| 11 | the card's own fixtures | 38 at the tip | **38 passed** — exit 0 | `pytest tests/test_sibling_omission.py` |
| 12 | register test | (implied green) | **24 passed, 10 deselected** — exit 0 | `pytest tests/test_corpus_gate_outcomes.py` |
| 13 | `DocumentReport` pinned field set | (implied green) | **26 passed** — exit 0; and the field set is **byte-identical to base** — `omissions` and its RULE S clause both pre-date this card (L1-S1), so no new-field obligation arises | `pytest tests/test_document_report.py`; `git show fea0bd2:analysis/pipeline.py` |
| 14 | corpus gate | GREEN 105/3/1, verdicts 1/3/102/3 | **carried, not re-run — see "the gate and the slice" below** | `python corpus_gate.py` |
| 15 | corpus-marked slice | 30 passed | **carried, not re-run — see "the gate and the slice" below** | `python -m pytest -q -p no:cacheprovider -m corpus` |
| 16 | added-line privacy scan | `hit_count` 0 over 2,191 added lines, raw 3 discarded | **`hit_count` 0 over 2,208 added lines** (the tip carries two more doc commits), 120 documents read, MONEY/DIGITS/DATES/WORDS all 0; raw 4, discarded 1 `round_money` + 3 `words_class`. The discards are **legitimate** — see §6 | `python tools/privacy_scan_branch.py --data-dir DATA --base fea0bd2 --ref HEAD --rows RUN/rows.csv --where "parser_id=symitar,community_section,dakota_west,mission_valley,zions"` |
| 17 | commit-message scan | `hit_count` 0 over 12 commits | **`hit_count` 0 over 13 commits**, every class 0, in BOTH populations: the five registrations (120 documents) and `--shas` over the 15 named carriers (15 documents, 3,549 printed MONEY / 5,136 WORDS / 694 DIGITS / 299 DATES). The count 12 reproduces at no tree (§8) | `python tools/huntington_msg_privacy_scan.py --data-dir DATA --base fea0bd2 --ref HEAD --shas <the 15 carriers>` |
| 18 | `l1_design_skip_probe` REFUSES at the tip | exit 3 | **exit 3**, naming `analysis.symitar:420`, `analysis.community_section:622`, `analysis.community_section:984` — its own anti-vacuity check firing on the lines this card rewrote (MINOR-1) | `python -m tools.l1_design_skip_probe …` |
| 19 | pinned `dakota_west` document | `F748A799FDC7F25E`, admitted by `printed_zero_activity_summary`, payload identical, validated before and after | **confirmed** — it is a carrier, its class is `printed_zero_activity_summary`, its account block is byte-identical, and it is in the replay's 117 payload-identical list | claims 2, 3, 5 |
| 20 | RULE S — `Statement` prompt surface | untouched | **`analysis/schema.py` is byte-identical base to tip** (`md5 4afa7d0cfac77dd03a73d2f52a76d766` at both), and `analysis/serialization.py` has an empty diff. `Statement` is defined nowhere else | `git show fea0bd2:analysis/schema.py \| md5sum` vs `git show 12bb0cf:…` |

**Nothing failed to reproduce.** The only numbers that moved are the two that move with the
branch's last two documentation commits (added lines 2,191 -> 2,208; commits 10/12 -> 13),
and every scan result they carry is still 0.

### The gate and the slice — carried, with the equivalence proved and the reason stated

The reviewer did **not** re-run `corpus_gate.py` or the corpus-marked slice, and both rows
above are the cell's, carried on two grounds.

* **They are provably invariant across the gap.** The cell ran both at `2440e65`
  (`gate_final.log`: GREEN, 105 PASS / 3 WITHHELD / 1 REFUSED, verdicts 1 / 3 / 102 / 3,
  109 pinned PDFs, `GATE_EXIT=0`; `30 passed, 7,574 deselected`, `CORPUS_EXIT=0`).
  `git diff --stat 2440e65..12bb0cf` is **one file**,
  `docs/moneythumb-replacement/W3_TRACKA_LOG.md`. The gate reads no document under `docs/`
  and `-m corpus` collects no test from it, so the two measurements at `2440e65` ARE the
  measurements at `12bb0cf`. Every other floor row was re-measured at the tip anyway
  (§10) and every one of them reproduced.
* **The host was not free.** The concurrent L1-S3 cell began a whole-archive
  `regfp_zero_movement_sweep` at 10:02 and the review's own rule is one heavy harness per
  host. The reviewer's first two attempts to launch the gate were started against that
  sweep before the check was repeated, produced two concurrent `corpus_gate.py` processes
  writing one log, and were **killed and cleaned up** rather than reported; the host was
  left with the other cell's sweep alone and nothing of the reviewer's. That mistake is
  recorded here rather than tidied away. **No measurement in this review was taken while a
  second harness ran**: every reproduced number above comes from a sequential foreground
  run, and the last of them (the seam probe's tip capture) wrote its log at **10:01:26**,
  35 seconds before the other cell's sweep started at **10:02:01**.

A 13-minute re-confirmation of a result that a one-Markdown-file diff already guarantees is
not worth contending with another cell's proof run for. If Ocean wants it anyway it is one
command at the train, where the gate runs regardless.

### Provenance of the cell's long measurements — checked, and sound

The cell ran the two replays, the seam probe, the admission probe, the mutation table and
the two archive sweeps at earlier tips (`5a36ed7`, `ce67cdd`) and says that is sound because
nothing executable changed after. The reviewer checked it rather than accepting it:
`analysis/symitar.py`, `analysis/zions.py`, `analysis/community_section.py`,
`analysis/pipeline.py` and `analysis/sibling_omission.py` are **AST-identical between
`5a36ed7` and `12bb0cf` once docstrings are stripped** (the only later production commit,
`7dfac44`, is two prose paragraphs). The claim holds. It is moot for every number above
anyway, because the reviewer re-ran them at the tip.

---

## 2. Scope item ADJUDICATION 1 — is `yield_only` printed evidence, or an absence-shaped skip?

**It is printed evidence. Not absence, and not smuggled.** Three grounds, the third measured.

1. **The vocabulary already carries it.** L1-C17's table (design :892) lists
   `yield_only_arithmetic_with_summary_equality` — "the ratified `symitar._yield_only`
   predicate, applied AS WRITTEN with its fourth condition" — as a member. The card did not
   invent a token; it used one the reviewed design ratified.
2. **The design and its own independent reviewer already ruled on the mechanism.** Design §9
   F1: *"The yield-only skip at :425 IS on printed evidence and IS the ratified predicate,
   including its fourth condition. So one of the module's two ratified skips is implemented
   as ratified and the other is not."* `BATCH9_L1DESIGN_REVIEW.md` confirms F1 and confirms
   that `:419` (absence) and `:425` (yield-only) are genuinely distinct skips.
3. **What the paper prints on the three, measured by the reviewer.** A probe wrapped
   `symitar._yield_only`, ran the three documents through `analyze_document` and reported
   structure only — booleans and counts, never a figure, a description, a caption or a date:

| sha16 | rows the omitted section PRINTED | equation row printed | every row matches the anchored dividend pattern | every row posts as a CREDIT | section also declares dormancy |
|---|---:|---|---|---|---|
| `3600FE7830C4A484` | 1 | no | yes | yes | no |
| `9C5B7D628D7511EE` | 1 | no | yes | yes | no |
| `C067BE96F6B0BE0F` | 1 | no | yes | yes | no |

   The omitted section is **not empty**: it printed a dated posting, an opening balance and a
   running balance that closes on the ending balance the DOCUMENT states for that account
   elsewhere. `_yield_only` returning true is the assertion that all three of those printed
   figures agree. That is the paper stating the account received only its own yield — the
   opposite of "no rows were parsed".

**Two honest qualifications, both of which cut in the card's favour and one of which does not.**

* On all three, the section printed **no six-figure equation row**, so condition 4 is vacuous.
  That is condition 4 *as written* (it is conditional on the row being printed) and is a
  different thing from the design's §2.3 disclosure, where the PROBE fabricated `None`.
  Production passes the real `equation`. Checked in source and at run time.
* `symitar._yield_only`'s own docstring names the residual hole exactly there: *"Where the
  equation row is NOT printed — the issue all three archive movers belong to — the hole stays
  reachable and its consequence is silent."* **S2 removes the "silent" half**: such a section
  is now a recorded omission rather than a disappearance. The card improves this hole; it does
  not open it.
* What it does NOT resolve is the count. See MAJOR-1.

### MAJOR-1, stated precisely

The card's Scope names `analysis/symitar.py:419–420` (7 sections) and nothing else in that
file; the design's §6 S2 row names the same three sites and states *"Payload bytes move on
those 12 documents and on no others"*. The cell delivered 15 / 19 on the authority of the
symitar module's own docstring (*"SIBLING-OMISSION-SURFACE (batch 8), which owns both
together"*) — a real authority, and one the cell disclosed prominently rather than buried.

The cost is deferred, not absent. Design §1.5 makes a document carrying an omission
`("review", "sibling_section_omitted")`. When S3 lands that fold, **15** currently-`validated`
batch-8 shas move down the ladder, not 12. Under BATCH9-RULES *"every previously validated
batch-8 sha is protected"* that is a three-sha enlargement of a protected-cohort demotion, and
it is not a call a cell makes for itself. The three are `3600FE7830C4A484`,
`9C5B7D628D7511EE`, `C067BE96F6B0BE0F`, disjoint from the design's four.

**Asked of Ocean:** accept or refuse the expansion explicitly, and if accepted amend the
design's §6 S2 row and §7 staging to 15 / 19 so S3 prices the right number. Today's movement
is 0 either way (§1 claims 3, 5, 7), so nothing about this blocks composition on correctness
grounds — it is an authorisation and a bookkeeping obligation.

---

## 3. Scope item ADJUDICATION 2 — the two files outside the card's ownership

**Both are necessary and minimal, both strictly STRENGTHEN, neither is creep.**

* **`tools/l1_census.py`** (+10 lines: one import, one keyword argument, one comment).
  `_parse_sectioned_statement` gained a REQUIRED `ledger` argument with no default; this
  census calls that function directly, so without the follow-through it raises `TypeError`.
  A signature change and its callers in one commit is the same discipline the rules demand of
  registry pins. The alternative — a default — is the thing the cell's own fixture
  (`test_the_shared_callee_will_not_run_without_a_ledger`) exists to forbid, and forbidding
  it is the fail-closed direction. **Accept.**
* **`tests/test_corpus_gate_outcomes.py`** (+12/-1): `WATCHED` gains `analyze_document`.
  The new probe reaches the analysis through the DOCUMENT entry point, so without this the
  caller sweep reports the register entry STALE. Adding a name to the watched set BROADENS the
  sweep; it removes nothing. **Accept.**

### Composition note for Ocean — L1-S3 makes the SAME change with different prose

`.claude/worktrees/mt9-l1s3` (branch `wave9-l1s3`, merge-base `4953806`) contains an
independent edit to the identical line. Both produce the same final code:

```
WATCHED = {"analyze_markdown", "analyze_document", "cached_analysis"}
```

* **L1-S2** `tests/test_corpus_gate_outcomes.py` `@@ -43,7 +43,17 @@` — a 10-line `#:`
  comment ("…is already a declared call site… It costs nothing today…").
* **L1-S3** `tests/test_corpus_gate_outcomes.py` `@@ -43,7 +43,12 @@` — a 5-line `#:`
  comment ("…is what the nine production seams call since L1-S3…").

Resolve by keeping the code line once and taking S3's comment (it is the one that stays true
after S3 lands), or a union of both reasons. **L1-S3 adds no `EXCLUDED_ANALYSIS_CALLERS`
key**, and its `corpus_gate.py` hunks are at `:85`, `:205` and `:1400` — none of them the
register block — so the register itself composes as a clean union.

---

## 4. The register set-difference

`EXCLUDED_ANALYSIS_CALLERS`, keys parsed from the AST at each ref:

| comparison | keys | difference |
|---|---:|---|
| base `fea0bd2` | 33 | — |
| tip `12bb0cf` | 34 | **ADDED** `tools/l1s2_admission_probe.py`; removed none |
| `train9` (`da8bd47`) | 34 | vs base, `train9` ADDED `tools/pagecov_probe.py` (composed after this branch's base) |
| tip vs `train9` | — | tip adds `tools/l1s2_admission_probe.py`, lacks `tools/pagecov_probe.py`; **no key both add, no key re-declared, no duplicate key in the tip** |

Composition is a **union of the two additions**, the same manual resolution Ocean performed
for L1-S1 (`6c9e89f`). The entry is truthful: `tools/l1s2_admission_probe.py` does call
`analysis.pipeline.analyze_document` (`:87`, `:95`), publishes no verdict, and supplies the
reconstructed page partition as `sheets`. `tools/l1s2_mutation_table.py` and
`tools/l1s2_sweep_diff.py` call the analysis nowhere and correctly claim no entry — the
mutation table shells out to pytest and to the probe, the sweep differencer reads JSON.

**MINOR-5.** `tools/l1s2_sweep_diff.py` declares `--base` and `--tip` as `nargs="+"`.
Repeating the flag (`--base a --base b`) is accepted by argparse and **silently keeps only
the last**, so the tool prints a complete-looking table over one chunk. The reviewer's first
run reported `documents 830 … INHERITED=14` before the second, correct invocation reported
`3,380 … INHERITED=70`. Nothing in the output says which happened. Use `action="extend"`, or
refuse a second occurrence.

---

## 5. The fixtures the reviewer constructed, and their outcomes

Written from the readers' own printed grammar with figures and names invented by the reviewer,
not by editing the cell's fixtures. 22 cases; the file lives outside the repository.

| constructed shape | required | **outcome** |
|---|---|---|
| symitar: a printed sibling with a beginning balance, an ending balance, **no row and no declaration** | document REFUSED | **REFUSED** — `parse_symitar_statement` returns `None`, the collector is empty |
| symitar: the same sibling declaring idleness in an **unratified wording** | document REFUSED | **REFUSED** — wording-independence is the class being two *ratified* patterns, not the patterns being loose |
| symitar: the same sibling with the platform's own ratified declaration (positive control) | published + recorded | **published, one `printed_dormancy_declaration`** — so the three refusals above are refusals of the thing under test, not of a fixture that never reached the site |
| community_section: an idle block printing all six clauses | published + recorded | **published, one `printed_zero_activity_summary`** |
| community_section: zero TOTALS beside a **non-zero printed COUNT** | REFUSED | **REFUSED** |
| community_section: zero totals and zero counts, **pair does NOT coincide** | REFUSED | **REFUSED** |
| dakota_west: the same two shapes through its own entry point | as above | **as above** |
| the classifier directly: missing count column; missing balance; unreadable count; four near-miss dormancy wordings | all refuse | **all refuse**; the two ratified wordings admit |
| community_section / dakota_west: a printed account heading with **no summary grid at all** | (reviewer's expectation: REFUSED) | **PUBLISHED — see MINOR-3** |

### The mutant with no archive population, killed by an INDEPENDENT fixture

`restore_the_absence_skip` (a section with no evidence admitted anyway, wearing a ratified
label) is invisible to the archive by construction, so its only killer is a constructed shape.
The reviewer applied that mutant by hand to `analysis/sibling_omission.py`, ran **the
reviewer's own fixture file**, and restored:

```
MUTANT_APPLIED restore_the_absence_skip
7 failed, 15 passed        (baseline for this file: 2 failed, 20 passed)
RESTORED  -> git status --porcelain empty
```

Five of the reviewer's independently-built refusal fixtures fire on it. The cell's claim that
constructed absence-only fixtures are the real killer is confirmed by fixtures the cell never
saw.

### MINOR-3 — the shared callee's other exits, and their measured population

`analysis/community_section.py::_parse_sectioned_statement` returns `None` five ways. The card
taught **one** of them to record:

```
if not block:                    return None        # not recorded
if not summary:                  return None        # not recorded
if start_year != end_year:       return None        # not recorded
if _section_oracle_disagrees(…): return None        # not recorded
if not txns:  ledger.record(…);  return None        # <- the card's site
```

So the cell's sentence *"At each site the section is either ADMITTED on printed evidence and
recorded, or the DOCUMENT is REFUSED"* is true of the SITE and not of the function. The
reviewer's bare-heading fixture reaches the second exit through `dakota_west` (which does
enumerate the printed heading) and the document publishes with that heading dropped and
nothing recorded.

**Then the reviewer measured it on the archive** with a probe that wraps the callee and
watches the ledger across every call:

| registration | validated documents | callee calls | `None` + recorded | `None` + **SILENT** | documents publishing WITH a silent drop |
|---|---:|---:|---:|---:|---:|
| `community_section` | 59 | 65 | 6 | **0** | **0** |
| `dakota_west` | 3 | 6 | 2 | **0** | **0** |
| `mission_valley` | 36 | 36 | 0 | **0** | **0** |
| **total** | **98** | **107** | **8** | **0** | **0** |

`SILENT_DROPS=0 DOCS_PUBLISHING_WITH_ONE=0`. Every one of the eight `None` returns on the
archive is the recorded site. The gap is real in code and **empty on this paper**, and the
class of paper that would reach it — a printed heading whose block has no readable summary —
is the design's already-measured *"no sibling section LOCATED at all"* class (§2.3, 16
documents), which is S4's boundary-mechanism work. **MINOR, carried to S3/S4**, not a defect
of this card.

### An attack that failed, recorded because it was the sharpest one

`publish_omissions` is called by a reader **before** the registry has chosen a winner, so
"a losing candidate's drops are not the document's omissions" looked like a property the code
does not actually guarantee. It does: `analysis/parser_registry.py::resolve` (`:999–1013`)
returns on the FIRST registration whose `parse` yields a statement, so a candidate that
publishes always wins and a candidate that loses always returned `None` — and a reader that
returns `None` never reaches `publish_omissions`. The invariant holds by the registry's
first-wins rule. No finding.

---

## 6. The six conditions, and the standing rules

| condition | verdict | evidence |
|---|---|---|
| **R-a** — an idle sibling admitted ONLY on explicit structure establishing the sibling AND its empty/silent state; absence insufficient | **SATISFIED at the three named sites** | every one of the 19 admitted sections carries a NAMED class (§1 claim 2); `no_printed_evidence` is 0 of 16 at base and 0 refusals at the tip; the reviewer's absence-only fixtures REFUSE the document at all three sites; `absence_of_parsed_rows` is not a member and `SiblingOmission.__post_init__` raises on any non-member. Residual: MINOR-3, population 0 |
| **each account validates independently by the UNCHANGED validator** | satisfied | no validator touched; 117/117 payload byte-identical under `--expect-identical`; corpus gate verdicts unchanged |
| **NO document-level combined ADB** | satisfied | the probe measures `document block carrying a fact beyond the omission and the count: 0` on all 15 carriers; the document block holds only `account_count` and `omitted_sections` |
| **inter-account transfers INTERNAL, no double-counting** | not in scope (S4) | untouched |
| **no arbitrary or memorised account selection** | satisfied — not made worse | `dakota_west`'s `len(stmt.transactions) > len(best.transactions)` is unchanged and the cell says so; `parse_mission_valley_statement`'s literal product name (F4) is untouched; canonical guards 255 pass |
| **explicit currency evidence outranks defaults** | not in scope (S5) | untouched |
| **RULE S — the `Statement` docstring and every field description byte-identical** | **satisfied** | `analysis/schema.py` md5 identical base to tip; `analysis/serialization.py` diff empty; `DocumentReport`'s field set identical to base, so no new field and no new RULE S clause is owed; `tests/test_document_report.py` 26 passed |
| **fail closed** | satisfied and strengthened | three readers gained a refusal branch that did not exist; the six clauses read fail-closed (an absent column refuses rather than defaulting); `_is_zero_count` treats `bool` and unreadable text as absence |
| **never gain by relaxing** | satisfied | newly validated 0; nothing relaxed; the only direction of change is more refusal |
| **no statement-specific hardcodes** | satisfied | the two dormancy patterns are the ratified ones, carried over BYTE FOR BYTE (`git show fea0bd2:analysis/symitar.py` `:116` and `fea0bd2:analysis/zions.py` `:78` are character-identical to `sibling_omission.py` `:107–108`); no new phrase, no product name, no account number; the class is a tuple a new wording is APPENDED to |
| **$0, deterministic** | satisfied | no model call anywhere on the branch |
| **commit messages carry no printed text or archive token** | satisfied | scanned 13 commits against two populations, all classes 0; read by eye — the messages speak in classes ("a fixture date", "two paragraphs of module prose") |

### The privacy discards, inspected rather than accepted

The scan reports `raw_hit_count 4`, `hit_count 0`, discarded by `round_money` ×1 and
`words_class` ×3. Both are **standing, committed, documented and self-tested** rules in
`tools/privacy_scan_branch.py` (the exclusion table at `:541` carries its own positive and
negative cases at `:555–562`), applied since the batch-8 train — not invented here.

The reviewer re-ran with `--no-exclusions` and looked at the four tokens (not reproduced here
and not committed): the MONEY one is a `.00` figure in the cell's own invented test fixture and
is the arithmetic sum of that fixture's other invented figures; the three WORDS ones are
generic two-word English phrases occurring in prose in `analysis/`, `docs/` and `tools/`. None
carries a document's identity. **The discards are legitimate.**

The residual risk is the program's, not this card's, and the scanner's own docstring names it:
`round_money` is blanket ("the rule does not stop at small") and `words_class` discards the
WORDS class entirely, so a leaked NAME is invisible to this instrument. That is
`FIXTURE-PRIVACY`'s standing card.

---

## 7. MINOR-1 — the design's skip probe is left red on `train9`

`tools/l1_design_skip_probe.py` verifies three watched lines against the source text they must
sit on before it reads a document, and refuses (`exit 3`) when one has moved. This card moved
all three, so after composition a committed instrument — the one that produces the design's
§2.7 headline table, which BATCH9-RULES requires to be reproducible from `tools/` — cannot be
run on `train9` at all.

The cell's position ("its refusal is evidence that the sites changed") is fine as a statement
about this branch and is not a durable answer for the train. **Re-anchor it** (the three
`LineSite` entries at `tools/l1_design_skip_probe.py:124–131`):

| module | watched now | expected text | **at `12bb0cf`** |
|---|---:|---|---:|
| `analysis.symitar` | 420 | `continue` | **457** (the `continue` after the record; the absence branch itself is now `return None` at 456) |
| `analysis.community_section` | 622 | `return None` | **655** (after `ledger.record(` at 643) |
| `analysis.community_section` | 984 | `stmt.transactions` | **1043** |

Or retire it in favour of `tools/l1s2_admission_probe.py` with a one-line note in the design
saying which instrument answers §2.7 from now on. Either is acceptable; leaving it red is not.
Ocean's at the train, or a one-commit follow-up on the design cell's surface.

---

## 8. MINOR-2 — three record inaccuracies in W3 §L1S2

Not numbers that change any conclusion; all three are the record describing itself.

1. *"were all re-run at the FINAL tip `2440e65`"* — `2440e65` is commit 11 of 13; the tip is
   `12bb0cf`. (The two later commits are W3-only, so the numbers stand.)
2. Of that list, only `corpus_gate.py` and the corpus-marked slice actually ran at `2440e65`
   (`gate_final.log`). The guards, the conformance set, the suite and **both** privacy scans
   ran at `4b0a4c2` (`final.log`). At the true tip the reviewer measures: guards 255,
   conformance 1,270, suite 7,527 / 43, gate GREEN 105/3/1, corpus 30 — unchanged.
3. *"commit-message scan … over **12** commits"* — the cell's own log records
   `commits_scanned: 10` at the tree it ran at, and the tip measures **13**. The count 12
   reproduces at no tree on this branch. `hit_count` is 0 at every one of them.

Suggested repair: one W3 amendment naming the tree per proof row honestly, and `13` (or the
scan's own `commits_scanned` with no number restated in prose, which is what commit `12bb0cf`
was already trying to do).

---

## 9. What the 6 seam movers are, explained by the reviewer

The cell says the six are "inside the 15". The reviewer checked the arithmetic rather than the
assertion. Intersecting the seam cohort with the 15 named carriers:

* the seam cohort is **232** documents and contains exactly **6** of the 15 carriers —
  `037774298FE1CD66`, `0A14AC169DEA62D4`, `1019F3C638AB1C81`, `21643A62A463EA39`,
  `3600FE7830C4A484`, `F748A799FDC7F25E`. The other **9** are not in the cohort at all;
* **every carrier in the cohort moved and nothing else did.** 6 of 6. RULE S clause 2 is what
  moves them: `analysis/serialization.py::_publishes_todays_payload` requires
  `not document.omissions`, and that clause is now false for a carrier;
* the **shape** changes, which is why the probe lists eleven key names. Base keys on each of
  the six: `classifications, detection, escalated, integrity, metrics, model_used, quality,
  reconciliation, statement`. Tip keys: `accounts, document`. The eleven names are the UNION
  of the two shapes — no value inside `metrics` or `integrity` changed;
* the **ACCOUNT seam payload is byte-identical on all six** (and on all 232), so the account
  block inside the new shape is the one the run of record stored.

**A consequence Ocean should carry forward explicitly.** At S3/S4, when production seams move
to `analyze_document`, those 15 documents publish a payload with **no top-level `statement`
key**. Design §1.4 makes that deliberate — *"its absence is what makes such a consumer
stop"* — but the blast radius is 15 protected documents landing on nine production readers at
once. S3 owns it; this review names the size.

---

## 10. Floor reproduced at the tip `12bb0cf`

| proof | result | exit |
|---|---|---:|
| tree state | `git status --porcelain` empty before and after every run | — |
| canonical guards (5 files) | 255 passed | 0 |
| canonical conformance (7 files) | 1,270 passed, 40 skipped | 0 |
| full default suite | 7,527 passed, 43 skipped, 34 deselected | 0 |
| `tests/test_sibling_omission.py` | 38 passed | 0 |
| `tests/test_corpus_gate_outcomes.py` | 24 passed, 10 deselected | 0 |
| `tests/test_document_report.py` | 26 passed | 0 |
| `python corpus_gate.py` | *carried from `2440e65`* — GREEN, 105 PASS / 3 WITHHELD / 1 REFUSED; verdicts 1 / 3 / 102 / 3 | 0 |
| corpus-marked slice | *carried from `2440e65`* — 30 passed, 7,574 deselected | 0 |
| `cohort_replay` at the tip, `--expect-identical` | 117/117 payload identical, 0 changed, 0 regressions | 0 |
| `l1_design_skip_probe` at a pristine `fea0bd2` | 117 / 12 / 16 / 0 | 0 |
| `l1s2_admission_probe` at the tip | 117 / 15 / 19 / 0 refused; 8 + 8 + 3; 15/15 identical | 0 |
| `l1s1_seam_probe`, pristine base -> tip | account 232/232; flags+order 232/232; outcome 232/232; document 226 / 6 moved, all six explained | 2 |
| `l1s2_mutation_table` (two halves) | 6 mutants, 6 killed, 0 survived; tree clean each time | 0 |
| `l1s2_sweep_diff` over the stored sweeps | 3,380; aggregates identical; 70 inherited / 0 movers / 0 removed | 0 |
| added-line privacy scan | `hit_count` 0 over 2,208 added lines / 120 documents | 0 |
| commit-message scan, five registrations | `hit_count` 0 over 13 commits / 120 documents | 0 |
| commit-message scan, `--shas` the 15 carriers | `hit_count` 0 over 13 commits / 15 documents | 0 |
| reviewer's own 22 constructed fixtures | 20 pass; the 2 failures are MINOR-3's bare-heading shape, not a regression | 1 |

**Not re-run, and why.** Three things, each with its reason on the record.

* **The two whole-archive sweeps** (about 50 minutes each, one per tree). Both logs are on
  disk with per-chunk exits and a terminator, at `ce67cdd` and `fea0bd2`; the differencer
  over them was re-run and reproduces exactly. Re-running 3,380 documents twice is not owed
  and would measure the same two trees.
* **The base control replay.** The base tree was independently re-established in a pristine
  detached worktree for claims 1 and 5, and the tip replay was run under the stricter
  `--expect-identical`, which is the half that can fail.
* **`corpus_gate.py` and the corpus-marked slice** — carried from `2440e65` with the
  equivalence proved by a one-Markdown-file diff, and the host left to the concurrent cell.
  See §1, "the gate and the slice".

---

### The reviewer's own instruments

Three, written for this review and kept outside the repository so the branch stays the
cell's — described here precisely enough to be rebuilt, since two of them produce numbers
this review leans on.

* **the fixture file** — 22 constructed cases (§5), figures and names invented by the
  reviewer, built from the readers' printed grammar rather than by editing the cell's
  fixtures. Also used as the independent killer of `restore_the_absence_skip`;
* **the silent-drop probe** — wraps `analysis.community_section._parse_sectioned_statement`,
  records `(returned None, did the ledger grow)` for every call, runs the 98 `validated`
  documents of `community_section` / `dakota_west` / `mission_valley` through
  `analyze_document`, and counts a call SILENT when it returned `None` and the ledger learned
  nothing. Prints registration ids, sha16s, counts and branch names only;
* **the yield-only evidence probe** — wraps `analysis.symitar._yield_only`, runs the three
  named documents, and reports STRUCTURE for each firing: row count, whether the equation row
  was printed, whether every row matches the anchored dividend pattern, whether every row
  posts as a credit. Booleans and counts only; no figure, description, caption or date is read
  out of it.

---

## 11. Verdict

**APPROVE WITH FINDINGS.** The card does what it set out to do and does it fail-closed. Three
readers that dropped a printed account because it parsed no row now either name the printed
evidence that admits the omission or refuse the document; the vocabulary is closed where the
record is built; the two ratified dormancy wordings are one class rather than two per-issuer
copies, carried over byte for byte; the record lands on the document object and `Statement` is
untouched; and the archive does not move — 117 of 117 byte-identical, 232 of 232 at the account
seam, 0 movers over 3,380, 0 privacy hits, and a corpus gate that was GREEN at the last tree
that could change it.

None of the five MINORs blocks composition. **MAJOR-1 does not block it either** — it asks for
a decision and a documentation amendment, not a code change — but the decision should be taken
before S3, because S3 is where the extra three shas are paid for.

---

## Re-review (closure 9f30b88) — 2026-08-30

**NOT CONFIRMED — two items, both documentation/coverage, neither a production change.**
Production code is unchanged by the closure and everything that was APPROVE-able before is
still measured green. What stops composition is (1) a §7 note that now contradicts Gustavo's
Q10 ruling and will merge beside Ocean's `SUPERSEDED` annotation, and (2) a Q10 pin that a
document-level fold walks straight past — demonstrated with a mutant, fixable in one commit.

Closure tip `9f30b88` (21 commits from `fea0bd2`, including this review's own `f7d7aca`);
floor tree `67f4b8d`; `git diff --stat 67f4b8d..9f30b88` is **one file**,
`docs/moneythumb-replacement/W3_TRACKA_LOG.md`. `git diff --stat f7d7aca..9f30b88` touches
**no production module** — the design, W3, two new test files, and three instruments
(`l1_design_skip_probe.py`, `l1s2_mutation_table.py`, `l1s2_sweep_diff.py`). `analysis/` is
byte-identical to the tree this review already approved.

### Per finding

| finding | claimed | **measured** | verdict |
|---|---|---|---|
| **MAJOR-1** design amended additively | 32 insertions / 0 deletions; §6.2 block 12/16 + 3/3 = 15/19 with the three sha prefixes; dated §7 note attributing the widening to Ocean | `git diff --numstat` = **32 / 0**. §6.2 carries the delivered-population table and the three prefixes; §7 carries a dated note that names Ocean as the acceptor and this review's §2 as the adjudication. Purely additive — the original 12/16 measurement is untouched, which is right | **CLOSED on the amendment, NOT CLOSED on its wording — see BLOCKING-1** |
| **MINOR-1** skip probe re-anchored | `:453` / `:655` / `:1043`, both-outcome lines; exit 0, 117 / 12 / 16, sites 7/8/0/1, 8+8+0 | **exit 0; 117 read / 12 documents / 16 sections; sites 7 / 8 / 0 / 1; 8 + 8 + 0 by class; seven clauses 8 of 8.** Identical, number for number, to the run this review took at a *pristine `fea0bd2` worktree* — which is what makes the re-anchoring correct rather than merely non-refusing | **CLOSED** |
| **MINOR-2** floor rebuilt, provenance named | guards 255, conformance 1,270/40, register 24, document-report 26, fixtures 58 (38+20), suite 7,547/43/35 | **255 / 1,270 + 40 skipped / 24 + 10 deselected / 26 / 58 (and 20 for the ruling file alone) / 7,547 passed, 43 skipped, 35 deselected** — all exit 0, all at `9f30b88`. The W3 floor table names its tree (`67f4b8d`) and the message-scan row now names its count *per tree*, which is the actual repair | **CLOSED** |
| **MINOR-3** carried to S3/S4 | this review's numbers, no code change, because routing the other exits would refuse the "no sibling section LOCATED" class (16 documents, §2.3) | **Agreed.** The reason is correct and it is the reviewer's own measurement: the population is 0 on this archive, and the three unrouted exits sit in front of a class the design has already assigned to S4's boundary rung. Refusing there would trade a measured zero for 16 documents | **CLOSED as carried** |
| **MINOR-4** concurrency refusal implemented | tasklist/ps, self excluded, exit 5, `--allow-concurrent` | **Verified against a sleeping python**: the harness printed `REFUSING: another python process is working on this host`, listed the offenders as `name:pid`, and returned **exit 5** — *before* the dirty-tree check and before any patch was written; `git status --porcelain` empty throughout. `--allow-concurrent` then ran the mutant to completion (1 killed, 0 survived) and left the tree clean. Self-exclusion is by `os.getpid()`, and the clean-host runs did not refuse | **CLOSED** |
| **MINOR-5** `action="extend"` | both spellings → 3,380 / 70 / 0 / 0, exit 0 | **Both spellings measured: `documents` 3,380 / 3,380, `compared_payload` 2,669, `INHERITED=70 MOVERS_AT_THE_TIP=0 REMOVED=0`, exit 0.** The repeated-flag form, which silently differenced one chunk before (830 / 14), now covers the whole archive | **CLOSED** |
| **scans** | 0 over 3,221 added lines, raw 4 (1 `round_money` + 3 `words_class`); messages 0 with `--shas` over 20 commits | **Reproduced exactly at the trees named**: at `67f4b8d`, 3,221 added lines, raw 4, `round_money` 1 + `words_class` 3, `hit_count` **0**. At the tip `9f30b88`: 3,419 added lines, raw 3 (1 + 2), `hit_count` **0**; messages `hit_count` **0** over **21** commits (19 at `67f4b8d`, 20 at `3b92785`, 21 at the tip). Every count the W3 states is right for the tree it names. Discards judged: the same two standing, committed, self-tested rules as before, firing on the cell's own invented fixture arithmetic and on generic English word-pairs in prose | **CLOSED** |
| **register** | union with `train9` | base 33 → tip 34: **ADDED `tools/l1s2_admission_probe.py`**, removed none. `train9` (`918de4c`) adds `tools/pagecov_probe.py`. **No key added by both, no duplicate, no re-declaration** | **CLOSED** |

### The Q10 pins, read and mutated

`tests/test_l1s2_omission_ruling.py` (**20 passed**) pins both halves per evidence class: the
omission is surfaced with a ratified class named; the account stays `validated` through the
*unchanged* `classify_outcome`; and — stronger than a literal `validated` —
`test_the_omission_changes_the_accounts_outcome_by_nothing` asserts the same account reaches
the *same verdict for the same reason* with and without the idle sibling on the page.
`test_nothing_is_misattributed_from_the_omitted_sibling` gives independence condition 5 as a
byte comparison. The fail-closed half carries two absence-only fixtures and an
ambiguous-boundary one (a sibling that POSTED).

`tests/test_l1s2_protected_carriers.py` (**1 passed, 26 s — it really replays**) pins the
population at **exactly 15**, asserts the pinned `dakota_west` carrier is inside it, and for
each: publishes, carries at least one omission, every reason in `EVIDENCE_CLASSES`, account
outcome `validated`, account block byte-identical to the run of record. It skips **only** when
the cold cache or the run pointer is absent, with a stated reason, and a *resolvable* document
whose text is missing is a **failure**, not a skip. No vacuous pass.

**Mutant Q-1 — the omission is admitted but never surfaced** (`publish_omissions` made a
no-op; applied in-tree, restored, `git status --porcelain` empty before and after):

```
ruling pins        -> 5 failed, 15 passed   (exit 1)
protected carriers -> 1 failed              (exit 1)   "publishes with NO omission recorded"
```

The *surface* half bites, on constructed fixtures and on the real 15 alike.

**Mutant Q-3 — the S3 fold, written exactly as design §1.5 originally had it** (a
`classify_document` added to `telemetry/record.py` returning
`("review", "sibling_section_omitted")` whenever `document.omissions` is non-empty; restored,
tree clean):

```
ruling pins                -> 20 passed  (exit 0)
protected carriers         ->  1 passed  (exit 0)
document-report + register -> 50 passed  (exit 0)
```

**Every pin passes while all 15 protected carriers are demoted.** That is BLOCKING-2.

### BLOCKING-1 — the §7 note now contradicts the ruling it will merge beside

The dated §7 note ends:

> "when §1.5's omission override lands, **15** protected batch-8 shas fold to `review`, not 12.
> That override is a ruling Ocean is putting to Gustavo; S3 keeps it dark until it is answered."

and the §6.2 block ends "**S3 prices 15 protected shas under §1.5's omission override, not 12.**"

The ruling has been answered. On `train9` (`918de4c`) design §1.5's third override already reads
**"SUPERSEDED by Gustavo's Q10 ruling (2026-08-30, BATCH9_TRANSITION §8.7): the document is NOT
demoted"**. The two edits do not collide textually — `train9` touches `@@ -329`, this branch
touches `@@ -1058` and `@@ -1193` — so they will merge **cleanly into a document that
contradicts itself**, and it will contradict itself precisely where S3 reads for its scope:
§1.5 saying do not demote, §6.2 and §7 saying price 15 demotions and keep the ruling dark.

Given that Q10 exists *specifically* to stop a silent demotion of these 15, shipping a design
that instructs S3 to perform one is not a cosmetic defect. **Correct before composition.** The
substance of both blocks is right and should stay: the population is 15 / 19, the widening was
Ocean's to accept, and S3 must price 15 rather than 12 — what changes is that it prices them as
documents that **surface an omission and keep their account validated**, not as demotions.

### BLOCKING-2 — the pins cover the account leg only, and a document fold demotes through the other

The ruling as relayed requires that "the 15 protected carriers must carry pinning coverage so
S3 cannot silently demote them." As delivered they carry coverage of the **account** outcome.
Mutant Q-3 shows a document-level fold demoting all 15 with every pin green.

This is disclosed rather than hidden — both test docstrings say "there is no document
classifier at this tree" and "S3: when `classify_document` lands, extend these cases to assert
its verdict too". That is honest, and it is a comment. Q10 asked for a mechanism, and the
failure mode it was written against is exactly a stage landing a fold that nobody's test
notices — which is how §1.5's override survived unchallenged until Gustavo ruled.

**The remedy is cheap and does not require S3's work**: a tripwire that fails the moment a
document-outcome fold exists without the carrier assertions being extended — e.g. assert that
no `classify_document` (or equivalently-named document-outcome symbol) is exported by
`telemetry.record` or `analysis.pipeline`, with the failure message reading "a document fold has
landed: extend `tests/test_l1s2_protected_carriers.py` to assert its verdict on all 15, per Q10".
Ten lines, no production change, and it converts the hand-off comment into the mechanism the
ruling asked for. Alternatively Ocean rules explicitly that the account-leg pin plus the written
hand-off is the coverage intended, and this becomes CLOSED by decision rather than by code.

### A smaller observation, not blocking

The fail-closed cases assert `pytest.raises(Exception)`. That passes on *any* exception,
including one thrown by a fixture that never reached the site, so it is weaker than the rest of
the file — and only the symitar absence case has an anti-vacuity companion
(`test_the_refusal_fixtures_differ_from_the_admitted_ones_only_in_the_evidence`). Naming the
class, or asserting that nothing was published rather than that something was raised, would
make those three cases as strong as the four above them. Worth doing whenever the file is next
touched; it does not affect this verdict.

### Floor, re-measured at the closure tip `9f30b88`

| proof | measured | exit |
|---|---|---:|
| tree state | `git status --porcelain` empty before and after every run, both mutants included | — |
| canonical guards (5 files) | 255 passed | 0 |
| canonical conformance (7 files) | 1,270 passed, 40 skipped | 0 |
| `tests/test_corpus_gate_outcomes.py` | 24 passed, 10 deselected | 0 |
| `tests/test_document_report.py` | 26 passed | 0 |
| `tests/test_sibling_omission.py` + `tests/test_l1s2_omission_ruling.py` | 58 passed (38 + 20) | 0 |
| `tests/test_l1s2_protected_carriers.py` (corpus-marked) | 1 passed, 26 s | 0 |
| full default suite | 7,547 passed, 43 skipped, 35 deselected | 0 |
| `l1_design_skip_probe`, re-anchored | 117 / 12 / 16; sites 7/8/0/1; 8+8+0; clauses 8 of 8 | 0 |
| `l1s2_sweep_diff`, both flag spellings | 3,380; 70 inherited / 0 movers / 0 removed | 0 |
| `l1s2_mutation_table` concurrency refusal | exit 5 on a busy host, tree untouched; `--allow-concurrent` runs, 1 killed / 0 survived | 5 / 0 |
| added-line privacy scan | `hit_count` 0 over 3,419 added lines (3,221 at `67f4b8d`) | 0 |
| commit-message scan, `--shas` the 15 carriers | `hit_count` 0 over 21 commits | 0 |
| `python corpus_gate.py` | **carried from `67f4b8d`** — GREEN, 105 PASS / 3 WITHHELD / 1 REFUSED; verdicts 1 / 3 / 102 / 3 | 0 |
| corpus-marked slice | **carried from `67f4b8d`** — 31 passed (30 + the protected-carriers proof), 7,594 deselected | 0 |

**The gate and the slice, carried again and why.** `git diff --stat 67f4b8d..9f30b88` is one
Markdown file; the gate reads no document under `docs/` and `-m corpus` collects no test from
it, so the `67f4b8d` runs *are* the runs at `9f30b88`. The corpus-marked slice's new member was
run directly at the tip anyway (1 passed, above), which is the only part of that slice this
closure changed. The host was held throughout by the concurrent L1-S3 cell's whole-archive
`regfp_zero_movement_sweep`; one heavy harness per host, and a 40-minute re-confirmation of a
result a one-file diff already guarantees is not worth contending for it.

### Verdict

**NOT CONFIRMED — BLOCKING-1 (the §6.2 / §7 wording contradicts the ruled Q10 and will merge
beside `train9`'s `SUPERSEDED` annotation) and BLOCKING-2 (the Q10 pins pass while a document
fold demotes all 15; needs a tripwire, or Ocean's explicit ruling that the account-leg pin is
the coverage intended).**

Everything else this closure set out to do is CLOSED and re-measured: the design amendment is
additive and attributes the decision correctly, the skip probe is re-anchored on both-outcome
lines and reproduces the pristine-base numbers exactly, the floor is rebuilt with its
provenance named per tree, both instrument defects are fixed and verified by exercising them,
the scans are 0, and the register composes as a union. No production code changed, and the
archive still does not move.
