# Backlog

## Deferred Source-Level Statement Issues

These two statements are intentionally not corporate-approved for transaction-level use yet. Do not reintroduce aggregate or synthetic "UNCAPTURED" transactions to make them reconcile.

### Farmers & Merchants Bank / Ace Auto

- File: `BankStatements/Misc/Ace_Auto_Final_Cut.pdf`
- Current parser: `analysis/farmers_merchants.py`
- Current quality: `summary_trusted`
- Current corporate use: `summary_only`
- Current status: bank summary reconciles, but visible transaction detail does not reconcile.
- Evidence: the PDF summary says `26 Checks/Debits` totaling `$3,945.12`, but the visible source pages only itemize about 26% of debit dollars.
- Later fix target: obtain a complete source statement or add support for any missing check/image detail pages if they become available. Transaction-level approval should require all bank-stated debit activity to be itemized and reconciled without aggregate rows.

### BMO Bank of Montreal

- File: `BankStatements/Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf`
- Current parser: `analysis/bmo.py`
- Current quality: `summary_trusted`
- Current corporate use: `summary_only`
- Current status: bank summary reconciles, but printed transaction rows and running balances are internally inconsistent.
- Evidence: the parser captures 41 printed rows, but multiple printed running balances do not equal prior balance plus/minus the printed row amount; page totals also conflict (`$294,700.00` deposits on page 1 vs `$300,000.00` on page 2).
- Later fix target: verify whether this is a bad/synthetic source PDF. Transaction-level approval should require corrected source totals and running balances, or a bank-authentic statement whose line items reconcile without aggregate rows.

## Current Coverage Baseline

- Last complete full audit before removing aggregates: 83 statements total, 81 transaction-level approved, 2 summary-only aggregate-backed.
- After aggregate removal and source parser fixes: the same 2 statements are `summary_trusted`, `summary_only`, and `aggregate_rows=0`.
- The expected near-term corporate baseline is therefore: 81 transaction-level approved statements, 2 deferred summary-only statements.
