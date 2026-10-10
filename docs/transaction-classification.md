# Transaction Classification Contract

`analysis.transaction_classifier.classify_statement_transactions` creates the
authoritative classification record for every parsed ledger row. The pipeline
creates this list once, then passes the same records to metrics, detection,
serialization, API responses, downloads, dashboard cards, filters, and evidence
tables. Consumers must use contribution flags on these records and must not scan
transaction descriptions independently.

Classification version 5.0 (2026-09-24) applies the owner's lender rulings in
`docs/superpowers/specs/2026-09-24-lender-detection-design.md` (decisions D1-D12).
Version 5.1 (2026-09-26) clarifies D6: a recurrence needs at least three
different dates, and D6 never takes a card-purchase posting.
Version 5.2 (2026-09-27) clarifies D6 again: D6 never takes a row whose words
name compensation, and a masked recipient account printed after `TO` is part
of the payee.
Version 5.3 (2026-09-27) is the false-potential-lender release: more D6 skips,
fee, NSF, cheque, card, payroll, mortgage and POS wording, admitted payees
printed in the bank's field order, unconfirmed flag payees routed to their flag,
D11 naming fixes, one Potential Lenders line per unnamed payee key, and the
Debt relief group.
Version 5.4 (2026-09-28) applies the owner's ruling that Idea Financial is a
counted lender, no longer a line of credit: its debits are `confirmed_lender`
rows, except a row whose own words say LOC or LINE OF CREDIT, which stays
`line_of_credit` (D9), and its credits stay financing proceeds (D1).

## States and precedence

Every row has exactly one state:

`confirmed_lender`, `potential_lender`, `insurance`, `alternative_position`,
`line_of_credit`, `vehicle_financing`, `bank_loan`, `mortgage`,
`lease_or_rental`, `personal_loan`, `floor_plan_financing`, `factoring`,
`debt_relief`, `fee`, `transfer`, `credit_card_payment`, `payroll`, `tax`,
`utility`, `rent`, `pos`, `atm`, `nsf_or_return`, `refund_or_reversal`, or
`other`.

`lease_or_equipment_financing` is retired: no rule produces it since version
5.0, but records stored before 5.0 carry it and still validate.

Only MCA and revenue-based funders and equipment financing are
`confirmed_lender`. Twelve groups are flagged instead. Their debits never enter
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
| `debt_relief` | `debt_relief` | Debt relief |

Premium financing is the one group that is not a state. Its rows stay
`insurance` and keep their insurance totals. The insurance rule sets
`flagged_group="premium_financing"` on a debit whose insurer is a
premium-finance payee (`PREMIUM_FINANCE_ALIASES`).

A flagged group's credits are another matter. A credit from a financing group
(every flagged group except credit cards, leases & rentals, premium financing,
factoring and debt relief) is financing proceeds, and D1 subtracts it from
eligible deposits as it does a lender's credit (see "Withholding rate"). Three
kinds of credit are not subtracted: a payout-credit entity's credits
(`PAYOUT_CREDIT_ENTITIES`), which are the holder's own sales; a premium-finance
payee's credits, which keep the insurance credit treatment; and a factoring
payee's credits (owner ruling 2026-09-26), which are the business's own sales,
paid by the factor that bought its invoices. A factoring credit takes the
operating-revenue path, as a payout credit does, and it is also flagged: its
state is `factoring`, its entity is the payee, and it counts in the Factoring
group as a credit. Since audit fix batch B6 (I10), a factoring review entity of
the ledger (`FACTORING_REVIEW_ENTITIES`, a factor not yet confirmed) is read
the same way on a credit, marked unconfirmed (`review_required`), where the
potential tier made it non-revenue; its debits keep the potential tier. A
factoring payee's credit is never verified, whichever rule read it. Debt-relief
payees (5.3) never apply to credits: their
credits are the debtor's own escrow refunds, and they follow the rules any
other credit follows.

The group list lives in `analysis/flag_groups.py`. A flagged row carries
`flagged_group`; a posted flagged debit, and a posted factoring credit, also
set `contributes_to_flagged_totals`. Proven duplicates, settlement-reversed
debits, a confirmed funder's payment returned unpaid (R2-OW13) and credits that
the reversal pass pairs clear it. The web app hides
unticked groups at serving time; the stored record never changes.

Every posted credit also has exactly one independent revenue state:

`verified_revenue`, `unverified_deposit`, or `non_revenue`.

This second state does not replace the transaction state. For example, a
returned e-transfer remains `refund_or_reversal` and is also `non_revenue`.
Revenue classification applies cancellations, reversals, financing proceeds,
and strong non-revenue exclusions before operating-income rules. Identifiable
card credits and refunds, purchase/payment/ACH returns, chargebacks, own-account
transfers, financing and insurance proceeds, tax refunds, card rewards and their
redemptions (`CASH REWARDS`, `CARD REWARDS`, `CASH BACK`, `CASH REDEMPTION` …),
fee refunds, the interest forms the strong rules name (`INTEREST PAID`,
`INTEREST CREDIT(ED)`, `INTEREST PAYMENT`, `INTEREST DEPOSIT`,
`INTEREST EARNED`, `CREDIT INTEREST`) and a `REIMBURSEMENT` the reversal rule
reads bypass manual revenue review as `non_revenue`. Since 5.6 the residual,
payer-less forms are not named non-revenue: a bare `INTEREST`,
`INTEREST RECEIVED` or `MONTHLY INTEREST`, a credit union's bare `DIVIDEND`, a
bare `REWARDS` and an entry code `REIMB…` are held as `non_sale_purpose` by the
true-revenue pass (spec §8.1, §18.2 item 7: out of True revenue, and
reviewable), and so is a wire or transfer whose purpose prints such a word (an
interest, dividend or investment-income purpose; audit I62). An employee's
expense reimbursement (`EXP REIMB`) is held as `payroll_or_salary`.
A maintained operating-source alias is supporting evidence, not sufficient
evidence by itself. Verification also requires credit direction plus
settlement, payout, merchant-deposit, or similar context; alternatively,
statement-level recurrence on a business account or related processing fees,
commissions, chargebacks, and adjustments can supply that context. Generic ACH,
wire, RTP and e-transfer credits, mobile/branch/ATM/night deposits,
checks, cash deposits, and unidentified credits are `unverified_deposit` until
reviewed; since 5.6 each is also counted in True revenue (`counted_flagged`) or
held for review (`excluded_pending_review`) by the tier rules below, and Q5 and
Q6 verify the named wires and ACH payers they admit. A Zelle credit is
`non_revenue` by the owner's Zelle policy of 2026-10-02 (`zelle_excluded`,
below) in the stored reading; the Settings choice "Mark Zelle Payments as True
Revenue" (the owner's amendment of 2026-10-06 to the underwriter's Q3, Yes by
default) shows the counted reading instead, in which a Zelle credit is read as
any person-to-person credit (below). Own-account transfers are
excluded when the description identifies the internal account or self-service
transfer channel.

### True revenue and the revenue tiers (classification 5.5 and 5.6)

True revenue is every posted credit except known non-revenue and the credits
held for review; Verified revenue is its part with positive proof
(`docs/superpowers/specs/2026-09-28-true-revenue-design.md`). Since 5.6 every
posted credit also carries exactly one revenue tier, stored beside its state:

| Tier | State | In True revenue |
|---|---|---|
| `verified` | `verified_revenue` | yes |
| `counted_flagged` | `unverified_deposit` | yes |
| `excluded_pending_review` | `unverified_deposit` | no |
| `non_revenue` | `non_revenue` | no |

