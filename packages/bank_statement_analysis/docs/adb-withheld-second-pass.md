# ADB Withheld Statements: Second-Pass Forensic Review

## Conclusion

| Statement | Classification | Parser missed data | OCR missed visible data | Unique exact ADB |
|---|---|---:|---:|---:|
| Ace_Auto_Final_Cut.pdf | A - supplied PDF has incomplete transaction detail | No | No | No |
| BMO_Statement_January_2026 Final-1-2 (1).pdf | A - supplied PDF has mutually contradictory financial records | No | No | No |

Both ADB values must remain withheld. This conclusion was rebuilt from the PDF bytes and does not rely on the first audit's candidate ledgers.

## Source Identification

| Statement | SHA-256 | Pages | Page geometry | Rotation |
|---|---|---:|---|---:|
| Ace_Auto_Final_Cut.pdf | A8BA41E099580C8D64C1CF683107F2287343C1581B614A51E20ECA079C0883E2 | 3 | 612 x 792 points on every page | 0 degrees |
| BMO_Statement_January_2026 Final-1-2 (1).pdf | E86143101E28E198EC5278B065E8BA967DD73E9AB735A1CAC4A0FE7CB46CB83F | 2 | 612 x 792 points on every page | 0 degrees |

The local branch and `origin/main` were both at commit `03b72c98fe4b872a2a04e5fc6b4fd5aead53ed10` after a fresh fetch. Git history contains one unchanged PDF blob for each statement; earlier commits only renamed the same Ace blob. There is no fuller repository copy.

## Inspection Method

Each page was inspected in four independent forms:

1. A full-page 200 DPI rendering.
2. A fresh 300 DPI rendering and Tesseract OCR using page segmentation modes 6 and 11.
3. Poppler native text in layout, raw, and bounding-box modes.
4. PyMuPDF page-object, word-coordinate, text-render, image, annotation, layer, attachment, and page-tree inspection.

Neither PDF contains image-only transaction regions. The only raster objects are header logos. All transaction and summary data are digital text. There are no rotated pages, alternate crop/trim/bleed boxes, annotations, attachments, optional-content layers, invisible text runs, words outside the visible page, unlinked page objects, or omitted page-tree entries. Native extraction and fresh OCR agree with the rendered pages.

## Manual Page Inventory

### Farmers & Merchants

- Page 1: account summary, exact December 1-31, 2025 period, opening balance, aggregate counts and totals, closing balance, Average Ledger, and Average Collected.
- Page 2: three deposits and eight visible checks/debits. The final 12/30 transaction's trace details continue onto page 3.
- Page 3: the 12/30 continuation text, three 12/31 checks/debits, one total service-charge row, and one informational service-charge component row. The remainder of the page is visibly blank.

### BMO

- Page 1: January 2026 summary, all 41 transaction rows, a printed balance on every row, and a footer explicitly saying transactions 1-41.
- Page 2: a second account-summary section and final balance. There is no continuation table.

## Farmers & Merchants Proof

### Summary identity

The page-1 summary itself reconciles exactly:

```
opening       -78.68
+ credits   7,329.22
- debits    3,945.12
- service       8.00
--------------------
closing      3,297.42
```

The visible details contain:

| Category | Printed summary | Visible detail | Missing |
|---|---:|---:|---:|
| Deposits | 3 / $7,329.22 | 3 / $7,329.22 | 0 / $0.00 |
| Checks/debits | 26 / $3,945.12 | 11 / $1,001.67 | 15 / $2,943.45 |
| Service charge | $8.00 | $8.00 | $0.00 |

The `BALANCE FEE IN SERVICE CHARGE 8.00-` row is a component of the immediately preceding `TOTAL SERVICE CHARGE 8.00 SC`, not a second debit. Counting it twice would conflict with both the summary and closing balance.

### Every reconstructed daily balance

`Visible-only` uses exactly the rows present in the PDF. Completions A and B are two different hypothetical sets of the 15 absent debits. They are not parser corrections; they prove non-uniqueness.

