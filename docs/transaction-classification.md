# Transaction Classification Contract

`analysis.transaction_classifier.classify_statement_transactions` creates the
authoritative classification record for every parsed ledger row. The pipeline
creates this list once, then passes the same records to metrics, detection,
serialization, API responses, downloads, dashboard cards, filters, and evidence
tables. Consumers must use contribution flags on these records and must not scan
transaction descriptions independently.

Classification version 5.0 (2026-09-24) applies the owner's lender rulings in
`docs/superpowers/specs/2026-09-24-lender-detection-design.md` (decisions D1-D12).

## States and precedence

Every row has exactly one state:

`confirmed_lender`, `potential_lender`, `insurance`, `alternative_position`,
`line_of_credit`, `vehicle_financing`, `bank_loan`, `mortgage`,
`lease_or_rental`, `personal_loan`, `floor_plan_financing`, `factoring`, `fee`,
`transfer`, `credit_card_payment`, `payroll`, `tax`, `utility`, `rent`, `pos`,
`atm`, `nsf_or_return`, `refund_or_reversal`, or `other`.

`lease_or_equipment_financing` is retired: no rule produces it since version
5.0, but records stored before 5.0 carry it and still validate.

Only MCA and revenue-based funders and equipment financing are
`confirmed_lender`. Eleven groups are flagged instead. Their debits never enter
lender counts, lender totals, withholding or potential exposure:

| State | `flagged_group` | Label |
|---|---|---|
| `alternative_position` | `alternative_positions` | Alternative positions |
| `line_of_credit` | `lines_of_credit` | Lines of credit |
| `credit_card_payment` | `credit_cards` | Credit cards |
| `vehicle_financing` | `vehicle_financing` | Vehicle loans & leases |
| `bank_loan` | `bank_loans` | Bank loans |
| `mortgage` | `mortgages` | Mortgages |
| `lease_or_rental` | `leases_rentals` | Leases & rentals |
| `personal_loan` | `personal_loans` | Personal loans |
| `floor_plan_financing` | `floor_plan` | Floor plan |
| `factoring` | `factoring` | Factoring |
| `insurance` (premium-finance payees only) | `premium_financing` | Premium financing |

Premium financing is the one group that is not a state. Its rows stay
`insurance` and keep their insurance totals. The insurance rule sets
`flagged_group="premium_financing"` on a debit whose insurer is a
premium-finance payee (`PREMIUM_FINANCE_ALIASES`).

A flagged group's credits are another matter. A credit from a financing group
(every flagged group except credit cards, leases & rentals, premium financing
and factoring) is financing proceeds, and D1 subtracts it from eligible deposits
as it does a lender's credit (see "Withholding rate"). Three kinds of credit
are not subtracted: a payout-credit entity's credits (`PAYOUT_CREDIT_ENTITIES`),
which are the holder's own sales; a premium-finance payee's credits, which keep
the insurance credit treatment; and a factoring payee's credits (owner ruling
2026-09-26), which are the business's own sales, paid by the factor that bought
its invoices. A factoring credit takes the operating-revenue path, as a payout
credit does, and it is also flagged: its state is `factoring`, its entity is
the payee, and it counts in the Factoring group as a credit.

The group list lives in `analysis/flag_groups.py`. A flagged row carries
`flagged_group`; a posted flagged debit, and a posted factoring credit, also
set `contributes_to_flagged_totals`. Proven duplicates, settlement-reversed
debits and credits that the reversal pass pairs clear it. The web app hides
unticked groups at serving time; the stored record never changes.

Every posted credit also has exactly one independent revenue state:

`verified_revenue`, `unverified_deposit`, or `non_revenue`.

This second state does not replace the transaction state. For example, a
returned e-transfer remains `refund_or_reversal` and is also `non_revenue`.
Revenue classification applies cancellations, reversals, financing proceeds,
and strong non-revenue exclusions before operating-income rules. Identifiable
card credits and refunds, purchase/payment/ACH returns, chargebacks, own-account
transfers, financing and insurance proceeds, tax refunds, rewards, fee refunds,
interest, and reimbursements bypass manual revenue review as `non_revenue`.
A maintained operating-source alias is supporting evidence, not sufficient
evidence by itself. Verification also requires credit direction plus
settlement, payout, merchant-deposit, or similar context; alternatively,
statement-level recurrence on a business account or related processing fees,
commissions, chargebacks, and adjustments can supply that context. Generic ACH,
wire, RTP, Zelle, and e-transfer credits, mobile/branch/ATM/night deposits,
checks, cash deposits, and unidentified credits are `unverified_deposit` until
reviewed. Own-account transfers are excluded when the description identifies
the internal account or self-service transfer channel.