A counted or held credit names its reason (`revenue_tier_reason`). The codes
and their labels live in one table, `analysis/revenue.py`
`REVENUE_TIER_REASONS`, which the dashboard mirrors. The table below repeats
it, in its order, and `tests/test_classification_contract_doc.py` fails when
the two differ (audit fix batch B12). A `verified` or `non_revenue` credit
carries no reason: its rule is its `revenue_match_method`. The exceptions are
the `non_revenue` codes the owner's rulings of 2026-10-02 decided
(`NON_REVENUE_REASONS`, the table's last rows): a Zelle deposit the owner's
Zelle policy excluded (the underwriter's Q3; in the stored reading, the No
choice since the owner's amendment of 2026-10-06), `non_revenue` with the reason
`zelle_excluded`, a government payment that prints no purpose (the
underwriter's Q12), `non_revenue` with the display reason
`government_no_purpose` (audit round 2, R2-OW03), and a non-dealer's sale of
equipment or vehicles (the underwriter's Q11 (b)), `non_revenue` with the reason
`asset_sale_proceeds` (R2-OW06). A reviewer's rejection keeps
the counted or held reason it had, which is none of them. The metrics count
these rows by code (`non_revenue_by_reason`, below). A held credit's reason
sentence (`revenue_reason`, which the JSON download and the package's evidence
sections write beside its tier) never says it is counted: a hold that re-tiers
a counted re-statement rewrites its "counted and flagged, never verified" as
"never verified, and held for review (<label>)", the held reason's own label
(audit round 3, R3-B15: R3-53).

| Reason code | Tier | Label | When (true revenue spec) |
|---|---|---|---|
| `direction_conflict` | `excluded_pending_review` | Direction conflicts with the amount | the printed direction disagrees with the amount; no pass lifts it (§6.1 step 2) |
| `insurer_payer` | `excluded_pending_review` | Insurance carrier | a listed insurer's credit with customer-payment wording (T14) that the underwriter's Q2 release (2026-10-02, R2-OW08) refuses: premium- or refund-coded, under $1, a direction conflict or claimed |
| `insurer_named_payer` | `excluded_pending_review` | Payer name reads as an insurer | an unlisted payer whose payer region, read without the holder's own names, prints an insurer's name word (`INSUR…`, `ASSURANCE`, `MUTUAL`, `CASUALTY`, `INDEMNITY`, `UNDERWRIT…`), or a `CLAIM` or `CLAIMS` word on a row that is neither an `HCCLAIMPMT` entry nor from a healthcare payer (T14, Q6, §8.1); audit I26 (by Q6 of 2026-09-28 and the underwriter's Q2 (2026-10-02) option's "a one-off claim … stays out"; R2-OW07): or any other insurer spelling, the abbreviation `INS`, the cut forms `ASSUR`, `MUTUA`, `CASUALT…` and `INDEMN…`, `ASSURANCES`, `ASSURANT`, `ASSUREUR`, `P AND C` at a name's end, `LOSS PMT`, `SUBRO…` and a Texas county mutual's `COUNTY MUT` (audit round 3, R3-B13: R3-11), or a carrier of `INSURER_CREDIT_BRANDS` that prints no insurer word (never `ASSURED`, `P AND C FOODS`, `CLM`, the given name `SUBROTO` or another word's `INS…`); a healthcare payer only by the spelled-out words, a §15 deferred payer only by those words or `CLAIM`, a government payer only by those words or `CLAIM` (R2-OW07 review round 1: never for work; R3-B13, R3-11: a listed insurer is read first, and `<WORD> COUNTY` before an insurer word is no government payer), a consumer person-to-person rail's sender (Zelle, Interac, e-Transfer, Venmo, Cash App, Apple Cash, Popmoney) only by the spelled-out words or `CLAIM` (R3-B13, R3-57: a push rail, a named transfer and an ACH entry worded `TRANSFER` read every spelling and brand, the cut `MUTUA` only beside a company form), never an `HCCLAIMPMT` entry, a premium financier or a listed insurer (the insurance rule's); a reading the underwriter's Q2 release counts as paid for the business's work is `insurer_paid_for_services` instead (owner ruling 2026-10-02, R2-OW08) |
| `possible_return` | `excluded_pending_review` | Possible return or adjustment | bare return or adjustment wording, a card credit no form verifies, or (audit round 3, R3-B09) a credit printing an outgoing e-Transfer label or a French fee adjustment (T3, §7.11, §8.1) |
| `financing_named_payer` | `excluded_pending_review` | Payer or entry suggests financing | a financing root on the payer's name or entry, a bank's own wire, a lending bank (T4, §8.1); the root arm alone is lifted for a finance-named customer paying an invoice, a leasing or property business's rent `LEASE` and a lender paying for services where no posted debit names the payer (owner ruling 2026-10-02, the underwriter's Q9: `finance_named_customer`, `lessor_rent`, `lender_paid_for_services`; R2-OW09) |
| `customer_financing_lump_sum` | `excluded_pending_review` | One-off lump sum from a lease-to-own or patient financier | a lease-to-own or patient financier's payout of $10,000 or more, by wire, in whole thousands or at least half the statement's posted credits, that is not one of three or more payouts of at least half its size from that financier (owner ruling 2026-10-02, Q8; §8.9) |
| `unread_run_names_financing` | `excluded_pending_review` | A lender is printed among this credit's unread payer blocks | a credit the parser marked unread whose run of welded payer blocks prints a registry lender's or a lending bank's block (§8.2, §8.10; audit round 2, R2-B07) |
| `payer_debited_as_lender` | `excluded_pending_review` | Payer is also debited as a lender | the statement debits the same payer as a lender (§8.1) |
| `holder_name` | `excluded_pending_review` | From the holder's own name or brand | the holder's own name, push or wire as the payer (Q4 to Q6, §5.2) |
| `payroll_or_salary` | `excluded_pending_review` | Payroll, salary or employee reimbursement | pay wording from another company, an earned-wage push (Q8) |
| `personal_income` | `excluded_pending_review` | Benefit or pension | a personal benefit or pension, a government benefit included (T3; GOV class B) |
| `non_sale_purpose` | `excluded_pending_review` | Not a sale: owner money, investment, grant, refund, claim or interest | owner money, investment, intercompany money, grants, legal settlements, gambling payouts, residual interest, dividends, rewards and reimbursements, and a posted credit under $1 that no non-revenue rule took (the $1 floor) (T3, §8.1) |
| `payer_also_debited` | `excluded_pending_review` | Payer also debited this account | a debit to the same payer that can be circular money: an own account, an affiliate, a funder that collects (§8.1, T3) |
| `wire_no_sender` | `excluded_pending_review` | Wire, no sender printed | a wire whose payer region names nobody (Q5); held still under the underwriter's Q1 (2026-10-02), its review item carries the funding aid (`revenue_funding_series`: the lender series that start after it) |
| `transfer_no_counterparty` | `excluded_pending_review` | Transfer, no counterparty | bare transfer wording (Q2) |
| `transfer_account_designation` | `excluded_pending_review` | Transfer naming an account | a named transfer that prints an account designation (T13, §6.3 narrowing 8) |
| `p2p_round_repeat` | `excluded_pending_review` | Repeated round sums from one sender | two or more whole $100 multiples from one person-to-person or transfer sender (Q4, T13) |
| `premium_trust_account` | `excluded_pending_review` | Deposit into a premium trust account | the account's printed title reads PREMIUM TRUST (statement account title, account name or holder name): every verified or counted credit, pass 7's step after the $1 floor (owner 2026-10-02, Q10) |
| `own_account_transfer_matched` | `excluded_pending_review` | Matches a transfer out of another account in this package | package-only: a counted deposit that prints no payer, matched to an exact-cents transfer out of another of the business's accounts 0 to 2 days earlier (`webapp/app.py` `_package_matches`, pass 2; owner 2026-10-02, Q4); never on a statement viewed alone |
| `wire_named_sender` | `counted_flagged` | Wire from a named sender | a named sender's wire Q5 does not verify (Q5) |
| `check_deposit` | `counted_flagged` | Check deposit | a mobile, remote, ATM or branch check deposit (Q3) |
| `no_payer_printed` | `counted_flagged` | No payer printed | a cash, branch, teller, ATM or bare deposit (Q2) |
| `payer_text_not_read` | `counted_flagged` | Payer text not read | the parser marked the credit's printed payer unread (§8.2, §8.10) |
| `p2p` | `counted_flagged` | Person-to-person | a person-to-person rail or a named transfer (Q4, T13) |
| `factoring_payout` | `counted_flagged` | Factoring payout | a factor's payout of the invoices it bought, never verified (§8.9) |
| `lender_paid_for_services` | `counted_flagged` | Lender paid for services | a listed auto lender's credit read on a payables word alone (`PAYABLES`, `TRADE PAY`, `ACCT FUND`) on a statement with no dealer evidence: a lender paying the business for its services (a repossession agency's recoveries), never verified; held as `financing_named_payer` when the lender also debits the account (owner ruling 2026-10-02, Q9 (c'); §8.7; the dealer evidence reads no card purchase at an auction, no floor-plan financier's service credit and no `FLOORPLANNER` or `FLOOR PLANKS`: audit round 3, R3-B14, R3-52); and (Q9 (c), R2-OW09) a payer whose own name reads as a lender's (a funding, lending, loan, capital, advance, credit or finance word) on a line that prints invoice, payables, vendor-payment or commission wording, which T4's financing root held, released where no posted debit names it; never verified (§8.1) |
| `construction_progress_draw` | `counted_flagged` | Builder's progress draw | a builder (a builder, homebuilder, construction or contractor name; never a builders' supplier, exchange or insurer) paying a `DRAW` that is no loan's, line's, escrow's or owner's draw, outside the payer's own name and never on a Zelle row in the stored reading (the counted reading of the owner's amendment of 2026-10-06 reads a builder's Zelle draw as any other's); every hold before it wins; never verified (owner ruling 2026-10-02, the underwriter's Q11 (a); §8.1, §8.10); the builder word read without the holder's names and, on a row that prints no payer-name field, never the entry's `CONST DRAW`, `CONSTRUCTION DRAW` or `BUILD DRAW`, with `DRAW` read only after it (audit round 3, R3-B15: R3-08) or in that entry phrase printed before it (its review round 1) when the phrase starts the payer region (its review round 2) |
| `insurer_paid_for_services` | `counted_flagged` | Insurer paid for the business's work | an insurer's credit (a listed insurer's, an insurer the payer region names however it is spelled, a carrier brand) that pays the business for its work, on the first of three grounds: the holder's name reads a repair shop, an insurance agency, a clinic or a pharmacy (a loose word, such as a bare `AGENCY`, `BROKER`, `HEALTH`, `VISION` or `TOWING`, only beside a second eligible insurer credit), the row prints a service form on its payer or purpose (`DRP`, `AGENTS EFT`, `AGTEFT`, `AGT COMM`, `AGENT COMP`, a commission word, `CONTINGENCY`, `REPAIR`, `VENDOR PMT`; never a wire's `REF`) or the classifier's customer-payment wording before its receiver fields (a wire's `REF` included, where Chase's book transfer and Santander print the purpose; never a bare `COMM`: audit round 3, R3-B13, R3-58), or one insurer pays three or more times within an inclusive 31-day span; never a premium, refund, return, dividend, cancellation, overpayment, member or personal-benefit credit unless a commission prints (R3-B13, R3-10: a disability benefit by any name, `STD`, a weekly or income benefit or `LTD` on the purpose, and death, survivor, surrender, cash-value, maturity or beneficiary wording everywhere; workers' compensation or a plain `BENEFIT(S)` wording except where the holder's first trade is a clinic or a pharmacy, a benefit word inside the carrier's name never read: R3-B13 review round 1), a claimed row, a title insurer or a government payer; every hold but the insurer-name hold still wins, and on a person-to-person row §8.4's round-sum repeat (`p2p_round_repeat`, R3-B13, R3-09); never verified and never a Q5 or Q6 repeat (owner ruling 2026-10-02, the underwriter's Q2; §8.1, §8.10) |
| `finance_named_customer` | `counted_flagged` | Customer with a finance word in its name, paying an invoice | a payer whose own name carries a financing root (`… FINANCIAL`, `ADVANCED …`), which T4 held, on a line that prints invoice, accounts-payable or vendor-payment wording or a commission (the orchestrator's extension under the underwriter's Q10), the root on the payer's name alone, no `PROCEEDS` or disbursement, no bank-only payer, and no posted debit naming the payer (the bank's receiving fee and a card purchase aside); on a layout with no entry label never two roots or a root after the payer's company form; never a payer-less row; every other financing arm and every later hold still win; never verified and never a Q5 or Q6 repeat (owner ruling 2026-10-02, the underwriter's Q9 (a); §8.1, §8.10; R2-OW09) |
| `lessor_rent` | `counted_flagged` | Rent received by a leasing or property business | a rent `LEASE` (never `LEASE FUND`, `LEASE FINANCING`, `LEASE PROCEEDS`, `LEASE BUYOUT`, `LEASE PURCHASE`, `LEASE TO OWN` or `LEASING`), which T4 held, the only root on the row (a payer place only as a memo after the payer's company form), on a statement whose business is in leasing or property (a trade word on the holder's names, a property-management platform's credit, or two or more distinct rent payers, whose rent words print outside the payer's own name; a payer-less transfer, person-to-person or wire row and an account designation never one: audit round 3, R3-B14, R3-60), no posted debit naming the payer; every other hold still wins; never verified and never a Q5 or Q6 repeat (owner ruling 2026-10-02, the underwriter's Q9 (b); §8.1, §8.10; R2-OW09) |
| `payout_credit_entity` | `counted_flagged` | BNPL or marketplace settlement (payer also lends) | a settlement from a platform that also finances the merchant (OQ2) |
| `customer_financing_payout` | `counted_flagged` | Lease-to-own or patient-financing payout | a lease-to-own or patient financier (`CUSTOMER_FINANCING_PAYERS`) paying the merchant for a customer's financed purchase, never verified (owner ruling 2026-10-02, Q8; §8.9); never a credit printing a non-sale or financing word (an advance, capital, interest, a dividend or a rebate: `_payout_non_sale`, the holds read it as any payer's row) nor a cut name of Katapult Engineering (`KATAPULT ENG…`) (audit round 3, R3-B14: R3-06, R3-54) |
| `platform_unconfirmed` | `counted_flagged` | Platform payout, not confirmed | a platform payout no form or recurrence confirms (§7.2, §6.3 narrowing 9) |
| `numbered_company_payer` | `counted_flagged` | Numbered company payer | a numbered company paying the holder, never verified (T11, OQ3) |
| `named_payer_purpose_refused` | `counted_flagged` | Named payer, purpose not accepted as proof | a named payer whose purpose words Q5 or Q6 refuse as proof, a §15 deferred source included (§18.2 item 2, §15) |
| `named_payer_one_off` | `counted_flagged` | One-off payer | an informal name that pays once (Q6) |
| `named_payer_unlabelled` | `counted_flagged` | Payer named, channel not printed | a payer printed with no channel label (§8.9) |
| `zelle_excluded` | `non_revenue` | Zelle deposit (excluded by policy) | excluded by the Zelle policy: a posted Zelle deposit (`ZELLE`, or PNC's `ZEL FROM`, before the receiver fields) the rules verified, counted or held, the rules' reading kept on the record; a Zelle credit another non-revenue rule decided keeps that rule and no reason (owner ruling 2026-10-02, the underwriter's Q3; §8.4, §8.10 step 26) |
| `government_no_purpose` | `non_revenue` | Government payment, no purpose printed | display only: a government payment that prints no purpose, which §6.1 step 3a made `non_revenue` (method `government_no_purpose_exclusion`, the seven forms of the underwriter's Q12 of 2026-10-02; a digit run glued before a letter-led form, a glued date, is read past: audit round 3, R3-B13, R3-55), carries this reason so the non-revenue breakdown names it; no tier, state, method or flag moves, and the row has no review path (R2-OW03; §5.3, §6.1 step 3a) |
| `asset_sale_proceeds` | `non_revenue` | Sale of equipment or vehicles (not a dealer) | on a statement that shows no dealer evidence, an equipment auction's or a car buyer's seller payout (`ASSET_SALE_PAYERS`) or a printed truck, trailer, vehicle or equipment sale, a vehicle's even when an invoice or customer-payment descriptor verified it: `non_revenue`, method `asset_sale_proceeds`, not held, with no review path (owner ruling 2026-10-02, the underwriter's Q11 (b); §8.1, §8.10); a sale printed net of a fee or a commission (a netting word beside it: `TRUCK SALE FEES WITHHELD`, `LESS COMMISSION TRUCK SALE`) is a sale, a bare commission or fee next to it, or a broker's `NET COMMISSION` (its review round 1), or a commission the netting phrase follows or the fees come out of (`COMMISSION LESS FEES ON TRUCK SALE`, `TRUCK SALE FEES WITHHELD FROM COMMISSION`; its review round 2), a broker's revenue (audit round 3, R3-B15: R3-59) |

**Precedence.** One credit's decision (`_classify_credit_revenue`) takes the
first match: a direction conflict, a reversal, a government payment that prints
no purpose (Q12, 2026-10-02), an auto lender paying a dealer, an insurer, the
financing-proceeds rules, the strong non-revenue rules and own-account
transfers, the channel gate, the operating registry, the
card-settlement forms, the verified descriptors (the holder's own name never
verifies), customer and invoice wording, payer accounts-payable remittance,
public payers, wire remittance, then the fallback. The statement passes then run
in order (the full list is under "Statement passes run in this order" below):
duplicates, the lender recurrence and the labels for unnamed potential payees
(debits), reversal pairs, the operating-source recurrence pass (pooled operating
sources verify by recurrence; the pool never shrinks and a veto word keeps a
row out) with the auction and property branches, the payer-remittance
counter-debit guard (pass 6), and the true-revenue pass (pass 7,
`analysis/true_revenue.py`), which tiers every posted credit, then the funding
aid, before duplicate finalisation. Between pass 7 and the duplicate
finalisation the returned funder payments pass (pass 7b, R2-OW13) and the
re-presented returned payments pass (pass 7c, audit round 3, R3-B02: the
owner's answer of 2026-10-07 to R3-73) read the lender side only. A
`non_revenue` credit stays `non_revenue` except where a rule narrows a
non-revenue pattern (spec §6.3); a held credit enters True revenue only when an
analyst confirms it, and a credit that returns a confirmed funder's payment
(`returns_funder_payment`) never does: its Confirm is refused (audit round 3,
R3-B02: R3-21).

**Holds.** The true-revenue pass holds a credit (tier
`excluded_pending_review`) in this order: insurer payer, insurer-named payer,
possible return, financing-named payer, payer debited as a lender, the holder's
own name, payroll or salary, personal income, a non-sale purpose, a payer also
debited this account; then by channel: a wire with no sender, a transfer with no
counterparty or naming an account, and repeated round person-to-person sums.
Before the holds, an insurer's credit paid for the business's work (owner
ruling 2026-10-02, the underwriter's Q2: the holder's name reads a repair shop,
an insurance agency, a clinic or a pharmacy, the row prints a service form, or
one insurer pays three or more times within 31 days) is re-stated as an
unverified deposit of method `insurer_paid_for_services`, unclaimed: the
insurer-name hold passes over it, every later hold still reads it, and it is
counted as `insurer_paid_for_services`, never verified and never a Q5 or Q6
repeat; another insurer's one-off in the same statement counts only with the
owner's switch `INSURER_FOR_WORK_STATEMENT_ARM`, which is off.
A lease-to-own or patient financier's merchant payout (owner ruling 2026-10-02,
Q8: `CUSTOMER_FINANCING_PAYERS`) is claimed as a payout entity's credit is,
counted as `customer_financing_payout` and never verified; after the tiers and
before the Zelle step, a large one-off lump sum among those payouts is held as
`customer_financing_lump_sum`. Neither a financier nor a payout entity claims a
credit printing a non-sale or financing word (an advance, capital, interest, a
dividend or a rebate, read without the receiver's value and the holder's
names): the holds read it as any payer's row, and a Cherry loan or advance
keeps D1 (audit round 3, R3-B14: R3-06).
A listed auto lender's credit Q7 verified on a payables word alone, on a
statement that shows no dealer evidence (owner ruling 2026-10-02, the
underwriter's Q9 (c')), leaves Verified after the factoring, own-push and
financier demotions: counted as `lender_paid_for_services`, or held as
`financing_named_payer` when the lender also debits the account (the
hidden-loan guard); its lender fields and every debit are unchanged. A card
purchase at an auction's town, a floor-plan financier's service credit and a
`FLOORPLANNER` or `FLOOR PLANKS` row are no dealer evidence (audit round 3,
R3-B14: R3-52).
The underwriter's Q9 (owner ruling 2026-10-02, "Keep them as true revenue";
R2-OW09) lifts the financing-named hold's root arm alone, in the payer facts,
on an unverified credit nothing claimed: a customer whose own name carries a
finance word paying on a line that prints invoice, payables, vendor-payment or
commission wording (`finance_named_customer`, or `lender_paid_for_services`
when the name reads as a lender's), and a rent `LEASE` received by a business in
leasing or property (`lessor_rent`, read beside the business shape); never a
line printing `PROCEEDS` or a disbursement, a bank-only payer or a payer the
statement debits (the hidden-loan guard). Every other financing arm and every
later hold still read the row; where the tiers count it, the release's reason
replaces the counted one last (the specific counted reasons and
`payer_text_not_read` are kept), never verified and never a Q5 or Q6 repeat.
A builder's progress draw (owner ruling 2026-10-02, the underwriter's Q11 (a):
a builder, homebuilder, construction or contractor payer that is no realty
firm, a `DRAW` that is no loan's, line's, escrow's, owner's or commission draw,
outside the payer's own name, never on a Zelle row in the stored reading) is counted as
`construction_progress_draw` right after the factoring and financier payouts,
never verified (one an earlier rule verified, §7.5's accounts-payable
remittance, is counted after the asset-sale demotion; R2-OW06 review round 1);
every hold before it wins, and on such a row the non-sale test spares `DRAW`
alone (audit round 3, R3-B15: R3-08: the builder word is read without the
holder's names, and on a row that prints no payer-name field the entry's
`CONST DRAW`, `CONSTRUCTION DRAW` or `BUILD DRAW` is no builder word and `DRAW`
is read only after the builder word or in that entry phrase printed before it,
its review round 1, when the phrase starts the payer region, its review round
2). On a statement that shows no dealer evidence, a
non-dealer's sale of equipment or vehicles (the underwriter's Q11 (b): an
equipment auction's or a
car buyer's seller payout, a printed truck, trailer, vehicle or equipment sale,
never with a commission or a fee next to it, unless a netting word stands
beside it (audit round 3, R3-B15: R3-59) that follows no commission word and
takes no fees from a commission (its review round 2), and never a bare
`FLEET SALE`) is
`non_revenue` with the reason `asset_sale_proceeds`, where the tier would count
it, where IAA's insurer-name hold alone holds it and no later hold would, or
where an invoice or customer-payment descriptor verified a vehicle's sale (after
the payables demotion); every other hold keeps it held.
After the tiers and before the $1 floor, the pass excludes every Zelle deposit
the tiers verified, counted or held (owner ruling 2026-10-02, the underwriter's
Q3): `non_revenue` with the reason `zelle_excluded`, the rules' own tier and
reason kept in its reason and its `zelle_prior:` context signal; a Zelle credit
a non-revenue rule decided keeps that rule, and a direction conflict keeps its
hold. That step runs in the stored reading only: the counted reading (the
owner's amendment of 2026-10-06 to the underwriter's Q3, R2-OW17;
`apply_true_revenue_pass(..., zelle_true_revenue=True)`) skips it, so each Zelle
credit keeps the rules' own reading of a person-to-person credit, and lifts two
Q3-era carve-outs (a builder's Zelle draw is a progress draw, a Zelle truck or
equipment sale is asset-sale proceeds); the lessor fact keeps its Zelle skip in
both readings, and the floor, the premium-trust hold and pass 7b read the
counted tiers. `classify_statement_readings` gives both readings at once (the
shared prefix once, pass 7 to the duplicate finalisation once per reading);
every caller that names no reading gets the stored one. The $1 floor is absolute: a posted credit under $1 is never verified and never
counted, whichever rule read it, and is held as `non_sale_purpose`.
Last, on a statement whose account title reads PREMIUM TRUST, every verified or
counted credit is held as `premium_trust_account` (owner, 2026-10-02, Q10); a
held credit keeps its first hold and a non-revenue one stays non-revenue. The
title is read on the statement's printed title, its account name and its
holder's name (`premium_trust_title`: the title at the field's end, the title
followed by an account word, or the title and an account or product word before
a separator), never on a row's payer; a verified credit so held leaves
verification (method `premium_trust_account`).
Then, as the pass's last step (owner ruling 2026-10-02, the underwriter's Q1:
"look at the day $ amount got deposited and see if there is a frequent payment
following the deposit"), each held wire with no sender printed
(`wire_no_sender`) carries the record field `revenue_funding_series`, a tuple
of `FundingSeries`: every Lenders or Potential Lenders series (one tab name,
the potential payee label or the canonical entity, and one amount to the cent;
posted, not a duplicate, counting toward the lender or potential-lender count;
since audit round 3, R3-B02 (R3-66), a series with an attempt, paid or
settlement-reversed, dated on or before the deposit's day is none)
whose every payment is dated after the deposit's day, the first at most 10 days
after it, on two or more dates `_promotion_cadence` reads daily or weekly, with
whether the statement shows one full gap of the series, at least 3 days, before
the deposit (`start_observed`). It is a review aid: every other record carries
`()`, and no tier, reason, flag, figure, gate or lender reading moves.
Every other unverified credit is counted (`counted_flagged`) with its reason. A
statement needs revenue review (`revenue_review_required`) when it has an
undecided direction conflict (one an analyst confirmed or rejected no longer
gates), when its held credits are ten percent or more of its posted
credits (compared in integer cents, `REVENUE_REVIEW_HELD_SHARE`), when they are
ten percent or more of True revenue plus held and at least $500
(`REVENUE_REVIEW_HELD_FLOOR`; audit B11: an advance is sized on True, so heavy
non-revenue no longer dilutes the share, and a $0-True statement never gates on
held cents), or when its four tiers do not sum to its posted credits
(`revenue_tiers_sum_to_posted`; `revenue_reconciles` is its deprecated alias,
and neither is a reconciliation against the bank's figures, which is
`reconciliation.ok`).

**Extending the tables.** Every table below is checked by
`python tools/operating_registry.py --check` and by its tests. So are the other
5.6 tables of `analysis/classification_registry.py`: a factoring payer
(`FACTORING_PAYOUT_PAYERS`) collides with no ledger, operating or insurer alias;
the owner-money and deferred-source patterns (`OWNER_MONEY_PLATFORMS`,
`SECTION_15_DEFERRED_PAYERS`) compile and read no operating alias; and the
sending banks' and statement banks' printed names (`P2P_SENDING_BANK_NAMES`,
`STATEMENT_BANK_PRINTED_NAMES`) are normalized and name no form twice; and (audit
round 3, R3-B08) the own bank's sending spellings (`OWN_BANK_SENDING_SPELLINGS`)
are normalized, name no spelling twice, and every spelling is a listed sending
bank's name.
- `OPERATING_REVENUE_SOURCE_ALIASES` and `OPERATING_REVENUE_SOURCE_TYPES`
  (`analysis/classification_registry.py`): a processor, marketplace or platform
  that pays a business its own sales. An alias is the name as banks print it, in
  upper case. A name a bank cuts at 16 characters goes in
  `OPERATING_REVENUE_TRUNCATIONS`, never as a bare prefix another entity could
  share. A source whose aliases also name its capital product goes in
  `OPERATING_SOURCES_READ_WITH_VETOES`, and the capital product in
  `PROCESSOR_ADVANCE_PRODUCTS`.
- `OPERATING_SOURCE_PAYOUT_FORMS` and `CARD_SETTLEMENT_CREDIT_FORMS`: a printed
  payout or settlement shape that verifies on its own. Each form is a whole-row
  pattern with its refusal words; add a positive and a negative test in the
  bank's format.
- `HEALTHCARE_PAYER_ALIASES`: a claims payer (a Medicare contractor, Medicaid,
  a large insurer or its payment network) whose claim payments are a practice's
  revenue.
- `DEALER_FUNDING_PAYERS`: an auto lender whose funding of a dealer's contract
  is the dealer's sale. A credit union's vehicle-purchase entry (`VHCL PURCH`)
  verifies as dealer funding (`auto_lender_dealer_funding`) when the statement
  prints two or more of them; a lone one is held as `financing_named_payer`.
  A listed lender's credit read on a payables word alone (`PAYABLES`,
  `TRADE PAY`, `ACCT FUND`) verifies only on a statement with dealer evidence
  (a dealer-worded Q7 credit or the credit-union arm, a floor-plan financier's
  debit or its credit printing no service wording, or `FLOOR PLAN` by the form's
  own words, a purchase at a dealer-only auction that is no card purchase, a
  dealer word in the holder's name that prints no `RECOVERY`, `REPO`,
  `REPOSSESS`, `TOWING` or `COLLATERAL`; the arms narrowed by audit round 3,
  R3-B14: R3-52); otherwise it is counted as `lender_paid_for_services`, never
  verified (owner ruling 2026-10-02, the underwriter's Q9 (c')).
- `PAYOUT_CREDIT_ENTITIES`: a platform whose payout is the business's sales but
  whose name is also its financing partner (buy-now-pay-later settlements
  included since 2026-09-28); its credits are counted, never verified.

#### Review decisions (2026-09-29)

- A date glued to a row never changes its reading (spec §7.0).
- The holder's own name (a receiver field, an incoming wire's beneficiary) never names a payer or a source (§5.2).
- An own-account transfer leaves `non_revenue` only on a distinctive payer word; account adjectives stay own-account (§6.1 step 9, §7.11).
- The wire vetoes also read a wire glued to its reference and a wire that cites an invoice (§7.9).
- The recurrence veto's holder-word exemption reads only on store-name platforms (§7.0).
- Statement pass 6, the counter-debit guard, reads a debit's first distinctive word, never a card purchase's city; since the final review it leaves a card purchase out, unless the classifier names it as a lender (§7.5).
- The true-revenue pass's `payer_also_debited` hold never reads a card purchase: buying at a merchant that shares the payer's word is spending, not the payer's money coming back (§8.1; A1 census, 2026-09-30). A card-form debit the classifier names as a lender still counts for `payer_debited_as_lender`.
- A buy-now-pay-later consumer credit (a return, withdrawal, refund or card credit) keeps its 5.4 reading; the OQ2 ruling covers settlements only (§19).
- A direction conflict is never lifted, grouped or counted by any pass (§6.1 step 2, §7.0).
- A bare transfer is held as `transfer_no_counterparty` (§8.2).
- The $1 floor is absolute: a posted credit under $1 is never verified and never counted, whichever rule read it, and never counts toward a repeat. It is held as `non_sale_purpose` (the reason table has no micro-deposit code); one a rule verified is held by the true-revenue pass's last step (method `micro_deposit_floor`), a credit already held keeps its first hold, and a non-revenue credit stays non-revenue (§7.0, §7.8, §8.10). Every pass-7 demotion leaves such a credit to the floor, the factoring and progress-draw demotions included (audit round 3, R3-B15: R3-63).
- Owner money, a brokerage, investing or crypto-exchange platform's credit included, is held as `non_sale_purpose` (§7.5, §8.1).
- A deferred source stays counted and flagged, never verified by Q5 or Q6 (§15, §19 OQ4).
- Repeated round sums from one sender are held as `p2p_round_repeat`, a named transfer printed without FROM included (§8.4).
- In the stored reading every Zelle deposit is `non_revenue` (`zelle_excluded`), whoever sent it, a lender or processor paying through Zelle included: the pass's last tier step, before the $1 floor, keeps the rules' reading on the record (`zelle_prior_reading`); a row a non-revenue rule decided keeps that rule, and a direction conflict keeps its hold (owner ruling 2026-10-02, the underwriter's Q3; §8.4, §8.10).
- The Settings choice "Mark Zelle Payments as True Revenue" (the owner's amendment of 2026-10-06 to the underwriter's Q3, Yes by default; R2-OW17) shows the counted reading, which the analysis computes beside the stored one: every Zelle deposit keeps the rules' own reading of a person-to-person credit (counted and flagged `p2p`, never Verified, or held: the holder's own name, one sender's repeated round sums, a payer also debited and the other holds), a builder's Zelle draw is `construction_progress_draw` and a Zelle truck or equipment sale `asset_sale_proceeds`; the lessor fact keeps its Zelle skip, so the choice moves Zelle rows only. No shows the stored reading above. The choice is a display setting: every saved analysis, the review, the package, the exports and the withholding rate follow it at once, and the stored record is never rewritten (true revenue spec §8.4, §9.1, §10.7).
- A builder's progress draw is counted and flagged as `construction_progress_draw`, never verified and never a Q5 or Q6 repeat: the payer region names a builder (`BUILDER(S)`, `BUILD`, `HOMEBUILDER(S)`, `CONSTRUCTION`, `CONST`, `CONSTR`, `CONTRACTOR(S)`, `CONTRACTING`, a homebuilder's `HOMES`; never `BUILDING`, a builders' supplier, exchange or insurer, a nursing or mobile home), `DRAW` prints outside the payer's own name, no loan, line, escrow, title, owner's, equity or commission draw or `DRAW ON` a line, no bank, title, owner-shaped, financing-root or realty payer, no Zelle rail in the stored reading (the counted reading of the owner's amendment of 2026-10-06 reads a Zelle draw as any other's); the lender, own-loan and holder guards run first and every other hold wins; a draw §7.5's accounts-payable remittance verified is counted, never verified (R2-OW06 review round 1). A developer's or a project LLC's draw stays held (owner ruling 2026-10-02, the underwriter's Q11 (a); §8.1, §17.1), and so does a county's (audit round 3, R3-B15: R3-08). The builder word is read without the holder's names; on a row that prints no payer-name field (the label-less layouts) the entry's `CONST DRAW` or `CONSTRUCTION DRAW` is no builder word and a `DRAW` printed before the builder word is inside the payer's name (R3-08); since its review round 1 `BUILD DRAW` is such an entry phrase too, and the entry phrase's own `DRAW` printed before the builder word is read (Truist's entry-first `CONST DRAW <NAME> BUILDERS INC …` counts); since its review round 2 only a phrase that starts the payer region is read, so a root-less payer's `<NAME> CONST DRAW` before a later builder word (`SAMPLE COUNTY CONST DRAW BUILDER PMT`) keeps its hold.
- A non-dealer's sale of equipment or vehicles is `non_revenue` (`asset_sale_proceeds`), not held, with no review path: an equipment auction's or a car buyer's seller payout (`ASSET_SALE_PAYERS`, read as the whole payer name; Copart and IAA only beside a seller word; never Proxibid) or a printed `<asset> SALE`, `SALE OF <asset>`, `SOLD <asset>` purpose (a vehicle's sale read through an invoice reference; a generic equipment sale keeping its invoice, vendor and supplier spares; never a commission or a fee next to the sale (a broker's `NET COMMISSION ON TRUCK SALE` included: a bare `NET` reads only before `FEES`, R3-B15's review round 1; and a commission the netting phrase follows or the fees come out of, `COMMISSION LESS FEES ON TRUCK SALE` or `TRUCK SALE FEES WITHHELD FROM COMMISSION`, R3-B15's review round 2), nor a bare `FLEET`; R2-OW06 review round 1; a commission or a fee a netting word stands beside is what the sale is net of, so `TRUCK SALE FEES WITHHELD` and `LESS COMMISSION TRUCK SALE` are a sale, audit round 3, R3-B15: R3-59), on a statement with no dealer evidence: no Q7 dealer funding that is not payables-only, no §7.8 auction payout credit or dealer-only auction purchase, no floor-plan row, and no vehicle or equipment trade name on the holder's names that prints no recovery or towing word (owner ruling 2026-10-02, the underwriter's Q11 (b); §8.1, §8.10, §17.1).
- An insurer's credit paid for the business's work is counted and flagged as `insurer_paid_for_services`, never verified and never a Q5 or Q6 repeat (owner ruling 2026-10-02, the underwriter's Q2, the spec's §19.1 line "insurers paying for the business's work"): on the holder's trade (a repair shop, an insurance agency, a clinic or a pharmacy; a loose word only beside a second eligible insurer credit), a service form (`DRP`, an agent's EFT, a commission, `CONTINGENCY`, `REPAIR`, `VENDOR PMT`; never a wire's `REF`, though the classifier's customer-payment wording, the ground's other reader, reads a wire's `REF`, where Chase's book transfer and Santander print the purpose: audit round 3, R3-B13, R3-58) or three or more credits from one insurer within an inclusive 31-day span; another insurer's one-off in the same statement only with the owner's switch, off. A personal benefit's wording is never paid for work: a disability benefit by any name, death, survivor, surrender, cash-value or maturity money, and workers' compensation or a plain benefit wording except at a clinic or a pharmacy (R3-B13, R3-10; its review round 1: the holder's first trade, and a benefit word inside the carrier's name, `MUTUAL BENEFIT INS CO`, is no benefit wording). On a person-to-person row one insurer's repeated round sums are held as any sender's (`p2p_round_repeat`, R3-B13, R3-09). A one-off claim on the business's own policy stays out however the insurer is spelled (the spec's separate §19.1 line "every insurer spelling", by Q6 of 2026-09-28 and audit I26): a listed insurer's credit stays `non_revenue`, any other is held as `insurer_named_payer`. `HCCLAIMPMT`, healthcare payers and the §15 deferred carriers read as before (§8.1).
- T4's financing root no longer holds three kinds of row (owner ruling 2026-10-02, the underwriter's Q9, "Keep them as true revenue"; the spec's §19.1 line "finance-named customers, rent received and lenders paying for services"): (a) a customer whose own name carries a finance word, on a line printing invoice, accounts-payable, vendor-payment or commission wording, counted as `finance_named_customer`; (c) the same where the name reads as a lender's (`lender_paid_for_services`, a label only); (b) a rent `LEASE` received by a business in leasing or property, counted as `lessor_rent`. Each is never verified and never a Q5 or Q6 repeat, and stays held as `financing_named_payer` when any posted debit names the payer (the hidden-loan guard, a documented over-hold; the bank's receiving fee and a card purchase aside). Only the root arm is lifted, read by place (the payer's name alone for (a) and (c)); a payer-less row, a `PROCEEDS` or disbursement line, a bank-only payer, and on a layout with no entry label two roots or a root after the payer's company form stay held; a registered lender's vendor-worded credit stays D1's financing proceeds (§8.1, §8.10, §17.1).
- Owner ruling 2026-10-02 (Q10): a premium trust account's verified or counted deposits are held as `premium_trust_account` (pass 7's step after the $1 floor); held and non-revenue rows keep their reading. The agency's operating, producer-payable, wire and other accounts read as before, and a payer that prints the words never makes a title (§8.10, §19.1).
- Owner ruling 2026-10-02 (Q1): every wire with no sender printed stays held as `wire_no_sender`; pass 7's last step records on it the Lenders or Potential Lenders series that start after it (`revenue_funding_series`, the review item's "possible funding" line), a review aid that moves no tier, figure or lender row (§8.5, §10.7, §19.1).
- Q5 and Q6 leave a row the operating registry names, and a NET SETTLE row, to its own rule (§7.1, §8.5, §8.6).
- VIREMENT is a person-to-person rail only in its Interac forms (§8.4).
- A cancelled French transfer is a reversal (§6.1 step 3).
- Quebec's numbered companies (`NNNN-NNNN`) are numbered-company payers: counted, never verified (§5.2, T11).
- Q7 honours the wording holds of §8.1 (never the holder's name: the lender is read without the receiver field), keeps its lender's name, and Suncoast Credit Union verifies only through its credit-union arm (§8.7). Since the owner's ruling of 2026-10-02 (the underwriter's Q9 (c')), a listed lender's payables-only credit stays Verified only on a statement with dealer evidence; otherwise the true-revenue pass counts it as `lender_paid_for_services`, or holds it as `financing_named_payer` when the lender also debits the account (§8.7). A listed lender's other credits stay D1's financing proceeds, its invoice- or vendor-worded ones included (a question for the owner, the spec's §17.1; R2-OW09).
- A3 fix (precision sample, 2026-09-30): a wire's channel and layout words (`INCOMING`, `FEDWIRE`, `FED WIRE`, `WIRE`, `TRANSFER`, `CREDIT`, `CHIPS`, `SWIFT`, `BOOK` …) never name a transfer's counterparty, and a transfer that prints wire wording and names no counterparty (`INCOMING FEDWIRE TRANSFER`) is a wire with no sender, held as `wire_no_sender` (Q5, §8.5).
- A3 fix: the SBA's name cut to an originator field (a payer region that is exactly `SMALL BUSINESS`, or `SMALL BUSINESS` and a leading cut of `ADMINISTRATION`) is an SBA disbursement, financing proceeds (`sba_disbursement_credit`, §7.11); a payer whose name goes on in other words (`SMALL BUSINESS SOLUTIONS LLC`) and a transfer from an account so named stay as they were.
- A3 fix: foreign-exchange and currency-conversion wording (`FOREIGN EXCHANGE`, `FX CONVERSION`, `CURRENCY EXCHANGE`, `CURRENCY CONVERSION`, `CONVERSION DE DEVISES`, `CHANGE DE DEVISES` …) never names a counterparty, and a credit that prints it and names no other payer is the holder's own money converted, held as `non_sale_purpose` (§8.1's own-money group, as a sweep is; it designates no account, so it is no T13 named transfer). A named payer that prints it keeps its reading. A3 review: the statement's own bank printing its name right before the wording names no payer (its whole name, and the short forms of `STATEMENT_BANK_PRINTED_NAMES` when the bank field contains one of the entry's bank words: `ROYAL`, `RBC`, `ROYAL BANK`, `RBC ROYAL BANK` on a statement whose bank field contains `ROYAL BANK OF CANADA`, `RBC ROYAL BANK`, the whole word `RBC` or `BANQUE ROYALE`; a bare `ROYAL BANK`, as in the Royal Bank of Scotland's name, is no marker), so `ROYAL FOREIGN EXCHANGE DEPOSIT` there is held. A named currency-exchange company is a payer: another name word beside the wording (neither a legal form nor an article) names it on any row, and a company form beside the wording (`LLC`, `INC`, `CORP`, `CO`, `LTD`, `INTERNATIONAL`, `INTL`) names it only on an originator field (an ACH originator, or a wire's labelled sender: `CURRENCY EXCHANGE INTERNATIONAL DES:PAYMENT`); elsewhere it names nobody (`INTL FOREIGN EXCHANGE DEPOSIT`, `FX CONVERSION LLC <n>` and BMO's `INCOMING WIRE PAYMENT … CA FOREIGN EXCHANGE LTD` stay held).
- A3 fix: a title firm named on the payer region (the whole word `TITLE` beside `AGENCY`, `CO`, `COMPANY`, `TRUST`, `INSURANCE`, `GUARANTY`, `SERVICES`, `ESCROW`, `CLOSING` or a legal form, or a national title insurer such as Chicago Title, First American Title, Fidelity National Title, Old Republic Title or Stewart Title) pays out property-closing proceeds, an asset sale: held as `non_sale_purpose` on wires and ACH alike, never verified by Q5 or Q6. `TITLEIST` and `TITLE BOXING CLUB` are no title firm. A title firm's credit whose purpose (a wire's OBI, RMR, PMT DET, RFB or URI field; an ACH entry; a transfer's memo) cites the holder's fee paid at closing (`COMMISSION`, `COMM`, `ORIGINATION`, `ORIG FEE`, `BROKER`, `INVOICE`, `INV`, `CONSULT…`, `FEE FOR SERVICES`, `SERVICES RENDERED`) is not held by it and takes its normal reading (orchestrator ruling). A3 review: a wire's REF field is never read for it: on the Fedwire layout it is the sender's bank reference (`REF COMM BANK NYC` exempts nothing), and Bank of America's `SERVICE REF` is its own reference; a URI printed inside REF (a book transfer's) is read, and so is Santander's REF field, which is its purpose (`ACCT <n> <originator> REF <purpose>`). `ORIG FEE` inside a purpose field is purpose wording, never an originator label.
- A3 fix: a wire that prints its sender right after its label, with no originator label, names that sender (§5.2): BMO's `INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT <country> <sender>`, `INCOMING WIRE <reference> <sender> NOTPROVIDED`, TD Bank's `WIRE TRANSFER INCOMING <sender>`, Wilson & Muir's `WIRE TRANSFER FROM <sender>`, Capital One's `WIRE TRANSFER DEPOSIT <sender> <reference>`, Scotiabank's `INCOMING WIRE TRANSFER <sender> WIRE PAYMENT` and SECU's `DOMESTIC WIRE DEPOSIT WIRE IN <sender>`; such a wire is no longer held as `wire_no_sender` when its sender prints a name word, and takes its normal reading (Q5). Audit round 3, R3-B07 (R3-42): and `INBOUND WIRE|FEDWIRE [TRANSFER FROM] <sender>`, `INCOMING FEDWIRE [TRANSFER FROM] <sender>`, `INCOMING WIRE TRANSFER FROM <sender>`, `INCOMING CHIPS <sender>` and `WIRE TRANSFER[S] CREDIT <sender>`; a listed sending bank's or the statement's own bank's channel name read there names no sender (R3-40: nor does a region of only label, holder-noise, account-designation, purpose, filler or legal-form words, on any wire layout). A sender whose only words after the label are a reference token and a legal form (`WIRE TRANSFER INCOMING 1ABC LLC`) names nobody, as the person-to-person reader rules: that wire stays `wire_no_sender`, which keeps census guard G4 green. A wire sender's name that a line wrap splits is read across the split for the financing roots too (`F INANCIAL`, `SERVICIN G`), on every wire sender, labelled (`B/O`, `ORIG` …) or read after the label; A3 review round 3: a join counts only when its two words together spell a financing word (`FINANCIAL`, `FUNDING`, `SERVICING`, `CAPITAL`, `LENDING`, `MORTGAGE`, `LOAN` and the other T4 roots spelled out) or a prefix of one of five letters or more, so two words that spell none never make one (`SERVICE REPAIR` is no `SERVICER`, `SOLO ANALYTICS` no `LOAN`, `ALLEN D` no `LEND`, `CAPT L` no `CAPTL`); A3-G review: a Fedwire or CHIPS sender's city and state after `B/O` are no longer skipped; they join only as any two words do, so `LAMORT GA` and `GLEN DE` spell no financing word and stay counted, while `B O NORTHWIND F INANCIAL CO` is held.
- A3 review: a payer whose name ends in a glued `CRED` (`FABRICRED INC`, a credit provider's glued name) is held as `financing_named_payer`, as §7.9's word-end `CRED` arm reads it. A3 review round 2: it is read on the payer's name only (a wire's sender, an ACH originator, a transfer's sender after `FROM`, and, round 3, a payer region that prints a company form: `ACH CREDIT FABRICRED LLC`), never on an entry field (`DES:ACCTCRED`) or a row whose payer words are neither (`ACHCRED 12345678`); the whole word `CRED` and the whole words `SACRED` and `ACCRED` are no root, and any other glued `…CRED` name is (§8.1, T4).
- A3-G (the redrawn largest-counted stratum, 2026-09-30): the Canada Revenue Agency's income-tax refund (`CANADA RIT`, `CANADA RIF`, `DIRECT DEPOSIT CANADA RIT RIF`) is a tax refund, `non_revenue` (§7.11 T5), when the form starts the payer (after DIRECT DEPOSIT, DEP, EFT or PAY; A3-G review; A3-G re-review: read after the classifier's revenue text and template prefixes, so a glued or spaced date, `GC`, `MISC PAYMENT`, `PAYMENT FROM`, `PREAUTHORIZED CREDIT` or `ELECTRONIC DEPOSIT FROM` may come before it, while `FABRIKAM LIFE CANADA RIF PMT` names its payer); the CRA's benefit, credit and payment forms (`CANADA GST TPS`, `GST CANADA`, the child and other benefits) were left for the owner, who ruled on them on 2026-09-30 (GOV, below).
- A3-G: a wire whose originator field reads as a bank (`BANK`, `BANCORP`, `BANK N A`, `CREDIT UNION`, `SAVINGS BANK`, `FEDERAL SAVINGS`, or Bank of America's sending bank itself) is held as `financing_named_payer`; only the originator field is read, and a bank's merchant-services, bankcard, processor or settlement form is a settlement, never held so; A3-G review: never a food or blood bank or a company whose name holds BANK (a company form counts only as the bank's own, right after its bank word), and the sending-bank arm needs eight letters and an originator with no company form (§8.1, T4); A3-G re-review: a form word that is the address's state is never a company form, so `B/O NORTHWIND BANK DENVER CO 80202 US` is a bank and a Fedwire `B/O SAMPLE CREDIT UNION BOULDER CO` a credit union; A3-G re-review 2: `CO` or `NV` is the state only when a ZIP or the country code (`US`, `USA`) follows it, or when it ends a Fedwire or CHIPS `B/O` field's city and state; at the end of any other field (Bank of America's `ORIG`, Chase's book-transfer `B O`) it is a company form, so `ORIG:LEFT BANK TRADING CO`, `B O WEST BANK OIL CO REF …` and `ORIG:BANK STREET HOLDINGS NV` are companies, and `ORIG:NORTHWIND SUPPLY CO` is never its sending bank `NORTHWIND SUPPLY`. A3-G refinement: a bank that names the ultimate originator after a relay label (`ORG`, `B/O`, `ORIGINATOR`, `ORIG CUST`, `BY ORDER OF`; never `ORIGINATOR TO BENEFICIARY` or `ORG TO BNF`) only relays, and that customer is the wire's sender, read normally. A3-G re-review: the wire's originator label takes the same guards (`… NORTHWIND SUPPLY LLC ORG TO BNF INFO 1234` reads `NORTHWIND SUPPLY LLC`). Audit round 3, R3-B07 (R3-14): `BANKING` reads as a bank word under the same company-form rule (`WESTPAC BANKING CORP` is a bank, `CONTOSO BANKING SOLUTIONS LLC` is not), and so do the non-English bank words `BANCO`, `BANCA`, `BANQUE`, `BANCAIRE` and `SPARKASSE`, a company form after one being the bank's own; a relayed numbered company is a named customer.
- A3-G refinement: Bank of America's `WIRE TYPE BOOK IN` reads its originator after `ORIG`, as `WIRE TYPE WIRE IN` does (§7.11 T19); a wire sender read as bare channel words (`WIRE`, `TRANSFER`, `BOOK`, `CREDIT`) names nobody (`wire_no_sender`); and when the account-name field names nobody (a product name), the holder's name the statement's own incoming receiver fields print on two credits or more from two distinct originators or more (A3-G re-review: compared by the payer's first distinctive word, so one platform's two spellings are one originator) is the holder's too, for the holder hold only, matched run together with twelve letters or more, and only on classified wire layouts, book transfers and transfer or person-to-person rows (never the word WIRE in an ACH entry) (never an ACH, card, processor or marketplace settlement, a push rail, or a row an earlier rule verified) (§5.2).
- A3-G: a wire originator's SWIFT 50F line number printed with its slash (`1/`, `2/`, `3/`) is never part of its name, while a name that starts with a number keeps it (§5.2), and a sender that is the holder's account name cut short (two whole words before the cut, or twelve letters) is the holder, `holder_name` (§5.2).
- A3-G: a credit from a personal trust (a person's name ending in `TRUST`, `TTEE`, or a trust adjective and `TR`; A3-G review: the form ends the name, the words before it read as a person's, and never a trust company's or a bank's form after it, a lawyer's or client trust account, a title or escrow firm; A3-G re-review: a wire originator's address after the form holds only place words, a city, a two-letter state, a ZIP and a country code, never a business, lawyer, company-form, `ACCOUNT`, `SERVICES`, `DEPT` or institution word, and the lawyer and IOLTA words are read across the whole sender; A3-G re-review 2: the banned words are a finite list of trade and institution words (`CUSTODY`, `CUSTODIAN`, `ADMINISTRATOR` and `ADMINISTRATORS` among them), and the address prints at most 3 words of its own before its state, never counting the agreement, date, PO box and country words, a number, a street type or an initial; A3-G re-review 3: two or more single letters in a row that join into a company form, such as a dotted `L.L.C.`, `L.P.`, `P.A.` or `P.C.`, make the sender a company) is owner money, held as `non_sale_purpose` (§8.1).
- A3-H (the Verified strata's misses at s56c): a freight-factoring payer the registry's `FACTORING_PAYOUT_PAYERS` names (the registry entry carries its name and evidence) pays the carrier's own invoices: its credits, wire or ACH, are `counted_flagged` / `factoring_payout` after the holds, and Q5 and Q6 never verify them nor count them toward a repeat. A3-H review: a factor is never verified by any path (an earlier rule's verification, such as an invoice-purpose wire's or a remittance descriptor's, is overruled: method `factoring_payout_payer`), and its alias is read only as the payer region (the ACH originator or the wire sender), followed only by company forms: `<alias> FOR PETS LLC`, `<alias> CLEANING LLC` and another payer's purpose citing the alias are other payers. A3-H review 2: a glued company form (`<alias>LLC`), a `DBA` tail, an entry word, date or number that falls into the region (`PAYMENT`, `PMT`), and a B/O field's address (place words ending in a US state, at most three of its own, as the personal-trust rule reads one) may follow the alias; the table holds the entity's two spellings of its apostrophe; and a factor claims its row as a factoring payee does, so a financing word in its trade name holds nothing. The table is read by the true-revenue pass alone; it is no lender-ledger entity, so its debits and every payee group, flag and lender reading are unchanged. A `SCHEDULE <n>` purpose alone names no factor.
- A3-H: a healthcare, insurer or health-plan payer (the healthcare payer table, an insurer's name, or `INS` on the payer region) whose entry field (`DES`, `CO ENTRY DESCR`) prints a premium code (`PREM`, `PREMIUM`, glued `PREMSEC`) is a commission or a premium refund, never a claim payment: Q6c and Q5 refuse it and it is `counted_flagged` / `named_payer_purpose_refused` (on such a row a premium word is no member-word hold). A3-H review: a row with no entry field keeps its reading; a `COMM` or `COMMISSION` word in the entry keeps the reading even beside `PREM`; government payers (state, county or federal public payers, Medicare and its contractors, Medicaid, TRICARE, VA) keep their reading. A `PREM REFUND` the reversal rule reads stays `non_revenue`.
- Final review (2026-09-30): a PPD or WEB entry is read only in the SEC code's slot (Chase's `SEC <code>` or the code before `TRACE` or `ID`, the code Bank of America prints after the company id or at the row's end, `ACH <code>`), never in a name or receiver field (§8.6).
- Final review: every receiver vocabulary is built from one tuple (`analysis/description_text.py`), `RECV NAME` included (§5.2).
- Final review: a healthcare alias of five letters or fewer, and `ANTHEM`, names a healthcare payer only as the whole payer name (a company form, a health-plan word or another healthcare alias may follow): `ANTHEM ROOFING` and `WPS INDUSTRIES` are other companies (§8.6 Q6c).
- Final review: on a store-name platform, a veto word that is the whole entry field, or forms it alone with generic words, is never spared as the holder's word (`DOORDASH INC DES:CAPITAL` is held as financing) (§7.0).
- Final review: Q7 reads the non-revenue patterns without the holder's receiver name (a declared move out of `non_revenue`) and its insurer on step 5's lookup text (§8.7).
- Final review: a reversal pair's widened markers change the credit's revenue reading only; the debit's lender side keeps classification 5.4's pairs (§6.2 pass 4).
- Final review: a factor's alias followed by `FOR`, `OF`, `AND` or `THE` names another payer, never the factor at an address (§8.9).
- Re-review: on a store-name platform a veto word that leads the entry field is never the holder's store word, whatever follows it (`DOORDASH INC DES:CAPITAL DISB` is held as financing) (§7.0).
- Re-review: a processor, marketplace or platform credit whose entry field leads with a financing word (`CAPITAL`, `LENDING`, `LOAN`, `ADVANCE`, `FUNDING`, `FINANCING` …) is never verified; it is held as `financing_named_payer` (§7.2).
- Re-review: a PPD or WEB code is also read as the row's last word after a receiver value (never the holder's own last word), before `DES` after a company form or a reference, and right after a row's posting label (`ACH CREDIT PPD`) (§8.6).
- FW wave 3: a store named with a financing word keeps its payouts: an entry whose words (two or more) are a consecutive run of the holder's own name (`DES:CAPITAL GRILLE` for a holder named `... CAPITAL GRILLE ...`) is the store's name, never financing; a bare `DES:CAPITAL` or a financing entry stays held (§7.0, §7.2).
- FW wave 3: PPD before `DES` is the SEC code after any word (`NORTHWIND SUPPLY PPD DES:` is a consumer entry) (§8.6).
- GOV (the owner's ruling of 2026-09-30: true revenue is the money the business earns by selling goods or services, as the MCA industry counts it, so government money it did not earn leaves True revenue). Class B, a personal benefit, is held as `personal_income`: the federal benefit descriptors the banks print before the CRA's name (`CANADA CHILD BENEFIT`, `CANADA ESSENTIALS BENEFIT` and its full name `CANADA GROCERIES AND ESSENTIALS BENEFIT`, `CANADA WORKERS BENEFIT`, `CANADA DISABILITY BENEFIT`, `OLD AGE SECURITY`), a provincial benefit the CRA pays (`PROV LOCAL GVT PAYMENT CANADA`, the Canada PRO labels `… CANADA PRO`, `PROV LOCAL GVT PRO <province>` and `CANADA PRO DEPOSIT`), a state's unemployment deposit (`UI DD`) and the IRS's stimulus (`TAX EIP`, on an IRS Treasury row). GOV review: a descriptor is read as the whole payer after the posting words, with the CRA's name around it, and a company form after `UI DD` or `TAX EIP` vetoes it, so `CANADA CHILD CARE CENTRE INC`, `CANADA DISABILITY BENEFITS CONSULTING INC`, `OLD AGE SECURITY SYSTEMS LTD` and `NORTHWIND UI DD LLC` are payers (§8.1).
- GOV, class C: a tax refund is `non_revenue` (strong non-revenue rule): a business's GST/HST refund as the whole payer after the posting words (`CANADA GST TPS`, `GST CANADA`, Revenu Quebec's `RQ GST`, and with the CRA's name, a country code or the GST program account after them; `GST CANADA LOGISTICS INC` is a payer), and a payment the IRS issues through the Treasury (`IRS TREAS 310`) that prints no entry or a refund-worded one; GOV review: an IRS vendor payment (`MISC PAY`, `VENDOR`, `VENDOR PAY`, any other entry) keeps its reading, and the child tax credit and stimulus are class B (§7.11 T5).
- GOV, class D: a grant or subsidy is held as `non_sale_purpose`: HHS's Provider Relief Fund (`US HHS STIMULUS`, `HHSPAYMENT`), the USDA's farm programs (`FSA TREAS 310`, and GOV review `CCC TREAS 310`; `USDA TREAS 310` keeps its reading), the CRA's wage subsidy (`CANADA CEWS` as the whole payer) and ESDC's federal payment code (`GOVERNMENT ESDC … FEDERAL PMT`, its grants and contributions) (§8.1).
- GOV, classes A and E: a government or public program paying the business for its goods or services keeps its reading (a Treasury vendor payment, `DOD MISC`, a county's or a ministry's accounts payable, `GC CDCP` paying a dentist, Medicaid and TRICARE plans paying a provider, a state's provider pay, a parent's child-care subsidy card such as `FIS EBT … WIDCF EBT` paying the provider). Class E, by the owner's ruling of 2026-10-02 (the underwriter's Q12): the seven government payments that print no purpose are `non_revenue` (§6.1 step 3a, method `government_no_purpose_exclusion`, the form in `matched_alias`): `MN STATE MMB`, the VA's `36 TREAS 310 MISC PAY` (agency code 36 only), Wisconsin DCF's `WI DCF … WIDCF DD`, `PROVINCIAL PAYMENT PROVINCE OF BC`, Ontario's WSIB, `GOUV QUEBEC MSP` and North Dakota's `WORKFORCE SAFETY`. The step reads the row with the receiver's value removed and every field after it kept, so a purpose in Bank of America's `PMT INFO` addenda is read, and the VA's entry codes (`XXVA CH33`, `CH31`, `BENEF`, `EDU`) are purposes; a purpose printed anywhere (`VENDOR PAY`, `PROV PAY`, `RMR IV`, an invoice, a grant, a rebate, a claim) keeps the row's reading, as does every form the ruling did not name (another agency's Treasury code, another province, another workers' compensation board). It decides at any amount, after the direction conflict and the reversal, before every other rule. Since audit round 2, R2-OW03 such a row carries the display reason `government_no_purpose` ("Government payment, no purpose printed"), so the non-revenue breakdown names it; it has no review path.
- Audit fix batch B2 (I01): a bank's name never names a transfer's counterparty (a sending bank's, the statement's own, a bank's name glued to `TRNSFER`, a credit union's one-word name before `CU` or `FCU`, `BANK` or `SAVINGS`), nor does an online-banking channel code or account description (`CBUSOL`, `OLB`, `EXT`, `CMO`, `TELEPHONE BANKING`, `PHONE`, `CRD`, `FSB`, `PROTECTION`, `OVERDRAFT`, `FOUND`, `BUSINESS BANKING`, `OPERATING ACCOUNT`, `FUNDING` beside `TRANSFER`): such a transfer is held as `transfer_no_counterparty`; a company or person after `FROM` keeps the named reading, and a custodian's name is not removed. A bare `FROM <digits>` designates an account (T13) unless it starts a numbered company. An ACH payer that is only a bank's name and an account description (`<bank> SAVINGS <n> ACH`) is held as `transfer_no_counterparty` and never verified by repetition. The own-account sources add `DDA`, `CHECKG`, `CL`, `LN`, `CRD`, `CREDIT CARD`, `CREDIT LINE`, `LINE OF CREDIT` and `LOC`, `FRM` reads as `FROM` and `XFR` as transfer wording, and Truist's `ONLINE TRANSFER ONLINE FROM <n>` is own-account (`MOBILE` between them is not read) (§8.2, §7.11).
- Audit fix batch B2 (I21): the holder's overdraft-protection sweeps (`OVERDRAFT PROTECTION FROM`, `OD PROTECTION TRANSFER`, `OVERDRAFT XFER FROM`, `ODP TRANSFER`) and Regions' `EB FROM CHECKING|SAVINGS` are `non_revenue`; `TRF`, `TRSFR`, `TRANSF`, `XFR` and `TRANSFER` glued to digits are transfer wording (never the e-transfer rail's glued `E TRANSFER<n>`; `TRANSFERS` waits for B8); a Square savings folder (`TRANSFER IN RAINY DAY`, `TRANSFER IN RENT`) is held as `transfer_account_designation`, never on Wealthsimple (§7.11, §8.2, T13).
- Audit fix batch B2 (I20, §6.3 narrowing 8): a named sender printed after an own-account designation (Bank of America's `… TRANSFER FROM CHK|SAV <n> CONFIRMATION <reference> <sender>`, a credit union's `TFR FROM X…<n> TRANSFER DEPOSIT <sender>`) that the holder test does not match is no own-account transfer: it is held as `transfer_account_designation` for review, never counted or verified; with no sender, or the holder's own name, it stays `non_revenue`, and Navy Federal's `TRANSFER FROM SHARES <name>` stays `non_revenue` (§6.3, T13).
- Audit fix batch B2 (I48): an explicit cash, ATM or check deposit form beats bare transfer wording (`CASH DEPOSIT TRANSFER IN` is counted as `no_payer_printed`, `MOBILE CHECK DEPOSIT TRANSFER` as `check_deposit`); `TELLER TRANSFER` and `BRANCH TRANSFER` stay held (M4), and a branch or teller transfer that names its counterparty is a named transfer (T13) (§8.2, §8.3).
- Audit fix batch B3 (I03): pass 4's revenue side pairs a debit that undoes a deposit (a returned deposited item such as `RETURNED ITEM`, `RET DEP ITEM`, `DEPOSITED ITEM RETN`, `RETURN ITEM CHARGEBACK`; an error, transaction or deposit correction; a mobile, remote or ATM deposit adjustment; `ADJUSTMENT CORRECTION`; never the fee for it, never TD's `RTN NSF`) with an equal deposit-channel credit (check, cash, branch, ATM or bare deposit; never an electronic payment) 0 to 14 days before it, with no shared word, the earliest first, so a redeposit stays counted. The lender side keeps 5.4's pairs (§6.2 pass 4).
- Audit fix batch B3 (I04): step 3 also reads `ITEM RET NOT PAID`, `NOT PAID`, `RET DEP ITEM`, `ERROR|TRANSACTION CORRECTION`, a leading `CORRECTION`, `PURCHASE RET`, `DEBIT CARD CREDI`, a credit's leading `CHECKCARD <mmdd>`, `POINT OF SALE DEPOSIT <merchant>`, `PROVISIONAL CR`, `UNAUTHORIZED`, `RECLAIM`, a leading `REV MOBILE|POS|DEBIT|PURCHASE|ACH|CARD`, `RENV`, `RENVERSEMENT`, `RETOUR`, `REMBOURSEMENT` (with REIMBURSEMENT's provider carve-out, and the Quebec health insurance board) and fee waivers and courtesy refunds; pass 4 reads them on the credit only. A card credit printed first (`CARD CREDIT`, `CARD CREDIT <merchant>`) with no push or person-to-person rail is held as `possible_return`; Regions' Cash App and Apple Cash card credits stay counted `p2p`. Cash App and Apple Cash on a `DEBIT CARD CREDIT` join the push words only with the owner's switch `CASH_APP_CARD_PUSH_RELEASE` (off under the owner's card-push ruling of 2026-10-02) (§6.1 step 3, §7.11, §8.1).
- Audit fix batch B3 (I11, §6.3 narrowing 9): with the owner's switch `PROCESSOR_CARD_PAYOUT_RELEASE` (off: on 2026-10-02 the owner kept a processor's payout printed as a bare card credit excluded, the underwriter's Q13), a `DEBIT CARD CREDIT` or `POS CREDIT` whose whole payer is a merchant processor (`CARD_PAYOUT_PROCESSOR_NAMES`: Stripe, QuickBooks Payments with a bare `INTUIT`, Square, PocketSuite) is that processor's instant payout, counted and flagged as `platform_unconfirmed`, when the statement prints the processor's own ACH payout or pull and no card purchase at it (§7.11).
- Audit fix batch B3 (I43): card-rewards redemptions are `non_revenue`: a whole-row `CASH REDEMPTION`, `PURCHASE PAYBACK [AWARD]`, `POINTS REDEMPTION`, and `MR REDEEM` or `MEMBERSHIP REWARDS` beside a card issuer's name; a payer named `REDEMPTION …` keeps its reading (§7.11).
- Audit fix batch B3, review round 1: the new step-3 spellings stay off company names and memos. `RECLAIM` is read only with its reference glued after it or last on the row (CIBC's `E TRANSFER RECLAIM<digits>`), never `RECLAIM <name> LLC`; `NOT PAID` only after an item or return word or as the whole row; `UNAUTHORIZED`, and a leading `REV <rail>` or `RETOUR` not followed by a transaction word, a reference or `MDSE`, only with no legal-form word later on the row. The deposit mode's undo debit is the bank's own return: never a person-to-person or push rail, `WIRE`, an electronic payment's mark or a paid check printed first, never the fee (`CHARGE`, `CHRG`); undated rows read the row order; a correction that shares an equal non-deposit credit's words undoes that payment, not a deposit (a returned item's printed name is the check's maker, so it still undoes the deposited check). A provider's `REMBOURSEMENT` marks no pass-4 pair, and a bare `POINT OF SALE DEPOSIT` with no merchant stays counted (§6.1 step 3, §6.2 pass 4, §8.1).
- Audit fix batch B4 (I02): the counter-debit holds (pass 6's guard and pass 7's `payer_also_debited`) read the debit's kind, as their purpose (circular money: an own account, an affiliate, a funder that collects) states. The bank's own receiving fee for an incoming wire or funds transfer, which reprints the sender (`FUNDS TRANSFER FEE TT <sender>`, `[INCOMING] WIRE [TRANSFER] FEE`), never holds the payer; the fee for the holder's own outgoing wire still does. A processor's own fee, discount, chargeback, adjustment or returns debit never holds a credit printing settlement, payout, `MID` or merchant-services wording, and a bill the holder pays (bill pay, EBPP, autopay, a utility, telecom, cable or subscription) never holds a payer that does not read as an insurer (`INS`, `INSUR…`), unless that debit is for the credit's own amount or (a bill only; B4 review round 1) one of two or more at one amount. The debit's kind is read without its receiver fields' values, the holder's own name (B4 review round 1). A transfer, wire, person-to-person or own-account debit matches at any size, and also by 5.6's reading of the first word. Generic words (`MERCHANT`, `UTILITIES`, `EXPRESS`, `INCOME`, `PAIEMENT`, `POSTED`, `SERVICE(S)`, `TRSFR`) and the bank names the corpus prints as a channel (`CHASE`, `TRUIST`, `BLUEVINE`) never make the first word (§7.5, §8.1).
- Audit fix batch B4 (I22, I38): both counter-debit holds compare names without regard to spaces (a name glued on one side matches it spaced on the other) and with a reference glued to the name split off (`<NAME>USA1`); `payer_debited_as_lender` also matches when both sides name one registry lender entity and, for an unverified credit in pass 7 (one no rule verified; before Q5 and Q6, as the first-word match), when one first word of five letters or more starts the other and the longer runs on into a financing root or the shorter side's next word (§8.1).
- Audit fix batch B4 (I56): a three-letter payroll provider (`ADP`) is a counter-debit word, so an `ADP TAX` credit beside the holder's `ADP TAX` debits is held as `payer_also_debited`; a payroll provider's tax-service credit (`ADP`, `PAYCHEX`, `GUSTO` or `INTUIT` with `TAX` or `TAXES`, the tax word read on the payer region and the entry fields since B4 review round 1) that no debit holds is held as `non_sale_purpose` (§8.1, §8.10).
- Audit fix batch B5 (I14, I23, I12's reader; 346881a): on the wire channel a payer region with no name word (a lone glued reference) or made only of bank and layout labels (`BANK`, `DEPOSIT`, `INTERNATIONAL`, `IN`, `INCOMING`, `RECEIVED`, `DEP`, the bare channel words) names no sender: `wire_no_sender`, held (Q5); `IWT` waits for audit batch B10. `BANK WIRE DEPOSIT`, `WIRE DEPOSIT WIRE IN` and `WIRE CREDIT REF<n>` are incoming-wire labels; a loose-wire row's `ORIG`, `ORG`, `B O` or `ORIGINATOR` label names its sender; and a wire a bank originates on its own behalf is held on every wire-channel row, never on a region of labels alone (§5.2, §8.1, §8.5).
- Audit fix batch B5 (I15, I19, I26, I55, I59; 346881a): the ACH and person-to-person payer readers read past a bank's label, entry or reference: Chase's real-time sender after its contra-bank `FROM ABA/CONTR BNK <routing>`; PNC's `CORPORATE ACH <entry> <reference> <payer>` (its entry an entry field; its Intuit `DEPOSIT` entry is QuickBooks Payments' card-settlement form); a payment reference before the payer after `DIRECT DEPOSIT`, `ACCOUNTS PAYABLE`, `MISC PAYMENT` or `BILL PAYMENT`, unless a province, Quebec's form or BMO's code tail follows it; Navy Federal's and Symitar's digit block; an `ORIG CO` label with no value (no payer); American Express's `ONLINE TRANSFER PAYMENT CREDIT <originator> <entry> <id> … EXTERNAL …`, an ACH template whose receiver block is a receiver field (the originator's own `TRANSFER` entry stays transfer wording). The numbered-company number is six to ten digits, and the template reads it only when nothing, a province or BMO's code tail follows (§5.2, T11).
- Audit fix batch B5 (I37, I61; 346881a): on TD Canada Trust's statements the trailing Payments Canada code `AP`, `MSP`, `BPY` or `APY` is an electronic-payment form (Q6 reads the row) and `PAY` is pay wording (Q8 holds it); Q5's repeat arm reads an `LLC` the wire's 35-character originator field cut to `LL` and glued to the city as a company form, never for Q6 (§5.2, §8.5, §8.6, §8.8).
- Audit fix batch B6 (I08, I22, I49; f5f9b61): a credit is read with the known-payee matcher's credit index, in which a run-together alias of eight letters or more also matches with a reference glued after it (`FORWARDFINUSA<n>`, `LCFGROUPINC<n>`) and the credit-only aliases (`CREDIT_ONLY_ALIASES`) are read; a debit keeps the default index. The ledger gains Forward Financing's, East Shore Equities' and The LCF Group's printed credit spellings and the instant-payment forms of SoFi's personal loan, Brigit, Tilt (Empower) and MoneyLion (Empower's two forms only where a reference code follows: `REFERENCE_TIED_ALIASES`; since the batch's review round 1 also Brigit's two forms and `TILT CASH`); the counter-debit holds read the payer past a leading `INSTPMNTIN` or `RTP CREDIT` label; `SPE` is a financing root (a glued `FINUSA` was one until the review round 1 dropped it: it read any run-together name ending in FIN + USA); an earned-wage access push (`PAYACTIV`, `DAILYPAY`) is held as wages (Q8) (true revenue spec §8.1, §20).
- Audit fix batch B6 (I23, I24, I25, I10; f5f9b61): a credit whose payer is a lending bank (`LENDING_BANK_CREDIT_PAYERS`: Celtic Bank, Newtek Bank) is held as `financing_named_payer`; on a credit the premium-finance lookup reads a glued digit run (`IPFS<n>`), so every IPFS credit is insurance and `non_revenue`; Treadstone's `TREADSTONE OPER` is a factoring alias, and a factoring payee's credit is never verified; a factoring review entity's credit (`FACTORING_REVIEW_ENTITIES`) is a factor's payout, flagged and marked unconfirmed, where the potential tier made it non-revenue, its debits keeping the potential tier, unless the credit revenue path's reversal rule reads it (review round 1: a reversal is no payout and takes no Factoring flag) (true revenue spec §6.3 narrowing 10, §8.1, §8.9, §20; lender detection spec §4.2, §4.6, §5).
- Audit fix batch B7 (I16, I47; 527194f): the financing roots are read only on text that can name the payer: never on a cash, branch, ATM or check deposit's location, a bank's branch label (`BOFA FIN CTR`), the banks' page furniture (`MEMBER FDIC`, `EQUAL HOUSING LENDER`), the plural `CREDITS`, a cut originator name's entry word (`<NAME> P CREDIT`), a fundraising purpose, Wave Payments' payout entry, a person-to-person sender's bank (a listed sending bank, the statement's own, a credit union's name) or a sender that reads as a person's name, or a wire's `ADVANCE PAYMENT` or `PREPAYMENT` purpose; and the possible-return, financing-root, pay, personal-income and non-sale holds read the row without the holder's own name runs, a run of its first two words or more included when the account name names the holder (true revenue spec §8.1, §20).
- Audit fix batch B7 (I18, I09, I36; the orchestrator's ruling on audit I57; 527194f): the non-sale words read only as a purpose (never a street's name, `OWNER COM`, an owners' association, `DISTRIB…` or `STOCK` in the payer's name field or a formed name, `JOINT STOCK`, `STOCK` on an invoice, the payer's `DISBURSEMENT ACCOUNT`, or an ordinary payer's recurring disbursement entry); `DIR DEP`, `DIRDEP`, `DIRECT DEP` and the `DIRECT DEPOSIT` entry are pay wording only beside a payroll provider, a person receiver, a consumer entry or on an account that does not read as a business's (Q7 still refuses them alone); a credit union's glued acronym (`BECU`) is a credit union, its other dealer-funding entries (`VADMIN FEE`) verify beside its verified VHCL PURCH credits or a verified deal's ID, and a named non-lender's wire memo is no dealer funding; a personal trust's payment citing the holder's service (`TUITION`, `STUDENT ID`) is counted (true revenue spec §8.1, §8.7, §8.8, §18.2, §20).
- Audit fix batch B7 review round 1 (8b067ec): a payer-less check, cash, branch or ATM deposit is read past its location (a branch's label, a credit union's name, a street) for whole financing words, so a funder's name printed on it still holds and a town's name never does; a payer named `<NAME> CREDITS LLC` holds; `DISTRIB…` and `STOCK` are spared in a formed name only after a name word; an owner-shaped payer's recurring disbursement keeps its hold; a direct deposit's person is read past a trailing reference or trace label; a floor-plan or wholesale sender keeps the dealer-word hold (true revenue spec §8.1, §8.7, §8.8, §20).
- Audit fix batch B7 review round 2 (be81f7c): a payer-less deposit's reading also removes the ATM's or branch's bank, a place a suffix names (`PLAZA`, `MALL`, `CIR`, `DISTRICT`, `HEIGHTS` …), a branch's name before `BRANCH`, a town printed with its state and a buyer's advance purchase, and keeps a hold notice's `FUNDS` only before a company form; a formed name's word before `DISTRIB…` is a name word with a letter, at most two digits and no period's code, and a tax, year-end, month, partnership or preferred word is a purpose; only a floor-plan form or `WHOLESALE` beside a lender's or a vehicle trade's word keeps a customer's vehicle wire held (true revenue spec §8.1, §8.7, §20).
- Audit fix batch B8 (I28, I44, I56; 84c824f): pass 7 holds as `non_sale_purpose` a gambling or prediction-market payout (DraftKings and its Crown <state> Gaming entity, FanDuel, BetMGM, Caesars Sportsbook, Fanatics' betting forms, ESPN BET, bet365, BetRivers, PrizePicks, Underdog's fantasy and sports forms, Kalshi, Polymarket, Chumba, Pulsz, `JACKPOT`, `WINNINGS`, `LOTTERY PRIZE`; never a vendor's invoice payment or a lottery's retailer settlement), a legal settlement (`LAWSUIT`, `LITIGAT…`, `CLASS ACTION`, `DATA BREACH`, `SETTLEMENT ADMIN…`, the claims administrators, a lawyer's or IOLTA payer's `SETTLEMENT PROCEEDS|FUNDS`; never a bare `SETTLEMENT`), a settlement or closing agent (a title firm), an owner-shaped payer's `DISB`, the crypto exchanges and retail brokerages `OWNER_MONEY_PLATFORMS` now names (Kraken/Payward, Binance/BAM Trading, Bitstamp, Uphold, BlockFi, Bakkt, Paxos, Apex Clearing, M1 Finance, `COINBA SE`, `P FIDELITY`; never a custodian) and a glued Canada Carbon Rebate (a grant), and as `personal_income` an HSA distribution, a cut `LIFE AN DISB…` annuity and RBC's `Prov./Loc.G.Paym Canada` (true revenue spec §8.1, §20).
- Audit fix batch B8 (I45, I46; the GOV follow-up; 84c824f): `SECTION_15_DEFERRED_PAYERS` adds the equipment auctions' and car buyers' seller payouts (never verified by Q5 or Q6; CarMax Auto Finance stays a listed auto lender; Copart and IAA only on a seller word); `revenue_text` cuts the statement furniture a parser glued onto a row (TD's footer and back panel, a Symitar balance, check-recap and fee summary, a page header, Citizens' continued-page header and footer, Fifth Third's disclosure line, a page number) before any credit rule reads it, and pass 7's counter-debit kinds read a debit past it (§6.3 narrowing 11 for a deposit it releases from a non-revenue rule); `TRANSFERS` is transfer wording, and `FUNDS TRANSFERS` a posting label of the holds; the IRS's `INT` or `INTEREST` entry is `non_revenue` with its refund forms (true revenue spec §6.3, §7.0, §7.11, §8.2, §15, §20).
- Audit fix batch B9 (I13, I38; 8607e54): the statement carries the holder's name as its own field (`holder_name`, read by Chase from its mailing block and by First Citizens from its holder line, apart from the product in `account_name`; Chase no longer publishes its summary grid header as the account name), every record carries it, and the holder tests read it first (`holder_reading`); each side of a DBA name is a name of the holder's; a row whose ACH or EFT originator is its own receiver field, or whose incoming wire's sender is its beneficiary, is held as `holder_name`, a processor's settlement or payout under the merchant's own name (`NET SETTLE`, `NETSWEEP`, `FINTECHEFT`, `BANKCARD`, `MERCH`, a statement descriptor) aside; the receiver fields' holder names are still read beside a parser's holder name; `metrics.holder_unscreened` says when no holder name is known (true revenue spec §5.2, §8.1, §9.1, §20).
- Audit fix batch B9 (I13; 1c94ff3): TD Bank, Truist, PNC, Navy Federal and TD Canada Trust read the holder's name from the line or mailing block they print (TD Canada Trust on both entry points); the holder test reads a payer region without the holder's name run printed after another payer's name and whatever follows it, Truist's receiver block (true revenue spec §5.2, §20).
- Audit fix batch B9 (I58; 8607e54): the holder test compares the leading words of two names as printed when either leads with a short initialism (a different initialism is a different company, the same one a likely affiliate), matches a one-word holder only when it leads the payer's name, reads `BMO`, `ADV`, `BUS`, `CKG` and `GENERAL` as noise on both sides, and never reads the holder's name printed after another payer's name (its unlabelled receiver) (true revenue spec §5.2, §20).
- Audit fix batch B9, review rounds 1 and 2 (fe1ed9d, ebd4ba3): a processor's settlement words exempt a row from the holder holds only where they print outside the holder's own names, never on an incoming wire or a person-to-person or push rail; the row's layout says where another payer's receiver block can print (never inside a labelled sender; one name word on Truist's receiver slot, read on a Truist statement only; two on any other row); an incoming wire is the holder's own only when its sender's and its beneficiary's whole names are one (each cut after its first legal form, or read without its town and state when no legal form ends it); a product name a holder reader publishes (PNC's `Treasury Enterprise Plan`) never names the holder, and an account name that names a holder is a second holder name beside the parser's; a one-word holder whose lead word the test drops is read with that word (true revenue spec §5.2, §8.1, §9.3, §20).
- Audit fix batch B10 (I05, I12, I14, I60; 7ac84c8, ed0a9ad): a credit a deterministic parser publishes with only its posting-type or section label, because it could not read the payer the statement printed, is marked (`Transaction.payer_text_unread`, written only where set, kept out of the extraction schema); where pass 7 would read it as a bare deposit (§8.10's last step) it is `counted_flagged` / `payer_text_not_read`, never verified, every hold before it still applying, and a marked cash, branch, teller or ATM deposit keeps `no_payer_printed`. `metrics.payer_text_unread` says when more than 30% of a statement's posted credit rows are marked (`payer_text_unread_count` counts them). The parsers keep the payer printed beside a credit's label: BMO US's activity grid (a page break skipped whole), the counted core-processor template's block below a credit's amount where the attribution count proves it one row's (the daily template marks the rows whose block it cannot attribute), the community platform's rest of a published credit's printed line (Falcon's `International IWT` an incoming-wire label, its sender read after the bank's own wire field), the balance-by-date template's transfer field and U.S. Bank's `ORG=` wire sender (the field's name, up to its address or the next field). Debits keep their labels until the owner admits the debit readings (G7) (true revenue spec §5.2, §5.3, §8.2, §8.5, §8.10, §9.1, §20).
- Audit fix batch B11 (I06, I07, I31, I33, I50 to I54; f97e607): the review gate's held-share test above (T7) also reads True plus held; the four-tier identity is `revenue_tiers_sum_to_posted` (`revenue_reconciles` its deprecated alias), and "Balanced" means `reconciliation.ok` with established revenue; a package leaves a repeated statement out of every figure, counts calendar months and publishes True, Verified and Non-revenue per month; the downloads leave unestablished figures empty and list every posted credit with its tier and reason (true revenue spec T7, §9.1, §9.2, §10, §20).
- Audit fix batch B12 (I62): this document and the README describe the code as built after the fix batches (the residual interest forms held, unverified deposits as counted plus held, both revenue withholding modes and the denominator `eligible_deposits` carries, every statement pass, the reason table); no behavior changes (true revenue spec §20).
- Audit fix batch B12, review round 1: the reason table's `insurer_named_payer` row names every word the hold reads and its claim-word arm, the metric definitions say the review gate reads the held total (`revenue_review_items` is the held-row count), the withholding section says no run or deploy file here sets the mode, and the docs test compares the reason table with `REVENUE_TIER_REASONS` row by row, in its order; no behavior changes (true revenue spec §20, §17.1).
- Audit round 2, R2-B02 (R18, R01, R02, R48 part 1): a platform's payout is known by its payout id (`ID:ST-<id>`, `IND ID:ST-<id>`; `processor_payout`), never by an entry that repeats the originator's first word: it takes no holder hold whatever descriptor it prints, and the platform's own pull printing a payout id never holds it unless the pull is for the payout's own amount; the holder's own push echoing its name is held on the row alone. The counter-debit holds (pass 6's guard and pass 7's) read a processor's payout by its settlement wording, its payout forms (`MRCHNTSVCS`, `COMB DEP`, Payment Brands' `PAYMNTBRAND` and `PYMNTBRDMIN`, `INTUIT CANADA PAYMENTS`, `DEPOSIT <bank> MERCHANT`, a twelve-character payout id after `ST`) or a merchant-ID field anywhere on the row, and such a payout is held only by a circular or lender debit, a debit for its own amount or a non-card debit recurring at one amount; a card purchase in another bank's form (`DEBIT CARD PURCHASE`, `DBCRD PUR`, `POS DB`, `POINT OF SALE`, a glued `PURCHASE<digits>`, `<city> <ST> USA|CAN`, or class `pos`) reads the kind `card`. A wallet's cash-out names no sender; the rails' and RBC's `PAIEMENT` label's words and (outside the lender hold) the states, provinces and nations are never a payer's or a debit's word; a person-to-person or push credit from, or debit to, a name of two words or more matches only that whole name; an e-Transfer's sender printed without `FROM` is read; ATM, ABM and cash withdrawals hold nothing; `Paiement divers COMPTE CHEQUE|EPARGNE <n>` is held as `transfer_account_designation`; the bank's receiving fee reads its outgoing words before the sender it reprints after `TT` or `FROM` (true revenue spec §5.2, §8.1, §20).
- Audit round 2, R2-B02 review round 1: in `payer_debited_as_lender` the whole name is one more arm, never the only one (the first word, the B4 forms and the prefix still read a person-to-person or push credit); the whole-name key is a person's (a sender printing a company form is compared by the B4 forms) and a debit for the credit's own amount that is no person-to-person debit still matches its first word; a card purchase in another bank's form keeps its kind and is marked a card charge, which only lifts a payout's hold; a payout id holds letters and digits; a company named `ATM` or `ABM`, or an ACH entry printing one, is no cash withdrawal; a credit `FR SAV` or `FR CHKG` (Bank of America's banking centre) is held as `transfer_account_designation`; `FROM` before the holder's own account starts no sender in the receiving fee (true revenue spec §8.1, §20).
- Audit round 2, R2-B03 (R05, R10): a payer region that names only a bank (a listed sending bank of `P2P_SENDING_BANK_NAMES`, which adds `MSPBNA` and `ALLY BANK`; the statement's own bank, such as its `CHASE ONLINE` channel; or one to four words ending in a bank's own form; a trailing `ACH`, `ONLINE` or `N A` aside) never verifies by Q6 and is counted as `no_payer_printed`; printed with no entry field, a sending bank or a bank by its form is the holder's pull from another of its accounts, held as `transfer_no_counterparty` unless a rule verified it or the registry claimed it; a bank's merchant deposit or card settlement entry (`DEPOSIT`, `DEP`, `MTOT`, `BTOT`, `SETTLE…`, `STLMT`, `MERCH…`) and a bank's settlement originator keep their readings. Northeast Bank joins the lending banks (`LENDING_BANK_CREDIT_PAYERS`), whose credits are held as `financing_named_payer`. The ledger adds `ROOK BRISTOL FI`, Rook Bristol Financial's 15-character CPA-005 short name, read on credits and debits (true revenue spec §8.1, §8.2, §8.6, §20).
- Audit round 2, R2-B04 (R19, R20, R40, R41, R04 parts 1 and 3): `metrics.holder_unscreened` is false whenever the parser read a holder's name the holder test reads a word of (a trailing `CO`, a partnership, a `DBA` or `Operating as` name, `S.E.N.C.`, five words or more), on a statement with no transaction too; the holder's own name runs the holds strip read each side of such a name, a last word the bank cut at the row's end, and every business name of the holder's beside a person's (the account field's business, a `DBA` name's trade side, its legal side with a company form), never a person-shaped name. The holder test's two shared words need the holder's lead word among them, or a payer whose own first distinctive word is a holder word; two person-shaped names are compared on shared words only (a cut word read as the holder word it starts), never by a given name. The holder's own push read on the row alone (`self_originated`, now pairing American Express's receiver block) is held as `holder_name` even where step 11 verified it (method `self_originated_holder`) and never counts toward a repeat; a processor's, a platform's or a franchisor's credit printing the merchant's name (a registry processor or platform, its cut, `INTUIT`, a franchise or platform fee entry; never a wire or a person-to-person or push rail) takes no holder hold; Capital One's row is read without Mercury's `MERCURYACH` and `MRCR` tails (true revenue spec §5.2, §8.1, §20).
- Audit round 2, R2-B05 (R04 parts 2 and 4; 5a3da3d): fourteen more parsers read `holder_name` from page 1's mailing address (Bank of America, Wells Fargo, U.S. Bank, RBC and Banque Royale, Scotiabank, Bluevine, Huntington, Capital One, CIBC, Square, Mission Valley, BMO's US activity layout, Santander, Citibank), TD Canada Trust's French issue reads it at the English issue's mail-routing anchor, and Chase, Navy Federal, TD Bank and PNC read page 1's mailing block where their anchor reads none; a reader reads the address line or the block's first name line (a `DBA` line kept; an owner's, a contact's or a co-holder's line never; an `ATTN` contact dropped) and reads nothing it cannot place. The holder tests read those names as they read the seven B9 readers'; every transaction is extracted as before. Desjardins' reader is held for the owner (true revenue spec §5.2, §9.1, §20).
- Audit round 2, R2-B06 (R03, R21 part B's parser line; 4487a1e, 3deadcf): Navy Federal's compatibility path reads a retail product's amount-first block text row by row (a pair owns the date group printed after it; a row printed date-first keeps its wrap lines; the old line reader runs only where that reading does not fit) and drops the page header (`Statement of Account`, `Joint Owner(s): NONE`) it glued into the last row before a page break, and the native layout rung reads the one checking product the summary declares instead of `Business Checking` alone. The classifier reads each row's own printed text; no rule changes (true revenue spec §9.3, §20).
- Audit round 2, R2-B07 (R07; e28b5e0, 99a9c2b): the counted core-processor template keeps, on each credit it marks unread at a welded flush, that flush's joined text (`Transaction.unread_payer_text`, written only where set, kept out of the extraction schema, never the description; debits keep none, and the daily template kept none until audit round 3, R3-B09); a marked credit whose unread run, split after each ACH class code, prints a registry lender's block (a lender or financing state other than an alternative position or a factor) or a lending bank's is held as `unread_run_names_financing` instead of counted as `payer_text_not_read`. The bare financing root is not read, every earlier hold and the cash, branch, teller and ATM reading keep precedence, nothing is put toward lender credits, and the review card prints the unread blocks (true revenue spec §8.2, §8.10, §9.1, §20).
- Audit round 2, R2-B08 (R08, R22, R47, R48 part 2; ccd3596): step 3's credit markers, which pass 4 reads on the credit row, read the French return, reversal and refusal wordings (`EFFET RETOURNE`, `CONTRE-PASSATION DE CHEQUE|DEBIT`, `EFFET|CHEQUE REFUSE SANS PROVISION`) and the check-word `CHECK|CHEQUE|CHK|CHQ [<n>] NOT PAID`; the strong non-revenue rule reads the French interest credit and fee rebate (`CREDIT D INTERET`, `INTERET CREDITE`, `RABAIS SUR LES FRAIS`); an e-Transfer reclaim also reads with the rail word right before `RECLAIM` and a spaced or colon-separated reference, or as TD's `RECLAIM E-TFR`; a fee waiver reads only with no legal-form word later on the row. The deposit mode's undo debits read `DEP RETURN CHARGEBACK`, a row-leading `CHARGE BACK ITEM` or `CHARGE BACK - <return reason>` and a cut `DEPOSIT [TYPE] CORRECT`, never a bare or a processor's chargeback. The credit known-payee index reads a run-together alias with one or two letters after its digit run (`FORWARDFINUSA1X`); the debit index is unchanged. A personal trust is released only by `TUITION` (never after `IN`) or `STUDENT ID` as whole words. `_NSF_PATTERNS`, every debit reading and the lender side of pass 4 are unchanged (true revenue spec §6.1, §6.2, §7.11, §8.1, §20).
- Audit round 2, R2-B08 review round 1 (95bb4c3): the check-word `NOT PAID` is read at the row's head only (a spaced or glued date before it at most), in step 3, pass 4's credit markers, the possible-return backstop and the census's declared markers alike, so a wire's remittance field, a person-to-person memo or an ACH entry description that mentions a check not paid keeps the payment's reading; a line wrap's split inside a trust's `STUDENT ID` purpose is joined, as `TUITION`'s is; a fee waiver printing a legal-form word other than the holder's is counted, a recorded residual with no corpus row (true revenue spec §6.1, §8.1, §20).
- Audit round 2, R2-B09 (R06, R31, R45, R28, R25; b95beec): the layouts' posting and channel labels that print `CREDIT` (`EDI EFT CCD CREDIT [CCD]`, `INTERNET CREDIT`, `PREAUTH CREDIT`, `HIP CREDIT RCVD FROM`, `HIP CREDIT`, `[I] AVIS DE CREDIT`, `AUTOMATED CREDIT`) are template prefixes, so the payer region starts after them, a bare label names no payer and the label's `CREDIT` is never a lender's name word; an ACH entry's `CREDIT NONE` after a cut name and a credit union's `DIVIDEND CREDIT` are no financing root; U.S. Bank's `WIRE CREDIT REF<n>` and the `<qualifier> WIRE CREDIT` labels are wire channel fields the financing veto never reads, the row still a wire. American Express's `ONLINE TRANSFER PAYMENT CREDIT` is an ACH label only before an originator word (the bare label or the label before an account designation is a bare transfer); the glued `ONLINETRANSFER`, `MOBILETRANSFER` and `INTERNETTRANSFER` are transfer wording and `CHCKING`, `CHKING`, `CKG` account designations; a credit's transfer wording inside a company-formed ACH originator's own name is the company's name (`credit_transfer_wording`; the entry field still read; debits unchanged); a teller, branch or counter transfer names its counterparty only by `FROM` and a sender or by a company form (true revenue spec §5.2, §7.9, §8.1, §8.2, §8.4, §20).
- Audit round 2, R2-B09 review round 1 (22243a1): `credit_transfer_wording` blanks a name's transfer wording only on a real originator field (Chase's label, or Bank of America's `DES` with a field of its layout after the entry), never on a town's `DES` (`DES MOINES`), and never when the name prints a transfer's phrase word (`FROM`, `FRM`, `FR`, `TO`, `BETWEEN`), so a named transfer keeps its transfer reading (counted, never verified; held with an account designation or as repeated round sums); two residuals are recorded and pinned: a lender name ending in `CREDIT` before an entry-less `NONE` is counted, and a glued `ONLINETRANSFER TO <payer>` debit does not hold that payer's credit (true revenue spec §8.2, §20).
- Audit round 2, R2-B10 (R32, R21 parts A to D, R11, R26; ce7c41e): a wire's payer region of labels alone names no sender, the labels being one list (the bare channel words, every wire layout word, `BANK`, `DEPOSIT`, `DEP`, `IN`, `RECEIVED`, `CR`), so `INCOMING FEDWIRE`, `FEDWIRE CR` or `INBOUND WIRE` is held as `wire_no_sender`; `INCOMING FEDWIRE`, `INBOUND FEDWIRE`, `INBOUND WIRE`, `INCOMING CHIPS` and the plural `WIRE TRANSFERS <DEPOSIT|CREDIT|IN|INCOMING|FROM>` are incoming-wire labels and `WIRE TRANSFER[S] IN <sender>` reads its sender, so a company wiring twice verifies by Q5; `revenue_text` also cuts Zions' legal-name footer before a page counter and Navy Federal's `[STATEMENT OF ACCOUNT] JOINT OWNER(S)` header; a funds-transfer row an incoming-wire label starts that prints only a reference (`_bare_incoming_wire`: no originator, no account or own-account product word) is an incoming wire with no sender, held as `wire_no_sender` and reviewable, never the holder's own transfer, and designates no own account for R-d (`prints_internal_transfer_designation`); a loose-wire originator label is read only after the row's first `WIRE` word, from its own position (`_loose_wire_label`), so a label word inside a `<sender> WIRE` row's name never cuts it; the census declares the bare incoming wire (`13_bare_incoming_wire`, never into True) and counts counted or Verified credits a non-revenue rule reads after their last page-break form (`furniture_tail_non_revenue`, the cut's recorded residual) (true revenue spec §6.3, §7.0, §7.9, §7.11, §8.5, §20).
- Audit round 2, R2-B10 review round 1 (61ec89f, ea8d19f): `_bare_incoming_wire` reads "prints only a reference" word by word: every word after the incoming-wire label is a reference token (digits, a masked token, a month), a single letter or a wire label word (`_BARE_WIRE_LABEL_WORDS`, the one wire label list plus `TT` and `FROM`), so a funds-transfer row printing a reference and a holder-noise, generic, currency or legal-form word (`<n> BUSINESS`, `<n> USD`, `<n> PAYMENT`, `<n> INC`) keeps its own-account reading and is never counted as a wire from a named sender; true revenue's `credit_facts` blanks a bare row's payer region, so it is held as `wire_no_sender`; a numbered company after the `TT` label keeps the own-account reading, a recorded residual (true revenue spec §6.3, §7.11, §20).
- Audit round 2, R2-B11 (R44, R38, R33, R24, R09 part A, R29; 84fc5dc): `revenue_text` splits a reference's digits glued after a consumer rail's word (`_GLUED_RAIL_REFERENCE`, the rail's words one list, `_CONSUMER_P2P_RAIL_WORDS`), so CIBC's `E-TRANSFER<n> <sender>` is a person-to-person credit on every bank, as its spaced twin is, and Q4's holds reach it (debits keep their text); a person-to-person sender ends at Truist's `PAYMENT ID` label, so its `PAYMENT` never joins a person's name; a province word, its cut or BMO's code after a template reference keeps a numbered company's number only when no letters-only name word follows it (`_PROVINCE_NOT_A_NAME_START`, `_NUMBERED_TAIL_WORDS`); a short own-account source after `FROM` (`CHK`, `CHECKG`, `CK`, `SAV`, `SV`, `MMA`, `DDA`, `PCA`, `CL`, `LOC`, `LN`, `CRD`) designates the holder's account only before a number, a mask, `ACCOUNT`, `ACCT` or the row's end (`_DESIGNATED_ACCOUNT_SOURCE`; `_INTERNAL_ACCOUNT_SOURCE` unchanged), so a company named with those letters is a named counterparty; TD Canada Trust's per-transfer e-Transfer code is dropped from the text pass 7 and the census's facts read (`without_transfer_code`) and names no sender, payer key or counter-debit key; Square's folder hold is unchanged and documented (true revenue spec §5.2, §7.0, §8.4, §20).
- Audit round 2, R2-B12 (R37, R36, R17, R42; d691f36): B8's hold readers read a word as the payer's or the purpose's, never inside a customer's trade name (`_trade_name`: a payer region that prints a company form and a name word of its own, or a purpose with a name word right after the word), for the legal words (`LAWSUIT`, `LITIGAT…`, `CLASS ACTION`, `DATA BREACH`, Epiq, Verita: `_LEGAL_NAME_WORDS`, held beside a settlement, claim or award word), a casino's `JACKPOT` and `WINNINGS` (`_GAMBLING_NAME_WORDS`, held beside a gambling word) and the owner-money platforms `KRAKEN`, `UPHOLD` and `PAXOS` (`owner_money_platform`, which also spares any platform's vendor payment; the registry's table unchanged); a processor's or a carrier's `<word> SETTLEMENT SERVICES` is no title firm; an owner-shaped payer's accounts-payable or vendor `DISB` is no owner money; BigIron's deferral reads `BIGIRON` and `BIG IRON AUCTION(S)` only. The gambling reader reads a lottery's prize entry, six more sportsbooks and a sportsbook's, a casino's or an online gaming payer's withdrawal or payout, and the lottery's retailer spare reads the entry (`_layout_entry`, the premium reader's), never the agency's name. A recurring disbursement entry B7's I18 spare drops is counted and flagged as `named_payer_purpose_refused`, never verified, and a retirement account's is never spared; the census declares `q6_spared_disbursement_refused` on the pass's `spared_disbursement` fact. `RETIRE…` inside a payer's own name (before an operator's word, or ending TD Canada Trust's fifteen-character payer field before an electronic-payment CPA code) is no personal income (`_spare_retire_name`), the hold and G11 reading the statement's bank alike (true revenue spec §8.1, §15, §20).
- Audit round 2, R2-B12 review round 1 (b807319): `_trade_name`'s purpose arm never reads a word that names the purpose (`_TRADE_NAME_PURPOSE_WORD`: a win, a prize, a withdrawal, a cash-out, a transfer, proceeds, a recovery, money, funds, a refund, a payment, a settlement word, a sale or an account, a coin, a preposition, a possessive or a time word) as a trade name's, so `DES:LAWSUIT PROCEEDS`, `OBI KRAKEN WITHDRAWAL` or `FOR JACKPOT WIN` keeps its hold; the legal reader's keep words add `SERVICES`, `SOLUTIONS`, `RESTRUCTURING` and `GROUP`; `owner_money_platform` spares a platform named by its own name on §7.5's accounts-payable wording only, a bare vendor, invoice or payables word sparing only `KRAKEN`, `UPHOLD` or `PAXOS` alone; `_disbursement_entry` reads the hold text outside the payer's own name field on a row that prints one; and on a row with no entry field a lottery agency's `LOTTERY COMMISSION` supplies no retailer word (`_LOTTERY_AGENCY_NAME`), in the pass and the census's class F alike (true revenue spec §8.1, §20).
- Audit round 2, R2-B12 review round 2 (d79c906): the legal reader's settlement words are the classifier's own settlement spellings (`_LEGAL_SETTLEMENT_SPELLINGS`: `_SETTLEMENT_CREDIT`'s `SETTLE…`, `SETTLMT`, `SETLMT`, `STLMT`, `STLMNT`, and `SETL`), read as its context and keep words, so `DES:CLASS ACTION STLMT` holds as `DES:CLASS ACTION SETTLEMENT` does; `_TRADE_NAME_PURPOSE_WORD` adds those spellings, the payment cuts the statements print (`PYMNT`, `PMNT`, `PAYMNT`, `PAYMT` and the like), a handpay, a distribution's, proceeds' or a compensation's cut, a judgment, a redemption, the betting words, a rail, a currency and a staking reward; and a row a legal, gambling or owner-money reader holds with `_trade_name`'s purpose arm off and spares with it on (`purpose_trade_name`) is a refused word, counted as `named_payer_purpose_refused` and never verified by Q5 or Q6, the census recording the `purpose_trade_name` fact and declaring `q5_q6_purpose_trade_name_refused` (true revenue spec §8.1, §20).
- Audit round 2, R2-B13 (R34, R35, R39, R23; cc23c79): B7's I18 spares read `DISTRIB…` and `STOCK` as a name word only inside the payer's name proper (`_payer_name_proper`: a wire's sender or an ACH originator field whole; a transfer's or a person-to-person sender after `FROM` up to its first company form, or, with no form, only when a label or a reference closes it), never after an earnings, liquidating or pro-rata word or a glued month-year code (`_NOT_A_NAME_WORD_BEFORE`, `_PERIOD_CODE`), and read a street's name only after a street number (`_NUMBERED_STREET_NAME`; a deposit's location still reads `_STREET_NAME`), so an owner's distribution printed after the payer's name is held; a payer-less deposit's place, branch name or town that holds a kept financing word is removed only after the row's start, a number, the deposit's own words (`_DEPOSIT_LEAD_WORDS`), a word inside the classifier's check or cash, branch or ATM form, or a numbered address's street suffix (`_deposit_location_removal`), so a funder's name before a location still holds; the floor-plan lender's name reads `WHOLESALE` beside a lender's or a vehicle trade's whole word (`_FLOOR_PLAN_LENDER_WORDS`), never a customer's `FINE`, `CAPE` or `AUTOMATION`; and a company's direct deposit on a consumer entry is pay only when its receiver is no company (`_business_receiver`: a receiver field that prints a company form, or names a company-formed holder, is the business), the hold and G11 alike (true revenue spec §8.1, §20).
- Audit round 2, R2-B13 review round 1 (64bb5d5): `_business_receiver`'s holder arm reads the business only on the holder's whole company-formed name (`_holder_business_name`: every name word in order, its trailing form left off, printed or cut, or its last word cut by the bank's field; never a holder with a `DBA` or `AKA`), never `holder_named`'s looser reading, so a shorter run of the holder's name (the owner's own name leading a trade name), a DBA's person side, a middle initial or a reversed order on a consumer entry keeps the direct deposit's pay reading, the hold and G11 alike; a person-named formed holder read whole is a recorded residual with the owner beside Q8. A check, cash, branch or ATM deposit with no payer region keeps B7's number-free street name in the non-sale reading; `STORE` right after `BRANCH` (Wells Fargo's own deposit furniture) leads a deposit's place (`_DEPOSIT_LEAD_PAIRS`); the floor-plan lender's words add `FINCO`, `FINCORP`, `CAPCO`, `CAPCORP` and `AUTOFIN` (true revenue spec §8.1, §20).
- Audit round 2, R2-B14 (R16, R46, R14, R49; 8943fed): package mechanics only, no classification change. Of the copies of one repeated statement a package keeps the copy with a completed analysis, then the one analysed under the current rules, then the one carrying the analyst's review decisions, then the one listed first, and says why (`duplicate_kept_because`); the statement key never joins two accounts whose printed full numbers conflict; a shorter printout of days another counted statement of the account covers, every posted row of it printed there, is left out (`superseded_interim`), and any other overlap of one account's statements that shares credits is named (`overlapping_statements`) and sent to review, never netted; the upload queue matches its batch's files on their content hash (true revenue spec §9.2, §10.1, §10.8, §20).
- Audit round 2, R2-B14 review round 1 (b4ea8df): package mechanics only, no classification change. The package tests a printout of more than a month (31 days) first, the longest first, so a quarterly printout or a multi-month export whose every posted row the account's monthly statements print is left out (`superseded_long_printout`) and the monthly statements stay, each its own calendar month; the rest keep the shortest-first order (`superseded_interim`), so a full month is never left out for partial printouts of it; each overlapping pair names its account's currency (`overlapping_statements[].currency`), which the package downloads' section and words print (true revenue spec §9.2, §10.1, §10.8, §20).
- Audit round 2, R2-B15 (R13, R15, R54, R55, R50; 14e7d2d): package mechanics and the dashboard only, no classification change, no tier or total moves. A package's `months` is floored by the days each account's statements cover, as whole months of 30.4375 days, half up, so consecutive statements of one account or a statement longer than a month never read fewer months than their days (the Month/Year labels unchanged), and a statement's copied summary reads its monthly figures over the months its period covers; an account left out for another reason than a repeat is named (`filename`, `completeness` `partial`, `excluded_account_count`, an `excluded_account_<n>` download section, a dashboard notice) and sends the package to review, its membership unchanged; a package with no statement analysed publishes no True, Verified, Counted or Held figure, and a job still queued or processing is `pending`, never `failed`; `monthly_lender_debits` is the lender debits per calendar month; the dashboard counts statements and accounts apart (true revenue spec §9.2, §10.1, §10.4, §10.8, §20).
- Owner ruling 2026-10-02, R2-OW01 (the underwriter's Q12 and Q13; 8c78f05): §6.1 step 3a: a government payment that prints no purpose is `non_revenue` (`government_no_purpose`: one of the seven forms of `GOVERNMENT_NO_PURPOSE_FORMS`, the row read with the receiver's value removed and every field after it kept, American Express's template from its originator up to its id; method `government_no_purpose_exclusion`, rule `government_payment_no_purpose`, the form's key in `matched_alias`), after the direction conflict and the reversal and before every other rule, at any amount; no source type and no tier reason are added (R2-OW03, below, adds its display reason `government_no_purpose`), and a purpose printed anywhere or a form the ruling did not name keeps its reading (the GOV bullet above). The census's class G reads the seven forms (the Treasury form at medium confidence), class H keeps the forms the ruling did not name (and, since audit round 3, R3-B13: R3-55, every named form's other rows), `government_no_purpose` is a declared demotion and guard G19 fails a True credit printing one of the six other forms. The underwriter's Q13 changes no behaviour: `PROCESSOR_CARD_PAYOUT_RELEASE` and `CASH_APP_CARD_PUSH_RELEASE` stay off, so a processor's payout printed as a bare card credit stays a card refund (true revenue spec §2.1, §6.1, §6.3, §7.6, §7.11, §8.6, §14.2, §14.3, §17.1, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW02 (the underwriter's Q3; ecbcd28): every posted Zelle deposit is `non_revenue` with the reason `zelle_excluded` (method and rule `zelle_deposit_excluded`), whoever sent it, a lender or processor paying through Zelle included. `true_revenue.zelle_deposit` reads the Zelle rail on the revenue text before the receiver fields (`ZELLE` with no letter on either side, a glued date or reference included, or PNC's `ZEL FROM|TO`; never `HAZEL`, `ROSZELL`, `MAZZELLA`, `ZELLER`) (Amended by audit round 3, R3-B12: R3-12 and R3-56, below: it reads the pass's own text, `true_revenue.pass_text`, where PNC's `ZEL` is spelled `ZELLE`, and never an incoming wire or a loose wire's originator row whose memo prints the word; review round 1 records the other wire layouts as residuals), and pass 7 excludes such a row as its last tier step, after Q5, Q6 and every hold and before the $1 floor: a count, a verification or a hold (round-sum repeats, the holder's name, a payer also debited, financing, a payer debited as a lender, the floor's) becomes the exclusion, the rules' own tier and reason kept in the reason sentence and the `zelle_prior:<tier>:<reason>` context signal (`zelle_prior_reading`). A row a non-revenue rule decided (a refund, a reversal, an opposite-direction pair, an own-account transfer, a listed funder's financing proceeds with the lender-credit exclusion, a non-operating credit) keeps that rule and no reason; a direction conflict keeps its hold. The legacy classification, the entity, the flag group, the lender fields, the withholding flags and the debits are unchanged; `_CONSUMER_P2P_RAIL` is unchanged; the other person-to-person rails keep their reading. `REVENUE_TIER_REASONS` ends with `zelle_excluded` (tier `non_revenue`), mirrored by the dashboard; the dashboard's statement of the exclusion and the confirm valve landed with R2-OW03 (below). The census declares a Verified Zelle row the policy excluded as `zelle_policy`. The underwriter's Q3b (no-sender e-Transfers' round-sum repeats) is ruled and held back from the code: the real-statement pin it would move moves only on the owner's word (true revenue spec §2.1, §5.3, §8.4, §8.10, §17.1, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW03 (the underwriter's Q3: the dashboard states the Zelle exclusion and the underwriter may confirm a Zelle deposit; the Q12 card's open point 2; ef5ed20): one mechanism for every `non_revenue` reason code. `NON_REVENUE_REASONS` is the codes `REVENUE_TIER_REASONS` files under `non_revenue` (`zelle_excluded`, then `government_no_purpose`, "Government payment, no purpose printed", which pass 7 gives a row of method `government_no_purpose_exclusion` where it sets its tier: display only). `non_revenue_by_reason` (`{code: {count, total}}`) is computed by one rule in the metrics and the rebuild, nulled before 5.6 with the tier figures, carried by every package document row and the package totals (kept members only; never nulled where revenue is not established or no statement was analysed; its money refused, its counts kept, under a currency refusal) and exported as `non_revenue.<code>.count` / `.total`. The dashboard: the True card's "Zelle deposits excluded: <money> (<n>)", the Non-Revenue evidence sub-rows and their `non_revenue:<code>` filter, the tag "Non-revenue: <label>" with its sentence, the Monthly Statements' "Zelle excluded <amount>" under the True cell, the copied summary's ", of which Zelle deposits excluded <money>" and the Non-Revenue notes naming Zelle deposits. The review: `REVIEWABLE_NON_REVENUE_REASONS` (`zelle_excluded`) rows take a confirm (Verified, the reason kept) and a reset, never a reject; the re-analysis replays a confirm and reports a stored reject as decided by the rules; the row shows Confirm Revenue only. No tier, figure or gate moves (true revenue spec §2.1, §5.3, §9.1, §9.2, §10.1, §10.2, §10.5 to §10.8, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW04 (the underwriter's Q8: lease-to-own and patient-financing payouts; a93aedc): `CUSTOMER_FINANCING_PAYERS` names Snap Finance, Koalafi, Cherry Technologies, Acima, Terrace Finance, Wisetack, Katapult and Progressive Leasing (each a ledger entity; Wisetack a rejected record kept as evidence), read on the payer region (a bare `CHERRY` only as the whole region with company or entry words; never `KATAPULT ENGINEERING` or `KATAPULT PRO`; `SNAP LOAN FUNDING` only in Snap's `F<n> <merchant>` form, which the strong LOAN rule reads out). Pass 7 claims such a credit (a wire, an ACH or EFT or an unlabelled row of $1 or more with no consumer-side word, no class-action word and no consumer entry to a person) as it claims a payout entity's: `counted_flagged` / `customer_financing_payout`, never verified (an earlier verification is overruled, method `customer_financing_payer`), never a Q5 or Q6 repeat, nor is any row naming one of them (`CUSTOMER_FINANCING_NAMES`). After the tiers and before the Zelle step, a payout of $10,000 or more by wire, in whole thousands or at least half the statement's posted credits, that is not one of three or more payouts of at least half its size from that financier, is held as `customer_financing_lump_sum`. Cherry Technologies joins `PAYOUT_CREDIT_ENTITIES` under OQ2's consumer-side veto. Debits, lender, withholding and flag readings are unchanged (true revenue spec §2.1, §5.3, §6.3 narrowing 12, §8.9, §8.10, §15, §17.1, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW05 (the underwriter's Q9, part (c'): an auto lender's payables need dealer evidence; 207530a): a listed auto lender's credit Q7 verified on a payables word alone (`PAYABLES`, `TRADE PAY`, `ACCT FUND`) stays Verified only when the statement shows dealer evidence (`_dealer_contract_evidence`: a dealer-worded Q7 credit or a credit union's `VHCL PURCH`, a floor-plan financier's row or a `FLOOR PLAN` form, a debit naming a dealer-only wholesale auction, or a dealer word in the holder's name that prints no recovery, repossession, towing or collateral word). Otherwise the true-revenue pass, after the factoring, own-push and financier demotions, counts it as `lender_paid_for_services` (method `lender_paid_for_services`, rule `q7_payables_without_dealer_evidence`, never verified), or holds it as `financing_named_payer` when the hidden-loan guard (`_payer_collects`: any lender or other posted debit naming the payer, the bank's receiving fee and a card charge aside) reads the lender collecting from the account. Its lender fields, every lender flag and every debit are unchanged (true revenue spec §5.3, §8.7, §8.10, §14.3, §17.1, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW06 (the underwriter's Q11: builder progress draws and asset sales; fcf5d4f): (a) `construction_progress_draw` reads a builder on the payer region (`_BUILDER_PAYER`), `DRAW` outside the payer's own name proper, no own-loan draw (`_OWN_LOAN_DRAW`), no bank, title, owner-shaped or financing-root payer and no Zelle rail; on a row nothing claimed the payer facts set `CreditFacts.progress_draw`, the non-sale test spares `DRAW` alone, Q5 and Q6 never read the row, and it is counted as `construction_progress_draw` right after the financier arm. (b) `ASSET_SALE_PAYERS` (equipment auctions and consumer car buyers, read as the whole payer name; `ASSET_SALE_SELLER_WORD_ONLY`: Copart and IAA) and the printed asset-sale purpose (`asset_sale_reading`) make a row `non_revenue` with method and reason `asset_sale_proceeds` (rule `asset_sale_payer` or `asset_sale_purpose`) on a statement with no dealer evidence (`_dealer_statement`: R2-OW05's `_dealer_activity`, a §7.8 auction's payout credit, or `_ASSET_TRADE_HOLDER` on the holder's names without `_DEALER_HOLDER_VETO`), read on the unverified rows and on a vehicle sale an invoice or customer-payment descriptor verified (`ASSET_SALE_INVOICE_METHODS`); a held tier keeps the row held, and the row has no review path. `REVENUE_TIER_REASONS` gains `construction_progress_draw` (after `lender_paid_for_services`) and `asset_sale_proceeds` (last), which `non_revenue_by_reason` counts; the census declares the demotion `asset_sale_proceeds`. Every debit, lender, withholding and flag reading is unchanged (true revenue spec §2.1, §5.3, §6.2, §8.1, §8.10, §14.1, §15, §17.1, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW06 review round 1 (the underwriter's Q11; e843c09): a realty firm on the payer region (`REALTY`, `REALTOR(S)`, `REAL ESTATE`) is no builder and a commission draw (`COMM`, `COMMISSION` or `COMMISSIONS DRAW`) is no progress draw, both keeping the non-sale hold; a builder's progress draw §7.5's accounts-payable remittance verified is counted, never verified (method `construction_progress_draw`, rule `construction_progress_draw_never_verified`), after the asset-sale demotion; `FLEET` alone is no asset noun of a sale (a fleet card's `FLEET SALE` keeps its reading); a commission or a fee next to a printed sale keeps the row out of the asset-sale purpose; IAA's insurer-name hold yields to Q11 only where no later hold would name the row (`CreditFacts.hold_past_insurer_name`). The census records `payer_key_digest` (a digest of the channel and payer key, never a name) and declares `construction_progress_draw_never_verified` and `q5_q6_q11_repeat_partner` (a Q5 or Q6 repeat whose same-payer row is an asset sale or a counted progress draw). No corpus row moves (true revenue spec §8.1, §8.10, §20).
- Owner ruling 2026-10-02, R2-OW07 (audit I26, by Q6 of 2026-09-28 and the last sentence of the underwriter's Q2 (2026-10-02) option the owner picked, "a one-off claim paid to a business on its own policy stays out"; not asked in the Q2 question; 28d7167): the insurer-name hold reads `insurer_payer_reading`, which covers every insurer spelling on the payer region without the holder's own names: `_INSURER_NAME`'s spelled-out words (unchanged), `_INSURER_SPELLINGS` (`INS`, `ASSUR`, `MUTUA`, `CASUALT…`, `INDEMN…`, `ASSURANCES`, `ASSURANT`, `ASSUREUR`, `P AND C` at a name's end, `LOSS PMT`, `SUBRO…`; never `ASSURED`, `P AND C FOODS` or `CLM`), the registry's credit-only `INSURER_CREDIT_BRANDS` (nine carriers that print no insurer word; no classifier rule, debit, flag or lender reading reads it) and `CLAIM`; an `HCCLAIMPMT` entry, a premium financier and a premium-finance wording are no insurer, a government payer is one only by the spelled-out words or `CLAIM` (never for work; review round 1), a listed insurer's credit stays the insurance rule's, a title firm with an insurer word is a title insurer, a healthcare payer is read only by the spelled-out words and a §15 deferred payer only by those words or `CLAIM`. A credit so read is held as `insurer_named_payer` (before the pay hold), and the census declares a Q5 or Q6 repeat it holds as `q5_q6_held_insurer`. Measured on the re-parsed basis: 39 rows leave True for Held, 5 of them Verified; none enters True and none moves to or from `non_revenue` (true revenue spec §7.7, §8.1, §17.1, §19.1, §20).
- Audit I26, R2-OW07 review round 1 (by Q6 of 2026-09-28 and the MCA principle; 3fdb67e): a government payer is an insurer only by the spelled-out words or `CLAIM` (never on a healthcare payer) and never for work, so a government insurance programme's credit (employment, parental, disability or family-leave insurance, a public insurer) stays held `insurer_named_payer` as before I26, never counted or Verified (amended by audit round 3, R3-B13: R3-11, below: a listed insurer is read first); on a person-to-person rail only the spelled-out words and `CLAIM` read (narrowed by R3-B13, R3-57, below: a consumer rail only); `SUBRO` reads `SUBRO` and `SUBROG…` only (never `SUBROTO`); a brand's and `P AND C`'s `INS` is `INS`, `INSU` or `INSUR…` (never `INSTITUTE`, `INSTANT`, `INSTRUMENTS`, `INSTALLATIONS`); Travelers' property line only before an insurer word or at the name's end. Recorded: an insurer's printed asset sale is held as the insurer (R2-OW06's precedence reads every spelling; qualified by R3-B13, R3-64, below: a row the Q2 release re-states is read by Q11 (b)), and a row whose only insurer reading was the holder's own name is counted where no later hold names it. No corpus row moves (true revenue spec §8.1, §20).
- Owner ruling 2026-10-02, R2-OW08 (the underwriter's Q2, "True revenue", option 2: insurers paid for the business's work; c1acc3e): before the payer facts, pass 7 re-states an insurer's credit paid for the business's work (`_insurer_for_work`) as an unverified deposit of method `insurer_paid_for_services`, unclaimed, so the insurer-name hold passes over it and every later hold still reads it; where none names it the tier is `counted_flagged` / `insurer_paid_for_services`, never verified and never a Q5 or Q6 repeat. Eligible: the insurer reading is for work (never a title insurer or a government payer), nothing claimed the row, $1 or more, an agreeing direction, an unverified deposit or the insurance rule's `non_revenue`, and no premium, refund, return, dividend, cancellation, unearned, overpayment, member, subscriber or personal-benefit word on the payer or the purpose (a wire's purpose fields, never its `REF`) unless a commission form prints there (amended by audit round 3, R3-B13: R3-10, below: the personal-benefit words read were the four stems `DISAB…`, `INVALIDIT…`, `ANNUIT…`, `PENSION…` alone; corrected, audit round 3, R3-B13: R3-58, below: the service form never reads a wire's `REF`, but the classifier's customer-payment wording, the service-form ground's other reader, does). Grounds, the first that applies: the holder's trade (`_SERVICE_TRADES`, strict, one credit; `_SERVICE_TRADES_LOOSE` only with two eligible insurer credits), a service form (`_INSURER_SERVICE_FORM`, or the classifier's customer-payment wording before the receiver fields), three or more credits of one insurer key within an inclusive 31-day span; another insurer's one-off only with `INSURER_FOR_WORK_STATEMENT_ARM`, off. On a released row the non-sale test reads no `CLAIM`, and `CounterCredit.insurer` is False (B4's bill clause; on R2-B02's `CounterCredit`). `REVENUE_TIER_REASONS` gains `insurer_paid_for_services` after `construction_progress_draw`; the census declares narrowing `15_insurer_paid_for_services` (counted only) and the demotion `insurer_paid_for_services`. Every debit, lender, withholding and flag reading is unchanged (true revenue spec §2, §2.1, §5.3, §6.3, §7.7, §8.1, §8.6, §8.10, §14.3, §17.1, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW09 (the underwriter's Q9, "Keep them as true revenue", option 2: finance-named customers, rent received and lenders paying for services; 78b066c): `financing_named`'s reading moves whole into `_financing_root_places` (each place a root fires: the payer reading, its special arms marked, the entry reading, a payer-less row's reading; `financing_named` is whether any fired, unchanged, and the census's `financing_root` and `hold_rule` facts with it). On an unverified credit nothing claimed, `finance_named_release` lifts the root arm alone: (a) `finance_named_customer`, or (c) `lender_paid_for_services` where the payer's name reads as a lender's (`_LENDER_NAME_WORD`, a label only) or a listed auto lender originates the row, when the root is on the payer's name alone and the line prints §7.5's accounts-payable, vendor-payment or invoice wording or `COMMISSION(S)` (the orchestrator's extension under the underwriter's Q10), never a bank-only payer (`_bank_only_payer`) and, on a layout with no entry label, never two roots or a root at or after the payer's first company form (`_labelless_root_refusal`); (b) `lessor_rent` when every place is a rent `LEASE` alone (`_RENT_LEASE`; a payer place only as a memo after its company form) on a statement `_lessor_business` reads as leasing or property (a trade word on the holder's names, a property-management platform's credit, two or more distinct rent payers; never a payer-less transfer, person-to-person, wire or Zelle row); never a `PROCEEDS` or disbursement line, and never a payer the statement debits (`_payer_collects`, a documented over-hold). `_first_hold` passes over the root arm on a released row (`released`); every other financing arm and every later hold still read it, and `CreditFacts.q9` is set only where none names it; Q5 and Q6 never verify or count it, and `_tier_reason` relabels its counted reason last, after the unread branch, keeping `_Q9_KEEPS`. `REVENUE_TIER_REASONS` gains `finance_named_customer` and `lessor_rent` after `insurer_paid_for_services`. A registered lender's vendor-worded credit stays D1's financing proceeds (an owner question). Every debit, lender, withholding and flag reading is unchanged (true revenue spec §2.1, §5.3, §8.1, §8.7, §8.10, §17.1, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW10 (the underwriter's Q10, its parser half: the account's printed title; e9fe8ec): the holder readers return the title they drop after the holder's name (`HolderReading`: what the cut after the name's last legal form, or of a trailing designation ending in `ACCOUNT`, leaves out, and in a mailing block a name line the reader does not keep that prints an account word or the premium-trust words and opens on no contact marker), and every holder reader's parser publishes it as `Statement.account_title` from the same anchor, serialized only where it is set and outside the extraction schema. The holder's names, the holder tests, every transaction and every tier are unchanged; no rule reads the title yet (R2-OW11 holds a premium trust account's deposits) (true revenue spec §9.1, §20).
- Owner ruling 2026-10-02, R2-OW11 (the underwriter's Q10, "Hold every deposit into an account titled "premium trust""; 1158b09): `premium_trust_title(account_title, account_name, holder_name)` reads the statement's own fields, never a row: the bank's designation (`Statement.account_title`) in three forms (the title at the field's end, the words followed by an account word, the words and an account or product word before a separator; never the words anywhere), then the account name and the holder's name (the account-word form refused on a field that ends in a legal form). `classify_statement_transactions` passes it to pass 7 (keyword `premium_trust`), whose step after the $1 floor holds every credit a rule verified or counted as `premium_trust_account` (`_held_in_premium_trust`: a verified one leaves verification with method `premium_trust_account`, a counted one keeps its state, method and rule); held and non-revenue credits keep their reading. `Metrics.premium_trust_account`, the package's `premium_trust_documents` and the True card's fact carry it; the census records the account's `premium_trust` flag, guard G20 and the declared demotion `premium_trust_account`. Every debit, lender, withholding numerator and flag reading is unchanged (true revenue spec §2.1, §5.3, §8.10, §9.1, §9.2, §10.1, §14.3, §15, §17.1, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW12 (the underwriter's Q1, "Held for review"; d9878f0): every wire with no sender printed stays held as `wire_no_sender`, and pass 7's last step, after the $1 floor and the premium-trust hold, records on each such held credit `revenue_funding_series` (`funding_series_after`: a tuple of `FundingSeries`, the Lenders or Potential Lenders series that start after the deposit; `FUNDING_SERIES_WINDOW_DAYS = 10`, `FUNDING_SERIES_MIN_PAYMENTS = 2`, `FUNDING_SERIES_MIN_LOOKBACK_DAYS = 3`). `apply_true_revenue_pass` gains the keyword `statement_start` (the printed period start), which `classify_statement_transactions` passes; the statement passes and their order are unchanged. The dashboard prints one "possible funding" line per series under the reason; the census counts the aid (`funding_series`, `funding_series_observed`, `funding_aid`). No tier, reason, figure, gate, debit, lender, withholding or flag reading moves (true revenue spec §2, §2.1, §5.4, §6.2, §8.5, §9.1, §10.7, §17.1, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW13 (the underwriter's Q5, "Match the return to the funder payment it reverses"; 2d81484): a confirmed funder's payment the bank returned unpaid leaves paid to lenders (`contributes_to_lender_totals`) and keeps `contributes_to_withholding_rate` and `contributes_to_lender_count`; the debit carries `returned_funder_payment_by` (the return credit's location, a returned-unpaid sentence on its reason) and the credit `returns_funder_payment` (the debit's location), two record fields right after `settlement_reversal`. A lender-side reversal pair (classification 5.4's markers, as before) whose debit is a confirmed funder's paid payment now keeps that count and withholding; every other debit is zeroed as before. After the true-revenue pass and before the duplicate finalisation, `_apply_returned_funder_payments` (rule D, spec §6.2 pass 7b) pairs a credit out of True (`non_revenue` or held) that prints a bounce form (`_RETURNED_PAYMENT_CREDIT_PATTERNS`: Bank of America's `RETURN OF POSTED CHECK|ITEM`, `ITEM RET`, `RET NOT PAID`, `RTN`, `NSF`, `UNPAID`, `NOT PAID`, `REJECT(ED)`, `RETURNED ITEM|ACH|PAYMENT|DEBIT|PAD|CHECK|CHEQUE|EFT|ENTRY|DR` in either order, `CREDIT RETURNED`, and R2-B08's French `EFFET RETOURNE` and `REFUSE SANS PROVISION`; the short codes never before a legal-form word, never a fee word) with a confirmed funder's paid debit of equal cents dated 0 to `RETURNED_FUNDER_PAYMENT_WINDOW_DAYS = 7` days before it (undated: printed before it): the debit dated on Bank of America's `RECEIVED ON` day first, then the latest, then the nearest row; skipped when an equal non-lender debit is as near or undated; a credit the revenue side paired only with its partner, and a credit naming a confirmed funder only with that funder's debits; each debit once. It sets no `reversed_by` (the reconciliation's reversal coverage, the settled-activity counts and the NSF count are unchanged) and moves no revenue field. Metrics: `lender_debits` stays paid, `returned_funder_payment_total` / `_count` / `_evidence` are new, and `withholding_numerator` is paid plus returned; detection lists `returned_funder_payments` and each funder's `returned_payment_count` / `_total`, and a funder whose every payment bounced stays listed; the package sums its members' numerators; the dashboard warns per returned payment. G7 declares the moves (`returned_funder_moves`, `kept_in_count_returned`). No tier, reason, True or Verified figure moves (true revenue spec §2.1, §6.2, §9.1, §9.2, §10.1, §10.6, §11, §14.3, §17.1, §19.1, §20).
- Owner ruling 2026-10-02, R2-OW14 (the underwriter's Q7, "2 Make True revenue the default"; 0aeb015): `DEFAULT_WITHHOLDING_DENOMINATOR_MODE = "true_revenue"` (`analysis/revenue.py`) is the withholding basis `Settings`, `load_settings` (an unset, empty or unknown `WITHHOLDING_DENOMINATOR_MODE`), `compute_metrics`' keyword and the `Metrics` dataclass take; `normalize_withholding_denominator_mode(value, default="legacy_eligible_deposits")` keeps reading a stored payload's missing mode as legacy. The legacy and verified bases stay selectable and `legacy_eligible_deposits` stays published; the note on a basis of $0 names it ("withholding rate is unavailable because True revenue is zero or missing"); the dashboard's "Eligible Deposits" card is "Withholding Basis" and the rate notes name the basis (see "Withholding rate"); the CLI's working lines name it; the lender census pins the legacy basis. The cash, branch and ATM form (`_CASH_BRANCH_ATM_FORM`) gains two last alternatives, so their rows are `counted_flagged` / `no_payer_printed`, never Verified, as Q2 of 2026-09-28 reads every cash deposit: a retail cash load printed `... US<RETAILER> W<n>` at the row's end (`_RETAIL_CASH_LOAD`: Walgreens, CVS, 7-Eleven, Walmart, Dollar General, Rite Aid, Family Dollar, Circle K; inferred from Bluevine's shape) and a branch deposit printed `DEPOSIT <place> <5-digit transit> <3-digit sequence>` as the whole row with no legal form (`_BRANCH_DEPOSIT_TRANSIT`, Scotiabank's). No other credit's reading and no debit moves (true revenue spec §2.1, §8.2, §10.1, §10.5, §11, §14.3, §17.1, §19.1, §20, T8).
- Owner ruling 2026-10-02, R2-OW15 (the underwriter's Q6, "2": "Flag, but do not deduct, returns that cannot be matched and processor chargebacks"; 4125f30): `processor_chargeback_debit(text)` reads a debit's text as a processor's chargeback (`CHARGE BACK(S)`, `CHARGEBACK(S)`, `CHBK`, `CHGBK`, `CHG BACK`) or adjustment (`MERCH ADJ…`, `MERCHANT ADJ…`, `FINCL ADJ`, `BANKCD ADJ`), never with a fee wording (`FEE(S)`, `FRAIS`, `SVC CHG`, `SERVICE CHARGE`, `CHRG`, `CHG` and `CHARGE(S)` other than before `BACK`) and never a returned deposited item (`_deposit_return_debit` reads first). It is a flag's reader only: no classification, tier, figure or lender reading reads it, and the classifier's records are unchanged. `analysis/revenue_view.py`'s `debit_side_flags` reads a statement's serialized rows (it imports the classifier's readers, never serialization): a posted, non-duplicate debit that undoes a deposit and that no credit of the statement pairs (`unmatched_deposit_return`), and a posted, non-duplicate processor chargeback or adjustment with no lender, potential-lender or withholding contribution and no financing, card-payment, insurance, tax or payroll class (`processor_chargeback`, with its wording). The served copy of a statement carries `<kind>_count`, `<kind>_total` and `<kind>_locations` where a debit is flagged, never deducted. A package's passes (`webapp/app.py` `_package_matches`, after R-d) match a return its own statement cannot pair to the nearest equal deposit-channel deposit in the same account's immediately preceding statement (no day cap inside it; `PACKAGE_CONSECUTIVE_DAYS = 7` between the statements) and take that deposit out of the package's True as `non_revenue` (method `matched_reversal_pair`, rule `returned_deposit_cross_statement`), on new copies of the members' rows, never written back; pass 4, R-d, every debit and every statement figure are unchanged (true revenue spec §2.1, §6.2's package passes, §9.1, §9.2, §10.1, §11, §17.1, §19.1, §20).
- Audit round 3, R3-B24 (R3-16; d2f209e, 9a5e610): a large counted deposit whose source the statement does not prove is flagged for information, beside R2-OW15's served debit flags, and no classification moves. `analysis/revenue_view.py`'s `large_unsourced_deposits` reads a statement's serialized rows: a posted, non-duplicate `counted_flagged` credit whose reason is one of the eight that name no proven source (`no_payer_printed`, `check_deposit`, `wire_named_sender`, `named_payer_one_off`, `numbered_company_payer`, `p2p`, `named_payer_unlabelled`, `payer_text_not_read`), of $10,000 or more and strictly more than 25% of the statement's True revenue (in integer cents), each with its share of True. The served copy of a statement whose revenue is established carries `large_unsourced_deposit_count`, `large_unsourced_deposit_total` and `large_unsourced_deposits` where one is flagged; a package lists each member's over the rows it counts, each share its own statement's True as the package counts it (its holds applied, the True Deposits its row shows on the package page; R3-B24 review round 1); the downloads, the batch CSV, `analyze.py` and the dashboard name them. No classification, tier, reason, figure, review gate, badge or decision reads them, and nothing is stored (true revenue spec §9.1, §9.2, §9.3, §10.1, §10.6, §10.7, §10.8, §13, §17.1, §20).
- Owner ruling 2026-10-02, R2-OW16 (the underwriter's Q4, "Let's go with option 2 and I'll review it anyways"; 3e6b2b6): `paper_or_cash_deposit(text)` reads, on a credit's text before its receiver fields (`_before_receiver` of `revenue_text`), a check deposit (`_CHECK_DEPOSIT_FORM`), a cash, branch, teller or ATM form (`_CASH_BRANCH_ATM_FORM`) that prints a cash device's word (`_CASH_DEVICE_WORD`: `ATM`, `ABM`, `CASH`, `COIN`, `SMART SAFE`, `CPS DEVICE`, `CURRENCY PROCESSING`, `NIGHT DEP…`, `NIGHT DROP`, `VAULT`, `PRE ENCODED`) or R2-OW14's retail cash load (arm R); a teller, counter or branch deposit printing none is no paper or cash deposit. It is a package pass's reader only: no classification, tier, figure or lender reading reads it, and the classifier's records are unchanged. A package's pass 2 (`webapp/app.py` `_package_matches`, after pass 1) holds a counted deposit that prints no payer (`counted_flagged` / `no_payer_printed`; never a rail, a round sum or a paper or cash deposit) matched to an exact-cents transfer out (a posted, dated debit printing transfer wording, no rail, no lender, potential-lender, withholding or flagged contribution, none of the financing, card-payment, insurance, tax, payroll or fee classes) of another of the business's accounts (`_different_accounts`: another member, one currency, both printing four digits or more that differ in their last four or conflict) 0 to `PACKAGE_TRANSFER_DAYS = 2` days before it, unless the debit prints another destination account (`TO CHK 9999`): the deposit reads `excluded_pending_review` / `own_account_transfer_matched` on the package's copy, its state, initial state and pending status kept, so Confirm Revenue releases it (and marks it Verified, §10.7); a held deposit naming no third party (`transfer_no_counterparty`, `transfer_account_designation`, `holder_name`, `wire_no_sender`) that pairs the same way is annotated only. A member printing fewer than four account digits is marked `no_account_number`. R-d, pass 4, every debit's reading and every statement figure are unchanged (true revenue spec §2.1, §6.2's package passes, §8.2, §9.2, §10.1, §10.6, §10.7, §11, §17.1, §19.1, §20).
- Owner ruling 2026-10-06, R2-OW17 (the owner's amendment of 2026-10-06 to the underwriter's Q3; b98076d): the Settings choice "Mark Zelle Payments as True Revenue" (`webapp/settings.py` `zelle_true_revenue`, Yes by default, a display setting). `apply_true_revenue_pass`, `classify_statement_transactions` and `guard_facts` take `zelle_true_revenue` (default False, the stored reading): True skips the Zelle step and lifts the builder-draw and asset-sale carve-outs (`construction_progress_draw`, `asset_sale_reading`), the lessor fact keeping its Zelle skip. `classify_statement_readings` gives both readings (the shared prefix once; None in second place when no credit prints the Zelle rail, `zelle_credits_present`); the pipeline builds the counted reading's metrics and detection beside the stored ones (`Report.zelle_counted`), and `report_to_dict` stores the account key `zelle_counted_reading`, the lean edits to it (`analysis/zelle_view.py`). The served copy applies the setting first (`apply_zelle_view`: the reading, `metrics.zelle_deposits` and, under Yes, the row tag `zelle_deposit`); the review writes both readings (`with_both_readings`: validated on the reading shown, the latest decision on a posting setting every reading), the audit's prior state is the reading shown and the replay follows the same rule; the package sums `zelle_deposits`; the downloads write readable `zelle_deposits.*` rows and a `zelle` column; R2-OW16's deposit test refuses the Zelle rail; `analyze.py` and `batch.py` take `--zelle-true-revenue`; the censuses read one reading, refuse mixed snapshots unless declared, and check G-Z and G7's rule D (true revenue spec §2.1, §5.3, §8.1, §8.4, §8.10, §9.1 to §9.3, §10, §11 to §14.3, §17.1, §19.1, §20).
- The owner's request of 2026-10-06 (lender payment changes; owner request 2026-10-06 (R2-OW18); 551c90b): "can we also detect when a payment to lender has decreased? That would be a really important metric to track." Clarified: "Decreases, increases, stops", "Sustained, 10%+ drop", "Confirmed + potential". Information only: `analysis/lender_payment_changes.py` reads the classification records (or their serialized dicts) and returns new items, and nothing it returns feeds a lender, withholding, revenue, flag or gate figure. A series is a confirmed funder's paid debits (`canonical_entity`) or a potential lender payee's (`potential_payee_key`): posted debits with the paid flag (`contributes_to_lender_totals` or `contributes_to_potential_lender_totals`) and no `duplicate_of`, `reversed_by` or `returned_funder_payment_by`; a bounced or reversed debit of the series is an attempt (presence, never an amount or a payment; since audit round 3, R3-23, an attempt at a level's amount also keeps its schedule when the dates together read a faster regular schedule that keeps its cycle: a daily one needs 60% of its dates or more in stretches of 5 consecutive business days holding 4 or more of them, more than NACHA's 3 presentments of one debit fill (R3-B04 review round 1), and, of the intervals between its paid dates with 3 business days or more inside, one at least and 60% holding 3 attempts or more, more than one debit's chain holds before its paid one (R3-B04 review round 2), so a weekly debit whose chains each end paid before the next week's entry never reads daily, while one whose chains are returned three times or re-presented past the next entry can, and a biweekly or monthly debit re-presented at weekly steps reads weekly, its dates being those of a weekly debit whose other presentments bounce). Its amounts form levels (equal cents, 1% merges, 2 or more payments; one payment is a one-off) with a cadence (`payment_cadence`: daily, weekly, biweekly, semi-monthly, monthly, daily irregular, irregular), concurrent levels separate positions, a level running alongside a schedule-confirmed level, or a position, under 5% of the series' weekly weight is a fee stream and is dropped (the level test since audit round 3, R3-24), and each position's regimes (a regular level held 2 or more payments; catch-up multiples of 2 or 3 times the main amount and short off-schedule regimes set aside; since audit round 3, R3-70, a 2x or 3x run of 2 at a schedule slower than the main level's is no catch-up but a possible change at a new schedule, the main level read on its payments' own schedule while it is still presented through the run and on its cadence once it no longer is, R3-B04 review rounds 1 and 2) are compared with the last reported level of the position: a decrease or an increase of 10% or more (on the weekly equivalent across schedules), a schedule change (confirmed by 3 payments, 5 if daily, over 80% of a cycle; a decrease or increase held 2 payments at an unconfirmed schedule is a possible one, "new schedule not yet confirmed"), a pause inside one regime longer than the grace window, a new concurrent stream raising the weekly total by 10% or more, and a stop after 3 or more payments with no payment, payment-sized debit (5% to under 2x), catch-up (since audit round 3, R3-25: a one-off within 2% of exactly 2 to 6 times the payment, presence for pauses, restarts and stops alike and never a payoff) or attempt for longer than the grace window (5 business days daily, 6 daily irregular, 10 weekly, 15 biweekly or semi-monthly, 25 monthly) before the covered period ends; business days follow the Federal Reserve's holidays, or Payments Canada's on a CAD statement. A change names a credit of the series' entity from 20 days before to 5 days after the new amount's first payment as a possible renewal, never (since audit round 3, R3-82) one that returns or reverses a payment, one within 1% of the change's own payment amounts or of a payment or attempt of the series 0 to 7 days before it, or one dated on or before the first payment of the regime just before the new one; a new stream names each other stream at the level it was paying when the new one began (R3-81). A potential series under $100 a week gives no item. `detect()` stores the statement's items as `detection.lender_payment_changes` (in each Zelle reading), the package reads each account's consecutive statements together (`webapp/app.py` `_package_lender_payment_changes`; a series' payment or attempt in another account of the package continues a stop, which is then never confirmed, only within the stop's grace window counted in the business days the two accounts' statements cover, and a later one is named apart, "reappear in another account", since audit round 3, R3-83), and the CLI, the batch CSV, the downloads and the lender census's new outputs publish them. The record gains `potential_payee_key` (below); no classification, contribution flag, reason, label or pass changes (true revenue spec §2.2, §9.1, §9.2, §10.1, §10.8, §11, §14.3, §17.1, §19.1, §20). R2-OW18 review round 1 (a4d9b7c): a change reached through unreported levels names each with the step into it and the last step (`via[].change_percent`, `last_step_percent`), never "steps of under 10% each"; a pause names what ended it (`first_after_kind`: `payment`, `attempt` or `other_amount`, and since audit round 3, R3-25, `catch_up`, with `first_after_amount` and `first_after_multiple`) and the date payments resumed (`resumed_date`), and since R3-B05 review round 1 each catch-up after what ended it, before payments resumed (`catch_ups_inside`), and a pause or a stop whose presence is a bounced attempt reads "no payment or payment attempt"; a restart's pause leaves out the days no statement of the chain covers; a stream whose previous cycle falls before the covered period or in a hole is no new stream; a payment taken as two debits on one day still reads as a change (a known shape, §17.1 point 29).
- Audit round 2, R2-L01 (R43, carried over from R2-B03; b02a930): the ledger admits Liberis US Inc, an embedded revenue-based financing provider (white-label platform capital such as Vagaro Capital, its US fundings paid through Airwallex US, LLC), as an alternative position, platform-embedded financing like Parafin, after an independent verify round (r2) recorded in the ledger, with the aliases `LIBERIS` and `LIBERIS US INC`: a Liberis credit (`LIBERIS <reference> ACH IN`, an Airwallex instant payment naming `LIBERIS US INC`) is `non_revenue` financing proceeds (D1) and a Liberis debit an alternative position. `AIRWALLEX` is never an alias, Vagaro keeps its platform reading, and no reader or tier rule changes (true revenue spec §8.1, §20).
- Audit round 2, R2-B16 (R51, R53, R52; e0eb9cb, 728515a, a869554, e17ad7c, e26e322): the surfaces only, no classification change and no tier, reason or figure moves. The Monthly Statements table names its units on the chart's rule (in a package that refuses to combine its currencies every declared row names its unit, USD included, and an undeclared row stays bare); the statement CSV/XLSX list every posted debit on its own row after the credit table (its classification, the flag group where Settings shows it, the entity, the review flag and the credit that returned a confirmed funder's payment unpaid), and an XLSX cell over the spreadsheet's 32,767-character limit holds a pointer to the JSON download; the CLI reads the dashboard's revenue rules (`analyze.py` prints "Balanced" only where the ledger reconciles and the revenue is established and N/A for an unestablished figure, `--json` carries both flags, `batch.py` names the identity `revenue_tiers_sum_to_posted`, adds `revenue_balanced`, `revenue_established` and `verified_revenue_established`, leaves the unestablished figures empty and asks for review where the revenue is not established), and the unestablished key lists are `analysis/revenue_view.py`'s (true revenue spec §10.2, §10.3, §10.4, §10.8, §13, §20).
- Audit round 2, R2-B16 (R56): classification 5.7 (`CLASSIFICATION_VERSION`), with `ANALYSIS_STAGE_VERSION` 33 in the same commit, the run's last. The audit's fix batches, round 2 and the owner's rulings of 2026-10-02 and 2026-10-06 moved tiers, reasons and the review gate under 5.6, so an analysis saved at 5.6 is now outdated (the re-analyze notice, lender spec D12) and its Re-analyze misses the stage-32 cache entry and recomputes it; no rule, tier, reason or figure changes (true revenue spec §9.3, §20).
- Audit round 3, R3-B25: classification 5.8 (`CLASSIFICATION_VERSION`), with `ANALYSIS_STAGE_VERSION` 36 in the same commit, the run's last (34 and 35 skipped: the hosting line used them for code this branch merges after the run). The round-3 fix batches (R3-B01 to R3-B24) moved tiers, reasons and lender readings under 5.7, so an analysis saved at 5.7 is now outdated (the re-analyze notice, lender spec D12) and its Re-analyze misses the stage-33 cache entry and recomputes it; no rule, tier, reason or figure changes in this commit (true revenue spec §9.3, §20).
- The final review of round 2, F1 (7854cf1): a statement whose withholding basis is not established (True revenue where the revenue is not, Verified where Verified is not) publishes no withholding rate, potential exposure or potential lender's exposure and asks for review (`withholding_basis_unestablished`, served only); its downloads leave the basis empty and the CLI prints it as N/A; the package marks such a member and its own partial basis the same way; the legacy basis and every stored figure are unchanged (true revenue spec §9.1, §9.2, §10.1, §10.4, §10.8, §11, §20).
- The final review of round 2, F2 (4cab9ef): a confirmed funder's paid payment pairs on the lender side (classification 5.4's named pair, R2-OW13's restore and its warning) only with a return dated on or after it, printed after it where a row prints no date; the package's pass 4 matches a member's unpaired bounce-worded return (rule D's reading and guards, with two departures from rule D named in the review round below) to the same account's preceding statement's confirmed funder payment 0 to 7 days before it, out of the package's paid to lenders, in its withholding numerator and lender count, with the warning naming both documents; each statement viewed alone is unchanged; G7 declares the moves of a return whose pairing moved (`returned_funder_redirects`) (true revenue spec §6.2, §9.2, §10.1, §10.6, §11, §14.3, §17.1, §20).
- The final review of round 2, review round 1 of its fix run (1dd3b64, 7b7fb1e, 2d81a43, 80e3d4b): a statement whose withholding basis is not established goes to review (its decision and the summary read review required where they would pass; a decision that already reads a review keeps its words) and so does its package; G7's snapshot records every row's date (`row_dates`) and declares a redirected return only where the dates show a payment dated after its return, and any payment returned in its place on or before it; R2-OW18's package payment changes read pass 4's matched payment as a returned attempt; pass 4's two departures from rule D (a lender credit naming the matched payment's funder is read; only a revenue partner dated on or before the credit holds it back) are named for ratification (true revenue spec §6.2, §9.2, §10.1, §11, §14.3, §17.1, §20).
- Audit round 3, R3-B01 (R3-22, R3-80, R3-26, R3-50; eba9664, e613e34, f579eae, 3c2a50d): G7's exit code alone carries its verdict (a returned row leaving the withholding rows, a paid row leaving for no return, a lost lender or a lender-count loss outside the allowlist, and `lender_debits` or the numerator moving with no row move each fail); on a debit, a bank's stop-payment, OD item, returned-item or unpaid-item charge printed with CHARGE or CHG, and a bare stop-payment row, is a charge before the registry, never the payment of the funder it names (steps 1 and 4 below); the ledger reads ODKRAOD as an OnDeck spelling (the orchestrator's sign-off under the owner's delegation, ONDECK allowlisted in G7 for exactly that move); and the Liberis notes call LIBERIS the company's name and also a rare surname and record the receiver residual for the owner (true revenue spec §14.3, §17.1, §20).
- Audit round 3, R3-B02 (R3-69, R3-71, R3-66, R3-21, R3-73; d32514f, f9b4be7, fe459a9, ecc4ebb, 2a17aac): a potential lender's return pairs on the lender side only with its payment on or before it, as a confirmed funder's does (`_returns_a_later_lender_payment`; every other debit keeps classification 5.4's pair); a lender series with an attempt, paid or settlement-reversed, on or before a held no-sender wire's day is no funding aid of that wire; a confirm on a credit that returns a confirmed funder's payment is refused ("a credit that returns a confirmed funder's payment can only be marked non-revenue"; Mark Non-Revenue and Reset stay); and, by the owner's answer of 2026-10-07 ("Count it once (Recommended)"), a returned funder payment the same funder re-debits (the same cents off its cycle, or an exact 2x catch-up, within one cadence gap after the return) leaves the withholding rate, `represented_by` naming the re-debit (pass 7c, and the package's pass 5 across a member boundary; G7 declares it as `returned_funder_represented`) (true revenue spec §6.2, §8.5, §9, §10.1, §10.6, §10.7, §11, §14.3, §17.1, §19.1, §20).
- Audit round 3, R3-B02, review round 1 (0290dc0): a re-debit is never the next payment of a weekday two or more other attempts of the series keep (a twice-weekly schedule or a second position at the same cents), nor a 2x debit that two more 2x debits on the series' cycle follow within two cycles (a step-up to a new level); a re-debited payment's reason no longer says "kept in the withholding rate"; a rule-verified credit carrying `returns_funder_payment` keeps Mark Non-Revenue (true revenue spec §6.2, §10.6, §10.7, §17.1, §20).
- Audit round 3, R3-B02, review round 2 (1249a3a): a 2x debit is no catch-up where two or more 2x debits of the funder fall within two cycles after it, on the series' cycle or not (a second position on another weekday), or two or more within two cycles before it (a level already running), a re-debit already taken left out; a weekday kept only by attempts that each follow another return of the series within one cycle is no recurring phase, so a funder re-presenting every bounce on one weekday counts each returned payment once (the package's pass 5 reads every dated return of its members) (true revenue spec §6.2, §17.1, §20).
- Audit round 3, R3-B03 (R3-20, R3-13, R3-27, R3-72, R3-79; a524dd5, 04a9dd3): a True or Verified withholding basis above $0 and under 500 in the statement's unit publishes no rate, as $0 does (`WITHHOLDING_BASIS_FLOOR`, `withholding_basis_below_floor`, a note naming the floor; never a gate; the legacy basis bypasses it); a review decision refreshes each potential lender's basis and exposure and the basis notes with the rate; a package mixing withholding bases publishes no package rate, names each member's basis and goes to review, and a failed member adds no basis; a package member row divides by the basis it prints; and, by the owner's answer of 2026-10-07 ("Exclude worded payoffs (Recommended)"), a confirmed funder's paid debit printing a payoff word leaves the withholding numerator and stays in paid to lenders and the lender count (`lump_sum_payoff`; G7 declares it as `lump_sum_payoff_excluded`) (true revenue spec §9, §10.1, §10.4, §10.7, §11, §14.3, §17.1, §19.1, §20).
- Audit round 3, R3-B04 (R3-23, R3-24, R3-70; 782a635): lender payment changes read a series more faithfully, information only: a bounced attempt at a level's amount keeps the level's and the regime's schedule when the attempt and payment dates together read a faster regular schedule that keeps its cycle (attempts still never set an amount or count as payments; the batch's first test of a daily cycle let a weekly debit re-presented twice read daily, which review round 1 below corrects); a level under 5% of the weekly weight of a schedule-confirmed level of the series (3 payments, 5 if daily) whose beat its dates keep is a fee level, dropped before positions are formed (a token payment that replaces the main level is kept), with the per-position fee test after it; and a 2x or 3x level whose run of 2 reads a slower regular schedule than the main level's is no catch-up but a possible change at a new schedule. No classification, contribution flag, reason, item field or kind changes (true revenue spec §9.3, §17.1 points 8, 18, 20 and 22, §20).
- Audit round 3, R3-B04, review round 1 (0b9f0dc): a daily schedule read through bounced attempts needs 60% of the dates or more in stretches of 5 consecutive business days holding 4 or more of them, more than NACHA's 3 presentments of one debit fill, so one weekly debit's presentments never fill such a stretch (the chains of two adjacent weeks still could, which review round 2 below corrects); a level whose attempts set its cadence is read on those attempts' dates by the concurrency and fee tests, as its cadence is, and R3-70's slower-run test reads its payments' own schedule; a biweekly or monthly debit re-presented at weekly steps still reads weekly, its dates being a weekly debit's whose other presentments bounce (a disclosed shape). No classification, contribution flag, reason, item field or kind changes (true revenue spec §17.1 points 20 and 22, §20).
- Audit round 3, R3-B04, review round 2 (6995376): a daily schedule read through bounced attempts also needs, of the intervals between its paid dates with 3 business days or more inside, one at least and 60% holding 3 attempts or more, more than one debit's chain holds before its paid one, so the chains of two adjacent weeks, or of a week a holiday shortens, never add up to daily, and a weekly debit whose chains each end paid before the next week's entry never reads daily (a weekly debit whose chains are returned three times or re-presented past the next entry still can: a disclosed shape); R3-70's slower-run test reads the main level's payments' own schedule only while that level is still presented through the 2x or 3x run, and its cadence, read through its attempts, once it no longer is. No classification, contribution flag, reason, item field or kind changes (true revenue spec §17.1 points 20 and 22, §20).
- Audit round 3, R3-B05 (R3-25, R3-84 and the owner's answer of 2026-10-07 to R3-25; afcca7b): lender payment changes, information only. A one-off within 2% of exactly 2 to 6 times the payment is a catch-up: presence for pauses, restarts and stops alike, never a payoff; a pause it ends names it (`first_after_kind` `catch_up`), a stop's later debits count the multiples among them (`other_debits_after.catch_ups`), the payoff note reads only a debit of 2x or more that is no exact multiple and counts the earlier ones (`payoff.earlier`), and every other debit of 2x or more inside a pause's gap is named (`larger_debits_inside`). The owner's answer ("Add a 'Caught up' line") adds the kind `catch_up`: such a multiple after one or more missed scheduled payments (business days for a daily schedule, due dates for the others, which allow one business day), read from the position's last paid presence, that no pause or stop line names, is one Caught up line. Debits no rule claimed (class `other`) at the series' exact cents on its schedule inside a pause's gap or after a stop's last presence, covering 60% of the payments the schedule expects there, are named (`same_amount_debits`), and such a stop is never confirmed; they never become presence, a payment or paid to lenders (R3-84). No classification, contribution flag, reason or lender, withholding, revenue or gate figure changes (true revenue spec §9.1, §9.3, §10.1, §10.8, §17.1 points 24 and 30, §19.1, §20).
- Audit round 3, R3-B05, review round 1 (cc8524e): a package stop whose last presence is a catch-up in a statement before the last one is read again (the batch's confirmation branch overwrote the set of catch-ups a line names, and the package view failed): it names the catch-up, confirms on the later statement, and no Caught up line repeats it. A catch-up after the presence that ended a pause (a bounced attempt, a payment at another amount or an earlier catch-up), up to and including the day payments resume, is named on the pause line (`catch_ups_inside`) and no Caught up line repeats it. A partial catch-up, the monthly 2x/3x/4x shape and a 1st-and-15th schedule read biweekly are disclosed shapes. No classification, contribution flag, reason or lender, withholding, revenue or gate figure changes (true revenue spec §9.1, §10.1, §10.8, §17.1 point 24, §20).
- Audit round 3, R3-B06 (R3-81, R3-82, R3-83, R3-85; 85a6d5f): lender payment changes, lines and notes, information only. A new stream names each other stream at the level it was paying when the new one began, for the 10% gate and the weekly totals too (R3-81; the new stream's own amount stays its last level). The funding note ("(renewal?)") never cites a credit that returns or reverses a payment, one within 1% of the change's own payment amounts or of a payment or attempt of the series 0 to 7 days before it, or one dated on or before the first payment of the regime just before the new one (R3-82; no size floor). Another account's payment or attempt continues a stop, never confirmed, only within the stop's grace window counted in the business days the two accounts' statements cover; a later one leaves the stop as its own statements read it and is named, "reappear in another account … after N business days without one" (`reappears_in_other_account`, R3-83). A confirmed stop whose "since" names its last regular payment names the anchor of its business-day count, and the CLI's stop line names the later debits and the anchor (R3-85). No classification, contribution flag, reason or lender, withholding, revenue or gate figure changes (true revenue spec §9.1, §9.2, §9.3, §10.1, §10.8, §17.1 points 11, 25 and 26, §20).
- Audit round 3, R3-B07 (R3-14, R3-40, R3-42, R3-18, R3-45, R3-46; b9c558b): wire senders, relays and financing names. A relaying bank that prints `BANKING` (under the English company-form rule) or a non-English bank word (`BANCO`, `BANCA`, `BANQUE`, `BANCAIRE`, `SPARKASSE`, a company form after it the bank's own) is a bank by its form, so its relayed customer is the wire's sender, a relayed numbered company included (counted, never verified), and such a bank naming no customer is held as a bank-originated wire; Q5's and Q6's bank words add `BANKING`, `BANCA`, `BANQUE`, `BANCAIRE` and `SPARKASSE`, so such a payer never verifies by its company form or by Q5's repetition (R3-14). A wire region of only label, holder-noise, account-designation, purpose, filler or legal-form words names no sender (`wire_no_sender`, on every wire layout; a numbered company keeps its reading; R3-40). The sender printed right after `INBOUND WIRE|FEDWIRE [TRANSFER FROM]`, `INCOMING FEDWIRE [TRANSFER FROM]`, `INCOMING WIRE TRANSFER FROM`, `INCOMING CHIPS` and `WIRE TRANSFER[S] CREDIT` is read, a sending or the statement's own bank's channel name there naming no sender (R3-42). A wire purpose's `ADV PAYM`, `ADV PMT`, `ADV PYMT` or `ADVANCE PYMT` is a buyer's advance payment, never after `MERCHANT`, `CASH` or `MCA` (R3-18). Off Scotiabank's statements arm S's whole-row match lifts no funder-name guard on a deposit's location (R3-45). A company name that holds `LN` before a legal form, with no loan word around it and no transfer wording, is read by the strong non-revenue patterns without the normaliser's `LOAN`, so it is held `financing_named_payer` (reviewable) where it was `non_revenue`; the normaliser's output is unchanged (R3-46). Debits, payee aliases and lender readings do not change (true revenue spec §7.11, §8.1, §8.2, §8.5, §9.3, §17.1 point 3, §20).
- Audit round 3, R3-B08 (R3-41, R3-88, R3-44, R3-31, R3-32, R3-92; 3c62215): ACH and label readers, bank-only payers and page furniture. American Express's full incoming-ACH template (`… <id> [<receiver block>] EXTERNAL …`) keeps its ACH reading whatever its originator's first word: R31's gate reads only a row the template does not match, and the row before the receiver block keeps the template's `EXTERNAL` (R3-41). A town's `DES` (Des Moines, Des Plaines, Des Peres, Des Allemands, Des Lacs) never opens the originator field, so a named transfer from such a town keeps its transfer reading; BMO's two-word CPA code pairs and Scotiabank's `BPY` and `PAY` after a numbered company's province keep its number (R3-88). A lost French accent inside `CHEQUE` (`CH QUE`) or after `RETOURN` is read in all three copies of R2-B08's arms and in rule D's French bounce arms, and the strong rule reads `INTERETS GAGNES|CREDITEURS|PAYES|VERSES` on credits (R3-44). The statement's own bank is read first, as a whole region, by its full name and its printed short forms (`OWN_BANK_SENDING_SPELLINGS`; every Chase field reads `CHASE`), so its own name alone is counted with no payer, never held as another bank's pull; a P2P label counts only after the bank's name in the payer region; a sperm, eye, tissue, milk, bone or cord-blood bank is no bank (R3-31, R3-32). A credit's category rules and its `is_check`, `is_ach` and `is_pos_context` flags read it without its statement furniture; a debit keeps its text until the owner admits the G7 move (R3-92). No tier, reason, revenue, lender, withholding or debit figure moves on the corpus (true revenue spec §5.2, §7.0, §8.2, §8.6, §9.3, §17.1, §20).
- Audit round 3, R3-B09 (R3-36, R3-87, R3-91, R3-75; 5705367): unread payer text and parser rows, TD e-Transfer sends and the census's row-count moves. The revenue census lists a parse change that adds or drops a row, a credit or a debit, as a G18 parse move ('row count changed', with both row counts), compared apart as a re-parsed account, so a note can explain it; G9 keeps an account the later run lost and a row-count change without a parse change, its item saying whether the parse changed (R3-36). A class-code word followed by a legal form (CashArc's `CASH-ARC LLC`) is part of a name, never a block's end, in R07's run split and in the counted template's one-block count, so a welded run printing such a lender is held and a lone block of its name is attributed (R3-87). The daily core-processor template keeps each marked credit's block (`Transaction.unread_payer_text`; reading it as the payer still waits on G7), balance_by_date keeps the continuation line under an incoming wire's row and B1 the lines under a wire's row, each on the wire it marks; a held `wire_no_sender` or `transfer_no_counterparty` credit carrying that text says "payer line not read" in its review text, and every hold stays (R3-91). A credit printing an outgoing e-Transfer label (`SEND E-TFR`, `e-Transfer sent`, never `SENT BY`), TD's French send, reversal or redeposit (`Envoi`, `Contr.`, `Redepot - VFC`) or a French fee adjustment (`AJUST FRAIS`, no legal-form word later) is held as `possible_return`; the parsers' tie-break stays with the owner's I41 G7 item (R3-75). No debit or lender reading moves; the True-basis withholding rate rises only where True falls (true revenue spec §8.1, §8.2, §8.5, §9.3, §10.7, §14.2, §14.3, §17.1, §20).
- Audit round 3, R3-B09, review round 1 (4776d05): a class-code word is part of a name only before a legal form of the LLC family (`LLC`, `L.L.C.`, `L L C`, `LLP`, `PLLC`), in the counted template's one-block count and in R07's run split: the other forms (`INC`, `CO`, `COMPANY`, `CORP`, `LTD`, `LP` and the rest) open real originator names, so a code before them still closes its block and two blocks welded under one row stay unread, never that row's description. R3-75's send and sent labels are read only with no incoming wording before them on the row (`RECEIVED`, `FROM`, `AUTODEPOSIT`, `RECEPT`, `DEPOT`), the send label with no legal-form word later, and none of the send, sent and fee-adjustment labels right after `NAME` (an ACH originator's name field). No corpus row moves (true revenue spec §8.1, §8.2, §20).
- Audit round 3, R3-B10 (R3-17, R3-37, R3-38, R3-39, R3-89, R3-90 part A; 6123a5d): the holder test reads the holder's name as it reads the payer's. The receiver-block strip and a one-word holder's dropped-lead run tokenize the holder's name as `payer_name` does (no single letter, no digit token), so a possessive's `S` (`SAMPLE'S` normalizes to `SAMPLE S`), a middle initial or a digit token never stops the strip, and `JB'S TRUCKING LLC` runs `JB TRUCKING`. The I47 strip tries the row-end cut before the whole-word runs, so a name of three words or more cut in its third word or later is stripped, and reads no leading `THE` as a run's word (its runs are read with and without it). Two shared trade words name the holder only when they include the holder's lead or when the payer's own printed lead word (a name-starter, a short word or an initialism included) is a holder word or the holder's abbreviation; a holder whose name leads with a name-starter or a two-letter initialism is named only by a payer that prints that word, by its brand word too. A `DBA` holder's whole name reads as a person's when its first side does, so another person sharing only the owner's given name is counted. The direct-deposit business receiver reads a cut form only as one of the holder's own forms and never a one-word holder's name cut; its person-named residual is an owner item beside Q8. A bare `SETTLEMENT` (`SETTLMT`, `STLMT`) under the merchant's own name, on a row that is no transfer or person-to-person row, is a settlement the holder holds skip, counted and never verified (true revenue spec §5.2, §8.1, §17.1, §20).
- Audit round 3, R3-B10, review round 1 (f598bca): `SETTLEMENT`'s short spellings `SETTLMT` and `STLMT` are verification-only words beside it (§8.6), so a settlement the holder hold no longer reads is counted and never verified in each of the three spellings, with or without a holder name read, and a third party's repeated `SETTLMT` or `STLMT` counts, flagged (`named_payer_purpose_refused`), as its `SETTLEMENT` does. The holder test is also read by §6.3 narrowings 4 and 8 and steps 11 to 14's holder veto, so the batch's narrowed test lets a released sender leave `non_revenue` and the possessive holder's own transfer enter it, and a released customer verifies by its own reading; a `THE`-led holder's strip is that of its name printed without `THE`. No corpus row moves (true revenue spec §8.1, §8.6, §9.3, §20). (Review round 2 takes the short spellings back out of §8.6: see the next entry.)
- Audit round 3, R3-B10, review round 2 (99d6760): a row the bare settlement word alone releases (from the pass-7 holder hold, or from the row-alone own-push test) is refused as proof by the pass's own flag (`CreditFacts.settlement_released`) wherever and however the word prints, an ID field, an originator's tail or digits glued on included, with or without a holder name read, in both Zelle readings, and never counts toward a repeat; where an earlier rule verified it (an operating-income or claim-payment descriptor), it leaves verification as `holder_named_settlement` (rule `holder_named_settlement_never_verified`) and is read as an unverified credit, every hold still reading it. `SETTLMT` and `STLMT` are no verification-only words again, so a third party's short spelling, a card issuer's or a bankcard form's included, reads as it did before the batch. No corpus row moves (true revenue spec §8.1, §8.6, §8.10, §9.3, §20).
- Audit round 3, R3-B11 (R3-61, R3-65, R3-30; c85df95): premium-trust titles are read by their words, not their spacing. A holder reader's contact (`ATTN`, `ATTENTION`, `C/O`, glued to its text by a colon or a dot or not, and `CARE OF` after the name's legal form) is never part of the holder's name and never an account title, except a contact whose words are the premium-trust designation itself, which is published as the account's title (`PREMIUM TRUST ACCOUNT`, without its marker) in any spacing, so the account's deposits are held (R3-61). The premium-trust rule also reads a product adjective before a kind word (`PREMIUM TRUST BUSINESS CHECKING`), `PREMIUM FUND(S) TRUST`, and the for-benefit form on an account name or a holder name that ends in the beneficiary's legal form (`PREMIUM TRUST ACCOUNT FBO NORTHWIND AGENCY LLC`); its recorded misses are labelled as overstating True and its recorded over-reads as understating it, held and reviewable (R3-65). The True card's holder-unscreened fact says that no premium-trust title is read on such a statement either (R3-30). No corpus statement moves (true revenue spec §5.2, §8.10, §9.1, §9.3, §10.1, §17.1, §20). (Review round 1 reads `CARE OF` only where the name has ended and reads the contact's designation as the title rule does: see the next entry.)
- Audit round 3, R3-B11, review round 1 (186c714): `CARE OF` is a contact only where the holder's name has ended, right after its legal form (a trailing comma allowed) or the account designation printed right after it, so a `DBA` trade name (`CONTOSO LLC DBA NORTHWIND HOME CARE OF SAMPLEVILLE`) and a name whose legal form prints inside it (`SAMPLE & CO HOME CARE OF SAMPLEVILLE LLC`) keep their `CARE OF`, as before the batch. A contact is the account's title when its words are the premium-trust rule's own title at a field's end, read from the contact's first word (a kind word such as `CHECKING`, the bare words, a reference; a reference's marker the address cut leaves dangling is dropped), never a department, `OPERATING`, an adjective alone or any other word after the designation. The for-benefit form reads a product adjective before the account word. No corpus statement moves (true revenue spec §5.2, §8.10, §9.1, §9.3, §17.1, §20).
- Audit round 3, R3-B12 (R3-12, R3-29, R3-56; 1360d98): pass 7 reads the consumer person-to-person rails as the banks print them. It reads a credit on its own text, `true_revenue.pass_text` (TD Canada Trust's e-Transfer code dropped, and PNC's Zelle rail `ZEL FROM|TO` spelled `ZELLE FROM|TO`), in the pass, the census's facts and the served Zelle view, so a PNC Zelle credit takes the person-to-person channel, its sender's key (pooled with the same sender's `ZELLE` rows), the round-sum repeat and the counter-debit hold's whole-name person match, as the owner's amendment of 2026-10-06 asks ("holds as for other P2P"); under No it stays `zelle_excluded`, its `zelle_prior` naming that reading (R3-12). Interac's French name, `VIREMENT(S) PAR COURRIEL` (Banque Royale's `DEPOT AUTO VIREMENTS PAR COURRIEL <sender>`), is the e-Transfer rail in pass 7, read before a cash or branch `DEPOT`, its sender read after `COURRIEL` and matched to a debit by its whole name, and `PAR COURRIEL` is an Interac form, so the singular is no transfer wording (R3-29). A wire is never a Zelle deposit: `true_revenue.zelle_deposit` reads no incoming wire and no loose wire's originator row, whatever its memo prints; the ACH entry-description forms (`DES:ZELLE`) and the rail after a bank's wording are kept (R3-56). The classifier's `_CONSUMER_P2P_RAIL`, the 5.5 channel gate, the legacy classes, the debits and the lender fields are unchanged (the recorded residuals: a `ZEL TO` debit's legacy class and missing person key, the French debit forms, a company named `… ZELLE …` paying by ACH, the classifier's Verified loss on a wire memo's `ZELLE`). In the re-parsed corpus True falls by $28,590.00 under Yes (53 PNC and 33 Banque Royale rows) and by $17,500.00 under No (the 33), with no Verified row and no debit moving (true revenue spec §8.2, §8.4, §9.3, §20). (Review round 1 records the readings pass 7 does not reach: see the next entry.)
- Audit round 3, R3-B12, review round 1 (f13d1e6): a PNC `ZEL` credit reads as its `ZELLE` twin in pass 7 only. The classifier reads the raw text first, so a `ZEL FROM` credit whose sender looks like an operating platform is still claimed as an operating source (counted, and Verified on a repeat) where its `ZELLE FROM` twin is counted `p2p` or held as a round repeat; a `ZEL TO` debit keeps its legacy class `other` and no person key (both twins are circular money to the counter-debit hold), so a credit for its own amount, or one with no person key, names it by the first word. `true_revenue.zelle_deposit` refuses an incoming wire or a loose wire's originator row only: a wire layout neither gate reads (`<sender> WIRE` with no originator label, `ONLINE WIRE TRANSFER FROM`, `WIRE TRANS SVC CREDIT`, `WIRE DEPOSIT`) still reads a memo's `ZELLE`, and a Zelle row printing `WIRE` and an originator label before its rail word is refused. Each is a recorded residual, pinned by the tests; no code changes and no row moves (true revenue spec §8.4, §20).
- Audit round 3, R3-B13 (R3-11, R3-57, R3-10, R3-09, R3-58, R3-64, R3-55; f103f68): the underwriter's Q2 and I26 insurer readings and Q12's glued forms. A Texas county mutual is a private carrier, never a county: the classifier's `_PUBLIC_PAYER_NAME` reads no `<WORD> COUNTY` followed by an insurer word (`MUTUAL`, `MUTUA`, `MUT`, `INS`, `INSUR…`, `CASUALT…`, `INDEMN…`, `ASSUR…`, `LLOYDS`; never `FIRE` or `SELF`, nor `MUTUAL AID`: review round 1), `COUNTY MUT` is an insurer spelling, and `insurer_payer_reading` reads a listed insurer before a government payer (the non-sale hold's public-payer arm reads no `CLAIM` on a released row either). Only a consumer person-to-person rail (`_p2p_rail`) keeps the spelled-out insurer words alone; a push or instant rail, a named transfer and an ACH entry worded `TRANSFER` read every spelling and brand, the cut `MUTUA` only beside a company form. The Q2 release refuses a personal benefit's wording (`_INSURER_PERSONAL_BENEFIT` everywhere; `_INSURER_LTD_BENEFIT` on the purpose; `_INSURER_NON_PROVIDER_BENEFIT` where no holder name reads a clinic or a pharmacy (amended by R3-B13 review round 1, below: where the holder's first trade is no clinic or pharmacy, never a benefit word inside the carrier's name)), and on a person-to-person row §8.4's round-sum repeat still holds a released insurer (`p2p_round_repeat`, its method kept). No code change for R3-58 (the service form never reads a wire's `REF`; the customer-payment wording does, where Chase's book transfer prints its purpose) or R3-64 (a released insurer's printed asset sale is Q11 (b)'s `non_revenue`). The six letter-led Q12 forms read past a digit run glued before them (`(?<![A-Z])`; the VA's form keeps `(?<![A-Z0-9])`), and the census's class H reads every named form's residue. Every debit, lender, withholding and flag reading is unchanged; no corpus row changes tier (true revenue spec §6.1, §7.6, §8.1, §8.10, §14.2, §17.1, §19.1, §20).
- Audit round 3, R3-B13, review round 1 (7135088): the Q2 release's provider is the holder's first trade (`_holder_provider` reads `_holder_service_trade`'s label with its loose words, as R3-10's brief ruled), so workers' compensation or a plain benefit wording paid to a holder whose first trade is an insurance agency or a repair shop is held, whatever clinic or pharmacy word the name also prints (`<NAME> HEALTH INSURANCE AGENCY LLC`, `<NAME> COLLISION DOCTORS LLC`). A plain `BENEFIT(S)` or `BNFT` on the payer region followed by an insurer word or spelling or a legal form is the carrier's name, never the payment (`_non_provider_benefit`: `MUTUAL BENEFIT INS CO DES:DRP PAYMENT` counts at a repair shop again); the purpose's wording, a wording printed after the carrier's name and workers' compensation anywhere still refuse. The county-mutual veto spares `MUTUAL AID` (`<NAME> COUNTY MUTUAL AID` is a public payer again). Every debit, lender, withholding and flag reading is unchanged; no corpus row changes tier (true revenue spec §7.6, §8.1, §9.3, §17.1, §20).
- Audit round 3, R3-B14 (R3-06, R3-54, R3-07, R3-52, R3-60; 17521f1): the underwriter's Q8 and Q9 reading rules. A lease-to-own or patient financier's credit, or a payout entity's (OQ2), that prints a non-sale or financing word (`ADVANCE(S)`, `ADVNC`, `ADVN`, `ADVC`, `CASH ADV…`, `CAPITAL`, `CAPTL`, `INTEREST`, `DIVIDEND(S)`, `REBATE(S)`, read without the receiver's value and the holder's names; never `FUNDING`, `PAYOUT`, `PAYMENT`, `LEASE FUND`, `PROCEEDS` or a bare `ADV`) is not claimed: the holds read it as the same row from any other payer (`financing_named_payer` or `non_sale_purpose`), and Q5 and Q6 never verify it (`_payout_claim_vetoed`, its Q6 guard: 439715b), so where no hold reads its word (`ADVNC`) it stays counted. A Cherry credit printing `LOAN(S)` or such a word keeps D1 (financing proceeds, entity Cherry, the lender-credit exclusion on), its reading before Q8. A cut name of Katapult Engineering (`KATAPULT ENG…`) is the namesake, never the lessor (`CUSTOMER_FINANCING_PAYERS`, `CUSTOMER_FINANCING_NAMES`; the ledger's Katapult note). Q9 (c')'s dealer evidence reads an auction purchase only where it is no card purchase, the floor-plan form by its own words (never `FLOORPLANNER` or `FLOOR PLANKS`) and a floor-plan financier's credit only where it prints no service wording; Q11 (b) reads the same arms. The lessor's third arm counts no account designation as a rent payer and reads rent words outside the payer's own name. The Q8 test file's rows carry fabricated values only. Every debit reading is unchanged, and the lender-credit exclusion moves only for a Cherry loan or advance; no corpus row moves and G7 finds no move (true revenue spec §6.3, §8.1, §8.7, §8.9, §8.10, §9.3, §17.1, §19.1, §20).
- Audit round 3, R3-B14, review round 1 (ddb4327): the classifier's Cherry veto reads its words as the pass's veto does, without the receiver field's value and without the holder's names (`without_receiver_and_holder`), so a practice whose own name prints `CAPITAL`, `ADVANCE` or `INTEREST` as an unlabelled receiver (Wells Fargo, TD, a generic `ACH CREDIT`) keeps its Cherry payouts counted, with no lender credit. A lease-to-own or patient financier's credit the veto unclaimed and the rules counted (an abbreviated advance, `ADVNC`, `ADVN`, `ADVC`) is read by the lump-sum test as that financier's payout (`_vetoed_financier`), so a large one-off one stays `customer_financing_lump_sum`. The lessor's third arm removes only the payer's name proper on a row with no payer-name field: a leading rent word (Truist's entry first) and a rent memo after a name with no company form still read; only a rent word inside a company-formed name, or `RENTAL(S)` used as a trade noun, is the payer's name. The dealer evidence reads the floor-plan service words without the holder's names, a wire, ACH or check purchase at the auction printing its state and country (never a card purchase), and the glued `FLOORPLANINT`, `FLOORPLANPAYOFF`, `FLOORPLANADV` and `FLOORPLANXPRESS`. Every debit reading is unchanged; no corpus row moves (true revenue spec §6.3, §8.1, §8.7, §8.9, §9.3, §17.1, §20).
- Audit round 3, R3-B15 (R3-08, R3-59, R3-63, R3-53; 8e00872): the underwriter's Q11 (a) and (b) reading rules and the held rows' sentences. A builder's progress draw reads the builder word on the payer region without the holder's names; on a row that prints no payer-name field (the label-less layouts of Wells Fargo, Citizens, TD Bank, Huntington and Truist) the entry's `CONST DRAW` or `CONSTRUCTION DRAW` is the draw's purpose, never the payer's builder word, and `DRAW` is read only after the builder word, so a root-less lender's, a developer's, a property firm's or a county's label-less draw, and a `DRAW` inside the payer's name, keep their `non_sale_purpose` hold, as their Bank of America DES twins do (a label-less `<NAME> CONSTRUCTION` with no company form before a bare `DRAW`, and a builder's draw on Truist's entry-first layout, are held too: recorded residuals; the latter counted again by its review round 1). A commission or a fee next to a printed sale that a netting word stands beside (`WITHHELD`, `DEDUCTED`, `DEDUCT…`, `NETTED` after it; `NET`, `NET OF`, `LESS`, `AFTER`, `MINUS` before it, a bare `NET` before `FEES` only since its review round 1) is what the sale is net of, so a non-dealer's `TRUCK SALE FEES WITHHELD` or `LESS COMMISSION TRUCK SALE` is `asset_sale_proceeds`, while a bare commission or fee stays a broker's revenue. The factoring and progress-draw demotions leave a credit under $1 to the $1 floor (method `micro_deposit_floor`, its sentence naming the overruled rule). A hold that re-tiers a counted re-statement rewrites the row's reason sentence, so a held row never says it is "counted and flagged" (true revenue spec §5.3, §8.1, §8.10, §9.3, §17.1, §19.1, §20). No tier, reason code or figure moves in the corpus; the reason sentence of 44 held insurer rows the Q2 release re-stated changes, and no other field.
- Audit round 3, R3-B15, review round 1 (9d5e9a6): a bare `NET` before a printed sale is a netting word only before `FEES`, so a broker's or an agent's `NET COMMISSION ON TRUCK SALE` (its own earned commission after splits) and `NET FEE FOR TRUCK SALE` stay its counted revenue, while `NET FEES TRUCK SALE` and `NET OF COMMISSION TRUCK SALE` are still a sale. On a row that prints no payer-name field the `DRAW` of the entry's own purpose phrase printed before the builder word is read (one that starts the payer region, since its review round 2), so a builder's draw on Truist's entry-first layout (`CONST DRAW <NAME> BUILDERS INC …`) counts as `construction_progress_draw` again, and `BUILD DRAW` is such a phrase too, so a root-less lender's label-less `BUILD DRAW` keeps its `non_sale_purpose` hold. The recorded label-less residual names `<NAME> CONSTRUCTION`, the cut `<NAME> CONST` and `<NAME> CONSTR`, and `<NAME> BUILD` with no company form before a bare `DRAW`. No corpus row moves (true revenue spec §8.1, §9.3, §19.1, §20).
- Audit round 3, R3-B15, review round 2 (bc8d55e): a seller's proceeds never lead with or come out of a commission, so a commission word printed directly before the netting phrase (`COMMISSION LESS FEES ON TRUCK SALE`, `NET COMMISSION LESS FEES TRUCK SALE`, `AGENT COMMISSION AFTER FEES FOR TRUCK SALE`) or fees a netting word takes from or off a commission (`TRUCK SALE FEES WITHHELD FROM COMMISSION`) keeps the commission veto and stays a broker's counted revenue, as its mirror `TRUCK SALE COMMISSION LESS FEES` does, while a commission a netting word itself stands before (`NET OF COMMISSION LESS FEES TRUCK SALE`) is still a sale. On a row that prints no payer-name field only a draw's purpose phrase that starts the payer region (Truist's entry-first entry) lends its `DRAW`, so a root-less lender's, a county's or a developer's `<NAME> CONST DRAW` followed by a later builder word in the region (`SAMPLE COUNTY CONST DRAW BUILDER PMT`) keeps its `non_sale_purpose` hold. No corpus row moves (true revenue spec §8.1, §9.3, §19.1, §20).
- Audit round 3, R3-B16 (R3-03, R3-35, R3-33, R3-34; c2bf1cf): the counter-debit holds read the debit's kind more closely. A credit the Q2 release counts (an insurer paying for the business's work, `insurer_paid_for_services`) is held `payer_also_debited` by a debit naming its carrier only when that debit is circular money, is for the credit's own amount, or recurs at one amount printing no premium or retry word (`PREM`, `PREMS`, `PREMIUM(S)`, `RETRY`): an agency's or a provider's premium to the carrier that pays it is an ordinary expense, never money going round; an insurer the release does not count stays held beside its premium or bill. American Income Life (`AM INCOME LIFE`, `AMERICAN INCOME LIFE`), whose agents' commissions print no insurer word, is a credit-only insurer brand, so the release reads it. Chase's glued SEC code is split off the entry before the processor's fee and the bill are read (`FEESSEC`, `MTHLY DISCSEC`, `CHARGEBACKSEC`, `BILL PAYMTSEC`, `PLANT UTILSEC`), and a fee word glued after another word at the entry's end is the processor's fee (`MONTHLYFEESEC`, never `COFFEESEC`), so an unclaimed processor's fixed glued fee never re-holds its settlements. The fee for the holder's own outgoing wire `FROM <account product> TO <payee>` (`BUSINESS CHECKING`, `OPERATING`, `MONEY MARKET`, an account number) is circular money, never a receiving fee. An ATM withdrawal printing a one-word company name (`ATM WITHDRAWAL <name> INC`) stays a cash withdrawal. In the corpus 59 held insurer rows ($268,447.94, 6 statements) are counted in True, never verified; nothing else moves (true revenue spec §8.1, §9.3, §17.1, §20).
- Audit round 3, R3-B17 (R3-77, R3-74, R3-15; 2b684b8): counter-debit keys and payee labels. A statement's bank's own posting-type label printed before the party names no party: on RBC (`INSURANCE`, `INVESTMENT`, `FEES DUES`, `EQUIPMENT RENT`, `PAY EMPLOYEE VENDOR`) and Scotiabank (`INVESTMENT`) the counter-debit readings read the party after it, on credits and debits alike, so a clinic's `INSURANCE <insurer>` payments are never held by a debit to another insurer the label alone named, while a premium to the same insurer still names it; any other bank reads a leading `INSURANCE` or `INVESTMENT` as a name's own word. A leading pre-authorized-debit label (`PRE-AUTH DEBIT [<reference>]` and its spellings, any bank) is cut from a debit and Scotiabank's `ACHDEBIT` is a label word, so a funder collecting under them, or under RBC's `Investment <name> PAD`, keeps its funding held (`financing_named_payer` by the underwriter's Q9 hidden-loan guard, `payer_debited_as_lender` for a payer with no financing root). A numbered company (`<n> ONTARIO INC`, BMO's cut `<n> ONTA AP CC`, Quebec's `NNNN-NNNN QUEBEC INC`) is compared by its number, read only where the numbered-company form prints (never a cheque or reference number), so a numbered funder's daily debits, a numbered affiliate's round trip and an e-Transfer round trip with a numbered company are held as their word-named twins are, and BMO's cut `ONTA` is no key; RBC's `ACCOUNT PAYABLE PMT` and Scotiabank's `ACCOUNTS PAYABLE` before a numbered company's number are removed before the payer region, so the holder's own number is held `holder_name`. D6's lender names are unchanged. No corpus row in the census moves in either Zelle reading; outside the shares, 9 counted e-Transfer credits from one numbered company in unreconciled RBC statements are held `payer_also_debited` (true revenue spec §5.2, T11, §8.1, §9.3, §20).
- Audit round 3, R3-B18 (R3-02, R3-04, R3-05; 272f28a to 6553740): package mechanics and the dashboard's overlap words only, no classification change, no stored output. One account's statements in a package are the ones whose printed account says so (the bank, an informal printout's label read as its bank, and the last four digits, no conflicting full numbers) or, for a statement whose bank or account number is not read, the ones its ledger, its balance chain or the credits it shares relate it to: another reading of a statement is the same statement when its period, its balances and its ledger rows on the day and the signed cents are the same (the `ledger:` key); the months' floor joins such a statement to its account by the balance chain of the owner's Q6 identity; a shorter printout is left out only on the exact row proof, and any other overlap of one account's statements is named (`overlapping_statements`, with `days_shared`) and sent to review, never netted, on the credits both print in the days both cover matched one to one on the cents within 3 days whatever their wording, a printed pair also when it shares more than 3 days or one period lies inside the other ("`<file>` and `<file>` cover `<n>` of the same days of one account"); a statement of more than a month is left out first only in favour of month-length statements that print it and count nothing twice between them (a statement of 32 to 35 days; a printout of more days in favour of all its account's statements that do, since its review round 1), so a 32-35-day monthly cycle stays over partial printouts of it. The revenue census does not move (true revenue spec §9.2, §9.3, §10.1, §10.8, §17.1, §20).
- Audit round 3, R3-B18, review round 1 (e2f83b6, ddbac69): the long-printout phase's month-length rule reads a statement of a monthly cycle's length (35 days or fewer) only. A printout of more days (a 60- or 90-day activity printout, a multi-month export) is left out first in favour of all its account's statements that cover its period and print its rows, a month-to-date and a short first or closing month included, so beside the monthly statements and the current month-to-date it no longer leaves them out in its favour, counting twice the days it shares with a month it does not print whole and losing a month; the double-count test reads only the statements the second phase would keep side by side (a month-to-date beside its month, or a printout two neighbouring months print, is left out there first, and before them another printout of more than 35 days that the others print, so a second activity printout never keeps the first in the package; qualified in place by its review round 2, below: true of the shapes pinned, not of every second printout). Recorded, not changed: a 32-35-day printout that only a shorter statement proves still waits for the second phase, the double count named; a possible pair leaves a statement out on a one-row proof; Chase's export label is read as Chase only, so a Chase savings account's export never meets its statements. The revenue census does not move (true revenue spec §9.2, §9.3, §20).
- Audit round 3, R3-B18, review round 2 (299778a): the long-printout phase reads a double count only between two statements that are one account's, each printing a posted row (a statement printing none counts no money): a printed pair, or a possible pair that the overlap pass names or whose two statements print only rows of the printout being tested in its days. So a second account of the holder at the bank whose number is not read, printing rows of its own, no longer keeps an activity printout or a 35-day export in the package (it had left the monthly statements and the month-to-date out in its favour, a month's days counted twice and a month lost), while two unkeyed printouts that print only the printout's rows keep it as keyed ones do. Its second-phase simulation leaves a 32-35-day printout that the month-length statements alone print without a double count out first, as the first phase does, so a 34-day export the monthly statements print no longer keeps a 90-day printout in the package; a printout with no posted row is no double count. Recorded, not changed: a long printout still waits beside a 32-35-day printout that only a shorter statement proves, or beside a month-length partial printout the second phase keeps over a short month inside it. The revenue census does not move (true revenue spec §9.2, §9.3, §20).
- Audit round 3, R3-B19 (R3-86; 8231040): the package revenue gate (T7) also reads the package's own sums. Besides each member's gate, a package needs revenue review when, per declared currency, the summed held credits of its members analysed at 5.6 or later are ten percent or more of their summed True revenue plus held and at least $500 (`REVENUE_REVIEW_HELD_FLOOR`), so a package of months each holding under the floor gates as the same credits printed as one statement would; currencies are never mixed. Review only: every member's gate and document row, every figure and the review badge are unchanged, and a decision moves only from approved or limited review to review required. The owner-decision default; the alternative is the per-statement gate alone. No classification moves (true revenue spec T7, §9.2, §9.3, §17.1, §20).
- Audit round 3, R3-B20 (R3-48, R3-19, R3-51; 9e10fd5, da7f88e, 5860bcc): the Zelle figures say what was judged, and no classification moves. Where an account's or a package's revenue is not established, the Zelle figures keep what the captured rows say (their count and total, and the non-revenue part) and drop every part of True or Held: the downloads leave those cells empty, the served package reads them as None, the CLI prints them N/A and the batch row leaves `zelle_in_true_revenue_total` empty, and the dashboard names "Zelle deposits captured … captured rows only" (R3-48). A package's `zelle_deposits.counted_as_true_revenue` is what its members serve, a new `setting` key holds the setting it was served under, and its memo carries the notice and names every Zelle part (R3-19). Under No, an excluded Zelle deposit's reason names the reading the rules give it with Zelle counted, a hold included, and says Confirm Revenue releases it in both settings; the one-click Confirm stays, the owner-decision default (R3-51). No stored output moves (true revenue spec §9.2, §9.3, §10.1, §10.4, §10.5, §10.6, §10.7, §10.8, §17.1, §20).
- Audit round 3, R3-B22 (R3-01, R3-67, R3-68; f0cec80, 84196a5, 88e430f): the copied memos and the batch CSV say what the dashboard says, and no classification moves. The statement memo's decision is the pill's, T7's revenue gate included, and both memos name the money held for review where the revenue is established (R3-01); the package memo names each funder's payments returned unpaid, a warning line per returned payment and the returned payments before the rate, a payment the funder re-debited read as counted once (R3-67); the memos and the batch CSV name the withholding basis the rates divide by (R3-68). No stored output moves (true revenue spec §9.3, §10.1, §13, §20).
- Audit round 3, R3-B23 (R3-49, R3-47, R3-67, R3-62; e482ed4, 47288fb, 686912a, 897d136): the downloads say what the dashboard says, and no classification moves. A package that analyses no statement downloads its counted-plus-held figures, its held count and its revenue counts as empty cells beside its empty True, never 0.0 or 0, the served totals unchanged (R3-49); the package CSV/XLSX name each account of a kept document left out as a repeat or a superseded printout in a `repeated_account_<n>` section with the duplicate notice's words (R3-47), and each returned funder payment in a `returned_funder_payment_<n>` section with the warning's words, in its own unit, a re-debited payment read as counted once (R3-67); the statement CSV/XLSX write the printed account title only where it reads as a bank's designation, an owner's name or a legal-form fragment left out, the JSON download and the payload keeping it as read, the owner-decision default (R3-62). No stored output moves (true revenue spec §9.3, §10.4, §10.8, §17.1, §20).

Cancellation and reversal rows are matched to opposite-direction transactions
by amount, date proximity, and description family when possible. The record
stores the related source location, revenue source type, context signals, match
method, alias/rule, confidence, reason, review status, and mutually exclusive
revenue contribution flags.

A reversal pair zeroes its debit's lender, potential-lender, withholding,
insurance and flag contributions, except where the debit is a confirmed
funder's paid payment: since the owner's ruling of 2026-10-02 (the
underwriter's Q5) such a payment, returned unpaid, leaves paid to lenders and
stays in the withholding rate and the lender count, and the returned funder
payment pass (above, R2-OW13) pairs the bounce forms that name no funder the
same way, without a `reversed_by`. Since the final review of round 2 (F2), such
a payment pairs only with a return dated on or after it (a return printed at a
month's start never takes a later payment), and a package matches a return
whose payment sits in the previous statement of the account (its pass 4).
Since audit round 3, R3-B02 (R3-71), so does a potential lender's counted
payment: its return zeroes the payment on or before it, or none, never a later
one; every other debit keeps classification 5.4's nearest pair either way. And
since the owner's answer of 2026-10-07 to R3-73 ("Count it once"), a returned
payment the same funder re-debits (the same cents off its cycle, or an exact 2x
catch-up, dated on or after the return and within one cadence gap after it)
leaves the withholding rate, `represented_by` naming the re-debit (pass 7c, and
the package's pass 5 across a member boundary); paid to lenders and the lender
count do not move. Since review round 1 of R3-B02, a payment on a weekday two
or more other attempts of the series keep (a twice-weekly schedule or a second
position at the same cents) is no re-presentment, and a 2x debit followed by two
more on the series' cycle within two cycles (a step-up to a new level) is no
catch-up: the returned payment stands. Since review round 2 of R3-B02, every 2x
debit counts toward that level, on the series' cycle or not (a second position
on another weekday), and two 2x debits within two cycles before the candidate are
a level already running, no catch-up either (a 2x debit already taken as another
bounce's catch-up is no level payment); a weekday kept only by attempts
that each follow another return of the series within one cycle is no recurring
phase (a funder re-presenting every bounce on one weekday): each returned payment
counts once.

Classification is applied in this order; the first match wins:

1. Non-posted items, NSF and returned items, refunds and reversals. Since 5.3,
   a returned item includes the banks' abbreviated and French wording
   (`RTN STOP PAY` / `RETURNED STOP PAY`, a stop-payment return of the
   business's own debit, and `EFFETS RETOURNES`), and a
   `DEPOSITED ITEM RETURNED` is a reversal, as `RETURNED DEPOSIT` is. Since
   audit round 3 (R3-B01: R3-80), on a debit only, a returned or unpaid item's
   charge printed with CHARGE or CHG rather than FEE (`RETURNED ITEM CHARGE`,
   `RETURN ITEM CHG`, `UNPAID ITEM CHARGE`) is a returned item too, even when it
   prints the item's payee; a bare `UNPAID ITEM <payee>` is not read (it may be
   the payee's own debit). A credit keeps its reading.
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
   instead (D8); since 5.3 a debt-relief payee (step 5) counts as one. An
   alternative-position payee's membership or balance top-up (its alias followed
   by `PLUS`, `MEMBER`, `MEMBERSHIP` or `BALANCE TOP UP`) is not a repayment and
   matches no known payee. The POS labels include, since 5.3, `RETAIL PURCHASE`,
   `MOBILE PURCHASE` and `PIN PURCHASE`, and the French card forms `C/ACHAT`,
   `ACHAT AU DETAIL`, `ACHAT INTERAC`, `ACHAT PAR CARTE` and `ACHAT EN LIGNE`
   (never a bare `ACHAT`: 'ACHAT DE CREANCES' is a factor's wording).
4. Fees (an overdraft charge included, even when it prints the item's payee),
   transfers, tax, payroll and utilities. Since 5.3:
   - fee wording printed without FEE: the `SVC` / `SERV` charge abbreviations,
     overdraft, handling, batch, item and wire charges (`CHG`, `CHRG`), RBC's
     `INTERAC SC`, the ATM withdrawal service charge, and the French `FRAIS`
     when no French loan or line-of-credit word is beside it. A bare `CHARGE`
     or `CHG` is never a fee word;
   - since audit round 3 (R3-B01: R3-80), on a debit only, the bank's
     stop-payment and OD item charges printed without FEE (`STOP PAYMENT
     CHARGE`, `STOP PAY CHG`, `STOP PMT REQUEST CHARGE`, `OD ITEM CHARGE`) and a
     bare stop-payment row at the row's start (`STOP PAYMENT …`, `ACH STOP PAY
     …`: a stop word is a bank instruction, never a payment), each even when it
     prints a funder's name, so a charge naming a funder is never that funder's
     payment. A payee whose name holds STOP is never read (the bare form is
     anchored at the row's start), a credit keeps its reading, and
     `ACH DEBIT RETURNED <funder>` and `OVERDRAFT ITEM <funder> DES:PAYMENT`
     keep their lender reading (each may be the funder's own debit);
   - payroll includes `PAYROLL` glued to an entry-description suffix
     (`PAYROLLTAX`, `PAYROLLDD`…), the payroll providers the corpus prints
     (Patriot Software, DataPay, Paycor, OnPay, PayWorks, Paycom, Paylocity),
     benefit administrators and retirement-plan recordkeepers (HealthEquity,
     WageWorks, TASC, Ascensus, Human Interest, Guideline) and the French
     `PAIE` and `SALAIRE`. Provider, administrator and French words are read on
     the originator segment only, so a holder named like one of them never
     hides its lender, and none of them applies to a row that names financing.
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
   Since 5.3:
   - on a debit, an admitted payee that the bank prints in separate fields is
     read from those fields when no alias matched (`FIELD_ORDER_PAYEE_FORMS`:
     Chase's 'ORIG CO NAME … CO ENTRY DESCR', Truist's entry description
     first). Amex loans become an alternative position and Amex card payments
     a card payment this way, with match method `known_payee_field_order` and
     rule `<state>_field_order`; LOC wording still wins (D9);
   - the known-payee index reads digits glued to the last word of a multi-word
     alias (see "Normalization and registries");
   - on a debit, a debt-relief payee is `debt_relief`. It is read only after no
     known payee matched, and on the row without its receiver fields, so the
     account holder's own name never makes a row debt relief.
6. Obligation descriptors, debits only, for rows no known payee claimed. A
   transfer between the holder's own accounts (`TRANSFER TO ... TRANSFER OUT`)
   takes none of them. In order:
   - a per-vehicle floor-plan payoff;
   - LOC or line of credit;
   - mortgage or home-equity loan, and since 5.3 the abbreviations `MTG PYMT`
     and `MTGE PAYMENT`;
   - auto or vehicle loan, lease or payment;
   - student loan (a personal loan);
   - a listed bank with loan wording (`LOAN` or French `PRET`);
   - the statement bank's own loan, D5: a transfer to it (since 5.3, to its
     `LOANS` too), its own loan-payment wording, its own `LOAN INTEREST` with no
     payee printed (5.3), its commercial-loan billing, its French loan wording,
     or a loan payment that prints no payee (entity the statement bank).
     Another bank's unnamed loan is a bank loan with no entity;
   - lease, rental or lease-to-own;
   - credit-card payments, including a listed card issuer with payment wording
     and a payment to a card account named only by its type. Since 5.3 the
     wording includes `CREDITCARD` and Navy Federal's `CREDIT CARD RECUR`;
   - unnamed equipment financing, which is a `potential_lender` for review (D4).
7. Rent. Landlord and office rent are never flagged (D3).
8. Checks and subscriptions (`other`). Since 5.3 the cheque spellings include
   the Canadian, credit-union and short forms, anchored at the start and with
   the instrument's number: `CHQ`, `SHARE DRAFT`, `DRAFT WITHDRAWAL DRAFT`,
   `CHK` (and `IMAGE CHK`, `PAID CHK`) and `CK`. A label never makes a row a
   cheque, and a bare `DRAFT` is lender collection wording.
9. Bank-specific lender rules, then the potential tier: the potential registry,
   unknown loan servicers and debt collectors (D10, `MCA SERVICING` included),
   direct-debit loans, explicit repayments (a loan payment that prints a lender,
   a servicer, a person or another bank stays potential, D5), and financing
   words with a payment marker (`other`, review). Since 5.3:
   - a debit whose potential alias belongs to a review entity of a routed flag
     group (`REVIEW_FLAG_ENTITIES`: vehicle financing, mortgages, leases and
     rentals, personal loans, debt relief) takes that flag, marked unconfirmed
     (`review_required`, match method `unconfirmed_flag_payee_alias`). Its
     credits keep the potential registry's exclusion;
   - a loan from the business's own shareholder, owner or director
     (`SHAREHOLDER LOAN`, `OWNER LOAN`, `DIRECTOR LOAN`, `DUE TO SHAREHOLDER`)
     names no lender: on a debit whose descriptor names no organisation, the
     row is `other`;
   - an `MCA SERVICING` payee carries the fixed name 'MCA servicer (funder not
     identified)' (D10): the words print for two unrelated funders.

Statement passes run in this order: duplicates (proven by a repeated printed
running balance); recurrence (D6 and the financing-keyword groups, debits
only); the labels for unnamed potential payees; reversal pairs;
operating-source context (pass 5, with its auction and property-management
branches); the accounts-payable counter-debit guard (pass 6); the true-revenue
pass (pass 7), which tiers every posted credit; the returned funder payments
(pass 7b, the lender side only); the re-presented returned payments (pass 7c,
the lender side only); duplicate finalisation. The
true revenue spec numbers them in its section 6.2, and audit fix batch B12
(I62) added the last three before pass 7b here; the owner's ruling of
2026-10-02 (the underwriter's Q5, R2-OW13) added pass 7b, and the owner's
answer of 2026-10-07 to audit round 3's R3-73 (R3-B02) pass 7c. Recurrence promotes to
`potential_lender`, review only, two kinds of same-amount debit groups on at
least three different dates on a daily or weekly cadence (several rows on one
date count as one): financing-keyword rows of one payee
(`recurring_financing_counterparty`), and rows no rule claimed (`other`, match
method `default`) whose descriptor names a payee and carries no transfer wording
(nor, since 5.3, a transfer template; see below) (`recurring_fixed_debit`, D6).
D6 never takes a row whose words name compensation: a commission (with its
misspellings, such as `COMMISION`), a bonus, a salary, a stipend or a
reimbursement; the row stays `other`. D6 never
takes a card-purchase posting, including
the card formats the POS rule does not read: a posting that starts `PURCHASE`
and its mmdd (after an optional `RECURRING`), and a descriptor with a
`processor*merchant` mark (`TST*NAME`, `SQ *NAME`, `TST* NAME`: a letter or
digit, an optional space, `*`, an optional space, a letter or digit). The star
is read only on a row with no ACH field mark (`ACH`, `CCD`, `PPD`, `CTX`, `WEB`,
`DES:`, `INDN`, `CO ID`, `ID:`, `ORIG CO`, `RMR`), because an ACH entry prints
stars too: in its addenda (`RMR*IV*`), a masked account or an ID. The word
`PURCHASE` alone is not a card mark, since an ACH entry description can print
it.

Since 5.3, D6 also never takes the rows below; they stay `other`. Every 5.3
skip reads the payee's words, never a receiver field, and every one reads the
shared veto on the whole row, so none fires on a row that names financing. The
shared veto reads prefix-tolerant roots, so KOVOCREDIT, CAPITA and FUNDIN veto
too, and so do SETTLE, CRED before IT, ORA, IBLY or a word end, and ACCEPT. It
leaves out only the skip's own matched words, and those hide no name: a vendor
word run together with a lending root is no vendor word, and only reference
numbers may sit inside the Atlas sweep's match.

- A payee whose words are all bank channel words (`BILL`, `RECURRING`,
  `AUTOPAY`, `ATM`, `TELLER`, `CHK`…) names no payee, unless the payee region
  prints an organisation cue. `OTHER`, `BANK`, `WD`, `WDL` and `WDRL` are left
  out, so 'Other Debit', 'Bank Debit' and 'Preauthorized Wd' rows stay in
  review.
- Card postings in the bank formats the POS rule does not read are skipped:
  labels such as `DBT CRD`, `PIN DEBIT`, `CARD TRANSACTION`, `PURCH` and
  `DDA PUR`, Square's 'Card spend' and Wells Fargo's '… authorized on mm/dd …
  Card nnnn'; Wealthsimple's bare-merchant card rows; and the 'NAME, CITY, ST'
  location suffix of Bluevine and Lead Bank (Found) rows. This skip never
  fires on a row that names a bank, an investment firm or an organisation.
- Person-to-person, wallet and card-push rails are skipped (`VIREMENT`,
  `ZEL TO`, `PAYMENT SENT` with its mmdd, Apple Cash, Wise, `IAT PAYPAL`,
  Greenlight). The transfer rule itself is not widened, because it runs before
  the known payee.
- Transfer templates are skipped for a payee that names no organisation:
  `XFR`, `TRF`, `TRSFR`, `TRNSFR`, `TRANSFER` with digits glued on,
  'TO <account type> <number>', a bare online withdrawal, Atlas's Smart Save
  sweep (`SMARTSAVE`, reference numbers, `ATLASFINANCIAL`), and RTP and FedNow
  payments.
- The holder's cash withdrawals in the formats the ATM rule does not read, the
  offset of an ACH batch sent from the holder's own bank portal, and tuition,
  school and childcare billing are skipped.
- A closed list of savings and investing apps is skipped: Stash, Alinea,
  Fidelity's MoneyLine, Albert, Acorns, Robinhood, Coinbase, Betterment and
  Wealthfront.
- Vendors and other named non-lenders are skipped, with the vocabulary the
  spec's D6 lists verbatim: bookkeepers, distributors, manufacturers,
  invoices, uniform, linen and food suppliers, ad platforms, landscaping and
  pest control, royalties and franchise funds, church giving, tolls, betting
  and lotteries, and a Bill.com or Melio payment with an invoice number. The
  words are read on the payee words, never beside a lending word or the
  holder's own name, and a vendor word run together with a lending root
  (`BOOKKEEPINGFUNDING`) is no vendor word. `DISTRIBUT…` also clears recurring
  owner distributions.
- Tax authorities and government agencies printed without TAX, IRS or CRA are
  skipped for a payee that names no organisation, read on the payee region
  only.
- Court-ordered family-support payments are skipped (`CHILD SUPPORT`, a
  family-support registry, a `STATE DISBURSEMENT UNIT`).
- Owner money is skipped: a draw or distribution to an owner, member, partner
  or shareholder, a dividend, a per diem, a guaranteed payment. So is a
  payments platform's payout to a named person.
- A same-amount group under $25 whose payee names no organisation is not
  promoted. The comparison is strict, so a $25.00 group promotes, and a named
  payee promotes at any amount.
- A processor's own charge of $50 or less is skipped, through Square's
  seller-account code or Intuit Payment Solutions. Besides the shared veto, it
  keeps its own guard: never with loan or capital wording.
- An insurer cut short by the ACH field (`INSU`, `INSUR`, `INSURA`, `INSURAN`,
  `INSURANC`) is skipped, read on the payee words only.
- Phone and cable carriers are skipped, matched at the start of the payee's
  leading words.
- A listed card issuer printed alone is skipped: a `card_issuer_context` alias
  whose words lead the payee's words.

The financing-keyword recurrence never promotes a government finance
department (`DEPARTMENT OF FINANCE`, `FINANCE DEPT` and the like), a retailer
named ADVANCE (`ADVANCE AUTO PARTS`, `ADVANCE STORES`) or a family-support
payment. Their single rows stay `other` / `financing_keyword_review`.

Recurrence never makes a counted lender: nothing is counted without a named
lender. The recurring-debit view
(`detection.recurring_debits`, the CLI's "Recurring fixed debits") lists both
kinds, grouped by entity and amount. The groups D6 no longer promotes (the 5.3
skips and the $25 floor) leave it too, and leave `batch.py`'s
`recurring_debit_groups`.

An unknown payee is named from its descriptor (D11). Originator-name labels are
removed; the text is cut at the first ACH field segment (DES, ID, INDN, IND
NAME, CO ID, TRACE, SEC, EED, TYPE and similar); channel words and reference
tokens (digits, masked numbers, months) are dropped; and at most four words are
kept. Without an organisation cue (LLC, INC, CORP, FUNDING, CAPITAL, FINANCIAL,
FINANCE, BANK, CREDIT, LENDING, ADVANCE, GROUP, HOLDINGS, SERVICES or a
legal-form suffix) the entity is `Unidentified lender obligation`, so a
person's name is never published as a lender. Payees are grouped for recurrence
by these words, so one payee keeps one name across dated descriptors and two
unnamed payees are never merged. D6 also groups by the digits of a masked
recipient account printed after `TO` (`To ....1234`, `TO XXXX1234`, `TO ***1234`,
`TO #1234`), so payments to two recipient accounts are never one payee. The
name never takes those digits.

Since 5.3 the naming follows these rules too:

- a legal form (`LLC`, `INC`, `CORP`, `CORPORATION`, `COMPANY`,
  `INCORPORATED`, `LTD`, `LIMITED`, `LP`, `LLP`, `PLLC`) counts as a cue only
  after the name's first word;
- a name made only of cue words names no organisation, and neither does `CO`,
  which is no longer a cue (it is also Colorado's state code in
  'NAME, CITY, CO');
- the name ends at its first legal form after the first word;
- trailing connectors (`OF`, `AND`, `THE`, `DE`, `DU`, `DES`), `PAID` and a
  leading `AND` are dropped;
- bank template prefixes printed before the payee are removed (`PMNT SENT`,
  `PAYMENT SENT`, `CORPORATE ACH`, `DOMESTIC ASSIST WIRE`, `HIP CREDIT SENT`,
  `RETAIL PURCHASE`, the `DBCRD PUR AP` card forms and Truist's
  `ACH CORP DEBIT` / `ACH CORP CREDIT`), so two recipients paid through one
  template are never one payee;
- a Truist `ACH CORP DEBIT` name is published only when a whole legal-form
  word lies inside its 16-character company field;
- a wire is named by its beneficiary (after `BNF`, or after the account label
  of Chase's 'Wire Transfer Via: <bank> A/C: <beneficiary>'), and the name ends
  at its first organisation cue after its first word;
- Truist's `CUSTOMER ID`, Huntington's `INSTR` and the wire fields `SRF`,
  `RFB` and `IMAD` are field segments;
- a card network's 'NAME, CITY, ST' line (with no ACH field mark) is named by
  the printed name before the first comma alone;
- an `MCA SERVICING` payee carries the fixed name 'MCA servicer (funder not
  identified)' (D10).

The Potential Lenders tab lists each unnamed payee key on its own line (5.3).
An unnamed potential payee's rows (entity 'Unidentified lender obligation' or
'MCA servicer (funder not identified)') carry `potential_payee_label`, shared
by the rows of one payee key (entity, rule, D6 payee words, amount and masked
recipient). The label names the entity, a recurrence's cadence and the amount,
never a payee word: 'Unidentified lender obligation (weekly, 450.00)', with
' #2' for a second key with the same label. The tab, the metric, the package
and the tab's click filter read the label; `canonical_entity` and each ledger
row's tag do not change. Every potential lender row, named or not, also
carries `potential_payee_key` (the owner's request of 2026-10-06, R2-OW18):
an amount-free digest of its payee key (the entity, the D6 payee words and the
masked recipient; the first 16 hex characters of their SHA-256), so no payee
word is published. Only `analysis.lender_payment_changes` reads it, to follow
a payee across an amount change; None on every other row.

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

Since 5.3 (2026-09-27):

- **Glued digits.** The known-payee index also reads the last word of a
  multi-word alias with digits glued on, when that word has at least three
  letters (`GOAT ADVANCE` matches `GOAT ADVANCE1234`). No other table reads
  glued digits, and an alias whose last word has one or two letters stays
  strict.
- **The debt-relief index.** `DEBT_RELIEF_ALIASES` is a table of its own, not a
  group registry, read through its own index (`match_debt_relief_payee`) only
  after no known payee matched, on debits, on the row without its receiver
  fields. It reads run-together forms (`FORTHPAY`, `RAMPAYMENTS`) as the
  known-payee index does. It is never a longest-alias peer of the known-payee
  groups, because a debt-relief firm in the holder's own name would outrank the
  funder.
- **`FIELD_ORDER_PAYEE_FORMS`**, hand-kept on the owner's ruling: the printed
  forms, in the bank's field order, of admitted payees whose bank prints the
  originator and the entry description apart (Chase's 'ORIG CO NAME … CO ENTRY
  DESCR', Truist's entry description first). Today it holds American Express
  Loans and the American Express card payment. They are read as regular
  expressions on the normalized row, on debits only, when no alias matched.
  The ledger validator refuses an entity that is not admitted in a known-payee
  group, and a form that does not compile.
- **`REVIEW_FLAG_ENTITIES`**, rendered from the ledger: each review entity of
  the vehicle, mortgage, lease, personal-loan or debt-relief group whose
  business type is known, mapped to its group. Its debits take that flag,
  marked unconfirmed, and its credits keep the potential registry's exclusion,
  because its aliases stay in `POTENTIAL_LENDER_ALIASES`.
- The D6 vocabularies of non-lender brands (savings apps, vendors, government
  agencies, payroll providers, telecom carriers) live in the classifier, as
  `_PAYROLL_PATTERNS` and `_TRANSFER_PATTERNS` already do. A name joins only
  after a collision check against every registry table and ledger alias prints
  no hit.

The record stores the source description, normalized description, canonical
entity, date, amount/direction, bank/account, source location, match method,
matched alias/rule, confidence, human-readable reason, review status, duplicate
status, flagged group, and every metric contribution flag.

## Metric definitions

- `lenders_detected`: distinct canonical entities with qualifying posted
  `confirmed_lender` debit rows (a funder whose every payment was returned
  unpaid included, R2-OW13).
- `potential_lenders_detected`: distinct Potential Lenders lines with
  qualifying posted `potential_lender` debit rows (5.3): a named payee's
  canonical entity, or an unnamed payee's `potential_payee_label`.
- `potential_lender_debit_count` and `potential_lender_debit_total`: qualifying
  posted potential-lender debit rows and their absolute sum. These rows remain
  excluded from confirmed lender totals and confirmed withholding.
- `lender_debit_count`: qualifying posted confirmed-lender debit rows.
- `total_lender_debits`: absolute sum of those exact rows.
  Both are paid to lenders: a funder payment returned unpaid is in neither.
- `returned_funder_payment_count` and `returned_funder_payment_total` (owner
  ruling 2026-10-02, the underwriter's Q5; R2-OW13): the confirmed funders'
  payments returned unpaid (rows with `returned_funder_payment_by`) and their
  absolute sum, out of the paid figure and in the withholding numerator.
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
  `source_locations`, and since 5.3 `review_required`, true when any counted
  row of the payee requires review, as a routed unconfirmed payee's rows do),
  in flag-group order, then by total debited plus total
  credited, then by payee. `count` and `total_debited` are debits only; a payee
  whose counted rows are all credits has an entry with a `count` of 0. The
  payee is the canonical entity, or the group label when the descriptor names
  none; the cadence (`daily`, `weekly`, `biweekly`, `monthly`, `irregular` or
  `single`) comes from `analysis.cadence.describe_cadence`, over the dates of
  every counted row, debit or credit, as do `first_date` and `last_date`.
- `detection.lender_payment_changes` (the owner's request of 2026-10-06;
  R2-OW18): one item per decrease, increase, cadence change (`cadence_change`),
  pause, catch-up (`catch_up`: an exact 2x to 6x payment after one or more
  missed scheduled payments that no pause or stop line names; the owner's
  answer of 2026-10-07 to audit round 3's R3-25), new stream (`new_stream`) or
  stop of a lender's regular payment in the statement, each with `kind`, `lender`, `lender_label`, `lender_state`
  (`confirmed` or `potential`), `position`, `positions` and `scope`, a change's
  amounts, schedules and `change_percent`, a stop's `quiet_business_days`,
  `grace_business_days` and `stop_confirmed` (never true inside one statement)
  and its notes. Information only: no lender, withholding, revenue or gate
  figure reads it. An empty list means checked, no change; a payload stored
  before the check has no key and reads "not checked".
- `verified_revenue_total` and `verified_revenue_count`: posted credits marked
  `contributes_to_verified_revenue`.
- `unverified_deposit_total` and `unverified_deposit_count`: posted credits that
  could be operating revenue but carry no proof (`unverified_deposit`). Since
  5.6 this is counted plus held: the counted part (`counted_flagged_total`) is
  in True revenue and only flagged, and only the held part needs review: its
  total (`excluded_pending_review_total`) feeds `revenue_review_required` (spec
  T2, T7), and `revenue_review_items` is the held-row count the review badge
  shows, not a gate input. `potential_revenue_total` is its deprecated alias.
- `true_revenue_total` and `true_revenue_count` (5.6): verified plus counted
  credits, the headline; `true_revenue` is its deprecated alias (T9). The
  counted and held figures are also split by reason
  (`counted_flagged_by_reason`, `excluded_pending_review_by_reason`).
- `non_revenue_by_reason` (audit round 2, R2-OW03): the `non_revenue` credits
  that carry a code `REVENUE_TIER_REASONS` files under `non_revenue`
  (`zelle_excluded`, `government_no_purpose`, `asset_sale_proceeds`),
  `{code: {count, total}}`, so the
  dashboard and the exports state the excluded Zelle deposits beside True; the
  package sums it over its kept members, never nulls it where revenue is not
  established, and refuses its money (keeping its counts) under a currency
  refusal. `None` on an analysis saved before 5.6. It is the stored reading's;
  the counted reading's carries no `zelle_excluded` (the owner's amendment of
  2026-10-06 to the underwriter's Q3).
- `zelle_deposits` (the owner's amendment of 2026-10-06 to the underwriter's
  Q3, R2-OW17; served, never stored): `{counted_as_true_revenue,
  setting_applied, count, total, by_tier: {tier: {count, total}}}` over the
  account's Zelle rows in the reading served, its parts in True (verified plus
  counted), held and out; served under Yes on every account with Zelle rows and
  under No only where the exclusion alone would misstate where the Zelle money
  sits. The stored account carries `zelle_counted_reading`, the lean edits that
  turn its stored reading into the counted one.
- `non_revenue_total` and `non_revenue_count`: funding, identifiable own-account
  transfers, contributions, returns, refunds, corrections, identifiable rewards
  and interest, proceeds, and proven duplicate credits.
- `maximum_revenue`: verified revenue plus unverified deposits, that is True
  revenue plus the held credits.
- `effective_nsf_count` (R18): the days that end with a negative balance in the
  validated daily ledger, on the basis in `nsf_source` (printed days by default,
  every calendar day when Settings carries the balance over inactive days;
  `analysis/nsf_days.py`). `nsf_or_return` rows are evidence and never counted.
  As served to the dashboard, `nsf_days` lists exactly the days it counts
  (`date`, `ending_balance`, the ledger day's `source`, and the `source_location`
  of the posting that ended the day, or of the last posting before a day with
  none); it is empty when the count is not computable, and no download carries it.

The dashboard's transaction chips follow this split (owner request 2026-09-27).
**NSFs** shows the days the NSF tile counts, each by the posting that ended it,
and its header counts days ("N days ending negative"), so it always equals the
tile; a row that ended several days is shown once, and a day that went below
zero only during the day is not listed. In a package each member account's days
are matched to its own rows. **NSF fees** lists the `nsf_or_return` rows (the
bank's NSF fee and returned-item lines), which may exist when no day ended
negative.

Revenue must reconcile from the authoritative rows:

`verified revenue + unverified deposits + non-revenue = total posted credits`

and, since 5.6, by tier:

`verified + counted + held + non-revenue = total posted credits`, with
`True revenue = verified + counted`.

Reviewer confirmation changes a held or counted row to `verified_revenue` (tier
`verified`); rejection changes it to `non_revenue` (tier `non_revenue`). A credit
a rule verified can be rejected, never confirmed. Reset restores the row's first
state and tier. A Zelle deposit the owner's policy excluded (`zelle_excluded`,
`REVIEWABLE_NON_REVENUE_REASONS`) can be confirmed back into revenue
(`verified_revenue`, tier `verified`, its reason kept) and reset to
`non_revenue`, never rejected (it is non-revenue already); the re-analysis
replays a confirm on it and reports a stored reject as decided by the rules.
Every other `non_revenue` credit has no review (audit round 2, R2-OW03; the
underwriter's Q3 of 2026-10-02, "I can review"), an `asset_sale_proceeds` one
included (R2-OW06). Since the owner's amendment of 2026-10-06 to the
underwriter's Q3 (R2-OW17) a decision is validated on the Zelle reading the
reviewer sees, and the latest decision on a posting sets every reading: a
reading that accepts it takes it, and a reading that refuses it returns to its
analysis state (so a reject taken under Yes resets the stored reading's
excluded row, clearing an earlier confirm); the re-analysis replays the same
rule, each reading on its own. The API, package aggregation, filters, evidence tables, and
exports are rebuilt from the updated record. An analysis saved before 5.6
carries no tier: its review follows the three-state rules and its True revenue
is not established.

Credits, funding deposits, duplicates proven by a repeated printed running
balance, refunds, reversals, NSF returns, insurance, flagged obligations, fees,
and all other non-lender states are excluded from lender totals.
Identical-looking rows without running-balance proof are retained because they
may be legitimate repeated transactions.

## Withholding rate

The default mode is `true_revenue` (the owner's ruling of 2026-10-02, the
underwriter's Q7, "2 Make True revenue the default"; audit I34; true revenue
spec T8, §11; R2-OW14): True revenue, verified plus counted credits (label
"True revenue"), divides the confirmed withholding rate and the potential
exposure. The earlier eligible-deposit policy, the default until then, stays
selectable as `legacy_eligible_deposits`:

`eligible_deposits = effective_total_deposits - recognized_lender_funding_credits`

This legacy figure is always published as `legacy_eligible_deposits`, whatever
the mode; in the legacy mode `eligible_deposits` equals it. The True-revenue
and verified bases follow the Zelle reading served (the owner's amendment of
2026-10-06 to the underwriter's Q3, R2-OW17): the counted reading's metrics are
`compute_metrics`' own, so the setting moves the rate where Zelle counts; the
legacy basis reads no tier and never moves with it.

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

`WITHHOLDING_DENOMINATOR_MODE` selects the basis:
`WITHHOLDING_DENOMINATOR_MODE=true_revenue` (the default; label "True revenue"),
`WITHHOLDING_DENOMINATOR_MODE=legacy_eligible_deposits` (the legacy figure
above, label "Legacy eligible deposits") or
`WITHHOLDING_DENOMINATOR_MODE=verified_revenue` (verified classified revenue,
label "Verified revenue"). An unset, empty or unknown value reads as the
default (`DEFAULT_WITHHOLDING_DENOMINATOR_MODE` in `analysis/revenue.py`, which
`Settings`, `load_settings`, `compute_metrics` and the `Metrics` dataclass
read), and no run or deploy file in this repository sets
`WITHHOLDING_DENOMINATOR_MODE` (the tryout host's environment is the
`fly.toml` on its deploy branch, whose `[env]` did not set it either on
2026-10-02), so the tryout host divides by True revenue. In
either revenue mode `eligible_deposits` carries the selected denominator: the
metrics (`analysis/metrics.py`) and the revenue rebuild (`analysis/revenue.py`)
overwrite it with the Verified or True revenue total, and `withholding_denominator`, `potential_withholding_denominator` and
`eligible_deposit_definition` follow it, so the subtraction above describes the
legacy mode only and the legacy figure stays in `legacy_eligible_deposits`
(audit I62). A statement whose True revenue is $0 has no rate on the default
basis and sets `withholding_review_required`, its note naming the basis
("withholding rate is unavailable because True revenue is zero or missing").
Since audit round 3, R3-B03 (R3-20), so does a True or Verified basis above $0
and under `WITHHOLDING_BASIS_FLOOR` (500 in the statement's own unit,
`REVENUE_REVIEW_HELD_FLOOR`): no rate, no potential exposure and no potential
lender's basis or exposure, `withholding_review_required` and
`withholding_basis_below_floor`, and a note naming the basis and the floor
("withholding rate is unavailable because True revenue (1.00 USD) is under the
withholding basis floor (500.00 USD)"); never a gate, and the legacy basis
bypasses it (`withholding_basis_publishable` decides every published rate and
exposure). A review decision refreshes everything the basis feeds on a True or
Verified basis (R3-13): the rate, each potential lender's basis and exposure
and the basis notes.
A stored analysis whose metrics carry no mode was made on the legacy basis and
keeps it: `normalize_withholding_denominator_mode` reads a missing or unknown
stored mode as `legacy_eligible_deposits`, so the review rebuild, the package
and the dashboard read it so. The lender census (`tools/lender_census.py`, G7)
computes its snapshot on the legacy basis, named explicitly, so it compares one
basis across trees. A package in the `true_revenue` mode deducts only the members'
internal-transfer credits that are verified or counted (the legacy mode deducts
them all, the verified mode none), and in a revenue mode a member whose figure is
not established leaves the package with no withholding rate and no potential
exposure and sets `withholding_review_required` (spec §11, §20). The statement
follows the same rule (the final review of round 2, F1): where its mode is
`true_revenue` and its revenue is not established, or `verified_revenue` and
its Verified figure is not, the served copy (`analysis/revenue_view.py`)
publishes no `withholding_rate`, `potential_withholding_exposure` or potential
lender's exposure, sets `withholding_review_required` and
`withholding_basis_unestablished`, the downloads leave the basis figures empty
and the CLI prints them as N/A; the package marks such a member's row and its
own totals the same way, and the statement and its package go to review. The
legacy basis never moves with it. A package whose ready members were analysed
under different bases (a job stored before R2-OW14, legacy or with no mode,
beside a new one; audit round 3, R3-B03: R3-27) publishes no package rate or
potential exposure over their sum, names each member's basis
(`withholding_basis_mixed`, `withholding_basis_by_member`) and goes to review;
a failed member contributes no basis. A member row divides by the basis it
prints (R3-72): where the package moved the member's basis, its rate and
exposure are recomputed over it. A deposit the
package passes take out of True (the underwriter's Q6 (2026-10-02), R2-OW15)
leaves the revenue basis it was in: the `true_revenue` mode loses the moved
credits stored verified or counted, the `verified_revenue` mode those stored
verified; the legacy basis and the numerator are untouched. A deposit the
package holds as a transfer between the business's accounts (the underwriter's
Q4 (2026-10-02), R2-OW16) is such a moved credit, stored counted, so only the
`true_revenue` mode loses it; a held deposit the package only annotates never
moves the basis. The legacy value
`confirmed_true_revenue` is accepted and normalized to `verified_revenue`; any
other unknown value reads as the default in the environment and as the legacy
basis on a stored analysis (above). API and UI output include
`withholding_denominator_mode` and `withholding_denominator_label`, and the
dashboard's Withholding Basis card (it was "Eligible Deposits") names the basis
in its note ("True revenue: verified plus counted credits"; the legacy basis's
"Gross deposits less lender funding (not True revenue)"); the mode is never
switched implicitly when revenue classification is available.

The formula is:

`withholding_rate = abs(paid lender debits + returned funder payments) / withholding basis * 100`

The numerator (`withholding_numerator`) is the exact total of the rows marked
`contributes_to_withholding_rate`, the rows of the lender transaction filter:
the confirmed lender debits paid (`lender_debits`, the lender evidence records)
plus, since the owner's ruling of 2026-10-02 (the underwriter's Q5; R2-OW13),
the confirmed funders' payments returned unpaid (`returned_funder_payment_total`):
the scheduled obligation stands, so a bounced payment leaves paid to lenders and
stays in the rate. A package sums its members' numerators. Since the owner's
answer of 2026-10-07 to audit round 3's R3-79 ("Exclude worded payoffs
(Recommended)"; R3-B03), a confirmed funder's paid debit whose own text prints
PAYOFF, PAY OFF, PAY-OFF, PREPAY, PRE-PAY, PREPAYMENT, BUYOUT, BUY OUT or
PAYOUT (whole words; `lump_sum_payoff`, the word as printed) leaves the
numerator and stays in `lender_debits` and the lender count
(`lump_sum_payoff_total`, `lump_sum_payoff_count`, the detection's
`lump_sum_payoffs` and a note name it); a credit and a potential lender's debit
read as before, and a payoff attempt the bank returned stays in the rate as Q5
rules. The basis is the
selected denominator above. Full precision is retained internally;
rounding occurs only for display. A zero or missing denominator, or a True or
Verified one under the withholding basis floor, returns no rate and sets
`withholding_review_required`. Lender payment changes (the owner's
request of 2026-10-06; R2-OW18) are information only: payment changes never
enter the numerator, the basis or the rate.

Potential lender exposure is a separate review metric over the same withholding
basis:

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
`CARD_ISSUER_CONTEXT_ALIASES`, `PREMIUM_FINANCE_ALIASES`, `BANK_NAME_ALIASES`,
`POTENTIAL_LENDER_ALIASES` and, since 5.3, `DEBT_RELIEF_ALIASES` and
`REVIEW_FLAG_ENTITIES`) and `docs/lender-registry-evidence.md`, and
commit the three files together. Never edit the GENERATED block by hand:
`tests/test_lender_registry_drift.py` fails when the committed tables are not
the rendering of the committed ledger.

The constants after the GENERATED block are hand-kept.
`PAYEE_GROUP_REGISTRIES` wires the rendered tables to the known-payee matcher.
`PAYOUT_CREDIT_ENTITIES` (financing-group payees whose credits are the holder's
own sales), `OWNER_NAMED_PAYEES`, `BARE_PLATFORM_NAMES`, `BARE_BRAND_NAMES`,
`PREMIUM_FINANCE_INSURER_ALIASES`, `MERGED_REGISTRY_ENTITIES`,
`REATTRIBUTED_REGISTRY_ALIASES` and, since 5.3, `FIELD_ORDER_PAYEE_FORMS` are
inputs of the ledger validator and change only on an owner ruling. Insurance
aliases (`INSURANCE_PROVIDER_ALIASES`) and operating-revenue aliases and source
types (`OPERATING_REVENUE_SOURCE_ALIASES`, `OPERATING_REVENUE_SOURCE_TYPES`) are
not in the ledger and are edited in that module directly.

An alias names the financing business, never a bare platform or a brand that
also sells goods; the validator refuses both. The one place a bare brand or
card issuer is allowed is a `card_issuer_context` or `bank_name` entity, whose
rules read it only beside card-payment or loan wording. Cover aliases, OCR variants,
token boundaries, precedence, both directions, and contribution flags in tests.
Do not add statement-specific description checks in parsers, metrics, API
routes, or frontend code.