| Date | Visible-only EOD | Completion A EOD | Completion B EOD |
|---|---:|---:|---:|
| 2025-12-01 | $1,006.74 | $1,006.74 | $1,006.74 |
| 2025-12-02 | $974.74 | $974.74 | $974.74 |
| 2025-12-03 | $974.74 | $974.74 | $974.74 |
| 2025-12-04 | $974.74 | $974.74 | $974.74 |
| 2025-12-05 | $974.74 | $974.74 | $974.74 |
| 2025-12-06 | $974.74 | $974.74 | $974.74 |
| 2025-12-07 | $974.74 | $974.74 | $974.74 |
| 2025-12-08 | $3,974.74 | $3,974.74 | $3,974.74 |
| 2025-12-09 | $3,974.74 | $3,974.74 | $3,974.74 |
| 2025-12-10 | $3,790.58 | $3,790.58 | $3,790.58 |
| 2025-12-11 | $3,590.58 | $3,590.58 | $3,590.58 |
| 2025-12-12 | $3,590.58 | $3,590.58 | $3,590.58 |
| 2025-12-13 | $3,590.58 | $3,590.58 | $3,590.58 |
| 2025-12-14 | $3,590.58 | $1,266.53 | $1,275.83 |
| 2025-12-15 | $3,590.58 | $647.13 | $647.13 |
| 2025-12-16 | $3,590.58 | $647.13 | $647.13 |
| 2025-12-17 | $3,590.58 | $647.13 | $647.13 |
| 2025-12-18 | $3,590.58 | $647.13 | $647.13 |
| 2025-12-19 | $3,540.58 | $597.13 | $597.13 |
| 2025-12-20 | $3,540.58 | $597.13 | $597.13 |
| 2025-12-21 | $3,540.58 | $597.13 | $597.13 |
| 2025-12-22 | $3,540.58 | $597.13 | $597.13 |
| 2025-12-23 | $3,356.50 | $413.05 | $413.05 |
| 2025-12-24 | $3,356.50 | $413.05 | $413.05 |
| 2025-12-25 | $3,356.50 | $413.05 | $413.05 |
| 2025-12-26 | $3,356.50 | $413.05 | $413.05 |
| 2025-12-27 | $3,356.50 | $413.05 | $413.05 |
| 2025-12-28 | $3,356.50 | $413.05 | $413.05 |
| 2025-12-29 | $6,581.01 | $3,637.56 | $3,637.56 |
| 2025-12-30 | $6,561.72 | $3,618.27 | $3,618.27 |
| 2025-12-31 | $6,240.87 | $3,297.42 | $3,297.42 |

| Ledger | Daily-balance sum | Exact ADB | Rounded ADB | Closing |
|---|---:|---:|---:|---:|
| Visible only | $101,004.80 | $3,258.219354... | $3,258.22 | $6,240.87 |
| Completion A | $48,642.10 | $1,569.10 | $1,569.10 | $3,297.42 |
| Completion B | $48,651.40 | $1,569.40 | $1,569.40 | $3,297.42 |

Completion A places seven absent debits totaling $2,324.05 on December 14 and eight totaling $619.40 on December 15. Completion B places seven absent debits totaling $2,314.75 on December 14 and eight totaling $628.70 on December 15. Each group can be split into positive cent-denominated transactions, for example six or seven $1.00 items plus the remainder. Both completions therefore have exactly 26 checks/debits totaling $3,945.12 and exactly the printed closing balance.

Both exact ADBs display as the statement's whole-dollar `Average Ledger 1,569` under either truncation or nearest-dollar rounding, yet they differ by $0.30. The whole-dollar printed value cannot identify the missing posting dates or the exact cent-level ADB. Infinitely many additional allocations are possible.

**Classification: A.** The supplied PDF's aggregate and detail sections are inconsistent. Its exact ADB cannot be uniquely reconstructed.

## BMO Proof

### Independent line-item totals

The visible table contains exactly the 41 rows claimed by its footer:

| Category | Page-1 summary | Page-2 summary | Visible detail |
|---|---:|---:|---:|
| Deposits | $294,700.00 | $300,000.00 | 27 / $255,500.00 |
| Withdrawals | $25,000.00 | $25,000.00 | 14 / $23,250.00 |
| Interest | $200.00 | $200.00 | $0.00 |
| Fees | -$1,000.00 | $1,000.00 | $0.00 |
| Closing/final | $1,000,000.00 | $1,000,000.00 | $962,350.00 from row amounts |

The page-1 summary reaches $1,000,000 only if its $1,000 fee is already included in total withdrawals:

```
730,100 + 294,700 - 25,000 + 200 = 1,000,000
```

Subtracting the fee separately produces $999,000. The page-2 summary cannot reconcile under either convention:

