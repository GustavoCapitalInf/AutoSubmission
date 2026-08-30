# BATCH9 WH-ROW-CAPTURE — independent adversarial review

Branch `wave9-rowcap`, base `train9` `aaa3441`, tip `2b88d94` (9 commits). The reviewer did
not write this cell and asked it nothing. Every number below was re-measured in the
reviewer's own detached worktrees (`rowcaprev/{base,tip,mut}`), so the cell's worktree was
never touched. The L1-S1 cell held a whole-archive replay on this host throughout; replays
and read-only probes were run alongside it, and the mutation harness was run only after
confirming that the only other python process was a read-only `cohort_replay` and not a
second harness.

**VERDICT: APPROVE WITH FINDINGS.** Newly validated 2 by sha; 454/454 preserved with
payloads **byte-identical**; the two withheld payload changes classified and correct;
regressions 0; currency and provenance unmoved; privacy 0. Findings are three MINORs
(two of them record-only) and three NOTES; none blocks composition.

---

## 1. Re-measurement table

| # | measure | cell's claim | reviewer's measurement | |
|---|---|---|---|---|
| 1 | `cohort_replay` base, five `WH:` groups, `--expect-identical` | 18 unchanged, changed 0 | 18 unchanged non-validated, payload changed 0, exit 0 | ✓ |
| 2 | `cohort_replay` base, `--parser` × 5, `--expect-identical` | 454/454 identical | rbc **159/159 identical**, wells **217/217 identical**, scotiabank **78/78 identical**, bmo 4 unchanged, ibc 1 unchanged — **454/454**, exit 0 each | ✓ |
| 3 | `cohort_replay` tip, target 18 | +2, regressions 0, 16 unchanged (2 payload changed) | **newly validated 2**, up 0, unchanged non-validated 16 (payload changed on 2), **validated regressions 0**, other ladder regressions 0, exit 0 | ✓ |
| 4 | the movers by sha | `D00562176BEC0AAE`, `B52CDF2BA874BBB4` | exactly those two | ✓ |
| 5 | `cohort_replay` tip, `--parser` × 5 | 454/454 preserved, payload identical | rbc 159/159 **identical**, wells 217/217 **identical**, scotiabank 78/78 **identical** (+2 newly validated), bmo 4, ibc 1 — **payload changed 0 on every preserved document**, regressions 0, exit 0 each | ✓ |
| 6 | the two withheld payload changes | every leaf downstream of one removed posting | classified in §3.3 — one removed debit record and its downstream aggregates only | ✓ |
| 7 | mutation table | 5/5 | **5 mutants · 5 killed · 0 survived · exit 0**; `git status --porcelain` empty before AND after; `scotia.py` / `wells.py` identical to HEAD after | ✓ |
| 8 | `rowcap_sheet_strips` | 17/17, 19/19, and 1 of 4 on the third | **17/17/0 · 19/19/0 · 4/1/3** — 36 of 36 on the movers | ✓ |
| 9 | `rowcap_ceiling` both modes | `as_is` 2, `wrapped_amount` 2 — the same two, no RBC | validated **2** in both modes, the same two shas, **no RBC document** | ✓ |
| 10 | the 78 "already ordered" claim | 78 ordered, 2 not | 81 swept: **78 already in printed-date order, 2 not, 1 with no rows** — and the 2 are exactly the movers | ✓ |
| 11 | the wells symbol census | 221 docs, 2 money cells, 0 balance cells | 221 docs, **2 money cells with the symbol, 0 balance cells**, both on `3725BB1189EA74D5` and `59FAF1FC17745A6E`; my record/cell denominators differ (see MINOR 2) | ✓ (load-bearing part) |
| 12 | full default suite | 7,456 | **7,456 passed, 0 failed, 43 skipped, 34 deselected**, exit 0 | ✓ |
| 13 | canonical guards / conformance | 255 / 1,270 | **255** / **1,270 passed, 40 skipped** | ✓ |
| 14 | privacy, added file lines | 0 over 1,598 | **hit_count 0** over **1,598** added lines, 472 documents; raw 7 = 6 `round_money` + 1 `words_class` | ✓ |
| 15 | privacy, commit messages | 0/0/0/0 over 9 | **0 in every class over 9 commits** | ✓ |
| 16 | archive sweep, three chunks | 3,380 · 2,669 compared · 2,620 identical · 70 findings · 4 inside / 66 outside | chunk arithmetic reconciles **exactly** from the cell's own logs (1200+1200+980; compared 937+963+769=2,669; identical 2,620; moved 46; publishes 21; raises 3; no-OCR 29). Inside = exactly the 4 named documents, all `moved` | ✓ |
| 17 | attribution of the 66 | fidelity fails on all 66 | **verified independently**: 12 of the 66 replayed `--expect-identical` at my own TRUE base `aaa3441` — 0 payload identical, 5 newly validated, 1 up, 5 preserved-but-changed, 1 down. Every one already differs from the run of record without this branch | ✓ |
| 18 | W3 | one section, append-only | **501 added / 0 removed** — but **no `# §ROWCAP` header** (MINOR 1) | partial |
| 19 | ownership | two production files + `corpus_gate.py` | `analysis/{scotia,wells}.py`, their two tests, five `tools/rowcap_*.py`, W3, and `corpus_gate.py` — the last outside the card's list, disclosed, **data-only** (three `EXCLUDED_ANALYSIS_CALLERS` entries, no logic) | ✓ disclosed |
| 20 | `bmo.py` / `rbc.py` / `ibc.py` / `tables.py` / `cibc.py` | untouched | **0 files changed** — every carried finding on those readers is pre-existing by construction | ✓ |

