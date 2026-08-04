# Balance Metrics Production Audit

Audit date: 2026-08-04

## Verdict

All **109** source PDFs were reopened and audited. **106** have a unique daily ledger; **3** correctly fail closed for non-unique daily extrema; **0** production mismatches remain.

The authoritative highest/lowest definition is the maximum/minimum **calendar-day ending ledger balance** over the inclusive statement period. Intraday running peaks and troughs are validation evidence, not extrema metrics.

## Totals

- PDFs/statements audited: **109**
- Banks represented: **44**
- Parser variants represented: **44**
- Digital/native PDFs: **103**
- Scanned/OCR PDFs: **6**
- Opening extraction matches: **109/109 (100.00%)**
- Ending policy matches: **109/109 (100.00%)**; one contradictory ending is unavailable
- Highest policy matches: **109/109 (100.00%)**; numeric coverage 106/109 (97.25%)
- Lowest policy matches: **109/109 (100.00%)**; numeric coverage 106/109 (97.25%)
- Statements requiring a code fix: **1** (IBC)
- Source contradictions withheld for daily extrema: **3**

## Method

`balance_forensic_audit.py` does not import the production ADB or metrics modules. It hashes and reopens every PDF, re-extracts all 103 digital documents, performs local page OCR on six image-only documents, independently groups Decimal signed postings by date, parses raw daily-ending tables where present, carries balances across inactive days, and requires the last same-day running balance to equal EOD. Expected values are then compared with serialized backend/API data, dashboard bindings, individual CSV/XLSX, and package JSON/CSV/XLSX.

## Statement Results

