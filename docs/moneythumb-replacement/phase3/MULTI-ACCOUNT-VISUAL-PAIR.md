# Multi-account statements in the visual pair (Phase 3.1)

Owner request (2026-09-23): statements that hold several accounts (a business checking account beside savings
shares, a bank's combined statement) are separated account by account; each account gets its own transactions and
average daily balance; the dashboard focuses on the account a lender funds (the main account: business checking)
and a Settings toggle shows every account's breakdown. The logic is kept for every account even when only the
main one is shown.

## What the visual pair does

A statement is first judged as ONE account, exactly as before. Only when that fails, and the statement prints two
or more account headings, is it judged account by account (`vlm/pair_accounts.py`). No model call is added: the
partition, the figures and the verdicts are deterministic readings of the proposer's layout blocks, the page text
layer and the reviewed rows.

1. **Headings** (`vlm/accounts.py::parse_heading`). A short title line printing an account kind (checking,
   savings, share, money market, certificate, ...) or an identifier printed as one (masked `XXXXXX1234`,
   `ID 0001`, `Suffix 10`, `(0001)`, `S 0001`, a 4+ digit number) names an account. Sentences, lines printing
   money, page headers/footers, identifier lines (`Account Number ...`, `Member Number ...`) and listing or notice
   captions ("Summary of Accounts", "Checks Cleared", "Withdrawal Summary", "... Information") never do.
2. **One account or two** (`_same_account`). Headings printing the same identifier (last four digits) are one
   account; different identifiers or different kinds are two. Without identifiers, equal titles are one account,
   and a title naming nothing but the kind ("Checking", "Checking Accounts", "Checking Account Activity - Main
   Account") is the account of that kind it does not contradict. A lower Markdown heading directly under an
   account's heading is its product name.
3. **Rows** (`assign_rows`). A row belongs to the account whose heading is printed last before it in reading
   order (crop-recovered rows are mapped to their full-page block). A reviewer's addition takes the position of the
   row it was added after (else before); on a page printing several accounts with no proposer row beside it, the
   height of its own box. A row whose account is still unknown holds that page's accounts; rows printed before
   every heading (a summary table the reviewer kept) belong to none and are counted.
4. **Figures** (`section_figures`, `summary_table_figures`). An account's opening balance is the first one its own
   section prints and its closing balance the last; totals count only when printed once and only when they carry
   the opening to the closing. A figure the page's text layer does not print is a misread and no candidate. When
   the section prints no opening or closing, a summary table whose header row labels the figure columns and
   whose row names the account (by number, else title) supplies it.
5. **Verdict**. Each account's rows go through the SAME gate as a single-account statement (balance chain, sum,
   printed totals, duplicates, dates), with the statement's period and currency. A listing that repeats ledger
   rows printing running balances ("Withdrawal Summary") is excluded first (`listing_echoes`; also applied to
   single-account statements). An account printing fewer than two amounts of a direction takes the statement's
   print style (a debits column printed "-$5.00").
   * `verified`: the gate admits it; its Statement is published.
   * `idle`: no row, equal printed opening and closing, zero or no totals, on pages with a text layer.
   * `held`: anything else, with reason codes. Another account's failure never holds it (R-b); a page problem
     (cut-off read, transport failure, unresolved row) holds only the accounts printed on that page.

Document facts every account needs hold them all: `period_mismatch`, `currency_conflict`, `currency_missing`.

## What the analysis publishes

`vlm/pair_adapter.py::_analyze_accounts` analyses each verified account with the ordinary account-report path
(`analyze_statement`, the account's own rows as its source text), so its ADB, revenue and lender analysis are the
same code as any statement's. `DocumentReport.account_roster` (new, `analysis/pipeline.py`) lists every account the
statement prints in printed order: `published` (with its index in `accounts`), `idle` (with its unchanged
balance) or `held` (with reason codes, and no figure: an unverified number is never published). Internal transfers
between the published accounts are identified as before (R-d). Nothing is summed across accounts (R-c).

Payload shape (RULE S unchanged): two or more published accounts publish `{"document": ..., "accounts": [...]}`; one
published account publishes today's payload plus a `document` block carrying the roster. The roster key appears
only when a reader judged the statement account by account, so every existing payload is byte-identical.

## What the dashboard shows

* **Default** ("All accounts" off): the main account's full analysis, and a note naming how many accounts the
  statement holds and which one is shown. The main account is a display default only (R-e: the engine chooses
  nothing): a business checking account; among several, the one with the most deposits.
* **Settings -> All accounts** (kept in the browser, `localStorage` key `bsa-all-accounts`): a table of every
  account (type, status, beginning, ending, deposits, withdrawals, average daily balance, transactions); the main
  account is tagged MAIN; selecting a verified account shows its full analysis below. Idle accounts show their
  unchanged balance; held accounts show why, and no figures.
* The statement modal (package view) shows the main account of a multi-account statement.

## Limits

* A statement printing a loan or credit-card section beside its deposit accounts: the section is judged like any
  account; its kind is shown, and the main account is still the business checking account.
* A closing balance derived from a last running balance (no printed closing) is held, as for single accounts.
* Accounts whose headings the proposer does not read as a block (a heading inside a paragraph) are not separated;
  the statement is then held as before.
