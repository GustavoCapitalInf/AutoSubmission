# Batch-9 census — the 784 non-validated shas of run `2026-08-28T22:46:40.553059+00:00-cda8882d`

Produced by `tools/batch9_census.py` (deterministic; read-only; no parser, OCR or model run) over `discovery_reports\TRAIN8-7185633\2026-08-28T224640.553059-0000-cda8882d` and its cold cache `.claude\recovery\webapp_data_train8_cold`. Batch-8 census sha lists read from `10cc722` (598 shas, 12 duplicate assignments). Per-sha data: `census_batch9/per_sha.csv` (77 columns); cluster membership: `census_batch9/clusters.json`. Documents are named by sha; no document text, amount, name or account number is reproduced. Estimates (yield / difficulty / cost) live in `census_batch9/opportunity_estimates.json` and are rendered under their own heading — they are Ocean's judgement, not this instrument's measurement.

## Population reconciliation

| | count |
|---|---:|
| shas in the run | 3380 |
| validated | 2596 |
| review | 18 |
| withheld | 55 |
| failed | 698 |
| deferred | 13 |
| **non-validated (census population)** | **784** |

| outcome / reason | docs | native | ocr_tesseract | none |
|---|---:|---:|---:|---:|
| failed/no_parser_matched | 557 | 560 | 122 | 16 |
| failed/parser_declined | 125 | 560 | 122 | 16 |
| withheld/withheld_adb | 55 | 39 | 16 | 0 |
| review/integrity_flags | 18 | 13 | 5 | 0 |
| failed/invalid_pdf | 16 | 560 | 122 | 16 |
| deferred/deferred_visual_ocr | 13 | 0 | 0 | 13 |

(route columns are per outcome CLASS, repeated on each reason row of that class)

| failure stage | docs |
|---|---:|
| dispatch:unclaimed | 557 |
| dispatch:declined | 125 |
| analysis:adb-withheld | 55 |
| analysis:integrity-review | 18 |
| preflight | 16 |
| ocr:no-text | 13 |

## Classification rules (fixed)

1. `PF-INVALID-PDF` — preflight `invalid_pdf`/`encrypted`.
2. `OCR-NEGATIVE` — `deferred_visual_ocr`: local Tesseract produced no text (cached negative artifact).
3. `WH:<parser>:<codes>` — withheld; codes are the batch-8 withheld census's letters for the ADB checks that failed (A ledger/closing, B running balances, C posting-date coverage, D out-of-period, E no validations run, F opening), raw check names otherwise.
4. `RV:<parser>:<flags>` — review; the integrity flags as emitted.
5. `DECL:<parser>` — `parser_declined`: a registration claimed at detection and its `parse` returned None.
6. `FAM:<key>` — `no_parser_matched` sha listed under a batch-8 census family / singleton (committed artifact).
7. `TEXT-LAYER-DEFECT`, `NOT-STATEMENT`, `NO-TEXT` — the batch-8 census's own lists; `NO-TEXT` also when the OCR artifact holds 0 characters.
8. `SCAN-UNCLAIMED:<hint>` / `DIG-UNCLAIMED-NEW:<hint>` — unclaimed shas the batch-8 census (digital only) never saw; hint = the human folder label when the folder is a bank, else the single registry bank label found on the first text page, else `unknown`.

`layout_family` is a census family key or `unknown`; `bank_hint` is a folder label or a registry label, never a token read out of the document. Near-miss scores are recorded but never used for identity (a score < 0.5 means not every required marker fired).

## Cluster groups (ranked by size)

