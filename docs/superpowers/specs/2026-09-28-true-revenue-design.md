# True and verified revenue: design

- **Date:** 2026-09-28
- **Branch:** `true-revenue`, from `lender-detection` at `c106634` (classification 5.4, `ANALYSIS_STAGE_VERSION` 23)
- **Owner:** Gustavo
- **Status:** draft for the owner's review
- **Replaces:** the lender work, which the owner set aside on 2026-09-28 for this project
- **Evidence (private, never committed):** `lender-research/revenue/`: `trace_report.md` (the pipeline trace), `definition_memo.md` (the eight questions and their measured options), `digest_families.md` and `hunt_result.json` (nine payer families, each reviewed by two independent Opus verifiers; 60 structural misses found in 437 fabricated statement shapes). Every example in this spec is fabricated in the bank's format. Only public companies (processors, marketplaces, lenders, agencies, large retailers) are named.

## 1. Why

Most uploads show $0 of verified revenue, and some of those merchants plainly had revenue.

- **Corpus:** 2,468 distinct reconciled statements with credits, $276.9M of credits. Under the 5.4 rules, 7.2% of credits are verified, 75.8% are unverified and 17.0% are non-revenue. 1,819 statements (74%) show $0 verified.
- **Tryout host:** 111 uploads, $13.8M of credits. 13.4% is verified, and 67 uploads show $0.

The trace and the hunt found two separate causes.

1. **A definitional gap.** The headline figure (the Monthly Statements' "True deposits", the chart, the cards) is the *proven-only* figure: credits a rule can prove are operating income, plus deposits an analyst confirms. Underwriters and MoneyThumb start from total deposits and remove what is known not to be revenue. MoneyThumb's own documentation, quoted in `MONEYTHUMB_MEMO.md` §7, says True Revenue removes "non-qualifying transactions like transfers, loans and other items". The app already computes that second figure as "Revenue Upper Bound" (`maximum_revenue`), but nothing reads it as revenue.
2. **Vocabulary and precedence bugs.** Card-processor, marketplace, healthcare, government, accounts-payable, invoice-wire and auction revenue is missed because the rules know too few words. Bank layouts (Chase's glued `Sec`, split originator and entry fields, 16-character truncation) hide the words the rules do know. Recurrence is available only to 31 registry names, and a registry name without a settlement word never verifies alone. Some rules also make real revenue `non_revenue` where no review can reach it (REIMBURSEMENT on Medicaid claims, a street `LN` read as LOAN, a Chase book transfer from a customer).

The revenue figures a funder reads therefore understated the business. And because every unverified deposit gates the package decision, 95.6% of the 2,493 reconciled corpus statements need revenue review today.

## 2. Owner rulings (2026-09-28)

The owner took every recommended option of the definition memo. These rulings are binding on this spec.

| # | Question | Ruling |
|---|---|---|
| Q1 | What the headline means | **Two figures.** "True revenue" (the headline, the chart and Monthly Statements) is all posted credits minus known non-revenue minus the credits held out until confirmed. "Verified revenue" is the part with positive proof. It is shown beside True revenue and stays selectable as the withholding basis. |
| Q2 | Cash, branch, teller, ATM and bare Deposit lines with no payer printed | Counted in True, flagged "no payer printed", never Verified. Bare transfer wording with no counterparty stays **out** until confirmed. |
| Q3 | Check deposits (mobile, remote, ATM, branch) | Counted in True, flagged, never Verified. |
| Q4 | Person-to-person (Zelle, Interac, RTP, wallets) | Counted in True, flagged, never Verified. Repeated round sums from one sender, and senders with the holder's name, stay **out** until confirmed. |
| Q5 | Incoming wires | Verified when the same company wires twice or more in the statement, and when the wire cites an invoice or PO. Other wires with a named sender are counted in True, flagged. A wire with no sender, or with the holder's own name, stays **out** until confirmed. |
| Q6 | Named ACH or EFT payers | Verified when the payer repeats, prints a company form, or is a government or healthcare payer. One-off informal names are counted in True, flagged. Lenders, insurers and the holder never count. |
| Q7 | An auto lender paying a dealer | Revenue and Verified when the entry names a funding or purchase. Other credits from listed auto lenders stay financing. |
| Q8 | "Payroll" or "Salary" credits from another company | **Out** of True until confirmed. |

The owner's standing instructions also bind this work. Non-revenue rules run first: loans, transfers, refunds and owner money never become revenue. Tests use fabricated rows only. The path is spec, then plan, then implementation, with independent reviewers.

## 3. Goals and non-goals

**Goals**
- Two figures and one per-row contract. Every posted credit carries exactly one of four outcomes, and the four add up to the posted credits.
- The vocabulary and precedence fixes of the nine hunt families, each as its verifiers amended it, plus the structural misses rated high or medium that this spec takes in (§7.12).
- Precedence that keeps every non-revenue rule first, with a closed list of named narrowings (§6.3) and guard checks that prove nothing else moved.
- A dashboard whose headline is True revenue, with Verified revenue beside it, that never prints $0.00 where revenue was not established.
- A review queue aimed at the deposits held out of True, and a package decision that no longer stops on every unproven deposit.
- Stored payloads that still render, marked outdated, and field names whose meaning never changes silently.

**Non-goals**
- Lender detection. Debit rules do not change. The one shared change, the street-`LN` guard in the normaliser (§7.11), must move no lender or flag (§14.3, G7).
- Payer-wide review decisions ("apply to every row of this payer"): a recommended follow-up (§17, OQ1).
- The rulings the families left open that this spec does not decide (§15).
- Recurrence across statements, accounts or packages. "Repeats" is always within one statement.
- The text-first reader, and any deployment to the tryout host.

## 4. Decisions this spec makes (the owner may overrule any of them at review)

The rulings above did not settle these. Each is numbered T1 to T17 so the plan and the reviews can cite it.

- **T1. Three revenue states stay; a tier is added.** `revenue_classification` keeps its three values (`verified_revenue`, `unverified_deposit`, `non_revenue`), so every consumer that reads them keeps its meaning. Two new record fields carry the per-row contract: `revenue_tier` (`verified`, `counted_flagged`, `excluded_pending_review`, `non_revenue`) and `revenue_tier_reason` (§5.3). Both `counted_flagged` and `excluded_pending_review` are `unverified_deposit` rows: neither is proven. Rejected alternative: a fourth state. It would break every consumer that validates three states (`REVENUE_STATES` in `webapp/app.py`, the "exactly one state" check in `analysis/metrics.py`) and every stored payload's reading of them.
- **T2. Counted is the default.** An unverified posted credit is `counted_flagged` unless one of the held reasons of §5.3 names it (§8 tests them). This is what "all posted credits minus known non-revenue" means row by row.
- **T3. The holds are a closed list** (§5.3). Besides the owner's own (Q2 transfer wording, Q4, Q5 and Q8, and the holder's name of Q4 to Q6), it holds six kinds of row that subtraction would otherwise count: a direction conflict, an insurer's customer-payment credit (T14), a payer whose name reads as financing (T4), a payer the statement also debits as a lender, benefit and pension credits, and bare return or adjustment wording. Each is reviewable.
- **T4. The financing-named payer hold.** Under subtraction, an unregistered funder's advance with a neutral entry (`FABFUND CAPITAL DES:PAYMENT`) would count as revenue. That breaks the standing rule that loans never become revenue. A credit whose payer name carries a financing root (§8.1) is therefore held unless a verifying rule has claimed it. Approximate cost, measured on the memo's deposit types: $5.0M (1.8% of corpus credits) in 282 statements. It errs in the safe direction: customers named "Advanced …" or "Capitol …" are held too.
- **T5. Newly named non-revenue.** Wording that was harmless while unverified credits never counted is now named, because it would otherwise count: the unambiguous return codes, tax-refund abbreviations, SBA and EIDL disbursements, Square Capital's `SQ CAP` spelling, and account-verification micro-deposits (§7.11). Each is a narrow, printed marker. The measured moves are reported in the census.
- **T6. Review.** Confirm makes a row `verified_revenue`, because an analyst's confirmation is proof. Reject makes it `non_revenue`. Reset restores the row's initial state and tier. Reviewable rows are every `counted_flagged` and `excluded_pending_review` row, and, new, every row a rule verified. A reviewer can reject a false verification. The new rules verify roughly three times today's dollars, and the government verifier required either this or a declaration that rule-verified rows are final. Rows a non-revenue rule decided stay outside review, as today (§15).
- **T7. The package gate.** A package needs revenue review when a member has a direction conflict, when its held credits are 10% or more of its posted credits, or when its revenue does not reconcile. Counted, flagged rows never gate: the owner ruled that they count. On the memo's approximate deposit types, 24.6% of statements have held credits of 10% or more. 39.9% have at least one held row. Today, 95.6% of statements are gated. The 10% is one constant, `REVENUE_REVIEW_HELD_SHARE`.
- **T8. Withholding.** The default denominator stays legacy eligible deposits. Verified revenue stays selectable, and True revenue is added as a third selectable basis (MoneyThumb describes its `mca_withhold_percent` against true revenue), but it is not the default (§11).
- **T9. Field names.** Names whose meaning is kept stay. The deprecated aliases `true_revenue`, `contributes_to_true_revenue` and `true_revenue_evidence` are **repointed** to the new True revenue, because a payload whose `true_revenue` differs from the "True revenue" on screen is a trap for every reader of the JSON and the exports. `confirmed_true_revenue*` stays an alias of Verified; the word "confirmed" says proof. `potential_revenue*` stays an alias of unverified (both tiers). Nothing in `webapp/static/app.js` reads the repointed names. The tests that pin them are re-pinned (§13).
- **T10. Old payloads.** A payload analysed before 5.6 carries no tier. It is served as stored and marked outdated. True revenue shows N/A with a Re-analyze action, and the served copy nulls `true_revenue`, so the old alias is never read as the new figure. Its verified figure is shown under the outdated notice (§12).
- **T11. Numbered-company payers are never Verified.** A Canadian numbered company paying the holder (`<digits> ONTARIO INC`, BMO's cut `<digits> ONTA`) may be the owner's holding company. Such a credit is counted in True, flagged `numbered_company_payer`, and never verified by a payer rule (§7.5, §8.5, §8.6). The amended accounts-payable rule required this exclusion. Approximate size, measured with §5.2's pattern on the memo's rows: $11.1M (4.0% of corpus credits) in 183 rows. Whether it counts at all is OQ3.
- **T12. Government payers: Q6 overrides the recurrence gate.** The government verifier asked that a single public-rail credit stay unverified. The owner's Q6 ruling (a government payer is proof, with Treasury "MISC PAY" among its examples) supersedes that. Every veto the gate was meant to back up is kept and widened (§7.6). The residual is a one-off grant or refund printed without its purpose word.
- **T13. A transfer from a named third party belongs to the person-to-person family.** "Online transfer from <person or company>" is counted and flagged `p2p`, under the same round-sum and holder holds. Only transfer wording with no counterparty is held (Q2). The memo held both, so True may land up to 1.5 points above the memo's 72.7% ($4.2M of named-transfer rows).
- **T14. Insurers stay out of True but become reviewable.** A credit from a listed insurer that prints customer-payment wording (a DRP payment to a body shop, a vendor payment, an agent's commission) is held as `insurer_payer` rather than decided `non_revenue`. It still never counts (Q6), but an analyst can confirm it. The one insurer credit that verifies is the healthcare claim payment, `HCCLAIMPMT` (§7.7).
- **T15. Property-management platforms verify by recurrence and carry a chip.** Buildium, AppFolio and Landlord Studio verify only by recurrence, and their verified rows show a "Property-management collections" chip. This is the reviewer's recommended option (b), "verified plus a flag", pending the owner's word on rent collected by a manager.
- **T16. The auction rule is adopted as amended.** A credit from a dealer-only wholesale auction verifies without recurrence when it prints the auction's observed payout form (§7.8).
- **T17. Two classification versions.** 5.5 carries the fixes (§7) under today's definition, so the census can measure them alone. 5.6 carries the definition (§5, §8, §10). They ship on one branch, each with its own stage bump and census (§14, §16).

## 5. Definitions and the per-row contract

### 5.1 The two figures

- **True revenue** = posted credits − known non-revenue − credits held out until confirmed = `verified` + `counted_flagged`.
- **Verified revenue** = the credits with positive proof: a rule of §7 or §8 verified them, or an analyst confirmed them. Verified revenue is always a subset of True revenue.
- **Held for review** = `excluded_pending_review`: not in True until an analyst confirms the row.
- **Non-revenue** = what a non-revenue rule (§6) decided: reversals, financing proceeds, insurance proceeds, own-account transfers, duplicates and the rest.

The reconciliation identity becomes:

`verified + counted_flagged + excluded_pending_review + non_revenue = total posted credits`

`maximum_revenue` (the old "Revenue Upper Bound") keeps its value, verified plus unverified, which is now True plus held.

### 5.2 Terms

Every term below is read on the credit's **revenue text** (§7.0), never on a receiver field. A receiver field is `INDN`, `IND NAME`, `IND ID` or `RECEIVER NAME`, where the bank prints the account holder.

- **Posted credit:** amount > 0 and `is_posted`.
- **Payer name** depends on the channel:
  - an ACH or EFT row: D11's payee words (`_unknown_payee_tokens`, at most four) read on the row before its receiver fields, after the bank template prefixes (`_PAYEE_TEMPLATE_PREFIX`, plus `BUSINESS TO BUSINESS ACH CREDIT`, `CCD DEPOSIT`, `CTX DEPOSIT`, `ELECTRONIC DEPOSIT FROM`, `ELECTRONIC CREDIT`, `ACH DEPOSIT`, `DEPOSIT FROM`, `PREAUTHORIZED CREDIT`, `EFT CREDIT`, `DIRECT DEPOSIT`, `MISC PAYMENT`, `BILL PAYMENT`) are removed;
  - a wire: the originator segment after `B O`, `ORG`, `ORIG` (not `ORIG CO NAME`, not `ORIG ID`), `ORIGINATOR`, `WIRE FROM`, `WIRE IN FROM`, `FUNDS TRANSFER CREDIT TT` or `INBD FUNDS TRANSFER RECEIVED`, cut before `BNF`, `BENEFICIARY`, `BBI`, `OBI`, `REF`, `SRF`, `TRN`, `RFB`, `IMAD`, `ACCT`, `SND BK` or the row end. D11 names a wire by its beneficiary, which on a credit is the holder, so a wire's payer is never read that way;
  - a person-to-person or transfer row: the sender after `FROM`, cut before `ON`, `REF`, `CONF`, `MEMO`, `TRN`, `ID` or a sending bank's name; Venmo and Cash App cash-outs have no sender.
- **Payer key:** the payer name's words, with tokens that hold a digit, single letters and generic channel words removed (the memo's `GENERIC_WORDS`), keeping at most the first four. Two credits have one payer when they share the channel family (§8) and their payer keys are equal.
- **Holder words:** the statement's `account_name`, normalized, minus product and legal-form words (`BUSINESS`, `CHECKING`, `ACCOUNT`, `SAVINGS`, `ADVANTAGE`, `ANALYZED`, `COMMERCIAL`, `PLATINUM`, `LLC`, `INC`, `CORP`, `LTD`, `GROUP`, `HOLDINGS`, `SERVICES`, `DBA`, `USD`, `CAD`, province and country names, and the rest of the memo's `HOLDER_NOISE`), minus tokens that hold a digit and tokens of two letters or fewer. `account_name` is often only a product name. When nothing is left, the holder test cannot fire, and nothing is held for it.
- **Holder's name:** a payer name matches the holder when it holds at least min(2, number of holder words) holder words, or when it holds a run of four or more digits that `account_name` also prints (a numbered company's number). An affiliate that shares the holder's brand word is held too; that is the safe direction.
- **Company form:** a legal-form word after the payer name's first word (`LLC`, `L L C`, `INC`, `INCORPORATED`, `CORP`, `CORPORATION`, `COMPANY`, `LTD`, `LIMITED`, `LP`, `LLP`, `LLLP`, `PLLC`, `ULC`, `PLC`, `GMBH`, `AG`, `SA`, `SAS`, `SRL`, `BV`, `NV`, `PTY`, `DOO`, `DMCC`, `SA DE CV`), or an institution word (`FOUNDATION`, `CHURCH`, `MINISTRIES`, `UNIVERSITY`, `COLLEGE`, `SCHOOL`, `ACADEMY`, `HOSPITAL`, `ASSOCIATION`, `SOCIETY`, `COOPERATIVE`, `CO OP`). `CO` is never a company form: since 5.3 it is also Colorado's state code (D11). `TRUST` is never one either: a family trust is owner money. This is narrower than the memo's `LEGAL` list, which also took words such as `SERVICES`, `TRANSPORT` and `CAPITAL`.
- **Electronic-payment form:** the row prints an ACH or EFT mark: `ORIG CO NAME`, `CO ENTRY DESCR`, `DES`, `CCD`, `CTX`, `PPD`, `IAT`, `ACH`, `EFT`, `ELECTRONIC DEPOSIT`, `ELECTRONIC CREDIT`, `ELECTRONIC PMT`, `ELECTRONIC PAYMENT`, `DIRECT DEPOSIT`, `MISC PAYMENT`, `CORPORATE ACH`, `BILL PAYMENT`, `EDI`, `INDN`, `PREAUTHORIZED CREDIT`, `DEPOSIT FROM`, `PAID FROM`, `PAYMENT FROM`, `CREDIT FROM`, `MSP DIV` or `AP CC`.
- **Repeats:** two or more posted, non-duplicate credits in the same statement with the same payer, counting every such credit that is not `non_revenue`, including those a rule already verified. Statement scope: one account's statement period. Nothing is counted across statements.
- **Round sum:** an amount of at least $100 that is a whole multiple of $100, compared in integer cents.
- **Numbered company:** the payer region, read before its tokens are filtered so its leading digits are kept, begins with six or more digits followed by a province, country or legal word, after an optional `DIRECT DEPOSIT`, `ACCOUNTS PAYABLE (PMT)`, `MISC PAYMENT` or `BILL PAYMENT` (the pattern of §7.5). `DIRECT DEPOSIT <digits>` with no such word after the digits is not a numbered company; it prints no payer.
- **Government payer:** a payer name that matches the public-payer patterns of §7.6 anchored at its start, and does not match the payer-name veto of §7.6.
- **Healthcare payer:** a payer name that matches `HEALTHCARE_PAYER_ALIASES` (§7.7), a new hand-kept table of Medicare contractors, state Medicaid programs, US health plans that are not in `INSURANCE_PROVIDER_ALIASES`, pharmacy-benefit managers and claim-payment platforms.
- **Financing root:** the credit-side root set of §8.1.

