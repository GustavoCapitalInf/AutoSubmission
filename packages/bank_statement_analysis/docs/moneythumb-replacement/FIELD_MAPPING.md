# Field Mapping — MoneyThumb → Our Platform

Phase 1 audit — MoneyThumb Replacement Initiative. Author: Ocean. Date: 2026-08-06.
Source: complete field catalog of `moneythumbResults/results/*/response.json`
(409 distinct JSON paths) vs our `report_to_dict` contract (`analysis/serialization.py`)
and package payload (`webapp/app.py:_package_analysis`).

Verdicts: **HAVE** (we emit an equivalent), **ADOPT** (add — materially improves the
product), **DERIVE** (cheap computation over data we already have), **IGNORE**
(redundant/deprecated/unsupported-by-evidence — deliberately not replicated).

## 1. Application / package level (`appinfo`)

| MoneyThumb field | Verdict | Our equivalent / disposition |
|---|---|---|
| `appid`, `appnumber` | ADOPT | We need a durable package/application entity with caller reference (today: ephemeral job-id list). |
| `owner`, `address1/2`, `city`, `state`, `zip` | ADOPT | Account-holder identity extraction. We only have `account_name`. Needed for package coherence checks. MT's own value misfires (bmo: "Interest Earned") — extraction must be evidence-gated. |
| `citystate` | IGNORE | Redundant concatenation. |
| `naccounts`, `accountlist[]` | ADOPT | Requires multi-account schema. MT's string-typed "acct - date" list is poor design; use structured entries. |
| `totalstatements`, `totalstatements_reconciled` | HAVE (partial) | Package `totals.completed/failed`; add reconciled count explicitly. |
| `totaltaxforms`, `totaltaxreturns`, tax fields | IGNORE | Out of scope — we do not ingest tax documents. |
| `expfactor` | IGNORE | Empty/unclear in every benchmark run. |
| `webSearch.*` | IGNORE (P3 at most) | Never populated in benchmark; web enrichment is a separate product decision. |

## 2. Per-file status (`file_status[]`, `statement_summaries[]` ops fields)

| MoneyThumb field | Verdict | Disposition |
|---|---|---|
| `filename`, `statusCode`, `message`, `tid` | HAVE (partial) | Job status exists; needs durable IDs + error taxonomy instead of raw exception strings. |
| `filePreviouslySeen.numInLast3Days` | ADOPT | Duplicate-submission detection via content hash — also fixes package double-counting (R-26). |
| `chargevalue`, `remaining` | IGNORE | Billing units — not applicable in-house; cost telemetry instead (DERIVE: per-statement processing cost/time). |
| `csvurl`, `logurl`, `outputurl`, `transactions:null` | IGNORE | Deprecated in MT itself. Our JSON already carries the full ledger — keep that advantage. |
| `webhook` | ADOPT | Async completion callback for scanned documents (G7). |

## 3. Document identification (`statement_summaries[].results[]`)

