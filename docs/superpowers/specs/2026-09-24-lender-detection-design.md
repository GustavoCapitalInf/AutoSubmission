# Lender detection and flagged positions: design

- **Date:** 2026-09-24
- **Branch:** `lender-detection`, from `text-first-v1` at `31f86b7`
- **Owner:** Gustavo
- **Status:** design approved in conversation 2026-09-24; this spec awaits the owner's read
- **Comes before:** the text-first reader (`2026-09-24-text-first-reader-design.md`)

## 1. Why

Across many statements, the owner kept catching lenders that detection missed. Two things were investigated:

- **A census:** today's code run read-only over the 7,241 analyses cached in the local job store, covering 675,935 debits.
- **A research ledger:** every payee that looked like a lender, identified from public sources and then independently re-checked by a second agent.

The census and the code found three kinds of failure.

**Missed lenders**
- NMEF is filed as "lease or equipment financing", which never reaches the lender list. The owner's example statement is `CHECKCARD … NMEF FUNDING`.
- Many MCA funders have no registry entry at all: Legend Advance Funding, Hunter Caroline, Zlur Funding, Coconut Funding and Lendr are among those confirmed so far.
- Spellings that run words together slip past the aliases. `FORWARDFINANCING` does not match the alias `FORWARDFINANCIN`, and `EXPANSIONCAP` matches no Expansion Capital alias.
- Some rules run before the lender check and take lender payments away:
  - a lender paid by debit card becomes a POS purchase;
  - a lender paid by check is never a lender.
- Payees hidden behind bank-channel prefixes are never matched, e.g. `BUSINESS TO BUSINESS ACH DEBIT … <funder>`.

**Wrongly counted, or wrongly shown as potential lenders**
- These are counted as lenders today, and the owner now rules they are not: SBA/EIDL, BDC, Affirm, Intuit, Square Capital, Shopify Capital, PayPal Working Capital, Fundbox, BlueVine and Kabbage.
- These are shown as potential lenders today but are other obligations: American Express, TD Auto Finance, RBC loan payments and plain "LOAN PAYMENT" rows.

**Missing obligations**
- Bank loans (for example `TRUIST LN … PYMT`), vehicle loans, mortgages and card payments are either "other" or classified inconsistently.

## 2. Owner rulings (2026-09-24)

| Group | Counts as a lender? | Who |
|---|---|---|
| **Lender** | **Yes**: lender count, lender totals, withholding | MCA and revenue-based funders (OnDeck, Bitty, Legend, LG Funding, Hunter Caroline, CAN Capital, CanaCap and so on) and **equipment financing** (NMEF, Balboa, Navitas, Deere and so on) |
| **Potential lender** | No; review, as today | Unknown payees with lender signals |
| Flag: **Alternative positions** | No | SBA/EIDL, BDC, Affirm and other BNPL, Amex loans and lines, Intuit, Square, Shopify, PayPal, Stripe and Amazon financing |
| Flag: **Lines of credit** | No; called out separately as LOC | Fundbox, BlueVine, Kabbage, and any row whose descriptor says LOC or LINE OF CREDIT |
| Flag: **Credit cards** | No | Card payments to Amex, Capital One, Chase, Credit One, Concora and so on |
| Flag: **Vehicle loans & leases** | No | GM Financial, Ford Credit, Toyota Financial, Ally, auto leases |
| Flag: **Bank loans** | No | A bank's own loan payments, e.g. `TRUIST LN … PYMT` |
| Flag: **Mortgages** | No | Mortgage servicers |
| Flag: **Leases & rentals** | No | Equipment rentals, leases, lease-to-own (Progressive, SmartPay, Snap) |
| Flag: **Personal loans** | No | Consumer and student loans paid from the account |
| Flag: **Floor plan** | No; flagged like alternative positions | Inventory (floor-plan) lenders for dealers: NextGear Capital, Westlake Flooring… |
| Flag: **Factoring** | No; flagged like alternative positions | Invoice factoring companies: RTS Financial, OTR Capital, Apex Capital, BC Factoring… |
| Flag: **Premium financing** | No; the rows **stay counted as insurance** as today, and are also flagged | Insurance premium financing: IPFS, First Insurance Funding… |

