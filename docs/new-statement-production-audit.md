# New Bank Statement Production-Readiness Audit

Audit date: 2026-08-03

## Verdict

The four supplied PDFs are safe to process with the current implementation. All four ledgers reconcile, all four standard ledger ADB values independently match production, all posted credits have one revenue state, and API/dashboard/export values match the backend.

Three statements are eligible for normal automated processing. Columbia is mathematically reconstructable, but the supplied PDF declares five bank pages and contains only pages 1 through 4. The application now reports `missing_declared_statement_page` with integrity risk `review`; it does not silently auto-clear the document. No value is withheld because the complete account summary, transaction sections, check register, daily balances, and closing reconciliation are present.

Release verdict: **SAFE TO MERGE**. Columbia remains a source-document review item, not an unresolved parser defect.

## Audit Totals

| Measure | Result |
|---|---:|
| New PDF files discovered | 4 |
| Statements/accounts audited | 4 |
| Pages manually inspected | 27 |
| Passed without parser changes | 0 |
| Parser/calculation paths fixed | 4 |
| Fully auto-clear statements | 3 |
| Manual document-integrity review | 1 |
| Withheld values | 0 |
| Unsupported formats | 0 |
| Ledger reconciliation pass rate | 4/4 (100%) |
| ADB pass rate | 4/4 (100%) |
| Revenue-classification pass rate | 4/4 (100%) |
| API/export/dashboard pass rate | 4/4 (100%) |

## Source Inventory

| File | Bank / Account | Period / Days | Pages | Source | Parser | Accounts | Running Balance | Daily Table | Printed Average | Consistency |
|---|---|---|---:|---|---|---:|---|---|---|---|
| Columbia May 26 complete.pdf | Columbia Bank, Marketplace Checking, suffix 4166 | May 1-31, 2026 / 31 | 4 PDF pages; bank labels 1-4 of 5 | Scanned, local OCR | `columbia-bank-deterministic` | 1 | EOD evidence only | Yes | Average balance $13,275.65 | Ledger consistent; declared page 5 absent |
| First Farmers 2026 01-document.pdf | First Farmers Bank & Trust, Business Basic Checking, suffix 0947 | Jan 1-30, 2026 / 30 | 3 | Scanned, local OCR | `first-farmers-bank-&-trust-deterministic` | 1 | Yes | No | Average Balance $2,979.63; Avg Available $2,779.44 | Consistent |
| Navigant Credit Union 2026-06-30.pdf | Navigant Credit Union, Quest Balance Checking, suffix 8125 | Jun 1-30, 2026 / 30 | 8 PDF pages; six numbered bank pages plus disclosure/blank pages | Digital | `navigant-credit-union-deterministic` | 1 | Yes | No | None | Gross ledger and settled summary both consistent |
| Relay Operations-June-2026.pdf | Thread Bank through Relay, Operations, suffix 7450 | Jun 1-30, 2026 / 30 | 12 | Digital | `thread-bank-(relay)-deterministic` | 1 | Yes, newest-first source | No | None | Consistent after restoring chronological order |

SHA-256 identifiers are enforced in `tests/test_new_statement_corpus.py`, so the regression tests cannot silently audit a replacement file with the same name.

## Required Results

`Credits` and `Debits` below are gross posted ledger activity so that opening + credits - debits = ending and every credit has exactly one revenue state. Navigant separately prints settled activity that excludes both sides of 11 rejected debit/reversal pairs.