```
fee separate: 730,100 + 300,000 - 25,000 + 200 - 1,000 = 1,004,300
fee folded:   730,100 + 300,000 - 25,000 + 200         = 1,005,300
```

Page 1 and page 2 also disagree by $5,300 on deposits. Dates cannot repair any endpoint identity because transaction dates alter ADB weighting, not the final arithmetic sum.

### Every reconstructed daily balance and conflicting printed EOD

Same-day ordering cannot explain these differences: each printed EOD below is the final printed row for that date, and grouping all same-day amounts leaves the same net activity under every ordering.

| Date | Net visible activity | Amount-derived EOD | Printed final EOD | Difference |
|---|---:|---:|---:|---:|
| 2026-01-01 | +$23,576.00 | $753,676.00 | $751,676.00 | -$2,000.00 |
| 2026-01-02 | +$13,000.00 | $766,676.00 | $765,676.00 | -$1,000.00 |
| 2026-01-03 | +$11,138.00 | $777,814.00 | $792,600.00 | +$14,786.00 |
| 2026-01-04 | +$10,788.00 | $788,602.00 | $803,600.00 | +$14,998.00 |
| 2026-01-05 | +$24,588.00 | $813,190.00 | $823,890.00 | +$10,700.00 |
| 2026-01-06 | +$9,988.00 | $823,178.00 | $824,600.00 | +$1,422.00 |
| 2026-01-07 | +$10,700.00 | $833,878.00 | $833,570.00 | -$308.00 |
| 2026-01-08 | +$23,576.00 | $857,454.00 | $846,100.00 | -$11,354.00 |
| 2026-01-09 | +$10,788.00 | $868,242.00 | $867,600.00 | -$642.00 |
| 2026-01-10 | +$11,788.00 | $880,030.00 | $877,600.00 | -$2,430.00 |
| 2026-01-11 | -$1,000.00 | $879,030.00 | $888,600.00 | +$9,570.00 |
| 2026-01-12 | +$11,788.00 | $890,818.00 | $899,100.00 | +$8,282.00 |
| 2026-01-13 | +$14,000.00 | $904,818.00 | $899,050.00 | -$5,768.00 |
| 2026-01-14 | -$7,000.00 | $897,818.00 | $895,050.00 | -$2,768.00 |
| 2026-01-15 | +$11,788.00 | $909,606.00 | $910,100.00 | +$494.00 |
| 2026-01-16 | +$13,000.00 | $922,606.00 | $917,550.00 | -$5,056.00 |
| 2026-01-17 | -$2,000.00 | $920,606.00 | $915,550.00 | -$5,056.00 |
| 2026-01-18 | +$11,788.00 | $932,394.00 | $920,600.00 | -$11,794.00 |
| 2026-01-19 | +$11,788.00 | $944,182.00 | $931,600.00 | -$12,582.00 |
| 2026-01-20 | -$1,000.00 | $943,182.00 | $942,600.00 | -$582.00 |
| 2026-01-21 | +$1,200.00 | $944,382.00 | $953,100.00 | +$8,718.00 |
| 2026-01-22 | +$1,200.00 | $945,582.00 | $963,600.00 | +$18,018.00 |
| 2026-01-23 | -$1,000.00 | $944,582.00 | $973,600.00 | +$29,018.00 |
| 2026-01-24 | +$1,380.00 | $945,962.00 | $983,600.00 | +$37,638.00 |
| 2026-01-25 | -$1,000.00 | $944,962.00 | $982,600.00 | +$37,638.00 |
| 2026-01-26 | +$1,188.00 | $946,150.00 | $983,688.00 | +$37,538.00 |
| 2026-01-27 | +$1,200.00 | $947,350.00 | $884,600.00 | -$62,750.00 |
| 2026-01-28 | +$300.00 | $947,650.00 | $984,100.00 | +$36,450.00 |
| 2026-01-29 | +$1,300.00 | $948,950.00 | $986,600.00 | +$37,650.00 |
| 2026-01-30 | -$1,000.00 | $947,950.00 | $985,600.00 | +$37,650.00 |
| 2026-01-31 | +$14,400.00 | $962,350.00 | $1,000,000.00 | +$37,650.00 |

The row-amount ledger has a daily-balance sum of $27,733,670 and ADB $894,634.52. Treating the final printed balance on each date as authoritative gives a daily-balance sum of $27,987,800 and ADB $902,832.26. The two candidate ADBs differ by $8,197.74.