*Amendment (owner, 2026-09-24):* Floor plan, Factoring and Premium financing were added after round 2 of the research. Each has its own checkbox, default on. The floor-plan and factoring rows are flagged like alternative positions. Premium-financing rows keep the `insurance` state and their insurance totals, and also carry the flag.

- Every flag group has its own Settings checkbox.
- Every checkbox is **on by default**.
- Unticking a checkbox persists, and it applies to every statement, old and new, without re-analysis.
- Flag groups never enter lender math.

## 3. Decisions this spec makes (the owner may overrule any of them at review)

The code forced these choices, and the rulings above did not settle them.

- **D1. Financing proceeds.** A credit from any financing group is financing proceeds. That covers lenders, alternative positions, lines of credit, bank loans, vehicle financing, mortgages and personal loans. Proceeds are `non_revenue` and are subtracted from eligible deposits. This is today's treatment for everything in the lender registry, so the withholding denominators for SBA, Intuit and LOC proceeds do not move. The card-issuer and lease/rental lists never apply to credits: an Amex merchant settlement is revenue.
- **D2. Affirm credits** keep today's treatment as financing proceeds. Whether an Affirm merchant payout is revenue is a separate revenue question and is out of scope here.
- **D3. Plain rent is not flagged.** Landlord and office rent stay `rent`. "Leases & rentals" covers equipment rentals, leases and lease-to-own.
- **D4. Unnamed equipment financing.** A generic `EQUIPMENT FINANCING/FINANCE` descriptor with no named company is a **potential lender** (review), never a counted lender.
- **D5. Unnamed loan payments.** A loan payment with no identifiable counterparty stays a potential lender (review), which is today's behavior. It becomes a **bank loan** only when:
  - the payee is on the bank-name list, or
  - the descriptor is the statement bank's own loan transfer (e.g. `TRANSFER TO LOAN …`).
- **D6. Unknown MCA-style debits.** A payee on no list, with at least 3 debits of the **same amount** on a **daily or weekly** cadence, becomes a **potential lender** (review). This does not apply to rows that are already a POS purchase, transfer, fee, payroll, tax, utility, rent or insurance. It relaxes "recurrence alone is never lender evidence" for the **review tier only**. Nothing is ever *counted* without a named lender.
- **D7. Unticking a checkbox only hides the flag.**
  - A setting never moves a row into review or into lender math.
  - Flag groups never change the package decision.
- **D8. Card-paid lenders.** A known lender or financing payee paid by debit card is classified by who was paid, not as a POS purchase (the NMEF example). Fees and transfers keep their precedence: `ONDECK TRANSFER FEE` stays a fee.
- **D9. LOC wins.** A descriptor that says LOC or LINE OF CREDIT puts the row in Lines of credit, even when the payee is a lender.
- **D10. Servicers.**
  - A servicer or collector whose funder is known is recorded under that funder.
  - An unknown servicer or collector is a potential lender (review).
- **D11. No personal names as lender names.** An unknown payee's entity name is never built from ID/INDN/IND NAME/CO ID/TRACE segments. If no organisation name is left, the entity is "Unidentified lender obligation".
- **D12. Saved jobs.**
  - Statements analysed before this change keep their stored labels until re-analysed. Nothing re-labels them silently.
  - The results page shows a notice and a **Re-analyze** action (§8.6).

## 4. Classification model

### 4.1 States

`ClassificationState` and `CLASSIFICATION_STATES` (`analysis/transaction_classifier.py`) gain:
- `alternative_position`
- `line_of_credit`
- `vehicle_financing`
- `bank_loan`
- `mortgage`
- `lease_or_rental`
- `personal_loan`
- `floor_plan_financing`
- `factoring`

