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
