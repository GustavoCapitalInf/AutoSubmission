# Batch-8 census — the 598 digital `failed/no_parser_matched` documents of run `7a317445`, and the 61 withheld

Produced 2026-08-22 by the `unid-census-7` workflow (12 read-only shard readers over cached OCR text by direct artifact path, one merge, one adversarial verifier per top-14 family, one withheld-cohort reader). Families are PRINTED identities (masthead / furniture / summary grammar), never folder labels. Documents are named by content_sha256. No document text, amount, name or account number is reproduced here; institution furniture (phone ladders, PO boxes, routing numbers, domains) is.

**Totals.** documents 598 · statement families 91 (472 documents) · singleton families 12 · text-layer defects routed to OCR 8 · portal/range exports 13 · not statements 104 (117 incl. exports) · no text 1 · census expected validated yield 270.8. Coverage: every one of the 598 shas accounted for exactly once (asserted in the merge).

**Confidence scale** (census): "P(a fail-closed deterministic reader, once written for this template, publishes a validated record). Drivers: printed period totals, printed transaction counts, a balance oracle (daily grid or running balance), row recoverability from the text layer, and L-1 multi-account risk. expected_validated = n * confidence."

## Ranked families (verified top 14 carry the adversarial columns)

| # | family | n | census expected | census conf | verify identity | misfiled | verify ceiling | verify conf |
|---:|---|---:|---|---|---|---:|---|---|
| 1 | `core_enclosures_avgledger_leading_counts` | 58 | 40.6 | 0.7 | YES | 4 | Honest expected validated: 30-36 of 58 (52-62%), against the census's 40.6 (70%). Derivation: start at 58; subtract 1 hard misfile (8CCAE7DD) and 3 scrambled text layers (5ED19A08, 0D1BCE71, 12EAD3A8) | 0.60 MEDIUM (down from the census's 0.70 |
| 2 | `lili_sunrise_banks_checking` | 20 | 15.0 | 0.75 | YES | 5 | Honest expected validated: 13-14 of 20, not 15. The clean set is exactly 15 (not 18 - the census double-counted the same 5 defective documents as 'two column-shredded' plus 'at least three with 2021 r | 0.70 MEDIUM-HIGH (down from the census's |
| 3 | `welch_state_bank_more_than_free` | 16 | 11.2 | 0.7 | YES | 0 | 16/16 — I am raising the census's 11.2. This is not an estimate from a sample: I ran the arithmetic on every document in the family. Credit count+sum, debit count+sum (once "Checks Cleared" is handled | 0.88 HIGH (raised from the census's 0.70 |
| 4 | `cu_summary_of_accounts_date_posted` | 13 | 7.15 | 0.55 | YES | 0 | Honest expected validated under the CURRENT architecture: 3, not 7.15 — and it could be 0 if the reader takes the masthead account number. The extraction physics are excellent (I reconciled the printe | 0.30 LOW on the census's 7.15 expected-v |
| 5 | `business_classic_statement_of_account` | 8 | 6.0 | 0.75 | YES | 0 | Honest ceiling 8/8, higher than the census's 6.0, but the DISTRIBUTION is bimodal not binomial. I did not merely inspect the oracle -- I mechanically reproduced it: a sign-anchored, date-tokenised par | 0.85 HIGH on identity, oracle presence a |
| 6 | `frost_bank_business_checking` | 9 | 5.4 | 0.6 | YES | 0 | 8 of 9 honest expected, plausibly 9 — the census's 5.4 at 0.60 UNDERRATES this family and I could not refute it. Basis: I did not merely inspect the furniture, I ran a prototype parse and it reconcile | 0.75 MEDIUM-HIGH — raised from the censu |
| 7 | `bank_ozk_plus_less_summary` | 8 | 5.2 | 0.65 | YES | 0 | Honest expectation ~5-6 of 8, and the distribution is BIMODAL rather than a smooth 65%-per-doc — which makes the census's 5.2 point estimate right by accident rather than by shape. Every document has  | 0.60 MEDIUM — I could not refute the fam |
| 8 | `space_coast_cu_member_statement` | 8 | 5.2 | 0.65 | YES | 0 | 8 of 8 is genuinely achievable and I would forecast 7, not the census's 5.2. I did not just eyeball the oracle - I built a throwaway parser and closed every document deterministically: all 8 reconcile | 0.80 HIGH - raised from the census's 0.6 |
| 9 | `accounts_at_a_glance_category_number_amount` | 8 | 4.8 | 0.6 | YES | 0 | Honest expectation 6 of 8, plausible range 5-8 — above the census's 4.8, because the census under-rated the arithmetic and over-rated two of its three risks. Grounds for raising it: the summary identi | 0.70 MEDIUM — raised from the census's 0 |
| 10 | `guardian_cu_statement_summary` | 8 | 4.8 | 0.6 | YES | 0 | Higher than the census's 4.8 on the tie-out gate, but gate-dependent. I ran a ~60-line naive text parser over the full text of all 8 and got 8/8 fully reconciled: every suffix's printed Previous Balan | 0.85 HIGH — raised above the census's 0. |
| 11 | `poplar_bluff_activity_summary_running` | 6 | 4.8 | 0.8 | YES | 0 | 6 of 6. I raise the census's 4.8 rather than cut it, and I raise it on executed arithmetic rather than on the look of the page. I tried to break all six with the crudest extractor I could write - one  | 0.92 HIGH |
| 12 | `american_savings_bank_hawaii` | 11 | 4.4 | 0.4 | YES | 0 | Honest ceiling 5-7 of 11; honest EXPECTATION 3.0-4.0, below the census 4.4. Composition matters more than the count. Two members (6E0E, 82BD) have zero transactions and all-zero summaries at 626/627 c | 0.30 LOW (down from the census 0.40 MEDI |
| 13 | `cu_idaho_equation_summary` | 8 | 4.4 | 0.55 | YES | 0 | Honest expected validated: 6 of 8, with a realistic range of 4-8 and a hard ceiling of 8. I am revising the census's 4.4 UP on mechanics but DOWN on independence, and the two roughly cancel. Upward: i | 0.60 MEDIUM — up marginally from the cen |
| 14 | `wpcu_summary_of_account_by_transaction` | 8 | 4.4 | 0.55 | YES | 0 | Honest ceiling depends entirely on what "validated" demands, and the two answers are far apart.

If validated = extraction gated on printed counts + printed totals + begin/net/end continuity: the ceil | 0.60 MEDIUM — raised only marginally fro |
| 15 | `cu_unq_clt_trailing_minus_totals` | 8 | 4.0 | 0.5 | — | — | — | — |
| 16 | `truist_your_account_statement` | 7 | 3.85 | 0.55 | — | — | — | — |
| 17 | `old_national_free_business_checking` | 5 | 3.75 | 0.75 | — | — | — | — |
| 18 | `dfcu_financial_account_statement` | 5 | 3.5 | 0.7 | — | — | — | — |
| 19 | `bank7_summary_of_accounts` | 4 | 3.4 | 0.85 | — | — | — | — |
| 20 | `chesapeake_bank_activity_in_date_order` | 5 | 3.25 | 0.65 | — | — | — | — |
| 21 | `wescom_cu_equation_summary` | 5 | 3.25 | 0.65 | — | — | — | — |
| 22 | `commerce_bank_mybusiness_checking` | 4 | 3.2 | 0.8 | — | — | — | — |
| 23 | `pnc_core_commercial_checking` | 4 | 3.2 | 0.8 | — | — | — | — |
| 24 | `mountain_america_cu_dot_leader` | 9 | 3.15 | 0.35 | — | — | — | — |
| 25 | `altura_riverside_cu` | 5 | 3.0 | 0.6 | — | — | — | — |
| 26 | `jh_spaced_caps_checking_summary` | 4 | 2.8 | 0.7 | — | — | — | — |
| 27 | `pnc_treasury_enterprise_plan` | 4 | 2.8 | 0.7 | — | — | — | — |
| 28 | `pnc_virtual_wallet_performance_spend` | 4 | 2.8 | 0.7 | — | — | — | — |
| 29 | `suncoast_cu_account_statement` | 4 | 2.8 | 0.7 | — | — | — | — |
| 30 | `usaa_fsb_classic_checking` | 4 | 2.8 | 0.7 | — | — | — | — |
| 31 | `vystar_balance_summary_transactional_detail` | 4 | 2.8 | 0.7 | — | — | — | — |
| 32 | `chime_bancorp_checking` | 5 | 2.75 | 0.55 | — | — | — | — |
| 33 | `bokf_business_access` | 4 | 2.6 | 0.65 | — | — | — | — |
| 34 | `nbkc_bank_dda_statement` | 4 | 2.6 | 0.65 | — | — | — | — |
| 35 | `associated_bank_financial_statement_of_accounts` | 4 | 2.4 | 0.6 | — | — | — | — |
| 36 | `city_national_bank_florida` | 4 | 2.4 | 0.6 | — | — | — | — |
| 37 | `greater_nevada_cu` | 4 | 2.4 | 0.6 | — | — | — | — |
| 38 | `green_dot_bank_partner_program` | 4 | 2.4 | 0.6 | — | — | — | — |
| 39 | `hapo_cu_estatement` | 4 | 2.4 | 0.6 | — | — | — | — |
| 40 | `ornl_fcu_oak_ridge` | 4 | 2.4 | 0.6 | — | — | — | — |
| 41 | `sierra_central_cu` | 4 | 2.4 | 0.6 | — | — | — | — |
| 42 | `townebank_balance_summary` | 4 | 2.4 | 0.6 | — | — | — | — |
| 43 | `cubase_suffix_box_summary_history` | 5 | 2.25 | 0.45 | — | — | — | — |
| 44 | `rbfcu_business_member_statement` | 5 | 2.25 | 0.45 | — | — | — | — |
| 45 | `altra_fcu_statement_summary` | 3 | 2.25 | 0.75 | — | — | — | — |
| 46 | `cu_statement_summary_prev_new_balance_unbranded` | 4 | 2.2 | 0.55 | — | — | — | — |
| 47 | `redstone_fcu_statement_of_accounts` | 4 | 2.2 | 0.55 | — | — | — | — |
| 48 | `security_service_fcu_asterisk_sections` | 4 | 2.2 | 0.55 | — | — | — | — |
| 49 | `capital_one_360` | 6 | 2.1 | 0.35 | — | — | — | — |
| 50 | `heritage_south_cu` | 3 | 2.1 | 0.7 | — | — | — | — |
| 51 | `hudson_valley_fcu` | 3 | 2.1 | 0.7 | — | — | — | — |
| 52 | `community_savings_bc` | 4 | 2.0 | 0.5 | — | — | — | — |
| 53 | `goldenwest_cu_member_account_statement` | 4 | 2.0 | 0.5 | — | — | — | — |
| 54 | `novo_monthly_account_statement` | 4 | 2.0 | 0.5 | — | — | — | — |
| 55 | `palmetto_citizens_cu` | 4 | 2.0 | 0.5 | — | — | — | — |
| 56 | `st_marys_bank_nh` | 4 | 2.0 | 0.5 | — | — | — | — |
| 57 | `pima_fcu_statement_of_account` | 3 | 1.95 | 0.65 | — | — | — | — |
| 58 | `access_fcu_member_statement_of_account` | 4 | 1.8 | 0.45 | — | — | — | — |
| 59 | `atb_financial_consolidated_statement` | 4 | 1.8 | 0.45 | — | — | — | — |
| 60 | `bank_of_tennessee_activity_summary` | 4 | 1.8 | 0.45 | — | — | — | — |
| 61 | `vystar_business_checking_analyzed` | 4 | 1.8 | 0.45 | — | — | — | — |
| 62 | `bangor_savings_three_count_summary` | 3 | 1.8 | 0.6 | — | — | — | — |
| 63 | `champion_cu_statement_summary` | 3 | 1.8 | 0.6 | — | — | — | — |
| 64 | `mt_bank_customer_statement_treasury` | 3 | 1.65 | 0.55 | — | — | — | — |
| 65 | `becu_deposit_and_loan_activity` | 4 | 1.6 | 0.4 | — | — | — | — |
| 66 | `beem_credit_union_bc` | 5 | 1.5 | 0.3 | — | — | — | — |
| 67 | `mt_bank_account_activity_daily_balance` | 3 | 1.5 | 0.5 | — | — | — | — |
| 68 | `fulton_bank_account_statement` | 4 | 1.4 | 0.35 | — | — | — | — |
| 69 | `firstbank_colorado` | 2 | 1.4 | 0.7 | — | — | — | — |
| 70 | `firstbank_pr_escrow_pipe_header` | 2 | 1.4 | 0.7 | — | — | — | — |
| 71 | `greenstate_cu_post_eff_type` | 3 | 1.35 | 0.45 | — | — | — | — |
| 72 | `umb_essential_business_checking` | 2 | 1.1 | 0.55 | — | — | — | — |
| 73 | `synovus_pinnacle_portal_statement_view` | 4 | 1.0 | 0.25 | — | — | — | — |
| 74 | `wisely_adp_paycard` | 4 | 1.0 | 0.25 | — | — | — | — |
| 75 | `ramp_business_account` | 1 | 0.85 | 0.85 | — | — | — | — |
| 76 | `psecu_shares_at_a_glance` | 4 | 0.8 | 0.2 | — | — | — | — |
| 77 | `pr_business_plus_corp_statement_of_account` | 5 | 0.75 | 0.15 | — | — | — | — |
| 78 | `ion_bank_customer_statement` | 4 | 0.6 | 0.15 | — | — | — | — |
| 79 | `pc_financial_pc_money_account` | 1 | 0.6 | 0.6 | — | — | — | — |
| 80 | `bofa_business_advantage` | 1 | 0.55 | 0.55 | — | — | — | — |
| 81 | `relationship_summary_daily_balance_unbranded` | 1 | 0.55 | 0.55 | — | — | — | — |
| 82 | `southern_bank_quadruplicated` | 1 | 0.55 | 0.55 | — | — | — | — |
| 83 | `onepay_coastal_community_monthly` | 1 | 0.5 | 0.5 | — | — | — | — |
| 84 | `eastern_bank_customer_statement` | 3 | 0.45 | 0.15 | — | — | — | — |
| 85 | `chase_total_checking_transaction_detail` | 1 | 0.45 | 0.45 | — | — | — | — |
| 86 | `cu_suffix_transfer_acct_grid` | 1 | 0.45 | 0.45 | — | — | — | — |
| 87 | `desjardins_accesd_releve_operations` | 1 | 0.45 | 0.45 | — | — | — | — |
| 88 | `laurentian_bank_current_account` | 1 | 0.4 | 0.4 | — | — | — | — |
| 89 | `rho_deposit_account_statement` | 1 | 0.4 | 0.4 | — | — | — | — |
| 90 | `conexus_cu_demand_products` | 1 | 0.3 | 0.3 | — | — | — | — |
| 91 | `paypal_account_statements` | 7 | 0.0 | 0.0 | — | — | — | — |

## Family records

### 1. `core_enclosures_avgledger_leading_counts` (n=58, expected 40.6, 0.7)

- **Printed identity:** Core-processor deposit block, licensed under many small-bank mastheads (most print NO bank name in the text layer): 'Date m/d/yy  Page N' + 'Account Number'/'Primary Account' + 'Enclosures N'; a banner ('CHECKING ACCOUNT'/'*** CHECKING ACCOUNTS ***', often painted 2-4x); then the invariant two-column block '<PRODUCT>  Number of Enclosures N / Account Number ... Statement Dates m/dd/yy thru m/dd/yy / Previous Balance (or Balance Last Statement) ... Days in the statement period N / <n> Deposits/Credits ... Average Ledger / <m> Checks/Debits ... Average Collected / Service Charge / Interest Paid / Ending (or Current) Balance'; then an ASCII pipe box 'Total For This Period | Total Year-to-Date' over Total Overdraft / Return item fees; then sectioned ledgers (Deposits and Additions / Checks and Withdrawals / CHECKS IN SERIAL NUMBER ORDER) and a 'Daily Balance Information' 3-up Date|Balance grid.
- **Oracle:** Printed six-figure summary (previous, credit total, debit total, service charge, interest, ending) PLUS both transaction counts as a bare integer immediately LEFT of the label PLUS a daily-balance grid on ~2/3 of the cohort. Three independent gates: count(rows)==printed count per direction, sum(rows)==printed total, and last-row-of-day==grid balance.
- **Nearest reader:** analysis/core_processor_counted.py, core_processor_daily.py, core_processor_sectioned.py, fiserv_premier.py (parenthesised-counts issue only), farmers_merchants.py, linkbank.py, capital_one.py
- **Risks:** Institution absent from the text layer on most members -> must register on template furniture, never a masthead. Label drift: Previous/Balance Last Statement, Ending/Current/Balance This Statement, Average Ledger(Bal.), Service Charge/Fee/MAINTENANCE CHARGE, Number of Enclosures/Images. Banner and marketing lines duplicated 2-4x. Two ledger arrangements (sectioned vs date-order) and a debit-side trailing minus. A minority prints no daily grid. Occasional 'SUMMARY OF ACCOUNTS' roll-up is L-1-capable.
- **Merged from:** 13 shard families across all 12 shards (jh_core_boxed_monospace, fiserv_premier_leading_counts_*, core_enclosures_*, jha_*, corebank_summary_sectioned_daily, unnamed_core_statement_of_account_daily_balance)
- **VERIFY (adversarial):** identity_confirmed=True; sampled 16; misfiled [{"sha": "8CCAE7DD830DF214", "why": "Genuine misfile - different processor. Six-branch OK bank template: NO 'Number of Enclosures', NO 'Average Ledger', NO 'Average Collected', no ASCII pipe box (prints 'Total For This Period Total Year-to-Date' as plain text). Summary grammar is only 'Account Number / Beginning Balance / Days in Statement Period / N Deposits-Other Credits / N Checks-Other Debits / Ending Balance'. Ledger row order is DESCRIPTION-then-date-then-amount, not date-leading. Also the only true L-1 in the cohort: 5 separate account summary blocks in one PDF. Shares only the leading-integer-count idiom, which is not sufficient to register on."}, {"sha": "5ED19A08317E0D12", "why": "Same core product by label vocabulary (Number of Enclosures / Average Ledger / Average Collected / Activity in Date Order / Total For This Period) but rendered by a modern proportional boxed composition whose PDF text layer is ORDER-SCRAMBLED: labels detached from values ('$23,460.00 Previous Balance', counts emitted as a bare '15 19' pair), amount-before-date rows, and the daily grid emitted as three balances then three dates. Belongs in the text-layer-defect / OCR-relayout route, not in a mono
  - oracle present: Verified by scripted probe over all 58 plus eye on 15. PRINTED SUMMARY: 'Statement Dates' 57/58, 'Days in/This statement period' 57/58, 'Average Ledger' 57/58, 'Average Collected' 51/58, enclosures token ('Number of Enclosures'/'Number of Images'/'Acct. Enclosures') 53/58. BOTH COUNTS as a bare integer LEFT of the label: 58/58 credit side, 57/58 debit side (the census's own probe undercounted - four members are FULL UPPERCASE, '7 DEPOSITS/CREDITS / 63 CHECKS/DEBITS'). DECISIVE TEST: a crude 20-line extractor (label drift + trailing-minus + $ handling) pulled previous/credit-total/debit-total/service-charge/interest/ending and the identity prev+credits-debits-fees+interest==ending CLOSED on 52/58; 3 misses are the scrambled docs named above, 3 arithmetic fails (311A8A44, A228C429, FA1FDBCA - all three carry a separate 'Checks in Serial Number Order' section, so my grab most likely took a wrong token rather than the print being inconsistent). DAILY GRID: 45/58 (78%, better than the census's ~2/3), 3-up Date|Balance, labelled 'DAILY BALANCE INFORMATION' / 'Daily Balance Information' / 'DAILY BALANCES' / 'Daily Balance'. ROW-LEVEL GATE PROVEN ONCE by hand on 44ABCCCAEC92BB81: 8 ledger credits summed exactly to the printed credit total, and 39 ledger debit rows + 18 rows in the separate 'SUMMARY BY CHECK NUMBER' grid == the printed 57 debit count exactly. So the oracle is real - but only if the check grid is merged into the debit side.
  - ledger shape: Monospaced fixed-column text on 54/58, columns preserved but each transaction is NOT one line. Four distinct arrangements: (1) SECTIONED, 48/58 - 'Deposits and Additions' / 'Checks and Withdrawals' / 'DEPOSITS AND OTHER CREDITS' / 'Summary of Deposits', section header AND the 'Date Description Amount' header repainted on every page; (2) 'ACTIVITY IN DATE ORDER' banner painted 2-4x, 9/58, no running balance; (3) date-order WITH a running Balance column, only 4/58; (4) scrambled/proportional, 3/58. Row grammar is NOT uniform: most are date-description-amount, but 094C1B33 / 228FD066 / the two F&M docs print date-AMOUNT-description (amount second, description trailing) - a reader keyed on 'last numeric token is the amount' inverts on those. Descriptions wrap badly: continuation fragments land AFTER the amount on the SAME line (CCE6F423: '3/10 From DDA 5001372894,To DDA 500 145.75 1634376,5%'), and on 44ABCC the wrapped ID#/TRACE# tail of the last transaction on page N is emitted at the TOP of page N+1 before the next date. Debit-side trailing minus ('700.00-') is common and also appears on printed SUMMARY figures (40A39755 prints a negative Average Ledger and a negative Ending Balance as '833.70-' / '215.22-'), and on negative daily-grid balances ('148.22-'). Checks are frequently NOT in the ledger at all: 19/58 carry a separate 2-up or 3-up collapsed grid ('date checkno amount   date checkno amount') with '*' break-in-sequence markers and occasional blank check numbers. 34/58 additionally end with a check/deposit IMAGE APPENDIX repeating every item as 'CHECK 2679 Date: 04/09 Amount: $35,875.00' - a naive amount scraper double-counts the whole debit side there.
  - multi-account (L-1): L-1 risk is LOW, lower than the census implies. Exactly ONE of 58 contains more than one account summary block - 8CCAE7DD, with 5 blocks, and that document is the misfile above. 10/58 print a roll-up page ('SUMMARY OF ACCOUNTS' / 'ACCOUNT SUMMARY' / 'Summary of Accounts' with Account Number | Type | Current Balance | ENCLS), but in every sampled case (5DD3029C, 094C1B33, 0B66ADB3) the roll-up lists exactly one account. The roll-up is therefore not an L-1 problem but a decoy: it prints an account-plus-balance pair before the real summary block, which a first-match summary parser will grab instead of the statement summary.
  - currency evidence: NO printed currency token anywhere in the cohort. Scripted scan of all 58: zero occurrences of 'CAD', zero of 'USD', zero of CANADA / any Canadian province / any Canadian postal pattern / 'Transit'. Evidence is entirely indirect: bare '$' on 45/58 (absent entirely on 3, and inflated to 1,200+ occurrences on 4 by the check-image appendix), 'FDIC' or 'Member FDIC' on 10/58, and US mailing addresses / NANP numbers on every sampled member (GA, AL, ME, OK, FL, CA, AR, VA). So currency here can only be a US jurisdiction default with currency_source = inferred, never printed - it is the mirror image of the RBC-CAD case and carries no printed evidence to pin against.
  - ceiling: Honest expected validated: 30-36 of 58 (52-62%), against the census's 40.6 (70%). Derivation: start at 58; subtract 1 hard misfile (8CCAE7DD) and 3 scrambled text layers (5ED19A08, 0D1BCE71, 12EAD3A8) that a column reader cannot touch -> 54 addressable. Of those 54, the printed summary is extractable and self-consistent on 52, so a summary-only reader would land high. But the staffing oracle is row-level, and the debit direction is where it dies: 19/58 require merging a collapsed 2-up/3-up check grid into the ledger, 34/58 require positively excluding a check-image appendix that restates every amount, at least two row grammars (date-desc-amount vs date-amount-desc) must be detected per document, and wrapped description fragments sit after the amount on the same line and across page breaks. Each of those is individually solvable - I proved the count gate closes exactly on one merged-check document by hand - but they compound, and a single missed or mis-signed row fails the whole document. If the validation gate accepts summary reconciliation plus one direction, expect the high 30s; if it demands both count gates plus the balance chain on every document, expect high 20s to low 30s. I would staff this at 34 expected, not 40.6.
  - confidence: 0.60 MEDIUM (down from the census's 0.70 HIGH). The family's existence and cohesion survive refutation strongly - 57/58 share the invariant two-column furniture and 52/58 self-reconcile arithmetically, which is unusually good. The downgrade is entirely about yield, not identity: the census treated 58 documents as one shape when they are one product in four printing arrangements plus three broken text layers, and its stated third gate does not exist on 93% of the cohort.
  - strongest refutation: The strongest reason this family underdelivers: THE CENSUS'S THIRD GATE IS MECHANICALLY WRONG FOR ALMOST THE WHOLE COHORT. It specifies 'last-row-of-day == grid balance', but only 4 of 58 documents print a running Balance column - the other 54 print Date/Description/Amount with no per-row balance. On those, the daily grid can only be checked by a CUMULATIVE CHAIN (previous balance plus every signed row through day D), which is not an independent third gate at all: it is the sum gate again, made strictly more fragile because it now needs correct sign inference on every single row (trailing minus), correct inclusion of the separately-printed check grid, and correct exclusion of the check-image appendix. One dropped or mis-signed row poisons every subsequent day. So the '58 documents x three independent gates' arithmetic behind expected_validated=40.6 is really '54 documents x two gates, one of which is a chain that fails whole-document on any single row error'. Secondary refutation: the family key is named for furniture that is not universal - the enclosures token is missing on 5/58 and 'Average Collected' on 7/58 - so a registration predicate built literally from the key will under-match, while a looser predicate risks pulling in the 8CCAE7DD-class impostor that shares only the leading-integer-count idiom.
- **shas:**
```
0022B7AD844C37CA1BDF4CBAAB6614EDF826B816B0C871A026C3D082C133898A
040919803174643E73107C1FC8872C2AF9C03D5B1FF49E14D4C53C6BE3D9D9A1
0943986A52D8226CE49C9858A0CE737501DD494FDA6B948307EE1486F7108185
094C1B3378BA42168B1D1CD5E501DF18FFEDC0E4982C4722BD662FE343B6DA33
0B66ADB3CD7F010B450BC8DAF170F536698CB33CE99CB0EC190A722894B40FC1
0D1BCE71A83973736D970BC7FD8EEEEBED8CD5FA150D663EFEDCDC01048BA135
12EAD3A8C2CEBAFA36ABA636321912ED12A57A3896D35F7AC79DCCE40A5D3A88
15919CA443659A2E27704CED8D89A637E6C36B123D1E957F6CD60BB1DB87BCDE
1FA95B7A8B25BB43B20DBF6F5E6462A9E59A0E5484D7D98CA2086A859DC374AB
228FD066863FF0625F316D727AE1FE1D7B59DD9102BC68740A2DC7CE965DE90A
23C747A3192D891D7B0842C6D31FF90BE1F111CBD3AAE9E90AFAEB95F9CF0463
284B6B31CEA939F85C0616A1E0AB632961306D409227C908F1221953B9475BF8
2ECDB7B332F4979F3DC2FA3719114BD5306615653ED68EB46B7FBEEFDE7CC108
311A8A44D93F273A62AC701F5A75AD33CCA662559CA21E6B25094434BC2ACD19
34C0C8560F617307A3E65FF7EE900866EB85C8181AE2DC1F0E801E41FD2D1BA8
371608D7F66D84E712971BB11F0A2E3AE28A48945861D6994EDD4AA848E1B7E8
373B73F98E63F9006F5074C8FFDF7A6ED34B0913A7B2959A328722B8451E8F09
375B7A2DF1405B7EAE96E51F4B6F7275998009689911CB262737506DB291C4FB
37D26C1E68119850136B9BA6CFBDBB44422FCBE63ABDF667803F7E183BD5356D
3AF6C459076B0506F0C8D75DD6CEF07C14074FB35D1C8575CB142657E9DED196
3F22BAB808B135052316835E55048603237DA30147029530202BF08CEB89ECA6
40A39755C2C7FFD493A92E19ADEBF113F24C15F4C831E34349E5F8FE29AB7039
44ABCCCAEC92BB81C9E8CEDD2A1530ACA50BEDD8017FBF9886B687D979E31E14
46D1D2B717623F7A7FDE1FC1A40DCD20C4D9C902610821E36CB5B7BD5BEFDCC9
597075B053682E540F4BBECE911E43CA21AB168245ACE163A6831E34418DA362
5B4DBE8B6444458AE13C09A239C80C9B3111571ACE93989CCEF1D77FEA797F62
5DD3029C0D28B93A78E5F44BF457B922E049FB0FC3E957D66A7838E45AC598F4
5ED19A08317E0D1252A93E4A99B94577D29DE933DDD5F483876CF5A1B69B1A31
6361FBBA92309D817C14ADA3435FD0651D343B86F532D930F6E42D2DAB0C137D
65ECB31F25446416E0F5518882567AFC12A5856A96D20451260FE1C01B1CFA4D
67B69A4DB272D70C8054E77EF6EA602BA2976E6A2C2C1C61315C708D1A22411F
68D4F9F06AA764D9F62171B7A4E1763276A43E0C458733ACD6DE8C2BFF707271
75724B78282A9FEC2D88B426C68349D8C91CAE4EC224520CE3C64A083C993DD8
75BEDE1315BD6AC9C50422CD590E932058A13298D83DD5085A399A985A839C17
75FE7191FD4E74A010B1254D37C8C6B05EF816901136D1894AB242AB48499E95
8C858D4ABF76D7D72E99F78566EDF69C9C13B8A92C565950AE0014D22A35093B
8CCAE7DD830DF214E269F145C130A10B60DD2F83FBD679FAB2467E733EEC6C05
90A62FB5A03A9A25E7223BA4752AB4ED821F059A9D740BF0583E4C9CEA0A1656
9B89E33071DACFCE930795B3F8E544AB3049816AE38B9440CE714855B004EC74
A07707C60DE334B1CDE284DCCB6BDCEAC4E54910AEFB4725C565A65E3D6380E9
A1760B1E58E32D7611669A6FA71D7DDC6E46E4EE9D328F91DB456537ACEFE83F
A1BD4B7284FEE78EBF0D4EE590F23F24FD1C694AA60422F01F67B9F6E0F3BCB5
A228C4293BFB603FA22B7176FB4DAAE5D8EBB611F380550F6F9F3F2DA15EEF17
A9B13BD64619F6345BFE2B95414C359E2E12A23B374298CA588D5FFA850AAC4C
AF40E5724B4A5642943A2DC90996D2BE3576E4701DC7E2C705A905060D3A4D5D
B9264C8022B8AAE6E792FE09A895B7FBEB99C3496C976A97C888E0CF65FB19E4
BB64D37A14A5CA988F9BA1E29387E15B1C8622D742A192481A31040CED3EDE3A
BD835DA79B01B332B35D6362D187CF277AF688EE05FCC4562F9178ABBC7662B2
C116BD38F7D6FC53F2E761A5A407473D29019AD60E0DCBB4C27FEB4BE4443E1F
C355B3706588F0B1198876A25F293CD7376B99A1EFAFEA880B1BB8047BDFB8DE
CCE6F423AFEE4750AE55EFC799E45D0A08FF20490610E39AEBAFFDABE11E3049
D31770634E04E104C26A54E3103C95E132CF66ACFFD4A4B6F7C3F2324E0B4B2D
D5E86E072929CB25724F3E5C5B9CBD154634AF00D77F9B66224F9CB1139A80CB
D7A7C1B0F6C7F79F378F5180149F90978BD3A445299C34158E9BB93F5D7E1924
EB33BA2FEB3A84BE39516CF4B4ED7ABBA938F45323F3D00820C6E01E80DD604F
F4165BC54388E4C783BB17DED099AE906A384E37145B82AF7174B9E937D5C1EC
FA1FDBCA9AF571EE7FFC327316E1141F4D3E7A6A2C9A39701D2C6709E99766BA
FEDEEA30246DC2EEE0FA64A738B6E30FA631DBB39D98D61B342B566BBEB76C3B
```

### 2. `lili_sunrise_banks_checking` (n=20, expected 15.0, 0.75)

- **Printed identity:** Lili (fintech, no masthead in the text layer): 'Account Number  Statement Period / 6921xxxxxxxx  <D Month, YYYY> - <D Month, YYYY>' (day-first long dates); 'Checking Account Summary' / 'Summary' with an Amount column; 'Checking Account Activity - Main Account'; back-page 'Lili is a financial technology company, not a bank. Banking services provided by Sunrise Banks N.A., Member FDIC' + support@lili.co / 1-855-545-4380; body rows 'Lili Plan Fee (Effective Date ...)', 'Lili Rewards', 'BusinessBuild Card collateral'.
- **Oracle:** Five printed rows -- Beginning balance on <date>, Deposits and other credits, Withdrawals and other debits, Fees, Ending balance on <date> -- plus a per-row running Balance, so both a sum gate and a chain gate are available.
- **Nearest reader:** none (no lili module); nearest genre analysis/bluevine.py, mercury.py, relay.py, square_checking.py
- **Risks:** One printing (BusinessBuild) puts the summary in three money columns (Checking | Collateral | Total) -- a 2-figure read grabs the wrong column. Two members have column-shredded Activity tables with a floating network tag (VS/PM/AD/IS). At least three members carry 2021-dated rows inside a 2026 period with a balance chain that does not continue -- integrity-suspect, do not use as fixtures. Folder labels say Bluevine/Chime/Unidentified; the printed identity is Lili.
- **Merged from:** s1,s2,s3,s4,s6,s7,s8,s9,s10,s12
- **VERIFY (adversarial):** identity_confirmed=True; sampled 15; misfiled [{"sha": "0388628F8E576D31", "why": "Institution is correct (Lili: support@lili.co, 1-855-545-4380, 'Lili Rewards' summary row), but this is a DIFFERENT printing that shares none of the family's stated furniture: header order reversed to 'Statement Period / Account Number', bare 'Summary' not 'Checking Account Summary', bare 'Activity' not 'Checking Account Activity - Main Account', and NO Sunrise Banks / Member FDIC back-page disclosure at all (the census made that disclosure part of the family identity). Also integrity-suspect: summary debits printed positive, sum gate misses by 0.10, activity carries a block of 06/2021-dated rows with a balance chain that does not continue."}, {"sha": "D6945B6F0F238A91", "why": "Same second printing, same account/entity as 0388628F. Carries the byte-identical 2021 junk-row block (same auth codes 119850024 / 119861451 / 119861448 / 119806870 / 116280071 / 182919294, same amounts) pasted into a Feb-2026 period - a template-tampering signature, not an OCR defect."}, {"sha": "E9FA142EE9E0134D", "why": "Same second printing. 'Deposits and other credits' line carries TWO figures and the 'Withdrawals and other debits' line carries NONE (the withdrawal 
  - oracle present: CONFIRMED and arithmetically verified for the 15 clean members. Printed: five summary rows on one line each - 'Beginning balance on <D Month, YYYY> $X', 'Deposits and other credits $X', 'Withdrawals and other debits $-X', 'Fees $-X', 'Ending balance on <D Month, YYYY> $X' - plus a per-row running 'Balance' column in the activity table. I ran both gates on all 20. SUM GATE: 14/15 clean members reconcile to the cent (beginning + deposits + withdrawals + fees = ending); 80D07A7D64B5672D fails by exactly $320.00 (printed Deposits 16,323.32 vs 16,643.32 actually summed from its own rows - a defect printed in the document, not an extraction error). CHAIN GATE: 15/15 clean members chain with ZERO breaks from the printed beginning balance to the printed ending balance (implied opening from row 1 == printed beginning; last row balance == printed ending) across 19 to 617 rows. Also confirmed: 'Withdrawals and other debits' EXCLUDES fees - the row-sum of negatives equals Withdrawals + Fees, verified exactly on 11 of 12 single-column members. NOT present anywhere in the family: no daily balance grid, no average-daily-balance line, no interest line, no check-image/check-number section. Absent entirely from the 5 second-printing members: their summary labels and figures sit on separate lines, so there is no line-anchored 5-row read at all.
  - ledger shape: Two incompatible shapes, and the census understated the split. SHAPE A (15 members, all model=native-pdf-text, 2-11 pages): fully collapsed to one line per transaction - 'MM/DD/YYYY <auth> <description> $<amount> $<balance>' - under a single header 'Date Authorization Code Description Amount Balance'. Descriptions do NOT wrap; merchant string, city and state/country run together with no delimiter ('UBER *EATS HELP.UBER.COMCAUS', 'THE HOME DEPOT #1109 COLUMBIA SCUS'), so amount is always the second-to-last money token and balance the last. Zero short rows across 2,718 parsed transaction lines. This is the easiest possible shape for a deterministic reader. SHAPE B (5 members, ~3.4KB, 2 pages): columns fully shredded - the header prints as 'Amount Balance / Date / Description Authorization Code', and each transaction is spread over three or four lines in inconsistent order (description, then date, then auth code, then amounts - or auth code first, or amounts stranded on the description line), with a floating two-letter network tag (VS / PM / AD / IS) landing on its own line or glued to the description. My row parser recovered ZERO transaction lines from all five. Summary labels and their figures are also on separate lines. Not deterministically parseable from this text layer.
  - multi-account (L-1): YES for 3 of 20 - a real L-1 case the census did not identify as such. The BusinessBuild members (9A841D10C92D6049, A3807F7D3956FCA2, B7BC8FF5A4EE3898, all the same account 6921xxx71334) carry TWO ledgers: 'Checking Account Activity - Main Account' followed by a second table headed 'Business Build Collateral Activity' with its own Date/Auth/Description/Amount/Balance and its own independent running balance. That is why a naive single-chain read of those three shows exactly one break and terminates on the collateral ending balance (1,000.00 / 2,500.00 / 1,500.00) instead of the checking ending balance. Each sub-ledger chains perfectly on its own, and the three-column summary (Checking | Collateral | Total) reconciles in BOTH the Checking and the Total column to the cent. So the census risk is real but mis-stated: it is not merely 'a 2-figure read grabs the wrong column', it is that the statement is genuinely two accounts and the transaction stream must be attributed to two sub-ledgers or the checking chain appears broken. The other 17 are single-ledger. Note also 4 members (Kimberly Cole account) show 'Deposit from Checking' / 'Withdraw to Checking' descriptions, but there is no second activity table - single ledger.
  - currency evidence: No printed currency code anywhere in the family - I grepped all 20 for USD/CAD/'Currency' and got zero hits. Every figure is a bare '$'. Currency is inferable only by US jurisdiction: 'Banking services provided by Sunrise Banks N.A., Member FDIC' (St. Paul, MN), 'Wire Transfer service provided by Column Bank N.A., Member FDIC', 'The Lili Visa Debit Card is issued by Sunrise Banks N.A. ... pursuant to a license from Visa U.S.A. Inc.', and US account-holder addresses (FL, KY, SC, CA). No Canadian institution anywhere, so the RBC-CAD ceremony precedent does not touch this family - USD by US jurisdiction default. The 5 second-printing members carry NO bank attribution at all (only support@lili.co and a US toll-free number), so their currency rests on the '$' plus a CA address alone - weaker, but still US.
  - ceiling: Honest expected validated: 13-14 of 20, not 15. The clean set is exactly 15 (not 18 - the census double-counted the same 5 defective documents as 'two column-shredded' plus 'at least three with 2021 rows', when in fact all five are one printing, one account, and all five are both shredded AND carrying the identical 2021 junk block). Of those 15: 14 pass the printed sum gate to the cent and 15 pass the chain gate with zero breaks, so a chain-anchored reader tops out at 15 and a strict-summary-sum reader tops out at 14 (80D07A7D64B5672D's printed Deposits figure is wrong by $320.00 in the document itself). Subtract further if L-1 two-ledger support is not in scope for this cell: the 3 BusinessBuild members need the 'Business Build Collateral Activity' table split out or their checking chain will not close, taking the floor to 11-12. The 5 second-printing members should be routed out (integrity-suspect / text-layer defect), not counted against this reader - if the staffing plan expects them to validate, expected drops to 13-14 out of a nominal 20 and the family looks like a miss. Also worth flagging for staffing math: the 20 documents are only 5 distinct accounts (four clean: 6921xxx61118, 6921xxx14505, 6921xxx71334, 2601xxx48858; one defective: 6921xxx98720), i.e. consecutive monthly statements of the same handful of holders - real template diversity is closer to n=5 than n=20, and month-over-month continuity is verifiable (ending balance of one statement equals beginning of the next, which I confirmed on the Blackwell and Razworx runs).
  - confidence: 0.70 MEDIUM-HIGH (down from the census's 0.75 HIGH). Identity and oracle are rock solid - I verified both gates arithmetically on every member rather than eyeballing them - but the staffing estimate carries real unmodelled risk from the 3 two-ledger BusinessBuild statements and from how the pipeline treats a document whose own printed summary is internally wrong. Realistic band 11-15.
  - strongest refutation: The strongest reason this family would underdeliver: it is not one family, it is two, and the census's own headline identity string is wrong for a quarter of it. Five of the twenty (0388628F, D6945B6F, E9FA142E, FD250EFB, FE2C9E80 - all one account, P2 Performance Horses, 6921xxx98720) print NONE of the furniture the family key is built on: no 'Checking Account Summary', no 'Checking Account Activity - Main Account', and no 'Lili is a financial technology company... Sunrise Banks N.A.' disclosure whatsoever. Their header order is reversed, their summary labels and figures are on separate lines, their activity rows are shredded across three or four lines with a floating VS/PM/AD/IS tag, they contain malformed money ('$-5,0000.50', '$84.240.23', '$35,000' with no cents), and all five carry a byte-identical block of June-2021 rows with a dead balance chain - the same auth codes and amounts pasted into five different 2026 months. Those are tampered or synthetic documents, and a reader written to the Skin-A grammar will not touch them at all. Secondary refutation: the census's stated printed identity pins the account number as '6921xxxxxxxx', but four clean members print 2601xxxxxxxx - so a masthead-prefix classifier tuned on the census string would drop a fifth of the clean set. Third: the census logged the BusinessBuild three-column summary as a column-picking hazard when the deeper problem is that those statements are two-account (L-1) documents with a second 'Business Build Collateral Activity' ledger; without sub-ledger attribution their balance chain does not close and all three fail the chain gate.
- **shas:**
```
0388628F8E576D31FA02FC0271AD3D45CD84AA95EBF02BBEFF790B79D109A84E
22C6933C0602DDDC77F74EFAB7AB63CF3A30C62D716910C3D063BCF0F50BDFBF
454A07BD54196A56C68578BF6E10B9F9AAF4D8C67AE31B1472FAB8B43B9EC03C
4857279C9994E7496A2EF80551F24692ED22F4FD223EFE13428B015927587544
687611256EA2F23F72612C7986D312EEDCC7DFD39EA50055D56AFEA575098EAF
7F25D12A150F3BFD4C04B8408F523EA977C5BAB45A67A4550DE3E57228065403
80D07A7D64B5672D8C65BE458BD1E47F1464DF5006644DEA3F3CBCFE96E3DC0A
823941CE532B788117E8D8B1B538D0E5F725D7700E71CDAD350F65FD9E7AFD98
9380A2576223B558E974173A4D5D5E35F22B54E868ED01A834253A76D48F6118
9A841D10C92D6049213095E58A8A312F4CAEC7F7DA8B39DFB8C123CB85EAB9B4
A2E648774BE757F6862EC008D7551D777F1541B6C6D805E243D2B9CA1F1D06D1
A3807F7D3956FCA20BC4309BB6BE99DE6872A51DB57CD0369A4F17B720EC0A73
A683FCE227D9023920DA4CAD3DFC5B6EE473BFE2F1854785D5691478D859EF16
B7BC8FF5A4EE389879A6A442258A87C7AF95DE1DF5EAB034AB96592015CCCF74
C76CEFA267138E0C98B167C05214516AFCBBB771BEA5FCE08A129146E2B3B22E
D33DB2B551B1F86AA14869074875E6A006389BD371FEA99C1AE93436B7AA70C8
D6945B6F0F238A915BC2B9161DF31085A43A7C35A4D590EEBDF63C1D4B1D2CBA
E9FA142EE9E0134D5A895D2AF3B8A34DF126E90B106A641812D760CAF9C93C1A
FD250EFBC9599CA617C7F6C10F1AAE8E8F3A1FF8FA7FE80C220A53B298304F4D
FE2C9E80A4001C761D6014011A6A5EEBFD5811AEFA7D70C00F6AF2AD4BB5E67B
```

### 3. `welch_state_bank_more_than_free` (n=16, expected 11.2, 0.7)

- **Printed identity:** Welch State Bank (NE Oklahoma). Masthead is a six-branch 'Direct Inquires To:' [sic] ladder -- 918-788-3373 Welch / 918-542-2000 Miami / 918-255-6611 South Coffeyville / 918-544-9100 / 918-476-8317 / 918-276-1430 with six PO boxes -- then 'ACCOUNT NUMBER n', 'STATEMENT DATES mm/dd/yy-mm/dd/yy', 'PAGE n of m', product line 'More Than Free Business Checking'. The literal 'Welch State Bank' appears only in a continuation header / check-image block. Stray print token 'DnpAndE Y' between sections.
- **Oracle:** 'Beginning Balance / Days in Statement Period / <n> Deposits/Other Credits / <m> Checks/Other Debits / Ending Balance' with leading counts, plus a 'Total For This Period | Total Year-to-Date (| Previous Year Total)' overdraft/returned-item box; some printings add a 'Daily Ending Balance' grid.
- **Nearest reader:** analysis/core_processor_sectioned.py / core_processor_counted.py (same lineage, different labels); no welch module
- **Risks:** Row order is DESCRIPTION -> mm/dd -> AMOUNT, so a leading-date row regex matches nothing. Amounts unsigned (sign from the section banner). Most printings have neither a running balance nor a daily grid, so beginning+credits-debits=ending is the only closure. Several months of one account (3964684) dominate the cohort -- yield is concentrated in few customers.
- **Merged from:** s1(1 of jh_core_proportional_skin),s3,s4,s7,s8,s9,s11,s12
- **VERIFY (adversarial):** identity_confirmed=True; sampled 16; misfiled []
  - oracle present: All 16 examined (not a sample: identity furniture grepped on 16/16, full text read on CF3F90A5 and F6291BF9, heads on 361167E3/732DD4B3, grid+tail on 160D382A, and all 16 parsed end-to-end arithmetically). PRINTED AND VERIFIED: (1) one-line summary box "Account Number n Beginning Balance B Days in Statement Period D <nc> Deposits/Other Credits C <nd> Checks/Other Debits Dr Ending Balance E" — leading counts confirmed, present 16/16, and B+C-Dr=E closes exactly 16/16; (2) an overdraft/returned-item box "Total For This Period | Total Year-to-Date", with a third "Previous Year Total" column on 2026 printings; (3) a "Daily Ending Balance" grid — present in 16/16, NOT "some" as the census said, with a "(continued)" spill in 3 docs. I replayed the parsed ledger against the grid day by day: ZERO mismatched days in 16/16, and the replayed running balance lands exactly on the printed Ending Balance in 16/16. The grid prints the opening day carrying the beginning balance, then only days with activity (17-22 rows vs 28-31 days in period), so calendar-day ADB needs a forward-fill but is exactly computable. A bespoke ~30-line regex reproduced printed credit count+sum AND debit count+sum EXACTLY on 16/16 (~3,300 rows total). There is no running-balance column on ledger rows.
  - ledger shape: Born-digital, not OCR: all 16 are model=native-pdf-text, single partition, empty:0 — deterministic text, no OCR noise. Columns are fully collapsed: an entire section's rows concatenate onto ONE physical line after a "Date Description Amount" header, and where the line does break it breaks unpredictably mid-section, so a line-oriented parser fails. Field order is DESCRIPTION -> mm/dd -> AMOUNT (census correct: a leading-date regex matches nothing); the working approach is to anchor on the `mm/dd <amount>` token pair and take the description as the text between anchors. Descriptions do NOT wrap; they carry internal multi-space padding ("ACH Deposit          DIGITAL TECHNOLO PAYROLL") and occasional trailing sequence tokens ("LN PyXXXXXX6925    1"). Amounts are unsigned, sign comes from the section banner. Negatives use a TRAILING minus ("1,000.87-"), in the summary box and throughout the daily grid. THE CENSUS MISSED A THIRD ROW GRAMMAR: a "Checks Cleared / Listed in numerical order" section with header "Date Check Amount Date Check Amount", two column-pairs, SINGLE-DIGIT months ("1/20 2226 500.00"), a `*` check-number suffix meaning gap-in-sequence, and footer "(*) indicates gap in sequence". Ignoring it is exactly the 1-5 missing debit rows I measured in 14/16 docs (e.g. 361167E3 short 5 rows / 1,161.95, which those five checks sum to precisely). Both the checks table and the daily grid are COLUMN-MAJOR interleaved, so left-to-right reading yields non-monotonic dates — de-interleave by sorting on date. TRAP: trailing check-image pages reprint "Number: 2226 Date: 1/20/2026 Amount: $500.00<F>" for items already counted in the Checks table, so a whole-document amount scan double-counts; section-scoping avoids it (my parser's exactness on 16/16 confirms it). Dates are mm/dd only, year inferred from STATEMENT DATES; every period is a clean calendar month, so no year-end straddle.
  - multi-account (L-1): L-1 NEGATIVE — single account per statement, and in fact a single account across the whole family. Exactly one "More Than Free Business Checking" product line and exactly one "Days in Statement Period" summary box in each of the 16. No savings / money-market / certificate / loan sections anywhere. All 16 are ACCOUNT NUMBER 3964684 (one business, MARTIN SPLICING LLC). Sibling accounts (*5024, *5094, *3434) appear only as transfer counterparties inside description text, never as statement sections.
  - currency evidence: No "USD" or "CAD" token appears anywhere in any of the 16. The only currency glyph printed is "$" on the trailing check-image pages ("Amount: $8,000.00<F>"), present in 14/16 and absent entirely from 9EFD01C58E412513 and CF3F90A50FEB07F5 (which have no check-image page). Institution is unambiguously US — Welch, Oklahoma; six 918-area-code branches; PO boxes in Welch/Miami/South Coffeyville/Chouteau/Vinita OK — so USD by jurisdiction default. Not a Canadian institution; the RBC/CAD ceremony and jurisdiction-default doctrine are not implicated here.
  - ceiling: 16/16 — I am raising the census's 11.2. This is not an estimate from a sample: I ran the arithmetic on every document in the family. Credit count+sum, debit count+sum (once "Checks Cleared" is handled), beginning+credits-debits=ending, and a day-by-day replay against the printed Daily Ending Balance grid all reconcile EXACTLY on 16/16, from clean born-digital text. Four independent oracles agree on every document. Honest expected validated: 15-16 — I hold back a fraction of a document only for integration surprises outside the text layer (whatever the harness requires beyond count/sum/balance closure, e.g. the open DESC-ATTRIB description-attribution policy, since descriptions here are positional rather than delimited). There is no technical shortfall I could find. Note the family cannot GROW: a repo-wide grep for these shas, for 3964684, and for "welch" returns nothing, so all 16 are genuinely uncovered and none sits on a pinned surface — but there are also no other Welch documents in the corpus to add later.
  - confidence: 0.88 HIGH (raised from the census's 0.70) on the reader axis — justified by direct arithmetic proof on the full population rather than inference from a sample. I would NOT raise it above 0.9 because the reader would be tuned against exactly one customer's printings, so its behavior on any unseen Welch template is unmeasured.
  - strongest refutation: The technical refutation failed — I went looking for the family to break and instead found it is the cleanest one I have read: born-digital text, four agreeing oracles, exact closure on all 16. The one real objection is CONCENTRATION, and the census understated it. It calls the risk "many months of one account"; the truth is 16 of 16 documents are the SAME account (3964684) of the SAME business, a near-contiguous 01/2025-05/2026 monthly run (only 03/2026 missing) whose beginning/ending balances chain month-to-month across the entire family. So: (a) you would ship a bank-specific module whose entire validation evidence is one customer's statement stream — zero template diversity, no second customer to prove generalization, and the printings that other Welch customers would produce (multi-account statements, interest-bearing sections, service-charge blocks, "Other Credits" without a "Deposits" banner) are wholly unobserved, making the true out-of-sample yield unknown; (b) if validated count is ever weighted by unique borrower or deduped by account, this family is worth ONE relationship, not sixteen; (c) the family is capped — nothing else in the corpus is Welch, so the module can never earn more than these 16. A secondary, smaller point: identity detection must not key on the literal string "Welch State Bank", which is absent from 2/16 (9EFD01C5, CF3F90A5) because those have no check-image page; the reliable furniture is the six-branch "Direct Inquires To:" phone/PO-box ladder plus "More Than Free Business Checking". If batch-7 staffing is scored on engineering-hours-per-validated-document this family is excellent; if it is scored on breadth of institutional coverage, it is one customer wearing a bank's letterhead.
- **shas:**
```
160D382A8CDF6898002AA969CD3F36E0177A11A5E0B7F5D147F5DCF61B116C02
29A4D03ECAFB0574B6C937B9D9F85DD8528C16632BEBDF6864BB2B2DE401C3C2
361167E3A263C346D948EFA40BC987E772D1A86AAFC164B8FD080893A4F9AD4E
4AA76269600A6B850995A3E446A2AAE3C61D57C1EC6BB3F9A749904D890CE947
6BB2BB7EE8CE443CA9484CD116DD1FE2523D6E4F77CAE6AC59CB5DC87C2544B0
732DD4B397EA962E8B9EB54F23A795598DB3171C5E027C99AD2105C2EBD9F624
7413D110AD142631AEF1EA0BC4B96EAAE388C38FDF99BEB4642C0E6E61B75088
78B930F7FE9A8BDEC0FB57972CF161E770794DED6CD4FA3708403F5B148589E3
8DCAB0CF5E3A8160BC39903F2C2930A471132C2BAD1AE68343A94035DBDD2F9C
9EFD01C58E412513A386A9EE1D5FCBF70FB5EF961763640B1E66FB89F7C89F7C
B9945604EA91AE460592EE16821F0536C2E64B341E18A39CDA256221B213C274
C5DB096DA4ADE8397E3D286366664E3FA63A7CCB647A1357DDF7DE042CD73D0D
CF3F90A50FEB07F5D3D808C40D9F5293A89DB1F5E743CE63379E5726BF0793F0
D5C818CC0BAADC25B537784105EDBC9302DAF8927B06C5A5FCC67039F47934DC
F6291BF90BAD9FC4BFCB87E5C9B0A181DBCBCF17C23B22E762852C573E07B0EA
F8155CC5F2F7A42C22EE1C18E23AE4AFF3E75D4E5850953391C00154823836CD
```

### 4. `cu_summary_of_accounts_date_posted` (n=13, expected 7.15, 0.55)

- **Printed identity:** One credit-union core under three mastheads (OnPoint Community CU / onpointcu.com; Addition Financial / AdditionFi.com, PO Box 958471 Lake Mary FL; HighPoint FCU / highpointfcu.com, Olean NY). Furniture: STATEMENTS SUMMARY then SUMMARY OF ACCOUNTS (Name | Beginning Balance | Ending Balance) closing on Total; JOINT OWNERS:; per account a SUMMARY block interleaved with a FEES This Period | Year-To-Date block; ledger banner ACCOUNT ACTIVITY FOR <PRODUCT> nnnn / NO ACCOUNT ACTIVITY FOR ...; footnote that an asterisk on the date means effective date.
- **Oracle:** Per account: Beginning Balance, <n> Total Credits/Deposits, <n> Total Debits/Checks, Ending Balance (counts printed as a leading integer, including explicit zeros on dormant shares), plus a document-level Total row and a per-row running Balance.
- **Nearest reader:** analysis/symitar.py (genre); no registered reader matched any member
- **Risks:** Every member is L-1 multi-share (2-4 accounts, dormant siblings print zero-count lines). The FEES sub-block is physically interleaved with the summary lines, so a line-adjacent parser pairs 196 Total Debits/Checks with Overdraft Fees. Two ledger column variants (single signed Amount vs split Debit/Credit) - bind from the printed header, not by position. Effective-date asterisks are a dating-policy question for ADB.
- **Merged from:** s1(A0A17154 of cu_share_suffix_ledger),s2,s3,s5,s6,s8,s10,s12
- **VERIFY (adversarial):** identity_confirmed=True; sampled 13; misfiled []
  - oracle present: PRINTED AND VERIFIED on all 13: (a) per-account "SUMMARY" block with Beginning Balance and Ending Balance; (b) leading-integer counts with their signed period sums — "<n> Total Debits/Checks -$X" / "<n> Total Credits/Deposits $X" (Addition, HighPoint) or "<n> Total Debits" / "<n> Total Credits" (OnPoint) — explicit zeros printed on dormant shares; (c) a document-level SUMMARY OF ACCOUNTS table (Name | Beginning | Ending) closing on "Total" / "Total Balance"; (d) a per-row running Balance on every ledger row. NOT printed: any daily-balance grid (zero of 13). Printed ADB: exactly ONE of 13 (A20A4F2D, "Average Daily Balance: $30,308.90", and only on the dividend-bearing share) — ADB is NOT a family oracle. OnPoint members additionally print a second, INDEPENDENT count/sum oracle in tail recap blocks ("TOTAL CLEARED CHECKS: 10 -5,878.90", "TOTAL WITHDRAWALS, FEES AND OTHER DEBITS: 173 -28,314.15", "TOTAL DEPOSITS, INTEREST AND OTHER CREDITS: 41 31,704.13") whose debit count (173) DISAGREES with the front summary (177) — a reader must not use the recap as the oracle. I mechanically reconciled the front-summary oracle against a join-and-chain extraction of the full text of all 13: running-balance chain has ZERO internal breaks (only account-boundary breaks), and total row counts land EXACTLY on the printed counts (e.g. 2046D9CE 256/256, A0A17154 278/278, 4C25E50F 84/84, 574D0EDA 203/203, EAF90DA0 55/55, 8C6F6729 26/26). With a leading-keyword direction rule, Addition sums land exactly ($35,992.75 / -$71,310.97 on 4C25E50F; $284,828.77 / -$255,336.83 on 574D0EDA). With "(Rejected)" reversal-pair suppression, OnPoint lands exactly (53C929C2: 30 credits 33,259.82 and 177 debits -39,055.76; 7DF42D16: 41 credits 31,704.13 and 177 debits -32,148.39).
  - ledger shape: Three furniture dialects over one CU core. Banner "ACCOUNT ACTIVITY FOR <PRODUCT>" (Addition appends the share suffix; OnPoint/HighPoint do not) with "... (continued)" repeats and a repeated column header on every page. COLUMNS COLLAPSE: Addition/HighPoint print the header "Date Posted Description Debit Amount Credit Amount Balance" but the text layer carries only ONE signed amount token per row, so the census's "bind from the printed header" mitigation is moot — position is gone and sign is the only signal. OnPoint prints a single "Amount Balance" pair. WRAPPING IS THE DOMINANT HAZARD: when the description is long the "amount balance" pair is orphaned onto the FOLLOWING line (roughly 40-60% of OnPoint rows; frequent on all three), the row is anchored only by the leading date, and description fragments also continue AFTER the amount line and ACROSS page boundaries (a bare fragment can be the first body line of a page, before or after the column header). Dates: OnPoint MM/DD/YYYY, Addition MM-DD-YYYY, HighPoint MM/DD/YY. AMOUNTLESS NON-TRANSACTION ROWS are interleaved and must be dropped — "Pending credit/return for $X on card nnnn", bare "Mail Deposit" notices, "Reverse Starter Checks" (6 in A20A4F2D, 13 in 4C25E50F, 6 in 574D0EDA). SIGN DOES NOT GIVE DIRECTION: "Withdrawal Adjustment Debit Card Credit Voucher …" rows carry POSITIVE amounts yet the CU counts them under Total Debits/Checks (14 such rows in 4C25E50F alone, 7 in 574D0EDA); direction must come from the leading transaction keyword. OnPoint further prints "(Rejected)" reversals whose original debit AND reversal credit are BOTH excluded from the printed counts and sums (10 in 7DF42D16, 6 in D6485565, 3 in 53C929C2) — pair suppression is mandatory, and the tail CLEARED CHECKS / WITHDRAWALS / DEPOSITS recap blocks (multiple date-amount pairs packed per text line) must be excluded from the ledger. OnPoint's SUMMARY OF ACCOUNTS also collapses TWO account rows onto ONE text line ("Business Savings 5.00 5.00 Business Checking 6,769.71 973.77"). Addition's FEES This Period | Year-To-Date block is interleaved with the summary lines exactly as the census warned — line-adjacent parsing pairs "196 Total Debits/Checks" with "Overdraft Fees".
  - multi-account (L-1): All 13 are multi-account MEMBER statements, and this is the load-bearing finding. HighPoint (2046D9CE, 9DD44157, A0A17154): 4 shares, and THREE of them genuinely post (e.g. 2046D9CE checking 228/10, payroll 9/4, insurance 3/2; only TAXES-0001 is 0/0). Addition (4C25E50F, 554486FB, 574D0EDA, 8C6F6729, A20A4F2D, DB0E1737, EAF90DA0): 2 shares and the savings share ALWAYS posts real transfers and MONTHLY SVC FEE (1-2 credits and 1-2 debits every month) — two genuinely active deposit ledgers, not a dormant sibling and not yield-only. OnPoint (53C929C2, 7DF42D16, D6485565): 2 shares, savings prints "NO ACCOUNT ACTIVITY FOR BUSINESS SAVINGS" with 0/0 counts and beginning == ending == 5.00 — a DORMANT sibling. No statement designates a publishable single account: the masthead prints the MEMBER number (Addition "Account Number XXXXXXXX58", HighPoint "Member Number: XXXXXX6507"), and OnPoint's "Primary Account Number 4665815587" is the DORMANT SAVINGS share (the operating checking is ...5702), so a reader that takes the masthead number publishes the checking ledger under the savings account number. The existing precedent analysis/symitar.py states the rule in force: dormant deposit siblings are skipped, but "Where TWO deposit accounts genuinely post, the single-account extraction schema cannot represent the document (L-1) and it is declined rather than published under one account's name." PROJECT_STATUS.md on main still carries "G5 multi-account & packages | OPEN (L-1, L-2)" and the open queue lists "L-1 architecture (evidence ~40 docs)". Under current doctrine only the 3 OnPoint members are publishable; the 7 Addition and 3 HighPoint members are L-1 declines.
  - currency evidence: No printed currency evidence at all — grep for USD / CAD / "currency" / "Canadian" across all 13 returns nothing; amounts carry a bare "$" (Addition, OnPoint/HighPoint print unsigned-of-symbol figures in the ledger). All three institutions are US credit unions with printed US identity: OnPoint Community CU (onpointcu.com, 503.228.7077, "Federally Insured by NCUA", Portland OR), Addition Financial (AdditionFi.com, PO Box 958471 Lake Mary FL), HighPoint FCU (highpointfcu.com, 1201 Wayne Street Olean NY). No Canadian institution and no FX line anywhere, so USD by jurisdiction default with zero doctrinal friction — this family raises no currency question.
  - ceiling: Honest expected validated under the CURRENT architecture: 3, not 7.15 — and it could be 0 if the reader takes the masthead account number. The extraction physics are excellent (I reconciled the printed oracle EXACTLY on every one of the 13 with a join-and-chain parse: zero internal balance-chain breaks, exact total counts, exact per-direction counts and sums once the keyword and rejected-pair rules are applied), so extractability is NOT the constraint. The constraint is L-1: 10 of 13 have two-to-three genuinely posting deposit accounts and are declines under the rule symitar.py already enforces. Only the 3 OnPoint members (53C929C2, 7DF42D16, D6485565) have a single active ledger beside a dormant $5.00 share, and each of those still needs (a) account identity taken from the section header "BUSINESS CHECKING - Account 4665815702" rather than the masthead "Primary Account Number 4665815587", (b) "(Rejected)" pair suppression or the stated-count gate fails (10, 6 and 3 pairs respectively; the delta is exactly +k credits and +k debits and shifts both sums), (c) the tail recap/CLEARED-CHECKS blocks excluded, (d) the collapsed two-accounts-on-one-line SUMMARY OF ACCOUNTS row parsed. So 3 is a realistic-but-not-free 3. If batch 7 instead scopes L-1 multi-account emission, the same reader plausibly reaches 12 of 13 — everything reconciles — with the one residual defect being that dividend-bearing Addition accounts OMIT the dividend posting from the printed ledger (A20A4F2D: last running balance 97.33 vs printed Ending Balance $98.51, credits 22 extracted vs 23 printed, credit sum short by exactly the printed $1.18 dividend), which breaks end-balance and credit reconciliation unless a synthetic row is derived from "Dividends Earned This Period". Staffing note: this is three printed grammars, not one, so it is a larger cell than n=13 suggests.
  - confidence: 0.30 LOW on the census's 7.15 expected-validated figure (I believe the true figure is ~3 under current architecture, ~12 only if L-1 ships); 0.90 HIGH on the printed identity, the oracle inventory, the ledger shape, and the L-1 classification, all of which I verified against full text.
  - strongest refutation: The family is L-1 blocked and the census did not price that in. Every member is a MEMBER statement, not an account statement, and 10 of 13 have two or three deposit accounts that genuinely post (all 7 Addition members' savings share posts transfers and a MONTHLY SVC FEE every month; all 3 HighPoint members have three active shares). The project's own registered precedent, analysis/symitar.py, states the governing rule verbatim — dormant siblings may be skipped, but "Where TWO deposit accounts genuinely post, the single-account extraction schema cannot represent the document (L-1) and it is declined rather than published under one account's name" — and PROJECT_STATUS.md on main still shows "G5 multi-account & packages | OPEN (L-1, L-2)". The handoff corpus repeats "multi-account: L-1 blocked; fail closed, record" as standing instruction to cells. So a batch-7 cell staffed on this family without L-1 in scope can publish at most the 3 OnPoint documents, and even those carry a trap: OnPoint's masthead "Primary Account Number" names the DORMANT savings share, so the W-F6 marked-account precedent points at the wrong ledger and a reader following it would either publish an empty ledger or attach the checking ledger to the savings account number — a correctness defect, not a validation win. Secondary refutation: the printed count oracle is not the naive ledger count. OnPoint excludes "(Rejected)" reversal pairs from BOTH counts and sums (verified: suppressing them moves 53C929C2 to exactly 30/33,259.82 and 177/-39,055.76, and 7DF42D16 to exactly 41/31,704.13 and 177/-32,148.39), and Addition counts positive-amount "Withdrawal Adjustment ... Credit Voucher" refunds as DEBITS, so any reader binding direction to sign fails the stated-count gate on nearly every member.
- **shas:**
```
2046D9CEAE1BB42BF6E4080DE9821D69AF5532B6B47F36033E979301910D0CCA
4C25E50F65E9BB195DCA3FD1A95E0E1D65BB2D47C8F57A7616B75F2BE1B27B76
53C929C29BBA7A7C0AD30DFEE3DCF656CA7A20BC58CA87D797BB025C628F2248
554486FB7B34EEA4FA814D15B0BEC65BCD77039B87C87F88D7C0BBB97BE54819
574D0EDA37087CC4C8CBABE85ABF0BF5ABC38CFC07E64D9649FC16371ABE26CC
7DF42D168EF592B6CDB48EF5F10D028E2E64768B9A34BBEB06EC09DC93F88417
8C6F67293F3EF7DFEB6FC19DAA438FBCEABE89811581382AFEEA85C561C9C7FA
9DD441570C0076CFB98B128B71C78FB99952C73FFD925AA145326DBD7E644B50
A0A17154688E7BFA25EFC5FB09A3076F10E265AE80B8EF6756DD33EA1B0C4090
A20A4F2DD3E4356E421BC507885570928071DB1CF2F85B51CE9181987A0AA664
D648556542E9D28950388047FFDA8F3F6BD5E58848B90EF9C47782C5AB1DD978
DB0E1737F4691450D3A3BEB22355A2605630B0334CD324D191FDDC1C7146C8A9
EAF90DA0CC4E21E62F575FCA7FB6D2B3247782FA71DE25A6D0C4E45D3E1B102F
```

### 5. `business_classic_statement_of_account` (n=8, expected 6.0, 0.75)

- **Printed identity:** Same core processor as core_enclosures but a different summary issue and no masthead in the text layer. Statement Date: m/d/yy top-left; Return Service Requested + Primary Account <name> XXXXXXnnnn; banner Statement of Account <PRODUCT> (BUSINESS CLASSIC / BUSINESS PLUS) + Account Title:; then Beginning Balance m/dd/yy $x, the bare word Summary, Credits (N) +$x / Interest Paid +$ / Debits (M) -$x, Ending Balance m/dd/yy $x; sections Deposits & Credits and Debits & Withdrawals; Daily Balance Information printed as a flat run of m/dd amount pairs.
- **Oracle:** Dated beginning and ending balances, parenthesised counts on both directions, signed totals, plus a Daily Balance Information grid and (on some) Average Ledger Bal. / Average Collected Bal. / Days in the Statement Period / Images Included.
- **Nearest reader:** analysis/fiserv_premier.py (this is its parenthesised-counts issue - near_miss fired at 0.125-0.25 without claiming), core_processor_daily.py, core_processor_counted.py
- **Risks:** Institution is image-only on every member, so registration must be on the Statement of Account + BUSINESS CLASSIC + Summary/Credits (N) furniture. Long ACH descriptions (CO# / ID # - / TRACE # -) wrap and push the amount onto the following line. Several members carry fully empty even pages. Debit amounts carry a trailing minus.
- **Merged from:** s1(E750D4F9 of jh_core_proportional_skin),s3,s4,s6,s10,s12
- **VERIFY (adversarial):** identity_confirmed=True; sampled 8; misfiled []
  - oracle present: VERIFIED MECHANICALLY ON 8/8, not just eyeballed. Every member prints, in this order: "Statement Date: m/d/yy"; "Return Service Requested Primary Account <name> XXXXXX9539"; "Statement of Account BUSINESS CLASSIC Account Title:"; "Beginning Balance<NBSP>m/dd/yy $ x"; the bare word "Summary"; "Credits (N) +$x Interest Paid +$.00 Debits (M) -$y"; "Ending Balance<NBSP>m/dd/yy $ z"; sections "Deposits & Credits" / "Debits & Withdrawals" / "Checks in Number Order Date Check Number Amount"; a SECOND "Summary Average Ledger Bal $ / Interest Paid $ / Days in the Statement Period N / Average Collected Bal $ / Service Charge(s) $ / Images Included N"; then "Daily Balance Information" as a flat run of m/dd amount pairs. (1) Balance equation beg+credits-debits=end closes to the cent on 8/8. (2) A sign-anchored parse (unsigned $ tokens in the credits section; trailing-minus $ tokens in the debits section; $ tokens in the checks section) reproduces BOTH printed counts and BOTH printed totals exactly on 8/8 -- e.g. DC5D6A42 debits (70) = 59 ledger rows + 11 checks = $78,223.68 exactly; E750D4F9 debits (152) = 133 + 19 = $166,721.88 exactly. The printed debit count and total INCLUDE the Checks section; a reader that reads only "Debits & Withdrawals" under-counts by 9-19 items. (3) "Days in the Statement Period" equals the inclusive calendar span between the DATED Beginning and Ending Balance on 8/8. (4) Forward-filling the Daily Balance grid to calendar days reproduces the printed Average Ledger Bal on 8/8 (delta $0.00-$0.01 on seven, $0.09 on E750D4F9); averaging only the printed banking-day points is wrong by -$2,054 to +$3,522. Average Collected Bal equals Average Ledger Bal on all 8. NO per-transaction running balance anywhere -- the daily grid is the only balance series. "Images Included" and check-image pages present.
  - ledger shape: Native pdf text layer (model native-pdf-text), columns COLLAPSED into a single reading-order stream, and the row/line correspondence is broken in two opposite directions. (a) Long descriptors (ACH "CO#... 26/mm/dd ID # - ... TRACE # - ...", "DBT CRD"/"POS DEB" card rows, wire strings) push the amount alone onto the FOLLOWING line. (b) Short descriptors concatenate two transactions onto ONE physical line -- e.g. "3/16 DDA Regular Deposit $20,000.00 3/18 SQ260318 Square Inc PPD CO#... TRACE # -" then the second amount on the next line. So a line-based parser fails both ways; the ledger must be tokenised as a date-anchored stream with the amount taken as the next $ token. Debits carry a TRAILING MINUS ("$11.40-") and nothing else does -- that sign is the load-bearing direction discriminator. Real trap found in 46E7AB7C: a correction row embeds dollar amounts INSIDE the description -- "2/11 FR26021041817 CK DEP 2/6 CK DEP AS $1614.60 S/B$1014.60 $600.00-" (note $1614.60 has no thousands comma) -- so a "first amount" or "last amount on the line" heuristic grabs the wrong figure; only the trailing-minus filter survives. Second trap in E750D4F9: check 1698 prints "-See above-" instead of an amount (it is already in the ledger, and is correctly EXCLUDED from the printed debit count). Other furniture: page 2 is fully empty on 8/8; "This page intentionally left blank." pages on 7/8; continuation pages repeat "Account Number: XXXXXX9539" then "Date Description Amount" inline with the first transaction; section headers appear MID-PAGE, not page-aligned; addenda end in a literal backslash ("NTE*ZZZ*P7194219247\", "RMR*IK*...\"); the Beginning/Ending Balance labels are separated from their date by a non-breaking/replacement char, not a space; check-image pages AFTER the Daily Balance grid repeat "#1543 01/05/2026 $6,250.00" and must not be re-counted (cut the ledger at "Summary Average Ledger Bal"). Checks section is itself one long collapsed run of date/number/amount triples ending in "(*) Indicates gap in check number sequence".
  - multi-account (L-1): NO multi-account exposure (no L-1). All 8 print exactly one account, XXXXXX9539, on every page ("Primary Account ... XXXXXX9539", "Account Number: XXXXXX9539", "Primary Acct No. XXXXXX9539"). No savings/MMA/loan/sweep sub-account, no "Total for all accounts" block. BUT the far more important structural fact: all 8 documents are the SAME account and the SAME customer (Pipe Creek Enterprises LTD DBA Pipe Creek Marina, Sandusky OH) -- eight consecutive monthly statements, 11/03/25 through 6/30/26, with a continuous balance chain (each ending balance is the next beginning balance, verified across all 8). The family is one template instance x 8 months, not 8 independent institutions, so n=8 carries the evidentiary weight of n=1.
  - currency evidence: No printed currency code anywhere -- no "USD", no "CAD", no "Canadian", no currency column, no FX line, on any of the 8. Institution identity is image-only: no masthead, no FDIC/Equal Housing line, no PO Box, no customer-service block, no URL. Only textual institution hint is a phone number in one member's notice (E750D4F9: "Enhanced Account Analysis ... Contact 888.452.2654"). Everything else is unambiguously US: customer address Sandusky OH 44870 with a US ZIP+4, bare "$" amounts, US NACHA/ACH descriptors (CCD/PPD/WEB/TEL, CO#, TRACE #), and US ABA routing numbers inside the wire strings (021000021 JPMorgan Chase, 072413829, 062005690 Regions, 074903719, 121000248, 111000002x, 041000xxx). Under the ratified currency doctrine this is a plain US-jurisdiction USD default; there is ZERO Canadian/RBC-style exposure and no cross-currency package math risk.
  - ceiling: Honest ceiling 8/8, higher than the census's 6.0, but the DISTRIBUTION is bimodal not binomial. I did not merely inspect the oracle -- I mechanically reproduced it: a sign-anchored, date-tokenised parse hits both printed counts and both printed totals exactly on all 8, the balance equation closes on all 8, printed Days matches the calendar span on all 8, and the forward-filled calendar-day ADB reproduces the bank's own Average Ledger Bal within a cent on 7/8 (9c on the eighth). There is no residual extraction uncertainty. Because all 8 are one account's consecutive months from one PDF producer, a correct reader takes all 8 and a reader missing any one of five specific rules takes roughly none: (1) include "Checks in Number Order" in the debit count/total; (2) key debit direction on the TRAILING MINUS, never on amount position (the 46E7AB7C "$1614.60 S/B$1014.60 $600.00-" row); (3) derive the period from the DATED Beginning/Ending Balance, NOT from "Statement Date" -- they disagree on 4 of 8 (46E7 stated 2/27/26 vs period 2/02-3/01; DC5D stated 1/30/26 vs 1/01-2/01; BFDD stated 11/28/25 vs 11/03-11/30; B3B10 stated 5/29/26 vs 5/01-5/31), and the periods do NOT align to calendar months, so month-bucketing a package will skip and double days; (4) forward-fill the banking-day daily grid to calendar days before any ADB; (5) terminate the ledger at "Summary Average Ledger Bal" so check-image pages are not re-counted. Expected value ~7-8. The real refutation is strategic, not technical: 8 documents (1.3% of this 598-doc census) from a SINGLE borrower, on the same core processor the census already ranks #1 (core_enclosures_avgledger_leading_counts, n=58) and which fiserv_premier.py already near-misses at 0.125-0.25. Extending an existing rank-1/fiserv_premier reader almost certainly picks these up for free; a dedicated batch-7 cell is likely duplicated work for a single-customer package, and nothing learned here generalises to another institution because the institution is never printed.
  - confidence: 0.85 HIGH on identity, oracle presence and extractability (all three verified mechanically on 8/8, not inferred). 0.35 LOW on this being worth a dedicated batch-7 cell -- single borrower, 8 docs, same core processor as rank 1, existing near-miss reader.
  - strongest refutation: The strongest reason this family would NOT deterministically validate is not the text layer -- it is registration collision plus zero independence. All 8 members carry NO institution identity in the text layer at all, so the reader can only register on generic core-processor furniture ("Statement of Account", "BUSINESS CLASSIC", "Return Service Requested Primary Account", "Daily Balance Information", "Credits (N)"). The census itself says rank 1 (n=58) is the SAME core processor with the same "Credits (N)" grammar, and that fiserv_premier.py already near-misses these at 0.125-0.25. Whichever reader is built first with loose registration swallows the other's documents, and because all 8 of these are one account's consecutive months from one PDF producer, a single registration or parsing error fails all 8 simultaneously -- the outcome is 8 or 0, never the census's implied ~6. Two concrete parse landmines would each zero the family: the printed debit count and total silently INCLUDE the "Checks in Number Order" section (miss it and every one of the 8 fails count and total by 9-19 items), and a correction row in 46E7AB7C embeds "$1614.60" and "S/B$1014.60" inside the description ahead of the real "$600.00-", so any position-based amount heuristic picks the wrong number. A third, subtler one would pass extraction but fail the analysis layer: "Statement Date" disagrees with the true dated period on 4 of 8 and the Daily Balance grid is banking-day sparse, so a reader that trusts Statement Date or averages the printed grid points directly produces an ADB wrong by up to $3,522 while every count and total still reconciles -- a green extraction with a bad denominator, which is exactly the failure mode the ratified ADB doctrine exists to prevent. Also note the census's printed_identity over-claims a "BUSINESS PLUS" variant: all 8 sampled members print BUSINESS CLASSIC only.
- **shas:**
```
15E5D7BB9EB121DA279C7D4E0A3ADF137197C40D36A777331C9FA2EF9151C65E
46E7AB7C9A3BCF692E8CFCD338B3825D6FA3F4EB60E0331EEA78C45859CE2811
6634A1FD32BDA05008FCAB3895BE7AED441EF700B211AEF5F34EA2C9BCF47B2B
89880D7E1B8BA5838ADD26ECEBA83188703B5C09E4C0DE27C7FD848119013B7B
B3B10CF00AEB92A8EAA895AE20398683B5ED305A90FACD979FC5958FE96783C3
BFDD966CB63A8441BDED8827060F9CA14FC171A654C156933BC0D15C43A95929
DC5D6A42B078954F5AFD47141C545689A9CE318A5C1110D58B40ADF5215D232C
E750D4F9F8DCBCB2202F11663E8021287C588A890960F860BCFAC8274087ABCC
```

### 6. `frost_bank_business_checking` (n=9, expected 5.4, 0.6)

- **Printed identity:** Frost Bank (Texas). FOR INFORMATION CALL 210-220-5111 / 361-844-1001 OR 1-800-513-7678, P.O. Box 1600 San Antonio or P.O. Drawer 749 Corpus Christi Texas Member FDIC, STATEMENT ISSUED mm-dd-yyyy; underscore/tilde rules and the banner FROST BUSINESS CHECKING : ACCOUNT NO. nn nnnnnnn; an ASCII pipe box | DEPOSITS | WITHDRAWALS | over BALANCE LAST STATEMENT | NO. | AMOUNT | NO. | AMOUNT | BALANCE THIS STATEMENT; dashed section rules ---- DEPOSITS/CREDITS ---- and ---- DAILY BALANCE ----.
- **Oracle:** The boxed strip carries balance last statement, deposit count+total, withdrawal count+total and balance this statement as one whitespace-separated value row, plus Activity Items Processed and Cash Processed; most printings add a DAILY BALANCE grid.
- **Nearest reader:** none (no frost module); nearest fixed-width shapes analysis/texas_bank.py, core_processor_counted.py
- **Risks:** Monospace mainframe print: the summary is a bare run of six numbers whose meaning comes only from the rule-drawn header above, so binding is positional. DEPOSITS/CREDITS prints TWO logical transactions per physical line separated by a pipe - ignoring it merges two transactions. Column order also differs between printings (DATE TRANSACTION AMOUNT vs DATE AMOUNT TRANSACTION DESCRIPTION). No running balance.
- **Merged from:** s4,s5,s6,s7,s8,s10,s11
- **VERIFY (adversarial):** identity_confirmed=True; sampled 9; misfiled []
  - oracle present: Sampled all 9 (n=9), full text read end-to-end on 39309BCD56995684 and 9A08EDD6BAA34D4A, full structural/section read on the other 7. Printed and VERIFIED in 9/9: the ASCII box value row carrying six ordered numbers = balance last statement, deposit NO., deposit AMOUNT, withdrawal NO., withdrawal AMOUNT, balance this statement; 'Activity Items Processed N' and 'Cash Processed $X'. DAILY BALANCE grid present in 9/9 (census said only 'most' — refuted, it is universal here). NOT printed anywhere in any of the 9: any average daily balance (no 'AVERAGE' token), any running per-transaction balance, any interest/APY block, any statement period start/end range (only 'STATEMENT ISSUED mm-dd-yyyy'). I built a ~40-line throwaway parser and reconciled against the printed oracle: box arithmetic (bal_last + deposits - withdrawals = bal_this) holds 9/9; deposit count exact 9/9; deposit sum exact 9/9; withdrawal sum exact 9/9; withdrawal count exact 9/9 once one rule is applied (see refutation); daily-balance first cell always equals BALANCE LAST STATEMENT and last-by-date always equals BALANCE THIS STATEMENT, giving a free internal cross-check; zero unparsed ledger lines across all 9.
  - ledger shape: Native text layer ('model: native-pdf-text', partitions=1, no OCR) — clean, no column collapse. Dates and amounts stay on one physical line; descriptions do NOT wrap. Only cosmetic defect is the masthead rule rendering as a run of U+FFFD replacement chars, which never touches the ledger. Sections are delimited by dashed rules: DEPOSITS/CREDITS, CHECKS PAID, OTHER WITHDRAWALS/DEBITS, DAILY BALANCE. Multi-up packing is separated by a literal '|' and the packing ORDER DIFFERS BY SECTION: DEPOSITS/CREDITS 2-up is ROW-MAJOR (left cell then right cell, dates ascend); CHECKS PAID 3-up is COLUMN-MAJOR and ordered by check number, NOT by date; DAILY BALANCE 3-up is COLUMN-MAJOR by date. Critically, ONE DEPOSITS/CREDITS section can carry TWO different column layouts back to back, each with its own header line — a 2-up 'DATE TRANSACTION AMOUNT' teller sub-block followed by a single-column 'DATE AMOUNT TRANSACTION DESCRIPTION' block. OTHER WITHDRAWALS/DEBITS is always single-column and re-emits its section rule and header on every continuation page (up to 5 times in one document); continuation pages repeat the account banner with '(CONTINUED)'. Descriptions are internally sub-fielded by multi-space runs (payee / memo / trace id) that collapse into one string — relevant to the open DESC-ATTRIB escalation. Tail pages are check images printing 'mm/dd/yy', '# num', '$amount' on separate lines outside any dashed section — a whole-document amount sweep would double-count checks; section-scoped parsing is immune.
  - multi-account (L-1): No L-1. Single FROST BUSINESS CHECKING account in 9/9 — exactly one distinct 'ACCOUNT NO.' per document, with continuation pages repeating that same account marked '(CONTINUED)'. No savings, loan, money-market or CD blocks anywhere. Note the whole family is only TWO distinct account numbers across two obligors (one San Antonio masthead, one Corpus Christi masthead), 4 and 5 consecutive monthly statements respectively; closing balances chain perfectly month to month within each obligor, which independently confirms the parse. Transaction descriptions reference INTERNET FUND TRANSFER TO/FROM ACCOUNT XXXXX#### — sibling accounts at the same bank, but they are not statemented here and must not be read as a second account section.
  - currency evidence: No printed currency code anywhere — zero 'USD' tokens in any of the 9. The only currency glyph is a bare '$' on 'Cash Processed' and on the check-image captions. Evidence is purely jurisdictional and unambiguous: 'P.O. Box 1600 San Antonio, Texas 78296 Member FDIC' / 'P.O. Drawer 749 Corpus Christi, Texas 78403-0749 Member FDIC', US phone numbers 210-220-5111 / 361-844-1001 / 1-800-513-7678. Under the ratified currency doctrine this is a US jurisdiction default to USD. No Canadian exposure and no FX content, so this family is doctrinally inert for the open ATB/package-FX questions — it will not exercise currency_source provenance beyond the plain US default.
  - ceiling: 8 of 9 honest expected, plausibly 9 — the census's 5.4 at 0.60 UNDERRATES this family and I could not refute it. Basis: I did not merely inspect the furniture, I ran a prototype parse and it reconciled every printed oracle on every document (box arithmetic 9/9, deposit count and sum 9/9, withdrawal sum 9/9, withdrawal count 9/9 with one rule, zero unparsed ledger lines 9/9). The text layer is native PDF text with no OCR noise, section rules are byte-stable, and the daily-balance grid gives a second independent oracle in all 9. Two fixes carried the entire gap from my first naive attempt: sub-dollar amounts print with NO leading zero ('.13', '.62', '.75' — a '\d+\.\d{2}' regex silently drops them and breaks both count and sum), and CHECKS PAID carries '*' (break in check sequence) and '#' (received electronically as image) flags between the check number and the amount. I withhold the 9th document because of the overdraft form: negative balances print with a TRAILING minus plus ' OD' ('1,678.15- OD'), appearing in exactly 1 of 9 documents in exactly 1 cell — rare enough to survive casual testing and sign-flipping enough to corrupt ADB on the one document that has it. Other modelled-but-cheap hazards: mm-dd dates with no year where the daily-balance grid opens on the PRIOR period's closing date, crossing the year boundary in 2 of 9 (year must come from STATEMENT ISSUED mm-dd-yyyy); the DAILY BALANCE grid splitting across two page blocks in 1 of 9; and zero-amount ATM INQUIRY rows printed in the withdrawals section. Staffing note: because the 9 are 2 obligors x consecutive months, they are near-clones — a reader that clears one clears nearly all, so effort is low, but the failure modes are fully correlated.
  - confidence: 0.75 MEDIUM-HIGH — raised from the census's 0.60 because the reconciliation was demonstrated end to end rather than inferred, but deliberately held below 0.85 for two reasons I could not resolve read-only: the sample is only 2 account templates so it says little about other Frost printings, and I do not know the validation harness's gate set, so a single unmodelled gate would fail all 9 together rather than a fraction.
  - strongest refutation: The strongest genuine refutation is a count-semantics trap the census did not identify: the printed withdrawal NO. EXCLUDES 'SERVICE CHARGE/FEE' rows while the printed withdrawal AMOUNT INCLUDES them. Every one of the five Corpus Christi statements carries exactly two such rows (ACTIVITY ITEMS CHARGE and NON-F...), so a reader that counts every withdrawal line reconciles the sum perfectly and still fails the count by exactly +2 on 5 of 9 documents — a silent, systematic, sum-passes/count-fails split that is easy to ship. If the validation harness gates on transaction counts, this family scores 4/9 until that rule is found. Second: there is NO printed average daily balance in any of the 9 and the DAILY BALANCE grid lists activity days only (17-23 cells for a ~30-day period), so a calendar-day ADB per the ratified ADB doctrine must be DERIVED by forward-filling across gap days — it is not a printed oracle. If the gate demands a printed ADB, this family scores 0/9 on that gate regardless of how clean the ledger is. Third, and the reason I did not push confidence higher: n=9 is really 2 obligors, so these failure modes are perfectly correlated — this family is a single reader bet dressed as nine documents, and the census's per-document expected-value framing overstates how much independent validation evidence it can produce. The census's own stated risks, by contrast, are largely overstated: the six-number strip is positionally bound but its order was IDENTICAL in 9/9, the count fields are bare integers while the money fields always carry '.dd', and the internal arithmetic self-validates — so the 'bare run of six numbers' is far safer than ranked.
- **shas:**
```
39309BCD5699568420F9E79AB14562657C8FCDD468D0D3463E9FED39D0CFDABE
4051FCDB5FDB82B79EB10581E6634CCC4844537AE9C5DE4011D969B6BBE1BD1B
794B22ED4AAB4D8D93C5BCAD82A214331F83BB9B110BDB1726FB17DF0935F2B4
9A08EDD6BAA34D4AD7F0C1BCEFA9ABE7A9BD78E01AE242FE9EDF5B4498E8E92B
A3C4A174DC64FBBC7F918FA435ED32790AEE2932AD50C82EF640A5D4FD53E3A7
AB3B864D013F609A4E6AA940AD1B2A45DF589084FC41F461E02C04BE1AECE566
B393D1C8A0FBB3C8D724FE317B06974FAD4988DC636ADEA3FF2C7891E5EB64B9
B46984457A8EBF5CB6F8DB7B85B2375B5536E77FD77A4CFD8FF0835D491378E9
B818C675A47C57F0A230A0B9C1E5B9616812CD05DDA1314AD709B516F5A48F49
```

### 7. `bank_ozk_plus_less_summary` (n=8, expected 5.2, 0.65)

- **Printed identity:** Bank OZK. No wordmark in the text layer; identity is the disclosure sentence citing ozk.com/disclosures plus 2804xxxxxx account numbers and FDCS BKOZ deposit descriptors. Product banner <PRODUCT>* ACCOUNT - <acct> (SMALL BUSINESS CHECKING*, INTEREST PLUS CHECKING*), then the all-caps sentence summary PREVIOUS STATEMENT BALANCE AS OF mm/dd/yy: / PLUS <N> DEPOSITS AND OTHER CREDITS: / LESS <M> CHECKS AND OTHER DEBITS: / CURRENT STATEMENT BALANCE AS OF mm/dd/yy: / NUMBER OF DAYS IN THIS STATEMENT PERIOD:; then CHECK TRANSACTIONS (SERIAL DATE AMOUNT, three-up, * marks a serial break) and OTHER TRANSACTIONS (DATE DESCRIPTION DEBITS CREDITS); some print BALANCE BY DATE.
- **Oracle:** The four-line sentence summary is a complete dated arithmetic oracle with both counts embedded between the verb and the label, plus a day count; several printings add a BALANCE BY DATE grid and an AVERAGE LEDGER BALANCE.
- **Nearest reader:** analysis/balance_by_date.py (the BALANCE BY DATE issue), analysis/core_processor_counted.py (sentence-summary shape); no ozk module
- **Risks:** Direction in OTHER TRANSACTIONS is carried ONLY by which of two adjacent unlabelled columns the figure lands in, and the text layer flattens both onto one line - the printed counts and totals are what disambiguate it, so the summary is load-bearing, not merely a check. One member (6E589801) prints no institution at all, only a mail-suppression control line and SMALL BUSINESS CHECKING*, and has a customer reconciliation worksheet on the back page.
- **Merged from:** s1(sg 6E589801),s3,s4,s6,s7
- **VERIFY (adversarial):** identity_confirmed=True; sampled 8; misfiled []
  - oracle present: ALL 8 print the complete dated four-line sentence summary with BOTH counts and BOTH totals embedded ("PREVIOUS STATEMENT BALANCE AS OF mm/dd/yy: / PLUS <N> DEPOSITS AND OTHER CREDITS: / LESS <M> CHECKS AND OTHER DEBITS: / CURRENT STATEMENT BALANCE AS OF mm/dd/yy: / NUMBER OF DAYS IN THIS STATEMENT PERIOD: <D>"). ALL 8 also print a POPULATED "BALANCE BY DATE" grid (verified the "DATE AMOUNT  DATE AMOUNT  DATE AMOUNT  DATE AMOUNT" data row in every member), whose last entry equals the printed CURRENT STATEMENT BALANCE. The 4 INTEREST PLUS members (27FB, 3261, 4A14, 6F85) additionally print AVERAGE LEDGER BALANCE, INTEREST EARNED/PAID, APY, INTEREST RATE and PAYER FEDERAL ID NUMBER 71-0130170; the 4 SMALL BUSINESS CHECKING members do not. CHECK TRANSACTIONS (SERIAL DATE AMOUNT, two-up, "*" = serial break) appears only on the 4 INTEREST PLUS members. IMPORTANT: the grid lists only days WITH activity, not calendar days, so ADB work must forward-fill. I did not merely observe the oracle, I EXERCISED it: I reconstructed the full signed ledger for 3 documents from prev-balance + daily grid + check list, and all three closed EXACTLY on ending balance, credit count, credit total, debit count and debit total (12CB 17/53,423.11 + 19/45,333.03; 6E58 16/58,750.00 + 23/78,631.92; 27FB 32/48,989.20 + 54/47,203.54).
  - ledger shape: Native PDF text (model: native-pdf-text), no OCR noise — but catastrophically flattened. An ENTIRE transaction table collapses onto ONE physical line: "OTHER TRANSACTIONS DATE DESCRIPTION DEBITS CREDITS 01/02 FDCS BKOZ DEPOSIT 945207818887 287.71 01/05 ... 2,142.10 01/05 ...". There are no row breaks; rows must be split on mm/dd tokens. The DEBITS and CREDITS columns are BOTH collapsed to the same position, so direction is absent from the text layer entirely. Confirmed row-split and amount-extraction traps, all seen in printed text: (a) date-like tokens INSIDE descriptions — "InvoicesRent 03/2026 2,720.00" (27FB) and "Wire In 96114164 ... BMG OF 26/04/01 18,000.00" (9BE2) — the latter defeats even a \d\d/\d\d(?!\d) guard; (b) wrapped description continuations emitted AFTER the amount: "... Funds Transfer 25.00 via Online", "... 275.00 Inv 634"; (c) POS trace numbers after the amount: "... 800.00 002215", "... 69.88 045661" (no decimal, so a strict amount regex survives); (d) an embedded dollar amount inside a description: "03/25 CHK# 2794 AMT $1,800.00, OVERDRAFT FEE 35.00" — first-amount rules get 1,800.00, last-amount rules get the correct 35.00; (e) a description literally beginning with digits: "03/09 26 PH ACH PAYMEN 108.00"; (f) negative daily balance printed with leading minus: "03/24 -45.90". Structurally, the customer reconciliation worksheet is the REVERSE side and sits at page 2 of N, INTERLEAVED between transaction pages, and check-image pages sit at the END after BALANCE BY DATE re-listing every check and several deposits as "$39010.00 01/15/2026" / "2790 $661.06 03/03/2026" — stray amounts that must be excluded or they double-count. The BALANCE BY DATE grid is printed column-major 4-up but flattens row-major; (date, amount) pairs stay intact, so it only needs sorting by date.
  - multi-account (L-1): NOT multi-account at the document level (L-1 = no). Every one of the 8 statements carries exactly ONE product banner, ONE account number and ONE summary block. However the family is two DIFFERENT accounts belonging to two DIFFERENT customers, forming two clean consecutive-month packages: acct 2804329303 / SMALL BUSINESS CHECKING* / GA obligor = 12CB (Jan), 6E58 (Feb), 78A4 (Mar), 9BE2 (Apr) 2026; acct 2804041852 / INTEREST PLUS CHECKING* / FL obligor = 27FB (Mar), 3261 (Apr), 6F85 (May), 4A14 (Jun) 2026. Both chains verify: each statement's printed CURRENT balance equals the next month's printed PREVIOUS balance (e.g. 27,796.63 -> 7,914.71 -> 10,114.35 chain on ...9303; 12,496.33 -> 20.82 -> 2,217.63 chain on ...1852). Note the statements do reference sibling accounts in descriptions ("ONLINE BANKING TRANSFER TO SDA XXXXXX1056", "TO DDA XXXXXX2459") but those accounts are not statemented here.
  - currency evidence: NO printed currency code anywhere in any of the 8 — no "USD", no "CAD", no currency column. The only currency marks are bare "$" glyphs on the reconciliation worksheet and on the check-image pages ("$39010.00 01/15/2026"). Institution is unambiguously US: "CUSTOMER SERVICE CENTER / P.O. BOX 196 OZARK, AR 72949 / 800-274-4482", "PAYER FEDERAL ID NUMBER: 71-0130170" (a US EIN), ozk.com/disclosures, and US obligor addresses (DOUGLASVILLE GA 30134; MIAMI FL 33122). So USD by US jurisdiction default, NOT by printed evidence. No Canadian exposure — this family raises no RBC/CAD-style currency-doctrine question.
  - ceiling: Honest expectation ~5-6 of 8, and the distribution is BIMODAL rather than a smooth 65%-per-doc — which makes the census's 5.2 point estimate right by accident rather than by shape. Every document has a complete, closed, exercisable oracle: I fully reconstructed 3 of 8 signed ledgers from the printed data alone and all 3 tied EXACTLY on ending balance, both counts and both totals, and all 8 carry the identical furniture (summary block + populated daily grid) needed to do the same. So if the cell builds the required machinery — a per-day sign solver using the BALANCE BY DATE delta, with the printed counts and totals as GLOBAL backtracking constraints — 8/8 is genuinely reachable. If the cell builds a conventional row/column reader, or infers direction from description keywords, near 0/8 validate, because the descriptions actively lie (see refutation). The two failure modes are also CORRELATED, not independent: the 8 docs are only 2 obligors and 2 templates, so one solver defect takes out a whole 4-document package at once. Discounting for that correlation, for the confirmed subset-sum ambiguity, and for the row-split traps (especially "BMG OF 26/04/01" in 9BE2, which defeats the obvious lookahead guard), I land at 5-6 expected. Staffing note: this family should be carded as an ARITHMETIC RECONSTRUCTION task, not a parsing task — the near-reader analysis/balance_by_date.py is relevant only to the grid, and no existing module does constrained sign solving.
  - confidence: 0.60 MEDIUM — I could not refute the family (8/8 identity clean, 0 misfiles, oracle stronger than the census claimed and demonstrably closing 3/3), but I am holding confidence DOWN rather than raising it, because whether these validate deterministically depends almost entirely on a build decision (constrained solver vs. ordinary reader) rather than on anything in the documents, and because the 8 docs are only 2 correlated packages.
  - strongest refutation: The strongest reason this family would NOT validate deterministically: direction is not merely unlabelled in the text layer, it is AFFIRMATIVELY MISLEADING, so no local rule of any kind can recover it. Identically-worded "FDCS BKOZ DEPOSIT 945207818887" lines land on BOTH sides of the ledger within a single statement — proved by arithmetic, not guessed: in 12CB the 01/05 58.68 and the 01/12 77.89 and 148.98 "DEPOSIT" lines are DEBITS (01/12 requires credits of exactly 5,474.38 against debits of exactly 1,395.11 to reach the printed 34,448.40), and in 6E58 the 02/12 39.95 "DEPOSIT" is a DEBIT. A keyword/description classifier does not degrade here, it systematically inverts real transactions. Recovery therefore requires a global constrained solve, and that solve is NOT always locally unique: on 27FB 03/13 the day delta admits TWO valid sign assignments over [838.64, 0.46, 0.02, 1700.00, 100.00, 25.00, 0.48, 283.00] (credits must total 2,539.12, satisfiable as {838.64, 1700.00, 0.48} or {838.64, 1700.00, 0.46, 0.02}), and BOTH reproduce the printed totals exactly — only the printed CREDIT COUNT of 32 discriminates them. So the census's phrasing understates the exposure: the counts are not "load-bearing rather than a check", they are a REQUIRED cross-day backtracking constraint, and a statement with two or more such ambiguous days that the global counts cannot separate would be unresolvable in principle. Secondary refutation pressure: 6E589801 prints no institution name at all (its reverse page is entirely BLANK in the text layer — the census is wrong that this member carries the reconciliation worksheet; that worksheet is on 12CB and 27FB), so standalone institution attribution for it rests only on the 2804xxxxxx account, the FDCS BKOZ descriptor and the summary grammar, and would fail outside its package context.
- **shas:**
```
12CB962E765A978FF8AE4F4437AFA339725D3639D20731E272B936CE9F0C1D45
27FB68128D1BFF551F77B2E10A1441AF3FFDA03D3FB5B7874FACEB9ABEB4673B
3261C8B14924B4C5E5AB7B4B6B6BEC118855962A9B89DDBAB5EB19665DD9BD8C
4A1403F44D2B6254EA3C737F253ABAE40F07353983D86163D1778000C687E776
6E589801F4B784F3F36D7E82A2EF2682B1F45405267CE556136C0F3FBE4E0F91
6F85B52CA2A6C0A8CCDDA808CCEBE668A91EAF29D838D00C606DF34D1565F2D0
78A4F9E9CB479532D1EC0E64BAAD31A25F6805074906F12AC12D59CD139356DC
9BE2AD7D75215D9B0FA0C5000BAE506D5ACF3928B7B764D8B586A6AF90BB9105
```

### 8. `space_coast_cu_member_statement` (n=8, expected 5.2, 0.65)

- **Printed identity:** Space Coast Credit Union. Representation of Printed Document / Member Statement; the four-phone Brevard / Miami-Dade / Broward / All Other block; P.O. Box 419001 Melbourne FL 32941-9001; the tagline SCCU Members' Watchdog Promise - Honest People, Trusted Products, Time Valued; footer SCCU Routing Number: 263177903 / SCCU.com; Statement Summary (Account Type | Beginning Balance | Ending Balance); per account <Product> Account Summary and Account Activity; an Overdraft and Returned Item Fees period-vs-YTD box.
- **Oracle:** Per account Days In Period, Beginning Balance, Total Money In, Total Money Out, Ending Balance and Total Service Charges, cross-checked by a document-level Statement Summary roll-up, with a running Balance bracketed by printed Beginning Balance and Ending Balance pseudo-rows.
- **Nearest reader:** analysis/symitar.py (genre), midflorida.py / secu.py (Florida CU siblings); no sccu module
- **Risks:** L-1: Business Savings plus Business Free Checking on every member, and a zero-activity account prints a summary with an empty activity table that must not read as a parse failure. Header cells arrive out of visual order, so extract by label not position. Two dates per row (transaction and effective) - a canonical-date policy is needed. One member opens with a full-page disclosure letter, so page-1 anchoring fails.
- **Merged from:** s4,s5,s7,s8,s9,s12
- **VERIFY (adversarial):** identity_confirmed=True; sampled 8; misfiled []
  - oracle present: All sampled n=8 print, verbatim: (1) document-level "Statement Summary" = Account Type | Beginning Balance | Ending Balance, one row per account; (2) per account "<Product> Account Summary" carrying Account Number, Days In Period, Beginning Balance, Total Money In, Total Money Out, Ending Balance, Total Service Charges (savings additionally prints Interest Rate / Annual Percentage Yield Earned / Dividends Paid This Period / Dividends Paid Year To Date); (3) a running Balance column on every ledger row, bracketed by printed pseudo-rows "Beginning Balance $X" and "Ending Balance $X"; (4) an "Overdraft and Returned Item Fees" box, Total for this Period vs Total Year to Date, printed once per account section; (5) a "Summary of Checks Cleared" recap grid (Check No. | Amount x4 across, "*" flags a skipped check number). I did not merely read these labels - I reconciled them numerically on all 8: Beginning + Total Money In - Total Money Out == printed Ending Balance, and the harvested ledger rows chain unbroken from the printed Beginning Balance to the printed Ending Balance with zero unplaced rows in every document (row counts 183-408). Sum of harvested credits/debits equals printed Total Money In / Total Money Out exactly on 8/8 once one netting rule is applied (see refutation). NOT printed anywhere: no daily-balance grid, no Average Daily Balance, no interest-earned line on checking, no ISO currency code. Days In Period is calendar (28/30/31 matching the printed period), which suits the ratified calendar-day ADB doctrine; ADB is computable from the intact running-balance chain but is never printed.
  - ledger shape: Native PDF text layer (model: native-pdf-text, empty:0) - no OCR involved. Columns are fully collapsed: Money In and Money Out arrive as ONE signed amount token (debits carry a leading minus, credits none, no $ sigil in the ledger), followed by the unsigned running balance. Descriptions never wrap onto a trailing continuation line. TWO row shapes exist. Shape A (dominant, all 8 docs): "TXNDATE EFFDATE DESCRIPTION AMOUNT BALANCE" on one text line - but 2-4 consecutive rows are frequently concatenated onto a SINGLE physical line (e.g. one line carrying Deposit, Withdrawal and Check as three complete rows), and the terminal "Ending Balance $X" sentinel is sometimes appended to the same line as the last transaction (62C13D4F, 7D31DD82) and sometimes stands alone (0624AC46). Splitting is deterministic on the M/D/YY M/D/YY boundary. Shape B (272041FB only, exactly 67 occurrences, cleanly formed - 67 bare date lines, 67 amount-only lines, 67 well-ordered triples): long AVIDPAY/EDI descriptions force a three-line block emitted OUT OF ORDER as description line, then a bare "TXNDATE EFFDATE" line, then a bare "AMOUNT BALANCE" line. A Shape-A-only reader silently drops all 67 rows (my naive pass lost 118,550.00 of money-in and produced 18 chain breaks); a reader that handles the triple recovers 371/371 rows and lands exactly on the printed ending balance. Two dates per row is real and they genuinely differ on some rows (5/28 txn / 5/29 effective; 6/8 txn / 6/9 effective) - transaction date is the correct canonical, since the printed ordering follows it. Header/value cells do arrive out of visual order, and worse, the two products use DIFFERENT block orders: savings is [labels][interest labels][interest values + Ending Balance + Total Service Charges][values], checking is [Account Number][Total Service Charges][labels][values][Ending Balance]. Extraction must be by label, never by offset. Per-page furniture: "<MEMBER> Page N of M", "<Product> Account (continued)", a repeated column header, "Continued to next page", and a bare numeric mail-code footer.
  - multi-account (L-1): L-1 confirmed and perfectly uniform: exactly two accounts on all 8, always in the order Business Savings then Business Free Checking, each with its own printed Account Number under its own "<Product> Account Summary". The savings account is zero-activity in 8/8 - its Account Activity table is empty and collapses into the header line itself ("Transaction Date Effective Date Transaction Description Money In Money Out Balance Beginning Balance $5.00 Ending Balance $5.00"), so a reader requiring >=1 row per account fails on every document. No loan, credit-card, or certificate sections appear; no third account anywhere. Worth flagging for staffing: the 8 documents are only TWO members - GRIMALDI CANDY COMPANY LLC (member 800220499, Feb/Mar/Apr/May 2026) and GARDEN AID LANDSCAPING LLC (member 800291365, Mar/Apr/May/Jun 2026) - four consecutive months each. Month-over-month continuity holds exactly (each ending balance is the next month's beginning balance for both members), which is a bonus cross-document oracle, but it also means the family exercises only two real template configurations, not eight.
  - currency evidence: No ISO code and no currency word is printed anywhere - I grepped USD / Dollar / Currency / Foreign across the family and got nothing but the boilerplate phrase "The dollar amount of the suspected error" in the error-resolution notice. Currency must come from jurisdiction default, and the printed evidence for it is unambiguous and US-only: "SCCU Routing Number: 263177903" in the page footer, P.O. Box 419001 Melbourne, FL 32941-9001, the Brevard/Miami-Dade/Broward/All Other Areas phone block, Florida member addresses, and "Federally Insured by NCUA. Equal Housing Opportunity." on the disclosure-letter page. Amounts carry a bare "$" in the summary blocks and no sigil at all in the ledger. Merchant descriptors end in a two-letter state plus "US" country suffix (FLUS, CAUS, TNUS, WIUS, DCUS) - these are POS country codes, not currency, and a naive currency sniffer could misread them. No Canadian institution, no foreign-exchange rows, no cross-currency exposure. statement.currency = USD by US jurisdiction default; currency_source should be recorded as jurisdiction default, not printed.
  - ceiling: 8 of 8 is genuinely achievable and I would forecast 7, not the census's 5.2. I did not just eyeball the oracle - I built a throwaway parser and closed every document deterministically: all 8 reconcile Beginning + Total Money In - Total Money Out to the printed Ending Balance, all 8 produce an unbroken running-balance chain from the printed Beginning Balance to the printed Ending Balance with zero unplaced rows, and harvested credit/debit sums equal the printed Total Money In / Total Money Out to the cent on 8/8. The whole family is one core (Symitar-genre) at one template revision; there is no OCR involved and no text-layer rot beyond the recoverable Shape-B blocks. The two things that will actually cost engineering time are the Shape-B three-line rows (272041FB, 67 of them) and the "(Rejected)" netting rule (62C13D4F, 78E26472) - both are one-time costs inside a single sccu.py, and both fail LOUDLY against the running-balance chain rather than silently, which is the good failure mode. I hold back from calling it 8 only because the family is two members deep, so a subtle member-specific assumption cannot be caught by a wider sample, and because the disclosure-letter cover page (two documents, not the one the census claims) breaks page-1 anchoring.
  - confidence: 0.80 HIGH - raised from the census's 0.65 on direct numeric evidence rather than on template appearance. Downgrade to ~0.6 if the pipeline's validator compares harvested row sums against printed Total Money In / Total Money Out without a netting rule, because that alone costs 2 of 8.
  - strongest refutation: The strongest reason this family would NOT validate deterministically is a printed-total netting rule the census did not see, and which no generic Symitar-genre reader would guess. SCCU excludes rejected-item PAIRS from the printed gross totals while leaving both legs in the ledger and in the running balance. A rejected debit prints as an "External Withdrawal ... (Rejected)" row carrying a POSITIVE amount (the money coming back), and the printed Total Money In excludes that credit while the printed Total Money Out simultaneously excludes the original debit. I measured it exactly: 62C13D4F is over by 1,438.06 on BOTH sides (one ALLY (Rejected) pair) and 78E2647278EC502A is over by 6,854.00 on both sides (2,600.00 UFS + 4,244.00 KAPITUS + 10.00 ONDECK, all suffixed "(Rejected)"). Note the trap is narrow and easy to over-fit: a sibling row in the same document, "Descriptive Deposit ACH Return Ondeck Revoked 2,676.92", IS counted in the printed totals, so the rule keys on the literal "(Rejected)" suffix, not on the semantics of a return. Any validator that asserts sum(credits) == printed Total Money In will fail 2 of 8 (25%) with a clean-looking chain and a correct ending balance, which is a confusing failure to debug. The second, independent refutation is 272041FB15350E44 alone: its 67 Shape-B blocks are dropped entirely by a one-line-per-row reader, losing 118,550.00 of money-in with only the running-balance chain (18 breaks) to signal it - if the reader does not validate the chain, that document validates its ending balance by luck of the sentinel while carrying an incomplete transaction list, which is worse than failing. Two further census corrections: the disclosure-letter cover page appears on TWO documents (6D0E6BA50DF1CAF9 and 7D31DD8257D6026B, both the April 2026 statements, both dated May 1 2026), not one, so page-1 anchoring must be a content probe not a page index; and "Total Service Charges" is not reconstructable from fee-labelled rows (78E26472 prints $75.00 = three Domestic Wire Wth Fee rows, while its two Stop Payment Fee rows and its $30.00 Insufficient Funds Charge sit outside that figure), so it must be read, never derived.
- **shas:**
```
0624AC4689BA526C33DA4034B897C7F9CF4A3633743983F1E4D88D6C3EC41228
272041FB15350E4448E746930A980098562749E0EC67FB5E1D2E5A94DA270231
62C13D4F0FF38474E23C9613A308DFD9E284CD0061EC7496A11E4277D1D952B9
6D0E6BA50DF1CAF9A485EC87C2F380572C9813757FCEDCA9C5A397B0CEDFF586
78E2647278EC502AE09D6C831732C4D1CB731BBCF9DC438BD0146F6CDD168A31
7B48A1E7134F90FEFE46189D9D372C5C5360DACCD6DF1176B0C566A32323B663
7D31DD8257D6026BD88A37F4BD389A5992971FE31A4A90EE9E1383EA3617FF09
CF1338DDC23EAB040E575E6F492D762E594815497A889DAED0C4795A1C550CF1
```

### 9. `accounts_at_a_glance_category_number_amount` (n=8, expected 4.8, 0.6)

- **Printed identity:** Community-bank core whose summary is a three-column category partition, under three mastheads (1STMERC.NET Cookeville TN; Independent Bank Memphis TN; MAVERICK BANK FORT DAVIS, PO BOX 1808 Fort Davis TX). Contact Us / Branch Name / Phone Number / Address / Online Access <DOMAIN>; Statement Date: / Account No.: / Page:; ACCOUNTS AT A GLANCE (Account No. | Sub Acct. | Account Title | Acct Type | Balance) closing on Your Total Deposits = x And Your Total Loans = y; then <PRODUCT> SUMMARY Type: **REG Status: Active over a Category | Number | Amount table (Balance Forward From, Deposits, Debits, Automatic Teller Withdrawals, Automatic Withdrawals, Automatic Deposits, Card Activity, Miscellaneous Fees, TOTAL SERVICE CHARGE, Ending Balance On, Average Balance (Ledger)); sections ALL CREDIT ACTIVITY / ELECTRONIC DEBITS / STATEMENT PERIOD ACTIVITY; footer Continued n/nnnn/1.
- **Oracle:** The Number column gives a printed item count for EVERY category alongside its amount, between a dated Balance Forward and a dated Ending Balance; Maverick printings add a DAILY BALANCE SUMMARY grid and a running balance, the Tennessee printings a COLLECTED BALANCE SUMMARY.
- **Nearest reader:** analysis/core_processor_counted.py, core_processor_sectioned.py, fiserv_premier.py (ACCOUNTS AT A GLANCE is Premier furniture); no per-issuer module
- **Risks:** The categories do NOT map one-to-one onto credits and debits (Deposits + Automatic Deposits + part of Card Activity are credits), so a reader needs an explicit category-to-sign map before the counts can gate anything. Maverick marks credits with a TRAILING plus and overdrawn balances with a TRAILING minus on the BALANCE column - three meanings for two characters in one grid. A 3-up deposit summary grid duplicates deposits also listed below.
- **Merged from:** s1,s2,s3,s9,s10,s11
- **VERIFY (adversarial):** identity_confirmed=True; sampled 8; misfiled []
  - oracle present: STRONGER than the census claimed on arithmetic, WEAKER on universality. What is actually printed: (a) the "<PRODUCT> SUMMARY Type : **REG Status : Active" block over a "Category Number Amount" table — verified to close EXACTLY on all 8/8. Maverick A78F1E6A: 78 trailing-plus rows = 308,723.07 = Deposits 5 + Automatic Deposits 73; 123 debit rows = 278,774.57 = Debits 27 + Automatic Withdrawals 95 + 1 TOTAL SERVICE CHARGE row; running balance chains with ZERO breaks over 201 rows to the printed ending 30,043.12. Same zero-break result on 2065EFBD (188 rows), 983F04D5 (199), FC3FF0D3 (205), each with credits/debits counts AND amounts matching the category table to the cent. 1STMERC 6E9A3A11: 63 card rows = 8,893.97 (Card Activity 63), 22 non-card electronic rows = 17,391.42 (AutoWdl 19 + MiscFees 3), 28 check-grid rows = 109,770.10 (Debits 28) — exact. Independent 3A9502DF: ATM_WDL 10/1,140.45, AutoWdl 3/397.94, Card 41/933.02, Fees 17/282.00, credits 49/7,840.30, MiscDebits 11/4,900.00 — all exact, and BalFwd(13.02-) + credits - debits = 158.27 = printed Ending. The full accounting identity closes on 8/8. (b) REFUTED: the count is NOT printed for EVERY category. No Number is printed for Balance Forward From, Ending Balance On, Average Balance (Ledger), SERVICE CHARGE / TOTAL SERVICE CHARGE, or for a zero-amount category ("Debits 0.00" bare in 3A9502DF and 889DAEBE). (c) Daily balances split three ways: Maverick (4 docs) prints DAILY BALANCE SUMMARY = true ledger, last row == printed Ending Balance, plus a per-row running balance column; Independent (1 doc) prints DAILY BALANCE SUMMARY = ledger, closes; 1STMERC (3 docs) prints COLLECTED BALANCE SUMMARY, which is NOT a ledger series — see refutation. Every grid is banking-day (20-22 rows against a printed "This Statement Cycle Reflects 29/30/32 Days"), so a calendar-day ADB needs forward-fill; 889DAEBE's grid additionally omits the first 13 days entirely (no activity). Maverick prints NO Average Balance at all; the TN/Memphis printings print "Average Balance (Ledger)" — a bank average, evidence-only under the ratified ADB doctrine, so this family offers no printed calendar-day ADB oracle anywhere.
  - ledger shape: Two shapes under one core. MAVERICK (2065EFBD, 983F04D5, A78F1E6A, FC3FF0D3): a single unified "STATEMENT PERIOD ACTIVITY" table, Date | Check/Description | Amount | Balance, strictly one transaction per text line, no wrapping, no column collapse; a 6-group regex over the raw text layer parsed 188-205 rows per doc with zero running-balance chain breaks. Credits carry a TRAILING PLUS on the amount; overdrawn balances carry a TRAILING MINUS on the balance (3 such rows in A78F1E6A) — two characters, but they sit in different columns, so the ambiguity is resolvable positionally, not lexically. TN/MEMPHIS (6E9A3A11, 889DAEBE, C47BEFE5, 3A9502DF): NO running balance column; activity is partitioned into named sections — ALL CREDIT ACTIVITY, ELECTRONIC DEBITS, CHECKS AND OTHER DEBITS, ITEMIZED SERVICE CHARGE — each Date | Description | Amount, one per line. The real text-layer defects are the 3-up grids: the deposit summary grid (Date Type Amount x3), the check grid (Date Check# Amount x3) and every daily-balance grid put THREE independent records on ONE text line in row-major order, so a line-oriented reader must split column-wise, not read the line. Three further traps I hit directly: (1) Independent embeds an auth timestamp "(MM/DD/YY HH:MM:SS)" INSIDE the description, so a date-anchored row splitter shatters rows — my first two parse attempts crashed on exactly this; (2) one row in 3A9502DF wraps, leaving the amount alone on the next line (LEWISBURG WATER ... / 53.22); (3) every document ends with IMAGE STATEMENT pages that restate every deposit and every check as "AM: <amount> CK: <n> DT: <date> SQ: <seq> Paid/Deposit" — 40 images in 6E9A3A11, 32 in A78F1E6A — which a naive amount-extractor will double-count. Separately, Maverick's CHECKS AND OTHER DEBITS grid duplicates checks already present in the unified STATEMENT PERIOD ACTIVITY ledger (CHK#5276 131.23 appears in both) and must be suppressed. Footer furniture is stable and parseable: "Continued n/nnn/p" and "End Statement n/nnn/pE".
  - multi-account (L-1): No L-1 in this family as sampled: all 8 are single-account. Seven print ACCOUNTS AT A GLANCE with EXACTLY ONE row and "Your Total Loans = .00"; the eighth (3A9502DF) has no ACCOUNTS AT A GLANCE block at all. One Account No. in every page header throughout each document; partitions=1 on all 8. The latent risk is real though not present: the AAAG grid (Account No. | Sub Acct. | Account Title | Acct Type | Balance) is structurally a multi-row table with a deposits-and-loans rollup, and the Maverick customer plainly holds five sibling accounts (transfers name CHK 3350/4513/4548/4602/2036) filed as separate statements — so a genuine multi-account AAAG printing almost certainly exists in the wider corpus and a reader must not assume one row.
  - currency evidence: NONE printed. A grep across all 8 for "$", USD, CAD, Canad, Dollar/DOLLAR and FDIC returned zero currency tokens — the only hits were incidental merchant names ("DOLLAR GENERAL", "DOLLARTREE"). Amounts are bare 1,234.56 with no symbol anywhere, including in the summary table and the balance grids. Currency is inferable ONLY from institution jurisdiction: MAVERICK BANK, PO BOX 1808 Fort Davis, TEXAS 79734, Tel (432) 426-3211; 1STMERC.NET, 860 East 10th Street Cookeville, TN 38501, (931) 528-6372; INDEPENDENT BANK, 5050 Poplar Ste 112 Memphis TN 38157, (901) 844-5050. All three US, no Canadian institution anywhere in the family, so this is a clean USD jurisdiction default under the ratified currency doctrine and raises no CAD/FX policy question. But it is an inference, not printed evidence — currency_source provenance for this family would be "jurisdiction default", never "printed".
  - ceiling: Honest expectation 6 of 8, plausible range 5-8 — above the census's 4.8, because the census under-rated the arithmetic and over-rated two of its three risks. Grounds for raising it: the summary identity (BalFwd + signed categories = Ending Balance) closes to the cent on 8/8, category counts AND amounts match extracted row counts exactly on every document I mechanically parsed (4 Maverick + 6E9A3A11 + 3A9502DF), and the four Maverick documents additionally chain a per-row running balance with zero breaks. That is a genuinely deterministic target. Grounds for not going higher: the 4 Maverick docs are near-certain (unified ledger + running balance + daily ledger grid, all three cross-checking) but the 3 1STMERC docs depend on how the harness treats COLLECTED BALANCE SUMMARY — if any daily-balance or ending-balance-from-grid oracle is required, they fail or, worse, silently pass wrongly (see refutation), and 3A9502DF's timestamp-in-description plus wrapped-amount row costs at least one extraction defect. So: 4 Maverick near-certain, 1 Independent likely, 3 1STMERC contingent — 6/8 expected, 5 if a daily-ledger oracle is mandatory, 8 only if the harness scores solely on the category-partition identity. Staffing note: the effort is one reader with a per-category sign map and section-scoped extraction, plus an IMAGE-STATEMENT suppressor and a 3-up grid column splitter — those last two are shared with any other Fiserv-Premier-core family, so the marginal cost is low even at 5 validated.
  - confidence: 0.70 MEDIUM — raised from the census's 0.60. Identity confirmed on 8/8 by printed furniture, and the oracle verified arithmetically rather than asserted. Held below high because (a) I cannot see the validation harness's pass criteria, and the collected-balance question below is decisive for 3 of 8; (b) n=8 across three mastheads with only 1 Independent Bank printing, so that variant is a sample of one; (c) the family key names furniture that is absent in 1 of 8.
  - strongest refutation: The strongest reason this family would NOT validate deterministically: the 1STMERC (Cookeville TN) printings do not print a daily LEDGER balance at all — they print "COLLECTED BALANCE SUMMARY", which is the ledger balance MINUS uncollected float, and it is a silent trap because it agrees with the ledger on most statements and disagrees on the ones that matter. In 6E9A3A11 the grid's last row is 05/29/26 13,276.17 while the printed Ending Balance On 05/29/26 is 26,966.17; the difference is exactly 13,690.00, the two same-day mobile deposits (5,764.00 + 7,926.00) still uncollected. In 889DAEBE (7,683.03) and C47BEFE5 (17,275.33) the last grid row DOES equal the printed ending balance, purely because those cycles ended with no float. So a reader that keys on "last row of the daily grid == ending balance" passes 2 of 3 and produces a wrong ADB on all 3 — a false-positive validation, the worst outcome. The collected series also dips deeply negative (18,644.61-, 9,353.01-, 14,352.46- in 6E9A3A11; 1,387.75- in C47BEFE5) while the ledger is positive, which would corrupt any negative-day or overdraft-day count. Two secondary refutations, both of which cut AGAINST the census's stated risks rather than for them: the census's "3-up deposit grid duplicates deposits also listed below" is REFUTED — in 6E9A3A11 the 6 grid deposits (67,877.51) and the 6 MOBILE DEPOSIT rows below (58,805.44) are DISJOINT and sum to exactly the printed Deposits 12 / 126,682.95; the actual duplication is elsewhere (the IMAGE STATEMENT pages, and Maverick's check grid against its unified ledger). And "part of Card Activity are credits" was NOT observed — Card Activity is debit-only in all four printings that carry it, matching to the cent. Two naming defects worth carding: ACCOUNTS AT A GLANCE, the phrase the family key is built on, is ABSENT in 3A9502DF, and that document also carries no masthead — "INDEPENDENT BANK" appears only mid-page under "Direct Inquiries About Electronic Entries To:". The true invariant is the "<PRODUCT> SUMMARY Type : ... Status : Active" header over "Category Number Amount", not the AAAG block; a detector keyed on AAAG would miss 1 in 8 today. Finally a sign trap the census missed: in 3A9502DF the description "MERCH BNKCD NSD DEPOSIT" appears as a CREDIT in ALL CREDIT ACTIVITY and as a DEBIT (234.51) in ELECTRONIC DEBITS in the same statement — sign must come from section membership, never from the description.
- **shas:**
```
2065EFBD0B1277B5F348499E7360798D3261A71AA41AC0BA6D5F258E3F91E093
3A9502DFFD9EA4D92C9B97FAD06A8A382AB6A3BA761F818E241B93CD63CBED45
6E9A3A110E6829EB6ECDE3F309E2094C9D493F1AD1923AD87D98E8BC145100DE
889DAEBE7D79133C142A46537574C0AD66805650D9D9F6F61AD7FBFB5EE31F8C
983F04D5AD628C79646B919E3694BEF9294CBE0A3B9F12B0318A05747C023BF1
A78F1E6A2231611D18173C0A59E4BD23BD1D0C5374844B87AE1B338A469F205F
C47BEFE559CB86008C7EF9D62DDB68FEA562D4DE55FAF763B9B8B3A7198EE352
FC3FF0D3ABA7BFADE1704F57639DE4E0B0CFEA2E839D62F66DA4725DBF31D636
```

### 10. `guardian_cu_statement_summary` (n=8, expected 4.8, 0.6)

- **Printed identity:** Guardian Credit Union (Prattville AL). Statement Dates: mm/dd/yy - mm/dd/yy over 1 Guardian Way| Prattville, AL 36066  334-244-9999 | www.MyGuardianCU.com repeated per page; Member #***nnn / Page n of m; a greeting line Hi, <FIRST>!; Statement Summary with Deposit Accounts Total Balance: and the grid ACCOUNT TYPE | PREVIOUS BALANCE | DEPOSITS | WITHDRAWALS | ENDING BALANCE; per share <PRODUCT> Suffix #nn Previous Balance:; back-page YOUR BILLING RIGHTS / Outstanding Items.
- **Oracle:** A four-figure printed row per suffix plus a Deposit Accounts Total Balance, each share section restating Previous Balance / Ending Balance / Average Daily Balance / Dividend Year to Date, with a running BALANCE column on every row.
- **Nearest reader:** analysis/symitar.py; no guardian module (near_miss fiserv_premier/regions all <=0.125)
- **Risks:** L-1 with 2-3 suffixes; the savings suffix can change printed NAME between cycles while keeping suffix #00, so account identity must key on the suffix. Dates print as Mon D with no year (year from Statement Dates). Withdrawal vs deposit is column-position only - use the balance delta. Unposted ACH NSF advisory rows carry no date and no balance and must be excluded. One printing has a column header with zero rows.
- **Merged from:** s5(FFAC0A88),s9(333E226A),s10,s11,s12
- **VERIFY (adversarial):** identity_confirmed=True; sampled 8; misfiled []
  - oracle present: PRINTED AND VERIFIED on 8/8: (a) "Statement Summary" + "Deposit Accounts Total  Balance: N"; (b) the grid "ACCOUNT TYPE PREVIOUS BALANCE DEPOSITS WITHDRAWALS ENDING BALANCE" with one four-figure row per suffix, e.g. "BUSINESS CHECKING (Suffix #71) 2,497.13 44,367.16 42,037.02 4,827.27"; (c) per-section restatement "<PRODUCT>  Suffix #nn Previous Balance: N" and closing "Dividend Year to Date   N Ending Balance: $N"; (d) a running BALANCE column on every posted row; (e) a closing "SUMMARY / Total Year-to-Date Earnings ... Year to Date Finance Charge ... Year to Date Nontax Dividends"; (f) an end-of-section CHECK RECAP grid "CHECK DATE AMOUNT" x3-across on the business statements; (g) a fee block "Period-to-Date Year-to-Date / Overdraft Fees / Returned Item Fees" (seen on E38FA786 only). I machine-reconciled all 8 documents end to end: for EVERY suffix the ledger reproduces printed Previous Balance, DEPOSITS total, WITHDRAWALS total and ENDING BALANCE to the cent, and the running-balance chain has ZERO breaks across 155/129/163/242/166/47/141/163 rows. NOT PRINTED: no transaction counts anywhere (the census "counts" oracle does not exist); no daily-balance grid (the running BALANCE column is the only per-row balance). CENSUS OVERSTATEMENT: "Average Daily Balance" is NOT a per-section field. It appears only as a continuation line under a posted dividend row ("Post Date: 03-31-2026 Average Daily Balance: 716.70") and only in 2 of 8 documents (7C7956EB, E38FA786 - both member ***803). It is absent from all six ***684 documents, including 596804AA/FFAC0A88 which do post a dividend ("Mar 31 Deposit Dividend 0.050% 0.60") and print the APY period but omit the ADB line. Worse for ADB doctrine: where printed, the figure is the DIVIDEND period ADB, not the statement-period ADB - savings suffixes show "APY 0.100% 01-01-2026 thru 03-31-2026" (quarterly) and one shows a stub "12-24-2025 thru 12-31-2025", while only the checking suffix happened to align to the statement month ("03-01-2026 thru 03-31-2026", printed unseparated as 46145.54). Treating the printed ADB as a statement-period ADB would be wrong on 3 of the 5 shares that print one.
  - ledger shape: Native text layer on 8/8 (model native-pdf-text, one OCR partition each, one trailing empty page on 7 of 8) - no image-only pages, no OCR route needed. Columns are FULLY COLLAPSED onto one line: "<TRAN DATE>[ <POST DATE>] <DESCRIPTION> <AMOUNT> <BALANCE>", e.g. "Jan 2 Withdrawal ACH Square Inc 169.00 2,659.09". Exactly two trailing decimals per posted row (amount then running balance), so the amount is recoverable positionally and the sign is recoverable from the balance delta. Descriptions do NOT wrap into the amount columns; instead detail spills onto following bare lines with no numbers ("TYPE: SQ260102 ID: 9591330001", "CO: Square Inc", "MAPLESVILLE SUPRMKTS MAPLESVILLE AL", "Daily Roundup", "SQ *ID - 2iWgTzuP - San Francisco CA"). Confirmed hazards, all of which I hit while parsing: (1) When TRAN DATE differs from POST DATE both print on one line with no delimiter ("Jan 6 Jan 7 Withdrawal Transfer 0071 150.00 1,810.13"; "Feb 28 Mar 1 Deposit POS ..."), so the tran date can fall OUTSIDE the statement window - a 1-or-2 leading "Mon D" token grammar is required. (2) Dates are "Mon D" with no year; one document is a TWO-MONTH window ("Statement Dates: 11/01/25 - 12/31/25"), so year inference must key on the window, and the en-dash in that header decodes as U+FFFD - never require a literal hyphen. (3) The section header repeats VERBATIM on every continuation page carrying the ORIGINAL previous balance - 7C7956EB prints "GUARDIAN CHECKING  Suffix #71 Previous Balance: 38,852.26" twelve times; the "(Cont)" marker is inconsistent (472A0966 and E38FA786 use it, the rest do not). Take the first occurrence per suffix or the balance chain resets. (4) Unposted advisory rows "ACH NSF Revenued $515.35" sit INSIDE the ledger with no date and no balance and a $-prefixed amount (confirmed in 472A0966, 596804AA, FFAC0A88, E38FA786); they must be excluded. (5) "Withdrawal Adjustment Debit Card Credit Voucher <amt>" rows INCREASE the balance and are booked by the CU as contra-withdrawals: they must be subtracted from the WITHDRAWALS total and must never enter DEPOSITS. This is the single rule that separates a tie-out from a miss - without it 4 of 8 documents (333E226A by 225.24, 596804AA/FFAC0A88 by 0.10+0.23, 7C7956EB by 32.09) overstate BOTH totals by exactly the adjustment amount; with it, 8/8 reconcile to the cent. (6) "Draft 2795 55.00 5,313.25" check rows carry no Deposit/Withdrawal keyword, so the balance delta (not the keyword) is the only universal sign source - though the census overstates this: every other posted row does print a literal "Deposit"/"Withdrawal" token. (7) The closing CHECK RECAP packs three checks per physical line ("2795 Jan 5 55.00 2798 Jan 5 294.51 2801 Jan 8 89.71") and duplicates the Draft ledger rows - a double-count trap; it is safe only because those lines start with a check number rather than "Mon D". (8) A suffix section can print its column header with ZERO rows (savings #00 in 5 of 8). (9) Furniture noise: bare page-sequence integers at the foot of each ledger page, mailer codes "1 62"/"0 0"/"1 14" under the address block, and an interleaved back-page legal sheet (PDF page 2) containing loose "$" tokens and "Balance Shown on this statement".
  - multi-account (L-1): YES - L-1 on 8/8, never a single-account statement. Member ***684 carries 2 deposit suffixes (#00 savings, #71 business checking); member ***803 carries 3 (#00 primary share, #01 roundup savings, #71 guardian checking). The Statement Summary grid enumerates every suffix with its own four figures, and each gets its own ledger section with its own Previous Balance, its own running BALANCE column and its own "Ending Balance: $N". Loans are NOT separate sections - they surface only inside transfer descriptions ("To RUFF,DAVID A XXXXXXXXXX Loan 0006", "Loan 0094"), so this is deposit-accounts-only L-1. The census risk about the savings NAME changing between cycles is REAL and observed: suffix #00 for ***684 prints "PRIMARY SHARE" in the 01/2026 cycle and "BUSINESS SAVINGS" in 02-05/2026 - identity must key on the suffix, never the product name. Inter-suffix transfers appear on both sides (roundup "Transfer To Share 0001" / "Transfer From Share 0071"), so a package-level rollup would double-count unless netted.
  - currency evidence: USD by US jurisdiction, NOT by printed code. No ISO code appears anywhere in any of the 8 documents - no "USD", no "CAD", no "Currency" label. The only currency mark is a bare "$" on the closing "Ending Balance: $4,827.27" line and on the unposted "ACH NSF ... $515.35" advisory amounts; ledger amounts and the Statement Summary grid print unsymbolled ("2,497.13 44,367.16 42,037.02 4,827.27"). Institution is unambiguously US: "Guardian Credit Union, 1 Guardian Way, Prattville, AL 36066  334-244-9999 | www.MyGuardianCU.com" in the per-page masthead and again in "REPORT ERRORS OR MAKE INQUIRIES TO:", plus the NCUA-style back-page line "Member Savings in this credit union are insured up to $250,000 per account" and an Equal Housing Opportunity notice. No Canadian exposure, so the RBC-CAD jurisdiction-default ceremony is not implicated here; this family should take the plain US jurisdiction default with currency_source = jurisdiction (not printed).
  - ceiling: Higher than the census's 4.8 on the tie-out gate, but gate-dependent. I ran a ~60-line naive text parser over the full text of all 8 and got 8/8 fully reconciled: every suffix's printed Previous Balance, DEPOSITS total, WITHDRAWALS total and ENDING BALANCE matched the derived ledger to the cent, "Deposit Accounts Total Balance" equals the sum of the suffix endings, and the running-balance chain broke zero times in ~1,200 posted rows. So on a "printed summary tie-out + unbroken balance chain" gate the honest ceiling is 8/8, realistically 7-8: the only thing standing between a first-pass reader and 8/8 is the Adjustment contra-withdrawal rule, which 4 of 8 documents require and which no one would guess (the row prints the word "Withdrawal" while the balance goes UP). Hand that rule to the cell and 8/8 is a defensible target; withhold it and expect 4/8. Two discounts against reading 8 as 8 independent wins: (i) 596804AA1ACD01EB and FFAC0A88768A8A59 are the SAME statement (member ***684, 03/01/26-03/31/26, identical grid figures, identical NSF advisories, same 12 pages) captured as two byte-different renderings (22,725 vs 22,482 chars - one splits "Statement Summary" and "TRAN DATE / POST DATE" across lines), so the 8 shas cover only 7 distinct statements and those two will always pass or fail together; (ii) the whole family is 2 members at 1 credit union over 7 consecutive cycles, so it is a narrow template sample - the reader will be well fitted to Symitar-style Guardian output and unproven beyond it. If instead the validation gate requires a printed statement-period Average Daily Balance under the ratified ADB doctrine, the ceiling collapses to roughly 0-2: 6 of 8 print no ADB at all, and the 2 that do print a dividend-period figure (quarterly or a partial stub) that is not the statement-period ADB for 3 of the 5 shares that carry one.
  - confidence: 0.85 HIGH — raised above the census's 0.60, but on evidence rather than agreement. I did not merely inspect the template: I re-derived every suffix's deposits/withdrawals/ending from the ledger text of all 8 documents and matched the printed oracle to the cent on 8/8, so the tie-out claim is machine-checked rather than eyeballed. The residual 0.15 is not about the template — it is (a) the Adjustment contra-withdrawal convention, which is inferred from 4 documents and 5 rows and could have a further variant (a debit-side adjustment) that I have not seen; (b) the sample being 2 members at 1 institution, so unseen suffix types (certificates, loans promoted to sections, a zero-suffix-only cycle) are untested; (c) the duplicate pair inflating apparent breadth; and (d) genuine uncertainty about which gate batch 7 will apply — the ADB-inclusive reading of this family is weak and I would not stake anything on it.
  - strongest refutation: The strongest honest case against staffing this family is breadth, not parseability. It is 8 shas that are really 7 statements belonging to just 2 members of one small Alabama credit union across consecutive 2026 cycles — a new reader module would be fitted to a sample with almost no internal variation (the same masthead, the same two-or-three suffix layouts, the same Symitar-derived furniture), and the census itself notes no existing guardian module and only weak near-misses (fiserv_premier/regions <= 0.125). Eight validated documents bought with a bespoke module that may never generalize is a poor ratio next to families with more distinct obligors. The second-strongest refutation is that the census's headline oracle is partly fictitious: it advertises per-section "Average Daily Balance" and transaction "counts", and neither survives contact — counts are printed nowhere, and ADB appears in only 2 of 8 documents and even there measures the dividend period, not the statement period. Anyone who sized this family expecting an ADB oracle sized it wrong. The third is the Adjustment trap: "Withdrawal Adjustment Debit Card Credit Voucher" rows print the word Withdrawal while the balance rises, and the CU nets them out of the withdrawals total rather than into deposits. This is silent — the running-balance chain stays perfect, so a reader that gets it wrong still looks healthy on every per-row check and fails only the summary tie-out, on 4 of 8 documents. What this refutation cannot claim is that the documents are hard to read: the text layer is native on all 8, one row per line with amount and balance adjacent, and I reconciled every suffix of every document to the cent. If the family is dropped it should be dropped for narrowness, not for risk.
- **shas:**
```
333E226A75FE544123159C1EAA83120BE56557E00F0B88D9DB78AC588C80829C
472A0966A5204513B90C0470791C7F6FB80C63E6A4DA1B612E41A1A5F1D29FCA
596804AA1ACD01EB1854A399CDE491F4D6E5A577DAC00BB7247D075CF36CCBAA
7C7956EB5E93DB1DA547E512443B898C8F4159E09B6192EC3BF13D3075C5FD58
C3D3E48F1E14AE2AB9DD448A891564271B028466170106B30227234D7C6944A6
E38FA786106F752E50941E30BF4013AD041A75C0C58B73280A566373FF905093
F5BC9FB6D084559E6C2D57D636B25427324195C8349149BE6FA6250F0805679C
FFAC0A88768A8A590297CB10182E86FFF73B4BE93724130F027732908B49B3AE
```

### 11. `poplar_bluff_activity_summary_running` (n=6, expected 4.8, 0.8)

- **Printed identity:** The running-balance issue of the same core processor as core_enclosures, printed for a Poplar Bluff MO bank (P O Box 160, Poplar Bluff, MO 63902  573.785.8461; no bank name in the text layer). Statement of Account / Statement Dates: m/dd/yy thru m/dd/yy / Page: n of m; an Activity Summary box (Account Number | Days in Cycle | Average Ledger Balance | Avg Collected Balance); product line (Totally Free Business Checking / Business Promise Checking) with Beginning Balance / <n> Deposits/Credits / <n> Checks/Debits / Service Charge / Interest Paid / Balance this Statement, restated as Statement Balance / Debits / Credits; a Total For This Period | Total Year-To-Date fee box; ledger banner Account Activity.
- **Oracle:** Beginning and ending balance, both counted totals, service charge, interest, average ledger and average collected, the totals restated a second time, AND a per-row running Balance - the summary is stated twice and the chain closes it.
- **Nearest reader:** analysis/fiserv_premier.py, core_processor_counted.py, core_processor_daily.py (core_processor_sectioned.py documents exactly this sectioned-vs-running fork)
- **Risks:** One page-1 mojibake OMR block must be skipped, and one member wastes its first two pages on a mailer sheet so the printed Page n disagrees with the PDF page index. Otherwise the cleanest of the core-processor issues: signed amounts, one row per line, running balance.
- **Merged from:** s1(5A93EF5A),s2,s7,s9,s10
- **VERIFY (adversarial):** identity_confirmed=True; sampled 6; misfiled []
  - oracle present: All six carry, printed on the page: 'Statement of Account / Statement Dates: m/dd/yy thru m/dd/yy / Page: n of m'; an 'Activity Summary' box with Account Number | Days in Cycle | Average Ledger Balance | Avg Collected Balance; a product line 'Totally Free Business Checking' followed by Beginning Balance | <n> Deposits/Credits <total> | <n> Checks/Debits <total> | Service Charge | Interest Paid | Balance this Statement; the trio restated as 'Statement Balance / Debits / Credits'; banner 'Account Activity' with column header 'Date Description Amount Balance'; a per-row running Balance; a 'Checks in Number Order' grid; and a trailing check/deposit image index. VERIFIED BY COMPUTATION on all 6/6, not just observed: a single one-line regex cut at the 'Checks in Number Order' banner reproduces the printed credit count, the printed debit count, the printed credit total, the printed debit total, and walks the running balance from printed Beginning Balance to printed Balance this Statement with ZERO chain breaks. NOT printed: there is no daily-balance grid and no balance-summary section anywhere in the family; the only day-level truth is the per-row running balance. Also NOT what the census implies: Service Charge and Interest Paid are printed but are 0.00 in all six (they exercise the label, not the arithmetic); 'Business Promise Checking' (named in the census identity) does not occur in this family at all; and the 'Total For This Period / Total Year-To-Date' overdraft-fee box is present in only 4 of 6 - the two 2025-dated members use an older template revision that omits it and carries disclosure typos ('appers', 'OCCURED') the 2026 members fixed. Bonus oracle: 'Days in Cycle' equals the exact calendar-day count of the printed period in all six (30/31/28/31/30/31), i.e. the denominator the ratified ADB doctrine requires is printed on the page.
  - ledger shape: The cleanest text layer I have seen in this census. One transaction = exactly one line, no exceptions: `M/DD  <description>  <signed amount>  <running balance>`. Columns do NOT collapse in the ledger. Descriptions do NOT wrap - the processor hard-truncates card descriptors to a fixed width and keeps ACH addenda (ID #- / TRACE #-) on the same physical line. Debits carry a leading minus INSIDE the amount token and negative running balances print as `-$x` (minus before the sigil, not after) - that is the single tokenizer trap, and it is what made my own first-pass regex silently drop three rows on 6A27035D until I fixed it; a reader that anchors on `\$` will lose exactly the overdraft rows. Continuation pages repeat 'Account Activity (Continued)' plus the 'Date Description Amount Balance' header; a bare 8-digit imaging sequence number is emitted once per physical page and sometimes lands BETWEEN two transaction rows rather than at the page end, so it must be filtered as a line, not as a page footer. Two regions genuinely are column-collapsed and both DUPLICATE ledger rows: (1) the 'Checks in Number Order' grid, three Date|Check No|Amount column-triples that serialize column-major so check numbers emerge out of sequence; (2) an unheaded trailing image index of `<acct> <mm/dd/yy> [<check no>] $<amt>`, two records per line, no thousands separators. Both sit after the 'Checks in Number Order' banner, so one section cut kills both; neither matches a date-first row pattern, so they are also naturally excluded. A full-page reconciliation worksheet (bare '$' tokens, 'BALANCE SHOWN ON THIS STATEMENT') sits on the back of printed page 1 and must be skipped.
  - multi-account (L-1): No - L-1 does not apply. Every one of the six statements covers exactly ONE demand-deposit account: a single 'Activity Summary' box, a single product block, and one and only one distinct account token across every 'Account Number:' furniture line in every member. There is no second account section, no savings/MMA block, no combined-statement relationship total. The one thing that could be mistaken for multi-account is a recurring ledger DESCRIPTION of the form 'Online Banking Xfer From: Checking - XXXX#### To: Checking - XXXX####', which proves the customer holds a sibling checking account at the same bank but that sibling is not statemented in any of these PDFs. Much more important, and the census does not say it: all six members are the SAME account of the SAME obligor - six monthly statements of one continuous series (Sep-25, Oct-25, Feb-26, Mar-26, Apr-26, May-26). I verified the series is genuinely continuous: each member's printed Balance this Statement is byte-identical to the next consecutive member's printed Beginning Balance across all four consecutive pairs.
  - currency evidence: No printed currency evidence of any kind. Zero occurrences of USD, CAD, EUR, 'US Dollars', or 'Canadian' in any of the six; amounts carry a bare '$' sigil only. Jurisdiction is unambiguously US and unambiguously domestic: the masthead return address is a P O Box in Poplar Bluff, MO 63902 with a 573 area-code phone, the addressee is in Missouri, and the card descriptors are Missouri/Arkansas/Alabama/Florida merchants. So: USD by US jurisdiction default, currency_source = jurisdiction, NOT printed. No Canadian exposure, so this family is doctrinally inert for the RBC-CAD line and contributes nothing to the FX/ATB escalations.
  - ceiling: 6 of 6. I raise the census's 4.8 rather than cut it, and I raise it on executed arithmetic rather than on the look of the page. I tried to break all six with the crudest extractor I could write - one line-anchored regex, one section cut at 'Checks in Number Order' - and every printed oracle closed exactly on every member: credit count, debit count, credit total, debit total all match the Activity Summary to the unit and to the cent, and the running-balance chain walks from printed Beginning Balance to printed Balance this Statement with zero breaks in 1,183 rows across the family. I then went after the hardest metric, the canonical calendar-day ADB, since no daily-balance grid is printed and it must be reconstructed from the chain: reconstructed end-of-day balances carried forward over the printed period reproduce the bank's printed Average Ledger Balance on all six to within about a dollar - pure per-day whole-dollar truncation on the bank's side, under 0.01% of the average - and the printed 'Days in Cycle' equals the calendar-day count of the printed period in all six, so the doctrine's denominator is corroborated on the page. Honest floor is 5, not 6, only because of the two mailer-cover members (see refutation). Real caveat for the STAFFING decision rather than the reading decision: this is six statements of one account of one obligor, so it is 6 documents but 1 template and 1 borrower - the coverage-percentage gain is real, the template-diversity gain is one.
  - confidence: 0.92 HIGH
  - strongest refutation: Strongest honest reason a member fails, and it is a packaging fault rather than a grammar fault: 5A93EF5A and FB68D20C (not 'one member', as the census says - two) are duplex renders whose first physical sheet is a mailer/cover carrying only the masthead, the address block and a mojibake OMR barcode line, with no 'Statement of Account', no Statement Dates and no Activity Summary. Their printed page numbering therefore starts at 'Page: 2 of 9' on PDF page 3, so any page-index assumption - read the header from PDF page 1, treat PDF page 1 as printed page 1, or assert printed_page == pdf_index - breaks on exactly these two. Related and also understated by the census: EVERY member is duplex, not just those two (PDF page count is exactly 2x the printed page count in all six, with the reconciliation worksheet or a near-empty back interleaved), and the mojibake OMR block is on every front page of every member, not one page-1 block in one document. Two lesser refutations. (a) The whole family's day-level truth is a derived chain: nothing prints a daily-balance grid, so if the validation harness demands a printed daily-balance oracle this family supplies none, and if it demands an EXACT match to the printed Average Ledger Balance it fails all six (agreement is only to about a dollar, because the bank truncates each day to whole dollars). Under the ratified ADB doctrine - calendar-day printed period, bank averages evidence-only - that is a pass, but it is the one arithmetic in the family that does not close to the cent, and it is the assumption the whole 6/6 rests on. (b) The 'Checks in Number Order' grid and the trailing image index restate check rows already in the ledger; a reader that scans for date+amount pairs document-wide instead of cutting the section will double-count checks and blow both the debit count and the debit total. That hazard is fully avoidable and my crude extractor avoided it with a single banner cut, so I do not discount for it.
- **shas:**
```
5A93EF5AFFB05B3DF7273C7F89DF0F58CE4013E2B7447D1525660EF5C01152F2
6A27035D392A42A215EAA4071AC3C88BE03DCA1C8FC1C112D71A70D042EE8194
9F0675CB72FAA03C6111E644D5C8C95923E0D13B0A78620A6E7B24A32CBD9CA9
D7C3E697A8F378624E64D7CC6E42521091F922CA7B48E04CDD63D42510CD558D
F7653841A17D4E72EB3C0EA52839AC68493033572893983CA8A6F23093BCA02D
FB68D20C79B9B4067127CD616E75BEE9D8691999C184723583106D03B540AA98
```

### 12. `american_savings_bank_hawaii` (n=11, expected 4.4, 0.4)

- **Printed identity:** American Savings Bank (Hawaii). Statement of Account with the stacked pair Last Statement: <Month DD, YYYY> / This Statement: <Month DD, YYYY> and Days in statement period: NN; Direct inquiries to 808-627-6900 or 800-272-2566 (Toll-free); product BIZ ESSENTIALS CHECKING / BIZ PLUS CHECKING; Checks Paid 3-up grid with * Skip in check sequence; ledger banner Account Activity; footer asbhawaii.com.
- **Oracle:** Beginning Balance, Average Balance, Total Additions, Total Subtractions, Ending Balance - all five printed - plus Days in statement period and a running Balance column in Account Activity.
- **Nearest reader:** analysis/core_processor_daily.py - its docstring names exactly this Last statement:/This statement: + Total additions/subtractions grammar, so this is a near-miss on a registered template reader, not a new institution
- **Risks:** The Account Activity table is emitted COLUMN-WISE and the header order rotates between pages, so consecutive text lines are not one transaction - needs coordinate-aware reconstruction or a summary-only publish. Summary labels and values also arrive in separate runs. Several members are near-empty (626-4,674 chars; one zero-activity month, one 3-day account-opening statement), so per-document yield is low even when the read succeeds.
- **Merged from:** s1(sg),s2,s4,s6,s7,s8,s9,s10,s11
- **VERIFY (adversarial):** identity_confirmed=True; sampled 11; misfiled []
  - oracle present: Identity furniture is real and unanimous across all 11: 'Statement of Account', the stacked 'Last Statement:'/'This Statement:' pair, 'Days in statement period:', 'Direct inquiries to 808-627-6900 or 800-272-2566 (Toll-free)', ledger banner 'Account Activity', footer 'asbhawaii.com'. Product is BIZ ESSENTIALS CHECKING on 10, BIZ PLUS CHECKING on 1 (D03A, which also carries a distinct page-1 block 'SUMMARY OF ACCOUNT BALANCE / Total Deposits / Total Loans' and a different form code in the top-left corner, so there are at least two sub-templates). CORRECTION TO THE CENSUS ORACLE: (a) 'all five printed' is FALSE for 2 of 11 — the two zero-activity months (6E0E32AA00B76720, 82BD2AB129E042D7) print only four labels, with no 'Average Balance' line at all, and their Account Activity reads 'No Activity For This Period'; (b) there is NO daily-balance grid anywhere in the family (grepped 'DAILY'/'Daily' across the four multi-page members: zero hits) — the only per-day evidence is the running Balance column inside Account Activity; (c) the institution name 'American Savings Bank' is printed ONLY as the continuation-page masthead, so the 6 single-page members never carry the bank's name in the text layer at all — identity rests entirely on the phone line + asbhawaii.com; (d) a 'Checks Paid' 3-up grid with '* Skip in check sequence' is present on 3 of 11, and 'N Number of Images' on 2. Critically, the five summary labels ARE printed but their values are NOT label-adjacent and the mapping ROTATES per document: in one full-read member the figure printed immediately after 'Average Balance' is the Beginning Balance and the Average sits orphaned above the product line; in the other full-read member the figure after 'Average Balance' is Total Additions. The pair 'Ending Balance Total Subtractions' is printed on one line with its two values following in the REVERSE order. Every summary figure I resolved I had to resolve by arithmetic (Beginning + Additions - Subtractions = Ending) anchored on the ledger's BEGINNING BALANCE row and its last running balance.
  - ledger shape: Column-wise, and worse than the census says in one respect, better in another. Confirmed rotation: the Account Activity header run itself reorders page to page within a single document — 'Additions Subtractions Date Description Balance', then 'Date Balance Description Subtractions Additions', then 'Subtractions Description ... Balance Date Additions' — so header x-order is unusable. In the BODY the dominant shape is actually semi-regular: a date on its own line, then the description, then the amount, then the running balance, with descriptions wrapping over 2-3 lines and the wrap fragments frequently emitted OUT OF ORDER (the city/timestamp tail lands before the merchant head). The sign is encoded positionally, not by column: a CREDIT amount is emitted on the line BEFORE its date line, a DEBIT amount after the description — I verified this by walking the running balance through ~95 rows in one full-read doc and ~110 in the other, and it held for the clean rows. It breaks in dense regions, and those breaks are fatal to line pairing: two transactions' dates merge onto one line while up to THREE running balances stack on another; one row's amount collides onto the neighbouring row's amount line so a single line carries two unrelated figures; a $0.00 row prints balance-then-amount reversed; the last row of one document prints balance before amount. Overdrawn balances print with a leading minus. The check-image page (last page of one document) is fully transposed — check numbers, dates and amounts are three parallel runs whose reading order does not pair them. Net: consecutive lines are NOT one transaction, and there is no reliable line grammar; a working reader must be a running-balance walker (use the printed Balance delta to recover each amount and its sign) or coordinate-aware, not a regex over lines.
  - multi-account (L-1): Single account per statement in all 11 — no L-1 realized in this sample. But the risk is latent and printed: the BIZ PLUS member (D03A961937256A19) carries a relationship block 'SUMMARY OF ACCOUNT BALANCE / Account Number / Ending Balance' with 'Total Deposits' and 'Total Loans' rows, which is a multi-account container that happens to list one deposit account and a zero loan total here. A reader keying on 'Account Number:' will find two or three occurrences per statement in the single-account case already (page-1 header block plus the summary block, with the label and the digits split across separate runs and their order rotating), so account attribution needs care even before a genuine two-account member shows up. Concentration is the bigger staffing fact: the 11 documents cover only THREE account contexts and TWO obligor groups (one pair of related LLCs at a shared address accounts for 10 of 11; the eleventh is an unrelated LLC). Consecutive-month runs from the same account mean a reader will over-fit and the marginal information per document is low.
  - currency evidence: No ISO currency code is printed anywhere — grepped USD/CAD/'U.S.' across all 11 and the only hit was a merchant name in a transaction description. All figures are bare '$' with US thousands/decimal punctuation. Institution is unambiguously US domestic (Hawaii): 808 area code on the inquiry line, HI addresses throughout, asbhawaii.com. Under the ratified jurisdiction-default doctrine this is a clean USD default with no CAD exposure and no FX surface — this family is currency-boring and raises none of the RBC-style questions.
  - ceiling: Honest ceiling 5-7 of 11; honest EXPECTATION 3.0-4.0, below the census 4.4. Composition matters more than the count. Two members (6E0E, 82BD) have zero transactions and all-zero summaries at 626/627 chars — they validate trivially or are excluded by an activity floor, so they are 2 free-or-dead units that carry no analytic value either way. Seven members are 1-3 pages with 1-8 transactions; these are the realistic wins for a balance-walk reader, call it 4-5 of the 7, and even there three of them show an amount colliding onto the BEGINNING BALANCE line or two dates merged on one line. The two documents that actually carry funder-relevant volume (200B, 6pp; D03A, 7pp) are the LEAST likely to reconcile — each contains several confirmed multi-transaction line collisions — so I put them at coin-flip or worse individually. That is the asymmetry to plan around: the count can look acceptable while both high-value documents fail. A summary-only publish does NOT rescue it, because without the reconstructed ledger you cannot pin which printed figure is Beginning vs Average — in two members those two figures are numerically equal, so the arithmetic solver is degenerate and the ledger's BEGINNING BALANCE row is the only disambiguator.
  - confidence: 0.30 LOW (down from the census 0.40 MEDIUM-LOW). Identity is certain and unanimous — that part of the census is fully confirmed. The downgrade is entirely about yield mechanics and about a load-bearing census claim that does not survive checking.
  - strongest refutation: The 'near-miss on a registered TEMPLATE reader' claim is FALSE, and it is the claim that justified rank 12. I read analysis/core_processor_daily.py. Its detector requires 'Total days in statement period:' — ASB prints 'Days in statement period:' with no 'Total', so the detector correctly does not and cannot claim these documents. Beyond the detector, none of its five value extractors can fire: _BEGINNING_RE/_ENDING_RE/_AVERAGE_RE demand 'Beginning balance $<fig>' style label-then-value on ONE line, and ASB never once prints a summary value on its label's line (values arrive in a separate run, sometimes ahead of the label, with a per-document rotation); _OPENING_DATE_RE/_CLOSING_DATE_RE demand 'Last statement: <date>' inline, while ASB stacks the label under its value, so a naive match returns the WRONG statement date — the closing date for 'Last Statement:' — in all 11. And its whole ledger model is named sections (CHECKS / DEBITS / CREDITS) closed by a 'DAILY BALANCES' grid; ASB prints one running-balance 'Account Activity' ledger and NO daily-balance grid at all. By the exact doctrine that module's own docstring uses ('not one grammar is shared, so this is a new registration rather than a widened period grammar'), ASB Hawaii is a new registration too. So this is not a cheap widening of a registered reader — it is a from-scratch reader whose ledger stage must be a running-balance reconstructor (nothing in the current sectioned/daily readers does that) and whose summary stage must be an arithmetic solver rather than a label match, all for 11 documents spanning 3 accounts, 2 of which are empty and 2 of which are the ones most likely to fail. Second-strongest refutation, if the first is somehow answered: because the summary mapping rotates, a label-adjacency reader does not fail loudly — it emits plausible, wrong Beginning and Average figures that only a ledger cross-check catches, which is the failure mode most dangerous to a validation harness that trusts printed summaries.
- **shas:**
```
200B4DB6ECAA46BF6418FD097AE797E3E82A057DD61F2DA55127181391F8A365
3E2B2FE65EF9A4EBD945366104FA6962449DBA7C30014E2D6D3FE9D7040C6C89
61A59770D98439F0A80DFA587B3DD979DFAF78B6816AAD61C116BF1CAE9A4405
6B22A09255A2B5A711B9E4499FAF5E9A3EB6550B18CA7F004401E6BCCEE989E9
6E0E32AA00B76720F07A049CAF6FACDA3659F00A7BB6E45AEA4F131D23A1B301
82BD2AB129E042D773E84CDF9AE850F9FD1583EFD979B9B22DD4DEB8F7289E9A
88D771CDA7C7EB4FD2F2A6BAD4E5ABA2C024612B6D9B67E39A60ABE4E3E162DE
92EB76D889DF84BFDEFBF3ED7FF5FB20098B34A544FF3A9F82A200AB9C2EE5F2
AF3CF313F96E5A04E5723E7E689668CA29A0D70BE165E0D2E9A4DA24FDEFEBA3
D03A961937256A19F20F8A8EC396B17CE50D6B32CFA2F52FB5CDD23F5D8F7B31
EA0FCD7850BBC0E3306DB891F173CE533D6BBB34ACEF0403FEDC8D38C88C255D
```

### 13. `cu_idaho_equation_summary` (n=8, expected 4.4, 0.55)

- **Printed identity:** An unnamed Idaho credit union (masthead image-only on every member; customer addresses Eagle / Caldwell / Twin Falls / Idaho Falls). Page n of m / Member Number: / Statement Start Date: mm-dd-yyyy Statement End Date: mm-dd-yyyy; a two-item balance strip (Savings $x Checking $y); RETURN SERVICE REQUESTED; per account <PRODUCT> - <nickname> Account No. **nnnn over the printed equation row Beginning Balance + Deposits + Interest Earned - Withdrawals - Service Charges = Ending Balance; internal marker Acct_Num=nnnnnnnnn; closing APY sentence giving the average daily balance and the minimum balance.
- **Oracle:** The six-cell equation row is the summary (labels on one line, six values on the next - strict positional zip), plus a per-account printed AVERAGE DAILY BALANCE and minimum balance sentence, plus a running Balance column and an Overdraft/Returned Item period-vs-YTD box.
- **Nearest reader:** analysis/symitar.py (six-figure equation-row oracle is its documented shape, but it expects Dividends where this prints Interest Earned and Service Charges, and there is no ACCOUNT SUMMARY heading) - a likely marker-widening rather than a new reader
- **Risks:** Declared column order is Eff Date | Post Date | Description | Deposit | Balance | Withdrawal - Balance sits BETWEEN the two amount columns and rows print only two numbers, so direction must come from the descriptor verb (ACH Deposit vs ACH Withdrawal / Point Of Sale Withdrawal) and be checked against the balance delta. L-1 savings+checking. Institution unidentifiable, so register on the equation sentence.
- **Merged from:** s1(5624334A),s4,s5,s7,s8(A4BC8F5F),s11
- **VERIFY (adversarial):** identity_confirmed=True; sampled 8; misfiled []
  - oracle present: Sampled all 8 (n=8), full text on 4FDCDEA7A42C4989 and 8A03D96FD8474EE9 plus effectively-full on the two 2-page members. PRESENT and verified on every document: (1) the six-cell equation, once per account section, 12/12 sections. Its printed shape is a THREE-line collapse, not two: label line A "Beginning Interest Service Ending", label line B "Balance + Deposits + Earned - Withdrawals - Charges = Balance", then six $-prefixed values. The census's "labels on one line, six values on the next" is wrong by one line — a reader anchoring on the two-line form will miss it. (2) A per-row running Balance column, and an explicit "<mm/dd> <balance> Beginning Balance" opening row in 12/12 sections, whose value equals the equation's Beginning cell 12/12. (3) Header trio "Page n of m / Member Number: / Statement Start Date: mm-dd-yyyy Statement End Date:", repeated per page in short form. (4) The balance strip, but it is one item on savings-only statements and two when a checking account exists. REFUTED oracle claim: "a per-account printed AVERAGE DAILY BALANCE". The ADB + minimum-balance + APY sentence occurs EXACTLY ONCE per statement (measured: ADB-sentence count = 1 while equation-row count = 2 on all six two-account docs) and it attaches only to the savings/dividend account. The CHECKING account — the cash-flow account — prints NO average daily balance, no minimum balance, no APY. ABSENT entirely: any daily-balance grid, and any printed transaction/item COUNT (no "number of deposits", no item tally anywhere). WEAK: the overdraft box exists but does not positionally zip — it flows as header "Total For Total This Period Year-To-Date" then "Total Overdraft Fees" followed by THREE values and "Total Returned Item Fees" followed by ONE, for what should be a 2x2 grid; every sampled value is zero so the true assignment is unverifiable from this family. The check-image list mis-zips the same way (header declares Date/Check#/Amount twice, rows print seq, check#, date, amount). The internal "Acct_Num=" marker is NOT a family marker: it appears once per document and only on checking-bearing statements, absent from both savings-only ones.
  - ledger shape: Native PDF text (model: native-pdf-text, zero empty pages) — no OCR noise. Columns are fully collapsed and, more importantly, ROWS are collapsed too: an entire page of transactions is emitted as ONE physical line (up to ~124 rows across only 5 such lines in the largest doc). A line-oriented parser gets nothing; this needs a regex scanner over flowed text. Critically, the text order is NOT the declared column order. The header prints "Eff Date | Post Date | Transaction Description | Deposit | Balance | Withdrawal", but every data row emits "EffDate PostDate <amount> <balance> <description...>": the amount always precedes the balance regardless of direction, and the description always trails. So the census's headline risk — "Balance sits BETWEEN the amount columns" — does not hold in the text layer; the shape is a clean fixed two-number [amount, balance] prefix. Descriptions wrap freely into the following text and contain digit strings, phone numbers, embedded dates ("Eff. 03-31"), merchant/city/country tokens ("...IDUS", "...CAUS") and "(Rejected)" suffixes; they are terminated only by the next MM/DD MM/DD pair. I ran that scanner over all 8 docs: 731 rows extracted, and |balance delta| equalled the printed amount on 731/731 — zero mismatches. Direction taken from the balance delta reconciles the oracle exactly: ending balance matched 12/12 sections, Withdrawals+ServiceCharges matched 12/12, Deposits matched 11/12. The single Deposits miss is understood and deterministic: the printed Deposits cell excludes a posted "Credit Interest" credit, which belongs in the Interest Earned cell. Service charges are separately identifiable by descriptors ending in "Fee" (e.g. an excessive-withdrawal fee, a tax-levy fee, an incoming-wire fee), each matching its Charges cell exactly. Note also that five savings sections carry ZERO transaction rows (only the Beginning Balance row) — a reader must not treat those as a parse failure.
  - multi-account (L-1): L-1 confirmed and VARIABLE within the family, which the census understates. Six of eight documents carry two account sections (a business share savings and a small business checking), each with its own "<PRODUCT> Account No. **nnnn" heading, its own equation row and its own ledger. Two of eight (A4BC8F5F6A0FB3AB and F450831654CE4671) are savings-ONLY, two pages, with a one-item balance strip and no checking account at all — the checking account was opened mid-family, so the same member switches from 1 account to 2 across consecutive months. A reader must key account count off the repeated "Account No. **" heading, not off the balance strip or a fixed assumption. Section splitting is clean: "Account No. \*\*\d+" is a reliable delimiter and each section self-contains its equation, beginning-balance row and ledger.
  - currency evidence: No printed currency evidence beyond the bare "$" glyph. I grepped all 8 documents for USD / CAD / any currency code or word: zero hits. There is no masthead name, no NCUA or Equal Housing line, no routing number, no website, no phone number for the institution — the only "Bank"/".com" hits in the whole family are inside merchant and ACH counterparty descriptors. Jurisdiction is inferable only indirectly: member mailing addresses are all Idaho (Eagle / Caldwell / Twin Falls), merchant descriptors carry US country suffixes ("IDUS", "CAUS", "DEUS"), and counterparties are US federal/state payees. So USD by jurisdiction inference under the currency doctrine, not by printed evidence — currency_source would be "jurisdiction default", never "printed". No Canadian exposure whatsoever; this family is doctrinally uninteresting for the FX/CAD questions.
  - ceiling: Honest expected validated: 6 of 8, with a realistic range of 4-8 and a hard ceiling of 8. I am revising the census's 4.4 UP on mechanics but DOWN on independence, and the two roughly cancel. Upward: identity is 8/8 with zero misfiles, the source is native PDF text with no OCR defect, the equation oracle is present on 12/12 account sections, and I verified by direct arithmetic that a delta-direction scanner reconstructs ending balance 12/12, withdrawals+charges 12/12 and deposits 12/12 once "Credit Interest" is routed to the Interest cell. Mechanically this family is close to a solved problem. Downward, and this is the part the census missed: the 8 documents are only TWO distinct members, four consecutive monthly statements each, and the two packets chain (one month's ending balance is the next month's opening strip). That is n=2 independent shapes wearing an n=8 coat. Any defect in either packet's handling takes 4 documents down together, which is exactly why the range runs as low as 4. The second discount is the ADB refutation: if the validator wants a per-account or primary-account average daily balance, the checking side of all six two-account statements supplies none, and only the savings side — the near-dormant account — can answer. Effort is genuinely small: this is a marker-widening on symitar.py (widen "Dividends" to "Interest Earned", add "Service Charges", drop the ACCOUNT SUMMARY heading requirement, add the three-line equation collapse) plus a flowed-text row scanner. Low cost, moderate and correlated payoff. I would staff it, but as a half-cell rider on an adjacent Symitar-family ticket rather than as a standalone batch-7 cell.
  - confidence: 0.60 MEDIUM — up marginally from the census's 0.55. Raised because I confirmed printed identity on 8/8 with no misfiles and independently verified the oracle reconciles to the cent on 12/12 account sections rather than merely asserting it. Held below 0.7 for three reasons I could not resolve from the documents: the family is really two members so my sample cannot distinguish "this template parses" from "these two members parse"; I cannot see the validator, so I do not know whether a missing checking-account ADB or missing item counts is fatal or merely unscored; and the institution is unnameable from the text layer, so registration rests entirely on template furniture that may be shared with other credit unions on the same core.
  - strongest refutation: The strongest single reason this family would NOT validate deterministically: registration, not parsing. There is no institution identity anywhere in the text layer — the masthead is image-only and the family carries no name, charter, routing number, NCUA line, website or phone. The only registration hooks are generic core-processor furniture: the sentence "Beginning Balance + Deposits + Interest Earned - Withdrawals - Service Charges = Ending Balance", the "Member Number: / Statement Start Date: / Statement End Date:" trio, and the "Eff Date Post Date Transaction Description Deposit Balance Withdrawal" ledger header. That is a CORE template, not an institution. Widening symitar.py's markers to catch it risks either (a) capturing statements from other credit unions on the same processor whose ledger geometry differs, converting a clean +8 into cross-family regressions on already-validated documents — the one outcome this project has never had — or (b) being tightened enough to avoid that and thereby matching nothing outside these two members. A close second: the direction rule the census proposes is backwards and would fail here. It says direction "must come from the descriptor verb and be checked against the balance delta", but 22 rows across two documents are reversals printed as "ACH Withdrawal ... (Rejected)" that are actually CREDITS; 19 of them sit in a single statement. Verb-first inference inverts every one. Delta-first is authoritative and verb is at best a tiebreaker for the (unobserved) case of two consecutive rows with equal magnitude and opposite sign. Third, smaller: the row-splitting anchor MM/DD MM/DD amount balance held on 731/731 rows here, but descriptions are unescaped free text carrying digit runs and embedded dates, and nothing in the format guarantees a description cannot end in a decimal figure immediately before the next date pair — a silent row-merge on unseen documents from this template.
- **shas:**
```
1E882271F57D157DB9C76243525AE69FF8DFB670DBD9A227513A1675AAEAC97B
4FDCDEA7A42C4989CC34D6AB1DE9AFE2D59296390DF77B3E252266F92A51CD61
5624334A39D447C137B0D4BA189015E84C44C543355AC51B7F26671DDBD3EC1A
8A03D96FD8474EE9FD240B80952D36147060CDB9104D0692D9EDB5931BBA06FB
92B653A0D8CD42D147FAFB3DA0627E71DF3AAD10A139F8F230347611154FC221
A4BC8F5F6A0FB3AB1A14017F60014CF412878E683A986D0E60D304259445C232
B9DE5300BBC4613875425F5130AF93B1E2E8BCBE001166BDAC3D7CC924D8CDBE
F450831654CE4671C185FCE3CA8967FEFA8505F74B1F9CF670618B583A2AD6A6
```

### 14. `wpcu_summary_of_account_by_transaction` (n=8, expected 4.4, 0.55)

- **Printed identity:** Wright-Patt Credit Union. Statement of Account / (800) 762-0047 | www.wpcu.coop / Member Number xxxxxx / P.O. Box 340134 Beavercreek OH / Statement For mm/dd/yyyy - mm/dd/yyyy; print-vendor control line 1/n UNQ mm-dd-yy CLT; template artifact 'When this box is generated the XS_Counter is set.'; Your Account Summary as of mm/dd listing <PRODUCT> ID nn with Account Balance Total; ledger banner Summary of Account by Transaction with sub-banners Withdrawals and Other Charges.
- **Oracle:** Counts at TWO levels: per account <n> Total Deposits for <amt> / <n> Total Withdrawals for <amt> between Beginning and Ending Balance, and per ledger section <n> Withdrawals and other Charges for -$x. Both totals and both counts printed.
- **Nearest reader:** analysis/symitar.py (genre only); no registered reader matched
- **Risks:** NO running balance and NO daily grid anywhere - the counts do all the validation work, so a dropped row is caught only by the count gate. Ledger is Date | Amount | Description (amount BEFORE description) with the dollar sign printed only on the first row of a section. L-1: checking share plus a share account, both can post.
- **Merged from:** probe-resolved out of s2.cu_member_stmt_typeco_shares; s6,s7,s8,s9,s10,s11,s12
- **VERIFY (adversarial):** identity_confirmed=True; sampled 8; misfiled []
  - oracle present: CONFIRMED and arithmetically closed on 8/8 — but the census's description of the count gate is INCOMPLETE and would fail as written.  Printed per account: "<Product> ID nn Beginning Balance $x / <n> Total Deposits for <amt> / <n> Total Withdrawals for -<amt> / Ending Balance $y". Begin + deposits - withdrawals = end holds exactly on all 8 checking blocks and all 8 share blocks (I verified each).  Printed per section, under the banner "Summary of Account by Transaction": "Withdrawals and Other Charges <n> Withdrawals and other Charges for -$x"; "Deposits and Other Credits <n> Deposits and other Credits for $x"; and a THIRD section the census never mentions, "Summary by Check Number * Asterisk next to number indicates skip in sequence <n> Checks Cleared for $x". Every one of the 8 has a check section (counts observed 2,2,3,5,5,6,6,23) and its count/amount are folded into the account-level withdrawal totals — miss it and the withdrawal gate fails 8/8.  The two levels do NOT reconcile naively. On 5 of 8 (1A606C14, 37005BAD, BC692377, E46D8DBA, FDA61D31) the Deposits section contains rows typed "Withdrawal Adjustment" (debit-card credit vouchers / POS reversals) that print inside the credits list but are counted as WITHDRAWALS at account level. The true rule, which closes on all 8: acct_withdrawal_count = W_section + Checks_Cleared + Adjustments, acct_deposit_count = D_section - Adjustments, and identically for the amounts. A cell implementing the census's stated gate (section count == account count) validates only 3/8 (826E0493, C35598E6, E4405190).  Also printed, and NOT part of any total: an "Other Transactions Item <merchant> Pending credit/return for $x on card nnnn mm/dd" block (5 of 8) and, on the 4 docs of one member, a "Service Charges Date ID Amount Description Date ID Amount Description mm/dd 90 <amt> Withdrawal ACH Monthly Fee" box sitting ABOVE the account block. Both look like transaction rows and are phantom rows if scraped; the Service Charges box is also unreliable as a mirror (one doc prints 0.00 in the box while the ledger carries the real fee row).  NOT present anywhere in any of the 8: running balance, daily balance grid, average/aggregate balance, APY or rate table. Confirmed by grep across all 8.
  - ledger shape: Native PDF text (all 8 tagged model: native-pdf-text, 0 empty pages) — no OCR involved. 3-7 pages each, 9.8k-30.4k chars.  Columns are FULLY collapsed: an entire section prints as one enormous logical line, "Date Amount Description" header then row after row concatenated with single spaces, no newline between transactions. Row order is Date (mm/dd) then Amount then Description — amount BEFORE description, as the census said. The "$" prints only on the first row of a section; every later row is a bare signed number. Withdrawals carry an explicit leading minus; deposits are unsigned positive.  Row splitting must be anchored on the mm/dd + signed-amount pair. Descriptions are hostile to a lazy anchor: they embed dates ("Post: January 31, 2026", "Date 01/31/26", "Internet Access 05/21/2026 21:27 491102") and embed amounts ("Withdrawal NSF Fee 1018 In the amount $2,000.00."). Descriptions do not wrap in the text layer — they just run on until the next mm/dd+amount.  Ledger dates are NOT sorted: I saw 01/22 before 01/21, 01/30 before 01/29, 05/27 before 05/26 in a single section. Rows dated before the statement period also appear as the first row of a section (11/30 in a 12/01-12/31 statement; 02/28 in a 03/01-03/31 statement), so a date-only replay from Beginning Balance is not safe, and mm/dd carries no year (year rollover must be inferred from the printed "Statement For mm/dd/yyyy - mm/dd/yyyy").  Two sub-tables print as TWO record-columns per printed line: the Service Charges box ("Date ID Amount Description Date ID Amount Description") and Summary by Check Number ("Number Cleared Amount Description Number Cleared Amount Description"). The check rows interleave row-major across the two columns (observed order 120,134,130,135,133 — not sequential), each column's first row carries its own "$", and each record is self-identifying because the description repeats "Check <number> Tracer nnnnnnnn". Parseable, but a single-record-per-line parser silently halves or scrambles the check section.  Sections continue across pages with the banner repeated as "<Section> Continued from previous page. Date Amount Description" and NO count — a reader that reads a count off every banner will read zero and blow the gate. Page 2+ headers repeat the masthead and truncate the template artifact to "When this box is generated the XS_Counter is" (no "set. N"), so the identity regex must tolerate both forms. A print-vendor control line "nnnnnnnnn 1 p/n UNQ mm-dd-yy CLT" appears inline in the text stream at page footers.
  - multi-account (L-1): L-1 CONFIRMED and load-bearing. Every one of the 8 carries exactly two accounts: a checking product "ID 90" and a share account "ID 00", listed together in "Your Account Summary as of mm/dd" with an "Account Balance Total" that sums them. No loans, certificates, or money-market blocks in any of the 8 (grepped).  The share account is not decorative — it posts on 4 of 8 (1A606C14, 37005BAD, BC692377, FDA61D31), with its own Beginning/Ending Balance, its own "<n> Total Deposits / <n> Total Withdrawals" counts, and its own repeated "Summary of Account by Transaction" banner with its own section counts. Share-to-checking Home Banking transfers appear on BOTH accounts, so a package-level dedupe that collapses accounts would double-count. When the share has zero activity (4 of 8) it prints the balance block but NO second banner and no sections — the reader must accept a 0/0 account with no ledger rather than error.  The "Account Balance Total" is a cross-account sum, so it is a third, weaker oracle. Balance chains across months are clean for both members (each month's Ending Balance equals the next month's Beginning Balance, 6/6 transitions).
  - currency evidence: No printed currency code anywhere — grepped all 8 for "USD" and "U.S. dollars": zero hits. Evidence is jurisdictional and symbolic only: a US credit union (Beavercreek/Dayton OH masthead and PO Box, wpcu.coop, a US 800 number), "Federally insured by NCUA." in the page furniture, bare "$" on every first-of-section amount, and US member addresses. Foreign activity is present but confirms rather than complicates the home currency: MX card purchases post already-converted alongside separate "Withdrawal Debit Card Fee International Transaction Fee" and "Withdrawal ATM Fee International Transaction Fee" rows, which is a USD-settled US card program. No Canadian institution and no CAD exposure, so the RBC jurisdiction-default doctrine is not implicated — this is a plain US-jurisdiction USD default with no printed confirmation.
  - ceiling: Honest ceiling depends entirely on what "validated" demands, and the two answers are far apart.  If validated = extraction gated on printed counts + printed totals + begin/net/end continuity: the ceiling is 8/8 and I would expect 6/8. I closed the arithmetic by hand on all 8 (both accounts each) and every document's oracle is complete and self-consistent; the text layer is native and clean, so nothing is lost upstream. The 2-document haircut is for the two heaviest docs (BC692377 at 30.4k chars with 23 interleaved check rows and 4 adjustments across 5 continuation banners, and 826E0493) where the collapsed two-column check table and the repeated "Continued from previous page" banners are most likely to cost a row.  If validated = a naive implementation of the count gate exactly as the census wrote it (section count == account count, no check section, no adjustment offset): 3/8. That is the realistic outcome for a cell that staffs off the census card without reading the documents, and it is BELOW the census's 4.4 estimate.  If validated requires a daily-balance or ADB oracle: 0/8. There is no daily grid, no running balance, and no average-balance line anywhere in the family. Under the ratified ADB doctrine (canonical ADB = calendar-day printed period), an ADB here can only be RECONSTRUCTED by replaying the ledger from Beginning Balance — and that reconstruction is unverifiable against anything printed, and actively unsafe here because posting order is not date order and the first row of a section is routinely dated before the period start. Nothing in the document can catch a mis-dated replay.  Net: I would revise the census's 4.4 to "6 if the cell is briefed on the adjustment rule and the check section, 3 if it is not" — the estimate is roughly right by accident, for the wrong reason.
  - confidence: 0.60 MEDIUM — raised only marginally from the census's 0.55, and deliberately held below 0.7. Upward pressure: n=8 was sampled exhaustively, printed identity is unanimous, the text layer is native and undamaged, and the oracle closes arithmetically on 16 of 16 account blocks. Downward pressure: the family is only TWO member instances (two 4-month consecutive runs), so template variance is essentially untested; the reconciliation rule I derived is inferred from 8 documents rather than from a spec; and the whole family has no balance-series oracle, which leaves one entire validation axis unsupported no matter how good the reader is.
  - strongest refutation: The strongest reason this family would NOT validate deterministically: the count gate the census is staking the family on does not reconcile as printed, and there is no second oracle to fall back on.  On 5 of the 8 documents the account-level "<n> Total Deposits" and "<n> Total Withdrawals" disagree with the sum of the printed section counts, because rows typed "Withdrawal Adjustment" are printed inside the Deposits and Other Credits section (with positive amounts, contributing to that section's own printed subtotal) while being counted as withdrawals at the account level. Add the "Summary by Check Number" section, which the census card omits entirely and which contributes to the withdrawal totals on 8 of 8, plus the "Other Transactions" pending-item block and the "Service Charges" box that both mimic transaction rows without belonging to any total, and a reader built from the census description fails the gate on 5 of 8 and mis-signs rows on 5 of 8.  That would merely be an implementation bug if something else could catch it — but the census's own risk note is correct and understated: with NO running balance and NO daily grid, the counts are the only check. A dropped, duplicated, or mis-signed row is invisible unless the count rule is exactly right, and the count rule is exactly the thing the census got wrong. The failure mode is silent: a reader that also mis-classifies the adjustments will produce a deposit total and a withdrawal total that are each wrong by the adjustment amount but whose difference is still correct, so begin/net/end continuity still passes and the error survives to the funder-facing numbers.  Secondary refutation: n=8 is really n=2. Both members are Ohio business members on the same print run, one of them with a "Service Charges" box and a "Joint Owner" line the other lacks. Any WPCU variant outside these two — a member with a loan or certificate block, three or more share suffixes, an overdraft-protection section, or a statement whose share account posts dividends monthly — is entirely unobserved, and a reader tuned to eight documents from two households is not evidence of a family-wide reader.
- **shas:**
```
1A606C1476CB49B4CA04DBC07490BFD73407EA3E7342EE295CEA6473BF405F05
37005BADB33376A8B430FDE39570EE86E72AAD9AFA11ACD186B30F7774711DEB
826E04939F2AFE7415DFB418DCAEDFE5FEB3CB3BBB86DA734E0F3CDD742D614D
BC692377D862E205EBE6EEDEE23CDC41C22C3482443957BB33C6256F86054739
C35598E63654727A186E8AE0644F69246D6536D93BE2F5531865C521A528AEFD
E4405190715B334D25D73CE54B57D2F39A67E20D6480F3DEF71E3D0E4AC771E0
E46D8DBAA5B0269977B4726188C853C9A6471D85BA9B9EE048D9C3936F59B72C
FDA61D31378FF484557889A2FF1B830F007B8D3E337D3FBD313D3E7137D87523
```

### 15. `cu_unq_clt_trailing_minus_totals` (n=8, expected 4.0, 0.5)

- **Printed identity:** One print-vendor CU core under three mastheads (Summit Credit Union WI / SummitCreditUnion.com PO Box 8046 Madison; Hoosier Hills CU / www.hoosierhills.com Bedford IN; Mountain America CU / www.macu.com in its UNQ-CLT printing, NOT its dot-leader printing). Member Statement of Account / Statement of Account + Member Number + Statement For mm/dd/yyyy - mm/dd/yyyy + RETURN SERVICE REQUESTED + the vendor control line n/m UNQ mm-dd-yy CLT; Your Share Balances / Your Account Balances as of mm/dd with Account Balance Total; per share <SHARE NAME> ID nn.
- **Oracle:** Per share: Previous/Beginning Balance, <n> Total Deposits for, <n> Total Withdrawals for, New/Ending Balance, plus Total Dividends Paid Year-To-Date and an APY sentence carrying an average daily balance; a running Balance column on every row.
- **Nearest reader:** analysis/symitar.py (genre); no registered reader matched
- **Risks:** THE sign trap of this census: every amount AND every balance is printed with a TRAILING hyphen regardless of sign ($6,010.21- is a positive balance). Direction must come from the Deposit/Withdrawal verb and be verified against the balance chain - a parser that reads trailing minus as negation inverts the whole document, and at least three other families here use trailing minus to MEAN negative. L-1 multi-share throughout. Mountain America appears here in one template and in mountain_america_cu_dot_leader in another.
- **Merged from:** probe-resolved out of s2 and s3.cu_share_totals_trailing_minus; s4,s8,s11,s12
- **shas:**
```
193EE809ECDEE364BA166D0933857E726B939EBB4D8A0DC664C8007AD3F726F8
51F90E779AB0D06B0C2938F337985BBDF893F12B3F941CFED4881AE969E9F481
573EA76A9CD69D1D7BF4175465FBAD88562E780CA263305DBD451F69CE0D11AC
58A3E63465F1DD338965D855E7D6F7AF6A72DCA5C3F3C2F6D2FF3C96D625FA54
65E9F798F60B82458922A987A6F3FEDF6BB8193F0176C1256CF5C2C2C1631ECE
8E4DBE9C27ED5139CA55CE93B7D47415DE87EC3CA8D389A4CCC289A7E901B7C1
A612A5F5437001CE34DF8CDDFD4F3A4D68835809B3ABFAB0D5487D6A481DE46A
D1B8E55A1BDBEFB96041E7EC684C2A40E239929D0F3A85EB02FC30C165394E84
```

### 16. `truist_your_account_statement` (n=7, expected 3.85, 0.55)

- **Printed identity:** Truist. Contact us / Your account statement / Truist.com (844) 4TRUIST or (844) 487-8478 / For mm/dd/yyyy; a bulleted product banner (TRUIST DYNAMIC BUSINESS CHECKING - CORE TIER / TRUIST SIMPLE BUSINESS CHECKING / TRUIST BUSINESS VALUE 200 CHECKING) repeated with (continued); Account summary; sections Checks (three-up DATE / CHECK # / AMOUNT($)), Other withdrawals debits and service charges, Deposits credits and interest, each closing on Total ... = $x; back-page Truist Ready Now Credit Line disclosure; page marker PAGE n OF m.
- **Oracle:** Your previous balance as of <date>, Checks -, Other withdrawals debits and service charges -, Deposits credits and interest +, Your new balance as of <date> =, with each direction section restating its own Total ... = $ line (a second, independent gate).
- **Nearest reader:** analysis/truist.py EXISTS and near_miss fired truist:0.167 on every member without claiming any - the highest-value repair in this census
- **Risks:** No daily grid and no running balance in any printing, so the four-line summary plus the section totals are the only closure. The +/-/= operators are emitted on separate lines from their labels and the summary values arrive out of label order. Several printings orphan the date token off wrapped rows (a bare 06/12 after the row it belongs to) and one splits the column head as DESCR IPTION. Amounts unsigned - sign from the section.
- **Merged from:** s1,s2,s5,s6,s7,s8,s12
- **shas:**
```
07A0913077CFE0562FB2C98BF7A8C5551E7172B202BFA5AFD200BE10D8D6C2EF
43784B8A67C40798605F711D522C22C4AA375D95BAB3003E6A1293D9D372EF08
663B51261DFF46C5509C6FCF360C957733B29FAD4C957906F83BC60C94DAAEA8
9C4E5EDCE424A80354B64B0F363B5345928C57C8292F1D7A563039D214870E2E
A5DA09E8618EBB038FC5C1FA4669DFC59319DFF3EAA2FF271604D3FB3533DC23
A8558BAB37C98F3F1369F45F1559529606B06FDC841B2EAA1B88D8EFA3B87F2B
C56409CA2F4628B6B851F1DAEF4E78FF2FEC1F79B411F68E3199D6EA5A80121A
```

### 17. `old_national_free_business_checking` (n=5, expected 3.75, 0.75)

- **Printed identity:** Old National Bank. FREE BUSINESS CHECKING banner over P. O. Box 718 Evansville, IN 47705; ACCOUNT INFORMATION DATE | ACCOUNT NUMBER | PAGE n OF m; CLIENT CARE CONTACT INFORMATION Client Care: 800-731-2265 / Visit us Online: www.oldnational.com / Written Inquiries: P. O. Box 419 Evansville, IN 47703; ACCOUNT SUMMARY; SERVICE CHARGE SUMMARY; OVERDRAFT CHARGES SUMMARY THIS CYCLE | YEAR TO DATE; DEPOSITS AND OTHER CREDITS with a TRACER column; DAILY BALANCE SUMMARY; a To Help Balance Your Account worksheet page; six-line OCR sortation alphabet blocks on every page.
- **Oracle:** Previous Statement Balance <date>, Deposits/Credits with its item count, Withdrawals/Debits with its item count (printed negative), Total Service Charges, Interest Paid, Current Statement Balance <date>, Days in Statement Period, plus a DAILY BALANCE SUMMARY grid - dated ends, both counts, both totals and a daily grid.
- **Nearest reader:** none (no old_national module); nearest counted-summary shapes analysis/core_processor_counted.py, fifth_third.py
- **Risks:** The per-page OCR sortation blocks (APBKFPBOBLFJ...) and the balance-your-account worksheet must be filtered before description capture or they poison a label-anchored read. A TRACER integer sits between date and description and is easy to mistake for a check number or an amount; the payee/ZELLE REF line wraps below the amount.
- **Merged from:** s4,s5,s6,s7,s8
- **shas:**
```
55DF08BDAB9399A82515506F65D27A4E856B808B7D77F076FCCFC090A5C02DEE
6BAE586D2838FC0974DC72D7CFF04A3F9993E3A25B42DB40E6AE233C915EF99F
6CE2546424B3F9103060BFD764AB806A1D9ABCC1CEA567F56FC62EA47D96079C
87DCA85DB76608006F69DC48CBB03F45FCE7FD17658DA7987CBAB0AD9D15D4B3
9F67C53D38F3DD984D81F0DF072744081BB78D7A19CC516356CDD5780B92359A
```

### 18. `dfcu_financial_account_statement` (n=5, expected 3.5, 0.7)

- **Printed identity:** DFCU Financial (Dearborn MI). Account Statement over the lockup The Cash Back Credit Union / F I N A N C I A L; 400 Town Center Drive, Dearborn, MI 48126  888.336.2700  dfcufinancial.com; Page n of m Member Number From mm/dd/yy Thru mm/dd/yy; ACCOUNTS SUMMARY ACCOUNT NUMBER | BALANCE | YTD DIV; section banners DEPOSITS AND OTHER CREDITS and WITHDRAWALS AND OTHER DEBITS each closing on a TOTAL line.
- **Oracle:** Beginning balance on <date>, Deposits and other credits, Withdrawals and other debits, Service fees, Ending balance on <date>, and then the same two totals restated as printed section footers - a redundant, fully closable arithmetic oracle.
- **Nearest reader:** analysis/core_processor_sectioned.py (section-with-printed-total shape), consumers.py / secu.py as CU siblings; no dfcu module
- **Risks:** No running balance and no daily grid at all, so daily balances must be derived. A marketing sentence is interleaved INSIDE the summary block between the credit and debit lines, defeating line-adjacent pairing. Rows carry TWO dates (Eff. Date and Trans Date) and long POS descriptions push the amount onto the next line. One printing misspells the month as Febuary.
- **Merged from:** s5,s6,s7,s8,s9
- **shas:**
```
2007DE85CAF9D9701BFD1425F4563F8C04939F7D9B39097C7357F3A411E25A66
8D0554E2A0C677BD090456F252F3DC23BB0F36CF14BCD678A2C9557DD2FDB6F8
9E97EE0CA842A3D30B18D9E13DBFF1607A1194CF1CD1C787EA687DD7AC3E0109
AFE8053C4899B0E834374705E5C494569218A392E1B4E1241CA952F162F823C3
CCC8C4019025C0F65AB43C9C1DD36E29067EC836F8330AC6DD8892073496A06A
```

### 19. `bank7_summary_of_accounts` (n=4, expected 3.4, 0.85)

- **Printed identity:** Bank7 (Oklahoma City). <Month YYYY> / Reporting Activity mm/dd - mm/dd  Page n of m; 1039 N.W. 63rd St Oklahoma City, OK 73116; Managing Your Accounts with Branch Location / Branch Phone # / Toll Free Support / Mailing Address / Online Access bank7.com; Summary of Accounts (Account Type | Account Number | Ending Balance) closing on Total Current Value; per account Account Summary and Account Activity; page footer a GUID plus <YYYYMMDD> Checking Account Statements.
- **Oracle:** The most complete oracle in the census for its size: dated Beginning and Ending Balance, <n> Debit(s) this period and <n> Credit(s) this period with both totals, Minimum Balance, Average Available Balance, a Daily Balances grid AND a per-row running Balance - two fully independent closure paths.
- **Nearest reader:** none (no bank7 module); the Summary of Accounts / Total Current Value furniture resembles analysis/community_section.py
- **Risks:** Almost none. Single account per member (the Summary of Accounts table is multi-account furniture listing one). Signed amounts, one row per line, opens on a Beginning Balance row. Lowest-risk registration in the census.
- **Merged from:** s2,s3,s9,s12
- **shas:**
```
07C874CCC28F85F5D49C72F4B62138CC3A7D1FF8BBDB9A606D22DC8CEA1D271D
39BCEC8D522E90993560FBE3EFC01C1589F23773AB146C1256C65FB25B73D753
49F18A6ED9520BD821FD8187C6239B58AD5A19EFEE255FDEB99C5F72C7CFBD56
84C4BE9824D45F634AFB6FEEC6EADC79F82F401EAF26A393F831253CFDF04782
```

### 20. `chesapeake_bank_activity_in_date_order` (n=5, expected 3.25, 0.65)

- **Printed identity:** Chesapeake Bank (VA). ches.bank 877-436-9032 Customer Service / PO Box 1419 Kilmarnock, VA 22482 page header with Date / Account Number / Enclosures / Page n of m; ACCOUNT INFORMATION with a Description | Account # | Balance | Enclosures roll-up; per account <acct> Checking Account BASIC BUSINESS CHECKING; an Account Details block (Number of Enclosures, Days in the Statement Period, Average Ledger, Average Collected); a Total Overdraft Fees period-vs-YTD table; ledger banner Activity in Date Order; Member FDIC footer.
- **Oracle:** Previous Balance and Current Balance with as-of dates, Deposits/Credits and Checks/Debits totals each with a bare integer item count, Service Charge, Interest Paid, Average Ledger, Average Collected, Days in the Statement Period, and a Daily Balance section on the longer printings.
- **Nearest reader:** analysis/linkbank.py and analysis/burke_herbert.py (top near_miss 0.125-0.167 on all members; same Previous Balance / Average Ledger / Average Collected core furniture)
- **Risks:** The field emission ORDER flips between cycles of the same account, so a reader must match labels and take the nearest following currency token, never a fixed offset. In Activity in Date Order the amount comes FIRST and the m/dd date trails the description at end of row. Amounts are pre-signed, so section-based signing must be off.
- **Merged from:** s1(FE237BF9),s9,s11
- **shas:**
```
18A33B29F500239E9B07B465CBF005C7FACAAB17FD92FA7DB94F0C515CEF2E1B
54C55E7FB9F0E49C20C473E6E4EFE18F271619F8B196BD6F4CA1708270CFA111
615305CFCEB7B260261731AF04EF369855BC081A715D2A629A17789597B32133
B0A280A3F70D3158F7422A259961FD4667975BB62AC2302647D9BA1E591E4813
FE237BF9465CBB716FEE7155DB95A716925FC4E5E344188C71331809BF5CBFD5
```

### 21. `wescom_cu_equation_summary` (n=5, expected 3.25, 0.65)

- **Printed identity:** Wescom Credit Union. Phone: 1-888-4-WESCOM / Email: mail@wescom.org / Website: wescom.org / P.O. Box 7058 Pasadena CA; Account Number nnnnnn Statement Period mm-dd-yy thru mm-dd-yy Page n of m; ACCOUNT SUMMARY panel with SAVINGS/CHECKING BALANCE, TOTAL BALANCES (N), AVERAGE DAILY BALANCE, YTD DIVIDENDS EARNED, TAXABLE DIVIDENDS EARNED; per share <PRODUCT> nn and a per-share Recap of Fees for Courtesy Pay / Check Card Overdraft / NSF.
- **Oracle:** A printed equation row per share - x Beginning Balance + Deposits & Other Credits (N) - Checks Cleared (N) - Withdrawals & Other Debits (N) = New Balance - with PARENTHESISED counts, plus a running New Balance column and a document-level AVERAGE DAILY BALANCE.
- **Nearest reader:** analysis/symitar.py; core_processor_counted.py for the parenthesised-count grammar
- **Risks:** Equation labels and their four values are separate emissions - zip positionally. L-1 savings+checking, both usually posting. Marketing prose is interleaved into the ACCOUNT SUMMARY panel. Printed ADB is directly usable as evidence-only bank average under the ADB doctrine.
- **Merged from:** s1(7CD6F828),s7,s8,s10
- **shas:**
```
0A7A025F6FB6650046EABFEB02B0B67A52C61E711B2E8321BBDDEE5257254D45
4E2FD250B3123AE274B86940E2FBA7A8465155FDE938E4B91F4BE91A1C137D8F
4F95815AA215D7EBCD4B85D99D4AE22CAA9DEAECF056C3CCD74BF4BBD82CA187
7CD6F8282CB8FEA9535AF8D8BB5C75598CE78EE08EDD88DA7D01293C76937B10
D473A9338CAE957409EFAA85C9BE121EF319478D164B97FD8FC243FCAE9A7306
```

### 22. `commerce_bank_mybusiness_checking` (n=4, expected 3.2, 0.8)

- **Printed identity:** Commerce Bank. Bank Statement / Primary Account Number: nnnnnnnnn; If you have questions about your statement, please call us at 800-453-BANK; Statement Date: / Page Number:; a FOR YOUR INFORMATION block naming the Commerce Bank Mobile App / CashFlow Complete; product banner myBusiness Checking Account # nnnnnnnnn; sections Account Summary, Service Charge Summary, Checks Paid and Daily Balance Summary, each repeating Account #.
- **Oracle:** Printed totals (Beginning Balance on <date>, Deposits & Other Credits, Debit Card Purchases & Debits, Withdrawals & Other Debits, Checks Paid, Ending Balance on <date>, each with an explicit + or - operator), a dedicated Transaction Counts table (Debits / Credits / Deposited Items / Total Transactions) AND a Daily Balance Summary grid.
- **Nearest reader:** none (no commerce module); nearest grammar analysis/core_processor_counted.py, core_processor_daily.py
- **Risks:** Summary labels and their values are emitted as two separate runs (positional zip), and the Transaction Counts values sit on a line below their labels. The debit side is split THREE ways (debit-card purchases, other withdrawals, checks paid), so a two-bucket reader mis-totals. Section headers repeat Account #, so the layout is built for L-1 even though every member here is single-account.
- **Merged from:** s1,s2,s11,s12
- **shas:**
```
11D0F46DC2CAB2413D1FA0583C5C7706E25FB83B9A7F559BC7635A2A39343F90
5EDDAD75540957AC33C358FEFDC03810610F35D9FAA5FC7D6BE0FCEB095D2E04
7C2331AC1F695BAE0C63D748D383AF67FAA5D4F8807EAE4C41923756809BC20A
B64BE4A0E069A66B1764AEDB10813832527E0793D35A190042049045734C11E6
```

### 23. `pnc_core_commercial_checking` (n=4, expected 3.2, 0.8)

- **Printed identity:** PNC Core Commercial Checking. Running title PNC Core Commercial Checking Account Statement on every page; For the period mm/dd/yyyy to mm/dd/yyyy; Number of enclosures; For Client Services: Call 1-800-669-1518; Visit us at PNC.com/treasury; Write to: Treas Mgmt Client Care ... Pittsburgh PA; sections Account Summary Information / Balance Summary, Deposits and Other Credits, Checks and Other Debits, Ledger Balance.
- **Oracle:** The richest oracle in the census: four balance figures, a nine-row Description | Items | Amount category partition on EACH side with per-category item counts and Total rows, each detail section restating <n> transactions for a total of $x, and a full Ledger Balance daily grid.
- **Nearest reader:** analysis/pnc.py (registered PNC reader; near_miss pnc 0.25 without claiming this treasury template)
- **Risks:** Balance Summary emits its four VALUES before its four LABELS, so binding is positional within the block. Ledger Balance negatives use a TRAILING minus (10,488.47-). Long wire narratives wrap over several lines before the next date.
- **Merged from:** s3,s6,s8,s10
- **shas:**
```
059FBDC9539A0D9441A17B85797689539F74FDC33CB45C36BD70BE7539F1CA7C
8E830F06DC3D72F7ACAD64C12EC3E1A317BA7DA389794A5FBB8AE4E1A7F824DC
A4F79D175A8686FD0A2477341849BB9043170ECBC368BF3C157EA602234C231E
ABDC6C8EBE3EDEF04238134307A3C64C48B3F858A2420810EFC5BFEBC561C980
```

### 24. `mountain_america_cu_dot_leader` (n=9, expected 3.15, 0.35)

- **Printed identity:** Mountain America Credit Union, dot-leader printing. STATEMENT OF ACCOUNT / ACCOUNT NUMBER: XXXXXXnnnn / STATEMENT DATE: mm/dd/yy - mm/dd/yy / 801-325-6228 - 1-800-748-4302 / macu.com; ACCOUNT SUMMARY under TOTAL SHARES listing nn <SHARE NAME> ......... $x with dot leaders; per share <PRODUCT> - ID nn over the stacked heads POSTING DATE / TRANSACTION DESCRIPTION / TRANSACTION AMOUNT / NEW BALANCE.
- **Oracle:** Weak. Per share only dot-leader pseudo-rows Previous Balance / Ending Balance plus dividends, and a share roll-up of ending balances. NO credit or debit totals and no counts anywhere, so the running NEW BALANCE chain is the only reconciliation path.
- **Nearest reader:** analysis/symitar.py (share-ID genre); no macu module
- **Risks:** Long dot-leader runs must be collapsed before the amount pair can be located; card rows wrap a 23-digit reference plus merchant onto continuation lines. L-1 with 2-4 shares, usually only one posting. Largest members are 40-80k chars. Mountain America also prints a completely different UNQ-CLT template (see cu_unq_clt_trailing_minus_totals) - do not let one reader claim both.
- **Merged from:** s2,s4,s7,s8,s9(F56290E4),s10,s12
- **shas:**
```
1BAA5D5CE5B9D5924E540D41A19B01C93106C776AE3FC5A2565948A0CDBFAC53
36F9E9E232B58030AC48CB8FC18F45D6A8348670DA793BD64987ECBC09447A52
38642D4854FAAB74F1B93193BBEE24D05EE09CC2E750076C12FFDF65A545FE74
607E46D7B080010174459D2DB222191DA0373E5639A0DFC42FFDF8E9F7000970
85822DB14B966F29884BD436201675A4690E52A4BB9FA240747BAEDE3A069376
B6C40C8C4C6BBF0A56A51F1E3E46A1EDDE05EB5A9BCA80CDAF4C9BC9DDDBAF45
B8A4CDE1808E30F8BE88033B9A21E7123C4D4566AEF488DBEB16643B896E5827
F56290E40D40C5AE11DE577A8BD9615865279F6363F2D91EE5B45749D861A43E
FCE99FBDF5289F719F2E4E122365F00AF068E6F1970668115F5FAA39E7732290
```

### 25. `altura_riverside_cu` (n=5, expected 3.0, 0.6)

- **Printed identity:** Altura Credit Union (Riverside CA), institution not named in the text layer. A Tray1 print token; Account No. | Statement Period | Page over ***nnnn | mm/dd/yy Thru mm/dd/yy; To inquire or verify EFT transactions write us at: P.O. Box 908 Riverside, CA 92502-0908 or Phone: 1 (888) 883-7228; RETURN SERVICE REQUESTED; ACCOUNT SUMMARY listing nn <PRODUCT> $x; per share <PRODUCT> ID nn; a Deposits in Transit to Credit Union (Not Credited in this Statement) section.
- **Oracle:** A five-label header row Beginning Balance | Deposits/Credits | Withdrawals/Debits | Ending Balance | Y-T-D Dividends with the five values on the next line (positional zip), plus a running Balance on every row.
- **Nearest reader:** analysis/symitar.py (same descriptor grammar: Withdrawal POS #, Home Banking Transfer To ... Share nn, Draft nnn Tracer)
- **Risks:** Column order is Transaction Date | Posting Date | Withdrawal | Deposit | Balance | DESCRIPTION - the description comes LAST, after the balance, which defeats any left-to-right date-description-amount parser. The Deposits in Transit section must NOT be read as ledger rows. Registration must key on the Riverside PO box plus the ID-suffix furniture, never on a masthead.
- **Merged from:** s1(B2019068),s4,s6,s8(3D2098AE),s12
- **shas:**
```
3C72611C002FC81C90E40C1A292A5B543A296475D2EC5A3D7DCB3FB409F4D622
3D2098AE571B53CB6B41BC8C4329CBA9DA599FF8FF612AA1B5B39B3351BEC4E3
576367B4F41241199F5015972C697E88FD4CC68A352772E9F7907D35229C2A71
6E30DAB8DA51D3EA155D4559A97F6969E88F86222D458B5EF99088158E1EC663
B2019068FA2FA9BDE331E35C08B509BC3FF24F514FB2547B3B77042316FBC0D0
```

### 26. `jh_spaced_caps_checking_summary` (n=4, expected 2.8, 0.7)

- **Printed identity:** Fixed-width core printing with LETTER-SPACED banners inside dashed rules and no institution name anywhere in the text layer. Page head 0 - 01 PAGE N plus ***************************SNGLP and STATEMENT PERIOD mm/dd/yyyy TO mm/dd/yyyy; banners ------- C H E C K I N G  S U M M A R Y -------, ----- F E E  S U M M A R Y -----, ---- SUMMARY OF OVERDRAFT AND RETURNED ITEM FEES ----, ---- A C C O U N T  C R E D I T  T R A N S A C T I O N S ----, ---- D A I L Y  B A L A N C E  I N F O R M A T I O N ----; column legend DATE.....AMOUNT....DESCRIPTION.
- **Oracle:** Dot-leader summary rows CHECKING BALANCE LAST STATEMENT / DEPOSITS / <n> OTHER CREDITS / CHECKS / <n> OTHER DEBITS / CHECKING BALANCE THIS STATEMENT with leading counts on the two OTHER rows, TOTAL FEES IMPOSED with itemised fee lines, a period-vs-YTD overdraft box, and a three-up DAILY BALANCE INFORMATION grid.
- **Nearest reader:** analysis/core_processor_counted.py, core_processor_sectioned.py, core_processor_daily.py
- **Risks:** Overdrawn amounts carry an OD SUFFIX instead of a minus (569.25OD, 145.87OD) in both the summary and the daily grid - stripping it as noise inverts the balance. Intra-word spacing must be normalised before banner matching. A check-image index page must not be parsed as ledger. Institution is nowhere in the text (customer addresses Artesia NM etc.), so register on the letter-spaced banners.
- **Merged from:** s2,s5,s6
- **shas:**
```
4BE2A56DFCCDC00AA74996076E7E1D39214D1188CA5C8C173D66DE6A6CBADED1
52658F9C9A78205504730336946D2DF9EA0EE61CF6C73A7B43184701D695A52C
C6FE5EE0B55ED2C39244B57EFA4D8F644C6919BD0EC65B648D76838EDD4901CD
F2316D8D0DDAD0C9E6591A25408DE5C5D933862505CE81B964F119481D10FB6B
```

### 27. `pnc_treasury_enterprise_plan` (n=4, expected 2.8, 0.7)

- **Printed identity:** PNC Bank, Treasury Enterprise Plan. PO Box 609 Pittsburgh, PA 15230-9738 with the plan name printed as its own line above PNC Bank; For the Period mm/dd/yyyy to mm/dd/yyyy; Primary Account Number: XX-XXXX-nnnn; Number of enclosures: n; Visit us at PNC.com/smallbusiness; <customer> Treasury Enterprise Plan Summary; Balance Summary; two Description | Items | Amount tables; Daily Balance; Activity Detail sub-sections.
- **Oracle:** Balance Summary (beginning, deposits and other additions, checks and other deductions, ending, average ledger balance, average collected balance) plus per-category Items counts with Total rows on both sides plus a three-up Daily Balance grid - three independent checks on a two-to-four page document.
- **Nearest reader:** analysis/pnc.py (near_miss pnc 0.25 on every member) - a product-template variant, not a new institution
- **Risks:** The six Balance Summary labels and six figures arrive as separate runs, so pairing is positional. Two of four members print the additions/deductions PARTITION rather than individual dated transactions, so confirm whether this plan type ever prints a per-transaction ledger before promising row-level output. Two pages of IMPORTANT ACCOUNT INFORMATION prose precede the summary on some members.
- **Merged from:** s2,s4,s5,s7
- **shas:**
```
5BDEAC480C50BD57696E6175D5843F3ACE1D604CBFADA497A9C978E121B29CCE
92B161D89019118EC723DC2236A956DEFD86A1FEEB17666A7192C325FEC47425
9607A01E00D167F1B82B539CF9904291B828B80009053EE32D983ABA8DBA8A19
A88122B84542B4ED88A9247FDBE96A7C5662767CC27E2D7F4C1AC02CA22E7B62
```

### 28. `pnc_virtual_wallet_performance_spend` (n=4, expected 2.8, 0.7)

- **Printed identity:** PNC consumer Virtual Wallet. Virtual Wallet With Performance Spend Statement repeated as the page header; PNC Bank / PO Box 609 Pittsburgh PA 15230-9738; Primary account number: XX-XXXX-nnnn; For the period mm/dd/yyyy to mm/dd/yyyy  Number of enclosures: n; VIRTUAL WALLET FINE PRINT UPDATES ARE CONTINUED AT THE END OF YOUR STATEMENT; sections Balance Summary, Transaction Summary, Interest Summary, Overdraft and Returned Item Fee Summary, Activity Detail, and on some a Daily Balance Detail.
- **Oracle:** Balance Summary (beginning, deposits and other additions, checks and other deductions, ending, average monthly balance, average collected balance) plus counts stated in PROSE above each section - There were 103 Deposits and Other Additions totaling $16,920.51 - which restates both the count and the total per direction, plus a Transaction Summary count block.
- **Nearest reader:** analysis/pnc.py (near_miss pnc 0.25) - the consumer Virtual Wallet skin differs from the business skin
- **Risks:** The four Balance Summary values arrive as one space-separated run AFTER four label lines and a negative ending balance is printed with a TRAILING minus. Counts must be parsed out of prose sentences. Virtual Wallet sub-accounts (Spend/Reserve/Growth) print as sections under one primary number and must not be read as separate statements. Up to 24 pages, many of them fine-print.
- **Merged from:** s1,s9,s11,s12
- **shas:**
```
028A40341991F9A5B4CD06E8057856BFCD2C9E52624DBAE9F14E53471C8C0B8A
392712FC2E9E69194658047485C5DF99C1468C4EC2F28A2C00A05BFD1CA4B3C1
3EA2CEF559AD67D48B849A0BAC289324E673884F31E7EF51960AD6DF10FFEEDC
CC533142FA14EDD55A80FDE15CD756EC51053945E7CE9DC32AEDBBF742C0335D
```

### 29. `suncoast_cu_account_statement` (n=4, expected 2.8, 0.7)

- **Printed identity:** Suncoast Credit Union. Suncoast Account Statement / Member Number: nnnnnnnnnn  mm/dd/yyyy - mm/dd/yyyy  Page n of m; Access Your Account: SunNet Online Banking / SunMobile App / SunTel Phone Banking; footer 800.999.5887 | 813.621.7511 | suncoastcreditunion.com | P.O. Box 11904, Tampa, FL 33680; per suffix <PRODUCT> Suffix nnnn with Activity Summary and Transaction History; Year to Date Summary Dividends Paid YTD.
- **Oracle:** Per suffix an Activity Summary of Previous Balance <date>, Deposits, Withdrawals (printed negative), Ending Balance <date>, plus a per-suffix Total for this Statement Period | Total Year to Date fee box and a running New Balance opened by a Balance Forward row.
- **Nearest reader:** analysis/symitar.py (genre); no suncoast module. Two members were probe-resolved out of shard-2's bundled vendor-core family by their P.O. Box 11904 masthead.
- **Risks:** L-1 savings plus checking suffix; a suffix can carry a Balance Forward row and No transactions for this cycle with NO Activity Summary block, so a reader must tolerate a missing per-account summary. The merchant/counterparty detail wraps to the following line. One member trips cp1252 output (an fi ligature codepoint survives), so the harness must be UTF-8 clean.
- **Merged from:** probe-resolved from s2; s10,s11
- **shas:**
```
0D2AC06CC734F16D4ACEAB0D402621BF103EC74BC4858EE8D5CB7CE3971C837D
39462E4FAE7414EC3B137EA3870527F2EDAD35B8DC4D91835987337E0AFAEE4C
404CF3726C6A5FEC1588FC6E03029D566056770774B5F9246F2485EA4A33EF31
B2F2627A213E1372DD60C54A4DC8B25F94AE08BE258166322ED8AFDC9336AA9C
```

### 30. `usaa_fsb_classic_checking` (n=4, expected 2.8, 0.7)

- **Printed identity:** USAA Federal Savings Bank. USAA CLASSIC / CHECKING masthead; USAA Federal Savings Bank 10750 McDermott Freeway San Antonio, Texas 78288-0544; for Account Number: nnnnnnnnnn  Statement Period: mm/dd/yyyy to mm/dd/yyyy; Activity Summary; a Fees table with Total For This Period | Total Year-to-Date for OD and NSF fees; Transactions / Transactions (continued); footer Online: usaa.com  Phone: 210-531-USAA (8722).
- **Oracle:** Beginning Balance, <n> Deposits/Credits, <n> Withdrawals/Debits (counts printed immediately LEFT of the label), Service Charges and ATM Service Fee, Ending Balance, plus a running Balance column opened by a Beginning Balance row - counts, totals and a chain.
- **Nearest reader:** none (no usaa module); nearest behavioural sibling analysis/navy_federal.py
- **Risks:** The text layer emits stray isolated 0 placeholder tokens for the empty debit/credit cell and pushes the amount pair onto the following line, so a naive line reader mis-assigns debit vs credit; the Debits and Credits columns collapse into one amount stream and the sign has to be re-derived from the running balance. Otherwise a clean, cheap win.
- **Merged from:** s1,s2,s4,s12
- **shas:**
```
2014B141CA507B9B31314D3E82A1F3868844D733FF94772E4D24BD86B1340F64
80FE707815B509E9BED7FE7276DD894DA885F097BA4E1658C08D6476FA7A23CC
937DCCDA51C88032E41BB5263F17AF490A2A64689F447A790D25F78B2C017089
C5CB05E28B201185E3714D46315FD493AC34E79FC3E1A4B634F15A719367D8FE
```

### 31. `vystar_balance_summary_transactional_detail` (n=4, expected 2.8, 0.7)

- **Printed identity:** VyStar Credit Union, Summary of Accounts issue. For assistance, call our Contact Center at 904-777-6000 or 800-445-6289 ... VyChat at vystarcu.org; Payment address PO Box 45085 Jacksonville, FL 32232; Statement Period: mm/dd/yyyy - mm/dd/yyyy / Statement Date: / Member Number: / Page n of m; Summary of Accounts (Account Type | Account Number | Balance); per account the paired headings Balance Summary and Account Summary; ledger banner Transactional Detail; a page-2 CHECKING ACCOUNT RECONCILIATION worksheet.
- **Oracle:** Beginning Balance as of mm/dd/yy, + Deposits and Credits (N), - Withdrawals and Debits (N) with parenthesised counts, Ending Balance as of mm/dd/yy - both balances dated and the operators printed - plus Interest for Period / Interest Paid YTD / Interest Rate and a running Balance opened by a Beginning Balance row.
- **Nearest reader:** analysis/symitar.py (genre); analysis/fiserv_premier.py reads the same parenthesised-counts convention under different direction labels
- **Risks:** TRAILING MINUS means NEGATIVE here (63.00-, Ending Balance ... 373.20-) - the exact opposite of the cu_unq_clt_trailing_minus_totals family, so the two must never share a money parser. Non-calendar statement periods (04/16-05/15) mean ADB must use the printed period. Card rows wrap merchant address plus Seq#nnnnnn Date Time onto continuation lines. L-1 on some members.
- **Merged from:** s2(2DA7A3F4),s4,s11
- **shas:**
```
24C879724BAF6D7B260A0112DB493A8592710BDB184C7B6D4A47AF446048F1E8
2DA7A3F496E8D46C83DD9B27B85574319CB9AA70AE4D03240E894D9C36FB4D68
9F1FD3D18E3221F84D1FF91D70F00B8925955C69A580D772AA87D5D2E2524133
D4E905D5F0C571FA938C7DA2FA73EDEC2D48A42C079C7D20CC7865B0355661FA
```

### 32. `chime_bancorp_checking` (n=5, expected 2.75, 0.55)

- **Printed identity:** Chime on The Bancorp Bank rails. Member Services (844) 244-6363; Checking Account Statement; Statement period <Month YYYY> (<Mon> 01, YYYY - <Mon> 31, YYYY); Issued by The Bancorp Bank, N.A., Member FDIC; the Chime-specific summary rows Round Up Transfers and SpotMe Tips; ledger heads TRANSACTION DATE | DESCRIPTION | TYPE | AMOUNT | NET AMOUNT | SETTLEMENT DATE.
- **Oracle:** An unusually rich nine-category signed partition between a dated Beginning balance and a dated Ending balance (Deposits, ATM Withdrawals, Purchases, Adjustments, Transfers, Round Up Transfers, Fees, SpotMe Tips), so each category can be validated independently.
- **Nearest reader:** none (no chime/bancorp module); nearest fintech readers analysis/relay.py, mercury.py, bluevine.py, found_lead.py
- **Risks:** No running balance and no daily grid - the category partition is the only closure. Two amount columns (AMOUNT and NET AMOUNT) per row invite double counting. Enormous Round-Up and Moved-to/from-Secured-Deposit-Account churn (one member is 27 pages / 88k chars) inflates gross deposit and withdrawal volume relative to real cash flow unless the paired internal transfers are classified out. One member has beginning and ending balance both $0.00 - a zero-balance guard must not reject it.
- **Merged from:** s5,s7,s9,s11
- **shas:**
```
298CE16010532430129EEC33F972CA6CB0BBA8D75DB5DB5BD70626C747B88D18
3BEE554535974F7F71574D2EEF59171C2939CE2DE5AEDFA18A26A1A72C501590
659A7C06C76C00751E9AAEB7ABD08E43802060D717AF02C87DE887328CC078D0
9DE68C11B95C52032C855C6034BF01414B008AF6D8CC7F36725A2BDB9D64CD42
DFF6FB0C93B51788B8C8E8D5A4F7188AC921F6A2ED3815688F48CA99AB7BF3D0
```

### 33. `bokf_business_access` (n=4, expected 2.6, 0.65)

- **Printed identity:** BOKF, NA (trading as Bank of Oklahoma and sibling regional brands). A division of BOKF, NA  P.O. Box 2300 Tulsa, OK 74192-0001; PRIMARY ACCOUNT nnnn; Member FDIC; Statement Period: mm-dd-yy to mm-dd-yy; Direct Inquiries To: 24-Hour ExpressBank; www.bok.com; <n> Images Provided Page n of m; product banner BUSINESS ACCESS ACCOUNT: <acct> and RD Statement Period from ... through ...; sections DEPOSITS / WITHDRAWALS / CHECKS / DAILY ACCOUNT BALANCE.
- **Oracle:** An operator-column equation - $ Starting Balance / + <n> Deposits <total> / - <n> Checks & Withdrawals <total> / - Service Fees / = Ending Balance - with the item count between the operator and the label, plus SERVICE FEE BALANCE INFORMATION (AVG LEDGER BALANCE, AVG COLLECTED BAL, MINIMUM LEDGER BAL) and, on most members, a DAILY ACCOUNT BALANCE grid.
- **Nearest reader:** none (no bokf/bok module); register on A division of BOKF, NA plus the operator column so it generalises across the regional mastheads
- **Risks:** The +/-/= glyphs are emitted on separate short lines from their labels, so the summary must be reassembled by label order rather than adjacency. No running balance on rows; amounts unsigned with direction from the section. Sub-cent amounts print without a leading zero (.59). Per-page barcode blocks need filtering.
- **Merged from:** s4,s5,s8,s12
- **shas:**
```
5A5FDD3FB7AED636A1B1A7B205CC1A57D015C5E1DBAA0009791EB0C62E12E706
C1C954F932F175D7105637066DBB62EDB50A519C3B7114FF61D2F7F51F48CE56
E2AA4A12F03DBCFDF28E4E56F3DD4C3551DF34BA0D917C55A17632B1AA7F5FAF
EAB8FD5941314C4CC53FD0A667681470F2ADEBAB4F85D0F5E4607AC03C38899B
```

### 34. `nbkc_bank_dda_statement` (n=4, expected 2.6, 0.65)

- **Printed identity:** nbkc bank. 8320 Ward Parkway, Kansas City, MO 64114  www.nbkc.com | 866.931.0850 as masthead and repeated footer; STATEMENT SUMMARY Page: n; Statement Date / Beginning Date / Ending Date; Business Account-XXXnnnn; Account Holder:; Transaction Details / Transaction Details (continued); Continued on next page; document trailer newdoc 000000NNNNNN DDA Statement.
- **Oracle:** Beginning Balance as of mm/dd/yy, Deposits & Other Credits, Charges & Fees, Checks & Other Debits, Ending Balance as of mm/dd/yy - a fully printed five-term identity; some printings add a Daily Balance grid.
- **Nearest reader:** none (no nbkc module)
- **Risks:** The AMOUNT is emitted on the line AFTER the description, so every transaction spans two lines. Rows are NOT in date order (all credits then all debits within a page), so date monotonicity cannot be used to segment. No counts and, on most members, no running balance - the five-term identity is the only closure. Direction lives inside the type word (ACH Credit / ACH Debit / ATM POS Credit).
- **Merged from:** s1,s2,s11,s12
- **shas:**
```
11D1DDBCC3BCE4F55F06A6D33F66E6A8923ACBCE2ED92D2488E89EBAC2BD1AE5
307187CA1EA1F9335037343866FA630977423D59C5C66F5CB7F6AECEC1759041
36F9981C9F025DC1D3A9D584E4C7204800D9027E4EF22B85E7C514DA7A19AF48
370B9256BA110FC1031BC66511B9875F6F0B6BA3FC05C16E3B69CCCB3852C2F6
```

### 35. `associated_bank_financial_statement_of_accounts` (n=4, expected 2.4, 0.6)

- **Printed identity:** Associated Bank N.A. PO Box 19097 Green Bay WI 54307-9097 Midwest-based Business Banking Concierge: 1-800-728-3501; FINANCIAL STATEMENT OF ACCOUNTS Primary Account:; Statement Activity Period mm/dd/yyyy to mm/dd/yyyy; FINANCIAL SUMMARY ACCOUNT# | BALANCE over DEPOSIT ACCOUNTS; product line Business Balanced Checking #<acct>; Bank: 001 / Mail Code: 0S.
- **Oracle:** Beginning Balance / Plus: Deposits and Other Additions / Minus: Withdrawals and Other Deductions / Minus: Checks Paid / ENDING BALANCE ON <date> - a four-way partition with checks split out - plus per-section TOTAL $ and TOTAL # OF ITEMS footers and a Balance Summary DATE | BALANCE grid.
- **Nearest reader:** none (no associated_bank module)
- **Risks:** EVERY non-ledger line (and on some members every ledger row) is emitted TWICE verbatim - a reader that sums matched summary lines or walks the ledger without collapsing adjacent identical lines will double every figure. Pages 1-2 are change-in-terms notice. The printed page count disagrees with the PDF page count, and the Balance Summary grid starts after day-one activity so its first row is not the Beginning Balance.
- **Merged from:** s3,s4,s5,s6
- **shas:**
```
2C0A230A83A11FA7F5D82A2DF713BEFFBC695CA4E49EB7EF436F6BE45DAAFD98
4C4EAE7A79B5583C00169A1371B1A180D1882B496CE8BB4DE51C797901926BF2
6B8B49B0C190146FE8D2460689967F0851B0B2F0FBFBB703C4409AA29388D301
86355161E964F37AC18A09F08BE5892DB0ECC217647510ADAF98A501A425DE20
```

### 36. `city_national_bank_florida` (n=4, expected 2.4, 0.6)

- **Printed identity:** City National Bank of Florida (Miami/Coral Gables - not City National of CA). Client Services / Online citynational.com  CityTel 1-800-762-CITY (2489); Your Banking Center and Your Banking Center Hours blocks; 2701 S Le Jeune Rd, 8th Floor Coral Gables FL 833-448-6500; product Regular Commercial Checking; Account Summary Account: XXXXXXXnnnn Last Statement: <Month D, YYYY> This Statement: <Month D, YYYY>; Daily Activity; a printed reconciliation worksheet on page 2; footer hash plus <YYYYMMDD> Checking Account Statements.
- **Oracle:** Beginning Balance, Ending Balance, Average Ledger Balance and Low Balance, plus a running Balance on every Daily Activity row opened by a Beginning Balance row, and on some members a closing mm-dd Ending totals row giving total deposits and total withdrawals.
- **Nearest reader:** none (no city_national module); analysis/core_processor_daily.py matches the Last Statement / This Statement period grammar
- **Risks:** No period credit or debit totals are printed on most members, so closure rests on beginning + rows = ending plus the printed Low Balance. Marketing copy is interleaved BETWEEN ledger rows and must be filtered. Deposits and withdrawals sit in adjacent unsigned columns - use the balance delta. The page-2 reconciliation worksheet repeats balance vocabulary.
- **Merged from:** s5,s6,s7,s8
- **shas:**
```
082219AD531A6A03CA60112444EC3B870F407726201266B124A3C0A59D89CA9A
66800C3774B1AFF1A527B39C3D1199D57455750E621FD896CA29A8CFF5A32542
BEAD76F55A7375F95FA44B6E6CE019E1BDCA442E646063FFFEFFD1E0AF861241
CBD038618A4BAEFEDD505CB13A4378D4F672DA3765211F9CC2AC1304C2991792
```

### 37. `greater_nevada_cu` (n=4, expected 2.4, 0.6)

- **Printed identity:** Greater Nevada Credit Union (Reno NV); the name appears only in the footer and the non-transferable-share notice. A Tray1 print tag; Member # | Statement Period | Page; Account Balance Summary listing each share by product name (Commercial Shares, Business Analysis); per share <Product> (Acct# ******nnnn); ledger heads Trans. Date | Transaction | Balance | Description; an APY paragraph per share; No Transactions This Period on dormant shares.
- **Oracle:** A five-cell per-share row: Previous Balance | Debits/Withdrawals | Credits/Deposits | Ending Balance | YTD Dividends, plus a running Balance opened by a Previous Balance row.
- **Nearest reader:** analysis/symitar.py (CU genre; the six-figure equation-row oracle is this shape minus dividends)
- **Risks:** Dates are the compact MMMDD token (APR01, FEB01) with NO year and no separator - the year must come from the period header and a December/January boundary needs care. Column order is amount-then-balance-then-description, the reverse of nearly every other family here. Multi-line EDI blobs (ISA*00*...) are embedded in descriptions. L-1 commercial share plus business analysis checking.
- **Merged from:** s1(DAC49AD1),s3,s5,s9
- **shas:**
```
770F8DD0404E6081DB3AD7EEA6DE7D136943598FB7E4B5AD288DD48B066754BD
C1C12193EA6AEAEA3391623502AB013C7C47DAA7943EA5ED7C9B5B2EC893F34C
D8278B18E789FE39837134049553EE582714C63EE667FC692D33143391C741E5
DAC49AD1DF91AC1455C3F88F8A3A81A3DA3E91F944A6346CC23640D8A5394F5E
```

### 38. `green_dot_bank_partner_program` (n=4, expected 2.4, 0.6)

- **Printed identity:** A Green Dot Bank sponsored program; the program brand is image-only and never appears in the text. Banking services provided by Green Dot Bank, Member FDIC repeated as a per-page header with ACCOUNT NUMBER nnnn-nnnn-nnnn-nn, STATEMENT PERIOD <Mon>. DD, YYYY to <Mon>. DD, YYYY and ROUTING NUMBER 124-303-214; sections ACCOUNT SUMMARY and TRANSACTIONS with DATE | DESCRIPTION | AMOUNT.
- **Oracle:** Beginning Balance on <date>, Credits, Debits, Ending Balance on <date> - four printed figures with the + and - printed as separate tokens; some members add per-sub-account Ending Balance and Average Daily Balance this Period.
- **Nearest reader:** none (no green_dot module); nearest fintech readers analysis/found_lead.py, relay.py, mercury.py, square_checking.py
- **Risks:** No running balance and no daily grid - the four figures are the whole oracle. The sign is a separate token joined to the amount by a non-breaking space (- $19.99) on its own wrapped line, so losing the prefix silently inverts the ledger. Merchant city/state wraps to a following line and the transaction-kind word (Purchase/Deposit/Fee/Transfer) terminates the description. Statement periods straddle month boundaries.
- **Merged from:** s9,s10,s11,s12
- **shas:**
```
055A3863CB800D9B72A287E9E36AEB7409D8C88CBDA32BE2996D786B59F6F433
18DC970783704F78629543C301F29D3AC1ED484720EE587271F738571A8CF9A2
AF9E7AA6ECD05B9CD771BCB68C14BCE874D22C780A8F556B22E4CB8F3B5EDEBE
DD3F97FDADDDA54EE64191160731BAE02514908414C4B37EA4020DE1A61ED1AD
```

### 39. `hapo_cu_estatement` (n=4, expected 2.4, 0.6)

- **Printed identity:** HAPO Community Credit Union. E Statement of Account with the stacked header Member # / Statement Period / Page; 601 WILLIAMS BLVD. RICHLAND, WA 99354-3258; 509.943.5676 - WWW.HAPO.ORG; 800.284.4276 (TOLL FREE); ACCOUNT SUMMARY / DEPOSIT ACCOUNTS TOTAL BALANCE: $x over Account Type | Previous Balance | Deposits | Withdrawals | Ending Balance; per account <PRODUCT> (Suffix nnnn) split into class sections Electronic Credits / Electronic Debits / Checks Deposited & Drafts Cleared, each continuing with (continued); footer TOTAL OVERDRAFT FEES / TOTAL RETURNED ITEM FEES period vs YTD.
- **Oracle:** The ACCOUNT SUMMARY table states Previous Balance, Deposits, Withdrawals and Ending Balance per account plus a DEPOSIT ACCOUNTS TOTAL BALANCE - four printed figures per account and nothing else.
- **Nearest reader:** analysis/community_section.py (sectioned, no running balance) and symitar.py
- **Risks:** No daily grid and NO balance column in any section, so previous + section credit totals - section debit totals = ending is the only path and section-completeness is therefore load-bearing, not optional. Direction comes solely from the class section heading, so a missed section boundary flips signs. Rows are hyphen-dated mm-dd with no year and several can share a line.
- **Merged from:** s4,s7,s10
- **shas:**
```
0933021A33F1DC4A346D46E75F552768FA98C1A589A1170EBE3290DFDC8E6A6F
8B640C6A89D81B32C1729BF072C1D621FD5D908EF42A9A5A21BE9E8C59484714
B53912D549B251019A54295D5DBD1A09D83B9549AD01688B40657DDD4DE876FE
FA078B47381E23F289611B505D8E13A28D340C67B89148AA5A704BFCAE1D4460
```

### 40. `ornl_fcu_oak_ridge` (n=4, expected 2.4, 0.6)

- **Printed identity:** ORNL Federal Credit Union (Oak Ridge TN); the name never appears in the text layer. PO Box 365  221 S Rutgers Ave  Oak Ridge, TN 37831 with Statement Date / Account #; ELECTRONIC SERVICE REQUESTED; ACCOUNT SUMMARY / Deposit Accounts | Account ID | Beginning Balance | Deposits | Withdrawals | Ending Balance; per account <PRODUCT> 00nn; boilerplate refers only to the Credit Union and 800.676.5328. Descriptions are Title-Cased throughout (Amzn.Com/Bill, Https://Canva.Com) - a distinctive fingerprint.
- **Oracle:** The ACCOUNT SUMMARY grid gives Beginning Balance, Deposits, Withdrawals and Ending Balance for EVERY account in one table, and each account ledger opens on a Beginning Balance row and carries a running Balance.
- **Nearest reader:** analysis/symitar.py
- **Risks:** L-1 with three shares (membership, small business checking, payroll) and heavy Home Banking Transfer mirroring: every inter-share transfer appears once in each share's ledger, so concatenating ledgers double-counts - the summary grid is the authority. A zero-activity PAYROLL account prints in the summary with no ledger. Largest member is ~59k chars. Institution must be inferred from the Oak Ridge address block.
- **Merged from:** s9(70DBD873, EC66EA1A),s10,s12
- **shas:**
```
2A39E0BC5EB09B8875A4F59E2FACBCAED6CCAFE586A84B67C4F6911C94AC43E4
70DBD873735633642E54CE8CC3CA11FBBCE1EAC5FE9659C54AFDF0CB94A08479
DABCBBB011E51CBCC63B47EBAFDA85F832A5F1206C9124F20611EB4B2C374145
EC66EA1AA7D2298CF8966676DE7D24C59FFC8B2670B5F2830A9B3C422D343000
```

### 41. `sierra_central_cu` (n=4, expected 2.4, 0.6)

- **Printed identity:** Sierra Central Credit Union, institution not spelled out in the text layer. Header is a bare <routing> mm/dd/yy mm/dd/yy n of m line with For inquiries, contact 800-222-SCCU (7228) as the only institution mark and as the footer of every page; Account Summary Ending Balance with a Total Checking roll-up; per account <acct> BUSINESS - LOW VOLUME CHECKING; a Y-T-D SUMMARIES FOR ALL ACCOUNTS tax block.
- **Oracle:** A four-line stacked equation Opening Balance / + Total Deposits(N) / - Total Withdrawals(M) / = Ending Balance with the counts glued into the label in parentheses and the four values emitted as a following run, plus a period-vs-YTD aggregate overdraft/NSF fee table.
- **Nearest reader:** analysis/symitar.py and core_processor_counted.py (genre only); no registered reader matched
- **Risks:** NO daily grid and NO running balance column at all, so the four summary figures plus the two counts are the entire oracle - a strict sum gate that fails loudly rather than quietly. Ledger is Date | Transaction Description | Deposit | Withdrawal with explicit signs, but several transactions can share one physical line, so split on the date token. Rejected/returned triples (debit, (Rejected) reversal, (Returned) fee) are all real rows.
- **Merged from:** s1,s4,s8,s9
- **shas:**
```
3920A0E77BE2850FE85EDC05D5113E9EC873179BABB638290FCB2482876CF6DB
510993B1B8CAF1398A74C8A371A910596973AFBB7C6DD7A38DBE00455B7C184E
89C644EFD337581C42E83FFB4E8ED075990C68A607AD89C3DCCC0B5C0E58D487
D322B95D1284D35A8908BB6F4AE3351D4133A48E2EB2D36DB8A91F028A3F49C3
```

### 42. `townebank_balance_summary` (n=4, expected 2.4, 0.6)

- **Printed identity:** TowneBank, and one sibling printing of the same statement-vendor template from a Kansas City MO mailstop (SmallBusiness ESSENTIAL BUSINESS CHECKING). Account Number: XXXXXXnnnn Statement Date: mm/dd/yyyy Items Enclosed: n; Member Service Information; Lost or Stolen Card: 888-638-6718; Email Inquiries: info@townebank.com / Visit Us Online: www.townebank.com / facebook.com/townebank; product banner VALUE CLASSIC; sections Balance Summary, Checks Posted (* Indicates a break in check sequence), Transaction Detail, Balance By Date; back page How to Balance Your Checkbook; OMR/job-code blocks on the first and last page.
- **Oracle:** Beginning Balance as of mm/dd/yy, + Deposits and Credits (N), - Checks Posted (N), - Withdrawals and Debits (N), Ending Balance as of mm/dd/yy with PARENTHESISED counts on all three directions, plus Number of Days in Statement Period, Items Enclosed and a Balance By Date grid.
- **Nearest reader:** analysis/balance_by_date.py (top near_miss - targets the same Balance By Date furniture); analysis/core_processor_counted.py for the parenthesised-count grammar
- **Risks:** Transaction Detail has NO balance column and the Deposits and Withdrawals columns are distinguished only by horizontal position, which the text layer flattens - the printed counts are what validate whichever split rule is chosen. Several transactions can share one physical line. Dates print as Mon DD with no year, so a December/January rollover needs the statement period.
- **Merged from:** s2(109829BB of balance_summary_paren_counts),s6,s11(A5BAD30E of vendor_balance_summary_as_of),s12
- **shas:**
```
109829BBA4AD538E8FB7F2ECFBA7F5A39D4F8A78DB9B61C9E41380EF19D3ACF7
5787A09F6D382E7EC4F6B03F44280AE2C86FA922D95EB9215DF3EBA4D12189CD
A5BAD30E8234394B87AA4C8431518AB33E31A865C3B9DCD37797B950B477834A
CEA84CFA7024197235129651096EEFB309FCD4103BF1EE05AECAB55C4E194F61
```

### 43. `cubase_suffix_box_summary_history` (n=5, expected 2.25, 0.45)

- **Printed identity:** A CU*BASE-style core, institution never named in the text layer on most members (one is Hercules First FCU, 3141 West 4700 South Taylorsville UT (801) 968-9011; the others print only Send Inquiries To: plus the tagline Rooted locally / Guided by care / Focused on you and Simply Better Banking). ACCOUNT NUMBER: / YTD DIV RECEIVED: / PAGE NUMBER: n of m; SUMMARY OF YOUR ACCOUNTS drawn as an ASCII pipe-and-underscore box with one COLUMN PER SUFFIX; per-suffix banner SUFFIX nnn <PRODUCT> and (NO ACTIVITY); ledger banner HISTORY / HISTORY (CONTINUED) with DATE | DESCRIPTION | TRANSACTION AMOUNT | ACCOUNT BALANCE | TRACE#.
- **Oracle:** Everything a gate needs is printed per suffix inside the box: BEGINNING BALANCE, DEPOSITS <n> <amt>, WITHDRAWALS <n> <amt>, CHECKS CLEARED <n> <amt>, ENDING BALANCE, DIVIDEND YEAR-TO-DATE / THIS PERIOD, AVERAGE DAILY BALANCE, DAYS DIVIDEND EARNED, APY - plus a running ACCOUNT BALANCE per row.
- **Nearest reader:** none (SUFFIX/HISTORY/TRACE# grammar is not represented in analysis/); analysis/symitar.py is the nearest CU core
- **Risks:** The defining hazard is the box: two or three suffixes sit SIDE BY SIDE, so every printed summary line carries a cell from more than one account separated by pipes - a line-oriented label:value parser silently attributes one account's totals to another. Must split on the rules and track the column-to-suffix map from the header. Loan suffixes appear alongside shares and print a different label set. Debits carry a trailing minus.
- **Merged from:** s4,s5,s6,s8
- **shas:**
```
1DE09FAE4185E4A1A789DD2DEC6D5D2A8A0A8470FE8BD908ECF3EE708EEF073D
458B42D3BEAF105A0D95AC8B1BAC0E52CC9A568A350833CEA7222EF719826CED
AAAC3125C9B69ACA7F0DC83BD994013B22704788D43534DB0CB0C7AD6BE998E7
C32D4729CD93A536D686CF2F8595368B86605895873588E20092D41231290624
F921E27F9C247E5EB305AEAB0063233182BC9CACAC4DAB353802669350C2EBB0
```

### 44. `rbfcu_business_member_statement` (n=5, expected 2.25, 0.45)

- **Printed identity:** Randolph-Brooks FCU. Statement Period mm/dd/yyyy through mm/dd/yyyy; rbfcu.org P.O. Box 2097, Universal City, TX 78148-2097; Direct Inquiries to Member Services; Routing #: 314089681; ** DO NOT MAIL **; per account <PRODUCT> SUMMARY | <account number> with **Savings Rate / *APYE, then a detached four-value row Previous Statement Balance | Total Credits | Total Debits | Current Statement Balance; activity banners <Account> Deposits & Other Transactions / Checking Account Deposits / Freedom Check Card & Other Transactions; an Other Information fee table with Total Overdraft / Returned Item Fees period vs YTD; No activity this statement period. on dormant accounts.
- **Oracle:** A four-figure per-account row (labels on one line, figures on the next - positional zip) and nothing else: no counts, no running balance, no daily grid.
- **Nearest reader:** none (no rbfcu module); nearest large-CU readers analysis/secu.py, navy_federal.py, midflorida.py
- **Risks:** The ledger is printed TWO logical columns across the page (Date Description Amount | Date Description Amount) which the text layer interleaves onto one run, and long wire descriptions wrap so the amount lands several lines away - row order within a day is unrecoverable. With no balance column the four-value row is the only gate, so a reader must sum the two-up ledger to it exactly or decline. L-1 savings+checking, savings usually dormant.
- **Merged from:** s3,s7,s8,s9
- **shas:**
```
16EFD50B640FF361C62F6FF147BE5E1B7232FF5A39AB3538BDBBFF9028741B60
6F721D4487BEFCB92D419E9124066783D0E9D20C499713FF88EFBF64DFEC61E5
8346B18E10AADAA91B42294789D697AA6EFC9CA6782E70618DDC2B42E4AB346D
C8264D9A0F79959F670545570FBA781C6E7E4415031627ED2D5EB7896F1C7315
F7D702B7B71342AD46027DC7C30A129BDF764454743FFFC1D5E3A5B1D545A5AF
```

### 45. `altra_fcu_statement_summary` (n=3, expected 2.25, 0.75)

- **Printed identity:** Altra Federal Credit Union. Statement Period | Primary Account stacked over mm/dd/yyyy and XXXXXXnnnn; Statement Summary with a Deposit Accounts | Beginning Balance | Deposits | Withdrawals | Ending Balance table closing on a DEPOSIT TOTALS row; per account <PRODUCT> - Account#: XXXXXXnnnn  mm/dd/yyyy - mm/dd/yyyy with YTD Dividends and Annual Percentage Yield Earned; footer Altra Federal Credit Union, 1700 Oak Forest Drive, Onalaska, WI 54650 ... Federally Insured by NCUA.
- **Oracle:** Totals at TWO levels - the front table gives all four figures per account plus a DEPOSIT TOTALS row that cross-foots them, and each account block restates Beginning Balance and Ending Balance - with a running Balance on every row.
- **Nearest reader:** none by name; descriptor grammar matches the sierra_central / Idaho-equation CU core
- **Risks:** Cheapest CU win in the census: explicit leading-minus signs, one row per line, no continuation wrapping. Only quirks are the abbreviated column labels Post. and Eff. (a regex for Posting Date / Effective Date will not match) and several transactions concatenated onto one physical line, so split on the date pair. Zero-activity accounts print There were no transactions for this statement period.
- **Merged from:** s4,s7,s11
- **shas:**
```
03630BDEBDFB60C9571EAA1B61991377F5FC68D10BB6F4591D4D802617481B84
2A8F1A9D95DD06721AF8C1F28B4811277BC0C6FA3669CE28B7DD78AC701711F9
B385771D2521F72AF460C9383C04BF58392A6F2BEA8A9C4F689B59852E52F6F5
```

### 46. `cu_statement_summary_prev_new_balance_unbranded` (n=4, expected 2.2, 0.55)

- **Printed identity:** An unbranded credit-union core - no institution name, phone, URL or wordmark anywhere in the text layer on any member (customer addresses Georgia). Statement of Account / Statement Period mm/dd/yy - mm/dd/yy / Account Number XXXXXX0006; STATEMENT SUMMARY with Deposit Accounts Total Deposits: $x over Account Type | Previous Balance | Deposits | Withdrawals | New Balance; per account <PRODUCT> (nn) New Balance: $x and <PRODUCT> (nn) continued; ACH rows carry TYPE: ... ID: ... NAME: ... Entry Class Code: CCD/WEB continuation lines.
- **Oracle:** A four-figure printed row per account (Previous Balance, Deposits, Withdrawals, New Balance) plus a document-level Total Deposits roll-up and a running Balance opened by a Previous Balance row.
- **Nearest reader:** analysis/community_section.py; analysis/fiserv_premier.py was the top near_miss (0.25) on the (nn) suffix plus Eff.-date shape
- **Risks:** Institution is unidentifiable, so registration must be on the STATEMENT SUMMARY / Deposit Accounts / Previous Balance ... New Balance furniture plus the Entry Class Code descriptor style. The Eff. column is usually blank and occasionally populated, so a fixed-position date reader mis-shifts those rows. NSF advisory rows print with no amount in either column and must not be read as transactions.
- **Merged from:** s5(D6E72C89),s6(D2D2ABE4),s7,s12
- **shas:**
```
47F8514AE17416CF2C9451CD22C3AFC6941663CBE79970468DEA8A0C2810B8B4
AA257B9EAB43035066EB3A54F4FF1A4F59801926CD723DB0D00ACD83B817F3B9
D2D2ABE4275AC46BDAC04813861496A27A437711C3B1FDB7C2FE8BB853FF4A1E
D6E72C89BA62C42CE316D459CFA46612B7B156889B78C4972BF155546F804A02
```

### 47. `redstone_fcu_statement_of_accounts` (n=4, expected 2.2, 0.55)

- **Printed identity:** Redstone Federal Credit Union. Statement of Accounts / Member Number | Statement Closing Date; 220 Wynn Drive, Huntsville, AL 35893  800-234-1234 - www.redfcu.org; Federally insured by NCUA; ledger heads printed once at the top as Date | Eff. Date | Account Activity | Debits(-) | Credits(+) | Balance - the signs are printed INTO the column heads; share sections headed <SHARE NAME> - * * * nnn.
- **Oracle:** Per share the summary is emitted as a TRANSACTION-SHAPED ROW at the end of the section: mm-dd Previous Balance <amt>  Total Deposits <amt>  Total Withdrawals <amt>  mm-dd Closing Date ... New Balance <amt>. A running Balance on every row makes the sign recoverable arithmetically.
- **Nearest reader:** analysis/symitar.py (CU genre); no registered reader matched
- **Risks:** A reader looking for a summary BOX will never find one - the summary is a ledger row at the END of each section, so a head-only or top-anchored summary scan returns nothing. Amounts are unsigned and the Debits(-)/Credits(+) column position is the only printed sign evidence, which the flattened text collapses; recover sign from the balance delta. L-1 share sections keyed by * * * nnn. Sparse low-activity members are dominated by legal boilerplate.
- **Merged from:** s1(8659960717),s2,s8,s9
- **shas:**
```
0366FDF251AD0D3241DB1C07FC4029EFB4474CF348D3CDE6A95C2F0800B2553A
203E8D2EC4631B6867A7ADC78F6225FF47CCA2E1ABE2B1AAF3C2B8AE83CDEBEB
7CDCEE2B9BC2C5B79C948021D66750A3D5AAC3FD631498A3C3ADC0C62A0CD2B0
8659960717EE4AB1F6D4179E4795E3044EB5351F6D744B1AEF6E817DD71CAFF4
```

### 48. `security_service_fcu_asterisk_sections` (n=4, expected 2.2, 0.55)

- **Printed identity:** Security Service FCU. All-caps fixed-pitch print: STATEMENT PERIOD <acct> mm/dd/yy to mm/dd/yy Page n of m, a batch line and a security paragraph naming SECURITY SERVICE / SSFCU.ORG, machine footer BCID|FC|D|TA|SSFCU000|...; per account <PRODUCT NAME> <account number> over a two-column monospaced summary block; sections delimited by asterisk triples * * * DEPOSITS/CREDITS * * *, * * * ATM WITHDRAWALS/DEBIT PURCHASES * * *, * * * WITHDRAWALS/DEBITS * * *, * * * TOTAL OVERDRAFT FEES * * *.
- **Oracle:** Per account PREVIOUS BALANCE, SERVICE CHARGES, <n> DEBITS <total>, <n> CREDITS <total>, CURRENT DIVIDEND, NEW BALANCE, YTD DIVIDEND, DAYS IN PERIOD and ANNUAL PERCENTAGE YIELD EARNED, plus a four-cell period-and-YTD OD/NSF table - counts and totals on both directions.
- **Nearest reader:** analysis/secu.py (nearest per-CU registration, fired in near_miss), symitar.py as platform sibling
- **Risks:** No balance oracle of any kind - no daily grid, no running balance - so the per-account PREVIOUS/NEW pair plus the counts is all there is. Debits are split across TWO asterisk sections (ATM/debit purchases vs other withdrawals) and a reader keyed on only one silently drops the larger. Amounts print BEFORE the description and are unsigned. Section-to-account binding must follow the most recent product banner. L-1 with 2-3 shares.
- **Merged from:** s2,s4,s9,s10
- **shas:**
```
06F4CF26F0A73C716275A4050AD3499EE8E3EED438470DE5EF7231810BD74DC6
3DB81A2CEAFCEDCDCB82E0E7EEB3F6838D6275997A4FF071A66921126D92373D
740670FA2A9F47F2B58F0A176176FC9A6C6493D7B1351CBE15BF8D026A1B89C2
A7C6D1682504A2C33DEB8D31FBE038E23DD81E0414871F5C6991F63789E253CE
```

### 49. `capital_one_360` (n=6, expected 2.1, 0.35)

- **Printed identity:** Capital One 360 (direct-bank consumer/joint product, not the Spark business layout). Thanks for saving with Capital One 360 / Here's your bank statement. <Month YYYY>  STATEMENT PERIOD <Mon D> - <Mon D, YYYY>; TOTAL ENDING BALANCE IN ALL ACCOUNTS; paired headings Account Summary and Cashflow Summary; INTEREST EARNED THIS PERIOD; an ACCOUNT NAME | <first-of-period> | <last-of-period> grid closing on All Accounts; per account <product> - <full account number> over ANNUAL PERCENTAGE YIELD (APY) EARNED / YTD INTEREST AND BONUSES / DAYS IN STATEMENT CYCLE and the heads DATE | DESCRIPTION | CATEGORY | AMOUNT | BALANCE; footer capitalone.com 1-888-464-0727 P.O. Box 85123, Richmond, VA.
- **Oracle:** Weak: the account grid prints only opening and closing balance per account plus an All Accounts row. NO period deposit or withdrawal totals and no counts anywhere - the only oracle is Opening Balance -> Closing Balance across the running BALANCE chain, helped by a printed Category token (Debit/Credit) that carries direction independently of the sign.
- **Nearest reader:** analysis/capital_one.py (registered on the Fiserv Premier leading-counts Capital One layout - a different product line; near_miss capital_one 0.167)
- **Risks:** L-1 on every member (one checking plus two or three savings/sub-accounts, usually one posting and the rest dormant). Negative amounts and balances print the minus DETACHED before the dollar sign (- $161.31), which a naive money regex reads as positive. Rejected-withdrawal rows carry a balance but no amount and must count as zero, not as debits. Row dates carry no year.
- **Merged from:** s1,s2,s3,s4,s6,s7
- **shas:**
```
16605579044C7D97203204EF29D3288B54E032B7035C7E8BD00D256D8985CA4D
582B2EFAEED06E3F3EA443624455092EEC4C99A1C83B89E836E1F75F8E31F545
61ED1EA3AA891D93EC87116B278326411C4D0AD0DFB6C66A3D1B57A9B0D65F5D
C92D574C1E005223143D8F73E4BD5C4D220274CE8B9E332369B793BCB85C103D
D7FA68731422AC0C3059AA90C52053A3386EEE475BAB5EA40D106710A93449CC
F2BC8EED8E58C888D0C3D75EC556D0B463B776FBEE3FE1B908DE182E5933355D
```

### 50. `heritage_south_cu` (n=3, expected 2.1, 0.7)

- **Printed identity:** Heritage South Credit Union (Shelbyville TN). Member Statement / Account Number: XXXXXXnnnn / Statement Period: mm/dd/yyyy to mm/dd/yyyy / Page n of m / P.O. Box 1219, Shelbyville, TN 37162  P: 931-684-3596 | www.heritagesouth.org; ACCOUNT SUMMARY with Shares | Beginning Balance | Total Withdrawals | Total Deposits | Ending Balance one row per share; per share ID 0001 - <PRODUCT> with Dividends Paid YTD.
- **Oracle:** The ACCOUNT SUMMARY four-figure row per share, a per-share closing count line <n> Withdrawal(s) = -x  <n> Deposit(s) = x, a printed Average Daily Balance per share, and a running Balance bracketed by Beginning Balance and Ending Balance rows.
- **Nearest reader:** analysis/symitar.py, community_section.py
- **Risks:** L-1 with two active shares, so a single-account schema hits the multi-account decline unless both are carried. APY sentences are interleaved between ledger rows and must be skipped. The printed per-share ADB is directly usable evidence under the ADB doctrine.
- **Merged from:** s5(C61EFFEC),s7,s8(38717970)
- **shas:**
```
38717970EAED51B644A445152570BBF9D421D01C7CD7D78906551D62EDB5A9F7
5EF0F71F080F79731D698E46274FC3EBF284056C8AA19A19B10EFD7531D26671
C61EFFECCA18B37904861E21B1339DD141951F9FAD69814B56CC0FDD2418AE49
```

### 51. `hudson_valley_fcu` (n=3, expected 2.1, 0.7)

- **Printed identity:** Hudson Valley Credit Union. <Month YYYY> Statement of Accounts / Member Account Number / Reporting Activity mm/dd/yy - mm/dd/yy / Page n of m; Account Balances At A Glance with a Share Accounts | Balance | YTD Dividends Earned table and a Share Totals row; per share <PRODUCT> ID nnnn; footer Hudson Valley Federal Credit Union, Insured by the NCUA.
- **Oracle:** A four-figure printed row per share (Beginning Balance | Deposits | Withdrawals | Ending Balance) plus the Share Totals roll-up, a running Balance bracketed by Starting Balance and Ending Balance rows, and Total Overdraft / Non-Sufficient Fund Fees this period and YTD.
- **Nearest reader:** analysis/symitar.py (its documented dormant-sibling skip is exactly the situation here)
- **Risks:** The four summary cells and the four fee cells print as two adjacent numeric runs on one line, so the fee quartet can be mistaken for summary values. Withdrawal totals are printed already-negative. L-1 primary business savings (usually dormant, No Activity This Period) plus value business checking. Wire/ACH addenda (TYPE:/ID:/DATA:/CO:) wrap onto their own line.
- **Merged from:** s5,s6(5970FDF2),s7
- **shas:**
```
0C78E2F2FA203C14CC067DF7B7C063217F742CA02567E2A7BD717DB66C2046BA
5970FDF20E7CE9014F7BEE6C1E21FBB02A813310CDC247E33D59E2CA7A67F2E4
943CCA7B9C8BC2699080FA36DEA8380A1A69EA17C79E283AB26518C3E92D11FE
```

### 52. `community_savings_bc` (n=4, expected 2.0, 0.5)

- **Printed identity:** Community Savings Credit Union (BC), CAD. STATEMENT DATE 31Jan2026  ACCOUNT # nnnnnnn  PAGE n of m (day-Mon-year, no separators); Your Branch <name> ... www.comsavings.com with a named Branch Manager and direct email; Your Account Summary in TWO currency columns CDN | USD listing Chequing / Savings / Consolidated Balance / Total Deposits / Total Withdrawals / Deposits less withdrawals / Spending as a % of deposits / Total Investment(s) / Loan(s) and Mortgage(s); Your Transaction Summary and a Methods of Spending ($ Value) percentage block; a Legend for EX/OD flags.
- **Oracle:** Total Deposits and Total Withdrawals per currency column plus a Consolidated Balance, a Transaction Summary printing Debit Card Transactions / ATM Transactions / Total Member Initiated Transactions and a per-account Transaction Count: n, and a running Balance opened by a Balance Forward row.
- **Nearest reader:** none (no comsavings module); Canadian siblings analysis/desjardins.py, bmo_ca_business.py, rbc.py
- **Risks:** The dual-currency columns are the trap: every summary label carries TWO values and a reader that takes the first silently drops the USD side; the page itself prints Transaction summary excludes any USD accounts. Per-currency separation is mandatory under the currency doctrine, and here the currency is PRINTED, not inferred. L-1 chequing plus savings. No printed opening balance in the summary - the opening is only the Balance Forward ledger row.
- **Merged from:** s1,s3,s11
- **shas:**
```
49D2A1794375A94DA42A85FD2932AB8C6D7880BE2C35860FC9A18435B75555DC
7CFA22EDDFEF552D32B5A172CEE0D2607FE8EA4E8D7B4CE18A8EA819555CA8A6
BFD6167706794EBC0564C03738B45281A823CBB267093F4C3446D20588901C6C
D0A6F2DEA0D32264854DEDB9F24D31BAFA5D64B69F937E0908DB8310EAF2FF9C
```

### 53. `goldenwest_cu_member_account_statement` (n=4, expected 2.0, 0.5)

- **Printed identity:** Goldenwest Credit Union (Utah). A page-top machine line STMT<mm/dd/yyyy>000<member#><MEMBER NAME>; Member Account Statement / Member Number: | Statement Date: | Page: n of m; marketing naming gwcu.org; ACCOUNT SUMMARY as a two-across Account Name | Ending Balance table; per share a banner nn <SHARE NAME> (BUSINESS PRIMARY SHARE, BUSINESS GOLD ACCOUNT, SIMPLY FREE BUSINESS CHECKING, BUSINESS VISA DEBIT); recap tables WITHDRAWAL SUMMARY and DEPOSIT SUMMARY.
- **Oracle:** Per share a PREVIOUS BALANCE row, an Ending Balance row, count lines <n> Deposit(s) <total> / <n> Withdrawal(s) <total>, Dividends Earned Year-to-Date, and a running Balance; the two-across recap tables restate the per-share counts and totals.
- **Nearest reader:** analysis/symitar.py; no goldenwest module. One member probe-resolved out of shard-2 by the gwcu token.
- **Risks:** Every transaction is printed TWICE by design - once in the per-share running ledger and again in the WITHDRAWAL SUMMARY / DEPOSIT SUMMARY recap tables - so a reader that consumes both doubles every account's activity; parse the recaps for reconciliation only and exclude them from the transaction set. Row geometry is shifted: the amount and balance often precede the description on the following line. The ACCOUNT SUMMARY mixes a VISA DEBIT card account in with the shares and it must not be folded into deposit totals. L-1 four shares.
- **Merged from:** s4,s6,s8(201B3B3D),probe-resolved from s2
- **shas:**
```
201B3B3D5F597D28A0A45B9539CF3962F83D28B1DB5FF94BDDD777288363DCA1
5C6B0555BB0B625713DBA0372A5C283D4E0021A27F75D6A5E33586B5CF9FF259
A137F6D65E29CAD56EA17471F0354A300BEAE9E2EC6E7F7621E11FD3FB579F21
F443964447A44FC15312EA491EE6324DA7D7EFCAED8B27DA87DB8398C342D8DC
```

### 54. `novo_monthly_account_statement` (n=4, expected 2.0, 0.5)

- **Printed identity:** Novo (fintech) on a sponsor bank. Monthly Account Statement; Deposit account services provided by: then the SPONSOR bank in the masthead position (Middlesex Federal Savings, F.A., Member FDIC  1 College Avenue Somerville, MA 02144); Account Number XXXX nnnn  Statement Date <Mon DD, YYYY> thru <Mon DD, YYYY>; Customer Info; page footer Page n of m  Novo Platform Inc. (844) 260 - 6800.
- **Oracle:** A four-cell strip Starting Balance | Income | Expenses | Ending Balance - non-banking direction vocabulary and only four figures.
- **Nearest reader:** none (no novo module); nearest neobank readers analysis/mercury.py, relay.py, brex.py, bluevine.py, square_checking.py
- **Risks:** No running balance, no daily grid and no counts anywhere, so the four-figure identity is the ONLY closure - one dropped row is undetectable except through it. Each row spans two lines: <Mon DD> description Type on one line with the signed AMOUNT on the next, and the Type vocabulary (POS Withdrawal / External Withdrawal / Real Time Payment Deposit / EFT Credit) is the direction key. Row dates carry no year. Key on the Novo footer plus Deposit account services provided by:, never on the sponsor bank - Novo has changed partners.
- **Merged from:** s2,s6,s7,s12
- **shas:**
```
24755C040FDB95680DC86B57166E517FF5289058C77B59DBD042936E7DABE125
4D46C511184497A6F7955FBAA185B7EEBF271A9BE4E03F8E866F5CD92E48B119
C42941520EA612BB0141A63F2020B47D7A88D563932A8F5A5ECAAC94C11BBEDF
DF5CDF8F4B7AB6CF0D01CE39050E27EFDF6608AFB0473C9C7A88BF9CF90A3866
```

### 55. `palmetto_citizens_cu` (n=4, expected 2.0, 0.5)

- **Printed identity:** Palmetto Citizens Federal Credit Union. MEMBER NUMBER | STATEMENT DATE | PAGE # header band with PO Box 5846 - Columbia, SC 29250-5846  www.palmettocitizens.org; Account Balances at a Glance with Total Shares: / Total Certificates: / Total Loans:; Legal Title:; per share S 0100 SAVINGS PRIME SHARE and S 8100 CHECKING LOW VOLUME BUSINESS CHECKING with Begining Balance: (misspelled in the template), Ending Balance:, Dividend To Be Posted:, Dividend YTD:; ledger heads TRANSACTION DATE | TRANSACTION DESCRIPTION | DEBITS(-) | CREDITS(+) | NEW BALANCE opened by Previous Balance and closed by Closing Date...New Balance.
- **Oracle:** Weak: per share only Begining Balance and Ending Balance plus dividends, and a document-level Total Shares / Certificates / Loans that are balances not flows. The signed DEBITS(-)/CREDITS(+) amounts and the NEW BALANCE chain are the only reconciliation.
- **Nearest reader:** analysis/symitar.py (share-sectioned member statement; this issue prints no equation row)
- **Risks:** No period credit or debit totals and no counts, so totals must be summed from the ledger and can only be checked against opening -> closing. The template's own misspelling Begining Balance is a reliable literal marker and must be matched as printed. L-1 prime share plus business checking, the share usually dormant.
- **Merged from:** s3,s5,s7(EB165260),s10(9844A367)
- **shas:**
```
3B4FE87E8586A3BDF4527147B9138C30709432E6D2F012ACCC65FB3A55B9C25B
9844A367DC57A131E8CD11C2A86D2CA34E4FF9CC68277819BBE3B44F0E104224
E9DD69D7CCF4F1AF1931AE2F657A3DE009A6B2FD4339D939AF323C501B090B31
EB165260EA113EE61A69F817FFB3CC3F4ADB762AEA24751B6851DB9627DA87BA
```

### 56. `st_marys_bank_nh` (n=4, expected 2.0, 0.5)

- **Printed identity:** St. Mary's Bank (Manchester NH credit union). PO BOX 990 Manchester, NH 03105 with Page: n of m; Membership Account Number | Statement Period over ******nnnn  m/d/yy - m/d/yy; Statement Summary with the paired column heads Total Shares Balance and Total Loans Balance; Statement Detail <SHARE NAME> - nnnn; the institution is named only in the disclosure (write to us at St. Mary's Bank Deposit Operations P.O. Box 990) and at www.stmarysbank.com.
- **Oracle:** Thin: the Statement Summary lists share and loan names with balances plus two roll-up totals, and each share block prints Beginning Balance: / Ending Balance: / Dividends Paid YTD:. No credit/debit totals and no counts - the running Balance chain is the oracle.
- **Nearest reader:** analysis/symitar.py (identical TYPE:/ID:/DATA:/CO:/Entry Class Code: continuation grammar); one member probe-resolved out of shard-2.
- **Risks:** L-1: shares named by FUNCTION (PAYROLL, DEPOSITS/WITHDRAWALS, CUSTOMER OUTGOING) so product type cannot be inferred from the share name, plus a vehicle LOAN that must be excluded. In the Statement Summary the names and the balances are emitted in separate runs with no column labels, so that mapping is positional and fragile - the per-share Beginning/Ending lines are the reliable anchors. Ligature loss (fi/ft dropped: Quesons, Overdra) means literal markers must avoid those letter pairs. A separate Deposits and Other Credits recap can double-count against the detail table.
- **Merged from:** s4,s6,s11,probe-resolved from s2
- **shas:**
```
0D2F43222E8AB491B298468FC84781DAAE20E420895FB819A59CBC7A75BEE052
52E7045D5655B5C245DD4EBC763A16835F632E3FD6C82AC47880F674986F5FDD
C50FADE975E05745CC2A3B151A5877E0CDEC54B94F3BFD3F559056F1B7C46B18
FF5D613E0308F203836AFCEA157249CD1DB4E48D60DFCA8D975BA7E09135BB15
```

### 57. `pima_fcu_statement_of_account` (n=3, expected 1.95, 0.65)

- **Printed identity:** Pima Federal Credit Union (Tucson AZ). STATEMENT OF ACCOUNT over Statement <Month Year>  Page n of m  Account Number XXXXXXnnnn  Statement Period mm-dd-yyyy through mm-dd-yyyy; P.O. Box 50267, Tucson, AZ 85703; footer www.pimafederal.org Phone: 520.887.5010 Toll: 1.800.746.2328; Account Summary as <PRODUCT> <suffix> <balance> rows; per account Transactions for <PRODUCT>.
- **Oracle:** A five-label header row Beginning Balance | Deposits | YTD Dividends Earned | Withdrawals | Ending Balance with the five figures on a separate value row (positional zip), plus a running Balance bracketed by a Starting Balance row and an Ending Balance row.
- **Nearest reader:** analysis/symitar.py; secu.py and midflorida.py are comparable per-CU suffix readers
- **Risks:** L-1 business savings plus business checking (a zero-activity account prints No Activity This Period). Posting dates can go BACKWARD inside a ledger (a 01-31 row after the 02-01 Starting Balance), so date monotonicity cannot be assumed as a row filter. Withdrawal amounts carry a leading minus so signs are self-describing.
- **Merged from:** s4,s6(BAD84923),s8(32F2BA78)
- **shas:**
```
32F2BA7871C2FC2F385BD9E435E51AAA9C66C407D30EA7421528B1BFD627C5F7
42113E197C631D0889F79A63B2C4455E5C65FA629713DE3A78A785971350D29F
BAD849239ED62579CBC2F3F624F60780BDD30FB5EFE9E081ADF354B97CC022CF
```

### 58. `access_fcu_member_statement_of_account` (n=4, expected 1.8, 0.45)

- **Printed identity:** Access Federal Credit Union (NY). Member Statement of Account (315) 557-1000 | www.accessfcu.org repeated as a page header; Member Number + Statement Period; a member-level share roll-up (Your Share Balances as of / Your Account Summary as of) with Share Balance Total / Account Balance Total and Total Dividends Year-To-Date; per share <SHARE NAME> ID 00nn (e.g. BUSINESS SHARE DRAFT CHECKING ID 0061); the print-vendor control line n/m UNQ mm-dd-yy CLT; ledger heads Date | Transaction Description | Amount | Balance.
- **Oracle:** Weak-to-moderate: per share Beginning Balance and Ending Balance only (no credit/debit totals, no counts on most members), but a clean running Balance on every row and a share roll-up total.
- **Nearest reader:** analysis/symitar.py (genre); no access module. Probe-resolved out of shard-2 and shard-9 bundled vendor-core families by the accessfcu.org page header.
- **Risks:** L-1 multi-share. With no printed direction totals the balance chain is the only closure, so ACH continuation sublines (TYPE:/ID:/DATA:/CO:/NAME:/Entry Class Code:) and card-address sublines must be folded into the preceding row or rows will be dropped. Shares the UNQ-CLT vendor lineage with wpcu / trailing-minus / greenstate families - one descriptor tokenizer serves all of them.
- **Merged from:** probe-resolved from s1,s2,s9,s10
- **shas:**
```
A73014E132333CA45CCACCC29C77C4D5BF27EA9E91A18304C92DD33053A8C067
B53613DD7BFA3DEFAC422CB6AD56C3DDA0037D8DC5C10AB153E70AD582087409
BF4D9BCDF02835144AA6B6E6C8D903402AC1C69C0622C63F3A7751428F443A92
E9C75B967303B444EFC39D672252A85BF5018EA867A2A0CAB4CDFB857BE5693B
```

### 59. `atb_financial_consolidated_statement` (n=4, expected 1.8, 0.45)

- **Printed identity:** ATB Financial (Alberta), CAD. Consolidated Statement; Statement date <Month D, YYYY>  Transit number 0nnnn-nnn  Customer number 000nnnnnnn  Cheque images n  Page number n of m; Your ATB Financial Branch <transit> <branch>; contact us at 1 800 332-8383 or visit us at www.atb.com; A summary of your accounts on <date> split into Deposits and Loans with Total Deposits / Total Loans; per-account pages A summary of Deposit Account <product> beginning Your balance forward; ATB batch codes (ATB0114003_...) and a repeated Keep your credentials private paragraph.
- **Oracle:** Per account: Your balance forward on <date>, Debits to your account (52 items) - $x, Credits to your account (95 items) + $x, Your closing balance on <date> - item counts printed inside the labels - plus a running Balance column and the front-page Total Deposits / Total Loans.
- **Nearest reader:** analysis/atb.py EXISTS (near_miss atb 0.167) - this Consolidated Statement multi-account printing is the variant it misses; live against the open ATB escalation
- **Risks:** L-1: two deposit accounts plus one or two loan/revolving facilities under one customer number - loans must never be folded into deposit math, and one front-page total mixes a negative deposit balance in. The security paragraph is duplicated many times per page and must be collapsed. Negative balances print the minus DETACHED (- 53.09). CAD jurisdiction default applies.
- **Merged from:** s1,s8,s11
- **shas:**
```
284B775D64C9F1F9464E11C5894260C8B9BD03E44774AF0FC0EC20B5F96E35D5
745B2968DC5A01970F0E8DAE6D47AB54BCF79ECEBF3D3CBF6700198F15F62B0E
EE09ADA6FCD4637A9FE0208FD5598B4861DA009082289CCBC3EF4FDA3E9DDE69
F1DA262D1C28D1AB6BA8E82EEA2BCDA4D51848CE599B11C90F668360F859915D
```

### 60. `bank_of_tennessee_activity_summary` (n=4, expected 1.8, 0.45)

- **Printed identity:** Bank of Tennessee. P.O. BOX 4980 JOHNSON CITY, TN 37602-4980 with the We're here to help / Customer Care: 866.378.9500 / Fingertip Banking: 866.965.2265 / Online: bankoftennessee.com panel; a full Important Information marketing page and a THIS FORM IS PROVIDED TO HELP YOU RECONCILE YOUR ACCOUNT worksheet before any figures; Activity Summary beside Account Summary; ledger banner Transaction History with heads printed one per line ending in Ending Daily Balance; Check Summary with Indicates skip in check numbers.
- **Oracle:** Beginning balance on m/d/yy, Deposits/Additions, Withdrawals/Subtractions, Service charges, Ending balance on m/d/yy, plus Average balance / Average collected balance / Minimum balance, and an Ending Daily Balance printed on the LAST row of each posting day (a daily closing series embedded in the ledger).
- **Nearest reader:** none (no bank_of_tennessee module); analysis/core_processor_daily.py is the nearest additions/subtractions dialect
- **Risks:** Direction is the blocker: amounts are emitted bare on their own lines after the description with no column marker, so a deposit and a withdrawal are textually indistinguishable and multi-transaction days cannot be resolved without geometry. The day-terminal balance resolves single-transaction days only. The summary does not appear until page 3 behind marketing and a reconcile worksheet, so head-only detection misses it.
- **Merged from:** s2,s7,s8,s10
- **shas:**
```
68ABA4BC07F2C1623B583FE570DE761E3515159B925114CD2B55496CA315330F
6A96F8DA638799BC02D539EF1E13BF9F719837CB231F7D4012D11DE36A4AA99C
9B1671E016220E587F29D84DCB749E64420D688B8F19F2CB558409A25C7892D8
B50EDDCD909A40A951E57E627CD962A65DDA2E9980AC66DBD534F7C7811C162C
```

### 61. `vystar_business_checking_analyzed` (n=4, expected 1.8, 0.45)

- **Printed identity:** VyStar Credit Union, BUSINESS CHECKING ANALYZED product - a second, unrelated VyStar template to vystar_balance_summary_transactional_detail. Statement Period <Month D, YYYY> - <Month D, YYYY> as the first line; <CUSTOMER> Business Checking Account: XXXXnnnn; a CUSTOMER SERVICE INFORMATION block (Direct Inquiries: (904) 777-6000 / Website: www.vystarcu.org / Mail: P.O. Box 45085 Jacksonville, FL); a full-page product marketing list; product banner BUSINESS CHECKING ANALYZED; ledger banner DAILY ACTIVITY with a column literally headed Running Balance.
- **Oracle:** Beginning Balance, Deposits/Credits, Withdrawals/Debits, Ending Balance, plus a per-row Running Balance seeded by a Beginning Balance row.
- **Nearest reader:** none matched; analysis/symitar.py and midflorida.py are the nearest CU readers
- **Risks:** PROVENANCE FLAG raised independently by three shards: every description is printed TRUNCATED with a trailing ellipsis (ACH CREDIT - Payment for Bulk Cotton Supply...), the figures are unusually round, and the layout matches no other VyStar printing - counterparty text is lost at source, so description attribution is impossible and authenticity should be decided before reader work. Amounts are unsigned in two adjacent columns; direction is only recoverable from the running-balance delta.
- **Merged from:** s2,s5,s10,s12
- **shas:**
```
2C9C57112D0F2FAB8AF64513C7328DD68AD58C7F324AE9340ABDB2ABBC61E7A6
3EF898B20DCED0BC97C84728B96F07DDEEF67BBCD3D9786CB669BEA95E30BD8B
9D19277503AB705EED69CFFBE03968A2BCBE87F756468E0D14E18374660D0B40
B259126FE7FAACB7F199DFC7F890C8C79DBF007071772543F876DFA373BBEF33
```

### 62. `bangor_savings_three_count_summary` (n=3, expected 1.8, 0.6)

- **Printed identity:** Bangor Savings Bank. Statement Date: / Account Number: / Page: three-up header with a Bangor Support notice (please contact Bangor Support at 1.877.226.4671); Summary of Accounts (Account Number | Account Title | Current Balance | Enclosures); <PRODUCT> Summary with Account Number / Truncated Items / Previous Balance / Statement Dates m/dd/yy thru m/dd/yy; an Overdraft Fees period-vs-YTD box; sections Deposits and Other Credits with Date | Description | Amount | Reference; footer MEMBER FDIC www.bangor.com.
- **Oracle:** Same core-processor vocabulary as core_enclosures but with the debit side partitioned THREE ways: <n> Deposits/Credits, <n> Withdrawals AND <n> Checks, each counted, plus Service Charges, Interest Paid, Average Ledger, Average Collected, Days In This Statement Period, Previous Balance and Current Balance. The balance identity is b0 + credits - withdrawals - checks - service = b1.
- **Nearest reader:** analysis/farmers_merchants.py / core_processor_sectioned.py / core_processor_counted.py (same platform, different summary partition)
- **Risks:** Kept out of core_enclosures precisely because of the three-way debit partition - a two-bucket reader mis-totals every member. No daily-balance grid found in any member. Card-detail descriptors wrap and push the amount onto the following line.
- **Merged from:** s1(19E3AE59),s3,s7
- **shas:**
```
19E3AE590011C0365EB7D5AF9B7D1D9A4EE1E952E2AF90F177F25CD9F776BE74
2ECD7C8C3035BC45635AFD0D24149F997788346C8A5552322F09D69733A05A9F
E0805CCD1DCC5A59402D18642789392E64F1CADC75AC50AD844D1C39E92A0ADB
```

### 63. `champion_cu_statement_summary` (n=3, expected 1.8, 0.6)

- **Printed identity:** Champion Credit Union (Canton NC). (828) 648-1515 www.championcu.com PO Box 1389 Canton, NC 28716; a Tray2 NotPerfed-nnnnn print token; Statement Summary / STATEMENT SUMMARY over Deposit Accounts TOTAL BALANCE: $x and the table Account Type | Previous Balance | Deposits | Withdrawals | Ending Balance; per account <PRODUCT> (#nnnn) with PREVIOUS BALANCE: / YTD Dividends: / NEW BALANCE:; ledger heads Tran Date | Description | Deposits | Withdrawals | Balance.
- **Oracle:** A four-figure printed row per account in the statement-level table plus per-account PREVIOUS BALANCE / NEW BALANCE bookends and a running Balance opened by a Previous Balance row.
- **Nearest reader:** analysis/symitar.py; no champion module. One member probe-resolved out of shard-2 by the championcu.com masthead.
- **Risks:** No counts. L-1 multi-share, and the deposits/withdrawals column ORDER flips between sibling printings of this core, so bind columns from the printed header row rather than positionally. Consumer reconciliation boilerplate sits on page 2 between ledger pages. Note shard-10 also carried a Champion CU Transaction History RANGE EXPORT (54BA73ED) which is correctly filed as not-a-statement.
- **Merged from:** s5(D2357D69),s6(0208F10F),probe-resolved from s2
- **shas:**
```
0208F10F797B1743DE43E380AC725CEC6BF7F0D0D925F6FBFCCB15F52E7C89BB
7487DA2E68EC313490A44A963D66833D6E2F5EA7748AF12B9A3487ED7F9D2894
D2357D69622CFE404722DDE77FC5B49EBE4C807F509C04F2865C61EF84AAAD03
```

### 64. `mt_bank_customer_statement_treasury` (n=3, expected 1.65, 0.55)

- **Printed identity:** M&T Bank, Customer Statement (treasury/relationship) issue. Customer Statement for the Period mm/dd/yy - mm/dd/yy; P.O. Box 767, Buffalo, NY 14240-0767; Treasury Management Service Team; mtb.com / mtb.com/locations; Here's a quick glance at your account on this statement: Statement Summary (Account Number | Ending Balance) naming the product (M&T ADVANCED BUSINESS CHECKING / BUSINESS PLUS CHECKING); interior pages carry THIS PAGE HAS BEEN INTENTIONALLY LEFT BLANK. and a rotated sidebar that reaches the text layer as the fragment Deposits & Checks & Daily.
- **Oracle:** An Account Summary block (Beginning Balance: / (+) Deposits & Other Credits / (+) Checks & <N> Other Debits / (+) Service Charges / Ending Balance:), a bare two-number count row NUMBER OF DEPOSITS/CHECKS PAID  10  30, a front Statement Summary with the ending balance and Total Deposits, and a running Balance opened by Beginning Balance and closed by Ending Balance:.
- **Nearest reader:** none (no mt/mtb module)
- **Risks:** The text layer is heavily out of reading order - page 1 summary, a blank page, the activity, and THEN the Account Summary block and its column headers emitted after their own table - so a reader must key on labels and never on position. The two counts arrive as a bare pair with no labels attached.
- **Merged from:** s3,s11
- **shas:**
```
35088A1B458FD1FF8BF25C09FF776290B7E195B7DBD2B562F276B14A4B32C1A0
9195C49BCE4EEB29A06C86CA7E54F1A32C56CB7FA07A2513E0FA6EF8DE340EA5
A0894D5A0B716D568252AF673B26D64C261447D1A30873E3C25B44D8817F7C14
```

### 65. `becu_deposit_and_loan_activity` (n=4, expected 1.6, 0.4)

- **Printed identity:** BECU (Seattle), identifiable only from the dispute address - masthead is image-only. Statement Period: mm/dd/yyyy - mm/dd/yyyy; Summary of Deposit Account Activity (Account # | Beginning Balance | Withdrawals/Fees* | Deposits | Dividends/Interest | Ending Balance); *Including the following Fees with Statement Period Total | <YYYY> Year-to-Date Total for Overdraft and Non-sufficient Funds (NSF) Fees; a separate Summary of Loan Account Activity grid; Deposit Account Activity with a per-account APY line printing Average Daily Balance: $x and Year-to-date dividends; dispute address Research and Adjustments-Account Dispute, P.O. Box 97050, Seattle WA 98124-9750.
- **Oracle:** A five-figure printed row per deposit account (beginning, withdrawals/fees as a parenthesised negative, deposits, dividends/interest, ending), plus a printed per-account AVERAGE DAILY BALANCE that is a free check on the canonical ADB metric.
- **Nearest reader:** none (no becu module); analysis/symitar.py solves the same loan/deposit split for its platform
- **Risks:** No daily grid and no running balance. Labels and numbers are emitted in separate runs with the account numbers interleaved between them, so pairing is positional and fragile. Inter-word spacing is lost inside descriptions (ExternalDepositINTUIT80501433-DEPOSIT), breaking any description tokenizer or whitespace row-split. The Deposits section CONTAINS withdrawal rows (External Withdrawal ... (Rejected)), so section-derived signing produces wrong totals - take direction from the descriptor verb. The vehicle-loan grid must be excluded from deposit math.
- **Merged from:** s3,s6,s11
- **shas:**
```
039BE1BED484095262D3EDDB46391A54274468B14AC0F50CDA879E8207628E09
77800C8DCB55210886771ACD312E4C4AA78F668E598CA782760ACA3BF298BEC0
9494F27ED35BE2E9315A0AE3DEE0DB71B24FABA36709E536DCDE9F5327908143
F3350960AD73AFFC058263B599B76254C1D6EEB9128B5A8A22F3D29122FDC45E
```

### 66. `beem_credit_union_bc` (n=5, expected 1.5, 0.3)

- **Printed identity:** Beem Credit Union (British Columbia), CAD. MEMBER NUMBER / STATEMENT PERIOD / CONTACT US: beemcreditunion.ca 1-855-336-2336; ACCOUNT(S) SUMMARY by Category with ACCOUNT NAME | DEPOSITS | LOANS and a TOTALS row; DETAILS blocks headed ACCOUNT NAME: / ACCOUNT NUMBER: / OWNER(S):; footer naming BlueShore Financial, GFCU Savings, Gulf & Fraser, Interior Savings and North Peace Savings as trade names.
- **Oracle:** Weak: a category balance roll-up with TOTALS, a Balance Forward opening row, and on some members a per-section TOTALS: row carrying total withdrawals, total deposits and the closing balance. No labelled beginning/ending pair and no counts.
- **Nearest reader:** none; Canadian siblings analysis/desjardins.py, rbc.py, cibc.py, bmo_ca_business.py
- **Risks:** Balances carry a two-letter status suffix (DR overdrawn, EX credit-limit exceeded) that inverts meaning if stripped as noise. On at least one member the printed running balance moves the WRONG way for the column the amount sits in, so column position cannot be trusted for sign without resolving the transposition. L-1 with a line-of-credit block that prints OVERDRAFT EXCESS RATE / LINE OF CREDIT LIMIT / TOTAL DUE instead of a deposit summary and must be skipped. CAD jurisdiction default applies.
- **Merged from:** s8,s9,s10,s11,s12
- **shas:**
```
16F3C31E9C7571500DA460FE5896287AAD43123E2E9A68FA63DB092C573A5E0D
23FDA98BD99EBB1DAFB922D154DB062CA26881AF4366DC07496864F9D5F78319
2C948423B1204168C289809A74C273631E89F3328ECEE9A93B82407BF53D32C1
9979AEBF6A38BB06DBC50555FD7E370D49431A54672BE044058D22C1F3ECBF61
FAD1CB6320180E484DC80FF11762C2780D29A79EE3D177EE7BCE04E09258068E
```

### 67. `mt_bank_account_activity_daily_balance` (n=3, expected 1.5, 0.5)

- **Printed identity:** M&T Bank, branch-inquiry issue. FOR INQUIRIES CALL: <BRANCH NAME> (<phone>); ACCOUNT TYPE over the product line M&T ADVANCED BUSINESS CHECKING / M&T SIMPLE CHECKING FOR BUSINESS; ACCOUNT NUMBER | STATEMENT PERIOD over <n> | mm/dd/yy - mm/dd/yy; section banner ACCOUNT ACTIVITY with the stacked heads POSTING DATE | TRANSACTION DESCRIPTION | DEPOSITS & OTHER CREDITS (+) | WITHDRAWALS & OTHER DEBITS (-) | DAILY BALANCE; NON-M&T ATM FEE as a house descriptor.
- **Oracle:** BEGINNING BALANCE, DEPOSITS & CREDITS, LESS CHECKS & DEBITS, LESS SERVICE CHARGES, ENDING BALANCE, plus a DAILY BALANCE column populated on the LAST row of each posting date - a daily closing series embedded in the ledger that lets a reader validate each day's rows as a group.
- **Nearest reader:** none (no mt/mtb module); analysis/citizens.py / huntington.py are the nearest regional readers
- **Risks:** Two logical transactions frequently share one physical line and the two are in OPPOSITE directions (the first belongs to the credits column, the second to the debits column) with no separator character to split on - direction is encoded purely in within-line position. Negative closing balances print in accounting PARENTHESES, a convention no other family here uses. The (+) and (-) markers are emitted on separate lines from their labels.
- **Merged from:** s4,s7,s9
- **shas:**
```
53DF0008FCEB9C152D83AB5AD115A4B087E801A7354DEB60CDAD69289F313877
7FA2051357EDDB37051CCDABC2C5737B6F3216AA5CB42727CC8B0E33446A322A
F40D49B89E1E5D3B81A2CC061E43D070F2F04A2E8BA1FA0C3C27DDD97C51F6C4
```

### 68. `fulton_bank_account_statement` (n=4, expected 1.4, 0.35)

- **Printed identity:** Fulton Bank, N.A. Account Statement over Deposit Support PM P.O. Box 4887 Lancaster, PA 17604; Statement Date: mm/dd/yy through mm/dd/yy; Primary Account: XXXXnnnn; Customer Service at 800.385.8664; product banner BUSINESS CHECKING Account XXXXnnnn; footers DEPSTMT Deposit Statement Rev. 04/01/2025 / fultonbank.com / Fulton Bank, N.A. Member FDIC; a full-page RECONCILEMENT FORM.
- **Oracle:** Four clean printed figures - Prior Statement Balance, Total Deposits/Credits, Total Checks/Debits, Ending Statement Balance - plus Average Collected / Average Ledger / Minimum Ledger Balance and period-vs-YTD overdraft and NSF totals.
- **Nearest reader:** none (no fulton module); DEPSTMT Deposit Statement Rev. and Deposit Support PM are unique detection tokens
- **Risks:** The summary labels and the four figures print as two separate runs and on at least one member in a DIFFERENT order, so pairing needs the printed grid geometry, not reading order. The Account Activity table is emitted column-wise: one transaction arrives as three to five lines with the two amount columns and the balance interleaved and the minus landing on the wrong token, so row order alone is unsafe. The RECONCILEMENT FORM repeats balance vocabulary and must be scoped out.
- **Merged from:** s1,s2,s3,s4
- **shas:**
```
34DCE89546A40CF56451CA041659ED4320BD981139395F320617912D500D2DFF
3CC3DB128BADFFB6F7F480578B7AEB9EFC5E928A69F6FC7595569CC8C32BBBE2
76549EE4389F64FCC302C1BF25B3B2FACE41502E50785C7E8A1CC330B8999AB1
83170CCE7832364EBDC3285F9596CD927C5A7023FE121307841689B969A53E42
```

### 69. `firstbank_colorado` (n=2, expected 1.4, 0.7)

- **Printed identity:** FirstBank (Colorado). PAGE 1  24-Hour Customer Service: 303-237-5000 or 800-964-3444 outside Denver Metro  New Account or Loan: 303-238-9000  www.efirstbank.com; FIRSTBANK  PO BOX 150097 LAKEWOOD CO 80215-0097; ACCOUNT NUMBER XXX-XXX-nnnn; STATEMENT DATE m-dd-yyyy; INTEREST EARNED THIS YEAR; ACCOUNT SUMMARY - - CHECKING ACCOUNT - SAFEKEEPING with dot-leader rows; sections CHECKS AND OTHER WITHDRAWALS / ELECTRONIC AND MISCELLANEOUS WITHDRAWALS / DEPOSITS AND OTHER ADDITIONS with the dot-leader head DATE..........AMOUNT..DESCRIPTION.................CARD NBR.
- **Oracle:** Dated opening and closing balances, both counted totals with TRAILING +/- signs (2 DEPOSITS AND OTHER ADDITIONS TOTALING 563.73+ / 10 CHECKS AND OTHER WITHDRAWALS TOTALING 428.89-), and a dated MINIMUM BALANCE OF x ON <date>.
- **Nearest reader:** none (no firstbank module); analysis/zions.py / us_bank.py are the nearest western readers
- **Risks:** Dot leaders run straight into the figures and the sign TRAILS the amount, so both must be handled. On one member the four amounts and two counts arrive on ONE line BEFORE any of their labels, so binding is positional. Dates print as 4 - 22 with spaces around the hyphen and the amount precedes the description. No daily grid.
- **Merged from:** s7,s9
- **shas:**
```
4577474CBE35E5CD8D4EB3D145542001997E5D2F21771586E2FBDB28F65BD48C
733E522E4C221ED9C52012754C682D6C332F93949521C658D8C7DE6C93A84F87
```

### 70. `firstbank_pr_escrow_pipe_header` (n=2, expected 1.4, 0.7)

- **Printed identity:** FirstBank Puerto Rico, pipe-header issue - structurally distinct from pr_business_plus_corp_statement_of_account. A pipe-delimited control line 20260201|FBPR|DD006604001943|DDAPUERTORICO|<name>||nnnnn|nnnn; After Five Days Return To: PO Box 9146 San Juan PR; STATEMENT OF ACCOUNT / STATEMENT DATE; product line 018-ESCROW ACCOUNT; OCR routing blocks of capital letters; sections CHECKING ACCOUNT TRANSACTIONS / DEPOSITS AND OTHER CREDITS / CHECKS / OTHER DEBITS with dot-leader heads and * * * DAILY BALANCE INFORMATION * * *; bilingual trailer THIS STATEMENT IS NOT ... A COLLECTION EFFORT / ESTE ESTADO NO ES ... UNA GESTION DE COBRO.
- **Oracle:** BEGINNING BALANCE, DEPOSITS/OTHER CREDITS with an explicit NUMBER column beside AMOUNT CREDITED, CHECKS/OTHER DEBITS with NUMBER and AMOUNT DEBITED, SERVICE CHARGES and ENDING BALANCE - six labels printed first and six values in a run afterwards - plus a DAILY BALANCE INFORMATION grid keyed by date.
- **Nearest reader:** analysis/banco_popular.py (the other Puerto Rico family); core_processor_sectioned.py / core_processor_daily.py as structural siblings
- **Risks:** The label-run-then-value-run layout means six labels must be zipped to six values positionally, and the OCR routing blocks (long runs of capitals) must be discarded before that zip. One member is checks-only, so a general reader must handle a document with no narrative transaction section. Balances in the grid carry a trailing D indicator.
- **Merged from:** s1,s9
- **shas:**
```
3F4139243F9C2F5A1135EECD863A1EE340C67262864DB095289C9DE437675CF8
E31B7B02B7EC5866841204733982AB420AA2DA87BF502D8675F420B8898C2521
```

### 71. `greenstate_cu_post_eff_type` (n=3, expected 1.35, 0.45)

- **Printed identity:** GreenState Credit Union (Iowa). STATEMENT OF ACCOUNT / MEMBER NO. | DATE | PAGE and a <CU> Account Statement Member Number: header; P.O. Box 800 / www.GreenState.org; a member-level share roll-up; per share <SHARE NAME> with an ID/suffix; ledger heads POST DATE | EFF. DATE | TYPE | DESCRIPTION | AMOUNT | BALANCE - the four-token date/type prefix is the distinguishing furniture.
- **Oracle:** Thin: Balance Forward and Ending Balance rows per share plus the roll-up; on some members an Activity Summary of Previous Balance / Deposits / Withdrawals / Ending Balance. A running Balance on every row.
- **Nearest reader:** analysis/symitar.py; no greenstate module. Probe-resolved out of shard-1, shard-2 and shard-3 bundled families by the www.GreenState.org masthead.
- **Risks:** One member prints NO credit/debit totals at all - only Balance Forward and Ending Balance - so the chain is the sole oracle. L-1 multi-share. Same UNQ-CLT vendor descriptor grammar as access_fcu / wpcu.
- **Merged from:** probe-resolved from s1,s2,s3
- **shas:**
```
279BD8E5E83DFDA02FB4D894C8E66A201ABC06A9AF3DDD2840325CFB60A36824
76AB6D1AC341538A59E1A3CEC5A2C4ED5874F1B840A048968979F5F380C3DB05
7BAEC76ABE889B76C2E013ED3B834B6CFD1CC717D5DBAF370633DAAABD51CAE1
```

### 72. `umb_essential_business_checking` (n=2, expected 1.1, 0.55)

- **Printed identity:** UMB Bank (inferred): the institution never prints in the text layer - identity is a Kansas City MO mailstop (Mailstop 1170103D P.O. Box 419226 Kansas City, MO 64141-6226) plus the TUMBDS batch prefix in the OCR scan-line blocks. Statement Period Start: / Statement Period End: / Page 1 of N; a literal BlogStatement divider; product line ESSENTIAL BUSINESS CHECKING Account Number: and Account Title(s):.
- **Oracle:** Account Summary with Beginning Balance as of mm/dd/yyyy, + Deposits and Credits (16), - Withdrawals and Debits (107), - Service Charges and Fees, Ending Balance as of mm/dd/yyyy - PARENTHESISED counts inline in the labels - plus Total Days in Statement Period.
- **Nearest reader:** none; analysis/core_processor_counted.py is the nearest counted-summary shape. Shares the OMR/job-code statement-vendor furniture with townebank_balance_summary.
- **Risks:** No balance column and no daily grid. The Deposits and Withdrawals money columns are not separately delimited in the text layer, so column discrimination is positional only and the printed counts are the sole validation of whatever split rule is chosen. Descriptions are fixed-width card-descriptor blobs.
- **Merged from:** s10(8ABEE7F3 of vendor_balance_summary_as_of),s11
- **shas:**
```
8ABEE7F32EC600787EBB9005609C330F0BDF1FBE237944B0EEDEA4A1AED34172
F8E3E2E9F78F76E8C04CCB59DADE7C67259FAEB18038E4B0F9FE389259363C92
```

### 73. `synovus_pinnacle_portal_statement_view` (n=4, expected 1.0, 0.25)

- **Printed identity:** Synovus / Pinnacle online-banking STATEMENT VIEW printed from the browser - kept in families rather than exports because it carries statement-grade summary totals and both signed sections. Page chrome captured as the first three lines Sign Off / Documents / Statement Search; then <CUSTOMER> <account>-mm/dd/yyyy, the issuer line PINNACLE (TN) DBA SYNOVUS BANK, the product line Pro Business Checking ID nnn-nnn-nnn-n; sections Other Debits / Other Debits Transactions and Deposits/ Other Credits / Deposits/ Other Credits Transactions with heads Date  Amount  Description; a Balance Summary block on some members.
- **Oracle:** Beginning Balance, Ending Balance, Debits, Credits, Low Balance, Avg Balance, Avg Collected Balance - all printed, but the LABELS TRAIL their values and two of the four principal figures share a label run, so binding is positional. No counts, no running balance; the Balance Summary grid samples only some dates.
- **Nearest reader:** none (no synovus/pinnacle module); near_miss pnc 0.25 / capital_one 0.167 is noise
- **Risks:** PROVENANCE: on one member the Deposits/Other Credits section reproduces the same rows as the debit section with only the card suffix changed, so the two sections are not independent and the ledger is suspect; another prints a malformed amount (,1000.00). The browser-print artifacts are the cheapest detection token but also the sign that this is a screen capture rather than a bank-issued statement. Recommend a provenance decision before reader work; treat the summary as the only usable surface.
- **Merged from:** s2,s8,s10(sg),s12(sg)
- **shas:**
```
5067B6B76C38CE3162B00596F20998644D68CB260EA68E36B0DCC2665E570201
515F0ADF0A5C3E67D4476BF66A2CAE731C827CD15EF87571031BE483BF51F127
F56CDBB3CCBBB8CAEDBB23D5E1DCDD21C8917A48C54FF2283A472718E6F50BDB
FAE6050A8F81831DE10689D0A751235CDD18B2B7C5EF3E210E12C8F674C5C9F5
```

### 74. `wisely_adp_paycard` (n=4, expected 1.0, 0.25)

- **Printed identity:** ADP Wisely prepaid PAYROLL CARD, issued through Fifth Third. P.O. Box 9008 San Dimas, CA 91773; Customer Service: 1-866-313-9029; Card Number: XXXX-XXXX-XXXX-nnnn; Period Start Date / Period End Date; info.mywisely.com/direct; Attention: Cardholder Services; sections Summary of Transactions, Summary of Fees, Account Transaction Activity (Date | Reference ID | Description | Credit | Debit).
- **Oracle:** Previous Balance, (+) Credits & Adjustments, (-) Purchases & Adjustments, New Balance printed as four labels followed by four figures, plus Fees for Current Statement and Year-to-Date Fees.
- **Nearest reader:** analysis/fifth_third.py is the issuing bank but not this layout; no prepaid/paycard reader exists in analysis/
- **Risks:** POLICY, not parsing: this is a stored-value payroll card with a card-number identity, no bank name, no account or routing number - two of the four shards filed it as not-a-statement and two as a family. It is mechanically readable (clean one-row-per-line ledger, signed amounts, long-form month dates with no year) but whether a paycard belongs in cash-flow analysis is a Gustavo call. No running balance and no daily grid.
- **Merged from:** s1(ns),s3,s5(ns),s9
- **shas:**
```
135362861CBF9616956C100F3E78C93EC38AD944BB6485D05A397D4B8A0B458D
24B2C6FC3B5674E9A51AA258269BFC32EEEE5162F1A89E5E2E5B4523F64B4ECE
594E4BA83342859EAF5E3D4B14E8A092ADEC79B2C713FA3B66651334D94B107C
F69247AE6F5DA7A92A3296AD95BCD65830E01290A8A015F5BE512EE15A985AB3
```

### 75. `ramp_business_account` (n=1, expected 0.85, 0.85)

- **Printed identity:** Ramp business account (deposits at First Internet Bank of Indiana). A six-label header grid Interest rate | Account ID | Account number | Statement start | Statement end over 2.00% | rba_<hex> | ....nnnn | <Mon D, YYYY> | <Mon D, YYYY>; product line Checking Account; per-page footer Checking Account statement generated by Ramp. All dates are displayed in Eastern Time. Page n of m; Interest From First Internet Bank of Indiana.
- **Oracle:** Starting balance, Total outflows, Total inflows, Interest paid*, Final balance - five printed signed figures - plus a per-row running Balance that chains.
- **Nearest reader:** none (no ramp module); analysis/brex.py and mercury.py are the nearest corporate-fintech readers
- **Risks:** The cleanest document in the census: one row per line, mm/dd/yy dates, signed amounts, chaining balance. Only mechanical notes are the bullet mask characters in the account number and the rba_ account-id prefix as the detection token. Single document, so the template is evidenced once.
- **Merged from:** s12
- **shas:**
```
B988C19C86AE595E6469BB6AA0CD57121BA69A3980E142918E27E82F525D107C
```

### 76. `psecu_shares_at_a_glance` (n=4, expected 0.8, 0.2)

- **Printed identity:** PSECU (Pennsylvania State Employees Credit Union); named only in the error-resolution boilerplate and psecu.com. Member Number: nnnn******; Statement Period: mm/dd/yy to mm/dd/yy; the print-control token ~~~PAGE1~~~ and Page Number: Regular n of m; Account Balances at a Glance with Total Shares: / Total Certificates: / Total Loans:; Description YEAR TO DATE INFORMATION / Total Dividends Year to Date; section SHARES with share banners REGULAR SHARE ID 0001 and CHECKING ID 0002; a BALANCING WORKSHEET page.
- **Oracle:** Very weak: Total Shares / Certificates / Loans plus per-share Beginning Balance and Ending Balance rows and a YTD dividend line. No credit or debit totals, no counts.
- **Nearest reader:** analysis/symitar.py (grammar is close but PSECU's core prints its own column order)
- **Risks:** The worst column scrambling in the census: the declared head is Date Posting | Transaction Description | Effective | New Balance | Transaction Date | Amount but the emitted order is <new balance> <mm/dd> <signed amount> with the description on the PRECEDING line, and several transactions merge onto one line. Recovery needs a balance-date-amount triple regex plus previous-line description capture, or geometry. The BALANCING WORKSHEET must be excluded. L-1 two shares.
- **Merged from:** s6,s7(35B503DD),s8,s10(9814E42F)
- **shas:**
```
2D1B80B92D720B02BFD08C173827FA2D01E46A41353B4CF928EE155E4F8320E2
35B503DD81B6C4897D6E02E5B167CE411816CDE9D1B5162B9EFF1A282ABDC53E
5A40F2B44C7AFDCAB6ACFD85B3D2C148F332CCF0B4E8BB138B8D6535F89C486A
9814E42F9CDF89CB9161134D495A1581203B1D58FDBD96A702D3C66EE9A7E960
```

### 77. `pr_business_plus_corp_statement_of_account` (n=5, expected 0.75, 0.15)

- **Printed identity:** A Puerto Rico STATEMENT OF ACCOUNT printing. After Five Days Return To: PO Box 9146 SSan Juan PR 00908-0146 (the doubled S is printed); a mailer control string of the form FFBPRRnnnnnnnnnnnnR; product tag 020-BUSINESS PLUS CORP; a single header row BEGINNING BALANCE | DEPOSITS | CHECKS | SERVICE CHARGERS | ENDING BALANCE (the misspelling CHARGERS is printed) over a bare value row; sections CHECKING ACCOUNT TRANSACTIONS / DEPOSITS AND OTHER CREDITS / OTHER DEBITS with dot-leader heads DATE ... AMOUNT ... DESCRIPTION.
- **Oracle:** Broken: the DEPOSITS and CHECKS cells of the summary row hold COUNTS where the labels promise amounts, so no credit or debit total is printed at all; only beginning balance, ending balance and a service-charge figure. Some printings add a DAILY BALANCE INFORMATION grid.
- **Nearest reader:** analysis/banco_popular.py is the registered Puerto Rico reader (different bank, same market conventions); core_processor_daily.py for the daily-grid grammar
- **Risks:** PROVENANCE FLAG, not a parsing problem: three independent shards reported that the printed ending balance does not follow from the beginning balance plus the listed activity, the header misspells CHARGERS, the addressee line doubles the S in San Juan, amounts are uniformly round and descriptions are bare single merchant words. Recommend an authenticity decision before any reader work; structurally it would be cheap to read.
- **Merged from:** s2,s3(sg),s7(sg),s8
- **shas:**
```
41EAFACAA0FCDF49B40EF7ED53FE0FB30718506F532D3F726BAF8A4B8C6D293B
53553C788ADB50FB345A9E80CB01B13A521C7CB4DDC391575463B82BBC6D8B8A
650A062450352B3B29320F347DD88F43EC656FBC1AE347778B65D70DAC90DF1C
95D41C76FAA009D25ABE6B6B74ED1B9C786F31C6D7F9F570BEB734C7C3B6BBC6
C3624E68DB6E892437657CBCDBA9CEB42806BC135959579673FE2E807AD84FD5
```

### 78. `ion_bank_customer_statement` (n=4, expected 0.6, 0.15)

- **Printed identity:** Ion Bank (Naugatuck CT). Customer Statement with Pg n of m; Phone 203.729.4442  Website www.ionbank.com; PO Box 370, Naugatuck, CT 06770-0370; Summary - All Accounts as Account # | Ending Balance | Product; per account <product> - xxxxxxxxnnnn; sections Balance Summary and Account Summary; stable footer token NOPRB.D.N.262IB0001 / NOPRT.D.N.262IB0001.
- **Oracle:** Broken in the text layer. The Account Summary labels (Previous Date / Beginning Balance / Ending Balance / Deposits / Interest Paid / Withdrawals / Fees) are all printed but the VALUES arrive in a separate, differently-ordered run, so the label-to-value mapping is not recoverable from the text alone; the Balance Summary grid likewise prints dates and balances in unpairable runs.
- **Nearest reader:** none (no ionbank module)
- **Risks:** The worst text layer in the census alongside eastern_bank: the ENTIRE description column for a page is emitted as one prose block and only then the dates and the numbers as separate streams, so the Nth description must be zipped to the Nth (date, amount, balance) triple and even the amount/balance grouping is inconsistent. Descriptions also carry an inline Activity token belonging to the NEXT row's date, and the in-description activity date differs from the posting date, so naive re-pairing mis-dates rows. Route to a geometry/positional extractor, not a text-layer reader. Same geometry across three consecutive months of one member, so it is a generator property, not one bad file.
- **Merged from:** s4,s9,s11
- **shas:**
```
62001A0434BC44DB357C4A6C1519BA83EC53E88CAF95579332B6455CE7C75933
C61CA61AD9CD86E812F14EA40CBB905D82D22E87E0308A0C6AFD897D8DFD2C9B
CB85DB48BF5D069BE4FC1EB47E879A699654468FFD893054C5CB3748BB87FB03
D6C8DCE6285406E83B980784AEC9AF791881F262C9B357BD0C48477BC885A215
```

### 79. `pc_financial_pc_money_account` (n=1, expected 0.6, 0.6)

- **Printed identity:** PC Financial (Canada), CAD. PC Money Account / Earn PC Optimum points on every purchase with no monthly fees; Account summary with Statement period <Mon. D, YYYY> - <Mon. D, YYYY> and Card number XXXX XXXX XX11 nnnn; pcfinancial.ca; section Account activity.
- **Oracle:** Opening balance on <date>, Total deposits:, Total withdrawals:, Closing balance on <date> - all four printed and sign-prefixed.
- **Nearest reader:** none
- **Risks:** DD/MM date order (day-first, Canadian) is the key trap - rows like 16/04 read as month-first would be silently wrong. Withdrawals and Deposits sit in adjacent unsigned columns with NO running balance, so direction must come from the description verb (ETRANSFER FROM vs ETRANSFER TO) and be validated against the printed totals.
- **Merged from:** s10
- **shas:**
```
7A872347F4970FBFB72A3946FE4E9EAC16B239074AD129EB43012535B5159559
```

### 80. `bofa_business_advantage` (n=1, expected 0.55, 0.55)

- **Printed identity:** BANK OF AMERICA masthead over Business Advantage; Your Business Advantage Fundamentals Banking for <Month D, YYYY> to <Month D, YYYY>; Account number: NNNN NNNN NNNN; Customer service Information 1.888.BUSINESS; Account summary; Daily ledger balances; BankAmeriDeals block.
- **Oracle:** Beginning balance on <date>, Deposits and other credits, Withdrawals and other debits, Checks, Service fees, Ending balance on <date>, plus # of deposits/credits, # of withdrawals/debits, # of items-previous cycle, # of days in cycle, plus a Daily ledger balances grid.
- **Nearest reader:** analysis/bofa.py EXISTS - this is a text-quality failure, not an unknown template
- **Risks:** The text layer is degraded (masthead renders as BANK OF AMERICA~~, address as r.o. 1.1o, 15~4 llmlnl!'on, DE), so the summary and daily grid read but individual ledger rows need OCR-grade tolerance. The fix is likely glyph tolerance in the existing reader rather than a new family.
- **Merged from:** s1
- **shas:**
```
B5F4A9F6F8D595CF42256ED262FEB4356AB9BA11C0AFF6BCAAC4B6C9307EE654
```

### 81. `relationship_summary_daily_balance_unbranded` (n=1, expected 0.55, 0.55)

- **Printed identity:** An unbranded core printing - the institution prints nowhere in the text layer (logo-only). Account Number | Statement Date | Statement Thru Date | Check/Items Enclosed | Page over OCR line blocks; RELATIONSHIP SUMMARY AND CURRENT STATEMENT ACTIVITY with Account Type | Account Number | Balance; per account <PRODUCT> / Account Owner(s): / Balance Summary; sections DEPOSITS AND OTHER CREDITS, DEBITS AND OTHER WITHDRAWALS, ATM/POS TRANSACTION SUMMARY, CHECKS PAID, DAILY BALANCE SUMMARY, CHECK IMAGES.
- **Oracle:** Very strong for its size: Beginning Balance as of mm/dd/yyyy, + Deposits and Credits (1), - Withdrawals and Debits (26) with PARENTHESISED counts, Ending Balance as of mm/dd/yyyy, Service Charges for Period, Average Balance for Period, and a DAILY BALANCE SUMMARY grid.
- **Nearest reader:** analysis/core_processor_counted.py (parenthesised/counted partition with DATED opening and closing) is the nearest registered grammar; fiserv_premier.py for the count convention
- **Risks:** Only one exemplar and no institution in the text, so registration must be on RELATIONSHIP SUMMARY AND CURRENT STATEMENT ACTIVITY plus Balance Summary. ATM/POS rows carry a trailing card mask and a second date/time and the amount frequently wraps to the next line. Worth holding as a fixture if a sibling appears in another shard.
- **Merged from:** s7
- **shas:**
```
9D985F70CD543CCD70CDA3381118261DB96AABF8131CCA680011874620FC25F4
```

### 82. `southern_bank_quadruplicated` (n=1, expected 0.55, 0.55)

- **Printed identity:** Southern Bank. Statement Period: <Month DD, YYYY> Thru <Month DD, YYYY>; Account Number:; Enclosure Count: N; the marketing line Thank you for choosing Southern Bank, where our interest is You!; an account table Account Name | Account Number | Interest Paid In <year> | Balance over BUSINESS BANKING.
- **Oracle:** Beginning Balance with its date, Deposits / Misc Credits with a printed count and total, Withdrawals / Misc Debits likewise, an ending balance, Enclosure Count, and a Daily Balance Summary grid.
- **Nearest reader:** none (no southern_bank module); the summary shape is core-processor-like
- **Risks:** Every line is printed FOUR times in the text layer, so de-duplication of repeated identical lines is a precondition, not a nicety - the same normaliser fixes associated_bank (x2) and the x4 marketing blocks inside core_enclosures.
- **Merged from:** s3
- **shas:**
```
FC129FA3BD5A670E024DB28645C93D9C22C0F771D781DC7709CDA72EF2311937
```

### 83. `onepay_coastal_community_monthly` (n=1, expected 0.5, 0.5)

- **Printed identity:** OnePay (One Finance, Inc.) on Coastal Community Bank. Monthly Statement with Name / Address / Account Number / Statement Period; Account Summary table of sub-accounts (Debit xNNNN, Savings, Credit Builder Deposit, Me) under Beg. Balance | Ending Balance; every page footer OnePay Cash banking services provided by Coastal Community Bank, Member FDIC / Credit Builder banking services provided by Coastal Community Bank.
- **Oracle:** A front Account Summary giving Beg. and Ending Balance per sub-account, then per sub-account an Activity Summary with Beginning Balance on <date> / Ending Balance on <date> and a TOTAL +$x line.
- **Nearest reader:** none (no onepay module); nearest fintech readers analysis/relay.py, mercury.py, found_lead.py
- **Risks:** L-1 by construction: four named sub-accounts each with its own Transaction History section. The ledger has NO balance column at all, so per-account reconcile must come from the Activity Summary pair. Bare Mon D dates, and the merchant string wraps across 2-3 lines with the Date/Type/Amount triple emitted on its own line between description fragments.
- **Merged from:** s10
- **shas:**
```
1104CA62ABDFB5477C944C351F04F57DFEF4681B95D20ED89E69E33A7CA3581E
```

### 84. `eastern_bank_customer_statement` (n=3, expected 0.45, 0.15)

- **Printed identity:** Eastern Bank (MA). Customer Statement / Statement Period: | Account Number: | Number of Items Enclosed:; BCK-305 - PO Box 4071, Wakefield, MA 01880-5371 and Eastern Bank, PO Box 4071, Wakefield, MA in the error notice; Summary - All Accounts (Account # | Ending Balance | Type) with a TOTAL BALANCE row; per account <PRODUCT> - <account number> with the declared heads Date | Transaction Description | Balance | Withdrawal | Deposit opened by a STARTING BALANCE row.
- **Oracle:** Thin and partly unusable: only per-account Ending Balance and a TOTAL BALANCE in the summary (the opening balance appears only as the STARTING BALANCE ledger row); some members add Average Collected Balance, Number of Days in Period, Total Deposits/Credits and Total Withdrawals/Debits at the END of each account section.
- **Nearest reader:** none (no eastern module); analysis/citizens.py is the nearest regional sibling
- **Risks:** Identity is certain, readability is not: the text layer emits ALL descriptions as one run-on block and then ALL date+amount pairs as a second block, so dates and amounts cannot be re-paired with their descriptions without word coordinates. Where the section-end totals are printed they are trustworthy and the ledger is not - a summary-only publish is the realistic option. The Balance column is populated only for the starting row.
- **Merged from:** s5,s7,s10
- **shas:**
```
7223BAA25DF20F84CD91F9C65443DC0AD731F350B07F6CBE208A420BBB257ACD
A7EBB8C87C394698DDD93C43E5EF6C50C54BEBF5F0661308F11CEF306D969E2E
D8366FDA93C39BC6227D97FA7F2FD9A2D58FA7AE55C85A0A70CC354DA5154A66
```

### 85. `chase_total_checking_transaction_detail` (n=1, expected 0.45, 0.45)

- **Printed identity:** JPMorgan Chase Bank, N.A.  P O Box 182051  Columbus, OH 43218; CUSTOMER SERVICE INFORMATION Web site: Chase.com; period line January 29, 2026 through April 26, 2026; CHECKING SUMMARY Chase Total Checking AMOUNT; TRANSACTION DETAIL DATE | DESCRIPTION | AMOUNT | BALANCE.
- **Oracle:** Beginning Balance, Deposits and Additions, ATM & Debit Card Withdrawals, Other Withdrawals, Ending Balance (a three-way debit partition) plus a running Balance bracketed by Beginning and Ending Balance rows.
- **Nearest reader:** analysis/chase.py
- **Risks:** The real finding is not the template: the printed period is nearly THREE months on a 3-page document, which is either a combined/replacement statement or a doctored one - this asks for a period-length sanity rule, not a new reader. The text layer also emits the date twice and splits one logical row across two lines, so assemble on the date+amount+balance triple.
- **Merged from:** s3
- **shas:**
```
EA4B7F19D508C7C89576266B4FC192D14CDB4986E9C6C3AAB5DD4C1096895DFF
```

### 86. `cu_suffix_transfer_acct_grid` (n=1, expected 0.45, 0.45)

- **Printed identity:** A US credit-union member statement (Chiropractic FCU by elimination among shard-1's nine mastheads; not named in the census read). Member Number plus statement period in the header instead of an account number; a whole-membership balance table; one section per share/suffix; ledger heads Date | Transaction Type | #/ID | Transfer Acct | Deposit | Withdrawal | Balance - the Transfer Acct column is the distinguishing furniture; Federally insured by NCUA.
- **Oracle:** A per-suffix table of Beginning Balance | Total Debits | Total Credits | Ending Balance | Last Tran, plus a running Balance in the ledger.
- **Nearest reader:** analysis/symitar.py (and secu.py / midflorida.py / navy_federal.py as sibling CU readers)
- **Risks:** Single exemplar, so the template is evidenced once. L-1 with two to four share suffixes; the whole-membership table must not be summed with the per-share sections. No transaction counts.
- **Merged from:** s1
- **shas:**
```
9AE97A14516FFB183D5D147C6B53DE3962120DED39DAA83E3A1C4AB8496F41C2
```

### 87. `desjardins_accesd_releve_operations` (n=1, expected 0.45, 0.45)

- **Printed identity:** Desjardins AccesD Affaires web print, French, CAD. Header dd/mm/yyyy hh:mm  Solutions en ligne - AccesD Affaires; the word Fermer; title Releve des operations; Pour la periode du <d> au <d> <mois> <annee>; Imprime le <date>; a folio line <succursale>-<transit>-<folio>-EOP EPARGNE AVEC OPERATIONS (C); page-foot URL accesd.affaires.mouv.desjardins.com/...ObtenirSelectionReleveADA.do.
- **Oracle:** None beyond a Solde reporte opening row and the final running Solde (CAD) - no total credits, no total debits, no ending-balance restatement.
- **Nearest reader:** analysis/desjardins.py and releve_facturation.py both exist - very likely a sibling printed issue (the AccesD web releve rather than the mailed statement)
- **Risks:** The single highest-risk parsing detail in its shard: amounts use a NON-BREAKING SPACE thousands separator (1 450.00), so a comma-built money regex reads 1 450.00 as 450.00. Currency is PRINTED as (CAD) in every column header, which is stronger evidence than the jurisdiction default.
- **Merged from:** s4
- **shas:**
```
522051A65595F7F61103C588A81EAF854347FB68CC064A326218F67FB00F9A02
```

### 88. `laurentian_bank_current_account` (n=1, expected 0.4, 0.4)

- **Printed identity:** Laurentian Bank (Canada), CAD. Laurentian Bank <Month D, YYYY>; Current Account <nnn-nnnnnnn-nn>: $(x); Overdraft Protection; Available Funds; Starting Cheque Number for Next Order; ledger head Date Description Debits Credits Balance.
- **Oracle:** NONE printed - no opening/closing pair, no totals. Only the header trio (current balance, overdraft protection, available funds) and a per-row running Balance, so the balance chain is the only validation surface.
- **Nearest reader:** no laurentian module; Canadian siblings analysis/desjardins.py, rbc.py, cibc.py, scotia.py
- **Risks:** Rows are in DESCENDING date order and long descriptions wrap so the amount lands on the following line; negatives print in accounting parentheses $(747.96). 50k chars. A reader must walk the balance chain BACKWARDS. CAD jurisdiction default applies.
- **Merged from:** s5
- **shas:**
```
577EC96A31F290ABBF71A53F2BA08D0546B7EF178881F4E4A2F3C5E12A14E000
```

### 89. `rho_deposit_account_statement` (n=1, expected 0.4, 0.4)

- **Printed identity:** Rho (Under Technologies Inc DBA Rho Technologies). Support 24/7 Telephone: 1 (855) 7-GETRHO  Email: clientservice@rho.co  Website: https://rho.co; Deposit Account Statement; Account Details with Company | Address | Statement Period | Account Number ****nnnn | Routing Number; per account Summary with Starting Balance / Ending Balance; ledger heads Date | Description | Sender/Recipient | Memo/Reference | Type | Amount | Balance.
- **Oracle:** Thin: Starting Balance and Ending Balance only per account, plus a running Balance column and an explicit Type column.
- **Nearest reader:** analysis/brex.py is the closest registered corporate-fintech reader; mercury.py structurally
- **Risks:** No credit/debit totals and no fees line, so the chain is the only oracle. The first page is dominated by a two-column error-resolution notice into which the Account Details fields (Statement Period, Account Number) are interleaved, so header extraction must survive the interleave. Two Summary/ledger blocks appear (the second with Starting = Ending = $0.00).
- **Merged from:** s7
- **shas:**
```
367CDBACFBA9A8F54202839FCB5833DC278A4ABE7DE30C645F6B312C741DC59D
```

### 90. `conexus_cu_demand_products` (n=1, expected 0.3, 0.3)

- **Printed identity:** Conexus Credit Union (Saskatchewan), CAD. P.O. Box 1960 Stn Main Regina SK S4P 4M1  Member Contact Centre 1.800.667.7477 / Branch: nnn; For the period beginning <date> / For the period ending <date> / Member Number / Number of enclosures; product banner Demand Products then Account Number ... / <PRODUCT> Sub Number 00n; marketing citing conexus.ca.
- **Oracle:** None printed - no beginning/ending pair and no credit/debit totals; only a Balance Forward opening ledger row, Number of enclosures, and a running Balance.
- **Nearest reader:** none; nearest jurisdiction siblings analysis/desjardins.py, td_can.py
- **Risks:** Overdrawn balances are marked by a TRAILING minus (9,557.32-) which must be handled or every balance flips sign. Fixed-width DDMonYYYY dates (08Feb2024) and many rows per physical line, so split on the date token. With no summary totals the chain is the sole oracle.
- **Merged from:** s10
- **shas:**
```
AFCEEC6A21F0561420A2C017D95F2876E49321042D078352B8D1E96D0F701FB3
```

### 91. `paypal_account_statements` (n=7, expected 0.0, 0.0)

- **Printed identity:** PayPal ACCOUNT STATEMENTS export. <Last, First>; Statement Period | PayPal Account ID over <date range> | <email>; the standing notice This document contains two statements: PayPal account statement ... PayPal Balance account statement ... Transactions paid with a PayPal Balance account and another payment method will appear in all affected statements; section banners PAYPAL ACCOUNT and ACCOUNT ACTIVITY; column head DATE DESCRIPTION CURRENCY AMOUNT FEES TOTAL*; legal footer naming PayPal Digital, Inc. (NMLS ID 2610315).
- **Oracle:** None usable. Some printings carry a BALANCE SUMMARY block but it is footnoted that the difference between Beginning and Ending Balances may not equal the sum of Account Activity - the issuer disclaims the reconciliation a validator needs - and other printings carry no balances at all.
- **Nearest reader:** none (no paypal module); analysis/shopify_balance.py and square_checking.py are the nearest processor-ledger readers
- **Risks:** CROSS-SHARD DISAGREEMENT resolved here: three shards filed this printing under not_statements and two under families; I unified all seven under one printed identity and marked it POLICY-BLOCKED. It is a payment processor, not a chartered deposit account, and the same transaction is printed TWICE by design (the PayPal account view and the PayPal Balance account view), so naive concatenation double-counts every balance-funded transaction. Recommend treating as not-a-statement unless Gustavo rules processor accounts in scope.
- **Merged from:** s3(ns),s5(ns),s6,s7(ns),s12
- **shas:**
```
3FEE1F2D3D5A88B71BDC0D8118FD10D2544A2EB0C77DFD3320DAA801C2CD7FA9
503711E979E42DC31F3EC3F1BE19252B4F82985BBF886137B7C726E39F3C646A
582D6AC9426733FBA6C55D98BB9599F347BAA37946D3872D581BA90E644450DC
7F7C50B5E6F0E9549934E45369B77537516B19C12AE678904414A8BB73713BFC
967C589E93D164018A58147531D595E832E09CC63A788CEB27116FC3696C5AF8
F13DAAE34C3C46C854589FAEDE3618D3EF1170AE7227695A9AE15C30E77325EA
F6E2E1B80BA6CDDDFC1D29BDFF898D8EE6F8B19A30B102CA6537C3C329767990
```

## Text-layer defects (route to OCR)

```
{
 "conf": 0.0,
 "pi": "Genuine statements whose PDF text layer cannot be read: embedded subset fonts with a broken or absent ToUnicode map decode every glyph to a substitution alphabet, hitting DIGITS as well as letters. Four are RBC Canada business statements (ROYAL BANK OF CANADA survives; Bu-in0-- A11ount 4t5t060nt = Business Account Statement; amounts render as M.,701-78 / 7G09H-00), one is Chase (CHASEO, %eJLQQLQJ %aOaQce for Beginning Balance), two are Bank of America / unidentified mojibake, and one (2E957B7D) is a First Citizens statement whose text layer contains ONLY back-of-statement boilerplate - the entire front is an image layer.",
 "oracle": "None. No deterministic reader can ever match these; they are NOT empty (chars>0) so a chars>0 filter keeps classifying them as digital and they keep consuming reader-matching attempts.",
 "reader": "analysis/rbc.py, chase.py, bofa.py all exist and are the correct institution readers - the blocker is the text layer, not the parser",
 "risks": "Route to raster/OCR re-extraction rather than reader work. Recommend a cheap mojibake detector (share of decoded characters outside the printable-ASCII/statement vocabulary) plus a scrambled-cmap check so these stop being offered to text readers. One document uses at least TWO different broken mappings on the same page, so the substitution is not a single shift. Under the currency doctrine the RBC members take the CAD jurisdiction default once readable.",
 "src": "s1,s2(sg),s3,s4(sg),s5,s9(sg)",
 "n": 8,
 "shas": [
  "19ED81F23EC1531D04693C01AF1FCF7C91E85254129EB557E7EBE54A96B3ABE0",
  "2D486AA4A94B5896E871EDA924138BFC8A0693202293899924601E9ACBC56784",
  "2E957B7DF84494B357AB255C5CB3B139BD6D2EAD73687AB0215FA8412D9AB9F8",
  "367DC3C3265D696BE8B553A5BD3BD6FDA68DD961AA70C14CF51D6C004BAFF0CC",
  "5B76F0B19AB02C5D37BC511FF01262371CFE7D9874AF3A9817A88E7B3781AFBB",
  "69D3AD2FE8AD820146E535759F8E145FE97BCC2490C93A32B62BC4990175B30C",
  "720C4C37AD3F9B76B701DCC829D6D60CCDADE04553399D203867036C77F35159",
  "ADB91E10278C8121E98783DF75CB1AFC76B3874E7C5033FCB8FAC3D712EA3622"
 ]
}
```

## Portal and range exports (not statements)

```
{
 "conf": 0.0,
 "pi": "Online-banking activity exports and browser prints that several shards had promoted to families. They carry a dated ledger and usually a running balance, but no statement period, no beginning/ending pair and no printed totals: Apex Bank / Addition Financial activity views, Bank of America Account Activity (two balance columns, Ending balance rows per day), TD Canada Trust FROM DATE/TO DATE range exports (one a detached Page 8 of 8 fragment), PNC Cash Flow Insight with PENDING rows, Scotiabank and RBC portal prints, a BMO Detail Report - by Processing Date (ledger-only, no balances at all), a Space Coast posted-transactions export, an unnamed treasury portal Transaction Details List View, and a Community Savings member-portal listing.",
 "oracle": "None that a fail-closed reader should accept: the window is customer-chosen (one spans thirteen months), pending rows are interleaved with posted ones, several are reverse-chronological, and the balance is sometimes labelled Calculated.",
 "reader": "analysis/found_lead.py and chase.py (chase_export) already register this GENRE, so the pipeline has precedent for how to treat them",
 "risks": "These are the boundary cases that most need a ruling: they are readable but not periods of record, and admitting them would put customer-chosen windows and pending items into revenue math. Counted here with not_statements. The BMO export prints no balance of any kind, so beginning/ending and ADB are not derivable from it at all.",
 "src": "s2,s6,s9,s10,s11(sg),s2(sg 5ACD950A),s9(sg 4F8D24A3)",
 "n": 13,
 "shas": [
  "0396C3A3FA9163FA63D7D1A88E27B7647A1FAF38604973154067B8239ADF8184",
  "18A524AD4D6AAF89AAF823A291712CDC57C63773C6CCD49ED3D5D903B90EEC3B",
  "3DBDF360144F12969186F1646923BAFB2E684CDD96E13B28305F03B9BEE6E1BC",
  "3FA5657F74925E51D0895977356ED7671F252208D53CCE5DAEAA80781E48B31E",
  "4F8D24A3629404371147D08A09BBA773F10443FD0E7562365F4B7AC17D8BBA82",
  "5ACD950A998E88ED63CE4E919F9773A178323E715DF77785E6D72A973EB1CA2B",
  "6D283A80D9473652C4C3769AA411D1D2D11F1E80B8A9540C208C6879425C5AAF",
  "79EAE384CB1B36DC4B2C0D2CF782CFF1C73B8446097AA6D2369C248DE2184186",
  "85DD6E65360BE1813111AA4A586CD815AB5159583A3DB5C515035ABD3563254F",
  "A751A35468A6BDCDCEA074C3A1EBA304F3E9CCFC3B250DC8077DEE782CB94AF6",
  "BA7A1CBD25EABDD2343D86C2DA5D0C2B551972EEC4E21FF7B3D57C731AE1E691",
  "BEDE7D5DE0D947D222CF19C606BF1534D757CA1469F06C50245BAD5F91B680B5",
  "D886A629369FE4454C89A37F642EFAC8AFD36308D28BA0618792E51599892BE9"
 ]
}
```

## singletons

```
[
 {
  "family_key": "ramp_business_account",
  "sha": "B988C19C86AE595E6469BB6AA0CD57121BA69A3980E142918E27E82F525D107C",
  "confidence": 0.85,
  "printed_identity": "Ramp business account (deposits at First Internet Bank of Indiana). A six-label header grid Interest rate | Account ID | Account number | Statement start | Statement end over 2.00% | rba_<hex> | ....nnnn | <Mon D, YYYY> | <Mon D, YYYY>; product line Checking Account; per-page footer Checking Account statement generated by Ramp. All dates are displayed in Eastern Time. Page n of m; Interest From First Internet Bank of Indiana."
 },
 {
  "family_key": "pc_financial_pc_money_account",
  "sha": "7A872347F4970FBFB72A3946FE4E9EAC16B239074AD129EB43012535B5159559",
  "confidence": 0.6,
  "printed_identity": "PC Financial (Canada), CAD. PC Money Account / Earn PC Optimum points on every purchase with no monthly fees; Account summary with Statement period <Mon. D, YYYY> - <Mon. D, YYYY> and Card number XXXX XXXX XX11 nnnn; pcfinancial.ca; section Account activity."
 },
 {
  "family_key": "bofa_business_advantage",
  "sha": "B5F4A9F6F8D595CF42256ED262FEB4356AB9BA11C0AFF6BCAAC4B6C9307EE654",
  "confidence": 0.55,
  "printed_identity": "BANK OF AMERICA masthead over Business Advantage; Your Business Advantage Fundamentals Banking for <Month D, YYYY> to <Month D, YYYY>; Account number: NNNN NNNN NNNN; Customer service Information 1.888.BUSINESS; Account summary; Daily ledger balances; BankAmeriDeals block."
 },
 {
  "family_key": "relationship_summary_daily_balance_unbranded",
  "sha": "9D985F70CD543CCD70CDA3381118261DB96AABF8131CCA680011874620FC25F4",
  "confidence": 0.55,
  "printed_identity": "An unbranded core printing - the institution prints nowhere in the text layer (logo-only). Account Number | Statement Date | Statement Thru Date | Check/Items Enclosed | Page over OCR line blocks; RELATIONSHIP SUMMARY AND CURRENT STATEMENT ACTIVITY with Account Type | Account Number | Balance; per account <PRODUCT> / Account Owner(s): / Balance Summary; sections DEPOSITS AND OTHER CREDITS, DEBITS AND OTHER WITHDRAWALS, ATM/POS TRANSACTION SUMMARY, CHECKS PAID, DAILY BALANCE SUMMARY, CHECK IMAGES."
 },
 {
  "family_key": "southern_bank_quadruplicated",
  "sha": "FC129FA3BD5A670E024DB28645C93D9C22C0F771D781DC7709CDA72EF2311937",
  "confidence": 0.55,
  "printed_identity": "Southern Bank. Statement Period: <Month DD, YYYY> Thru <Month DD, YYYY>; Account Number:; Enclosure Count: N; the marketing line Thank you for choosing Southern Bank, where our interest is You!; an account table Account Name | Account Number | Interest Paid In <year> | Balance over BUSINESS BANKING."
 },
 {
  "family_key": "onepay_coastal_community_monthly",
  "sha": "1104CA62ABDFB5477C944C351F04F57DFEF4681B95D20ED89E69E33A7CA3581E",
  "confidence": 0.5,
  "printed_identity": "OnePay (One Finance, Inc.) on Coastal Community Bank. Monthly Statement with Name / Address / Account Number / Statement Period; Account Summary table of sub-accounts (Debit xNNNN, Savings, Credit Builder Deposit, Me) under Beg. Balance | Ending Balance; every page footer OnePay Cash banking services provided by Coastal Community Bank, Member FDIC / Credit Builder banking services provided by Coastal Community Bank."
 },
 {
  "family_key": "chase_total_checking_transaction_detail",
  "sha": "EA4B7F19D508C7C89576266B4FC192D14CDB4986E9C6C3AAB5DD4C1096895DFF",
  "confidence": 0.45,
  "printed_identity": "JPMorgan Chase Bank, N.A.  P O Box 182051  Columbus, OH 43218; CUSTOMER SERVICE INFORMATION Web site: Chase.com; period line January 29, 2026 through April 26, 2026; CHECKING SUMMARY Chase Total Checking AMOUNT; TRANSACTION DETAIL DATE | DESCRIPTION | AMOUNT | BALANCE."
 },
 {
  "family_key": "cu_suffix_transfer_acct_grid",
  "sha": "9AE97A14516FFB183D5D147C6B53DE3962120DED39DAA83E3A1C4AB8496F41C2",
  "confidence": 0.45,
  "printed_identity": "A US credit-union member statement (Chiropractic FCU by elimination among shard-1's nine mastheads; not named in the census read). Member Number plus statement period in the header instead of an account number; a whole-membership balance table; one section per share/suffix; ledger heads Date | Transaction Type | #/ID | Transfer Acct | Deposit | Withdrawal | Balance - the Transfer Acct column is the distinguishing furniture; Federally insured by NCUA."
 },
 {
  "family_key": "desjardins_accesd_releve_operations",
  "sha": "522051A65595F7F61103C588A81EAF854347FB68CC064A326218F67FB00F9A02",
  "confidence": 0.45,
  "printed_identity": "Desjardins AccesD Affaires web print, French, CAD. Header dd/mm/yyyy hh:mm  Solutions en ligne - AccesD Affaires; the word Fermer; title Releve des operations; Pour la periode du <d> au <d> <mois> <annee>; Imprime le <date>; a folio line <succursale>-<transit>-<folio>-EOP EPARGNE AVEC OPERATIONS (C); page-foot URL accesd.affaires.mouv.desjardins.com/...ObtenirSelectionReleveADA.do."
 },
 {
  "family_key": "laurentian_bank_current_account",
  "sha": "577EC96A31F290ABBF71A53F2BA08D0546B7EF178881F4E4A2F3C5E12A14E000",
  "confidence": 0.4,
  "printed_identity": "Laurentian Bank (Canada), CAD. Laurentian Bank <Month D, YYYY>; Current Account <nnn-nnnnnnn-nn>: $(x); Overdraft Protection; Available Funds; Starting Cheque Number for Next Order; ledger head Date Description Debits Credits Balance."
 },
 {
  "family_key": "rho_deposit_account_statement",
  "sha": "367CDBACFBA9A8F54202839FCB5833DC278A4ABE7DE30C645F6B312C741DC59D",
  "confidence": 0.4,
  "printed_identity": "Rho (Under Technologies Inc DBA Rho Technologies). Support 24/7 Telephone: 1 (855) 7-GETRHO  Email: clientservice@rho.co  Website: https://rho.co; Deposit Account Statement; Account Details with Company | Address | Statement Period | Account Number ****nnnn | Routing Number; per account Summary with Starting Balance / Ending Balance; ledger heads Date | Description | Sender/Recipient | Memo/Reference | Type | Amount | Balance."
 },
 {
  "family_key": "conexus_cu_demand_products",
  "sha": "AFCEEC6A21F0561420A2C017D95F2876E49321042D078352B8D1E96D0F701FB3",
  "confidence": 0.3,
  "printed_identity": "Conexus Credit Union (Saskatchewan), CAD. P.O. Box 1960 Stn Main Regina SK S4P 4M1  Member Contact Centre 1.800.667.7477 / Branch: nnn; For the period beginning <date> / For the period ending <date> / Member Number / Number of enclosures; product banner Demand Products then Account Number ... / <PRODUCT> Sub Number 00n; marketing citing conexus.ca."
 }
]
```

## not_statements

```
{
 "n": 104,
 "shas": [
  "023CDC26749D65BE98C3B7C6B8467143157A220C216BCA41E784C23959BBFC5C",
  "03D93BC1C67F148AF2E08DC11AC44ECADDBB725701B74C240668BB6DD991979C",
  "0A8307BD6B355EFEFF143615EA51CD9BEC339DA3558FF101B4C98307F77E17AA",
  "0CD13C8F3A4BE4E1601578BCE5A491DA27BCD130A3F8A19D8BD9F6E943F38D66",
  "0D6010E4C1382622DA75B70A5040DF6B026330E8D203D9354B671162D0AE9184",
  "0ECBD5376B4A6CFF59B864C1FC28EB9A0E958CBEB3B5C556B660982FAE44E6E3",
  "0F1A3B4712E59F6A83605C2FF92E053DAD0F36B812BFD9DE74272224F72A01ED",
  "0F802A511CDA76D30D35D7FD18D1BCE152ADBA5622B7FE07855C9536D63F08F5",
  "16E811FC7DE632BCA24C5C19ADB44BEE066A9FBBE7FA17D0E4F2C7A7344B340D",
  "1839E3B63049372266AD7F13A2C77E1806AEA3E13765699760423B7F372CB5C2",
  "1B82DF47498A59680A79B4BDB33DBD46BBBBFC806C5FD45EE9E368A8DB59721A",
  "1BBD4ADF433C19910BD5D5F08A8AAAAA5E636F85FA4957B58632E17A575BC3A1",
  "1C5EC0C012980EF6C7DA4B13AC447F01A1BED727099F94BB5A437F4254B56488",
  "1EDC9E104C7AAD3F37C7AD344B683FF1BCF802579C6E75E1A78E86CFD5EA3723",
  "228DF61DCE5D604B3537F155BC921899E97C8F4FBBF823F29A5AD1F2A61F8F8B",
  "2A6E98002176D99B1BCC18EE8BFF81E8F75C28D2181293584F3DE9843FDE4CE4",
  "2AAD7259F64140437431A4FB2E5FA2A0202A293F566F3A23472C608FD5D56A0C",
  "2CDC5BF87CCF129081DD44BD901A088413E01775367343CCA9AD84F9600BE69E",
  "2F24037A2F1F9D16134604B42A9E271AF078F24AEECD9D3F93E0972610FA7D36",
  "3126951648C781AA6A62890B859C1A3CA4CFAFECF763C51662CB416A1E90F799",
  "31BC9E17AF2FC679D46DD00FDF32A97334C21071C26E0A1B5AAE9C68156D78B4",
  "323E99F886E5BE345B4638AA46A28E05EF50C6E13C63A70C195BB1327C3FCA31",
  "3258D9A0A735E1D34155CFD1EE11D8A9942740069C7D7A89E50DC9C800B8A9B3",
  "34002EC276B446A11B3542D5522202EE4AE3182EC2C87B6E8A66D3613F779ACA",
  "362A08B720DFDF4CF29F271B9D1BCECD78CD4B80D60F1234E648F5A0699D061F",
  "39E0152153B2D219B7589E91F1407C01175B3B0E8983F9C94BEABA612DAC8E1C",
  "3B385E3A8B76D5249227262C3D9E5E1A9990B31114807A9A8692174D355EAF8F",
  "3CC7EE3B499634CA65ED21691ABE661E2BFD9D19AE63E1AF02CA3BE7153D6C22",
  "3D1F8163572B002C030153CB9D45527361ED2DE410D6246E2E4FB8DF6CEEE5F1",
  "3EF955504367FEBA227BEDA73FAC81E13BCBA49CD8C6B26309AEBCAE45A4CCB6",
  "3F04C47DD9A745E1425BE43EC4FDADEE27B47571A70624600B90E4FF457EA8F0",
  "4295D7A86F1AF93E0B74548D321CF9B24EA522BF16038E133C44358F5E11E222",
  "4341EBE2CFE03A9C109E07AEA0305D24F6DA541C92E40BEFAD924D6D59A73126",
  "46624A5EB99F5F451F34FD682698CF764CC87AB6B22A3BC96CB84B70725A5A36",
  "47C25055594C7725A5EF8538437A4E2B976ADF4E5EA07063E4DDD81356A556AB",
  "4CACCC5B7ADFBBBFB443DB3ACC51B434CB4E5CCA96B65E4F09155B484ED82675",
  "4F5D0B78CD8BC40A705297FB7E3559AA9032F08DB20517E39A7D3486492471D9",
  "52BF0C2B414CBAA696D28B203E04FB5703B4104A2C0CB13B92EA3FB491FD66D4",
  "54BA73ED0129410BB5B01234D0EDFA4F0B7196AB0D75A369AE48DC8005A39F36",
  "5C528616944EB1773169E5EDB1281C5D25FDE9163C606D4387EBDFF1B99A1A6B",
  "5D870BEC15DAE2027134D7B748B4D76517BE5FFBA9F535068F87FFAAF9EA1606",
  "5EC52143CBB74004E01A64346A494E051E491E559192A63FBD9889B3F29AF5A8",
  "618BAD3639FD6496EF95E04F2E45D24B906751FF23EFAA74690D6E86796D4998",
  "62AEFF4DF6009C949C0FAF8792A486D5ED32E189C36F2CA3A6F353AD42BFA424",
  "63F24D62C0B29EEF82849A688BE35EF48EB41C8186570893EBEFD5AF92C7C4F9",
  "66BC0F48B64308D7FEC699B820D87F8B95999F27AD9030631BA89DFE5127E4DE",
  "6D1D94BEC40396C44D504C2706B701DFDA46F331FB4F00F0BCF3DB3686C2228E",
  "720CF485E216D916989AB4D6BC45238A419CE61EF7CBA549B2B114B67778FA2D",
  "7447415D4CD5DE805D29F74F85A999518586FB06BFC868CBE2D01B8DCD62A64E",
  "75EEE5141C1A930E38F70442B0B484102D9A905165B0976EDBC4A4968D65D38F",
  "78183B283FCB9C6F9180788B9F97918C00166304F76103C39F1BCDCBF38C72E7",
  "7A9F3274C2E8368DEBD8643C3B5434C4650B01C35F0D9D3CD8770A0343B19219",
  "7C66346972EB5716642B839FCF9EA7356D7D0C36B4570569396295A86FA4D361",
  "81C743048B48E1592902AD34BC0447271F9E446BCC51D2C35DACD96D84B06E0A",
  "8629813BBAC062CA629DF5CCAAE66978D768D6AEC4CB6C067B399E492D79C402",
  "89749FC636DFFC0B5DEF44B23E6050D3CF2121D91756D7F5148BD6261E0A0F0C",
  "8A437C80861F8135A4D1B673278A72DD498D1CAEF988983362A43F18F32DE52C",
  "9039432FB3001898F5C4FE9353DF42D752A5FF8C8367EF8DB52DFFC9DF6BEE9C",
  "939FF46F2CA134EFBC37CF29E78FC577428341AD34D2EC2EEDC628B84BF67566",
  "94B5C66AAE85E40739B5C5787B875DA3BAD788F03193EA417D239D72035DFC9F",
  "96970042B5C31FE89181166ACD06AD41EC87FADCEFF4B7E4E64BF66449404115",
  "9ACA05CD44BE1227D103E525E483D591D77B8C6C63D3763E7EAE1BC7426D3E59",
  "9B5024A6DD7A1FAE8348F041BBE054EE5E79A35B346132FEEE7985A2E5CD4873",
  "9D791424425D3B9628170D6501810B5A9E0829BBA3F7F3DA68A3819BCC61A628",
  "A52A9D7ECC521286C70264D4CD4880FCC326D730E12F8B57503D56B2AD5C4FB2",
  "A71DEDC7D93C92ADEC583908CBB5C1AC45B3619E82ED5991402681FCF557C171",
  "AE0581F138F4356AFCFA7CCFC4ACBBA8F7917E05AD3DFE115E15E101273AD661",
  "B1589A7157F91E15DA97E6AFB8CE945CB4ECCA26CAC3A0135A85C62893566694",
  "B573F0C70843A5C39E9C68A8949A606F896E632077D7FD5A8018B424168A457E",
  "B5C8EE8958B39FE54B2F9BA4AC94827060F81996C5664B7C17FDDB475C371633",
  "B6F3AE2A854A345023B6E698D8D86B1A690FF8024BD4A12DEF037E34FB26C918",
  "BBB8DF1DDE469179BAFA329CA3F308FF580997875607BFFAC5352D89937960E8",
  "BFE3E7D7E24ACA6742A1E418AF3CB92E7A7B7A911ED44D104ED9AEAA33D47CC2",
  "BFF548686DBB02025F461D673CBD18DBB7D5051A04518CB6E1606AADA7DABF94",
  "C0186760BCD1667E5D6753D315AF668362A0DDF0538A41312557CFF169801D3A",
  "C175A7FD8003E07F0DE3FFA82BD4A6708543E8652749B6348642648D2F7AC854",
  "C21E3683C072471018EC82BBCF185A3A42D9349CBBEC69B12DE262D96B00B9B2",
  "C3BFA577B3ABD183EAE26015D7B540106D990F50B18603CB24BE9CF0F4CEBF5D",
  "C41E5EBEA32A80C625D54CDE1C51E1F0F580FF664A67C9CC42FFF09C69749736",
  "CAF3FB335C6A270DEA3F19B0A92F1A4059FAF6ED2CA59746B3E46ED69B221773",
  "CB2F300419D35FA70C091E68D88534F8EF4922FDB35EB150EDBAFFBC44775EFD",
  "CC05BBA8B9C86A93BB8C361AADEA1A0EB6FF0C3A7BCC1BB3ED8DD321648160B1",
  "CCC0FA538142AA88E294070085C8321D41EB9CD58E7F5D0F862AC53253543DC2",
  "CDDD6BD32B037D4C4A157EAE2EB357C169C2F3EDA94C660633B0291DFD511C88",
  "D070198E0816B80FBFD94F25BED98D1B3CA7116D53A5D8A93D7D269B26307D76",
  "D7E5437DB818FC2B76490B2685541D7707C4AEFB03A01A80DD48E402A369E8B9",
  "D810DA664AA4654CB077BFABA4132750CEDD52DF6F9B6C17CFC475EBA3E133CB",
  "D8DBB5A34126A24EF991C7A3C1357B5F3B3E810CAE3EB9E18EE4324AD8808F95",
  "D9CF1D8378071C1E104ABE02EAF9087BD3AE0549DCB5EAA27CCB939B9E32FC9F",
  "DBA2417935EC9C8F5B57E8C4C84ADBE4537A19F22694006855846AF33A33CF37",
  "DDDB1C8EA583D823B79102E329C85E8FCCD973E580B21250C16C324F61AAE620",
  "DE640D9C514EE54DA92A084F356A6A79837D2E1F6A2090D719095120CA74300E",
  "E557342C8695251DD7457D7CDB5A5B9374503CCE7FA39BE0C6ECEB018E9EDDAB",
  "E6473C22D671666D7BC5142587AD201B72AEB365540D88435B5FBE36A140097C",
  "EBAD3C3AB2FC50EB3103070A8684814E6BB13987D525AB2E7EAAE7E0E7083FFC",
  "ED27862D211F2067528B52661B1ADA9E4F12F173092E53539216BEC060EDC8FF",
  "EEEE8F601CA8BD4514113955E186C26CB72132C58CEC8675069F2C1DB5F33C87",
  "F12C59314D61C02D7B061C6FACC6C4F57F1A9C9FCD0A5DD88DA58C3511F65A08",
  "F4938809751D0AA69EA4FD02678EAABF4B9AE9D3644541D61B0F8108A3C23628",
  "F549E78D5C516DF29348F1A59AE49AB5588D1C4F912404C3BA97EE6B68D67311",
  "F9BC8447E38EC2A8B41A3A3E65DFDDA31763BDF545EC75FBFE4256527DFE58A7",
  "FD03CDFBD165C3E537005A80C7E67E98715F9016750DCF59488269121D8DFD39",
  "FD044BD587D80616FD32C72FC3A17CD4DE08D5D1C327512C89B030C83D949C28",
  "FE34B1EA11F6B82D544A2057FA00273DE6CD787E32D4AB1912CBC5D1388D8283"
 ]
}
```

## no_text

```
{
 "n": 1,
 "shas": [
  "A9D3C95326B1686D6A41D0F590930874A8EDAFE4F48E5D25F118326AC0BE67AD"
 ]
}
```

## The withheld 61 (run `7a317445`)

# Withheld-cohort census — 61 documents, batch-6 run of record

**Method.** Each sha was re-analysed from cached OCR text (`doc_text.text_for` → `analyze_markdown(..., parse_mode="deterministic")` → `report_to_dict`), read-only, no hosted model, no sqlite index. All 61 reproduce as withheld locally (`metrics.average_daily_balance is None`, `adb_ok False`) — **zero divergence from the published run**. Cause was taken from `metrics.adb.validations` (the required-check set in `analysis/adb.py::_validate`), then the printed text was read for daily-balance furniture. Documents are named by content sha16 only; no amounts, names or account numbers appear below.

**Cause codes** (the required check that failed):
- **A `ledger-no-close`** — `ledger_reconciles_to_closing` / `final_balance_matches_statement_closing`
- **B `runbal-conflict`** — `running_balances_support_daily_ledger`
- **C `postdate-coverage`** — `posting_dates_cover_source`
- **D `out-of-period`** — `transactions_within_period`
- **E `no-ledger`** — early return: no period and no opening derivable (no validations run)
- **F `no-opening`** — `opening_balance_matches_statement`

**Headline.** 42 of 61 documents PRINT end-of-day balance evidence the reader is not consuming — either a dedicated daily-balance grid (PNC, TD US, Regions digital, Citizens, the community/sectioned family, Southside) or a day-terminal balance column (TD Canada native and French, Wells Fargo). `stated_daily_balance_count` is **0 on 59 of 61** documents; only the two Zions statements read their grid at all. Six further withholds (4 Navy Federal, 3 community_section, 1 Wells Fargo, 2 Zions — overlapping) are pure `source_posting_dates` heuristic false positives: the "missing posting date" is a Beginning/Ending-Balance boundary row, an interest-rate line, a page-header statement date, a second account's grid row, or a marketing sentence.

## Group table

| parser_id | cause | n | printed daily evidence unread? | plausible lift | notes |
|---|---|---|---|---|---|
| `td_canada_native` | A | 6 | **yes** — day-terminal `BALANCE` printed on every posting day; 0 of 37–264 rows carry a parsed balance | **yes (highest)** | Family furniture: `DESCRIPTION / CHEQUE-DEBIT / DEPOSIT-CREDIT / DATE / BALANCE`, opening printed as `BALANCE FORWARD`. Ledger fails only because line items don't sum to the printed closing (credit/debit **count** mismatches). The printed day-terminal balances are primary daily evidence and would settle the day set independently. |
| `td_canada_french` | A | 4 | **yes** — day-terminal `SOLDE` printed for **every** posting day (measured 21/21, 22/22, 20/20); 0 read | **yes (highest)** | Same masthead family, French furniture (`Relevé de compte`, `RETRAITS / DEPOTS / DATE / SOLDE`, `SOLDE REPORTE`, `DC`/`CR` suffix, space-thousands + comma decimal). The amount-format handling is also why only 94–95% of stated credits are captured. |
| `community_section` | B | 4 | **yes** — `Ending Daily Balances` / `Daily Balances` grid, `Date Amount` pairs = every posting day; 0 read | **yes (high)** | Sectioned core-processor family (`Statement Ending MM/DD/YYYY`, `Managing Your Accounts`, `Summary of Accounts`, separate Deposits / Electronic Credits / Checks sections). Every break is on a check-listing row (section order vs posting order). The printed grid resolves the day totals without trusting row order. |
| `community_section` | C | 3 | **yes** — same grid unread (grid holds 23–27 dated pairs vs 22–26 parsed posting days) | **yes (high)** | The single "missing posting date" on all three is the period-start date printed on the `Interest Rate Changes` line (`MM/DD/YYYY 0.0000%`). Heuristic false positive; the grid even prints that day's balance. |
| `td_us` | A (+C on 2) | 4 | **yes** — `DAILY BALANCE SUMMARY / DATE BALANCE` grid on all four; 0 read | **yes** | Scanned, but the grid OCRs cleanly (two-column `MM/DD  balance`), and it prints the pre-period day too. Worst scan (`D3396D14`) parsed only 3 of 18 printed posting days — yet its grid is intact. `Average Collected Balance` printed = evidence only. |
| `pnc` | A (+C on 2) | 4 | **yes** — `Daily Balance / Date  Ledger balance` grid on all four; 0 read | **yes, with geometry** | In the native-text digital docs the grid's columns are shredded by PDF flattening (dates on one line, balances on another); the short scanned one reads cleanly. Ledger fails because Activity Detail capture is incomplete (0–24% of stated credits). `Average ledger` / `Average collected balance` printed = evidence only. |
| `regions` | A | 3 (digital) | **yes** — `DAILY BALANCE SUMMARY / Date Balance` grid; grid dates == parsed posting days (15/15, 16/16, 16/15); 0 read | **yes** | Also prints `Minimum Balance` / `Average Balance` = evidence only. |
| `regions` | A | 1 (scanned) | no — this statement prints no grid and no per-row balance | **no** | A declared page is absent from the supplied PDF; only ~96% of stated debits captured. Honest withhold. |
| `navy_federal` | C | 4 | no — `Balance($)` read on **every** row (156–268) | **yes (high)** | 2 docs: the only "missing" dates are the printed `Beginning Balance` / `Ending Balance` boundary rows — false positives. 2 docs: genuinely folded posting dates, where a row's embedded card-transaction date was taken instead of the printed posting date. Both are deterministic parser fixes. Prints `Average Daily Balance - Current Cycle` = evidence only. Printed identity is Navy Federal (`Statement of Account`, `Access No.`, navyfederal.org) regardless of folder label. |
| `zions` | C | 2 | no — the grid **is** read (12 and 17 snapshots) | **yes (high)** | Both missing dates are false positives: one is a row of the *second* account's dot-leader daily-balance grid (`Date....Balance`, which the daily-balance-section detector does not recognise), the other is the page-header statement-date line. Nothing else fails. |
| `wells_fargo` | C | 1 | partly — day-terminal `Ending daily balance` column, 18 of 37 rows read | **yes** | The missing date comes from a marketing sentence in the message block. Pure false positive. |
| `wells_fargo` | F + B | 1 | **yes** — the printed `Beginning balance on 6/1` is unread (the amount precedes the label on the flattened line) | **yes** | 354 rows, only 22 carry a parsed day-terminal balance; opening was inferred from closing, which the H1 check correctly refuses. |
| `wells_fargo` | A (+B on 1) | 3 | **yes** — `Ending daily balance` column printed, only 2–3 of 37–47 rows parsed | conditional | Prints `Average ledger balance` / `Minimum daily balance` = evidence only. Lift depends on recovering the balance column, which the flattening scatters. |
| `rbc` | A + B (+C on 1) | 6 | partly — day-terminal `Balance ($)` printed, ~40% of rows parsed | conditional (geometry) | Flattening merges two postings onto one line, so parsed credit/debit counts disagree with the printed `Total deposits & credits (n)` / `Total cheques & debits (n)`. Fixing row segmentation would likely fix both A and B; not a pure evidence-reading gap. |
| `scotiabank` | A (+B on 2) | 3 | no — per-row `Balance ($)` read on every row (54–213) | conditional | The *amount* columns are shredded (amount fragments land on the balance's line), so the ledger cannot close even with balances present. Needs column recovery, not a doctrine change. |
| `bmo` | A (+B on 2) | 3 | no — `Balance` column read on every row; no grid printed | **no** | One template family across three months (`BANK STATEMENT`, `Statement Period: <Month> <Year>`, `Account Summary` / `Transaction Details`, footer `Page n - Transactions a-b`). The document's **own** printed arithmetic does not close (`summary_math_inconsistent`, `conflicting_statement_summaries`, printed running balances contradict printed amounts). Withheld is the honest outcome. |
| `atb` | D + A + B | 2 | n/a — per-row `Balance ($)` read in full, but the file is not one statement | **yes, after segmentation** | Each PDF concatenates 5–6 consecutive monthly ATB `Deposit Account Statement`s (each with its own `Statement date`, `Page number k of n`, `balance forward on`, `closing balance on`). 444/476 and 514/546 rows fall outside the first period. One document, many printed periods — the doctrine's "one ADB over the printed period" needs a segmentation decision first. This is the open ATB escalation. |
| `farmers_merchants` | E | 3 | no grid, no row balances — but the printed period, `Previous Balance`, `Ending Balance` and `Days in the statement period` are all unread | **yes for the header; ADB still conditional** | Core-processor `Image Statement` family: the whole summary block is flattened onto one line, so the reader produces dated rows with no period and no opening and returns before any validation. Also prints `Average Ledger` / `Average Collected` = evidence only. After the header is read the ADB still has to reconcile. |
| `capital_one` | D + A + B | 1 | no — `Resulting Balance` read on every row | conditional | A row dated the previous-balance day is printed inside the activity table. The declared initialization-event path does not apply (opening is nonzero), so today's refusal is correct; any lift is a doctrine question, not a reading gap. |
| `relay` | D + A | 1 | no — per-row `Balance` read on every row | conditional | Thread Bank / Relay furniture (`SUMMARY`, `Opening Balance`/`Closing Balance`, `Name Date Status Amount Balance`). One settled row dated the day after period end is printed in the table. |
| `citizens` | A | 1 | **yes** — `Daily Balance / Date Balance` grid, 19 grid dates == 19 parsed posting days; 0 read | **yes** | Scanned but the grid OCRs cleanly. Prints its own qualifying average daily balance = evidence only. Line-item credit capture is 0% of the stated total, which is why the ledger cannot close — the grid bypasses that. |
| `southside_scanned` | A | 1 | **yes, but unusable** — `** DAILY BALANCE SUMMARY ***` grid printed, dates OCR-garbled | **no** | Grid date tokens come through corrupted; publishing from them would not be deterministic evidence. Honest withhold. |

**Doctrine note on the "yes" rows.** A printed daily-balance grid or a printed day-terminal balance column is *primary daily evidence*, not a bank average — reading it is not the "bank averages are evidence only" prohibition. The safe, checkable rule these groups all satisfy is: the printed day set covers every posting day, the series is anchored at the printed opening and its last entry equals the printed closing, and non-activity days carry forward. That yields exactly one user-facing calendar-day ADB over the printed period. Where the grid is absent, garbled, self-contradictory, or the file prints more than one period (bmo, southside, regions-scanned, atb pre-segmentation), withheld remains the honest outcome.

## Per-document list

| sha16 | parser | cause | evidence seen |
|---|---|---|---|
| 72D259CA8B8A9C1B | bmo | A+B | row Balance read 57/57; no grid; printed summary self-inconsistent; declared page labels absent |
| 009BCF1055FBE62E | bmo | A | row Balance read 55/55; no grid; captured credits exceed the stated credit total |
| AE953B1A2E4129F8 | bmo | A+B | row Balance read 57/57; no grid; printed running balances contradict printed amounts |
| 36B502B81C5D4BCA | navy_federal | C | Balance($) 268/268; missing date = printed `Beginning Balance` boundary row (false positive) |
| 60B0EE6AF00F874D | navy_federal | C | Balance($) 216/216; one missing date = `Ending Balance` row, one = a real posting folded onto the embedded card date |
| 6F3DEB4D5CBA5A42 | navy_federal | C | Balance($) 156/156; both missing dates are real POS postings folded onto their embedded card dates |
| 74F34B80B54E159B | navy_federal | C | Balance($) 260/260; both missing dates = `Beginning Balance` / `Ending Balance` rows; prints Average Daily Balance (evidence only) |
| 538375B8A6BD9D8F | capital_one | D+A+B | `Resulting Balance` 137/137; one activity row dated the previous-balance day |
| 675EB43935FEDA73 | citizens | A | `Daily Balance` grid 19 dates == 19 posting days, unread; row balances none; stated qualifying average printed |
| BE703D525955253C | pnc | A | `Daily Balance` grid printed (columns shredded by flattening), unread; credit capture 0% of stated |
| 5684857C24B79344 | pnc | A+C | `Daily Balance` grid printed, unread; credit capture 0% |
| 4145E2C82C6B8329 | pnc | A+C | `Daily Balance` grid printed (12 dates recovered), unread; credit capture 24% |
| 1F31588B36B2E4AF | pnc | A | scanned; `Daily Balance` grid reads cleanly (8 dated pairs vs 6 parsed days), unread; debit capture 95% |
| 7F33CCF581D23CCC | community_section | B | `Daily Balances` grid 20 dates == 20 posting days, unread; 19/80 rows carry a balance; breaks on check rows |
| D0DE1BF0A19D53A2 | community_section | B | `Ending Daily Balances` grid 23 dates == 23 posting days, unread; breaks on check + return-item rows |
| D47263FDFC86F6C3 | community_section | B | grid 21 == 21 posting days, unread; single break on a check row |
| F2931E93870A04AB | community_section | B | grid 22 vs 21 posting days, unread; two breaks on check rows |
| 31F347BE1494314F | community_section | C | grid 24 dated pairs vs 23 posting days, unread; missing date is the `Interest Rate Changes` line (false positive) |
| C6E5B0D3EA9F857B | community_section | C | grid 23 pairs vs 22 posting days, unread; same interest-rate-line false positive |
| 5F1CC8C0198DB4EB | community_section | C | grid 27 pairs vs 26 posting days, unread; same false positive |
| 142E1DB7CB103EFB | rbc | A+B | day-terminal Balance printed; 45/107 rows parsed; merged postings on one line; count mismatches vs printed totals |
| B834D69701C0D40D | rbc | A+B | 44/107 parsed balances; same merge defect |
| 503DDEE755E7A4AD | rbc | A+B | 37/90 parsed balances; same |
| 16174BD143C4702D | rbc | A+B+C | 47/114 parsed balances; 2 source posting dates unmatched |
| FD82EBEFDCBD3FA5 | rbc | A+B | 40/104 parsed balances; same |
| 42405BDA7E97986B | rbc | A+B | 34/57 parsed balances; same |
| B4855A59F6E14D58 | regions | A | scanned; **no** grid and no row balances printed; a declared page is absent |
| 05B4557681329483 | regions | A | `DAILY BALANCE SUMMARY` grid 15 == 15 posting days, unread |
| 6439032B2446B5DF | regions | A | grid 16 == 16 posting days, unread |
| EB2D2C7B04B6A7EA | regions | A | grid 16 vs 15 posting days, unread |
| B52CDF2BA874BBB4 | scotiabank | A+B | row Balance 213/213 read; amount columns shredded; count mismatches vs printed section totals |
| D00562176BEC0AAE | scotiabank | A | row Balance 185/185; printed summary itself does not close |
| 125127F359039F2F | scotiabank | A+B | row Balance 54/54; debit count mismatch |
| 59BD662C0D4FE1A7 | td_canada_french | A | day-terminal SOLDE printed 21/21 posting days, **0 read**; credit capture 94% |
| 654AB29A910A5DB9 | td_canada_french | A | same family; 0 balances read; credit capture 94% |
| A3A50C108B7F4646 | td_canada_french | A | SOLDE printed 22/22, 0 read; credit capture 95% |
| 4DE22E685A04F9D7 | td_canada_french | A | SOLDE printed 20/20, 0 read; credit/debit count mismatch |
| 6E2635D8B95E51B0 | td_canada_native | A | BALANCE printed on 7/7 date tokens, 0 read; BALANCE FORWARD printed |
| 477E2FD610A1C4A8 | td_canada_native | A | BALANCE printed on 13 of 16 date tokens, 0 read |
| 5E682B9B2C697A80 | td_canada_native | A | BALANCE column printed, 0 read; credit capture 83% |
| F841051765A5ABDB | td_canada_native | A | BALANCE column printed, 0 read |
| 21C3FFF212E9E61D | td_canada_native | A | BALANCE column printed, 0 read; credit capture 85% |
| EA5C61862BB8DA56 | td_canada_native | A | BALANCE column printed, 0 read; 264 rows, count mismatches |
| D3396D14BA8A6A4A | td_us | A+C | `DAILY BALANCE SUMMARY` grid 19 dates, unread; parser reached only 3 of 18 printed posting days |
| 2A0B516B2C7D652E | td_us | A+C | grid printed (twice, both accounts), unread; 1 folded posting date |
| 1A8B92DC61678F71 | td_us | A | grid 17 == 17 posting days, unread |
| BDA1DE2F3481295F | td_us | A | grid printed, unread; credit capture 0% of stated |
| 4D7CD4EBDA968759 | relay | D+A | row Balance 39/39; one settled row dated the day after period end |
| 7F2B71AFDD7F901F | atb | D+A+B | 5 monthly statements concatenated (Jan–May), each with its own balance forward/closing; 444/476 rows out of the first period |
| 1B6768E84D00C4B2 | atb | D+A+B | 6 monthly statements concatenated (Jan–Jun); 514/546 rows out of period |
| B311029716C1206F | southside_scanned | A | `** DAILY BALANCE SUMMARY ***` grid printed but date tokens OCR-garbled; credit capture 82% |
| 5BE3147453261138 | farmers_merchants | E | printed `Statement Dates`, `Previous Balance`, `Ending Balance`, `Days in the statement period` all on one flattened line, all unread; no period, no opening → early return |
| DAC9ED50E290AC71 | farmers_merchants | E | same family, same unread summary line |
| 4CC3DE36B4895660 | farmers_merchants | E | same family, same unread summary line |
| 4BE21534DC540342 | wells_fargo | C | `Ending daily balance` column, 18/37 rows read; missing date sourced from a marketing sentence (false positive) |
| 59FAF1FC17745A6E | wells_fargo | A | `Ending daily balance` printed, only 2/47 rows read; debit capture 146% of stated |
| A4E41C80E7362D58 | wells_fargo | F+B | printed `Beginning balance on 6/1` unread (amount precedes the label); 22/354 rows carry a balance |
| 3725BB1189EA74D5 | wells_fargo | A | `Ending daily balance` printed, 3/41 rows read; credit capture 96% |
| 938D4BEBF401A03D | wells_fargo | A+B | `Ending daily balance` printed, 2/37 rows read |
| 1019F3C638AB1C81 | zions | C | dot-leader `Date....Balance` grid **read** (12 snapshots); missing date is a row of the second account's grid (false positive) |
| 595137FD1861DCCD | zions | C | grid read (17 snapshots); missing date is the page-header statement-date line (false positive) |

**Ranking of deterministic lift, by size and safety:** (1) TD Canada native + French, 10 docs — printed day-terminal balances, none read; (2) the sectioned community family, 7 docs — a clean printed `Ending Daily Balances` grid, none read; (3) TD US 4 + Regions digital 3 + PNC 4 + Citizens 1 — printed grids, none read (PNC needs column geometry); (4) the 6 `source_posting_dates` false positives (2 Navy Federal, 3 community_section, 1 Wells Fargo) plus both Zions — no evidence gap at all, only the heuristic; (5) Wells Fargo `A4E41C80` — an unread printed opening balance. That is roughly 30–34 of the 61 with a defensible deterministic path; bmo (3), regions-scanned (1), southside (1) and the ATB pair (until segmented) are honest withholds under the doctrine as written.