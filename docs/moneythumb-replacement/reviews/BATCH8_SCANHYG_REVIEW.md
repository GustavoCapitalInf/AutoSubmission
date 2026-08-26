# BATCH 8 REVIEW — SCAN-HYGIENE (`wave8-scanhyg`, tip `24b5f8e`, base `10cc722`)

Independent adversarial review. The reviewer did not write this code and asked
the cell nothing; every headline number below was re-measured on this host.
Read: the card `docs/agent-handoffs/SCAN-HYGIENE.md`, the whole branch diff,
`W3_TRACKA_LOG.md` §SCANHYG SH0–SH13, `analysis/tables.py::unique_match`,
`analysis/adb.py`, the four registrations, and the shared privacy instrument on
`main`. Nothing else.

**No archive content appears in this file.** Documents are named by an 8-hex
`content_sha256` prefix; magnitudes are classes; no figure, date, name, account
number, reference or merchant string is quoted.

**Closed file list** (`git diff --stat 10cc722..wave8-scanhyg`) — **15 files,
+3,228 / −119**: `analysis/citizens.py`, `analysis/date_tokens.py`,
`analysis/eq_bank_scanned.py`, `analysis/parser_registry_entries.py`,
`analysis/scanned_small_bank.py`; `tests/test_citizens_scanned.py`,
`tests/test_eq_bank_scanned.py`, `tests/test_no_parser_helper_clones.py`,
`tests/test_shared_parser_utils.py`, `tests/test_southside_scanned.py`;
`tools/scanhyg_family_replay.py`, `tools/scanhyg_gate_probe.py`,
`tools/scanhyg_mutation_table.py`, `tools/scanhyg_pinned_replay.py`;
`docs/moneythumb-replacement/W3_TRACKA_LOG.md`.

---

## VERDICT: **APPROVE WITH FINDINGS** — 0 BLOCK, 1 MAJOR, 5 MINOR

Every behavioural claim in §SCANHYG reproduces, and several reproduce to the
digit. Nothing in the findings below touches a published financial figure, an
outcome class, a pinned document or the protected core.

| claim | re-measured at HEAD | verdict |
|---|---|---|
| population **47** = citizens 21 + southside 9 + texas_first 8 + eq_bank 5 + apex 4 | 47, derived independently from `rows.csv`: 41 dispatched + 6 declined | reproduces |
| **0** validated movers, **0** outcome movement | `outcome_moved: 0` over 47 | reproduces |
| **8** withheld payload movers = 5 southside + 3 citizens | the same 8 shas, all `withheld/withheld_adb` → `withheld/withheld_adb` | reproduces |
| no financial leaf moves | 26 distinct moved leaf paths across all 8; **every one** is `integrity.flags[]`, `integrity.notes[]`, `integrity.risk_level`, `integrity.possible_document_issue`, `metrics.notes[]`, `quality.notes[]` or `quality.summary_totals_reliable`. No amount, balance, count, date, transaction or `average_daily_balance` | reproduces |
| base reproduces the run of record **41/41** | `base_matches_run_of_record: 41`, `base_differs_from_run_of_record: 0` | reproduces |
| **PINNED 109 replayed, 0 movement**, 6 owned | `{"pinned":109,"identical":108,"moved":0,"refused_both_sides":1,"claimed_by_target_reader":6}`, `findings: []` | reproduces |
| mutation table 30 / 25 killed / 5 survivors | 30 / 25 / 5 / 0 unapplied, baseline `251 passed` exit 0, `tree_clean_after: true` | reproduces |
| canonical guards **252 → 253** | `253 passed`, exit 0 | reproduces |
| canonical conformance **1,164**, registry **75** | `1164 passed, 35 skipped`, `len(load()) == 75` | reproduces |
| SS-UNIQUE-MATCH census: 72 rows, 0 printed twice, 0 with two readings | 9 docs × 8 rows = 72; `rows_printed_more_than_once: 0`; `rows_with_two_distinct_readings: 0` | reproduces |
| the two EQ declines refuse at `sole_day` pass 2 with **3** and **2** candidates | `E630CB66` pass 2 candidates 3; `B0E16E92` pass 2 candidates 2 | reproduces |
| the clone-bound sweep: safe band, next candidate needs 8 | offenders empty at every bound 1–7; `fiserv_premier._issuer` (8 statements) enters at 8 | reproduces |
| D5's reach is 63 tokens, all leading-zero | **63**, and **0** of them begin with anything but a literal `0` | reproduces |
| TG9/TG10 not implemented | `analysis/adb.py` absent from the diff and still refuses any out-of-period row (`adb.py:495`); no changed reader sets a currency field; `average_daily_balance` unmoved on all 47 | reproduces |
| privacy MONEY/DIGITS/DATES 0, WORDS 2 | re-run over a **wider** population (41, apex included): MONEY 0, DIGITS 0, DATES 0, **WORDS 2** — the same two adjacencies | reproduces (scope caveat: finding 2) |
| control bytes 0 | 0 across all **15** committed files (the record says 14) | reproduces |

