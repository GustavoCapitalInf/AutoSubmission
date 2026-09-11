# P23-PRECISION — independent adversarial review

```
REVIEWER      REV23-PRECISION — independent; wrote none of this code and none of the cell's W3.
              Detached worktree .claude/worktrees/rev23-precision @ d0172eb (never modified; nothing merged,
              pushed or committed).  The cell's branch wave23-precision and worktree mt23-precision untouched.
BASE          08704aa (the P23-PRECISION card commit)
TIP           d0172eb  ·  17 commits  ·  14 files  ·  +2,403 / -76
CODE TREE     layout/ analysis/ discovery/ ocr/ telemetry/ evidence/ webapp/ are BYTE-IDENTICAL between
              89dbde7 (where the cache-heavy floor ran) and d0172eb — verified, so the floor stands for the tip.
              c035560..d0172eb is the W3 section alone.
VERDICT       APPROVE WITH FINDINGS   (0 BLOCK · 1 MAJOR · 10 MINOR)
              Seven of eight heavy proofs RUN by me in two lock windows; the eighth (the tip census) was
              released, not queued, and its number re-derived from the raw per-sha CSVs (§4, §6).
```

---

## 1. Verdict

**APPROVE WITH FINDINGS.** Every ruled property I attacked held: `analysis/bank_repairs.py` has no behaviour
change of any kind (AST-proven, two additions, zero modifications, zero removals); the 2,625 validated
documents are preserved payload-identical at base and at closure over 2,695 shas; the classifier reaches no
verdict and no router; the three `unsafe_rewrite` classifications are correct as I read the code myself; the
R10 ceremony's instrument is genuinely blind to bank names; the Q2 duplicate-definition rule closes the
re-reviewer's Y7 in both placements and every escape I found is caught by another layer of the same fence.

The one MAJOR is not a correctness defect: it is the cell's decision **not** to fix a measured worsening it
introduced on six validated documents, justified in the W3 by a statement about file ownership that is
factually wrong. The ten MINORs are proof and precision defects — three fresh mutants of the cell's own new
rules survive, the "invention guard" does not check three of the fields a repair is most dangerous with, and
R-3 accuses a complete statement of missing pages when one declared total is misread.

---

## 2. Findings, ranked

### MAJOR-1 — the deep-wrap window worsens six validated documents, and the reason given for not fixing it is false

The new `WRAPPED_ROW_LOOKAHEAD = 3` hands more ledger rows to a gate that is an **interval**:

```
layout/document_class.py:915
    if counted_rows < TABLE_MIN_ROWS and 1 <= len(ledger) < TABLE_MIN_ROWS:
```

Reading *more* of a statement's ledger can therefore take it **out** of `short_ledger` at the top. The cell
measured 21 movers, 7 the wrong way (6 validated), and declined the fix with this sentence:

> "Turning the interval into a floor (`len(ledger) >= 1`) would move all seven back and would also move
> documents this cell never measured, **on a signal cell C owns and this card does not list among my files.**"

`layout/document_class.py` is the **first entry** on the card's own ownership list
(`docs/agent-handoffs/P23-PRECISION.md` §"Files you own"), and line 915 is in it. The second half of the
sentence — that a floor would move unmeasured documents — is a legitimate reason; the ownership claim is not,
and it is the half that makes the deferral read as forced rather than chosen.

Reproduced independently and synthetically (no archive, no census):

```
$ PYTHONPATH=. python scratchpad/rev23precision_interval.py
TABLE_MIN_ROWS=5  TABLE_RUN_MAX_GAP=2  WRAPPED_ROW_LOOKAHEAD=3
  -- 3 one-line wraps + 3 three-line wraps (isolated rows)
     window=1 (BASE) -> STATEMENT_COMPLETE findings=[] signals=['short_ledger']
     window=3 (TIP ) -> STATEMENT_PARTIAL  findings=['table_truncated'] signals=['table_truncated']
  -- 3 one-line wraps only (control)          BASE COMPLETE / TIP COMPLETE
  -- 6 one-line wraps (control)               BASE PARTIAL  / TIP PARTIAL
```

A complete statement becomes `STATEMENT_PARTIAL{table_truncated}` **because more of its ledger was read**.
The cell's own `movers-shape-closure.log` shows the same transition on the archive with the same signal
delta (`short_ledger` present before, `table_truncated` after, tier unchanged): 4 + 2 + 1 = 7 documents.

