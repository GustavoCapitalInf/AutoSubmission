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

# §TD — Cell 2: `td_canada_native x detail_coverage`, 61 documents

REEF-TD, 2026-08-07. Branch `wave3-td-completeness`, base `d775bbe`.
Same mandate and idiom as §1: layout families, capability-level fixes, fail
closed rather than fabricate. Ocean reviews and merges; nothing here was
merged, pushed, or re-baselined by this agent.

## T0. Summary

| | |
|---|---|
| Cell worked | `td_canada_native x detail_coverage` — **61 records, 61 distinct content hashes**, all digital, all native-text |
| Layout families characterised | 6 — four fixed, two pinned as already correct |
| Result over the cell | **51 / 61 validated** (from 0 / 61); **10 fail closed by design** |
| Movement outside the cell | `td_canada_native x ledger_identity` (5 documents, same parser, same root cause): **0 → 5 validated**. The 7 already-validated `td_canada_native` documents: **unchanged**. No other parser touched |
| Truth-set movement | **none.** `python corpus_gate.py` **GREEN**, 106 PASS / 3 WITHHELD, no ceremony requested or performed |
| Pinned corpus TD Canada documents | 6, all **field-identical** before and after (637 rows, every field, verified directly as well as through the gate) |
| Statement-specific constants | one **removed** (`0 CHQS ENCLOSED` — the enclosed-cheque count is statement data); none added |
| Protected modules touched | none |
| Files changed | `analysis/td_can.py`, `tests/test_td_can_native_variants.py` (new), this log |
| Cache implication | analysis output changes for unchanged settings → `ANALYSIS_STAGE_VERSION` must be bumped at merge. **Ocean's, not done here** (`webapp/` is protected for this agent) |

## T1. The cell reproduced independently

Joining the frozen baseline run `c3e557f0`'s telemetry diagnostics to its
`rows.csv` parser attribution reproduces Ocean's table exactly — 334 withheld
records, top cell `td_canada_native x detail_coverage` = **61**, 61 distinct
content hashes, no duplicates inside the cell. The failing checks are uniform
and match §4's reconnaissance line for line:

| Evidence | Documents |
|---|---|
| `adb:final_balance_matches_statement_closing` | 61 / 61 |
| `adb:ledger_reconciles_to_closing` | 61 / 61 |
| `integrity:ledger_sum_mismatch`, `recon:sum_check_failed` | 61 / 61 |
| `integrity:debit_detail_coverage_mismatch`, `recon:debit_coverage_short` | 61 / 61 |
| `integrity:credit_detail_coverage_mismatch`, `recon:credit_coverage_short` | 59 |
| `running_balance_breaks`, `posting_dates_cover_source` | **0** |

Every document resolves through the native `DESCRIPTION CHEQUE/DEBIT
DEPOSIT/CREDIT DATE BALANCE` path; none carries a `<table>` fragment, so the
HTML-table half of `td_can.py` is not exercised by this cell at all.

## T2. The measurement instrument, and what it found before any code changed

TD prints two independent self-checks on every page: a per-page summary block
(`Credits <count> <total>`, `Debits <count> <total>`) and a running **BALANCE**
on the last row of each date group. Both are the document's own evidence, so
completeness is checkable with no expectation file and no audited truth set.

Baseline over the 61, before any change:

| Instrument | Result |
|---|---|
| extracted row count == the bank's stated credit + debit counts | **61 / 61 exact** |
| extracted credit total == stated credit total | 0 / 61 (57 short, 4 over) |
| extracted debit total == stated debit total | 0 / 61 (57 over, 4 short) |
| credit shortfall + debit excess | **equal and opposite on every document** |

**That is the finding that scopes the whole cell, and it is not Chase's.** No
row is missing: every row, every amount and every date is already read. The
credit and debit totals are wrong by exactly the same amount in opposite
directions, which is the signature of rows landing on the wrong side of the
ledger — a *direction* defect, not the coverage loss the diagnostic class name
suggests. The class is still accurate (the detail does not cover the stated
totals); its cause is one level down.

## T3. Why the direction is lost, and where it still is

The printed grid is five columns:

    DESCRIPTION        CHEQUE/DEBIT   DEPOSIT/CREDIT   DATE    BALANCE

The native text layer (`ocr/native_text.py::_native_pages`, protected) reads
each printed row as one PyMuPDF block and joins its spans with single spaces,
so the row reaches the parser as `<description> <amount> <DATE> [<balance>]`.
The amount survives; **which of the two adjacent money columns it was printed
in does not.** `td_can.py` therefore decided direction from the description's
trailing TD transaction code (`MSP`/`CLN`/`PAY`/`GST` credit, `BUS` debit,
`TFR-FR`/`TFR-TO`/`SEND E-TFR`/`E-TRANSFER`). That is a reading of what a row
*means*; the grid encodes which column it *is*, and the two disagree often.

The bank prints the answer anyway. Between two printed balances the signed
amounts must equal the difference the bank printed, so the lost column is
recoverable arithmetic over the printed grid: with `S` the sum of a group's
amounts and `delta` the printed change, the deposit rows sum to
`(delta + S) / 2`. Over the cell:

| | |
|---|---|
| balance-checkpoint groups | **1,134** |
| groups with exactly one split reproducing the printed balance | **1,110 (97.9%)** |
| groups admitting more than one split | **24** |
| groups admitting **no** split | **0** |
| groups hitting the solver's row or state bound | **0** |

Zero unsatisfiable groups is the independent confirmation of T2: the rows,
amounts and balances being read are complete and correct on all 61 documents.

The solved direction is checked by evidence the solver never reads — the bank's
own stated credit and debit totals — so reconciliation stays a real gate rather
than a restatement of the input. That is exactly what it does below: it rejects
10 documents.

## T4. The families

Named by structure. Nothing below names a customer, a bank product, an amount
or a date; every rule is anchored on the printed grid.

| # | Family | Structural signature | Root cause | Ruling | Fixture |
|---|---|---|---|---|---|
| T-F1 | two-money-column row | one money token per row, printed under either CHEQUE/DEBIT or DEPOSIT/CREDIT; the flattened text keeps neither the gap nor the column | direction was read from the description's trailing transaction code instead of from the column the bank printed the amount in | FIX — direction is the split of the group's amounts that reproduces the balance the bank printed at the end of it | `TestF1TwoMoneyColumnRow` (5 cases incl. identical rows whose direction flips with the printed balance alone) |
| T-F2 | page-carried balance | a page break lands inside a date group; the next page reprints `BALANCE FORWARD <DATE> <balance>` | only the *first* `BALANCE FORWARD` was read (as the opening balance); the carried balance — a printed checkpoint like any other — was discarded, leaving the split group to merge across the break and lose determinacy | FIX — every printed balance closes a group, including a carried one | `test_f2_*` |
| T-F3 | cheque-enclosure terminator | the ledger ends at `<n> CHQS ENCLOSED …`, where `n` is the number of cheques enclosed | the terminator was matched as the literal `0 CHQS ENCLOSED`, a memorized statement value of exactly the class R-1 purged. **20 of the 61 documents enclose cheques**, so on those the ledger never closed and the scan ran on through the summary block into the next page's letterhead | FIX — the marker is `<digits> CHQS ENCLOSED`; the count is data | `test_f3_*` (parametrised over four counts, with a row-shaped probe line below the terminator) |
| T-F4 | underdetermined date group | inside one group the printed balance delta admits more than one split of the printed amounts — characteristically a round amount against the same amount split into a transfer and its fee | none; the printed evidence genuinely does not say | **FAIL CLOSED BY DESIGN.** The rows are still emitted with the transaction-code reading, and the bank's independent stated totals reject the document when that reading is wrong. **24 groups in 18 documents; 8 of those documents still validate because the fallback agrees with the summary, 10 stay withheld** | `test_f4_*` |
| T-F5 | converted-amount row | a foreign-currency row prints its original amount inside the description and the converted amount in the money column (`… $ 8.00 11.00 FEB01`) | none — the existing right-to-left scan already takes the cell adjacent to the DATE column | NO CHANGE; pinned so the new grouping cannot regress it. 3 rows in 2 documents | `test_f5_*` |
| T-F6 | overdraft-suffixed balance | a printed balance carries the `OD` suffix (`371.96OD`) | none — `parse_money` reads the trailing `D` as a debit marker | NO CHANGE; pinned, because the whole solver depends on the carried balance's sign. **34 of 61 documents run overdrawn** | `test_f6_*` |

Negative fixtures (each constrains a new rule rather than demonstrating a
defect):

- two rows with **identical descriptions and amounts** produce opposite
  directions when only the printed closing balance differs — the rule cannot be
  keyed on wording;
- a printed credit code (`MSP`) loses to the printed balance;
- a description containing `CHQS` mid-ledger does not terminate the ledger;
- the first `BALANCE FORWARD` is the opening balance, not a carry;
- rows with no printed balance anywhere keep the transaction-code reading;
- the solver returns "undetermined", never a guess, for a parity mismatch, an
  out-of-range delta, multiple splits, an empty group, and an over-long group.

### T4.1 What did NOT change, deliberately