The corpus gate row is addressed in §3.6.

---

## 2. The two production changes, driven

### 2.1 scotiabank — the stable date sort (hostile question 1)

Four synthetic documents through the real parser and the real `reconcile`:

| construction | result |
|---|---|
| **the repair**: whole sheets bound backwards, dates distinct | **published, correct** — right directions, right closing balance, breaks 0, `sum_delta` 0, coverage 1.0/1.0 |
| control: the same rows bound in ledger order | published, identical reading |
| **attack 1a**: a SAME-DAY pair spanning a sheet boundary, bound backwards | **published with a WRONG SIGN on one row and a mid-period closing balance — and REFUSED by `reconcile`**: `ok=False`, 2 continuity breaks, `summary_ok=False`, credit coverage 0.0 |
| **attack 1b**: print order IS ledger order, dates non-monotonic (a back-dated correction printed last) | **the sort MOVES the row; the chain then breaks and the document is REFUSED** (`ok=False`, 2 breaks) where the base, walking print order, would have reconciled |

Both attacks answer the question honestly and neither is a BLOCK:

* **1a — the sort does not repair a same-day cross-sheet inversion**, and cannot: within one
  printed date the print order is the only ordering evidence the paper carries, which is
  exactly why the sort is stable. The reader then assigns a direction from a predecessor the
  ledger never had. What stops that reaching a validated payload is `reconcile` — the bank's
  own printed instance counts and totals — not the ordering rule. The exposure is unchanged
  from the base, where print order produced the same inversion.
* **1b — the ordering rule can cost a document the base could read.** Its failure mode is a
  refusal, never a wrong figure. **Exposure measured and nil**: of the 81 scotiabank
  documents in the run of record, **78 are already in printed-date order, 2 are not (exactly
  the two movers, both withheld at base) and 1 sweeps no rows** — and **zero validated
  documents have a row the sort would move**. That is the measurement the rule rests on and
  it reproduces exactly.

Nothing is computed or rewritten: the amounts and balances are printed cells, and the
closing balance is a running balance the statement prints, selected by the date beside it.

### 2.2 wells_fargo — the restatement symbol (hostile question 2)

