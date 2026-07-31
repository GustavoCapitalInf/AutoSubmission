# Transaction Classification Contract

`analysis.transaction_classifier.classify_statement_transactions` creates the
authoritative classification record for every parsed ledger row. The pipeline
creates this list once, then passes the same records to metrics, detection,
serialization, API responses, downloads, dashboard cards, filters, and evidence
tables. Consumers must use contribution flags on these records and must not scan
transaction descriptions independently.

## States and precedence

Every row has exactly one state:

`confirmed_lender`, `potential_lender`, `insurance`,
`lease_or_equipment_financing`, `fee`, `transfer`, `credit_card_payment`,
`payroll`, `tax`, `utility`, `rent`, `pos`, `atm`, `nsf_or_return`,
`refund_or_reversal`, or `other`.

Classification is applied in this order:

1. Non-posted items, NSF/returns, refunds, and reversals.
2. Insurance and strong non-lender exclusions.
3. POS, ATM, fees, transfers, payroll, tax, utilities, rent, leases, and
   credit-card payments.
4. Verified lender aliases and explicit repayment descriptors.
5. Bank-specific lender rules.
6. Recurrence combined with a financing-related counterparty.
7. Confidence scoring and the final state.

A higher-precedence non-lender match overrides generic words such as `finance`,
`capital`, `funding`, and `payment`. Recurrence alone is never lender evidence.
Unverified credible financing counterparties are `potential_lender` and require
review. Ambiguous rows remain `other` and require review; they do not contribute
to lender metrics.

## Normalization and registries

Descriptions are preserved verbatim and also normalized case-insensitively.
Normalization standardizes whitespace, punctuation, hyphens, common OCR errors,
and safe transaction identifiers while preserving meaningful counterparty
tokens. Registry aliases use token-boundary matching and resolve to one canonical
entity. Insurance aliases are maintained separately and have precedence over
lender rules.

The record stores the source description, normalized description, canonical
entity, date, amount/direction, bank/account, source location, match method,
matched alias/rule, confidence, human-readable reason, review status, duplicate
status, and every metric contribution flag.

## Metric definitions

- `lenders_detected`: distinct canonical entities with qualifying posted
  `confirmed_lender` debit rows.
- `potential_lenders_detected`: distinct canonical entities with qualifying
  posted `potential_lender` debit rows.
- `potential_lender_debit_count` and `potential_lender_debit_total`: qualifying
  posted potential-lender debit rows and their absolute sum. These rows remain
  excluded from confirmed lender totals and confirmed withholding.
- `lender_debit_count`: qualifying posted confirmed-lender debit rows.
- `total_lender_debits`: absolute sum of those exact rows.
- `insurance_count` and `insurance_total`: qualifying posted insurance debit
  rows and their absolute sum.

Credits, funding deposits, duplicates proven by a repeated printed running
balance, refunds, reversals, NSF returns, insurance, leases, fees, and all other
non-lender states are excluded from lender totals. Identical-looking rows without
running-balance proof are retained because they may be legitimate repeated
transactions.

## Withholding rate

The existing eligible-deposit policy is preserved:

`eligible_deposits = effective_total_deposits - recognized_lender_funding_credits`

`effective_total_deposits` uses a reconciled bank-printed total when available
and otherwise uses parsed credit rows. Recognized lender funding credits are
excluded because they are financing proceeds, not operating deposits.

The formula is:

`withholding_rate = abs(total_qualifying_lender_debits) / eligible_deposits * 100`

The numerator is the exact lender debit total represented by the lender evidence
records and lender transaction filter. Full precision is retained internally;
rounding occurs only for display. A zero or missing denominator returns no rate
and sets `withholding_review_required`.

Potential lender exposure is a separate review metric over the same eligible
deposit definition:

`potential_withholding_exposure = abs(potential_lender_debit_total) / eligible_deposits * 100`

Its numerator is the exact set of rows marked
`contributes_to_potential_withholding_exposure`; those rows are exposed in the
potential evidence table and transaction filter. A material potential debit sets
`potential_withholding_review_required` even when confirmed withholding is 0%.
The potential amount remains available when the denominator is unavailable; only
the exposure is reported as `N/A` in that case.

## Extension rule

Add provider and counterparty knowledge in `analysis/classification_registry.py`,
with tests that cover aliases, OCR variants, token boundaries, precedence, and
metric contribution flags. Do not add statement-specific description checks in
parsers, metrics, API routes, or frontend code.
