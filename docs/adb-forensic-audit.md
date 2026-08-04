# Average Daily Balance Forensic Audit

## Result

- Statements audited: **109**
- Valid independent ledgers passed end to end: **106**
- Correctly withheld invalid source ledgers: **3**
- Incorrect production outputs after fixes: **0**
- Automatic calculation coverage: **97.25%**
- Pass rate among mathematically valid statements: **100.00%**
- Statements with independently parsed raw daily-ledger tables: **27**
- Bank-printed averages found: **59**; non-exact comparisons explained: **50**
- Inclusive period lengths covered: **27 days: 1, 28 days: 10, 29 days: 8, 30 days: 38, 31 days: 32, 32 days: 12, 33 days: 5, 34 days: 3**
- Corpus periods containing February 29: **0** (the synthetic February 2028 regression verifies leap-day inclusion)

`WITHHELD` is a successful fail-closed result, not a fabricated ADB. These 3 source ledgers do not contain enough internally consistent evidence to calculate one reliably.

## Method

The expected-value routine in `adb_forensic_audit.py` never imports or calls `analysis.adb`. It uses Decimal cents, inclusive calendar dates, signed raw postings grouped by date, one EOD value per day, carry-forward on no-activity days, and `ROUND_HALF_UP` only after division. For nine bank families with dated book/ledger summaries, those raw balance snapshots are parsed independently and used as direct EOD evidence. Each expected value is compared separately with the backend metric, serialized API property, and single-statement dashboard package value.

## Statement Results