| construction | result |
|---|---|
| the merged restatement (what the card fixes) | the fabricated posting is **dropped**; `reconcile` refuses, debit coverage 0.0 |
| the same rows without the symbol | published as two ordinary postings, `ok=True` |
| **attack**: a GENUINE posting whose money cell carries the symbol | **the row is dropped and the document is REFUSED** (`ok=False`, debit coverage 0.0) |
| the symbol in the BALANCE cell | not read for the symbol; the row is kept (the rule reads only the two money columns) |

So a legitimate symbol-carrying posting costs the document, but **fail-closed** — it never
publishes a short ledger as validated on a statement whose own totals include the lost row.

**Does 221 documents cover the space?** It covers the reader's archive cohort
**exhaustively** — every document `wells_fargo` claimed in the run of record — and that is
the honest claim. It cannot cover Wells layouts absent from the archive, so "this bank never
prints the symbol on a posting" is a statement about the archive, not about the bank. The
consequence of being wrong is a refusal, not a wrong figure, which is the right side to be
wrong on. Independently re-measured: **2 money cells carry the symbol and 0 balance cells
do**, and both cells are on the two documents the card names.

*Bound worth recording (NOTE 2):* the drop is caught by the statement's own printed totals.
Where those totals do not cover the dropped row — I built a statement printing a zero debit
total beside a debit row — the loss is invisible and the document still reconciles. That is
a self-contradictory document, and it is the **same shape as the drop the reader already
had** (`bool(credit) == bool(debit)`), so the card adds no new class.

---

## 3. The remaining hostile questions

### 3.1 The 454 preserved

Not "changed but proven" — **payload identical on all 454**, at both trees, on every one of
the five registrations. That is the strongest available form of the non-regression claim and
it is what the replays report.

### 3.2 Currency and provenance

Unmoved, and provable without the gate: the two CAD-pinned readers (`rbc`, `scotiabank`) are
`159/159` and `78/78` **payload identical**, and a payload-identical replay includes the
`currency` and `currency_source` leaves. `rbc.py` is untouched by the branch. The two movers
publish CAD by the institution default, value and provenance unchanged from base.

### 3.3 The two withheld payload changes (hostile question 3)

Both stay `withheld / withheld_adb`. Every changed leaf on both is downstream of **one
removed debit record**:

* the record's own leaves (`amount`, `date`, `description`, `direction`, `running_balance`)
  and its whole `classification` sub-object, count **1** on every leaf;
* debit-side aggregates only — `metrics.adb.total_debits`,
  `metrics.adb.computed_closing_balance`, `metrics.{num,effective_num}_withdrawals`,
  `metrics.total_withdrawals`, `reconciliation.{gross_debit_total, debit_coverage,
  settled_debit_detail, sum_delta, computed_ending}`;
* narrative restating those — `reconciliation.issues[*]`, `metrics.notes[*]`,
  `metrics.adb.warnings[*]`, `quality.notes[*]`, `integrity.notes[*]`.

**No credit-side leaf moves on either document**, and no printed figure does: not
`beginning_balance`, `ending_balance`, `stated_total_*`, `period_*`, `account_number` or
`currency`. That is exactly the signature of removing one fabricated debit and nothing else.

On `3725BB1189EA74D5` only, three `integrity.flags[*]`,
`metrics.adb.validations.posting_dates_cover_source`, `metrics.adb.missing_posting_dates`
and `metrics.adb.parsed_posting_days` also move. **`posting_dates_cover_source` now fails
for the right reason**: the removed record was the only posting the reader had dated to the
period's last day, so the source text prints a posting date the ledger no longer covers, and
the check says so. Before, that day was covered by a figure that was the history's
restatement. A check newly failing because a fabricated row stopped standing in for a real
one is the check working.

### 3.4 rbc — is the ceiling honest? (hostile question 4)

**Yes, and it is a reading rather than a relaxation.** `--mode wrapped_amount` re-runs the
RBC grid with a money-only line joined to the description above it, patched in memory; it
relaxes no gate and removes no check. Re-run at the tip it moves the capture ratio on four
of the six RBC documents and **overshoots past 1.000 on three** (1.003, 1.005, 1.009) —
trading one misreading for another — and reaches `validated` on **none**. The two documents
it validates are the same two scotiabank movers. The cell's decision not to ship it is
correct and the ceiling's own text says why.