Relative to the page-1 summary, the visible detail lacks $39,200 of deposits, $1,750 of withdrawals, and $200 of interest, a net $37,650. Assigning those absent amounts to January 1 yields a closing-reconciled ADB of $932,284.52. Assigning the same amounts to January 31 yields $895,849.03. Both satisfy the page-1 aggregate totals and closing balance but have different ADBs. The document provides no dates for those amounts, and its footer simultaneously claims all 41 transactions are already present.

### Every printed row balance conflict

This table compares every printed row balance with the cumulative balance implied by the opening balance and all row amounts through that row. All 41 differ. The separate local continuity check reports 36 of 41 row-to-row transitions as broken.

| Row | Date | Type | Amount | Amount-ledger balance | Printed balance | Difference |
|---:|---|---|---:|---:|---:|---:|
| 1 | 2026-01-01 | Deposit | $11,788.00 | $741,888.00 | $740,888.00 | -$1,000.00 |
| 2 | 2026-01-01 | Deposit | $11,788.00 | $753,676.00 | $751,676.00 | -$2,000.00 |
| 3 | 2026-01-02 | Withdrawal | $1,000.00 | $752,676.00 | $762,464.00 | +$9,788.00 |
| 4 | 2026-01-02 | Deposit | $14,000.00 | $766,676.00 | $765,676.00 | -$1,000.00 |
| 5 | 2026-01-03 | Withdrawal | $650.00 | $766,026.00 | $765,026.00 | -$1,000.00 |
| 6 | 2026-01-03 | Deposit | $11,788.00 | $777,814.00 | $792,600.00 | +$14,786.00 |
| 7 | 2026-01-04 | Deposit | $11,788.00 | $789,602.00 | $773,252.00 | -$16,350.00 |
| 8 | 2026-01-04 | Withdrawal | $1,000.00 | $788,602.00 | $803,600.00 | +$14,998.00 |
| 9 | 2026-01-05 | Deposit | $11,788.00 | $800,390.00 | $814,600.00 | +$14,210.00 |
| 10 | 2026-01-05 | Deposit | $12,800.00 | $813,190.00 | $823,890.00 | +$10,700.00 |
| 11 | 2026-01-06 | Withdrawal | $1,800.00 | $811,390.00 | $821,090.00 | +$9,700.00 |
| 12 | 2026-01-06 | Deposit | $11,788.00 | $823,178.00 | $824,600.00 | +$1,422.00 |
| 13 | 2026-01-07 | Deposit | $13,500.00 | $836,678.00 | $835,878.00 | -$800.00 |
| 14 | 2026-01-07 | Withdrawal | $2,800.00 | $833,878.00 | $833,570.00 | -$308.00 |
| 15 | 2026-01-08 | Deposit | $11,788.00 | $845,666.00 | $835,100.00 | -$10,566.00 |
| 16 | 2026-01-08 | Deposit | $11,788.00 | $857,454.00 | $846,100.00 | -$11,354.00 |
| 17 | 2026-01-09 | Withdrawal | $1,000.00 | $856,454.00 | $856,600.00 | +$146.00 |
| 18 | 2026-01-09 | Deposit | $11,788.00 | $868,242.00 | $867,600.00 | -$642.00 |
| 19 | 2026-01-10 | Deposit | $11,788.00 | $880,030.00 | $877,600.00 | -$2,430.00 |
| 20 | 2026-01-11 | Withdrawal | $1,000.00 | $879,030.00 | $888,600.00 | +$9,570.00 |
| 21 | 2026-01-12 | Deposit | $11,788.00 | $890,818.00 | $899,100.00 | +$8,282.00 |
| 22 | 2026-01-13 | Deposit | $14,000.00 | $904,818.00 | $899,050.00 | -$5,768.00 |
| 23 | 2026-01-14 | Withdrawal | $7,000.00 | $897,818.00 | $895,050.00 | -$2,768.00 |
| 24 | 2026-01-15 | Deposit | $11,788.00 | $909,606.00 | $910,100.00 | +$494.00 |
| 25 | 2026-01-16 | Deposit | $13,000.00 | $922,606.00 | $917,550.00 | -$5,056.00 |
| 26 | 2026-01-17 | Withdrawal | $2,000.00 | $920,606.00 | $915,550.00 | -$5,056.00 |
| 27 | 2026-01-18 | Deposit | $11,788.00 | $932,394.00 | $920,600.00 | -$11,794.00 |
| 28 | 2026-01-19 | Deposit | $11,788.00 | $944,182.00 | $931,600.00 | -$12,582.00 |
| 29 | 2026-01-20 | Withdrawal | $1,000.00 | $943,182.00 | $942,600.00 | -$582.00 |
| 30 | 2026-01-21 | Deposit | $1,200.00 | $944,382.00 | $953,100.00 | +$8,718.00 |
| 31 | 2026-01-22 | Deposit | $1,200.00 | $945,582.00 | $963,600.00 | +$18,018.00 |
| 32 | 2026-01-23 | Withdrawal | $1,000.00 | $944,582.00 | $973,600.00 | +$29,018.00 |
| 33 | 2026-01-24 | Deposit | $1,380.00 | $945,962.00 | $983,600.00 | +$37,638.00 |
| 34 | 2026-01-25 | Withdrawal | $1,000.00 | $944,962.00 | $982,600.00 | +$37,638.00 |
| 35 | 2026-01-26 | Deposit | $1,188.00 | $946,150.00 | $983,688.00 | +$37,538.00 |
| 36 | 2026-01-27 | Deposit | $1,200.00 | $947,350.00 | $884,600.00 | -$62,750.00 |
| 37 | 2026-01-28 | Withdrawal | $1,000.00 | $946,350.00 | $983,600.00 | +$37,250.00 |
| 38 | 2026-01-28 | Deposit | $1,300.00 | $947,650.00 | $984,100.00 | +$36,450.00 |
| 39 | 2026-01-29 | Deposit | $1,300.00 | $948,950.00 | $986,600.00 | +$37,650.00 |
| 40 | 2026-01-30 | Withdrawal | $1,000.00 | $947,950.00 | $985,600.00 | +$37,650.00 |
| 41 | 2026-01-31 | Deposit | $14,400.00 | $962,350.00 | $1,000,000.00 | +$37,650.00 |