| MoneyThumb field | Verdict | Disposition |
|---|---|---|
| `detectedDocType`, `processedDocType`, `language`, `currencycode`, `country`, `pagecount` | ADOPT (partial HAVE) | We have currency + implicit doc handling; explicit doc-type/language/page metadata belongs in a document-inspection record. |
| `producer`, `cdate`/`mdate`, `image`, `ocr`, `maxResolution`/`minResolution` | ADOPT | PDF forensics inputs for the fraud/integrity subsystem (G6) — cheap to extract via PyMuPDF. |
| `uselessPages` | DERIVE | We already detect missing declared pages; page-utility classification is a small extension. |
| `bankName` | HAVE | `statement.bank`. |
| `bankURL`, `bankphones[]` | IGNORE | Cosmetic; placeholder values even in MT. |
| `fdicname/fdicaddress/fdiccity/fdicstate/fdiczipcode` | ADOPT (P2) | FDIC registry enrichment — public dataset join keyed on bank name/routing number. |
| `accountNumber` (unmasked), `isStrongAccountNo` | HAVE (partial) | We extract account number; must add masking policy at export (R-24) and a confidence flag. |
| `accounttype/accounttypestr` | ADOPT | PROJECT_GOAL requires account type; schema lacks the field today. |
| `accounttitle`, `accountOwner[]`, `company`, `isBusiness` | ADOPT | Business-vs-personal signal already influences classification; formalize extraction. MT's noisy lists ("Opening Balance" as an owner) show why evidence-gating matters. |
| `accountSequence`, `numAccounts` | ADOPT | Multi-account segmentation metadata. |
| `startDate/endDate`, `firstDate/lastDate` | HAVE (partial) | We have period bounds; add first/last transaction dates (trivial derive) — useful for month-to-date detection. |
| `isMonthToDate`, `numMonths`, `monthSequence`, `month_gap` | DERIVE | Package coherence checks (G5). |
| `numTransactions`, `numCredits/numDebits`, `totCredits/totDebits` | HAVE | metrics. |
| `startBalance`, `endBalance`, `endBalanceCalc`, `endBalancePDF` | HAVE | Ours is stronger: stated vs computed with reconciliation verdict and fail-closed export. |
| `balancesValid`, `columnsValid`, `headerValid`, `reconciled`, `fail` | HAVE | ReconResult + quality levels carry more detail. |
| `likelyMissingTransactions`, `suspectCount`, `numTypos`, `uncounted`, `nonTransactions[]` | HAVE (partial) | Coverage bands + integrity flags cover most; a typo/suspect-count style signal could feed fraud scoring (DERIVE). |
| `suggestion` | ADOPT | Operator-facing next-step hint strings ("second account detected but not analyzed") — high UX value, low cost. |
| `requiresRerunWithOCR`, `previewRequired` | HAVE (partial) | Worker ladder does this implicitly; surface it as an explicit flag. |
| `fraudscore`, `tpreasons[]`, `thumbprint_score`, `contributing_factors` | ADOPT | Composite tamper score with human-readable reasons (G6). Keep our arithmetic flags as one input; add PDF forensics. Do NOT copy the redundant score duplication. |
| `thumbprintData[]`, `balance_match` | IGNORE | Empty/dead in every benchmark payload. |

## 4. Scorecard transaction lists

