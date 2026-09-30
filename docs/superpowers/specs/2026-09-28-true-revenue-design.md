# True and verified revenue: design

- **Date:** 2026-09-28
- **Branch:** `true-revenue`, from `lender-detection` at `c106634` (classification 5.4, `ANALYSIS_STAGE_VERSION` 23)
- **Owner:** Gustavo
- **Status:** draft for the owner's review, revised after the first independent review (§18)
- **Replaces:** the lender work, which the owner set aside on 2026-09-28 for this project
- **Evidence (private, never committed):** `lender-research/revenue/`: `trace_report.md` (the pipeline trace), `definition_memo.md` (the eight questions and their measured options), `digest_families.md` and `hunt_result.json` (nine payer families, each reviewed by two independent Opus verifiers; 60 structural misses found in 437 fabricated statement shapes), `work/spec/review/` (the first review's 48-row simulation) and `work/spec/revision/revision_probe.py` (the revised holds re-measured on the memo's rows). Every example in this spec is fabricated in the bank's format. Only public companies (processors, marketplaces, lenders, agencies, large retailers) are named.

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

The rulings above did not settle these. Each is numbered T1 to T19 so the plan and the reviews can cite it. T18 and T19 move rows out of `non_revenue` and need the owner's explicit word before they ship (OQ5, OQ6).

- **T1. Three revenue states stay; a tier is added.** `revenue_classification` keeps its three values (`verified_revenue`, `unverified_deposit`, `non_revenue`), so every consumer that reads them keeps its meaning. Two new record fields carry the per-row contract: `revenue_tier` (`verified`, `counted_flagged`, `excluded_pending_review`, `non_revenue`) and `revenue_tier_reason` (§5.3). Both `counted_flagged` and `excluded_pending_review` are `unverified_deposit` rows: neither is proven. Rejected alternative: a fourth state. It would break every consumer that validates three states (`REVENUE_STATES` in `webapp/app.py`, the "exactly one state" check in `analysis/metrics.py`) and every stored payload's reading of them.
- **T2. Counted is the default.** An unverified posted credit is `counted_flagged` unless one of the held reasons of §5.3 names it (§8 tests them). This is what "all posted credits minus known non-revenue" means row by row.
- **T3. The holds are a closed list** (§5.3). Besides the owner's own (Q2 transfer wording, Q4, Q5 and Q8, and the holder's name of Q4 to Q6), it holds the kinds of row that subtraction would otherwise count although the standing rule (loans, transfers, refunds and owner money never become revenue) or Q6 ("insurers never count") keeps them out:
  - a direction conflict;
  - an insurer's customer-payment credit (T14), and a payer whose name reads as an insurer;
  - bare return or adjustment wording, and a card credit released from the reversal rule that no form verifies (§7.11);
  - a payer whose name or entry reads as financing (T4);
  - a payer the statement also debits, as a lender or otherwise (an own account, an affiliate or a funder that collects);
  - a non-sale purpose: owner money, investment, intercompany sweeps, grants, rebates, claims, interest, dividends, and a public payer's refund or benefit;
  - benefit and pension credits;
  - a named transfer that prints an account designation.
  Each is reviewable.