| cluster group | docs | outcomes | route | text density | in batch-8 census | batch-8 movement | bank hints (top) | fine clusters |
|---|---:|---|---|---|---:|---|---|---:|
| `NOT-STATEMENT` | 117 | failed/no_parser_matched 117 | native 117 | medium 44, thin 37, dense 36 | 117 | unchanged 117 | unknown 44, Bank of America 16, Chase 7, Scotiabank 6, … (+27) | 2 |
| `SCAN-UNCLAIMED` | 89 | failed/no_parser_matched 89 | ocr_tesseract 89 | thin 51, dense 25, medium 13 | 0 | unchanged 89 | unknown 25, TD Bank 12, Wells Fargo 6, Chase 5, … (+23) | 27 |
| `DECL:core_processor_sectioned` | 22 | failed/parser_declined 22 | ocr_tesseract 14, native 8 | dense 17, medium 4, thin 1 | 0 | unchanged 22 | unknown 18, Square 4 | 1 |
| `PF-INVALID-PDF` | 16 | failed/invalid_pdf 16 | none 16 | none 16 | 0 | unchanged 16 | Desjardins 11, unknown 4, TD Bank 1 | 1 |
| `FAM:cu_summary_of_accounts_date_posted` | 13 | failed/no_parser_matched 13 | native 13 | dense 11, medium 2 | 13 | unchanged 13 | unknown 13 | 1 |
| `OCR-NEGATIVE` | 13 | deferred/deferred_visual_ocr 13 | none 13 | none 13 | 0 | unchanged 13 | Bank of America 3, unknown 3, Chase 2, BMO 1, … (+4) | 1 |
| `DECL:huntington` | 12 | failed/parser_declined 12 | native 12 | dense 12 | 0 | unchanged 12 | Huntington Bank 12 | 1 |
| `FAM:american_savings_bank_hawaii` | 11 | failed/no_parser_matched 11 | native 11 | medium 8, thin 2, dense 1 | 11 | unchanged 11 | Chase 10, unknown 1 | 1 |
| `DECL:community_section` | 9 | failed/parser_declined 9 | native 9 | dense 8, thin 1 | 0 | unchanged 9 | unknown 4, Rogue Credit Union 3, Chase 2 | 1 |
| `DECL:core_processor_enclosures` | 9 | failed/parser_declined 9 | native 6, ocr_tesseract 3 | dense 5, medium 4 | 6 | unchanged 9 | unknown 7, Community Bank 2 | 1 |
| `DECL:lili` | 9 | failed/parser_declined 9 | native 9 | dense 8, medium 1 | 9 | unchanged 9 | Lili 7, Bluevine 1, unknown 1 | 1 |
| `FAM:mountain_america_cu_dot_leader` | 9 | failed/no_parser_matched 9 | native 9 | dense 9 | 9 | unchanged 9 | unknown 4, Bluevine 2, Capital One 2, Square 1 | 1 |
| `WH:frost` | 9 | withheld/withheld_adb 9 | native 9 | dense 9 | 9 | improved 9 | Frost Bank 5, unknown 3, Wells Fargo 1 | 2 |
| `FAM:cu_idaho_equation_summary` | 8 | failed/no_parser_matched 8 | native 8 | dense 6, medium 2 | 8 | unchanged 8 | unknown 5, Bluevine 2, American Express 1 | 1 |
| `FAM:cu_unq_clt_trailing_minus_totals` | 8 | failed/no_parser_matched 8 | native 8 | dense 8 | 8 | unchanged 8 | unknown 8 | 1 |
| `FAM:guardian_cu_statement_summary` | 8 | failed/no_parser_matched 8 | native 8 | dense 8 | 8 | unchanged 8 | Square 4, unknown 4 | 1 |
| `FAM:space_coast_cu_member_statement` | 8 | failed/no_parser_matched 8 | native 8 | dense 8 | 8 | unchanged 8 | Space Coast Credit Union 4, unknown 4 | 1 |
| `FAM:wpcu_summary_of_account_by_transaction` | 8 | failed/no_parser_matched 8 | native 8 | dense 8 | 8 | unchanged 8 | Wright-Patt Credit Union 4, unknown 2, Capital One 1, Chase 1 | 1 |
| `TEXT-LAYER-DEFECT` | 8 | failed/no_parser_matched 8 | native 8 | thin 5, medium 2, dense 1 | 8 | unchanged 8 | RBC 4, Bank of America 1, Central Bank 1, Chase 1, … (+1) | 1 |
| `FAM:paypal_account_statements` | 7 | failed/no_parser_matched 7 | native 7 | dense 7 | 7 | unchanged 7 | Bank of America 4, unknown 3 | 1 |
| `FAM:truist_your_account_statement` | 7 | failed/no_parser_matched 7 | native 7 | dense 7 | 7 | unchanged 7 | Truist 7 | 1 |
| `DECL:bmo_ca_business` | 6 | failed/parser_declined 6 | native 6 | dense 6 | 0 | unchanged 6 | BMO 6 | 1 |
| `DECL:capital_one` | 6 | failed/parser_declined 6 | native 6 | medium 6 | 0 | unchanged 6 | Capital One 6 | 1 |
| `DECL:navy_federal` | 6 | failed/parser_declined 6 | native 6 | dense 6 | 0 | unchanged 6 | unknown 4, Bank of America 2 | 1 |
| `FAM:capital_one_360` | 6 | failed/no_parser_matched 6 | native 6 | dense 3, medium 3 | 6 | unchanged 6 | Capital One 6 | 1 |
| `WH:rbc` | 6 | withheld/withheld_adb 6 | native 6 | medium 6 | 6 | unchanged 6 | RBC 6 | 2 |
| `FAM:altura_riverside_cu` | 5 | failed/no_parser_matched 5 | native 5 | dense 5 | 5 | unchanged 5 | unknown 2, Square 1, U.S. Bank 1, Wells Fargo 1 | 1 |
| `FAM:beem_credit_union_bc` | 5 | failed/no_parser_matched 5 | native 5 | medium 5 | 5 | unchanged 5 | Beem Credit Union 5 | 1 |
| `FAM:chesapeake_bank_activity_in_date_order` | 5 | failed/no_parser_matched 5 | native 5 | dense 5 | 5 | unchanged 5 | Square 5 | 1 |
| `FAM:chime_bancorp_checking` | 5 | failed/no_parser_matched 5 | native 5 | dense 5 | 5 | unchanged 5 | The Bancorp Bank 3, Chime 2 | 1 |
| `FAM:cubase_suffix_box_summary_history` | 5 | failed/no_parser_matched 5 | native 5 | dense 5 | 5 | unchanged 5 | Chase 2, unknown 2, Hercules Credit Union 1 | 1 |
| `FAM:dfcu_financial_account_statement` | 5 | failed/no_parser_matched 5 | native 5 | dense 5 | 5 | unchanged 5 | DFCU Financial 5 | 1 |
| `FAM:old_national_free_business_checking` | 5 | failed/no_parser_matched 5 | native 5 | dense 5 | 5 | unchanged 5 | Old National Bank 5 | 1 |
| `FAM:pr_business_plus_corp_statement_of_account` | 5 | failed/no_parser_matched 5 | native 5 | dense 5 | 5 | unchanged 5 | unknown 5 | 1 |
| `FAM:rbfcu_business_member_statement` | 5 | failed/no_parser_matched 5 | native 5 | dense 5 | 5 | unchanged 5 | unknown 5 | 1 |
| `FAM:wescom_cu_equation_summary` | 5 | failed/no_parser_matched 5 | native 5 | dense 5 | 5 | unchanged 5 | unknown 5 | 1 |
| `WH:southside_scanned` | 5 | withheld/withheld_adb 5 | ocr_tesseract 5 | dense 5 | 1 | unchanged 5 | unknown 3, Capital One 1, Chase 1 | 1 |
| `DECL:columbia_bank` | 4 | failed/parser_declined 4 | ocr_tesseract 4 | dense 4 | 0 | unchanged 4 | Columbia Bank 4 | 1 |
| `DECL:core_processor_daily` | 4 | failed/parser_declined 4 | ocr_tesseract 4 | dense 4 | 0 | unchanged 4 | City Bank 4 | 1 |
| `FAM:access_fcu_member_statement_of_account` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 3, Capital One 1 | 1 |
| `FAM:associated_bank_financial_statement_of_accounts` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | Associated Bank 4 | 1 |
| `FAM:atb_financial_consolidated_statement` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | ATB Financial 4 | 1 |
| `FAM:bank7_summary_of_accounts` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:bank_of_tennessee_activity_summary` | 4 | failed/no_parser_matched 4 | native 4 | medium 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:becu_deposit_and_loan_activity` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:bokf_business_access` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | Square 4 | 1 |
| `FAM:city_national_bank_florida` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | City National Bank 4 | 1 |
| `FAM:commerce_bank_mybusiness_checking` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | Commerce Bank 4 | 1 |
| `FAM:community_savings_bc` | 4 | failed/no_parser_matched 4 | native 4 | medium 3, dense 1 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:cu_statement_summary_prev_new_balance_unbranded` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:fulton_bank_account_statement` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | Citizens Bank 4 | 1 |
| `FAM:goldenwest_cu_member_account_statement` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:greater_nevada_cu` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | Capital One 4 | 1 |
| `FAM:green_dot_bank_partner_program` | 4 | failed/no_parser_matched 4 | native 4 | medium 4 | 4 | unchanged 4 | Green Dot Bank 4 | 1 |
| `FAM:hapo_cu_estatement` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:ion_bank_customer_statement` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:jh_spaced_caps_checking_summary` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:nbkc_bank_dda_statement` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | NBKC Bank 4 | 1 |
| `FAM:novo_monthly_account_statement` | 4 | failed/no_parser_matched 4 | native 4 | medium 4 | 4 | unchanged 4 | Square 4 | 1 |
| `FAM:ornl_fcu_oak_ridge` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:palmetto_citizens_cu` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:pnc_core_commercial_checking` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | PNC Bank 4 | 1 |
| `FAM:pnc_treasury_enterprise_plan` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | PNC Bank 4 | 1 |
| `FAM:pnc_virtual_wallet_performance_spend` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | PNC Bank 4 | 1 |
| `FAM:psecu_shares_at_a_glance` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | The Bancorp Bank 4 | 1 |
| `FAM:redstone_fcu_statement_of_accounts` | 4 | failed/no_parser_matched 4 | native 4 | dense 3, medium 1 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:security_service_fcu_asterisk_sections` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:sierra_central_cu` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:st_marys_bank_nh` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:suncoast_cu_account_statement` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:synovus_pinnacle_portal_statement_view` | 4 | failed/no_parser_matched 4 | native 4 | medium 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:townebank_balance_summary` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:usaa_fsb_classic_checking` | 4 | failed/no_parser_matched 4 | native 4 | medium 3, dense 1 | 4 | unchanged 4 | USAA 4 | 1 |
| `FAM:vystar_balance_summary_transactional_detail` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:vystar_business_checking_analyzed` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `FAM:wisely_adp_paycard` | 4 | failed/no_parser_matched 4 | native 4 | dense 4 | 4 | unchanged 4 | unknown 4 | 1 |
| `RV:chase_export` | 4 | review/integrity_flags 4 | native 3, ocr_tesseract 1 | medium 4 | 0 | unchanged 4 | Chase 4 | 1 |
| `RV:linkbank` | 4 | review/integrity_flags 4 | native 4 | dense 4 | 0 | unchanged 4 | LINKBANK 4 | 1 |
| `WH:bmo` | 4 | withheld/withheld_adb 4 | native 4 | dense 4 | 3 | unchanged 4 | BMO 4 | 2 |
| `WH:pnc` | 4 | withheld/withheld_adb 4 | native 3, ocr_tesseract 1 | dense 4 | 4 | unchanged 4 | PNC Bank 4 | 2 |
| `WH:wells_fargo` | 4 | withheld/withheld_adb 4 | native 4 | dense 4 | 4 | unchanged 4 | Wells Fargo 4 | 3 |
| `DECL:category_partition` | 3 | failed/parser_declined 3 | native 3 | medium 2, dense 1 | 3 | unchanged 3 | unknown 3 | 1 |
| `DECL:consumers` | 3 | failed/parser_declined 3 | native 3 | dense 3 | 0 | unchanged 3 | unknown 3 | 1 |
| `DECL:scotiabank` | 3 | failed/parser_declined 3 | native 3 | medium 3 | 0 | unchanged 3 | unknown 3 | 1 |
| `DECL:texas_first_scanned` | 3 | failed/parser_declined 3 | ocr_tesseract 3 | medium 3 | 0 | unchanged 3 | Texas First Bank 3 | 1 |
| `DECL:truist` | 3 | failed/parser_declined 3 | native 3 | dense 3 | 0 | unchanged 3 | Truist 3 | 1 |
| `FAM:altra_fcu_statement_summary` | 3 | failed/no_parser_matched 3 | native 3 | dense 3 | 3 | unchanged 3 | unknown 3 | 1 |
| `FAM:bangor_savings_three_count_summary` | 3 | failed/no_parser_matched 3 | native 3 | dense 3 | 3 | unchanged 3 | unknown 3 | 1 |
| `FAM:champion_cu_statement_summary` | 3 | failed/no_parser_matched 3 | native 3 | dense 3 | 3 | unchanged 3 | unknown 2, Capital One 1 | 1 |
| `FAM:core_enclosures_avgledger_leading_counts` | 3 | failed/no_parser_matched 3 | native 3 | dense 3 | 3 | unchanged 3 | unknown 2, Square 1 | 1 |
| `FAM:eastern_bank_customer_statement` | 3 | failed/no_parser_matched 3 | native 3 | dense 3 | 3 | unchanged 3 | unknown 3 | 1 |
| `FAM:greenstate_cu_post_eff_type` | 3 | failed/no_parser_matched 3 | native 3 | dense 3 | 3 | unchanged 3 | GreenState Credit Union 3 | 1 |
| `FAM:heritage_south_cu` | 3 | failed/no_parser_matched 3 | native 3 | dense 3 | 3 | unchanged 3 | unknown 3 | 1 |
| `FAM:hudson_valley_fcu` | 3 | failed/no_parser_matched 3 | native 3 | dense 3 | 3 | unchanged 3 | Hudson Valley Federal Credit Union 3 | 1 |
| `FAM:mt_bank_account_activity_daily_balance` | 3 | failed/no_parser_matched 3 | native 3 | dense 3 | 3 | unchanged 3 | unknown 3 | 1 |
| `FAM:mt_bank_customer_statement_treasury` | 3 | failed/no_parser_matched 3 | native 3 | medium 2, thin 1 | 3 | unchanged 3 | unknown 2, USAA 1 | 1 |
| `FAM:pima_fcu_statement_of_account` | 3 | failed/no_parser_matched 3 | native 3 | dense 3 | 3 | unchanged 3 | Square 2, unknown 1 | 1 |
| `RV:found_lead_activity` | 3 | review/integrity_flags 3 | native 3 | medium 3 | 0 | unchanged 3 | Lead Bank 3 | 1 |
| `WH:citizens` | 3 | withheld/withheld_adb 3 | ocr_tesseract 3 | dense 3 | 1 | unchanged 3 | Citizens Bank 3 | 1 |
| `WH:eq_bank_scanned` | 3 | withheld/withheld_adb 3 | ocr_tesseract 3 | dense 2, medium 1 | 0 | unchanged 3 | TD Bank 3 | 1 |
| `WH:farmers_merchants` | 3 | withheld/withheld_adb 3 | native 3 | medium 3 | 3 | unchanged 3 | unknown 3 | 1 |
| `WH:scotiabank` | 3 | withheld/withheld_adb 3 | native 3 | medium 3 | 3 | unchanged 3 | Scotiabank 3 | 2 |
| `WH:td_us` | 3 | withheld/withheld_adb 3 | ocr_tesseract 3 | dense 3 | 3 | unchanged 3 | TD Bank 3 | 2 |
| `DECL:banco_popular` | 2 | failed/parser_declined 2 | native 2 | dense 2 | 0 | unchanged 2 | unknown 2 | 1 |
| `DECL:bank_of_america` | 2 | failed/parser_declined 2 | native 2 | dense 1, thin 1 | 0 | unchanged 2 | Bank of America 2 | 1 |
| `DECL:bluevine` | 2 | failed/parser_declined 2 | native 2 | medium 2 | 0 | unchanged 2 | Bluevine 2 | 1 |
| `DECL:eq_bank_scanned` | 2 | failed/parser_declined 2 | ocr_tesseract 2 | dense 1, medium 1 | 0 | unchanged 2 | TD Bank 2 | 1 |
| `DECL:ibc` | 2 | failed/parser_declined 2 | native 2 | dense 2 | 0 | unchanged 2 | unknown 2 | 1 |
| `DECL:santander` | 2 | failed/parser_declined 2 | native 2 | dense 2 | 0 | unchanged 2 | Santander 2 | 1 |
| `DECL:td_us` | 2 | failed/parser_declined 2 | native 1, ocr_tesseract 1 | dense 2 | 0 | unchanged 2 | TD Bank 2 | 1 |
| `FAM:firstbank_colorado` | 2 | failed/no_parser_matched 2 | native 2 | dense 2 | 2 | unchanged 2 | unknown 2 | 1 |
| `FAM:firstbank_pr_escrow_pipe_header` | 2 | failed/no_parser_matched 2 | native 2 | medium 2 | 2 | unchanged 2 | unknown 2 | 1 |
| `FAM:umb_essential_business_checking` | 2 | failed/no_parser_matched 2 | native 2 | dense 2 | 2 | unchanged 2 | UMB Bank 2 | 1 |
| `RV:community_section` | 2 | review/integrity_flags 2 | native 2 | dense 2 | 0 | unchanged 2 | unknown 2 | 1 |
| `RV:southside_scanned` | 2 | review/integrity_flags 2 | ocr_tesseract 2 | dense 1, medium 1 | 0 | unchanged 2 | unknown 2 | 1 |
| `WH:atb` | 2 | withheld/withheld_adb 2 | native 2 | dense 2 | 2 | unchanged 2 | ATB Financial 2 | 1 |
| `DECL:apex_scanned` | 1 | failed/parser_declined 1 | ocr_tesseract 1 | medium 1 | 0 | unchanged 1 | Apex Bank 1 | 1 |
| `DECL:chase` | 1 | failed/parser_declined 1 | native 1 | thin 1 | 0 | unchanged 1 | Chase 1 | 1 |
| `DECL:cibc_french` | 1 | failed/parser_declined 1 | native 1 | thin 1 | 0 | unchanged 1 | CIBC 1 | 1 |
| `DECL:first_farmers` | 1 | failed/parser_declined 1 | ocr_tesseract 1 | dense 1 | 0 | unchanged 1 | unknown 1 | 1 |
| `DECL:pnc` | 1 | failed/parser_declined 1 | native 1 | dense 1 | 0 | unchanged 1 | PNC Bank 1 | 1 |
| `DECL:rbc` | 1 | failed/parser_declined 1 | native 1 | medium 1 | 0 | unchanged 1 | RBC 1 | 1 |
| `DECL:wealthsimple` | 1 | failed/parser_declined 1 | native 1 | thin 1 | 0 | unchanged 1 | Wealthsimple 1 | 1 |
| `DECL:welch_state_bank` | 1 | failed/parser_declined 1 | native 1 | dense 1 | 1 | unchanged 1 | unknown 1 | 1 |
| `DECL:woodforest` | 1 | failed/parser_declined 1 | native 1 | dense 1 | 0 | unchanged 1 | unknown 1 | 1 |
| `FAM:bofa_business_advantage` | 1 | failed/no_parser_matched 1 | native 1 | medium 1 | 1 | unchanged 1 | Bank of America 1 | 1 |
| `FAM:chase_total_checking_transaction_detail` | 1 | failed/no_parser_matched 1 | native 1 | dense 1 | 1 | unchanged 1 | Chase 1 | 1 |
| `FAM:conexus_cu_demand_products` | 1 | failed/no_parser_matched 1 | native 1 | dense 1 | 1 | unchanged 1 | unknown 1 | 1 |
| `FAM:cu_suffix_transfer_acct_grid` | 1 | failed/no_parser_matched 1 | native 1 | dense 1 | 1 | unchanged 1 | unknown 1 | 1 |
| `FAM:desjardins_accesd_releve_operations` | 1 | failed/no_parser_matched 1 | native 1 | dense 1 | 1 | unchanged 1 | Desjardins 1 | 1 |
| `FAM:laurentian_bank_current_account` | 1 | failed/no_parser_matched 1 | native 1 | dense 1 | 1 | unchanged 1 | Desjardins 1 | 1 |
| `FAM:onepay_coastal_community_monthly` | 1 | failed/no_parser_matched 1 | native 1 | medium 1 | 1 | unchanged 1 | Coastal Community Bank 1 | 1 |
| `FAM:pc_financial_pc_money_account` | 1 | failed/no_parser_matched 1 | native 1 | dense 1 | 1 | unchanged 1 | unknown 1 | 1 |
| `FAM:ramp_business_account` | 1 | failed/no_parser_matched 1 | native 1 | medium 1 | 1 | unchanged 1 | TD Bank 1 | 1 |
| `FAM:relationship_summary_daily_balance_unbranded` | 1 | failed/no_parser_matched 1 | native 1 | medium 1 | 1 | unchanged 1 | unknown 1 | 1 |
| `FAM:rho_deposit_account_statement` | 1 | failed/no_parser_matched 1 | native 1 | dense 1 | 1 | unchanged 1 | Brex 1 | 1 |
| `FAM:southern_bank_quadruplicated` | 1 | failed/no_parser_matched 1 | native 1 | dense 1 | 1 | unchanged 1 | Southern Bank 1 | 1 |
| `NO-TEXT` | 1 | failed/no_parser_matched 1 | native 1 | thin 1 | 1 | unchanged 1 | BMO 1 | 1 |
| `RV:citizens` | 1 | review/integrity_flags 1 | ocr_tesseract 1 | dense 1 | 0 | unchanged 1 | Citizens Bank 1 | 1 |
| `RV:core_processor_enclosures` | 1 | review/integrity_flags 1 | native 1 | dense 1 | 1 | improved 1 | unknown 1 | 1 |
| `RV:texas_first_scanned` | 1 | review/integrity_flags 1 | ocr_tesseract 1 | dense 1 | 0 | unchanged 1 | Texas First Bank 1 | 1 |
| `WH:capital_one` | 1 | withheld/withheld_adb 1 | native 1 | dense 1 | 1 | unchanged 1 | Capital One 1 | 1 |
| `WH:core_processor_enclosures` | 1 | withheld/withheld_adb 1 | native 1 | dense 1 | 1 | improved 1 | Chase 1 | 1 |
| `WH:ibc` | 1 | withheld/withheld_adb 1 | native 1 | dense 1 | 0 | unchanged 1 | unknown 1 | 1 |
| `WH:regions` | 1 | withheld/withheld_adb 1 | ocr_tesseract 1 | dense 1 | 1 | unchanged 1 | Regions Bank 1 | 1 |
| `WH:relay` | 1 | withheld/withheld_adb 1 | native 1 | dense 1 | 1 | unchanged 1 | Thread Bank 1 | 1 |
| `WH:zions` | 1 | withheld/withheld_adb 1 | native 1 | dense 1 | 1 | unchanged 1 | Zions Bank 1 | 1 |

## Institution roll-up (shared root cause: one reader per institution)

Across FAM / DECL / WH / RV / SCAN groups (non-document groups excluded), keyed by `bank_hint` (human folder label, else the single registry label on the first text page).

| institution (hint) | docs | by kind | readers involved | census families |
|---|---:|---|---|---|
| unknown | 270 | FAM 180, DECL 50, SCAN-UNCLAIMED 25, WH 10, RV 5 | core_processor_sectioned 18, core_processor_enclosures 8, community_section 6, southside_scanned 5, … (+12) | cu_summary_of_accounts_date_posted 13, core_enclosures_avgledger_leading_counts 9, cu_unq_clt_trailing_minus_totals 8, … (+52) |
| Chase | 28 | FAM 14, SCAN-UNCLAIMED 5, RV 4, DECL 3, WH 2 | chase_export 4, community_section 2, chase 1, core_processor_enclosures 1, … (+1) | american_savings_bank_hawaii 10, cubase_suffix_box_summary_history 2, chase_total_checking_transaction_detail 1, … (+2) |
| Square | 28 | FAM 22, DECL 4, SCAN-UNCLAIMED 2 | core_processor_sectioned 4 | chesapeake_bank_activity_in_date_order 5, bokf_business_access 4, guardian_cu_statement_summary 4, … (+5) |
| Capital One | 24 | FAM 15, DECL 6, WH 2, SCAN-UNCLAIMED 1 | capital_one 7, southside_scanned 1 | capital_one_360 6, greater_nevada_cu 4, mountain_america_cu_dot_leader 2, … (+3) |
| TD Bank | 23 | SCAN-UNCLAIMED 12, WH 6, DECL 4, FAM 1 | eq_bank_scanned 5, td_us 5 | ramp_business_account 1 |
| PNC Bank | 17 | FAM 12, WH 4, DECL 1 | pnc 5 | pnc_core_commercial_checking 4, pnc_treasury_enterprise_plan 4, pnc_virtual_wallet_performance_spend 4 |
| Bank of America | 13 | FAM 5, DECL 4, SCAN-UNCLAIMED 4 | bank_of_america 2, navy_federal 2 | paypal_account_statements 4, bofa_business_advantage 1 |
| Truist | 13 | FAM 7, DECL 3, SCAN-UNCLAIMED 3 | truist 3 | truist_your_account_statement 7 |
| Huntington Bank | 12 | DECL 12 | huntington 12 | - |
| Wells Fargo | 12 | SCAN-UNCLAIMED 6, WH 5, FAM 1 | wells_fargo 4, frost 1 | altura_riverside_cu 1, frost_bank_business_checking 1 |
| BMO | 11 | DECL 6, WH 4, SCAN-UNCLAIMED 1 | bmo_ca_business 6, bmo 4 | - |
| Citizens Bank | 11 | FAM 4, SCAN-UNCLAIMED 3, WH 3, RV 1 | citizens 4 | fulton_bank_account_statement 4 |
| RBC | 9 | WH 6, SCAN-UNCLAIMED 2, DECL 1 | rbc 7 | - |
| Bluevine | 7 | FAM 4, DECL 3 | bluevine 2, lili 1 | cu_idaho_equation_summary 2, mountain_america_cu_dot_leader 2, lili_sunrise_banks_checking 1 |
| Frost Bank | 7 | WH 5, SCAN-UNCLAIMED 2 | frost 5 | frost_bank_business_checking 5 |
| Lili | 7 | DECL 7 | lili 7 | lili_sunrise_banks_checking 7 |
| The Bancorp Bank | 7 | FAM 7 | - | psecu_shares_at_a_glance 4, chime_bancorp_checking 3 |
| ATB Financial | 6 | FAM 4, WH 2 | atb 2 | atb_financial_consolidated_statement 4 |
| Beem Credit Union | 5 | FAM 5 | - | beem_credit_union_bc 5 |
| Commerce Bank | 5 | FAM 4, SCAN-UNCLAIMED 1 | - | commerce_bank_mybusiness_checking 4 |
| DFCU Financial | 5 | FAM 5 | - | dfcu_financial_account_statement 5 |
| Old National Bank | 5 | FAM 5 | - | old_national_free_business_checking 5 |
| USAA | 5 | FAM 5 | - | usaa_fsb_classic_checking 4, mt_bank_customer_statement_treasury 1 |
| Associated Bank | 4 | FAM 4 | - | associated_bank_financial_statement_of_accounts 4 |
| Central Bank | 4 | SCAN-UNCLAIMED 4 | - | - |
| City Bank | 4 | DECL 4 | core_processor_daily 4 | - |
| City National Bank | 4 | FAM 4 | - | city_national_bank_florida 4 |
| Columbia Bank | 4 | DECL 4 | columbia_bank 4 | - |
| Green Dot Bank | 4 | FAM 4 | - | green_dot_bank_partner_program 4 |
| LINKBANK | 4 | RV 4 | linkbank 4 | - |
| NBKC Bank | 4 | FAM 4 | - | nbkc_bank_dda_statement 4 |
| Space Coast Credit Union | 4 | FAM 4 | - | space_coast_cu_member_statement 4 |
| Texas First Bank | 4 | DECL 3, RV 1 | texas_first_scanned 4 | - |
| Wright-Patt Credit Union | 4 | FAM 4 | - | wpcu_summary_of_account_by_transaction 4 |
| American Express | 3 | SCAN-UNCLAIMED 2, FAM 1 | - | cu_idaho_equation_summary 1 |
| CIBC | 3 | SCAN-UNCLAIMED 2, DECL 1 | cibc_french 1 | - |
| Community Bank | 3 | DECL 2, SCAN-UNCLAIMED 1 | core_processor_enclosures 2 | - |
| GreenState Credit Union | 3 | FAM 3 | - | greenstate_cu_post_eff_type 3 |
| Hudson Valley Federal Credit Union | 3 | FAM 3 | - | hudson_valley_fcu 3 |
| Lead Bank | 3 | RV 3 | found_lead_activity 3 | - |
| Rogue Credit Union | 3 | DECL 3 | community_section 3 | - |
| Scotiabank | 3 | WH 3 | scotiabank 3 | - |
| Signature Bank | 3 | SCAN-UNCLAIMED 3 | - | - |
| Chime | 2 | FAM 2 | - | chime_bancorp_checking 2 |
| Desjardins | 2 | FAM 2 | - | desjardins_accesd_releve_operations 1, laurentian_bank_current_account 1 |
| … 19 more institutions | | | | |

## Scanned-unclaimed text density (`SCAN-UNCLAIMED`)

| density / hint / pages | docs |
|---|---:|
| thin / hint known / 1 page | 31 |
| thin / hint unknown / 1 page | 11 |
| dense / hint known / 2+ pages | 9 |
| dense / hint known / 1 page | 7 |
| medium / hint known / 1 page | 7 |
| medium / hint known / 2+ pages | 6 |
| dense / hint unknown / 2+ pages | 6 |
| thin / hint unknown / 2+ pages | 5 |
| thin / hint known / 2+ pages | 4 |
| dense / hint unknown / 1 page | 3 |

## Fine clusters (all)

| cluster | docs | group |
|---|---:|---|
| `NOT-STATEMENT:other` | 104 | `NOT-STATEMENT` |
| `SCAN-UNCLAIMED:unknown` | 25 | `SCAN-UNCLAIMED` |
| `DECL:core_processor_sectioned` | 22 | `DECL:core_processor_sectioned` |
| `PF-INVALID-PDF` | 16 | `PF-INVALID-PDF` |
| `FAM:cu_summary_of_accounts_date_posted` | 13 | `FAM:cu_summary_of_accounts_date_posted` |
| `NOT-STATEMENT:portal-export` | 13 | `NOT-STATEMENT` |
| `OCR-NEGATIVE` | 13 | `OCR-NEGATIVE` |
| `DECL:huntington` | 12 | `DECL:huntington` |
| `SCAN-UNCLAIMED:TD Bank` | 12 | `SCAN-UNCLAIMED` |
| `FAM:american_savings_bank_hawaii` | 11 | `FAM:american_savings_bank_hawaii` |
| `DECL:community_section` | 9 | `DECL:community_section` |
| `DECL:core_processor_enclosures` | 9 | `DECL:core_processor_enclosures` |
| `DECL:lili` | 9 | `DECL:lili` |
| `FAM:mountain_america_cu_dot_leader` | 9 | `FAM:mountain_america_cu_dot_leader` |
| `FAM:cu_idaho_equation_summary` | 8 | `FAM:cu_idaho_equation_summary` |
| `FAM:cu_unq_clt_trailing_minus_totals` | 8 | `FAM:cu_unq_clt_trailing_minus_totals` |
| `FAM:guardian_cu_statement_summary` | 8 | `FAM:guardian_cu_statement_summary` |
| `FAM:space_coast_cu_member_statement` | 8 | `FAM:space_coast_cu_member_statement` |
| `FAM:wpcu_summary_of_account_by_transaction` | 8 | `FAM:wpcu_summary_of_account_by_transaction` |
| `TEXT-LAYER-DEFECT` | 8 | `TEXT-LAYER-DEFECT` |
| `FAM:paypal_account_statements` | 7 | `FAM:paypal_account_statements` |
| `FAM:truist_your_account_statement` | 7 | `FAM:truist_your_account_statement` |
| `DECL:bmo_ca_business` | 6 | `DECL:bmo_ca_business` |
| `DECL:capital_one` | 6 | `DECL:capital_one` |
| `DECL:navy_federal` | 6 | `DECL:navy_federal` |
| `FAM:capital_one_360` | 6 | `FAM:capital_one_360` |
| `SCAN-UNCLAIMED:Wells Fargo` | 6 | `SCAN-UNCLAIMED` |
| `WH:frost:bank_daily_balance_dates_valid+statement_period_dates_valid` | 6 | `WH:frost` |
| `FAM:altura_riverside_cu` | 5 | `FAM:altura_riverside_cu` |
| `FAM:beem_credit_union_bc` | 5 | `FAM:beem_credit_union_bc` |
| `FAM:chesapeake_bank_activity_in_date_order` | 5 | `FAM:chesapeake_bank_activity_in_date_order` |
| `FAM:chime_bancorp_checking` | 5 | `FAM:chime_bancorp_checking` |
| `FAM:cubase_suffix_box_summary_history` | 5 | `FAM:cubase_suffix_box_summary_history` |
| `FAM:dfcu_financial_account_statement` | 5 | `FAM:dfcu_financial_account_statement` |
| `FAM:old_national_free_business_checking` | 5 | `FAM:old_national_free_business_checking` |
| `FAM:pr_business_plus_corp_statement_of_account` | 5 | `FAM:pr_business_plus_corp_statement_of_account` |
| `FAM:rbfcu_business_member_statement` | 5 | `FAM:rbfcu_business_member_statement` |
| `FAM:wescom_cu_equation_summary` | 5 | `FAM:wescom_cu_equation_summary` |
| `SCAN-UNCLAIMED:Chase` | 5 | `SCAN-UNCLAIMED` |
| `WH:rbc:A+B` | 5 | `WH:rbc` |
| `WH:southside_scanned:A` | 5 | `WH:southside_scanned` |
| `DECL:columbia_bank` | 4 | `DECL:columbia_bank` |
| `DECL:core_processor_daily` | 4 | `DECL:core_processor_daily` |
| `FAM:access_fcu_member_statement_of_account` | 4 | `FAM:access_fcu_member_statement_of_account` |
| `FAM:associated_bank_financial_statement_of_accounts` | 4 | `FAM:associated_bank_financial_statement_of_accounts` |
| `FAM:atb_financial_consolidated_statement` | 4 | `FAM:atb_financial_consolidated_statement` |
| `FAM:bank7_summary_of_accounts` | 4 | `FAM:bank7_summary_of_accounts` |
| `FAM:bank_of_tennessee_activity_summary` | 4 | `FAM:bank_of_tennessee_activity_summary` |
| `FAM:becu_deposit_and_loan_activity` | 4 | `FAM:becu_deposit_and_loan_activity` |
| `FAM:bokf_business_access` | 4 | `FAM:bokf_business_access` |
| `FAM:city_national_bank_florida` | 4 | `FAM:city_national_bank_florida` |
| `FAM:commerce_bank_mybusiness_checking` | 4 | `FAM:commerce_bank_mybusiness_checking` |
| `FAM:community_savings_bc` | 4 | `FAM:community_savings_bc` |
| `FAM:cu_statement_summary_prev_new_balance_unbranded` | 4 | `FAM:cu_statement_summary_prev_new_balance_unbranded` |
| `FAM:fulton_bank_account_statement` | 4 | `FAM:fulton_bank_account_statement` |
| `FAM:goldenwest_cu_member_account_statement` | 4 | `FAM:goldenwest_cu_member_account_statement` |
| `FAM:greater_nevada_cu` | 4 | `FAM:greater_nevada_cu` |
| `FAM:green_dot_bank_partner_program` | 4 | `FAM:green_dot_bank_partner_program` |
| `FAM:hapo_cu_estatement` | 4 | `FAM:hapo_cu_estatement` |
| `FAM:ion_bank_customer_statement` | 4 | `FAM:ion_bank_customer_statement` |
| `FAM:jh_spaced_caps_checking_summary` | 4 | `FAM:jh_spaced_caps_checking_summary` |
| `FAM:nbkc_bank_dda_statement` | 4 | `FAM:nbkc_bank_dda_statement` |
| `FAM:novo_monthly_account_statement` | 4 | `FAM:novo_monthly_account_statement` |
| `FAM:ornl_fcu_oak_ridge` | 4 | `FAM:ornl_fcu_oak_ridge` |
| `FAM:palmetto_citizens_cu` | 4 | `FAM:palmetto_citizens_cu` |
| `FAM:pnc_core_commercial_checking` | 4 | `FAM:pnc_core_commercial_checking` |
| `FAM:pnc_treasury_enterprise_plan` | 4 | `FAM:pnc_treasury_enterprise_plan` |
| `FAM:pnc_virtual_wallet_performance_spend` | 4 | `FAM:pnc_virtual_wallet_performance_spend` |
| `FAM:psecu_shares_at_a_glance` | 4 | `FAM:psecu_shares_at_a_glance` |
| `FAM:redstone_fcu_statement_of_accounts` | 4 | `FAM:redstone_fcu_statement_of_accounts` |
| `FAM:security_service_fcu_asterisk_sections` | 4 | `FAM:security_service_fcu_asterisk_sections` |
| `FAM:sierra_central_cu` | 4 | `FAM:sierra_central_cu` |
| `FAM:st_marys_bank_nh` | 4 | `FAM:st_marys_bank_nh` |
| `FAM:suncoast_cu_account_statement` | 4 | `FAM:suncoast_cu_account_statement` |
| `FAM:synovus_pinnacle_portal_statement_view` | 4 | `FAM:synovus_pinnacle_portal_statement_view` |
| `FAM:townebank_balance_summary` | 4 | `FAM:townebank_balance_summary` |
| `FAM:usaa_fsb_classic_checking` | 4 | `FAM:usaa_fsb_classic_checking` |
| `FAM:vystar_balance_summary_transactional_detail` | 4 | `FAM:vystar_balance_summary_transactional_detail` |
| `FAM:vystar_business_checking_analyzed` | 4 | `FAM:vystar_business_checking_analyzed` |
| `FAM:wisely_adp_paycard` | 4 | `FAM:wisely_adp_paycard` |
| `RV:chase_export:not_a_formal_statement` | 4 | `RV:chase_export` |
| `RV:linkbank:missing_declared_statement_page` | 4 | `RV:linkbank` |
| `SCAN-UNCLAIMED:Bank of America` | 4 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Central Bank` | 4 | `SCAN-UNCLAIMED` |
| `DECL:category_partition` | 3 | `DECL:category_partition` |
| `DECL:consumers` | 3 | `DECL:consumers` |
| `DECL:scotiabank` | 3 | `DECL:scotiabank` |
| `DECL:texas_first_scanned` | 3 | `DECL:texas_first_scanned` |
| `DECL:truist` | 3 | `DECL:truist` |
| `FAM:altra_fcu_statement_summary` | 3 | `FAM:altra_fcu_statement_summary` |
| `FAM:bangor_savings_three_count_summary` | 3 | `FAM:bangor_savings_three_count_summary` |
| `FAM:champion_cu_statement_summary` | 3 | `FAM:champion_cu_statement_summary` |
| `FAM:core_enclosures_avgledger_leading_counts` | 3 | `FAM:core_enclosures_avgledger_leading_counts` |
| `FAM:eastern_bank_customer_statement` | 3 | `FAM:eastern_bank_customer_statement` |
| `FAM:greenstate_cu_post_eff_type` | 3 | `FAM:greenstate_cu_post_eff_type` |
| `FAM:heritage_south_cu` | 3 | `FAM:heritage_south_cu` |
| `FAM:hudson_valley_fcu` | 3 | `FAM:hudson_valley_fcu` |
| `FAM:mt_bank_account_activity_daily_balance` | 3 | `FAM:mt_bank_account_activity_daily_balance` |
| `FAM:mt_bank_customer_statement_treasury` | 3 | `FAM:mt_bank_customer_statement_treasury` |
| `FAM:pima_fcu_statement_of_account` | 3 | `FAM:pima_fcu_statement_of_account` |
| `RV:found_lead_activity:not_a_formal_statement` | 3 | `RV:found_lead_activity` |
| `SCAN-UNCLAIMED:Citizens Bank` | 3 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Signature Bank` | 3 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Truist` | 3 | `SCAN-UNCLAIMED` |
| `WH:bmo:A+B` | 3 | `WH:bmo` |
| `WH:citizens:A` | 3 | `WH:citizens` |
| `WH:eq_bank_scanned:A+D` | 3 | `WH:eq_bank_scanned` |
| `WH:farmers_merchants:E` | 3 | `WH:farmers_merchants` |
| `WH:frost:A+bank_daily_balance_dates_valid+statement_period_dates_valid` | 3 | `WH:frost` |
| `DECL:banco_popular` | 2 | `DECL:banco_popular` |
| `DECL:bank_of_america` | 2 | `DECL:bank_of_america` |
| `DECL:bluevine` | 2 | `DECL:bluevine` |
| `DECL:eq_bank_scanned` | 2 | `DECL:eq_bank_scanned` |
| `DECL:ibc` | 2 | `DECL:ibc` |
| `DECL:santander` | 2 | `DECL:santander` |
| `DECL:td_us` | 2 | `DECL:td_us` |
| `FAM:firstbank_colorado` | 2 | `FAM:firstbank_colorado` |
| `FAM:firstbank_pr_escrow_pipe_header` | 2 | `FAM:firstbank_pr_escrow_pipe_header` |
| `FAM:umb_essential_business_checking` | 2 | `FAM:umb_essential_business_checking` |
| `RV:community_section:missing_declared_statement_page` | 2 | `RV:community_section` |
| `RV:southside_scanned:missing_declared_statement_page` | 2 | `RV:southside_scanned` |
| `SCAN-UNCLAIMED:American Express` | 2 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:CIBC` | 2 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Frost Bank` | 2 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:RBC` | 2 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Square` | 2 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:US Bank` | 2 | `SCAN-UNCLAIMED` |
| `WH:atb:A+B+D` | 2 | `WH:atb` |
| `WH:pnc:A` | 2 | `WH:pnc` |
| `WH:pnc:A+C` | 2 | `WH:pnc` |
| `WH:scotiabank:A+B` | 2 | `WH:scotiabank` |
| `WH:td_us:A` | 2 | `WH:td_us` |
| `WH:wells_fargo:A` | 2 | `WH:wells_fargo` |
| `DECL:apex_scanned` | 1 | `DECL:apex_scanned` |
| `DECL:chase` | 1 | `DECL:chase` |
| `DECL:cibc_french` | 1 | `DECL:cibc_french` |
| `DECL:first_farmers` | 1 | `DECL:first_farmers` |
| `DECL:pnc` | 1 | `DECL:pnc` |
| `DECL:rbc` | 1 | `DECL:rbc` |
| `DECL:wealthsimple` | 1 | `DECL:wealthsimple` |
| `DECL:welch_state_bank` | 1 | `DECL:welch_state_bank` |
| `DECL:woodforest` | 1 | `DECL:woodforest` |
| `FAM:bofa_business_advantage` | 1 | `FAM:bofa_business_advantage` |
| `FAM:chase_total_checking_transaction_detail` | 1 | `FAM:chase_total_checking_transaction_detail` |
| `FAM:conexus_cu_demand_products` | 1 | `FAM:conexus_cu_demand_products` |
| `FAM:cu_suffix_transfer_acct_grid` | 1 | `FAM:cu_suffix_transfer_acct_grid` |
| `FAM:desjardins_accesd_releve_operations` | 1 | `FAM:desjardins_accesd_releve_operations` |
| `FAM:laurentian_bank_current_account` | 1 | `FAM:laurentian_bank_current_account` |
| `FAM:onepay_coastal_community_monthly` | 1 | `FAM:onepay_coastal_community_monthly` |
| `FAM:pc_financial_pc_money_account` | 1 | `FAM:pc_financial_pc_money_account` |
| `FAM:ramp_business_account` | 1 | `FAM:ramp_business_account` |
| `FAM:relationship_summary_daily_balance_unbranded` | 1 | `FAM:relationship_summary_daily_balance_unbranded` |
| `FAM:rho_deposit_account_statement` | 1 | `FAM:rho_deposit_account_statement` |
| `FAM:southern_bank_quadruplicated` | 1 | `FAM:southern_bank_quadruplicated` |
| `NO-TEXT` | 1 | `NO-TEXT` |
| `RV:citizens:missing_declared_statement_page` | 1 | `RV:citizens` |
| `RV:core_processor_enclosures:missing_declared_statement_page` | 1 | `RV:core_processor_enclosures` |
| `RV:texas_first_scanned:missing_declared_statement_page` | 1 | `RV:texas_first_scanned` |
| `SCAN-UNCLAIMED:Altra Federal Credit Union` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:BMO` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Banco Popular` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Capital One` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Commerce Bank` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Community Bank` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Community Trust Bank` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Home Federal Bank` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Regions Bank` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:TBK Bank` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:TD Canada Trust` | 1 | `SCAN-UNCLAIMED` |
| `SCAN-UNCLAIMED:Zions Bank` | 1 | `SCAN-UNCLAIMED` |
| `WH:bmo:A` | 1 | `WH:bmo` |
| `WH:capital_one:A+B+D` | 1 | `WH:capital_one` |
| `WH:core_processor_enclosures:agrees_with_bank_stated_average` | 1 | `WH:core_processor_enclosures` |
| `WH:ibc:A` | 1 | `WH:ibc` |
| `WH:rbc:A+B+C` | 1 | `WH:rbc` |
| `WH:regions:A` | 1 | `WH:regions` |
| `WH:relay:A+D` | 1 | `WH:relay` |
| `WH:scotiabank:A` | 1 | `WH:scotiabank` |
| `WH:td_us:A+C` | 1 | `WH:td_us` |
| `WH:wells_fargo:A+B` | 1 | `WH:wells_fargo` |
| `WH:wells_fargo:B+F` | 1 | `WH:wells_fargo` |
| `WH:zions:C` | 1 | `WH:zions` |

## Batch-8 census families — residual accounting

Every family the batch-8 census listed, with its members' outcome in THIS run. `remaining` = still non-validated (these shas carry `FAM:<key>` above when unclaimed, or a WH/RV/DECL cluster when a reader now claims them).

| family | b8 rank | n (b8) | validated now | remaining | remaining outcomes | b8 expected | b8 conf | census yield on remaining | handoff cards naming the key |
|---|---:|---:|---:|---:|---|---:|---:|---:|---|
| `cu_summary_of_accounts_date_posted` | 4 | 13 | 0 | 13 | failed/no_parser_matched 13 | 7.15 | 0.55 | 7.15 | - |
| `core_enclosures_avgledger_leading_counts` | 1 | 58 | 47 | 11 | failed/parser_declined 6, failed/no_parser_matched 3, review/integrity_flags 1, … (+1) | 40.6 | 0.7 | 7.7 | CORE-ENCLOSURES |
| `american_savings_bank_hawaii` | 12 | 11 | 0 | 11 | failed/no_parser_matched 11 | 4.4 | 0.4 | 4.4 | - |
| `lili_sunrise_banks_checking` | 2 | 20 | 11 | 9 | failed/parser_declined 9 | 15.0 | 0.75 | 6.75 | LILI |
| `frost_bank_business_checking` | 6 | 9 | 0 | 9 | withheld/withheld_adb 9 | 5.4 | 0.6 | 5.4 | FROST-OZK |
| `mountain_america_cu_dot_leader` | 24 | 9 | 0 | 9 | failed/no_parser_matched 9 | 3.15 | 0.35 | 3.15 | - |
| `space_coast_cu_member_statement` | 8 | 8 | 0 | 8 | failed/no_parser_matched 8 | 5.2 | 0.65 | 5.2 | - |
| `guardian_cu_statement_summary` | 10 | 8 | 0 | 8 | failed/no_parser_matched 8 | 4.8 | 0.6 | 4.8 | - |
| `cu_idaho_equation_summary` | 13 | 8 | 0 | 8 | failed/no_parser_matched 8 | 4.4 | 0.55 | 4.4 | - |
| `wpcu_summary_of_account_by_transaction` | 14 | 8 | 0 | 8 | failed/no_parser_matched 8 | 4.4 | 0.55 | 4.4 | - |
| `cu_unq_clt_trailing_minus_totals` | 15 | 8 | 0 | 8 | failed/no_parser_matched 8 | 4.0 | 0.5 | 4.0 | - |
| `truist_your_account_statement` | 16 | 7 | 0 | 7 | failed/no_parser_matched 7 | 3.85 | 0.55 | 3.85 | - |
| `paypal_account_statements` | 91 | 7 | 0 | 7 | failed/no_parser_matched 7 | 0.0 | 0.0 | 0.0 | - |
| `capital_one_360` | 49 | 6 | 0 | 6 | failed/no_parser_matched 6 | 2.1 | 0.35 | 2.1 | - |
| `old_national_free_business_checking` | 17 | 5 | 0 | 5 | failed/no_parser_matched 5 | 3.75 | 0.75 | 3.75 | - |
| `dfcu_financial_account_statement` | 18 | 5 | 0 | 5 | failed/no_parser_matched 5 | 3.5 | 0.7 | 3.5 | - |
| `chesapeake_bank_activity_in_date_order` | 20 | 5 | 0 | 5 | failed/no_parser_matched 5 | 3.25 | 0.65 | 3.25 | - |
| `wescom_cu_equation_summary` | 21 | 5 | 0 | 5 | failed/no_parser_matched 5 | 3.25 | 0.65 | 3.25 | - |
| `altura_riverside_cu` | 25 | 5 | 0 | 5 | failed/no_parser_matched 5 | 3.0 | 0.6 | 3.0 | - |
| `chime_bancorp_checking` | 32 | 5 | 0 | 5 | failed/no_parser_matched 5 | 2.75 | 0.55 | 2.75 | - |
| `cubase_suffix_box_summary_history` | 43 | 5 | 0 | 5 | failed/no_parser_matched 5 | 2.25 | 0.45 | 2.25 | - |
| `rbfcu_business_member_statement` | 44 | 5 | 0 | 5 | failed/no_parser_matched 5 | 2.25 | 0.45 | 2.25 | - |
| `beem_credit_union_bc` | 66 | 5 | 0 | 5 | failed/no_parser_matched 5 | 1.5 | 0.3 | 1.5 | - |
| `pr_business_plus_corp_statement_of_account` | 77 | 5 | 0 | 5 | failed/no_parser_matched 5 | 0.75 | 0.15 | 0.75 | - |
| `bank7_summary_of_accounts` | 19 | 4 | 0 | 4 | failed/no_parser_matched 4 | 3.4 | 0.85 | 3.4 | - |
| `commerce_bank_mybusiness_checking` | 22 | 4 | 0 | 4 | failed/no_parser_matched 4 | 3.2 | 0.8 | 3.2 | - |
| `pnc_core_commercial_checking` | 23 | 4 | 0 | 4 | failed/no_parser_matched 4 | 3.2 | 0.8 | 3.2 | - |
| `jh_spaced_caps_checking_summary` | 26 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.8 | 0.7 | 2.8 | - |
| `pnc_treasury_enterprise_plan` | 27 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.8 | 0.7 | 2.8 | - |
| `pnc_virtual_wallet_performance_spend` | 28 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.8 | 0.7 | 2.8 | - |
| `suncoast_cu_account_statement` | 29 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.8 | 0.7 | 2.8 | - |
| `usaa_fsb_classic_checking` | 30 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.8 | 0.7 | 2.8 | - |
| `vystar_balance_summary_transactional_detail` | 31 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.8 | 0.7 | 2.8 | - |
| `bokf_business_access` | 33 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.6 | 0.65 | 2.6 | - |
| `nbkc_bank_dda_statement` | 34 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.6 | 0.65 | 2.6 | - |
| `associated_bank_financial_statement_of_accounts` | 35 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.4 | 0.6 | 2.4 | - |
| `city_national_bank_florida` | 36 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.4 | 0.6 | 2.4 | - |
| `greater_nevada_cu` | 37 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.4 | 0.6 | 2.4 | - |
| `green_dot_bank_partner_program` | 38 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.4 | 0.6 | 2.4 | - |
| `hapo_cu_estatement` | 39 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.4 | 0.6 | 2.4 | - |
| `ornl_fcu_oak_ridge` | 40 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.4 | 0.6 | 2.4 | - |
| `sierra_central_cu` | 41 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.4 | 0.6 | 2.4 | - |
| `townebank_balance_summary` | 42 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.4 | 0.6 | 2.4 | - |
| `cu_statement_summary_prev_new_balance_unbranded` | 46 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.2 | 0.55 | 2.2 | - |
| `redstone_fcu_statement_of_accounts` | 47 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.2 | 0.55 | 2.2 | - |
| `security_service_fcu_asterisk_sections` | 48 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.2 | 0.55 | 2.2 | - |
| `community_savings_bc` | 52 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.0 | 0.5 | 2.0 | - |
| `goldenwest_cu_member_account_statement` | 53 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.0 | 0.5 | 2.0 | - |
| `novo_monthly_account_statement` | 54 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.0 | 0.5 | 2.0 | - |
| `palmetto_citizens_cu` | 55 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.0 | 0.5 | 2.0 | - |
| `st_marys_bank_nh` | 56 | 4 | 0 | 4 | failed/no_parser_matched 4 | 2.0 | 0.5 | 2.0 | - |
| `access_fcu_member_statement_of_account` | 58 | 4 | 0 | 4 | failed/no_parser_matched 4 | 1.8 | 0.45 | 1.8 | - |
| `atb_financial_consolidated_statement` | 59 | 4 | 0 | 4 | failed/no_parser_matched 4 | 1.8 | 0.45 | 1.8 | - |
| `bank_of_tennessee_activity_summary` | 60 | 4 | 0 | 4 | failed/no_parser_matched 4 | 1.8 | 0.45 | 1.8 | - |
| `vystar_business_checking_analyzed` | 61 | 4 | 0 | 4 | failed/no_parser_matched 4 | 1.8 | 0.45 | 1.8 | - |
| `becu_deposit_and_loan_activity` | 65 | 4 | 0 | 4 | failed/no_parser_matched 4 | 1.6 | 0.4 | 1.6 | - |
| `fulton_bank_account_statement` | 68 | 4 | 0 | 4 | failed/no_parser_matched 4 | 1.4 | 0.35 | 1.4 | - |
| `synovus_pinnacle_portal_statement_view` | 73 | 4 | 0 | 4 | failed/no_parser_matched 4 | 1.0 | 0.25 | 1.0 | - |
| `wisely_adp_paycard` | 74 | 4 | 0 | 4 | failed/no_parser_matched 4 | 1.0 | 0.25 | 1.0 | - |
| `psecu_shares_at_a_glance` | 76 | 4 | 0 | 4 | failed/no_parser_matched 4 | 0.8 | 0.2 | 0.8 | - |
| `ion_bank_customer_statement` | 78 | 4 | 0 | 4 | failed/no_parser_matched 4 | 0.6 | 0.15 | 0.6 | - |
| `accounts_at_a_glance_category_number_amount` | 9 | 8 | 5 | 3 | failed/parser_declined 3 | 4.8 | 0.6 | 1.8 | GLANCE |
| `altra_fcu_statement_summary` | 45 | 3 | 0 | 3 | failed/no_parser_matched 3 | 2.25 | 0.75 | 2.25 | - |
| `heritage_south_cu` | 50 | 3 | 0 | 3 | failed/no_parser_matched 3 | 2.1 | 0.7 | 2.1 | - |
| `hudson_valley_fcu` | 51 | 3 | 0 | 3 | failed/no_parser_matched 3 | 2.1 | 0.7 | 2.1 | - |
| `pima_fcu_statement_of_account` | 57 | 3 | 0 | 3 | failed/no_parser_matched 3 | 1.95 | 0.65 | 1.95 | - |
| `bangor_savings_three_count_summary` | 62 | 3 | 0 | 3 | failed/no_parser_matched 3 | 1.8 | 0.6 | 1.8 | - |
| `champion_cu_statement_summary` | 63 | 3 | 0 | 3 | failed/no_parser_matched 3 | 1.8 | 0.6 | 1.8 | - |
| `mt_bank_customer_statement_treasury` | 64 | 3 | 0 | 3 | failed/no_parser_matched 3 | 1.65 | 0.55 | 1.65 | - |
| `mt_bank_account_activity_daily_balance` | 67 | 3 | 0 | 3 | failed/no_parser_matched 3 | 1.5 | 0.5 | 1.5 | - |
| `greenstate_cu_post_eff_type` | 71 | 3 | 0 | 3 | failed/no_parser_matched 3 | 1.35 | 0.45 | 1.35 | - |
| `eastern_bank_customer_statement` | 84 | 3 | 0 | 3 | failed/no_parser_matched 3 | 0.45 | 0.15 | 0.45 | - |
| `firstbank_colorado` | 69 | 2 | 0 | 2 | failed/no_parser_matched 2 | 1.4 | 0.7 | 1.4 | - |
| `firstbank_pr_escrow_pipe_header` | 70 | 2 | 0 | 2 | failed/no_parser_matched 2 | 1.4 | 0.7 | 1.4 | - |
| `umb_essential_business_checking` | 72 | 2 | 0 | 2 | failed/no_parser_matched 2 | 1.1 | 0.55 | 1.1 | - |
| `welch_state_bank_more_than_free` | 3 | 16 | 15 | 1 | failed/parser_declined 1 | 11.2 | 0.7 | 0.7 | WELCH |
| `ramp_business_account` | 75 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.85 | 0.85 | 0.85 | - |
| `pc_financial_pc_money_account` | 79 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.6 | 0.6 | 0.6 | - |
| `bofa_business_advantage` | 80 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.55 | 0.55 | 0.55 | - |
| `relationship_summary_daily_balance_unbranded` | 81 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.55 | 0.55 | 0.55 | - |
| `southern_bank_quadruplicated` | 82 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.55 | 0.55 | 0.55 | - |
| `onepay_coastal_community_monthly` | 83 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.5 | 0.5 | 0.5 | - |
| `chase_total_checking_transaction_detail` | 85 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.45 | 0.45 | 0.45 | - |
| `cu_suffix_transfer_acct_grid` | 86 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.45 | 0.45 | 0.45 | - |
| `desjardins_accesd_releve_operations` | 87 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.45 | 0.45 | 0.45 | - |
| `laurentian_bank_current_account` | 88 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.4 | 0.4 | 0.4 | - |
| `rho_deposit_account_statement` | 89 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.4 | 0.4 | 0.4 | - |
| `conexus_cu_demand_products` | 90 | 1 | 0 | 1 | failed/no_parser_matched 1 | 0.3 | 0.3 | 0.3 | - |
| `business_classic_statement_of_account` | 5 | 8 | 8 | 0 | - | 6.0 | 0.75 | 0.0 | CORE-ISSUES-2 |
| `bank_ozk_plus_less_summary` | 7 | 8 | 8 | 0 | - | 5.2 | 0.65 | 0.0 | FROST-OZK |
| `poplar_bluff_activity_summary_running` | 11 | 6 | 6 | 0 | - | 4.8 | 0.8 | 0.0 | CORE-ISSUES-2 |
| **total** | | | | **372** | | | | **200.2** | |

## Registry label vocabulary used for first-page hints

`ATB Financial`, `Altana Federal Credit Union`, `American Express`, `Apex Bank`, `B1Bank`, `BMO`, `Banco Popular`, `Bank OZK`, `Bank of America`, `Banque Royale du Canada`, `Bluevine`, `Brex`, `Burke & Herbert Bank`, `CIBC`, `Capital One`, `Chase`, `Chase Savings`, `Chase Transaction Export`, `Citibank`, `Citizens Bank`, `Columbia Bank`, `Consumers Credit Union`, `Core Processor Daily Balances Platform`, `Dakota West Credit Union`, `Demo National Bank`, `Desjardins`, `EQ Bank`, `Farmers & Merchants Bank`, `Fifth Third Bank`, `First Citizens Bank`, `First Community Credit Union`, `First Farmers Bank & Trust`, `Fiserv Premier`, `Frost Bank`, `Huntington National Bank`, `IBC Bank`, `LINKBANK`, `Lead Bank (Found) Month-to-Date Activity`, `Lili`, `MIDFLORIDA Credit Union`, `Mercury`, `Mission Valley Bank`, `Navigant Credit Union`, `Navy Federal Credit Union`, `PNC Bank`, `Regions Bank`, `Releve de Compte Statement Template`, `Royal Bank of Canada`, `SECU Maryland`, `Santander Bank`, `Scotiabank`, `Shopify Balance`, `Southside Bank`, `Square`, `Symitar Credit Union`, `TD Bank`, `TD Canada Trust`, `Texas Bank and Trust`, `Texas First Bank`, `Thread Bank (Relay)`, `Truist`, `U.S. Bank`, `Wealthsimple`, `Welch State Bank`, `Wells Fargo`, `Wilson & Muir Bank & Trust`, `Woodforest National Bank`, `Zions Bancorporation`

## Opportunity table (Ocean's estimates over the measured clusters)

Basis: `Ocean's estimates over the measured clusters of CENSUS_BATCH9 (run cda8882d). expected_recoverable = conservative-optimistic (mid). score = mid / effort_sessions / cost_factor; cost_factor 1.0 = native text, deterministic; 1.1 = depends on the cached local-Tesseract text (CPU only, $0 vendor); gated rows score 0 until their ruling lands. Yields for batch-8 census families start from the census's own pro-rated expectation (census yield on remaining) and the verify columns where they exist; the rest are judgement from the run's deterministic signatures (coverage, breaks, codes, density). Nothing here is a measurement.`