The malformed printed strings `$9,17,550.00` and `$1000,000.00` were interpreted as $917,550.00 and $1,000,000.00, respectively. Fresh OCR, native text, and visual inspection all agree on those glyphs. Correcting comma placement does not resolve any arithmetic conflict.

**Classification: A.** The supplied PDF has three incompatible evidence sets: transaction amounts, printed running balances, and summary totals. No objective rule in the document selects one as correct, and different choices produce materially different ADBs.

## Parser Assumption Review

| Assumption | Farmers & Merchants | BMO |
|---|---|---|
| Period and inclusive day count | Exact printed period, 31 days | January 2026, 31 days |
| Opening and closing extraction | Matches page 1 | Matches page 1 and page 2 final |
| Continuation pages | Page-2/3 continuation captured | Page 2 has no transaction continuation |
| Debit/credit direction | Explicit section headers; all rows correct | Word coordinates place 14 amounts in withdrawal column and 27 in deposit column; parser matches all 41 |
| Ordering and same-day grouping | Source order retained; same-day net verified | Source order retained; grouped EOD still conflicts on all 31 days |
| Duplicate suppression | No visible row dropped | Both identical 1/1 deposits and all repeated $11,788 deposits retained |
| Multi-account handling | One account | One account |
| OCR loss | Disproved | Disproved |
| Hidden/clipped content | Disproved | Disproved |
| Parser omission | Disproved by exact visible-row transcription | Disproved by exact 41-row transcription |

## Code And Regression Outcome

No Farmers & Merchants or BMO transaction parser change is justified: adding inferred transactions or changing printed values would fabricate data not present in the PDFs.

The following hardening was made:

- Reconciliation coverage diagnostics no longer assume a mismatch is "likely OCR" or advise trusting a summary unconditionally. They identify incomplete or source-inconsistent detail and forbid using it for daily reconstruction.
- BMO integrity checking now proves that the secondary summary fails its own opening-to-final identity, in addition to detecting the cross-page deposit-total conflict.
- Raw-PDF integration tests assert every visible Ace transaction and every BMO amount/running-balance row, exact residuals, candidate daily sums, and end-to-end ADB withholding.

The correct production behavior is unchanged: backend, API, and dashboard expose no ADB for either source. A value can become calculable only if the supplied PDF is replaced with complete, internally consistent transaction detail or authoritative exact daily balances.