`credit_card_payment` stays; it is the credit-card group.

`lease_or_equipment_financing` is retired:
- equipment financing becomes `confirmed_lender`;
- the rest becomes `lease_or_rental` or `vehicle_financing`.

The dashboard keeps a label for the retired state so that analyses stored before this change still render.

### 4.2 New fields on each classification record

- **`flagged_group: str | None`** holds the group key from the table below, or None. It is set whenever the state is one of the flag groups.
- **`contributes_to_flagged_totals: bool`** is True only for a posted debit of a flag group. It follows the same rules as the lender flags:
  - it is off for proven duplicates;
  - it is off for settlement-reversed debits.

| State | `flagged_group` | Settings key (default `true`) | Label |
|---|---|---|---|
| `alternative_position` | `alternative_positions` | `flag_alternative_positions` | Alternative positions |
| `line_of_credit` | `lines_of_credit` | `flag_lines_of_credit` | Lines of credit |
| `credit_card_payment` | `credit_cards` | `flag_credit_cards` | Credit cards |
| `vehicle_financing` | `vehicle_financing` | `flag_vehicle_financing` | Vehicle loans & leases |
| `bank_loan` | `bank_loans` | `flag_bank_loans` | Bank loans |
| `mortgage` | `mortgages` | `flag_mortgages` | Mortgages |
| `lease_or_rental` | `leases_rentals` | `flag_leases_rentals` | Leases & rentals |
| `personal_loan` | `personal_loans` | `flag_personal_loans` | Personal loans |
| `floor_plan_financing` | `floor_plan` | `flag_floor_plan` | Floor plan |
| `factoring` | `factoring` | `flag_factoring` | Factoring |
| `insurance` (premium-finance payees only) | `premium_financing` | `flag_premium_financing` | Premium financing |

**Premium financing** is the one group that is not a state of its own. The row keeps `classification="insurance"` and `contributes_to_insurance_totals`. When the insurance match is a premium-finance payee (`PREMIUM_FINANCE_ALIASES`), the classifier also sets `flagged_group="premium_financing"` and `contributes_to_flagged_totals`. **D1** (financing proceeds) covers `floor_plan_financing` and `factoring` credits. Premium-financing credits keep today's insurance treatment.

`CLASSIFICATION_VERSION` becomes `"5.0"`.

### 4.3 Rule order (debits). The first match wins.

1. Not posted → `other` (unchanged).
2. NSF or returned item → `nsf_or_return` (unchanged).
3. Refund, reversal or void → `refund_or_reversal` (unchanged).
4. Insurance, by registry or by term (unchanged). Premium finance stays insurance.
5. POS and ATM (unchanged), **except** when the row matches the **known-payee matcher** (§4.6). Today only the lease registry is excepted (D8).
6. Fee, then transfer, then tax, then payroll, then utility (unchanged).
7. **Known-payee matcher** (§4.6), which gives the payee's group. The one exception is LOC wording (D9): if the descriptor says LOC or LINE OF CREDIT and the group is `confirmed_lender`, `alternative_position` or `line_of_credit`, the row becomes `line_of_credit`.
8. Descriptor patterns for rows with no named payee:
   - LOC/LINE OF CREDIT → `line_of_credit`
   - MORTGAGE → `mortgage`
   - AUTO/VEHICLE LOAN, LEASE or PAYMENT → `vehicle_financing`
   - a bank name plus LOAN, LN or LOAN PAYMENT, or the statement bank's own loan transfer → `bank_loan` (D5)
   - LEASE, RENTAL or LEASE-TO-OWN → `lease_or_rental`
   - credit-card payment patterns, widened to the card issuers the research found → `credit_card_payment`
   - EQUIPMENT FINANCING/FINANCE with no named company → `potential_lender` (D4)