| # | cluster | docs | current outcomes | root cause | likely fix | expected recoverable | confidence | difficulty | regression surface | marginal runtime/model cost | score |
|---:|---|---:|---|---|---|---|---|---|---|---|---:|
| 1 | `DECL:huntington` | 12 | failed/parser_declined 12 | one institution, one reader: huntington claims at detection (required markers only, score 0.5) and parse returns None on 12 native documents of 3-10 pages - a layout variant the reader's grammar does not cover | probe the 12 declines for the shared missing shape; widen huntington's period/summary/row grammar; family replay over the validated huntington cohort | 6-10 (8) | medium-high (single reader, single folder, native) | low-medium | huntington validated cohort only | $0; native text | 8.0 |
| 2 | `CP-DECLINES` | 38 | failed/parser_declined 38 | core-processor template readers recognise the document (exclusive marker, score 1.0) and fail closed in parse: layout variants on native text (17) and OCR noise on Tesseract text (21); folders all Unidentified | widen the four readers' row/summary grammars on the native variants first, then OCR-tolerant tokens for the scanned members (CP-SECTIONED-SCAN precedent); one decline-reason probe per reader before any change | 10-22 (16) | medium (readers exist; decline reasons unprobed) | medium | every core_processor_* / category_partition validated family (mutation tables + family replays mandatory) | $0 vendor; native text + cached Tesseract; CPU only | 7.6 |
| 3 | `RV-PAGE-COVERAGE` | 11 | review/integrity_flags 11 | integrity flag missing_declared_statement_page with reconciliation OK on all 11: the declared page count and the delivered pages disagree - either a genuinely partial upload (stays review, fail closed) or a misread declaration | read-only probe first: declared count vs page_count per sha; fix only a proven misread of the declaration; never relax the page-coverage check | 1-6 (3) | low-medium (unknown split until probed) | low | page-coverage integrity check (shared); linkbank / community_section / southside / citizens / texas_first readers | $0 | 6.0 |
| 4 | `FAM-PNC-LAYOUTS` | 12 | failed/no_parser_matched 12 | three PNC product layouts the pnc reader's markers do not claim (census conf 0.7-0.8, oracle present); with WH:pnc (4, coverage 0-0.24 = rows not captured) and DECL:pnc (1) PNC is a 17-document institution | widen the pnc reader (markers + row grammar) to the three layouts; measure with the pnc family replay; take WH:pnc row capture in the same session if the grammar is shared | 6-11 (8.5) | medium-high (census verified oracle; reader exists) | medium | pnc validated cohort | $0 | 5.7 |
| 5 | `WH-ROW-CAPTURE` | 22 | withheld/withheld_adb 22 | withheld with an extraction signature in the run's own payload: rbc credit coverage 0.46-0.86 with 5-14 continuity breaks (rows missed), pnc coverage 0-0.24 (rows not captured), bmo coverage 1.7 (rows duplicated), scotiabank/wells breaks 2-8 - the ledger cannot close because the reader's row set is wrong, not because evidence is absent | per-reader row-grammar fixes measured by coverage -> 1.0 and breaks -> 0 on the withheld members, family replay on the validated members; rbc/bmo/scotiabank are CAD-pinned surfaces (currency doctrine) | 8-16 (12) | medium-high (signatures are measured; fixes are per reader) | medium | rbc / pnc / bmo / wells_fargo / scotiabank / ibc validated cohorts; PINNED_CURRENCY surface for the Canadian readers | $0 | 4.8 |
| 6 | `DECL:community_section` | 9 | failed/parser_declined 9 | community_section (the sectioned core family) claims and declines 9 native documents (Rogue CU 3, Chase-folder 2, Unidentified 4) - a section-grammar variant | decline-reason probe; widen the section grammar; replay the 62-document validated community_section cohort | 3-6 (4.5) | medium | medium | community_section validated cohort (largest sectioned family) + WITHHELD-GRIDS leaf behaviour | $0 | 4.5 |
| 7 | `WH-NO-PERIOD` | 3 | withheld/withheld_adb 3 | farmers_merchants publishes no period and no opening (code E: no validations run) on 3 native documents | read the printed period/opening labels the reader currently skips; small | 1-3 (2) | medium | low | farmers_merchants cohort (also a RAISE-PRIVACY-4 module) | $0 | 4.0 |
| 8 | `WH-CLOSE-FULL-COVERAGE` | 18 | withheld/withheld_adb 18 | withheld with detail coverage ~1.0 and 0 breaks but the closing/period checks fail (codes A, A+C, A+D, C): summary identity or period edges disagree with a ledger that is internally consistent - printed daily-balance grids or closing labels the reader does not consume (batch-8 withheld census headline), or out-of-period rows (D) | per-reader: consume the printed grid / closing label (WITHHELD-GRIDS precedent), period-edge handling for D; measured by the ADB check set on the withheld members | 4-12 (8) | medium | medium | southside_scanned / citizens / td_us / eq_bank_scanned / relay / zions / regions cohorts; ADB doctrine (calendar-day period) untouched | $0; 12 of 19 depend on cached Tesseract text | 3.8 |
| 9 | `SCAN-UNCLAIMED` | 89 | failed/no_parser_matched 89 | 89 scanned/mixed documents with Tesseract text no reader claims. Measured split: dense 25 (15 with 2+ pages; hints TD 12, Wells 6, Chase 5, BoA 4 across the block), medium 13, thin 51 (42 single-page, <600 chars or <3 money tokens per page - screenshots, photos, partial pages). Only the dense members are a reader problem; the thin members are a classification problem | dense: OCR-tolerant markers/grammar on the existing td_us / wells_fargo / chase / bank_of_america readers (scanned variants), measured on the cached text; thin/medium: no deterministic path - they are the population for a later, measured VLM experiment, not wave 1 | 5-12 (8) from the dense 25; 0 from the thin/medium 64 in this wave | medium-low | medium-high | td_us / wells_fargo / chase / bank_of_america scanned cohorts; OCR-stage version | $0 vendor; cached Tesseract; CPU only | 3.6 |
| 10 | `DECL:navy_federal` | 6 | failed/parser_declined 6 | navy_federal claims and declines 6 native documents of 12-15 pages (4 Unidentified, 2 filed under Bank of America) | decline probe; widen; replay | 2-5 (3.5) | medium | medium | navy_federal cohort | $0 | 3.5 |
| 11 | `DECL:lili` | 9 | failed/parser_declined 9 | LILI residual: 9 of the census's 20 still decline; the batch-8 verify named ~5 defective members (column-shredded text layers, out-of-range years) - the recoverable remainder is small; the Lili tampering finding is an open ruling | probe which of the 9 are the named defects (unrecoverable by a text reader) vs grammar gaps; widen only the latter | 2-5 (3.5) | medium-low | medium | lili validated cohort (11) + LILI integrity fingerprint | $0 | 3.5 |
| 12 | `CAPITAL-ONE` | 13 | failed/parser_declined 6, failed/no_parser_matched 6, withheld/withheld_adb 1 | one institution across three groups: capital_one declines 6 native six-page documents, the capital_one_360 layout (6, census conf 0.35) is unclaimed, 1 withheld (A+B+D) | decline probe + 360-layout markers in the capital_one reader; one session | 3-8 (5) | medium-low (360 layout rated 0.35 by the census) | medium | capital_one validated cohort | $0 | 3.3 |
| 13 | `DECL-OTHER-READERS` | 45 | failed/parser_declined 45 | 22 readers each declining 1-6 documents (45 total); bmo_ca_business's 6 are single-page (summary pages, low); columbia_bank / core-daily / texas_first / eq_bank / apex / first_farmers decline on Tesseract text; the rest are native grammar gaps of 1-3 documents each | per-reader decline probes bundled by institution; take a reader only when its probe shows a shared shape; WELCH x DESC-COLUMNS (361167E3) is the carded WELCH-PRINTED-ROWS case | 8-18 (13) | medium-low (tiny cohorts) | medium (breadth) | each touched reader's cohort | $0 | 3.2 |
| 14 | `FAM-BANK-TAIL-TOP` | 38 | failed/no_parser_matched 38 | the best-rated bank families of the long tail (census conf 0.55-0.85, oracle present), 38 documents in 8 families; Truist is a 13-document institution with DECL:truist | one reader per family, ordered by census confidence (bank7 0.85, commerce 0.8, old_national 0.75, jh 0.7, usaa 0.7, chesapeake 0.65, truist 0.55, chime 0.55) | 15-28 (21) | medium (census-rated) | medium per family; breadth is the cost | new readers; registry conformance only | $0 | 2.6 |
| 15 | `TEXT-LAYER-DEFECT` | 8 | failed/no_parser_matched 8 | 8 digital documents whose embedded fonts decode to a substitution alphabet (digits included); RBC x4 with an existing reader. The census's vowel-share proxy does NOT separate them (0.68-1.0) - a detector is still missing | the first 'cheap OCR' rung: rasterise + local Tesseract for digital documents that are unclaimed AND carry a bank hint, triggered deterministically; provenance recorded; measured on these 8 before widening | 2-6 (4) | medium-low | medium (a rung, not a reader) | OCR ladder / OCR_STAGE_VERSION; must not touch documents with a sound text layer | $0 vendor; Tesseract CPU per triggered document | 2.4 |
| 16 | `FAM-BANK-TAIL-REST` | 83 | failed/no_parser_matched 83 | 29 families / 83 documents of 1-11 each (census yield 50.0): per-family readers at ~1 session for 1-4 documents; american_savings_bank_hawaii (11, verify LOW, filed under Chase - a folder/identity contradiction) and the 3 core_enclosures residual (scrambled text layers) are the low end; ATB consolidated (4) is ceremony-gated | defer; pick individual families only when a session is otherwise idle; ATB waits for its ceremony | 15-40 (25) | low | medium x breadth | new readers | $0 | 1.3 |
| 17 | `FAM-ZERO-RATED` | 27 | failed/no_parser_matched 27 | families the batch-8 census itself rated <= 0.25 (no oracle, portal views, paycards): 27 documents, census yield 3.8 | none in batch 9 | 0-4 (1) | n/a | - | - | $0 | 0.3 |
| 18 | `FAM-CU-SUFFIX-CORE` | 176 | failed/no_parser_matched 176 | the largest deterministic reservoir: 37 credit-union families / 176 documents (census yield 95.0) sharing core-processor mechanics - suffix sections, summary-of-accounts roll-ups, equation summaries, dot leaders - with the L-1 multi-account exposure the batch-8 verify flagged (cu_summary_of_accounts: 3 not 7 under the current architecture; Space Coast in the open L-1 ruling) | NOT per-family readers. One shared suffix/summary template family (as core_processor_* is for banks) with per-family markers, built AFTER the L-1 multi-account ruling; until then only single-suffix members are publishable and their share is unmeasured | 25-95 (50) | low until L-1 is ruled; medium after | high (shared design + ruling) | new template family - no existing cohort, but the ADB doctrine and the L-1 rule are load-bearing | $0 | 0 |
| 19 | `WH-FROST-PERIOD` | 9 | withheld/withheld_adb 9 | 9 Frost documents withheld because the reader refuses to derive a period the paper does not print (FROST-OZK, by design). MEASURED in this run: 6 fail only the two period-date checks (bank_daily_balance_dates_valid + statement_period_dates_valid) with counts present, coverage 1.0, 0 breaks and 17-23 stated daily balances; 3 also fail ledger closing (A). This is the per-document table W3 SFZ14 asked for; it is NOT the packet's derived-period ADB result | none without the FROST-PERIOD ruling (recommendation on record: REFUSE). If re-argued, FROST-PERIOD-PACKET (read-only) is the instrument; the census table above is its starting point | 0 (6 if the ruling admits a derived period) | n/a - ruling | ruling | ADB doctrine (calendar-day printed period) | $0 | 0 |
| 20 | `WH-ATB` | 2 | withheld/withheld_adb 2 | 2 ATB consolidated statements with detail coverage ~10x (multi-account roll-up read as one ledger; codes A+B+D) | none before the ATB ceremony / R3 and the L-1 ruling | 0 | n/a | ceremony | ATB packet, currency doctrine | $0 | 0 |
| 21 | `RV-INFORMAL-EXPORTS` | 7 | review/integrity_flags 7 | 7 online-activity exports the registry claims as non-formal documents (not_a_formal_statement); review is the designed outcome | none - admitting customer-chosen windows is a doctrine change, not a parser change | 0 | n/a | doctrine | - | $0 | 0 |
| 22 | `NOT-STATEMENT` | 117 | failed/no_parser_matched 117 | 104 not-statements and 13 portal/range exports per the batch-8 census (committed lists): no statement period, no beginning/ending pair, no printed totals | none under the fail-closed doctrine; a ruling on exports would be a doctrine change | 0 | n/a | - | - | $0 | 0 |
| 23 | `PF-INVALID-PDF` | 16 | failed/invalid_pdf 16 | 16 files whose first bytes are the Java object-serialisation magic (AC ED 00 05), 12-26 KB, 0 pages - portal download artifacts saved with a .pdf name (Desjardins 11, TD 1, Unidentified 4). Not documents | none; permanently unrecoverable inside the 3,380 denominator | 0 | certain (magic bytes) | - | - | $0 | 0 |
| 24 | `OCR-NEGATIVE` | 14 | deferred/deferred_visual_ocr 13, failed/no_parser_matched 1 | 13 scans (11 single-page) where local Tesseract produced nothing, plus 1 digital document with no text: photos / screenshots / blank layers | none deterministic; with SCAN-UNCLAIMED's 64 thin/medium members this is the 78-document population for a later, measured visual experiment (documents tested | additional validated | regressions | cost/document | latency) - not wave 1 | 0 in this wave | n/a | new rung | OCR ladder | $0 now; a visual rung would be the first paid/GPU cost of the program | 0 |