- **The HTML-table path** (`parse_td_canada_statement`'s table branch) is
  untouched. Zero of the 3,506 archive documents reach it, so changing it would
  be unevidenced — the same ruling §1.4 made for Chase's table path.
- **Shared utilities** (`tables.py`, `money.py`, `date_tokens.py`) — untouched;
  no behaviour of theirs changed, so no differential-equivalence proof is owed.
- **`running_balance` stays `None`** on native rows, as before. TD prints
  balances at group endings, not a full daily series; the existing suppression
  ruling in this file stands, and reading them as a daily-balance oracle is the
  carried finding §3.3 already queues, not this cell's work.
- **TD's transaction codes were not extended.** `CANCEL E-TFR`, for one, would
  settle a document by itself — and it is a TD verb, not a counterparty — but
  each such addition is content-keyed, fits observed data, and would erode the
  one independent check that catches the residual. The arithmetic decides;
  where it cannot, the platform withholds.
- **The page-carry rule (T-F2) fires on 0 of the 73 archive TD documents** —
  no page break in the archive falls inside a date group. It is kept because
  the segmentation rule is "a printed balance closes a group", and a carried
  balance is a printed balance; the alternative is an arbitrary exception. It
  is pinned by a synthetic fixture rather than by measured volume, and that is
  recorded here rather than glossed.
- **The terminator fix (T-F3) changes no measured output** on those same 73
  documents: nothing printed below a stuck terminator happens to parse as a
  ledger row today. It is a memorized-constant removal and a fail-open
  hardening, not a coverage change, and is reported as such.

## T5. Result over the cell

`analyze_markdown` in deterministic mode over locally rendered markdown
(`ocr.pipeline.parse_statement`, native rung, no OCR, no model calls, `$0.00`),
classified with `telemetry.record.classify_outcome` and diagnosed with
`telemetry.diagnostics.diagnose` — the same ladder discovery uses.

| Instrument | before | after |
|---|---|---|
| row count == stated counts | 61 / 61 | 61 / 61 |
| credit total == stated credit total | 0 / 61 | **51 / 61** |
| debit total == stated debit total | 0 / 61 | **51 / 61** |
| documents fully determined by the printed balances | — | 43 |
| documents with ≥1 underdetermined group | — | 18 (8 validate, 10 withheld) |

| Cell | documents | before | after |
|---|---|---|---|
| `td_canada_native x detail_coverage` | 61 | 0 validated / 61 withheld | **51 validated / 10 withheld** |
| `td_canada_native x ledger_identity` (adjacent, outside the assigned cell) | 5 | 0 / 5 | **5 validated / 0 withheld** |
| `td_canada_native`, already validated | 7 | 7 validated | **7 validated (unchanged)** |

**51 of 61, and nothing was padded to get there.** Every document that now
validates does so because the rows extracted reproduce, independently: the
bank's printed running balance at the end of every date group, the bank's
stated credit and debit totals *and* counts, the ledger identity, and the full
ADB validation suite. The fail-closed gate is unchanged; the documents pass it
on their own arithmetic.

**The 10 that remain withheld are the honest residual.** Each contains at least
one date group where the bank's printed balance admits more than one split of
its printed amounts, the transaction-code fallback picked wrong, and the
summary block caught it. Their diagnostics are accurate: 6 `detail_coverage`,
4 `ledger_identity`, with the credit shortfall and debit excess equal and
opposite — the residue of direction, not of missing rows.

## T7. Proofs

All four run in this worktree against `6c6c5c7` — the last commit that touches
code or tests — on a clean tree (`git status --short` empty), `set -o pipefail`,
exit codes as printed. `845df94` adds this section and nothing else.

```
$ python -m pytest -q
2064 passed, 18 deselected, 1 warning in 167.47s (0:02:47)
SUITE_EXIT=0

$ python -m pytest -m corpus -q
14 passed, 2068 deselected, 1 warning in 1082.61s (0:18:02)
CORPUS_MARKED_EXIT=0

$ python corpus_gate.py
Coverage: 109 pinned PDFs (103 native text, 6 committed OCR), 0 exclusions
Ignored:  0 non-corpus PDFs under the corpus root
Outcomes: 106 PASS / 3 WITHHELD
Runtime:  453.9s
RESULT: GREEN
GATE_EXIT=0

$ python -m pytest tests/test_no_statement_hardcodes.py tests/test_r1_hardcodes.py \
      tests/test_no_parser_helper_clones.py -q
100 passed in 0.80s
GUARDS_EXIT=0
```

Baseline for comparison, same worktree at base `0c13c21` before any change:
`2036 passed, 18 deselected`; gate `RESULT: GREEN`, `106 PASS / 3 WITHHELD`.
The suite grew by the 28 new fixtures and by nothing else; no existing
assertion was edited.

**Fails-before / passes-after.** Each committed fixture run through the
pre-change parser (loaded from git) and the current one in the same process:

```
FIXED  F1 balance rose -> the uncoded row is the deposit         before=[-40.0, -10.0]  after=[40.0, -10.0]
kept   F1 same rows, balance fell -> both withdrawals            before=[-40.0, -10.0]  after=[-40.0, -10.0]
FIXED  F1 printed balance outranks a credit transaction code     before=[40.0, -10.0]   after=[-40.0, -10.0]
FIXED  F1 a group spans several printed dates                    before=[-40.0, -25.0, -10.0]  after=[40.0, 25.0, -10.0]
FIXED  F2 page carry closes the split group                      before=[-10.0, -20.0, -30.0]  after=[10.0, 20.0, -30.0]
kept   F3 zero cheque count (the old literal) closes the ledger  before=[40.0]          after=[40.0]
FIXED  F3 non-zero cheque count also closes the ledger           before=[40.0, -5.0]    after=[40.0]
kept   F5 converted amount next to the DATE column               before=[-11.0]         after=[-11.0]
FIXED  F6 overdraft-suffixed opening balance is negative         before=[-50.0]         after=[50.0]
```

The two `kept` F1/F3 lines are the contrast halves of their pairs, not weak
tests: F1's pair is the same text with a different printed balance, and only
the pair proves the rule fires on the grid rather than on wording. F5 is
pinned-as-correct by ruling.

**Byte-identity on the pinned corpus**, checked directly as well as through the
gate — old and new module loaded side by side, same markdown, every field of
the serialised statement compared:

```
IDENTICAL  TD Can/Dec_31-Jan_30_2026 (6).pdf  (115 rows)
IDENTICAL  TD Can/Feb_27-Mar_31_2026 (2).pdf  (126 rows)
IDENTICAL  TD Can/Jan_30-Feb_27_2026 (3).pdf  (105 rows)
IDENTICAL  TD Can/Mar_31-Apr_30_2026.pdf      (123 rows)
IDENTICAL  TD Can/Nov_28-Dec_31_2025 (7).pdf  (110 rows)
IDENTICAL  TD Can/TD Bank Bank Statement.pdf   (58 rows)
claimed by the TD Canada parser: 6; differing: 0
```

That the balance arithmetic independently reproduces the audited signs on all
637 pinned rows is a cross-check on the solver, not only a regression result.

**Cell outcome at `6c6c5c7`**, via `analyze_markdown` + `classify_outcome` +
`diagnose`:

```
outcomes:      {'validated': 51, 'withheld': 10}
primary_class: {None: 51, 'detail_coverage': 6, 'ledger_identity': 4}
row count == stated counts: 61 / 61   (unchanged from baseline)
credit total == stated:     51 / 61   (baseline 0 / 61)
debit total == stated:      51 / 61   (baseline 0 / 61)
```

**Commits (oldest first)**

| Commit | Contents |
|---|---|
| `443440e` | `analysis/td_can.py` + `tests/test_td_can_native_variants.py` |
| `6c6c5c7` | this log's §TD.T0–T6 |
| `845df94` | this proofs section (§TD.T7) |

## T6. Carried findings and questions for Ocean

1. **The column identity is in the PDF; the extractor discards it.** Read-only
   word geometry on a cell document places every ledger amount squarely inside
   one of the two printed money columns (`CHEQUE/DEBIT` band `x∈[212,284]`,
   `DEPOSIT/CREDIT` band `x∈[309,389]` on that page). On the very group that
   defeats the balance arithmetic, the geometry is unambiguous: twelve amounts
   at `x0≈250/274` are debit-column, one at `x0≈352` is credit-column — exactly
   the split the arithmetic left as one of two candidates and the code fallback
   got wrong. `ocr/native_text.py` already recovers geometry this way for two
   other banks (`parse_native_wells_fargo`, `_navy_transaction_rows`), so a
   geometry-preserving TD native extractor is precedented in that same file and
   would close **all 24** underdetermined groups. `ocr/` is protected for this
   agent: **raised, not attempted.** Recommended as the next TD card. The
   balance solver should stay either way — it is what makes the result
   self-checking, and it is the only path that survives an OCR'd TD statement,
   where geometry is unavailable.
2. **Row-grouper promotion (§3.4).** This cell does not need Chase's grouper and
   does not argue for or against promoting it: TD's rows arrive one per line,
   already segmented. What TD *does* contribute to that decision is a second
   witness that "the amount is the right-aligned cell" is underdetermined —
   here because two money columns collapse into one token, in RBC because a
   balance column follows the amount. Recorded; the decision stays Ocean's.
3. **`ANALYSIS_STAGE_VERSION` must be bumped at merge** (`webapp/` protected
   here), as for Cell 1.
4. **Movement outside the assigned cell.** The 5 `td_canada_native x
   ledger_identity` documents move withheld → validated. Same parser, same root
   cause, no separate work; flagged because Ocean's archive-wide measurement
   will show **+56** TD documents, not +51.
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

---

# §GROUPER — the row grouper promoted to `analysis/tables.py`

REEF-GROUPER, 2026-08-08. Branch `wave3-grouper-promotion`, base `8ce6abc`.
Brief: `docs/agent-handoffs/REEF-GROUPER.md` (Ocean ruling 2 of 2026-08-08,
executing carried finding §3 item 4 now that both remaining cells are
characterised). **Pure refactor under the R-2 differential-equivalence
standard: no capability changed, no document's output moved.**

## G0. Summary

| | |
|---|---|
| Primitive | `analysis/tables.py::group_rows(items, *, starts_row, ends_row=None)` |
| Consumers | `chase.py` (2 call sites), `td_can.py` (1), `rbc.py` (1, serving both the English and French layouts) |
| Behaviour change | **none.** Differential oracles per parser + 457 archive documents byte-identical + corpus gate GREEN |
| Statement-specific constants | none added, none removed |
| Protected modules touched | none. `money.py`, `date_tokens.py`, every other parser, pipeline/registry, `ocr/`, `webapp/`, `discovery/`, `telemetry/`, corpus assets and audit CSVs all unmodified |
| Sign/direction solvers | untouched, as ruled — `td_can._credit_counts_from_balances` / `_resolve_native_directions` and `rbc._column_split_signs` / `_subset_signs` / `_solve_from_printed_balances` stay parser-local |
| `ANALYSIS_STAGE_VERSION` | **no bump owed** — output is byte-identical on every document measured (§G5) |
| Files changed | `analysis/tables.py`, `analysis/chase.py`, `analysis/td_can.py`, `analysis/rbc.py`, `tests/test_row_grouping.py` (new), this log |

## G1. What was promoted, and what deliberately was not

Ocean's approved rule set had three rules. **Two of them are one rule in three
parsers and moved; the third is three different rules and stayed.**

| Rule | Status | Why |
|---|---|---|
| 1. a row starts where the printed grid starts one | **PROMOTED** — `starts_row` | The same control flow in all three parsers. Only the *predicate* differs, and it is bank knowledge: Chase's leading `MM/DD`, RBC's leading `DD Mon`, TD Canada's `MonDD` **inside** the line, Chase's CHECK NO. column. It is passed in, exactly as `tables.py` already passes headings and "continued" spellings |
| 2. wrapped lines continue the row | **PROMOTED** — the `elif current is not None` arm | Same code in Chase and RBC. It is a no-op on TD Canada, whose native text layer emits each printed row as one physical line; that is stated at TD's call site rather than hidden |
| 3. a lone money cell is an amount; adjacent money cells are (amount, balance) in printed column order | **NOT promoted — reported instead** | §G2 |

A terminator predicate (`ends_row`) is part of the primitive because Chase
needs one — the printed section total and the headings that follow a section
inside the same block end a row without starting another. TD Canada and RBC
close their sections in the caller and pass nothing.

## G2. Why rule 3 did not move (finding for Ocean)

§5.7 item 1 identified that Chase's "the amount is the right-aligned cell" is
underdetermined where a balance column is printed, and proposed the adjacency
form as the promotable one. Working all three implementations together shows
the adjacency form is **also** not one rule:

| Layout | Printed columns | How the amount is found | Would the adjacency rule reproduce it? |
|---|---|---|---|
| Chase native | `DATE / DESCRIPTION / AMOUNT` — no balance column | preference order over candidates: a wrapped amount cell alone on its line, else the token terminating a line, else any money token | no — F6's cash-back row prints money **inside** the description, so "the first money cell is the amount" reads the description's figure |
| RBC | `... / Cheques & Debits / Deposits & Credits / Balance` | a state machine over the section's cells: a row ends at its amount cell, and the next cell is that row's balance if nothing stands between them — and it spans physical lines (F5's centred cell) | this IS the rule |
| TD Canada native | `DESCRIPTION / CHEQUE-DEBIT / DEPOSIT-CREDIT / DATE / BALANCE` | the money cell adjacent to the **DATE column**, scanning leftward; the balance is the cell on the date's other side | no — the amount and its balance are not adjacent (the Date column stands between them), and T-F5's converted-amount row prints a second money cell earlier in the description |

So a shared rule-3 function would need an anchor-selection strategy and a
separator, per parser — a three-way switch with no shared body, which is the
opposite of what R-2's shared utilities are for. Both wrong readings above are
already pinned as fixtures in the existing family suites, so this is measured,
not argued. **Rule 3 stays parser-local and is documented as such in
`group_rows`'s docstring. Ocean may rule otherwise; nothing here forecloses
it.** The two adjacent candidates §5.7 named — the at-rate / percentage
operand exclusion and the leading-zero reference-number rule — were likewise
not moved: they are money-token grammar, not row grouping, and belong to a
`money.py` question with its own differential burden.

## G3. The refactor, per parser

- **`chase.py`** — `_native_rows` becomes the primitive applied to Chase's own
  two predicates. `_check_rows` splits into `_check_pieces` (the CHECKS PAID
  counterpart of `_physical_lines`: furniture stripped, multi-check lines
  broken at the amount/number seam) and the same primitive over the CHECK NO.
  column. The legacy check loop tested the terminator **before** the row start
  and the primitive tests the row start first; the two orders can differ only
  on a line both predicates match, and both row-start rules are anchored on a
  leading digit while every terminator alternative is anchored on a letter.
  That is asserted structurally and over the whole adversarial matrix
  (`test_the_chase_row_predicates_cannot_both_match_one_line`).
- **`td_can.py`** — `_parse_native_td_canada` was one pass that interleaved
  statement-field extraction with row reading. It is now two: the first pass
  is unchanged and additionally collects the printed ledger lines **with the
  statement year in force where each was printed** (TD can print the period
  line after part of the ledger, and the old guard dropped ledger lines seen
  before it — that behaviour is preserved exactly by carrying the year per
  line rather than reading it once at the end). `_native_date_index` names the
  row-start rule. Rule 2 never fires here, and the call site says so.
- **`rbc.py`** — `_read_grid_rows` keeps its cell machine verbatim; what
  changed is that the "a new posting date closes whatever was pending" reset
  is now the group boundary the primitive computes. Its `starts_row` is "a
  printed posting date, or the table's own opening-balance row", the latter
  because that row prints no date and still opens the table. One asymmetry is
  explicit: the primitive drops items printed above the first row start
  (Chase's section furniture), and RBC has none to drop, so the entries above
  its first row start are restored as the leading group. Without that, the
  French layout's opening-balance row would have stopped supplying the balance
  chain's first anchor — a real divergence, caught by
  `test_rbc_grid_reader_matches_the_oracle_on_raw_entry_streams` before it
  could reach a document.

## G4. The differential proof

`tests/test_row_grouping.py`, in the R-2 idiom (`test_shared_parser_utils.py`):
each parser's pre-promotion implementation is reproduced **verbatim** as a
frozen oracle, spliced back into the live parser, and the two readings of the
same input are asserted identical.

| Oracle | Compared over | Result |
|---|---|---|
| `chase._native_rows` | 728 adversarial line streams: 26 printed line shapes drawn from families F1–F12 and their negatives, alone and in every ordered pair, the whole matrix forwards and reversed, plus every real stream `_physical_lines` produces from the 19 family documents across all 7 section headings | identical on 728 / 728 |
| `chase._check_rows` | every CHECKS PAID block in the matrix plus 6 hand-built ones (F7 short / long / dual-dated, F8 described check, F9 multi-check line, the page-barcode negative, an empty block, a totals-only block) | identical |
| `chase.parse_chase_statement` | 19 whole family documents (F1–F12, the 5 parametrised F2 prefixes, 3 rebuilt negatives), full `Statement` JSON | identical |
| `rbc.parse_rbc_statement` | 26 whole documents — F1 dual money cell, F3 compressed line, F4 wrapped row, F5 centred cell, F6 rate operands (all three printed forms), F7 reference number, F8 closing-balance cell, F9 repeated date, the page-footer and third-adjacent-cell negatives, 4 French documents, and 4 documents built specifically to exercise the row boundary itself | identical |
| `rbc._read_grid_rows` | 8 raw entry streams including ones the callers cannot currently produce (a stream opening with an entry that belongs to no posting date) | identical |
| `td_can._parse_native_td_canada` | 35 whole documents — T-F1 (5 shapes incl. identical rows whose direction flips with the printed balance alone), T-F2 page carry, T-F3 over four enclosed-cheque counts with a row-shaped probe below the terminator, T-F4 underdetermined group, T-F5 converted amount, T-F6 overdraft suffix, a mid-ledger CHQS description, a dateless continuation line, a ledger with no printed period — each with and without a stated summary, and each again with a carried `base` statement | identical |

**The proof is not vacuous, and that is asserted two ways.**
`test_the_frozen_oracles_are_not_silently_passing_on_nothing` requires each
matrix to contain at least 15 documents that really parse. And each oracle was
run against a deliberately *wrong* implementation as a negative control before
the real refactor: a grouper that keeps leading orphans differs on **567 of
728** Chase streams; an RBC reader with the posting-date reset removed differs
on 2 of 26 documents and 2 of 8 entry streams; the orphan-dropping RBC variant
— the exact mistake §G3 describes — differs on 1 of 8 entry streams; a TD
reader that folds continuation lines into the row differs on **28 of 35**
documents. The harness detects the mistakes it exists to detect.

## G5. Proofs

| | |
|---|---|
| default suite | **2,241 passed**, 18 deselected, exit 0 (2,093 before; the 148 added are this module) |
| family suites unchanged and green | `test_chase_native_variants.py`, `test_td_can_native_variants.py`, `test_rbc_variants.py` — not one fixture edited |
| R-2 / R-1 guards | green inside the default suite: no cloned bodies in `analysis/`, no new private cross-module import, shared utilities still import no parser |
| corpus-marked | `set -o pipefail; python -m pytest -m corpus -q` — **14 passed**, 2,245 deselected, exit 0 |
| corpus gate | `python corpus_gate.py` — **RESULT: GREEN**, exit 0, 106 PASS / 3 WITHHELD, the same three by name |
| archive spot-verification | 457 archive documents rendered once through the production native rung and analysed under both revisions: chase 171 + chase_export 3 + relay 4, rbc 160 + rbc_french 1, td_canada_native 86, td_us 32 — **0 payload hashes moved** |

The archive verification is read-only: the PDFs are read, the rendered markdown
is cached in local scratch and never committed, and only aggregate counts are
reported here.
# §BOFA — Cell 4: `bank_of_america × {detail_coverage, ledger_identity, posting_date_coverage}`, 70 documents

REEF-BOFA, 2026-08-08. Branch `wave3-bofa-completeness`, base `e614fcc`
(worktree tip `8ce6abc`, which adds only the two handoff files). Brief:
`docs/agent-handoffs/REEF-BOFA.md`.

Same method and idiom as §1/§TD/§5: reproduce the cell independently, build the
in-document instrument BEFORE changing code, characterise layout families
structurally, fix at the capability level or fail closed with the volume
stated, prove both directions with synthetic fixtures, measure honestly.

## B0. Summary

| | |
|---|---|
| Cell worked | `bank_of_america × detail_coverage` (30), `× ledger_identity` (25), `× posting_date_coverage` (15) — **70 records, 70 distinct content hashes**, the whole `bank_of_america` withheld population |
| Result over the cell | **70 / 70 validated**, from 0 / 70. No residual |
| Already-validated `bank_of_america` documents (291 records / 289 hashes) | **289 / 289 still validate** — zero regressions, and 5 corrected (§B6) |
| Layout families characterised | 8, all closed at the capability level |
| Statement-specific constants added | **none**; one wording-keyed rule **removed** (a description beginning "Total" was discarded) |
| Protected modules touched | none. `analysis/tables.py`, `money.py`, `date_tokens.py` and every other parser are unmodified; `parse_money`, `iso_or_none`, `table_rows`, `tables_after` are consumed exactly as they were |
| Truth-set movement | **none.** All 8 pinned corpus BofA statements are financially identical field for field; `corpus_gate.py` GREEN, 106 PASS / 3 WITHHELD, same three by name. **No re-baseline requested or performed** |
| Files changed | `analysis/bofa.py`, `tests/test_bofa_variants.py` (new, 24 fixtures), this log |
| Cache implication | analysis output changes for unchanged settings → `ANALYSIS_STAGE_VERSION` must be bumped at merge. **Ocean's, not done here** (`webapp/` is protected for this agent) |

## B1. The cell reproduced independently

Joining the frozen baseline run `7a98b6cd`'s telemetry diagnostics to its
`rows.csv` parser attribution by content hash reproduces Ocean's table exactly:
`parser_id == "bank_of_america"` gives **361 records — 291 validated, 70
withheld** — and the withheld split by primary class is **`detail_coverage`
30 · `ledger_identity` 25 · `posting_date_coverage` 15**. 70 records, 70
distinct hashes, no duplicates inside the cell. Every one is in the
`Bank of America/` folder; 69 resolve through the native rung, 1 through local
Tesseract.

The failing checks are uniform, and the shape of the failure is the finding:

| Evidence | Documents |
|---|---|
| `adb:final_balance_matches_statement_closing`, `adb:ledger_reconciles_to_closing` | 70 / 70 |
| `integrity:ledger_sum_mismatch`, `recon:sum_check_failed` | 70 / 70 |
| `integrity:transaction_detail_not_corporate_reliable` | 55 |
| `integrity:credit_detail_coverage_mismatch` | 18 |
| `integrity:debit_detail_coverage_mismatch` | 12 |
| `adb:posting_dates_cover_source` | 16 |

Only 30 of the 70 carry a coverage flag at all, yet all 70 fail the ledger
identity — so "detail_coverage" names a third of the cell and the class labels
are, as in §TD and §5, one level above the cause.

## B2. The measurement instrument (used before any code changed)

BofA is unusually generous with self-checks, and all of them are printed on the
document:

* an **account summary** giving beginning balance, one credit total, one to
  three outflow totals, checks, service fees and ending balance;
* a **printed total per detail section** (`Total deposits and other credits`,
  `Total withdrawals and other debits`, `Total checks` + `Total # of checks`,
  `Total service fees`, and the consumer layout's own three);
* on most business statements, a full **`Daily ledger balances`** series —
  every day of the period with its end-of-day balance. **No part of the parser
  reads it**, which makes it an independent oracle of exactly the kind §2 used
  to settle the Chase posting-date question.

The instrument's own trustworthiness is checked first: the printed account
summary closes arithmetically (beginning + credits − outflows − checks − fees =
ending) on **70 / 70** cell documents, so a document that fails it is failing
the bank's own figures rather than ours.

Baseline over the 70, before any change:

| Instrument | Result |
|---|---|
| printed account summary closes | 70 / 70 |
| every printed **section** total reproduced | **0 / 70** |
| — `Total deposits and other credits` reproduced | 26 / 55 |
| — `Total withdrawals and other debits` reproduced | 49 / 55 |
| — `Total checks` reproduced | 7 / 28 |
| — `Total service fees` reproduced | 62 / 62 |
| — the consumer layout's three section totals | 0 / 15, 0 / 14, 0 / 15 |
| stated credit total reproduced | 26 / 70 |
| stated debit total reproduced | 28 / 70 |
| ledger identity holds | **0 / 70** |
| printed `Daily ledger balances` series reproduced exactly | **0 / 55** |

Every deviation is in the same direction — **captured < printed**, never above.
The platform was losing rows and never inventing them, which is why the cell
landed on coverage and reconciliation classes rather than on a contradiction.

## B3. The two things that were wrong

**(1) The grid was flattened before it was read.** BofA's detail sections are a
`Date Description Amount` grid: the Amount column is right-aligned and printed
last, and a row begins at a physical line headed by the MM/DD/YY posting date.
The reader collapsed each section to one string (`\s+` → `" "`) and then
re-segmented it at *every* date-shaped token. Two printed forms defeat that
immediately, and between them they account for every deposit-side loss in the
cell:

* a wire prints its own reference date inside the description —
  `… PMT DET:BOH OF 26/01/03 /CATPURP/CTRC` — in `YY/MM/DD` order, so the split
  produced one fragment with no amount and one whose leading token is not a
  calendar date (this is the same token class that crashed 16 documents in
  W3-1, now fixed but still costing the row);
* an adjustment row prints one — `Temporary Credit Adjustment on 01/28/26 14.70`
  — so the row was split into a fragment with no amount and a fragment with no
  description, and both were discarded.

**(2) Two whole layouts had never been taught.** The consumer statement prints
a different section vocabulary (`Deposits and other additions`, `ATM and debit
card subtractions`, `Other subtractions`) and the parser knew only the business
one, so on those 15 documents it read nothing but the fee rows — which is
precisely why they diagnosed as `posting_date_coverage`: the only posting dates
the ledger had were fee days. A statement with a single cheque prints one
`Date Check # Amount` column group rather than two, and the check reader
demanded the doubled header.

## B4. The families

Named by structure. Nothing below names a customer, an amount, a date or an
account fragment; every rule is anchored on the printed grid.

| # | Family | Structural signature | Root cause | Ruling | Fixture | Volume |
|---|---|---|---|---|---|---|
| B-F1 | **description-embedded date** | a date-shaped token printed inside a row's description — a wire's `PMT DET:… 26/01/03 …`, an adjustment's `… on 01/28/26` | rows were segmented at any date-shaped token, so one printed row became two unusable fragments | FIX — a row begins at a physical line whose FIRST token is the posting date; a date anywhere else on the line is description text | `test_f1_*` | a row is lost on **31** cell documents and on 38 already-validated ones (5 of which lose the posting date rather than the row — §B6) |
| B-F2 | **wrapped amount cell** | the Amount column wraps onto a line of its own below a long description | flattening rejoined it, and the "last money token" rule then had to compete with money printed inside the description | FIX — a row ends at its amount cell: the money token that terminates a physical line | `test_f2_*` | present on **38** cell documents and 138 already-validated ones |
| B-F3 | **money printed inside the description** | `… PMT INFO: PRODUCT(S): 101.40 S&H: 9.62 MI TAX: 6.66` on the description line, the real Amount cell on the next | *(a hazard created by this restructuring, not a pre-existing defect — the naive form of B-F2's rule closes the row on the tax figure. Caught by the 289-document regression differential before commit, as RBC's F9/F10 were)* | FIX — a cell printed ALONE on its own line outranks a token that merely ends a description line: the same preference order Chase's F1/F6 pair settled | `test_f2_a_bare_amount_cell_outranks_*` | **2** documents, both already validated |
| B-F4 | **inline section total / card subtotal** | `… -263.62 Subtotal for card account # XXXX … -$263.62 Total withdrawals and other debits -$133,503.06` — all on the last row's physical line, which on a page break is also the heading line | the printed figures were read as the row's amount | FIX — the bank's own `Subtotal`/`Total <section>` labels end the row and the section wherever they are printed; a line is walked rather than classified once | `test_f3_*` | a subtotal is glued to a row's line on **39** cell documents, a section total on **52**, and on **1** the section total lands on the continued-heading line as well |
| B-F5 | **counterparty named "Total"** | `05/13/26 Total Quality Lo DES:PAYMENTS …`, `03/02/26 TOTALWINE 1147 …` | a row whose description began with "total" was discarded — a wording rule standing in for a structural one | FIX — the rule is deleted; a total line is recognised by not being date-headed | `test_f4_*` (parametrised) | **3** documents |
| B-F6 | **single-column `Checks` table, and a cheque with no printed number** | one `Date Check # Amount` header group instead of two; a row printed as `05/11/26 -300.00` | the reader required the doubled header and required a check number | FIX — check rows are `<date> [<number>[*]] <amount>`; the number is what the bank printed, and BofA does not always print one | `test_f5_*` | **19** single-column tables, **2** unnumbered cheques |
| B-F7 | **consumer section vocabulary** | `Deposits and other additions` / `ATM and debit card subtractions` / `Other subtractions`, under a `Withdrawals and other subtractions` umbrella, with no `# of` counts and no daily series | the layout was unknown, so only Checks and Service fees were read and the stated debit total was never assembled | FIX — the three sections join the printed-section table; the summary's debit total is the sum of every outflow line the summary prints | `test_f6_*` | **15 documents** — the whole `posting_date_coverage` class |
| B-F8 | **OCR-degraded column header** | local Tesseract renders `Date Description Amount` as `Date __Description 2.0.2.2 AMO` | the section opener required the exact three column words | FIX — a section is entered by the line its heading owns; the column header is furniture that is stripped when recognisable and skipped when not, because it is never date-headed | `test_f7_*` | 1 document (the cell's only scanned one) |

Negative fixtures — each constrains a new rule rather than demonstrating a
defect, and each is asserted:

- a date that really does start a line still starts a row, and an
  uncalendarable one (`26/13/24`) is dropped rather than guessed;
- a completed row is not extended by the next line, so a `Card account # XXXX …`
  sub-heading never joins a description and never becomes a row;
- the printed section total is never a row;
- the account summary's `Checks -7,500.00` line never opens the Checks section
  — a heading owns its line, a summary line is heading words plus an amount;
- the `Daily ledger balances` series is never read as activity;
- a page footer and the reprinted account header never join a row that is
  waiting for its amount cell.

### B4.1 What did NOT change, deliberately

- **The HTML-table path** (`_parse_section` / `_table_total`) is untouched.
  Zero of the 359 archive `bank_of_america` documents and zero of the 8 pinned
  ones carry a `<table>` fragment, so changing it would be unevidenced — the
  same ruling §1.4 made for Chase and §T4.1 for TD. Its historical behaviour of
  also reading Checks and Service fees through the native reader is preserved
  exactly (`_TABLE_PATH_EXTRAS`).
- **No shared utility was touched**, and no shared utility's behaviour changed,
  so no R-2 differential-equivalence proof is owed. Stop condition 1 never
  fired: everything this cell needed is a BofA layout fact.
- **The row grouper was not promoted and not imported.** §5.7's promotable form
  ("a lone money cell is an amount; adjacent money cells are (amount, balance)")
  is not what BofA needs — BofA prints no running-balance column, so its rows
  carry exactly one grid cell and the open question is *which line* the cell is
  on, not which of two it is. What BofA contributes to the promotion decision is
  §B7.1.
- **`running_balance` stays `None`.** BofA publishes a daily series, not a
  per-row balance; reading that series as a first-class oracle is carried
  finding §3.3, not this cell's work. It is used here as an outside check only.
- **The description vocabulary was not extended.** One wording-keyed rule was
  removed and none was added.

## B5. Result over the cell

Same production ladder discovery uses (`ocr.pipeline.parse_statement`, native
rung + the cached local-Tesseract read for the one scanned document, no visual
rung, no model calls, `$0.00`), then `analyze_markdown` in deterministic mode,
classified with `telemetry.record.classify_outcome` and diagnosed with
`telemetry.diagnostics.diagnose`.

| Instrument | before | after |
|---|---|---|
| every printed section total reproduced | 0 / 70 | **70 / 70** |
| stated credit total reproduced | 26 / 70 | **70 / 70** |
| stated debit total reproduced | 28 / 70 | **70 / 70** |
| ledger identity holds | 0 / 70 | **70 / 70** |
| printed `Daily ledger balances` series reproduced exactly, no day invented | 0 / 55 | **54 / 55** |

| Cell | records | documents | before | after |
|---|---|---|---|---|
| `bank_of_america × detail_coverage` | 30 | 30 | 0 validated / 30 withheld | **30 / 0** |
| `bank_of_america × ledger_identity` | 25 | 25 | 0 / 25 | **25 / 0** |
| `bank_of_america × posting_date_coverage` | 15 | 15 | 0 / 15 | **15 / 0** |
| **total** | **70** | **70** | **0 / 70** | **70 / 0** |

**Nothing was padded to get there.** Every document that now validates does so
because the rows extracted reproduce, independently: the bank's printed total
for every detail section, the bank's stated credit and debit totals, the ledger
identity, the printed daily-balance series where one exists, and the full ADB
validation suite. The fail-closed gate is unchanged; these documents pass it on
their own arithmetic.

The one document whose daily series is not reproduced is the cell's scanned
one: local OCR recovered a single line of its `Daily ledger balances` block, so
the oracle has nothing to compare against rather than disagreeing. It validates
on the printed section totals, the stated totals and the ledger identity.

## B6. The already-validated population — zero regressions, five corrections

The 291 already-validated `bank_of_america` records (289 distinct hashes) were
re-run through the same ladder, and the old and new modules were also loaded
side by side in one process over the identical markdown, comparing every field
of the serialised statement.

| | |
|---|---|
| still validated | **289 / 289** |
| every printed section total reproduced (after) | **289 / 289** |
| field-identical, including descriptions | 65 |
| identical except descriptions | 219 |
| **financially different** | **5** |
| printed daily series reproduced exactly | **280 → 285** (5 improved, **0 regressed**) |

**The five financial differences are one class, and the bank's own daily ledger
settles them.** Each is a single row of the form
`01/05/26 LEASEDIRECT … PMT INFO:INV# … DUE 01/01/26 REC# … -5,030.28`: the old
splitter cut at the printed *due* date, so the row was dated `01/01` — a day the
bank publishes no balance for — and its description became the fragment after
the cut. The new reader dates it by the DATE column. Before the change those
five documents reproduced 0 of their printed daily balances from the affected
day onward; after it, all five reproduce the bank's entire printed series
exactly and invent no activity day. This is the same condition `analysis/adb.py`
names in `posting_dates_cover_source`, caught here on documents that were
passing every existing check.

**Descriptions moved on 224 documents, all toward the printed text.** The
change is a single class: a `Card account # XXXX XXXX XXXX NNNN` sub-heading is
printed on its own line inside the withdrawals section, and flattening appended
it to the description of the row above. It is now recognised as the sub-heading
it is. No audited field is a description — neither audit CSV has a description
column — and all 8 pinned statements are financially identical, so no truth-set
movement arises. It is reported here rather than buried because downstream
transaction classification reads descriptions.

**Pinned corpus, checked directly as well as through the gate** — old and new
module loaded side by side, same markdown, every field of the serialised
statement compared:

```
BofA/Bofa 2026-02-27.pdf              financially identical (1 description)
BofA/BofA 2026-05-29.pdf              financially identical (1 description)
BofA/BofA Statement.pdf               financially identical (1 description)
BofA/BofA.pdf                         financially identical (1 description)
BofA/eStmt_2026-01-30 (3) (1).pdf     financially identical (1 description)
BofA/eStmt_2026-02-27 (3) (1).pdf     financially identical (1 description)
BofA/eStmt_2026-03-31 (3) (1).pdf     financially identical (1 description)
BofA/eStmt_2026-04-30 (1).pdf         financially identical (1 description)
claimed by the BofA parser: 8; financially differing: 0
```

## B7. Carried findings and questions for Ocean

1. **Row-grouper promotion (§3 item 4) — this cell's contribution.** BofA is the
   third witness and it splits the difference. Chase's first two rules carry
   over verbatim and are what closed this cell: *a row starts at a date-shaped
   FIRST token on a physical line* and *wrapped lines continue it*. The third
   rule needs BofA's refinement as well as RBC's: on a layout with no balance
   column the amount is still not simply "the last money token", because
   descriptions print money (`MI TAX: 6.66`) and the bank prints subtotals
   inline. The promotable form after three cells is: *the amount is the cell
   that terminates a physical line, a cell printed alone on its own line
   outranks one that merely ends a description line, and where a balance column
   exists adjacent cells are (amount, balance) in printed column order.* Two
   further pieces look layout-general: the "a printed `Total`/`Subtotal` label
   is furniture wherever it appears" rule (B-F4, RBC F8) and "a heading owns its
   line" (B-F5 negative, Chase F5). Each would need its own differential proof.
2. **`Daily ledger balances` as a first-class oracle (§3 item 3) — BofA is the
   strongest case yet.** BofA prints the full series on 55 of the 70 cell
   documents and on the large majority of the validated ones, and reading it
   would have caught the five §B6 defects automatically. It settled them here
   only because this cell went looking. Reading it into `stated_daily_balances`
   is a parser change; *checking* it is a protected-module change. Recommended
   as the next BofA card, and it is the same card §3.3 already queues for Chase.
3. **`stated_credit_count` / `stated_debit_count` are still extracted and never
   checked** (§5.7 item 4). BofA prints `# of deposits/credits` and
   `# of withdrawals/debits` on every business statement, so it is a second
   population where the check would be free. Out of this cell's scope.
4. **The consumer layout exists elsewhere in the archive.** All 15 consumer-form
   documents were inside this cell, and all 15 now validate; no already-claimed
   document uses that vocabulary. Worth re-checking after the next full run in
   case any consumer statement is currently unclaimed rather than withheld.
5. **`ANALYSIS_STAGE_VERSION` must be bumped at merge** (`webapp/` protected
   here). This change alters analysis output for unchanged settings on 294 of
   the 359 archive `bank_of_america` documents.

## B8. Proofs

All four run in this worktree against `1eeb123` — the tip after the last commit
that touches code or tests (`dc61540`) — on a clean tree (`git status --short`
empty), `set -o pipefail`, exit codes as printed.

```
$ git rev-parse --short HEAD
1eeb123
$ git status --short
(empty)

$ python -m pytest -q
2117 passed, 18 deselected, 1 warning in 144.93s (0:02:24)
SUITE_EXIT=0

$ python -m pytest -m corpus -q
14 passed, 2121 deselected, 1 warning in 1018.84s (0:16:58)
CORPUS_MARKED_EXIT=0

$ python corpus_gate.py
[PASS] oracle_independence: 4 audit modules import no production financial mathematics
Coverage: 109 pinned PDFs (103 native text, 6 committed OCR), 0 exclusions
Ignored:  0 non-corpus PDFs under the corpus root
Outcomes: 106 PASS / 3 WITHHELD
Runtime:  350.1s
RESULT: GREEN
GATE_EXIT=0

$ python -m pytest tests/test_no_statement_hardcodes.py tests/test_r1_hardcodes.py \
      tests/test_no_parser_helper_clones.py -q
100 passed in 0.80s
GUARDS_EXIT=0
```

The suite grew from **2,093** to **2,117** — the 24 new fixtures and nothing
else. `git diff e614fcc..HEAD --name-only -- tests/` lists exactly one file,
`tests/test_bofa_variants.py`, so **no existing assertion was edited**.

**Fails-before / passes-after.** Every committed fixture captured as the suite
runs and replayed through the pre-change module loaded from git, in the same
process:

```
FIXED  f1_a_wire_detail_date_does_not_open_a_row              before=None  after=[10300.0]
FIXED  f1_an_adjustment_row_carries_its_own_reference_date    before=None  after=[14.7]
kept   f1_negative_a_date_that_does_start_a_line...           before=[10.0, 20.0]  after=[10.0, 20.0]
kept   f1_negative_an_uncalendarable_row_date_is_dropped      before=None  after=None
kept   f2_a_bare_amount_line_completes_the_row_above_it       before=[-500.0]  after=[-500.0]
kept   f2_a_bare_amount_cell_outranks_a_money_token...        before=[-117.68]  after=[-117.68]
kept   f2_negative_a_completed_row_is_not_extended...         before=[-50.0, -10.0]  after=[-50.0, -10.0]
kept   f3_a_section_total_printed_after_the_last_row...       before=[-263.62]  after=[-263.62]
kept   f3_a_card_subtotal_is_never_a_row                      before=[-10.0, -20.0]  after=[-10.0, -20.0]
FIXED  f4_a_counterparty_named_total[Total Quality Lo...]     before=None  after=[-24.33]
FIXED  f4_a_counterparty_named_total[TOTALWINE 1147...]       before=None  after=[-24.33]
kept   f4_negative_the_printed_section_total_is_never_a_row   before=[10.0]  after=[10.0]
FIXED  f5_a_single_column_checks_table_is_read                before=None  after=[-750.0]
FIXED  f5_a_check_the_bank_printed_no_number_for...           before=[-200.0]  after=[-300.0, -200.0]
kept   f5_a_gap_marked_check_number_keeps_its_marker          before=[-68.79]  after=[-68.79]
kept   f5_negative_the_account_summary_checks_line...         before=[10.0]  after=[10.0]
FIXED  f6_the_consumer_layout_is_read_on_both_sides           before=None  after=[500.0, -30.0, -70.0]
FIXED  f7_a_scanned_column_header_does_not_hide_the_section   before=None  after=[-55.4]
kept   f8_a_section_continues_across_a_page_break             before=[10.0, 20.0]  after=[10.0, 20.0]
kept   f8_negative_the_daily_ledger_series_is_never_activity  before=[10.0]  after=[10.0]
kept   f8_negative_the_page_header_line_never_joins_a_desc    before=[-500.0]  after=[-500.0]
kept   a_waived_fee_of_zero_is_still_an_outflow_row           before=[-0.0]  after=[-0.0]
FIXED  every_section_together_reconciles_against_the_summary  before=[-200.0, -300.0, -25.0]
                                                              after=[900.0, 100.0, -200.0, -300.0, -100.0, -300.0, -25.0]

fixtures: 23 (24 tests, one parametrised) · behaviour changed: 9 · unchanged: 14
```

The 14 `kept` lines are not weak tests and are reported as what they are:
**constraints**, not demonstrations. Each pins a rule the new reader had to be
built around — a minimal synthetic document is often one the old flattening
happened to read correctly, and the point of the fixture is that the new rule
still does. Two are explicit about it: `a_waived_fee_of_zero…` compares
`direction`, which the amount list above cannot show (`debit` before, `debit`
after — the *new* reader would have said `credit` without the section-side
rule), and `f2_a_bare_amount_cell_outranks…` guards the hazard §B4's B-F3 row
names, which the naive form of this restructuring introduced and the
289-document differential caught before commit.

**Commits (oldest first)**

| Commit | Contents |
|---|---|
| `dc61540` | `analysis/bofa.py` + `tests/test_bofa_variants.py` |
| `1eeb123` | this log's §BOFA B0–B7 |
| (this one) | §B8, and the B-F3 root-cause line corrected to name it as a hazard of this restructuring rather than a pre-existing defect |

---

# §WELLS — Cell 5: `wells_fargo × {period_integrity, detail_coverage, balance_continuity}`, 40 documents

REEF-WELLS, 2026-08-08. Branch `wave3-wells-completeness`, base `b839bfa`
(`5443cfa` plus the two handoff files). Brief:
`docs/agent-handoffs/REEF-WELLS.md`.

Same method and idiom as §1/§TD/§5/§BOFA: reproduce the cell independently,
build the in-document instrument BEFORE changing code, characterise layout
families structurally, fix at the capability level or fail closed with the
volume stated, prove both directions with synthetic fixtures, measure honestly.

The recurring lesson holds a fifth time. `period_integrity` names 22 of the 40
and it is a **symptom**: not one of those documents has a period problem. Every
one prints its period exactly where the others do, and the parser read none of
it because a single flattened regex demanded that the four cells of the
activity summary be adjacent in the text — and they are not.

## W0. Summary

| | |
|---|---|
| Cell worked | `wells_fargo × period_integrity` (22), `× detail_coverage` (13), `× balance_continuity` (5) — **40 records, 40 distinct content hashes**, no duplicates inside the cell |
| Result over the cell | **36 / 40 validated**, from 0 / 40. **4 fail closed by design** (§W4 W-F7 — the amount column is not in the text layer; `ocr/` is protected for this agent) |
| Movement outside the cell | none. The 1 `wells_fargo × posting_date_coverage` record parses **field-identically** and stays withheld |
| Already-validated `wells_fargo` documents (192 records / 180 hashes) | **192 / 192 still validate**, and every one is **field-identical** — same period, same balances, same stated totals, same rows, same amounts, same directions, same running balances, same descriptions. Zero regressions and zero description movement |
| Layout families characterised | 7 — six fixed, one ruled FAIL CLOSED with its volume |
| Statement-specific constants added | **none.** Two dead constructs **removed**: `_is_credit`, an unused description vocabulary that named a counterparty, and `_PERIOD_RE`, an unused regex |
| Protected modules touched | none. `analysis/tables.py`, `money.py`, `date_tokens.py`, every other parser, pipeline/registry, `ocr/`, `webapp/`, `discovery/`, `telemetry/`, corpus assets and both audit CSVs are unmodified. `parse_money` and `iso_from_month_day` are consumed exactly as they were |
| Truth-set movement | **none.** All 4 pinned corpus Wells Fargo statements parse field-identically; `corpus_gate.py` **GREEN**, 106 PASS / 3 WITHHELD, same three by name. **No re-baseline requested or performed** |
| Files changed | `analysis/wells.py`, `tests/test_wells_variants.py` (new, 25 fixtures), this log |
| Cache implication | analysis output changes for unchanged settings on **40 of the 233** archive `wells_fargo` documents → `ANALYSIS_STAGE_VERSION` must be bumped at merge. **Ocean's, not done here** (`webapp/` is protected for this agent) |

## W1. The cell reproduced independently

Joining the frozen baseline run `70123cf2`'s telemetry diagnostics to its
`rows.csv` parser attribution by content hash reproduces the assigned cell
exactly: `parser_id == "wells_fargo"` gives **233 records — 192 validated, 41
withheld**, and the withheld split by primary class is **`period_integrity` 22
· `detail_coverage` 13 · `balance_continuity` 5 · `posting_date_coverage` 1**.
The first three are the assigned cell: 40 records, 40 distinct hashes. Every
one of the 233 is in the `Wells Fargo/` folder and every one resolves through
the native `native-pdf-text+wells` rung; none is scanned, and none carries an
HTML `<table>` fragment.

(The brief quotes the run as validated 1,533 / withheld 147; the run's own
`report.txt` and `rows.csv` both say **1,577 / 148**. The discrepancy is in the
brief, not in the data — the derivation above is from the run itself, and the
per-cell counts it quotes, 22 / 13 / 5, match exactly.)

The failing checks are uniform within each class, and the shape of the two
groups is the finding:

| Evidence | period_integrity (22) | detail_coverage (13) | balance_continuity (5) |
|---|---|---|---|
| `adb:statement_period_dates_valid` | 22 | — | — |
| `adb:opening_balance_matches_statement` | 22 | — | — |
| `adb_state:period_start_missing` / `period_end_missing` / `period_dates_invalid` | 22 | — | — |
| `adb_state:beginning_balance_absent` / `closing_balance_absent` | 22 | — | — |
| `recon:sum_check_inputs_missing` | 22 | — | — |
| `adb:final_balance_matches_statement_closing` | 22 | 13 | 5 |
| `adb:ledger_reconciles_to_closing`, `integrity:ledger_sum_mismatch` | — | 13 | 5 |
| `integrity:running_balance_breaks` | 2 | 13 | 5 |
| `integrity:credit_detail_coverage_mismatch` | — | 12 | — |
| `integrity:debit_detail_coverage_mismatch` | — | 10 | — |

On all 22 `period_integrity` documents, **every one of the 13 summary fields is
absent** — period start and end, beginning and ending balance, both stated
totals, both stated counts, days in period. That is not a period defect. It is
one block that was not read at all, and the class is simply the highest-ranked
consequence.

## W2. The measurement instrument (used before any code changed)

Wells Fargo prints three independent self-checks, all on the document:

* the **Statement period activity summary** — beginning balance, one credit
  total, one debit total and an ending balance, per account;
* a **`Totals $C $D`** line at the foot of each account's transaction history,
  which is that account's captured credit and debit totals as the bank
  computes them — printed, and read by no part of the parser;
* the **Ending daily balance** column, printed on the last row of each posting
  day, which the parser does carry as `running_balance`.

The instrument's own trustworthiness is checked first rather than assumed: over
the 192 `wells_fargo` documents discovery had already validated, the printed
summary closes arithmetically (beginning + credits − debits = ending) on
**192 / 192**, and the rows reproduce both the stated totals and the printed
`Totals` line on **192 / 192**. A document that fails it is failing the bank's
own arithmetic.

Baseline over the cell, before any change — the parser's published statement
measured against the statement's own printed figures:

| Instrument | period_integrity (22) | detail_coverage (13) | balance_continuity (5) |
|---|---|---|---|
| period read | 0 | 13 | 5 |
| beginning + ending balance read | 0 | 13 | 5 |
| stated credit + debit totals read | 0 | 13 | 5 |
| the printed summary closes | 0 | 13 | 5 |
| rows reproduce the stated credit total | 0 | 0 | 4 |
| rows reproduce the stated debit total | 0 | 3 | 0 |
| rows reproduce the printed `Totals` line | **18** | 0 | 0 |
| ledger identity holds | 0 | 0 | 0 |

**Two disjoint findings, and neither is what the class names.**

1. On `period_integrity` the rows were already right — 18 of 22 reproduce the
   bank's own printed `Totals` line before any change. Nothing was missing from
   the ledger; the *summary block* was unread.
2. On `detail_coverage` and `balance_continuity` the summary was read
   perfectly and the **rows** were wrong — and the direction of the error is
   the tell. Captured gross money (credits + debits) is **above** the stated
   gross on **16 of the 18** and below it on 2. The platform was reading *more*
   money than the account printed, which no coverage defect can produce: a
   coverage defect can only lose rows. `detail_coverage` was, on 14 of these
   18 documents, exactly the wrong diagnosis of the wrong sign.

## W3. The two things that were wrong

**(1) A statement can carry more than one account, and every account's rows
were being read against one account's summary.** Wells prints each account as a
section that opens with its own `Account number:` line, exactly one of which
carries the bank's `(primary account)` marker; the section holds that account's
activity summary, its transaction history and its own `Totals` line. Over the
233 documents this structure is exact: the account line precedes its summary
heading 1:1 on **233 / 233**, the first section is the primary-marked one on
**233 / 233**, and **zero** transaction rows are printed before the first
account line. The parser took the first `Account number:`, the first summary
block and **every** `WF_TX` row in the document, so on a two-account statement
it published the union of two ledgers against one of them. 17 documents print
two accounts: 14 in the cell, 3 already validated (whose second account has no
activity, which is why they passed).

**(2) The activity summary was read as a sentence, not as the printed
label/value block it is.** The block prints four labelled rows —
`Beginning balance on M/D`, `Deposits/<direction>`, `Withdrawals/<direction>`,
`Ending balance on M/D`. `ocr/native_text.py` emits one PyMuPDF *block* per
line in (y, x) order, so the page furniture printed in the same vertical band —
the account-terms line, the two routing-number lines, the account holder's name
— lands **between** those rows. The old regex required the four cells to be
adjacent in one run of text, required the business spelling
(`Deposits/Credits`), required the word `Ending`, and required a printed minus
in front of the withdrawals figure. Any one of those four assumptions failing
lost the entire block, and with it the period, both balances and both stated
totals.

The structural correction is one sentence: **each label owns its own printed
row and claims the amount cell printed on it** — and the period is printed
*inside the labels*, not in the cells, so a statement whose amount column is
unreadable still dates itself.

## W4. The families
# §TRIO — Cells 6–8: `us_bank`, `truist`, `pnc`

REEF-TRIO, 2026-08-08. Branch `wave3-trio-completeness`, base `5443cfa`
(worktree tip `b839bfa`, which adds only the two handoff files). Brief:
`docs/agent-handoffs/REEF-TRIO.md`. Three cells worked in strict sequence,
each fully proven before the next.

Same method and idiom as §1/§TD/§5/§BOFA: reproduce the cell independently from
the frozen baseline, build the in-document instrument and check the instrument
itself against the parser's already-validated population BEFORE changing code,
characterise layout families structurally, fix at the capability level or fail
closed with the volume stated, prove both directions with synthetic fixtures,
measure honestly.

## TRIO-0. The three cells, derived from the baseline

Joining run `70123cf2`'s telemetry diagnostics to its `rows.csv` parser
attribution by content hash. The run itself: 3,506 records / 3,380 distinct
documents — validated 1,533 / review 10 / withheld 147 / deferred 13 / failed
1,677 at distinct-document level (1,577 / 10 / 148 / 13 / 1,758 at record level).

| Cell | brief | measured | note |
|---|---|---|---|
| `us_bank × summary_identity` | 20 | **20 records, 20 distinct hashes** | agrees |
| `us_bank × ledger_identity` | 2 | **0** | the brief's "+ ledger_identity 2" is not in this baseline: `us_bank` has 40 records — 20 validated, 20 withheld — and **all 20 withheld are `summary_identity`**. Reported rather than reconciled away |
| `truist × detail_coverage` | 12 | **12** | agrees |
| `truist × ledger_identity` | 8 | **8** | agrees |
| `pnc × detail_coverage` | 14 | **14** | agrees |
| `pnc × ledger_identity` | 2 | **2** | agrees |
| `pnc × summary_identity` | — | **1** | outside the brief's cell; `pnc` has 17 withheld records, not 16 |

## TRIO-1. Cell 6 — `us_bank × summary_identity`, 20 documents

### 1.0 Summary

| | |
|---|---|
| Cell worked | `us_bank × summary_identity` — **20 records, 20 distinct hashes**, all digital, all native-text, all in the `US Bank/` folder |
| Result over the cell | **20 / 20 validated**, from 0 / 20. No residual |
| Already-validated `us_bank` documents (20) | **20 / 20 still validate, and all 20 are field-identical** — not merely still-passing |
| Layout families characterised | 8, all closed at the capability level |
| Statement-specific constants added | **none** |
| Protected modules touched | none. `analysis/tables.py`, `money.py`, `parser_registry.py`, `schema.py` and every other parser are unmodified; `compact_whitespace`, `group_rows` and `parse_amount` are consumed exactly as they were |
| Truth-set movement | **none.** Both pinned corpus U.S. Bank statements parse **byte-identically**, every field and every row. **No re-baseline requested or performed** |
| Files changed | `analysis/us_bank.py`, `tests/test_us_bank_variants.py` (new, 21 fixtures), this log |
| Cache implication | analysis output changes for unchanged settings on 20 of 40 `us_bank` documents → `ANALYSIS_STAGE_VERSION` must be bumped at merge. **Ocean's, not done here** (`webapp/` is protected for this agent) |

### 1.1 The cell reproduced independently

`parser_id == "us_bank"` gives **40 records — 20 validated, 20 withheld** — and
the withheld are **20/20 `summary_identity`**, 20 distinct hashes, no duplicates
inside the cell. The failing checks are uniform:

| Evidence | Documents |
|---|---|
| `integrity:summary_math_inconsistent`, `recon:summary_identity_failed` | 20 / 20 |
| `adb:final_balance_matches_statement_closing`, `adb:ledger_reconciles_to_closing` | 20 / 20 |
| `integrity:ledger_sum_mismatch`, `recon:sum_check_failed` | 20 / 20 |
| `adb_state:final_balance_drift`, `adb_state:ledger_reconcile_failed` | 20 / 20 |
| `adb:posting_dates_cover_source`, `adb_state:posting_dates_incomplete` | 12 |

**The class name is accurate and, as in every previous cell, one level above the
cause.** `summary_identity` says the bank's own summary block fails its own
identity — but the bank's block closes perfectly (§1.2); what fails its identity
is *our reading of it*. The handoff's suspicion — "suspect summary-extraction
capability, not the ledger" — is exactly right, and §1.3 is why.

### 1.2 The measurement instrument (used before any code changed)

U.S. Bank prints an Account Summary that is a complete, self-checking index of
the ledger:

```
Number of Days in Statement Period 31
Beginning Balance on Mar 2 $ 14,948.95 Other Deposits 37 100,753.73 Card Deposits 2 18,900.00
   Card Withdrawals 5 39.14- Other Withdrawals 107 63,875.76- Checks Paid 21 41,761.15-
Ending Balance on  Mar 31, 2026 $ 28,926.63
```

(printed as two physical lines; wrapped here.) Every category carries **a count
and a signed amount** — outflows print the bank's trailing minus — each category
is itemized in a detail section that ends with its own printed
`Total <category>`, and beginning + every category = ending. So completeness,
direction and the ledger identity are all checkable **against the document
itself** — no expectation file, no audited truth set.

**The instrument's own trustworthiness is checked first, not assumed:** the
printed summary closes arithmetically on **40 / 40** documents (20 withheld +
20 already-validated) and on both pinned corpus statements. A document that
fails it is failing the bank's own figures.

There is a second, stronger instrument the parser does not touch at all: a
`Balance Summary` block printing an **end-of-day balance for every day the
account moved** ("Balances only appear for days reflecting change"). Nothing in
`analysis/us_bank.py` reads it, which makes it an independent oracle of rows,
amounts, signs *and* posting dates — the role Chase's DAILY ENDING BALANCE
series played in §2 and BofA's `Daily ledger balances` in §B2. 36 of the 40
documents print one.

Baseline over the cell, before any change:

| Instrument | withheld (20) | already validated (20) |
|---|---|---|
| printed summary closes | 20 / 20 | 20 / 20 |
| parser claims the document | 20 / 20 | 20 / 20 |
| `stated_total_credits` = the summary's printed credit categories | 12 / 20 | 20 / 20 |
| `stated_total_debits` = the summary's printed debit categories | **0 / 20** | 20 / 20 |
| captured credit rows reproduce the printed credit total | 12 / 20 | 20 / 20 |
| captured debit rows reproduce the printed debit total | **0 / 20** | 20 / 20 |
| captured row counts equal the printed per-direction counts | 12 / 20 credit, **0 / 20** debit | 20 / 20 |
| ledger identity holds | **0 / 20** | 20 / 20 |
| the printed `Balance Summary` series reproduced exactly | **0 / 20** | 16 / 16 (4 print none) |

Every deviation is in the same direction — **captured < printed** on both the
stated totals and the rows — so the platform was losing whole categories and
never inventing any.

### 1.3 The root cause: a closed vocabulary that dropped both halves at once

The parser knew **three** summary categories (`Customer Deposits`,
`Other Deposits`, `Other Withdrawals`) and read **three** detail sections, one
per category. U.S. Bank prints **six**, and a statement prints exactly the ones
it has activity in. The three the parser did not know are `Card Deposits`,
`Card Withdrawals` and `Checks Paid` (itemized under the printed heading
`Checks Presented Conventionally`).

That partition is the cell, exactly: **the 20 withheld documents are precisely
the `us_bank` documents that print a category outside the three, and the 20
already-validated ones are precisely those that do not.** Measured across the
population — `Card Deposits` 8, `Card Withdrawals` 16, `Checks Paid` 14, every
occurrence inside the withheld 20 and none in the validated 20.

**Why the diagnosis was `summary_identity` and not a coverage class.** An
unknown category was dropped from the stated totals *and* from the ledger *at
the same time*, so the two stayed consistent with each other while both drifted
from the bank. `stated_total_debits` was `Other Withdrawals` alone; the ledger
was `Other Withdrawals` alone; the parser's own publish gate — captured totals
must equal stated totals — therefore passed. What could not pass was the bank's
own identity: beginning + our credits − our debits missed the printed ending
balance by exactly the categories we never read. The platform reported the
symptom it could see.

### 1.4 The families

Named by structure. Nothing below names a customer, an amount, a date or an
account fragment; every rule is anchored on the printed grid.

| # | Family | Structural signature | Root cause | Ruling | Fixture | Volume (cell / already-validated) |
|---|---|---|---|---|---|---|
| W-F1 | **consumer summary vocabulary** | the activity rows are labelled `Deposits/Additions` and `Withdrawals/Subtractions` instead of `Deposits/Credits` / `Withdrawals/Debits` | the summary regex spelled out one vocabulary, so the consumer layout matched nothing | FIX — a row's direction is its label's FIRST word, the word that names the printed column; the second word is data (`Deposits/\S+`), not vocabulary to enumerate | `test_f1_*` | **13 / 0** |
| W-F2 | **closed-account balance label** | an account closed in the period prints `Closing balance on M/D` where an open one prints `Ending balance on M/D` | the regex required the word `Ending` | FIX — both printed forms are the period-end balance row | `test_f2_*` | **1 / 1** |
| W-F3 | **page furniture between the summary rows** | the four labelled rows are separated by the account-terms line, the routing-number lines and the account holder's name | the block was read as one run of text in which the four cells had to be adjacent | FIX — a label owns its own row; nothing is assumed about adjacency | `test_f3_*` | **6 / 0** |
| W-F4 | **unsigned withdrawal cell** | `Withdrawals/Debits 257,049.31` — the minus glyph is not in the text layer | the regex required `-` before the figure | FIX — the direction of an activity row is its label's, so its cell is read as a magnitude. A *balance* keeps whatever sign the bank printed | `test_f4_*` (four printed sign forms) | **1 / 0** |
| W-F5 | **the record's delimiter inside a description** | an ACH row quotes EDI reference text whose interchange trailer contains the pipe character — the same character the `WF_TX` record uses to separate its own fields | the record was split left to right with a fixed field count, so a description containing the delimiter shifted every field after it: the amount vanished and reference text was read as a money cell | FIX — only the description can carry the delimiter and exactly three grid cells follow it, so the tail is taken from the right. The fixture reproduces the old read as a **$1,500,022,281** row | `test_f5_*` | **4 documents / 8 rows / 0** |
| W-F6 | **multi-account statement** | two `Account number:` sections, one marked `(primary account)`, each with its own summary, history and `Totals` | the parser read the first summary and every row in the document | FIX — the published ledger is the marked account's section. `Statement` is single-account (MASTER_PLAN L-1); the union is arithmetic over two ledgers. See §W7.1 | `test_f6_*` (incl. moving the marker to the second section) | **14 / 3** |
| W-F7 | **the amount column is not in the text layer** | rows whose money cell landed in neither printed column or in both, and printed rows merged into one record — the extractor's line binning and column bands do not hold on this layout | the geometry is recovered in `ocr/native_text.py::_wells_rows`, which is protected for this agent | **FAIL CLOSED — 4 documents (10% of the cell).** They keep accurate diagnostics (3 `detail_coverage`, 1 `summary_field_missing`). A row the grid does not place is dropped rather than assigned a direction | `test_a_row_whose_amount_is_in_neither_money_column_is_dropped`, `..._in_both_money_columns_is_dropped`, `test_a_summary_cell_printed_before_its_label_is_not_claimed_by_it` | **4 / 0** |
| # | Family | Structural signature | Root cause | Ruling | Fixture | Volume |
|---|---|---|---|---|---|---|
| U-F1 | **unlisted summary category** | the Account Summary prints a `<category> <# items> <amount>` line outside the parser's three | a closed vocabulary in two places at once — the summary reader and the section list | FIX — read every category the grid prints; each indexes the detail section printed under the bank's own heading for it. **And refuse when our reading of the summary fails the summary's own identity**, which is what turns the old silent drop into a fail-closed refusal | `test_f1_*` | **20 / 20** cell documents |
| U-F2 | **card sub-block furniture** | a card section prints one block per card: `Card Number: xxxx-…`, a reprinted column header, the rows, then `Card <n>  Deposit/Withdrawals Subtotal $ x` | the section had never been read at all; reading it naively makes the bank's own subtotal a row and glues the sub-block heading to the row above | FIX — furniture closes the row above it and opens nothing | `test_f2_*` | 24 sub-blocks across 18 documents |
| U-F3 | **the checks grid** | `Checks Presented Conventionally` prints `Check Date Ref Number Amount` in up to **four** column groups on one physical line, carries `*` gap markers, and closes with a differently-worded total naming no section (`Conventional Checks Paid (n) $ x-`) plus a `* Gap in check sequence` footnote | the section was unknown, and its shape is not the described-row shape either | FIX — a row ends at its Amount cell, so text after one begins the next row; the row's own printed number is its description (`Check 1004*`), and the two footer lines are section terminators | `test_f3_*` | **14** documents |
| U-F4 | **money printed after the Amount cell** | a foreign-currency purchase prints `Exchg Amt: $54.63 Orig Curr:936.38` and `Currency Type: …` on continuation lines BELOW the Amount cell | *(a hazard of this restructuring, not a pre-existing defect — the section was previously unread. The naive "last money token" rule reads the original-currency figure, and so does a naive "last line-terminating token" rule)* | FIX — the Amount cell is the money cell that TERMINATES a printed line, and the FIRST such cell in the row, because everything after it is the description continuing | `test_f4_*` | **2** documents, 8 rows; caught by the printed section total before commit |
| U-F5 | **compressed line** | several printed rows on one physical line, in the numbered sections (`Feb 3 8353743994 15,532.63 Feb 6 9253307465 14,000.00`) and in the described ones | none — the pre-change flatten-and-split-at-every-date rule handled it | NO CHANGE in outcome; the rule is now the narrower amount→date seam, and it is pinned so the restructuring cannot regress it | `test_f5_*` | present on 19 documents |
| U-F6 | **a heading owns its line** | the Account Summary prints EVERY section's name on one line (`… Other Withdrawals 107 63,875.76- …`) | none — pinned. Had a section been opened by a line merely containing its heading, the summary's own figures would have been read as ledger rows | NO CHANGE; pinned as a negative, because the new section walk is line-based and this is the constraint it had to be built around | `test_f6_*` | every document |
| U-F7 | **page break inside a section** | `--- Page n ---`, then the reprinted letterhead and account header, then `<heading> (continued)` and a reprinted column header | the old chunker stopped at `--- Page` and re-entered on the next heading match; the new walk must do the same or the letterhead joins a row still waiting for its amount cell | FIX — a page break leaves the section, the `(continued)` heading re-enters it | `test_f7_*` | 60 continuations across 20 documents |
| U-F8 | **the printed sign** | outflow figures print their minus AFTER the digits — in the summary (`63,875.76-`), in the rows, and on an overdrawn balance (`8,288.08-`) | none — direction was previously implied by which of three hard-coded sections a row came from | FIX in kind, not in outcome: direction is now the sign the summary prints for that category, so a category's direction is a grid fact rather than a memorised name | `test_f8_*` | 34 of 40 documents print at least one negative balance |

Negative fixtures — each constrains a new rule rather than demonstrating a
defect, and each is asserted:

- a routing number is not an amount cell (a digit run with no cents is not
  money), and the balance row it stands next to yields **no value** rather than
  the routing number;
- a printed negative balance keeps its sign, while a withdrawals row is a
  magnitude either way;
- the ledger's own `Deposits/ Credits` column header is not a summary row —
  it is below the `Transaction history` heading that closes the block;
- a heading owns its line: a sentence containing the words
  "Transaction history" or "Overdraft Protection" does not close the block;
- the `Ending daily balance` column is never read as a summary row;
- a single-account statement is unaffected by the section rule;
- an ordinary two-cell transaction record is unaffected by the right-split;
- a period that crosses New Year still dates its opening day to the prior year;
- a statement with no ledger publishes nothing, and (pinned in
  `test_r1_hardcodes.py`, unchanged) one with no year evidence is not parsed.

### W4.1 What did NOT change, deliberately

- **`ocr/native_text.py` was not touched**, and this is the cell's stop
  condition (§W7.2). The four W-F7 documents need the PDF's word geometry read
  differently; that is a protected module and an architecture decision.
- **No shared utility was touched**, and no shared utility's behaviour changed,
  so no R-2 differential-equivalence proof is owed. Stop condition 1 never
  fired: everything this cell needed is a Wells Fargo layout fact.
- **`group_rows` was not consumed.** Wells Fargo is the one bank in Track A
  whose rows do not need grouping: `ocr/native_text.py` already emits one
  delimited record per printed row from the page's word geometry, so rules 1
  and 2 of the promoted primitive have nothing to do here. What Wells
  contributes to the promotion question is §W7.3.
- **`_infer_year` is unchanged.** Its rule — the first four-digit year printed
  in the document — was checked against the printed statement-date line
  (`<Month> D, YYYY  Page N of M`) on all 233 documents and agrees on
  **233 / 233**. There is no evidence for changing it, and R-1's rule is that
  period evidence, not a better guess, is what may date a statement.
- **The `Totals` line is read by the instrument and not by the parser.** It is
  a printed, independently computed credit and debit total that nothing in the
  platform consumes; using it would be a second source for fields the summary
  already publishes. It is the strongest oracle in this layout and §W7.4 queues
  it rather than spending it here.
- **`stated_average_balance` extraction is unchanged**, beyond being scoped to
  the published account's section like everything else.

## W5. Result over the cell

Same production ladder discovery uses (`ocr.pipeline.parse_statement`, native
rung, no OCR, no model calls, `$0.00`), then `analyze_markdown` in
deterministic mode, classified with `telemetry.record.classify_outcome` and
diagnosed with `telemetry.diagnostics.diagnose`.

| Cell | records | documents | before | after |
|---|---|---|---|---|
| `wells_fargo × period_integrity` | 22 | 22 | 0 validated / 22 withheld | **18 / 4** |
| `wells_fargo × detail_coverage` | 13 | 13 | 0 / 13 | **13 / 0** |
| `wells_fargo × balance_continuity` | 5 | 5 | 0 / 5 | **5 / 0** |
| **total** | **40** | **40** | **0 / 40** | **36 / 4** |
| `wells_fargo × posting_date_coverage` (outside the cell) | 1 | 1 | 0 / 1 | 0 / 1 — field-identical, untouched |
| already-validated `wells_fargo` | 192 | 180 | 192 validated | **192 validated, all field-identical** |

Against the in-document instrument, after the change:

| Instrument | period_integrity (22) | detail_coverage (13) | balance_continuity (5) | already validated (192) |
|---|---|---|---|---|
| period read | **22** (was 0) | 13 | 5 | 192 |
| beginning + ending balance read | **21** (was 0) | 13 | 5 | 192 |
| stated credit + debit totals read | **21** (was 0) | 13 | 5 | 192 |
| the printed summary closes | **21** (was 0) | 13 | 5 | 192 |
| rows reproduce the stated credit total | **19** (was 0) | **13** (was 0) | **5** (was 4) | 192 |
| rows reproduce the stated debit total | **18** (was 0) | **13** (was 3) | **5** (was 0) | 192 |
| rows reproduce the printed `Totals` line | **18** (was 18) | **13** (was 0) | **5** (was 0) | 192 |
| ledger identity holds | **18** (was 0) | **13** (was 0) | **5** (was 0) | 192 |

**Nothing was padded to get there.** Every document that now validates does so
because the rows extracted reproduce, independently: the bank's stated credit
and debit totals for the published account, the `Totals` line that account's
transaction history prints, the ledger identity, and the full ADB validation
suite. The fail-closed gate is unchanged; these documents pass it on their own
arithmetic.

**The 4 that remain withheld are the honest residual** and they are one family
(W-F7), all from a single source layout. On them the native extractor's line
binning merges printed rows and its column bands miss the amount cell
altogether: one document's rows carry a credit and a debit cell at once, three
lose rows entirely, and one has its summary's value column emitted **ahead** of
its label column, so three of that block's four cells are not attributable to a
label at all. Their diagnostics are accurate — 3 `detail_coverage`, 1
`summary_field_missing` — and their period is now read correctly on all four,
because the period is printed in the labels.

## W6. The already-validated population — zero regressions, zero movement

The 192 already-validated `wells_fargo` records (180 distinct hashes) were
re-run through the same ladder, and the old and new modules were also loaded
side by side in one process over the identical markdown, comparing every field
of the serialised statement.

| | |
|---|---|
| still validated | **192 / 192** |
| **field-identical**, descriptions included | **192 / 192** |
| financially different | **0** |
| descriptions moved | **0** |

Unlike §5 and §BOFA, this cell moves nothing on the already-validated
population at all. That is a property of what changed: the summary rules only
*add* readings where the old regex found none (it never mis-read a block it
matched — it matched or it did not), and the section rule only bites where a
second account is printed, which on the three already-validated multi-account
documents contributes no rows.

**Pinned corpus, checked directly as well as through the gate** — old and new
module loaded side by side, same markdown, every field of the serialised
statement compared:

```
IDENTICAL    WellsFargo/02-28-26 WellsFargo.pdf   (196 rows)
IDENTICAL    WellsFargo/03-31-26 WellsFargo.pdf   (261 rows)
IDENTICAL    WellsFargo/04-30-26 WellsFargo 1.pdf (220 rows)
IDENTICAL    WellsFargo/113025 WellsFargo.pdf      (28 rows)
claimed by the Wells Fargo parser: 4; differing: 0
```

## W7. Carried findings and questions for Ocean

1. **Multi-account statements are published as their primary account, and that
   is a ruling, not a detail.** 17 archive `wells_fargo` documents print two
   accounts. `Statement` is single-account (MASTER_PLAN L-1, G5), and the
   parser already published the primary account's number, period and balances —
   what it also did was append the other account's rows to that ledger. This
   cell scopes the ledger to the section the bank marks `(primary account)`.
   The consequence is stated plainly: **the second account's transactions are
   not published.** They were not publishable before either — they were
   corrupting the primary account's arithmetic — but "we read one account and
   there was another" is a different statement from "we read the statement",
   and the platform currently has no surface on which to say it. The L-1
   multi-account schema is the real fix; until it lands, an advisory at the
   parser boundary (the shape `likely_account_count` already has at intake)
   would let the difference be seen. **Raised for a ruling.**
2. **W-F7 needs the PDF's word geometry re-read (stop condition, reported not
   acted on).** Four documents from one source layout defeat
   `ocr/native_text.py::_wells_rows`. The evidence is specific and read-only:
   its line binning is a fixed `round(y0 / 3.0) * 3.0` bucket, so two printed
   rows whose baselines fall in one bucket merge into a single record carrying
   a credit cell and a debit cell at once; and its column bands are fixed x
   ranges (`395–452` credit, `452–520` debit, `>=520` balance), so a layout
   printed at another scale drops its amount cells outside every band and the
   record arrives with both money fields empty. Both are the same class of
   defect: geometry read as constants rather than as the page's own column
   positions. `ocr/` is protected for this agent — **raised, not attempted**,
   and recommended as the next Wells card. The text-layer reader should stay
   either way: it is what makes the result self-checking against the printed
   `Totals` line.
3. **Row-grouper promotion (§3 item 4) — this cell's contribution is a
   boundary, not a rule.** Wells Fargo is the one Track A bank whose rows never
   need grouping, because its native extractor already emits one record per
   printed row from the page's word geometry. What that shows is that the
   promoted primitive's domain is *text-layer* layouts, and that where geometry
   is available the row-start and continuation rules are not needed at all.
   Nothing here argues for or against moving rule 3.
4. **The printed `Totals` line is an unread oracle, and it is the same card as
   §3 item 3 and §B7.2.** Every Wells account prints its own captured credit and
   debit totals at the foot of its transaction history. Nothing in the platform
   reads them. They are what this cell's instrument used to prove the residual
   honest, and — unlike the activity summary — they are printed *per account
   section*, which makes them the natural check for the multi-account question
   in item 1. Reading them into `stated_*` would be a parser change; checking
   them is a protected-module change (§5.7 item 4's count check is the same
   shape). Queued, not taken.
5. **`ANALYSIS_STAGE_VERSION` must be bumped at merge** (`webapp/` protected
   here). This change alters analysis output for unchanged settings on **40 of
   the 233** archive `wells_fargo` documents and on none of the other 193.

## W8. Proofs

All five run in this worktree against `07c21fb` — the only commit that touches
code or tests — on a clean tree (`git status --short` empty),
`set -o pipefail`, exit codes as printed.

```
$ python -m pytest -q
2290 passed, 18 deselected, 1 warning in 173.59s (0:02:53)
SUITE_EXIT=0

$ python -m pytest -q --ignore=tests/test_wells_variants.py
2265 passed, 18 deselected, 1 warning in 155.42s (0:02:35)
BASELINE_COUNT_EXIT=0

$ python -m pytest -m corpus -q
14 passed, 2294 deselected, 1 warning in 1130.72s (0:18:50)
CORPUS_MARKED_EXIT=0

$ python corpus_gate.py
[PASS] oracle_independence: 4 audit modules import no production financial mathematics
Coverage: 109 pinned PDFs (103 native text, 6 committed OCR), 0 exclusions
Ignored:  0 non-corpus PDFs under the corpus root
Outcomes: 106 PASS / 3 WITHHELD
Runtime:  393.5s
- a printed category the parser cannot read makes the summary miss its own
  identity, and the parser **refuses** rather than publishing a partial summary;
- a section whose rows do not reproduce its printed total fails closed;
- the per-card subtotal is never a row, and the checks section's total and gap
  footnote are never rows;
- the printed `Total <section>` line is never a row;
- a date printed mid-description (`Invoice dated Feb 27 and Mar 1`) never opens
  a row — the seam is an Amount cell followed by the next row's Date cell;
- the `Balance Summary` series is never read as activity;
- a wrapped Amount cell alone on its line, with the bank's trace lines printed
  below it, is still the amount.

### 1.5 What did NOT change, deliberately

- **No shared utility was touched**, and no shared utility's behaviour changed,
  so no R-2 differential-equivalence proof is owed. `group_rows` is consumed
  exactly as §GROUPER promoted it, with U.S. Bank's own predicates: a row starts
  at a physical line whose first cell is the Date column (optionally preceded by
  the row's number column), and the furniture predicate is `ends_row`. Rule 3 —
  which money cell is the amount — stays parser-local as §G2 ruled; U.S. Bank's
  answer (§U-F4) is a fourth distinct one.
- **The detection markers are unchanged**, so the set of documents reaching this
  parser is unchanged. Verified over the whole `US Bank/` folder: the 19
  documents no parser claimed in the baseline are refused by both the old and
  the new reader, so this change creates no new claim and loses none.
- **`stated_daily_balances` stays empty.** U.S. Bank publishes a daily series and
  the parser still does not read it; it is used here as an outside check only.
  Reading it as a first-class oracle is carried finding §3.3 / §B7.2, not this
  cell's work.
- **`account_name` stays the memorised product string.** It is wrong on 38 of the
  40 documents (which print `U.S. BANK SILVER - BUSINESS CHECKING` or
  `… GOLD - …`), but it is a pre-existing literal of a class roughly twenty other
  parsers share, it is not an audited field, and it is not on this cell's
  evidence path. Raised in §1.8, not touched.
- **There is no HTML-table path in this parser**; every `us_bank` document in the
  archive resolves through the native rung, so §1.4's ruling has no table-path
  counterpart.

### 1.6 Result over the cell

Same production ladder discovery uses (`ocr.pipeline.parse_statement`, native
rung, no OCR, no model calls, `$0.00`), then `analyze_markdown` in deterministic
mode, classified with `telemetry.record.classify_outcome` and diagnosed with
`telemetry.diagnostics.diagnose`.

| Instrument | before | after |
|---|---|---|
| stated credit total = the summary's printed credit categories | 12 / 20 | **20 / 20** |
| stated debit total = the summary's printed debit categories | 0 / 20 | **20 / 20** |
| captured rows reproduce both printed totals | 0 / 20 | **20 / 20** |
| captured row counts equal both printed counts | 0 / 20 | **20 / 20** |
| ledger identity holds | 0 / 20 | **20 / 20** |
| the printed `Balance Summary` series reproduced exactly, no day invented | **0 / 20** | **20 / 20** |

| Cell | records | documents | before | after |
|---|---|---|---|---|
| `us_bank × summary_identity` | 20 | 20 | 0 validated / 20 withheld | **20 / 0** |
| already-validated `us_bank` | 20 | 20 | 20 validated | **20 validated, all field-identical** |

**Nothing was padded to get there.** Every document that now validates does so
because the rows extracted reproduce, independently: the bank's printed total for
every detail section, the bank's printed per-direction counts, its stated totals,
the ledger identity, the bank's own end-of-day balance for every day it publishes
one, and the full ADB validation suite. The fail-closed gate is unchanged and was
tightened, not loosened — the parser now refuses three conditions it previously
published through (§1.4 U-F1 and its negatives).

The `Balance Summary` line deserves its own sentence. On all 20 documents the
reconstructed activity-day set is **exactly** the day set U.S. Bank prints a
balance for, and **every** printed balance is reproduced — from a block no part
of the parser reads. Before the change, none of the 20 reproduced it.

### 1.7 The already-validated population — zero regressions, zero drift

Old and new modules loaded side by side in one process over identical markdown,
comparing every field of the serialised `Statement` including descriptions:

```
20 / 20 already-validated us_bank documents : IDENTICAL (every field, every row)
 2 /  2 pinned corpus us_bank statements    : IDENTICAL (every field, every row)
19 / 19 unclaimed US Bank/ folder documents : refused by both readers
```

Unlike §5 and §BOFA, **no description moved at all**: the grouping the new reader
computes is the same grouping the old flatten-and-split produced on every
document both readers claim, which is itself a check on the restructuring.

### 1.8 Carried findings for Ocean

1. **The brief's `us_bank × ledger_identity` cell does not exist in baseline
   `70123cf2`** (§TRIO-0). All 20 `us_bank` withheld records are
   `summary_identity`. Reported rather than silently absorbed; the cell as worked
   is 20 documents, not 22, and all 20 moved.
2. **16 `US Bank/` documents print no Account Summary grid at all** and are
   unclaimed (`failed` / `no_parser_matched`) rather than withheld — a different
   U.S. Bank layout the parser has never been taught. Out of this cell's scope
   (the cell is defined by having been withheld), but it is the whole remaining
   `us_bank` population and a well-defined next card.
3. **`Balance Summary` as a first-class oracle (§3 item 3, §B7.2) — U.S. Bank is
   a fourth witness and the cleanest one yet.** It prints an end-of-day balance
   for every day of change on 36 of 40 documents, and it settled every question
   this cell raised. Reading it into `stated_daily_balances` is a parser change;
   *checking* it is a protected-module change.
4. **`stated_credit_count` / `stated_debit_count` are still extracted and never
   checked** (§5.7 item 4, §B7.3). U.S. Bank prints a count for every summary
   category, so this is a third population where the check would be free — and
   here it would have caught the defect on its own, since the withheld documents'
   debit counts were short by the whole missing category.
5. **`account_name` is a memorised product string** (§1.5). Wrong on 38 of 40
   documents, not audited, shared with roughly twenty other parsers. It is an
   R-1-class literal and a small self-contained card; deliberately not taken here
   because it is off this cell's evidence path and would move (non-financial)
   output on pinned statements.
6. **`ANALYSIS_STAGE_VERSION` must be bumped at merge** (`webapp/` protected
   here). This change alters analysis output for unchanged settings on 20 of the
   40 archive `us_bank` documents.

## TRIO-2. Cell 7 — `truist × {detail_coverage 12, ledger_identity 8}`, 20 documents

### 2.0 Summary

| | |
|---|---|
| Cell worked | `truist × detail_coverage` (12) + `× ledger_identity` (8) — **20 records, 20 distinct hashes**, all digital, all native-text, all in the `Truist/` folder, all single-account |
| Result over the cell | **20 / 20 validated**, from 0 / 20. No residual |
| Already-validated `truist` documents (28) | **28 / 28 still validate, and all 28 are field-identical** |
| Layout families characterised | 5, all closed at the capability level |
| Statement-specific constants added | **none** |
| Protected modules touched | none. `analysis/money.py`, `date_tokens.py`, `tables.py`, `parser_registry.py`, `schema.py` and every other parser are unmodified; `parse_amount` and `iso_from_month_day` are consumed exactly as they were |
| Truth-set movement | **none.** All 5 pinned corpus Truist statements parse **byte-identically**, every field and every row. **No re-baseline requested or performed** |
| Files changed | `analysis/truist.py`, `tests/test_truist_variants.py` (new, 13 fixtures), this log |
| Cache implication | analysis output changes for unchanged settings on 20 of 48 `truist` documents → `ANALYSIS_STAGE_VERSION` must be bumped at merge. **Ocean's, not done here** |

### 2.1 The cell reproduced independently

`parser_id == "truist"` gives **48 records — 28 validated, 20 withheld** — and
the withheld split by primary class is **`detail_coverage` 12 · `ledger_identity`
8**, 20 distinct hashes, no duplicates inside the cell. The failing checks are
uniform, and the two classes are one population:

| Evidence | Documents |
|---|---|
| `adb:final_balance_matches_statement_closing`, `adb:ledger_reconciles_to_closing` | 20 / 20 |
| `adb_state:final_balance_drift`, `adb_state:ledger_reconcile_failed` | 20 / 20 |
| `integrity:ledger_sum_mismatch`, `recon:sum_check_failed` | 20 / 20 |
| `integrity:transaction_detail_not_corporate_reliable` | 20 / 20 |
| `integrity:debit_detail_coverage_mismatch`, `recon:debit_coverage_short` | 12 |

The only thing separating the 12 from the 8 is whether the coverage flag fired
as well as the ledger one — the same population, the same cause.

### 2.2 The measurement instrument (used before any code changed)

Truist prints its own Account summary as a closed identity:

```
Account summary Your previous balance as of 01/30/2026 $2,844.74 Checks - 662.35
Other withdrawals, debits and service charges - 35,411.68
Deposits, credits and interest + 36,799.28 Your new balance as of 02/27/2026 = $3,569.99
```

and each of the three detail sections closes with its own printed
`Total <section> = $x`. Both are the document checking itself — no expectation
file, no audited truth set.

**The instrument's own trustworthiness is checked first:** the printed Account
summary closes arithmetically on **48 / 48** documents, and on the
already-validated single-account population every ledger figure reproduces it
**24 / 24**. (The instrument is scoped to the FIRST printed account block,
because that is the one the platform publishes; the four already-validated
multi-account statements are outside its scope and are covered instead by the
byte-identity differential in §2.6. All 20 cell documents are single-account.)

Baseline over the cell, before any change:

| Instrument | withheld (20) | already validated, single-account (24) |
|---|---|---|
| printed Account summary closes | 20 / 20 | 24 / 24 |
| the printed `Total checks` equals the summary's `Checks` figure | 20 / 20 | 9 / 9 of those that print a table (15 print none) |
| parser claims the document | 20 / 20 | 24 / 24 |
| `stated_total_debits` = summary `Checks` + `Other withdrawals` | 20 / 20 | 24 / 24 |
| captured credit rows reproduce the printed deposits total | 20 / 20 | 24 / 24 |
| captured cheque rows reproduce the printed `Total checks` | **0 / 20** | 24 / 24 |
| captured debit rows reproduce the printed debits | **0 / 20** | 24 / 24 |
| ledger identity holds | **0 / 20** | 24 / 24 |

The shape of the failure is unusually sharp: **the deposits side is perfect and
the debit side is short by exactly the printed `Total checks`, on every document
in the cell.**

### 2.3 The root cause: one printed-grid fact the reader did not admit

Truist emits its currency symbol as its own grid cell, so the flattened text
carries `Total checks` in two spellings:

| spelling | documents |
|---|---|
| `Total checks = $662.35` (symbol against the figure) | 28 already-validated, 0 cell |
| `Total checks = $ 662.35` (symbol apart from the figure) | **20 cell documents, 0 already-validated** |

That partition is the cell, exactly. The Checks-section pattern was
`Total checks\s*=\s*\$?([\d,]+\.\d{2})` — the `\$?` had to be followed
immediately by a digit — so on the spaced spelling the section had **no
terminator**, was never matched, and **every cheque in it was dropped from the
ledger**. The stated totals were unaffected because they come from the Account
summary, which is read by a different pattern; so the ledger came out short by
precisely the cheques, on both sides of the `detail_coverage` /
`ledger_identity` split.

Two further printed forms travel with the same layout and had to be admitted
before the section could be read correctly once it was found (§2.4 T-F2/T-F3).

### 2.4 The families

Named by structure. Nothing below names a customer, an amount, a date or an
account fragment; every rule is anchored on the printed grid.

| # | Family | Structural signature | Root cause | Ruling | Fixture | Volume |
|---|---|---|---|---|---|---|
| T-F1 | **currency symbol printed as its own cell** | `= $ 662.35` instead of `= $662.35`, in the printed section total and in the two summary balances | every money pattern in the module required the symbol to abut its figure; the `Total checks` pattern is also the Checks section's terminator, so the whole section vanished | FIX — the gap is a printed-grid fact carrying no meaning: one `_DOLLAR` fragment admits it everywhere this module reads money | `test_f1_*` (both spellings parametrised, and asserted to produce the identical statement) | **20 / 20** cell documents |
| T-F2 | **detached skip marker** | `02/23 * 975172 114.55` — the sequence-gap marker printed apart from the check number | the row pattern was `(\*?\d+~?)`, so a marker with a space after it matched nothing and the row was lost | FIX — the marker is its own optional cell and belongs to the number beside it; the description is still the number the bank printed (`Check *975172`) | `test_f2_*` (attached form pinned as the contrast half) | **9** rows across 9 documents |
| T-F3 | **cheque with no printed number** | `04/21 10.00`, and `05/18 * 300.00` — the CHECK # cell is empty, with or without a skip marker beside it | the row pattern required a number, so the row was lost and the section total then refused the document | FIX — a cheque row is `DATE [marker] [number] AMOUNT`; the Amount cell is the only one always printed. `Check` with no number, exactly as `analysis/bofa.py` B-F6 ruled | `test_f3_*` | **5** rows across **3** documents — the residual left standing after T-F1 and T-F2 alone |
| T-F4 | **one column group instead of three** | the Checks header prints `DATE CHECK # AMOUNT($)` once where the statement has few cheques, three times where it has many | the pattern matched a single group only, which happened to be a prefix of the tripled header — so this was never the blocker, but the new pattern must not lose the tripled form | FIX in kind, not in outcome: the header is one-or-more column groups. Pinned in both forms | `test_f4_*` | 1 group on all 20 cell documents, 3 on all 13 already-validated tables — a clean partition, and one more sign the two populations are two printed variants of the same table |
| T-F5 | **the printed total is the gate** | `Total checks = $x` under the table | the cheque check was `stated_total_debits - other_total` — the residue of two other figures — and it only ran `if checks`, so a section that produced no rows at all passed silently. That is what let all 20 documents publish a ledger missing every cheque | FIX — where the Checks table is printed, its rows must reproduce the total the bank printed under it | `test_f5_*` | every document with a Checks table |

Negative fixtures — each constrains a new rule rather than demonstrating a
defect, and each is asserted:

- the `* indicates a skip in sequential check numbers above this item` footnote
  is never a row;
- a Checks table whose rows do not reproduce its printed total publishes nothing;
- a statement that prints `Checks - 0.00` and no table is unaffected;
- the attached skip marker and the tripled column header still read exactly as
  before.

### 2.5 What did NOT change, deliberately

- **No shared utility was touched**, and no shared utility's behaviour changed,
  so no R-2 differential-equivalence proof is owed. In particular `parse_money`
  already tolerates the spacing; the rigidity was in this module's own patterns,
  which is why the fix belongs here.
- **The description sections' row reader is unchanged.** It reproduces the
  printed deposits and other-withdrawals totals on 44 of 44 single-account
  documents, before and after; nothing in the evidence asks for it.
- **Multi-account statements still publish only the first printed account.**
  Four already-validated `truist` documents carry two accounts; they are
  unchanged byte for byte. Reading the rest is the L-1 single-account-schema gap,
  not this cell's work (§2.7).
- **The detection markers are unchanged**, so the set of documents reaching this
  parser is unchanged. Verified over the whole `Truist/` folder: the 16 documents
  no parser claimed in the baseline are refused by both the old and the new
  reader.
- **`account_name` stays `"Checking"`**, as before.

### 2.6 Result over the cell, and zero regressions

Same production ladder discovery uses, then `analyze_markdown` in deterministic
mode, classified with `telemetry.record.classify_outcome` and diagnosed with
`telemetry.diagnostics.diagnose`:

| Instrument | before | after |
|---|---|---|
| captured cheque rows reproduce the printed `Total checks` | 0 / 20 | **20 / 20** |
| captured debit rows reproduce the printed debits | 0 / 20 | **20 / 20** |
| captured credit rows reproduce the printed deposits | 20 / 20 | 20 / 20 |
| ledger identity holds | 0 / 20 | **20 / 20** |

| Cell | records | documents | before | after |
|---|---|---|---|---|
| `truist × detail_coverage` | 12 | 12 | 0 validated / 12 withheld | **12 / 0** |
| `truist × ledger_identity` | 8 | 8 | 0 / 8 | **8 / 0** |
| **total** | **20** | **20** | **0 / 20** | **20 / 0** |

**Nothing was padded to get there.** Every document that now validates does so
because the rows extracted reproduce, independently: the bank's printed total for
each of the three detail sections, the bank's own Account summary identity, the
ledger identity, and the full ADB validation suite. The gate was **tightened**,
not loosened: the cheque check now runs against a printed figure and runs
unconditionally where the table exists.

Old and new modules loaded side by side in one process over identical markdown,
comparing every field of the serialised `Statement` including descriptions:

```
28 / 28 already-validated truist documents : IDENTICAL (every field, every row)
 5 /  5 pinned corpus Truist statements    : IDENTICAL (every field, every row)
16 / 16 unclaimed Truist/ folder documents : refused by both readers
```

### 2.7 Carried findings for Ocean

1. **Multi-account Truist statements publish one account of several.** Four
   already-validated documents print two `Account summary` blocks and the
   platform reads the first. Nothing regressed here and nothing was attempted;
   it is the L-1 single-account-schema gap, and Truist is a concrete population
   for it.
2. **The currency-gap rigidity is a shape, not a Truist fact.** `_DOLLAR` here is
   a two-character regex fragment, but the defect class — a printed symbol
   admitted in only one of its emitted spellings, in a pattern that also serves
   as a section terminator — is worth a sweep across the other parsers. It cost
   20 documents here and it fails silently by construction: the section simply
   is not found.
3. **`stated_credit_count` / `stated_debit_count` are not printed by Truist**, so
   the count check queued in §5.7 item 4 has no input on this bank. Recorded so
   the check's coverage is not assumed universal.
4. **`ANALYSIS_STAGE_VERSION` must be bumped at merge** (`webapp/` protected
   here). This change alters analysis output for unchanged settings on 20 of the
   48 archive `truist` documents.

## TRIO-3. Cell 8 — `pnc × {detail_coverage 14, ledger_identity 2}`, 16 documents

### 3.0 Summary

| | |
|---|---|
| Cell worked | `pnc × detail_coverage` (14) + `× ledger_identity` (2) — **16 records, 16 distinct hashes**. The parser's whole withheld population is 17 records; the 17th is `pnc × summary_identity` (1), outside the brief's cell, and it is reported and measured with the rest |
| Result over the cell | **12 / 16 validated**, from 0 / 16; **4 fail closed with their volume stated** (§3.5). Counting the adjacent `summary_identity` record, **13 of the parser's 17 withheld records** move |
| Already-validated `pnc` documents (28) | **28 / 28 still validate, and all 28 are financially identical field for field**; descriptions move toward the printed text on 28 (§3.6) |
| Layout families characterised | 6 — four fixed, two ruled FAIL CLOSED with their volume |
| Statement-specific constants added | **none** |
| Protected modules touched | none. `analysis/money.py`, `date_tokens.py`, `tables.py`, `parser_registry.py`, `schema.py` and every other parser are unmodified; `parse_money` and `iso_from_month_day_strict` are consumed exactly as they were |
| Truth-set movement | **none.** All 5 pinned corpus PNC statements are financially identical field for field (one description each drops printed furniture). **No re-baseline requested or performed** |
| Files changed | `analysis/pnc.py`, `tests/test_pnc_variants.py` (new, 12 fixtures), this log |
| Cache implication | analysis output changes for unchanged settings on 44 of 45 `pnc` documents → `ANALYSIS_STAGE_VERSION` must be bumped at merge. **Ocean's, not done here** |

### 3.1 The cell reproduced independently

`parser_id == "pnc"` gives **45 records — 28 validated, 17 withheld** — and the
withheld split by primary class is **`detail_coverage` 14 · `ledger_identity` 2 ·
`summary_identity` 1**, 17 distinct hashes, no duplicates. 16 resolve through the
native rung and 1 through local Tesseract. The failing checks:

| Evidence | Documents |
|---|---|
| `adb:final_balance_matches_statement_closing`, `adb:ledger_reconciles_to_closing` | 17 / 17 |
| `adb_state:final_balance_drift`, `adb_state:ledger_reconcile_failed`, `recon:sum_check_failed` | 17 / 17 |
| `integrity:ledger_sum_mismatch`, `integrity:transaction_detail_not_corporate_reliable` | 16 |
| `integrity:debit_detail_coverage_mismatch`, `recon:debit_coverage_short` | 15 |
| `integrity:credit_detail_coverage_mismatch`, `recon:credit_coverage_short` | 3 |
| `adb:posting_dates_cover_source` | 2 |

### 3.2 The measurement instrument (used before any code changed)

PNC prints two independent self-checks, and the second is unusually strong:

1. the **Balance Summary** — beginning + deposits and other additions − checks and
   other deductions = ending;
2. above the Activity Detail, a **`Description Items Amount` table** giving the
   **item count and total of every section the statement itemizes**, closing with
   a `Total` for each direction:

```
Description Items Amount Deposits 6 105,150.00 ATM Deposits and Additions 6 2,158.25 Fee Refunds 1 6.00
Description Items Amount Debit Card Purchases 355 289,547.07 POS Purchases 34 5,309.44
   ATM/Misc. Debit Card Transactions 32 10,605.35 ACH Deductions 5 3,021.00
   Service Charges and Fees 17 482.25   Total 13 107,314.25   Total 443 308,965.11
```

That table is **the bank's own index of its ledger**: it names every section,
counts its rows and totals its money. Completeness is therefore checkable
section by section against the document itself, with no expectation file and no
audited truth set.

**The instrument's own trustworthiness is checked first:** its subtotals
reproduce the Balance Summary on **45 / 45** documents, and over the 28 the
platform had already validated the captured ledger reproduces the printed
credits, the printed debits AND the printed item count **28 / 28**.

Baseline over the cell, before any change:

| Instrument | withheld (17) | already validated (28) |
|---|---|---|
| printed Balance Summary closes | 17 / 17 | 28 / 28 |
| the printed subtotals reproduce the Balance Summary | 17 / 17 | 28 / 28 |
| the statement prints a section the parser does not read | **17 / 17** | 3 / 28 |
| parser claims the document | 17 / 17 | 28 / 28 |
| captured credit rows reproduce the printed credits | 13 / 17 | 28 / 28 |
| captured debit rows reproduce the printed debits | **1 / 17** | 28 / 28 |
| captured row count equals the printed item count | **0 / 17** | 28 / 28 |
| ledger identity holds | **0 / 17** | 28 / 28 |

**A note on building the instrument honestly.** The instrument's first draft
inherited the parser's own money pattern and therefore its P-F4 defect, and it
reported one document's Balance Summary as not closing. The bank's figures do
close; both readings of them were wrong. The instrument was corrected to read the
printed grid before any of the numbers above were taken, which is the whole point
of building it from the document rather than from the code.

### 3.3 The root cause: a section list doing two jobs

The parser knew ten sections. PNC prints twelve, and the two it did not know are
`Checks and Substitute Checks` (13 cell documents) and `Fee Refunds` (5 cell
documents, 3 already-validated).

**The same list is also the list of section BOUNDARIES**, so an unknown section
is not merely unread — it is **swallowed by the section printed above it**:

* its rows take that section's **direction**, not the one they were printed
  under;
* its own heading and column header are glued onto the **last description** of
  the section above;
* and that section's captured count and total then disagree with the bank's
  printed pair for it, which is what the instrument sees.

`Fee Refunds` is always printed inside the `Deposits and Other Additions` group
in this archive, so the section that swallowed it was always a credit section
and no observed amount changed sign; the damage that IS observed is the wrong
section attribution and the polluted description. The sign hazard is latent
rather than measured, and it is pinned directly as a rule
(`test_f1_a_swallowed_section_would_take_the_wrong_direction`) with that
disclosure in the fixture itself.

`Checks and Substitute Checks` is worse: it prints a **different column group**
from every other section, so even once its heading is a boundary its rows need a
reader of their own.

### 3.4 The families

Named by structure. Nothing below names a customer, an amount, a date or an
account fragment; every rule is anchored on the printed grid.

| # | Family | Structural signature | Root cause | Ruling | Fixture | Volume |
|---|---|---|---|---|---|---|
| P-F1 | **a printed section outside the vocabulary** | the subtotal table names a section the parser's list does not have (`Fee Refunds`) | the list is both the section list and the boundary list, so the section is unread AND swallowed by the one above it | FIX — the vocabulary covers every section the bank's own subtotal table names; a row's direction is the section it was printed in | `test_f1_*` | **5** cell documents, 3 already-validated |
| P-F2 | **the cheque section's own column group** | `Checks and Substitute Checks` prints `Date posted \| Check number \| Amount \| Reference number`, several column groups per physical line, with `*` sequence-gap markers | the section was unknown, and its shape is not the `Date posted \| Amount \| Transaction description \| Reference number` shape every other section uses | FIX — a cheque row is date, number, optional marker, amount; the Reference number that follows carries no decimal point, so it can never be read as money. The printed number is the description | `test_f2_*` | **13** cell documents |
| P-F3 | **furniture that owns a line** | the two umbrella headings (`Deposits and Other Additions`, `Checks and Other Deductions`), the `<section> continued on next page` trailers, and the cheque section's `* Gap in check sequence` footnote — which PNC prints **on the heading line itself** | none of the three closed a section, so each was appended to the description of the row above it; and the footnote made the cheque heading unrecognisable as a heading | FIX — each is furniture: it owns its line, closes the section above it and opens nothing. The gap footnote is a suffix of its heading, not a different heading | `test_f3_*` | the umbrella headings on every document; the gap footnote on **8** cell documents |
| P-F4 | **a sub-dollar figure printed without its leading zero** | a Balance Summary balance of eighty-seven cents prints `.87` | the money pattern's `\b` does not match after a space, so the figure was skipped and the NEXT one — the average ledger balance printed below it — was read as the closing balance | FIX — the boundary is "not preceded by a digit, comma or point", which is a statement about the grid rather than about word characters | `test_f4_*` | **1** document — the `summary_identity` record, whose diagnosis was therefore about our arithmetic, not the bank's |
| P-F5 | **column-major text layer** | the Date column is emitted as its own block, away from the rows: `04 04 04` on one line, `/08 /10 /10` on the next, and the amounts, descriptions and reference numbers elsewhere again | the PDF's text objects are not emitted in grid order, so no row carries its own date | **FAIL CLOSED — 3 documents (3 of 16).** They stay withheld with accurate `detail_coverage` diagnostics. This is RBC's F11 exactly: no text-layer rule can reorder what the text layer has already reordered, and the input needed is the PDF word boxes | none: this family is defined by the ABSENCE of the structure the fixtures pin | **3** cell documents |
| P-F6 | **an OCR-lost cheque row** | the cell's one scanned document prints the cheque section's heading and column header, and local Tesseract recovered no row beneath them | none in the parser — the row is not in the text at all | **FAIL CLOSED — 1 document.** Its printed subtotal says one cheque of a thousand dollars and the ledger is short by exactly that; nothing is invented to close it | none: same reason as P-F5 | **1** cell document |

Negative fixtures — each constrains a new rule rather than demonstrating a
defect, and each is asserted:

- a row whose description contains a section's words never opens that section —
  a heading owns its line;
- a cheque row's Reference number is never read as its amount;
- the `<section> continued on next page` trailer is furniture, and the section
  re-enters at its `- continued` heading after the page break;
- a whole-dollar Balance Summary reads exactly as it did before the P-F4 change.

### 3.5 What did NOT change, deliberately

- **No parser-level publish gate was added.** `us_bank` and `truist` gained one
  in cells 6 and 7 because on those parsers a refusal costs nothing: every
  document that would trip the gate now validates instead. On PNC a printed-total
  gate would fire on the four P-F5/P-F6 documents and turn them from **withheld**
  into **unclaimed** — a *different* outcome class, and one Ocean's movement
  instrument would read as a transition other than withheld→validated. The
  platform's own ADB and reconciliation gate is already withholding them
  correctly and with an accurate diagnosis, so the refusal it would add is one
  the system already performs. Recorded as a deliberate asymmetry rather than an
  oversight; if Ocean wants parser-level symmetry, the transition it produces
  should be an explicit ruling.
- **No shared utility was touched**, and no shared utility's behaviour changed,
  so no R-2 differential-equivalence proof is owed.
- **The `Daily Balance` block is still not read.** PNC prints a full daily ledger
  series and it would be the natural independent oracle here — but on these
  documents the text layer emits it column-major (the same defect as P-F5), so it
  is not usable as an oracle without geometry. Recorded in §3.7; the section
  subtotals did the work instead, and they are stronger anyway because they carry
  item COUNTS.
- **The detection markers are unchanged**, so the set of documents reaching this
  parser is unchanged. Verified over the whole `PNC Bank/` folder: the 17
  documents no parser claimed in the baseline are refused by both the old and the
  new reader.
- **`account_name` stays `"Business Checking"`**, as before.

### 3.6 Result over the cell, and zero regressions

Same production ladder discovery uses (native rung, plus the cached local
Tesseract read for the one scanned document; no visual rung, no model calls,
`$0.00`), then `analyze_markdown` in deterministic mode, classified with
`telemetry.record.classify_outcome` and diagnosed with
`telemetry.diagnostics.diagnose`.

| Instrument | before (17) | after (17) |
|---|---|---|
| captured credit rows reproduce the printed credits | 13 | **14** |
| captured debit rows reproduce the printed debits | 1 | **13** |
| captured row count equals the printed item count | 0 | **13** |
| ledger identity holds | 0 | **13** |

| Cell | records | documents | before | after |
|---|---|---|---|---|
| `pnc × detail_coverage` | 14 | 14 | 0 validated / 14 withheld | **10 / 4** |
| `pnc × ledger_identity` | 2 | 2 | 0 / 2 | **2 / 0** |
| **the brief's cell** | **16** | **16** | **0 / 16** | **12 / 4** |
| `pnc × summary_identity` (adjacent, outside the assigned cell) | 1 | 1 | 0 / 1 | **1 / 0** |
| already-validated `pnc` | 28 | 28 | 28 validated | **28 validated** |

**Nothing was padded to get there.** Every document that now validates does so
because the rows extracted reproduce, independently: the bank's printed item
COUNT and total for every section it itemizes, the Balance Summary identity, the
ledger identity, and the full ADB validation suite. The fail-closed gate is
unchanged, and the four documents that stay withheld are the honest residual —
three whose text layer does not carry rows at all, and one whose cheque row OCR
did not recover.

**The already-validated population.** Old and new modules loaded side by side in
one process over identical markdown:

```
28 / 28 already-validated pnc documents : financially identical (every row's date, amount and direction)
 5 /  5 pinned corpus PNC statements    : financially identical (every audited field)
17 / 17 unclaimed PNC Bank/ folder docs : refused by both readers
```

**Descriptions moved on 28 already-validated documents and on all 5 pinned ones,
in one direction only: furniture came off.** The change is a single class — a
printed umbrella heading, a `continued on next page` trailer or a swallowed
section's heading and column header had been appended to the description of the
row above it, and is now recognised as the furniture it is (`… Amazon.Com Servi
Fcs003587716422 Checks and Other Deductions` → `… Amazon.Com Servi
Fcs003587716422`). No audited field is a description — neither audit CSV has a
description column — and every pinned statement is financially identical, so no
truth-set movement arises. It is reported here rather than buried because
downstream transaction classification reads descriptions.

### 3.7 Carried findings for Ocean

1. **P-F5 needs geometry (stop condition 4, reported not acted on).** Three
   documents emit the Date column as its own block, away from the rows it dates.
   This is RBC F11 in a second bank, and it takes the deferred geometry follow-up
   from 16 documents to **19**. Vehicle: the structurer-integration HARBOR card,
   as ruled on 2026-08-08.
2. **PNC's `Daily Balance` series is printed on every statement and is unusable
   as an oracle for exactly the same reason.** It is emitted column-major on the
   documents that would most benefit from it. Recorded so the
   `stated_daily_balances` card (§3 item 3, §B7.2, §1.8) is not assumed to be
   uniformly cheap: on PNC it is a geometry problem, not a parsing one.
3. **PNC prints an item COUNT per section, and the platform still does not check
   counts** (§5.7 item 4, §B7.3, §1.8 item 4). This is the fourth population, and
   the strongest argument yet: the count is what caught the swallowed-section
   defect here, ahead of any money check, because a swallowed section keeps the
   money in the right direction while moving the rows.
4. **The parser-level-gate asymmetry in §3.5 is a decision, not an omission**, and
   it turns on a question only Ocean can answer: is withheld→unclaimed an
   acceptable transition when the parser can prove its own reading is incomplete?
5. **`ANALYSIS_STAGE_VERSION` must be bumped at merge** (`webapp/` protected
   here). This change alters analysis output for unchanged settings on 44 of the
   45 archive `pnc` documents (13 financially, the rest by description).

## TRIO-4. Proofs

Each cell was fully proven before the next was started, on a clean tree, with
`set -o pipefail` and the exit codes as printed.

### 4.1 Cell 6 — `us_bank`, at `67689ad`

```
$ python -m pytest -q
2286 passed, 18 deselected, 1 warning in 128.00s (0:02:07)
SUITE_EXIT=0

$ python -m pytest -m corpus -q
14 passed, 2290 deselected, 1 warning in 1115.91s (0:18:35)
CORPUS_MARKED_EXIT=0

$ python corpus_gate.py
[PASS] inventory / foreign_files / source_integrity
[PASS] balance_audit / adb_audit
[PASS] balance_outcomes / adb_outcomes
[PASS] ocr_coverage / exclusions / oracle_independence
Coverage: 109 pinned PDFs (103 native text, 6 committed OCR), 0 exclusions
Outcomes: 106 PASS / 3 WITHHELD
Runtime:  445.5s
RESULT: GREEN
```

(That gate invocation was launched through a detached wrapper that did not echo
its exit code; the run printed `RESULT: GREEN` with every module PASS. The two
later gate runs, including the one over all three parsers together, capture
`GATE_EXIT=0` explicitly. Reported as it happened rather than tidied.)

```
$ python -m pytest tests/test_no_statement_hardcodes.py tests/test_r1_hardcodes.py \
      tests/test_no_parser_helper_clones.py -q
100 passed in 0.98s
GUARDS_EXIT=0
```

### 4.2 Cell 7 — `truist`, at `cf3181e`

```
$ python -m pytest -q
2299 passed, 18 deselected, 1 warning in 157.52s (0:02:37)
SUITE_EXIT=0

$ python -m pytest -m corpus -q
14 passed, 2303 deselected, 1 warning in 1012.96s (0:16:52)
CORPUS_MARKED_EXIT=0

$ python corpus_gate.py
Coverage: 109 pinned PDFs (103 native text, 6 committed OCR), 0 exclusions
Outcomes: 106 PASS / 3 WITHHELD
Runtime:  423.5s
RESULT: GREEN
GATE_EXIT=0

$ python -m pytest tests/test_no_statement_hardcodes.py tests/test_r1_hardcodes.py \
      tests/test_no_parser_helper_clones.py -q
100 passed in 0.81s
GUARDS_EXIT=0
```

The suite grew from **2,265** to **2,290** — the 25 new fixtures and nothing
else. `git diff b839bfa..HEAD --name-only -- tests/` lists exactly one file,
`tests/test_wells_variants.py`, so **no existing assertion was edited**.

**Fails-before / passes-after.** Every committed fixture document captured as
the suite runs and replayed through the pre-change module loaded from git, in
the same process. `summary` is
`(beginning, ending, stated_credits, stated_debits)`.

```
FIXED  f1_a_consumer_summary_is_read
         before  period=[null,null]  summary=[null,null,null,null]
         after   period=[2026-03-01,2026-03-31]  summary=[1000.0,1300.0,500.0,200.0]
kept   f1_the_business_vocabulary_is_unchanged
FIXED  f2_a_closed_account_prints_closing_balance             before period=[null,null]
FIXED  f3_a_summary_split_across_lines_by_furniture_is_read   before period=[null,null]
FIXED  f3_negative_a_routing_number_is_not_an_amount_cell     before period=[null,null]
         after   beginning=null - the routing number is not a money cell
kept   f4_a_withdrawal_row_is_a_magnitude[-  200.00]
kept   f4_a_withdrawal_row_is_a_magnitude[- 200.00]
FIXED  f4_a_withdrawal_row_is_a_magnitude[200.00]             before summary=[null,null,null,null]
FIXED  f4_a_withdrawal_row_is_a_magnitude[-200.00]            before summary=[null,null,null,null]
kept   f4_negative_a_printed_negative_balance_keeps_its_sign
FIXED  f5_an_edi_description_does_not_shift_the_amount_columns
         before  amounts=[1500022281.0]       after  amounts=[-590.93]
kept   f5_negative_an_ordinary_row_is_unaffected
FIXED  f6_only_the_primary_account_ledger_is_published
         before  amounts=[500.0,-200.0,-20.0]  after  amounts=[500.0,-200.0]
FIXED  f6_the_summary_published_is_the_primary_accounts        same movement
FIXED  f6_the_second_accounts_ledger_reconciles_when_it_is_the_primary
         before  account=1111111111  amounts=[500.0,-200.0,-20.0]
         after   account=2222222222  amounts=[-20.0]  summary=[50.0,30.0,0.0,20.0]
kept   f6_negative_a_single_account_statement_is_unaffected
kept   a_row_whose_amount_is_in_neither_money_column_is_dropped
FIXED  a_row_whose_amount_is_in_both_money_columns_is_dropped
         before  amounts=[500.0,8175.0]        after  amounts=[500.0]
FIXED  a_summary_cell_printed_before_its_label_is_not_claimed_by_it
         before  period=[null,null]
         after   period=[2026-06-01,2026-06-30]  summary=[null,1450000.05,null,44275.81]
kept   a_statement_with_no_ledger_publishes_nothing            before=null  after=null
kept   negative_the_transaction_history_column_header_is_not_a_summary_row
FIXED  negative_a_heading_word_inside_prose_does_not_close_the_block
         before  period=[null,null] - the old regex could not reach past the prose
kept   negative_the_ledgers_ending_daily_balance_column_is_never_a_summary_row
kept   a_period_that_crosses_new_year_dates_its_opening_to_the_prior_year
kept   the_summary_rows_are_read_even_when_the_ledger_is_printed_first

fixtures replayed: 25 | behaviour changed: 13 | unchanged: 12
```

The 12 `kept` lines are reported as what they are: **constraints**, not
demonstrations. Each pins a rule the new reader had to be built around — a
minimal synthetic document is often one the old regex happened to match, and
the point of the fixture is that the new rule still reads it the same way.
Three are explicit about it: the two signed forms of `f4` are the contrast
halves of the unsigned pair, and only the four together prove the rule is the
label's rather than the glyph's; `a_row_whose_amount_is_in_neither_money_column`
pins a fail-closed rule the old code also had, which the restructuring had to
preserve rather than widen; and
`negative_the_transaction_history_column_header_is_not_a_summary_row` guards
the hazard the label reader introduces — `Deposits/ Credits` is also the
ledger's printed column header, and the block boundary is what keeps it out.

**Archive differential**, old and new module loaded side by side over all 233
`wells_fargo` archive documents, every field of the serialised statement
compared (read-only; the rendered markdown is cached in local scratch, never
committed, and only aggregate counts are reported):

```
period_integrity      n= 22  moved 22   (period_start 22, period_end 22, beginning 21,
                                         ending 22, stated_credits 21, stated_debits 22)
detail_coverage       n= 13  moved 13   (no summary field moved; the row set is scoped
                                         to the published account and the EDI rows read)
balance_continuity    n=  5  moved  5   (same)
posting_date_coverage n=  1  identical
already validated     n=192  identical 192  (0 financial, 0 description)
```

**Commits (oldest first)**

| Commit | Contents |
|---|---|
| `07c21fb` | `analysis/wells.py` + `tests/test_wells_variants.py` |
| `71d1e03` | this log's §WELLS |
100 passed in 0.82s
GUARDS_EXIT=0
```

### 4.3 Cell 8 — `pnc`, at `306f2ac` (all three parsers together)

```
$ python -m pytest -q
2311 passed, 18 deselected, 1 warning in 100.36s (0:01:40)
SUITE_EXIT=0

$ python -m pytest -m corpus -q
14 passed, 2315 deselected, 1 warning in 811.29s (0:13:31)
CORPUS_MARKED_EXIT=0

$ python corpus_gate.py
Coverage: 109 pinned PDFs (103 native text, 6 committed OCR), 0 exclusions
Outcomes: 106 PASS / 3 WITHHELD
Runtime:  361.4s
RESULT: GREEN
GATE_EXIT=0

$ python -m pytest tests/test_no_statement_hardcodes.py tests/test_r1_hardcodes.py \
      tests/test_no_parser_helper_clones.py -q
100 passed in 0.78s
GUARDS_EXIT=0
```

### 4.4 The suite grew by the fixtures and by nothing else

Baseline at `b839bfa`: **2,265** default tests. Final: **2,311** — the 46 new
fixtures (21 us_bank + 13 truist + 12 pnc) and nothing else.
`git diff b839bfa..HEAD --name-only -- tests/` lists exactly the three new files,
so **no existing assertion was edited**, and
`git diff b839bfa..HEAD --name-only` lists exactly seven paths: the three
parsers, the three new test files and this log.

### 4.5 Combined result over the three parsers

Measured on the final tree over every `us_bank`, `truist` and `pnc` document in
the baseline run, through the same production ladder discovery uses
(`ocr.pipeline.parse_statement`, native rung plus the cached local-Tesseract read
for the one scanned PNC document, no visual rung, no model calls, `$0.00`), then
`analyze_markdown` in deterministic mode, classified with
`telemetry.record.classify_outcome`:

| Parser | already validated | withheld → validated | still withheld |
|---|---|---|---|
| `us_bank` | 20 → **20** | **20** | 0 |
| `truist` | 28 → **28** | **20** | 0 |
| `pnc` | 28 → **28** | **13** | 4 |
| **total** | **76 → 76** | **53** | **4** |

**withheld → validated 53 · regressed 0 · transitions in any other direction 0.**

The four that remain are the honest residual and each is named with its cause in
§3.4: three PNC documents whose text layer emits the Date column away from the
rows it dates (geometry, RBC F11's family in a second bank), and one scanned PNC
document whose single cheque row local OCR did not recover.

### 4.6 Fails-before / passes-after

Every committed fixture document captured as its suite runs and replayed through
the pre-change module loaded from git, in the same process.

**`us_bank`** (14 distinct fixture documents · behaviour changed 8 · unchanged 6):

```
FIXED  test_f1_a_summary_category_outside_the_old_list_is_read    before=[500.0, -80.0]  after=[500.0, -70.0, -50.0, -80.0]
FIXED  test_f1_every_printed_credit_category[Card Deposits]       before=[500.0, -80.0]  after=[500.0, 400.0, -80.0]
FIXED  test_f1_every_printed_credit_category[Customer Deposits]   before=[400.0, 500.0, -80.0]  after=[500.0, 400.0, -80.0]
FIXED  test_f1_negative_an_unreadable_printed_category_fails_clos before=[500.0, -80.0]  after=None
kept   test_f1_negative_a_section_that_does_not_reproduce_its_pri before=None  after=None
FIXED  test_f2_a_card_section_split_over_several_card_sub_blocks_ before=[500.0, -80.0]  after=[500.0, -70.0, -50.0, -80.0]
FIXED  test_f3_several_check_column_groups_on_one_printed_line_ar before=[500.0, -80.0]  after=[500.0, -80.0, -100.0, -200.0, -300.0]
FIXED  test_f4_an_original_currency_figure_below_the_amount_cell_ before=[500.0, -80.0]  after=[500.0, -54.63, -80.0]
kept   test_f4_negative_a_wrapped_amount_cell_alone_on_its_line_i before=[500.0, -80.0]  after=[500.0, -80.0]
kept   test_f5_two_printed_rows_on_one_physical_line_are_two_rows before=[500.0, -6000.0, -11000.0]  after=[500.0, -6000.0, -11000.0]
FIXED  test_f5_negative_a_date_inside_a_description_does_not_open before=None  after=[500.0, -250.0]
kept   test_f7_a_section_continues_across_a_page_break_and_the_le before=[500.0, -100.0, -200.0]  after=[500.0, -100.0, -200.0]
kept   test_f7_negative_the_balance_summary_series_is_never_activ before=[500.0, -80.0]  after=[500.0, -80.0]
kept   test_f8_an_overdrawn_balance_prints_its_minus_after_the_fi before=[500.0, -1700.0]  after=[500.0, -1700.0]
```

**`truist`** (10 distinct fixture documents · behaviour changed 6 · unchanged 4):

```
FIXED  test_f1_the_checks_table_is_read[symbol apart from figure] before=[-200.0, 500.0]  after=[-100.0, -200.0, -200.0, 500.0]
kept   test_f1_the_checks_table_is_read[symbol against figure]    before=[-100.0, -200.0, -200.0, 500.0]  after=[-100.0, -200.0, -200.0, 500.0]
FIXED  test_f2_a_detached_skip_marker_still_belongs_to_its_check_ before=[-200.0, 500.0]  after=[-100.0, -200.0, -200.0, 500.0]
kept   test_f2_an_attached_skip_marker_is_unchanged               before=[-100.0, -200.0, -200.0, 500.0]  after=[-100.0, -200.0, -200.0, 500.0]
FIXED  test_f2_negative_the_skip_footnote_is_never_a_row          before=[-200.0, 500.0]  after=[-300.0, -200.0, 500.0]
FIXED  test_f3_a_cheque_with_no_printed_number_is_still_a_cheque  before=[-200.0, 500.0]  after=[-100.0, -200.0, -200.0, 500.0]
FIXED  test_f3_a_skip_marker_with_no_number_beside_it             before=[-200.0, 500.0]  after=[-100.0, -200.0, -200.0, 500.0]
kept   test_f4_a_three_column_checks_header_is_read               before=[-100.0, -150.0, -50.0, -200.0, 500.0]  after=(same)
FIXED  test_f5_negative_checks_that_do_not_reproduce_the_printed_ before=[-200.0, 500.0]  after=None
kept   test_f5_negative_a_statement_with_no_checks_table_is_unaff before=[-200.0, 500.0]  after=[-200.0, 500.0]
```

**`pnc`** (7 distinct fixture documents · behaviour changed 7 · unchanged 0).
Amounts alone do not show two of PNC's families, so the shape compared here is
`(amounts, directions, ending balance, descriptions)`:

```
FIXED  test_f1_a_printed_section_outside_the_old_vocabulary_is_read
       before desc=['ATM Deposit A Branch 000000001 Fee Refunds', 'A Fee Reimbursement 000000002 Checks and Other Deductions', ...]
       after  desc=['ATM Deposit A Branch 000000001', 'A Fee Reimbursement 000000002', ...]
FIXED  test_f1_a_swallowed_section_would_take_the_wrong_direction
       before=([-300.0, -100.0], ['debit', 'debit'])   after=([100.0, -300.0], ['credit', 'debit'])
FIXED  test_f2_several_cheque_column_groups_on_one_printed_line_are_separate_rows
       before=([500.0])  after=([500.0, -50.0, -250.0, -300.0], desc ['Deposit …', 'Check 1100*', 'Check 1101', 'Check 1102'])
FIXED  test_f3_the_gap_footnote_printed_on_the_heading_line_does_not_hide_the_section
       before=([500.0])  after=([500.0, -600.0])
FIXED  test_f3_negative_a_heading_still_owns_its_line
       before desc=['… 000000001 Checks and Other Deductions', …]   after desc=['… 000000001', …]
FIXED  test_f3_the_continued_on_next_page_trailer_is_furniture_not_description
       before desc=['Deposit 000000001 Deposits continued on next page', …]  after desc=['Deposit 000000001', …]
FIXED  test_f4_a_closing_balance_of_less_than_a_dollar_is_read_as_the_closing_balance
       before ending=900.0   after ending=0.87
```

The `kept` lines are reported as what they are: **constraints**, not
demonstrations. Each pins a rule the new reader had to be built around — a
minimal synthetic document is often one the old reader happened to read
correctly, and the point of the fixture is that the new rule still does. Two are
explicit contrast halves of a pair (`us_bank` F4's wrapped amount cell against
its foreign-currency twin; `truist` F1's two spellings of the same total, which
are additionally asserted to produce the identical statement).

### 4.7 Commits (oldest first)

| Commit | Contents |
|---|---|
| `67689ad` | `analysis/us_bank.py` + `tests/test_us_bank_variants.py` |
| `0f559c5` | this log's §TRIO-0 and §TRIO-1 |
| `cf3181e` | `analysis/truist.py` + `tests/test_truist_variants.py` |
| `403e95e` | this log's §TRIO-2 |
| `306f2ac` | `analysis/pnc.py` + `tests/test_pnc_variants.py` |
| `007d255` | this log's §TRIO-3 |
| (this one) | §TRIO-4, the proofs |

## TRIO-5. Carried findings across the three cells

Per-cell findings are in §1.8, §2.7 and §3.7. Four are worth stating once, across
all three:

1. **`stated_credit_count` / `stated_debit_count` — the count check (§5.7 item 4,
   §B7.3) now has three more witnesses and one decisive one.** U.S. Bank prints a
   count per summary category and PNC prints an item count per section; Truist
   prints neither. PNC is the decisive case: a *swallowed* section keeps its money
   on the correct side while moving the rows, so the money checks see nothing and
   only the count notices. Every cell in Track A that has looked has found the
   same gap.
2. **The geometry queue grows to 19 documents.** The three PNC P-F5 documents are
   RBC F11 in a second bank — the Date column emitted as its own block, away from
   the rows it dates. Same vehicle (the structurer-integration HARBOR card), same
   ruling, three more documents.
3. **A daily-balance oracle is not uniformly cheap.** U.S. Bank's `Balance
   Summary` is the cleanest such series Track A has met and it settled every
   question cell 6 raised; PNC's `Daily Balance` is printed on every statement and
   is *unusable* without geometry, because it is emitted column-major. The
   `stated_daily_balances` card (§3 item 3, §B7.2) should be scoped per bank
   rather than as one sweep.
4. **Silent-rigidity defects keep costing whole cells.** Cell 6 was a closed
   category list; cell 7 was a currency symbol admitted in only one of its two
   printed spellings; cell 8 was a section list that was also, unnoticed, the
   boundary list. None of the three announced itself: each simply produced a
   smaller ledger. A sweep for the *shape* — a pattern that is both a matcher and
   a terminator, or a closed vocabulary of the bank's own words — across the
   remaining parsers looks like high-value, low-risk work.

---

# §BMO-LAYOUTS — Cell 9, and the first cell of a new work class: `BMO × no_parser_matched`, 164 documents

REEF-BMO-LAYOUTS, 2026-08-10. Branch `wave3-bmo-layouts`, base `bb7d644` (main
`181e131` plus the two handoff files). Brief:
`docs/agent-handoffs/REEF-BMO-LAYOUTS.md`.

The new class is **unclaimed layouts of known banks**. Every Track A cell so far
worked documents a parser already claimed and failed to validate. This one works
documents no registration claimed at all, so the first question is not "what did
the extractor get wrong" but "how many different printed documents are in this
folder, and which of them is our platform even the right shape for". The method
is otherwise §BOFA's, in the same order: reproduce the cell independently,
characterise the layout families structurally BEFORE changing code, build the
in-document instrument and validate the instrument, fix at the capability level
or fail closed with the volume stated, prove both directions with synthetic
fixtures, measure honestly.

## M0. Summary

| | |
|---|---|
| Cell worked | `folder_label == "BMO"` × `outcome_class == failed` (`no_parser_matched`) in run `52b4b2b2`: **179 records, 164 distinct content hashes** (15 duplicate records). |
| Families found | **6.** Three are BMO statement layouts (160 documents); three are not this platform's problem (4 documents). Table in §M3. |
| Result over the cell | **154 / 164 newly CLAIMED; 128 / 164 newly VALIDATED**, from 0 and 0. 23 claimed-and-blocked, 3 claimed-and-withheld, 10 fail-closed. Nothing was ambiguous and nothing crashed. |
| The honest headline | The validated number is **128, not 154**. 23 of the 26 claimed-but-not-validated documents reconcile perfectly and are held by a false positive in a protected module (§M6.1) — a finding, not a success. |
| Registrations added | 3: `bmo_ca_business`, `bmo_ca_business_french`, `bmo_us_activity`. Registry 46 → 49. |
| Existing `bmo` registration | Unchanged. `analysis/bmo.py` is not modified. Its four archive documents are still claimed by it alone, still withheld, still `source_contradiction`, same transaction counts (§M5.3). |
| Statement-specific constants added | **none.** Every marker is R-4b issuer furniture; every extraction rule is anchored on the printed grid. |
| Protected modules touched | none. No shared utility, no registry machinery, no pipeline, no other parser, no `ocr/`, no truth-set movement. |
| Files changed | `analysis/bmo_ca_business.py` (new), `analysis/bmo_us_activity.py` (new), `analysis/parser_registry_entries.py` (3 entries + 3 overrides), `tests/test_bmo_layouts.py` (new, 38 fixtures), `tests/data/parser_conformance_fixtures.py` (+3), the two registry-count pins, and this log. Seven files, four of them new. |
| Cache implication | New parsers change deterministic output for these documents, so `ANALYSIS_STAGE_VERSION` must be bumped at merge. **Ocean's, not done here.** |

## M1. The cell reproduced independently

Reading run `52b4b2b2`'s `rows.csv` directly, and counting distinct
`content_sha256` as well as records:

| | records | distinct documents |
|---|---|---|
| whole run | 3,506 | 3,380 |
| validated | 1,666 | **1,622** |
| withheld | 59 | **58** |
| review / deferred | 10 / 13 | 10 / 13 |
| failed | 1,758 | 1,677 |

The distinct-document column reproduces the brief's `1,622 / 58` exactly, which
fixes the denominator: **every count in this section is distinct documents
unless it says records.**

The `BMO/` folder holds 184 records / 169 distinct documents:

| BMO folder | records | documents | note |
|---|---|---|---|
| `failed` / `no_parser_matched` | 179 | **164** | the cell |
| `withheld` | 4 | 4 | claimed by `bmo`, all `source_contradiction` |
| `deferred` | 1 | 1 | a voided-cheque image, deferred by the tranche |

The brief expected ≈176–178; the measured cell is **179 records / 164 distinct
documents**. 164 is also the figure `PROJECT_STATUS.md` carries ("BMO 164"), so
the brief's range was counting records and excluding the scanned one.

**One correction to the brief, reported rather than reconciled away.** The brief
states that BMO's validated base is "only ~4 archive docs". Measured: the `bmo`
registration claims exactly 4 documents in the entire run, **all four withheld**
with `source_contradiction`. BMO's validated base in run `52b4b2b2` is **zero**.
The four are one customer's four consecutive monthly statements, one of which is
the pinned corpus document; they are a genuinely self-contradictory set and
their withholding is correct. This does not change the cell, but it means the
"before" for every BMO figure in this section is 0, and it means
`analysis/bmo.py` has no validated document anywhere to regress.

Every one of the 164 carries `near_miss` evidence naming `bmo` at `0.166667` —
one of the pre-existing registration's markers (the bank name) firing and
`ACCOUNT SUMMARY TOTALS` not. That is the shape of the whole cell: BMO's name is
everywhere, and BMO's `ACCOUNT SUMMARY TOTALS` heading is on **0 of 164**.

## M2. The measurement instrument (built and validated before any code changed)

The 164 documents were rendered read-only through the production ladder
(`ocr.pipeline.parse_statement`, native rung, `allow_local_ocr=False`,
`allow_visual_ocr=False` — no OCR, no model calls, `$0.00`), cached in local
scratch and never committed. Only aggregates are reported here; no customer,
amount or date from the archive appears in this document or in any fixture.

Grouping by structural signature over that text gave the families in §M3. For
each of the three statement families, the instrument is what the document
asserts about itself, and it was validated on the archive text **before** a line
of parser code existed:

**Family A / C** — the `Summary of account` row prints
`opening | total debited | total credited | closing`. On the 127 documents whose
text layer is clean the identity `opening − debited + credited = closing` holds
**127 / 127**; the ledger's own `Closing totals` row re-prints the same two
totals and agrees with the summary row **127 / 127**; `Number of items
processed` parses **127 / 127**. Three independent printings, mutually
consistent on every document — that is what made it safe to build on.

**Family B** — the summary row prints
`BEGINNING BALANCE | NUMBER OF DEPOSITS | DEPOSIT AMOUNT | NUMBER OF WITHDRAWALS | WITHDRAWAL AMOUNT | SERVICE CHARGES | ENDING BALANCE`.
`begin + deposits − withdrawals − charges = end` holds **23 / 23**.

The baseline against that instrument is zero on every line by construction:
nothing claimed these documents, so no ledger existed to compare.

## M3. The families — the deliverable, and what drove everything

Named by structure. Nothing below names a customer, a bank product, an amount or
a date; every rule is anchored on the printed grid.

| # | Family | Structural signature | Root cause | Ruling | Volume |
|---|---|---|---|---|---|
| **A** | BMO Canada `Business Banking statement` | `bmo.com` · `Business Banking statement` · `Summary of account` (one row: opening / debited / credited / closing) · ledger columns `Amounts debited from your account ($)` / `Amounts credited to your account ($)` / `Balance ($)` · `Closing totals` · `Number of items processed` | **both** — never claimed (no `ACCOUNT SUMMARY TOTALS`), and the four-column grid is not the grid `analysis/bmo.py` reads | new registration `bmo_ca_business` | **133** (127 clean + 6 → E3) |
| **C** | the same statement, French edition | `bmo.com` · `Relevé de services bancaires aux entreprises` · `Sommaire de votre compte` · `Montants déduits` / `Montants ajoutés` · `Totaux à la fermeture` · FR-CA money `7 227,65` · French Date column `1er mai`, `02 Avr` | **both** — same grid, different printed vocabulary and a different number grammar | new registration `bmo_ca_business_french` (precedent: `rbc_french`) | **4** |
| **B** | BMO Bank N.A. (US) `Monthly Activity Details` | `BMO BANK N.A.` · `bmo.com/contact` · `Account Summary - … #…` with `BEGINNING BALANCE AS OF` · grid `Date · Transaction description · Withdrawal · Deposit · Balance` · bracketed withdrawals `($300.00)` · `ENDING BALANCE` terminator | **both** — a different institution's statement format entirely | new registration `bmo_us_activity` | **23** |
| **E3** | family A with a **degraded text layer** | the same furniture, but the glyph stream is corrupt: `Closing tobls`, `De.posit`, `S0,000.00` for `50,000.00`, `010` for `0.10` | **unusable input** — the money tokens themselves are wrong, so no arithmetic could be trusted | **FAIL CLOSED BY DESIGN**: detected, then declined at parse. Reported as `unclaimed` with `attempted=['bmo_ca_business']` — "detected, then declined", which is the honest signal | **6** |
| **E1/E2** | no readable text layer | one scanned deposit notice with an empty native text layer; one PDF whose embedded font has no usable encoding, so the text layer decodes to mojibake | **unusable input** (E1 is also **scanned — the OCR path, and out of scope**) | **FAIL CLOSED BY DESIGN**, volumes stated | **2** |
| **D** | not this statement class | a payroll stub; a BMO online-banking `Detail Report - by Processing Date` — a transaction export with no summary, no period balances and no running balance | **not a bank statement** (the export is the BMO analogue of `chase_export`) | **NO CHANGE.** One document does not justify a registration, and building one would be corpus-fitting. Volume reported; see §M6.4 | **2** |

The single fact that ruled family A/C's "detection" half: **`ACCOUNT SUMMARY
TOTALS` appears on 0 of the 164**, and `analysis/bmo.py` requires it. The
extraction half is equally clear: the flattened text of an A row carries
`<date> <description> <amount> <balance>` — one money cell, not two — so a
parser built for a `Withdrawal | Deposit | Balance` grid could not have read it
even if it had claimed it.

### M3.1 The rules the families produced

* **Direction from the printed Balance column (A/C).** Which of the two money
  columns a cell stood in is destroyed by flattening and recoverable from the
  grid: the balance printed on the row is the balance *after* the row, so the
  movement between consecutive printed balances orients the row. The magnitude
  published is still the one BMO printed, so a row this rule reads wrongly
  produces a **continuity break** the fail-closed gate sees — it does not
  produce a ledger that balances with itself. `test_f9` is the adversarial
  fixture that pins exactly that.
* **Direction is printed, not inferred (B).** This layout brackets a withdrawal.
  No vocabulary, no arithmetic; the day-end balances check it.
* **`Closing totals` / `Totaux à la fermeture` ends the grid** (`group_rows`
  rule 3). It is a printed section total, and reading it as a row doubles the
  ledger.
* **The last two money cells are the row's amount and balance.** BMO prints unit
  prices and exchange-rate operands *inside* the Description column
  (`13 ITMS AT 1.25`, `AT1.3285 HC $0.00,`); they stand to the left of the money
  columns and are therefore never among the last two cells.
* **Inter-word spacing is a property of the text layer, not of the statement.**
  Some PDFs render the same furniture as `Forthe period ending April30, 2026`.
  Every space in the furniture patterns is optional; **no money or date token is
  relaxed** — only the gaps between words — and the ledger identity still has to
  close. This recovered one document; it is a structural rule, not a fix for it.
* **The period starts where the opening-balance row is dated.** It is the only
  start the A/C statement prints, and it can fall in the previous calendar year.

Negative fixtures — each constrains a new rule rather than demonstrating a
defect:

* the pre-existing `bmo` layout is claimed by none of the three new
  registrations, and none of the three new layouts is claimed by `bmo`;
* the French edition is not claimed by the English registration, and vice versa;
* the Canadian and US layouts do not claim each other;
* `bmo.com` and `bmo.com/contact` appearing in a *transaction line* on another
  bank's statement is not a claim — the single-marker invariant, stated per
  registration;
* a header with no ledger is not parsed, at the parser level as well as through
  the registry's self-invalidation check;
* all four BMO layouts resolve to exactly one claimant each, with
  `len(candidates) == 1` — the ambiguity protection exercised rather than
  assumed.

### M3.2 What did NOT change, deliberately

* **`analysis/bmo.py` is untouched.** Its `_WITHDRAWAL_KEYS` description
  vocabulary is exactly the construct §TD/§5/§BOFA deleted elsewhere, and the
  new parsers need no equivalent — but it is reached only when contradictory
  printed balances make direction uninferable, which is precisely the state of
  the one pinned corpus document, and that document's withheld diagnosis is a
  correctness property. Removing it is a change to a withheld document's
  behaviour with no validated document to prove it against. Carried to Ocean as
  §M6.3 rather than done here.
* **No shared utility's behaviour changed**, so no R-2 differential-equivalence
  proof is owed. `group_rows` is consumed with caller-supplied predicates, as
  designed; `parse_french_amount`, `parse_grouped_float`, `compact_whitespace`
  and `normalize_mojibake` are consumed unmodified.
* **No `supersedes` edge and no band change.** All three registrations sit at
  band 100. Precedence would be the wrong tool: the layouts are disjoint, and
  §M5.3 proves it rather than asserting it.
* **The HTML-table path is untouched** — no document in this cell uses it.
* **Description continuation lines in family B are not folded into the
  description.** `RECORD NO. …`, the card number and the merchant location print
  under the row and are real description text, but so is the repeated page
  furniture between them, and separating the two would need a list of BMO's
  furniture wordings. Left as a carried finding (§M6.5) rather than guessed at.

## M4. The two defects the family measurement caught in this cell's own code

Reported as they happened rather than tidied:

1. **The description ended at the last place the amount's text occurred.**
   `INTERAC e-Transfer Sent 200.00 1,200.00` prints the amount `200.00`, and
   those same characters occur again *inside* the balance beside it, so three
   characters of the money columns leaked into every such description. Money
   cells are now carried as match objects and sliced by position. `test_f5`.
2. **The item-count line prints one number, not two, when a money column carried
   nothing all period** — and the dotted leader that would have held the second
   runs to the end of the line. "The first two digit runs" split `23` into 2 and
   3, and on one document reached forward into the following `Number of cheques
   or related items enclosed…` line. The line's numbers are now read and paired
   with the columns that carry a total. `test_f4`. This one is the reason the
   instrument is worth running twice: the money was already exact when the
   counts were wrong.

## M5. Result over the cell

### M5.1 The instrument, before → after

| Family A — 127 claimed of 133 | before | after |
|---|---|---|
| summary row closes (`opening − debited + credited = closing`) | 0 / 127 | **127 / 127** |
| captured debits reproduce the printed debited total | 0 / 127 | **127 / 127** |
| captured credits reproduce the printed credited total | 0 / 127 | **127 / 127** |
| captured debit rows equal the printed item count | 0 / 127 | **127 / 127** |
| captured credit rows equal the printed item count | 0 / 127 | **127 / 127** |
| every printed running balance follows from the row above | 0 / 127 | **127 / 127** |

| Family C — 4 of 4 | before | after |
|---|---|---|
| all six of the above | 0 / 4 | **4 / 4** |

| Family B — 23 of 23 | before | after |
|---|---|---|
| summary row closes (`begin + deposits − withdrawals − charges = end`) | 0 / 23 | **23 / 23** |
| captured withdrawals reproduce the printed withdrawal total | 0 / 23 | **23 / 23** |
| captured deposits reproduce the printed deposit total | 0 / 23 | **23 / 23** |
| captured withdrawal rows equal the printed count | 0 / 23 | 19 / 23 |
| captured deposit rows equal the printed count | 0 / 23 | 22 / 23 |

The two count lines are the honest residual of family B and are reported as
such: the money reproduces exactly on all 23, and BMO's item counter and the
ledger's row count differ by one or two on five of them. One cause is visible —
a printed `$0.00` row (`NON-BMO ATM INQUIRY`) is a ledger row BMO does not count
as an item; the rest is not yet characterised. Nothing in validation reads these
counts, and the count that is published is the bank's printed one.

### M5.2 The cell, before → after

| Family | documents | claimed before → after | validated before → after | remainder |
|---|---|---|---|---|
| A — BMO Canada Business Banking (EN) | 133 | 0 → **127** | 0 → **124** | 3 withheld · 6 fail-closed |
| C — BMO Canada Business Banking (FR) | 4 | 0 → **4** | 0 → **4** | — |
| B — BMO Bank N.A. Monthly Activity | 23 | 0 → **23** | 0 → **0** | 23 blocked in `review` |
| D — not this statement class | 2 | 0 → 0 | 0 → 0 | 2 unclaimed by design |
| E1/E2 — no readable text layer | 2 | 0 → 0 | 0 → 0 | 2 unclaimed |
| **total (documents)** | **164** | **0 → 154** | **0 → 128** | 26 claimed-not-validated · 10 fail-closed |
| **total (records)** | **179** | — | **0 → 140** | 26 review · 3 withheld · 10 failed |

Ambiguous dispatches: **0.** Parser exceptions: **0.**

**Nothing was padded to get there.** Every document that now validates does so
because the rows extracted reproduce, independently: the `Summary of account`
identity BMO prints, the `Closing totals` row BMO prints a second time, the item
counts BMO prints, and every printed running balance in the Balance column —
or, for family B, the summary row's two totals, two counts and service charge.
The fail-closed gate is unchanged; these documents pass it on their own
arithmetic.

**Claimed but not validated — 26 documents, both causes named:**

| n | class | diagnosis | cause |
|---|---|---|---|
| 23 | `review` / `integrity_flags` | `missing_declared_statement_page` | a false positive in `analysis/pipeline.py` — §M6.1. Every one of the 23 reconciles perfectly: `recon.ok`, coverage 1.000 / 1.000, zero continuity breaks, `sum_delta 0.00` |
| 3 | `withheld` / `withheld_adb` | `posting_date_coverage` | a false positive in `analysis/dates.py::source_posting_dates` — §M6.2 |

**Fail-closed — 10 documents, by design:** 6 with a corrupt text layer (detected,
declined, `attempted=['bmo_ca_business']`), 1 scanned with no native text, 1 with
an undecodable font encoding, 2 that are not this statement class.

### M5.3 Regressions — zero, and the evidence

* **The four documents the `bmo` registration claims today**: still
  `outcome=claimed`, `parser=bmo`, `candidates=(('bmo', 0.5),)` — a single
  claimant, so nothing became ambiguous — still `withheld` with
  `primary_class=source_contradiction`, and the same transaction counts
  (57 / 55 / 41 / 57). The three new registrations do not appear in their top
  four detections at all.
* **The pinned corpus**: `python -m pytest -m corpus -q` and `python
  corpus_gate.py` both green, 106 PASS / 3 WITHHELD, same three by name —
  including `BMO_Statement_January_2026 Final-1-2 (1).pdf` with its
  `source_contradiction` diagnosis intact (§M7).
* **Cross-bank**: a read-only stratified sample of the frozen archive — up to 12
  digital documents from each of the 64 non-BMO folders, validated ones first,
  **more than 400 documents** — produced **zero claims** by any of the three new
  registrations. The highest score any of them reached outside `BMO/` was
  **0.1**, one required marker of four, a fifth of the way to the threshold.
* **The conformance cross-product**: 49 × 48 fixture pairs, **zero cross-claims**;
  the single-marker invariant holds for all three new registrations (four
  required markers each); SOURCE-comment invariance holds; both
  `COUNTERPARTY_VULNERABLE` and `FILENAME_DEPENDENT_PARSERS` remain empty.
* **The suite**: 2,336 → **2,410**, and by nothing else. The growth is the 38
  fixtures in `tests/test_bmo_layouts.py` plus 36 tests the conformance and
  registry modules generate by *enumerating* the registry, which is what those
  modules are for. No existing assertion was edited: the only changes to
  existing test files are the two registration-count pins, the dispatch-order
  list, one added `by_bank_label` pin and three conformance fixtures — the R-4
  idiom for adding a registration.

## M6. Carried findings and questions for Ocean

### M6.1 `missing_declared_statement_page` reads BMO's page footer as a page declaration — 23 documents, one line, zero regression risk

`analysis/pipeline.py` finds declared pages with
`re.findall(r"\bPage\s*:?\s*(\d+)\s+of\s+(\d+)\b", markdown, re.IGNORECASE)`.
BMO Bank N.A. prints `CONTINUED ON NEXT PAGE` immediately above its page number,
so the flattened text reads `…NEXT PAGE` / `2 of 20` — and the heuristic reads
the last word of one sentence plus the first line of the next as "Page 2 of 20".
It therefore declares a 20-page statement, finds pages 2–18 (the pages that carry
that footer) and reports pages 1, 19 and 20 "absent from the supplied PDF". All
20 pages are present.

Measured, not asserted: with the pattern changed to `(?<!NEXT )\bPage…`,
monkey-patched **in a scratch script only**, all 23 documents move from
`review / integrity_flags` to `validated / approved`. As shipped: 23 review, 0
validated.

`analysis/pipeline.py` is protected and this cell did not touch it. The proposed
change is a negative lookbehind, which can only *remove* matches and therefore
can only *remove* the flag: it cannot turn a validated document into a flagged
one. **Requested: a ruling, and a gate run to confirm no pinned document
currently depends on the flag.** This is the difference between the cell's
headline being 128 and 151.

### M6.2 `source_posting_dates` counts a printed section total as a posting date — 3 documents

`analysis/dates.py::_NOT_A_POSTING_ROW` excludes `total(s)? for` but not a bare
`totals`, so `Apr 30 Closing totals 8,051.66 2,245.03` is counted as a posting on
Apr 30. On three documents the closing-totals date carries no actual posting, so
`posting_dates_cover_source` fails and ADB is correctly refused — for the wrong
reason. `analysis/dates.py` is a shared utility and this cell did not touch it.
The structural generalisation is `total(s)?\b` rather than a BMO wording; that
is a shared-utility change and therefore Ocean's, with a differential-equivalence
proof owed. Volume: 3 documents in this cell, and the class ("a printed section
total dated in the Date column") will recur in every ledger layout that prints
one.

### M6.3 `analysis/bmo.py`'s `_WITHDRAWAL_KEYS` is the last description vocabulary in the BMO family

14 description literals, reached only when contradictory printed balances make
direction uninferable — i.e. only on the four self-contradictory documents,
which stay withheld either way. The three new parsers demonstrate that the same
job is done by the printed Balance column with no vocabulary at all. Removing it
changes a withheld document's transactions with no validated document to prove
the change against, so it is proposed rather than done. Ruling requested.

### M6.4 BMO prints an online-banking transaction export, exactly as Chase does

`Detail Report - by Processing Date` — per-account sections, `Date · Transaction
Description · Cust Ref · Bank Ref · Debit · Credit`, no summary, no period
balances, no running balance. One document in this cell. It is the same document
class as `chase_export`, and the registry already models it
(`formal_statement=False` plus the two informal notes). Not built: one document
cannot evidence a registration, and the R-3 standard would have it fitted to a
corpus of one. Queued as a card for whenever the volume justifies it.

### M6.5 Family B's merchant detail lines are available and are not being used

`RECORD NO. …`, the card number and the merchant/location line print under each
row in the Description column and carry the counterparty name — which is what
downstream classification actually reads. They are currently dropped, because
the same continuation region also carries the repeated page header and footer,
and separating the two structurally needs something better than a list of BMO's
furniture wordings. `POS PURCHASE` is a truthful but weak description. This is a
description-quality card, not a correctness one; flagged because §BOFA
established that description movement is reported, not buried.

### M6.6 The count check gains a ninth witness, and family B is its first partial failure

Both BMO layouts print item counts. On the 131 Canadian documents the counts and
the ledger rows agree 131 / 131 — after the defect in §M4 item 2 was fixed, and
the counts are what caught it. On the 23 US documents they disagree by one or two
on five. Every Track A cell that has looked has found this check earns its place;
this is the first cell where it disagrees on documents whose money is exact.

### M6.7 The new work class is bounded by the platform, not by layout knowledge

Of the 164 documents in this cell, layout knowledge was the binding constraint on
128. For 26 more the layout is fully read and the block is elsewhere in the
platform (§M6.1, §M6.2); for 10 the input itself is unusable. If the
unclaimed-layout class behaves like this generally, the next cells' yield will
depend at least as much on clearing platform-level false positives as on writing
parsers.

### M6.8 The three new registrations claim no pinned corpus document

Their only coverage is `tests/test_bmo_layouts.py` and the R-4 conformance
fixtures — the same status `demo_national` has, and stated here rather than
discovered later. `tests/data/parser_expectations.json` and
`tools/record_parser_expectations.py::PIPELINE_ENTRY_POINTS` are the pre-R-3
or-chain baseline, deliberately **not** extended: that file records what the
chain did on the pinned 109, and adding parsers that claim none of them would
make it a record of something else. Its tests pass unchanged, and the divergence
from the registry (49 vs 46 ids) is now three, not zero — noted so it is a
decision rather than a drift.

### M6.9 The registration count is documented in four historical places

`tests/test_parser_conformance.py` says "update this count and the docs
together", and this is the first cell to add a registration. The count moved
46 → 49 in both pinned tests and is stated here. `R4_CONFORMANCE_FINDINGS.md`
(`46 × 45`, "all 46 registrations"), `R3_DETECTION_FINDING.md`, `H3_SCHEMA.md`
and `WAVE2_EXECUTION_LOG.md` still say 46. They are records of what was true when
they were written and this cell's scope does not include them; flagged so the
decision — annotate or leave as history — is made rather than defaulted.

### M6.10 `ANALYSIS_STAGE_VERSION`

Must be bumped at merge — `webapp/` is protected and this is Ocean's, not done
here.

## M7. Proofs

Run on a clean tree at `a990e95`, the last commit touching code or tests.

```
$ git status --short
$ git rev-parse --short HEAD
a990e95

$ set -o pipefail; python -m pytest -q
2410 passed, 18 deselected, 1 warning in 150.24s (0:02:30)
SUITE_EXIT=0

$ python -m pytest tests/test_no_statement_hardcodes.py tests/test_r1_hardcodes.py \
      tests/test_no_parser_helper_clones.py -q
100 passed in 0.97s
GUARDS_EXIT=0

$ python -m pytest tests/test_parser_conformance.py tests/test_parser_registry_entries.py \
      tests/test_parser_parity.py tests/test_parser_detection_markers.py \
      tests/test_bmo_layouts.py -q
698 passed, 9 deselected in 1.20s
R34_EXIT=0

$ set -o pipefail; python -m pytest -m corpus -q
14 passed, 2414 deselected, 1 warning in 940.66s (0:15:40)
CORPUS_MARKED_EXIT=0

$ python corpus_gate.py
Corpus gate

[PASS] inventory: 109 pinned corpus PDFs, all on disk and audited by both oracles
[PASS] foreign_files: no non-corpus PDFs under the corpus root
[PASS] source_integrity: 109/109 pinned source PDFs match their pinned SHA-256
[PASS] balance_audit: 109 statements reproduce every audited balance field across backend, API, dashboard, CSV, XLSX, and package surfaces
[PASS] adb_audit: 109 statements reproduce every audited ADB field across backend, API, and dashboard-package surfaces
[PASS] balance_outcomes: balance: 106 pass, 3 withheld, same three statements
[PASS] adb_outcomes: adb: 106 pass, 3 withheld, same three statements
[PASS] ocr_coverage: 103 native-text + 6 committed-OCR = 109 statements resolved offline; no live OCR, no model calls
[PASS] exclusions: 0 named exclusions
[PASS] oracle_independence: 4 audit modules import no production financial mathematics

Coverage: 109 pinned PDFs (103 native text, 6 committed OCR), 0 exclusions
Ignored:  0 non-corpus PDFs under the corpus root
Outcomes: 106 PASS / 3 WITHHELD
Runtime:  297.8s

RESULT: GREEN
GATE_EXIT=0
```

The three WITHHELD are the same three statements by name, including
`BMO_Statement_January_2026 Final-1-2 (1).pdf`, whose `source_contradiction`
diagnosis is re-asserted by
`tests/test_telemetry_corpus.py::test_withheld_diagnostics_reproduce_the_documented_diagnosis`
inside the corpus-marked suite above. No re-baseline was requested or performed;
neither audit CSV was regenerated.

**The suite grew by the new fixtures and by nothing else.** Base `bb7d644`:
2,336 passed. Head `a990e95`: 2,410. `tests/test_bmo_layouts.py` collects 38;
the remaining 36 are generated by `tests/test_parser_conformance.py` and
`tests/test_parser_registry_entries.py` *enumerating* the registry, which is
what those two modules exist to do.

```
$ git diff bb7d644..HEAD --stat
 analysis/bmo_ca_business.py               | 510 ++++++++++++++++
 analysis/bmo_us_activity.py               | 263 +++++++++
 analysis/parser_registry_entries.py       |  16 +
 tests/data/parser_conformance_fixtures.py |  13 +
 tests/test_bmo_layouts.py                 | 623 ++++++++++++++++++++
 tests/test_parser_conformance.py          |   9 +-
 tests/test_parser_registry_entries.py     |  11 +-
 7 files changed, 1439 insertions(+), 6 deletions(-)
```

The six deletions are the two registration-count pins being re-worded. No
existing assertion changed meaning; the additions to existing test files are the
dispatch-order list (3 ids), the conformance fixtures (3), and one new
`by_bank_label("BMO")` pin that did not previously exist because the label was
not previously shared.

## M8. Commits

| Commit | Contents |
|---|---|
| `d25c1da` | `analysis/bmo_ca_business.py`, `analysis/bmo_us_activity.py`, 3 registry entries + 3 overrides, `tests/test_bmo_layouts.py`, conformance fixtures and the two count pins |
| `be15877` | the two defects of §M4, and their fixtures |
| `b7b734d` | `bmo_us_activity`: the ledger's bounds named by label rather than position, and `resolve_year` consumed instead of a second local copy |
| `a990e95` | `bmo_us_activity`: the §M4 item-1 defect class closed in its twin |
| (this one) | §BMO-LAYOUTS M0–M8 |

---

# §CHASE-LAYOUTS — Cell 10: `Chase × no_parser_matched`, 176 documents

REEF-CHASE-LAYOUTS, 2026-08-13. Branch `wave3-chase-layouts`, base `b18d999`
(current main, FIXUPS-1 landed). Brief:
`docs/agent-handoffs/REEF-CHASE-LAYOUTS.md`. Baseline: run `ca2ba0eb`.

Method as §BMO-LAYOUTS: reproduce the cell independently, characterise the
families structurally BEFORE changing code, build and validate the in-document
instrument, fix at the capability level or fail closed with the volume stated,
prove both directions with synthetic fixtures, measure honestly.

## C0. Summary

| | |
|---|---|
| Cell worked | `folder_label == "Chase"` × `outcome_class == failed` (`no_parser_matched`) in `ca2ba0eb`: **176 records, 176 distinct content hashes** (no duplicates). |
| Families found | **11.** Table in §C3. |
| Result over the cell | **115 / 176 newly CLAIMED and 113 / 176 newly VALIDATED**, from 0 and 0. 2 claimed-and-withheld (fail-closed, diagnosed). Nothing ambiguous, nothing crashed. |
| Result outside the cell | `square_checking` also claims and validates **4** documents in the `Square/` folder, all `failed` at baseline. **Total validated gain: 117.** |
| What the cell actually was | **not an unclaimed-layout cell.** 126 of the 176 carry Chase's `*start*summary` sentinel and ARE detected by the existing `chase` registration at 0.5 — `parse` then declined them (`Dispatch.attempted == ('chase',)`). 17 more were detected and declined by `mission_valley`. The `no_parser_matched` label described R-3's parse-fallthrough, not a missing layout. |
| The two changes | **(1)** `analysis/chase.py`: the two `CHECKING SUMMARY` balance rows now use the module's own sign-aware `_SUMMARY_AMOUNT` instead of a private unsigned copy, so an overdrawn period is a balance rather than a missing one — **106 documents validated** (§C6.1). Authorized by Ocean 2026-08-13 under merge authority; the brief protects `chase.py`, MASTER_PLAN §4 does not. **(2)** new registration `square_checking` — **11 documents** (§C3 D1). |
| Registrations added | 1: `square_checking`. Registry 49 → 50. |
| Statement-specific constants added | **none.** Every marker is R-4b issuer furniture; every extraction rule is anchored on the printed grid. |
| Protected modules touched | none beyond the authorized two-line `chase.py` fix. No shared utility, no registry machinery, no pipeline, no other parser, no `ocr/`, no truth-set movement. |
| Regressions | **zero.** All 393 documents the chase family already claims are identical across every compared field, before and after (§C6.1b). |
| Files changed | `analysis/chase.py` (2 lines + comment), `analysis/square_checking.py` (new), `analysis/parser_registry_entries.py` (1 entry + 1 override), `tests/test_chase_layouts.py` (new, 37 fixtures), `tests/data/parser_conformance_fixtures.py` (+1), the two registry-count pins, the dispatch-order list, and this log. |
| Left as proposals | **A' zero-activity** (7 docs, scratch-measured 4 validated, §C6.2) and **B1 savings** (10 docs, failed closed with a card recommendation, §C6.3) — both per Ocean's ruling of 2026-08-13. |
| Cache implication | `ANALYSIS_STAGE_VERSION` must be bumped at merge. **Ocean's, not done here.** |
| Scope deviation, declared | the brief allows "new `analysis/chase_*.py` module(s)". The one buildable family is **not Chase's**, so the module is named for its issuer, `analysis/square_checking.py` (§C6.7). |

## C1. The cell reproduced independently

Reading `ca2ba0eb`'s `rows.csv` directly, counting distinct `content_sha256`
as well as records:

| | records | distinct documents |
|---|---|---|
| whole run | 3,506 | 3,380 |
| validated | 1,835 | **1,776** |
| withheld | 59 | **58** |
| review / deferred | 10 / 13 | 10 / 13 |
| failed | 1,589 | **1,523** |

The distinct-document column reproduces the brief's `1,776 / 10 / 58 / 1,523`
over a denominator of 3,380 exactly, which fixes the denominator: **every count
in this section is distinct documents unless it says records.**

The `Chase/` folder holds 613 records / 591 distinct documents:

| Chase folder | records | documents | note |
|---|---|---|---|
| `validated` / `approved` | 430 | 408 | claimed by `chase` (411 records), `chase_export` (4), `mission_valley` (16), `relay` (4) |
| `failed` / `no_parser_matched` | 176 | **176** | the cell |
| `withheld` / `withheld_adb` | 4 | 4 | |
| `review` / `integrity_flags` | 1 | 1 | |
| `deferred` / `deferred_visual_ocr` | 2 | 2 | |

The brief expected roughly 171-176; the measured cell is **176 records / 176
distinct documents**, and 176 is also the figure `summary.json`'s
`unknown_layout_clusters` carries for `Chase`.

**The brief's central assumption is measurably false, and that is the finding.**
It expected "DIFFERENT Chase layouts (likely consumer/secure-message/older
templates)" whose problem would be *detection*. Measured:

* **126 of the 176 carry Chase's `*start*summary` sentinel and ARE detected by
  the existing `chase` registration** — both of its required markers fire, it
  scores 0.5, and `parse_chase_statement` then returns `None`. They are
  `Dispatch.attempted == ('chase',)`: the R-3 §4.3 parse-fallthrough path,
  visible exactly because R-3 made it visible.
* 17 more are detected by `mission_valley` and declined the same way.
* Only 33 were not detected by anything, and 20 of those are not bank
  statements or not this platform's document class.

So this cell is not an unclaimed-layout cell at all. It is an **extraction**
cell wearing an unclaimed-layout label, and its centre of mass was inside
`analysis/chase.py`.

## C2. The measurement instrument (built and validated before any code changed)

The 176 documents were rendered read-only through the production ladder
(`ocr.pipeline.parse_statement`, native rung plus the Tesseract rung discovery
itself ran, `allow_visual_ocr=False` — no model client is ever constructed),
served from the D-3 artifact cache: **176 cache hits, 0 misses, `$0.00`.** All
176 have a text layer. Aggregates only are reported here; no customer, amount
or date from the archive appears in this document or in any fixture.

Grouping by structural signature over that text gave the families in §C3. Two
instruments were built and validated on the archive text **before** any code
changed:

**Family A** — the token-class shape of every `CHECKING SUMMARY` line was
tabulated across the cell (shapes, never values). The result is one table:

| printed label | shape | lines |
|---|---|---|
| `Beginning Balance` | `$M` | 57 |
| `Beginning Balance` | **`-$M`** | 50 |
| `Ending Balance` | `N $M` | 44 |
| `Ending Balance` | **`N -$M`** | 60 |

Chase prints an overdrawn balance with the sign **outside** the currency
symbol, and prints the period's **total** instance count on the `Ending
Balance` row. `analysis/chase.py::_parse_native_summary` matched
`\$?[0-9][0-9,]*\.[0-9]{2}` on those two rows — no sign — so the balance was
not read, the function returned `False`, and `parse` returned `None`. That is
the whole of family A. The arithmetic confirms the reading rather than assuming
it: `beginning + deposits - withdrawals - fees` reproduces the printed ending
balance including its sign.

**Family D1 (Square Checking)** — the layout prints its own summary row, a
running Balance on every row, and an activity count. On the 7 cell documents,
before any parser existed:

| check | before |
|---|---|
| `Starting balance Activities Ending balance` row parses | 7 / 7 |
| every printed running balance follows from the row above | 7 / 7 (1,723 rows) |
| ending balance equals the last printed running balance | 7 / 7 |
| `starting + sum(amounts) = ending` | 7 / 7 |
| printed `Activities` count equals rows read | 7 / 7 |

Five independent printings, mutually consistent on every document — that is
what made it safe to build on.

The baseline against both instruments is zero on every line by construction:
nothing claimed these documents, so no ledger existed to compare.

## C3. The families — the deliverable

Named by structure. Nothing below names a customer, a bank product, an amount
or a date; every rule is anchored on the printed grid.

| # | Family | Structural signature | Root cause | Ruling | Volume |
|---|---|---|---|---|---|
| **A** | Chase native, **overdrawn** | `*start*summary` · `CHECKING SUMMARY` · `Beginning Balance -$…` and/or `Ending Balance <n> -$…` | **extraction** — detected by `chase` at 0.5, declined at `_parse_native_summary` because those two rows' money pattern had no sign | **FIXED** (§C6.1), authorized by Ocean: **106 validated, 2 fail-closed** | **108** |
| **A'** | Chase native, **zero-activity period** | the same furniture; a zero opening balance, a zero closing balance with a printed instance count of 0, and no detail section at all | **extraction** — `chase.py` returns `None` on `not txns`, so a period in which nothing happened is not a statement | **PROPOSAL, NOT LANDED** (§C6.2); scratch-measured 4 of 7 | **7** |
| **B1** | Chase native **savings** | `*start*summary` · `SAVINGS SUMMARY` · a single `*start*transaction detail` block · grid `DATE DESCRIPTION AMOUNT BALANCE` · `Annual Percentage Yield Earned` | **detection + extraction** — `chase.py` hard-requires `CHECKING SUMMARY` and reads only the six named checking sections | **FAILED CLOSED**, card recommended (§C6.3) | **10** |
| **B2** | Chase native, **empty sentinel skeleton** | every `*start*…*end*` pair present and **empty**: the producer emitted the section sentinels and none of the content | **unusable input** — structure without data | **FAIL CLOSED BY DESIGN**, volume stated | **1** |
| **C** | Mission Valley Bank, **other products** | the `Managing Your Accounts` core-processor template · `missionvalleybank.com` · account sections `Business Analyzed Checking` (9), `Business Interest Checking` (4), `Business Checking` (4) | **extraction** — detected by `mission_valley` at 0.5 and declined; the parser reads one product's section shape | **STOP AND PROPOSE.** Root cause is inside `analysis/community_section.py`, another parser (§C6.4) | **17** |
| **D1** | **Square Checking** (Block, Inc.) | `Square Checking Routing number:` · `squareup.com/help` · `Block Inc.` footer · grid `Date Details Activity type Balance Amount` · signed Amount column · running Balance on every row | **no registration existed** — a readable layout nobody owned | **BUILT**: new registration `square_checking` | **7** (+4 outside the cell) |
| **D2** | American Savings Bank `Statement of Account` | `asbhawaii.com` · `Statement of Account` / `Last Statement:` · `Account Activity` grid `Additions Subtractions Date Description Balance` | **geometry** — the flattened reading order does not preserve the columns: the header's own column order differs page to page, descriptions arrive token-reversed, and money-cells-per-row runs 1/2/3/4/6/13 | **FAIL CLOSED. Routed to the geometry queue** (§C6.5) | **10** |
| **D3** | First Carolina Bank | `fcbcarolinas.com` on the **same** core-processor template as family C | needs a new entry point in `analysis/community_section.py`, a protected parser | **STOP AND PROPOSE** (§C6.4) | **2** |
| **D4** | Chase, **scanned** | Chase furniture present via Tesseract; no `*start*` sentinels, because those live in the native text layer | **scanned — the OCR path, out of scope** | **NO CHANGE**, volume stated | **4** |
| **D5** | Chase **credit card** | `CHASE FREEDOM UNLIMITED` / `UNITED MILEAGEPLUS AWARD` · `New Balance` · `Minimum Payment Due` · `Payment Due Date` · `REWARDS SUMMARY` | **not this statement class** — a card statement is not a deposit-account statement | **NO CHANGE** | **2** |
| **D6** | not a bank statement | a 1120-S tax return, a business plan, an EIN letter, a credit-denial notice, a zero-balance letter, a voided cheque, a bridge-loan overview, a routing-number screenshot | **not a statement** | **NO CHANGE** | **8** |

The single fact that ruled families A, A' and B: **`chase` detected 126 of the
176 and declined all 126 at parse.** `Dispatch.attempted` named it on every one.

### C3.1 The rules family D1 produced

* **Direction is printed, not inferred.** The Amount column carries its own
  sign; no description vocabulary, no arithmetic.
* **The printed column order decides which cell is which.** The grid header
  reads `Date Details Activity type Balance Amount` — **Balance then Amount** —
  so the row's last two money cells are read in that order rather than by
  guessing which is larger. Reading them the other way round inverts the whole
  ledger, and `test_the_printed_column_order_decides_which_cell_is_the_amount`
  pins it.
* **A wrapped Details cell does not end the row.** A counterparty name long
  enough to fill the column pushes Activity type, Balance and Amount onto the
  line below — the F1 family `chase.py` met in W3 Track A. Rows are grouped by
  the printed Date column through the shared `group_rows`; the reprinted grid
  header closes an open row. This is §C4's defect and it is the difference
  between 9 validated and 11.
* **Money cells are matches, not strings**, sliced by position: the amount's
  characters occur again inside the balance printed beside it.
* **Every money cell of this layout prints the currency symbol**, which is what
  keeps a bare reference number in the Details column out of the money columns.
* **Only the closing year is printed.** A period opening in the previous
  calendar year is recognised by its opening month standing *after* its closing
  month — the only ordering that can occur.
* **Inter-word spacing is a property of the text layer, not of the statement**
  (§BMO-LAYOUTS M3.1); case likewise, for detection. **Parse does not read
  through the upper-casing**, because the Details column is description text
  this platform publishes — a defect the fixtures caught (§C4).

Negative fixtures — each constrains a new rule rather than demonstrating a
defect:

* a Chase statement that pays Square is not claimed by `square_checking`, and
  the Square statement — which names Chase as the counterparty of a recurring
  transfer on nearly every document — is not claimed by `chase`. This is the
  R4-3 hazard in the exact shape that produced this cell;
* no single one of the four required markers carries a claim on its own — the
  single-marker invariant, stated per registration;
* no other registration claims the Square layout, asserted by enumerating the
  registry;
* a header with no grid is not parsed, and neither is a grid with no summary
  row;
* detection reads nothing from the source filename;
* a page footer **carrying a money figure** is not absorbed into the row
  above it — asserted with the row's own money cells one line further down
  as well (§C4 item 3);
* the reprinted grid header does not continue the row that ended the page
  before it.

### C3.2 What did NOT change, deliberately

* **`analysis/chase.py` changed by two lines and nothing else.** Its detection
  markers, its `detection_text`, its section readers, its check grammar and its
  HTML-table path are untouched; §C6.1(b) and (e) measure both halves of that
  claim rather than asserting them.
* **`analysis/community_section.py` is untouched** (families C and D3).
* **No shared utility's behaviour changed**, so no R-2 differential-equivalence
  proof is owed. `group_rows`, `compact_whitespace` and `parse_grouped_float`
  are consumed unmodified, with caller-supplied predicates as designed.
* **No `supersedes` edge and no band change.** `square_checking` sits at band
  100; it is disjoint from everything, and §C5.3 proves that rather than
  asserting it.
* **`stated_total_credits` / `stated_total_debits` are left unset** on Square.
  It prints *net* category movements, not gross period totals. Deriving them
  from the ledger would be circular — the ledger is the thing they would be
  checking.

## C4. The defects the instrument caught in this cell's own code

Reported as they happened rather than tidied:

1. **The Square parser read through its own detection normalization.**
   `detection_text` upper-cases so that a producer's capitalisation cannot
   decide whether we claim — and `parse` was reading the same string, so every
   published description came out in capitals. Detection normalization and
   parse normalization are now separate functions with the shared part named
   once. Caught by
   `test_the_description_is_the_text_between_the_date_and_the_money_columns`
   before any measurement ran.
2. **A wrapped Details cell lost its row.** Found by the instrument, not by the
   tests: two `Square/` documents read 190 of 191 and 269 of 270 rows, with
   **exactly one continuity break each**, immediately after the missing row —
   and the last printed balance still equalled the summary's ending balance.
   One long counterparty name per document had pushed the money columns onto
   the next physical line. Both documents were `withheld` on
   `ledger_sum_mismatch` plus `running_balance_breaks` — the fail-closed gate
   doing its job — and both now validate. This is why the instrument is worth
   running against documents outside the cell as well.

3. **A money-bearing page footer was absorbed into the row above it.** Found
   by Ocean's independent adversarial review, not by me: my comment asserted
   that "the page footer carries no money and so cannot be mistaken for a
   cell" — a statement about content, not a structural guarantee, and the
   fixture I wrote for it used a money-free footer, so it pinned the wrong
   property. Given a footer like `Overdraft protection limit $500.00 applies.`
   the page's last row published **500.00 as its amount** while its running
   balance held the real figure. It reached `review` rather than being refused,
   because Square's printed Activities count still matched and only one
   continuity break fired — the fail-closed gate caught it, but only just.

   Fixed with two independent structural bounds, neither of which reads the
   footer's wording for its meaning: the footer is **issuer furniture standing
   outside the grid**, so it now terminates an open row exactly as the
   reprinted grid header does (reusing two markers this parser already
   declares, introducing no new vocabulary); and a row's money cells are now
   taken from **the row's own printed line** — the search stops at the first
   line carrying two money cells — rather than from everything before the next
   row starts. Both fixtures are verified to reproduce the defect against the
   pre-revision loop.

## C5. Result over the cell

### C5.1 The instrument, before then after (family D1)

| Square Checking — 7 of 7 in the cell | before | after |
|---|---|---|
| summary row parses | 0 / 7 | **7 / 7** |
| every printed running balance follows from the row above | 0 / 7 | **7 / 7** |
| ending balance equals last printed running balance | 0 / 7 | **7 / 7** |
| `starting + sum(amounts) = ending` | 0 / 7 | **7 / 7** |
| printed `Activities` count equals rows read | 0 / 7 | **7 / 7** |

### C5.2 The cell, before then after — the full accounting

Measured on the final tree with the shipped code, classified with the same
mapping discovery uses (`telemetry.record.classify_outcome`).

| Family | docs | claimed 0 → | VALIDATED 0 → | review | withheld + diagnosis | unusable / no change |
|---|---|---|---|---|---|---|
| A — Chase native, overdrawn | 108 | **108** | **106** | 0 | **2** · `withheld_adb`, `summary_math_inconsistent` + `ledger_sum_mismatch` + coverage mismatches | — |
| A' — Chase native, zero activity | 7 | 0 | 0 | 0 | 0 | 7 unclaimed — proposal §C6.2 |
| B1 — Chase native savings | 10 | 0 | 0 | 0 | 0 | 10 unclaimed — failed closed §C6.3 |
| B2 — empty sentinel skeleton | 1 | 0 | 0 | 0 | 0 | 1 unusable input |
| C — Mission Valley other products | 17 | 0 | 0 | 0 | 0 | 17 unclaimed — §C6.4 |
| **D1 — Square Checking** | **7** | **7** | **7** | 0 | 0 | — |
| D2 — American Savings Bank | 10 | 0 | 0 | 0 | 0 | 10 geometry — §C6.5 |
| D3 — First Carolina Bank | 2 | 0 | 0 | 0 | 0 | 2 unclaimed — §C6.4 |
| D4 — Chase scanned | 4 | 0 | 0 | 0 | 0 | 4 OCR path, out of scope |
| D5 — Chase credit card | 2 | 0 | 0 | 0 | 0 | 2 not this statement class |
| D6 — not a bank statement | 8 | 0 | 0 | 0 | 0 | 8 not statements |
| **TOTAL (documents)** | **176** | **0 → 115** | **0 → 113** | **0** | **2** | **61** |

Outcome classes over the cell: `failed 169 / validated 7` → **`validated 113 /
withheld 2 / failed 61`**. Ambiguous dispatches: **0.** Parser exceptions:
**0** — every still-unclaimed document raises the deterministic mode's own
`RuntimeError: no deterministic parser matched this statement`, which is the
unclaimed path, not a crash.

**The 2 withheld are the fail-closed gate working, and they are named.** Both
carry `summary_math_inconsistent`: Chase's own printed summary does not close
on those two documents, so the platform refuses to publish an authoritative
figure. Reading the sign correctly is what made that visible — before the fix
they were simply unreadable.

**Outside the cell — the 4 that reconcile the movement.** The `Square/` folder
holds 4 documents, all `failed`/`no_parser_matched` at baseline, all now
`validated`/`approved` under `square_checking`:
`864bf469_L2BWM61KMP7YZ_2026-03`, `_2026-04`, `_2026-05`, `_2026-06`
`_account_statement.pdf` (149, 164, 191 and 270 transactions). **Total
validated gain: 113 + 4 = 117.**

**Nothing was padded to get there.** Every document that now validates does so
because the rows extracted reproduce, independently: for family A, Chase's own
printed per-section totals, its stated credit and debit totals and the ledger
identity — with the negative balance read correctly, since a mis-signed balance
breaks that identity rather than closing it; for D1, the summary row Square
prints, the activity count Square prints, and every printed running balance.
The fail-closed gate is unchanged; these documents pass it on their own
arithmetic.

### C5.3 Regressions — zero, and the evidence

* **The 393 documents the chase family claims today**: swept before and after
  in one process, comparing outcome class and reason, dispatch outcome, parser
  id, candidate count, transaction count, transaction sum, integrity flags and
  nine statement fields. **388 validated / 4 withheld / 1 review before;
  identical after; 0 documents differ in any field** (§C6.1b).
* **Chase's detection surface**: unchanged over both populations — 389 of 393
  and 126 of 176 claims before and after, **0 scores moved** (§C6.1e).
* **The stratified cross-bank probe**: up to 12 digital documents from each of
  the **65** folders, validated ones first — **447 documents**.
  `square_checking` claims **4**, all of them in the `Square/` folder, i.e. its
  own layout. **Zero claims anywhere else**; it reached 0.0 on every non-Square
  document. **Zero ambiguous dispatches** anywhere in the sample.
* **The conformance cross-product**: 50 × 49 fixture pairs, **zero
  cross-claims**; the single-marker invariant holds for `square_checking` (four
  required markers); SOURCE-comment invariance holds; both
  `COUNTERPARTY_VULNERABLE` and `FILENAME_DEPENDENT_PARSERS` remain empty.
* **The pinned corpus**: `python -m pytest -m corpus -q` and
  `python corpus_gate.py` both green, 106 PASS / 3 WITHHELD, same three by
  name; all 11 pinned Chase-family statements byte-identical (§C7).
* **The suite**: 2,475 → **2,524**, and by nothing else. 37 fixtures in
  `tests/test_chase_layouts.py` plus 12 tests the conformance and registry
  modules generate by *enumerating* the registry. No existing assertion changed
  meaning: the edits to existing test files are the two registration-count
  pins, the dispatch-order list (1 id) and one conformance fixture.

## C6. Carried findings and questions for Ocean

### C6.1 `chase.py` could not read an overdrawn balance — 108 documents, two lines, LANDED under Ocean's authorization

**This is the cell's central result.** It arrived as a stop-and-propose (the
brief protects `analysis/chase.py`); Ocean ruled on 2026-08-13 under merge
authority that the change is structural capability rather than a statement
patch, and authorized it with six conditions. All six are discharged below.

`_parse_native_summary` reads the summary block's money one way for every row
except two. `_SUMMARY_AMOUNT` — the module's own constant, already used for
`Deposits and Additions` and for every debit label — is sign-aware:

```python
_SUMMARY_AMOUNT = r"-?\s*\$?\s*[0-9][0-9,]*\.[0-9]{2}"
```

The two balance rows carried a private, unsigned copy of it. Chase prints an
overdrawn balance with the sign **outside** the currency symbol, exactly as it
prints every debit row of the same summary, so neither balance matched, the
function returned `False`, and `parse_chase_statement` returned `None` — which
is why an extraction defect arrived filed as an unclaimed-layout cell.

**(a) The minimal diff.** The fix is a *reuse*, not a new pattern: the two rows
now read money the same way the rest of the block already does. Nothing else in
`chase.py` changed.

```python
-    beginning = re.search(r"Beginning Balance\s+(\$?[0-9][0-9,]*\.[0-9]{2})", summary, re.IGNORECASE)
-    ending = re.search(r"Ending Balance(?:\s+\d+)?\s+(\$?[0-9][0-9,]*\.[0-9]{2})", summary, re.IGNORECASE)
+    beginning = re.search(rf"Beginning Balance\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE)
+    ending = re.search(rf"Ending Balance(?:\s+\d+)?\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE)
```

`chase._money` already parsed a leading minus
(`parse_digit_scrubbed(..., leading_minus=True, ...)`), so only the capture
pattern was ever at fault.

**(b) Zero movement on the previously-claimed population.** All
393 documents the chase family claims in `ca2ba0eb` were rendered
read-only and swept twice **in one process**: once with the pre-fix
`_parse_native_summary` restored, once with the shipped code — so the only
variable measured is those two lines. Compared per document: outcome class and
reason, dispatch outcome, parser id, candidate count, transaction count,
transaction sum, integrity flags and nine statement fields.

```
BEFORE: {'validated': 388, 'withheld': 4, 'review': 1}
AFTER : {'validated': 388, 'withheld': 4, 'review': 1}
documents differing in ANY compared field: 0
CLAIMED_POPULATION_DIFFS= 0
```

Not one document moved. The change is a strict superset of the old pattern: on
a statement that read correctly before, the captured text is character-identical,
because the only addition is a sign the old pattern could not stand adjacent to.
The sweep is the evidence rather than the argument.

**(c) The pinned corpus.** `python -m pytest -m corpus -q` and
`python corpus_gate.py` both green after the change, 106 PASS / 3 WITHHELD,
same three by name — §C7. The pinned manifest carries 11 Chase-family
statements (not 8; see §C7), all byte-identical.

**(d) The conformance cross-product** is re-proven at the final tree: 50 × 49
fixture pairs, zero cross-claims — §C7.

**(e) The detection surface did not move.** This is a parse-level fix; the
markers and `detection_text` are untouched. Asserted rather than argued, over
both populations, before and after:

```
  claimed  n= 393  chase claims before=389 after=389  scores moved=0
  cell     n= 176  chase claims before=126 after=126  scores moved=0
DETECTION_MOVED= 0
```

`test_the_sign_fix_did_not_move_chase_detection` pins the same property
synthetically: `matched == ("bank_name", "section_sentinels")` and an identical
score with and without the overdrawn figure.

**(f) The movers are VALIDATED, not merely claimed.** The per-family table in
§C5.2 is the accounting. Every mover reaches `validated` / `approved` through
the unchanged fail-closed gate, which means its rows reproduce Chase's own
printed per-section totals, its stated credit and debit totals, and the ledger
identity — with the negative balance read correctly, since a mis-signed balance
would break that identity rather than close it. A synthetic overdrawn statement
pins the arithmetic directly:
`test_the_overdrawn_statement_reconciles_on_its_own_arithmetic` asserts
`beginning + moved == ending` with both balances negative, and
`test_the_captured_rows_reproduce_the_printed_section_totals` asserts the
captured rows equal the two `Total …` lines the statement prints. The fixture
is a genuine regression test: with the pre-fix pattern restored in-process it
parses to `None`.

### C6.2 PROPOSAL, not landed — `chase.py` refuses a period in which nothing happened (7 documents)

Ocean's ruling: keep as a scratch-measured proposal. Not implemented.

`parse_chase_statement` ends with
`if not txns or stmt.beginning_balance is None or stmt.ending_balance is None: return None`.
Seven documents in this cell print a zero opening balance, a zero closing
balance with the bank's own instance count printed as `0`, a service-charge
summary of zeros, and no detail section at all — Chase's statement for a period
with no activity.

**The proposed rule, and why it is conservative.** An empty ledger is
admissible only when the bank itself printed no instances in any section *and*
the two balances agree:

```python
if stmt.beginning_balance is None or stmt.ending_balance is None:
    return None
if not txns and not (
    not (stmt.stated_credit_count or 0) and not (stmt.stated_debit_count or 0)
    and stmt.beginning_balance == stmt.ending_balance
):
    return None
```

**Scratch-measured** (in-process source rewrite; `analysis/chase.py` on disk
never modified):

| the 7 A' documents | shipped | proposed |
|---|---|---|
| validated | 0 | **4** |
| failed | 7 | 3 |

The 3 that stay failed are the honest half of the result: they are **not**
zero-activity documents — they state instances or their balances differ — so
the conservative rule correctly refuses them, and they remain a separate
undiagnosed shape rather than being swept in.

**Regression surface, by construction:** the relaxed branch is reachable only
when `txns` is empty, and every document the chase family claims today has
transactions. No currently-claimed document can traverse it. A full sweep
should still be required when the card is implemented, not accepted from this
argument.

### C6.3 FAILED CLOSED — the Chase savings layout is a second grid reader, not a one-liner (10 documents)

Ocean's ruling: if the evidence is murkier, fail closed with the diagnosis. It
is murkier, and it is failed closed.

Chase's savings statement is the same native template with different furniture:
`SAVINGS SUMMARY` instead of `CHECKING SUMMARY`, an `Annual Percentage Yield
Earned This Period` line, and — the substantive part — a **single**
`*start*transaction detail` block carrying the grid
`DATE DESCRIPTION AMOUNT BALANCE`, in place of the six named checking sections
`chase.py` knows. Two further structural facts make it a card rather than a fix:

* the amount cell frequently wraps onto the physical line **above** its row
  (a bare money token standing before the `MM/DD …` line), the mirror image of
  the F1 family;
* the grid's own `Beginning Balance` / `Ending Balance` rows are bounds, not
  transactions, and must not be published as rows.

**Scratch-measured** with a deliberately rough reader, to size the family
rather than to propose an implementation:

| the 10 B1 documents | shipped | scratch reader |
|---|---|---|
| validated | 0 | 6 |
| withheld (fail-closed, `ledger_sum_mismatch`) | 0 | 3 |
| failed | 10 | 1 |

The 3 withheld are the point: the rough reader captures 1–3 rows on documents
whose ledgers plainly carry more, and the fail-closed gate catches it. That is
the difference between this family and §C6.1 — the sign fix made 106 documents
reconcile on arithmetic they already printed, whereas this one needs a reader
whose correctness has to be established in its own right. **Recommended as a
dedicated card with its own instrument**, not a FIXUPS-class one-liner. Volume
10 here, and Chase savings statements will recur across the archive.

### C6.4 The Mission Valley core template is read for one product out of four, and a second bank prints it — 19 documents

`analysis/community_section.py`'s Mission Valley entry point pins the account
section by `Business Checking\s*-\s*([X0-9]+)`. The 17 cell documents are the
same customer's other products on the same template — `Business Analyzed
Checking` (9), `Business Interest Checking` (4) and `Business Checking` (4) —
and `mission_valley` detects all 17 and declines all 17. Two further documents
(§D3) are **First Carolina Bank** (`fcbcarolinas.com`) printing the identical
core-processor template: `Statement Ending`, `Customer Number`,
`Managing Your Accounts`, `Summary of Accounts`, `Account Activity`, grid
`Post Date Description Debits Credits Balance`.

Both need `analysis/community_section.py`, a protected parser: the first as a
section-naming generalisation, the second as a new entry point plus a
registration alongside `mission_valley` and `dakota_west`. Volume 19 in this
cell alone, and the template is a core processor's, so it will recur under
other banks' names. **Requested: a ruling**, ideally as one card.

### C6.5 American Savings Bank is a geometry family — 10 documents, routed to the geometry queue

Reported with the measurement rather than the impression. The issuer furniture
is clean (`asbhawaii.com` in every page footer, `American Savings Bank` in the
page-2 header), so **detection is not the problem**; the flattened text layer
is. Its `Account Activity` grid prints
`Additions | Subtractions | Date | Description | Balance`, and:

* the printed column order in the header itself differs between page 1 and
  page 2 of the same document;
* description tokens arrive reversed within a row;
* money-cells-per-row runs 1, 2, 3, 4, 6 and 13;
* a reader that takes each row's last two money cells as amount and balance
  reads 34 of 34 rows on one document and leaves **9 of 20** and **10 of 55**
  balance movements unexplained on the two larger ones.

Which of Additions and Subtractions a cell stood in is destroyed by flattening
and — unlike §BMO-LAYOUTS family A — is **not** recoverable from the printed
Balance column, because the row-to-money association is itself unreliable.
Four of the 10 are single-page statements with no activity at all. Building
this from the text layer would produce ledgers that balance by accident.
**FAIL CLOSED**, volume 10, routed to the geometry queue.

### C6.6 The new class is bounded by the platform, not by layout knowledge — the §BMO-LAYOUTS M6.7 pattern, confirmed and sharpened

§BMO-LAYOUTS observed that of 164 documents, layout knowledge bound 128 and the
platform bound 26. This cell inverts that ratio completely. Of 176 documents,
**new layout knowledge bound 7** (family D1); **an existing parser's own
extraction bound 142** (families A, A', B1 at 125, family C and D3 at 19); and
26 are honestly closed. The one authorized two-line fix inside an existing
parser delivered **106 validated documents — fifteen times what the new parser
delivered.**

The `no_parser_matched` label is what hid this: R-3's parse-fallthrough reports
a registration that detected a document and then declined it as "no parser
matched", so an extraction defect arrives filed as a missing layout.

**Recommendation for the phase, now evidenced rather than suspected:** rank the
remaining cells by `Dispatch.attempted` — documents a registration detected and
declined — rather than by folder. That column already exists in `rows.csv` and
separates "we have never seen this layout" from "we own this layout and drop
it" without opening a single PDF. On this cell it would have pointed at the
right 143 documents on day one.

### C6.7 The module-naming deviation, declared rather than discovered

The brief allows "new `analysis/chase_*.py` module(s)", written when the cell
was believed to be Chase layouts. The one buildable family is Square's. The
module is therefore `analysis/square_checking.py`, named for its issuer as
every other parser in `analysis/` is. Nothing protected is touched, the
registration meets the full R-3/R-4 standard, and the alternative — leaving 11
statements that read perfectly unbuilt because of a filename prefix — seemed
the worse call. Renaming is cheap if Ocean disagrees.

### C6.8 `square_checking` claims no pinned corpus document

Its only coverage is `tests/test_chase_layouts.py` and the R-4 conformance
fixture — the same status `demo_national` and the three BMO layouts have.
`tests/data/parser_expectations.json` and
`tools/record_parser_expectations.py::PIPELINE_ENTRY_POINTS` are the pre-R-3
or-chain baseline and are deliberately **not** extended, for the reason
§BMO-LAYOUTS M6.8 gives. The divergence from the registry is now four ids, not
three — noted so it stays a decision rather than a drift.

### C6.9 The registration count moved 49 to 50

Both pinned tests are updated and stated here. `R4_CONFORMANCE_FINDINGS.md`
(`46 × 45`), `R3_DETECTION_FINDING.md`, `H3_SCHEMA.md` and
`WAVE2_EXECUTION_LOG.md` still say 46; §BMO-LAYOUTS M6.9 already flagged them
as records of what was true when written.

### C6.10 `ANALYSIS_STAGE_VERSION`

Must be bumped at merge — `webapp/` is protected and this is Ocean's, not done
here.

## C7. Proofs

Run on a clean tree at `39efc0f`, the last commit touching code or tests.

```
$ git status --short
$ git rev-parse --short HEAD
39efc0f

$ set -o pipefail; python -m pytest -q
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2522 passed, 18 deselected, 1 warning in 155.42s (0:02:35)
SUITE_EXIT=0

$ python -m pytest tests/test_no_statement_hardcodes.py tests/test_r1_hardcodes.py tests/test_no_parser_helper_clones.py -q
............................                                             [100%]
100 passed in 1.06s
GUARDS_EXIT=0
$ python -m pytest tests/test_parser_conformance.py tests/test_parser_registry_entries.py tests/test_parser_parity.py tests/test_parser_detection_markers.py tests/test_chase_layouts.py tests/test_chase_native_variants.py -q
..........                                                               [100%]
730 passed, 9 deselected in 1.41s
R34_EXIT=0

$ set -o pipefail; python -m pytest -m corpus -q
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
14 passed, 2526 deselected, 1 warning in 977.01s (0:16:17)
CORPUS_MARKED_EXIT=0

$ python corpus_gate.py
Corpus gate
[PASS] inventory: 109 pinned corpus PDFs, all on disk and audited by both oracles
[PASS] foreign_files: no non-corpus PDFs under the corpus root
[PASS] source_integrity: 109/109 pinned source PDFs match their pinned SHA-256
[PASS] balance_audit: 109 statements reproduce every audited balance field across backend, API, dashboard, CSV, XLSX, and package surfaces
[PASS] adb_audit: 109 statements reproduce every audited ADB field across backend, API, and dashboard-package surfaces
[PASS] balance_outcomes: balance: 106 pass, 3 withheld, same three statements
[PASS] adb_outcomes: adb: 106 pass, 3 withheld, same three statements
[PASS] ocr_coverage: 103 native-text + 6 committed-OCR = 109 statements resolved offline; no live OCR, no model calls
         served from committed OCR artifact: Chase/Chase Business.pdf
         served from committed OCR artifact: Misc/Builder June 2026.pdf
         served from committed OCR artifact: Misc/Columbia May 26 complete.pdf
         served from committed OCR artifact: Misc/First Farmers 2026 01-document.pdf
         served from committed OCR artifact: Misc/KLR.May 31,2026 (1).pdf
         served from committed OCR artifact: Regions/Regions.pdf
[PASS] exclusions: 0 named exclusions
[PASS] oracle_independence: 4 audit modules import no production financial mathematics
Coverage: 109 pinned PDFs (103 native text, 6 committed OCR), 0 exclusions
Ignored:  0 non-corpus PDFs under the corpus root
Outcomes: 106 PASS / 3 WITHHELD
Runtime:  404.8s
RESULT: GREEN
GATE_EXIT=0
```

The three WITHHELD are the same three statements by name. No re-baseline was
requested or performed; neither audit CSV was regenerated.

**Post-review re-run.** Ocean's independent adversarial review returned SHIP
conditional on two revisions (§C4 item 3 and the adversarial negative fixture
below). Re-run on the final tree — the code state of this branch's head,
which differs from the tree the proofs above ran on only by the two revisions:

```
$ python -m pytest tests/test_chase_layouts.py -q
37 passed in 0.27s
CHASE_LAYOUTS_EXIT=0

$ python -m pytest tests/test_parser_conformance.py tests/test_parser_registry_entries.py       tests/test_parser_parity.py tests/test_parser_detection_markers.py       tests/test_chase_native_variants.py -q
695 passed, 9 deselected in 1.26s
R34_EXIT=0

$ python -m pytest tests/test_no_statement_hardcodes.py tests/test_r1_hardcodes.py       tests/test_no_parser_helper_clones.py -q
100 passed in 0.77s
GUARDS_EXIT=0

$ set -o pipefail; python -m pytest -q
2524 passed, 18 deselected, 1 warning in 112.55s (0:01:52)
SUITE_EXIT=0
```

The claimed-population sweep was **not** re-run, and does not need to be: the
revision touches `analysis/square_checking.py` only, and that registration
cannot reach a chase-family document. Measured rather than argued — over all
393 documents `chase`/`chase_export` claim in `ca2ba0eb`, `square_checking`
makes **0 claims** and its highest score is **0.0**, three required markers
short of the threshold. The `analysis/chase.py` hunk is byte-identical to the
one the §C6.1 sweep was run against.

The review also strengthened the R4-3 negative fixture: it now carries **three
of the four** required markers (Square's legal entity, its help domain and its
routing-number header line, all plausible on a statement settling Square
deposits), so the grid header alone carries the negative. A companion fixture
pins what happens when that negative is defeated outright — a document carrying
all four Square markers and both Chase markers resolves **`ambiguous`**, with
both ids listed and no registration selected. Never first-wins, never a wrong
parse.

**Correction to the brief.** It states "the 8 pinned Chase corpus statements".
Measured from `docs/balance-metrics-audit-results.csv`, the pinned manifest
carries **11** Chase-family statements — 10 `chase-deterministic` and 1
`chase-transaction-export-deterministic`. All 11 are byte-identical after the
change; the corpus gate and the corpus-marked suite above are the proof.

**The suite grew by the new fixtures and by nothing else.** Base `b18d999`:
2,475. Branch head: 2,524. `tests/test_chase_layouts.py` collects 37;
the remaining 12 are generated by `tests/test_parser_conformance.py` and
`tests/test_parser_registry_entries.py` *enumerating* the registry, which is
what those two modules exist to do.

```
$ git diff b18d999..HEAD --stat
analysis/chase.py                            |   9 +-
 analysis/parser_registry_entries.py          |   7 +
 analysis/square_checking.py                  | 228 +++++++++++++
 docs/moneythumb-replacement/W3_TRACKA_LOG.md | 471 +++++++++++++++++++++++++++
 tests/data/parser_conformance_fixtures.py    |   5 +
 tests/test_chase_layouts.py                  | 395 ++++++++++++++++++++++
 tests/test_parser_conformance.py             |  12 +-
 tests/test_parser_registry_entries.py        |   8 +-
 8 files changed, 1124 insertions(+), 11 deletions(-)
```

The deletions are the two registration-count pins being re-worded and the two
`chase.py` balance patterns being replaced by the module's own
`_SUMMARY_AMOUNT`. No existing assertion changed meaning; the additions to
existing test files are the dispatch-order list (1 id) and one conformance
fixture.

## C8. Commits

| Commit | Contents |
|---|---|
| `537f65a` | `analysis/square_checking.py`, 1 registry entry + 1 override, `tests/test_chase_layouts.py`, the conformance fixture and the count pins |
| `67bcd8b` | `square_checking`: the wrapped Details cell of §C4 item 2, and its fixtures |
| `39efc0f` | `chase`: the §C6.1 sign fix, its five fixtures, and §CHASE-LAYOUTS C0–C6 |
| `30930cd` | §CHASE-LAYOUTS rewritten around the landed fix, plus C7–C8 |
| (this one) | `square_checking`: the two revisions from Ocean's adversarial review — the money-bearing-footer defect closed with two structural bounds, and the R4-3 negative rebuilt to 3-of-4 markers |


# §STRUCTFIX-1 — Three fuzzer-evidenced false-validation cards: `pnc` ×2, `bmo_ca_business` ×1

STRUCTFIX-1, 2026-08-13. Branch `wave3-structfix-1`, base `cc3ab29`. Brief:
`docs/agent-handoffs/STRUCTFIX-1.md`. Baseline: run `6893a75b`. Live
reproducers: the wave scratch `repro.py` (cases P1-A, P1-C, P1-B), run first
and re-run against the fix.

These are not coverage cells. Each card is a document that publishes
**approved / clear with wrong numbers** — the failure mode where every printed
identity still closes because the error is applied uniformly, so no downstream
oracle can see it. The method is therefore the reverse of a coverage cell:
characterise what the archive ACTUALLY prints before choosing the rule, because
the whole risk is a fix that reads a fuzzer's document correctly and a real
one wrongly.

## S0. Summary

| | |
|---|---|
| Cards worked | 3 (`pnc` space-thousands truncation; `pnc` dated zero-amount furniture; `bmo_ca_business` `_MONEY_EN`). |
| Shipped | **2 of 3.** Both `pnc` cards fixed. |
| **Card B not shipped** | **STOP fired.** The proposed alignment regresses **30 real documents from `validated/approved` to `withheld`**, each losing printed transaction rows. The card's premise is refuted by the archive — §S4. |
| Populations swept | `PNC Bank` **62 distinct documents** (superset of the 45 `pnc` claimed) and `BMO` **169 distinct documents** (superset of the 127 `bmo_ca_business` claimed). |
| Movers | **zero.** Both sweeps byte-identical, before and after, over every audited field and every transaction. |
| Pinned corpus | 5 PNC + 1 BMO statements are in the gate's 109. Gate GREEN, no audited-field movement. |
| Files changed | `analysis/pnc.py`, `tests/test_pnc_variants.py` (+11 fixtures), this log. **`analysis/bmo_ca_business.py` deliberately untouched.** |
| Statement-specific constants added | **none.** No furniture-text blocklist. No grammar beyond what `analysis/money.py` already surveys. |
| Cache implication | `ANALYSIS_STAGE_VERSION` bump at merge — Ocean's, not done here. Output changes only for documents that do not exist in the archive today, but the stage version guards the cache regardless. |

## S1. The populations and the instrument

Run `6893a75b`, distinct by `content_sha256`: 3,506 records → **3,380
documents**, reproducing M-QUEUE's baseline. Claimed populations:

| parser | records | distinct | outcome at baseline |
|---|---:|---:|---|
| `pnc` | 45 | **45** | 41 `validated/approved`, 4 `withheld/withheld_adb` |
| `bmo_ca_business` | 139 | **127** | 127 `validated/approved` |

Both sweeps were run over the whole **source folder** rather than the claimed
set — `PNC Bank` 62 documents, `BMO` 169 — because a fix can newly CLAIM a
document that no parser claimed before, and a claimed-set sweep cannot see
that. The folder population is a strict superset of the claimed one (`PNC
Bank`: 45 claimed + 17 unclaimed; `BMO`: 127 + 23 `bmo_us_activity` + 4 `bmo` +
4 `bmo_ca_business_french` + 11 unclaimed).

**Instrument.** Markdown is served from the D-3 artifact cache the run itself
consumed (`webapp_data/artifacts/ocr`, keyed by `content_sha256`), so the sweep
sees the exact text the run saw — including the one `PNC Bank` document that
came from local Tesseract and cannot be reproduced from the PDF offline. Cache
paths are derived arithmetically; the sqlite index is never opened, because
`Storage`/`ArtifactCache` write on read. Each document is then run through
`analyze_markdown(..., parse_mode="deterministic")` →
`analysis.serialization.report_to_dict` → `telemetry.record.classify_outcome`
and serialised as one canonical JSON line. Two sweeps are compared **byte for
byte**.

Three things were checked before any of its output was believed:

1. **Determinism** — two consecutive baseline runs are byte-identical.
2. **Fidelity to the run of record** — the 45 `pnc` documents come back 41
   `validated` / 4 `withheld`, matching `rows.csv` exactly; the 17 unclaimed
   `PNC Bank` documents come back `RuntimeError: no deterministic parser
   matched this statement`, which is the fail-closed outcome recorded as such
   and diffed like any other.
3. **Baseline provenance** — the "before" tree is `git archive cc3ab29`
   extracted to scratch, not the worktree before editing. The first attempt at
   this disagreed with the worktree baseline on 17 records; the entire
   difference was the `trace` field embedding the tree's own path, which is now
   not recorded. Type and message are.

## S2. Card P1 — `pnc`: a space-grouped thousands figure read as its tail

**Defect.** `_SUMMARY_MONEY_RE`'s integer part admitted only comma grouping, so
`1 000.00` could not match whole; the piece that DID fit was its `000.00` tail.
The Balance Summary is a flattened grid, so all four columns truncate together:
`beginning`, `ending` and the average balance are each wrong by the same
thousand, `beginning + activity == ending` still holds, and the statement
publishes approved/clear. Measured in the reproducer: beginning `1000.00 →
0.00`, ending `1200.00 → 200.00`, ADB `1243.33 → 243.33`, no flag.

**What the archive prints — measured before choosing the rule.** 53 of the 62
`PNC Bank` documents have a Balance Summary body. **27 of them contain a
`<digit><space><3 digits>.<dd>` sequence** — which is exactly the shape a
space-thousands reading would consume. In every one of the 27, the leading
digit is the **cents tail of a completed figure** and the space is a column
gap:

```
balance 541.22 541.22            <- average ledger / average collected
Ending balance 232.79 10,321.82 8,358.20 2,196.41
```

So the naive rule ("a space between digit groups is a thousands separator")
would have glued real columns together, and the naive fail-closed rule ("refuse
a figure preceded by digit-space") would have refused the second column of
every summary line in the archive. Neither is admissible.

**The rule that is.** One space character does two jobs, and what separates
them is what stands to its left: **a complete `.dd` figure ENDS a column**, so a
space after one is a column gap; anywhere else a digit run adjoining a
`<space><3 digits>` group is the head of one figure. Both halves are needed and
they fail in opposite directions — without the grouped integer part the figure
cannot match whole; without the boundary guard the truncated tail is what
matches instead.

```python
_THOUSANDS_SPACE = "\u0020\u00a0\u202f"
_SUMMARY_MONEY_RE = re.compile(
    rf"(?<![\d.,])"
    rf"(?:(?<=\.\d\d[{_THOUSANDS_SPACE}])|(?<![\d][{_THOUSANDS_SPACE}]))"
    rf"(?:\d[\d,]*(?:[{_THOUSANDS_SPACE}]\d{{3}})*)?\.\d{{2}}-?"
)
```

The separators are the ones `analysis/money.py` already surveys — its format
axes list `1 234.56` (:17) and `EITHER_MINUS_SPACED` (:214) exists to strip
them. `_money` now removes them before `parse_money`, which strips `$ , *` but
not spaces and SEARCHES rather than anchors, and would otherwise read
`1 000.00` as one dollar by a second route. `_average_balance` reads the same
figure grammar: same block, same printed format, and a document whose columns
are read whole must not publish a truncated average beside them.

**Effect on the 53 real bodies.** For 22 of them the pattern now returns a
different *list* of figures — every difference is at index 6 or later, in the
`Description Items Amount` index table and the `Daily Balance` grid that the
non-greedy body capture happens to include. `_summary_amounts` consumes
`amounts[:4]`. **No document's first four figures move**, and the end-to-end
sweep is byte-identical. Recorded because it is real: the boundary guard
suppresses figures that follow a bare digit run (`04/01 30,226.60`, `ACH
Additions 31 46,670.49`) in the part of the body no reading depends on.

## S3. Card P2 — `pnc`: a dated row that moves no money published as a posting

**Defect.** PNC genuinely prints sub-dollar amounts with the leading zero
dropped, so the row grammar must accept `.dd`; a dated informational line
carrying `.00` then satisfies it exactly as a posting does. `04/30 .00
Overdraft fees assessed this statement period` published as a third
transaction at approved/clear.

Nothing downstream can catch it: the row adds zero to the ledger sum and zero
to the section total, so `beginning + activity == ending` still holds with it
in the ledger, and PNC discloses no per-direction count oracle
(`analysis/count_semantics.py` `SECTION_LEVEL_ORACLES`) that could see the
extra row. The refusal has to happen at the row or nowhere.

**What the archive prints.** Over the 62 documents the two section readers
accept **6,673 rows**:

| measured | count | consequence |
|---|---:|---|
| rows carrying a **zero amount** | **0** | the rule reaches no printed posting |
| rows using the bare `.dd` form | **54** | genuine postings — `02/02 .82 ACH Credit Acctverify …`; the concession must stay |
| rows with **no** trailing reference number | **3,822** | a "postings carry a Reference number" rule is not available |

So the reference-number column — the other candidate the brief names — is not a
reliable structural discriminator on this layout, and is not used. The rule
shipped is the one the measurement supports: **a posting moves money.**

```python
def _posts(amount: float) -> bool:
    ...
    return amount != 0
```

`_posts` never reads the description, so a furniture wording this parser has
never seen is refused on the same grounds, and no real posting is refused for
how it is worded. Applied to `_parse_checks` as well, where `.00` is equally
readable and a cheque that moves no money is not a cheque.

`Total Overdraft Fees .00 .00` is unaffected and pinned as such: it is printed
outside the Balance Summary body and carries no date, so it was never a row.

## S4. Card B — `bmo_ca_business` `_MONEY_EN`: STOP, premise refuted by the archive

The card asks for `_MONEY_EN` to be aligned with its `_MONEY_FR` sibling —
`1 000.00` being "the Canadian/SI convention, on a CANADIAN bank". **The
archive says this printed layout does not use it, and that the space-grouped
shape means something else entirely on these documents.**

**Measurement 1 — every space-grouped occurrence is a reference number.** On
the lines the parser actually reads (the summary row it selects and the ledger
grid), the EN population contains **441 occurrences of `<1-3 digits><space><3
digits>.<dd>` across 65 of 168 documents**. Every one of the 30 read verbatim
is a merchant, cheque or account number abutting the amount column — and
Measurement 2 below is what generalises that from a sample to the population:

```
Apr 27 Debit Card Purchase, DOLLARAMA # 95 122.44 1,303.25
   -> store #95, amount 122.44, balance 1,303.25
Business Account # 3849 1981-774 277.52 23,730.09 23,955.40 502.83
   -> account 3849 1981-774, then the four summary cells
ISN: 5716186693 Cheque #174 500.00
   -> cheque #174, amount 500.00
Dec 01 Online Transfer, TF 3849#8840-536 800.00 1,077.52
   -> reference 3849#8840-536, amount 800.00, balance 1,077.52
```

The same lines print their real thousands **with commas** — `1,303.25`,
`23,730.09`, `239,642.85`.

**Measurement 2 — the separator census.** Of the 168 EN-population documents
with markdown:

| | documents |
|---|---:|
| print comma-grouped thousands **and** a space-shaped sequence | 65 |
| print comma-grouped thousands only | 96 |
| print a space-shaped sequence and **no** comma-grouped figure | **0** |
| print neither (no grouped figure at all) | 7 |

**No document in the archive uses the space as its thousands convention.** The
space-shaped sequences never stand alone; they always coexist with comma
grouping, which is what identifies them as reference numbers rather than
separators.

**Measurement 3 — the proposed fix, swept.** The literal alignment (FR's
separator class AND FR's `-` lookbehind; the separator class alone is not even
self-consistent, since without excluding `-` an account number's trailing group
starts a money cell):

```python
_MONEY_EN = re.compile(r"(?<![\d.,-])-?\$?(?:\d{1,3}(?:[,\u0020\u00a0\u202f]\d{3})+|\d+)\.\d{2}(?!\d)")
```

It does fix the reproducer, and the `-` exclusion does rescue the account-number
and transfer-reference lines. Over the 169-document `BMO` sweep:

| | |
|---|---:|
| movers | **30** |
| `validated/approved` → `withheld/withheld_adb` | **30** |
| any document improved | **0** |

Named movers, with the row each loses (glued cell → `parse_grouped_float`
raises → the row is skipped → continuity breaks → withheld):

| document | txns | first row lost |
|---|---|---|
| `BMO/3b3a1a46_April 30_ 2026.pdf` | 115 → 114 | `-122.44 Debit Card Purchase, DOLLARAMA # 95` |
| `BMO/3dc6c574_December 31_ 2025.pdf` | 122 → 120 | `-126.44 Debit Card Purchase, MARSHALLS #723` |
| `BMO/3ecfcd90_April 30_ 2025.pdf` | 74 → 72 | `-938.04 Debit Card Purchase, BEST BUY #84` |
| `BMO/3ecfcd90_March 31_ 2025.pdf` | 122 → 121 | `-115.42 Debit Card Purchase, BEST BUY #84` |
| `BMO/548fa9bf_July 31_ 2025-1.pdf` | 59 → 58 | `-143.18 Debit Card Purchase, SWISS CHALET #1` |
| `BMO/7246d185_February 27_ 2026.pdf` | 206 → 205 | `-137.74 Debit Card Purchase, FOOD BASICS 63` |
| `BMO/8b7d99d9_April 30_ 2026.pdf` | 198 → 189 | 9 rows |
| `BMO/8b7d99d9_February 27_ 2026.pdf` | 153 → 148 | 5 rows |

…30 in total. The brief's stop condition — "any outcome-class regression is a
stop" — fires. **`analysis/bmo_ca_business.py` is unchanged on this branch.**

**What the truncation actually is.** At the token level `1 000.00` (a
space-grouped amount) and `# 95 122.44` (a store number beside an amount) are
the same string shape. No lookbehind separates them: the `-` exclusion handles
the `1981-774` and `8840-536` forms but not the `# <digits>` form, which is the
common one. And the mutant is self-consistent under truncation — every figure
truncates together, the balance-continuity rule this module relies on still
holds, `Closing totals` still agrees with the summary, `Number of items
processed` still matches — so there is no second printing to catch it either.

The one place the ambiguity resolves is **document level**: no archive document
mixes the two conventions (0 space-only, 161 comma-bearing). A rule of the form
"a document that prints comma-grouped thousands anywhere is a comma-grouping
document, so a space in it is not a separator" would be correct on 161/161 of
the documents that print any grouped figure, and would read the fuzzer's
document (which prints no comma anywhere) correctly. That is a real design with
archive support, but it is per-document state threaded through `_cells`, it is
materially more than the card scopes, and getting it wrong publishes wrong
numbers silently — the exact failure class being closed. **Carried to Ocean as
a proposal (§S6), not taken unilaterally.**

Two smaller findings from the same measurement:

* The FR-style `-` lookbehind, **alone**, removes **0** matches on the whole
  169-document population — it is free. It does not fix the card (without the
  separator class `1 000.00` still truncates), so it is not shipped as a change
  with no defect behind it; it is available to Ocean as a one-character
  hardening if the document-level rule is ever taken.
* `_MONEY_FR`'s lookbehind excluding `-` is load-bearing for exactly this
  reason, and the EN sibling's omission of it is only harmless because EN does
  not admit space groups. The two facts are coupled: **whoever adds the
  separator class must add the `-` exclusion in the same change.**

## S5. Proofs

All from the worktree at HEAD, `set -o pipefail`, exit codes verbatim.

```
$ git rev-parse --abbrev-ref HEAD ; git rev-parse --short HEAD
wave3-structfix-1
367baa0                                            (this log is the commit after)

$ git status --short
(clean)

$ python repro.py                                  # wave scratch, against main
   P1-A  MUTANT (ASCII space): beginning=0.0   ending=200.0   ADB=243.33   approved/clear
   P1-C  MUTANT: 3 rows, third is ('2026-04-30', 'Overdraft fees assessed …', -0.0)
   P1-B  MUTANT (ASCII space): beginning=0.0   ending=100.0   ADB=115.0    approved/clear

$ python sf_repro_worktree.py                      # same reproducer, this branch
   P1-A  MUTANT (ASCII space): beginning=1000.0 ending=1200.0 ADB=1243.33  == TRUTH
   P1-A  MUTANT (U+00A0 NBSP): beginning=1000.0 ending=1200.0 ADB=1243.33  == TRUTH
   P1-C  MUTANT: 2 rows, the zero-amount line is gone                      == TRUTH
   P1-B  MUTANT: unchanged — Card B not shipped (§S4)

$ python -m pytest tests/test_pnc_variants.py -q   # against base_tree (cc3ab29)
7 failed, 16 passed                                PREFIX_EXIT=1
   the 7 are the new fixtures that pin the two defects;
   the other 4 new ones are controls and pass in both directions

$ python -m pytest tests/test_pnc_variants.py -q   # this branch
23 passed                                          EXIT=0

$ python -m pytest -q
2573 passed, 18 deselected, 1 warning in 259.65s   SUITE_EXIT=0

$ python -m pytest tests/test_no_statement_hardcodes.py tests/test_r1_hardcodes.py \
      tests/test_no_parser_helper_clones.py -q
100 passed in 1.28s                                GUARDS_EXIT=0

$ python -m pytest tests/test_parser_conformance.py tests/test_parser_registry_entries.py \
      tests/test_parser_parity.py tests/test_parser_detection_markers.py \
      tests/test_pnc_variants.py tests/test_bmo_layouts.py -q
733 passed, 9 deselected in 2.20s                  CONFORMANCE_EXIT=0

$ python -m pytest -m corpus -q
14 passed, 2577 deselected, 1 warning in 2333.07s  CORPUS_MARKED_EXIT=0

$ python corpus_gate.py
Coverage: 109 pinned PDFs (103 native text, 6 committed OCR), 0 exclusions
Outcomes: 106 PASS / 3 WITHHELD
Runtime:  753.7s
RESULT: GREEN                                      GATE_EXIT=0

$ python sf_sweep.py "PNC Bank" …   (base_tree vs branch)
folder='PNC Bank' documents=62 no_markdown=0 crashed=17
BYTE-IDENTICAL                                     CMP_EXIT=0

$ python sf_sweep.py "BMO" …        (base_tree vs branch)
folder='BMO' documents=169 no_markdown=1 crashed=10
BYTE-IDENTICAL                                     CMP_EXIT=0
```

The sweep harness is scratch-only and not committed, per §TRIO-4.5 / §M2
precedent; only aggregate counts and named movers are reported.

## S6. Carried findings and questions for Ocean

1. **Card B is not shipped, and should not be shipped in the form the card
   states.** §S4 is the evidence. The decision to want is whether the
   document-level separator determination is worth a scoped follow-up card, or
   whether the residual risk (a genuine space-thousands BMO EN document, which
   the archive does not contain) is accepted as fail-open until one appears.
2. **The same question exists for every parser whose money pattern admits
   space grouping while its layout prints reference numbers next to amounts.**
   `_MONEY_FR` already admits it and already carries the `-` exclusion; whether
   the FR population contains a `# <digits> <amount>` shape was not measured —
   out of scope here, and worth a card.
3. **`_average_balance` was fixed alongside Card P1** (same block, same defect,
   one line past the card's `:50`). Separable if Ocean wants it out: it is the
   `_LABELLED_FIGURE` use inside `_average_balance` only.
4. **`_posts` was applied to `_parse_checks` as well as `_parse_section`.** The
   card names `:131`. The cheque reader has the identical hole and zero real
   rows are affected; disclosed rather than assumed.
5. **What refusing a fragment does when the body has spare figures.**
   `_summary_amounts` takes the first four figures of a loose scan over a body
   that, on many real documents, runs well past the Balance Summary grid. So a
   figure the guard refuses is not always a `None` — on a body with more than
   four figures the four taken simply shift along. That is still strictly
   better than what it replaces: the shifted four do not cohere, so
   reconciliation sees it, whereas the truncated four cohered perfectly and
   nothing saw it. Fail-loud replacing fail-silent, not fail-closed replacing
   fail-silent, and worth saying plainly. Tightening the body capture to end at
   the Balance Summary grid would make it fail-closed properly; that is a
   separate change and is not made here.
6. **`ANALYSIS_STAGE_VERSION` bump** is required at merge and is not done here.
7. The 17 unclaimed `PNC Bank` documents and the 11 unclaimed `BMO` documents
   are untouched by this branch and remain `no_parser_matched`. They are
   coverage, not false validation, and belong to a different wave.

## S7. Commits

```
1cf9a1c  fix(pnc): a space-grouped thousands figure is one figure, not its tail
367baa0  fix(pnc): a dated row that moves no money is not a posting
<LOG>    log: §STRUCTFIX-1
```