9. Rent → `rent` (unchanged, D3).
10. Check, then subscription → `other` (unchanged).
11. Potential-lender rules: the potential registry, direct-debit loans, explicit repayments, and financing words with a payment marker. These are unchanged, except that entity naming follows D11.

Statement-level passes, in order:
1. Duplicates (unchanged).
2. **Recurrence**:
   - today's daily/weekly promotion of financing-keyword rows;
   - plus **D6** for unknown payees with fixed daily or weekly debits.
3. Reversal pairs (unchanged; the pass also clears `contributes_to_flagged_totals`).
4. Operating-source context (unchanged).
5. Duplicate finalisation (unchanged; it also clears `contributes_to_flagged_totals`).

### 4.4 Credits

In `_classify_credit_revenue`, the known-payee matcher runs **before** the operating-revenue registry. A credit from a **financing group** (D1) is `non_revenue`, with match method `financing_proceeds_credit`, and sets `contributes_to_lender_credit_exclusion`. Group aliases are financing-specific: `SQUARE CAPITAL`, never bare `SQUARE`. So platform sales settlements (Square, Shopify, PayPal, Stripe) stay revenue.

Three existing tests pin this:
- `tests/test_revenue_classification.py:440-523`
- `:475-499`
- `:502-523`

### 4.5 Unknown lenders (the potential tier)

**Naming (D11).** Before naming a payee, `_canonical_unknown_entity` removes three kinds of text:
- bank-channel prefixes (`BUSINESS TO BUSINESS ACH DEBIT`, `ELECTRONIC WITHDRAWAL TO`, `ORIG CO NAME`…);
- ACH field segments (`DES`, `ID`, `INDN`, `IND NAME`, `CO ID`, `TRACE`, `SEC`, `EED`…);
- reference tokens.

It then keeps at most four tokens.

If what remains has no organisation cue, the entity is "Unidentified lender obligation". Organisation cues are the words LLC, INC, CORP, CO, FUNDING, CAPITAL, FINANCIAL, FINANCE, BANK, CREDIT, LENDING, ADVANCE, GROUP, HOLDINGS, SERVICES, or a registry-style company token.

Stable names also fix recurrence grouping. Today "NORTHSTAR FINANCE PAYMENT JAN 2…8" splits into five entities.

**D6 rule.** An unknown payee whose key has at least 3 debits of the same amount on a daily or weekly cadence, and none of the excluded states, becomes `potential_lender` with match method `recurring_fixed_debit`, review required.

### 4.6 The known-payee matcher

- **One index, built once.** A single index over every group registry is built at import time. Each alias is normalised once and the patterns are compiled once. A lookup returns `(entity, group, alias)` for the **longest** matching alias across all groups, using the token-boundary rule the current matcher applies (`(?<![A-Z0-9])alias(?![A-Z0-9])`). For example, `AMERICAN EXPRESS BUSINESS LOAN` (alternative position) beats `AMERICAN EXPRESS` (credit card).
- **Run-together forms.** A registry alias written with spaces also matches its run-together form when that form is at least 8 characters long; for example, `FORWARD FINANCING` also matches `FORWARDFINANCING`.
- **Speed.** Today one registry miss costs about 7 ms, and a 300-row statement takes about 3.2 s to classify. The new matcher must be at least **10×** faster on the same synthetic statement.

## 5. The registry

- **Where the lists live.** All names stay in `analysis/classification_registry.py`, the one module the no-hardcode guard exempts (`tests/test_no_statement_hardcodes.py:85-87`). It holds one alias table per group:
  - `LENDER_ALIASES` (MCA funders and equipment financing)
  - `ALTERNATIVE_POSITION_ALIASES`
  - `LINE_OF_CREDIT_ALIASES`
  - `CARD_ISSUER_ALIASES`
  - `VEHICLE_FINANCE_ALIASES`
  - `MORTGAGE_SERVICER_ALIASES`
  - `BANK_NAME_ALIASES` (for D5)
  - `LEASE_RENTAL_ALIASES`
  - `PERSONAL_LOAN_ALIASES`
  - `FLOOR_PLAN_ALIASES`
  - `FACTORING_ALIASES`
  - `PREMIUM_FINANCE_ALIASES`, consulted inside the insurance rule
  - `POTENTIAL_LENDER_ALIASES`

  `CONFIRMED_LENDER_ALIASES` stays as a compatibility name for `LENDER_ALIASES`.
