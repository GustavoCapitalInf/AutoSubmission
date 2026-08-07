# W3 Track A — variant completeness: per-family inventory and rulings

Agent E (REEF-2), 2026-08-07. Branch `wave3-variant-completeness`.
Mandate: Gustavo's ruling 2 — work the 614 claimed-but-withheld documents at
the **layout-family / extraction-capability** level, ranked by the W3-2
evidence queue. No statement-specific fixes. Fail closed rather than fabricate.

Idiom follows `R1_HARDCODE_LOG.md`: one row per finding, each with the
structural signature it was recognised by, the root cause, the ruling, and the
fixture that pins it.

---

## 0. Summary

| | |
|---|---|
| Cells worked | `chase x detail_coverage` (217), `x ledger_identity` (88), `x posting_date_coverage` (6), `x period_integrity` (5) — **316 of the 317 chase withheld records, 300 distinct documents** |
| Layout families characterised | 12, all closed at the capability level |
| Result | **300 / 300 validated**, from 0 / 300 |
| Statement-specific constants added | none (23 description literals **removed**) |
| Protected modules touched | none |
| Files changed | `analysis/chase.py`, `tests/test_chase_native_variants.py` (new), this log, plus the re-baselined `docs/adb-audit-results.csv` + its companion `docs/adb-forensic-audit.md` (§2.2) |
| Truth-set movement | **24 ADB fields on 3 Chase statements, re-baselined — approved by Ocean 2026-08-07.** Ceremony, field-level verification and evidence in §2. Every balance field on all 109 byte-identical; outcome classes unmoved |
| Proof (post-merge, post-ceremony) | `pytest -q` **2,024 passed** / 18 deselected · `pytest -q -m corpus` **green** · `python corpus_gate.py` **RESULT: GREEN** (exit 0, every module PASS) · guard tests (R-1 hardcodes, R-2 clones) 100 passed |

## 1. Cell 1 — `chase x detail_coverage`, 217 documents

The largest single withheld cell: 35% of all withheld documents, 63.5% of the
`detail_coverage` class (WAVE2_EXECUTION_LOG, W3-2 measured re-run
`…-02e90a86`).

### 1.1 The cell reproduced independently

