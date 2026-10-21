# CURRENCY DOCTRINE — RATIFIED (Gustavo, 2026-08-16)

Ratified alongside the Batch-6 GO. This document is the doctrine of record;
the WAVE2_EXECUTION_LOG batch entry references it. It governs every cell
that touches currency, packages, or published financial metrics.

The program records this document cites (logs, rulings, reviews, plans, handoffs) were removed from the tree. [`docs/HISTORY.md`](../HISTORY.md) says how to read them.

## A. Native currency is canonical

The bank-statement analysis layer preserves the NATIVE currency of the
account. We do NOT normalize statement metrics to USD because Capital
Infusion is U.S.-based or because many lenders operate in USD. Currency
conversion and lender eligibility are separate concerns from statement
analysis.

All financial metrics remain in the account's native currency:
Average Daily Balance, beginning balance, ending balance, credits, debits,
verified revenue, non-revenue, lender activity, transaction amounts, and
all other financial totals. **No FX conversion occurs inside the
bank-statement analysis layer.**

Examples:
- U.S. Chase account → USD
- U.S. Bank of America account → USD
- RBC Canada account → CAD by native account/jurisdiction default
- RBC U.S. Dollar / `U.S. Funds` account → USD
- Canadian TD account → CAD
- Canadian TD account explicitly denominated in USD → USD

**Explicit document evidence always overrides a native default. Do not
infer currency from the `$` symbol alone.**

## B. Jurisdiction defaults, not absence rules (the RBC reframe)

The rejected framing: `absence of "U.S. Funds" => CAD`.
The ratified rule: **a proven RBC Canada account/product has CAD as its
native default unless the document contains affirmative evidence of
another currency.**

- `U.S. Funds`, U.S. Dollar wording, USD account designation, or
  equivalent explicit evidence → USD
- proven RBC Canada account/product with no contrary currency evidence
  → CAD
- RBC U.S. institution/product → the Canadian default does not apply
- conflicting or genuinely uncertain evidence → fail closed / preserve
  uncertainty rather than force a currency

This is a bank/account-jurisdiction default expressed structurally by
bank/product/jurisdiction evidence — never by filename or folder
assumptions. The same shape generalizes to other cross-border
institutions (TD, BMO, CIBC…), each requiring its own proven-jurisdiction
evidence base before any default is wired.

## C. RBC 151-document gate (pre-ceremony obligations)

No pinned ceremony until a READ-ONLY measurement packet over all 151
documents proves, all eight:
1. every affected document is actually an RBC Canada account/product to
   which CAD is the correct native default;
2. none contains explicit USD or other contrary currency evidence;
3. RBC U.S. products cannot be swept into the rule;
4. the four pinned RBC documents are individually enumerated;
5. exact before/after currency values are shown;
6. no financial amounts, ADB values, ledger math, classifications, or
   validation outcomes change merely because the currency label changes;
7. the nine explicit-evidence CURRENCY-1 corrections remain unchanged;
8. the rule is expressed structurally by bank/product/jurisdiction
   evidence, not filename/folder assumptions.
If all eight prove clean, Gustavo receives the formal ceremony packet for
the four pinned RBC expectations and the exact 151-document movement.
**Do not weaken the gate to make the ceremony pass.**

## D. Product / UI rule

The dashboard shows ONE Average Daily Balance metric, denominated:
`Average Daily Balance: $42,500 CAD` or `Average Daily Balance: $42,500 USD`.
No separate CAD-ADB / USD-ADB / bank-reported-ADB cards. The currency
identifies the denomination of the one canonical underwriting ADB
(ADB doctrine sections A–B unchanged). The same applies to the other
financial metrics.

## E. Lender-matching separation

The statement parser must not depend on which lender Capital Infusion may
eventually submit the merchant to. The statement analyzer answers: *what
happened in this bank account, in the account's real currency?* A future
lender-matching/underwriting-routing layer may answer lender-threshold
questions. If a lender eventually requires USD-normalized values, the
conversion happens there, explicitly and separately, and must preserve:
original native amount, original currency, converted amount, target
currency, exchange rate, rate source, rate timestamp. **The original
statement values are never overwritten.**

## F. Multi-statement packages

Statements in the same native currency continue through normal package
analysis. **Never silently combine financial values from different
currencies** — `30,000 CAD + 20,000 USD != 50,000 package ADB`. If a
package contains multiple currencies: preserve statement-level results and
stop any cross-currency package aggregation that would mathematically mix
units, until a separate package-level FX policy is explicitly approved.

## Standing constraint

Any unexpected pinned financial movement remains a hard stop.