- **Admission.** An entity enters a counted or flagged list only when the research ledger shows all of the following:
  - its identity and business type, confirmed from a public source or an unambiguous descriptor;
  - confirmation by an **independent** second agent (verdict *upheld* or *corrected*).

  *Unresolved* entities never enter a counted list. They go to `POTENTIAL_LENDER_ALIASES` (review), or they are left out and listed for an owner ruling.
- **Aliases:**
  - They come from spellings seen on real statements. They are payee names only, never customer names, amounts or account numbers.
  - Bare platform names (`SQUARE`, `SHOPIFY`, `PAYPAL`, `STRIPE`, `INTUIT`, `AMAZON`) appear only in the operating-revenue registry.
  - An alias must name the *financing* business, not a brand that also sells goods. `TOYOTA FINANCIAL`, `FORD CREDIT` and `GM FINANCIAL` are fine; `TOYOTA`, `FORD`, `APPLE` and `CAPITAL ONE` alone are not. Otherwise a card purchase at a dealership or store would become a flagged position, because card payments to known payees now bypass POS (D8).
  - `BLUEVINE` must not catch transfers to or from a BlueVine *bank account*; it keeps the transfer precedence.
  - `ONDECK`'s `ENOVA` alias must not catch Journey Capital or NetCredit rows.
- **Collision audit.** `tools/lender_alias_audit.py` reads only the local cache and runs outside CI. For every alias it reports the payees it matches, and it must report **zero** matches on a different payee. The research found collisions to fix: `BLUEVINE` catches BlueVine banking, `SmartPay` catches Atlas Financial card rows, and `ONDECK` catches Journey Capital.
- **Evidence ledger.** `docs/lender-registry-evidence.md` lists every entity with its group, a public source URL, the verification verdict, and, for anything unconfirmed, where the researchers looked. It contains no statement text, amounts or customer names.
- **Entities awaiting an owner ruling** are listed at the end of the ledger. One example is a numbered Ontario company debited daily/weekly in about three customer accounts; it is not searched anywhere, by rule.

## 6. The payload (the contract §8 builds on)

Per account:
- **Rows.** Every `statement.transactions[].classification` carries `flagged_group` and `contributes_to_flagged_totals`.
- **`metrics.flagged_groups`** is `{group: {"count": int, "total": float, "payees": int}}`, built from rows with `contributes_to_flagged_totals`. It **never** feeds `lender_*`, `withholding_*`, `eligible_deposits` or `potential_*`.
- **`detection.flagged_positions`** is a list of entries, sorted by total within each group. Each entry holds:
  - `group`, `payee`, `matched_alias`
  - `count`, `total_debited`
  - `cadence` and `avg_gap_days`
  - `first_date` and `last_date`
  - `source_locations`
- **Cadence** comes from a new helper that returns `daily`, `weekly`, `biweekly`, `monthly` or `irregular`. `classify_cadence` and today's promotion gate stay unchanged.
- **Versions:**
  - `CLASSIFICATION_VERSION = "5.0"`.
  - `ANALYSIS_STAGE_VERSION` goes 18 → 19 in the same commit (`webapp/artifact_cache.py`), so a re-upload does not reuse a stale analysis. OCR stays cached.

## 7. Command-line tools, benchmark, docs