**The `tables.py` mechanism is real.** `read_grid_rows` pairs two money cells with nothing
between them as one row's amount and its running balance, and keeps the line-level fact that
a money-only line lets a following description line continue the row above — so an amount
pushed onto its own line by a wrapped description is taken as the **previous** row's balance.
It is shared with `cibc.py`.

**The population, measured (this quantifies a carried finding the record leaves open):**

| reader | documents | trigger shape (a money-cells-only line) |
|---|---|---|
| `rbc` | 165 (159 validated, 6 withheld) | **58 lines, on the 6 withheld only — 0 of the 159 protected** |
| `cibc` | 34 (all validated) | **2,098 lines, on all 34 protected** |

So a `tables.py` repair would not disturb a protected RBC document through this shape, but
its blast radius is **every one of CIBC's 34 validated documents**. That is the reason it
belongs in its own card with its own full replay, and the carried finding should say so.

### 3.5 bmo — the silent drop (hostile question 5)

The mechanism is real and I located it: in the row loop, `except ValueError: continue`, plus
a `continue` where the year cannot be resolved. A printed row whose date does not exist —
the 29th of a February the statement itself dates to a non-leap year — is dropped with no
flag and no refusal.

**It is pre-existing, and not this card's movement**, by construction: `analysis/bmo.py` is
among the five readers the branch does not touch (0 files changed), and `--parser bmo`
reports 4 unchanged with payload changed 0 at both trees.

On doctrine: refusing to date the row is right and is the Huntington ruling — a parser never
writes a date the paper did not print. The weaker half is that the refusal is silent rather
than an answer. Exposure today is nil (bmo has **0 validated documents**; the whole cohort is
withheld), but the shape is the one the doctrine warns about and the cell is right to carry
it. I also confirm the second carried item: `bmo._WITHDRAWAL_KEYS` is a list of description
keywords printed by its own four-document cohort — an R-1-class hardcode that the canonical
guards do not catch. Both deserve a card; neither is this branch's to fix.

### 3.6 The sweep attribution, the scans, W3 and ownership (hostile question 6)

**The attribution method is sound.** Restoring the base's `scotia.py` and `wells.py` into the
tip worktree isolates this card, because those are the branch's only production files: the
`corpus_gate.py` change is three string entries in a register with no logic, and
`corpus_gate` is not on the analysis path the replay exercises. **Verified independently
rather than accepted**: 12 of the 66 outside findings, replayed `--expect-identical` at my
own true base `aaa3441`, come back with **0 payload identical** — all 12 already differ from
the run of record with none of this branch present. The 4 inside findings are exactly the 4
documents the card touched.

**Scans** reproduce: 0 over 1,598 added lines against the 472-document population (raw 7, six
`round_money` and one `words_class`), and 0 in every class over 9 commit messages.

**The corpus gate.** The corpus-marked slice runs `corpus_gate.run_gate` and asserts no check
failed, so the marked slice is the gate. The cell reports GREEN — 105 PASS / 3 WITHHELD / 1
REFUSED with currency 108/108 = 14 CAD / 94 USD and `currency_source` unchanged. The currency
conclusion is independently established by the payload-identical replays above, which is the
stronger evidence for the pinned surface because it covers all 454 rather than the 109.

**W3** is append-only — 501 added, **0 removed**, no other section edited — but see MINOR 1.

**Ownership**: two production files as the card allows, plus `corpus_gate.py` outside the
card's list. Disclosed by the cell in ROWCAP.12, forced by the repo's own guard
(`test_every_production_caller_of_the_analysis_is_classified`), and data-only. Acceptable as
a disclosed deviation. The cell's handling of that guard is a credit to it: answering it
turned up a second, real defect — three instruments calling the analysis with the cached text
and no page partition — which it fixed and re-measured.

---

## 4. Findings