| Statement | Bank | Printed ADB | Independent ADB | Backend ADB | API ADB | Dashboard ADB | Difference | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Amex Apr2026.pdf | American Express | - | $1,507.49 | $1,507.49 | $1,507.49 | $1,507.49 | $0.00 | PASS |
| Amex June2026.pdf | American Express | - | $1,636.90 | $1,636.90 | $1,636.90 | $1,636.90 | $0.00 | PASS |
| Amex May2026.pdf | American Express | - | $491.93 | $491.93 | $491.93 | $491.93 | $0.00 | PASS |
| ATB August 2023.pdf | ATB Financial | - | $17,536.57 | $17,536.57 | $17,536.57 | $17,536.57 | $0.00 | PASS |
| ATB Dec 2023.pdf | ATB Financial | - | $2,463.96 | $2,463.96 | $2,463.96 | $2,463.96 | $0.00 | PASS |
| ATB Nov 2023.pdf | ATB Financial | - | $3,861.78 | $3,861.78 | $3,861.78 | $3,861.78 | $0.00 | PASS |
| ATB October statement 2023.pdf | ATB Financial | - | $5,811.81 | $5,811.81 | $5,811.81 | $5,811.81 | $0.00 | PASS |
| ATB Sep 2023.pdf | ATB Financial | - | $6,598.08 | $6,598.08 | $6,598.08 | $6,598.08 | $0.00 | PASS |
| Bofa 2026-02-27.pdf | Bank of America | $234.35 | $234.35 | $234.35 | $234.35 | $234.35 | $0.00 | PASS |
| BofA 2026-05-29.pdf | Bank of America | $2,718.80 | $2,498.72 | $2,498.72 | $2,498.72 | $2,498.72 | $0.00 | PASS |
| BofA Statement.pdf | Bank of America | $4,180.50 | $4,180.51 | $4,180.51 | $4,180.51 | $4,180.51 | $0.00 | PASS |
| BofA.pdf | Bank of America | $96.99 | $28.63 | $28.63 | $28.63 | $28.63 | $0.00 | PASS |
| eStmt_2026-01-30 (3) (1).pdf | Bank of America | $4,321.03 | $4,321.04 | $4,321.04 | $4,321.04 | $4,321.04 | $0.00 | PASS |
| eStmt_2026-02-27 (3) (1).pdf | Bank of America | $4,055.74 | $4,055.75 | $4,055.75 | $4,055.75 | $4,055.75 | $0.00 | PASS |
| eStmt_2026-03-31 (3) (1).pdf | Bank of America | $4,078.38 | $4,078.39 | $4,078.39 | $4,078.39 | $4,078.39 | $0.00 | PASS |
| eStmt_2026-04-30 (1).pdf | Bank of America | $4,265.42 | $4,265.43 | $4,265.43 | $4,265.43 | $4,265.43 | $0.00 | PASS |
| capital one april 2026.pdf | Capital One | $684.19 | $700.69 | $700.69 | $700.69 | $700.69 | $0.00 | PASS |
| capital one february 2026.pdf | Capital One | $974.40 | $986.45 | $986.45 | $986.45 | $986.45 | $0.00 | PASS |
| capital one march 2026.pdf | Capital One | $194.39 | $193.91 | $193.91 | $193.91 | $193.91 | $0.00 | PASS |
| capital one may 2026.pdf | Capital One | $368.67 | $311.37 | $311.37 | $311.37 | $311.37 | $0.00 | PASS |
| Chase Apr.pdf | Chase | - | $2,763.39 | $2,763.39 | $2,763.39 | $2,763.39 | $0.00 | PASS |
| Chase Business.pdf | Chase Transaction Export | - | $15,414.81 | $15,414.81 | $15,414.81 | $15,414.81 | $0.00 | PASS |
| chase jun 30.pdf | Chase | - | $9,286.41 | $9,286.41 | $9,286.41 | $9,286.41 | $0.00 | PASS |
| Chase Jun.pdf | Chase | - | $1,820.13 | $1,820.13 | $1,820.13 | $1,820.13 | $0.00 | PASS |
| Chase Mar.pdf | Chase | - | $3,074.34 | $3,074.34 | $3,074.34 | $3,074.34 | $0.00 | PASS |
| chase may 29.pdf | Chase | - | $7,242.09 | $7,242.09 | $7,242.09 | $7,242.09 | $0.00 | PASS |
| Chase May.pdf | Chase | - | $697.03 | $697.03 | $697.03 | $697.03 | $0.00 | PASS |
| Chase Salomomon February 27 2026.pdf | Chase | - | $35,269.16 | $35,269.16 | $35,269.16 | $35,269.16 | $0.00 | PASS |
| Chase Salomon Dec 2025.pdf | Chase | - | $63,478.10 | $63,478.10 | $63,478.10 | $63,478.10 | $0.00 | PASS |
| Chase Salomon January.pdf | Chase | - | $42,323.94 | $42,323.94 | $42,323.94 | $42,323.94 | $0.00 | PASS |
| Chase Salomon March 2026.pdf | Chase | - | $31,603.35 | $31,603.35 | $31,603.35 | $31,603.35 | $0.00 | PASS |
| Account Statement 1.pdf | CIBC | - | $2,013.81 | $2,013.81 | $2,013.81 | $2,013.81 | $0.00 | PASS |
| Citizen June 2026.pdf | Citizens Bank | $2,182.00 | $2,182.35 | $2,182.35 | $2,182.35 | $2,182.35 | $0.00 | PASS |
| Citizens April 2026.pdf | Citizens Bank | $822.00 | $821.63 | $821.63 | $821.63 | $821.63 | $0.00 | PASS |
| Citizens March 2026.pdf | Citizens Bank | $3,206.00 | $3,206.34 | $3,206.34 | $3,206.34 | $3,206.34 | $0.00 | PASS |
| Citizens May 2026.pdf | Citizens Bank | $17.00 | $15.09 | $15.09 | $15.09 | $15.09 | $0.00 | PASS |
| 7429_Statement_October_2025_Statement.pdf | First Community Credit Union | $1,233.51 | $1,714.41 | $1,714.41 | $1,714.41 | $1,714.41 | $0.00 | PASS |
| Ace_Auto_Final_Cut.pdf | Farmers & Merchants Bank | $1,569.00 | $3,258.22 | - | - | - | - | WITHHELD |
| Builder June 2026.pdf | Southside Bank | - | $6,303.69 | $6,303.69 | $6,303.69 | $6,303.69 | $0.00 | PASS |
| Checking Account Statements - 1_30_2026 - 4001245.pdf | Mission Valley Bank | - | $121,318.02 | $121,318.02 | $121,318.02 | $121,318.02 | $0.00 | PASS |
| Columbia May 26 complete.pdf | Columbia Bank | $13,275.65 | $13,275.65 | $13,275.65 | $13,275.65 | $13,275.65 | $0.00 | PASS |
| Consumers March - Monthly Statement.pdf | Consumers Credit Union | - | $26,804.59 | $26,804.59 | $26,804.59 | $26,804.59 | $0.00 | PASS |
| Field Trucking November 2025 .pdf | Dakota West Credit Union | - | $6,725.12 | $6,725.12 | $6,725.12 | $6,725.12 | $0.00 | PASS |
| First Farmers 2026 01-document.pdf | First Farmers Bank & Trust | $2,979.63 | $2,979.64 | $2,979.64 | $2,979.64 | $2,979.64 | $0.00 | PASS |
| KLR.May 31,2026 (1).pdf | Apex Bank | $2,786.20 | $2,785.53 | $2,785.53 | $2,785.53 | $2,785.53 | $0.00 | PASS |
| Link Bank April statement.pdf | LINKBANK | $14,655.66 | $14,655.66 | $14,655.66 | $14,655.66 | $14,655.66 | $0.00 | PASS |
| MidFlorida.pdf | MIDFLORIDA Credit Union | - | $2,462.42 | $2,462.42 | $2,462.42 | $2,462.42 | $0.00 | PASS |
| Texas Bank.pdf | Texas Bank and Trust | $4,879.33 | $4,879.00 | $4,879.00 | $4,879.00 | $4,879.00 | $0.00 | PASS |
| USD FEB 2026.pdf | Desjardins | - | $3,595.43 | $3,595.43 | $3,595.43 | $3,595.43 | $0.00 | PASS |
| WMB May 25.pdf | Wilson & Muir Bank & Trust | $22,677.84 | $22,677.85 | $22,677.85 | $22,677.85 | $22,677.85 | $0.00 | PASS |
| APRIL 2026.pdf | Navy Federal Credit Union | $87.57 | $87.58 | $87.58 | $87.58 | $87.58 | $0.00 | PASS |
| JUNE 2026.pdf | Navy Federal Credit Union | $138.76 | $138.77 | $138.77 | $138.77 | $138.77 | $0.00 | PASS |
| MARCH 2026.pdf | Navy Federal Credit Union | -$12.90 | -$12.91 | -$12.91 | -$12.91 | -$12.91 | $0.00 | PASS |
| MAY 2026.pdf | Navy Federal Credit Union | $72.99 | $73.00 | $73.00 | $73.00 | $73.00 | $0.00 | PASS |
| Altana april 26.pdf | Altana Federal Credit Union | - | $7,188.19 | $7,188.19 | $7,188.19 | $7,188.19 | $0.00 | PASS |
| Altana june 26.pdf | Altana Federal Credit Union | - | $10,508.91 | $10,508.91 | $10,508.91 | $10,508.91 | $0.00 | PASS |
| Altana may 26.pdf | Altana Federal Credit Union | - | $9,244.82 | $9,244.82 | $9,244.82 | $9,244.82 | $0.00 | PASS |
| b1 april 2026.pdf | B1Bank | $165,555.58 | $165,555.58 | $165,555.58 | $165,555.58 | $165,555.58 | $0.00 | PASS |
| b1 feb 2026 (1).pdf | B1Bank | $346,074.54 | $346,074.54 | $346,074.54 | $346,074.54 | $346,074.54 | $0.00 | PASS |
| b1 march 2026.pdf | B1Bank | $300,817.84 | $300,817.84 | $300,817.84 | $300,817.84 | $300,817.84 | $0.00 | PASS |
| Banco Popular April 2026.pdf | Banco Popular | $680.07 | $679.27 | $679.27 | $679.27 | $679.27 | $0.00 | PASS |
| Banco Popular Junio 2026.pdf | Banco Popular | $1,508.41 | $1,507.80 | $1,507.80 | $1,507.80 | $1,507.80 | $0.00 | PASS |
| Banco Popular May 2026.pdf | Banco Popular | $2,333.48 | $2,342.51 | $2,342.51 | $2,342.51 | $2,342.51 | $0.00 | PASS |
| bluevine_Statement_2026-04-02T21_36_47.777670Z (1).pdf | Bluevine | - | $11,652.27 | $11,652.27 | $11,652.27 | $11,652.27 | $0.00 | PASS |
| BMO_Statement_January_2026 Final-1-2 (1).pdf | BMO | - | $894,634.52 | - | - | - | - | WITHHELD |
| First Citizens Bank.pdf | First Citizens Bank | $8,117.14 | $8,116.50 | $8,116.50 | $8,116.50 | $8,116.50 | $0.00 | PASS |
| IBC April (1).pdf | IBC Bank | $14,388.96 | $4,534.03 | - | - | - | - | WITHHELD |
| Navigant Credit Union 2026-06-30.pdf | Navigant Credit Union | - | $2,770.02 | $2,770.02 | $2,770.02 | $2,770.02 | $0.00 | PASS |
| Relay Operations-June-2026.pdf | Thread Bank (Relay) | - | $122.62 | $122.62 | $122.62 | $122.62 | $0.00 | PASS |
| Santander_April26.pdf | Santander Bank | $770,434.95 | $770,434.95 | $770,434.95 | $770,434.95 | $770,434.95 | $0.00 | PASS |
| Santander_February 2026.pdf | Santander Bank | $411,379.06 | $411,379.06 | $411,379.06 | $411,379.06 | $411,379.06 | $0.00 | PASS |
| Santander_March 2026.pdf | Santander Bank | $526,096.09 | $526,096.09 | $526,096.09 | $526,096.09 | $526,096.09 | $0.00 | PASS |
| Secu.pdf | SECU Maryland | - | $9,275.35 | $9,275.35 | $9,275.35 | $9,275.35 | $0.00 | PASS |
| PNC_Statement-2026-01-29.pdf | PNC Bank | $541.22 | $538.46 | $538.46 | $538.46 | $538.46 | $0.00 | PASS |
| PNC_Statement-2026-02-26.pdf | PNC Bank | $728.48 | $746.57 | $746.57 | $746.57 | $746.57 | $0.00 | PASS |
| PNC_Statement-2026-03-30.pdf | PNC Bank | $884.26 | $864.63 | $864.63 | $864.63 | $864.63 | $0.00 | PASS |
| PNC_Statement-2026-04-29.pdf | PNC Bank | $1,243.82 | $1,243.83 | $1,243.83 | $1,243.83 | $1,243.83 | $0.00 | PASS |
| PNC_Statement-2026-05-28.pdf | PNC Bank | $353.47 | $280.22 | $280.22 | $280.22 | $280.22 | $0.00 | PASS |
| Chequing Statement-DEC+.pdf | Royal Bank of Canada | - | $9,977.51 | $9,977.51 | $9,977.51 | $9,977.51 | $0.00 | PASS |
| Chequing Statement-FEB+.pdf | Royal Bank of Canada | - | $6,629.84 | $6,629.84 | $6,629.84 | $6,629.84 | $0.00 | PASS |
| Chequing Statement-JAN+.pdf | Royal Bank of Canada | - | $3,896.40 | $3,896.40 | $3,896.40 | $3,896.40 | $0.00 | PASS |
| Chequing Statement-MAR+.pdf | Royal Bank of Canada | - | $3,993.35 | $3,993.35 | $3,993.35 | $3,993.35 | $0.00 | PASS |
| 12 - Relevé Royale Décembre 2025 - Tommy Aspirot.pdf | Banque Royale du Canada | - | $669.07 | $669.07 | $669.07 | $669.07 | $0.00 | PASS |
| Regions-29-2026 (3).pdf | Regions Bank | $1,545.00 | $1,545.75 | $1,545.75 | $1,545.75 | $1,545.75 | $0.00 | PASS |
| Regions.pdf | Regions Bank | - | $100,285.84 | $100,285.84 | $100,285.84 | $100,285.84 | $0.00 | PASS |
| Regions_03-31-2026 (3) (1).pdf | Regions Bank | $4,136.00 | $4,136.28 | $4,136.28 | $4,136.28 | $4,136.28 | $0.00 | PASS |
| Regions_04-30-2026 (2) (1).pdf | Regions Bank | $297.00 | $296.75 | $296.75 | $296.75 | $296.75 | $0.00 | PASS |
| Scotiabank -2.pdf | Scotiabank | - | $697.00 | $697.00 | $697.00 | $697.00 | $0.00 | PASS |
| TD BANK NARROW APR.pdf | TD Bank | $16,089.93 | $17,582.93 | $17,582.93 | $17,582.93 | $17,582.93 | $0.00 | PASS |
| TD BANK NARROW FEB.pdf | TD Bank | $8,128.59 | $8,127.88 | $8,127.88 | $8,127.88 | $8,127.88 | $0.00 | PASS |
| TD BANK NARROW JAN.pdf | TD Bank | $22,239.36 | $22,238.72 | $22,238.72 | $22,238.72 | $22,238.72 | $0.00 | PASS |
| TD BANK NARROW MAR.pdf | TD Bank | $2.00 | $1.68 | $1.68 | $1.68 | $1.68 | $0.00 | PASS |
| Dec_31-Jan_30_2026 (6).pdf | TD Canada Trust | $1,373.33 | $1,375.26 | $1,375.26 | $1,375.26 | $1,375.26 | $0.00 | PASS |
| Feb_27-Mar_31_2026 (2).pdf | TD Canada Trust | $2,920.00 | $2,750.39 | $2,750.39 | $2,750.39 | $2,750.39 | $0.00 | PASS |
| Jan_30-Feb_27_2026 (3).pdf | TD Canada Trust | $2,476.51 | $2,389.88 | $2,389.88 | $2,389.88 | $2,389.88 | $0.00 | PASS |
| Mar_31-Apr_30_2026.pdf | TD Canada Trust | $483.78 | $469.13 | $469.13 | $469.13 | $469.13 | $0.00 | PASS |
| Nov_28-Dec_31_2025 (7).pdf | TD Canada Trust | $200.14 | $202.11 | $202.11 | $202.11 | $202.11 | $0.00 | PASS |
| TD Bank Bank Statement.pdf | TD Canada Trust | $294.88 | $270.65 | $270.65 | $270.65 | $270.65 | $0.00 | PASS |
| Truist April, 2026.pdf | Truist | - | $4,419.06 | $4,419.06 | $4,419.06 | $4,419.06 | $0.00 | PASS |
| Truist AUTO February, 2026.pdf | Truist | - | $2,133.05 | $2,133.05 | $2,133.05 | $2,133.05 | $0.00 | PASS |
| Truist AUTO March 2026.pdf | Truist | - | $5,582.29 | $5,582.29 | $5,582.29 | $5,582.29 | $0.00 | PASS |
| Truist February, 2026.pdf | Truist | - | $3,597.15 | $3,597.15 | $3,597.15 | $3,597.15 | $0.00 | PASS |
| Truist March, 2026.pdf | Truist | - | $4,013.81 | $4,013.81 | $4,013.81 | $4,013.81 | $0.00 | PASS |
| US Bank 2026-03-31 Statement.pdf | U.S. Bank | - | $20,097.47 | $20,097.47 | $20,097.47 | $20,097.47 | $0.00 | PASS |
| US Bank 2026-04-30 Statement.pdf | U.S. Bank | - | $18,722.33 | $18,722.33 | $18,722.33 | $18,722.33 | $0.00 | PASS |
| 02-28-26 WellsFargo.pdf | Wells Fargo | $2,181.00 | $2,180.57 | $2,180.57 | $2,180.57 | $2,180.57 | $0.00 | PASS |
| 03-31-26 WellsFargo.pdf | Wells Fargo | - | $6,476.30 | $6,476.30 | $6,476.30 | $6,476.30 | $0.00 | PASS |
| 04-30-26 WellsFargo 1.pdf | Wells Fargo | - | $3,437.97 | $3,437.97 | $3,437.97 | $3,437.97 | $0.00 | PASS |
| 113025 WellsFargo.pdf | Wells Fargo | -$118.00 | -$118.66 | -$118.66 | -$118.66 | -$118.66 | $0.00 | PASS |