| Statement | Opening | Ending | Gross Credits | Gross Debits | Bank Settled Credits | Bank Settled Debits | Independent ADB | Production ADB | Verified | Unverified | Non-Revenue | Revenue Upper Bound | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Columbia | $6,291.76 | $13,904.87 | $147,052.51 | $139,439.40 | $147,052.51 | $139,439.40 | $13,275.65 | $13,275.65 | $98,103.31 | $5,002.00 | $43,947.20 | $103,105.31 | MANUAL_REVIEW_REQUIRED |
| First Farmers | $1,552.27 | $2,028.08 | $6,705.81 | $6,230.00 | $6,705.81 | $6,230.00 | $2,979.64 | $2,979.64 | $0.00 | $6,705.81 | $0.00 | $6,705.81 | FIXED |
| Navigant | $19,207.58 | -$989.63 | $150,484.24 | $170,681.45 | $108,982.74 | $129,179.95 | $2,770.02 | $2,770.02 | $1,543.85 | $107,438.89 | $41,501.50 | $108,982.74 | FIXED |
| Relay | $175.71 | $0.70 | $14,799.79 | $14,974.80 | $14,799.79 | $14,974.80 | $122.62 | $122.62 | $2,020.00 | $0.00 | $12,779.79 | $2,020.00 | FIXED |

## Mathematical Proof

All arithmetic below uses decimal currency values and inclusive calendar days.

| Statement | Closing identity | Daily balance sum / days | Result |
|---|---|---|---:|
| Columbia | 6,291.76 + 147,052.51 - 139,439.40 = 13,904.87 | 411,545.17 / 31 | $13,275.65 |
| First Farmers | 1,552.27 + 6,705.81 - 6,230.00 = 2,028.08 | 89,389.16 / 30 | $2,979.64 |
| Navigant gross ledger | 19,207.58 + 150,484.24 - 170,681.45 = -989.63 | 83,100.46 / 30 | $2,770.02 |
| Navigant settled summary | 19,207.58 + 108,982.74 - 129,069.95 - 110.00 = -989.63 | Same gross ledger daily series | $2,770.02 |
| Relay | 175.71 + 14,799.79 - 14,974.80 = 0.70 | 3,678.57 / 30 | $122.62 |

Every independently reconstructed calendar-day ending balance is listed here. Blank means the statement period ended on day 30.

| Day | Columbia May 2026 | First Farmers Jan 2026 | Navigant Jun 2026 | Relay Jun 2026 |
|---:|---:|---:|---:|---:|
| 1 | 9,072.74 | 1,552.27 | 3,546.64 | 112.75 |
| 2 | 9,072.74 | 1,372.27 | -112.55 | 0.75 |
| 3 | 9,072.74 | 1,372.27 | -123.81 | 21.50 |
| 4 | 14,908.58 | 1,372.27 | -971.28 | 1.50 |
| 5 | 9,369.15 | 4,778.08 | -763.11 | 54.08 |
| 6 | 14,479.21 | 4,838.08 | 7,178.20 | 0.08 |
| 7 | 15,322.85 | 2,338.08 | 7,178.20 | 0.08 |
| 8 | 10,705.49 | 2,338.08 | 2,442.61 | 0.08 |
| 9 | 10,705.49 | 2,338.08 | 1,466.96 | 0.08 |
| 10 | 10,705.49 | 2,338.08 | 161.46 | 0.08 |
| 11 | 18,768.22 | 2,338.08 | 28.98 | 485.41 |
| 12 | 13,726.42 | 2,138.08 | -931.86 | 207.39 |
| 13 | 16,712.17 | 4,738.08 | -931.86 | 302.53 |
| 14 | 37,211.56 | 4,738.08 | -931.86 | 280.59 |
| 15 | 19,110.95 | 4,878.08 | 895.37 | 74.25 |
| 16 | 19,110.95 | 4,878.08 | -728.52 | 56.24 |
| 17 | 19,110.95 | 4,878.08 | 63.22 | 9.06 |
| 18 | 9,772.30 | 4,878.08 | 5,955.29 | 278.05 |
| 19 | 4,831.08 | 4,878.08 | 5,955.29 | 62.08 |
| 20 | 7,525.18 | 2,278.08 | 3,931.50 | 0.00 |
| 21 | 13,011.28 | 2,278.08 | 3,931.50 | 153.63 |
| 22 | 9,619.35 | 2,128.08 | 353.41 | 2.00 |
| 23 | 9,619.35 | 2,528.08 | 10,353.41 | 0.00 |
| 24 | 9,619.35 | 2,528.08 | 290.41 | 1,175.34 |
| 25 | 9,619.35 | 2,528.08 | 15,604.26 | 310.30 |
| 26 | 9,677.65 | 2,528.08 | 6,498.26 | 57.28 |
| 27 | 17,084.73 | 2,528.08 | 5,914.99 | 2.58 |
| 28 | 12,285.24 | 2,528.08 | 5,914.99 | 2.58 |
| 29 | 13,904.87 | 2,528.08 | 1,919.99 | 27.58 |
| 30 | 13,904.87 | 2,028.08 | -989.63 | 0.70 |
| 31 | 13,904.87 |  |  |  |
| **Sum** | **411,545.17** | **89,389.16** | **83,100.46** | **3,678.57** |