Cancellation and reversal rows are matched to opposite-direction transactions
by amount, date proximity, and description family when possible. The record
stores the related source location, revenue source type, context signals, match
method, alias/rule, confidence, reason, review status, and mutually exclusive
revenue contribution flags.

Classification is applied in this order; the first match wins:

1. Non-posted items, NSF and returned items, refunds and reversals.
2. Insurance, by registry or by term. Premium-finance payees are looked up
   first; they stay insurance and a debit also carries the premium-financing
   flag. On the owner's ruling a premium-finance alias may repeat a hand-kept
   insurer's alias (`PREMIUM_FINANCE_INSURER_ALIASES`), and such rows are premium
   financing too. A descriptor with premium-finance
   wording (`PREM FIN`, `PREMIUM FINANCE`, `INSPREMFIN`) and no premium-finance
   payee is premium financing under the insurer it names, or under
   `Insurance provider not identified`. A premium-finance payee's credit is
   treated as any insurer's credit.
3. POS and ATM. A row whose payee is a known payee is classified by who was paid
   instead (D8). An alternative-position payee's membership or balance top-up
   (its alias followed by `PLUS`, `MEMBER`, `MEMBERSHIP` or `BALANCE TOP UP`) is
   not a repayment and matches no known payee.
4. Fees (an overdraft charge included, even when it prints the item's payee),
   transfers, tax, payroll and utilities.
5. The known-payee matcher (`analysis.payee_matcher.match_known_payee`) over the
   group registries. A debit takes the payee's group. A descriptor that says LOC
   or LINE OF CREDIT moves a lender, alternative-position or line-of-credit payee
   to `line_of_credit` (D9). A credit from a financing group (lenders,
   alternative positions, lines of credit, bank loans, vehicle financing,
   mortgages, personal loans, floor plan) is financing proceeds: `other`,
   revenue `non_revenue`, excluded from eligible deposits (D1). The exclusion
   follows the credit's revenue decision, whichever rule named the row: a
   financing group's credit that a transfer or insurance-term rule claims first
   keeps that state, and its revenue decision is still financing proceeds, so
   it is still `non_revenue` and excluded from eligible deposits. Two payees'
   credits are revenue instead, and their debits keep their group: a
   payout-credit entity's (`PAYOUT_CREDIT_ENTITIES`, owner ruling), the account
   holder's own sales; and a factoring payee's (owner ruling 2026-09-26), the
   business's own sales paid by the factor. Both take the operating-revenue
   path and stay in eligible deposits. A factoring credit is also recorded as
   `factoring` under its payee (`factoring_revenue_credit`), so it carries the
   Factoring flag. Three credits are proceeds by their own words: the
   statement bank's line advance (exactly `LOAN CREDIT`), a line-of-credit draw
   and a per-vehicle floor-plan advance (`ADVANCE`, a model year, `VIN`).
   Card-issuer and lease/rental payees never apply to credits.
6. Obligation descriptors, debits only, for rows no known payee claimed. A
   transfer between the holder's own accounts (`TRANSFER TO ... TRANSFER OUT`)
   takes none of them. In order:
   - a per-vehicle floor-plan payoff;
   - LOC or line of credit;
   - mortgage or home-equity loan;
   - auto or vehicle loan, lease or payment;
   - student loan (a personal loan);
   - a listed bank with loan wording (`LOAN` or French `PRET`);
   - the statement bank's own loan, D5: a transfer to it, its own loan-payment
     wording, its commercial-loan billing, its French loan wording, or a loan
     payment that prints no payee (entity the statement bank). Another bank's
     unnamed loan is a bank loan with no entity;
   - lease, rental or lease-to-own;
   - credit-card payments, including a listed card issuer with payment wording
     and a payment to a card account named only by its type;
   - unnamed equipment financing, which is a `potential_lender` for review (D4).
7. Rent. Landlord and office rent are never flagged (D3).
8. Checks and subscriptions (`other`).
9. Bank-specific lender rules, then the potential tier: the potential registry,
   unknown loan servicers and debt collectors (D10, `MCA SERVICING` included),
   direct-debit loans, explicit repayments (a loan payment that prints a lender,
   a servicer, a person or another bank stays potential, D5), and financing
   words with a payment marker (`other`, review).

Statement passes run in this order: duplicates; recurrence; reversal pairs;
operating-source context; duplicate finalisation. Recurrence promotes to
`potential_lender`, review only, two kinds of same-amount debit groups on at
least three different dates on a daily or weekly cadence (several rows on one
date count as one): financing-keyword rows of one payee
(`recurring_financing_counterparty`), and rows no rule claimed (`other`, match
method `default`) whose descriptor names a payee and carries no transfer wording
(`recurring_fixed_debit`, D6). D6 never takes a card-purchase posting, including
the card formats the POS rule does not read: a posting that starts `PURCHASE`
and its mmdd (after an optional `RECURRING`), and a descriptor with a
`processor*merchant` mark (`TST*NAME`, `SQ *NAME`, `TST* NAME`: a letter or
digit, an optional space, `*`, an optional space, a letter or digit). The star
is read only on a row with no ACH field mark (`ACH`, `CCD`, `PPD`, `CTX`, `WEB`,
`DES:`, `INDN`, `CO ID`, `ID:`, `ORIG CO`, `RMR`), because an ACH entry prints
stars too: in its addenda (`RMR*IV*`), a masked account or an ID. The word
`PURCHASE` alone is not a card mark, since an ACH entry description can print
it. Recurrence never makes a counted lender: nothing is counted without a named
lender. The recurring-debit view
(`detection.recurring_debits`, the CLI's "Recurring fixed debits") lists both
kinds, grouped by entity and amount.

An unknown payee is named from its descriptor (D11). Originator-name labels are
removed; the text is cut at the first ACH field segment (DES, ID, INDN, IND
NAME, CO ID, TRACE, SEC, EED, TYPE and similar); channel words and reference
tokens (digits, masked numbers, months) are dropped; and at most four words are
kept. Without an organisation cue (LLC, INC, CORP, CO, FUNDING, CAPITAL,
FINANCIAL, FINANCE, BANK, CREDIT, LENDING, ADVANCE, GROUP, HOLDINGS, SERVICES or
a legal-form suffix) the entity is `Unidentified lender obligation`, so a
person's name is never published as a lender. Payees are grouped for recurrence
by these words, so one payee keeps one name across dated descriptors and two
unnamed payees are never merged.

A higher-precedence non-lender match overrides generic words such as `finance`,
`capital`, `funding`, and `payment`. Unverified credible financing counterparties
are `potential_lender` and require review. Ambiguous rows remain `other` and
require review; they do not contribute to lender metrics.

## Normalization and registries

Descriptions are preserved verbatim and also normalized case-insensitively.
Normalization standardizes whitespace, punctuation, hyphens, common OCR errors,
and safe transaction identifiers while preserving meaningful counterparty
tokens. Registry aliases use token-boundary matching and resolve to one canonical
entity. The alias tables are normalized and compiled once
(`analysis/payee_matcher.py`); a known-payee lookup returns the longest alias
across all group registries (`PAYEE_GROUP_REGISTRIES`), so a financing-specific
alias beats a shorter brand alias. Insurance aliases (`INSURANCE_PROVIDER_ALIASES`)
and premium-finance aliases (`PREMIUM_FINANCE_ALIASES`, not a group registry)
are maintained separately and have precedence over lender rules. Operating revenue aliases and source
types are maintained in `OPERATING_REVENUE_SOURCE_ALIASES` and
`OPERATING_REVENUE_SOURCE_TYPES`.

The record stores the source description, normalized description, canonical
entity, date, amount/direction, bank/account, source location, match method,
matched alias/rule, confidence, human-readable reason, review status, duplicate
status, flagged group, and every metric contribution flag.

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
  rows and their absolute sum, premium-financing rows included.
- `flagged_groups`: per flagged group key, `{count, total, count_credited,
  total_credited, payees}` over rows marked `contributes_to_flagged_totals`.
  `count` and `total` are the debits and their absolute sum; `count_credited`
  and `total_credited` are the credits (a factoring payee's payouts) and their
  sum; `payees` counts the payees with any contributing row. Only groups with a
  contributing row appear, in flag-group order. It never feeds lender,
  withholding, eligible-deposit or potential figures.
- `detection.flagged_positions`: one entry per flagged group and payee (`group`,
  `payee`, `matched_alias`, `count`, `total_debited`, `count_credited`,
  `total_credited`, `cadence`, `avg_gap_days`, `first_date`, `last_date`,
  `source_locations`), in flag-group order, then by total debited plus total
  credited, then by payee. `count` and `total_debited` are debits only; a payee
  whose counted rows are all credits has an entry with a `count` of 0. The
  payee is the canonical entity, or the group label when the descriptor names
  none; the cadence (`daily`, `weekly`, `biweekly`, `monthly`, `irregular` or
  `single`) comes from `analysis.cadence.describe_cadence`, over the dates of
  every counted row, debit or credit, as do `first_date` and `last_date`.
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
balance, refunds, reversals, NSF returns, insurance, flagged obligations, fees,
and all other non-lender states are excluded from lender totals.
Identical-looking rows without running-balance proof are retained because they
may be legitimate repeated transactions.

## Withholding rate

The existing eligible-deposit policy is preserved:

`eligible_deposits = effective_total_deposits - recognized_lender_funding_credits`

`effective_total_deposits` uses a reconciled bank-printed total when available
and otherwise uses parsed credit rows. Recognized lender funding credits are
every credit from a financing-group payee (D1: lenders, alternative positions,
lines of credit, bank loans, vehicle financing, mortgages, personal loans and
floor plan).
They are excluded because they are financing proceeds, not operating deposits.
D1 reads the payee registries, except two kinds of payee whose credits are the
account holder's own sales and stay in eligible deposits: a payout-credit entity
(`PAYOUT_CREDIT_ENTITIES`) and a factoring payee (owner ruling 2026-09-26: a
factor's payout for the invoices it bought; it is flagged, never subtracted). A
credit is subtracted whenever its revenue decision is financing proceeds,
whichever rule named the row: a financing group's credit that a transfer or
insurance-term rule claims first is subtracted too. A premium-finance payee's
credits keep the insurance credit treatment and are not subtracted. D1 also
reads three descriptors: the statement bank's
own line advance (`LOAN CREDIT`), a line-of-credit draw and a per-vehicle
floor-plan advance. Any other credit whose descriptor names no listed payee (an
unnamed loan advance, for example) keeps its revenue rule and is not subtracted
here.

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

Lender and flagged-payee knowledge lives in the curated ledger
`docs/lender-registry-ledger.json` (contract C10 of the lender-detection plan),
never in hand-edited tables. Add or change an entity there: its group
(`confirmed_lender` for MCA funders and equipment financing, a flagged group,
`card_issuer_context` for a bare card issuer that needs payment wording,
`premium_financing`, `bank_name` for the D5 bank-loan rule, or
`potential_lender`), its aliases, status, evidence and verdicts. Then run
`python -m tools.build_lender_registry --check` to validate the ledger and
`python -m tools.build_lender_registry --write` to render the GENERATED block
of `analysis/classification_registry.py` (`LENDER_ALIASES`, each group's table,
`CARD_ISSUER_CONTEXT_ALIASES`, `PREMIUM_FINANCE_ALIASES`, `BANK_NAME_ALIASES`
and `POTENTIAL_LENDER_ALIASES`) and `docs/lender-registry-evidence.md`, and
commit the three files together. Never edit the GENERATED block by hand:
`tests/test_lender_registry_drift.py` fails when the committed tables are not
the rendering of the committed ledger.

The constants after the GENERATED block are hand-kept.
`PAYEE_GROUP_REGISTRIES` wires the rendered tables to the known-payee matcher.
`PAYOUT_CREDIT_ENTITIES` (financing-group payees whose credits are the holder's
own sales), `OWNER_NAMED_PAYEES`, `BARE_PLATFORM_NAMES`, `BARE_BRAND_NAMES`,
`PREMIUM_FINANCE_INSURER_ALIASES`, `MERGED_REGISTRY_ENTITIES` and
`REATTRIBUTED_REGISTRY_ALIASES` are inputs of the ledger validator and change
only on an owner ruling. Insurance aliases (`INSURANCE_PROVIDER_ALIASES`) and
operating-revenue aliases and source types (`OPERATING_REVENUE_SOURCE_ALIASES`,
`OPERATING_REVENUE_SOURCE_TYPES`) are not in the ledger and are edited in that
module directly.

An alias names the financing business, never a bare platform or a brand that
also sells goods; the validator refuses both. The one place a bare brand or
card issuer is allowed is a `card_issuer_context` or `bank_name` entity, whose
rules read it only beside card-payment or loan wording. Cover aliases, OCR variants,
token boundaries, precedence, both directions, and contribution flags in tests.
Do not add statement-specific description checks in parsers, metrics, API
routes, or frontend code.