- `batch.py` gains a `flagged_positions` column (`group:payee` list), and `analyze.py` prints a Flagged positions block. Both run at analysis time and do not read Settings.
- `benchmark/lenders.py` and `benchmark/compare.py`: MoneyThumb lenders that we now flag are reported as *flagged here*, not as misses. `NON_MCA_SCOPE` is replaced by the flagged groups.
- `docs/transaction-classification.md`: update the state list, the precedence and the extension rule.
- `docs/moneythumb-replacement/R1_HARDCODE_LOG.md`: record that the owner moved `INTUIT FINANCING` (item 12a) to alternative positions on 2026-09-24.

## 8. Webapp

### 8.1 Settings

- `webapp/settings.py` `DEFAULTS` gains the eight `flag_*` keys, each `True`.
- The `GET/POST /api/settings` routes do not change.
- The tests that compare the whole settings dict are updated.

### 8.2 Serving

`_displayed(analysis, *, settings=None)` reads Settings once, when no snapshot is passed. It applies the NSF basis, then the new `apply_flagged_groups_to_payload`. That function:
- **copies before it changes anything.** It copies each account's `statement.transactions`, `detection` and `metrics`. `apply_nsf_basis_to_payload` copies shallowly, and the stored job must never be touched;
- removes unticked groups from `metrics.flagged_groups` and `detection.flagged_positions`;
- sets `flag_shown: bool` on each copied row's classification;
- adds `analysis_rules_outdated: true` when the stored records carry `classification_version < "5.0"`;
- never refuses. Payloads without the new fields pass through unchanged.

`_package_members` reads the whole settings snapshot once per package, as it already does for NSF, and passes it to `_displayed` and to `_package_analysis`.

### 8.3 Package

- **Roll-up.** `_package_analysis` adds `flagged_positions: {group: [{payee, documents, count, total_debited, cadence, first_date, last_date}]}`, built from the rows of each validated member for the ticked groups:
  - internal-transfer legs are excluded;
  - evidence carries `source_account`;
  - cadence is computed across all members' dates.
- **Totals.** `flagged_position_count` and `flagged_position_total` are added.
  - The money keys join `_CROSS_CURRENCY_TOTAL_KEYS` and `EXPECTED_REFUSED_TOTALS`.
  - The count joins `UNIT_FREE_TOTALS`.
  - `total_debited` is already a refused roll-up key.
  - A refused package orders roll-ups by count, then by name.
- **Untouched:** lender totals, withholding, and the `decision` rule (D7).

### 8.4 Downloads

- **Single-statement CSV/XLSX:** readable `flagged_<group>_<n>` rows (payee, count, total, cadence) for ticked groups only, through the escaped-row path.
- **Package CSV/XLSX:** `flagged_<group>_<n>` rows. The currency sweep's `CROSS_DOCUMENT_SECTION` widens to cover them.
- **JSON:** follows the displayed payload automatically.

### 8.5 Dashboard

- **Settings.** A new "Flagged positions" section sits between Analysis and Statements, with its own status line.
  - The checkboxes are rendered from one JS constant into a container.
  - One delegated `change` listener saves one key per change, then calls `refreshShownResults()`.
  - The whole group is disabled while a save is in flight.
- **Flagged positions panel.** It sits on the results page, the package page and the statement modal.
  - Columns: Group, Payee, Count, Total, Cadence, plus Statements on the package page.
  - Money is shown with the payload's currency.
  - Clicking a payee filters the ledger.
  - An empty state says no ticked group has payments.
  - The header text must not reuse "Potential Withholding", "Eligible Deposits" or "Exposure".
- **Transaction tags.**
  - Each new state gets a label.
  - A row with `flag_shown` carries a "Flagged" chip.
  - A credit shows its revenue state first (unchanged).
  - A "Flagged" ledger filter pill is added.
  - When the group being filtered is unticked, the ledger filter resets.
- **Lender table.** No change beyond its now-correct contents.
- **Outdated notice.** When `analysis_rules_outdated` is set, the results page shows "Analysed with older lender rules" and a **Re-analyze** button (§8.6).