The minimum/maximum balances are Columbia $4,831.08/$37,211.56; First Farmers $1,372.27/$4,878.08; Navigant -$989.63/$15,604.26 with nine negative days; Relay $0.00/$1,175.34. No leap day occurs in these four periods. Existing leap-year tests remain green.

## Printed Average Review

- Columbia's printed `Average balance` is $13,275.65 and exactly matches standard ledger ADB.
- First Farmers' cent-ledger mean is $2,979.638666..., which rounds half-up to $2,979.64. The printed `Average Balance` is $2,979.63, consistent with truncation rather than half-up rounding. Its separate `AVG AVAILABLE BALANCE` of $2,779.44 is not ledger ADB.
- Navigant and Relay do not print an average balance.

## Revenue Proof

| Statement | Classification evidence |
|---|---|
| Columbia | 48 dental claim, EDIRPAY, and merchant-card settlement credits total $98,103.31 verified. One generic deposit of $5,002.00 is unverified. Four Bizpoint funding credits total $43,849.20 and one $98.00 MetLife reversal are non-revenue. |
| First Farmers | All five credits are generic/check/cash deposits with insufficient source evidence, totaling $6,705.81 unverified. None is automatically verified. |
| Navigant | One Square settlement of $1,543.85 is verified. Nineteen source-ambiguous deposits total $107,438.89 unverified. Eleven rejected-debit reversal credits total $41,501.50 non-revenue. |
| Relay | Two Intuit payment credits total $2,020.00 verified. Fifteen internal transfers total $3,434.53, 25 Visa/card credits total $6,060.79, and nine returned ACH credits total $3,284.47; all $12,779.79 is non-revenue. No credit remains unverified. |

For every statement, `Verified + Unverified + Non-Revenue = gross posted credits`, and `Revenue Upper Bound = Verified + Unverified`. Returned credits, internal transfers, funding, refunds, and cash-advance/card credits do not enter the analyst deposit-review queue.

## Lender, Insurance, And Channel Metrics

| Statement | Confirmed lender activity | Potential activity | Insurance | ACH C/D | POS | ATM | Checks | NSF / returned |
|---|---|---|---|---:|---:|---:|---:|---|
| Columbia | Bizpoint, Kapitus, Forward Financing, Rapid Finance/SBFS, Fundation, BHG, and SBA: 26 debits / $79,378.55 | Three explicit but unverified loan debits / $19,412.49 | 0 / $0.00 | 52 / 49 settled | 0 | 0 | 2 | 0 / 1 reversal pair |
| First Farmers | Bluevine: 1 / $100.00 | 0 | 0 / $0.00 | 0 / 0 | 5 | 0 | 1 | 0 / 0 |
| Navigant | 0 | Beacon Bank loan: 1 settled debit / $1,191.00; the earlier rejected attempt is excluded | 2 / $1,251.74 | 1 / 37 settled | 30 | 0 | 20 settled | 5 NSF fees / 11 rejected pairs |
| Relay | 0 | 0; lender-like card credits remain non-revenue but are not fabricated as withholding | 0 / $0.00 | 2 / 8 settled | 66 purchases | 9 | 0 | 0 / 9 returned ACH pairs |

Confirmed withholding uses confirmed lender debits only. Potential lender debits remain outside the confirmed numerator. Insurance and reversed attempts are excluded. Bizpoint funding credits reduce Columbia's legacy eligible-deposit denominator by $43,849.20.

## Defects Found And Fixed