**BLOCK: none.** No regression; no weakened check; no wrong published figure; no hardcode
added; no currency or provenance movement; the floor green at the tip.

**MINOR 1 — W3 §ROWCAP has no section header.** The appended block opens at
`## ROWCAP.1`; there is no `# §ROWCAP — …` line. Every one of the twelve preceding sections
has one, BATCH9-RULES names the section `§<CARD>`, and the train helper rebuilds the log
keyed on sections — so as committed the ROWCAP record reads as a continuation of
`§COMMSEC9`'s body rather than as its own section. Nothing was removed (501 added / 0
removed); the fix is one header line.

**MINOR 2 — three record figures do not reproduce.** (a) The floor row says the privacy scan
covered **1,592** added lines over **8** commits; at the tip it is **1,598** over **9** — the
row was measured before the last W3 commits, which the section itself anticipates, so the
numbers should be refreshed. (b) The wells census denominators in ROWCAP.4 (30,347 records /
30,339 money cells / 4,218 balance cells) do not reproduce for me (**29,857 / 29,849 /
4,074**) sweeping the same 221 documents through `_published_section` and
`_transaction_rows`. The load-bearing figures — **2** symbol money cells, **0** symbol
balance cells, both on the two named documents — reproduce exactly, so the conclusion stands;
the denominators should be re-derived or their method stated.

**MINOR 3 — the `tables.py` carried finding is under-specified.** It should carry the
measurement in §3.4: the trigger shape touches **0 of the 159 protected rbc** documents and
**all 34 protected cibc** documents. Without that, the next cell cannot size the work.

**NOTE 1 — the ordering rule's two bounds**, both driven in §2.1: a same-day cross-sheet
inversion is not repaired (and is caught only by `reconcile`), and a back-dated correction
printed after later-dated rows would now be refused where the base validated it. Zero
documents in the archive are exposed to either. Worth one sentence in the record.

**NOTE 2 — the wells coverage claim** is exhaustive over the archive cohort, not over Wells
layouts generally; and the drop is invisible where the statement's own totals do not cover
the dropped row (the same pre-existing shape as the reader's existing drop).

**NOTE 3 — `corpus_gate.py` is outside the card's ownership list.** Disclosed, data-only,
guard-forced; recorded so composition sees it named.

---

## 5. Answers to the deliverable's explicit questions

* **Newly validated 2 by sha?** YES — `D00562176BEC0AAE` and `B52CDF2BA874BBB4`, re-measured,
  with 17/17 and 19/19 printed sheet strips reproduced exactly in count and total by evidence
  the reader never reads, coverage 1.000/1.000 and breaks 0.
* **Preserved 454/454 identical?** YES — 159 + 217 + 78 payload **identical**, payload changed
  0, at base and at the tip, exit 0 on every cohort.
* **Withheld payload changes classified?** YES — two documents, both still withheld, every
  changed leaf downstream of one removed debit record; no credit-side leaf and no printed
  figure moved; `posting_dates_cover_source` fails for the right reason.
* **Regressions 0?** YES — validated regressions 0 and other ladder regressions 0 on every
  cohort; the whole-archive sweep's 70 findings are 4 inside the named population and 66
  outside, and the 66 are proven — on an independent 12-document sample at my own true base —
  to differ from the run of record without this branch.
* **Currency / provenance unmoved?** YES — the two CAD-pinned readers replay payload-identical
  on all 237 of their protected documents, `rbc.py` is untouched, and the movers publish CAD
  by the institution default with provenance unchanged.
* **Privacy 0?** YES — 0 over 1,598 added file lines and 0 in every class over 9 commit
  messages.

---

*Reviewer's instruments and logs are private (`scratchpad/b9/review_rowcap/`):
`base_replay.log`, `tip_replay.log`, `floor.log`, `mutation.log`, `scotia_attack.py`,
`wells_attack.py`, `wells_census.py`, `order_census.py`, `tables_population.py`,
`attrib_sample_base.md`, `rev_ceiling_wrapped.md`. They print shas, gate names, shapes,
counts and ratios only — never a document value.*