## Appendix — sha16 lists per cluster group

### `NOT-STATEMENT` (117)

```
023CDC26749D65BE
0396C3A3FA9163FA
03D93BC1C67F148A
0A8307BD6B355EFE
0CD13C8F3A4BE4E1
0D6010E4C1382622
0ECBD5376B4A6CFF
0F1A3B4712E59F6A
0F802A511CDA76D3
16E811FC7DE632BC
1839E3B630493722
18A524AD4D6AAF89
1B82DF47498A5968
1BBD4ADF433C1991
1C5EC0C012980EF6
1EDC9E104C7AAD3F
228DF61DCE5D604B
2A6E98002176D99B
2AAD7259F6414043
2CDC5BF87CCF1290
2F24037A2F1F9D16
3126951648C781AA
31BC9E17AF2FC679
323E99F886E5BE34
3258D9A0A735E1D3
34002EC276B446A1
362A08B720DFDF4C
39E0152153B2D219
3B385E3A8B76D524
3CC7EE3B499634CA
3D1F8163572B002C
3DBDF360144F1296
3EF955504367FEBA
3F04C47DD9A745E1
3FA5657F74925E51
4295D7A86F1AF93E
4341EBE2CFE03A9C
46624A5EB99F5F45
47C25055594C7725
4CACCC5B7ADFBBBF
4F5D0B78CD8BC40A
4F8D24A362940437
52BF0C2B414CBAA6
54BA73ED0129410B
5ACD950A998E88ED
5C528616944EB177
5D870BEC15DAE202
5EC52143CBB74004
618BAD3639FD6496
62AEFF4DF6009C94
63F24D62C0B29EEF
66BC0F48B64308D7
6D1D94BEC40396C4
6D283A80D9473652
720CF485E216D916
7447415D4CD5DE80
75EEE5141C1A930E
78183B283FCB9C6F
79EAE384CB1B36DC
7A9F3274C2E8368D
7C66346972EB5716
81C743048B48E159
85DD6E65360BE181
8629813BBAC062CA
89749FC636DFFC0B
8A437C80861F8135
9039432FB3001898
939FF46F2CA134EF
94B5C66AAE85E407
96970042B5C31FE8
9ACA05CD44BE1227
9B5024A6DD7A1FAE
9D791424425D3B96
A52A9D7ECC521286
A71DEDC7D93C92AD
A751A35468A6BDCD
AE0581F138F4356A
B1589A7157F91E15
B573F0C70843A5C3
B5C8EE8958B39FE5
B6F3AE2A854A3450
BA7A1CBD25EABDD2
BBB8DF1DDE469179
BEDE7D5DE0D947D2
BFE3E7D7E24ACA67
BFF548686DBB0202
C0186760BCD1667E
C175A7FD8003E07F
C21E3683C0724710
C3BFA577B3ABD183
C41E5EBEA32A80C6
CAF3FB335C6A270D
CB2F300419D35FA7
CC05BBA8B9C86A93
CCC0FA538142AA88
CDDD6BD32B037D4C
D070198E0816B80F
D7E5437DB818FC2B
D810DA664AA4654C
D886A629369FE445
D8DBB5A34126A24E
D9CF1D8378071C1E
DBA2417935EC9C8F
DDDB1C8EA583D823
DE640D9C514EE54D
E557342C8695251D
E6473C22D671666D
EBAD3C3AB2FC50EB
ED27862D211F2067
EEEE8F601CA8BD45
F12C59314D61C02D
F4938809751D0AA6
F549E78D5C516DF2
F9BC8447E38EC2A8
FD03CDFBD165C3E5
FD044BD587D80616
FE34B1EA11F6B82D
```