| Statement / scope | Before | Root cause | Corrective action |
|---|---|---|---|
| Columbia | Generic extraction used Apr 30-May 31 (32 days), had $26,999 ledger drift, and produced a non-defensible $13,066.78 candidate | OCR date/decimal corruption, one $3,000 amount error, one $30,000 recurring-credit error, and no page-sequence check | Added section totals, dominant recurring-payment evidence, daily-table agreement, exact period derivation, and missing-page integrity detection |
| First Farmers | ADB happened to be correct, but no maintained parser proved all 16 running transitions and source counts | New image-only layout | Added a deterministic running-balance parser and source regression |
| Navigant | ADB withheld; gross detail appeared 138%/132% of printed totals with $63,003 drift | Rejected debit attempts and reversal credits were treated as unrelated settled activity | Derived signs from every printed running balance and reconciled gross ledger separately from settled summary |
| Relay | ADB withheld and 158 false continuity breaks | Reverse-chronological source order was treated as forward order | Reversed the complete source stream, retained within-day order, and validated every transition |
| Shared ADB guard | Columbia's page header/daily table created a false missing posting date | Page/date heuristic treated `Page: 1 of 5` or a daily-summary line as activity | Excluded page headers and labeled daily-balance sections from source posting dates |
| Shared classifications | Returned attempts could inflate ACH/check/lender counts; unnamed explicit loan payments were omitted from potential exposure | Gross ledger and settled activity shared one counting path | Added evidence-matched reversal links and separate settled activity counting; explicit unnamed loan payments are potential only |
| Test discovery | A generated baseline worktree under `output/` could be collected as a duplicate test package | Artifact directories were not excluded explicitly | Added `norecursedirs = output`; the complete source suite under `tests/` remains collected |

No filename, account-number, or statement-amount exception was added. Every parser is selected by bank/layout evidence and fails closed when section totals, running balances, summary identities, or final balances do not reconcile.

## Original Corpus Regression

The identical cached source text for the original 105 PDFs was analyzed at commit `27d4748` and with this change. Results:

- Transaction row hashes unchanged: 105/105.
- Transaction counts unchanged: 105/105.
- Gross credits, gross debits, and effective totals unchanged: 105/105.
- Opening, ending, ADB, minimum, and maximum unchanged: 104/105. The subsequent balance-metrics audit exposed a pre-existing IBC recap contradiction; that parser now preserves the printed recap and fails closed instead of substituting its conflicting daily table.
- Current original-corpus ADB result is 102 PASS, 3 WITHHELD, 0 FAIL.
- Current combined-corpus result is 106 PASS, 3 WITHHELD, 0 FAIL.

Twenty-five original statements have intentional classification/channel corrections. These are not ledger regressions:

| Statement(s) | Exact production change | Reason |
|---|---|---|
| Amex Apr / Jun | Insurance 0 -> 1; $0 -> $255 / $238 | `INS PREM` is now recognized |
| Chase Mar / May | POS 124 -> 123 and 112 -> 111; POS credits 5 -> 4 and 1 -> 0 | Matched reversal pairs no longer count as settled POS activity |
| Consumers March | Potential lender 0/$0 -> 2/$1,952.47 | Explicit automatic loan payments now enter potential review, never confirmed withholding |
| KLR May | Lender 0/$0 -> 1/$1,116; potential 1/$1,116 -> 0; insurance 1/$155.79 -> 2/$271.79 | Maintained BHG alias and insurance descriptor evidence |
| Link Bank April | Insurance 1/$2,786.14 -> 3/$5,013.36 | Explicit insurance premium rows |
| Altana May | Insurance 2/$2,511.35 -> 3/$3,849.00 | Explicit insurance premium row |
| Banco Popular Apr | Verified $0 -> $2,658.12; unverified $63,675.89 -> $61,017.77; lenders 4/$7,564.60 -> 2/$3,782.30; potential 20/$8,416.44 -> 14/$6,443.88 | Operating-source evidence plus reversal-pair exclusion |
| Banco Popular Jun | Verified $0 -> $6,457.19; unverified $77,254.08 -> $70,796.89; lenders 7/$11,416.90 -> 4/$6,171.66; potential 5/$10,850 -> 2/$4,340 | Same evidence-based corrections |
| Banco Popular May | Verified $0 -> $6,967.74; unverified $104,350.46 -> $97,382.72; lenders 7/$10,950.43 -> 6/$9,059.28; potential 5/$10,850 -> 4/$8,680 | Same evidence-based corrections |
| First Citizens | Insurance 0/$0 -> 1/$494 | Explicit insurance premium row |
| Santander Apr / Feb | Settled checks 61 -> 57 and 47 -> 45 | Returned check pairs excluded |
| PNC Jan / Apr | POS credits 0 -> 3 and 0 -> 1 | Debit-card credits are now identifiable refund/non-revenue activity |
| PNC Mar | Unverified $22,691.43 -> $22,447.43; non-revenue $3,123.69 -> $3,367.69; upper bound $22,691.43 -> $22,447.43; settled ACH 25/29 -> 17/21; POS credits 0 -> 2 | $244 identifiable card credits and eight reversal pairs |
| PNC May | Insurance 1/$1,673.55 -> 2/$2,532.89; settled ACH 20/35 -> 15/30; POS credits 0 -> 1 | Insurance evidence and five reversal pairs |
| RBC Jan / Mar | Settled checks 10 -> 8 and 8 -> 4 | Returned check pairs excluded |
| TD Narrow Apr / Jan | POS credits 0 -> 4 and 0 -> 3 | Debit-card credits classified as non-revenue refunds |
| Truist Apr / Auto Feb | Settled POS 76 -> 75 and 106 -> 103 | Matched reversals excluded |
| Truist Feb | POS credits 0 -> 1 | Debit-card credit classified as a refund |

## API, Dashboard, And Exports

- `metrics.average_daily_balance` is the only public ADB value. The nested ADB object contains proof and validations, not another numeric ADB.
- JSON, CSV, and XLSX tests assert each statement's ADB and daily-balance sum.
- Package ADB is weighted by days: `(411,545.17 + 89,389.16 + 83,100.46 + 3,678.57) / 121 = $4,857.14`.
- A live local Playwright package upload displayed all four statement ADB values, package ADB $4,857.14, and Relay modal ADB $122.62 in the existing card.
- No frontend file, dashboard card, label, layout, style, or component was changed.
- The local server was restarted on `http://127.0.0.1:5003` with the audited code.

## Automated Verification

- Final full repository run after the balance-metrics correction: `523 passed, 1 deselected` in 44.55 seconds.
- New source corpus: `16 passed`, reopening all four original PDFs and asserting all 121 daily balances.
- Focused ADB/classification/API/export suites: all pass.
- Live dashboard: `1 passed` with four-file package upload.
- Independent full ADB corpus: `106 PASS`, `3 WITHHELD_SOURCE_CONTRADICTION`, `0 FAIL`.

Machine-readable results are in `docs/new-statement-audit-results.csv`.

## Remaining Risks

- Columbia's supplied artifact is physically incomplete: its page labels declare page 5, but only pages 1-4 exist. The available financial sections reconcile uniquely, so values are not withheld; production correctly requires document-integrity review.
- Columbia and First Farmers are image-only formats. Their exact source hashes and OCR repairs are regression tested, but materially degraded future scans can still fail closed and require review.
- Three contradictory statements in the original corpus are withheld. The later balance-metrics audit added IBC after proving that its recap conflicts with both its detail and daily table.

## Final Answers

- **Are all statements in the new folder production-ready?** Yes. Three auto-clear; Columbia is safely processed with a mandatory source-integrity review.
- **Are any parser defects still unresolved?** No defect represented by these four sources remains unresolved.
- **Are any values being withheld?** No value from the new folder is withheld. Three original-corpus source contradictions are withheld as designed.
- **Did any existing corpus result regress?** No ledger, ADB, balance, transaction-count, or transaction-row result regressed. The intentional classification/channel corrections are itemized above.
- **Is the implementation safe to merge?** Yes, subject to retaining Columbia's review state and the existing two fail-closed source contradictions.