## Withheld Statements

### Ace_Auto_Final_Cut.pdf

- Bank: Farmers & Merchants Bank
- Expected / actual ADB difference: not mathematically determinable / withheld / N/A
- Incomplete-ledger candidate (not reportable): $3,258.22
- Closing drift: $2,943.45
- Backend / API / dashboard: withheld
- Root cause: opening plus raw line items misses closing by +2943.45; independent final daily balance misses closing by +2943.45
- Affected parser: `farmers-&-merchants-bank-deterministic`
- Affected code: `analysis/farmers_merchants.py`; fail-closed gate in `analysis/adb.py`
- Recommended handling: retain fail-closed behavior and require a corrected statement or manual source-document review.
- Confidence: high

### BMO_Statement_January_2026 Final-1-2 (1).pdf

- Bank: BMO
- Expected / actual ADB difference: not mathematically determinable / withheld / N/A
- Incomplete-ledger candidate (not reportable): $894,634.52
- Closing drift: -$37,650.00
- Backend / API / dashboard: withheld
- Root cause: opening plus raw line items misses closing by -37650.00; independent final daily balance misses closing by -37650.00; printed running-balance evidence conflicts with reconstructed EOD
- Affected parser: `bmo-deterministic`
- Affected code: `analysis/bmo.py`; fail-closed gate in `analysis/adb.py`
- Recommended handling: retain fail-closed behavior and require a corrected statement or manual source-document review.
- Confidence: high