Three doctrine surfaces were checked directly and all hold. **Repair doctrine:**
an AST scan of every new function (`daily_grid_amount_contradictions`,
`printed_section_total_contradictions`, `closing_accrual_contradictions`,
`_southside_daily_cells`, `day_readings`, `sole_day`) finds **zero** assignments
to any attribute or subscript of the statement they inspect — nothing is
repaired, nothing is preferred, no figure is written. **Fail-closed:** 144
adversarial `(text, statement)` pairs across the three new checks — empty text,
NUL bytes, 5,000-char runs, repeated page markers, astral characters, a
duplicated 400-row ledger, an undated transaction, a reversed period, an
unparseable period, missing balances — produce **0 exceptions and 0 non-list
returns**; a period the scan damaged into spanning four centuries returns in
0.00s. (The pipeline is fail-closed one layer up too: `pipeline.py:398-404`
catches a raising check and degrades it to `integrity_check_exception` →
review.) **Protected modules:** `analysis/adb.py`, `tables.py`, `schema.py`,
`pipeline.py` are absent from the diff; the `parser_registry_entries.py` hunks
add `integrity_checks` and nothing else — the three added entries carry no
other key.

**The `risk` promotion `review` → `high` is a QUALITY LABEL, not a doctrine
question.** `conflicting_statement_summaries` is a pre-existing shared flag;
`pipeline.py:490-505` sets `possible_document_issue` on any contradiction and
`pipeline.py:771-780` clears `summary_totals_reliable` from it. Every line of
that is unmodified shared policy that `columbia_bank` and `brex` already trip,
all 8 affected documents are `withheld` before and after, and no funding
decision moves. §SH11 item 4 names it correctly.

---

## FINDINGS

### 1. MAJOR — a privacy claim in shipped production source that does not reproduce

**Claim.** `135a719` restated three archive figures as classes and added to
`analysis/scanned_small_bank.py:672`: *"The size is stated as a CLASS here and
everywhere else in tracked source: the figure is the document's."* §SH10 repeats
the universal.

**Evidence.** It is false, and the counterexamples are in a file this card owns
and edited in the same commit. `analysis/citizens.py:297` states the citizens
cheque over-read — the very finding the same commit reclassed five lines away in
`printed_section_total_contradictions` — as an exact archive figure;
`analysis/citizens.py:206` states two archive debit magnitudes to the cent. Both
are present verbatim at base (`git show 10cc722:analysis/citizens.py`, same line
numbers), so this branch did not introduce them and the shared instrument, which
scans **added lines only**, is structurally unable to see them. The sentence,
however, is this branch's, and it is wrong.

**Why MAJOR.** The precedent is `BATCH8_COREENC_REVIEW` finding 1 — a
measurement in shipped source that does not reproduce — and this one is a claim
about the standing privacy rule that was a batch-7 BLOCK, asserted over a file
the card owns.

**Closure (either is cheap).** Redact `analysis/citizens.py:206` and `:297` to
classes, which makes the sentence true and is the shape `cc64232` already used
for the census; or narrow the sentence to "here". Git history retains the tokens
either way — that is Gustavo's call, as it was for `cc64232`.

### 2. MINOR — the privacy scan the record calls "at the final tree" is not

**Claim.** §SH10: *"The scan at the final tree, over the 38 documents of the four
readers' population, **2,656 added lines**."*

**Evidence.** The branch's diff adds **3,228** lines. 3,228 − 2,656 = **572**,
which is exactly the line count of `W3_TRACKA_LOG.md` in `git diff --stat
10cc722..wave8-scanhyg`. The recorded scan therefore ran before `62d7d17` and so
never scanned the record's own 572 lines — the same file §SH10 says introduced
three collisions of its own (`f0ce314`).

