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