No verdict, payload or outcome moves (the union replay proves it), and the rule is net-POSITIVE overall
(463 → 461), so this is not a BLOCK and the deferral itself is defensible. **What makes it MAJOR is the
misstatement**: it is in a durable record, it is about ownership, and it is decision-changing — an Ocean who
reads "not among my files" defers to 2.4; an Ocean who knows the gate is the card's first owned file can
direct the one line and its census before composing. **Remedy:** correct the sentence, then decide with the
population attached (7 documents, 6 validated, all at `short_ledger`'s upper edge). Do not compose the
current sentence.

### MINOR-1 — three fresh mutants of the cell's OWN new rules survive

Run through the committed harness's `apply` / `restore` / `run_tests` (tree clean after each, verified):

| mutant | mutation | verdict | what is unpinned |
|---|---|---|---|
| F1 | `MICR_SYMBOLS` loses `c`/`C` | KILLED (3) | — |
| **F2** | `(continuing or candidates)[-1]` → `[0]` | **SURVIVED** | R-2's *fall back to the lowest line* — the half of the re-review's ask the fixtures cannot see |
| F3 | R-3 fires only when the total INCREASES | KILLED (3) | — |
| **F4** | R-4's overlap guard → `if False:` | **SURVIVED** | the guard is live (`find_dates("mar 03/01-03/31")` → 1 token with it, 3 without) and unfixtured |
| F5 | the invention guard reads any row's magnitude | KILLED (1) | — |
| **F6** | `WRAPPED_ROW_LOOKAHEAD` 3 → **4** | **SURVIVED** | the window's UPPER bound — the whole substance of the rule's reach |

`P5` pins the window narrowing to 1; nothing pins it widening. This is exactly the cell's own Risk 1 ("a
killer that has not been exercised is not a killer") turned on the rows the cell added. Three fixtures close
it: a page with two *non*-continuing markers of different numbers (F2); `mar 03/01-03/31` (F4); a row whose
amount sits four lines under its date and must stay unread (F6).

### MINOR-2 — the "invention guard" does not read three of the fields a repair is most dangerous with

`restates_a_printed_figure` compares transaction magnitudes keyed on `(date, description)` and nothing else.
Reproduced:

```
$ python -c "...
  True   every running_balance rewritten to a number the paper did not print
  True   the statement ENDING BALANCE rewritten
  True   the BEGINNING BALANCE rewritten
  True   EVERY transaction deleted
  True   a row DUPLICATED (same key, another dropped)
  False  control: a magnitude changed
```

Its own docstring says "False as soon as a magnitude changes, **a row appears**, or a row's date or
description changes" — the fifth line above shows a row appearing and the guard returning True. Nothing
calls the function, so no behaviour is at risk **today**, and I read all three SAFE repairs myself: they
touch only `amount`, `direction` and row removal, so their classification is sound. But the W3 says "the
line the classification is drawn on is code, not prose", and it is not: the prose does the work. A repair
promoted to SAFE on the strength of this predicate could rewrite every running balance and both statement
balances. Fix: extend it to `running_balance`, `beginning_balance`, `ending_balance`, and require the after
rows to be a sub-multiset of the before rows.

### MINOR-3 — R-3 accuses a COMPLETE statement of missing pages when one declared total is misread

```
$ PYTHONPATH=. python scratchpad/rev23precision_pages.py
  B2 complete 3pp, last page's total misread '3 of 8'   STATEMENT_PARTIAL ['missing_pages','missing_first_page','missing_pages']
  B3 complete 3pp, middle page's total misread '2 of 8' STATEMENT_PARTIAL ['missing_pages','missing_pages','missing_first_page','missing_first_page']
```

Every "at base" figure in this review was **run**, not reasoned: I staged `08704aa`'s `layout/signals.py`,
`layout/document_class.py` and `tests/layout_fixtures/kinds.py` into a scratch tree beside the tip's other
modules and re-ran the same scripts. At base B3 is `STATEMENT_COMPLETE` with **no findings**, and B2 is
`['missing_pages']` alone. One OCR digit now makes B3 a four-finding partial,
including `missing_first_page` about a page that is present and marked `1 of 3`. The shape is in the archive:
`census-diffs.log` carries `STATEMENT_COMPLETE [-] → STATEMENT_PARTIAL [missing_pages;missing_pages;
missing_first_page;missing_first_page]`, 1 document. The W3 characterises the eight R-3 movers as
"multi-statement files"; that is the rule's own premise restated, not independent evidence — a total change
is equally a misread total. Three of the ten movers are validated. There is no cheap discriminator (the
re-review's own N2 case, `1 of 1` → `2 of 2`, is itself a numeric continuation), so the honest disposition is
the one the cell chose — route to adjudication — but the W3 should say "a total change, which is a new
sequence *or* a misread total", not assert the reading.

### MINOR-4 — one finding code repeated once per owed sequence

`missing_first_page;missing_first_page;missing_first_page` (three documents) and
`missing_first_page;missing_first_page;missing_first_page;missing_first_page` (two) appear as **distinct
rows** of the census's validated-exception table, so the table can never aggregate them. Reproduced at B5
(`[('missing_first_page', 1, 'declared=2;first_observed=2'), ('missing_first_page', 2, 'declared=3;
first_observed=3'), …]`) and at A1c, where the loop's finding and the pre-existing `numbers[0] > 1 and short`
finding both fire. The cell names it (Risk 5) and calls it cosmetic; it is, but it is also load-bearing for
the census output it now pollutes.

### MINOR-5 — R-4 emits a HALF date from a half-valid range

The docstring claims ranges are read "as WHOLE SHAPES — two complete dates and nothing else between them".
They are not: the regex shape is whole, the *validity* of the halves is not.

```
  n=1  '03/01-03/32'   [(0,5,'short')]      (base: 0)
  n=1  '10/20-30/40'   [(0,5,'short')]      (base: 0)
  n=1  '99/99-03/31'   [(6,11,'short')]     (base: 0)
  n=0  '03/01-03/311'  []                   (the far boundary P4d now pins — correct)
```

Three non-date strings now yield one date token each where the base yielded none. Archive movement measured
0, so the cost today is nil; the fix is one line (emit both halves or neither).

### MINOR-6 — R-1 admits a hyphen-joined reference number carrying a colon

`is_micr_shaped("123456-789012:345678901")` → **True** at the tip, **False** at the base. The review's ask
was "require ≥ 1 glyph or confusion among the non-digit characters and refuse a date-shaped digit run", and
the cell implemented exactly that — but `:` is in the confusion set, so admitting `-` and `.` beside it
widens the class to digit-and-separator reference lines with a colon. The date guard does not catch them.
Archive cost 0 (census R-1 movement 0 of 3,380); the cheque-page population is unchanged. Recorded, not
asked to change. The cell's refusal to readmit `'` and `"` is correct and is asserted by a test.

### MINOR-7 — the kind-literal AST guard is literal-exact

`_kind_literals` finds `"STATEMENT_COMPLETE"` but not `"STATEMENT_" + "COMPLETE"` (reproduced). The real
fence is the second guard (`analysis/` and `ocr/` may not import `layout` at all), which I re-derived myself:
`analysis`, `ocr`, `evidence`, `webapp` carry **no** kind literal; `discovery` (2 files) and `telemetry`
(1 file) do, exactly as the W3 says and for the reasons it gives. No change asked.

### MINOR-8 — the positive control covered one repair of six · **CLOSED BY MY OWN RUN, no action for Ocean**

`ceremony-control.log` is `repair_capital_one_running_amount` on its 22 candidates only. The other five
populations route through different parsers, and `analysis/pipeline.py:988` has a branch that explicitly
does **not** call `apply_statement_repairs` — so "0 movers" could in principle have meant "never reached".
I closed the gap myself rather than asking for it (§4): two further positive controls fire (Truist **48 of
48**, Santander **3 of 3**), and my instrumented replay shows the stage **reached 900 / 900** for every one
of the eight repairs. The cell's "latent" reading is not merely consistent with the evidence — it is now
measured. Recorded so the next ceremony runs the control per repair, not once.

### MINOR-9 — the ceremony covers the MODULE; the repair STAGE runs three more keyed repairs

`apply_statement_repairs` runs **eleven** bank- or parser-keyed steps, not eight:

```
analysis/pipeline.py:143-154
    repair = _SUMMARY_REPAIRS.get(owner.id)        # repair_bofa_summary   (analysis/bofa.py:593)
    if repair is not None: stmt = repair(...)      # repair_regions_summary (analysis/regions.py:329)
    stmt = repair_first_community_posted_activity(stmt)   # analysis/first_community.py:160
    …then the eight in analysis/bank_repairs.py
```

R10 scopes the ceremony to "the six bank-keyed `bank_repairs.py` rewrites", so the cell is **inside its
mandate** — but `inventory()` enumerates one module while reading `analysis/pipeline.py` for call sites, and
the W3's prose ("the repair stage") will leave the next reader believing the stage is covered. The two
summary repairs are *registration*-gated (a narrower gate than a `stmt.bank` substring);
`repair_first_community_posted_activity` is gated by neither. Name the three in the STOP packet so the next
ceremony's scope is the stage.

### MINOR-10 — three record defects

* `tests/test_layout_boundary.py` is not on the card's file list, although the card §2 requires the AST guard
  it holds. Justified, of the same class as cell C's Ocean-directed harness widening; record it.
* W3 Risk 4 names five validated documents ("Four … `table_truncated` and one … `KIND_UNCERTAIN`") against
  the six claimed in §"the deep-wrap window". The six reconcile with the census (4 `COMPLETE →
  table_truncated` + 2 `missing_closing → +table_truncated`); the prose sentence does not.
* Disclosed by the cell and confirmed by me: `census-after-r1` was taken at `ea29e34` = R-1 + the census
  tool's own output change, so that one census is nominally of two commits.

---

## 3. The attack list, item by item

**1. `bank_repairs.py` AST-compared, docstrings stripped.** My own comparator (strips a leading
`Expr(Constant(str))` from every Module/Class/Function body, dumps with `ast.dump`): **11 units at base, 13
at the tip; ADDED `['_row_key','restates_a_printed_figure']`; REMOVED []; CHANGED [].** No guard was
inserted into any repair — no repair body changed at all, and `restates_a_printed_figure` is called by no
production module (`grep`: only `tests/test_bank_repairs_ceremony.py`). There is no input on which a guard
could turn a base rewrite into a no-op, because there is no guard on any path. **Unbroken.**

**2. The ceremony's reproduction.** `reproduce` does `setattr(pipeline, name, stand_in)`;
`apply_statement_repairs` calls all eight repairs as **bare module globals** (`analysis/pipeline.py:147-154`),
so the substitution intercepts the production path; `cohort_replay` runs in-process, so the patch is live;
`cohort_replay` reads the cache for the document TEXT and the recorded baseline **only** (`cache.text`,
`cache.baseline_payload`) and re-runs `analyze_document` — which the control proves, since a cache hit could
not have changed 22 payloads. The 696 is `statement_bank` carrying a repair's own literals, a faithful
superset of a guard that is a substring test on the same field. §4 answers what the control cannot: *latent,
or never reached?*, for all eight at once.

**3. R-1..R-4 re-applied.** The re-review's own shapes all close: the E-13B dash line is MICR-shaped again;
the boilerplate footer and the trailing cross-reference are `STATEMENT_COMPLETE` with no findings in both
modes; `1 of 1` → `2 of 2` earns `missing_first_page` and no `page_gap`; `find_dates` gives 2 / 2 / 0 / 1 on
`03/01-03/31`, `2031-03-01-2031-03-31`, `INV-03/31`, `03-05-2031`. My own shapes produced MINOR-3, MINOR-5,
MINOR-6 and the F2 / F4 survivors; the arithmetic is in §6.

**4. The signal classes.** 272 + 184 − 88 = 368 distinct + 95 in neither = 463: it closes. I would admit none
of the listed unread shapes as a closing label either — every one is an opening label or a column header.
**No rule is tuned to a document**: `grep -iE "chase|truist|regions|capital one|scotiabank|santander|
[0-9a-f]{16,}"` over the test diff hits only `tests/test_bank_repairs_ceremony.py`, where a bank label IS the
repair's guard; no sha, no archive literal, every fixture date ≥ 2031.

**5. Never a verdict.** A planted kind is found (MINOR-7 for the literal-exact limit); `analysis`, `ocr`,
`evidence`, `webapp` clean; the boundary test unchanged and green; the runner projects the class *after*
`analyze_document` returns (`discovery/runner.py:1596`).

**6. Q2 and Q1.** Eight placements — Y7 after the real def (B8 HIT), `async def _analyse` (HIT), duplicate
`_account_report` / `analyze_markdown` / `analyze_document` (HIT), Y7 in a module-level `if True:` and in a
`try:` (B8 miss, **B7 catches both**), `_analyse = _shadow` and a class-level `def _analyse` (B8 miss, **B3 +
B7 catch both**), clean pipeline (0). **No exploitable hole.** Q1: both harnesses' `append_table` leaves two
headers for two runs.

**7. The mutation table.** §5. **8. Ownership.** 14 files; every one on the card's list except
`tests/test_layout_boundary.py` (MINOR-10) and `tests/layout_fixtures/kinds.py` (covered by "or the existing
C test files"). `layout/refusals.py` untouched. `analysis/pipeline.py`, every parser, `ocr/**`,
`telemetry/**`, `discovery/**`, `evidence/**`, `webapp/**`: **untouched**. All 17 commits carry both trailers.

**9. Scans.** §7. **10. Heavy proofs.** §4. **11. The single-row repair.** §8.

---

## 4. My heavy proofs (lock window, mine vs the cell's)

| step | mine | the cell's | log |
|---|---|---|---|
Targeted runs need no lock and were taken first:

| step | mine | the cell's |
|---|---|---|
| the layout / ceremony / fence files at the tip | **764 passed, 3 skipped** | 764 / 3 |
| the fifteen classifier-consumer files | **546 passed** (2 deselected, 277 s) | 546 |
| the ceremony `inventory` re-run | 8 repairs, bank-keyed ×8, declared 6 / 8, outside the vocabulary 0 | identical, byte for byte |
| six fresh hand mutants | **3 KILLED · 3 SURVIVED** (F2, F4, F6) | not run |
| the cell's nine new fixtures against the BASE code | 7 fail at base, 2 controls unchanged | not run |

Under the lock (`discovery_reports/train13-logs/HARNESS.lock`, mkdir-only, holder `REV23-PRECISION`, ~1 s
unbounded poll behind `P23-WAVE`'s live CTRL wave; logs under `discovery_reports/train13-logs/rev23-precision/`
each ending `EXIT=`, window in that directory's `MASTER.log`):

| step | mine | the cell's |
|---|---|---|
| **my instrumented ceremony** — every repair in `analysis.pipeline` wrapped with a counter that calls the REAL repair and records *stage reached · returned the same object · changed the payload*, over the union of ALL EIGHT populations (**900** distinct shas, the 696 plus the two held-out repairs) | **stage reached 900 / 900 for every one of the eight · returned the same object 900 / 900 · payload changed 0** · replay 887 of 887 validated preserved, identical, 0 regressions, EXIT=0 (1,496 s) | not run (the cell measured the end payload only) |
| positive controls for the two repairs the cell did NOT control | **Truist 48 of 48 validated move · Santander 3 of 3** — the path is live on three cohorts, not one | control on `repair_capital_one_running_amount` only: 21 / 21 |
| the 50-row mutation table re-run in MY worktree | **50 / 50 KILLED**, survivors `[]`, baseline 678, final tree clean, EXIT=0 (774 s) | 50 / 50 KILLED |
| UNION `cohort_replay --expect-identical` chunk 01 (`--parser chase`) **at the tip** | **504 population · 504 of 504 preserved · payload identical · 0 changed · 0 regressions**, EXIT=0 | identical |
| the 5 canonical guards · the 7 canonical conformance files | **276 passed** · **1,282 passed, 41 skipped** | 276 · 1,282 / 41 |
| `python corpus_gate.py` | **GREEN — 105 PASS / 3 WITHHELD / 1 REFUSED**, EXIT=0 (711 s) | GREEN 105 / 3 / 1 |
| the full default suite **at the tip** | **9,929 passed**, 48 skipped, 39 deselected, **0 failed**, EXIT=0 (720 s) | 9,922 at `89dbde7` |
| the cache census at the TIP | **NOT RUN — released, not queued** (see below); the number it would have produced is re-derived instead from the raw per-sha CSVs, §6 | 461 |

**The one heavy proof I did not take.** A third window was armed for the tip census and polled from 21:41:55Z;
at 21:35 `P23-WAVE` began the **U755** population (755 documents in chunks of 100 — its CTRL population of 114
took 65 minutes), so the lock was not going to free for hours. Rather than leave an unattended driver to take
the lock overnight, I stopped my own pollers (`MASTER.log`, 22:11:22Z) and re-derived the census's headline
from the cell's raw per-sha CSVs instead (§6). **`P23-WAVE`'s holder was never removed, written into or
polled past; every lock this review took was released by its own holder with the directory confirmed gone.**
What the census would have added that the CSV re-derivation cannot: a proof that the classifier *re-run at
the tip* produces those same rows. The classifier is pinned at the tip by other means — 50 / 50 mutants, the
764-test layout suite, the 9,929-test full suite, and my own base-vs-tip fixture runs — so the gap is the
weakest link in the chain, not a missing link.

The suite figures differ by exactly 7 because the cell ran the suite at `89dbde7` and three test files changed
after it; mine is taken at `d0172eb`, so the tip's suite is proven green here for the first time.

**LOCK WINDOWS (two, both mkdir-only, holder `REV23-PRECISION` inside, released by their own holder with the
directory confirmed gone):**
* **Window 1 — 2026-09-11T20:05:39Z → 20:30:17Z.** First poll 19:24:13Z, re-armed at ~1 s from 19:45:04Z
  (the cell's own record shows `P23-WAVE` re-taking the lock five seconds after a release, so a coarse poll
  starves); **1,234 polls** behind `P23-WAVE`'s live CTRL wave. Guards, conformance, the gate, the suite.
  Four steps in this window failed on MY OWN bug — relative `--run` / `--data-dir` paths, which resolve
  inside the detached worktree where the git-ignored cache does not exist — and the mutation table refused a
  tree made dirty by this review file. Both are recorded in `MASTER.log` rather than tidied away.
* **Window 2 — 2026-09-11T20:33:17Z → 21:3x Z.** First poll 20:30:18Z, 179 polls behind `P23-EGATE`. The four
  corrected steps with absolute paths and a clean tree (this file parked in the scratchpad for the table's
  duration), plus the scans and the tip census.

---

## 5. The mutation table, re-run

**My own re-run in my own worktree: baseline 678 passed, `50 / 50 KILLED`, survivors `[]`, final tree clean,
EXIT=0 (774 s)** — the cell's headline confirmed independently, not transcribed. I also checked the rows that
matter rather than accepting the total. Three checks worth naming:

* **P10's killers are the right ones.** The table names
  `test_at_most_one_extract_statement_call_in_the_module_inside_the_analysis_body` (the *accident* the whole
  Q2 finding was about) **and** `test_no_two_reconcile_results_are_compared_or_selected_between`, which is
  `assert reconcile_selection_violations(PIPELINE_SOURCE.read_text()) == []`. So B8 is enforced on the
  PRODUCTION module, not merely on synthetic text, and the Y7 hole is genuinely closed rather than re-papered.
* **M21 was re-worded honestly.** R-2 deleted the site the old row named (`other_words <= best[0]`), so the row
  would have failed its own "the anchor occurs exactly once" check. It now mutates the rule that carries the
  same property and kills at 6, naming `test_a_prose_page_cross_reference_is_not_the_page_marker` first.
* **The harness cannot launder a survivor**: it refuses a dirty tree, refuses a non-green baseline *per test
  set*, restores in a `finally`, asserts `clean()` after every mutant, and exits 1 when any row survives.

**P4d, judged.** The first P4d (`DATE_RE.fullmatch(...)` → `.match(...)`) was a genuinely **equivalent**
mutant and the cell proved it exhaustively rather than asserting it: the call's argument is group 1 or 2 of
one of the two range patterns, so its whole domain is 9,801 `m/d` strings and 80,000 `yyyy-mm-dd` strings,
and `match` and `fullmatch` return the same span on every one (`p4d-equivalence.log`). Re-wording the row
onto the short pattern's **far boundary** — whose removal reads `03/01-03/311` as a two-date range, killed by
one asserted line — is the right move and is disclosed in the commit, the table's comment and the W3. **An
honest kill, not a laundered survivor.** The near boundary (`(?<![\d/.-])`) is still carried by no row.

**P4d, judged.** The first P4d (`DATE_RE.fullmatch(...)` → `.match(...)`) was a genuinely **equivalent**
mutant and the cell proved it exhaustively rather than asserting it: the call's argument is group 1 or 2 of
one of the two range patterns, so its whole domain is 9,801 `m/d` strings and 80,000 `yyyy-mm-dd` strings,
and `match` and `fullmatch` return the same span on every one (`p4d-equivalence.log`). Re-wording the row
onto the short pattern's **far boundary** — whose removal reads `03/01-03/311` as a two-date range, killed by
one asserted line — is the right move and is disclosed in the commit, the table's comment and the W3. **An
honest kill, not a laundered survivor.** The near boundary (`(?<![\d/.-])`) is still uncarried by any row.

---

## 6. The W3's numbers, re-derived

| claim | the cell | mine |
|---|---|---|
| R-1 / R-2 / R-4 archive movement | 0 / 0 / 0 of 3,380 | `census-diffs.log` line by line: "no document changed kind, sub-kind, tier, findings, account kind or modality" ×3 |
| R-3 movement | 10 (3 validated), 460 → 463 | the six transition rows sum to 10; the exception tables differ by exactly the 3 `missing_first_page;×3` rows |
| the unmarked allowance / deep-wrap | 2 (0 validated) / 21 (14 validated) | `movers-shape-closure.log`: 10+4+2+2+1+… = 23 movers, split by the `short_ledger` / `first_page_missing` signal delta as claimed |
| **the whole validated-exception series** | 460 · 460 · 460 · 463 · 463 · **461** | **re-derived by me from the six RAW per-sha CSVs** (counting `outcome_class == validated` and `kind != STATEMENT_COMPLETE` myself, not reading the tool's summary): before-cache **460**, after-r1 **460**, after-r2 **460**, after-r3 **463**, after-r4 **463**, closure **461** — every figure and every direction exact, on 3,380 rows with 2,625 validated in all six. The arithmetic also closes internally: 463 − 6 removed (`table_truncated → COMPLETE`) + 4 added (`COMPLETE → table_truncated`) = 461 |
| union replay | 2,695 shas, 2,625 preserved identical, 0 regressions, at base and closure | the 7 chunk populations sum to **2,695**; the preserved counts sum to **2,625**; 0 regressions in all 14 logs |
| `bank_repairs.py` AST identity | 2 added, 0 changed, 0 removed | reproduced independently ✓ |
| the 696 candidate population | 22·24·48·518·81·3 | `ceremony-population.log` ✓; the instrument carries **no bank literal** (grep) and reads every fact from the AST |
| the two censuses collapse to one | cache census now reads native word boxes for 3,172 / 3,380; 179 page-text; 29 nothing | **re-derived independently** from the cold cache's own sqlite index and artefacts (read-only): 3,364 `ocr` artefacts, of which `native_evidence` **3,172**, page `text` **179**, nothing **13** — plus the 16 shas with no `ocr` artefact at all = the 29 the cell names. Exact. |

---

## 7. Scans

**Both scans re-run by me over the full `08704aa..d0172eb`, and both reproduce the cell's numbers exactly:**

| scan | mine | the cell's |
|---|---|---|
| `privacy_scan_branch --base 08704aa --ref d0172eb --data-dir <cold cache> --rows <run>/rows.csv` | `population` 3,380 · `documents_read` 3,351 · `added_lines` **2,403** · **`hit_count` 0** (DATES 0 / DIGITS 0 / MONEY 0 / WORDS 0) · `raw_hit_count` 46, every one dismissed by rule (`words_class` 39, `hex_sha_substring` 7) · `residue_files` **0** · `residue_sites` **0** · EXIT=0 | identical |
| `huntington_msg_privacy_scan --base 08704aa --ref d0172eb` | `commits_scanned` **17** · MONEY 0 / DIGITS 0 / DATES 0 · **WORDS 11** · EXIT=1 | identical |

The three DIGITS residue sites an earlier scan found were real and the cell closed them the right way
(`c035560` rebuilt three synthetic ceremony balances that collided with archive digit strings, so every
figure of five digits or more in the added lines is either already in the base tree or under the scan's
floor). The WORDS 11 are attributed hit by hit in §8(b): every one is ordinary English prose, and none is a
name, amount, date, account number or institution. **Trailers:** all 17 commits carry `Co-Authored-By` and
`Claude-Session`. **Fixtures:** every added date is ≥ 2031; no sha and no archive literal anywhere; the only
bank names in the diff are in `tests/test_bank_repairs_ceremony.py`, where a bank label IS the repair's guard.

---

## 8. The three ruling questions

**(a) The deep-wrap fix.** Take it, but not silently and not here. The one line is
`1 <= len(ledger) < TABLE_MIN_ROWS` → `len(ledger) >= 1` at `layout/document_class.py:915`. It returns the
six validated documents and it *will* move documents this cell never measured — which is why it needs its
own before/after census, not a late edit at composition. My recommendation to Ocean: **correct the W3's
ownership sentence now** (the file is on the card's list), and open the floor as a measured item with its
population attached. Both edges then want a fixture — nothing today pins either.

**(b) WORDS 11.** I attribute all eleven; none is a finding. Each is an ordinary English adjacency in a
commit subject or body — `MESSAGE PAGE` (092d17e), `BEEN REPLACED` and `CARD PRECISION` (2e6acc1),
`PAGE SIMPLY` and `PAGE UNLESS` (370c69a), `LONGER APPLY` (4b56a5d), `HAVE FULL` (8728440),
`CONSTRUCTION GROUP`, `LAST COMPLETE` and `MESSAGES THAT` (c35ca84), `REPORT NUMBER` (d0172eb) — that also
occurs somewhere in 3,380 statements. MONEY / DIGITS / DATES are 0; not one hit is a name, amount, date,
account number or institution. The cell's diagnosis of the instrument gap is correct and I verified it:
`privacy_scan_branch._words_class` dismisses every WORDS hit unconditionally (which is how its own 39 raw
WORDS candidates became `hit_count 0`), while the message scan imports that module's patterns and loader but
never calls `excluded_by` — so the two `hit_count`s are not comparable. **Do not rewrite six mid-branch
commits**: every proof log names those shas, and rewriting them dangles every tree reference in the record to
buy a zero-information word collision. Reword only if Ocean squashes at composition; otherwise accept.

**(c) `repair_single_row_signs_from_balances`.** **Yes — it is the anti-optimizer pattern, and more sharply
than the cell states.** The function walks the ledger a printed-balance step at a time and, where a segment's
sum disagrees with the step, iterates its rows and flips the sign of the **first** row whose flip reconciles
the segment. Reproduced:

```
  CIBC, one flip reconciles (unique)                      flipped: [('SYNTHETIC ROW A', -500.0, 500.0, 'credit')]
  CIBC, TWO interpretations reconcile                     flipped: [('SYNTHETIC ROW ONE', -500.0, 500.0, 'credit')]
  CIBC, no single flip reconciles — left alone            flipped: []
  restates_a_printed_figure: True in every case
```

When two rows of equal magnitude both reconcile the segment, the repair **does not detect the ambiguity**: it
takes the earliest in document order and publishes it as a direction. The ruling's own words are "several
independently plausible interpretations → REVIEW / REFUSE". Mitigations, stated fairly: it preserves every
magnitude (it passes the invention guard), its reconciling figure is a *printed per-row balance* rather than
the statement summary, and it is silent when nothing reconciles. It therefore sits **between** the Santander
repair (which fires only where magnitudes already agree and chooses nothing) and the three `unsafe_rewrite`s
— but it is on the production analysis path, it is bank-keyed exactly as the six are (`CIBC` substring,
`ROYAL BANK OF CANADA` exact — note `"ROYAL BANK OF CANADA (RBC)"` does **not** fire), and it has the largest
held-out population (201). One fact the cell could not give the ruling and my instrumented replay can:
**it does not fire on any of its 201 candidates on the run of record** (stage reached 201 / 201 within the
900, returned the same object every time, 0 payload changes) — so retiring or replacing it moves nothing
today, exactly like the three STOP items. **My recommendation: admit it as a fourth STOP item (S-4) in the
same ruling packet, classified `unsafe_rewrite` on the SELECTION rather than on the magnitude.** Nothing
changed here.

---

## 9. Properties I attacked and could not break

* **No behaviour change in `analysis/bank_repairs.py`** — AST-proven by my comparator and by the union replay.
* **"The six repairs are latent on this archive" is TRUE, and now measured rather than inferred.** The cell
  could only show that disabling a repair changes no payload — which a blind instrument also shows. I wrapped
  every repair bound in `analysis.pipeline` with a counter that calls the REAL repair, and replayed the union
  of all eight candidate populations (900 shas). Result, for every one of the eight: **stage reached 900 /
  900, returned the SAME object 900 / 900, payload changed 0.** So the stage is not being skipped (the
  `analysis/pipeline.py:988` no-repairs branch is taken for none of them) and no repair constructs a new
  statement on any candidate document. This also covers the two repairs the card held out, including
  `repair_single_row_signs_from_balances` on all 201: **it does not fire on this archive either.**
* **The ceremony instrument is blind to banks** — no bank literal anywhere in it; every fact (guard literals,
  written fields, row drops, text reads, call sites, classification) comes out of the AST, so adding,
  renaming or deleting a repair changes the table instead of agreeing with it. I re-ran `inventory` myself and
  got `ceremony-inventory-final.log` byte for byte.
* **The Q2 rule** — eight placements attacked; every escape from B8 is caught by B3 or B7. No hole. And B8 is
  enforced on the PRODUCTION module, not only on synthetic text: `test_no_two_reconcile_results_are_compared_
  or_selected_between` asserts `reconcile_selection_violations(PIPELINE_SOURCE) == []`, and it is the second
  killer of mutant P10 in the cell's own table.
* **The three `unsafe_rewrite` classifications** — I read all three functions and agree with every reason as
  written, including the fair treatment of Chase's digit-suffix gate and the Regions split recommendation.
* **`restates_a_printed_figure` cannot change any repair's result** — no repair calls it (AST-proven).
* **The safe-repair tripwires cannot pass on a repair that does nothing** — each asserts the fixture fires
  before asserting the guard.
* **The R-3 allowance does not over-forgive** — one unmarked page against a sequence owing three still earns
  `missing_first_page` (my B7).
* **Every new fixture distinguishes base from tip — none is a tautology.** Run against the BASE layout code in
  a scratch tree, all seven positive fixtures FAIL (`page_gap` ×3, no `missing_first_page`, `missing_period`
  ×2, `table_truncated`) and both controls (`statement_with_page_cross_reference`,
  `two_statements_second_with_unmarked_cover`) are `STATEMENT_COMPLETE` at both ends.
* **The `layout/` boundary and `classify_document`'s purity** — unchanged and green.
* **The census tool no longer names a document beside a verdict**, and its static guard reproduces against a
  planted `print`.

---

## 10. Instruments (all untracked, in the session scratchpad; nothing written into the tree)

`rev23precision_ast.py` (the docstring-stripped AST comparison) · `rev23precision_attacks.py` (R-1 / R-4) ·
`rev23precision_pages.py` (R-2 / R-3 over real documents built from the committed fixture builders) ·
`rev23precision_q2p6.py` (the fence's B8 and the kind guards) · `rev23precision_handmutants.py` (six fresh
mutants through the committed harness) · `rev23precision_interval.py` (the `short_ledger` interval) ·
`rev23precision_singlerow.py` (the third ruling) · `rev23precision_latency.py` (my instrumented ceremony) ·
`rev23precision_lock.py`, `rev23precision_harness.sh`, `rev23precision_driver.sh`. `git status --porcelain`
was empty in the worktree before and after every mutation run.