**Closure — measured here, and the conclusion survives.** Re-run at the true
final tree over a **wider** population than the record's (41 documents, `apex_scanned`
included; 4,650 printed MONEY tokens, 4,139 of them distinctive), **3,228 added
lines**: `MONEY 0, DIGITS 0, DATES 0, WORDS 2`, exit 1 (the tool exits 1 on any
hit). Both WORDS hits are the two the record discloses and both are code-only
adjacencies: `tests/test_citizens_scanned.py:460` (a printed section label that
is institution furniture present in `analysis/citizens.py` at base, beside the
test's own loop variable) and `tests/test_eq_bank_scanned.py:734` (a registry
loader name beside a parser id). Fixtures are invented and stated to be
(`tests/test_eq_bank_scanned.py:11-18`); the southside and citizens fixtures use
an invented 2026-04 period, the EQ Bank fixture an invented 2026-09 one, and no
DATES hit lands. **The record's number should be restated as 3,228 over the
final tree; nothing leaks either way.**

### 3. MINOR — the day gate's change is not monotone, and the record names only the narrowing

**Claim.** §SH4 presents SCAN-DAY-GLYPH as an evidence gate that refuses what the
base reader silently guessed, and prices it at **+0**. The `_resolve_dates`
docstring describes pass 2 as "the days its nearest LEGIBLE neighbours bound it
between".

**Evidence.** Base's pass 2 required the two neighbours to name the **same** day
and then took it; the branch's requires exactly one of the cell's enumerated
readings to fall in the **span** between them. That is a two-directional change,
and both directions are reachable. Measured base-vs-branch on `_resolve_dates`
alone, base loaded from its own blob at `10cc722` (10 constructed shapes, no
archive text): **6 same, 3 stricter, 1 WIDER**.

* the widening: a stray glyph before a digit whose neighbours are ten days apart
  — base resolves the cell at pass 1 to a day that breaks the printed order and
  the monotonicity gate **refuses the document**; the branch resolves it inside
  the span and **publishes a reconstructed date**. A date is a financial leaf.
* one of the narrowings is a **correct base derivation now lost**: a lone stray
  glyph between two agreeing two-digit neighbours. Base derived it from the
  printed order alone and was right to; the branch refuses, because
  `day_readings` of a single glyph is `{1..9}` and can never contain a two-digit
  day. Fail-closed, so nothing wrong is published — but the reader is less
  capable than base on a shape base handled soundly.

Archive impact is **zero and measured** (EQ Bank 5/5 unmoved, 3 identical and 2
declined as before), and mutant D3 plus two named tests pin the gate itself.

**Closure.** Two sentences in §SH4 naming both directions, and — if the train
wants the shape pinned — a test for each. No code change is owed.

### 4. MINOR — K3 is closable, and the closure is one assertion the record declines to write

**Claim.** §SH8.1 discloses K3 as "a real, narrow gap … left for review", and
§SH11 item 2 carries it.

**Evidence and adjudication.** K3 reproduces exactly: lowering
`NEAR_CLONE_MAX_STATEMENTS` from 6 to 2 leaves the guard's offender list empty
over all 92 modules, and no test notices, because the self-check
`_is_unique_match_shape(removed)` does not consult the bound. **The bound is
pinnable**, measured here: against the shipped bound, a `unique_match`
paraphrase of **6** statements is CAUGHT and one of **7** is a documented MISS.
So the assertion the record describes is not merely plausible — it separates the
two cases today. The mechanism is not at risk (K1 and K2 are killed), and the
calibration itself is safe: the sweep's offender set is empty at every bound 1–7
and the first innocent function (`fiserv_premier._issuer`, 8 statements) enters
at 8.

**Closure.** Add to `test_no_parser_re_implements_the_one_distinct_reading_helper`:
assert a 6-statement paraphrase is caught at `NEAR_CLONE_MAX_STATEMENTS` and a
7-statement one is not. Test-only; owed at the train or the next hygiene card.

### 5. MINOR — the grid oracle's resolution is ±1 cent per span, and nothing says so

**Claim.** `daily_grid_amount_contradictions` exists to catch an over-capture,
and its docstring and §SH3 describe a per-span comparison with no stated floor.

**Evidence.** The comparison is `abs(step - moved) > 0.01`, so a span the ledger
and the grid disagree about by exactly one cent is **silent**. Measured on the
branch's own invented fixture: a printed cell off by one cent → **0 notes**; off
by two cents → 2 notes; off by a dollar → 2 notes. The citizens check has the
same inclusive floor (`abs(read - printed) <= 0.01`).