### 8.6 Re-analyzing a saved statement (D12)

`POST /analysis/<job_id>/reanalyze` re-runs the analysis for a saved job.

1. It reads the job's stored PDF bytes, which are kept on disk by content hash.
2. OCR is served from the cache.
3. It **replaces the job's analysis in place**. The job id and its place in Recent do not change.
4. The previous analysis is kept in the audit log.
5. Revenue review decisions are **replayed** from `review_decisions` onto the new analysis. A decision is replayed only when the row at the same account and location has the same description and amount. Anything that cannot be replayed is reported back: "N reviews need redoing".

The route refuses when the stored PDF is missing.

## 9. Proof

- **Tests**, all with fabricated descriptors and never statement text:
  - classification tables for every group, both directions, including the card-paid lender (D8), LOC wording (D9), unnamed loans (D5), unnamed equipment financing (D4), the D6 recurrence rule and D11 naming;
  - the credit-side financing proceeds, and platform settlements that stay revenue;
  - Settings, serving and exports for every checkbox, with the stored record unchanged;
  - the package roll-up and the currency refusal;
  - the dashboard through `tests/webapp_js_harness.py`;
  - re-analysis with review replay.
- **Pins that move, re-pinned with derived totals only:**
  - ATB November (BDC leaves the lenders)
  - Altana (Affirm leaves; NMEF joins)
  - first_farmers (BlueVine becomes a LOC)
  - `SBA LOAN PAYMENT`, the Affirm card purchase, and De Lage Landen
  - Intuit (item 12a)
  - NMEF, Navitas and Balboa
  - `ANALYSIS_STAGE_VERSION`
- **Before/after census** (`tools/lender_census.py`, local only), over the 7,241 cached analyses. For each analysis it reports lenders gained and lost, flagged groups and the change in the withholding rate. Acceptance:
  1. Every gained lender traces to an admitted ledger entity.
  2. Every lost lender is a ruled move.
  3. The alias audit reports zero collisions.
  4. The owner's NMEF statement shows NMEF as a lender and Truist as a bank loan.
  5. No statement gains a lender from a generic word.
- **Speed:** the 300-row synthetic statement classifies at least 10× faster than today.

## 10. Services

The owner's standing rule applies: one Opus 5.5 agent per service, then an independent Opus reviewer, and the orchestrator checks every report's evidence before accepting it.

| # | Service | Owns | Starts after |
|---|---|---|---|
| S1 | Registry & matcher | §4.6, §5: compiled matcher, group registries from the ledger, alias fixes, collision audit, evidence ledger | this spec |
| S2 | Classifier & analysis payload | §4.1-4.5, §6, §7: states, rule order, credits, the potential tier, metrics/detection/serialization, cadence helper, versions, CLI, benchmark, docs, re-pins | S1 |
| S3 | Webapp serving, package & downloads | §8.1-8.4 | S2's payload contract (§6); may start against fixtures built from §6 |
| S4 | Dashboard | §8.5 | §6 and §8.2's `flag_shown` / `analysis_rules_outdated` |
| S5 | Re-analysis of saved statements | §8.6 plus its notice in the dashboard | S2 |

- **Order.** S1 runs first, then S2. S3, S4 and S5 run in parallel against the §6 contract, and each finishes once S2 lands.
- **Checks.** At the end the orchestrator runs the census, the alias audit, the targeted test selections and a browser check of the dashboard.
- **Merge and hosting.** The branch merges into `text-first-v1` after all reviews close. The Fly tryout is not updated unless the owner asks.

## 11. Out of scope

- Learning from analyst decisions (marking a potential lender as a lender, position or LOC in the app, remembered for future statements). This is the next project.
- Whether Affirm merchant payouts are revenue (D2).
- Revenue changes beyond financing proceeds.
- The text-first reader.