| Statement | Bank | Opening Expected | Opening Production | Highest Expected | Highest Production | Lowest Expected | Lowest Production | Ending Expected | Ending Production | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Amex Apr2026.pdf | American Express | $2,495.23 | $2,495.23 | $7,827.84 | $7,827.84 | $70.26 | $70.26 | $856.11 | $856.11 | PASS |
| Amex June2026.pdf | American Express | $2,089.90 | $2,089.90 | $7,457.64 | $7,457.64 | $49.36 | $49.36 | $3,534.01 | $3,534.01 | PASS |
| Amex May2026.pdf | American Express | $856.11 | $856.11 | $3,424.36 | $3,424.36 | $3.30 | $3.30 | $2,089.90 | $2,089.90 | PASS |
| ATB August 2023.pdf | ATB Financial | $34,313.58 | $34,313.58 | $23,637.09 | $23,637.09 | $12,209.41 | $12,209.41 | $14,742.49 | $14,742.49 | PASS |
| ATB Dec 2023.pdf | ATB Financial | $8,676.14 | $8,676.14 | $7,216.12 | $7,216.12 | -$427.30 | -$427.30 | $7,115.84 | $7,115.84 | PASS |
| ATB Nov 2023.pdf | ATB Financial | $10,024.34 | $10,024.34 | $8,676.14 | $8,676.14 | $490.05 | $490.05 | $8,676.14 | $8,676.14 | PASS |
| ATB October statement 2023.pdf | ATB Financial | $15,851.99 | $15,851.99 | $15,851.99 | $15,851.99 | $426.09 | $426.09 | $10,024.34 | $10,024.34 | PASS |
| ATB Sep 2023.pdf | ATB Financial | $14,742.49 | $14,742.49 | $15,951.99 | $15,951.99 | $376.67 | $376.67 | $15,851.99 | $15,851.99 | PASS |
| Bofa 2026-02-27.pdf | Bank of America | $729.80 | $729.80 | $1,100.09 | $1,100.09 | $1.12 | $1.12 | $3.16 | $3.16 | PASS |
| BofA 2026-05-29.pdf | Bank of America | $4,864.62 | $4,864.62 | $9,004.81 | $9,004.81 | -$1,769.42 | -$1,769.42 | $9,004.81 | $9,004.81 | PASS |
| BofA Statement.pdf | Bank of America | $614.59 | $614.59 | $14,877.35 | $14,877.35 | $614.59 | $614.59 | $1,345.87 | $1,345.87 | PASS |
| BofA.pdf | Bank of America | -$225.43 | -$225.43 | $412.87 | $412.87 | -$495.07 | -$495.07 | $34.81 | $34.81 | PASS |
| eStmt_2026-01-30 (3) (1).pdf | Bank of America | $5,297.45 | $5,297.45 | $9,611.77 | $9,611.77 | $1,520.80 | $1,520.80 | $6,767.39 | $6,767.39 | PASS |
| eStmt_2026-02-27 (3) (1).pdf | Bank of America | $6,767.39 | $6,767.39 | $8,449.88 | $8,449.88 | $1,464.07 | $1,464.07 | $1,498.58 | $1,498.58 | PASS |
| eStmt_2026-03-31 (3) (1).pdf | Bank of America | $1,498.58 | $1,498.58 | $12,199.00 | $12,199.00 | $1,498.58 | $1,498.58 | $3,333.46 | $3,333.46 | PASS |
| eStmt_2026-04-30 (1).pdf | Bank of America | $3,333.46 | $3,333.46 | $9,509.73 | $9,509.73 | $940.38 | $940.38 | $8,930.06 | $8,930.06 | PASS |
| capital one april 2026.pdf | Capital One | $866.38 | $866.38 | $2,886.86 | $2,886.86 | -$59.78 | -$59.78 | $1,751.11 | $1,751.11 | PASS |
| capital one february 2026.pdf | Capital One | $89.40 | $89.40 | $6,370.72 | $6,370.72 | -$351.74 | -$351.74 | $619.39 | $619.39 | PASS |
| capital one march 2026.pdf | Capital One | $619.39 | $619.39 | $866.38 | $866.38 | -$20.71 | -$20.71 | $866.38 | $866.38 | PASS |
| capital one may 2026.pdf | Capital One | $1,751.11 | $1,751.11 | $1,533.56 | $1,533.56 | -$211.02 | -$211.02 | $1,216.55 | $1,216.55 | PASS |
| Chase Apr.pdf | Chase | $4,663.35 | $4,663.35 | $7,762.41 | $7,762.41 | $83.12 | $83.12 | $2,572.03 | $2,572.03 | PASS |
| Chase Business.pdf | Chase Transaction Export | $14,658.45 | $14,658.45 | $29,410.45 | $29,410.45 | $9,676.45 | $9,676.45 | $29,410.45 | $29,410.45 | PASS |
| chase jun 30.pdf | Chase | $15,761.57 | $15,761.57 | $15,761.57 | $15,761.57 | $846.55 | $846.55 | $846.55 | $846.55 | PASS |
| Chase Jun.pdf | Chase | $2,586.33 | $2,586.33 | $5,829.53 | $5,829.53 | $202.90 | $202.90 | $3,362.48 | $3,362.48 | PASS |
| Chase Mar.pdf | Chase | $9,260.54 | $9,260.54 | $11,754.55 | $11,754.55 | $158.40 | $158.40 | $4,663.35 | $4,663.35 | PASS |
| chase may 29.pdf | Chase | $1,824.83 | $1,824.83 | $27,783.10 | $27,783.10 | -$1,929.57 | -$1,929.57 | $15,761.57 | $15,761.57 | PASS |
| Chase May.pdf | Chase | $2,011.28 | $2,011.28 | $2,748.50 | $2,748.50 | $44.57 | $44.57 | $1,557.24 | $1,557.24 | PASS |
| Chase Salomomon February 27 2026.pdf | Chase | $40,810.36 | $40,810.36 | $42,969.73 | $42,969.73 | $27,407.75 | $27,407.75 | $28,438.08 | $28,438.08 | PASS |
| Chase Salomon Dec 2025.pdf | Chase | $68,163.52 | $68,163.52 | $170,569.49 | $170,569.49 | $26,993.14 | $26,993.14 | $28,314.72 | $28,314.72 | PASS |
| Chase Salomon January.pdf | Chase | $28,314.72 | $28,314.72 | $102,633.45 | $102,633.45 | $17,272.42 | $17,272.42 | $40,810.36 | $40,810.36 | PASS |
| Chase Salomon March 2026.pdf | Chase | $28,438.08 | $28,438.08 | $40,021.99 | $40,021.99 | $24,574.69 | $24,574.69 | $28,876.02 | $28,876.02 | PASS |
| Account Statement 1.pdf | CIBC | -$16.31 | -$16.31 | $9,687.89 | $9,687.89 | -$535.86 | -$535.86 | -$114.65 | -$114.65 | PASS |
| Citizen June 2026.pdf | Citizens Bank | $620.01 | $620.01 | $11,806.24 | $11,806.24 | -$4,691.10 | -$4,691.10 | -$4,691.10 | -$4,691.10 | PASS |
| Citizens April 2026.pdf | Citizens Bank | -$2,197.06 | -$2,197.06 | $9,063.34 | $9,063.34 | -$4,969.99 | -$4,969.99 | $2,318.68 | $2,318.68 | PASS |
| Citizens March 2026.pdf | Citizens Bank | $1,677.59 | $1,677.59 | $12,835.11 | $12,835.11 | -$2,197.06 | -$2,197.06 | -$2,197.06 | -$2,197.06 | PASS |
| Citizens May 2026.pdf | Citizens Bank | $2,318.68 | $2,318.68 | $3,123.43 | $3,123.43 | -$4,299.19 | -$4,299.19 | $620.01 | $620.01 | PASS |
| 7429_Statement_October_2025_Statement.pdf | First Community Credit Union | $301.73 | $301.73 | $7,364.11 | $7,364.11 | $26.44 | $26.44 | $643.76 | $643.76 | PASS |
| Ace_Auto_Final_Cut.pdf | Farmers & Merchants Bank | -$78.68 | -$78.68 | - | - | - | - | $3,297.42 | $3,297.42 | WITHHELD_SOURCE_CONTRADICTION |
| Builder June 2026.pdf | Southside Bank | $8,816.33 | $8,816.33 | $18,803.03 | $18,803.03 | $308.03 | $308.03 | $791.26 | $791.26 | PASS |
| Checking Account Statements - 1_30_2026 - 4001245.pdf | Mission Valley Bank | $355,283.88 | $355,283.88 | $355,283.88 | $355,283.88 | $19,944.60 | $19,944.60 | $67,502.71 | $67,502.71 | PASS |
| Columbia May 26 complete.pdf | Columbia Bank | $6,291.76 | $6,291.76 | $37,211.56 | $37,211.56 | $4,831.08 | $4,831.08 | $13,904.87 | $13,904.87 | PASS |
| Consumers March - Monthly Statement.pdf | Consumers Credit Union | $47,864.30 | $47,864.30 | $36,889.47 | $36,889.47 | $10,624.10 | $10,624.10 | $26,707.42 | $26,707.42 | PASS |
| Field Trucking November 2025 .pdf | Dakota West Credit Union | $6,461.11 | $6,461.11 | $23,522.70 | $23,522.70 | $1,135.39 | $1,135.39 | $4,026.32 | $4,026.32 | PASS |
| First Farmers 2026 01-document.pdf | First Farmers Bank & Trust | $1,552.27 | $1,552.27 | $4,878.08 | $4,878.08 | $1,372.27 | $1,372.27 | $2,028.08 | $2,028.08 | PASS |
| KLR.May 31,2026 (1).pdf | Apex Bank | $14,341.03 | $14,341.03 | $10,535.39 | $10,535.39 | $152.58 | $152.58 | $1,388.55 | $1,388.55 | PASS |
| Link Bank April statement.pdf | LINKBANK | $12,926.51 | $12,926.51 | $36,696.33 | $36,696.33 | -$2,286.83 | -$2,286.83 | $4,939.50 | $4,939.50 | PASS |
| MidFlorida.pdf | MIDFLORIDA Credit Union | -$438.53 | -$438.53 | $14,287.42 | $14,287.42 | -$607.48 | -$607.48 | $288.40 | $288.40 | PASS |
| Texas Bank.pdf | Texas Bank and Trust | $9,793.64 | $9,793.64 | $9,656.98 | $9,656.98 | $1,251.25 | $1,251.25 | $6,141.48 | $6,141.48 | PASS |
| USD FEB 2026.pdf | Desjardins | $628.57 | $628.57 | $32,893.03 | $32,893.03 | $50.70 | $50.70 | $1,071.53 | $1,071.53 | PASS |
| WMB May 25.pdf | Wilson & Muir Bank & Trust | $27,343.29 | $27,343.29 | $44,595.43 | $44,595.43 | $7,307.26 | $7,307.26 | $24,915.47 | $24,915.47 | PASS |
| APRIL 2026.pdf | Navy Federal Credit Union | $0.00 | $0.00 | $565.01 | $565.01 | $0.00 | $0.00 | $64.46 | $64.46 | PASS |
| JUNE 2026.pdf | Navy Federal Credit Union | $0.48 | $0.48 | $971.48 | $971.48 | -$28.52 | -$28.52 | $255.69 | $255.69 | PASS |
| MARCH 2026.pdf | Navy Federal Credit Union | -$28.08 | -$28.08 | $1.92 | $1.92 | -$28.08 | -$28.08 | $0.00 | $0.00 | PASS |
| MAY 2026.pdf | Navy Federal Credit Union | $64.46 | $64.46 | $914.72 | $914.72 | -$57.52 | -$57.52 | $0.48 | $0.48 | PASS |
| Altana april 26.pdf | Altana Federal Credit Union | $635.57 | $635.57 | $33,808.47 | $33,808.47 | $791.41 | $791.41 | $3,927.30 | $3,927.30 | PASS |
| Altana june 26.pdf | Altana Federal Credit Union | $5,613.58 | $5,613.58 | $48,972.25 | $48,972.25 | $163.34 | $163.34 | $3,903.99 | $3,903.99 | PASS |
| Altana may 26.pdf | Altana Federal Credit Union | $3,927.30 | $3,927.30 | $43,437.81 | $43,437.81 | $426.72 | $426.72 | $5,613.58 | $5,613.58 | PASS |
| b1 april 2026.pdf | B1Bank | $203,824.07 | $203,824.07 | $200,084.07 | $200,084.07 | $79,802.46 | $79,802.46 | $79,802.46 | $79,802.46 | PASS |
| b1 feb 2026 (1).pdf | B1Bank | $250.00 | $250.00 | $507,220.00 | $507,220.00 | $250.00 | $250.00 | $389,985.94 | $389,985.94 | PASS |
| b1 march 2026.pdf | B1Bank | $389,985.94 | $389,985.94 | $389,985.94 | $389,985.94 | $203,824.07 | $203,824.07 | $203,824.07 | $203,824.07 | PASS |
| Banco Popular April 2026.pdf | Banco Popular | $470.78 | $470.78 | $5,613.94 | $5,613.94 | -$4,851.79 | -$4,851.79 | $42.30 | $42.30 | PASS |
| Banco Popular Junio 2026.pdf | Banco Popular | $1,908.41 | $1,908.41 | $5,666.34 | $5,666.34 | -$2,081.11 | -$2,081.11 | $1,821.39 | $1,821.39 | PASS |
| Banco Popular May 2026.pdf | Banco Popular | $42.30 | $42.30 | $18,103.54 | $18,103.54 | -$2,547.53 | -$2,547.53 | $1,908.41 | $1,908.41 | PASS |
| bluevine_Statement_2026-04-02T21_36_47.777670Z (1).pdf | Bluevine | $1,556.68 | $1,556.68 | $40,471.22 | $40,471.22 | $5.59 | $5.59 | $24,054.06 | $24,054.06 | PASS |
| BMO_Statement_January_2026 Final-1-2 (1).pdf | BMO | $730,100.00 | $730,100.00 | - | - | - | - | $1,000,000.00 | $1,000,000.00 | WITHHELD_SOURCE_CONTRADICTION |
| First Citizens Bank.pdf | First Citizens Bank | -$1,145.55 | -$1,145.55 | $26,177.95 | $26,177.95 | -$2,967.36 | -$2,967.36 | $14,702.87 | $14,702.87 | PASS |
| IBC April (1).pdf | IBC Bank | $10,625.31 | $10,625.31 | - | - | - | - | - | - | WITHHELD_SOURCE_CONTRADICTION |
| Navigant Credit Union 2026-06-30.pdf | Navigant Credit Union | $19,207.58 | $19,207.58 | $15,604.26 | $15,604.26 | -$989.63 | -$989.63 | -$989.63 | -$989.63 | PASS |
| Relay Operations-June-2026.pdf | Thread Bank (Relay) | $175.71 | $175.71 | $1,175.34 | $1,175.34 | $0.00 | $0.00 | $0.70 | $0.70 | PASS |
| Santander_April26.pdf | Santander Bank | $225,068.44 | $225,068.44 | $1,545,644.23 | $1,545,644.23 | $159,601.02 | $159,601.02 | $1,354,921.70 | $1,354,921.70 | PASS |
| Santander_February 2026.pdf | Santander Bank | $307,300.73 | $307,300.73 | $1,010,016.72 | $1,010,016.72 | $106,947.13 | $106,947.13 | $274,900.71 | $274,900.71 | PASS |
| Santander_March 2026.pdf | Santander Bank | $274,900.71 | $274,900.71 | $855,044.12 | $855,044.12 | $147,540.15 | $147,540.15 | $225,068.44 | $225,068.44 | PASS |
| Secu.pdf | SECU Maryland | $8,646.18 | $8,646.18 | $14,234.36 | $14,234.36 | $4,562.34 | $4,562.34 | $12,604.47 | $12,604.47 | PASS |
| PNC_Statement-2026-01-29.pdf | PNC Bank | $232.79 | $232.79 | $2,196.41 | $2,196.41 | -$109.49 | -$109.49 | $2,196.41 | $2,196.41 | PASS |
| PNC_Statement-2026-02-26.pdf | PNC Bank | $2,196.41 | $2,196.41 | $3,482.61 | $3,482.61 | -$1,231.44 | -$1,231.44 | $712.47 | $712.47 | PASS |
| PNC_Statement-2026-03-30.pdf | PNC Bank | $712.47 | $712.47 | $8,244.32 | $8,244.32 | -$2,977.36 | -$2,977.36 | $706.87 | $706.87 | PASS |
| PNC_Statement-2026-04-29.pdf | PNC Bank | $706.87 | $706.87 | $8,085.49 | $8,085.49 | -$2,431.32 | -$2,431.32 | $4,578.31 | $4,578.31 | PASS |
| PNC_Statement-2026-05-28.pdf | PNC Bank | $4,578.31 | $4,578.31 | $5,962.99 | $5,962.99 | -$3,040.51 | -$3,040.51 | $1,108.20 | $1,108.20 | PASS |
| Chequing Statement-DEC+.pdf | Royal Bank of Canada | $13,785.29 | $13,785.29 | $21,014.56 | $21,014.56 | $3,829.29 | $3,829.29 | $21,014.56 | $21,014.56 | PASS |
| Chequing Statement-FEB+.pdf | Royal Bank of Canada | $171.86 | $171.86 | $13,561.34 | $13,561.34 | -$216.54 | -$216.54 | -$216.54 | -$216.54 | PASS |
| Chequing Statement-JAN+.pdf | Royal Bank of Canada | $21,014.56 | $21,014.56 | $20,953.30 | $20,953.30 | $130.06 | $130.06 | $171.86 | $171.86 | PASS |
| Chequing Statement-MAR+.pdf | Royal Bank of Canada | -$216.54 | -$216.54 | $23,030.66 | $23,030.66 | -$6,393.90 | -$6,393.90 | -$6,393.90 | -$6,393.90 | PASS |
| 12 - Relevé Royale Décembre 2025 - Tommy Aspirot.pdf | Banque Royale du Canada | $8,580.70 | $8,580.70 | $8,580.70 | $8,580.70 | -$5,487.43 | -$5,487.43 | $6,331.79 | $6,331.79 | PASS |
| Regions-29-2026 (3).pdf | Regions Bank | $7,317.34 | $7,317.34 | $8,538.83 | $8,538.83 | -$3,304.91 | -$3,304.91 | -$595.51 | -$595.51 | PASS |
| Regions.pdf | Regions Bank | $86,739.72 | $86,739.72 | $115,788.84 | $115,788.84 | $86,739.72 | $86,739.72 | $115,788.84 | $115,788.84 | PASS |
| Regions_03-31-2026 (3) (1).pdf | Regions Bank | $4,887.64 | $4,887.64 | $10,529.45 | $10,529.45 | $529.60 | $529.60 | $1,732.67 | $1,732.67 | PASS |
| Regions_04-30-2026 (2) (1).pdf | Regions Bank | $131.00 | $131.00 | $3,454.00 | $3,454.00 | $119.00 | $119.00 | $119.00 | $119.00 | PASS |
| Scotiabank -2.pdf | Scotiabank | $4.92 | $4.92 | $2,959.59 | $2,959.59 | -$55.49 | -$55.49 | $67.99 | $67.99 | PASS |
| TD BANK NARROW APR.pdf | TD Bank | $11,982.22 | $11,982.22 | $47,198.62 | $47,198.62 | $4,103.88 | $4,103.88 | $35,121.16 | $35,121.16 | PASS |
| TD BANK NARROW FEB.pdf | TD Bank | $11,571.45 | $11,571.45 | $20,787.49 | $20,787.49 | $109.65 | $109.65 | $14,497.39 | $14,497.39 | PASS |
| TD BANK NARROW JAN.pdf | TD Bank | $3,665.70 | $3,665.70 | $62,149.46 | $62,149.46 | -$9,440.92 | -$9,440.92 | $11,571.45 | $11,571.45 | PASS |
| TD BANK NARROW MAR.pdf | TD Bank | $2.00 | $2.00 | $2.00 | $2.00 | -$8.00 | -$8.00 | -$8.00 | -$8.00 | PASS |
| Dec_31-Jan_30_2026 (6).pdf | TD Canada Trust | $102.59 | $102.59 | $7,432.15 | $7,432.15 | $42.84 | $42.84 | $42.84 | $42.84 | PASS |
| Feb_27-Mar_31_2026 (2).pdf | TD Canada Trust | $121.45 | $121.45 | $6,983.43 | $6,983.43 | $29.42 | $29.42 | $29.42 | $29.42 | PASS |
| Jan_30-Feb_27_2026 (3).pdf | TD Canada Trust | $42.84 | $42.84 | $9,027.11 | $9,027.11 | $42.84 | $42.84 | $121.45 | $121.45 | PASS |
| Mar_31-Apr_30_2026.pdf | TD Canada Trust | $29.42 | $29.42 | $1,849.47 | $1,849.47 | $26.03 | $26.03 | $26.03 | $26.03 | PASS |
| Nov_28-Dec_31_2025 (7).pdf | TD Canada Trust | $248.44 | $248.44 | $639.10 | $639.10 | -$78.03 | -$78.03 | $102.59 | $102.59 | PASS |
| TD Bank Bank Statement.pdf | TD Canada Trust | -$19.07 | -$19.07 | $1,567.62 | $1,567.62 | -$19.07 | -$19.07 | $167.73 | $167.73 | PASS |
| Truist April, 2026.pdf | Truist | $11,920.41 | $11,920.41 | $11,639.34 | $11,639.34 | $814.57 | $814.57 | $1,154.65 | $1,154.65 | PASS |
| Truist AUTO February, 2026.pdf | Truist | -$666.85 | -$666.85 | $6,093.34 | $6,093.34 | -$666.85 | -$666.85 | $6,093.34 | $6,093.34 | PASS |
| Truist AUTO March 2026.pdf | Truist | $6,093.34 | $6,093.34 | $12,932.35 | $12,932.35 | $1,109.80 | $1,109.80 | $2,550.02 | $2,550.02 | PASS |
| Truist February, 2026.pdf | Truist | $3,366.00 | $3,366.00 | $12,619.51 | $12,619.51 | $873.32 | $873.32 | $1,646.47 | $1,646.47 | PASS |
| Truist March, 2026.pdf | Truist | $1,646.47 | $1,646.47 | $11,920.41 | $11,920.41 | $906.60 | $906.60 | $11,920.41 | $11,920.41 | PASS |
| US Bank 2026-03-31 Statement.pdf | U.S. Bank | $0.00 | $0.00 | $85,508.20 | $85,508.20 | $2,028.20 | $2,028.20 | $4,664.53 | $4,664.53 | PASS |
| US Bank 2026-04-30 Statement.pdf | U.S. Bank | $4,664.53 | $4,664.53 | $152,600.42 | $152,600.42 | $400.42 | $400.42 | $4,313.57 | $4,313.57 | PASS |
| 02-28-26 WellsFargo.pdf | Wells Fargo | $9,497.70 | $9,497.70 | $9,497.70 | $9,497.70 | -$350.24 | -$350.24 | $916.39 | $916.39 | PASS |
| 03-31-26 WellsFargo.pdf | Wells Fargo | $916.39 | $916.39 | $18,903.62 | $18,903.62 | -$522.71 | -$522.71 | $6,697.73 | $6,697.73 | PASS |
| 04-30-26 WellsFargo 1.pdf | Wells Fargo | $6,697.73 | $6,697.73 | $21,305.61 | $21,305.61 | $50.83 | $50.83 | $21,305.61 | $21,305.61 | PASS |
| 113025 WellsFargo.pdf | Wells Fargo | -$218.58 | -$218.58 | $431.30 | $431.30 | -$461.03 | -$461.03 | -$461.03 | -$461.03 | PASS |