**Assessment.** The floor is the platform's ordinary float tolerance and is not
a defect. It is an undocumented limit of a check whose whole purpose is to find
money the reader took that the bank did not print, and a reader of §SH3 would
not know the oracle cannot see a one-cent over-capture.

**Closure.** One clause in the docstring and one line in §SH3. No code change.

### 6. MINOR — three bookkeeping slips in the record

* §SH0 and §SH9 say control bytes were checked over "**all 14** files the branch
  commits". The branch commits **15**. (Re-measured: 0 control bytes over all
  15.)
* §SH12's commit table lists **10** commits; `git log 10cc722..wave8-scanhyg`
  has **11** — `24b5f8e`, the commit that completed the table, is absent from
  it.
* §SH11 item 3 self-discloses that the new clone-guard comment says 89 modules
  where the sweep measures 92. **Confirmed**, and the source of the drift is
  now visible: `_modules()` returns **92**, of which **89** are non-shared. The
  comment's "all 89 modules of `analysis/`" is the non-shared count wearing the
  total's name. Recording rather than editing was the right call for a comment;
  naming the arithmetic makes the fix a one-word one.

---

## THE PINNED SURFACE

`python -m tools.scanhyg_pinned_replay --base 10cc722` re-run in full, not
sampled: **109 pinned documents, 108 identical leaf for leaf including the whole
published integrity block, 1 pinned refusal raising the same message on both
sides, `moved: 0`, `findings: []`**, exit **0**, 481s. The 6 the four readers
own are `citizens` ×4 (`0A6946CA`, `2E777BDD`, `D3613B60`, `FC9C0E8F`),
`southside_scanned` ×1 (`4C96DDA2`) and `apex_scanned` ×1 (`A4C49ACB`); the card
predicted five of the six. **No pinned leaf moves. There is no unannounced
pinned movement on this branch.** The instrument compares branch against the
base commit's own output rather than against `PINNED_OUTCOMES`, which is a
stricter question than the gate's, and its own construction was audited here:
it enumerates the 109 paths from the committed balance audit, resolves each
through the production intake ladder with both OCR rungs disabled, and diffs
every leaf plus `outcome`, `reason`, `flags`, note templates, `risk_level`,
`possible_document_issue` and `claimed_by`.

---

## THE FIVE SURVIVORS, ADJUDICATED INDEPENDENTLY

* **E1 and E2 are equivalent, and it is a proof.** The walk sets `credit = step
  > 0`, refuses `step == 0`, then builds `amount = round(step / 100, 2)` and
  `direction = "credit" if credit else "debit"`. So for every transaction this
  parser can construct, `direction == "credit"` ⟺ `amount > 0` — verified on
  every transaction of the fixture. The two halves of `direction != "credit" or
  amount <= 0` are therefore one predicate written twice, and **no separating
  input exists**: a DEBIT dated `period_end + 1` has `amount < 0` and is caught
  by either half (constructed and confirmed refused); a credit with `amount <=
  0` is unconstructible, since `step >= 1` cent forces `amount >= 0.01`.
* **E3 is equivalent one gate up.** `_resolve_dates` refuses any non-monotone
  sequence (`eq_bank_scanned.py:370`), so `{i : dates[i] > period_end}` is
  necessarily an upward-closed suffix and the explicit contiguity test can never
  fire. Constructed the case anyway — an out-of-period credit sitting mid-grid —
  and it is refused by the order gate, never reaching the contiguity check.
* **D5's reach is exactly what the record says.** Enumerated every token over
  `0-9 & g` up to length 3: **63** tokens change reading when the bound widens
  from two glyphs to three, and **all 63** begin with a literal `0`. Corroborated
  structurally: `_ROW_RE` already caps this reader's day cell at three glyphs
  (`eq_bank_scanned.py:139`), so the mutant reaches only a leading-zero
  three-glyph cell. Not testable without pinning a shape no document prints.
* **K3 is real, and closable — see finding 4.** It is the only survivor that is
  a genuine gap rather than a redundancy, and it is a test gap, not a mechanism
  gap.
* **The detector fires on nothing innocent.** Swept the base tree's **89**
  non-shared `analysis/` modules with the guard's own predicate at the shipped
  bound: exactly **two** offenders, `eq_bank_scanned._sole` and
  `scanned_small_bank._tf_one` — the two paraphrases this card removed, and
  nothing else. This guard is not a train blocker.