### `SCAN-UNCLAIMED` (89)

```
01C783D0D1CE8F90
03A60D807F8490C3
03CCBE7CDD23FC09
040B160EEE46D5E4
057ECBEF01AD87DE
13F7C3CC4E2AA910
171DF4B7CA1B966C
17DE58CAF91A7AE5
1A211D23A39B1067
2678F293EE09ECC4
28B989E1A47BFE38
292C07373CDEFCD3
2A3166D739D1D1B2
2D918FE31F797632
2EFBEA8BCF690F21
315335482F84E154
3167CABACB52F8C5
36A66AC9B8BE18B1
37FC4E3E7380A455
3D59E620E90762B0
3E131B2B1FF03476
3E5162613B91FA5B
3EA6FF274B9185BC
4A6872D2C37F0E62
511E232FE66AEDB0
5CFD73CFC7A37097
60510C3C7F2FE746
67585BD5E84C8EEB
68742CE1231125DF
6AE5AA21EDD53D10
6EDCDA71729E866F
7495CB73BC174325
75BC12E4AA0FD4D5
7B0BC67A5C441BF7
7EC25DDA575C0C43
81501512E1B6B243
81A518BE3385C2FA
82A0943C6B465403
848ADBAE57E5AB14
85F7E63A2FEF16F6
873E50962A1BCD32
87B48C32313B5B5D
8996A160173A7C19
8AE51A345F8524E9
8D8BBAE808EFBADD
8EEB0CF3497872AC
95C607A97DFB95D0
9884FE042173EAA8
99C8C9F9C206EC39
9D869A856C56D2E6
A008D125DEB1F4F0
A09D86E7C3C3A85B
A5EDEA12752FA427
A953984667DCABDB
A97C57C57DE3CB5E
ADAF9691931CFB91
AE2E9FC2F2C368BF
AEFB680076CF0542
B5C67C294BCEC862
B62B74DE4C99AC6E
B711ADCC8A8AB099
BAD20297265EF397
BC6C0E7A24856E25
BCC96877D8363892
BD3F77959DF40249
C4659AB94565583E
C9BE2B9EE5014F7B
CAC0867E682F731A
CF86634770A186B5
D6E07BDEC056B688
D976983D5106D8DE
DAEFEF33083F11C0
DC5725876FCD7E0C
DD86C0D6724662AD
DE8BEEA9F2EB5E35
E4141E0C32A06693
E6E6E99618CB25DD
EBBD56F5FE566F65
EF291D54F9922641
F072F45EE42012A9
F0D2899669C86B0E
F37970DB30895679
F5DA1E8E7900BA95
F8EE0316B23AAD2F
F9A7F0D6DA01CDF2
FC4587C605ABFDDF
FE6D02CCE028F6B6
FFD77AEC54CA0529
FFEBAF819F74A283
```

