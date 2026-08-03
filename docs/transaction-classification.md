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

Every posted credit also has exactly one independent revenue state:

`verified_revenue`, `unverified_deposit`, or `non_revenue`.

This second state does not replace the transaction state. For example, a
returned e-transfer remains `refund_or_reversal` and is also `non_revenue`.
Revenue classification applies cancellations, reversals, lender funding, and
strong non-revenue exclusions before operating-income rules. Identifiable card
credits and refunds, purchase/payment/ACH returns, chargebacks, own-account
transfers, financing and insurance proceeds, tax refunds, rewards, fee refunds,
interest, and reimbursements bypass manual revenue review as `non_revenue`.
A maintained
operating-source alias is supporting evidence, not sufficient evidence by
itself. Verification also requires credit direction plus settlement, payout,
merchant-deposit, or similar context; alternatively, statement-level recurrence
on a business account or related processing fees, commissions, chargebacks, and
adjustments can supply that context. Generic ACH, wire, RTP, Zelle, and
e-transfer credits, mobile/branch/ATM/night deposits, checks, cash deposits, and
unidentified credits are `unverified_deposit` until reviewed. Own-account
transfers are excluded when the description identifies the internal account or
self-service transfer channel.

Cancellation and reversal rows are matched to opposite-direction transactions
by amount, date proximity, and description family when possible. The record
stores the related source location, revenue source type, context signals, match
method, alias/rule, confidence, reason, review status, and mutually exclusive
revenue contribution flags.

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
lender rules. Operating revenue aliases and source types are maintained in
`OPERATING_REVENUE_SOURCE_ALIASES` and `OPERATING_REVENUE_SOURCE_TYPES`.

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
- `verified_revenue_total` and `verified_revenue_count`: posted credits marked
  `contributes_to_verified_revenue`.
- `unverified_deposit_total` and `unverified_deposit_count`: posted credits that
  could be operating revenue but require review.
- `non_revenue_total` and `non_revenue_count`: funding, identifiable own-account
  transfers, contributions, returns, refunds, corrections, rewards, interest,
  proceeds, and proven duplicate credits.
- `maximum_revenue`: verified revenue plus unverified deposits.

Revenue must reconcile from the authoritative rows:

`verified revenue + unverified deposits + non-revenue = total posted credits`

Reviewer confirmation changes an unverified row to `verified_revenue`; rejection
changes it to `non_revenue`. Reset restores `unverified_deposit`. The
API, package aggregation, filters, evidence tables, and exports are rebuilt from
the updated record.

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

The default mode is explicitly exposed as `legacy_eligible_deposits`. Set
`WITHHOLDING_DENOMINATOR_MODE=verified_revenue` to opt into verified classified
revenue instead. The legacy value `confirmed_true_revenue` is accepted and
normalized to `verified_revenue`. API and UI output include
`withholding_denominator_mode` and `withholding_denominator_label`; the mode is
never switched implicitly when revenue classification is available.

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