### IBC April (1).pdf

- Bank: IBC Bank
- Expected / actual ADB difference: not mathematically determinable / withheld / N/A
- Incomplete-ledger candidate (not reportable): $4,534.03
- Closing drift: -$10,000.00
- Backend / API / dashboard: withheld
- Root cause: opening plus raw line items misses closing by +1250.62; independent final daily balance misses closing by -10000.00
- Affected parser: `ibc-bank-deterministic`
- Affected code: `analysis/ibc.py`; fail-closed gate in `analysis/adb.py`
- Recommended handling: retain fail-closed behavior and require a corrected statement or manual source-document review.
- Confidence: high

## Printed-Average Differences

- **BofA 2026-05-29.pdf** (Bank of America): printed $2,718.80, independent $2,498.72, difference -$220.08 (8.0947%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **BofA Statement.pdf** (Bank of America): printed $4,180.50, independent $4,180.51, difference $0.01 (0.0002%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **BofA.pdf** (Bank of America): printed $96.99, independent $28.63, difference -$68.36 (70.4815%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **eStmt_2026-01-30 (3) (1).pdf** (Bank of America): printed $4,321.03, independent $4,321.04, difference $0.01 (0.0002%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **eStmt_2026-02-27 (3) (1).pdf** (Bank of America): printed $4,055.74, independent $4,055.75, difference $0.01 (0.0002%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **eStmt_2026-03-31 (3) (1).pdf** (Bank of America): printed $4,078.38, independent $4,078.39, difference $0.01 (0.0002%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **eStmt_2026-04-30 (1).pdf** (Bank of America): printed $4,265.42, independent $4,265.43, difference $0.01 (0.0002%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **capital one april 2026.pdf** (Capital One): printed $684.19, independent $700.69, difference $16.50 (2.4116%). Different disclosed basis: the bank prints collected balance, while ADB uses posted ledger EOD balances.
- **capital one february 2026.pdf** (Capital One): printed $974.40, independent $986.45, difference $12.05 (1.2367%). Different disclosed basis: the bank prints collected balance, while ADB uses posted ledger EOD balances.
- **capital one march 2026.pdf** (Capital One): printed $194.39, independent $193.91, difference -$0.48 (0.2469%). Different disclosed basis: the bank prints collected balance, while ADB uses posted ledger EOD balances.
- **capital one may 2026.pdf** (Capital One): printed $368.67, independent $311.37, difference -$57.30 (15.5424%). Different disclosed basis: the bank prints collected balance, while ADB uses posted ledger EOD balances.
- **Citizen June 2026.pdf** (Citizens Bank): printed $2,182.00, independent $2,182.35, difference $0.35 (0.0160%). The bank displays a whole-dollar qualifying/summary value; the independent ledger retains cents.
- **Citizens April 2026.pdf** (Citizens Bank): printed $822.00, independent $821.63, difference -$0.37 (0.0450%). The bank displays a whole-dollar qualifying/summary value; the independent ledger retains cents.
- **Citizens March 2026.pdf** (Citizens Bank): printed $3,206.00, independent $3,206.34, difference $0.34 (0.0106%). The bank displays a whole-dollar qualifying/summary value; the independent ledger retains cents.
- **Citizens May 2026.pdf** (Citizens Bank): printed $17.00, independent $15.09, difference -$1.91 (11.2353%). The bank displays a whole-dollar qualifying/summary value; the independent ledger retains cents.
- **7429_Statement_October_2025_Statement.pdf** (First Community Credit Union): printed $1,233.51, independent $1,714.41, difference $480.90 (38.9863%). The account-analysis average uses a collected/availability basis not reproduced by posted ledger EOD balances.
- **Ace_Auto_Final_Cut.pdf** (Farmers & Merchants Bank): printed $1,569.00, independent $3,258.22, difference $1,689.22 (107.6622%). opening plus raw line items misses closing by +2943.45; independent final daily balance misses closing by +2943.45
- **First Farmers 2026 01-document.pdf** (First Farmers Bank & Trust): printed $2,979.63, independent $2,979.64, difference $0.01 (0.0003%). One-cent presentation difference caused by the bank's rounding/truncation convention.
- **KLR.May 31,2026 (1).pdf** (Apex Bank): printed $2,786.20, independent $2,785.53, difference -$0.67 (0.0240%). The raw ledger closes, but the bank-printed average uses an undisclosed alternate balance basis.
- **Texas Bank.pdf** (Texas Bank and Trust): printed $4,879.33, independent $4,879.00, difference -$0.33 (0.0068%). The raw ledger closes, but the bank-printed average uses an undisclosed alternate balance basis.
- **WMB May 25.pdf** (Wilson & Muir Bank & Trust): printed $22,677.84, independent $22,677.85, difference $0.01 (0.0000%). One-cent presentation difference caused by the bank's rounding/truncation convention.
- **APRIL 2026.pdf** (Navy Federal Credit Union): printed $87.57, independent $87.58, difference $0.01 (0.0114%). One-cent presentation difference caused by the bank's rounding/truncation convention.
- **JUNE 2026.pdf** (Navy Federal Credit Union): printed $138.76, independent $138.77, difference $0.01 (0.0072%). One-cent presentation difference caused by the bank's rounding/truncation convention.
- **MARCH 2026.pdf** (Navy Federal Credit Union): printed -$12.90, independent -$12.91, difference -$0.01 (0.0775%). One-cent presentation difference caused by the bank's rounding/truncation convention.
- **MAY 2026.pdf** (Navy Federal Credit Union): printed $72.99, independent $73.00, difference $0.01 (0.0137%). One-cent presentation difference caused by the bank's rounding/truncation convention.
- **Banco Popular April 2026.pdf** (Banco Popular): printed $680.07, independent $679.27, difference -$0.80 (0.1176%). The bank's cycle average differs from the arithmetic mean of its own printed Book Balance history.
- **Banco Popular Junio 2026.pdf** (Banco Popular): printed $1,508.41, independent $1,507.80, difference -$0.61 (0.0404%). The bank's cycle average differs from the arithmetic mean of its own printed Book Balance history.
- **Banco Popular May 2026.pdf** (Banco Popular): printed $2,333.48, independent $2,342.51, difference $9.03 (0.3870%). The bank's cycle average differs from the arithmetic mean of its own printed Book Balance history.
- **First Citizens Bank.pdf** (First Citizens Bank): printed $8,117.14, independent $8,116.50, difference -$0.64 (0.0079%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **IBC April (1).pdf** (IBC Bank): printed $14,388.96, independent $4,534.03, difference -$9,854.93 (68.4895%). opening plus raw line items misses closing by +1250.62; independent final daily balance misses closing by -10000.00
- **PNC_Statement-2026-01-29.pdf** (PNC Bank): printed $541.22, independent $538.46, difference -$2.76 (0.5100%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **PNC_Statement-2026-02-26.pdf** (PNC Bank): printed $728.48, independent $746.57, difference $18.09 (2.4833%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **PNC_Statement-2026-03-30.pdf** (PNC Bank): printed $884.26, independent $864.63, difference -$19.63 (2.2199%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **PNC_Statement-2026-04-29.pdf** (PNC Bank): printed $1,243.82, independent $1,243.83, difference $0.01 (0.0008%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **PNC_Statement-2026-05-28.pdf** (PNC Bank): printed $353.47, independent $280.22, difference -$73.25 (20.7231%). The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis.
- **Regions-29-2026 (3).pdf** (Regions Bank): printed $1,545.00, independent $1,545.75, difference $0.75 (0.0485%). The bank displays a whole-dollar qualifying/summary value; the independent ledger retains cents.
- **Regions_03-31-2026 (3) (1).pdf** (Regions Bank): printed $4,136.00, independent $4,136.28, difference $0.28 (0.0068%). The bank displays a whole-dollar qualifying/summary value; the independent ledger retains cents.
- **Regions_04-30-2026 (2) (1).pdf** (Regions Bank): printed $297.00, independent $296.75, difference -$0.25 (0.0842%). The bank displays a whole-dollar qualifying/summary value; the independent ledger retains cents.
- **TD BANK NARROW APR.pdf** (TD Bank): printed $16,089.93, independent $17,582.93, difference $1,493.00 (9.2791%). Different disclosed basis: the bank prints collected balance, while ADB uses posted ledger EOD balances.
- **TD BANK NARROW FEB.pdf** (TD Bank): printed $8,128.59, independent $8,127.88, difference -$0.71 (0.0087%). Different disclosed basis: the bank prints collected balance, while ADB uses posted ledger EOD balances.
- **TD BANK NARROW JAN.pdf** (TD Bank): printed $22,239.36, independent $22,238.72, difference -$0.64 (0.0029%). Different disclosed basis: the bank prints collected balance, while ADB uses posted ledger EOD balances.
- **TD BANK NARROW MAR.pdf** (TD Bank): printed $2.00, independent $1.68, difference -$0.32 (16.0000%). Different disclosed basis: the bank prints collected balance, while ADB uses posted ledger EOD balances.
- **Dec_31-Jan_30_2026 (6).pdf** (TD Canada Trust): printed $1,373.33, independent $1,375.26, difference $1.93 (0.1405%). Different disclosed basis: the bank prints average credit balance rather than signed ledger EOD balance.
- **Feb_27-Mar_31_2026 (2).pdf** (TD Canada Trust): printed $2,920.00, independent $2,750.39, difference -$169.61 (5.8086%). Different disclosed basis: the bank prints average credit balance rather than signed ledger EOD balance.
- **Jan_30-Feb_27_2026 (3).pdf** (TD Canada Trust): printed $2,476.51, independent $2,389.88, difference -$86.63 (3.4981%). Different disclosed basis: the bank prints average credit balance rather than signed ledger EOD balance.
- **Mar_31-Apr_30_2026.pdf** (TD Canada Trust): printed $483.78, independent $469.13, difference -$14.65 (3.0282%). Different disclosed basis: the bank prints average credit balance rather than signed ledger EOD balance.
- **Nov_28-Dec_31_2025 (7).pdf** (TD Canada Trust): printed $200.14, independent $202.11, difference $1.97 (0.9843%). Different disclosed basis: the bank prints average credit balance rather than signed ledger EOD balance.
- **TD Bank Bank Statement.pdf** (TD Canada Trust): printed $294.88, independent $270.65, difference -$24.23 (8.2169%). Different disclosed basis: the bank prints average credit balance rather than signed ledger EOD balance.
- **02-28-26 WellsFargo.pdf** (Wells Fargo): printed $2,181.00, independent $2,180.57, difference -$0.43 (0.0197%). The bank displays a whole-dollar qualifying/summary value; the independent ledger retains cents.
- **113025 WellsFargo.pdf** (Wells Fargo): printed -$118.00, independent -$118.66, difference -$0.66 (0.5593%). The bank displays a whole-dollar qualifying/summary value; the independent ledger retains cents.

## Defects Corrected

1. Out-of-period rows were silently clamped to statement boundaries. Capital One cycle charges and Consumers included boundary activity are now normalized by their parsers; the central calculator rejects any remaining outside row.
2. Transaction running balances previously replaced reconstructed balances. They now validate the ledger only and cannot alter ADB.
3. Banco Popular's dated Book Balance history was ignored. It is now normalized as direct daily-ledger evidence, correcting all three Banco statements.
4. Binary floats and Python's tie-to-even rounding caused a half-cent error. ADB now uses Decimal and financial half-up rounding.
5. Missing printed-average extraction for LINKBANK, First Citizens, IBC, and integer Regions formats prevented complete comparison; those selected-account fields are now captured.
6. The dashboard and package API consumed a legacy `average_balance` fallback. They now bind directly to validated `average_daily_balance`; bank-stated averages remain audit evidence only.
7. Same-day validation accepted any printed running balance from the day. It now requires the final printed balance, which is the only end-of-day evidence.
8. Missing or inverted statement dates could produce a diagnostic candidate over an inferred transaction span. Such periods now fail closed and never become a reportable ADB.
9. Rejected candidate averages and daily ledgers leaked through nested JSON and spreadsheet exports. Public API, package, CSV, and XLSX contracts now expose only the authoritative validated ADB and retain non-numeric failure diagnostics.
10. BMO parsing hardcoded January 2026. It now derives month length, leap-year dates, currency, and transaction direction from the printed statement and running-balance continuity.

## Dashboard Contract

No dashboard markup, card, label, layout, typography, or component was added. The existing Average Daily Balance field reads `metrics.average_daily_balance`; package rows read `average_daily_balance`; and invalid ledgers display no substituted bank-stated, stale, zero, or candidate value. JSON, CSV, and XLSX follow the same fail-closed contract.

Machine-readable per-statement evidence, including periods, opening/closing balances, day counts, leap-day flags, same-day activity, no-activity days, boundary counts, running-balance checks, differences, and confidence, is in `docs/adb-audit-results.csv`.