### `DECL:core_processor_sectioned` (22)

```
0808DD1E79FAE74B
29CA4402F172B7B9
337FE9AA2F7750D6
3E1F4145F82144AC
3E907CEFE6B6F4B4
4BE815516A392B34
4D806D550CFD5A5A
586B9481FFE276BD
627D9AE36DD28FB7
6BC052E9B49DB281
7088F5912CF22515
8AD1943146C53176
8CC1F233682E5B79
8CC3F4922CCB87A0
95246AAF1A2D7F59
9AACD0850F64A893
9FD4C16EA7364D5F
A3427B2BE24EB245
D03F4D27CC73202B
D59DE10944242B1E
DCF3A85ECE6CB67F
EF1C5806D1A584BD
```

### `PF-INVALID-PDF` (16)

```
1639623EBEBE780E
2AAD41D7B94A9734
3A427B1CB917FF42
4A0F7F21D2E4C61B
544B2947A2A7C656
5B87826CA305297E
6AE3B791993C500C
7B67D06FC36A32E7
864C83A248BEBE22
9DCC12B3B93DB206
B2BEF1ADEA11263F
B8806DECEF6452C8
BD72C8140CF35D66
E851A43593EF666D
EEE63EC6CEC84D94
FCF5A22575CB9DD9
```