## Source Contradictions

### Ace_Auto_Final_Cut.pdf

- Bank/parser: Farmers & Merchants Bank / `farmers-&-merchants-bank-deterministic`
- Source opening/ending: -$78.68 / $3,297.42
- Root cause: Printed opening/summary/ending reconcile, but dated detail closes $2,943.45 high; the missing amount has no unique posting date, so daily extrema are not unique.
- Public highest/lowest: unavailable / unavailable
- Handling: Retained source opening/ending and fail-closed daily extrema.
- Confidence: High

### BMO_Statement_January_2026 Final-1-2 (1).pdf

- Bank/parser: BMO / `bmo-deterministic`
- Source opening/ending: $730,100.00 / $1,000,000.00
- Root cause: Primary summary closes, but line items close $37,650.00 low, 36 running transitions conflict, and a secondary summary disagrees; daily extrema are not unique.
- Public highest/lowest: unavailable / unavailable
- Handling: Retained source opening/ending and fail-closed daily extrema.
- Confidence: High

### IBC April (1).pdf

- Bank/parser: IBC Bank / `ibc-bank-deterministic`
- Source opening/ending: $10,625.31 / $18,442.35
- Root cause: The recap prints $10,625.31 opening and $18,442.35 closing, while the complete detail and daily table reconcile -$625.31 to $8,442.35. The recap identity is $1,250.62 off and the two closing balances differ by $10,000.00.
- Public highest/lowest: unavailable / unavailable
- Handling: Stopped deriving source balances from the daily table, preserved both evidence paths, and withheld the conflicting public ending/ADB/extrema values.
- Confidence: High