- **T4. The financing-named payer hold.** Under subtraction, an unregistered funder's advance with a neutral entry (`FABFUND CAPITAL DES:PAYMENT`) or a neutral name (`CONTOSO PARTNERS LLC DES:FUNDING`) would count as revenue. That breaks the standing rule that loans never become revenue. A credit whose payer region or entry fields carry a financing root (§8.1) is therefore held unless a verifying rule, the registry, a payout entity or a factoring payee has claimed it. Approximate cost, measured on the memo's deposit types with the rule as §8.1 words it: $2.1M (0.8% of corpus credits), 402 rows, 174 statements. The first draft's $5.0M read the whole row, and left out the branch rows that its own wording would have held: Bank of America's `COUNTER CREDIT` read as `CRED(?=IT)` (307 rows, $4.92M, which the review measured). It errs in the safe direction: customers named "Advanced …" or "Capitol …" are held too.
- **T5. Newly named non-revenue.** Wording that was harmless while unverified credits never counted is now named, because it would otherwise count: the unambiguous return codes, tax-refund abbreviations, SBA and EIDL disbursements, Square Capital's `SQ CAP` spelling, and account-verification micro-deposits (§7.11). Each is a narrow, printed marker. The measured moves are reported in the census.
- **T6. Review.** Confirm makes a row `verified_revenue`, because an analyst's confirmation is proof. Reject makes it `non_revenue`. Reset restores the row's initial state and tier. Reviewable rows are every `counted_flagged` and `excluded_pending_review` row, and, new, every row a rule verified. A reviewer can reject a false verification. The new rules verify roughly three times today's dollars, and the government verifier required either this or a declaration that rule-verified rows are final. Rows a non-revenue rule decided stay outside review, as today (§15).
- **T7. The package gate.** A package needs revenue review when a member has a direction conflict, when its held credits are 10% or more of its posted credits, or when its revenue does not reconcile. The share is compared in integer cents (`held_cents * 100 >= REVENUE_REVIEW_HELD_SHARE * posted_cents`), and its denominator is every posted credit, non-revenue included. Counted, flagged rows never gate: the owner ruled that they count. On the memo's approximate deposit types, with the revised holds that can be measured there, 27.5% of statements have held credits of 10% or more, and 48.6% have at least one held row (the first draft's memo holds gave 24.6% and 39.9%). The holds that need debits or non-revenue rows cannot be measured there, so expect about 28% to 32%. Today, 95.6% of statements are gated. The 10% is one constant, `REVENUE_REVIEW_HELD_SHARE`.
- **T8. Withholding.** The default denominator stays legacy eligible deposits. Verified revenue stays selectable, and True revenue is added as a third selectable basis (MoneyThumb describes its `mca_withhold_percent` against true revenue), but it is not the default (§11).
- **T9. Field names.** Names whose meaning is kept stay. The deprecated aliases `true_revenue`, `contributes_to_true_revenue` and `true_revenue_evidence` are **repointed** to the new True revenue, because a payload whose `true_revenue` differs from the "True revenue" on screen is a trap for every reader of the JSON and the exports. `confirmed_true_revenue*` stays an alias of Verified; the word "confirmed" says proof. `potential_revenue*` stays an alias of unverified (both tiers). Nothing in `webapp/static/app.js` reads the repointed names. The two server fallbacks that read `metrics["true_revenue"]` as a verified figure or a withholding denominator are dropped (§9.2). The tests that pin them are re-pinned (§13).
- **T10. Old payloads.** A payload analysed before 5.6 carries no tier. It is served as stored and marked outdated. True revenue shows N/A with a Re-analyze action. The served copy nulls `true_revenue` and every `true_revenue_evidence`, and drops `contributes_to_true_revenue` from every row, so no old alias is ever read with its new meaning. Its verified figure is shown under the outdated notice. Its rows are reviewed under today's rules, and it is gated by today's rule (§12).
- **T11. Numbered-company payers are never Verified.** A Canadian numbered company paying the holder (`<digits> ONTARIO INC`, BMO's cut `<digits> ONTA`) may be the owner's holding company. Such a credit is counted in True, flagged `numbered_company_payer`, and never verified by a payer rule (§7.5, §7.6, §8.5, §8.6). The amended accounts-payable rule required this exclusion. Approximate size, measured with §5.2's widened pattern on the memo's rows: $11.4M (4.1% of corpus credits) in 293 rows. Whether it counts at all is OQ3.
- **T12. Government payers: Q6 overrides the recurrence gate.** The government verifier asked that a single public-rail credit stay unverified. The owner's Q6 ruling (a government payer is proof, with Treasury "MISC PAY" among its examples) supersedes that. Every veto the gate was meant to back up is kept and widened (§7.6). The residual is a one-off grant or refund printed without its purpose word.
- **T13. A transfer from a named third party belongs to the person-to-person family.** "Online transfer from <person or company>" is counted and flagged `p2p`, under the same holds: the round-sum repeat and the holder's name. A named transfer that prints an account designation (an account-type word or a masked account number, `ONLINE TRANSFER FROM SMITH J EVERYDAY CHECKING XXXXXX1234`) is held as `transfer_account_designation`: it reads as the owner's own account at another bank. Transfer wording with no counterparty is held (Q2). The memo held every named transfer. Measured on its rows: $1.2M of named transfers print a designation and stay held, and about $3.0M are counted.
- **T14. Insurers stay out of True but become reviewable.** A credit from a listed insurer that prints customer-payment wording (a DRP payment to a body shop, a vendor payment, an agent's commission) is held as `insurer_payer` rather than decided `non_revenue`. An unlisted payer whose name reads as an insurer (`… INSURANCE`, `… MUTUAL`, `… ASSURANCE`, `… CASUALTY`) is held as `insurer_named_payer` (§8.1; measured $1.1M, 527 rows). Neither ever counts (Q6), but an analyst can confirm either. The one insurer credit that may verify is the healthcare claim payment, `HCCLAIMPMT` (§7.7, T18).
- **T15. Property-management platforms verify by recurrence and carry a chip.** Buildium, AppFolio and Landlord Studio verify only by recurrence of their ACH payout shape, and their verified rows show a "Property-management collections" chip. This is the reviewer's recommended option (b), "verified plus a flag", pending the owner's word on rent collected by a manager. The evidence reviewer also offered admitting Buildium and Landlord Studio now and holding AppFolio, whose only holder in the data looks like a landlord paid owner distributions (OQ4).
- **T16. The auction rule is adopted as amended.** A credit from a dealer-only wholesale auction verifies without recurrence when it prints the auction's observed payout form (§7.8).
- **T17. Two classification versions.** 5.5 carries the fixes (§7) under today's definition, so the census can measure them alone. 5.6 carries the definition (§5, §8, §10). They ship on one branch, each with its own stage bump and census (§14, §16). The channel gate and the holder veto (§6.1 step 9b, §5.2) ship in 5.5, because they decide which rows the 5.5 rules may verify.
- **T18. Claim first for an insurer's healthcare claim payment (owner's word needed, OQ5).** A credit that prints the NACHA claim-payment entry `HCCLAIMPMT` skips the insurer registry, so a Blue plan paying a provider's claim verifies (§7.7). Both healthcare verifiers asked for an explicit owner ruling, and the evidence verifier expected a glued BCBSM row to stay `non_revenue`. The case for it: the entry names a claim paid to a provider, which is the provider's revenue, and Q6 names healthcare payers as proof. Measured: 177 BCBS rows, $908,159, in 16 statements move from `non_revenue` to `verified_revenue`; all 16 statements belong to the healthcare providers §7.7 lifts. **Until the owner answers, and if the owner declines,** an `HCCLAIMPMT` credit from an insurer-registry payer is held as `insurer_payer`, and so is every alias-escaping Blue-plan spelling (the glued rows of §7.7's fix, 376 rows, $424,597.31, 23 statements, and the spaced `BCBSF` and `Blue Cross Blue` rows that verify today, a declared demotion the census lists), so the insurer check and the descriptor never decide one payer both ways.
- **T19. Book transfers from a third party (owner's word needed, OQ6).** Chase's `BOOK TRANSFER CREDIT B O <originator>` from an originator that is not the holder leaves the own-account rule (§7.11), and Bank of America's `WIRE TYPE BOOK IN` is read as an incoming wire in §7.9 and §8.5, so the two banks agree. The wire verifier said to leave `WIRE TYPE BOOK IN` out until the owner rules. The case for it: a book transfer is a same-bank wire, and the originator is printed. Measured: 308 Chase rows, $6.25M, in 73 statements leave `non_revenue`; `WIRE TYPE BOOK IN` adds 1 row (an amount in the tens of thousands) to §7.9. Under 5.6 these rows then pass through Q5 and every hold of §8.1 (holder's name, non-sale purpose, counter-debit). **If the owner declines,** both stay as today: the Chase rows `non_revenue`, and `WIRE TYPE BOOK IN` never verifies (it is counted as `wire_named_sender` or held by §8.1).

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
- **Template prefixes:** the bank's words printed before the payer, removed before the payer is read: `_PAYEE_TEMPLATE_PREFIX`, plus `BUSINESS TO BUSINESS ACH CREDIT`, `CCD DEPOSIT`, `CTX DEPOSIT`, `ELECTRONIC DEPOSIT FROM`, `ELECTRONIC DEPOSIT`, `ELECTRONIC CREDIT`, `ACH DEPOSIT`, `ACH CREDIT`, `ACH CORP CREDIT`, `DEPOSIT FROM`, `PREAUTHORIZED CREDIT`, `EFT CREDIT`, `DIRECT DEPOSIT`, `MISC PAYMENT`, `BILL PAYMENT`.
- **Payer region** depends on the channel. It is read before any token is filtered, so a numbered company's leading digits and a legal word are kept:
  - an ACH or EFT row: `_payee_region` of the row before its receiver fields, after the template prefixes are removed (§7.6's `payer_name`), ending at the first token that holds a digit once a name word has started, as `_originator_segment` ends it. Unlike `_originator_segment`, it keeps a leading digit token, so `7654321 NEW BRUNSWICK INC DES:PAYMENT` has the payer region `7654321 NEW BRUNSWICK INC`. In a layout with no entry label (Wells Fargo's `FABRIKAM INC DIR DEP 240115 …`), the entry words sit inside this region and are read with it;
  - a wire: the originator segment after `B O`, `ORG`, `ORIG` (not `ORIG CO NAME`, not `ORIG ID`), `ORIGINATOR`, `WIRE FROM`, `WIRE IN FROM`, `FUNDS TRANSFER CREDIT TT` or `INBD FUNDS TRANSFER RECEIVED`, cut before `BNF`, `BENEFICIARY`, `BBI`, `OBI`, `REF`, `SRF`, `TRN`, `RFB`, `IMAD`, `ACCT`, `SND BK` or the row end. D11 names a wire by its beneficiary, which on a credit is the holder, so a wire's payer is never read that way;
  - a person-to-person or transfer row: the sender after `FROM`, cut before `ON`, `REF`, `CONF`, `MEMO`, `TRN`, `ID` or a sending bank's name; Venmo and Cash App cash-outs have no sender;
  - a check, cash, branch, ATM or bare-deposit row (§8.2, §8.3): none. These channels print no payer.
- **Payer name:** the payer region's words with the tokens that hold a digit and the single letters removed. `_unknown_payee_tokens` (D11, at most four words) is never the payer name: it drops leading financing words and digit tokens (`CAPITAL ONE …` becomes `ONE`, `TREAS 310` becomes `TREAS`).
- **Payer key:** the payer name's words minus `GENERIC_WORDS` (below), keeping at most the first four.
- **Entry fields:** the words the payer prints about the payment, as against its name:
  - Bank of America: the `DES` field, up to `ID`, `INDN`, `CO ID`, `IND NAME`, `IND ID` or an SEC code;
  - Chase and its layout: the `CO ENTRY DESCR` field, up to `SEC`, `TRACE`, `EED`, `IND ID`, `IND NAME`, `TRN` or an SEC code;
  - a wire: `OBI`, `RMR`, `PMT DET`, `RFB` text and the purpose text after `REF`, up to the next wire field;
  - a person-to-person or transfer row: `MEMO`, `NOTE`, `FOR`, `PMT INFO` or `PAYMENT INFO`, up to `CONF`, `REF`, `TRN` or `ID`;
  - any other layout: the words inside the payer region after the payer's name (see the payer region).
- **Channel family:** one of `wire` (§8.5), `ach_eft` (an electronic-payment form, below), `person_to_person` (a rail of §8.4, or transfer wording with a named counterparty), `check` (§8.3), `cash_branch_atm` (§8.2) and `other`. Two credits have one payer when they share the channel family and their payer keys are equal.
- **`GENERIC_WORDS`** (from the memo's `categorize.py`, inlined here because that file is private): `DEPOSIT`, `DEPOSITS`, `CREDIT`, `CREDITS`, `TRNSFR`, `TRANSFER`, `OTHER`, `REAL`, `TIME`, `INCOMING`, `RECEIVED`, `ACH`, `ELECTRONIC`, `DIRECT`, `MEMO`, `MISC`, `BILL`, `FILE`, `INTERNET`, `BANKING`, `EXTERNAL`, `RECD`, `CR`, `DEP`, `ONLINE`, `MOBILE`, `INSTANT`, `FUNDS`, `ADJUSTMENT`, `ADJ`, `MONEY`, `VISA`, `CORPORATE`, `PREAUTHORIZED`, `SEQ`, `IN`, `NEW`, `ITEM`, `ITEMS`, `MSP`, `DIV`, `DP`, `FD`, `BR`, `BRANCH`, `RECEIPT`, `RECEIVE`, `PAYMENT`, `DOMESTIC`, `TRANS`, `CUSTOMER`, `DDA`, `SAV`, `SAVINGS`, `CHECKING`, `CHK`, `ACCOUNT`, `ACCT`, `FR`, `FROM`, `WIRE`, `REF`, `TRN`, `TYPE`, `DATE`, `ET`, `USD`, `TRF`, `WT`, `FED`, `NUMBER`, `NO`, `NOTPROVIDED`, `INTERNATIONAL`, `FX`, `CAD`, `SWIFT`, `IMAD`, `OMAD`, `SRF`, `RFB`, `OBI`, `PM`, `AM`, `ON`, `AT`, `VIA`, `CARD`, `ID`, `CONF`, `CONFIRMATION`, `TRACE`, `SENT`, `RCVD`, `PMNT`, `PMT`, `AUTHORIZED`, `SEQUENCE`.
- **`HOLDER_NOISE`** (from the same file): `BUSINESS`, `CHECKING`, `ACCOUNT`, `LLC`, `INC`, `CORP`, `COMPANY`, `THE`, `OF`, `AND`, `SAVINGS`, `PLATINUM`, `COMPLETE`, `ANALYZED`, `COMMERCIAL`, `ADVANTAGE`, `FUNDAMENTALS`, `SIMPLE`, `BASIC`, `PREFERRED`, `INTEREST`, `OPERATING`, `PERFORMANCE`, `SELECT`, `ESSENTIALS`, `CHECK`, `TOTAL`, `PREMIUM`, `SMALL`, `STANDARD`, `FREE`, `DBA`, `USD`, `CAD`, `ACCT`, `PLUS`, `ELITE`, `EVERYDAY`, `BANKING`, `DEPOSIT`, `MONEY`, `MARKET`, `ONTARIO`, `CANADA`, `ALBERTA`, `QUEBEC`, `BRITISH`, `COLUMBIA`, `SASKATCHEWAN`, `MANITOBA`, `NOVA`, `SCOTIA`, `LTD`, `LIMITED`, `CORPORATION`, `INCORPORATED`, `LLP`, `PLLC`, `GROUP`, `HOLDINGS`, `SERVICES`, `ENTERPRISES`, `USA`, `AMERICA`, `AMERICAN`, `NATIONAL`, `INTERNATIONAL`, `TRUST`, `SOLUTIONS`, `MANAGEMENT`, `CO`, `LP`. This spec adds the bank-template and product words `COMPTE`, `DIVERS`, `BANK`, `BANQUE`, `CAISSE`, `ENTREPRISE`, `AFFAIRES`, `OPERATIONS`, `CU` and `FCU`, the remaining province and territory names, and every word of `GENERIC_WORDS`.
- **Holder words:** the statement's `account_name`, normalized, minus `HOLDER_NOISE`, minus tokens that hold a digit and tokens of two letters or fewer. `account_name` is often only a product name. When nothing is left, only the digit test can fire.
- **Holder's first distinctive word:** the first holder word of four or more letters that is not one of the common name-starters `FIRST`, `NORTH`, `SOUTH`, `EAST`, `WEST`, `CENTRAL`, `UNITED`, `GLOBAL`, `PREMIER`, `ROYAL`, `GOLDEN`, `GREAT`, `CITY`, `STATE`, `COUNTY`. A payer's first distinctive word is read the same way on its payer name, skipping `GENERIC_WORDS`.
- **Holder's name (the holder test).** It is read on the payer region, and only on a row that has one (never on a check, cash, branch, ATM or bare-deposit row). It matches when any of these holds:
  - the payer's first distinctive word equals the holder's first distinctive word (the brand-word affiliate: `CONTOSO HOLDINGS LLC` paying `CONTOSO BAKERY LLC`);
  - the payer name holds at least min(2, number of holder words) holder words;
  - the payer region holds a run of four or more digits that `account_name` also prints (a numbered company's number).
  An affiliate or a supplier that shares the holder's brand word is held too; that is the safe direction. The test is a **veto** in every rule that verifies on the payer's identity or remittance: step 11's customer and invoice descriptors, steps 12 to 14 (§6.1), Q5 and Q6. A row it vetoes is `unverified_deposit` (method `holder_named_payer`) under 5.5, and is held as `holder_name` under 5.6. It is not applied to the operating registry (step 10, the recurrence pass) or to the card-settlement and claim-payment forms, whose payer is the platform, the processor or the insurer, and whose rows print the merchant's own name as the payout's recipient (BMO's `DIRECT DEPOSIT DOORDASH <store> MSP/DIV`).
- **Company form:** a legal-form word after the payer name's first word (`LLC`, `L L C`, `INC`, `INCORPORATED`, `CORP`, `CORPORATION`, `COMPANY`, `LTD`, `LIMITED`, `LP`, `LLP`, `LLLP`, `PLLC`, `ULC`, `PLC`, `GMBH`, `AG`, `SA`, `SAS`, `SRL`, `BV`, `NV`, `PTY`, `DOO`, `DMCC`, `SA DE CV`), or an institution word (`FOUNDATION`, `CHURCH`, `MINISTRIES`, `UNIVERSITY`, `COLLEGE`, `SCHOOL`, `ACADEMY`, `HOSPITAL`, `ASSOCIATION`, `SOCIETY`, `COOPERATIVE`, `CO OP`). `CO` is never a company form: since 5.3 it is also Colorado's state code (D11). `TRUST` is never one either: a family trust is owner money. This is narrower than the memo's `LEGAL` list, which also took words such as `SERVICES`, `TRANSPORT` and `CAPITAL`.
- **Electronic-payment form:** the row prints an ACH or EFT mark: `ORIG CO NAME`, `CO ENTRY DESCR`, `DES`, `CCD`, `CTX`, `PPD`, `IAT`, `ACH`, `EFT`, `ELECTRONIC DEPOSIT`, `ELECTRONIC CREDIT`, `ELECTRONIC PMT`, `ELECTRONIC PAYMENT`, `DIRECT DEPOSIT`, `MISC PAYMENT`, `CORPORATE ACH`, `BILL PAYMENT`, `EDI`, `INDN`, `PREAUTHORIZED CREDIT`, `DEPOSIT FROM`, `PAID FROM`, `PAYMENT FROM`, `CREDIT FROM`, `MSP DIV` or `AP CC`.
- **Repeats:** two or more posted, non-duplicate credits in the same statement with the same payer. A credit counts toward the repeat when it is verified, or unverified and held by no hold of §8.1. A `non_revenue` credit, a direction conflict and a held credit never count, so `NORTHWIND SUPPLY DES:RETURN` cannot make `NORTHWIND SUPPLY DES:CREDIT` a repeat. Statement scope: one account's statement period. Nothing is counted across statements.
- **Round sum:** an amount of at least $100 that is a whole multiple of $100, compared in integer cents.
- **Numbered company** (the one guard §5.2, §7.5, §7.6, Q5 and Q6 all read). A credit's payer is a numbered company when either:
  - its row before the receiver fields begins with one of the template prefixes `DIRECT DEPOSIT`, `ACCOUNTS PAYABLE`, `ACCTS PAYABLE`, `ACCOUNTS PAYABLE PMT`, `MISC PAYMENT` or `BILL PAYMENT`, and the next token is six or more digits: `^(?:DIRECT DEPOSIT|ACC(?:OUN)?TS? PAYABLE(?: PMT)?|MISC PAYMENT|BILL PAYMENT) \d{6,}\b`. This is the accounts-payable verifier's guard. BMO cuts the name to the field width, so the digits alone decide (`DIRECT DEPOSIT 7654321 CANA AP CC`);
  - its payer region (which keeps a leading digit token) begins with six or more digits followed by a Canadian province or territory, `CANADA`, or a cut of one, or by at most four words and then a legal form: `^\d{6,}\b(?: (?:<province>)\b| (?:[A-Z]+ ){0,4}(?:INC|INCORPORATED|LTD|LIMITED|CORP|CORPORATION|ULC|LLC|LP|CO|COMPANY)\b)`.
  - `<province>` is every province and territory and `CANADA`, as the full name, the postal and common abbreviations, and any cut of three or more leading letters: `ONTARIO` (`ON`, `ONT`, `ONTA`…), `QUEBEC` (`QC`, `QUE`, `QUEB`…), `NOVA SCOTIA` (`NS`, `NOV`, `NOVA`…), `NEW BRUNSWICK` (`NB`, `NEW`…), `MANITOBA` (`MB`, `MAN`, `MANI`…), `BRITISH COLUMBIA` (`BC`, `B C`, `BRI`, `BRIT`…), `PRINCE EDWARD ISLAND` (`PE`, `PEI`, `PRI`, `PRIN`…), `SASKATCHEWAN` (`SK`, `SAS`, `SASK`…), `ALBERTA` (`AB`, `ALB`, `ALTA`…), `NEWFOUNDLAND AND LABRADOR` (`NL`, `NFLD`, `NEWF`…), `YUKON` (`YT`, `YUK`…), `NORTHWEST TERRITORIES` (`NT`, `NWT`, `NOR`, `NORT`…), `NUNAVUT` (`NU`, `NUN`…), `CANADA` (`CAN`, `CANA`…). The cut is a whole token, so `ONTA` matches and `ONTARIOS` does not.
  A bare `DIRECT DEPOSIT <digits>` is therefore a numbered company, counted and flagged `numbered_company_payer`, as it was counted before under `no_payer_printed`.
- **Government payer:** a payer region that matches the public-payer patterns of §7.6 anchored at its start (`^(?:\S+ ){0,3}(?:<payer>)`), and does not match the payer-name veto of §7.6. It is read on the payer region, never on D11's tokens, so `TREAS 310` keeps its digits.
- **Healthcare payer:** a payer region that matches `HEALTHCARE_PAYER_ALIASES` (§7.7), a new hand-kept table of Medicare contractors, state Medicaid programs, US health plans that are not in `INSURANCE_PROVIDER_ALIASES`, pharmacy-benefit managers and claim-payment platforms.
- **Financing root:** the credit-side root set of §8.1.

### 5.3 Tiers and reason codes

Every posted credit gets exactly one tier. `counted_flagged` and `excluded_pending_review` rows always carry a reason. The table groups the reasons by tier; §8.10 gives the order in which the tier pass tests them.

| Tier | Reason code | Label on screen | Source |
|---|---|---|---|
| `verified` | (none; the rule is `revenue_match_method`) | Verified revenue | §7, §8 |
| `excluded_pending_review` | `direction_conflict` | Direction conflicts with the amount | today's rule |
| `excluded_pending_review` | `insurer_payer` | Insurance carrier | T14 |
| `excluded_pending_review` | `insurer_named_payer` | Payer name reads as an insurer | T14, Q6 |
| `excluded_pending_review` | `possible_return` | Possible return or adjustment | T3, §7.11 |
| `excluded_pending_review` | `financing_named_payer` | Payer or entry suggests financing | T4 |
| `excluded_pending_review` | `payer_debited_as_lender` | Payer is also debited as a lender | §8.1 |
| `excluded_pending_review` | `holder_name` | From the holder's own name or brand | Q4, Q5, Q6 |
| `excluded_pending_review` | `payroll_or_salary` | Payroll, salary or employee reimbursement | Q8 |
| `excluded_pending_review` | `personal_income` | Benefit or pension | T3 |
| `excluded_pending_review` | `non_sale_purpose` | Not a sale: owner money, investment, grant, refund, claim or interest | T3, Q5, Q6 |
| `excluded_pending_review` | `payer_also_debited` | Payer also debited this account | §8.1 |
| `excluded_pending_review` | `wire_no_sender` | Wire, no sender printed | Q5 |
| `excluded_pending_review` | `transfer_no_counterparty` | Transfer, no counterparty | Q2 |
| `excluded_pending_review` | `transfer_account_designation` | Transfer naming an account | T13 |
| `excluded_pending_review` | `p2p_round_repeat` | Repeated round sums from one sender | Q4, T13 |
| `counted_flagged` | `wire_named_sender` | Wire from a named sender | Q5 |
| `counted_flagged` | `check_deposit` | Check deposit | Q3 |
| `counted_flagged` | `no_payer_printed` | No payer printed | Q2 |
| `counted_flagged` | `p2p` | Person-to-person | Q4, T13 |
| `counted_flagged` | `factoring_payout` | Factoring payout | owner 2026-09-26 |
| `counted_flagged` | `payout_credit_entity` | Platform payout (financing partner) | owner 2026-09-25 |
| `counted_flagged` | `platform_unconfirmed` | Platform payout, not confirmed | registry |
| `counted_flagged` | `numbered_company_payer` | Numbered company payer | T11 |
| `counted_flagged` | `named_payer_purpose_refused` | Named payer, purpose not accepted as proof | §8.6 |
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
   - REIMBURSEMENT no longer fires when the row prints a claim or provider signal (§7.11);
   - `DEBIT CARD CREDIT` and `POS CREDIT` no longer fire when the row prints a push-rail word, or names a `merchant_processor` or invoice-type source together with a payout word (§7.11). Such a released row reaches True only when a form or the registry verifies it; otherwise it is held as `possible_return`.
4. **New, Q7:** a dealer's funding from a listed auto lender: `verified_revenue` (§8.7). This is the only carve-out ahead of D1. It never fires on a row that names a lender outside vehicle financing, a potential lender or an insurer, or that prints a loan, proceeds, advance or refund word.
5. Insurer registry: `non_revenue`, with two **changes:**
   - a credit that prints the NACHA claim-payment entry skips this step (§7.7; T18, owner's word needed);
   - a credit that prints customer-payment wording (§8.1) becomes `unverified_deposit` with method `insurer_customer_payment`, which the tier pass holds as `insurer_payer` (T14).
6. D1 financing-proceeds payee: `non_revenue` (unchanged).
7. D1 by descriptor: `non_revenue`. **New:** Square Capital's `SQ CAP` spelling, and SBA and EIDL disbursements (§7.11).
8. Potential-lender registry: `non_revenue` (unchanged).
9. Strong non-revenue: `non_revenue`. **Changed:**
   - `BOOK TRANSFER` and `FUNDS TRANSFER` are own-account only when no third-party originator is printed (§7.11; the Chase book transfer is T19, owner's word needed);
   - the tax-refund abbreviations and account-verification micro-deposits join (§7.11);
   - a street `LN` is no longer read as LOAN (§7.11, in the normaliser).

   **9b. New, the channel gate** (Q2, Q3 and Q4 say "never Verified"). It decides which of the later steps may verify a row:
   - a row that prints a consumer person-to-person rail (`ZELLE`, `INTERAC`, `E TRANSFER`, `E TFR`, `VIREMENT`, `VFC`, `AUTODEPOSIT`, `VENMO`, `CASH APP`, `SQUARE CASH`, `APPLE CASH`, `POPMONEY`) is never verified by any step, the registry and the recurrence pass included;
   - a row that prints a check-deposit form (§8.3), a cash, branch or ATM form (§8.2), or no payer word at all (a bare deposit, credit or EFT) is never verified by any step;
   - a row that prints a real-time or push rail (`RTP`, `FEDNOW`, `REAL TIME TRANSFER`, `REAL TIME PAYMENT`, `INSTANT PMT`, `INSTANT PAYMENT`, `INSTANT TRANSFER`, `VISA DIRECT`, `VISA MONEY TRANSFER`, `MC SEND`, `MONEY TRANSFER`, `PMNT RCVD`, `PAYMENT RECEIVED`) is verified only by step 10 (the registry's payout form, its alias with context, or its recurrence) with the registry entity read as the sender. Steps 11 to 14, Q5 and Q6 never verify it.
   A gated row falls through to step 15 or 16, and the tier pass gives it its channel's tier. The gate is a declared verified → unverified move under 5.5: today's `CUSTOMER` descriptors verify `MOBILE DEPOSIT CUSTOMER PAYMENT`, a bare teller `CUSTOMER DEPOSIT` and `ZELLE … MEMO INVOICE PAYMENT`.
10. Operating registry: `verified_revenue` with context, a payout form or a card form; otherwise `unverified_deposit` / `operating_source_requires_context`. **Changed** (§7.1 to §7.4, §7.8, §7.10): payout forms, source-type rules, the pay, financing and reversal vetoes, P2P-rail refusal, 16-character truncations and the joined-field reading.
11. Verified descriptors: `verified_revenue`. **Changed:** the card settlement forms (§7.1); the narrowed HCCLAIMPMT glue (§7.7); `CUSTOMER` never read in `CUSTOMER ID` and never with CHECK or CHEQUE (§7.11); the customer and invoice descriptors (`CUSTOMER …`, `INVOICE PAYMENT`, `ACCOUNTS RECEIVABLE`) refuse a row the holder test matches (§5.2).
12. **New:** payer accounts-payable remittance (§7.5): `verified_revenue`.
13. **New:** public-payer remittance, arms A and B (§7.6): `verified_revenue`.
14. **New:** wire remittance purpose (§7.9): `verified_revenue`.
15. Deposit wording: `unverified_deposit` / `ambiguous_credit_descriptor` (unchanged). The tier is set by the pass in §8.
16. Everything else: `unverified_deposit` / `unidentified_posted_credit` (unchanged). The tier is set by the pass in §8.

Steps 12 to 14 sit after every non-revenue rule and the registry, so they can only replace the two fallbacks, 15 and 16. Steps 11 (customer and invoice descriptors) to 14 refuse a row the holder test (§5.2) or the numbered-company guard matches; a row the holder test refuses gets method `holder_named_payer`.

### 6.2 Statement passes, in order

1. Duplicate detection by printed running balance (unchanged).
2. Lender recurrence and D6 on debits (unchanged).
3. Labels for unnamed potential payees (unchanged).
4. Reversal pairs (unchanged logic; the credit markers of step 3 widen which pairs it finds).
5. Operating-source context. **Fixed** (§7.0): the veto pool, the pool that admits only registry rows, the pool that never shrinks, direction conflicts left out, the absolute micro-deposit floor, legal-form holder names read as business accounts, recurrence-only verification for property-management platforms, and the auction branch.
6. **New:** the accounts-payable counter-debit guard (§7.5). Its rows are held as `payer_also_debited` under 5.6.
7. **New (5.6):** the true-revenue pass (§8): payer facts for each row, then Q7's credit-union arm (§8.7), then the Q5 and Q6 verifications, then the tiers.
8. Duplicate finalisation (unchanged). A proven duplicate is `non_revenue` with tier `non_revenue`.

### 6.3 What may leave `non_revenue`, and what may never enter True

A row that a non-revenue rule decides stays `non_revenue`, except through exactly these seven named narrowings, each measured in the census (§14.2):
1. REIMBURSEMENT on a credit that prints a claim or provider signal (`MEDICAID`, `MEDICARE`, `MEDI CAL`, `TRICARE`, `CHAMPVA`, `GEMT`, `EMS`, `HCCLAIMPMT`, `PROV PAY`, `EDI PYMNTS`, `CLAIM PMT`);
2. HCCLAIMPMT from an insurer-registry payer: verified under claim first (T18, only on the owner's word), otherwise **held** as `insurer_payer`, so it stays out of True;
3. an insurer credit with customer-payment wording, which is **held**, so it still stays out of True;
4. `BOOK TRANSFER` (T19, only on the owner's word) and `FUNDS TRANSFER` with a third-party originator;
5. a street `LN`;
6. a card-credit row that prints a push-rail word, or names a `merchant_processor` or invoice-type source with a payout word; it enters True only when a form or the registry verifies it, and is otherwise **held** as `possible_return`;
7. Q7 dealer funding from a listed auto lender (from D1).

Nothing else leaves `non_revenue`. In particular, no financing-group credit other than Q7's dealer funding, no own-account transfer with an own-account designation, no refund or reversal marker and no duplicate. §14.3 lists the guard checks.

## 7. The bug fixes (classification 5.5)

These fixes change no definition. Under 5.5 they change which credits are verified. They move rows into or out of `non_revenue` only where §6.3 and §7.11 name the move, and they demote verified rows only where §7.0 and §7.11 declare it (the channel gate of §6.1 step 9b and the holder veto of §5.2 among them). Each family below is the proposed fix **as amended by both of its verifiers' required changes**. "Measured" figures are the verifiers' corrected corpus figures.

### 7.0 Shared mechanics

- **Revenue text.** Every credit revenue rule reads `revenue_text(text)`: the normalized row with Chase's glued `Sec` split. `(\bCO (?:ENTRY )?DESCR (?:\S+ ){0,2}?\S{2,}?)SEC (CCD|CTX|PPD|WEB|IAT|COR|TEL|POP|BOC|ARC|RCK|CIE)\b` becomes `\1 SEC \2`. It is bounded to the entry-description field, so a word elsewhere that ends in SEC is untouched. `normalized_description`, D11's payee keys and every debit rule keep today's text. The healthcare family's "cross-family normalizer split" is deliberately not done: it would move lender matching. Measured: 2,907 glued Chase rows, $15.5M, in 207 statements, $2.15M of them HCCLAIMPMT.
- **Joined fields.** Bank of America prints `NAME DES:ENTRY` and Chase prints `ORIG CO NAME … CO ENTRY DESCR …`, so a phrase that needs the name and the entry side by side never matches. The card forms, the verified descriptors and the operating-context patterns are also read on a joined text: `<originator> <entry>`, with ` DES `, and `ORIG ID <id> DESC DATE [<date>] CO ENTRY DESCR`, removed between them. The registry validator warns when a multi-word operating alias spans the name/entry boundary.
- **Glued date prefix.** A leading `01/02Bankcard Deposit` normalizes to `01 02BANKCARD DEPOSIT`. Every card form uses `(?<![A-Z])` as its left boundary, never `\b`, so a digit glued on the left does not block it.
- **16-character truncations.** For every operating alias longer than 16 characters, the registry build adds its first 16 characters as an alias (for example `FIRST DATA MERCH`, `QUICKBOOKS PAYME`, `AMAZON MARKETPLA`). This applies when the cut keeps at least two words, its last word has three or more characters, and it collides with no other registry or ledger alias (the validator refuses a collision). `BY STRI` and `BY STRIPE` after a platform name read as Stripe (Stripe Connect's `<platform> - By Stri`).
- **The recurrence pass** (`_apply_operating_source_context`), fixed for every operating source, old and new:
  - The pool admits only a credit whose single-row decision came from the operating registry (`operating_source_requires_context`) or that an operating-source method verified (`operating_source_with_credit_context`, `recurring_operating_source`, `operating_source_related_activity`, a payout or card form). A row another rule decided, or one the channel gate (§6.1 step 9b) closed to verification, never joins it.
  - The pool counts an entity's credits already verified by an operating-source method toward its recurrence total, and it upgrades only the unverified ones. A per-row upgrade must never shrink the pool. Measured: the family fix without this lost 20 rows ($100,388), of which $16,029 was genuine Stripe, Square and Helcim payouts.
  - Veto pool: a credit never counts toward recurrence, and is never lifted by it, when:
    - its transaction classification is `payroll`;
    - `_row_before_receiver` matches `\b(?:LOANS?|CAPITAL|CAP\d*(?:SEC)?|CAPI|CAPIT|CAPITA|FIN|ADVANCE|ADV|FINANC\w*|LEND\w*|MCA|CASH ADV\w*|PAYROLL\w*|PAYRLL|PAYROL|PAYRL|DIR ?DEP|DIRDEP|DIRECT DEP|SALARY|SALARIES|REG SAL|WAGES?|NET ?PAY|BONUS|REIMB\w*|ACCT ?VERIFY|ACCTVERIFY\w*|VERIFY|VERIFICATION|INSUR\w*)\b`, or the card-credit labels `\bDEBIT CARD CREDIT\b` and `\bPOS CREDIT\b` (a card refund released from the reversal rule is never pooled, §7.11);
    - it is below $1 (the absolute micro-deposit floor);
    - its revenue method is `direction_conflict`.
    `FUNDING` stays out of the veto: TapGoods, Braintree and Buildium print it on real settlements. The veto reads the row before its receiver fields, so a holder named `… PAYROLL SERVICES LLC` never demotes its own settlements.
  - Declared demotions of rows verified today:
    - Square Capital's `SQ CAP####` credits, which now become financing proceeds (§7.11);
    - Square payroll credits (measured: 7 rows, $2,808.60, one statement falls to 0% verified);
    - `ACCTVERIFY` micro-deposits;
    - rows the channel gate closes (§6.1 step 9b) and rows the holder test vetoes (§5.2), in step 11's customer descriptors;
    - `CUSTOMER ID` rows (§7.11);
    - with the T18 switch off, the spaced Blue-plan `HCCLAIMPMT` rows that escape the insurer aliases (§7.7).
    All are false revenue today, proof the owner's rulings no longer accept, or rows held until the owner rules. The owner's approval of this spec is the sign-off both verifiers asked for.
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

**Ledger before aliases.** A new processor's bare alias is added only after its own advance product is admitted through the lender ledger as an alternative position, or after the ledger records that it has none:
- Shift4 Capital (`SHIFT4 CAPITAL`, `SHIFT4 CAP`) before `SHIFT4`;
- SumUp's cash advance before `SUMUP`;
- Jobber Capital (paid through Parafin and Stripe) before `JOBBER BY STRI(PE)`;
- Clearent's, SmartTab's and Braintree's capital products, if any, before `CLEARENT`, `SMARTTAB` and `BRAINTREE` (card evidence verifier R3: a processor's `<name> CAPITAL` credit must never reach the recurrence pool as a settlement).
Admission follows the ledger's process: a public source and an independent second agent. If the ledger can neither admit the product nor record that there is none, that processor's bare alias is not added. The recurrence veto (§7.0) catches `CAPITAL`, `CAP` and `ADV` either way.

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

Ledger items from the delivery risk verifier (R10), carried by S1 through the ledger's process: Parafin, the capital provider behind several platforms' merchant advances, and Pipe, including its 16-character cut `PIPE TECHNOLOGIE`, are proposed for the financing registry. Until they are admitted, their names carry no financing root that T4 reads (`PARAFIN`, `PIPE`), so a platform advance paid through them is counted: the residual is recorded in §15.

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

Free-text gate: a person-to-person row never verifies here; the channel gate (§6.1 step 9b) closes every consumer rail, whatever the sender prints (Q4). On a `PAYPAL` row and on a wire from a person, the invoice, bill and "for invoices" forms count only when the sender prints a company form. A person's Zelle memo "paying bills" or "Invoice 1234" never verifies.

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
- **Numbered companies (T11):** the rule never verifies a payer that §5.2's numbered-company guard matches: after a template prefix, six or more digits alone (`DIRECT DEPOSIT 7654321 CANA AP CC`); with no prefix, six or more digits and then a province, territory or its cut, or words up to a legal form (`1234567 NOVA SCOTIA LTD DES:VENDOR PAY`).
- **The holder (G3):** the rule never verifies a row the holder test matches (§5.2): `CONTOSO BAKERY LLC DES:VENDOR PAY` into Contoso Bakery's own account stays unverified, and is held as `holder_name` under 5.6.
- **Counter-debit guard (statement pass 6):** a credit decided `payer_remittance_descriptor` goes back to `unverified_deposit` (method `payer_remittance_with_counter_debit`) when a posted debit in the same statement shares the payer's first distinctive word. A distinctive word has four or more letters and is not an AP word, a bank template word, a legal suffix, a word of `GENERIC_WORDS` or a public-payer word of §7.6 (`STATE`, `COUNTY`, `CITY`, `TOWN`, `DEPT`, `DEPARTMENT`, `TREAS`, `GOVERNMENT`). Under 5.6 the row is held as `payer_also_debited` (review required), as the verifier's R2 asked. Measured cost: 19 rows, $242K.

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
  - tax, refunds and benefits: `\bTAX(?:ES)?\b`, `\bTAXRFD\b`, `\bTAX ?REF(?:UND)?S?\b`, `\bREFUNDS?\b`, `\bRFD\b`, `\bSTUREFUND\b`, `\bR(?:E)?F(?:U)?ND\b`, a refund glued on the left (`[A-Z]*REFUNDS?\b`, `[A-Z]*RFND\b`: Maryland's `MDREFUND`), `\bEIC\b`, `\b(?:XX)?SOC SEC\b`, `\bSUPP SEC\b`, `\bSSI\b`, `\b(?:XX)?VA BEN\w*\b`, `\bBENEF\w*\b`, `\bBEN\b`;
  - pay and pensions: `\bFED SAL\b`, `\bSALARY\b`, `\bPAYROLL\b`, `\bWAGES?\b`, `\bSTIPENDS?\b`, `\bPER DIEM\b`, `\bRETIRE\w*\b`, `\bPENSION\b`, `\bANNUIT\w*\b`;
  - relief, grants and loans: `\bUNEMPLOY\w*\b`, `\bUI\b`, `\bSTIMULUS\b`, `\bGRANTS?\b`, `\bRELIEF\b`, `\bDISASTER\b`, `\bCARES\b`, `\bPPP\b`, `\bSBAD?\b`, `\bEIDL\b`, `\bEIDG\b`, `\bLOANS?\b`, `\bADVANCES?\b`, `\bADV\b`, `\bFORGIV\w*\b`;
  - family and court: `\bCHI?LD ?SUPP\w*\b`, `\bCHILD ?CTC\b`, `\bCTC\b`, `\bJURY\b`, `\bRESTITUTION\b`, `\bFOSTER\b`, `\bADOPT\w*\b`, `\bKINSHIP\b`, `\bWORK(?:ERS)? ?COMP\b`;
  - claims, awards and recoveries: `\bCLAIMS?\b`, `\bAWARDS?\b`, `\bSUBSID\w*\b`, `\bDISB\w*\b`, `\bPROCEEDS\b`, `\bUNCLAIMED\b`, `\bOVERPA\w*\b`, `\bOVERP(?:Y)?MT\b`, `\bREBATES?\b`, `\bREIMB\w*\b`, `\bBONDS?\b`, `\bESCROW\b`, `\bRETURN(?:ED)?\b`, `\bSTABILI[SZ]\w*`, `\bOFFSET\b`, `\bRECOVERY\b`, `\bARPA\b`, `\bRESCUE\b`, `\bERT?C\b`, `\bINCENTIVES?\b`, `\bTUITION\b`;
  - person-to-person: `\b(?:ZELLE|VENMO|CASH ?APP|E ?TRANSFER|INTERAC)\b`;
  - financing and leases: `\b(?:FUNDING|FUNDER|LENDING|LENDER|FINANC\w*|CAPITAL|CREDIT UNION|FCU|MORTGAGE|LEASE|LEASING|FACTOR\w*)\b`.
  - assistance: `\bASSISTANCE\b`, read only after the boilerplate is deleted (the risk verifier's R2). The evidence verifier's objection was that the boilerplate prints the word; deleting the boilerplate first answers it, and a public payer's "assistance" payment is a program payment, not a sale.
  - Arms A and B also veto `\bSETTLEMENT\b`, and arm B vetoes `\b(?:TRANSFER|XFER|TFR)\b`.
- **Numbered companies and the holder:** arm B never verifies a payer region that §5.2's numbered-company guard or holder test matches.
- **No recurrence gate** (T12). A single public-rail credit verifies.
- **Under 5.6, a public payer's non-sale credit is held.** A credit whose payer region matches a payer pattern above or the payer-name veto, and whose row prints a whole-row veto word (the list above without the person-to-person and financing groups, which other holds cover), is held as `non_sale_purpose` (§8.1). `COMPTROLLER OF MD DES:MDREFUND`, `IRS TREAS 310 DES:TAX EIC` and `STATE OF OHIO DES:GRANT` are held, not counted. Measured on the memo's rows: $0.16M, 407 rows, 39 statements.

A rule-verified row is reviewable (T6), which settles the verifier's "no undo" note. The residual is recorded: Chase can leave the Treasury agency prefix blank, so on arm A's MISC PAY branch, RMR IV is the only real guard.

Measured: 131 rows, $3,870,472.30, in 20 distinct statements. Tryout host: 3 rows, $629,249.40, in 2 statements (dump only). $0-verified statements 1,819 → 1,804. Verified 7.17% → 8.57% on this family alone.

### 7.7 Healthcare payers (family 6)

- The verified pattern becomes `(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b`. Its unbounded branch takes only the full NACHA token, so `THECLAIMPMT` and `CHECLAIMPMT` stay unmatched.
- **Claim first (the insurer-vs-claim order; T18, only on the owner's word).** On credits, a row whose revenue text matches that pattern skips the insurer registry (§6.1 step 5). Inside `_classify_credit_revenue`, the financing, potential-lender and insurer lookups read the text with a space inserted before a glued `HCCLAIMPMT` (a lookbehind on `[A-Z0-9]`), so a 16-character funder name glued to the token is still found. D1, descriptor proceeds, the potential registry, strong non-revenue and reversals still win. The rule is entry-based, so every Blue-plan spelling (`BCBS`, `BCBSM`, `BLUE CROSS BLUE`, Blue Care Network, Anthem Blue Cross, CareFirst) is treated alike. That settles the in-statement split the verifier found.
  - Measured: 177 BCBS rows, $908,159, in 16 statements move from `non_revenue` to `verified_revenue`. 376 alias-escaping Blue rows ($424,597.31, 23 statements) are already in the glue fix.
  - S2 builds claim first behind one switch, `HCCLAIMPMT_CLAIM_FIRST`, whose value is the owner's answer to OQ5. Off, an `HCCLAIMPMT` credit from an insurer-registry payer or a Blue-plan spelling above is held as `insurer_payer` (5.6) and stays unverified (5.5), and the evidence verifier's expectation holds: the glued BCBSM row is not verified. Off also demotes the spaced `BCBSF` and `Blue Cross Blue` claim rows that verify today; that demotion is declared, and the census lists it.
- **`HEALTHCARE_PAYER_ALIASES`** (registry, new): Medicare contractors (Noridian, Palmetto GBA, Novitas, WPS, NGS, CGS, First Coast), state Medicaid programs and Medi-Cal, TRICARE and VA Community Care (`VA CCN`), US health plans that are not in the insurer table (Aetna, Cigna, Humana, UnitedHealthcare, `UHC`, Optum, Molina, WellCare, Centene, Anthem), pharmacy-benefit managers (Express Scripts, Caremark, OptumRx), and claim-payment platforms (Zelis, ECHO Health, InstaMed, VPay, PaySpan).
  - It is read on the payer region, on a row with an electronic-payment form. It is used by Q6 (§8.6).
  - A healthcare payer's credit that prints `\bREIMB\w*`, `\bMEMBER\b`, `\bMBR\b`, `\bSUBSCRIBER\b` or `\bPREMIUM\b` is a member's reimbursement or a premium refund, not a claim paid to a provider: Q6 never verifies it, and it is held as `non_sale_purpose` (§8.1).
  - Canadian benefit carriers (Sun Life, Manulife, Canada Life, Equitable Life, Great-West, Desjardins Insurance, Alberta Blue Cross), RBC's `HEALTH DENTAL CLAIM <carrier>` label (normally a member's reimbursement), NEMT brokers, `CLMEFT`, and a bare X12 `TRN*1*` with no entry description are **out**: they are counted and flagged. They also print broker commissions, member reimbursements or non-claim payments.
- Tests lock today's spaced Chase `Hcclaimpmt Sec:CCD` row. The glued Chase, Huntington `<16-char name>HCCLAIMPMT` and digit-prefixed forms verify. `<name>HCLAIMPMT`, `HCCLAIMPMT0001`, `Hhspaymentsec`, `ASSURANCE OF THECLAIMPMT 123456789 CLAIM 123` and Chase's `CO Entry Descr:Theclaimpmt` stay unverified. A BCBSM glued row verifies with the claim-first switch on, and is held as `insurer_payer` with it off; both are tested. A registered funder's glued row stays `non_revenue` / `financing_proceeds_credit`. An HCCLAIMPMT row with `Merchant Cash Advance` or `Loan Proceeds` stays `non_revenue` / `strong_non_revenue_rule`.

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
- The residual is recorded: an arbitration refund in a later statement, or a partial refund, prints like seller proceeds. The auction risk verifier (R9) found one likely case in the corpus: a small credit whose equal Manheim debit sits in the same account's previous statement. Pairing an auction credit with an equal same-auction debit in the applicant's previous statement would need a package-level pass; it is put to the owner (OQ4) and not built here.

Measured: 138 rows, $282,944.45 (+1.42% of corpus verified). 11 statements leave 0%. Non-revenue unchanged.

### 7.9 Wires that cite an invoice or PO (family 8)

A verified rule, `wire_remittance_purpose`, at step 14.
- **N1, channel.** The normalized row must **begin** with an incoming-wire label: `^(?:WIRE TYPE (?:WIRE|INTL|FX) IN\b|USD WIRE IN\b|[A-Z]{3} WIRE IN\b|FEDWIRE CREDIT\b|CHIPS CREDIT\b|WT FED|WIRE TSF\b|WIRE TRANSFER (?:DEPOSIT|CREDIT|IN|INCOMING|FROM)\b|INCOMING WIRE\b|WIRE IN\b|WIRE FROM\b|(?:DOMESTIC|INTL|INTERNATIONAL|FOREIGN) (?:INCOMING )?WIRE\b|INCOMING FUNDS TRANSFER\b|FUNDS TRANSFER CREDIT TT\b|INBD FUNDS TRANSFER\b|FUNDS TRANSFER WIRE FROM\b)`, or be a Chase `BOOK TRANSFER CREDIT B O` whose originator is not the holder (§7.11). Bank of America's `WIRE TYPE BOOK IN` is read the same way as Chase's book transfer, so the two banks agree. Both book-transfer forms enter only with the owner's yes to T19 (OQ6); until then the wire verifier's N2 stands and they are left out.
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
- The recurrence pass counts recurrence only: three or more credits, or two in a business-named account. It uses no related fee debit. It pools only the platform's ACH payout shape (a row with an electronic-payment form, §5.2), never a push or real-time shape (`VISA DIRECT`, `PMNT RCVD`, `PAYMENT RECEIVED`, `RTP`), so one Visa Direct row plus one PMNT RCVD row never verify each other (property evidence verifier R4). A push-shaped platform row stays `operating_source_requires_context`.
- A guard runs only when one of the three matched. A row printing `\bOWNERS? ?(?:DIST\w*|DISB\w*|DRAWS?\w*|CONT\w*)`, `\bDISTRIBUT\w*`, `\bSEC(?:URITY)? ?DEP\w*`, `\bDEP(?:OSIT)? ?(?:RETURN\w*|RTN\w*|RT\w*|REFUND\w*)`, `\bSD ?(?:RETURN\w*|RTN\w*|RT\w*|REFUND\w*)`, `\bADVANCE\w*` or `\bORIG CO NAME\b.*\bORIG CO NAME\b` stays unverified (`property_platform_owner_or_deposit_wording`) and is left out of the count.
- Micro-deposits never count: `\bACCT ?VERIFY\w*`, `\bMICRO ?(?:DEP\w*|ENTRY)\b`, `\bPENNY TEST\b`, `\bTRIAL (?:DEP\w*|CREDIT)\b`, or under $1.
- A verified row carries the context signal `property_management_collections`, shown as a chip (§10.6).

Measured: 78 rows, $263,112.59, in 8 statement-months of 3 bank accounts; 0 tryout-host rows. The AppFolio rows are payouts to a landlord (owner distribution or rent), not vendor payments.

### 7.11 Wrong non-revenue, and newly named non-revenue

Narrowings of non-revenue rules (§6.3):
- **REIMBURSEMENT.** `\bREIMBURSEMENT\b` in `_REVERSAL_CANCELLATION_CREDIT_PATTERNS` does not fire only when the row prints a claim or provider signal: `MEDICAID`, `MEDICARE`, `MEDI CAL`, `TRICARE`, `CHAMPVA`, `GEMT`, `EMS`, `HCCLAIMPMT` (§7.7's pattern), `PROV PAY` (§7.6's provider-pay pattern), `EDI PYMNTS` or `CLAIM PMT`. A healthcare or government payer's name alone is not enough: `UNITEDHEALTHCARE DES:REIMBURSEMENT` (a member's reimbursement) and `STATE OF TEXAS DES:TRAVEL REIMBURSEMENT` (an employee's travel) stay `non_revenue`. An employer's `EXPENSE REIMBURSEMENT` stays `non_revenue`. The abbreviated `EXP REIMB` does not match the whole word, so it is not `non_revenue` today; under 5.6 it is held as `payroll_or_salary` (§8.1).
- **Street `LN`** (`analysis/description_text.py:24`). `\bLN\b` is rewritten to `LOAN` except when it ends a street address: a token of digits followed by one to three alphabetic tokens, then `LN`. The guard never applies when a loan-product word sits among those tokens (`COMMERCIAL`, `COMM`, `AUTO`, `BUSINESS`, `BUS`, `TERM`, `PERSONAL`, `MORTGAGE`, `MTG`, `EQUIPMENT`, `EQUIP`, `INSTALLMENT`, `INSTL`, `CONSUMER`, `HOME`, `HELOC`, `STUDENT`, `VEHICLE`, `SBA`, `BRIDGE`, `CONSTRUCTION`, `LINE`), or when `LN` is followed by `PMT`, `PYMT`, `PAYMENT`, `DISB`, `DISBURSEMENT`, `ADV`, `ADVANCE`, `PROCEEDS` or `DRAW`, so `1234 COMMERCIAL LN PMT` and `000123 AUTO LN DISB` still read LOAN. The same guard applies to printed Wells Fargo and Chase ATM and branch locations. This is the only normaliser change. It moves `normalized_description` for such rows, debits and credits, so G7 (§14.3) must show no lender or flag moved on debits, and G7b must list every credit whose revenue decision it moved. Measured: 8 or 9 rows, $19K to $32K, including one $105K wire.
- **Book and funds transfers.** In `_INTERNAL_TRANSFER_CREDIT_PATTERNS`:
  - `BOOK TRANSFER` and `FUNDS TRANSFER` stay own-account only when no third-party originator is printed (`B O`, `CUSTOMER`, `ORIGINATOR`, `ORG`, `TT <payer>`, `FROM <payer>`, `WIRE FROM`), or when that originator matches the holder's name (§5.2's holder test). The `BOOK TRANSFER` half ships only with the owner's yes to T19 (OQ6); the `FUNDS TRANSFER` half is this spec's decision.
  - `INCOMING FUNDS TRANSFER`, `FUNDS TRANSFER CREDIT TT`, `INBD FUNDS TRANSFER` and `FUNDS TRANSFER WIRE FROM` are incoming-wire labels. `ELECTRONIC FUNDS TRANSFER DEPOSIT` is an EFT channel, so the registry reads the processor that follows.
  - `prints_internal_transfer_designation` reads the same tuple, so R-d's package pairing narrows with it. A book transfer from a third party designates no own account, which is R-d's own test.
  - Chase's Paymentech settlements delivered as a book transfer (`B O CUSTOMER PAYMENTECH LLC … DEPOSIT ID`) then reach the registry.
  - Measured: 308 rows, $6.25M, in 73 statements (book transfers); 119 rows, $2.27M, in 26 statements (funds-transfer wires).
- **Push payouts printed as card credits.** `DEBIT CARD CREDIT` and `POS CREDIT` do not fire when the row prints a push-rail word (`VISA DIRECT`, `MC SEND`, `VISA MONEY TRANSFER`, `FASTPAY`, `INSTANT PAY`, `INSTANT PAYOUT`), or names a `merchant_processor` or `invoice_and_receivables` source that also prints a payout word (`\b(?:PAYOUTS?|INSTANT (?:PAYOUT|PAY|TRANSFER)|SETTLEMENT|DEPOSIT)\b`). Naming any other maintained source is not enough: Uber, DoorDash, PayPal, Instacart, Toast, Etsy, Shopify and Amazon also print their names on a customer's card refund (`DEBIT CARD CREDIT UBER *TRIP HELP.UBER.COM CA`). A released row:
  - is verified only by a form or by step 10's single-row context (`DEBIT CARD CREDIT VISA DIRECT SQUARE INC` verifies through Square's real-time-rail context);
  - otherwise stays `unverified_deposit` and is held as `possible_return` under 5.6;
  - never joins the recurrence pool (§7.0's veto), so three refunds from one source never verify each other.
  A retail merchant's card refund keeps the reversal. The first draft measured 126 rows, $220K, in 12 statements on the wider release; the census restates the narrower one.
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
| 17, 28, 29 | M | Insurer as the customer (DRP, vendor, commission) | **In** as held `insurer_payer` when the row prints customer-payment wording (T14); HCCLAIMPMT verified only with T18 (§7.7). An unlisted payer whose name reads as an insurer is held (`insurer_named_payer`). A carrier's bare `PAYMENTS` entry stays `non_revenue`: a business's own claim prints the same way (Q6: insurers never count) |
| 18, 57 | M | Healthcare payers without HCCLAIMPMT | **In** through `HEALTHCARE_PAYER_ALIASES` and Q6; Canadian carriers and the RBC claim label **out** (§7.7) |
| 20, 47 | M | Treasury and state vendor payments | **In** (§7.6) |
| 21 | M | Auctions and dealer funding | **In** (§7.8; §8.7 for listed auto lenders and the credit-union form); Copart and IAA **out** |
| 22 | M | Canadian brand deposit codes | **In** (anchored `brand_dep`) |
| 27 | H | HCCLAIMPMT from BCBS | **In** only on the owner's yes to T18: claim first (§7.7, OQ5) |
| 30, 31 | H | Chase book transfers from third parties | **In** only on the owner's yes to T19 (§7.11, OQ6) |
| 32 | H | FUNDS TRANSFER incoming wires | **In** (§7.11) |
| 34 | M | Push-to-card printed as card credit | **In** for push-rail words and processor payouts; a released row that no form verifies is held (§7.11) |
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

Statement pass 7 (§6.2) runs after every verifying rule. It first computes each posted credit's payer facts (channel family, payer region, payer name, payer key, entry fields, and the hold predicates of §8.1). Then it runs Q7's credit-union arm (§8.7) and the Q5 and Q6 verifications (§8.5, §8.6), which refuse any row a hold of §8.1 names. Last, it gives every remaining `unverified_deposit` its tier and reason, in the order of §8.10.

### 8.1 Holds that apply to any channel

Every hold below skips a row that the registry, a payout entity or a factoring payee claimed (§8.9), except `insurer_payer`, `possible_return` and the pay and benefit holds, which read wording no platform prints on its own payouts. The **posting labels** removed before a hold reads a row are §7.5's credit posting labels, plus `INSTANT CREDIT`, `REAL TIME CREDIT`, `COUNTER CREDIT`, `POS CREDIT`, `ATM CREDIT`, `TELLER CREDIT`, `BRANCH CREDIT`, `CARD CREDIT`, `BATCH CREDIT`, `MERCHANT CREDIT` and `CREDIT FROM`, and the channel phrases `FUNDS TRANSFER`, `FUNDS AVAILABLE` and `INSTANT FUNDS`.

- **`insurer_payer`:** a row whose revenue method is `insurer_customer_payment` (§6.1 step 5, T14). The customer-payment wording, read on a credit from a listed insurer, is `\b(?:DRP|VENDOR ?(?:PMT|PAY|PAYMENT)|COMM?ISS?IONS?|AGT ?COMM|AGENT COMP|AGTEFT|REPAIR)\b`.
- **`insurer_named_payer`** (new): the payer region prints `\bINSUR\w*`, `\bASSURANCE\b`, `\bMUTUAL\b`, `\bCASUALTY\b`, `\bINDEMNITY\b` or `\bUNDERWRIT\w*`, or `\bCLAIMS?\b` on a row that is neither an `HCCLAIMPMT` entry nor from a healthcare payer. It closes Q6's "insurers never count" for carriers no registry lists (`FABRIKAM MUTUAL INSURANCE COMPANY DES:CLAIM PAYMT`). Measured on the memo's rows: $1.06M, 527 rows, 61 statements.
- **`possible_return`:**
  - `\bRETURN(?:ED|S)?\b`, `\bADJ(?:USTMENT|USTED)?\b`, `\bDISPUTE[DS]?\b`, `\bCREDIT MEMO\b`, `\bOVERPA\w*`, on a row the reversal rule did not claim;
  - a `DEBIT CARD CREDIT` or `POS CREDIT` row released from the reversal rule (§7.11) that no form and no single-row registry context verified.
- **`financing_named_payer`** (T4). The financing roots are read, after the posting labels are removed, on:
  - the payer region (§5.2), read before D11's filtering, so `CAPITAL ONE …` keeps `CAPITAL`;
  - the entry fields (§5.2): `DES`, `CO ENTRY DESCR`, a wire's `OBI` and purpose text, and a memo;
  - on a row with no payer region (a check, cash, branch, ATM or bare row), the row before its receiver fields.

  A run that equals the holder's whole normalized `account_name` (two or more words) is removed first, so a label-less receiver field never supplies a root. A whole-word `CREDIT` or `CREDITS` counts as a root only inside a payer name, next to another name word (`UNITED AUTO CREDIT`, `CREDIT ACCEPTANCE`, `FABRIKAM CREDIT UNION`); in an entry field and on a row with no payer region, a standalone `CREDIT` is a posting word and is never read (BofA's `COUNTER CREDIT`, `DES:CREDIT`). Glued, it always counts (`BIZ2CREDIT`, `CREDITLINE`).

  The roots: `(?:FUND|CAPIT|CAPTL|LOAN|LEND|FINANC|ADVANC|MORTG|ACCEPTANCE|SERVICING|SERVICER|LEASING|PORTFOL)`, `CRED(?=ORA|IBLY)`, `CREDIT` glued on either side, or the whole words `CAP`, `CAPI`, `FIN`, `FINA`, `FINAN`, `FINL`, `FNCL`, `ADV`, `MTG`, `MCA`, `RTR`, `SPV`, `LEASE`. `FACTOR` is not a root: a factor's payout is revenue (owner, 2026-09-26), and registered factors are decided before this pass.

  Also held here:
  - a credit from a `DEALER_FUNDING_PAYERS` lender that the ledger has not yet admitted, and that Q7 did not verify (§8.7);
  - a row that prints a Q7 dealer-funding word (`VHCL PURCH`, `VEHICLE PURCHASE`, `DEAL FUND`, `CONTRACT FUND`, `DEALER FUND`, `DLR PMT`, `AUTODLRPMT`, `VADMIN FEE`, `FUNDLOAN`) that Q7 did not verify.

  Measured on the memo's rows with the rule as written here (`work/spec/revision/revision_probe.py`): $2.1M, 402 rows, 174 statements. The first draft's $5.0M read the whole row before the receiver fields, and left out the branch rows its wording would also have held (`COUNTER CREDIT`: 307 rows, $4.92M, as the review measured).
- **`payer_debited_as_lender`:** the payer's first distinctive word (§7.5) is also the first distinctive word of a posted debit in the same statement whose state is `confirmed_lender`, `potential_lender` or a financing group. This is the unregistered funder that funds and then collects.
- **`holder_name`:** the holder test of §5.2 matches the payer region. It never runs on a check, cash, branch, ATM or bare row.
- **`payroll_or_salary`** (Q8), read on the row before its receiver fields:
  - `\bPAYROLL\w*`, `\bPAYRLL\b`, `\bPAYROL\b`, `\bPAYRL\b`, `\bSALARY\b`, `\bSALARIES\b`, `\bREG SAL\b`, `\bWAGES?\b`, `\bNET ?PAY\b`, `\bBONUS(?:ES)?\b`, `\bPAY PAY\b` (BMO's pay code), `\bPAIE\b`, `\bSALAIRES?\b`;
  - `\bDIR ?DEP\b`, `\bDIRDEP\b` and `\bDIRECT DEP\b` (not followed by `OSIT`) anywhere in the row, so Wells Fargo's `FABRIKAM INC DIR DEP 240115 …` is held; the whole phrase `DIRECT DEPOSIT` only as an entry description (`\b(?:DES|CO ENTRY DESCR) DIRECT DEPOSIT\b`), because BMO and ATB print it as their channel template (`^DIRECT DEPOSIT`);
  - an employee's reimbursement from a company: `\bEXP(?:ENSE)? REIMB\w*`;
  - or `_is_payroll_provider_row`.
- **`personal_income`:** `\b(?:XX)?SOC SEC\b`, `\bSSA\b`, `\bSSI\b`, `\bSUPP SEC\b`, `\b(?:XX)?VA BEN\w*`, `\bUNEMPLOY\w*`, `\bUI BEN\w*`, `\bCHI?LD ?SUPP\w*\b`, `\bCHILD ?CTC\b`, `\bPENSION\b`, `\bANNUIT\w*`, `\bRETIRE\w*`.
- **`non_sale_purpose`** (new). Any of these, read on the row before its receiver fields after the posting labels are removed:
  - owner money, investment and intercompany: `\bINVEST\w*`, `\bDISTRIB(?!UTORS?\b|UTING\b)\w*` (a distributor paying is a customer), `\bDIVIDENDS?\b`, `\bEQUITY\b`, `\bCONTRIB\w*`, `\bSHAREHOLDER\w*`, `\bOWNERS?\b` (not `OWNER OP`, `OWNER OPERATOR`: a carrier paying an owner-operator), `\bSTOCK\b`, `\bINTERCO\w*`, `\bINTER COMPANY\b`, `\bDUE FROM\b`, `\bSWEEP\b`, `\bZBA\b`, `\bZERO BAL\w*`;
  - financing that carries no root: `\bREPAY\w*`, `\bPRINCIPAL\b`, `\bPAYOFF\b`, `\bPROMISSORY\b`, `\bCONVERTIBLE\b`, `\bTRANCHE\b`, `\bDRAWS?\b`, `\bDRAWDOWNS?\b`, `\bDISBURS\w*`;
  - deposits held for others: `\bESCROW\b`, `\bEARNEST\b`, `\bSECURITY DEPOSIT\b`, `\bDEPOSIT BACK\b`, `\bSURPLUS\b`;
  - gifts, grants and courts: `\bGRANTS?\b`, `\bDONATION\w*`, `\bGIFT\b` (not `GIFT CARD`), `\bCOURT\b`, `\bJUDGMENT\b`;
  - rebates, claims, reimbursements and interest: `\bREBATES?\b`, `\bCLAIMS?\b` (not on an `HCCLAIMPMT` entry or a healthcare payer's `CLAIM PMT`), `\bREIMB\w*`, `\bINTEREST\b`, `\bREWARDS?\b`, `\bCASH ?BACK\b`. A bank's own interest, dividend or reward credit prints no payer; it is held here rather than named `non_revenue` (M12 of the review: about $0.12M of interest and $0.31M of dividends in the memo's rows);
  - a public payer's refund or benefit (§7.6): the payer region matches a §7.6 payer pattern or the payer-name veto, and the row prints a §7.6 whole-row veto word (tax, refunds including a glued `MDREFUND`, `EIC`, benefits, pay, relief, grants, loans, family and court, claims and awards, assistance);
  - a healthcare payer's member or premium credit: a healthcare payer with `\bREIMB\w*`, `\bMEMBER\b`, `\bMBR\b`, `\bSUBSCRIBER\b` or `\bPREMIUM\b` (§7.7).

  Measured on the memo's rows: $1.3M, 855 rows (of which the public-payer part is $0.16M, 407 rows).
- **`payer_also_debited`:** the payer's first distinctive word (§7.5's definition) is also the first distinctive word of a posted debit in the same statement that is not a lender debit. The payer may be the owner's other account, an affiliate, or a funder whose daily debits no rule names; the accounts-payable verifier's R2 required review. It covers the §7.5 counter-debit rows (`payer_remittance_with_counter_debit`, 19 rows, $242K) and the Q5 and Q6 counter-debit guards (§8.5, §8.6). A payer debited as a lender is `payer_debited_as_lender` instead.

### 8.2 Q2: cash, branch, ATM and bare deposits; transfer wording

The patterns follow the memo's `categorize.py`, which agrees with 94% of 315 hand-sorted payer groups; every pattern that file holds is inlined below. The cash, branch and ATM patterns apply only to a row that prints no electronic-payment form and no person-to-person rail, so an ACH payer named like a branch (`BRANCH MESSENGER`) is never read as a teller deposit.
- **Cash:** `\bCASH DEP(?:OSIT)?\b`, `\bATM CASH\b`, `\bCPS DEVICE\b`, `\bCURRENCY PROCESSING\b`, `\bSMART ?SAFE\b`, `\bCOIN\b`, `\bCASH IN\b`.
- **Branch and teller:** `\bCOUNTER (?:CREDIT|DEPOSIT)\b`, `\bTELLER\b`, `\bIN BRANCH\b`, `\bBRANCH\b`, `\bBRCH\b`, `\bDEPOSIT AT BR\b`, `\bDEPOSIT THANK YOU\b`, `\bMAIN OFFICE\b`, `\bPRE ?ENCODED\b`, `\bNIGHT (?:DEP|DROP)\b`, `\bBANKING CENTRE\b`, `^GC\b.*\bDEPOSIT\b`, `\bG DEPOT\b`, `\bDEPOT\b`, `\bDEPOSIT IBB\b`, `\bVAULT DEP\w*`, `\bSTORE DEPOSIT\b`, `\bDEPOSIT MADE IN\b`.
- **ATM:** `\bATM\b.*\bDEP(?:OSIT)?\b`, `\bDEP(?:OSIT)?\b.*\bATM\b`, `\bABM\b`.
- These three are `counted_flagged` / `no_payer_printed`, never Verified (§6.1 step 9b).
- **Bare deposit, credit or EFT,** on any channel: after the template prefixes, `GENERIC_WORDS` and the reference tokens are removed, no payer word remains, and the row prints no transfer wording. It is `counted_flagged` / `no_payer_printed` too (§8.10, last step), never Verified. BMO's `DIRECT DEPOSIT <digits>` is a numbered company (§5.2) instead.
- **Transfer wording:** `\bTRANSFER\b`, `\bTRNSFR\b`, `\bXFER\b`, `\bTFR\b`, `\bBR TO BR\b`, `\bONLINE BANKING\b`, `\bINTERNET (?:BANKING|TRANSFER)\b`, `\bFUNDS TRANSFER\b`, on a row that prints no person-to-person rail.
  - With no counterparty (no payer word after the template prefixes, `GENERIC_WORDS`, the account words of T13 and the reference tokens are removed), it is `excluded_pending_review` / `transfer_no_counterparty`. The tier pass tests this **before** the check, cash, branch and ATM tiers, so `TELLER TRANSFER` is held, not counted.
  - With a named counterparty, T13 and §8.4 apply.

### 8.3 Q3: check deposits

`\bMOBILE (?:CHECK |CHEQUE )?(?:DEPOSIT|DEP)\b`, `\bMOBILE CHE(?:CK|QUE)\b`, `\bMB DEP\b`, `\bBKOFAMERICA MOBILE\b`, `\bREMOTE (?:ONLINE )?(?:DEPOSIT|CAPTURE)\b`, `\bDEPOSIT CAPTURE\b`, `\bMERCHANT CAPTURE\b`, `\bDESKTOP (?:REMOTE )?DEPOSIT\b`, `\bEDEPOSIT SCAN\b`, `\bE ?CHEQUE DEPOSIT\b`, `\b(?:ATM )?CHE(?:CK|QUE)S? (?:DEPOSIT|DEP|RECEIVED)\b`, `\bMAIL DEPOSIT\b`, `^REMOTE$`, `\bIMAGED DEPOSIT\b`, `\bDEPOSITED (?:CHECK|ITEM)\b`, `\bRDC\b`, `\bSCAN(?:NED)? DEPOSIT\b`, `\bLOCKBOX\b`, `\bLBX DEP\b`.

These are `counted_flagged` / `check_deposit`, never Verified (§6.1 step 9b). A returned deposited item is decided earlier, as a reversal.

### 8.4 Q4: person-to-person, and named transfers

- **Rails:** the consumer rails `\bZELLE\b`, `\bINTERAC\b`, `\bE ?TRANSFER\b`, `\bE ?TFR\b`, `\bVIREMENT\b`, `\bVFC\b`, `\bAUTODEPOSIT\b`, `\bVENMO\b`, `\bCASH ?APP\b`, `\bSQUARE CASH\b`, `\bAPPLE CASH\b`, `\bPOPMONEY\b`, and the real-time and push rails `\bREAL TIME (?:TRANSFER|PAYMENT)\b`, `\bRTP\b`, `\bFEDNOW\b`, `\bINSTANT (?:PMT|PAYMENT|TRANSFER)\b`, `\bVISA (?:MONEY TRANSFER|DIRECT)\b`, `\bMONEY TRANSFER\b`, `\bMC SEND\b`, `\bPMNT RCVD\b`, `\bPAYMENT RECEIVED\b`. A row the registry or a form already claimed (an RTP payout from Amazon, a Visa Direct payout from Square) is not a person-to-person row.
- **Named transfers** (T13): transfer wording (§8.2) with a named counterparty belongs here.
- **The sender** is the payer region (§5.2).
- **`transfer_account_designation`:** a named transfer whose row prints an account designation, an account-type word (`CHECKING`, `CHK`, `CHKG`, `SAVINGS`, `SAVING`, `SAV`, `SVGS`, `MONEY MARKET`, `MMA`, `DDA`, `ACCOUNT`, `ACCT`, `EVERYDAY`) or a masked account number (`\bX{2,}\d{2,}\b`, `\bENDING (?:IN )?\d{3,}\b`), is held: it reads as the owner's account at another bank. Measured on the memo's rows: $1.18M, 1,473 rows, 168 statements.
- **`p2p_round_repeat`:** a sender with two or more round-sum credits on these rails or through named transfers in the statement has every one of its round-sum credits held. Its other credits stay counted. The memo counted a repeat of any amount; this reading follows the ruling's words, "repeated round sums from one sender".
- A sender with the holder's name is `holder_name` (§8.1).
- Everything else is `counted_flagged` / `p2p`, never Verified, even when the sender prints a company form (Q4, §6.1 step 9b).

### 8.5 Q5: incoming wires

- **The wire family:** the leading labels of §7.9 N1, a third-party book transfer (§7.11, only with T19), or, for tiering only, the loose wire words `\bWIRE\b`, `\bFEDWIRE\b`, `\bFED WIRE\b`, `\bIWT\b`, `\bCHIPS CREDIT\b`, `\bSWIFT\b`, `\bFOREIGN REMITTANCE\b`, `\bWT FED\b`, `\bFED REF\b` on a row no rail of §8.4 claimed.
- **Verified: the same company twice or more** (method `repeat_wire_sender`, confidence 0.85). The row begins with an N1 label (or is a third-party book transfer under T19), and:
  - no hold of §8.1 applies to it;
  - its sender prints a company form (§5.2) or is a government or healthcare payer;
  - two or more wire credits in the statement have that payer key (repeats, §5.2, which never count a held row);
  - the sender is not a numbered company (§5.2), and names no bank (`BANK`, `BANCO`, `BANCORP`, `N A`, `TRUST COMPANY`, `CREDIT UNION`, `FCU`, `SAVINGS`), since a relaying bank hides the real payer, and no title or escrow firm (`TITLE`, `ESCROW`, `CLOSING`, `SETTLEMENT`);
  - the row passes every veto of §7.9: the financing roots read as §7.9 reads them (after the channel words and the sending and intermediary bank fields are removed, and wrap-tolerant on the originator), the non-sale purposes, the own-account test, the brand-word affiliate test, the cut-field test and `match_known_payee`;
  - it prints none of the words that refuse a Q6 verification (§8.6).
- **Verified: an invoice or PO wire:** §7.9 (step 14).
- **Held:** a wire with no sender printed is `wire_no_sender`; one the holder test matches is `holder_name`; one whose sender is also debited in the statement is `payer_also_debited` (§8.1); one that a hold of §8.1 names takes that hold (`OBI SERIES A INVESTMENT`, `REF INTERCO SWEEP` and `OBI PAYROLL` are held).
- **Otherwise:** `counted_flagged` / `wire_named_sender`, including senders that are persons, banks or title companies. A wire that §8.6's verification-only words refused is `named_payer_purpose_refused`.

### 8.6 Q6: named ACH and EFT payers

**Eligible rows** are unverified posted credits that meet all of these:
- the row prints an electronic-payment form (§5.2) and has a payer region;
- the channel gate (§6.1 step 9b) does not close it: it prints no person-to-person rail, and no transfer wording in its entry fields;
- it is not a wire;
- no registry alias, payout entity or factoring payee matched it, because platforms are decided by §7;
- no hold of §8.1 applies, so no financing root in its payer region or entry fields, no insurer name, no non-sale purpose, no pay wording and not the holder;
- it is not a numbered company (§5.2).

**Refused** (counted as `named_payer_purpose_refused`, not verified, not held): a row whose entry fields or payer region print one of the verification-only words below. They are sales wording often enough that holding them would take real revenue out of True, but they are not proof: `\bSETTLEMENT\b` (a legal or insurance settlement prints it, and so does an unregistered processor), `\bTAX(?:ES)?\b`, `\bIRS\b`, `\bCRA\b`, `\bFEES?\b`, `\bSUBSCRIPTIONS?\b`, `\bDISCOUNT\w*`, `\bCOMM?ISS?IONS?\b`, `\bCOMPENSATION\b`, `\bEXPENSES?\b`, `\bAFFILIATE\b`, `\bPERSONAL\b`, `\bCLOSING\b`, `\bSCF\b`, `\bSUPPLY CHAIN\b`, `\bEARLY PAY(?:MENT)?\b`, `\bALLOWANCES?\b`, `\bSHORTAGES?\b`, `\bRMA\b`, and, in the entry fields only, `\bFLOOR ?PLAN\b`, `\bFLOORPLAN\b`, `\bVIN\b`, `\bEQUIP\w*`.

**Verified** (method `named_payer_repeats`, `named_payer_company_form` or `public_or_healthcare_payer`) when any of these holds:
- (a) the payer repeats (§5.2) and at least one of its credits is not a `PPD` or `WEB` entry. A consumer entry never verifies by repetition alone (structural S50);
- (b) the payer name prints a company form;
- (c) the payer is a government payer (§5.2, with §7.6's patterns and every veto) or a healthcare payer (§7.7) whose row prints none of `REIMB`, `MEMBER`, `MBR`, `SUBSCRIBER` or `PREMIUM`.

**Guard:** no posted debit in the same statement shares the payer's first distinctive word (§7.5). A payer that is also debited is held as `payer_also_debited`, and one debited as a lender is held as `payer_debited_as_lender` (§8.1).

**Otherwise** the row is `counted_flagged` / `named_payer_one_off`.

Lenders are decided `non_revenue` earlier (D1 and the potential registry), unregistered ones are held (T4), insurers are `non_revenue` or held (T14, `insurer_named_payer`), and the holder is held. That is Q6's "lenders, insurers and the holder never count."

### 8.7 Q7: an auto lender paying a dealer

At step 4 (§6.1), a credit is `verified_revenue` (method `auto_lender_dealer_funding`, source type `auto_dealer_funding`, confidence 0.90) when its payer, read on the originator segment (`_originator_segment`, never a receiver or memo field), is an auto lender, and one of these holds:
- **the listed-lender arms.** The payer is a listed auto lender: a `vehicle_financing` registry entity, or an entry of `DEALER_FUNDING_PAYERS` (registry, new: Westlake Financial (never Westlake Flooring), United Auto Credit, Strike Acceptance, PFS, Suncoast Credit Union, CU Direct / CUDL, Credit Acceptance, Exeter, Flagship Credit, GLS, Santander Consumer, Chrysler Capital, GM Financial, Toyota Financial, Honda Financial, Nissan Motor Acceptance, CarMax Auto Finance, Ally, American Credit Acceptance, Regional Acceptance, Nicholas Financial, Lendbuzz). And the row prints either:
  - dealer-specific funding words: `\bVHCL PURCH\w*`, `\bVEHICLE PURCHASE\b`, `\bDEAL ?FUND\w*`, `\bFUNDLOAN\b`, `\bDEALER (?:FUND\w*|FND|PMT|PAY\w*)\b`, `\bDLR PMT\b`, `\bAUTODLRPMT\b`, `\bCONTRACT FUND\w*`, `\bVADMIN FEE\b`; or
  - `\bPAYABLES\b`, `\bTRADE PAY\w*` or `\bACCT FUND\w*`.
- **the credit-union arm.** Credit unions fund dealers' indirect auto loans through CU Direct (CUDL) and print their own name with the entry `VHCL PURCH`. The payer region names a credit union (`\bCU\b`, `\bCREDIT UNION\b`, `\bFCU\b`) or CU Direct / CUDL; the entry field is `\bVHCL PURCH(?:ASE)?\b` (Chase's glued `VHCL PURCHSEC` is split by the revenue text, §7.0); and the statement holds two or more such credits. A single one can be a member's own purchase loan paid into the member's account, so it is held as `financing_named_payer`. Because it needs the statement, this arm is decided in statement pass 7 (§6.2), before the Q5 and Q6 verifications: step 4 leaves such a row `unverified_deposit` (method `credit_union_vehicle_purchase`), and the pass verifies it with method `auto_lender_dealer_funding` when the count is met.

Q7 never fires when any of these holds:
- the row matches a D1 entity outside the vehicle-financing group, a potential lender or an insurer (`KAPITUS DES:CONTRACT FUNDING`, `ONDECK CAPITAL DES:DEAL FUND`, `GEICO DES:VEHICLE PURCHASE`);
- the row prints `\bLOANS?\b`, `\bPROCEEDS\b`, `\bADVANCES?\b`, `\bADV\b`, `\bMCA\b`, `\bCASH ADV\w*` or a refund word (`REFUND`, `RFND`, `REFND`, `RFD`, `RETURN`, `RTN`, `REVERSAL`, `RVSL`, `CHARGEBACK`, `CHBK`) (`SUNCOAST CREDIT UNION DES:VHCL PURCH LOAN PROCEEDS`);
- the channel gate (§6.1 step 9b) closes the row.

A reversal marker still wins, because step 3 runs first. Any other credit from a listed auto lender stays financing: D1 makes it `non_revenue` / financing proceeds. S1 admits the `DEALER_FUNDING_PAYERS` lenders the ledger lacks into its vehicle-financing group, through the ledger's process. Until a lender is admitted, its credits that Q7 does not verify are held as `financing_named_payer`, whether or not its name carries a financing root; so is any row printing a dealer-funding word that Q7 did not verify (`FABRIKAM MERCHANT FUNDING DES:DEAL FUNDING`). A dealer-funding credit is not financing proceeds, so it leaves `lender_credits` and returns to eligible deposits (an intended move).

Measured on the memo's rows: the first draft's arms (dealer wording alone) reached $4.02M, 214 rows, 11 statements. The revised rule keeps all of it: the listed-lender arms $0.37M (150 rows, 8 statements) and the credit-union arm the other $3.64M (64 rows, 4 statements of one dealer, 15 to 18 such credits in each). The corpus holds no dealer-worded credit from an unlisted, non-credit-union payer, so the tightening removes only the fabricated false positives the review built. Tryout host: $0.56M, one used-car dealer (not re-measured; the census restates it).

### 8.8 Q8: payroll and salary

`payroll_or_salary` (§8.1) is held, whoever the payer is. A payroll credit from the holder is `holder_name`. `DES:BONUS`, `DES:PAYRL`, Wells Fargo's `… DIR DEP …` and an employer's `EXP REIMB` are held here.

### 8.9 Everything else

- A registry match that did not verify: `counted_flagged` / `platform_unconfirmed`.
- A factoring payee's credit: `counted_flagged` / `factoring_payout`. It keeps its Factoring flag. The owner deferred its Verified status (2026-09-26).
- A credit from `PAYOUT_CREDIT_ENTITIES`: `counted_flagged` / `payout_credit_entity`.
- A numbered company: `counted_flagged` / `numbered_company_payer` (T11).
- A named payer that Q5 or Q6 refused on a verification-only word: `counted_flagged` / `named_payer_purpose_refused`.
- A named payer on a row with no electronic-payment form (fintech exports, S51): `counted_flagged` / `named_payer_unlabelled`. It is never verified in this release. The census reports how much of it would pass Q6's test.
- No payer word at all: `counted_flagged` / `no_payer_printed`.

### 8.10 Tiering order and thresholds

For each unverified posted credit the pass takes the first that applies:
1. `direction_conflict`
2. `insurer_payer`
3. `insurer_named_payer`
4. `possible_return`
5. `financing_named_payer`
6. `payer_debited_as_lender`
7. `holder_name`
8. `payroll_or_salary`
9. `personal_income`
10. `non_sale_purpose`
11. `payer_also_debited`
12. wires (§8.5: `wire_no_sender`, `wire_named_sender` or `named_payer_purpose_refused`)
13. `transfer_no_counterparty` (before the check and branch tiers, so `TELLER TRANSFER` is held)
14. `transfer_account_designation`
15. `check_deposit`
16. cash, branch, ATM (`no_payer_printed`)
17. person-to-person and named transfers (`p2p_round_repeat`, or `p2p`)
18. `platform_unconfirmed`
19. `factoring_payout`
20. `payout_credit_entity`
21. `numbered_company_payer`
22. `named_payer_purpose_refused`
23. `named_payer_one_off`
24. `named_payer_unlabelled`
25. `no_payer_printed`

Holds 2 to 11 are §8.1's; the owner's own holds (Q2, Q4, Q5, Q8 and the holder) are among them or in tiers 12 to 17.

| Threshold | Value | Where |
|---|---|---|
| Repeats | 2 or more credits, same payer, one statement | §5.2, Q5, Q6 |
| Round sum | at least $100, a whole multiple of $100 | §5.2, Q4 |
| Round-sum repeat | 2 or more round sums from one sender, rails and named transfers alike | §8.4 |
| Credit-union dealer funding | 2 or more `VHCL PURCH` credits from credit unions in the statement | §8.7 |
| Operating recurrence | 3 or more credits, or 2 on a business account (a legal-form holder counts) | §7.0 |
| Micro-deposit floor | under $1 never verifies and never counts | §7.0, §7.8, §7.10 |
| NET SETTLE from an unregistered originator | 3 or more credits | §7.1 |
| Auction refund window | 14 days, equal amount, one debit each | §7.8 |
| Package gate | held credits at least 10% of all posted credits, non-revenue included, in integer cents (`REVENUE_REVIEW_HELD_SHARE`) | T7 |

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
- **Evidence:** the package's revenue evidence stays per state, and each evidence record carries its tier fields. The package's own `true_revenue_evidence`, at the top level (`webapp/app.py:2155`) and inside `detection` (`:2167`), is repointed with the per-account one: the members' verified plus counted evidence, not `package_revenue_evidence["verified_revenue"]`. `counted_flagged_evidence` and `excluded_pending_review_evidence` join both places.
- **Fallbacks:** `_package_analysis` reads `metrics["true_revenue"]` twice as a fallback today: for a member's verified total when its rows are not authoritative (`:1441-1447`, after `verified_revenue_total` and `confirmed_true_revenue_total`), and for the withholding denominator when `withholding_denominator` is missing (`:1471-1474`). After the repoint that key is True revenue, so both fallbacks are dropped: the verified total falls back to `verified_revenue_total`, then `confirmed_true_revenue_total`, then `None` (the member's verified figure is not established); the denominator falls back to the legacy eligible deposits.
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
- An outdated payload (before 5.6): True, Counted and Held are N/A, with the note "Re-analyze to compute true revenue". Verified shows the stored figure under the outdated notice. A package with an outdated member shows its True, Counted and Held totals as N/A, as for any member whose `revenue_established` is false.

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
- **Replay:** `webapp/reanalysis.py` `_awaits_review` becomes decision-aware, `_awaits_review(record, decision)`:
  - a row whose initial state is `unverified_deposit` awaits any decision, as today;
  - a row whose initial state is `verified_revenue` (decided by a rule) awaits only a `reject`: the analyst's word wins over a rule, so the reject is replayed;
  - a `confirm` on a row whose initial state is `verified_revenue` does not await review. `replay_reviews` puts it in `ruled`, reported under `reviews_decided_by_rules`, as today. It never reaches the review writer, which would refuse it ("already verified") and report it as needing redoing.
- **The multi-select batch** (`/analysis/<job_id>/revenue-reviews`) takes the same rows.
- **An outdated payload (before 5.6)** is reviewed under today's rules. Its records carry no tier, so the server writes no tier field. Only `unverified_deposit` rows are reviewable, confirm sets `verified_revenue` and reject sets `non_revenue`. Its rebuild takes the tier-less path of §12.

### 10.8 Exports

- **Statement CSV/XLSX:** the new metric keys flatten as today. The by-reason dicts are written as readable rows through the escaped-row path: section `revenue_tier`, field `<tier>.<reason>.count` / `.total`. A row's classification record, in evidence, carries its tier fields.
- **Package CSV/XLSX:** totals and document rows gain the keys of §9.2. The per-state evidence sections are unchanged, and each record carries its tier fields. The currency sweep covers the new money keys and the by-reason totals.
- **JSON:** follows the displayed payload.

## 11. Withholding

- **Default unchanged:** `legacy_eligible_deposits`, effective deposits minus lender (financing-proceeds) credits, less internal-transfer credits in a package. Nothing in this spec gives a reason to move the default.
- **Selectable:** `verified_revenue` (unchanged, Q1), and the new `true_revenue` (T8). Both are set through `WITHHOLDING_DENOMINATOR_MODE`, as today; the tryout host does not set it.
- **Package internal transfers in the `true_revenue` mode.** `_package_analysis` deducts R-d's internal-transfer credits from the legacy denominator only (`webapp/app.py:1478`). The verified mode needs no deduction, because an internal-transfer credit is `non_revenue` and was never in it. That reasoning does not hold for True revenue: an R-d pair can include a credit a member counted (a named transfer between two members, `p2p`). In the `true_revenue` mode, the package deducts the R-d internal-transfer credits whose tier is `verified` or `counted_flagged`, and only those.
- **How the figures relate.** Every financing-proceeds credit is `non_revenue`, so when a statement's line items are its Total, True revenue ≤ legacy eligible deposits. The gap is the other non-revenue (own-account transfers, refunds, insurance, potential-lender credits, duplicates) plus the held credits. Verified ≤ True always.
- **Where eligible deposits move:**
  - down, where `SQ CAP` and SBA or EIDL credits become financing proceeds (§7.11);
  - up, where Q7 takes dealer funding out of D1 (§8.7).

  Both moves are listed in the census.

## 12. Backward compatibility

- **Stored analyses are never rewritten.** A saved job keeps its payload until someone re-analyzes it, and the Re-analyze route (lender spec §8.6) replays review decisions as today, with §10.7's widening.
- **Outdated notice:** automatic for every analysis older than the running version (§9.3).
- **Before 5.6:** no tiers. The served copy:
  - sets `revenue_established` false;
  - sets `true_revenue`, `true_revenue_total` and the tier totals to `None`;
  - sets every `true_revenue_evidence` to `None`: in each account's metrics and detection, and in the package's top level and `detection`;
  - removes `contributes_to_true_revenue` from every row's classification record, so a reader never takes the old verified meaning for the new one;
  - keeps `verified_revenue_*` as stored (T10).
  The stored job is untouched: `_displayed` copies before it changes anything, as `apply_flagged_groups_to_payload` does.
- **The tier-less rebuild path.** A review on a pre-5.6 job rebuilds its revenue views (`rebuild_serialized_revenue_views`). When no record in the payload carries `revenue_tier`, the rebuild runs today's three-state logic: it computes no tier totals, skips the state/tier agreement check, and leaves `revenue_established` false. A payload in which some records carry a tier and others do not is refused, as a missing state is refused today. The review writer follows §10.7's outdated rules.
- **Gating an outdated member.** Its held rows cannot be told from its counted ones, so T7's held share cannot be computed. An outdated member is gated by today's rule: it needs revenue review when it has a pending `unverified_deposit` row, a direction conflict, or revenue that does not reconcile. The package note names it ("Re-analyze to compute true revenue").
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
| `analysis/metrics.py` | tier sums, the "exactly one tier" check, new fields, repointed `true_revenue` and `true_revenue_evidence` (`:148`, `:441`), the gate, the `true_revenue` mode; `eligible_deposits` unchanged |
| `analysis/detect.py` | repointed `true_revenue_evidence` (`:94`, `:336`); the counted and held evidence lists; `manual_review` |
| `analysis/serialization.py` | the same evidence keys (`:195-208`) |
| `analysis/flagged_view.py` | none: the outdated flag already compares versions |
| `webapp/app.py` | §9.2, §10.4 in `_displayed` and `_package_analysis`; the two `metrics["true_revenue"]` fallbacks dropped (`:1441-1447`, `:1471-1474`, §9.2); the `true_revenue` mode's internal-transfer deduction (`:1478`, §11); the package's `true_revenue_evidence` (`:2155`, `:2167`); the outdated served copy (§12); the decision gate (`:1951-1962`); currency keys (`:692-727`); exports (`:346-486`); review routes (`:2521`, `:2574`) |
| `webapp/reanalysis.py` | `_awaits_review(record, decision)` (§10.7) |
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
- **§7.5:** the 21 positives and 18 negatives of the probe; every reviewer negative (the funder statement with AP-worded credit plus same-name daily debits; a floor-plan-shaped `Payables … Vin:` credit; the cut names `… CAPI`, `… FUN`, `… FINA`, `… FINAN`, `… LOA`, `… LEASIN`, `… ADVANTAG`, `BIZ2CREDIT`; `Direct Deposit, <digits> ONTA AP /CC`; `ONLINE TRANSFER FROM INV 1234567`; `ZERO BALANCE TRANSFER CREDIT A/P PAYMENTS`; `ACH RTN VENDOR PAY … R03`; `BILL.COM DES:PAYABLES`; a person's Zelle "paying bills" and "Invoice 1234"; `DEPOSIT INV 1234`; `Remote Online Deposit … Invoice 55`); the numbered-company rows `DIRECT DEPOSIT 7654321 CANA AP CC`, `1234567 NOVA SCOTIA LTD DES:VENDOR PAY` and `7654321 NEW BRUNSWICK INC DES:PAYMENT`, which never verify; the holder's own `CONTOSO BAKERY LLC DES:VENDOR PAY` into Contoso Bakery, which never verifies; the verifier's funder statement (an AP-worded credit plus same-name daily debits that no rule classifies as lender), whose credit is held as `payer_also_debited` under 5.6.
- **§7.6:** each arm in the Citibank, BofA CTX, U.S. Bank, Chase glued and Wells Fargo formats; label-less holder-leak negatives (Wells Fargo, Truist, PNC `RECEIVER NAME`); a glued lender name; an EBT-in-DES row; one negative per veto word; the BofA boilerplate positive; `TRANSFER FROM COUNTY LINE … VENDOR PAY`; a PPD `DOD MISC` row that stays unverified; a verified row still demoted by the duplicate pass and by a `RETURNED ITEM` pair.
- **§7.7:** the list in §7.7.
- **§7.8:** direction conflict; `FUNDING`, `ADVANCE`, `CAPTL`, `AFC FUNDNG`, `FLOORPLAN`, `FINANCING`, `NGC`; an alias in `IND NAME`, `INDN`, a Zelle "to" field and a memo, with and without `DISBURSEMENT`; `PAYROLL`, `PPD`, `DIR DEP`; `DEALSHIELD`, `ARB CREDIT`, card credits; a wire-paid and a Wells Fargo `Manheim ACH Paymnt` debit pair; the ACV `PYMT` hold; the D1 controls (ACV Capital, NextGear, AFC Funding, Westlake Flooring, Kinetic Advantage); the duplicate override.
- **§7.9:** the 40 cases of `simulate_v3.py`; the hazard groups G1 to G11; the returned-wire two-row statement; `CAPI TAL` and `FUN DING`; an individual citing an invoice; a sister company sharing its first word; `INV 1234 ADJ`; an address `PO 4521`; a Zelle memo with "wire"; `Unknown wire credit` stays unverified.
- **§7.10:** the eight lone rows that stay `operating_source_requires_context`; a Buildium fee debit plus one credit that stays unverified; a `$0.12` / `$0.21` ACCTVERIFY pair; a mixed-shape AppFolio pair (one Visa Direct row plus one PMNT RCVD row in a business-named account) that stays unverified.
- **§6.1 step 9b (the channel gate):** `ZELLE PAYMENT FROM JOHN SMITH MEMO INVOICE PAYMENT CONF 99`, `MOBILE DEPOSIT CUSTOMER PAYMENT REF 1234` and a bare teller `CUSTOMER DEPOSIT` stay unverified (counted `p2p`, `check_deposit` and `no_payer_printed` under 5.6); a Zelle from a sender with a company form stays unverified; `RTP CREDIT AMAZON COM` three times verifies by Amazon's recurrence; a lone `RTP CREDIT FROM FABRIKAM LLC INV 1234` stays unverified.
- **§7.11:** a Medicaid REIMBURSEMENT and an `HCCLAIMPMT … REIMBURSEMENT` that leave `non_revenue`; `UNITEDHEALTHCARE DES:REIMBURSEMENT` and `STATE OF TEXAS DES:TRAVEL REIMBURSEMENT` that stay `non_revenue`; an employer's `EXPENSE REIMBURSEMENT` that stays `non_revenue`, and an employer's `EXP REIMB` that is held as `payroll_or_salary` under 5.6; `12 OAK LN` in a wire and an ATM location that no longer read LOAN, and `TRUIST LN PYMT` (debit), `1234 COMMERCIAL LN PMT` and `000123 AUTO LN DISB` that still do; a Chase book transfer from a third party and one from the holder, each with the T19 switch on and off; RBC `Funds transfer credit TT`; `DEBIT CARD CREDIT VISA DIRECT SQUARE INC` that verifies; Relay's `Debit Card Credit: Stripe Payout` that verifies, and a bare `Debit Card Credit: Stripe` that stays `non_revenue` (§7.11's release rule: a processor's card credit leaves the reversal rule only with a payout word; §20); three `DEBIT CARD CREDIT UBER *TRIP HELP.UBER.COM CA` refunds, three `DEBIT CARD CREDIT DOORDASH*<store>` refunds and three `POS CREDIT PAYPAL *<store>` refunds, each set staying `non_revenue` (no push-rail or payout word), and never verified by recurrence; `CUSTOMER ID` on a Truist ACH row; each new non-revenue marker.
- **§8, one test per reason code in §5.3** and per verification (Q5 repeats, Q6 a, b and c), each with its guard's negative (holder, financing root, counter-debit, PPD repeats, bank-named and title senders, numbered company). The round-sum rule: two round sums from one sender are held, and one round plus one odd are counted, for rails and for named transfers alike. A named transfer is counted. A transfer with no counterparty is held. `TELLER TRANSFER` is held.
- **§8, the first review's rows** (`work/spec/review/sim_review.py`), each with the outcome this revision gives it:
  - Q7 (§8.7): `KAPITUS DES:CONTRACT FUNDING`, `ONDECK CAPITAL DES:DEAL FUND` and `GEICO DES:VEHICLE PURCHASE` stay `non_revenue`; `SUNCOAST CREDIT UNION DES:VHCL PURCH LOAN PROCEEDS` is not verified; `FABRIKAM MERCHANT FUNDING DES:DEAL FUNDING` is held as `financing_named_payer`; a statement with two `SAMPLE CU DES:VHCL PURCH` credits verifies both, and a lone one is held;
  - T4 (§8.1): `CONTOSO PARTNERS LLC DES:FUNDING` and `FABRIKAM GROUP LLC DES:CASH ADV` are held as `financing_named_payer`; `COUNTER CREDIT` is `no_payer_printed`; `CAPITAL FABRIKAM LLC DES:PAYMENT` is held (D11 drops the leading `CAPITAL`; the payer region keeps it);
  - non-sale purposes (§8.1): `FABRIKAM HOLDINGS LLC DES:INVESTMENT`, `FABRIKAM PARTNERS LP DES:DISTRIB`, `FABRIKAM SUPPLY INC DES:REBATE`, two `WIRE TYPE WIRE IN … ORIG FABRIKAM VENTURES LLC … OBI SERIES A INVESTMENT` wires and two `BOOK TRANSFER CREDIT B O FABRIKAM HOLDINGS LLC … REF INTERCO SWEEP` rows are held as `non_sale_purpose`; `FABRIKAM DISTRIBUTORS INC DES:PAYMENT` is not;
  - insurers: `FABRIKAM MUTUAL INSURANCE COMPANY DES:CLAIM PAYMT` is held as `insurer_named_payer`;
  - pay (Q8): `FABRIKAM INC DES:BONUS`, `FABRIKAM INC DES:PAYRL`, Wells Fargo's `FABRIKAM INC DIR DEP 240115 1234567 JOHN SMITH` and two `… OBI PAYROLL JAN` wires are held as `payroll_or_salary`;
  - public payers (§7.6, §8.1): `COMPTROLLER OF MD DES:MDREFUND`, `IRS TREAS 310 DES:TAX EIC` and `STATE OF OHIO DES:GRANT` are held as `non_sale_purpose`;
  - the holder (§5.2): `CONTOSO HOLDINGS LLC DES:PAYMENT` into Contoso Bakery is held as `holder_name`; `CONTOSO BAKERY LLC DES:VENDOR PAY` into Contoso Bakery is held as `holder_name`; `SQUARE INC DES:SQ240115` into `SQUARE ONE BAKERY LLC` still verifies (the registry is exempt);
  - repeats (§5.2): `NORTHWIND SUPPLY DES:RETURN` (held) does not make `NORTHWIND SUPPLY DES:CREDIT` a repeat; the latter is `named_payer_one_off`;
  - named transfers (T13): `ONLINE TRANSFER FROM SMITH J EVERYDAY CHECKING XXXXXX1234 REF IB0ABCD` is held as `transfer_account_designation`;
  - numbered companies (§5.2): the three rows of the §7.5 list are `numbered_company_payer`, never verified; a bare `DIRECT DEPOSIT 1234567` is `numbered_company_payer`;
  - the reviewer's controls stay as they were: `FABRIKAM FUNDING LLC DES:PAYMENT` (`financing_named_payer`), `ZELLE PAYMENT FROM CONTOSO BAKERY LLC` (`holder_name`), `FABRIKAM INC DES:PAYROLL` (`payroll_or_salary`), `SSA TREAS 310 DES:XXSOC SEC` (`personal_income`), `ONLINE BANKING TRANSFER CREDIT REF 88` (`transfer_no_counterparty`), `WIRE IN DATE 240102 TRN 123` (`wire_no_sender`).
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
- the package gate's blocked share before and after (T7), and each hold's contribution to it;
- the sizes behind T4, T11, T13, T18 and T19, and how much of `named_payer_unlabelled` would pass Q6;
- the holds the memo's rows could not measure: `payer_also_debited`, `payer_debited_as_lender`, `insurer_payer` and the released card credits held as `possible_return`;
- every row the channel gate and the holder veto demoted under 5.5, by rule;
- every credit whose `normalized_description` the street-`LN` guard changed, with its base and new decision (G7b).

### 14.3 Guard checks (hard gates)

No loan, transfer, refund or owner money becomes revenue:
- **G1:** no row decided `non_revenue` by reversal, the insurer registry, D1, descriptor proceeds, the potential registry, strong non-revenue or duplicates at the base reaches True at 5.6, except through the narrowings of §6.3 that lead to True (1, 2, 4, 5, 6 and 7), each listed.
- **G2:** no Verified row carries a financing root, read as T4 reads it (§8.1: on the payer region and the entry fields, after the posting labels are removed), except a Q7 row whose payer is a listed auto lender or a credit union under §8.7's credit-union arm (G12 checks that).
- **G3:** no row the holder test matches (§5.2, read on the payer region) is Verified by step 11's customer and invoice descriptors, steps 12 to 14, Q5 or Q6, and none is `counted_flagged`. The only rows the holder test matches that may be in True are those the registry (step 10) or a card-settlement or claim-payment form verified; the census lists them, and they join the precision sample (§14.5).
- **G4:** no row with transfer wording and no counterparty is in True.
- **G5:** no row that `match_known_payee` places in a financing group reaches True, except payout-credit entities, factoring payees and Q7's dealer funding.
- **G6:** no row whose revenue method is `direction_conflict` is in True.
- **G7:** `tools/lender_census.py` at 5.6 shows zero lender, potential-lender and flag changes on debits against 5.4.
- **G7b:** every credit whose normalized text the street-`LN` guard changed is listed with its base and new decision; none moved from a financing decision to True.
- **G8:** every fabricated negative of §14.1 passes.
- **G9:** the four-tier identity holds on every cached analysis.
- **G10:** no Verified row prints a consumer person-to-person rail, a check-deposit form, a cash, branch or ATM form, or no payer word at all; a Verified row that prints a real-time or push rail was verified by the registry (§6.1 step 9b).
- **G11:** no row that prints the pay words of Q8 (§8.1 `payroll_or_salary`) or the personal-income words (§8.1 `personal_income`) is in True.
- **G12:** every `auto_lender_dealer_funding` row's payer, read on its originator segment, is a listed auto lender, or a credit union with two or more `VHCL PURCH` credits in the statement (§8.7), and the row prints no loan, proceeds, advance or refund word.
- **G13:** no row whose payer region §5.2's numbered-company guard matches is Verified.
- **G14:** no row the channel gate closed, or that a `DEBIT CARD CREDIT` or `POS CREDIT` label names, is counted toward any recurrence pool.

### 14.4 Measured targets

These are the definition memo's and the verifiers' measurements. The census must report each one, and it must explain every deviation beyond the tolerance by a named decision of §4.

| Figure | Base (5.4) | Target |
|---|---|---|
| Corpus Verified, after 5.5 | 7.2% | about 14% or more. The card and platform fixes alone: 14.1% per the memo, 13.1% per the card verifier; the other families add more |
| Corpus $0-verified statements, after 5.5 | 1,819 | at most about 1,465; the memo's processor-gap estimate is 1,338 |
| Corpus True, after 5.6 | (7.2%, verified only) | 71.3% ± 3 points, measured on the memo's rows with every hold of §8.1 they can show (the memo's own holds gave 72.7%). Plus up to 2.3 points if the owner accepts T19 and 0.3 with T18, plus 0.8 for the funds-transfer wires; less the T5 moves and the holds the memo's rows cannot show (§14.2) |
| Corpus $0-True statements, after 5.6 | 1,819 | about 107 |
| Corpus median statement True share | 0% | about 87% |
| Corpus Verified, after 5.6 | 7.2% | 22% to 29%; the memo gives 22.3% with the rulings and 29.2% with the processor gaps |
| Corpus $0-verified statements, after 5.6 | 1,819 | between 945 and 1,281 |
| Tryout host True, after 5.6 | 13.4% | about 77% |
| Tryout host Verified, after 5.6 | 13.4% | about 26% (39.8% only if one payer's repeat wires verify) |
| Package revenue gate, corpus statements | 95.6% | about 28% to 32% (T7: 27.5% with the holds the memo's rows can show; statements with at least one held row 48.6%) |
| Non-revenue moves | — | only §6.3 and §7.11's declared moves |

The healthcare, government and auction fixes barely move the tryout host. The owner should expect its gains from the card and platform fixes and from the definition.

The memo-row figures above come from `work/spec/revision/revision_probe.py` (private). It reads the memo's 5.4 unverified rows only, proxies the rows the 5.5 fixes verify by the memo's processor-and-platform category, and cannot see debits or `non_revenue` rows. The census replaces every one of them.

### 14.5 Precision sample (before merge)

The census proves that nothing moved outside the declared paths. It cannot prove that what a new rule verifies is revenue. Before merge, an independent reviewer hand-sorts a stratified sample from the 5.6 census, digit-masked and kept in the private folder:
- about 200 Verified rows, at least 20 from each of: Q5 repeat wires; Q6 (a) repeats; Q6 (b) company form; Q6 (c) government and healthcare; §7.5 accounts-payable remittance; §7.6 public payers; §7.9 invoice wires; the card forms and payout forms of §7.1 and §7.2; Q7 (every Q7 row if fewer than 20); and the holder-test rows G3 lists;
- the 50 largest `counted_flagged` rows of the corpus, whatever their reason.

Each row is sorted as revenue, not revenue (naming which: loan, own money, refund, transfer, insurance, other) or cannot tell. The acceptance bar:
- in each Verified stratum, at least 95% of the rows are revenue, and none is a loan, an own-account transfer, owner money or a refund;
- among the 50 largest counted rows, none is a loan, an own-account transfer, owner money or a refund;
- every row that misses the bar gets a named rule, hold or registry entry, with a fabricated test, before merge, and its stratum is re-sampled.

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
  - auction vendor payments and non-dealer consignors, and pairing an auction credit with an equal same-auction debit in the applicant's previous statement (auction risk verifier R9, §7.8);
  - whether to admit AppFolio now or hold it with Buildium and Landlord Studio admitted (property evidence verifier R4, T15);
  - eCommission's commission advances.
- The transaction classification of credits, such as Heartland's `TXNS/FEES` credit classified `fee`: revenue is unaffected, and the dashboard shows a credit's revenue tag first.
- Residuals that no printed word can close, recorded for the owner:
  - an unregistered funder that prints a neutral name and a neutral entry (it is counted), including a platform advance paid through Parafin or Pipe before the ledger admits them (§7.3);
  - processor or platform capital paid out inside normal settlements;
  - a Faire retailer's refund;
  - a single-row PayPal push-to-card from a person, verified today by PayPal recurrence;
  - the bank templates that print `ACH CREDIT` on every credit, which verify a lone registry alias (§7.10 closes this for property platforms only).

## 16. Services and rollout

The owner's standing rule applies: one Opus 5.5 implementer per service, then an independent reviewer under the orchestration model policy (`docs/agent-handoffs/ORCHESTRATION-MODEL-POLICY.md`). The orchestrator checks each report's evidence before accepting it.

| # | Service | Owns | Starts after |
|---|---|---|---|
| S1 | Registry and vocabularies | §7.1 to §7.10's registry tables, truncations, `HEALTHCARE_PAYER_ALIASES`, `DEALER_FUNDING_PAYERS`, the validator (§7.4), the ledger admissions of the processors' capital products (§7.1) and of Parafin and Pipe (§7.3) | this spec's approval |
| S2 | Classifier 5.5 | §6.1 steps 3 and 5 to 14 (the channel gate, step 9b, included), statement passes 4 to 6, §5.2's holder test and numbered-company guard, §7.0 to §7.11, the T18 and T19 switches, the 5.5 tests, the version bump | S1 |
| S3 | Census tool | §14.2 and §14.3; runs on 5.4 → 5.5 before S4 starts; the §14.5 sample is drawn from its 5.6 run | S2 |
| S4 | Classifier and payload 5.6 | §6.1 step 4 (Q7), statement pass 7, §5, §8, §9, §11, `analysis/revenue.py`, `metrics.py`, `detect.py`, `serialization.py`, `batch.py`, `analyze.py`, the benchmark, the docs, the version bump | S3's 5.5 report accepted |
| S5 | Webapp serving, package, review and exports | §9.2, §10.4, §10.7, §10.8 | S4's contract (§9); may start on fixtures built from it |
| S6 | Dashboard | §10.1 to §10.3, §10.5, §10.6, §10.7's controls | the same |

- **Order:** S1, then S2, then the 5.5 census (S3), then S4, then S5 and S6 in parallel. Then the 5.6 census, both guard sets, the precision sample (§14.5), the targeted tests, the full suite at the train, and a browser check of the dashboard.
- **Merge and hosting:** the branch merges only after every review closes, the precision sample meets its bar, and the owner has read both census reports and answered OQ5 and OQ6 (without an answer, T18 and T19 ship switched off). The tryout host is not updated unless the owner asks, and its census runs read-only.

## 17. Open questions

The owner has ruled on Q1 to Q8. These are the few left.

- **OQ1. "Apply to every row of this payer."** Recommendation: a follow-up release, not this one.
  - It needs a payer identity that holds across statements and uploads. This spec defines the credit payer key (§5.2), which the follow-up would reuse. It also needs a decisions table keyed by that payer (today's decisions are per job and row), and a rule for when a later statement's row matches.
  - Shipping it inside this release would make the census unmeasurable, because a decision would move rows the rules did not.
  - T7 already cuts the gated share from 95.6% to about 28% to 32%.
- **OQ2. BNPL merchant settlements** (Affirm, Klarna, Afterpay, GreenSky, Sunbit). Should they join `PAYOUT_CREDIT_ENTITIES`, so that their settlements to the merchant are revenue rather than financing proceeds (lender spec D2)? Today they are `non_revenue`. They are rare in the corpus (13 rows).
- **OQ3. Numbered-company payers** (T11: $11.4M, 4.1% of corpus credits, 293 rows). This spec counts them in True, flagged, and never verifies them. Should they be held out until confirmed instead? That would take about 4 points off True.
- **OQ4. The deferred family items of §15.** Each one's rows stay counted and flagged (or held) until you rule. The research folder lists every item with its measured size. Two are new: pairing an auction refund across statements, and admitting AppFolio now or holding it.
- **OQ5. Claim first for an insurer's `HCCLAIMPMT`** (T18). Should a Blue plan's (or any insurer's) healthcare claim payment to a provider verify as revenue, although the insurer registry otherwise makes an insurer's credit non-revenue? Yes moves 177 rows, $908,159, in 16 statements of healthcare providers from `non_revenue` to Verified. No holds them, and the alias-escaping Blue spellings with them, for review.
- **OQ6. Third-party book transfers** (T19). Should Chase's `BOOK TRANSFER CREDIT B O <customer>` and Bank of America's `WIRE TYPE BOOK IN` from someone other than the holder be read as incoming wires, rather than as own-account transfers? Yes moves 308 Chase rows, $6.25M, in 73 statements out of `non_revenue` (into Q5's tiers and holds) and adds one invoice-citing BofA wire ($55,259.05). No keeps both as today.

## 18. Revision notes (first review, 2026-09-28)

The first independent review returned "changes needed". It simulated 48 fabricated rows against the draft (`work/spec/review/sim_review.py`, private) and found five critical and eleven important problems, plus twelve minor ones. This revision applies every critical and important finding and every minor one. The holds and sizes the review asked to re-measure were re-measured on the memo's rows (`work/spec/revision/revision_probe.py`, private; totals only).

### 18.1 Where each finding went

| Finding | What changed | Where |
|---|---|---|
| C1, Q7 verified loan and MCA proceeds | Q7 needs an auto-lender payer on the originator segment (a listed lender, or a credit union under the new credit-union arm); never on a D1 entity outside vehicle financing, a potential lender or an insurer; never with a loan, proceeds, advance or refund word; unverified dealer-worded rows are held; the four rows are negatives; G2 no longer exempts Q7 wholesale; G12 added | §6.1 step 4, §8.7, §8.1, §14.1, §14.3 |
| C2, T4 read only D11's payer name | T4 reads the payer region before D11's filtering and the entry fields; registry, payout and factoring rows are skipped; Q5 and Q6 refuse any row a hold names; re-measured at $2.1M, 402 rows, 174 statements | T4, §5.2, §8.1, §8.5, §8.6 |
| C3, card refunds released into revenue | Release needs a push-rail word, or a processor or invoice source with a payout word; a released row no form verifies is held as `possible_return` and never pooled; the two labels join the pool veto; refund tests for Uber, DoorDash and PayPal | §6.1 step 3, §6.3, §7.0, §7.11, §8.1, §14.1, G14 |
| C4, owner money, investment, rebates, insurance and pay verified | New holds `non_sale_purpose` and `insurer_named_payer`; Q5 needs no hold; Q5 and Q6 refuse the non-sale list; Q5 takes §7.9's own-account and brand-word vetoes | §8.1, §8.5, §8.6, §5.3 |
| C5, the holder test failed three ways | Read on the payer region; brand word, min(2, n) words or a digit run; a veto in steps 11 (customer descriptors) to 14, Q5 and Q6 | §5.2, §6.1, §7.5, §7.6, G3 |
| I1, numbered-company guard too narrow | The AP verifier's digits-after-prefix guard restored; prefix-less form with every province, territory and cut, or words up to a legal form; one guard for §5.2, §7.5, §7.6, Q5 and Q6; re-measured at $11.4M, 293 rows | §5.2, §7.5, T11, G13 |
| I2, "never Verified" not enforced | The channel gate, step 9b; G10 | §6.1, §7.0, §14.3 |
| I3, `COUNTER CREDIT` held as financing | Standalone `CREDIT` never read outside a payer name; the branch and card `… CREDIT` labels removed; the gate re-measured at 27.5% | §8.1, T7, §14.4 |
| I4, Q8 not exact | `PAYRL`, `BONUS`, `DIR DEP` anywhere; `EXP REIMB` held; the §7.11 test corrected | §8.1, §7.11, §14.1 |
| I5, refused public credits counted | Narrowing 1 needs a claim or provider signal; a public payer with a §7.6 veto word is held; a healthcare payer's member words are held | §7.6, §7.7, §7.11, §8.1, §8.6 |
| I6, counter-debit rows counted | Both held as `payer_also_debited`; the funder-statement test added | §5.3, §7.5, §8.1, §8.5, §8.6 |
| I7, named transfers with an own account counted | Held as `transfer_account_designation`; the round-sum hold covers named transfers | T13, §8.4 |
| I8, consumers not listed | The two `metrics["true_revenue"]` fallbacks dropped; `:2155` and `:2167` listed; the `true_revenue` mode deducts counted R-d credits | §9.2, §11, §13 |
| I9, backward-compatibility gaps | The tier-less rebuild path; today's review rules on outdated payloads; the outdated member's gate; `true_revenue_evidence` nulled and `contributes_to_true_revenue` removed in served copies | T10, §10.4, §10.7, §12 |
| I10, two owner decisions without a number | T18 (claim first) and T19 (book transfers), both behind switches that stay off until the owner answers | §4, §7.7, §7.9, §7.11, §16, OQ5, OQ6 |
| I11, "never" clauses not enforced | G10 to G14; G2 read on the payer region and entry fields; G3 on every verifying rule; the precision sample and its bar | §14.3, §14.5 |
| M1 | Government and healthcare payers read on the payer region | §5.2 |
| M2 | Repeats never count a held or direction-conflict row | §5.2 |
| M3 | "Channel family", "entry fields", `GENERIC_WORDS`, `HOLDER_NOISE` and every `categorize.py` pattern inlined | §5.2, §8.2, §8.3, §8.4 |
| M4 | `transfer_no_counterparty` before the check and branch tiers | §8.2, §8.10 |
| M5 | `_awaits_review(record, decision)` | §10.7 |
| M6 | The street-`LN` guard excludes loan-product words and `PMT`, `DISB`, `ADV` after `LN`; G7b lists credit-side moves | §7.11, §14.3 |
| M7 | `ASSISTANCE` added, read after the boilerplate is deleted | §7.6 |
| M8 | `ASSURANCE OF THECLAIMPMT` and Chase `Theclaimpmt` tests | §7.7 |
| M9 | Parafin and Pipe to the ledger; Clearent, SmartTab and Braintree capital products before their aliases; AppFolio's push shapes out of its pool, and holding AppFolio offered; cross-statement auction pairing put to the owner | §7.1, §7.3, §7.8, §7.10, §15, OQ4 |
| M10 | The recurrence pool admits only registry rows and operating-method rows | §7.0 |
| M11 | T7 in integer cents, over all posted credits | T7, §8.10 |
| M12 | Payer-less interest, dividends and rewards held as `non_sale_purpose` | §8.1 |

### 18.2 Where this revision departs from the review's wording, and why

1. **Q7's credit-union arm (C1).** The review asked that every Q7 payer be a listed lender, with CU Direct / CUDL for the credit-union form. On the memo's rows, $3.64M of the draft's $4.02M Q7 reach is a credit union's own name with the entry `VHCL PURCH` (the CUDL indirect-lending form), paid to one dealer in 15 to 18 rows a statement. Requiring the credit union itself to be listed would drop all of it, and listing credit unions one by one does not scale. The revision admits the credit-union form instead, with three guards: the payer is a credit union, the entry is exactly `VHCL PURCH`, and the statement holds two or more such credits (a member's own purchase loan is a single credit). The loan-word veto and the lender and insurer vetoes apply as the review asked. G12 checks it.
2. **Refused, not always held (C4).** The review asked that every row Q5 or Q6 refuses on a purpose word be held. The revision holds the review's own list (investment, distributions, dividends, equity, contributions, owner money, intercompany, sweeps, rebates, interest, grants, claims, insurer words, reimbursements, bonus, pay, repayment) and the rest of §7.9's clearly non-sale purposes. It refuses verification but still counts a short list of words that ordinary sales also print: `SETTLEMENT` (an unregistered processor prints it), `TAX`, `FEES`, `SUBSCRIPTION`, `DISCOUNT`, `COMMISSION`, `COMPENSATION`, `EXPENSES`, and, in the entry fields only, floor-plan and equipment words. Holding them would take real sales out of True, and `TAX` would also hold the tax-preparer disbursements the owner has not ruled on (§15). These rows get their own reason, `named_payer_purpose_refused`, so the census shows them. `DISTRIB` excludes `DISTRIBUTORS` and `DISTRIBUTING`, and `OWNER` excludes owner-operators; the probe found a distributor's payments caught by the bare root.
3. **The holder test's reach (C5).** The review asked for the veto in every verifying rule of steps 10 to 14. The revision applies it to step 11's customer and invoice descriptors, steps 12 to 14, Q5 and Q6, but not to the registry (step 10 and recurrence) or to the card-settlement and claim-payment forms. Their payer is the platform, processor or insurer, and their rows print the merchant's own name as the payout's recipient. BMO prints `DIRECT DEPOSIT DOORDASH <store> MSP/DIV`, and the store is the holder, so the veto would hold every such payout. G3 lists any holder-matching row those paths verify, and the precision sample reads them.
4. **The first-distinctive-word test (C5).** The review's wording matched the holder's first distinctive word anywhere in the payer region. That would hold a supplier that shares a trade word with the holder (`FABRIKAM PLUMBING SUPPLY` paying `SAMPLE PLUMBING LLC`). The revision compares the payer's first distinctive word with the holder's, as §7.9's brand-word veto does. It skips common name-starters (`FIRST`, `UNITED`, `PREMIER` and the like), and never runs on a channel that prints no payer. Run unrestricted on the memo's rows, the test matched only bank and product words on check deposits (`COMPTE`, `BANK`) and no real affiliate, so those words are now holder noise.
5. **Push rails (I2).** The review asked that a row with a person-to-person rail verify only by a registry payout form. The revision closes the consumer rails completely, and lets the real-time and push rails (RTP, FedNow, Visa Direct, MC Send) verify through the registry only, by its form, its alias with context or its recurrence. §7.2 already decided that `RTP CREDIT AMAZON COM` verifies by recurrence, and Q4 names people paying people, not a platform's payout on a real-time rail.
6. **`DIRECT DEPOSIT` as pay wording (I4).** The review asked for `DIR ?DEP` anywhere except BMO's leading template. The revision takes `DIR DEP`, `DIRDEP` and `DIRECT DEP` anywhere, but the whole phrase `DIRECT DEPOSIT` only as an entry description. BMO and ATB print it as their channel template, and §5.2 lists it among the template prefixes.
7. **Bank interest (M12).** Held as `non_sale_purpose`, not named `non_revenue` under T5. Holding it is reviewable, adds no new non-revenue move to account for under §6.3, and takes it out of True all the same.
8. **`CREDIT` in T4 (C2, I3).** The review asked that a standalone posting `CREDIT` never be read on payer-less rows. The revision extends that to the entry fields (`DES:CREDIT` is a posting word too). It keeps a whole-word `CREDIT` as a root inside a payer name, next to another name word, so `UNITED AUTO CREDIT` and a credit union still read as financing.
9. **T18 and T19 (I10).** The review asked for explicit T numbers with measured sizes. The revision keeps the draft's direction as its recommendation, and adds the verifiers' fallback in full. It builds each behind a switch that ships off unless the owner says yes (§16), so neither non-revenue move happens on this spec's word alone.

### 18.3 What the re-measurement changed

| Figure | First draft | Revised | Source |
|---|---|---|---|
| T4 financing-named hold | $5.0M, 954 rows, 282 statements (whole row) | $2.1M, 402 rows, 174 statements (payer region and entry fields) | `revision_probe.py` |
| Numbered-company payers (T11) | $11.1M, 183 rows | $11.4M, 293 rows | the same |
| Named transfers held for an account designation (T13) | none (the memo held all) | $1.18M, 1,473 rows | the same |
| New holds: insurer name; non-sale purpose (public part) | none | $1.06M; $1.28M ($0.16M) | the same |
| Q7 reach | $3.7M in 4 statements (first draft's words; its arms reached $4.02M, 11 statements, on the memo's rows) | $4.02M, 214 rows, 11 statements: listed lenders $0.37M (8 statements), the credit-union arm $3.64M (4 statements); nothing lost | the same |
| Corpus True, memo rows | 72.7% (memo holds) | 71.3% (every hold the rows can show) | the same |
| Package gate at 10% | 24.6% | 27.5% measured; 28% to 32% expected | the same |
| Statements with a held row | 39.9% | 48.6% | the same |

## 19. Owner review (2026-09-28)

The owner approved this spec with every recommendation:

- **OQ1:** payer-wide review ("apply to every row of this payer") is a follow-up release, not this one.
- **OQ2:** BNPL merchant settlements (Affirm, Klarna, Afterpay, GreenSky, Sunbit) join `PAYOUT_CREDIT_ENTITIES`: their settlements to the merchant are revenue, not financing proceeds.
- **OQ3:** numbered-company payers are counted in True, flagged, and never verified (T11 as written).
- **OQ4:** the deferred family items of §15 stay counted and flagged (or held, as §15 says) until the owner rules on each.
- **OQ5 (T18): yes.** `HCCLAIMPMT_CLAIM_FIRST` ships ON: an insurer's healthcare claim payment to a provider verifies.
- **OQ6 (T19): yes.** Third-party Chase book transfers and BofA `WIRE TYPE BOOK IN` are read as incoming wires and pass through Q5 and every hold of §8.1.

## 20. Implementation amendments (2026-09-29/30)

The implementation reviews decided these behaviors, which differ from or add to the text above. Each line names the section it amends and the commit(s) that carry it; `docs/transaction-classification.md` ("Review decisions (2026-09-29)") states the same decisions for the code's readers. "A3 review" is the commit that adds this section (418c5f9), "A3 review round 2" is 3dca290, "A3 review round 3" is 851093f, "A3-G" (the redrawn largest-counted stratum's misses) is 1ce3624, "A3-G refinement" is f59db7f, "A3-G review" is a998228, "A3-G re-review" is 75906d2, "A3-G re-review 2" is 35457ff, "A3-G re-review 3" is 66645fe (after b6b5f48, the fixtures' neutral amounts), "A3-H" (the Verified strata's misses at s56c) is bf54caf, "A3-H review" is 6491643 (with 4d1da1b, the registry comment), and "A3-H review 2" the commit that follows it. The final whole-branch review's fix wave (2026-09-30) is 8021847 (the reader fixes), 59c5335 (the lender side and the census) and 69486cb (the webapp); the commit that carries these lines is "FW-4" (1377e3f), and "FW re-review" is the commit that follows it (the re-review of the fix wave).

- **Glued dates** (§7.0, §6.1 step 9b): a date glued to a row's first word never changes its reading: the revenue text strips it, the channel gate fails closed on a glued or dated prefix, and every card form's boundaries, refusals and required words read through it. 3504281, a5e6f90, 94334b5, 65440df, 8d70ba5.
- **The holder's name is never a payer** (§5.2): the receiver field's value (the holder's name) never names a payer, an operating source or a wire; an incoming wire's beneficiary never names a source. 3bde85e, 58720e6, 213586f.
- **Own-account transfers** (§6.1 step 9, §7.11): a transfer leaves `non_revenue` only on a distinctive payer word; account adjectives stay own-account. a9b4754, 58720e6.
- **Wire vetoes** (§7.9): the vetoes also read a wire glued to its reference and a wire that cites an invoice. a9b4754.
- **The recurrence veto's holder-word exemption** (§7.0) reads only on store-name platforms. 93185ad.
- **Pass 6's counter-debit guard** (§7.5) reads a card purchase's merchant, never its city. 071215a, 151f898. Superseded for card purchases by the final review's line below: pass 6 now leaves a card purchase out.
- **The card-purchase hold rule** (§8.1 `payer_also_debited`): a card purchase at a merchant that shares the payer's word never holds the payer; a card-form debit the classifier names as a lender still counts for `payer_debited_as_lender`. 8cb733b.
- **BNPL consumer credits** (§19 OQ2, §7.11): a buy-now-pay-later return, withdrawal, refund or card credit keeps its 5.4 reading; the OQ2 ruling covers merchant settlements only. 2652ba1, 9f3d954.
- **Direction conflicts** (§6.1 step 2, §7.0, §10.7, T7): a direction conflict is never lifted, grouped, counted or made a repeat by any pass; one an analyst has confirmed or rejected no longer gates the statement's review. 167c83d, 75eae34.
- **Bare transfers** (§8.2): field labels, SEC codes, reference labels and their values, account words and an account description never name a transfer's counterparty; such a transfer is `transfer_no_counterparty`. 167c83d, 213586f.
- **The $1 floor** (§7.0, §7.8, §8.10, §5.3): absolute; a posted credit under $1 is never verified, never counted and never a repeat, whichever rule read it. It is held as `non_sale_purpose` (§5.3's table has no micro-deposit code); one a rule verified is held by pass 7's last step (method `micro_deposit_floor`); a held credit keeps its first hold; a non-revenue credit stays non-revenue. 167c83d, 75eae34.
- **Owner money** (§7.5, §8.1 `non_sale_purpose`): a credit from a brokerage, investing or crypto-exchange platform (the registry's `OWNER_MONEY_PLATFORMS`) or a consumer savings or investing originator is held; `BROKERAGE`, `SECURITIES` and `WEALT…` join the investment words, except on a row that prints §7.5's accounts-payable wording (counted, never verified). 167c83d, 3d6fd9a, 213586f.
- **§15 deferred sources** (§15, §19 OQ4): their payers (the registry's `SECTION_15_DEFERRED_PAYERS`) stay counted and flagged, never verified by Q5 or Q6, never a Q5 or Q6 repeat; on a wire or ACH row their reason is `named_payer_purpose_refused`. 167c83d, 213586f.
- **Rows left to their family** (§7.1, §8.5, §8.6): Q5 and Q6 never verify a row the operating registry names or a NET SETTLE row; a waiting processor's bare word takes no row from them. 167c83d, 213586f.
- **Round-sum repeats** (§8.4): a sender printed without FROM after a person-to-person rail, and a named transfer's counterparty printed without FROM, take the holder test and the round-sum repeat (`p2p_round_repeat`); rail, layout, city and bank words are never a sender. 167c83d, 213586f, ad2c69d, 5997234.
- **VIREMENT** (§8.4, §8.2): a person-to-person rail only in its Interac forms; any other `VIREMENT` is transfer wording. 2309bc1.
- **ANNULE** (§6.1 step 3): a cancelled French transfer (`ANNULE` and its forms) is a reversal. ad2c69d, d168fb3.
- **Quebec numbered companies** (§5.2, T11): the `NNNN-NNNN` form, also after a leading date, is a numbered-company payer (counted, never verified), keyed by both numbers. e0f4747, d168fb3, 5997234.
- **Q7's §8.1 holds and Suncoast** (§8.7, §6.1 step 4): Q7 refuses a row whose wording a hold of §8.1 names (pay, personal income, non-sale purpose, possible return, insurer or claim, floor plan), reads its lender without the receiver field, and keeps its lender's name on the record; Suncoast Credit Union is not a listed lender and verifies only through the credit-union arm. ab2870c.
- **Wires with no sender** (§8.2, §8.5): a wire's channel and layout words (`INCOMING`, `FEDWIRE`, `WIRE`, `TRANSFER`, `CREDIT`, `CHIPS`, `SWIFT`, `BOOK` …) never name a transfer's counterparty, and a transfer that prints wire wording and names no counterparty is a wire with no sender (`wire_no_sender`). fdbdb2a.
- **The SBA's cut name** (§7.11): a payer region that is exactly `SMALL BUSINESS`, or `SMALL BUSINESS` with a leading cut of `ADMINISTRATION`, on an N1 wire or an electronic-payment row, is an SBA disbursement (`sba_disbursement_credit`, financing proceeds). fdbdb2a.
- **Currency conversion** (§8.1 `non_sale_purpose`): a credit that prints foreign-exchange or currency-conversion wording and names no payer beside it is the holder's own money converted, held; the wording never names a counterparty. The statement's own bank printing its name right before the wording names no payer: its whole normalized name, and the registry's `STATEMENT_BANK_PRINTED_NAMES` forms when the bank field contains one of that entry's bank words (RBC: a bank field containing `ROYAL BANK OF CANADA`, `RBC ROYAL BANK`, the whole word `RBC` or `BANQUE ROYALE` reads `ROYAL`, `RBC`, `ROYAL BANK`, `RBC ROYAL BANK` and the `BANQUE ROYALE` forms; a bare `ROYAL BANK`, as in the Royal Bank of Scotland's name, is no marker). Another name word beside the wording (neither a legal form nor an article) names the payer on any row. A currency-exchange company named by the wording and a company form (`LLC`, `INC`, `CORP`, `CO`, `LTD`, `INTERNATIONAL`, `INTL`) is a payer only on an originator field: an ACH originator (the name before `DES` or `CO ENTRY DESCR`, or after `ORIG CO NAME`) or a wire's labelled sender. Elsewhere the company form names nobody and the credit stays held (`INTL FOREIGN EXCHANGE DEPOSIT`, `FX CONVERSION LLC <n>`, BMO's `INCOMING WIRE PAYMENT … CA FOREIGN EXCHANGE LTD`). fdbdb2a, A3 review, A3 review rounds 2 and 3.
- **Title firms** (§8.1 `non_sale_purpose`, §8.5): a title firm named on the payer region (`TITLE` beside a title-firm word or a legal form, or a national title insurer) pays property-closing proceeds, held on wires and ACH alike; §8.5's `wire_named_sender` no longer covers title companies. Its credit whose purpose cites the holder's fee (a commission, an origination or broker fee, an invoice, consulting, services rendered) takes its normal reading; the purpose is a wire's OBI, RMR, PMT DET, RFB or URI field (`ORIG FEE` inside one is purpose wording, never an originator label), Santander's REF field (its layout prints `ACCT <n> <originator> REF <purpose>`), an ACH entry or a memo; any other REF field is never read (on the Fedwire layout it is the sender's bank reference; Bank of America's `SERVICE REF` is its own reference). fdbdb2a, A3 review, A3 review round 2.
- **Senders printed after the wire's label** (§5.2, §8.5): the layouts that print the sender right after their label with no originator label (BMO, TD Bank, Wilson & Muir, Capital One, Scotiabank, SECU, and the reference-then-sender form) name that sender; a sender whose only words are a reference token and a legal form names nobody and stays `wire_no_sender`. fdbdb2a.
- **The wrap-tolerant financing root** (§8.1 T4): every wire sender's region, labelled or read after the label, is also read across its word joins, among its first six words with no digit. A join counts only when its two words together spell a financing word (`FINANCIAL`, `FINANCE`, `FINANCING`, `FUND`, `FUNDS`, `FUNDED`, `FUNDING`, `CAPITAL`, `LOAN`, `LOANS`, `LEND`, `LENDER`, `LENDERS`, `LENDING`, `MORTGAGE`, `ADVANCE`, `ADVANCES`, `ACCEPTANCE`, `SERVICING`, `SERVICER`, `LEASING`, `PORTFOLIO`) or a prefix of one of five letters or more, so the join falls inside that word: a line wrap's split (`F INANCIAL`, `SERVICIN G`, `FUN DING`, `LO AN`, `MORT G`: held as `financing_named_payer`). Two words that spell none never make a root (`SERVICE REPAIR`, `SOLO ANALYTICS`, `ROYAL ENDEAVORS`, `ALLEN D`, `HELEN DE`, `GLEN DI`, `CAPT L`, `SERVICE RX` keep their reading). A Fedwire sender's city and state spell no financing word either (`GLEN DE`, `LAMORT GA`), so no city and state skip is needed; A3-G review removed round 3's, which read a company form `CO` as Colorado (`B/O NORTHWIND F INANCIAL CO` is held). Person names that do spell one are held and listed for the owner (`LEN D`, `MORT G`, `LO AN`, `AD VANCE`). §7.9's veto keeps its own six-word run for verification. fdbdb2a, A3 review, A3 review rounds 2 and 3, A3-G review.
- **A glued CRED** (§8.1 T4): §7.9's word-end `CRED` arm, with a glued letter on its left, read on the payer's name only, as the whole-word `CREDIT` is: a word of the payer name that ends in `CRED` (a credit provider's glued name) holds the credit as `financing_named_payer` when the payer region is a payer's name field (a wire's sender, an ACH originator, a transfer's sender after `FROM`) or prints a company form (`FABRICRED INC EDI PYMNTS`, `ACH CREDIT FABRICRED LLC`). It is never read on an entry, description, `IND` or `ID` field, or on a row whose payer words are neither (`ACHCRED <n>`); the whole word `CRED` and the whole words `SACRED` and `ACCRED` are no root, and every other glued `…CRED` name is. A3 review, A3 review rounds 2 and 3.
- **Canada's income-tax refund** (§7.11 T5): the Canada Revenue Agency's income-tax refund direct deposit (`CANADA RIT`, `CANADA RIF`, bilingual `CANADA RIT RIF`) joins the tax-refund forms of the strong non-revenue rule, so it is `non_revenue`. Word boundaries are strict (`CANADA RITE …` is no refund), and the form starts the payer, after the posting words `DIRECT DEPOSIT`, `DIRECT DEP`, `DEPOSIT`, `DEP`, `EFT` (`EFT CREDIT`, `EFT DEPOSIT`) or `PAY`/`PAYMENT` only (A3-G review: `<name> CANADA RIF PAYMENT` is a payer's name). A3-G re-review: the form is read after the classifier's revenue text and template prefixes (`revenue_text`, `_strip_revenue_template`: `MISC PAYMENT`, `PREAUTHORIZED CREDIT`, `ELECTRONIC DEPOSIT FROM` …), then after a glued or spaced date, `GC` (Government of Canada), `ELECTRONIC DEPOSIT`, `MISC PAYMENT` and `PAYMENT FROM` as well as the posting words above, so `MISC PAYMENT CANADA RIT`, `PAYMENT FROM CANADA RIT`, `GC DIRECT DEPOSIT CANADA RIT` and `0102DIRECT DEPOSIT CANADA RIT` are refunds, while `FABRIKAM LIFE CANADA RIF PMT` and a Zelle sender named so are not. The CRA's benefit, credit and payment forms (`CANADA GST TPS`, `GST CANADA`, the child and other benefits, a government paying a supplier) are unchanged and wait for the owner. A3-G, A3-G review, A3-G re-review.
- **A wire a bank originates** (§8.1 T4, §8.5): a wire whose originator field reads as a bank is held as `financing_named_payer`: money a bank sends on its own behalf is more often loan proceeds or its own funds than a sale. Only the originator field is read (never the sending or receiving bank field, nor the text after it). Two arms:
  - *by form:* the originator prints `BANK`, `BANCORP`, `CREDIT UNION` or `FEDERAL SAVINGS` (so `BANK N A` and `SAVINGS BANK`), never a bank's merchant-services, bankcard, processor or settlement form (`MERCHANT`, `MERCH`, `MERCH SVCS`, `BANKCARD`, `CARD SERVICES`, `PAYMENTECH`, `PROCESSING`, `SETTLEMENT`, `STLMT`), never a food or blood bank, and never a company whose name holds the word: a company form (`LLC`, `INC`, `CORP`, `CO`, `COMPANY`, `LTD`, `LIMITED`, `PLC`, `PARTNERS` …) counts only as the bank's own, right after its bank word, after `OF <place>` (up to four words) or its own form words (`PUBLIC`, `CO`, `N A`) (`<X> BANK LTD` and `<X> BANK PUBLIC CO LTD` are banks; `LEFT BANK BAKERY LLC` and `BANK STREET PARTNERS LLC` are not);
  - *the sending bank itself:* the originator's letters and Bank of America's `SND BK` field's letters, spaces removed (so a line wrap's `BA NK` reads `BANK`), where one starts the other, the shorter keeps eight letters or more, and the originator prints no company form (`ORIG SUMMIT ROOFING LLC` with `SND BK SUMMIT` is counted).
  A3-G refinement: a bank-by-form originator that names the ultimate originator after a relay label (`ORG`, `B/O`, `ORIGINATOR`, `ORIG CUST`, `BY ORDER OF`; never the purpose's `ORIGINATOR TO BENEFICIARY` or `ORG TO BNF`, A3-G review; its account number and a SWIFT line number skipped, up to `OGB` or the next field) only relays: that customer is the wire's sender, read normally (a company that wires twice verifies by Q5), so only an originator equal to the sending bank, or a bank that names no customer, is held. A3-G re-review: a form word that is the address's state is never a company form, in the bank-by-form reader and the sending-bank arm alike: `B/O NORTHWIND BANK DENVER CO 80202 US` and a Fedwire `B/O NORTHWIND BANK LAS VEGAS NV` are banks, a Fedwire `B/O SAMPLE CREDIT UNION BOULDER CO` a credit union, and such a bank's relayed customer is the sender. A3-G re-review 2: `CO` or `NV` is the state only when a ZIP or the country code (`US`, `USA`) follows it, in the region or in the row's text right after it, or when it ends a Fedwire or CHIPS `B/O` field's city and state (the row starts `FEDWIRE CREDIT` or `CHIPS CREDIT` and its originator label is `B/O`). At the end of any other field it is a company form: Bank of America's `ORIG` field never takes the region-end reading, nor does Chase's book-transfer `B O`, so `ORIG:LEFT BANK TRADING CO`, `BOOK TRANSFER CREDIT B O WEST BANK OIL CO REF …` and `ORIG:BANK STREET HOLDINGS NV` are companies, counted, and `ORIG:NORTHWIND SUPPLY CO` with `SND BK:NORTHWIND SUPPLY` prints a company form, so it is no sending bank. The wire's originator label takes the relay label's guards too (`ORG` and `ORIGINATOR` never before `TO BNF` or `TO BENEFICIARY`), and that phrase ends an originator field, so `WIRE TRANSFER INCOMING NORTHWIND SUPPLY LLC ORG TO BNF INFO 1234` reads `NORTHWIND SUPPLY LLC`. A3-G, A3-G refinement, A3-G review, A3-G re-review, A3-G re-review 2.
- **Bank of America's `WIRE TYPE BOOK IN`** (§7.9 N1, §7.11 T19): its originator follows `ORIG`, as on `WIRE TYPE WIRE IN` (a SWIFT 50F line number printed with its slash dropped), so the owner's T19 yes reads it as an incoming wire. On the wire channel, a sender read as bare channel words (`WIRE`, `TRANSFER`, `BOOK`, `CREDIT`) names nobody: `wire_no_sender`. A3-G refinement.
- **The holder's receiver name** (§5.2, §8.1 `holder_name`): when the statement's account-name field names nobody (no company form and no person's name: a product name or an empty field), the names the statement's own incoming receiver fields print (`INDN`, `IND NAME`, `RECEIVER NAME`) on credits from two distinct originators or more (A3-G review: a receiver constant across payers is the holder; a name one platform prints, such as a rent platform's tenant, is its customer; A3-G re-review: originators are compared by the payer's first distinctive word, the classifier's grouping word, or the payer key where it holds none, so `SAMPLE RENT PAY` and `SAMPLE RENT PAYMENTS` are one originator), with two words and eight letters or more, naming no bank and holding a word that is no product, noise or generic word, are the holder's too. They are read by the holder hold only, and match a payer when the two names run together and one starts the other with twelve letters or more (a receiver field and an originator field cut one name at different widths); never to verify anything. They are read only on a classified wire layout (an incoming-wire label or a third-party book transfer; never the word `WIRE` printed in an ACH entry, A3-G review) or a transfer or person-to-person row (Zelle, Venmo, an online, mobile, book or internal transfer; never a push or real-time rail), where the holder moves its own money, never on an ACH, card, processor or marketplace settlement (a platform prints the store's own name as its payer) nor on a row an earlier rule verified on sale evidence (a card settlement, a platform payout, an accounts-payable remittance, a public payer). A holder name read from the account-name field keeps its full reach. A U.S. Bank `WIRE CREDIT REF<n> <sending bank> <city> <ref>` prints only its sending bank after the reference: it names no sender. A3-G refinement.
- **SWIFT field 50F line numbers** (§5.2): a wire originator's leading line number printed with its slash (`1/`, `2/`, `3/`, right after `ORIG`, `ORG`, `ORIGINATOR`, `B/O` or `BY ORDER OF`) is never part of the name: the normalizer drops it, where the slash still shows, so the holder test, the payer key and the SBA cut-name rule read the name itself. A name that starts with a number keeps it (`ORIG:2 NORTHWIND BAKERS LLC`, A3-G review). This amends §7.11's street-`LN` line: the `LN` guard is no longer "the only normaliser change"; the 50F strip is a second one, and it too moves `normalized_description` (credits and debits alike), so G7 and G7b read it as they read the `LN` guard. A person-to-person row that prints `ORG` before a slash-form token loses the token too (`ZELLE TO ORG 1/A SAMPLE` reads `ZELLE TO ORG A SAMPLE`), which is negligible and recorded for the owner. A3-G, A3-G review, A3-G re-review.
- **The holder's cut name** (§5.2 holder test): a sender that is a word-by-word prefix of the holder's normalized account name, whose last word is a proper prefix of the holder's word there, is the holder when it keeps two whole words before the cut or twelve letters in all (a single common word never matches); held as `holder_name`. A3-G.
- **Personal trusts** (§8.1 `non_sale_purpose`; revises the A3 call that personal trusts stay counted): a credit whose named sender is a personal trust is held as owner money. The sender (a wire's originator field, or the sender it prints right after its label, before the digit cut; the payer region on any other row) prints `TRUST`, `TRST`, `TTEE`, or `TR` after a trust adjective (`REVOCABLE`, `REV`, `LIVING`, `FAMILY`, `FAM`, `IRREVOCABLE`, `IRREV`), after one to five name words. A plain `TRUST` with no adjective needs two name words and never reads a person-to-person row (whose sender field also prints the sending bank). A3-G review: a personal trust needs all of (a) the trust form ends the sender's name: only its agreement and date words (`DTD`, `DATED`, `U A`, `UAD`, `UTA`), a date, a number, a PO box, the country or the trust's beneficiary after `FBO` may follow it, or, on a wire's originator field, an address ending in a US state code (`IN GOD WE TRUST ROOFING`, `... TRUST ACCOUNT` and a street named `TRUST RD` are none); A3-G re-review: that address holds only place words, city words, a two-letter state, a ZIP and a country code, never a business, lawyer, company-form, institution, `ACCOUNT`, `SERVICES`, `DEPT`, `OFFICE` or trade word (A3-G re-review 2: a finite list of trade and institution words, `CUSTODY`, `CUSTODIAN`, `ADMINISTRATOR` and `ADMINISTRATORS` among them, and at most 3 address words before the state, counting only the address's own words, never the agreement, date, PO box and country words, a number or reference token, a street type or an initial (`… TRUST U/A DTD PO BOX <n> <city> <state>`, `… TTEE <name> <initial> <name glued to a street number> AVE <city> <state>` and `… REVOCABLE TRUST UAD US/<two-word city> <state>` stay held; A3-G re-review 3: two or more single letters in a row that join into a company form, the classifier's (`L L C`, `L P`, `I N C`, `C O` …) or `PA` and `PC`, reject the address, so a dotted `TRUST L.L.C.`, `L.P.`, `P.A.` or `P.C. 123 MAIN ST` before its city and state is a company, counted, on the Fedwire and Chase layouts alike, while initials that join into none keep their skip, and a lone `PA` stays Pennsylvania; `TRUST 1STOP …` and `TRUST GARDEN PROS …` stay held within the cap, recorded for the owner), so `TRUST CUSTODY`, `TRUST ADMINISTRATORS`, `TRUST LANDSCAPE` and a four-word tail stay counted, while a three-word city keeps a personal trust held; a city whose name holds a banned word, such as `FEDERAL WAY WA`, leaves a family trust counted, the safe direction, recorded for the owner), so `TRUST ACCOUNT`, `TRUST SERVICES`, `TRUST DEPT`, `TRUST IOLTA`, `TRUST LLC` and `NORTHWIND SAMPLE TRUST ROOFING` before `SAMPLEVILLE WA 12345 US` stay counted on the Fedwire and Chase layouts; (b) the words before it read as a person's name: no business, institutional or benefit word (`REALTY`, `PROPERTIES`, `HOLDINGS`, `INVESTMENTS`, `HEALTH`, `WELFARE`, `PENSION`, `BENEFITS`, `FUND`, `UNION`, `LOCAL`, `PLAN`, `CARPENTERS`, `ANNUITY`, `BANK`, `TITLE`, `ESCROW`, `ACADEMY` …, and the classifier's holder-noise words) and no company form; (c) no bank's or trust company's form right after the trust word (`TRUST NA`, `N A`, `FSB`, `BANK`, `COMPANY`, `CO`) and no lawyer's or client trust account (`ESQ`, `ATTORNEY`, `LAW`, `LEGAL`, `IOLTA`, `IOTA`, `IOLA`; A3-G re-review: read across the whole sender, before or after the trust word). Held is review, not exclusion. A3-G, A3-G review, A3-G re-review, A3-G re-review 2, A3-G re-review 3.
- **A freight factor's payouts** (§8.9, the factoring table; the lender-scope ruling of 2026-09-24: factoring payouts are revenue, counted and flagged, never verified): the registry's `FACTORING_PAYOUT_PAYERS` names factoring payers that the true-revenue pass alone reads, in the spelling the statements print (A3-H: one freight-factoring provider, confirmed by web research; the registry entry carries its name and evidence). A credit from one, on any channel, is `counted_flagged` / `factoring_payout` after the holds, and Q5 and Q6 never verify it nor count it toward a repeat. A3-H review: a factor is never verified by any path: a credit an earlier rule verified (an invoice-purpose wire, an accounts-payable remittance descriptor) leaves verification (method `factoring_payout_payer`, its reason naming the overruled rule) and is `counted_flagged` / `factoring_payout`. Its alias is read only in the payer region (the ACH originator or the wire sender), which must be the alias followed only by company forms: a longer name that starts with it (`<alias> FOR PETS LLC`, `<alias> CLEANING LLC`) or another payer's purpose citing it names another payer, read normally. A3-H review 2: after the alias the payer region may also print a company form glued to its last word (`<alias>LLC`), a `DBA` tail (the factor's trade name), an entry word that falls into the region on a layout with no entry field (`PAYMENT`, `PMT`), a date or a number, and, on a B/O field (Fedwire, CHIPS, Chase's book transfer), the sender's address after the name or its company form: place words ending in a US state code, at most three of the address's own (the personal-trust rule's place reading), its ZIP and country; a trade word or a fourth address word is no address. The entity prints its apostrophe both ways, so the table holds both spellings; Chase's 14-character cut of the name is left unread (the 16-character cut reads). A factor claims its row as a factoring payee does (§8.1: only the insurer, possible-return, pay and benefit holds read it), so a financing word in its trade name holds nothing. The table is not the lender ledger: the ledger's factoring group renders `FACTORING_ALIASES`, a payee group that also reads debits and carries the factoring flag, so admitting the payer there waits for the owner (G7). No debit, lender or flag reading moves. A numbered `SCHEDULE <n>` purpose alone names no factor (construction pay applications print schedules too). A3-H, A3-H review, A3-H review 2.
- **An insurer's premium-coded credit** (§8.6 Q6c, §8.1's healthcare member words): a healthcare, insurer or health-plan payer (`HEALTHCARE_PAYER_ALIASES`, an insurer's name, or its `INS` abbreviation on the payer region) whose entry field prints a premium code (`PREM`, `PREMIUM`, the Chase layout's glued `PREMSEC`) is a commission or a premium refund the text cannot tell apart, never a claim payment: Q5 and Q6 refuse it as proof, and it is `counted_flagged` / `named_payer_purpose_refused`, and on such a row a premium word no longer holds it with §8.1's healthcare member words (member, subscriber and reimbursement words still do). A3-H review: the premium code is read only in the entry field the layout prints (Bank of America's `DES`, Chase's `CO ENTRY DESCR`); a row that prints no entry field keeps its reading (a healthcare payer's `PREMIUM` there stays held with the member words). A `COMM` or `COMMISSION` word in the entry keeps the entry's reading even beside `PREM`. Government payers' premium forms are unchanged: a government payer (the public-payer patterns: a state, county or federal payer) and a public health program (Medicare and its administrative contractors, Medicaid, TRICARE, VA) keep their reading. Earlier holds and non-revenue rules keep their precedence: a `PREM REFUND` the reversal rule reads stays `non_revenue`, and an insurer named `INSURANCE` keeps `insurer_named_payer`. A3-H, A3-H review.
- **Consumer entries** (§8.6 Q6 (a) and (b); final review I1): a PPD or WEB entry is read only in the SEC code's own slot: Chase's `SEC <code>` (a glued `…SEC <code>` split first), the code printed right before its `TRACE` or `ID` field when a wrap drops the label, the code Bank of America prints after the company id or at the row's end (`CO ID <id> PPD`, `ID <id> PPD`), and a layout's `ACH <code>`. It is never read in a name or receiver field: each receiver field's value is removed first, up to the next `CO ID`, `TRN`, `TRACE` or `SEC` field, never at a code word. A holder or a payer named with `WEB` (`CONTOSO WEB STUDIO LLC`, `NORTHWIND WEB DESIGN LLC`) no longer refuses Q6's repeat or company-form verification. The corpus moved 0 rows. 8021847.
- **One receiver vocabulary** (§5.2; final review I2): every receiver-field vocabulary of the classifier and the pass is built from one tuple (`analysis/description_text.py`: the name labels `INDN`, `IND NAME`, `RECEIVER NAME`, `RECV NAME`; the field labels add Chase's `IND ID`), so `RECV NAME` is a receiver field everywhere and the holder's name printed there never names an operating source or a payer (the `SQUARE ONE BAKERY` probe). The one tuple also widens the debit-side D6 reader (`_row_before_receiver`, `_RECEIVER_NAME_FIELD`), which now cuts a debit at `RECEIVER NAME` and `RECV NAME` too (re-review N2): measured, 0 of 676,525 debits moved. The corpus moved 0 rows. 8021847.
- **Short healthcare aliases** (§5.2, §8.6 Q6c; final review I3): a healthcare alias of five letters or fewer (`WPS`, `UHC`, `VPAY`, `AETNA`, `CIGNA`, `OPTUM`, `ZELIS`, `VA CCN`) and `ANTHEM` name a healthcare payer only as the whole payer name: before the alias only reference tokens, generic words and health-plan words, after it nothing, a reference token, a company form, a health-plan word (`HEALTH`, `HEALTHCARE`, `HLTH`, `PLAN`, `INS`, `INSURANCE`, `CLAIMS`, `HCCLAIMPMT`, `BLUE`, a `BCBS` form, `LIFE`, `BENEFITS`, `COMMUNITY` …) or another healthcare alias, after which the plan's name may run on (`UHC PLAN OF THE <place>`). `ANTHEM ROOFING` and `WPS INDUSTRIES` are other companies (`named_payer_one_off`). A longer alias keeps the registry's token read. The corpus moved 0 rows (no verified row). 8021847.
- **The store-name exemption's financing entry** (§7.0; final review I4, amends the S2.4 line above): a veto word that is the whole entry field, or forms it alone with generic words, reference tokens, company forms and the platform's own words (`DOORDASH INC DES:CAPITAL`, `DES:CAPITAL ADVANCE`, `DES:LENDING PAYMENT`), is the platform's own financing wording, never the holder's store name, so a holder named `… CAPITAL …` no longer lifts it: it is held as `financing_named_payer`, as for any holder. A store name that holds the holder's word (`DES:<store> CAPITA`) keeps the exemption; the 138 corpus rows it exists for did not move. 8021847.
- **Pass 6 and card purchases** (§7.5, §6.2 pass 6; final review I5): pass 6 leaves out a card purchase the classifier names as no lender or financing payee (`_debit_word_reading`'s card flag), as pass 7's `payer_also_debited` hold does (8cb733b): an accounts-payable remittance from a customer the business also buys from by card stays verified. A card-form debit the classifier names as a lender still counts. The corpus moved 0 rows. 8021847.
- **Q7's receiver-free read** (§8.7, §6.3, §6.1 step 4; final review M9): a declared move out of `non_revenue`: Q7 reads the strong non-revenue patterns on the row without the receiver field's value, so a holder named `… LOAN …` never stops a listed lender's dealer funding (`CU DIRECT DES:DEALER PMT`), where step 9's whole-row read would decide it `non_revenue`. Q7's insurer check now reads step 5's lookup text (a glued `HCCLAIMPMT` split from the name before it). The corpus moved 0 rows. 8021847.
- **A factor's connector words and the trust's trade words** (§8.9, §8.1; the final review's [A3H-m1] and A4): `FOR`, `OF`, `AND` and `THE` after a factor's alias are never address words, so a B/O `<alias> FOR PETS <city> <state>` is another payer; the personal-trust reader's trade words drop `PIZZA` (a banned statement literal) and add `DELI`. The corpus moved 0 rows. 8021847.
- **Reversal pairs keep the lender side on 5.4** (§6.2 pass 4, §7.11; final review I6): the widened pair markers (the return codes and the French cancel words) change the credit's revenue reading only. The debit's lender, potential-lender, withholding, insurance and flag contributions, its `reversed_by`, and the credit's settlement-reversal fields and flag contribution follow the pairs classification 5.4's markers make. G7 (`tools/lender_census.py`) now records each row's potential-lender, withholding and potential-withholding flags and its `reversed_by`, and reports their moves. Measured against c106634 on the corpus cache: ea9c934 moved 3 debits' `reversed_by`; this tree moves 0 debit-side readings beyond the owner's allowlist. 59c5335.
- **The census** (§14.2, §14.3; final review I7, I8, M11): `DECLARED_DEMOTIONS` is the table the compare reads, and every §20 demotion is declared by the rule that fires: the factor never verified, a Q5 or Q6 row a later hold names (the holder test, a personal trust, the holder's currency conversion, a title firm, a bank-originated wire, a financing root, owner money) or whose relaying bank's customer the payer region now reads, the premium-coded insurer entry, a short healthcare alias inside a name, a §15 deferred source, a row left to its family, pass 6's counter debit, the $1 floor's own method, and the CRA refund among the new non-revenue markers (the pass records the readings: `hold_rule`, `relayed_customer`, `premium_coded`, `factoring_payer`, `deferred_source`, `short_healthcare_alias`). Narrowing 5 needs a loan-reading base and a `LOAN` the later text prints `LN`, with no other change; narrowings 2 and 6 reach True only verified; narrowing 8 fails on a BNPL consumer-side word; G7b fails for any `non_revenue` base a text change takes into True, except the street-`LN` guard's own release (a `LOAN` printed `LN` at the end of a street address: a number, one to three alphabetic words, no loan-product word, no loan-payment word after it); the row and account guards also read an account only the later run holds, and an error skip the base recorded and the later run lost fails G9. 59c5335.
- **A partial revenue denominator** (§11, §9.2; final review M10): in the True- and Verified-revenue withholding modes, when a member's figure is not established, the package publishes no withholding rate and no potential exposure on the partial denominator and sets `withholding_review_required`. 69486cb.
- **The chart's room** (§10.3; the A4 train): the tallest bar is the plot box less the figures stacked above it (a 16px line, an 8px gap, each figure after the first pulled up 6px): 129px in the Both view, 147px in the True view and 165px in the Total view, so the bars, their figures and the baseline fit exactly (the Verified figure had pushed the bars 3px and 6px below the baseline). The page's script is `app.js?v=true-revenue-2`. 69486cb.
- **A bare `Debit Card Credit: Stripe`** (§7.11, §14.1; final review M5): it stays `non_revenue` by §7.11's release rule (a processor's card credit leaves the reversal rule only with a payout word); §14.1's earlier "held as `possible_return`" is corrected. No code change. FW-4.
- **A veto word that leads the entry field** (§7.0; re-review I4-R, amends the final review's I4 line above): on a store-name platform, a veto word that leads the entry field (the field's first word after its generic words, references, company forms and the platform's own words) is never spared as the holder's store word, whatever follows it: the NACHA entry field is ten characters, so a financing entry often prints a cut second word (`DES:CAPITAL DISB`, `CAPITAL DISBURSE`, `CAPITAL OFFER`, `CAPITAL XFER`, `LENDING DAILY` are held as `financing_named_payer` for a holder named `… CAPITAL LENDING FUNDING …`, as for any holder). A store name prints its own words first (`DES:<store> CAPITA`), and only then may a later word be spared. The 138 corpus rows the exemption exists for did not move. FW re-review.
- **A platform's financing entry** (§7.2, §6.1 step 10; re-review N6, which predates this branch): a processor, marketplace or platform credit whose entry field (the same leading word) leads with a financing word (`CAPITAL` and its cuts, `LENDING`, `LOAN`, `ADVANCE`, `FINANCING`, `FUNDING` except on the three platforms that print it on settlements, `CASH ADV`, `MCA` …) is the platform's financing, never its settlement of the business's sales, for any holder: the operating registry never verifies it by context (rule `platform_entry_leads_with_financing`), the recurrence pass never lifts it, and pass 7 holds it as `financing_named_payer` (`SQUARE INC DES:CAPITAL PAYOUT`, `SHOPIFY DES:CAPITAL PAYOUT`, `DOORDASH INC DES:ADVANCE PAYOUT`, `GRUBHUB DES:LENDING PAYOUT`); a `LOAN` entry stays `non_revenue` by the strong non-revenue rule. The census declares it (`platform_financing_entry`). No debit or lender reading moves. FW re-review.
- **The consumer entry's other slots** (§8.6; re-review N1, amends the final review's I1 line): a PPD or WEB code is also read as the row's last word after a receiver value that no later field ends (unless it is the last word of the holder's own name: `INDN:CONTOSO WEB` is the holder), before `DES` after a company form or a reference token (`NORTHWIND SUPPLY LLC PPD DES:…`; after a name word it is the payer's name, `NORTHWIND WEB DES:…`), and right after the posting label a row starts with (`ACH CREDIT PPD <payer>`). It is still never read inside a name or a receiver field. FW re-review.
- **G7's row flags are gated** (§14.3 G7; re-review N5): `tools/lender_census.py compare` fails on any potential-lender, withholding, potential-withholding or `reversed_by` move whose row's payee entity (the snapshot's `row_entities`) is not on the owner's signed-off allowlist (`--allowlist`), so the G7 verdict is the tool's own. FW re-review.
- **A store named with a financing word** (§7.0, §7.2; FW wave 3, the wave 2 confirmation's W2-1, amends the I4-R and N6 lines above): on a store-name platform (DoorDash, Uber Eats, Grubhub …), an entry field whose words (two or more, after its generic words, references, company forms and the platform's own words) are a consecutive run of whole words of the holder's own name (the statement's account name, a trade name after `DBA` included, or a name the row's receiver field prints) is the store's own name, even when it leads with a financing word: `DES:CAPITAL GRILLE` for a holder named `… CAPITAL GRILLE …`, `CAPITAL CITY`, `FIN AND FORK` (also on BMO's no-entry layout) and `ADVANCE PIZZA` keep their payouts (verified by recurrence), and the run's words are spared at any length. A bare `DES:CAPITAL`, a financing entry (`CAPITAL DISB`, `CAPITAL DI`, `CAPITAL OFFER`, `CAPITAL XFER`, `LENDING DAILY`, `CAPITAL PAYOUT`) and a store entry that is no run of the holder's name stay held as `financing_named_payer`. The 138 corpus rows did not move. FW wave 3.
- **PPD before `DES`** (§8.6; FW wave 3, amends the N1 line above): PPD is never a name word, so it is read as the SEC code before `DES` after any word (`NORTHWIND SUPPLY PPD DES:…` is a consumer entry); `WEB` there stays conditional (after a company form or a reference token only). FW wave 3.