### `FAM:cu_summary_of_accounts_date_posted` (13)

```
2046D9CEAE1BB42B
4C25E50F65E9BB19
53C929C29BBA7A7C
554486FB7B34EEA4
574D0EDA37087CC4
7DF42D168EF592B6
8C6F67293F3EF7DF
9DD441570C0076CF
A0A17154688E7BFA
A20A4F2DD3E4356E
D648556542E9D289
DB0E1737F4691450
EAF90DA0CC4E21E6
```

### `OCR-NEGATIVE` (13)

```
08D8D3B6DF17B63B
173C3E43651F8D99
1C6CB4078AC0644C
8E837AFE912B1048
9413957E2F56DEC6
98F73D0251873DEC
A28F62D0C1064235
A900066843940E01
BD2A40D672A2A5CC
E593F21E6B672449
E9CA26A655233663
EA916818FA6D49BD
FCA53A4DD928C42C
```

### `DECL:huntington` (12)

```
0DCABEBAE6D99BE0
1EEC7DABB4AB35E0
2D4E5714444ED7C3
46F2599A8757F72F
4AF6AB4A97E468F3
5D52C3A69E5A7FA9
7C351D71B06A3E10
89F586D7BA16DC32
BFA453F0CE2769A0
C15A2E0F14E89FF5
F14DAFC2118B3058
F7C683846985F86D
```

### `FAM:american_savings_bank_hawaii` (11)

```
200B4DB6ECAA46BF
3E2B2FE65EF9A4EB
61A59770D98439F0
6B22A09255A2B5A7
6E0E32AA00B76720
82BD2AB129E042D7
88D771CDA7C7EB4F
92EB76D889DF84BF
AF3CF313F96E5A04
D03A961937256A19
EA0FCD7850BBC0E3
```

### `DECL:community_section` (9)

```
01B82FEC38EEEF16
868ECE6AD6640AFA
8AB3A4213D009DA4
9D97506F7221D012
A90F51E67FB86E1C
C49144D76DCE44F0
E32EFCCCC63DA611
EA62440C2FB7330D
FA0B3967E477B9F7
```

### `DECL:core_processor_enclosures` (9)

```
0943986A52D8226C
2988BC5E90EA9FD8
33BF261CCC7C0CCA
373B73F98E63F900
3858F625B9881EAD
75FE7191FD4E74A0
BD835DA79B01B332
C355B3706588F0B1
D31770634E04E104
```

### `DECL:lili` (9)

```
0388628F8E576D31
80D07A7D64B5672D
9A841D10C92D6049
A3807F7D3956FCA2
B7BC8FF5A4EE3898
D6945B6F0F238A91
E9FA142EE9E0134D
FD250EFBC9599CA6
FE2C9E80A4001C76
```

### `FAM:mountain_america_cu_dot_leader` (9)

```
1BAA5D5CE5B9D592
36F9E9E232B58030
38642D4854FAAB74
607E46D7B0800101
85822DB14B966F29
B6C40C8C4C6BBF0A
B8A4CDE1808E30F8
F56290E40D40C5AE
FCE99FBDF5289F71
```

### `WH:frost` (9)

```
39309BCD56995684
4051FCDB5FDB82B7
794B22ED4AAB4D8D
9A08EDD6BAA34D4A
A3C4A174DC64FBBC
AB3B864D013F609A
B393D1C8A0FBB3C8
B46984457A8EBF5C
B818C675A47C57F0
```

### `FAM:cu_idaho_equation_summary` (8)

```
1E882271F57D157D
4FDCDEA7A42C4989
5624334A39D447C1
8A03D96FD8474EE9
92B653A0D8CD42D1
A4BC8F5F6A0FB3AB
B9DE5300BBC46138
F450831654CE4671
```

### `FAM:cu_unq_clt_trailing_minus_totals` (8)

```
193EE809ECDEE364
51F90E779AB0D06B
573EA76A9CD69D1D
58A3E63465F1DD33
65E9F798F60B8245
8E4DBE9C27ED5139
A612A5F5437001CE
D1B8E55A1BDBEFB9
```

### `FAM:guardian_cu_statement_summary` (8)

```
333E226A75FE5441
472A0966A5204513
596804AA1ACD01EB
7C7956EB5E93DB1D
C3D3E48F1E14AE2A
E38FA786106F752E
F5BC9FB6D084559E
FFAC0A88768A8A59
```

### `FAM:space_coast_cu_member_statement` (8)

```
0624AC4689BA526C
272041FB15350E44
62C13D4F0FF38474
6D0E6BA50DF1CAF9
78E2647278EC502A
7B48A1E7134F90FE
7D31DD8257D6026B
CF1338DDC23EAB04
```

### `FAM:wpcu_summary_of_account_by_transaction` (8)

```
1A606C1476CB49B4
37005BADB33376A8
826E04939F2AFE74
BC692377D862E205
C35598E63654727A
E4405190715B334D
E46D8DBAA5B02699
FDA61D31378FF484
```

### `TEXT-LAYER-DEFECT` (8)

```
19ED81F23EC1531D
2D486AA4A94B5896
2E957B7DF84494B3
367DC3C3265D696B
5B76F0B19AB02C5D
69D3AD2FE8AD8201
720C4C37AD3F9B76
ADB91E10278C8121
```

### `FAM:paypal_account_statements` (7)

```
3FEE1F2D3D5A88B7
503711E979E42DC3
582D6AC9426733FB
7F7C50B5E6F0E954
967C589E93D16401
F13DAAE34C3C46C8
F6E2E1B80BA6CDDD
```

### `FAM:truist_your_account_statement` (7)

```
07A0913077CFE056
43784B8A67C40798
663B51261DFF46C5
9C4E5EDCE424A803
A5DA09E8618EBB03
A8558BAB37C98F3F
C56409CA2F4628B6
```

### `DECL:bmo_ca_business` (6)

```
09CAB64775AD7F8F
0B1E11FD0B024EEE
183928E50AAAE255
1BB68B31D9D09EA3
581CEC3273DFB85B
BA9D67DF60A53DA7
```

### `DECL:capital_one` (6)

```
38C1A3EA047CA747
4BD7B234EAFA0130
5A6B0A2385AA5210
685246A457DD4899
C74CB8708351DAEB
EA51981AE97B4F3B
```

### `DECL:navy_federal` (6)

```
0629A2DC8C335F11
2A0F4E83C59F2A94
78EA3605EC232D95
9197694CB883B6B2
B8A40B218D229BF1
BFE8213B09FA1E13
```

### `FAM:capital_one_360` (6)

```
16605579044C7D97
582B2EFAEED06E3F
61ED1EA3AA891D93
C92D574C1E005223
D7FA68731422AC0C
F2BC8EED8E58C888
```

### `WH:rbc` (6)

```
142E1DB7CB103EFB
16174BD143C4702D
42405BDA7E97986B
503DDEE755E7A4AD
B834D69701C0D40D
FD82EBEFDCBD3FA5
```

### `FAM:altura_riverside_cu` (5)

```
3C72611C002FC81C
3D2098AE571B53CB
576367B4F4124119
6E30DAB8DA51D3EA
B2019068FA2FA9BD
```

### `FAM:beem_credit_union_bc` (5)

```
16F3C31E9C757150
23FDA98BD99EBB1D
2C948423B1204168
9979AEBF6A38BB06
FAD1CB6320180E48
```

### `FAM:chesapeake_bank_activity_in_date_order` (5)

```
18A33B29F500239E
54C55E7FB9F0E49C
615305CFCEB7B260
B0A280A3F70D3158
FE237BF9465CBB71
```

### `FAM:chime_bancorp_checking` (5)

```
298CE16010532430
3BEE554535974F7F
659A7C06C76C0075
9DE68C11B95C5203
DFF6FB0C93B51788
```

### `FAM:cubase_suffix_box_summary_history` (5)

```
1DE09FAE4185E4A1
458B42D3BEAF105A
AAAC3125C9B69ACA
C32D4729CD93A536
F921E27F9C247E5E
```

### `FAM:dfcu_financial_account_statement` (5)

```
2007DE85CAF9D970
8D0554E2A0C677BD
9E97EE0CA842A3D3
AFE8053C4899B0E8
CCC8C4019025C0F6
```

### `FAM:old_national_free_business_checking` (5)

```
55DF08BDAB9399A8
6BAE586D2838FC09
6CE2546424B3F910
87DCA85DB7660800
9F67C53D38F3DD98
```

### `FAM:pr_business_plus_corp_statement_of_account` (5)

```
41EAFACAA0FCDF49
53553C788ADB50FB
650A062450352B3B
95D41C76FAA009D2
C3624E68DB6E8924
```

### `FAM:rbfcu_business_member_statement` (5)

```
16EFD50B640FF361
6F721D4487BEFCB9
8346B18E10AADAA9
C8264D9A0F79959F
F7D702B7B71342AD
```

### `FAM:wescom_cu_equation_summary` (5)

```
0A7A025F6FB66500
4E2FD250B3123AE2
4F95815AA215D7EB
7CD6F8282CB8FEA9
D473A9338CAE9574
```

### `WH:southside_scanned` (5)

```
0E887D8EC7525F3B
3B0738E968D43202
9D7EB67ADE0A8A39
B311029716C1206F
FD022A8600DA35AE
```

### `DECL:columbia_bank` (4)

```
0CBD2AD897B90137
2E667295DFCB16BA
6ADFE63F4F745B8B
88AAC06119FC0B7D
```

### `DECL:core_processor_daily` (4)

```
0FFA1DA3837F5518
2FC2A756EE5A8C50
790B4EA8224B8ADE
DE92B503B2EFF9CB
```

### `FAM:access_fcu_member_statement_of_account` (4)

```
A73014E132333CA4
B53613DD7BFA3DEF
BF4D9BCDF0283514
E9C75B967303B444
```

### `FAM:associated_bank_financial_statement_of_accounts` (4)

```
2C0A230A83A11FA7
4C4EAE7A79B5583C
6B8B49B0C190146F
86355161E964F37A
```

### `FAM:atb_financial_consolidated_statement` (4)

```
284B775D64C9F1F9
745B2968DC5A0197
EE09ADA6FCD4637A
F1DA262D1C28D1AB
```

### `FAM:bank7_summary_of_accounts` (4)

```
07C874CCC28F85F5
39BCEC8D522E9099
49F18A6ED9520BD8
84C4BE9824D45F63
```

### `FAM:bank_of_tennessee_activity_summary` (4)

```
68ABA4BC07F2C162
6A96F8DA638799BC
9B1671E016220E58
B50EDDCD909A40A9
```

### `FAM:becu_deposit_and_loan_activity` (4)