## Printed Extrema Cross-Checks

- All four Capital One `Minimum Balance This Cycle` values exactly match the independent daily EOD minima, including negative balances.
- Five ordinary Chase lowest-daily-ending disclosures exactly match. `chase may 29.pdf` also matches after preserving its printed negative sign.
- `chase jun 30.pdf` prints a $1,901.71 service-fee qualification value dated June 24, but its own June 30 daily table and ending balance are $846.55. Standard full-period EOD minimum is therefore $846.55.
- Lower balances printed for Dakota West savings and generic Wells Fargo disclosure examples belong to non-selected accounts or instructions and were excluded from the selected-account metrics.

## Pipeline Verification

- Opening, ending, minimum, and maximum values match in serialized JSON and individual CSV/XLSX for every reportable metric.
- Package document rows now include `beginning_balance`, `ending_balance`, `min_balance`, `max_balance`, and `daily_balance_extrema_validated`; package JSON/CSV/XLSX match all per-statement expected values.
- The dashboard continues to bind `statement.ending_balance`, `metrics.min_balance`, and `metrics.max_balance` directly. It contains no daily-ledger or extrema recalculation.
- No dashboard card, layout, label, style, or component was added or moved.

## Code Changes

1. IBC now preserves the printed recap balances and normalizes its raw dated daily table instead of silently replacing the recap with a derived ledger.
2. Serialization withholds a closing balance when neither detailed reconciliation nor the bank's own summary identity validates it; source evidence remains in reconciliation diagnostics.
3. Reconciliation now records the source opening balance alongside source/computed ending evidence.
4. Package document exports now carry the four audited balance fields and an extrema-validation state.
5. Regression tests cover the IBC contradiction, fail-closed extrema, package fields/exports, and direct frontend binding.