Joining the W3-2 diagnostics run to the tranche-1/2 parser attribution by
content hash reproduces Ocean's table exactly — 614 diagnosed, `chase x
detail_coverage` = 217 — so the queue this work is ranked by is confirmed, not
assumed. Within the cell the failing checks are uniform:

| Evidence | Documents |
|---|---|
| `adb:final_balance_matches_statement_closing` | 217 / 217 |
| `adb:ledger_reconciles_to_closing` | 217 / 217 |
| `integrity:ledger_sum_mismatch`, `recon:sum_check_failed` | 217 / 217 |
| `integrity:credit_detail_coverage_mismatch` | 142 |
| `integrity:debit_detail_coverage_mismatch` | 118 |
| `adb:posting_dates_cover_source` | 20 |

217 documents, 213 distinct content hashes (4 exact duplicates inside the
cell). Every one is a **native-text** document: zero of the 213 carry a single
`<table>` fragment, so all 213 resolve through `chase.py`'s native
`*start*…*end*` block path and none through its HTML-table path. That is the
first structural fact and it scopes the whole cell.

### 1.2 The measurement instrument (used before any code changed)

Chase prints, for every detail section, a `Total <section> $X` line, and in
CHECKING SUMMARY an instance count per section. That makes completeness
**checkable against the document itself**, with no expectation file and no
audited truth set: for each section, does the sum of the rows we capture equal
the total the bank printed?

Baseline over the 213, before any change:

| Section | printed total reproduced | printed total NOT reproduced |
|---|---|---|
| DEPOSITS AND ADDITIONS | 53 | **160** |
| ATM & DEBIT CARD WITHDRAWALS | 127 | **54** |
| ELECTRONIC WITHDRAWALS | 89 | **123** |
| OTHER WITHDRAWALS | 47 | 9 |
| FEES | 78 | **117** |
| CHECKS PAID | 59 | 23 |
| **documents with every printed section total reproduced** | **0 / 213** | |

Every deviation was in the same direction — **captured < printed**, never
above. The platform was losing rows, never inventing them, which is why the
whole cell landed on `detail_coverage` and not on `source_contradiction`.

### 1.3 The families

Named by structure. Nothing below names a customer, a bank product, an amount
or a date; every rule is anchored on the printed grid.

| # | Family | Structural signature | Root cause | Ruling | Fixture |
|---|---|---|---|---|---|
| F1 | wrapped-amount cell | the amount column wraps onto its own physical line and the description continues on lines after it | the block was flattened to one string and the row's **last** money-shaped token was taken as the amount | FIX — the amount is the cell the grid prints: a line that is only a money token, else the token that terminates a line (the column is right-aligned) | `test_f1_*` |
| F2 | unlisted description prefix | a row whose description begins with a phrase absent from the parser's 23-entry `_ROW_STARTERS` whitelist | rows were segmented by **description wording**: an unlisted row was folded into its predecessor — the row vanished *and* the predecessor took the swallowed row's amount | FIX — a row begins where the statement begins one: a physical line whose first token is the MM/DD posting date. The whitelist is deleted | `test_f2_*` (5 parametrised prefixes incl. one that exists nowhere) |
| F3 | compressed line | the text layer emits the column header and several rows on ONE physical line | same whitelist rule; unlisted rows on a shared line could not be separated | FIX — split inside a line only at the **amount → date seam** (`\.\d{2}` then whitespace then MM/DD), which cannot fire on the second MM/DD inside a card row because that one is preceded by words | `test_f3_*` |
| F4 | rate-suffixed amount | a foreign-currency row prints `<n> X 0.000668276 (Exchg Rte)` after the amount | the money regex had no right boundary, so `0.000668276` matched as `0.00` and, being last, became the row's amount | FIX — `(?![\d])` boundary on the money token | `test_f4_*` |
| F5 | heading-prefixed continuation line | an ACH description wraps onto a line beginning `Fees Sec:PPD Trace#…` | the section-block scan matched `^HEADING(\s|\(|$)`, so that line made an ELECTRONIC WITHDRAWALS block *also* claim to be the FEES section — its rows were counted twice. The same loose anchor made the CHECKING SUMMARY block (`Fees 1 -15.00`) read as a detail section | FIX — a heading owns its line: `^HEADING (continued)? ($ or DATE…)`. That admits all three printed forms and rejects description furniture | `test_f5_*` |
| F6 | purchase-with-cash-back | the description itself carries money (`Purchase $352.94 Cash Back $40.00`) and the amount cell wraps below | any "first/last money token" rule reads a description amount | FIX — the standalone wrapped amount cell outranks line-terminal tokens (this is what decides F1's preference order) | `test_f6_*` |
| F7 | check-number and dual-date variants | check numbers shorter than 3 digits or longer than 6; a second printed date between the check date and the amount | the check regex required `\d{3,}` and exactly one date, and required two separate whitespace runs around the `*`/`^` markers | FIX — check rows are segmented like transaction rows (row starts at the check number, bounded at 10 digits so a page-barcode digit run cannot open one) and matched with an explicit marker/date/date/amount grammar | `test_f7_*` |
| F8 | described electronic check | an electronic check prints an ACH description, so the check number and its date+amount land on **different** physical lines | the regex was single-line and matched neither | FIX — same row grouping; the grammar allows a description between the number and the date | `test_f8_*` |
| F9 | multi-check line | several check rows on one physical line | no inline segmentation | FIX — amount → check-number seam | `test_f9_*` |
| F2b | dual-date row | `12/15 12/13 Online Transfer …` — the DATE column plus a printed transaction date | the deleted splitter cut the line **twice**, once before each date, orphaning the posting date on a line with no amount, so the row began at the *transaction* date | FIX — a row is dated by the DATE column. See §2: this is the change that moves two pinned corpus documents | `test_f2b_*` |
| F10 | Commercial Checking summary | debit rows print a space between sign and figure (`Checks Paid 1 - 530,178.70`); the withdrawals/fees rows are one combined row | the summary amount pattern demanded the sign adjacent to the digits, so NO debit row matched and `stated_total_debits` stayed `None` — the bank's own summary could not be checked against the ledger at all | FIX — allow whitespace after the sign; the combined summary label joins the debit-label set (it cannot collide with the shorter labels, which only match when a count follows immediately) | `test_f10_*` |
| F11 | page-break-split row | the amount cell is the last line of a page and the rest of the description opens the next page's `(continued)` block | `(continued)` was treated as a row boundary, so the row lost its description and was discarded | FIX — `(continued)` is furniture; a section's blocks are grouped as one line stream in document order | `test_f11_*` |
| F12 | combined detail section | the same layout prints `OTHER WITHDRAWALS, FEES & CHARGES` instead of separate OTHER WITHDRAWALS and FEES sections | the parser never asked for that heading, so a summary-stated debit total had no detail read at all | FIX — the combined heading joins the native section list, symmetric with F10's summary label | `test_f10_*` |

Negative fixtures (each must keep passing, and each did before the change —
they constrain the new rules rather than demonstrate the defect):

- a second MM/DD **inside** a card row never starts a row (`test_f2_negative_*`);
- an inline date not preceded by an amount never splits a row (`test_f3_negative_*`);
- a real heading still matches standalone, with `(continued)`, and with the
  column header on the same line (`test_f5_negative_*`);
- a long page-barcode digit run is not a check number;
- a CHECKING SUMMARY line is never a transaction section.

### 1.4 What did NOT change, deliberately

- **The HTML-table path** (`_parse_section` / `_parse_txn_table`) is untouched.
  No document in the cell uses it, so changing it would be unevidenced.
  Its known gap — the table path never reads CHECKS PAID or OTHER
  WITHDRAWALS — is recorded here as a **carried finding**, not fixed, because
  no measured document needs it yet.
- **`analysis/pipeline.py`, the registry, the shared utilities** — untouched.
  `compact_whitespace` from `analysis/tables.py` is now used (it was already
  the correct shared helper); no shared utility's behaviour changed, so no
  differential-equivalence proof is owed.
- **Daily-ending-balance extraction.** Chase prints a DAILY ENDING BALANCE
  section that the parser still does not read (`stated_daily_balances` is
  absent on all 217). It was not needed to close the cell and adding it would
  be scope the evidence does not ask for. Carried finding.

### 1.5 Result over the cell

Section-total agreement after the change, same instrument, same 213 documents:

| Section | printed total reproduced | not reproduced |
|---|---|---|
| DEPOSITS AND ADDITIONS | 213 | 0 |
| ATM & DEBIT CARD WITHDRAWALS | 181 | 0 |
| ELECTRONIC WITHDRAWALS | 212 | 0 |
| OTHER WITHDRAWALS | 56 | 0 |
| FEES | 195 | 0 |
| CHECKS PAID | 82 | 0 |
| **documents with every printed section total reproduced** | **213 / 213** | |

(Section counts below 213 are documents that do not print that section at all.
The instrument's "heading present but no printed total" bucket was checked by
hand and is a measurement artefact, not a missing section: those matches are
CHECKING SUMMARY service-charge lines and disclosure prose that merely contain
the heading words. No document in the cell is missing a detail block its
summary counts.)

### 1.6 Outcome, production path

`analyze_markdown` in deterministic mode over the same locally rendered
markdown, classified with the same mapping discovery uses
(`telemetry.record.classify_outcome`), and diagnosed with the same
`telemetry.diagnostics.diagnose`:

| Cell | documents (distinct hashes) | before | after |
|---|---|---|---|
| `chase x detail_coverage` (217 records) | 213 | 0 validated / 213 withheld | **213 validated / 0 withheld** |
| `chase x ledger_identity` (88), `x posting_date_coverage` (6), `x period_integrity` (5) | 87 | 0 validated / 87 withheld | **87 validated / 0 withheld** |
| **total** | **300** | **0 / 300** | **300 / 0** |

That is **316 of the 317 chase withheld records**, 300 distinct documents.
"Before" is the frozen discovery result itself: these documents ARE the cells,
defined by having been withheld. Ocean re-measures against the frozen baseline
post-merge; the numbers above are a local preview computed from the same
production ladder (`ocr.pipeline.parse_statement`, native rung, no OCR, no
model calls, `$0.00`).

**Nothing was padded to get there.** Every document that now validates does so
because the rows we extract reproduce, independently: the bank's printed
per-section totals, the bank's stated credit and debit totals, the ledger
identity (beginning + activity = ending), and the full ADB validation suite.
The fail-closed gate is unchanged; the documents pass it on their own
arithmetic. The three that resisted longest (§F10/F11/F12) were each a real
layout the parser had never been taught to read, not a threshold that was
loosened.

---

## 2. Truth-set re-baseline — 3 pinned documents — **APPROVED AND EXECUTED**

**Approval: Ocean, 2026-08-07** (coordinator message, this session). The first
truth-set movement in the project's history. Approved on three grounds, each
independently checkable and recorded below: the transaction sets are identical
before and after; the bank's own DAILY ENDING BALANCE day set — never read by
the parser — matches exactly after and not before; and the old pins encode the
defect `analysis/adb.py` itself names.

The finding as raised is §2.1; the ceremony as executed is §2.2.

### 2.1 The finding

`python corpus_gate.py` goes RED on exactly three pinned statements — all
Chase, all in the `adb_audit` module only:

```
[PASS] inventory / foreign_files / source_integrity
[PASS] balance_audit: 109 statements reproduce every audited balance field ...
[FAIL] adb_audit: ... (25 field lines across 3 statements, listed below)
[PASS] balance_outcomes: balance: 106 pass, 3 withheld, same three statements
[PASS] adb_outcomes:     adb:     106 pass, 3 withheld, same three statements
[PASS] ocr_coverage / exclusions / oracle_independence
Outcomes: 106 PASS / 3 WITHHELD
RESULT: RED
```

Every *balance* field on all 109 is byte-identical, and the outcome classes
(106 PASS / 3 WITHHELD, the same three by name) do not move.

**The drift is not a loss of detail.** All three documents parse to the
*identical* set of transactions before and after — same 89 / 98 / 100 rows,
same amounts, same descriptions — and all three reproduce their bank-stated
credit and debit totals exactly, before and after. What changed is the **date**
on the rows Chase prints with two dates (`12/15 12/13 Online Transfer …`):

- Before: the transaction date (`12/13`).
- After: the posting date (`12/15`) — the value printed in the DATE column.

The old value was an accident of the deleted whitelist splitter: it split the
line twice, once before each date, leaving the posting date orphaned on a line
of its own with no amount, so the row began at the *second* date.

Forensic proof that the new dates are the correct ones, taken from each
document's own DAILY ENDING BALANCE section — the bank's published daily
ledger, which no part of the parser reads and which is therefore an
independent oracle:

| | Feb 27 2026 | Dec 2025 | March 2026 |
|---|---|---|---|
| days the bank prints a daily ending balance for | 19 | 22 | 22 |
| activity days reconstructed BEFORE | 22 | 27 | 24 |
| — days the bank prints NO balance for | `01/31`, `02/14`, `02/21` | `11/29`, `12/07`, `12/13`, `12/27`, `12/28` | `03/01`, `03/14` |
| activity days reconstructed AFTER | **19** | **22** | **22** |
| — days the bank prints NO balance for | none | none | none |
| day set identical to the bank's | **yes** | **yes** | **yes** |
| printed daily balances reproduced | 19 / 19 | 22 / 22 | 22 / 22 |

After the change each reconstructed activity-day set is **exactly** the day set
Chase prints, and every printed daily balance is reproduced. Before the change
the ledger invented up to five activity days the bank does not recognise — one
of them (`11/29`) outside the statement period entirely — and the ADB was
divided across that phantom day series. This is precisely the condition
`analysis/adb.py` itself names: *"posting dates have been folded together, so
end-of-day balances are attributed to the wrong days and the ADB is not
trustworthy"* (`posting_dates_cover_source`).

Consequently the pinned expectations for these three documents encode a defect.
The drifting fields:

| Field | Feb 27 2026 | Dec 2025 | March 2026 |
|---|---|---|---|
| `posting_days` | 22 → 19 | 27 → 22 | 24 → 22 |
| `same_day_groups` | 18 → 19 | 21 → 20 | — |
| `max_same_day_transactions` | 9 → 10 | — | — |
| `no_activity_days` | 6 → 9 | 6 → 11 | 8 → 10 |
| `daily_balance_sum` | 987,536.52 → 1,004,811.64 | 2,094,777.33 → 2,232,248.29 | 1,011,307.06 → 1,011,610.88 |
| `independent_candidate_adb` / `backend_adb` / `api_adb` / `dashboard_adb` | 35,269.16 → 35,886.13 | 63,478.10 → 67,643.89 | 31,603.35 → 31,612.84 |

Note the independent oracle (`independent_candidate_adb`, which imports no
production financial mathematics — the gate's `oracle_independence` check still
passes) moves *with* the production surfaces to the same new number. The two
agree on the corrected value as they agreed on the old one; what changed is the
day series both are computed over.

The alternative — preserving the old dates — means knowingly dating
transactions to days the bank publishes no balance for, and would leave the
`posting_dates_cover_source` failures in the chase population unfixable by
construction.

### 2.2 The ceremony, as executed

Order, and the assertion discharged at each step:

| # | Step | Evidence |
|---|---|---|
| 1 | `git merge main` **first** (main at `cba8c77`, the W3-3c structurer merge) | clean, no conflict; `git diff HEAD~1 -- analysis/chase.py tests/test_chase_native_variants.py docs/.../W3_TRACKA_LOG.md` is **empty** — the merge touched none of this branch's files. Post-merge default suite re-run: **2,024 passed, 18 deselected** |
| 2 | Regenerate **only** the ADB CSV, by running the **unmodified** oracle | `git diff --exit-code adb_forensic_audit.py` → empty, exit 0 (asserted before the run; the file's last commit is still `515bfaa`, CI-1c). Command: `python adb_forensic_audit.py "Bank Statements" --ocr-cache tests/corpus_cache`, exit 0, `Wrote 109 rows … {'PASS': 106, 'WITHHELD': 3, 'FAIL': 0}` |
| — | The balance CSV is **not** touched | `sha256(docs/balance-metrics-audit-results.csv)` unchanged at `dbf59901…fb10e89`; `git diff --exit-code` on it → empty, exit 0 |
| 3 | Field-level verification, scripted | see the delta classes below; verifier exit 0 |
| 4 | Statuses hold | `{'PASS': 106, 'WITHHELD': 3}`, `FAIL` absent; withheld set asserted equal to `Ace_Auto_Final_Cut.pdf`, `BMO_Statement_January_2026 Final-1-2 (1).pdf`, `IBC April (1).pdf` |
| 6 | Proofs | `corpus_gate.py` → **RESULT: GREEN**, exit 0, every module PASS · `pytest -m corpus` green · default suite green · guard tests green |

**Delta classes.** The verifier keys both CSVs by corpus-relative path (so an
identically named statement in another folder can never be compared against
this one), walks every cell, and partitions every difference into exactly one
of three classes. It exits non-zero if the third is non-empty.

| Class | Cells | Meaning |
|---|---|---|
| **APPROVED** | **24**, on **3** statements | the re-baselined fields, enumerated below |
| **POSIX folder reformat** (CI-1c) | **17** | writer-side only: `folder` values written on Windows before CI-1c read `Others\Altana`; the unmodified writer emits `as_posix()`. The gate has compared path-valued fields separator-agnostically since CI-1c, so these were never drift — they are counted and reported separately, not folded into the approved total |
| **UNEXPECTED** | **0** | anything on any other statement, or any non-path field difference outside the three. Zero |

Column set identical (38), row key set identical (109/109).

The line-level diff corroborates the cell-level partition independently:
`git diff --numstat docs/adb-audit-results.csv` reports **20 changed rows** =
3 approved + 17 POSIX, and the changed row keys are exactly the 3 Chase
statements plus 17 rows under nested `Others/*` folders (the only rows whose
`folder` value contained a separator).

**Per-statement before → after.** Every changed field, by column name:

| Field | Feb 27 2026 | Dec 2025 | March 2026 |
|---|---|---|---|
| `posting_days` | 22 → **19** | 27 → **22** | 24 → **22** |
| `same_day_groups` | 18 → **19** | 21 → **20** | — |
| `max_same_day_transactions` | 9 → **10** | — | — |
| `no_activity_days` | 6 → **9** | 6 → **11** | 8 → **10** |
| `daily_balance_sum` | 987,536.52 → **1,004,811.64** | 2,094,777.33 → **2,232,248.29** | 1,011,307.06 → **1,011,610.88** |
| `independent_candidate_adb` | 35,269.16 → **35,886.13** | 63,478.10 → **67,643.89** | 31,603.35 → **31,612.84** |
| `backend_adb` | 35,269.16 → **35,886.13** | 63,478.10 → **67,643.89** | 31,603.35 → **31,612.84** |
| `api_adb` | 35,269.16 → **35,886.13** | 63,478.10 → **67,643.89** | 31,603.35 → **31,612.84** |
| `dashboard_adb` | 35,269.16 → **35,886.13** | 63,478.10 → **67,643.89** | 31,603.35 → **31,612.84** |
| **fields changed** | **9** | **8** | **7** |

Nothing else moved on these rows: `opening_balance`, `closing_balance`,
`transactions`, `calendar_days`, `evidence_basis`, `closing_drift`,
`backend_difference`, `status`, `confidence` and every other column are
byte-identical. The transaction **count** is unchanged on all three (89 / 98 /
100) — the re-baseline moves the day series the ADB is computed over, not the
ledger.

The independent oracle moves *with* the three production surfaces to the same
corrected number on every statement, and the gate's `oracle_independence` check
still passes — `independent_candidate_adb` is computed by
`adb_forensic_audit.py`, which imports no production financial mathematics.

**Companion report.** The same unmodified script writes
`docs/adb-forensic-audit.md` alongside the CSV. Its diff is **3 lines** — the
same three statements, all four surfaces agreeing, `$0.00` difference, `PASS`
— and nothing else. Reported distinctly because it was not separately
requested; it is the same run's output and is committed with it so the two
cannot drift apart.

---

## 3. Carried findings — all ruled (Ocean, 2026-08-07)

1. **§2 re-baseline** — **APPROVED and executed.** Closed.
2. **Table-path CHECKS PAID / OTHER WITHDRAWALS gap** (§1.4) — **RULED: stays
   deliberately unfixed, evidence-gated.** Recorded here as a known gap: the
   HTML-table path never reads those two sections. No document in any worked
   cell uses that path (0 of 300 carry a `<table>` fragment), so fixing it
   would be an unevidenced change to code the measurement cannot exercise. It
   becomes live the moment a measured document needs it.
3. **`stated_daily_balances` as a first-class oracle** (§1.4) — **RULED: a
   strong future card, queued.** Chase publishes its own daily ledger and the
   platform ignores it. §2 is the argument for its value: that printed series,
   read by nothing in the parser, is exactly what settled the posting-date
   question against a pinned truth set. Reading it would let the ADB engine
   validate against the bank's series rather than only reconstructing one.
4. **Promotion of the row grouper to `analysis/tables.py`** — **RULED: AGREED,
   in that order.** Characterise `td_canada_native x detail_coverage` (61) and
   `rbc x detail_coverage` (48) FIRST; the promotion decision follows the
   evidence, and if it moves it moves with an R-2 differential-equivalence
   proof. The grouper's three rules (a row starts at a date-shaped first token,
   wrapped lines continue it, the amount is the right-aligned cell) are layout
   facts rather than bank facts, but one parser's evidence is not enough to
   move code that every parser would then depend on.

## 4. Handoff — reconnaissance on the next two cells

Diagnostics-only (no documents read, no code touched); recorded so whoever
takes these cells starts from evidence rather than from the Chase analogy.

| | `td_canada_native x detail_coverage` (61) | `rbc x detail_coverage` (48) |
|---|---|---|
| ledger identity fails | 61 / 61 | 48 / 48 |
| debit coverage short | 61 / 61 | 46 / 48 |
| credit coverage short | 59 / 61 | 35 / 48 |
| `running_balances_support_daily_ledger` fails | **0** | **48 / 48** |
| `integrity:running_balance_breaks` | **0** | **48 / 48** |
| `posting_dates_cover_source` fails | 0 | 1 |

**The two cells are not the same shape, and neither is exactly Chase's.**
td_canada looks like the Chase case: coverage is short on both sides, and no
printed running balance exists to contradict. RBC is different — every one of
its 48 documents *also* breaks running-balance continuity, which means RBC
prints a running-balance column. A row in that layout carries **two** money
cells, so the grouper's "the amount is the right-aligned cell" rule is
underdetermined there and needs a two-column variant before anything is
promoted.

That is the concrete question the promotion decision turns on, and it is why
the ruling to characterise both cells first is the right order: had the grouper
been promoted on Chase's evidence alone, RBC would have inherited a rule that
reads its balance column as its amount.

---

## 5. Cell 3 — `rbc x detail_coverage`, 48 records / 46 documents

REEF-RBC, 2026-08-07. Branch `wave3-rbc-completeness`, base `d775bbe`
(worktree tip `0c13c21`, which adds only the two handoff files and the
execution log on top of it). Brief: `docs/agent-handoffs/REEF-RBC.md`.

Same method as §1 — characterise families, root-cause, capability-level fix or
fail-closed-by-design, prove with synthetic fixtures both directions, measure
the cell honestly. Different shape: §4's reconnaissance was right, and the trap
it named is the whole cell.

### 5.0 Summary

| | |
|---|---|
| Cell worked | `rbc x detail_coverage` — 48 records, 46 distinct documents |
| Result | **42 of 48 records / 40 of 46 documents validate**, from 0 |
| Side cluster `rbc x balance_continuity` (18) | **18 / 18 validate**, from 0 |
| Already-validated rbc documents (89) | **89 / 89 still validate** — zero regressions |
| Layout families characterised | 11, all closed at the capability level: 10 fixed, 1 ruled FAIL CLOSED with its volume |
| Statement-specific constants added | none (two description-keyed rules **removed**) |
| Protected modules touched | none. `analysis/tables.py`, `analysis/money.py`, `analysis/date_tokens.py`, `analysis/chase.py`, `analysis/td_can.py` unchanged; `_MONTHS` and `normalize_mojibake` consumed unchanged |
| Truth-set movement | **none.** All five pinned RBC statements (4 English + 1 French) parse byte-identically; `corpus_gate.py` GREEN, 106 PASS / 3 WITHHELD, same three by name. **No re-baseline requested or performed** |
| Files changed | `analysis/rbc.py`, `tests/test_rbc_variants.py` (new), `tests/test_analysis.py` (one fixture description), this log |

### 5.1 The cell reproduced independently

Joining the frozen `c3e557f0` run's telemetry diagnostics to its parser
attribution reproduces Ocean's table exactly: `parser_id == "rbc"` gives 156
records — 90 validated, 66 withheld — and the withheld split by primary class
is **`detail_coverage` 48** and **`balance_continuity` 18**. The 48 records are
46 distinct content hashes (two exact duplicates inside the cell), every one in
the `RBC/` folder, every one resolved through the **native** rung. The failing
checks are uniform and match §4's reconnaissance:

| Evidence | Records |
|---|---|
| `adb:final_balance_matches_statement_closing`, `adb:ledger_reconciles_to_closing`, `adb:running_balances_support_daily_ledger` | 48 / 48 |
| `integrity:ledger_sum_mismatch`, `integrity:running_balance_breaks`, `recon:running_balance_break`, `recon:sum_check_failed` | 48 / 48 |
| `integrity:debit_detail_coverage_mismatch` | 46 |
| `integrity:credit_detail_coverage_mismatch` | 35 |
| `adb:posting_dates_cover_source` | 1 |

### 5.2 The measurement instrument (used before any code changed)

RBC prints, in Account Summary, a **count and a total for each direction**:

```
Total deposits & credits (109) + 43,062.10
Total cheques & debits  (223) - 44,655.90
```

plus an opening and a closing balance, plus an intermittent running-balance
column. Completeness, sign assignment and the ledger identity are therefore all
checkable **against the document itself** — no expectation file, no audited
truth set. That instrument is stronger than Chase's per-section totals because
it pins the row COUNT on each side as well as the money.

Its trustworthiness is not assumed: over the 89 rbc documents discovery had
already validated, the instrument agrees on **89 / 89** for row count and gross
money — so a document that fails it is failing the bank's own arithmetic.

Baseline over the cell, before any change (46 documents):

| | documents |
|---|---|
| row count equals `credit_count + debit_count` | 40 / 46 |
| gross money equals `stated credits + stated debits` | 16 / 46 |
| credit total reproduced | 10 / 46 |
| debit total reproduced | **0 / 46** |
| ledger identity holds | 0 / 46 |
| printed balance chain unbroken | 0 / 46 |

The decisive partition: **16 documents captured every row and every amount
correctly and got only the SIGNS wrong** (row count and gross money both exact,
per-direction totals both wrong). That is the dual-money-cell problem in its
purest form and it is not a coverage problem at all — the platform reported it
as `detail_coverage` because a mis-signed row moves money from one stated total
to the other, which reads exactly like a missing row.

### 5.3 The dual money cell, solved structurally

RBC's activity table prints **three** money columns:

```
Date | Description | Cheques & Debits ($) | Deposits & Credits ($) | Balance ($)
```

The native text layer collapses every run of whitespace before any parser sees
it (verified: 22,278 money-shaped tokens across the 153 rbc activity sections,
zero column padding preserved), so **the column an amount was printed in is not
in the text**. Two distinct questions follow, and both are answered from the
statement's own printed evidence rather than from token order or wording:

**(1) Which cell is the amount and which is the running balance.**
The Balance column is printed last and is never printed without an amount
beside it. So: *two money cells with no text between them are one row's amount
and its running balance; a lone money cell is an amount.* The rule is decided
by adjacency in the grid, and it is deliberately blind to the values — a
balance smaller than its own amount is still the balance (`test_f1_*`). This is
what the old rule got wrong: it took "the last money token, if the line has two
and ends with one", which is the same thing on a simple row and wrong on every
row that carries three cells, a printed rate, or a printed reference number.

**(2) Which activity column the amount stood in — the sign.**
The printed running balance closes the arithmetic: over the rows between two
printed balances the signed amounts must reproduce the delta. Two solvers, same
evidence:

* `_column_split_signs` — inside one balance block RBC prints the deposits
  column above the withdrawals column, so the credit set is a **prefix**. The
  prefix total is strictly increasing, so at most one split reproduces the
  delta: **the assignment is unique whenever it exists, with nothing to choose
  between.** Measured: **4,513 of 4,570 segments** across the whole rbc
  population solve here.
* `_subset_signs` — the same delta with no ordering assumption: a bounded
  subset-sum (max 24 rows, max 200,000 states, refuses past either). Used on
  the remainder.

Where several assignments reproduce the same delta — which happens only when
equal amounts sit on both sides, and where **every candidate publishes the
identical credit and debit totals** — the printed column order breaks the tie
deterministically. This is disclosed rather than hidden: it moves a
*direction label* between two rows of the same amount and cannot move a
financial result. It is observable on exactly two of the 153 documents (§5.6).

Where the chain cannot close, **the signs are not invented**. Those rows keep
the direction their transaction type implies and the document then fails the
bank's own stated totals and the ledger identity — which is what keeps the
remaining six documents (§5.4 F11) withheld instead of repaired into agreement.

**No geometry was needed, and none was used.** Stop condition 4 does not fire:
the printed balance column plus the printed stated counts and totals carry
enough evidence to decide the column assignment for 147 of the 153 documents.
The six that remain are not short of column information — their text layer does
not carry the rows in grid order at all (§5.4 F11).

### 5.4 The families

Named by structure. Nothing below names a customer, an amount, a date or an
account fragment; every rule is anchored on the printed grid.

| # | Family | Structural signature | Root cause | Ruling | Fixture |
|---|---|---|---|---|---|
| F1 | **dual money cell** | a row prints an amount cell and a running-balance cell | cells were classified by position in the flattened line (`>= 2 tokens and the last one ends the line`), with a **description-keyed exception** — rows whose text contained `TRANSACTION FEE` were denied a balance, so on those rows the balance became the amount | FIX — the grid decides: adjacent cells are (amount, balance), a lone cell is an amount. The wording exception is deleted | `test_f1_*` |
| F2 | **column of origin (the sign)** | the amount's column is absent from the text | the sign came from a description vocabulary and was repaired only for segments of at most 16 rows, and only toward whichever assignment was closest to the vocabulary's guess — so long blocks were never solved and short ones could be solved wrongly | FIX — `_solve_from_printed_balances`: column-order split, bounded subset-sum fallback, no repair when the chain cannot close | `test_f2_*` |
| F3 | **compressed line** | several printed rows emitted on ONE physical line (`... 10,000.00 32,118.42 Misc Payment ... 783.48 ...`) | only the last two money tokens of a line were ever considered; everything earlier was lost or folded into a description | FIX — a row ends at its amount cell, so text after one begins the next row. No wording whitelist, unlike the Chase F2 defect | `test_f3_*` |
| F4 | **wrapped row** | one printed row spread over several physical lines | description accumulation existed but a line carrying no money cell after an amount was dropped | FIX — same rule; a description-only line continues the pending row | `test_f4_*` |
| F5 | **vertically centred amount cell** | the amount is printed alone on its line, BETWEEN two description lines | the line after the amount opened a new row and took the rest of the previous row's description with it | FIX — a bare-amount line does not close the description | `test_f5_*` |
| F6 | **printed rate operand** | `Regular transaction fee 17 Drs @ 2.50 42.50`, `Overdraft interest @ RBP+05.00%P.A 0.04 4,820.18`, `Handling fee 2 @ $ 5.00 10.00` | the money pattern had no `@`/`%` boundary, so a printed unit price matched as a cell and became the amount; the resulting damage was patched by a `^\d+ Crs @ ...$` regex gated on the words `REGULAR TRANSACTION FEE` | FIX — the operand of the statement's own `@` marker, and a `%`-suffixed operand, are not grid cells. The description-keyed patch is deleted. 170 lines, 89 documents | `test_f6_*` |
| F7 | **printed reference number** | `Water Bill Payment ... 00314.06 1,432.28 -28,340.36` | a zero-padded reference number in the description matched the money pattern, so the real amount was read as a balance and the reference as the amount | FIX — a printed price carries no leading zero. Measured over all 22,278 activity money tokens: every leading-zero token is either an `@` rate or a reference number, and `0.45` (single leading zero) is unaffected. 20 tokens, 6 documents | `test_f7_*` |
| F8 | **closing-balance cell inside a row line** | `31 Mar Online Transfer ... 4,000.00 4.40 Closing balance 4.40` | the table end was recognised only at the start of a line, so the closing cell was read as another transaction | FIX — the printed label ends the table wherever it is printed | `test_f8_a_closing_balance_cell_*` |
| F9 | **page footer shaped like a date** | `1 of 16` / `1 de 7` inside the activity section | *(hazard created by this restructuring, caught by the corpus-marked proof before any commit)* the French footer `1 de 7` parses as day `1` + month token `de`, and `de` resolves unambiguously to `DECEMBRE` — moving whole posting-date groups | FIX — the footer is dropped BEFORE the Date column is read, in both language paths | `test_f8_a_page_number_*` |
| F10 | **French page break** | the French layout reprints its column header on every page, but the French path never left the activity section | *(same hazard)* with F4 in place, the page's own header block (`--- Page n ---`, the Docusign line, the section title) accumulated into the next row's description | FIX — symmetric with the English path: a page break leaves the table and the reprinted column header re-enters it | the pinned French statement, byte-identical; `test_french_*` |
| F11 | **reflowed text layer** | money cells and description fragments emitted out of grid order: a balance opens a physical line, an amount is printed between the description lines of a DIFFERENT row, and in places cells are absent from the text stream altogether | the PDF's text objects are not emitted in grid order, so the row/column structure is not recoverable from the text layer at all | **FAIL CLOSED — 6 documents (6 of 48 records).** They stay withheld with accurate `detail_coverage` diagnostics. The grid reader recovers most rows but the printed balance chain does not close and the bank's stated counts and totals are not reproduced, so nothing is published | none: this family is defined by the ABSENCE of the structure the fixtures pin |

Negative fixtures — each constrains the new rules rather than demonstrating a
defect, and each is asserted:

- a digit run inside a description never opens a row
  (`test_negative_a_digit_run_in_a_description_never_opens_a_row`);
- the `Opening balance` row is never a transaction, and it still supplies the
  chain's first balance;
- a third adjacent money cell does not become a second balance — the reader
  refuses to name a row it cannot see and the document then fails the bank's
  stated totals;
- a single leading zero (`0.45`) is still money;
- a page footer never becomes a row and never breaks the row around it;
- the printed rate operands stay in the description on all three printed forms.

**The mandatory adversarial fixture** the brief requires is
`test_f1_the_naive_last_money_token_rule_is_what_this_fixture_refutes`: a
document on which the naive "the amount is the right-aligned / last money
token" rule — the rule the Chase row grouper would have brought with it —
produces an arithmetically impossible ledger, and which the grid rule extracts
correctly and reconciles. It names the naive read explicitly and asserts the
parser does not produce it.

### 5.5 Result over the cell

Same production ladder discovery used (`ocr.pipeline.parse_statement`, native
rung, no OCR, no model calls, `$0.00`), then `analyze_markdown` in
deterministic mode, classified with `telemetry.record.classify_outcome` and
diagnosed with `telemetry.diagnostics.diagnose`:

| Cell | records | documents | before | after |
|---|---|---|---|---|
| `rbc x detail_coverage` | 48 | 46 | 0 validated / 46 withheld | **40 validated / 6 withheld** |
| `rbc x balance_continuity` (side cluster, measured as asked) | 18 | 18 | 0 validated / 18 withheld | **18 validated / 0 withheld** |
| already-validated rbc | 90 | 89 | 89 validated | **89 validated** |

Record-level, which is how the 614 are counted: **42 of the 48 cell records
validate**; the 6 that remain are the F11 documents. Adding the side cluster,
**60 of the 66 withheld rbc records** move to validated.

Against the in-document instrument, after the change:

| | detail_coverage (46) | balance_continuity (18) | already validated (89) |
|---|---|---|---|
| row count equals stated counts | 41 | 18 | 89 |
| gross money equals stated totals | 40 | 18 | 89 |
| credit count AND total reproduced | 40 | 18 | 89 |
| debit count AND total reproduced | 40 | 18 | 89 |
| ledger identity holds | 40 | 18 | 89 |
| printed balance chain unbroken | 40 | 18 | 89 |

**Nothing was padded to get there.** Every document that now validates
reproduces, independently: the bank's printed credit COUNT and total, its debit
COUNT and total, the ledger identity, the printed running-balance chain at
every printed balance, and the full ADB validation suite. The fail-closed gate
is unchanged; these documents pass it on their own arithmetic.

The already-validated set is worth its own line. 89 / 89 still validate, and
**8 of them improved**: six had a credit/debit COUNT that disagreed with the
bank's own summary (zero-amount and equal-amount rows on the wrong side) and
two had a credit TOTAL that was wrong by tens of thousands while still passing
ADB. All eight now reproduce the printed counts and totals exactly. That is a
correctness gain the outcome class could not have shown.

### 5.6 What did NOT change, deliberately, and what is disclosed

- **No shared utility was touched.** `analysis/tables.py`, `analysis/money.py`
  and `analysis/date_tokens.py` are unmodified; `parse_money`,
  `parse_french_amount` and td_can's `_MONTHS` / `normalize_mojibake` are
  consumed exactly as they were. The R-2 clone guard and the private-import
  allowlist are unchanged and green.
- **The Chase row grouper was not reused and not promoted.** Deferred to Ocean
  as ruled. §5.7 records what this cell contributes to that decision.
- **The description vocabularies (`_is_credit` / `_is_debit`) stay as R-1 left
  them.** They are now only the initial reading, and only survive on rows in a
  block the printed chain cannot close. No entry was added; none was removed.
  Removing them is a separate change with its own evidence burden.
- **Two documents' direction labels are a disclosed tie-break.** On two
  statements (the same statement under two hashes) a block contains two rows of
  the identical amount, one on each side. Every assignment consistent with the
  printed delta publishes the identical credit count, credit total, debit count,
  debit total, ledger identity and balance chain, so no financial value can move;
  what moves is which of the two descriptions carries `credit`. The choice is
  now made by the printed column order — deposits above withdrawals — instead of
  by a memorised description list, which is a better-grounded rule but still a
  choice, and it is pinned by
  `test_f2_equal_amounts_on_both_sides_resolve_to_the_printed_column_order`.
  Downstream transaction classification reads `direction`, so this is named
  rather than buried.
- **Descriptions moved on 35 documents**, all toward the printed text: rate
  operands are no longer amputated from a fee description, reference numbers
  stay in the description they were printed in, and wrapped descriptions are
  now complete. One synthetic fixture in `tests/test_analysis.py` asserted the
  truncated form and was updated with its reason; **no audited value moved** —
  the fixture is not part of the truth set, and every pinned corpus statement is
  byte-identical.
- **The F11 volume is stated, not hidden**: 6 documents, 6 records, 12.5% of the
  cell. They need the PDF's word boxes to read at all; that input belongs to the
  structurer subsystem and wiring it into a parser is an architecture decision,
  so it is reported to Ocean rather than attempted here (§5.7).

### 5.7 Carried findings for Ocean

1. **Row-grouper promotion (§3 item 4) — this cell's contribution.** The Chase
   grouper's third rule ("the amount is the right-aligned cell") is
   **not** promotable as written: it is underdetermined wherever a layout prints
   a running-balance column, and RBC is that layout on every one of its 153
   documents. The promotable form is the one this cell proves: *a lone money
   cell is an amount; adjacent money cells are (amount, balance) in printed
   column order.* That degrades exactly to Chase's rule on a layout with no
   balance column. The other two rules (a row starts at a date-shaped first
   token; wrapped lines continue it) carried over unchanged and needed no RBC
   variant. Two further pieces look layout-general rather than bank-specific and
   would need their own differential proof before moving: the `@`/`%` rate
   exclusion (F6) and the leading-zero reference-number rule (F7).
2. **The printed-balance sign solver looks reusable and is deliberately not
   moved.** `_solve_from_printed_balances` answers "which column was this
   amount printed in" for ANY two-column-plus-balance layout — td_canada_native
   prints the same shape. It lives in `analysis/rbc.py` because promoting it is
   a shared-utility change (stop condition 1).
3. **F11 needs geometry (stop condition 4, reported not acted on).** Six
   documents' text layers emit cells out of grid order. Evidence: balances open
   physical lines, amounts are printed between the description lines of a
   different row, and some cells are missing from the text stream entirely —
   one document's stated 129 rows yield at most 118 recoverable cells. No
   text-layer rule can reorder what the text layer has already reordered. The
   input needed is the PDF word boxes W3-3c already produces for the structurer.
   **Architecture decision, not taken here.**
4. **`stated_credit_count` / `stated_debit_count` are extracted but never
   checked by the platform.** W3-2 §2 recorded that there is no platform-level
   count check. This cell is the strongest argument for one: 6 of the 89
   already-validated rbc documents had a *wrong* per-direction count while
   passing every existing check, and the printed count is exactly what caught
   it. Adding the check is a protected-module change (`analysis/pipeline.py` or
   `analysis/reconcile.py`) and is out of this cell's scope.
5. **`ANALYSIS_STAGE_VERSION` must be bumped at merge.** This change alters
   analysis output for unchanged settings on 72 of 153 rbc documents. The bump
   is Ocean's at merge; `webapp/` was not touched.