```
039BE1BED4840952
77800C8DCB552108
9494F27ED35BE2E9
F3350960AD73AFFC
```

### `FAM:bokf_business_access` (4)

```
5A5FDD3FB7AED636
C1C954F932F175D7
E2AA4A12F03DBCFD
EAB8FD5941314C4C
```

### `FAM:city_national_bank_florida` (4)

```
082219AD531A6A03
66800C3774B1AFF1
BEAD76F55A7375F9
CBD038618A4BAEFE
```

### `FAM:commerce_bank_mybusiness_checking` (4)

```
11D0F46DC2CAB241
5EDDAD75540957AC
7C2331AC1F695BAE
B64BE4A0E069A66B
```

### `FAM:community_savings_bc` (4)

```
49D2A1794375A94D
7CFA22EDDFEF552D
BFD6167706794EBC
D0A6F2DEA0D32264
```

### `FAM:cu_statement_summary_prev_new_balance_unbranded` (4)

```
47F8514AE17416CF
AA257B9EAB430350
D2D2ABE4275AC46B
D6E72C89BA62C42C
```

### `FAM:fulton_bank_account_statement` (4)

```
34DCE89546A40CF5
3CC3DB128BADFFB6
76549EE4389F64FC
83170CCE7832364E
```

### `FAM:goldenwest_cu_member_account_statement` (4)

```
201B3B3D5F597D28
5C6B0555BB0B6257
A137F6D65E29CAD5
F443964447A44FC1
```

### `FAM:greater_nevada_cu` (4)

```
770F8DD0404E6081
C1C12193EA6AEAEA
D8278B18E789FE39
DAC49AD1DF91AC14
```

### `FAM:green_dot_bank_partner_program` (4)

```
055A3863CB800D9B
18DC970783704F78
AF9E7AA6ECD05B9C
DD3F97FDADDDA54E
```

### `FAM:hapo_cu_estatement` (4)

```
0933021A33F1DC4A
8B640C6A89D81B32
B53912D549B25101
FA078B47381E23F2
```

### `FAM:ion_bank_customer_statement` (4)

```
62001A0434BC44DB
C61CA61AD9CD86E8
CB85DB48BF5D069B
D6C8DCE6285406E8
```

### `FAM:jh_spaced_caps_checking_summary` (4)

```
4BE2A56DFCCDC00A
52658F9C9A782055
C6FE5EE0B55ED2C3
F2316D8D0DDAD0C9
```

### `FAM:nbkc_bank_dda_statement` (4)

```
11D1DDBCC3BCE4F5
307187CA1EA1F933
36F9981C9F025DC1
370B9256BA110FC1
```

### `FAM:novo_monthly_account_statement` (4)

```
24755C040FDB9568
4D46C511184497A6
C42941520EA612BB
DF5CDF8F4B7AB6CF
```

### `FAM:ornl_fcu_oak_ridge` (4)

```
2A39E0BC5EB09B88
70DBD87373563364
DABCBBB011E51CBC
EC66EA1AA7D2298C
```

### `FAM:palmetto_citizens_cu` (4)

```
3B4FE87E8586A3BD
9844A367DC57A131
E9DD69D7CCF4F1AF
EB165260EA113EE6
```

### `FAM:pnc_core_commercial_checking` (4)

```
059FBDC9539A0D94
8E830F06DC3D72F7
A4F79D175A8686FD
ABDC6C8EBE3EDEF0
```

### `FAM:pnc_treasury_enterprise_plan` (4)

```
5BDEAC480C50BD57
92B161D89019118E
9607A01E00D167F1
A88122B84542B4ED
```

### `FAM:pnc_virtual_wallet_performance_spend` (4)

```
028A40341991F9A5
392712FC2E9E6919
3EA2CEF559AD67D4
CC533142FA14EDD5
```

### `FAM:psecu_shares_at_a_glance` (4)

```
2D1B80B92D720B02
35B503DD81B6C489
5A40F2B44C7AFDCA
9814E42F9CDF89CB
```

### `FAM:redstone_fcu_statement_of_accounts` (4)

```
0366FDF251AD0D32
203E8D2EC4631B68
7CDCEE2B9BC2C5B7
8659960717EE4AB1
```

### `FAM:security_service_fcu_asterisk_sections` (4)

```
06F4CF26F0A73C71
3DB81A2CEAFCEDCD
740670FA2A9F47F2
A7C6D1682504A2C3
```

### `FAM:sierra_central_cu` (4)

```
3920A0E77BE2850F
510993B1B8CAF139
89C644EFD337581C
D322B95D1284D35A
```

### `FAM:st_marys_bank_nh` (4)

```
0D2F43222E8AB491
52E7045D5655B5C2
C50FADE975E05745
FF5D613E0308F203
```

### `FAM:suncoast_cu_account_statement` (4)

```
0D2AC06CC734F16D
39462E4FAE7414EC
404CF3726C6A5FEC
B2F2627A213E1372
```

### `FAM:synovus_pinnacle_portal_statement_view` (4)

```
5067B6B76C38CE31
515F0ADF0A5C3E67
F56CDBB3CCBBB8CA
FAE6050A8F81831D
```

### `FAM:townebank_balance_summary` (4)

```
109829BBA4AD538E
5787A09F6D382E7E
A5BAD30E8234394B
CEA84CFA70241972
```

### `FAM:usaa_fsb_classic_checking` (4)

```
2014B141CA507B9B
80FE707815B509E9
937DCCDA51C88032
C5CB05E28B201185
```

### `FAM:vystar_balance_summary_transactional_detail` (4)

```
24C879724BAF6D7B
2DA7A3F496E8D46C
9F1FD3D18E3221F8
D4E905D5F0C571FA
```

### `FAM:vystar_business_checking_analyzed` (4)

```
2C9C57112D0F2FAB
3EF898B20DCED0BC
9D19277503AB705E
B259126FE7FAACB7
```

### `FAM:wisely_adp_paycard` (4)

```
135362861CBF9616
24B2C6FC3B5674E9
594E4BA83342859E
F69247AE6F5DA7A9
```

### `RV:chase_export` (4)

```
112431717DA12CA4
5A29258D7626A561
5C93775BBA875217
E5C8D422FDBE9277
```

### `RV:linkbank` (4)

```
4A38F944469B8A43
931AA83E94362F52
AF6BD563A3D7165A
E002430E81CADFE7
```

### `WH:bmo` (4)

```
009BCF1055FBE62E
72D259CA8B8A9C1B
AE953B1A2E4129F8
E86143101E28E198
```

### `WH:pnc` (4)

```
1F31588B36B2E4AF
4145E2C82C6B8329
5684857C24B79344
BE703D525955253C
```

### `WH:wells_fargo` (4)

```
3725BB1189EA74D5
59FAF1FC17745A6E
938D4BEBF401A03D
A4E41C80E7362D58
```

### `DECL:category_partition` (3)

```
6E9A3A110E6829EB
889DAEBE7D79133C
C47BEFE559CB8600
```

### `DECL:consumers` (3)

```
394291917794798D
593EC5C237F5C6AA
9B8E7D807228DA2B
```

### `DECL:scotiabank` (3)

```
A63E37F95056FDDE
ADFE654CC9FE211E
B49461502EABA7CB
```

### `DECL:texas_first_scanned` (3)

```
33A2F2DD6CAF1791
8FC408139D8A437A
9B3DB6CF995DB68B
```

### `DECL:truist` (3)

```
2C3766D86270D70E
AD9997D34B3EC8F2
C65EC1947F8F95BC
```

### `FAM:altra_fcu_statement_summary` (3)

```
03630BDEBDFB60C9
2A8F1A9D95DD0672
B385771D2521F72A
```

### `FAM:bangor_savings_three_count_summary` (3)

```
19E3AE590011C036
2ECD7C8C3035BC45
E0805CCD1DCC5A59
```

### `FAM:champion_cu_statement_summary` (3)

```
0208F10F797B1743
7487DA2E68EC3134
D2357D69622CFE40
```

### `FAM:core_enclosures_avgledger_leading_counts` (3)

```
0D1BCE71A8397373
12EAD3A8C2CEBAFA
5ED19A08317E0D12
```

### `FAM:eastern_bank_customer_statement` (3)

```
7223BAA25DF20F84
A7EBB8C87C394698
D8366FDA93C39BC6
```

### `FAM:greenstate_cu_post_eff_type` (3)

```
279BD8E5E83DFDA0
76AB6D1AC341538A
7BAEC76ABE889B76
```

### `FAM:heritage_south_cu` (3)

```
38717970EAED51B6
5EF0F71F080F7973
C61EFFECCA18B379
```

### `FAM:hudson_valley_fcu` (3)

```
0C78E2F2FA203C14
5970FDF20E7CE901
943CCA7B9C8BC269
```

### `FAM:mt_bank_account_activity_daily_balance` (3)

```
53DF0008FCEB9C15
7FA2051357EDDB37
F40D49B89E1E5D3B
```

### `FAM:mt_bank_customer_statement_treasury` (3)

```
35088A1B458FD1FF
9195C49BCE4EEB29
A0894D5A0B716D56
```

### `FAM:pima_fcu_statement_of_account` (3)

```
32F2BA7871C2FC2F
42113E197C631D08
BAD849239ED62579
```

### `RV:found_lead_activity` (3)

```
3C32452110B2600C
D797FB9B035ADCD5
EB8908909B4E4E2D
```

### `WH:citizens` (3)

```
5198A34DB12B0D84
675EB43935FEDA73
FA7ED54A969FAD65
```

### `WH:eq_bank_scanned` (3)

```
5C65DFB2A096997B
75AE79521F5DC0B1
958322F16B7F21EA
```

### `WH:farmers_merchants` (3)

```
4CC3DE36B4895660
5BE3147453261138
DAC9ED50E290AC71
```

### `WH:scotiabank` (3)

```
125127F359039F2F
B52CDF2BA874BBB4
D00562176BEC0AAE
```

### `WH:td_us` (3)

```
1A8B92DC61678F71
2A0B516B2C7D652E
D3396D14BA8A6A4A
```

### `DECL:banco_popular` (2)

```
CE5A47BCA5A40EBB
E76A7856D2CAFD34
```

### `DECL:bank_of_america` (2)

```
9E51C8E2F10E2575
EEE8629494E764EE
```

### `DECL:bluevine` (2)

```
0659456EEE4F0F43
D20965F33549707C
```

### `DECL:eq_bank_scanned` (2)

```
B0E16E92A1ECFDFB
E630CB66DBDB3C1D
```

### `DECL:ibc` (2)

```
7A232770A4475902
7BD8711EC9DFD186
```

### `DECL:santander` (2)

```
31CE951B09EE927D
B0558F1186BD97BD
```

### `DECL:td_us` (2)

```
7645F0A8583CD86F
A7E4B895E2A96F96
```

### `FAM:firstbank_colorado` (2)

```
4577474CBE35E5CD
733E522E4C221ED9
```

### `FAM:firstbank_pr_escrow_pipe_header` (2)

```
3F4139243F9C2F5A
E31B7B02B7EC5866
```

### `FAM:umb_essential_business_checking` (2)

```
8ABEE7F32EC60078
F8E3E2E9F78F76E8
```

### `RV:community_section` (2)

```
008E53F5C39E6766
25038CB7E38DB036
```

### `RV:southside_scanned` (2)

```
4C96DDA28A6728FB
90A1EBAC3745317F
```

### `WH:atb` (2)

```
1B6768E84D00C4B2
7F2B71AFDD7F901F
```

### `DECL:apex_scanned` (1)

```
71864C4034B5CADD
```

### `DECL:chase` (1)

```
681171A74E76ED7D
```

### `DECL:cibc_french` (1)

```
73C253BA7528A51F
```

### `DECL:first_farmers` (1)

```
8035EE1A5453C75D
```

### `DECL:pnc` (1)

```
31E43C6F9393CA15
```

### `DECL:rbc` (1)

```
BFEB79B26E426C2F
```

### `DECL:wealthsimple` (1)

```
C307782D0559CC6C
```

### `DECL:welch_state_bank` (1)

```
361167E3A263C346
```

### `DECL:woodforest` (1)

```
4410084695A06C96
```

### `FAM:bofa_business_advantage` (1)

```
B5F4A9F6F8D595CF
```

### `FAM:chase_total_checking_transaction_detail` (1)

```
EA4B7F19D508C7C8
```

### `FAM:conexus_cu_demand_products` (1)

```
AFCEEC6A21F05614
```

### `FAM:cu_suffix_transfer_acct_grid` (1)

```
9AE97A14516FFB18
```

### `FAM:desjardins_accesd_releve_operations` (1)

```
522051A65595F7F6
```

### `FAM:laurentian_bank_current_account` (1)

```
577EC96A31F290AB
```

### `FAM:onepay_coastal_community_monthly` (1)

```
1104CA62ABDFB547
```

### `FAM:pc_financial_pc_money_account` (1)

```
7A872347F4970FBF
```

### `FAM:ramp_business_account` (1)

```
B988C19C86AE595E
```

### `FAM:relationship_summary_daily_balance_unbranded` (1)

```
9D985F70CD543CCD
```

### `FAM:rho_deposit_account_statement` (1)

```
367CDBACFBA9A8F5
```

### `FAM:southern_bank_quadruplicated` (1)

```
FC129FA3BD5A670E
```

### `NO-TEXT` (1)

```
A9D3C95326B1686D
```

### `RV:citizens` (1)

```
13B6B39D629BCA0D
```

### `RV:core_processor_enclosures` (1)

```
68D4F9F06AA764D9
```

### `RV:texas_first_scanned` (1)

```
A20AACF22B6A475A
```

### `WH:capital_one` (1)

```
538375B8A6BD9D8F
```

### `WH:core_processor_enclosures` (1)

```
90A62FB5A03A9A25
```

### `WH:ibc` (1)

```
413AD4C2FBFB71A0
```

### `WH:regions` (1)

```
B4855A59F6E14D58
```

### `WH:relay` (1)

```
4D7CD4EBDA968759
```

### `WH:zions` (1)

```
595137FD1861DCCD
```