## Automated Verification

- Independent balance corpus: `106 PASS`, `3 WITHHELD_SOURCE_CONTRADICTION`, `0 FAIL` across all 109 PDFs.
- Independent ADB cross-check: `106 PASS`, `3 WITHHELD`, `0 FAIL` after reopening every PDF and locally OCRing the six image-only documents.
- Focused balance/ADB/parser/API/dashboard/export/package suites: `196 passed` in 32.36 seconds.
- Full repository suite: `523 passed, 1 deselected` in 44.55 seconds.
- Static dashboard binding checks confirm no frontend balance reconstruction and no UI file changes.
- Live dashboard upload: `1 passed`; IBC rendered `High review` and `N/A` for ending, ADB, lowest, and highest, with no browser errors.

## Remaining Risk

Columbia's supplied PDF still declares a missing page 5 and remains a document-integrity review item, although all financial sections and all four balance metrics reconcile uniquely. Future materially degraded scans can fail closed and require manual review.

## Final Assessment

The balance-metrics pipeline is production-ready for the audited corpus: every uniquely reconstructable value matches across all production surfaces, and every non-unique daily ledger is withheld rather than fabricated. The implementation is safe to merge after the recorded full-suite regression run.

Machine-readable evidence is in `docs/balance-metrics-audit-results.csv`.

