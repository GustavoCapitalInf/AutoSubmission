# Backlog

## Deferred Source-Level Statement Issues

These three statements are intentionally not corporate-approved for
transaction-level use yet. They are the three withheld source contradictions
counted in the corpus baseline. Do not reintroduce aggregate or synthetic
"UNCAPTURED" transactions to make them reconcile.

### Farmers & Merchants Bank / Ace Auto

- File: `Bank Statements/Misc/Ace_Auto_Final_Cut.pdf`
- Current parser: `analysis/farmers_merchants.py`
- Current quality: `needs_review`
- Current corporate use: `manual_review_required`
- Current status: bank summary reconciles, but visible transaction detail does not reconcile.
- Evidence: the PDF summary says `26 Checks/Debits` totaling `$3,945.12`, but the visible source pages only itemize about 26% of debit dollars.
- Later fix target: obtain a complete source statement or add support for any missing check/image detail pages if they become available. Transaction-level approval should require all bank-stated debit activity to be itemized and reconciled without aggregate rows.

### BMO Bank of Montreal

- File: `Bank Statements/Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf`
- Current parser: `analysis/bmo.py`
- Current quality: `needs_review`
- Current corporate use: `manual_review_required`
- Current status: bank summary reconciles, but printed transaction rows and running balances are internally inconsistent.
- Evidence: the parser captures 41 printed rows, but multiple printed running balances do not equal prior balance plus/minus the printed row amount; page totals also conflict (`$294,700.00` deposits on page 1 vs `$300,000.00` on page 2).
- Later fix target: verify whether this is a bad/synthetic source PDF. Transaction-level approval should require corrected source totals and running balances, or a bank-authentic statement whose line items reconcile without aggregate rows.

### IBC Bank

- File: `Bank Statements/Others/IBC/IBC April (1).pdf`
- Current parser: `analysis/ibc.py`
- Current status: the printed recap and the complete detail/daily table describe two different ledgers, so no unique daily ledger exists.
- Evidence: the recap prints a `$10,625.31` opening and `$18,442.35` closing, while the complete detail and the raw daily table reconcile from `-$625.31` to `$8,442.35`. The recap identity is `$1,250.62` off and the two closing balances differ by `$10,000.00`.
- Current handling: both evidence paths are preserved; the public ending balance, ADB, and daily extrema are withheld rather than fabricated.
- Later fix target: a corrected source statement whose recap and detail agree.

## Current Coverage Baseline

As of August 6, 2026, measured by the two independent forensic audits over the
full 109-PDF corpus (`docs/adb-audit-results.csv`,
`docs/balance-metrics-audit-results.csv`):

- 109 statement PDFs audited: 103 digital/native, 6 local-OCR scans.
- 106 pass end to end across backend, API, dashboard, CSV, XLSX, and package surfaces.
- 3 are withheld source contradictions — the three statements above.
- All three withheld statements carry `aggregate_rows=0` — no synthetic
  "UNCAPTURED" row was reintroduced to force reconciliation — and all three are
  now `needs_review` / `manual_review_required`, which is stricter than the
  `summary_trusted` / `summary_only` handling this backlog originally recorded.

`python corpus_gate.py` re-verifies all 109 against those committed audits.