| MoneyThumb list | Verdict | Disposition |
|---|---|---|
| `credit_transactions`, `true_credit_transactions`, `nontrue_credit_transactions` | HAVE | Our three-state revenue classification is strictly richer (verified/unverified/non-revenue + evidence + review loop vs MT's binary true/non-true). |
| `mca_transactions[].lender` | HAVE | FunderMatch evidence lists with canonical lender names. |
| `incoming_transfers`/`outgoing_transfers` + `Matches` | ADOPT | Transfer classification exists; **cross-account counterpart matching does not** (PARITY #14). Requires multi-account/package entities. |
| `large_transactions` | DERIVE | Trivial view over the ledger. |
| `repeating_transactions` | HAVE (partial) | We detect recurring debits (cadence-gated, lender-oriented); MT's list covers all recurring activity incl. credits — widen ours into a general recurring-transaction view. |
| `nsf_transactions`, `overdraft_transactions`, `returned_transactions` | HAVE | Classified rows with evidence; MT's were empty in all benchmark sets. |
| Transaction fields `memo` (raw ACH detail) | HAVE (partial) | Our `description` keeps printed text; we do not separately parse ACH subfields (Descr/Trace#/Ind Name). DERIVE later for counterparty analytics. |
| Transaction fields `number`, `type` | IGNORE | Always "0"/"" in MT output. But note: our schema also lacks check number — worth adding for our own reasons (check-section parsers already know it). |

## 5. Time series

| MoneyThumb field | Verdict | Disposition |
|---|---|---|
| `daily_balances[]` (activity days only) | HAVE (better) | Our validated per-calendar-day ledger with source markers is superior; MT's gaps make its ADB unverifiable. Keep ours; extend to package level. |
| `daily_balances[].od_balance` | IGNORE (P3) | Requires overdraft-limit extraction; niche. |
| `daily_balances[].true_balance` | ADOPT | True-balance duality: recompute daily ledger excluding non-revenue funds (MCA proceeds, transfers). High underwriting value; direct derivation from our classification (G6). |
| `daily_cash_flows`, `monthly_cash_flows` | DERIVE | Trivial from the ledger. |
| `monthly_negative_days` (3 variants) | DERIVE (partial HAVE) | We compute actual negative days; add true-balance variant; OD variant IGNORE with od_balance. |
| `monthly_recovery` | IGNORE | Empty in every benchmark payload; structure unknown. |
| `monthly_mca[]` (per-month per-lender cadence, `workdays`) | ADOPT | Best MT view we lack: month × lender withdrawal count/total/latest + funding deposits. Our FunderMatch has the data; needs the time-dimension rollup. |

## 6. Statement summary counters (`statements_summary[]`)

| Group | Verdict | Disposition |
|---|---|---|
| Balances (`avg_balance`, `min_balance`, `low_days`, `days_neg`) | HAVE | Fail-closed ADB, min/max, negative days. `avg_true_balance` → ADOPT (true-balance duality). `low_days` (days below threshold) → DERIVE. |
| Volume (`total/num credits/debits`, `net_cashflow`) | HAVE | metrics. `true_expenses`, `true_profit` → DERIVE once debit-side true classification is defined. |
| MCA group (`num_of_mca_positions`, `mca_withhold_percent`, `mcas_with_deposits`, `mca_deposit_dates`) | HAVE (partial) | We have funders, debits, exposure; position counting and funding-date surfacing → DERIVE. |
| NSF/OD (`num_nsfs`, `total_nsfs`, `num_ods`, `num_stops`, `days_w_returns`) | HAVE (partial) | NSF counts/totals yes; OD events and stop-payments are not distinct categories today → ADOPT (classifier states). |
| Category counters (~20: payroll, insurance, factoring, healthcare, mobile payments, payment processors, tolls, construction, debt collectors, "nefarious", investments, non-MCA loans, other financing, nondescript revenue, recovery) | ADOPT (selective) | Our 16-state taxonomy covers payroll/insurance/loan/transfer/fee/tax/utility/lease. Worth adding: factoring, payment-processor, healthcare-claims, debt-collector as registry-backed categories. IGNORE "nefarious" (undefined), tolls/construction (niche verticals) unless business demand. |
| `fraud_score` + `thumbprint_score` duplication, 4 month renderings, string-typed numbers | IGNORE | Schema defects, not features. |

## 7. `revenue_statistics[]` (27 label/monthly/annual rows)

| Rows | Verdict | Disposition |
|---|---|---|
| Revenue / True Revenue / Non-True Revenue / Expenses / Profit | HAVE (partial) | Our revenue triple is stronger; monthly averaging needs true month semantics (G5). |
| DTI Percent, Debt Service Coverage Ratio, Total Debt Withdrawals, MCA Withhold Percent | ADOPT | Core underwriting ratios (G6). Definitions must be ours, documented, and evidence-based — MT's are opaque. |
| Average Monthly Net/Factoring/Credit Card Revenue, Minimum Monthly True Revenue, Average True Revenue (Recent) | DERIVE | Monthly rollups over classified ledger (credit-card revenue requires processor-source tagging we partially have). |
| Months Since Last Negative Balance, Average Daily Cash Flow, Average Monthly Deposit Count, Total Days Parsed | DERIVE | Trivial. |
| `Total Revenue` (actually net cash flow) | IGNORE | Mislabeled in MT — a defect we must not copy. |
| The label/monthly/annual loose-table format itself | IGNORE | Emit typed, named fields; never a stringly stats table. |

## 8. Fields WE emit that MoneyThumb lacks (preserve — competitive advantages)

- Complete classified transaction ledger with per-row evidence (method, alias, rule,
  confidence, reason, source location, related transaction, review state).
- Reconciliation detail: issues list, coverage ratios, reversal-adjusted totals,
  summary-identity variants.
- ADB validation suite results + per-day source-marked daily ledger + debug trace.
- Three-state revenue with conservation identity and analyst review loop.
- Quality/corporate-use gating and document-integrity flags with explicit fail-closed
  semantics ("rejected numbers are never API data").
- Withholding-rate workings with formula provenance and configurable denominator.

## Adoption summary

**ADOPT (new capabilities):** package/application entity + caller ref; multi-account
schema + segmentation metadata; account-holder identity + account type + business flag;
duplicate-document detection; webhook/async job contract; PDF forensics + composite
tamper score with reasons; operator `suggestion` strings; cross-account transfer
matching; true-balance daily series; monthly MCA cadence rollup; DTI/DSCR/withhold%;
selective new classifier categories (factoring, processor, healthcare, debt-collector,
OD/stop-payment); FDIC enrichment (P2).

**IGNORE (deliberately):** tax fields, webSearch, billing fields, deprecated URLs/inline
ledgers, dead/empty fields, redundant renderings, string-typed schema patterns,
mislabeled Total Revenue, "nefarious" category, od_balance (P3).