### 5.3 Tiers and reason codes

Every posted credit gets exactly one tier. `counted_flagged` and `excluded_pending_review` rows always carry a reason. The table groups the reasons by tier; §8.10 gives the order in which the tier pass tests them.

| Tier | Reason code | Label on screen | Source |
|---|---|---|---|
| `verified` | (none; the rule is `revenue_match_method`) | Verified revenue | §7, §8 |
| `excluded_pending_review` | `direction_conflict` | Direction conflicts with the amount | today's rule |
| `excluded_pending_review` | `insurer_payer` | Insurance carrier | T14 |
| `excluded_pending_review` | `possible_return` | Possible return or adjustment | T3 |
| `excluded_pending_review` | `financing_named_payer` | Payer name suggests financing | T4 |
| `excluded_pending_review` | `payer_debited_as_lender` | Payer is also debited as a lender | §8.1 |
| `excluded_pending_review` | `holder_name` | From the holder's own name | Q4, Q5, Q6 |
| `excluded_pending_review` | `payroll_or_salary` | Payroll or salary | Q8 |
| `excluded_pending_review` | `personal_income` | Benefit or pension | T3 |
| `excluded_pending_review` | `wire_no_sender` | Wire, no sender printed | Q5 |
| `excluded_pending_review` | `p2p_round_repeat` | Repeated round sums from one sender | Q4 |
| `excluded_pending_review` | `transfer_no_counterparty` | Transfer, no counterparty | Q2 |
| `counted_flagged` | `wire_named_sender` | Wire from a named sender | Q5 |
| `counted_flagged` | `check_deposit` | Check deposit | Q3 |
| `counted_flagged` | `no_payer_printed` | No payer printed | Q2 |
| `counted_flagged` | `p2p` | Person-to-person | Q4, T13 |
| `counted_flagged` | `factoring_payout` | Factoring payout | owner 2026-09-26 |
| `counted_flagged` | `payout_credit_entity` | Platform payout (financing partner) | owner 2026-09-25 |
| `counted_flagged` | `platform_unconfirmed` | Platform payout, not confirmed | registry |
| `counted_flagged` | `numbered_company_payer` | Numbered company payer | T11 |
| `counted_flagged` | `payer_also_debited` | Payer also debited this account | §8.6 |
| `counted_flagged` | `named_payer_one_off` | One-off payer | Q6 |
| `counted_flagged` | `named_payer_unlabelled` | Payer named, channel not printed | §8.9 |
| `non_revenue` | (none; the rule is `revenue_match_method`) | Non-revenue | §6 |

The reason codes live in one table in `analysis/revenue.py` (`REVENUE_TIER_REASONS`: code → tier and label). Nothing else lists them.

### 5.4 Record fields and contribution flags (5.6)

`TransactionClassification` gains three fields:
- `revenue_tier`, one of the four tiers, or None on a row with no revenue state;
- `revenue_initial_tier`, the tier the rules gave, which reset restores;
- `revenue_tier_reason`, a reason code or None.

`revenue_contribution_flags` takes the tier as well as the state. Exactly one of the first four flags is set on every posted credit:

| Flag | Set when |
|---|---|
| `contributes_to_verified_revenue` | tier `verified` (unchanged meaning) |
| `contributes_to_counted_flagged` (new) | tier `counted_flagged` |
| `contributes_to_excluded_pending_review` (new) | tier `excluded_pending_review` |
| `contributes_to_non_revenue` | tier `non_revenue` (unchanged meaning) |
| `contributes_to_unverified_deposit` | `counted_flagged` or `excluded_pending_review` (unchanged meaning) |
| `contributes_to_true_revenue` (repointed, T9) | `verified` or `counted_flagged` |
| `contributes_to_potential_revenue` | alias of `contributes_to_unverified_deposit` (unchanged) |

`revenue_review_required` on a row becomes true for `excluded_pending_review` only. Counted rows are reviewable, but not required. `revenue_review_status` stays `pending` for every unverified row a person has not decided.

The state and the tier must agree. `verified` goes with `verified_revenue`, `non_revenue` with `non_revenue`, and the two middle tiers with `unverified_deposit`. `compute_metrics` and `rebuild_serialized_revenue_views` refuse a record where they disagree, as they refuse a missing state today.

## 6. Precedence

### 6.1 One credit's decision (`_classify_credit_revenue`); the first match wins

Every step reads the revenue text (§7.0). New and changed steps are marked. A step that fixes a tier names it; tiers exist from 5.6 on.

1. Not posted, or amount ≤ 0: no revenue state (unchanged).
2. Direction conflict: `unverified_deposit`, tier `excluded_pending_review` / `direction_conflict` (unchanged state). No later pass ever lifts it (§7.0).
3. Reversal, cancellation, NSF, provisional credit: `non_revenue` (unchanged). **Changed:**
   - the unambiguous return codes join the credit markers (§7.11);
   - REIMBURSEMENT no longer fires when the row names a healthcare or public-program payer (§7.11);
   - `DEBIT CARD CREDIT` and `POS CREDIT` no longer fire when the row names a maintained operating source or a push rail (§7.11).
4. **New, Q7:** a dealer's funding from an auto lender: `verified_revenue` (§8.7). This is the only carve-out ahead of D1.
5. Insurer registry: `non_revenue`, with two **changes:**
   - a credit that prints the NACHA claim-payment entry skips this step (§7.7);
   - a credit that prints customer-payment wording (§8.1) becomes `unverified_deposit` with method `insurer_customer_payment`, which the tier pass holds as `insurer_payer` (T14).
6. D1 financing-proceeds payee: `non_revenue` (unchanged).
7. D1 by descriptor: `non_revenue`. **New:** Square Capital's `SQ CAP` spelling, and SBA and EIDL disbursements (§7.11).
8. Potential-lender registry: `non_revenue` (unchanged).
9. Strong non-revenue: `non_revenue`. **Changed:**
   - `BOOK TRANSFER` and `FUNDS TRANSFER` are own-account only when no third-party originator is printed (§7.11);
   - the tax-refund abbreviations and account-verification micro-deposits join (§7.11);
   - a street `LN` is no longer read as LOAN (§7.11, in the normaliser).
10. Operating registry: `verified_revenue` with context, a payout form or a card form; otherwise `unverified_deposit` / `operating_source_requires_context`. **Changed** (§7.1 to §7.4, §7.8, §7.10): payout forms, source-type rules, the pay, financing and reversal vetoes, P2P-rail refusal, 16-character truncations and the joined-field reading.
11. Verified descriptors: `verified_revenue`. **Changed:** the card settlement forms (§7.1); the narrowed HCCLAIMPMT glue (§7.7); `CUSTOMER` never read in `CUSTOMER ID` and never with CHECK or CHEQUE (§7.11).
12. **New:** payer accounts-payable remittance (§7.5): `verified_revenue`.
13. **New:** public-payer remittance, arms A and B (§7.6): `verified_revenue`.
14. **New:** wire remittance purpose (§7.9): `verified_revenue`.
15. Deposit wording: `unverified_deposit` / `ambiguous_credit_descriptor` (unchanged). The tier is set by the pass in §8.
16. Everything else: `unverified_deposit` / `unidentified_posted_credit` (unchanged). The tier is set by the pass in §8.

Steps 12 to 14 sit after every non-revenue rule and the registry, so they can only replace the two fallbacks, 15 and 16.

### 6.2 Statement passes, in order

1. Duplicate detection by printed running balance (unchanged).
2. Lender recurrence and D6 on debits (unchanged).
3. Labels for unnamed potential payees (unchanged).
4. Reversal pairs (unchanged logic; the credit markers of step 3 widen which pairs it finds).
5. Operating-source context. **Fixed** (§7.0): the veto pool, the pool that never shrinks, direction conflicts left out, the absolute micro-deposit floor, legal-form holder names read as business accounts, recurrence-only verification for property-management platforms, and the auction branch.
6. **New:** the accounts-payable counter-debit guard (§7.5).
7. **New (5.6):** the true-revenue pass (§8): payer facts for each row, then the Q5 and Q6 verifications, then the tiers.
8. Duplicate finalisation (unchanged). A proven duplicate is `non_revenue` with tier `non_revenue`.

### 6.3 What may leave `non_revenue`, and what may never enter True

A row that a non-revenue rule decides stays `non_revenue`, except through exactly these seven named narrowings, each measured in the census (§14.2):
1. REIMBURSEMENT on a healthcare or public-program payer's credit;
2. HCCLAIMPMT from an insurer-registry payer (claim first);
3. an insurer credit with customer-payment wording, which is **held**, so it still stays out of True;
4. `BOOK TRANSFER` and `FUNDS TRANSFER` with a third-party originator;
5. a street `LN`;
6. a card-credit row that names a maintained source or a push rail;
7. Q7 dealer funding (from D1).

Nothing else leaves `non_revenue`. In particular, no financing-group credit other than Q7's dealer funding, no own-account transfer with an own-account designation, no refund or reversal marker and no duplicate. §14.3 lists the guard checks.

## 7. The bug fixes (classification 5.5)

These fixes change no definition. Under 5.5 they change which credits are verified. They move rows into or out of `non_revenue` only where §6.3 and §7.11 name the move, and they demote verified rows only where §7.0 and §7.11 declare it. Each family below is the proposed fix **as amended by both of its verifiers' required changes**. "Measured" figures are the verifiers' corrected corpus figures.

### 7.0 Shared mechanics