Banks: ATB Financial, Altana Federal Credit Union, American Express, Apex Bank, B1Bank, BMO, Banco Popular, Bank of America, Banque Royale du Canada, Bluevine, CIBC, Capital One, Chase, Chase Transaction Export, Citizens Bank, Columbia Bank, Consumers Credit Union, Dakota West Credit Union, Desjardins, Farmers & Merchants Bank, First Citizens Bank, First Community Credit Union, First Farmers Bank & Trust, IBC Bank, LINKBANK, MIDFLORIDA Credit Union, Mission Valley Bank, Navigant Credit Union, Navy Federal Credit Union, PNC Bank, Regions Bank, Royal Bank of Canada, SECU Maryland, Santander Bank, Scotiabank, Southside Bank, TD Bank, TD Canada Trust, Texas Bank and Trust, Thread Bank (Relay), Truist, U.S. Bank, Wells Fargo, Wilson & Muir Bank & Trust.

Parser variants: `altana-federal-credit-union-deterministic`, `american-express-deterministic`, `apex-bank-deterministic`, `atb-financial-deterministic`, `b1bank-deterministic`, `banco-popular-deterministic`, `bank-of-america-deterministic`, `banque-royale-du-canada-deterministic`, `bluevine-deterministic`, `bmo-deterministic`, `capital-one-deterministic`, `chase-deterministic`, `chase-transaction-export-deterministic`, `cibc-deterministic`, `citizens-bank-deterministic`, `columbia-bank-deterministic`, `consumers-credit-union-deterministic`, `dakota-west-credit-union-deterministic`, `desjardins-deterministic`, `farmers-&-merchants-bank-deterministic`, `first-citizens-bank-deterministic`, `first-community-credit-union-deterministic`, `first-farmers-bank-&-trust-deterministic`, `ibc-bank-deterministic`, `linkbank-deterministic`, `midflorida-credit-union-deterministic`, `mission-valley-bank-deterministic`, `navigant-credit-union-deterministic`, `navy-federal-credit-union-deterministic`, `pnc-bank-deterministic`, `regions-bank-deterministic`, `royal-bank-of-canada-deterministic`, `santander-bank-deterministic`, `scotiabank-deterministic`, `secu-maryland-deterministic`, `southside-bank-deterministic`, `td-bank-deterministic`, `td-canada-trust-deterministic`, `texas-bank-and-trust-deterministic`, `thread-bank-(relay)-deterministic`, `truist-deterministic`, `u.s.-bank-deterministic`, `wells-fargo-deterministic`, `wilson-&-muir-bank-&-trust-deterministic`.