---

## SS-GRID-AMOUNTS: ORACLE, NEVER A SOURCE

Constructed adversarially on the branch's own invented fixture, `parse` and check
run for each:

| shape | behaviour | correct |
|---|---|---|
| a cell equal to the ledger step | silent | yes |
| off by one cent | silent (finding 5) | within tolerance |
| off by two cents, off by a dollar | flags the span | yes |
| a day printed twice with two balances | flags "not readable"; the day still counts as posted | yes |
| a day reprinted **identically** | silent — corroboration | yes |
| a grid printing fewer cells (spans covering non-posting days) | silent | yes — indifferent to gaps |
| a cell on a day the ledger does not post, balance unchanged | silent | yes |
| the same, balance moved | flags | yes |
| the last cell vs the printed ending balance | flags | yes |
| four OCR-garbled cells (letter-for-digit in the date, in the amount, a stray glyph, a comma decimal) | none raises; the unreadable cell is dropped | yes |

**Decisively, the reader adopts nothing.** The full ledger fingerprint —
beginning and ending balance, both stated counts, days in period, every
transaction's date/amount/direction, every published daily balance — is
**identical** between the clean grid and a grid the check flags. The grid is
consulted and reported on; it is never a source of a published figure.

---

## RE-RUN TABLE

All from the branch worktree at `24b5f8e`, sequentially, one heavy process at a
time; the concurrent `mt8-desccols` session was not touched. `git status
--porcelain` was empty after the mutation harness and after every probe.

| # | proof | result | exit | wall |
|---|---|---|---|---|
| 1 | `python -m pytest -q tests/test_southside_scanned.py tests/test_citizens_scanned.py tests/test_eq_bank_scanned.py tests/test_shared_parser_utils.py tests/test_no_parser_helper_clones.py` | `251 passed, 1 warning` | **0** | 5.3s |
| 2 | `python -m pytest -q tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py tests/test_r1_hardcodes.py tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py` | `253 passed, 1 warning` (252 → 253) | **0** | 19.3s |
| 3 | `python -m pytest -q tests/test_parser_conformance.py tests/test_parser_registry_entries.py tests/test_parser_detection_markers.py tests/test_parser_registry.py tests/test_parser_crash_shapes.py tests/test_parser_exception_boundary.py tests/test_count_semantics.py` | `1164 passed, 35 skipped` | **0** | 4.4s |
| 4 | `python -c "from analysis.parser_registry_entries import load; print(len(load()))"` | `75` | **0** | — |
| 5 | `python -m tools.scanhyg_family_replay --rows <run>/rows.csv --data-dir <main>/webapp_data --baseline-settings-key <key> --base 10cc722 --out <private>` | 47; identical 33, payload_moved 8, outcome_moved 0, raised_either_side 6, no_ocr_artifact 0, base_matches_run_of_record 41, base_differs 0 | **0** | 137s |
| 6 | `python -m tools.scanhyg_pinned_replay --base 10cc722 --out <private>` | `pinned 109, identical 108, moved 0, refused_both_sides 1, claimed_by_target_reader 6` | **0** | 481s |
| 7 | `python -m tools.scanhyg_mutation_table --out <private>` | `mutants 30, killed 25, survived 5, unapplied 0, baseline 251 passed / exit 0, tree_clean_after true, 208.7s` | **0** | 217s |
| 8 | `python -m tools.scanhyg_gate_probe --rows … --data-dir … --baseline-settings-key … --summaries --declines --clone-bound --out <private>` | 9 docs × 8 rows, 0/0 contradictions; declines refuse at pass 2 with 3 and 2; 92 modules, bounds 1–7 clean | **0** | 1s |
| 9 | `python tools/privacy_scan_branch.py --rows … --where parser_id=southside_scanned,eq_bank_scanned,citizens,texas_first_scanned,apex_scanned --data-dir … --base 10cc722 --ref wave8-scanhyg` (from `mt-lead`) | population 41, read 41, 3,228 added lines, MONEY 0 DIGITS 0 DATES 0 WORDS 2 | **1** (by design on hits) | 5s |
| 10 | reviewer's own probe: 144 fail-closed pairs, oracle discipline, K3 pin, D5 reach, base-tree clone sweep, repair-doctrine AST scan | **0 failed checks** | **0** | 2s |
| 11 | reviewer's own base-vs-branch `_resolve_dates` differential (base loaded from `10cc722` blobs) | 6 same / 3 stricter / **1 wider** | **0** | 2s |
| 12 | reviewer's control-byte scan of the 15 committed files | 0 control bytes, 15 files | **0** | — |