- **Revenue text.** Every credit revenue rule reads `revenue_text(text)`: the normalized row with Chase's glued `Sec` split. `(\bCO (?:ENTRY )?DESCR (?:\S+ ){0,2}?\S{2,}?)SEC (CCD|CTX|PPD|WEB|IAT|COR|TEL|POP|BOC|ARC|RCK|CIE)\b` becomes `\1 SEC \2`. It is bounded to the entry-description field, so a word elsewhere that ends in SEC is untouched. `normalized_description`, D11's payee keys and every debit rule keep today's text. The healthcare family's "cross-family normalizer split" is deliberately not done: it would move lender matching. Measured: 2,907 glued Chase rows, $15.5M, in 207 statements, $2.15M of them HCCLAIMPMT.
- **Joined fields.** Bank of America prints `NAME DES:ENTRY` and Chase prints `ORIG CO NAME … CO ENTRY DESCR …`, so a phrase that needs the name and the entry side by side never matches. The card forms, the verified descriptors and the operating-context patterns are also read on a joined text: `<originator> <entry>`, with ` DES `, and `ORIG ID <id> DESC DATE [<date>] CO ENTRY DESCR`, removed between them. The registry validator warns when a multi-word operating alias spans the name/entry boundary.
- **Glued date prefix.** A leading `01/02Bankcard Deposit` normalizes to `01 02BANKCARD DEPOSIT`. Every card form uses `(?<![A-Z])` as its left boundary, never `\b`, so a digit glued on the left does not block it.
- **16-character truncations.** For every operating alias longer than 16 characters, the registry build adds its first 16 characters as an alias (for example `FIRST DATA MERCH`, `QUICKBOOKS PAYME`, `AMAZON MARKETPLA`). This applies when the cut keeps at least two words, its last word has three or more characters, and it collides with no other registry or ledger alias (the validator refuses a collision). `BY STRI` and `BY STRIPE` after a platform name read as Stripe (Stripe Connect's `<platform> - By Stri`).
- **The recurrence pass** (`_apply_operating_source_context`), fixed for every operating source, old and new:
  - The pool counts an entity's credits already verified by an operating-source method (`operating_source_with_credit_context`, a payout or card form) toward its recurrence total, and it upgrades only the unverified ones. A per-row upgrade must never shrink the pool. Measured: the family fix without this lost 20 rows ($100,388), of which $16,029 was genuine Stripe, Square and Helcim payouts.
  - Veto pool: a credit never counts toward recurrence, and is never lifted by it, when:
    - its transaction classification is `payroll`;
    - `_row_before_receiver` matches `\b(?:LOANS?|CAPITAL|CAP\d*(?:SEC)?|CAPI|CAPIT|CAPITA|FIN|ADVANCE|ADV|FINANC\w*|LEND\w*|MCA|CASH ADV\w*|PAYROLL\w*|PAYRLL|PAYROL|DIR ?DEP|DIRDEP|DIRECT DEP|SALARY|SALARIES|REG SAL|WAGES?|NET ?PAY|BONUS|REIMB\w*|ACCT ?VERIFY|ACCTVERIFY\w*|VERIFY|VERIFICATION|INSUR\w*)\b`;
    - it is below $1 (the absolute micro-deposit floor);
    - its revenue method is `direction_conflict`.
    `FUNDING` stays out of the veto: TapGoods, Braintree and Buildium print it on real settlements. The veto reads the row before its receiver fields, so a holder named `… PAYROLL SERVICES LLC` never demotes its own settlements.
  - Declared demotions of rows verified today: Square Capital's `SQ CAP####` credits, which now become financing proceeds (§7.11); Square payroll credits (measured: 7 rows, $2,808.60, one statement falls to 0% verified); and `ACCTVERIFY` micro-deposits. All are false revenue today. The owner's approval of this spec is the sign-off both verifiers asked for.
  - A credit whose revenue method is `direction_conflict` is never grouped, never counted and never lifted, by this pass or any other. Today the pass verifies mis-signed rows: three direction-conflict Elavon credits in a fabricated test.
  - A holder whose `account_name` prints a legal form (`LLC`, `INC`, `CORP`, `LTD`, `LLP`, `PLLC`) is a business account for the "two or more credits" rule, as `BUSINESS`, `COMMERCIAL`, `OPERATING` and `MERCHANT` are today (structural S6, S41). Measured: 12 keys, 86 accounts, $290K. Customer-payment platforms (PayPal) keep the three-credit rule.
- **Readable matched alias.** A form match records the entity's form label (`ebay_payments_form`), never the regular expression, in `revenue_matched_alias` and in the reason text.
- **Where vocabulary lives.** Every table that names a company (aliases, payout forms, card forms that name an entity, dealer-funding payers, healthcare payers) goes in `analysis/classification_registry.py`, the module the no-hardcode guard exempts (`tests/test_no_statement_hardcodes.py`). Generic wording stays in the classifier. Thresholds are written as integers ($1 as `1`, $100 as `100`), because the guard's amount scan refuses exact-cent literals.

### 7.1 Card-processor settlements (family 1)

One card-settlement reading, placed after every non-revenue rule. `CARD_SETTLEMENT_CREDIT_FORMS` (registry) is a table of (form label, pattern, optional entity). It is read on the row before its receiver fields and on the joined text. It serves as extra credit context for a registry alias (step 10), and as a verified descriptor on its own (step 11, method `operating_income_descriptor`, rule `card_settlement_form_<label>`).

Forms (left boundary `(?<![A-Z])` throughout):
- `bankcard`: `^(?!.*\b(?:BANKCARD CTR|BANKCARD CENTER|PREMIER BANKCARD|FIRST BANKCARD|ELAN|CARDMEMBER|CARD SERVICES|CARD SVCS|CREDIT CARD)\b)(?=.*(?<![A-Z])(?:BANKCARD|BANKCD|BNKCD|BKCD|BKCRD|BNKCRD)\b)(?=.*\b(?:DEP|DEPOSITS?|DEPST|SETTLEMENT|SETTLE|SETLMT|SETL|STLMT|BTOT|MTOT)(?:SEC)?\b)`. The form is refused when `(?<![A-Z])(?:BANKCARD|BANKCD|BNKCD|BKCD|BKCRD|BNKCRD)(?: [A-Z]+){0,2} (?:LLC|INC|CORP|LTD|GROUP|HOLDINGS|FUNDING|CAPITAL|FINANCIAL|PARTNERS|SOLUTIONS|SERVICES|SVCS|CO)\b` matches: that names a company called Bankcard, not the bank's settlement label. Card-issuer credits such as `ELAN BANKCARD SETTLEMENT CREDIT` are refused by the lookahead.
- `merch_dep`: the abbreviated forms only: `MERCH DEP`, `MERCH SETL`, `MERCH SVCS DEP`, `MERCHANT MERCH DEP` and their `DEPOSIT(S)`, `SETTLE`, `SETLMT`, `STLMT` and `SETTLEMENT` variants. The full-word `MERCHANT SERVICES DEPOSIT` / `SETTLEMENT` branch is removed, because ISOs that also fund MCAs print it.
- `mrchntsrvs`: `\bDESCR MRCHNTSRVS(?:SEC)?\b`. `merch_svcs_setl_code`: `\bMERCH(?:ANT)? SVCS?(?: DES)? [A-Z0-9]*SETL\b`. `merchant_services_mid`: `\bMERCHANT SERVI(?:CES?)?\b.*\b(?:MID ?\d{6,}|TRANS SLIP)\b`.
- `brand_dep` and `dep_brand` (`VSA`, `VISA`, `VI`, `MC`, `MCD`, `MCARD`, `AMX`, `AMEX`, `DSC`, `DCVR`, `IDP`, `DEBITCD` beside `DEP`), anchored to the observed layouts: at row start; after `MISC PAYMENT`, `COMPTE DIVERS` or `DIRECT DEPOSIT`; or with `DEP` glued to digits or followed by `MSP`, `DIV` or `MERCH SVC` (Truist's `MC VI DEP … MERCH SVC`). `VISA DEP <person>` and `MOBILE DEP VISA` stay unmatched.
- `gbl_brand` (entity Global Payments): `\b(?:(?:VISA|MC|AMEXO?|IDP|DISC|DCVR) )?GBL (?:VI|MC|AX|IDP|DS|DC)\d*\b`.
- `net_settle` (the entry-description field only): `\b(?:DES|DESCR) NET (?:SETTLE|SETLMT|STLMT|SETL)(?:SEC)?\b`. It is refused on `LAW`, `ATTORNEYS?`, `ESQ`, `TRUST`, `ESCROW`, `TITLE` and `CLAIMS?`. For an originator that is not a registered processor it also needs three or more NET SETTLE credits from that originator in the statement, so it is decided in the recurrence pass.
- `batch_total`: `\b[BM]TOT DEP\b` (BTOT joins the existing MTOT).
- `intuit_deposit` (entity QuickBooks Payments): `\bINTUIT \d{6,}(?: DES)? DEPOSIT\b`, `\bDEPOSIT FROM INTUIT \d{6,}\b`, `\bINTUIT PYMT SOLN\b`, `\bQBOOKS\b`, and Chase's `ORIG CO NAME INTUIT <digits> … DESCR DEPOSIT`. It is refused on `TAX`, `RFND`, `REFUND`, `QBC`, `CAPITAL` and `LOAN`. Bare `INTUIT` is never an alias.
- `square_checking_sales` (entity Square): `^(?:\d+ ACTIVITIES|CARD PAYMENT) SALES$`, only when the statement's bank is Square (the Details and Activity-type layout).
- `network_settlement`: `AMERICAN EXPRESS` or `DISCOVER NETWORK` with `SETTLEMENT` or `SETL`, through the joined text; `AMEXO GBL`; and `AMEX BANK OF CANADA` after `MISC PAYMENT` (structural S9, S39). Bare `AMEX` is never read.
- `generic_card_sales`: `\b(?:VISA ?MC|CARD PROCESSING) (?:DEPOSIT|DEP|SETTLEMENT|SETL|STLM|STLMT)\b` and, on a row that names no card issuer (`CARD_ISSUER_CONTEXT_ALIASES`) and prints no `BALANCE`, `REFUND` or `REWARD`, `\b(?:CREDIT CARD|CR CD|CC) (?:DEPOSIT|DEP|SETTLEMENT|SETL|STLMT)\b` (structural S53).
- French and Canadian: `\bREGLEMENT (?:CARTE|MARCHAND|COMMERCANT)\b` and `\bDEPOT MARCHAND\b`; the alias `GLOBAL PAIEMENTS` for Global Payments (structural S56).

**The card veto.** It serves the forms and the processor payout context, and neither fires when it matches:

`\b(?:CHBK|CHGBK|CHARGEBACKS?|DISPUTE\w*|ADJ|ADJUSTMENT|BILLING|FEES?|DISC|DISCOUNT|MTHLY|INTERCHANGE|PAYROLL|TAX|LOANS?|CAPITAL|ADVANCE|FUNDING|FINANCING|FINANCE|RETURN(?:ED|S)?|ACCT ?VERIFY|ACCTVERIFY\w*|VERIFY|VERIFICATION|INSUR\w*|ZELLE|VENMO|CASH ?APP|E ?TRANSFER|INTERAC|REWARDS?|REBATES?|CASH ?BACK|INTEREST|CLAIMS?|ADV|ADVN?C?|CAP\d*(?:SEC)?|CAPI|CAPIT|CAPITA|FUNDS?|FUNDED|FNDG|FNDNG|FINANCIAL|FINCL|LEND\w*|PROCEEDS|DISB\w*|PURCH\w*|MCA|CONTRIB\w*|OWNERS?|MEMBER|SHAREHOLDER|RTN|RET|REV\d*|RVSL|RVRSL|CB|INTCHG|DUP\w*|CORR\w*|OVERPAY\w*|XFER|TFR|SWEEP|ZBA|BOOK)\b`

It also fires on the phrases `\b(?:TRANSFER|XFER|TFR) (?:FROM|TO)\b` and `\bONLINE TRANSFER\b`. A bare `TRANSFER` never fires, because Stripe, Jobber and bank merchant-services rows print it.

**Processor payout context** counts as context only for source types `merchant_processor` and `invoice_and_receivables`, never for PayPal or a marketplace: `\bSQ ?\d{6}\b`, `\bMISC PAYMENTS?\b`, `\bMSP(?: DIV)?\b`, the real-time rail words, `\bDAILY DEP\b`, and Stripe's `ST-` payout id (context only, never proof on its own).

**Registry additions** (all `merchant_processor` unless stated):
- From the card family, measured on corpus keys: Heartland (`HRTLAND PMT SYS TXNS`, `HEARTLAND PMT SYS TXNS`, `HEARTLAND PAYMENT SYSTEMS`, `HEARTLAND PAYMEN`; never bare `HEARTLAND`, which is also a bank, a dental group and a carrier), SpotOn (`SPOTON`, `SPOTON VIA ASTRA`), SumUp (`SUMUP`), Clearent / Xplor Pay (`CLEARENT`, `CLEARENT LLC`, `XPLOR PAY`), Shift4 (`SHIFT4`, `SHIFT4 PAYMENTS`, `SHIFT4 PYMT PROC`), SmartTab (`SMARTTAB`, `SMARTTAB PAY`), Braintree, TapGoods Payments (`TGPAYMENTS`), Cents (`TRYCENTS`, `TRYCENTS COM`), Jobber Payments (`JOBBER BY STRI`, `JOBBER BY STR`, `JOBBER BY STRIPE`; `invoice_and_receivables`), Esquire Payment Solutions (`ESQUIRE EPS DAILY DEP`, `ESQUIRE EPS HELD DEP`), and the Fiserv alias `FIRST DATA CANADA`.
- From the structural lens (S4, S40), whose spellings were fabricated from knowledge: TSYS / TransFirst, Vantiv, EVO Payments, Paysafe, North American Bancard / Payanywhere, Priority Payment Systems, Payroc, CardConnect, Stax / Fattmerchant, Repay, Paya, NMI, Finix, WePay, TD Merchant Solutions, Desjardins Monetico and Chase QuickAccept. S1 adds each only in a spelling the corpus or the tryout dump prints, confirmed read-only; a name with no printed spelling waits.

Short brand words (`EVO`, `PAYA`, `NMI`, `STAX`, `REPAY`) are never aliases on their own: an alias carries a second name token or the processor's entry description.

**Ledger before aliases.** The bare `SHIFT4`, `SUMUP` and `JOBBER BY STRI(PE)` aliases are added only after their own advance products are admitted through the lender ledger as alternative positions: Shift4 Capital (`SHIFT4 CAPITAL`, `SHIFT4 CAP`), SumUp's cash advance, and Jobber Capital. Admission follows the ledger's process: a public source and an independent second agent. If the ledger cannot admit one, that processor's bare alias is not added.

**Kept out:**
- `APPLIED SYSTEMS` (agency-bill insurance premium, $484,571 over 68 corpus rows);
- the payfac `SV\d[0-9T]` suffix form, which carries $5.1M of private-school tuition that the verifier said must not verify before a ruling;
- `RTP CREDIT FROM MERCHANT SERVI` with no merchant id.

The ten keys the hunt rejected stay rejected. The recorded residual: an unregistered funder whose ACH entry description is literally a card form (201 of 1,487 fabricated funder rows), and processor capital paid out inside normal settlements.

Measured: +$16.43M net on the corpus, after the $100,388 pool regression that §7.0's fix partly recovers; verified 7.17% → 13.11%; $0-verified statements 1,819 → 1,465; 493 distinct statements.

### 7.2 Marketplace and platform payouts (family 2)

`OPERATING_SOURCE_PAYOUT_FORMS` (registry) maps each entity to its forms. A form names the platform together with its payout rail or field layout. A form match names the entity **and** counts as payout context, so one row verifies. An alias without a form still needs recurrence or a related fee debit. One helper, `_operating_source(text)`, is used by step 10 and by the recurrence pass.

Aliases and types:
- Whatnot (`WHATNOT INC`, `FBO WHATNOT`), Faire (`FAIRE WHOLESALE`; never bare `FAIRE`), TikTok Shop (`TIKTOK SHOP`, `TIKTOK INC`, `TIKTOK USA`), eBay (`EBAY COMMERCE INC`), RepeatMD: `ecommerce_marketplace`.
- Snackpass, ezCater, Menufy: `delivery_marketplace`.
- Groupon (`GRPN MERCH SVCS`), ClassPass, Outdoorsy: `booking_marketplace` (a new type).
- Brightwheel: `customer_payment_platform`. Buildertrend, FieldPulse: `invoice_and_receivables`.
- Amazon Marketplace gains `RTP CREDIT AMAZON COM`, recurrence only.
- Stripe gains `STP FBO`: Stripe-Treasury payouts of a connected platform (structural S11).
- Vagaro, Mindbody, Housecall Pro, Squarespace Payments and Wix: `merchant_processor`, with `DEPOSIT` and `PAYOUT` as context (structural S43). Seamless becomes a Grubhub alias. The hunt fabricated these spellings, so S1 adds each alias only in a spelling the corpus prints, confirmed read-only; a name with no corpus spelling waits.

Forms:
- `FBO WHATNOT`; `RTP CREDIT WHATNOT INC`.
- `FAIRE WHOLESALE … ORDER`.
- eBay: `^(?=.*\bPAYMENTS\b)(?!.*\bRETURN(?:ED)?\b).*\bEBAY COM[A-Z0-9]{8}\b`; `RTP (?:CREDIT|RCVD) EBAY COMMERCE INC`.
- Amazon Marketplace: `^(?=.*\bPAYMENTS\b)(?!.*\bRETURN(?:ED)?\b).*\bAMAZON C(?!ORPORATE\b|OM|APITAL|REDIT|ASH\b)[A-Z0-9]{8}\b`.
- ClassPass: `CLASSPASS INC … EDI PYMNTS`.
- ezCater: `PAYONEER … EZCATER`.
- Groupon: `GRPN MERCH SVCS`.

Vetoes on every new read (form and new alias):
- pay: the pay words of the recurrence veto, plus `_PAYROLL_PATTERNS` and `_is_payroll_provider_row`;
- financing: `\b(?:LOANS?|ADVANCE[SD]?|ADV|CAPITAL|LENDING|LENDER|FINANC\w*|FUNDING|FUNDED|PROCEEDS|DRAW)\b`;
- reversal and adjustment: `\b(?:RETURN(?:ED|S)?|RTN|REFUND(?:ED|S)?|RFND|REFND|RFD|REVERS(?:AL|ED|E)|VOID(?:ED)?|CANCEL(?:LED|ED|LATION)?|CNCL|ADJ|ADJUSTMENT|ADJUSTED|DISPUTE[DS]?|CHARGEBACK|CREDIT MEMO|NSF|REJECT(?:ED)?)\b`;
- person-to-person rails: `\b(?:ZELLE|VENMO|CASH APP|E ?TRANSFER|ETRANSFER|INTERAC)\b`.

Employer-type aliases (`TIKTOK INC`, `TIKTOK USA`, Amazon's RTP alias) also refuse `DIR DEP`, `DIRECT DEP`, `PAYRL` and `REIMB` / `EXP REIMB`. The TikTok aliases count only on ACH-shaped rows (`\b(?:ACH|CCD|PPD|ORIG CO NAME|DEPOSIT|PAYMENT|PAYOUT|CORP|CORPORATE)\b`), so a `TIKTOK SHOP <city> CA` card refund never enters recurrence.

**Deferred** (not verified; counted and flagged under 5.6): TikTok creator and affiliate payouts as such; tax-preparer fee disbursements (`TAX PROC … FEE DISB`) and SBTPG; fintech EFT, iink, GoodLeap; PayPal and Payoneer wallet withdrawals; Outdoorsy and RepeatMD payouts to a person's name. The residuals no words can close are recorded: a Faire retailer's refund prints like a brand's payout, and platform-embedded capital paid out under the platform's name.

Measured: 3,291 corpus rows ($4,155,430) promoted in 132 statements; 7 demoted ($2,808.60, the declared Square payroll rows); non-revenue unchanged; $0-verified statements 1,819 → 1,747. Tryout host: at most +$1,436,474, from samples only.

### 7.3 Gig, delivery and transport platforms (family 3)

Part A only: Super Dispatch (`SUPER DISPATCH`, `SUPERDISPATCH`) and Autosled (`AUTOSLED`) join the registry as a new type, `transport_marketplace`. They verify through the fixed recurrence pass, and no doctrine change is made. A credit of these entities never counts toward recurrence when it prints a veto of §7.2, a wallet or subscription word (`\b(?:CASHOUT|CASH OUT|SUBSCRIPTION|MEMBERSHIP)\b`) or a wire word (`\b(?:WIRE|WT|FEDWIRE|OBI|BNF)\b`).

Part B, the type-verification rule, is out: it is a doctrine change whose extra reach is 15 rows ($4,445.48). Lyft, Shipt, Postmates, Roadie, Amazon Flex and Walmart Spark stay out of the registry until the owner rules on individuals' gig income (structural S15); their rows are counted and flagged under 5.6. Super Dispatch Instant Transfer is a fee-bearing quick-pay advance on a delivered load; it is recorded with the other deferred items (§15).

Measured: 29 rows, $16,177.10, in 3 statements, with no rows lost.

### 7.4 Registry hygiene

The registry validator (`tools/lender_ledger.py` or its operating-registry sibling) checks:
- every operating entity has a source type;
- every payout form and card form compiles, and its entity is typed;
- no operating alias, truncation or form equals a ledger financing alias or an insurer alias;
- `HEALTHCARE_PAYER_ALIASES` collides with no ledger alias and no insurer alias;
- `DEALER_FUNDING_PAYERS` collides with no ledger alias outside the vehicle-financing group, which Q7 names on purpose.

### 7.5 Payer accounts-payable remittance (family 4)

A credit-only verified descriptor, `_PAYER_REMITTANCE_CREDIT_PATTERNS`, at step 12 (method `payer_remittance_descriptor`).

Patterns:
- `\bACC(?:OUN)?TS? PAYABLE\b`
- `^DIRECT DEPOSIT\b(?=.* AP CC$)`
- `\bA ?P (?:PMTS?|PAYMENTS?|PYMTS?)\b`
- `\bCO ENTRY DESCR A ?P\b`
- `\b(?:CCD)?ACC PAY\b`
- `\bVENDOR ?(?:PMTS?|PAYMENTS?|PAY|PYMTS?)(?:SEC)?\b`
- `\bTRADE PAY(?:MENTS?)?(?:SEC)?\b`
- `\bPAYABLES\b`, never on a row that prints `BI ?LL COM` (PAYABLES is Bill.com's payer-side debit wording)
- `\bPO REMIT(?:TANCE)?\b`
- `\bAVID ?PAY\b`, `\bAVIDXCHANGE\b`, `\bCOUPA PAY\b`, `\bPAYMODE\b`
- `\bPAYING BILLS? (?:\d|INV)` (Ramp's form), `\bFOR \d+ BILLS\b`
- `\bBI ?LL COM (?:INV|MULTIPLE INVOICES|RECEIVABLE)\b`, `\b(?:DESCR|DES) BI ?LL COM\b` (receivable forms only), `\bRECEIVABLE\b.*\bBI ?LL COM\b`
- `\bINV(?:OICE)? (?:PMT|PYMT)\b`, `\b(?:OF|FOR) INVOI ?CES?\b`
- `\bRMR IV\b` (X12 invoice remittance)
- the invoice number `\bINV(?:OICE)?S?(?: (?:NO|NUM|NUMBER|N))? ?\d`, only on a row that also prints a payment-channel word: `ACH`, `PMT`, `PAYMENT(S)`, `ZELLE`, `WIRE`, `FEDWIRE`, `CHIPS`, `CCD`, `CTX`, `PPD`, `EFT`, `RTP` or `REMIT`. `DEPOSIT`, `TRANSFER` and `CREDIT` are not channel words here. The number is never read after `CREATED FROM` or `TRANSFER FROM`.
- French: `\bPAIEMENT (?:DE )?FACTURE\b` (structural S56).

Free-text gate: on a person-to-person row (`ZELLE`, `E TRANSFER`, `INTERAC`, `VENMO`, `CASH APP`, `PAYPAL`) or a wire from a person, the invoice, bill and "for invoices" forms count only when the sender prints a company form. A person's Zelle memo "paying bills" or "Invoice 1234" never verifies.

Veto: it is read on the row after removing the matched words and the credit posting labels (`\b(?:ELECTRONIC|ACH|RTP|ONLINE|WIRE|BOOK|CORP|CORPORATE|ZELLE|MISC|DIRECT|PAYMENT|DEPOSIT|TRANSFER|MOBILE|EFT|CHIPS|FEDWIRE)\s+CREDIT\b|^CREDIT\b`). It refuses:
- financing: `FUND`, `CAPIT`, `CAPTL`, `LOAN`, `LEND`, `FINANC`, `ADVANC`, `MORTG`, `ACCEPTANCE`, `SERVICING`, `SERVICER`, `PORTFOL`, and `CREDIT` with no word boundaries; `CRED(?=ORA|IBLY|\b)`; `CAPI?\b` with any left context; `LEAS(?:E|ES|ING|IN|I)?\b` with any left context; the whole words `CAP`, `FIN`, `FINA`, `FINAN`, `FI`, `FINL`, `FNCL`, `ADV`, `MTG`, `MCA`, `RTR`, `SPV`, `FUN`, `FUNDI`, `LOA`;
- insurance, investment, tax and grants: `INSUR`, `INS`, `ASSURANCE`, `INVEST`, `BROKERAGE`, `SECURITIES`, `WEALT`, `TAX(ES)`, `IRS`, `CRA`, `GRANTS?`, `REBATES?`, `DIVIDENDS?`;
- pay and claims: `PAYROLL`, `SALARY`, `WAGES?`, `REIMB\w*`, `EXPENSES?`, `BONUS`, `COMM?ISS?IONS?`, `CLAIMS?`, `MUTUAL`, `INDEMNITY`, `CASUALTY`, `UNDERWRIT\w*`;
- equipment, floor plan and vehicles: `EQUIP`, `FLOOR`, `MERCH`, `\bVIN\b`;
- SBA: `\bSBAD?\b`, `\bEIDL\b`;
- own money and sweeps: `\bINTERCO(?:MPANY)?\b`, `\bDUE FROM\b`, `\bSHAREHOLDER\b`, `\bOWNERS?\b`, `\bZBA\b`, `\bZERO BAL\w*`, `\bSWEEP\b`, `\bCONTROLLED DISB\w*`, `\b(?:TRANSFER|XFER|TFR) FROM\b`, `\bINTERNAL\b`;
- returns: `\bRTN\b`, `\bRETURN(?:ED)? ITEM\b`, `\bRECALL\w*`, `\bUNPAID\b`, `\bADJ\b`;
- lease-to-own: `ACIMA`.

Where the words appear:
- **Numbered companies (T11):** the rule never verifies a payer whose payer region begins with six or more digits followed by a province, country or legal word (`^(?:DIRECT DEPOSIT |ACC(?:OUN)?TS? PAYABLE(?: PMT)? |MISC PAYMENT |BILL PAYMENT )?\d{6,} (?:ONTARIO|ONTA|ONT|ALBERTA|ALTA|BC|B C|QUEBEC|QUE|QC|CANADA|SASK|MANITOBA|INC|LTD|LIMITED|CORP|ULC)\b`).
- **Counter-debit guard (statement pass 6):** a credit decided `payer_remittance_descriptor` goes back to `unverified_deposit` (method `payer_remittance_with_counter_debit`) when a posted debit in the same statement shares the payer's first distinctive word. A distinctive word has four or more letters and is not an AP word, a bank template word or a legal suffix. Measured cost: 19 rows, $242K.

Deferred, and recorded for the owner (§15): government AP grants versus contract fees; foundation and council payers through AP; `TRADE PAY` from trading or securities names; insurers and claims administrators whose names carry no `INS`; development lenders on AP-coded EFTs; property-manager owner distributions to named persons; bare trailing `<payer> AP` entries; EDI PYMNTS from non-financial payers.

Measured as simulated before narrowing: 1,125 rows, $22.94M, 263 statements. After narrowing: about $13.4M. The census restates it at row level.

### 7.6 Government payers (family 5)

A verified rule, `_public_payer_remittance`, at step 13 (method `public_payer_remittance`, source type `government_payer`).

- **Arm A (whole row):** `\bTREAS \d{3}(?: DES)? DOD MISC\b` with no `\bPPD\b`; and `\bTREAS \d{3}\b.*\bMISC PAY(?:SEC)?\b.*\bRMR IV\b`.
- **Arm B:** a public payer **anchored on the payer name** and a payer-side purpose.
  - `payer_name` = `_payee_region(_row_before_receiver(text))` with the bank template words removed: `^(?:ELECTRONIC (?:CREDIT|DEPOSIT)(?: FROM)?|ACH (?:CORP )?CREDIT|ACH DEPOSIT|CCD DEPOSIT|DEPOSIT FROM|PREAUTHORIZED CREDIT|EFT CREDIT)`.
  - The payer pattern must match as `^(?:\S+ ){0,3}(?:<payer>)` on `payer_name`, with no digit and no purpose word before the end of that match. The payer patterns are:
    - `TREAS \d{3}`;
    - `(?:STATE|COUNTY|CITY|TOWN|VILLAGE|TOWNSHIP|BOROUGH|PARISH|DISTRICT|PROVINCE|COMMONWEALTH|GOVERNMENT|GOVT|MUNICIPALITY) OF [A-Z]`;
    - `(?<!\bFROM )(?<!\bTO )(?<!\bTHE )(?<!\bOF )(?<!\bAND )(?<!\bINTO )\b[A-Z]{3,} (?:COUNTY|PARISH|TOWNSHIP|BOROUGH)\b`;
    - `(?:DEPT|DEPARTMENT|MINISTRY) OF`;
    - `DHS|DHHS|DSHS|DCF|DCFS|DSS`;
    - `SCHOOL DIST(?:RICT)?`;
    - `DFAS`.
  - The purpose is read on the row before its receiver fields: `\bVEN(?:DOR)? ?(?:PAY(?:MENTS?)?|P(?:Y)?MTS?)(?:SEC)?\b`, `\bPROV(?:IDER)? ?PAY(?:MENTS?)?(?:SEC)?\b` or `\bEDI ?(?:PYMNTS|PAYMENTS?|PMTS?)(?:SEC)?\b`.
- **Arm C (EBT settlements) is deferred:** one holder in the data, and an open owner question.
- **Payer-name veto** (tax, labour and treasurer agencies): `\b(?:DEPT OF REVENUE|DEPARTMENT OF REVENUE|TAXATION|COMPTROLLER|TREASURER|DEPT OF LABOR|UNEMPLOYMENT|WORKFORCE)\b`. Financing names are vetoed without word boundaries on `payer_name` (`FUNDING`, `FUNDER`, `FINANC`, `CAPITAL`, `LENDING`, `LENDER`), which catches glued lender names.
- **Whole-row veto,** read after deleting Bank of America's boilerplate `ADDITIONAL INFORMATION IS AVAILABLE FOR THIS PMT CONTACT A TREASURY SALES OFFICER FOR ASSISTANCE`:
  - tax, refunds and benefits: `\bTAX(?:ES)?\b`, `\bTAXRFD\b`, `\bTAX ?REF(?:UND)?S?\b`, `\bREFUNDS?\b`, `\bRFD\b`, `\bSTUREFUND\b`, `\bR(?:E)?F(?:U)?ND\b`, `\b(?:XX)?SOC SEC\b`, `\bSUPP SEC\b`, `\bSSI\b`, `\b(?:XX)?VA BEN\w*\b`, `\bBENEF\w*\b`, `\bBEN\b`;
  - pay and pensions: `\bFED SAL\b`, `\bSALARY\b`, `\bPAYROLL\b`, `\bWAGES?\b`, `\bSTIPENDS?\b`, `\bPER DIEM\b`, `\bRETIRE\w*\b`, `\bPENSION\b`, `\bANNUIT\w*\b`;
  - relief, grants and loans: `\bUNEMPLOY\w*\b`, `\bUI\b`, `\bSTIMULUS\b`, `\bGRANTS?\b`, `\bRELIEF\b`, `\bDISASTER\b`, `\bCARES\b`, `\bPPP\b`, `\bSBAD?\b`, `\bEIDL\b`, `\bEIDG\b`, `\bLOANS?\b`, `\bADVANCES?\b`, `\bADV\b`, `\bFORGIV\w*\b`;
  - family and court: `\bCHI?LD ?SUPP\w*\b`, `\bCHILD ?CTC\b`, `\bCTC\b`, `\bJURY\b`, `\bRESTITUTION\b`, `\bFOSTER\b`, `\bADOPT\w*\b`, `\bKINSHIP\b`, `\bWORK(?:ERS)? ?COMP\b`;
  - claims, awards and recoveries: `\bCLAIMS?\b`, `\bAWARDS?\b`, `\bSUBSID\w*\b`, `\bDISB\w*\b`, `\bPROCEEDS\b`, `\bUNCLAIMED\b`, `\bOVERPA\w*\b`, `\bOVERP(?:Y)?MT\b`, `\bREBATES?\b`, `\bREIMB\w*\b`, `\bBONDS?\b`, `\bESCROW\b`, `\bRETURN(?:ED)?\b`, `\bSTABILI[SZ]\w*`, `\bOFFSET\b`, `\bRECOVERY\b`, `\bARPA\b`, `\bRESCUE\b`, `\bERT?C\b`, `\bINCENTIVES?\b`, `\bTUITION\b`;
  - person-to-person: `\b(?:ZELLE|VENMO|CASH ?APP|E ?TRANSFER|INTERAC)\b`;
  - financing and leases: `\b(?:FUNDING|FUNDER|LENDING|LENDER|FINANC\w*|CAPITAL|CREDIT UNION|FCU|MORTGAGE|LEASE|LEASING|FACTOR\w*)\b`.
  - Arms A and B also veto `\bSETTLEMENT\b`, and arm B vetoes `\b(?:TRANSFER|XFER|TFR)\b`. `ASSISTANCE` is never added, because Bank of America's boilerplate prints it.
- **No recurrence gate** (T12). A single public-rail credit verifies.

A rule-verified row is reviewable (T6), which settles the verifier's "no undo" note. The residual is recorded: Chase can leave the Treasury agency prefix blank, so on arm A's MISC PAY branch, RMR IV is the only real guard.

Measured: 131 rows, $3,870,472.30, in 20 distinct statements. Tryout host: 3 rows, $629,249.40, in 2 statements (dump only). $0-verified statements 1,819 → 1,804. Verified 7.17% → 8.57% on this family alone.

### 7.7 Healthcare payers (family 6)

- The verified pattern becomes `(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b`. Its unbounded branch takes only the full NACHA token, so `THECLAIMPMT` and `CHECLAIMPMT` stay unmatched.
- **Claim first (the insurer-vs-claim order).** On credits, a row whose revenue text matches that pattern skips the insurer registry (§6.1 step 5). Inside `_classify_credit_revenue`, the financing, potential-lender and insurer lookups read the text with a space inserted before a glued `HCCLAIMPMT` (a lookbehind on `[A-Z0-9]`), so a 16-character funder name glued to the token is still found. D1, descriptor proceeds, the potential registry, strong non-revenue and reversals still win. The rule is entry-based, so every Blue-plan spelling (`BCBS`, `BCBSM`, `BLUE CROSS BLUE`, Blue Care Network, Anthem Blue Cross, CareFirst) is treated alike. That settles the in-statement split the verifier found.
  - Measured: 177 BCBS rows, $908,159, in 16 statements move from `non_revenue` to `verified_revenue`. 376 alias-escaping Blue rows ($424,597.31, 23 statements) are already in the glue fix.
- **`HEALTHCARE_PAYER_ALIASES`** (registry, new): Medicare contractors (Noridian, Palmetto GBA, Novitas, WPS, NGS, CGS, First Coast), state Medicaid programs and Medi-Cal, TRICARE and VA Community Care (`VA CCN`), US health plans that are not in the insurer table (Aetna, Cigna, Humana, UnitedHealthcare, `UHC`, Optum, Molina, WellCare, Centene, Anthem), pharmacy-benefit managers (Express Scripts, Caremark, OptumRx), and claim-payment platforms (Zelis, ECHO Health, InstaMed, VPay, PaySpan).
  - It is read on the payer name, on a row with an electronic-payment form. It is used by Q6 (§8.6).
  - Canadian benefit carriers (Sun Life, Manulife, Canada Life, Equitable Life, Great-West, Desjardins Insurance, Alberta Blue Cross), RBC's `HEALTH DENTAL CLAIM <carrier>` label (normally a member's reimbursement), NEMT brokers, `CLMEFT`, and a bare X12 `TRN*1*` with no entry description are **out**: they are counted and flagged. They also print broker commissions, member reimbursements or non-claim payments.
- Tests lock today's spaced Chase `Hcclaimpmt Sec:CCD` row. The glued Chase, Huntington `<16-char name>HCCLAIMPMT` and digit-prefixed forms verify. `<name>HCLAIMPMT`, `HCCLAIMPMT0001` and `Hhspaymentsec` stay unverified. A BCBSM glued row verifies (claim first). A registered funder's glued row stays `non_revenue` / `financing_proceeds_credit`. An HCCLAIMPMT row with `Merchant Cash Advance` or `Loan Proceeds` stays `non_revenue` / `strong_non_revenue_rule`.

Measured: 1,626 corpus rows, $2,156,058.97, in 34 statements from about 8 healthcare businesses. The largest holds 49% of the dollars, and the 17 statements it lifts from 0% belong to 5 businesses. The tryout host barely moves: 6 rows, $531.

### 7.8 Dealer-only wholesale auto auctions (family 7)

A new operating type, `wholesale_auto_auction`: Manheim (`MANHEIM US`), ACV Auctions (`ACV AUCTIONS`) and OPENLANE (`OPENLANE INC`, `BACKLOTCARS`; not the spaced `BACKLOT CARS`).
- The aliases are read on the originator segment only (`_originator_segment`), in step 10 and in the recurrence pass. An alias in `INDN`, `IND NAME`, a Zelle "to" field or a memo never matches.
- For this type, the single-row context verification and the generic recurrence are off. A branch of the recurrence pass decides alone. It touches only a posted credit with `direction_consistent` true and a revenue method in {`operating_source_requires_context`, `recurring_operating_source`, `operating_source_related_activity`, `operating_source_with_credit_context`}.
- It verifies only an observed payout form:
  - Manheim: `\bMANHEIM US (?:DES )?(?:ACH PAYMNT|EDI PYMNTS)\b`;
  - ACV: `\bACV AUCTIONS INC PAYMENTS\b`, or `\bORIG CO NAME ACV AUCTIONS INC\b.*\bCO ENTRY DESCR PAYMENTS SEC CCD\b`;
  - OPENLANE: `\bORIG CO NAME OPENLANE INC\b.*\bCO ENTRY DESCR OPENLANE SEC CCD\b`, or `^BACKLOTCARS PAYMENT\b`.
  Any other auction row stays `unverified_deposit` (rule `auction_credit_without_payout_form`).
- An ACV credit printing a buyer-payment reference `\bPYMT\d` stays unverified (`auction_credit_prints_buyer_payment_reference`), whatever the date gap.
- A refund pair is found by the broad auction name (`\bMANHEIM\b`; `\bACV AUCTIONS\b` but not `ACV CAPITAL`; `\bOPENLANE\b`, `\bBACKLOT ?CARS\b`), on debits and wire `BNF` lines. It needs an equal amount within 14 days, and each debit is used once. A paired credit stays unverified (`auction_credit_matches_same_source_debit`).
- The $1 floor is absolute. A credit under $1 is never verified and never counts toward recurrence.
- The residual is recorded: an arbitration refund in a later statement, or a partial refund, prints like seller proceeds.

Measured: 138 rows, $282,944.45 (+1.42% of corpus verified). 11 statements leave 0%. Non-revenue unchanged.

### 7.9 Wires that cite an invoice or PO (family 8)

A verified rule, `wire_remittance_purpose`, at step 14.
- **N1, channel.** The normalized row must **begin** with an incoming-wire label: `^(?:WIRE TYPE (?:WIRE|INTL|FX) IN\b|USD WIRE IN\b|[A-Z]{3} WIRE IN\b|FEDWIRE CREDIT\b|CHIPS CREDIT\b|WT FED|WIRE TSF\b|WIRE TRANSFER (?:DEPOSIT|CREDIT|IN|INCOMING|FROM)\b|INCOMING WIRE\b|WIRE IN\b|WIRE FROM\b|(?:DOMESTIC|INTL|INTERNATIONAL|FOREIGN) (?:INCOMING )?WIRE\b|INCOMING FUNDS TRANSFER\b|FUNDS TRANSFER CREDIT TT\b|INBD FUNDS TRANSFER\b|FUNDS TRANSFER WIRE FROM\b)`, or be a Chase `BOOK TRANSFER CREDIT B O` whose originator is not the holder (§7.11). Bank of America's `WIRE TYPE BOOK IN` is read the same way as Chase's book transfer, so the two banks agree.
- **Purpose,** read on the row with the party-name fields removed (`\bB O\b…`, `\bN?BNF\b…`, `\bORIG\b(?! TO BNF)…`, `\bACCT \d+\b…`, `\bORIGINATOR NAME\b…`, `\bORG\b…`, and `account_name` when it has 6 or more characters):
  - an invoice word, including one split once by a line wrap (`INVOIC E`);
  - an invoice number `\bINV(?:OICE)?S? ?(?:NO |NUM |NBR |NUMBER )?\d`;
  - a PO `\bPO ?(?:NO |NUM |NBR |NUMBER )?\d{3,}` or `\bPURCHASE ORDERS?\b`;
  - an order number: `ORDER` + number, not after `MONEY`, `STANDING`, `PAYMENT`, `PMT`, `COURT`, `PAY`, `TRANSFER`, `SUPPORT`, `BANK` or `WIRE`;
  - payment for goods; `PAGO PROVEEDOR`, `FACTURA`; SWIFT `REF INV`; `PRO FORMA` (the bare `PI <digits>` form is dropped); `COMPRA DE MERCAD`.
- **Vetoes**, read on the whole row:
  - `_FINANCING_ROOT_PATTERN`, after removing the channel words and the sending and intermediary bank fields, and also run on the first six words after the originator label with their spaces removed (wrap-tolerant, so `CAPI TAL` and `FUN DING` are caught);
  - the non-sale purposes: `INVEST…`, `DISTRIBUTION`, `DIVIDEND`, `EQUITY`, `MEMBERSHIP INTEREST`, `SHAREHOLDER`, `STOCK`, `CONTRIBUTION`, `PROCEEDS`, `ESCROW`, `CLOSING`, `OVER PAYMENT`, `REBATE`, `RETURN(ED)`, `CREDIT MEMO`, `DUPLICATE`, `SALARY`, `PAYROLL`, `WAGES`, `TAX`, `GRANT`, `DONATION`, `GIFT`, `INTEREST`, `REPAY…`, `PRINCIPAL`, `SECURITY DEPOSIT`, `INTER COMPANY`, `AFFILIATE`, `OWNER(S)`, `PERSONAL`, `COURT`, `JUDGMENT`, `INSURANCE`, `CLAIM(S)`, plus `RETN`, `RTN`, `REJT`, `REJECT(ED)`, `RECALL(ED)`, `UNABLE TO APPLY`, `DRAW(S)`, `DRAWDOWN(S)`, `DISBURS…`, `FEE(S)`, `SCF`, `SUPPLY CHAIN`, `EARLY PAY(MENT)`, `DISCOUNT(ED/ING)`, `PAYOFF`, `SURPLUS`, `EARNEST`, `SUBSCRIPTION(S)`, `COMPENSATION`, `ADJ`, `ADJUSTMENT(S)`, `RMA`, `SHORTAGE(S)`, `ALLOWANCE(S)`, `PROMISSORY`, `CONVERTIBLE`, `BRIDGE`, `SAFE`, `TRANCHE` and `DEPOSIT BACK`;
  - own account: the originator's first two name words equal the beneficiary's, or appear in `account_name`;
  - brand-word affiliate: the originator's first distinctive word equals the first word after `BNF` / `NBNF` or the first word of `account_name`;
  - cut field: an originator that fills its field to within two characters of the width (Santander 16, Bank of America 25) whose run-together name starts any financing or potential alias or ledger entity of 6+ characters, or whose last word of 3+ letters is a proper prefix of a financing word (`FUNDING`, `FINANCIAL`, `CAPITAL`, `LENDING`, `LOANS`, `ADVANCE`, `MERCHANT`, `CREDIT`, `LEASING`, `SERVICING`, `FACTORING`, `MORTGAGE`, `RECEIVABLES`, `EQUIPMENT`, `ACCEPTANCE`, `COLLECTIONS`, `RECOVERY`, `SETTLEMENT`, `REMITTANCE`, `EQUITIES`, `EQUITY`, `VENTURES`);
  - `match_known_payee(text)` is not None.
- **Stated:** tuition wires that cite an invoice verify (the invoice is the proof, and the holder is a school). A wire from a private person that cites an invoice verifies (about 4 rows, about $119K), as proposed. Requiring an organisation cue would cost $3.28M of $4.15M.

Measured with N1 to N8: 75 rows, $4,093,290.86, in 27 statements; non-revenue unchanged. The registry side findings go to the ledger, not this rule: eCapital and Stenn in `FACTORING_ALIASES`, the printed legal names of FairFigure, GFE, One River Group and Uncapped, and the spaced `SAMSON SERVICING`.

### 7.10 Property-management platforms (family 9)

Buildium, AppFolio and Landlord Studio join the registry as type `property_management_payments` (T15). `YARDI` stays out, and `FUNDING` is never a context word.
- For this type, step 10 returns `unverified_deposit` / `operating_source_requires_context` even when the context patterns match. Relay's `ACH Credit:`, PNC's `ACH Credit` and ATB's `Direct Deposit Misc. Payments` print those words on every credit.
- The recurrence pass counts recurrence only: three or more credits, or two in a business-named account. It uses no related fee debit.
- A guard runs only when one of the three matched. A row printing `\bOWNERS? ?(?:DIST\w*|DISB\w*|DRAWS?\w*|CONT\w*)`, `\bDISTRIBUT\w*`, `\bSEC(?:URITY)? ?DEP\w*`, `\bDEP(?:OSIT)? ?(?:RETURN\w*|RTN\w*|RT\w*|REFUND\w*)`, `\bSD ?(?:RETURN\w*|RTN\w*|RT\w*|REFUND\w*)`, `\bADVANCE\w*` or `\bORIG CO NAME\b.*\bORIG CO NAME\b` stays unverified (`property_platform_owner_or_deposit_wording`) and is left out of the count.
- Micro-deposits never count: `\bACCT ?VERIFY\w*`, `\bMICRO ?(?:DEP\w*|ENTRY)\b`, `\bPENNY TEST\b`, `\bTRIAL (?:DEP\w*|CREDIT)\b`, or under $1.
- A verified row carries the context signal `property_management_collections`, shown as a chip (§10.6).

Measured: 78 rows, $263,112.59, in 8 statement-months of 3 bank accounts; 0 tryout-host rows. The AppFolio rows are payouts to a landlord (owner distribution or rent), not vendor payments.

### 7.11 Wrong non-revenue, and newly named non-revenue

Narrowings of non-revenue rules (§6.3):
- **REIMBURSEMENT.** `\bREIMBURSEMENT\b` in `_REVERSAL_CANCELLATION_CREDIT_PATTERNS` does not fire when the payer name is a healthcare or government payer (§5.2) or the row prints `MEDICAID`, `MEDICARE`, `MEDI CAL`, `TRICARE`, `CHAMPVA`, `GEMT` or `EMS`. An employer's `EXP REIMB` / `EXPENSE REIMBURSEMENT` stays `non_revenue`.
- **Street `LN`** (`analysis/description_text.py:24`). `\bLN\b` is rewritten to `LOAN` except when it ends a street address: a token of digits followed by one to three alphabetic tokens, then `LN`. The same guard applies to printed Wells Fargo and Chase ATM and branch locations. This is the only normaliser change. It moves `normalized_description` for such rows, debits included, so G7 (§14.3) must show no lender or flag moved. Measured: 8 or 9 rows, $19K to $32K, including one $105K wire.
- **Book and funds transfers.** In `_INTERNAL_TRANSFER_CREDIT_PATTERNS`:
  - `BOOK TRANSFER` and `FUNDS TRANSFER` stay own-account only when no third-party originator is printed (`B O`, `CUSTOMER`, `ORIGINATOR`, `ORG`, `TT <payer>`, `FROM <payer>`, `WIRE FROM`), or when that originator matches the holder's name.
  - `INCOMING FUNDS TRANSFER`, `FUNDS TRANSFER CREDIT TT`, `INBD FUNDS TRANSFER` and `FUNDS TRANSFER WIRE FROM` are incoming-wire labels. `ELECTRONIC FUNDS TRANSFER DEPOSIT` is an EFT channel, so the registry reads the processor that follows.
  - `prints_internal_transfer_designation` reads the same tuple, so R-d's package pairing narrows with it. A book transfer from a third party designates no own account, which is R-d's own test.
  - Chase's Paymentech settlements delivered as a book transfer (`B O CUSTOMER PAYMENTECH LLC … DEPOSIT ID`) then reach the registry.
  - Measured: 308 rows, $6.25M, in 73 statements (book transfers); 119 rows, $2.27M, in 26 statements (funds-transfer wires).
- **Push payouts printed as card credits.** `DEBIT CARD CREDIT` and `POS CREDIT` do not fire when the row names a maintained operating source or a push rail (`VISA DIRECT`, `MC SEND`, `VISA MONEY TRANSFER`, `INSTANT`, `FASTPAY`). A retail merchant's card refund keeps the reversal. Measured: 126 rows, $220K, in 12 statements.
- **Insurer customer-payment wording** (T14): §6.1 step 5. The row leaves `non_revenue` but stays out of True.
- **Q7:** §8.7 (5.6 carries it with the definition, since the owner ruled it as one).

Tightened verification (a declared verified → unverified move):
- `CUSTOMER` in `_VERIFIED_REVENUE_CREDIT_PATTERNS` becomes `\bCUSTOMER\b(?! ID\b)`, and neither CUSTOMER pattern accepts `CHECK` or `CHEQUE` (Q3). Truist prints `CUSTOMER ID` on every ACH line. Measured: 5 verified keys, $125K.

Newly named non-revenue (T5):
- the return codes, added to the credit markers only (the debit rules keep `_REFUND_REVERSAL_PATTERNS`): `\bRTN\b`, `\bRETN\b`, `\bRFND\b`, `\bREFND\b`, `\bRFD\b`, `\bRVSL\b`, `\bRVRSL\b`, `\bREVSL\b`, `\bRECALL(?:ED)?\b`, `\bUNPAID\b`, `\bREJT\b`, `\bCHBK\b`, `\bCHGBK\b`. The reversal-pair pass reads them too, which closes the returned-wire hole the wire verifier found. A won chargeback printed `CHBK REVSL` becomes `non_revenue`, in the conservative direction.
- tax refunds: `\bTAX ?REF(?:UND)?S?\b`, `\bTAXRFD\b`, `\bTAX RFD\b` join the TAX REFUND rule (Treasury's `IRS TREAS 310 TAX REF`);
- D1 by descriptor, credits only: `square_capital_credit` for `\bSQ ?CAP\d*\b` on a row that names Square; `sba_disbursement_credit` for `\bSBAD TREAS\b`, `\bSBA (?:EIDL|LOAN|DISB\w*)\b` and `\bEIDL\b`. Both are financing proceeds, subtracted from eligible deposits;
- account verification: `\bACCT ?VERIFY\w*\b`, `\bMICRO ?DEPOSITS?\b`, `\bPENNY TEST\b`, `\bTRIAL DEPOSITS?\b` join the strong non-revenue rule.

### 7.12 Structural misses: what is in and what is out

S1 to S25 are `result.structural[0].misses` and S26 to S60 are `result.structural[1].misses` of `hunt_result.json`, in order. High and medium only (H/M); the low ones follow the table.

| S | H/M | Shape | Decision |
|---|---|---|---|
| 1, 26 | H | Chase glued `Sec` | **In**: revenue text (§7.0) |
| 2 | H | BofA/Chase split originator and entry | **In**: joined fields (§7.0) |
| 3, 37 | H | Bankcard, BTOT, MERCH DEP, BKCD, COMB DEP, brand DEP codes | **In** (§7.1); Fifth Third `COMB DEP` via `bankcard` |
| 4, 40 | H | Acquirers missing from the registry | **In** (§7.1) with specific aliases; ledger first for Shift4, SumUp and Jobber |
| 5 | M | Aliases over 16 characters | **In**: truncations (§7.0) |
| 6, 41 | M | Registry source with fewer than 3 credits | **In** in part: a legal-form holder name is business context; payout codes as context (§7.1). Counting across statements is **out** (non-goal) |
| 7, 35 | M | BNPL merchant settlements read as financing | **Out**: `PAYOUT_CREDIT_ENTITIES` changes only on an owner ruling (lender spec §5, D2) (OQ2) |
| 8 | M | Payout entities and lease-to-own funding unverified | **Out** for Verified (same ruling); counted and flagged under 5.6 |
| 9, 39 | M | Amex, Discover and GBL network settlements | **In** (§7.1 `network_settlement`, `gbl_brand`) |
| 10, 38 | H | Merchant-services wording | **In** for the abbreviated forms, `MRCHNTSRVS`, MID-bearing rows and bank-arm aliases with DEP or MID; **out** for full-word `MERCHANT SERVICES DEPOSIT` and bare `RTP … MERCHANT SERVI` (verifier) |
| 11, 43 | M | Vertical SaaS, payfacs, `STP FBO` | **In**: registry aliases, and `STP FBO` as Stripe (§7.2); the payfac SV suffix is **out** (§7.1) |
| 12 | H | Intuit / QuickBooks deposits | **In** (`intuit_deposit`) |
| 13, 42 | H | Marketplaces | **In** (§7.2) |
| 14 | M | eBay's glued payout id | **In** (§7.2 form) |
| 15 | M | Lyft, Shipt, Postmates, Roadie, Amazon Flex, Spark | **Out**: waits on the gig-income ruling (§15) |
| 16, 45 | H | Payables codes and AP networks | **In** (§7.5) |
| 17, 28, 29 | M | Insurer as the customer (DRP, vendor, commission) | **In** as held `insurer_payer` when the row prints customer-payment wording (T14); HCCLAIMPMT verified (§7.7). A carrier's bare `PAYMENTS` entry stays `non_revenue`: a business's own claim prints the same way (Q6: insurers never count) |
| 18, 57 | M | Healthcare payers without HCCLAIMPMT | **In** through `HEALTHCARE_PAYER_ALIASES` and Q6; Canadian carriers and the RBC claim label **out** (§7.7) |
| 20, 47 | M | Treasury and state vendor payments | **In** (§7.6) |
| 21 | M | Auctions and dealer funding | **In** (§7.8, §8.7); Copart and IAA **out** |
| 22 | M | Canadian brand deposit codes | **In** (anchored `brand_dep`) |
| 27 | H | HCCLAIMPMT from BCBS | **In**: claim first (§7.7) |
| 30, 31 | H | Chase book transfers from third parties | **In** (§7.11) |
| 32 | H | FUNDS TRANSFER incoming wires | **In** (§7.11) |
| 34 | M | Push-to-card printed as card credit | **In** (§7.11) |
| 44 | M | RTP and FedNow payer after the rail prefix | **In**: the payer after `FROM` or at the end of the RTP reference is parsed for the registry and §8; the rail word never verifies |
| 46 | M | RMR*IV and invoice memos | **In** for `RMR IV` (§7.5); free-text memos gated (§7.5) |
| 48 | H | Organisation wires with no invoice words | **In** through Q5 (§8.5); `PROGRESS BILLING` and `DRAW REQUEST` **out** (construction draws, §15) |
| 49 | M | Bank corporate-ACH wrappers | **In**: wrappers stripped before the payer is read (§5.2); a wrapper is an electronic-payment form |
| 50 | H | SEC code ignored | **In** as a signal only: a PPD or WEB entry never verifies by repetition alone (§8.6) |
| 51 | M | Fintech exports that print only the counterparty | **In** as `named_payer_unlabelled`, counted and not verified (§8.9) |
| 52 | M | Unregistered originator settling daily | **In** through Q6's repetition test (§8.6) |
| 53 | M | Generic card-sales words | **In** (`generic_card_sales`, §7.1) |
| 56 | M | French and TD merchant wording | **In** (§7.1, §7.5) |
| 58 | M | B2B payables platforms | **In** for AvidPay, AvidXchange, Coupa and Paymode (§7.5); Tipalti, Melio, Nvoicepay, MineralTree and Corpay **out** (they also move the business's own funds; counted and flagged) |

Low: S19 and S33 are in (§7.11). S24 is in (with S32). S23 (Venmo and Cash App business cash-outs) is out; they are counted as `p2p`. S25 (won chargebacks, reserve releases) is out; a reserve release under the `bankcard` form stays sales. S36 (consumer-finance funders) is out; they are counted. S54 (a holder named "… LOANS" makes every credit non-revenue) is out; it errs toward non-revenue, and one corpus row is affected. S55 (program reimbursements, tax-prep fee disbursements) is out; it waits on the subsidy ruling. S59 (lockbox) is out for Verified; it is counted as `check_deposit` (Q3). S60 is covered by Q7.

## 8. The definitional rules (classification 5.6)

Statement pass 7 (§6.2) runs after every verifying rule. It first computes each posted credit's payer facts (channel family, payer name, payer key, and the hold predicates of §8.1). Then it runs the Q5 and Q6 verifications (§8.5, §8.6). Last, it gives every remaining `unverified_deposit` its tier and reason, in the order of §8.10.

### 8.1 Holds that apply to any channel

- **`insurer_payer`:** a row whose revenue method is `insurer_customer_payment` (§6.1 step 5, T14). The customer-payment wording, read on a credit from a listed insurer, is `\b(?:DRP|VENDOR ?(?:PMT|PAY|PAYMENT)|COMM?ISS?IONS?|AGT ?COMM|AGENT COMP|AGTEFT|REPAIR)\b`.
- **`possible_return`:** `\bRETURN(?:ED|S)?\b`, `\bADJ(?:USTMENT|USTED)?\b`, `\bDISPUTE[DS]?\b`, `\bCREDIT MEMO\b`, `\bOVERPA\w*`, on a row the reversal rule did not claim.
- **`financing_named_payer`** (T4): the payer name, or the row before its receiver fields when no payer name is read, matches the credit-side financing roots. Before the roots are read, the credit posting labels of §7.5 are removed (plus `INSTANT CREDIT`, `REAL TIME CREDIT` and `CREDIT FROM`), and so are the channel phrases `FUNDS TRANSFER`, `FUNDS AVAILABLE` and `INSTANT FUNDS`. The roots: `(?:FUND|CAPIT|CAPTL|LOAN|LEND|FINANC|ADVANC|MORTG|ACCEPTANCE|SERVICING|SERVICER|LEASING|PORTFOL)`, `CRED(?=IT|ORA|IBLY|\b)`, or the whole words `CAP`, `CAPI`, `FIN`, `FINA`, `FINAN`, `FINL`, `FNCL`, `ADV`, `MTG`, `MCA`, `RTR`, `SPV`, `LEASE`. `FACTOR` is not a root: a factor's payout is revenue (owner, 2026-09-26), and registered factors are decided before this pass. A credit from a `DEALER_FUNDING_PAYERS` lender that the ledger has not yet admitted, and that prints no dealer wording, is held here too (§8.7). Approximate reach: $5.0M, 954 rows, 282 statements.
- **`holder_name`:** the payer name matches the holder's name (§5.2).
- **`payroll_or_salary`** (Q8), read on the row before its receiver fields:
  - `\bPAYROLL\w*`, `\bPAYRLL\b`, `\bPAYROL\b`, `\bSALARY\b`, `\bSALARIES\b`, `\bREG SAL\b`, `\bWAGES?\b`, `\bNET ?PAY\b`, `\bPAY PAY\b` (BMO's pay code), `\bPAIE\b`, `\bSALAIRES?\b`;
  - `DIR DEP` as an entry description: `\b(?:DES|CO ENTRY DESCR) DIR(?:ECT)? DEP\b` and `\bDIRDEP\b`. BMO's leading `DIRECT DEPOSIT,` template is not pay wording;
  - or `_is_payroll_provider_row`.
- **`personal_income`:** `\b(?:XX)?SOC SEC\b`, `\bSSA\b`, `\bSSI\b`, `\bSUPP SEC\b`, `\b(?:XX)?VA BEN\w*`, `\bUNEMPLOY\w*`, `\bUI BEN\w*`, `\bCHI?LD ?SUPP\w*\b`, `\bCHILD ?CTC\b`, `\bPENSION\b`, `\bANNUIT\w*`, `\bRETIRE\w*`.
- **`payer_debited_as_lender`:** the payer's first distinctive word (§7.5) is also the first distinctive word of a posted debit in the same statement whose state is `confirmed_lender`, `potential_lender` or a financing group. This is the unregistered funder that funds and then collects.

### 8.2 Q2: cash, branch, ATM and bare deposits; transfer wording

The patterns follow the memo's `categorize.py`, which agrees with 94% of 315 hand-sorted payer groups. The cash, branch and ATM patterns apply only to a row that prints no electronic-payment form and no person-to-person rail, so an ACH payer named like a branch (`BRANCH MESSENGER`) is never read as a teller deposit.
- **Cash:** `\bCASH DEP(?:OSIT)?\b`, `\bATM CASH\b`, `\bCPS DEVICE\b`, `\bCURRENCY PROCESSING\b`, `\bSMART ?SAFE\b`, `\bCOIN\b`, `\bCASH IN\b`.
- **Branch and teller:** `\bCOUNTER (?:CREDIT|DEPOSIT)\b`, `\bTELLER\b`, `\bIN BRANCH\b`, `\bBRANCH\b`, `\bBRCH\b`, `\bDEPOSIT AT BR\b`, `\bDEPOSIT THANK YOU\b`, `\bMAIN OFFICE\b`, `\bPRE ?ENCODED\b`, `\bNIGHT (?:DEP|DROP)\b`, `\bBANKING CENTRE\b`, `^GC\b.*\bDEPOSIT\b`, `\bDEPOT\b`, `\bVAULT DEP\w*`, `\bSTORE DEPOSIT\b`, `\bDEPOSIT MADE IN\b`.
- **ATM:** `\bATM\b.*\bDEP(?:OSIT)?\b`, `\bDEP(?:OSIT)?\b.*\bATM\b`, `\bABM\b`.
- These three are `counted_flagged` / `no_payer_printed`, never Verified.
- **Bare deposit, credit or EFT,** on any channel (BMO's `DIRECT DEPOSIT <digits>` included): after the generic words and reference tokens are removed, no payer word remains, and the row prints no transfer wording. It is `counted_flagged` / `no_payer_printed` too (§8.10, last step), never Verified.
- **Transfer wording:** `\bTRANSFER\b`, `\bTRNSFR\b`, `\bXFER\b`, `\bTFR\b`, `\bBR TO BR\b`, `\bONLINE BANKING\b`, `\bINTERNET (?:BANKING|TRANSFER)\b`, `\bFUNDS TRANSFER\b`.
  - With no counterparty (no payer word after the generic words, the account words and the reference tokens are removed), it is `excluded_pending_review` / `transfer_no_counterparty`.
  - With a named counterparty, the person-to-person rule applies (T13).

### 8.3 Q3: check deposits

`\bMOBILE (?:CHECK |CHEQUE )?(?:DEPOSIT|DEP)\b`, `\bMOBILE CHE(?:CK|QUE)\b`, `\bMB DEP\b`, `\bREMOTE (?:ONLINE )?(?:DEPOSIT|CAPTURE)\b`, `\bDEPOSIT CAPTURE\b`, `\bMERCHANT CAPTURE\b`, `\bDESKTOP (?:REMOTE )?DEPOSIT\b`, `\bEDEPOSIT SCAN\b`, `\bE ?CHEQUE DEPOSIT\b`, `\b(?:ATM )?CHE(?:CK|QUE)S? (?:DEPOSIT|DEP|RECEIVED)\b`, `\bMAIL DEPOSIT\b`, `^REMOTE$`, `\bIMAGED DEPOSIT\b`, `\bDEPOSITED (?:CHECK|ITEM)\b`, `\bRDC\b`, `\bSCAN(?:NED)? DEPOSIT\b`, `\bLOCKBOX\b`, `\bLBX DEP\b`.

These are `counted_flagged` / `check_deposit`, never Verified. A returned deposited item is decided earlier, as a reversal.

### 8.4 Q4: person-to-person, and named transfers

- **Rails:** `\bZELLE\b`, `\bINTERAC\b`, `\bE ?TRANSFER\b`, `\bE ?TFR\b`, `\bVIREMENT\b`, `\bAUTODEPOSIT\b`, `\bVENMO\b`, `\bCASH ?APP\b`, `\bSQUARE CASH\b`, `\bAPPLE CASH\b`, `\bREAL TIME (?:TRANSFER|PAYMENT)\b`, `\bRTP\b`, `\bFEDNOW\b`, `\bINSTANT (?:PMT|PAYMENT|TRANSFER)\b`, `\bVISA (?:MONEY TRANSFER|DIRECT)\b`, `\bMONEY TRANSFER\b`, `\bMC SEND\b`, `\bPMNT RCVD\b`, `\bPAYMENT RECEIVED\b`, `\bPOPMONEY\b`. A row the registry or a form already claimed (an RTP payout from Amazon, a Visa Direct payout from Square) is not a person-to-person row.
- **The sender** is the payer name (§5.2).
- **`p2p_round_repeat`:** a sender with two or more round-sum credits on these rails in the statement has every one of its round-sum credits held. Its other credits stay counted. The memo counted a repeat of any amount; this reading follows the ruling's words, "repeated round sums from one sender".
- A sender with the holder's name is `holder_name` (§8.1).
- Everything else is `counted_flagged` / `p2p`, never Verified, even when the sender prints a company form (Q4).

### 8.5 Q5: incoming wires

- **The wire family:** the leading labels of §7.9 N1, a Chase third-party book transfer (§7.11), or, for tiering only, the loose wire words `\bWIRE\b`, `\bFEDWIRE\b`, `\bFED WIRE\b`, `\bIWT\b`, `\bCHIPS CREDIT\b`, `\bSWIFT\b`, `\bFOREIGN REMITTANCE\b`, `\bWT FED\b`, `\bFED REF\b` on a row no rail of §8.4 claimed.
- **Verified: the same company twice or more** (method `repeat_wire_sender`, confidence 0.85). The row begins with an N1 label (or is a third-party book transfer), and:
  - its sender prints a company form (§5.2) or is a government or healthcare payer;
  - two or more wire credits in the statement have that payer key (repeats, §5.2);
  - the sender is not the holder and not a numbered company (T11), carries no financing root, and names no bank (`BANK`, `BANCO`, `BANCORP`, `N A`, `TRUST COMPANY`, `CREDIT UNION`, `FCU`, `SAVINGS`), since a relaying bank hides the real payer, and no title or escrow firm (`TITLE`, `ESCROW`, `CLOSING`, `SETTLEMENT`);
  - no posted debit in the statement goes to the same payer (an own account or an affiliate).
- **Verified: an invoice or PO wire:** §7.9 (step 14). N2's condition for Bank of America's `WIRE TYPE BOOK IN`, a ruling on Chase's book transfers, is §7.11 of this spec.
- **Held:** a wire with no sender printed is `wire_no_sender`; one with the holder's name is `holder_name`.
- **Otherwise:** `counted_flagged` / `wire_named_sender`, including senders that are persons, banks or title companies.

### 8.6 Q6: named ACH and EFT payers

**Eligible rows** are unverified posted credits that meet all of these:
- the row prints an electronic-payment form (§5.2) and a payer name;
- it prints no person-to-person rail and no transfer wording in its entry description;
- it is not a wire;
- no registry alias, payout entity or factoring payee matched it, because platforms are decided by §7;
- no hold of §8.1 applies;
- it is not a numbered company (T11).

**Verified** (method `named_payer_repeats`, `named_payer_company_form` or `public_or_healthcare_payer`) when any of these holds:
- (a) the payer repeats (§5.2) and at least one of its credits is not a `PPD` or `WEB` entry. A consumer entry never verifies by repetition alone (structural S50);
- (b) the payer name prints a company form;
- (c) the payer is a government payer (§5.2 and §7.6's patterns and vetoes) or a healthcare payer (§7.7).

**Guard:** no posted debit in the same statement shares the payer's first distinctive word (§7.5). A payer that is also debited is `counted_flagged` / `payer_also_debited`, and one debited as a lender is held (§8.1).

**Otherwise** the row is `counted_flagged` / `named_payer_one_off`.

Lenders are decided `non_revenue` earlier (D1 and the potential registry), unregistered ones are held (T4), insurers are `non_revenue` or held (T14), and the holder is held. That is Q6's "lenders, insurers and the holder never count."

### 8.7 Q7: an auto lender paying a dealer

At step 4 (§6.1), a credit is `verified_revenue` (method `auto_lender_dealer_funding`, source type `auto_dealer_funding`, confidence 0.90) when either:
- the row prints dealer-specific funding words: `\bVHCL PURCH\w*`, `\bVEHICLE PURCHASE\b`, `\bDEAL ?FUND\w*`, `\bFUNDLOAN\b`, `\bDEALER (?:FUND\w*|FND|PMT|PAY\w*)\b`, `\bDLR PMT\b`, `\bAUTODLRPMT\b`, `\bCONTRACT FUND\w*`, `\bVADMIN FEE\b`; or
- its payer is a listed auto lender and the row prints `\bPAYABLES\b`, `\bTRADE PAY\w*` or `\bACCT FUND\w*`. A listed auto lender is a `vehicle_financing` registry entity, or an entry of `DEALER_FUNDING_PAYERS` (registry, new: Westlake Financial (never Westlake Flooring), United Auto Credit, Strike Acceptance, PFS, Suncoast Credit Union, CU Direct / CUDL, Credit Acceptance, Exeter, Flagship Credit, GLS, Santander Consumer, Chrysler Capital, GM Financial, Toyota Financial, Honda Financial, Nissan Motor Acceptance, CarMax Auto Finance, Ally, American Credit Acceptance, Regional Acceptance, Nicholas Financial, Lendbuzz).

A reversal marker still wins, because step 3 runs first. Any other credit from a listed auto lender stays financing: D1 makes it `non_revenue` / financing proceeds. S1 admits the `DEALER_FUNDING_PAYERS` lenders the ledger lacks into its vehicle-financing group, through the ledger's process. Until a lender is admitted, its credits without dealer wording are held as `financing_named_payer`, whether or not its name carries a financing root. A dealer-funding credit is not financing proceeds, so it leaves `lender_credits` and returns to eligible deposits (an intended move).

Measured: corpus $3.7M in 4 statements, mostly one truck dealer. Tryout host: $0.56M, one used-car dealer.

### 8.8 Q8: payroll and salary

`payroll_or_salary` (§8.1) is held, whoever the payer is. A payroll credit from the holder is `holder_name`.

### 8.9 Everything else

- A registry match that did not verify: `counted_flagged` / `platform_unconfirmed`.
- A factoring payee's credit: `counted_flagged` / `factoring_payout`. It keeps its Factoring flag. The owner deferred its Verified status (2026-09-26).
- A credit from `PAYOUT_CREDIT_ENTITIES`: `counted_flagged` / `payout_credit_entity`.
- A numbered company: `counted_flagged` / `numbered_company_payer` (T11).
- A named payer on a row with no electronic-payment form (fintech exports, S51): `counted_flagged` / `named_payer_unlabelled`. It is never verified in this release. The census reports how much of it would pass Q6's test.
- No payer word at all: `counted_flagged` / `no_payer_printed`.

### 8.10 Tiering order and thresholds

For each unverified posted credit the pass takes the first that applies:
1. `direction_conflict`
2. `insurer_payer`
3. `possible_return`
4. `financing_named_payer`
5. `payer_debited_as_lender`
6. `holder_name`
7. `payroll_or_salary`
8. `personal_income`
9. wires (§8.5: `wire_no_sender`, or `wire_named_sender`)
10. `check_deposit`
11. cash, branch, ATM (`no_payer_printed`)
12. person-to-person and named transfers (`p2p_round_repeat`, or `p2p`)
13. `transfer_no_counterparty`
14. `platform_unconfirmed`
15. `factoring_payout`
16. `payout_credit_entity`
17. `numbered_company_payer`
18. `payer_also_debited`
19. `named_payer_one_off`
20. `named_payer_unlabelled`
21. `no_payer_printed`

| Threshold | Value | Where |
|---|---|---|
| Repeats | 2 or more credits, same payer, one statement | §5.2, Q5, Q6 |
| Round sum | at least $100, a whole multiple of $100 | §5.2, Q4 |
| Round-sum repeat | 2 or more round sums from one sender | §8.4 |
| Operating recurrence | 3 or more credits, or 2 on a business account (a legal-form holder counts) | §7.0 |
| Micro-deposit floor | under $1 never verifies and never counts | §7.0, §7.8, §7.10 |
| NET SETTLE from an unregistered originator | 3 or more credits | §7.1 |
| Auction refund window | 14 days, equal amount, one debit each | §7.8 |
| Package gate | held credits at least 10% of posted credits (`REVENUE_REVIEW_HELD_SHARE`) | T7 |

Each threshold is one named integer constant ($1 as `1`, $100 as `100`, 10% as `10`). The classification thresholds live in `analysis/transaction_classifier.py`. The gate's `REVENUE_REVIEW_HELD_SHARE` lives in `analysis/revenue.py`, which the metrics and the webapp both import.

## 9. The data contract

### 9.1 Per account (`report_to_dict` / `rebuild_serialized_revenue_views`)

- **Rows:** every `statement.transactions[].classification` carries `revenue_tier`, `revenue_initial_tier`, `revenue_tier_reason` and the flags of §5.4 (5.6).
- **Metrics:** unchanged keys keep their meaning. New keys:
  - `true_revenue_total`, `true_revenue_count`;
  - `counted_flagged_total`, `counted_flagged_count`;
  - `excluded_pending_review_total`, `excluded_pending_review_count`;
  - `counted_flagged_by_reason` and `excluded_pending_review_by_reason`, each `{reason: {"count": int, "total": float}}`;
  - `revenue_review_items`, the held count.

  `true_revenue` is repointed to `true_revenue_total` (T9). `revenue_review_required` means the gate of T7. `revenue_reconciles` checks the four-tier identity (§5.1).
- **Detection:** `true_revenue_evidence` is repointed to verified plus counted. `counted_flagged_evidence` and `excluded_pending_review_evidence` are new. `manual_review` holds the rows whose `revenue_review_required` is set (held rows) plus today's `review_required` rows.
- **Withholding:** `WITHHOLDING_DENOMINATOR_MODES` gains `true_revenue` (§11).

### 9.2 Package (`_package_analysis`)

- **Each document row** gains:
  - `true_revenue_total`, `true_revenue_count`, `counted_flagged_total`, `counted_flagged_count`, `excluded_pending_review_total`, `excluded_pending_review_count` and the two by-reason dicts;
  - `revenue_established`. It is today's `verified_revenue_established` condition (`webapp/app.py:1367-1376`) and every posted credit carries a 5.6 tier. `verified_revenue_established` stays, with the old condition, for the verified figure.
- **Totals:**
  - the same keys, summed over the members;
  - `true_revenue_total`, `counted_flagged_total`, `excluded_pending_review_total` and their counts are `None` when any completed member's `revenue_established` is false, and `verified_revenue_total` is `None` when any completed member's `verified_revenue_established` is false (§10.4);
  - `revenue_unestablished_documents` lists those members' ids;
  - `revenue_review_items` is the sum of the members' held counts;
  - `revenue_review_required` is the gate of T7, applied to each member.
- **Evidence:** the package's revenue evidence stays per state, and each evidence record carries its tier fields.
- **Currency:** the new money keys join `_CROSS_CURRENCY_TOTAL_KEYS` and the test's `EXPECTED_REFUSED_TOTALS`, the counts join `UNIT_FREE_TOTALS`, and a refused package sets every `total` inside the by-reason dicts to `None`.

### 9.3 Versions

- 5.5 (the fixes, §7): `CLASSIFICATION_VERSION = "5.5"`, and `ANALYSIS_STAGE_VERSION` 23 → 24 in the same commit.
- 5.6 (the definition, §5, §8): `CLASSIFICATION_VERSION = "5.6"`, and `ANALYSIS_STAGE_VERSION` 24 → 25 in the same commit.

Each bump makes a re-upload recompute the analysis, keeps OCR cached, and sets `analysis_rules_outdated` on older saved analyses (lender spec D12).

## 10. Metrics and UI

### 10.1 Cards (statement page, package page, statement modal)

The Credits section becomes:

| Card | Value | Glyph, tone | Filter |
|---|---|---|---|
| **True Revenue** (headline, first and larger) | `true_revenue_total` | REV, green | `true_revenue` |
| Verified Revenue (beside it) | `verified_revenue_total`, with its share of True | VER, green | `verified_revenue` |
| Counted, Not Verified | `counted_flagged_total` | CNT, teal | `counted_flagged` |
| Held for Review | `excluded_pending_review_total` | ?, amber | `excluded_pending_review` |
| Non-Revenue | `non_revenue_total` | X, neutral | `non_revenue` |
| Total Credits | unchanged | CR, neutral | — |
| ACH Credits | unchanged | ACH, neutral | — |

The "Unverified Deposits" and "Revenue Upper Bound" cards are removed. `maximum_revenue` stays in the payload and the exports. The statement modal shows counts beside totals, as today.

### 10.2 Monthly Statements

The Settings basis keeps its three views (both, total, true), which are stored in the browser only. A single-basis view keeps the CRM's own headers, as today.
- **The True view:** "Monthly Deposits ($)" (True revenue), "Deposits Per Month" (verified plus counted rows) and, new, "Verified ($)".
- **The Both view:** "Total Deposits ($)", "Total Deposits Per Month", "True Deposits ($)" (True revenue), "True Deposits Per Month" and, new, "Verified ($)".
- `trueDeposits(doc)` reads `true_revenue_total` when `revenue_established` is true, otherwise N/A.
- A new `verifiedDeposits(doc)` reads `verified_revenue_total` when `verified_revenue_established` is true, otherwise N/A.

The Settings text (`index.html:1507-1508`) becomes: "True revenue: every posted credit except known non-revenue (own-account transfers, funding, refunds) and the deposits held for review. The verified part, with positive proof, is shown beside it."

### 10.3 The chart

Each Total bar holds its True part, and the True part holds its Verified part, in three shades.
- Legend: "Total deposits", "True revenue", "of which verified".
- In the True view, the bar is True revenue, with its Verified part shaded.
- A statement whose revenue is not established draws no True or Verified part, and its labels read N/A.

### 10.4 N/A rules (the D-1 fix)

The trace's D-1: the Verified Revenue cards print $0.00 or a partial figure where revenue is not established, and the package total adds such members in.
- A statement's True, Counted and Held figures show **N/A**, never $0.00, unless `revenue_established` is true: every posted credit carries a revenue state and a 5.6 tier, and the captured credits are the money the statement's Total counts. Its Verified figure shows N/A unless `verified_revenue_established` is true (today's condition, without the tier).
- The server computes both flags once, in `_displayed` for a statement and in `_package_analysis` for a package member, and the dashboard reads them. A statement with no captured credit and a zero Total is established at zero.
- A package's True, Counted and Held totals are N/A when any completed member's `revenue_established` is false, and its Verified total when any completed member's `verified_revenue_established` is false. The note under them names how many statements are not established ("2 of 6 statements have no established revenue"). A failed member is counted under `failed` as today; its credits are in no total.
- An outdated payload (before 5.6): True, Counted and Held are N/A, with the note "Re-analyze to compute true revenue". Verified shows the stored figure under the outdated notice.

### 10.5 Copy (`REVENUE_METRIC_COPY`)

- `trueRevenue`: "Posted credits minus known non-revenue and the deposits held for review"
- `verifiedRevenue`: "Revenue with proof: settlements, platform payouts, repeat or institutional payers, invoices, and deposits you confirmed"
- `countedFlagged`: "Counted in true revenue without proof of the payer: cash, checks, person-to-person, one-off payers"
- `heldForReview`: "Kept out of true revenue until you confirm it"
- `nonRevenue`: "Own-account transfers, funding, refunds and other known non-revenue"
- `totalCredits`, `achCredits`: unchanged.

The side badge's title (`index.html:965`) becomes "Deposits held for review". The results-page sentence (`index.html:925`) becomes "Deposits held for review, and counted deposits, can be confirmed or excluded from the Review column." The outdated notice (`index.html:1179`) reads "Analysed with older classification rules." instead of "older lender rules", because it now covers revenue.

### 10.6 Ledger tags, filters and chips

- `transactionCategory`: a verified credit is "Verified revenue" (VER, green), a counted one is "Counted: <reason label>" (CNT, teal), a held one is "Held: <reason label>" (?, amber), and a non-revenue one is "Non-revenue" (X, neutral). Reason labels come from the payload's reason code through one JS table that mirrors `REVENUE_TIER_REASONS`.
- A property-management verified row shows the chip "Property-management collections" (T15). A factoring credit keeps its "Flagged" chip.
- Filter pills (statement and modal): True Revenue, Verified, Counted, Held for Review, Non-Revenue. The `data-transaction-filter` values are `true_revenue`, `verified_revenue`, `counted_flagged`, `excluded_pending_review` and `non_revenue`.
- `revenueReviewReason` shows the reason label and one sentence for each code.

### 10.7 The review queue

- **What needs review now:** the held rows. The side badge counts `revenue_review_items` (the held count), and a "Held for Review" view groups them by reason, largest total first.
- **What may be reviewed:**
  - Held and counted rows show Confirm Revenue and Mark Non-Revenue.
  - A rule-verified row shows Mark Non-Revenue only (T6).
  - A decided row shows its decision and Reset Decision.
  - Non-revenue rows have no controls (§15).
- **The server** (`analysis/revenue.py` `record_serialized_revenue_review`):
  - allowed initial states become `unverified_deposit` and `verified_revenue`;
  - `confirm` on a row whose initial state is `verified_revenue` is refused ("already verified");
  - confirm sets tier `verified`, reject sets tier `non_revenue`, and reset restores `revenue_initial_classification` and `revenue_initial_tier`;
  - the reason is kept for the audit.
- **Storage:** `webapp/jobs.py` records the full classification as `prior_state` today, so the tier fields reach the audit without a schema change. `review_decisions` is unchanged.
- **Replay:** `webapp/reanalysis.py` `_awaits_review` accepts rows whose initial state is `unverified_deposit`, or `verified_revenue` decided by a rule. A replayed reject on a now rule-verified row stands: the analyst's word wins over a rule. A replayed confirm on a now rule-verified row is reported under `reviews_decided_by_rules`, as today.
- **The multi-select batch** (`/analysis/<job_id>/revenue-reviews`) takes the same rows.

### 10.8 Exports

- **Statement CSV/XLSX:** the new metric keys flatten as today. The by-reason dicts are written as readable rows through the escaped-row path: section `revenue_tier`, field `<tier>.<reason>.count` / `.total`. A row's classification record, in evidence, carries its tier fields.
- **Package CSV/XLSX:** totals and document rows gain the keys of §9.2. The per-state evidence sections are unchanged, and each record carries its tier fields. The currency sweep covers the new money keys and the by-reason totals.
- **JSON:** follows the displayed payload.

## 11. Withholding

- **Default unchanged:** `legacy_eligible_deposits`, effective deposits minus lender (financing-proceeds) credits, less internal-transfer credits in a package. Nothing in this spec gives a reason to move the default.
- **Selectable:** `verified_revenue` (unchanged, Q1), and the new `true_revenue` (T8). Both are set through `WITHHOLDING_DENOMINATOR_MODE`, as today; the tryout host does not set it.
- **How the figures relate.** Every financing-proceeds credit is `non_revenue`, so when a statement's line items are its Total, True revenue ≤ legacy eligible deposits. The gap is the other non-revenue (own-account transfers, refunds, insurance, potential-lender credits, duplicates) plus the held credits. Verified ≤ True always.
- **Where eligible deposits move:**
  - down, where `SQ CAP` and SBA or EIDL credits become financing proceeds (§7.11);
  - up, where Q7 takes dealer funding out of D1 (§8.7).

  Both moves are listed in the census.

## 12. Backward compatibility

- **Stored analyses are never rewritten.** A saved job keeps its payload until someone re-analyzes it, and the Re-analyze route (lender spec §8.6) replays review decisions as today, with §10.7's widening.
- **Outdated notice:** automatic for every analysis older than the running version (§9.3).
- **Before 5.6:** no tiers. The served copy sets `revenue_established` false, sets `true_revenue`, `true_revenue_total` and the tier totals to `None`, and keeps `verified_revenue_*` as stored (T10). The stored job is untouched: `_displayed` copies before it changes anything, as `apply_flagged_groups_to_payload` does.
- **Field names** (T9):
  - kept with their meaning: `revenue_classification`, `verified_revenue_*`, `unverified_deposit_*`, `non_revenue_*`, `maximum_revenue`, `revenue_initial_classification`, `revenue_review_status`, `confirmed_true_revenue*` (Verified) and `potential_revenue*` (unverified);
  - repointed: `true_revenue`, `contributes_to_true_revenue` and `true_revenue_evidence`, to the new True revenue;
  - changed in meaning and stated: `revenue_review_required`, on a row and in metrics (T7), and `manual_review`;
  - new: everything in §9.
- **`LEGACY_REVENUE_STATE_MAP`** (`true_revenue` → `verified_revenue`, `potential_revenue` → `unverified_deposit`) keeps reading records from before version 3.0. It maps stored **state** strings, not metric names, so repointing the `true_revenue` metric does not touch it.

## 13. Every consumer, and what it must do

| Consumer | Change |
|---|---|
| `analysis/transaction_classifier.py` | §6 and §7 (5.5); the record fields, `_replace_revenue_state` taking a tier, the true-revenue pass, duplicate finalisation setting tier `non_revenue` (5.6); versions |
| `analysis/description_text.py` | the street-`LN` guard (5.5) |
| `analysis/classification_registry.py` | the operating additions, payout and card forms, `HEALTHCARE_PAYER_ALIASES`, `DEALER_FUNDING_PAYERS`, truncations; ledger admissions for processor capital products |
| `analysis/revenue.py` | `REVENUE_TIERS`, `REVENUE_TIER_REASONS`, `REVENUE_REVIEW_HELD_SHARE`, `revenue_contribution_flags(state, tier)`, the new totals and evidence, repointed aliases, `revenue_review_required` (T7), review rules (§10.7), the `true_revenue` withholding mode |
| `analysis/metrics.py` | tier sums, the "exactly one tier" check, new fields, repointed `true_revenue`, the gate, the `true_revenue` mode; `eligible_deposits` unchanged |
| `analysis/detect.py` | repointed `true_revenue_evidence`; the counted and held evidence lists; `manual_review` |
| `analysis/serialization.py` | the same evidence keys (`:195-208`) |
| `analysis/flagged_view.py` | none: the outdated flag already compares versions |
| `webapp/app.py` | §9.2, §10.4 in `_displayed` and `_package_analysis`, the decision gate (`:1951-1962`), currency keys (`:692-727`), exports (`:346-486`), review routes (`:2521`, `:2574`) |
| `webapp/reanalysis.py` | `_awaits_review` (§10.7) |
| `webapp/jobs.py`, `webapp/storage.py` | none: the full record already reaches `prior_state` |
| `webapp/settings.py` | none |
| `webapp/static/app.js`, `webapp/templates/index.html` | §10.1 to §10.7 |
| `batch.py` | columns `true_revenue_total`, `counted_flagged_total`, `excluded_pending_review_total`; its manual-review flag reads the new `revenue_review_required` |
| `analyze.py` | prints True, Verified, Counted and Held |
| `benchmark/compare.py`, `benchmark/run.py` | MoneyThumb's `true_credits` is subtraction-based, so it is compared with `true_revenue_total`, and Verified is reported beside it |
| `tools/lender_census.py` | unchanged; it runs as guard G7 |
| `tools/revenue_census.py` (new) | §14.2 |
| `docs/transaction-classification.md` | the revenue section (`:86-105`, `:496-503`): the definition, tiers, precedence, holds, extension rules for the operating registry, payout forms and healthcare and dealer tables |
| Tests | re-pinned: `tests/test_analysis.py:3361` (`m.true_revenue`), `tests/test_package_currency.py:732-735` and its key sets, `tests/test_factoring_credits.py:47-53` (the RTS row becomes counted, `factoring_payout`), `tests/l1s3_payloads.py:149-150`; new cases in §14.1 |

## 14. Testing and acceptance

### 14.1 Fabricated tests, for each rule

All rows are fabricated, in the bank's format (`FABRIKAM`, `CONTOSO`, `SAMPLE` names). They go in `tests/test_revenue_classification.py` unless stated.
- **§7.0:** Chase glued and spaced `Sec` for HCCLAIMPMT, SETTLEMENT and NET SETTLE; the joined fields for BofA `MERCHANT BANKCD DES:DEPOSIT` and Chase `Merchant Bankcd … Merch Dep`; the glued date prefix; each truncation; the pool that does not shrink (three Square rows, one verified by context); the recurrence veto (`SQ CAP` inside a Square statement; `SHIFT4 PAYMENTS DES:CAP ADV` and `SUMUP DES:CASH ADV` beside three settlements; four weekly `HEARTLAND PAYMENT SYSTEMS DES:PAYROLL`); a holder `… PAYROLL SERVICES LLC` whose settlements stay verified; three mis-signed Elavon rows that stay unverified; a $0.03 micro-deposit beside three payouts.
- **§7.1:** every form positive in each bank layout; every verifier negative: `<X> Bankcard LLC` with ADV and with DEPOSIT, `MISC PAYMENT <processor> CAP ADV`, `TRANSFER FROM SV01`, `BANKCARD DEP CB REV`, `OWNER CONTRIB MERCH DEP`, `ELAN BANKCARD SETTLEMENT CREDIT`, `VISA DEP <person>`, `STRIPE DES:CLAIM PAYM ID:ST-…`, law-firm and title NET SETTLE rows in the DES and CO ENTRY DESCR layouts.
- **§7.2:** each form and alias; every negative of both verifiers: the pay variants, the financing words, the reversal abbreviations, `AMAZON CAPITALSV … PAYMENTS`, `AMAZON COMSERVIC … PAYMENTS`, `EBAY COM<8> PAYMENTS RETURN`, `TIKTOK INC DES:DIR DEP`, a TikTok card refund three times, Zelle naming Whatnot, three mis-signed form rows.
- **§7.3:** three Super Dispatch payouts that verify; a single one that stays unverified; three card-shaped refunds that never recur into verified.
- **§7.5:** the 21 positives and 18 negatives of the probe; every reviewer negative (the funder statement with AP-worded credit plus same-name daily debits; a floor-plan-shaped `Payables … Vin:` credit; the cut names `… CAPI`, `… FUN`, `… FINA`, `… FINAN`, `… LOA`, `… LEASIN`, `… ADVANTAG`, `BIZ2CREDIT`; `Direct Deposit, <digits> ONTA AP /CC`; `ONLINE TRANSFER FROM INV 1234567`; `ZERO BALANCE TRANSFER CREDIT A/P PAYMENTS`; `ACH RTN VENDOR PAY … R03`; `BILL.COM DES:PAYABLES`; a person's Zelle "paying bills" and "Invoice 1234"; `DEPOSIT INV 1234`; `Remote Online Deposit … Invoice 55`).
- **§7.6:** each arm in the Citibank, BofA CTX, U.S. Bank, Chase glued and Wells Fargo formats; label-less holder-leak negatives (Wells Fargo, Truist, PNC `RECEIVER NAME`); a glued lender name; an EBT-in-DES row; one negative per veto word; the BofA boilerplate positive; `TRANSFER FROM COUNTY LINE … VENDOR PAY`; a PPD `DOD MISC` row that stays unverified; a verified row still demoted by the duplicate pass and by a `RETURNED ITEM` pair.
- **§7.7:** the list in §7.7.
- **§7.8:** direction conflict; `FUNDING`, `ADVANCE`, `CAPTL`, `AFC FUNDNG`, `FLOORPLAN`, `FINANCING`, `NGC`; an alias in `IND NAME`, `INDN`, a Zelle "to" field and a memo, with and without `DISBURSEMENT`; `PAYROLL`, `PPD`, `DIR DEP`; `DEALSHIELD`, `ARB CREDIT`, card credits; a wire-paid and a Wells Fargo `Manheim ACH Paymnt` debit pair; the ACV `PYMT` hold; the D1 controls (ACV Capital, NextGear, AFC Funding, Westlake Flooring, Kinetic Advantage); the duplicate override.
- **§7.9:** the 40 cases of `simulate_v3.py`; the hazard groups G1 to G11; the returned-wire two-row statement; `CAPI TAL` and `FUN DING`; an individual citing an invoice; a sister company sharing its first word; `INV 1234 ADJ`; an address `PO 4521`; a Zelle memo with "wire"; `Unknown wire credit` stays unverified.
- **§7.10:** the eight lone rows that stay `operating_source_requires_context`; a Buildium fee debit plus one credit that stays unverified; a `$0.12` / `$0.21` ACCTVERIFY pair; a mixed-shape AppFolio pair.
- **§7.11:** a Medicaid REIMBURSEMENT that verifies, and an employer EXP REIMB that stays `non_revenue`; `12 OAK LN` in a wire and an ATM location, and `TRUIST LN PYMT` still a bank loan (debit); a Chase book transfer from a third party and one from the holder; RBC `Funds transfer credit TT`; Relay `Debit Card Credit: Stripe`; `CUSTOMER ID` on a Truist ACH row; each new non-revenue marker.
- **§8:** one test per reason code in §5.3, and per verification (Q5 repeats, Q6 a, b and c), each with its guard's negative (holder, financing root, counter-debit, PPD repeats, bank-named and title senders, numbered company). The round-sum rule: two round sums from one sender are held, and one round plus one odd are counted. A named transfer is counted. A transfer with no counterparty is held.
- **§9:** the identity `verified + counted + held + non_revenue = posted` on every fixture; a record whose tier and state disagree is refused.
- **Webapp** (`tests/test_webapp_revenue_batch.py`, `tests/test_webapp_review_ui.py`, `tests/test_webapp_reanalysis.py`, `tests/test_package_currency.py`, `tests/webapp_js_harness.py`): the cards, the N/A rules (an unestablished statement, an outdated payload, a package with one unestablished member), the gate, reviewing each tier, rejecting a rule-verified row, reset to the initial tier, replay across 5.5 → 5.6, exports and currency refusal of the new keys.

### 14.2 The census (`tools/revenue_census.py`, local only)

The census re-classifies every cached analysis at the base (5.4), at 5.5 and at 5.6. It uses the account filter of `tools/lender_census.py` (reconciled, de-duplicated by statement fingerprint) and never drops `non_revenue` rows. Its output is digit-masked and stays in the private research folder.

For the tryout host, the same tool runs read-only against a copy of the host's job store. This is the per-row dump both government and AP verifiers asked for, because the existing tryout dump is grouped by payer and holds no `non_revenue` rows.

It reports, for each run:
- True share, Verified share, and the count of statements at $0 for each; the median statement share;
- the dollars and rows in each tier and each reason code;
- a move matrix, from each base (state, rule) to each new (tier, reason), in dollars, rows and statements;
- every row that left `non_revenue`, grouped by the narrowing of §6.3 that moved it; any row outside those seven is a failure;
- every row that went from verified to anything else, grouped by declared cause (§7.0, §7.11); any other cause is a failure;
- `lender_credits` and eligible-deposit moves by cause (§11);
- the package gate's blocked share before and after (T7);
- the sizes behind T4, T11 and T13, and how much of `named_payer_unlabelled` would pass Q6.

### 14.3 Guard checks (hard gates)

No loan, transfer, refund or owner money becomes revenue:
- **G1:** no row decided `non_revenue` by reversal, the insurer registry, D1, descriptor proceeds, the potential registry, strong non-revenue or duplicates at the base reaches True at 5.6, except through the narrowings of §6.3 that lead to True (1, 2, 4, 5, 6 and 7), each listed.
- **G2:** no row whose payer name carries a financing root is Verified, except Q7's dealer funding.
- **G3:** no row whose payer is the holder is in True.
- **G4:** no row with transfer wording and no counterparty is in True.
- **G5:** no row that `match_known_payee` places in a financing group reaches True, except payout-credit entities, factoring payees and Q7's dealer funding.
- **G6:** no row whose revenue method is `direction_conflict` is in True.
- **G7:** `tools/lender_census.py` at 5.6 shows zero lender, potential-lender and flag changes on debits against 5.4.
- **G8:** every fabricated negative of §14.1 passes.
- **G9:** the four-tier identity holds on every cached analysis.

### 14.4 Measured targets

These are the definition memo's and the verifiers' measurements. The census must report each one, and it must explain every deviation beyond the tolerance by a named decision of §4.

| Figure | Base (5.4) | Target |
|---|---|---|
| Corpus Verified, after 5.5 | 7.2% | about 14% or more. The card and platform fixes alone: 14.1% per the memo, 13.1% per the card verifier; the other families add more |
| Corpus $0-verified statements, after 5.5 | 1,819 | at most about 1,465; the memo's processor-gap estimate is 1,338 |
| Corpus True, after 5.6 | (7.2%, verified only) | 72.7% ± 3 points, less about 1.8 (T4), plus up to 1.5 (T13) |
| Corpus $0-True statements, after 5.6 | 1,819 | about 107 |
| Corpus median statement True share | 0% | about 87% |
| Corpus Verified, after 5.6 | 7.2% | 22% to 29%; the memo gives 22.3% with the rulings and 29.2% with the processor gaps |
| Corpus $0-verified statements, after 5.6 | 1,819 | between 945 and 1,281 |
| Tryout host True, after 5.6 | 13.4% | about 77% |
| Tryout host Verified, after 5.6 | 13.4% | about 26% (39.8% only if one payer's repeat wires verify) |
| Package revenue gate, corpus statements | 95.6% | about 25% to 30% (T7; the memo's holds give 24.6%, and T3's extra holds add to it) |
| Non-revenue moves | — | only §6.3 and §7.11's declared moves |

The healthcare, government and auction fixes barely move the tryout host. The owner should expect its gains from the card and platform fixes and from the definition.

## 15. Out of scope, and the deferred items

- Payer-wide review decisions: OQ1.
- Analyst overrides of rows a non-revenue rule decided. The trace's wrong non-revenue rows are fixed by §7.11. An override would move eligible deposits and the lender-credit exclusion, so it needs its own design.
- Counting recurrence across statements, accounts or packages.
- The families' open owner items that this spec does not decide. Their rows are counted and flagged (or held, where §8.1 says) until the owner rules:
  - tuition through a payfac (the SV suffix);
  - Applied Systems' agency-bill premium;
  - Lyft and individuals' gig income, and Super Dispatch's quick-pay;
  - TikTok creator payouts;
  - tax-preparer fee disbursements and SBTPG;
  - EBT settlements (arm C) and child-care subsidies (CCDF, CACFP);
  - government grants paid as vendor payments;
  - Canadian benefit carriers and the RBC claim label;
  - construction draws and progress billing;
  - intercompany invoices;
  - lease-to-own payers (Acima), and the other accounts-payable items listed at the end of §7.5;
  - property managers' trust money;
  - auction vendor payments and non-dealer consignors;
  - eCommission's commission advances.
- The transaction classification of credits, such as Heartland's `TXNS/FEES` credit classified `fee`: revenue is unaffected, and the dashboard shows a credit's revenue tag first.
- Residuals that no printed word can close, recorded for the owner:
  - an unregistered funder that prints a neutral name and a neutral entry (it is counted);
  - processor or platform capital paid out inside normal settlements;
  - a Faire retailer's refund;
  - a single-row PayPal push-to-card from a person, verified today by PayPal recurrence;
  - the bank templates that print `ACH CREDIT` on every credit, which verify a lone registry alias (§7.10 closes this for property platforms only).

## 16. Services and rollout

The owner's standing rule applies: one Opus 5.5 implementer per service, then an independent reviewer under the orchestration model policy (`docs/agent-handoffs/ORCHESTRATION-MODEL-POLICY.md`). The orchestrator checks each report's evidence before accepting it.

| # | Service | Owns | Starts after |
|---|---|---|---|
| S1 | Registry and vocabularies | §7.1 to §7.10's registry tables, truncations, `HEALTHCARE_PAYER_ALIASES`, `DEALER_FUNDING_PAYERS`, the validator (§7.4), the ledger admissions of the processors' capital products | this spec's approval |
| S2 | Classifier 5.5 | §6.1 steps 3 and 5 to 14, statement passes 4 to 6, §7.0 to §7.11, the 5.5 tests, the version bump | S1 |
| S3 | Census tool | §14.2 and §14.3; runs on 5.4 → 5.5 before S4 starts | S2 |
| S4 | Classifier and payload 5.6 | §6.1 step 4 (Q7), statement pass 7, §5, §8, §9, §11, `analysis/revenue.py`, `metrics.py`, `detect.py`, `serialization.py`, `batch.py`, `analyze.py`, the benchmark, the docs, the version bump | S3's 5.5 report accepted |
| S5 | Webapp serving, package, review and exports | §9.2, §10.4, §10.7, §10.8 | S4's contract (§9); may start on fixtures built from it |
| S6 | Dashboard | §10.1 to §10.3, §10.5, §10.6, §10.7's controls | the same |

- **Order:** S1, then S2, then the 5.5 census (S3), then S4, then S5 and S6 in parallel. Then the 5.6 census, both guard sets, the targeted tests, the full suite at the train, and a browser check of the dashboard.
- **Merge and hosting:** the branch merges only after every review closes and the owner has read both census reports. The tryout host is not updated unless the owner asks, and its census runs read-only.

## 17. Open questions

The owner has ruled on Q1 to Q8. These are the few left.

- **OQ1. "Apply to every row of this payer."** Recommendation: a follow-up release, not this one.
  - It needs a payer identity that holds across statements and uploads. This spec defines the credit payer key (§5.2), which the follow-up would reuse. It also needs a decisions table keyed by that payer (today's decisions are per job and row), and a rule for when a later statement's row matches.
  - Shipping it inside this release would make the census unmeasurable, because a decision would move rows the rules did not.
  - T7 already cuts the gated share from 95.6% to about 25% to 30%.
- **OQ2. BNPL merchant settlements** (Affirm, Klarna, Afterpay, GreenSky, Sunbit). Should they join `PAYOUT_CREDIT_ENTITIES`, so that their settlements to the merchant are revenue rather than financing proceeds (lender spec D2)? Today they are `non_revenue`. They are rare in the corpus (13 rows).
- **OQ3. Numbered-company payers** (T11: $11.1M, 4.0% of corpus credits, 183 rows). This spec counts them in True, flagged, and never verifies them. Should they be held out until confirmed instead? That would take about 4 points off True.
- **OQ4. The deferred family items of §15.** Each one's rows stay counted and flagged (or held) until you rule. The research folder lists every item with its measured size.