Five mutant/killer pairs were additionally hand-checked against the named test's
own assertions rather than trusted: G1↔`…amount_read_too_large_is_caught…`,
G2↔`…walk_is_seeded_at_the_summarys_own_beginning_balance`,
G3↔`…span_covers_every_day_since_the_previous_printed_cell`,
G4↔`…day_the_grid_prints_twice…is_not_an_oracle`,
C2↔`…takes_MORE_than_the_page_states_is_named` (the mutant hard-codes the
direction; the test asserts it). Each mutant's documented edit does what its row
says, and each named killer asserts the gate the row names.

---

## PRIVACY RE-MEASUREMENT (this reviewer's own)

* Shared instrument, wider population than the record's (41 vs 38 documents;
  `apex_scanned` added), at the true final tree, 3,228 added lines: **MONEY 0,
  DIGITS 0, DATES 0, WORDS 2**, both WORDS hits code-only adjacencies and both
  already disclosed in §SH10. Exit 1, which is the tool's contract on any hit.
* `135a719` read line by line: comment and docstring text only, no AST change,
  three archive figures correctly replaced by classes.
* Fixtures: invented and declared so; the two scanned families use invented
  2026-04 and 2026-09 periods and no DATES token collides.
* **This review file:** 0 archive-sourced tokens. Documents named by 8-hex
  prefix; every magnitude a class; no figure, date, name, account number,
  reference or merchant string.
* Standing residue, out of the branch diff's scope but named here: two base-era
  archive figures survive in `analysis/citizens.py:206` and `:297` — see
  finding 1.

---

## CLAIMS I COULD NOT VERIFY

* The four proofs §SH13 explicitly leaves to the train — the full default suite,
  the corpus-marked slice, `python corpus_gate.py` GREEN, and
  `tools.regfp_zero_movement_sweep` at the final production tree. My mandate
  excluded them. The pinned replay (109, 0 movement) is a stricter question than
  the gate asks on this card's own surface, so what the train owes is
  confirmation, not discovery.
* §SH3's attribution of the five southside movers to §SCANFINISH SF2's partial
  daily-cell reproduction. The five movers and their note counts reproduce
  exactly; SF2's own table was outside my read list.
* §SH11 item 7 (the harness's two self-inflicted defects, `94cfaba`) is
  historical; I confirmed only the present state — the harness refuses a dirty
  tree, runs without `-x`, restores per mutant, and leaves the tree clean.

---

## THE RECORD'S OWN RISKS AND QUESTIONS, RELAYED

The record carries seven items in §SH11 and I confirm the substance of each.
Three want a decision from Ocean or Gustavo:

1. **The EQ Bank +2 is unavailable on this evidence, not merely unimplemented**
   (§SH11 item 5). Both declines refuse with two- and three-day windows —
   re-measured and reproduced. Closing them needs a `&`→digit confusion table,
   and this family's own evidence argues against one: the witnessed `&`
   occurrences stand beside a legible digit, which is the opposite claim. That
   is a card with an evidence packet, not a hygiene round. **Agreed; do not let
   a later card smuggle a glyph table in.**
2. **TG9 and TG10 remain Gustavo's bundled ruling** (§SH11 item 6). Verified
   untouched: `adb.py` is out of the diff and still refuses every out-of-period
   row, so `closing_accrual_contradictions` is evidence for a future ruling and
   nothing more. The corroboration is silent on all three EQ Bank documents that
   parse, which is what makes it usable as a base.
3. **The clone guard's constant is unpinned** (§SH11 item 2 / K3). I have
   shown the pin is writable today — finding 4 — so this is a small owed test,
   not an open question.

The other four (five movers rather than the card's one; the stale 89-module
comment; `quality.summary_totals_reliable` moving on all 8; the harness's own
fixed defects) are correctly characterised and need no decision. §SH11 item 1's
reason holds: the five are exactly the documents whose printed daily cells the
reader already reproduced only partially, all five are inside the named
population, and all five are withheld on both sides.

---

*Reviewed by an independent Opus 5 session. Verdict tally: 0 BLOCK, 1 MAJOR,
5 MINOR — matching findings 1–6 above.*
