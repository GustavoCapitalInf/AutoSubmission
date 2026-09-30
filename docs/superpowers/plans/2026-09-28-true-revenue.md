# True and Verified Revenue (classification 5.5 and 5.6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. Every task is sized for one implementer and one independent reviewer, and ends with a deliverable its own tests prove.

**Goal:** Make "True revenue" (every posted credit minus known non-revenue minus the credits held for review) the headline, with "Verified revenue" (the part with positive proof) beside it, and fix the vocabulary and precedence bugs that hid revenue, in two releases on one branch: classification **5.5** / analysis stage **24** (the fixes, spec §7) and classification **5.6** / analysis stage **25** (the definition, spec §5, §8 to §12).

**Architecture:**
- **S1 (registry and vocabularies)** adds the hand-kept tables to `analysis/classification_registry.py` (operating sources and their 16-character cuts, payout and card-settlement forms, auction forms, healthcare and dealer-funding payers, the BNPL ruling) and their validator `tools/operating_registry.py`; S1.5 carries the ledger admissions through the ledger's research process.
- **S2 (classifier 5.5)** adds the credit revenue readers (revenue text, payer region, entry fields, the holder test, the numbered-company guard, the channel gate) and the street-`LN` guard, then the family helpers, then the rewritten credit decision of §6.1, then the statement passes 4 to 6, then the 5.5 version.
- **S3 (census)** adds `tools/revenue_census.py` and runs the 5.4 to 5.5 census before any 5.6 code lands.
- **S4 (classifier and payload 5.6)** adds the tier vocabulary and the per-row contract, the true-revenue pass (`analysis/true_revenue.py`: holds, Q5, Q6, tiers), Q7 dealer funding, the tiered metrics and serialized views, then the consumers, the docs and the 5.6 version.
- **S5 (webapp)** serves the revenue flags and the N/A rules (`analysis/revenue_view.py`), the package figures, the gate and the True-revenue withholding mode, the exports, the review routes and the replay.
- **S6 (dashboard)** shows True revenue first, the four tiers, the reasons, the Held for Review view, and the Monthly Statements and chart in three shades.
- **Acceptance (A1 to A4)** runs the 5.6 census and every guard, the tryout host's census read-only, the precision sample, and the train.

**Spec:** `docs/superpowers/specs/2026-09-28-true-revenue-design.md` (approved, owner review §19: every recommendation; OQ5/T18 and OQ6/T19 **on**).

**Tech Stack:** Python 3.14 (`C:/Python314/python.exe`), pytest 9, `re`, dataclasses; vanilla JS (`webapp/static/app.js`, driven in node through `tests/webapp_js_harness.py`). No new dependency.

**Prototype (the code below was run, not only written).** Every code block of Tasks S1.1 to S6.3 was applied, task by task, to a scratch clone of this branch at `4227a76` (`C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/stage`, one local commit per task), and each task's tests were run there: failing before its implementation, passing after. The full suite was run at the end of S2.4, S4.4, S5.2 and S6.3 with every failure bisected to the task that caused it (the pin ledger), and again at the final commits of S2.5, S4.5, S5.2 and S6.3; at those four the only failures are the 16 known ones listed in `C:/Users/GustavoPrietodePaula/lender-research/census/failed-ld-final.txt`. The census figures of S3.2, A1 and A3 were measured with that code on the corpus cache. Of the scratch scripts in S1.5 and A1 to A4: S1.5's guard tests, A1's G7 check and A4's seed script were run; A2's copy script was compiled and its decoding checked on a fabricated jobs table (it was not run against the host); S1.5's gate script waits for its research file. Line numbers are those of the file as the task finds it (after the tasks before it).

**Revised after review (2026-09-29).** Every change listed under "Revision after review" was made in the prototype first; the per-task clone was then rebuilt from `4227a76` by the same scripts (branch `plan-stages-r1`), each task's tests were measured again before and after its implementation, the four selections at every task commit, the full suite at S2.5, S4.5, S5.2 and S6.3, the census at 5.4, 5.5 and 5.6, and the lender census (G7). Every figure below is from that run; S1.5's admission-effect script and A1's G7 check with an allowlist were run on fabricated inputs (a one-record research file, a one-row move).

**Sources (PRIVATE: they hold real payer words; never copy a person's or a private business's name out of them):**
- `C:/Users/GustavoPrietodePaula/lender-research/revenue/`: `trace_report.md`, `definition_memo.md`, `digest_families.md`, `hunt_result.json`, `fly_credits.json` (the tryout host's per-payer credit dump), `work/spec/` (the spec's review and revision probes).
- The plan's scratch folder `C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/`: `proto/` (the finished prototype), `stage/` (the per-task clone), `stages/*.py` (the scripts that built each task's commit), `run_snap.py` (the parallel census runner), `census/` (the digit-masked corpus copy and the first run's snapshots and reports), `rev1/` (the revision's scripts, probes, snapshots, reports and suite runs).

## Owner rulings this plan implements

- **Q1 to Q8 (2026-09-28, spec §2):** two figures (True revenue, the headline; Verified revenue beside it); cash, branch, ATM and bare deposits, checks and person-to-person counted and flagged, never verified; wires verified on two or more from one company or on an invoice or PO; named ACH/EFT payers verified on a repeat, a company form, or a government or healthcare payer; an auto lender's dealer funding verified; payroll and salary held.
- **§19 (2026-09-28):** OQ1 payer-wide review is a follow-up (not in this plan); OQ2 the BNPL settlements (Affirm, Klarna, Afterpay, GreenSky, Sunbit) join `PAYOUT_CREDIT_ENTITIES` (Task S1.4); OQ3 numbered-company payers are counted, flagged, never verified (T11, Tasks S2.1, S4.2); OQ4 the deferred items of §15 stay counted or held until ruled (nothing in this plan decides them); OQ5 `HCCLAIMPMT_CLAIM_FIRST = True` (Task S2.1, used by S2.3); OQ6 `THIRD_PARTY_BOOK_TRANSFER_AS_WIRE = True` (Task S2.1).

## Global Constraints

- **Where you work.** Only in the worktree `C:/Users/GustavoPrietodePaula/work/true-revenue` (branch `true-revenue`, from `lender-detection` at `c106634`; the plan starts at `4227a76`). A shell starts in the MAIN checkout, so every command starts with `cd C:/Users/GustavoPrietodePaula/work/true-revenue &&` or uses `git -C C:/Users/GustavoPrietodePaula/work/true-revenue`. Never edit, stage, commit, check out, stash or reset anything in the main checkout. After each task, `git -C "C:/Users/GustavoPrietodePaula/OneDrive - Capital Infusion/Desktop/Capital Infusion Projects/bankStatementAnalysis" status --short --branch` must print only `## lender-detection`.
- **Versions (spec §9.3, verbatim):** "5.5 (the fixes, §7): `CLASSIFICATION_VERSION = "5.5"`, and `ANALYSIS_STAGE_VERSION` 23 → 24 in the same commit." "5.6 (the definition, §5, §8): `CLASSIFICATION_VERSION = "5.6"`, and `ANALYSIS_STAGE_VERSION` 24 → 25 in the same commit." Task S2.5 makes the first bump, Task S4.5 the second. Tasks before a bump change output under the older number: the branch merges as one unit and no intermediate commit is served.
- **Precedence invariants (spec §6):** "Non-revenue rules run first: loans, transfers, refunds and owner money never become revenue." A row that a non-revenue rule decides stays `non_revenue` "except through exactly these seven named narrowings" of §6.3 (REIMBURSEMENT with a claim signal; HCCLAIMPMT from an insurer, T18; an insurer's customer payment, held; a third-party BOOK or FUNDS TRANSFER, T19; a street `LN`; a released card credit; Q7 dealer funding), plus the owner's OQ2 ruling (BNPL settlements). "Nothing else leaves `non_revenue`." Steps 11 to 14, Q5 and Q6 never verify a row the holder test or the numbered-company guard matches. Every guard G1 to G14 of §14.3, and the review's G15 to G17 (no refund word, no tax refund and no holder's own ACH transfer in True), holds (Task A1).
- **Constants (verbatim):** `HCCLAIMPMT_CLAIM_FIRST = True` and `THIRD_PARTY_BOOK_TRANSFER_AS_WIRE = True` (§19); `REVENUE_REVIEW_HELD_SHARE = 10`, compared as `held_cents * 100 >= REVENUE_REVIEW_HELD_SHARE * posted_cents` (T7); `OPERATING_ALIAS_CUT = 16` (§7.0); `CREDIT_UNION_DEALER_MIN_CREDITS = 2` (§8.7); the round sum is at least $100 and a whole multiple of $100 (§5.2); the micro-deposit floor is $1 (§7.0); `_NET_SETTLE_MIN_CREDITS = 3` (§7.1).
- **Withholding (§11):** the default stays `legacy_eligible_deposits`; `verified_revenue` stays selectable; `true_revenue` is added and is never the default.
- **Field names (T9):** `revenue_classification`, `verified_revenue_*`, `unverified_deposit_*`, `non_revenue_*`, `maximum_revenue`, `confirmed_true_revenue*` and `potential_revenue*` keep their meaning; `true_revenue`, `contributes_to_true_revenue` and `true_revenue_evidence` are repointed to True revenue; a payload analysed before 5.6 has them nulled or removed in its served copy (T10).
- **Privacy.**
  - Tests are FABRICATED in the bank's printed format: names `FABRIKAM`, `CONTOSO`, `NORTHWIND`, `SAMPLE`; dates in 2031 or 2054; whole-dollar amounts (the privacy canaries of `tests/test_no_statement_hardcodes.py` and `tests/test_webapp_studio_views.py:16` flag cent figures). Public companies (processors, marketplaces, agencies, insurers, lenders, government payers) may be named.
  - Never copy a person's or a private business's name, an account number, a statement amount or a statement date from the research folder into code, tests, docs or a commit message. The census writes only outside the repository (the tool refuses a path inside it) and masks every digit.
  - Commit messages carry no statement value; scan each message before committing.
- **Tooling.**
  - Write or patch Python and JS with the Write/Edit tools, never with Bash heredocs: the Bash tool mangles backslashes here, and almost every block below has them.
  - Run tests with `C:/Python314/python.exe -m pytest <paths under tests/> -q -p no:cacheprovider` (a bare `pytest` also collects `discovery_reports/`). The dashboard tests need `node` on PATH (`C:/Program Files/nodejs/node.exe`); they skip without it, and a skip is not a pass for S6.
  - Restart Flask after a template edit when checking in a browser (Task A4).
- **Stop rules.**
  - Never re-pin a real-statement test to whatever the code produces; stop and report instead. The only assertions that move are the rows of the pin ledger below, each to the value it lists. Row 35 is a real-statement assertion (`tests/test_new_statement_corpus.py:476-478`): it moves only on the owner's word, asked in Task S5.1's first step; without it, S5.1 stops before its commit. Any other failing test (for example `tests/test_new_statement_corpus.py`, the ATB/RBC/TD pins of `tests/test_transaction_classifier.py` and `tests/test_revenue_classification.py`, `tests/test_analysis.py`) stops the task: report its id to the orchestrator.
  - A census guard that fails (S3.2, A1), an undeclared verified demotion, a debit move G7 cannot trace to the owner's signed-off admission list, a target outside its tolerance that §4 does not explain, or a precision stratum below its bar (A3), stops the release.
  - A research entry that is not VERIFIED is never added to the ledger (Task S1.5).
- **Commits.** Each task ends with one commit: the exact `git add` paths and the subject it gives, and the attribution as a second message: `-m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`. Never push.
- **Test selections** (baselines measured at `4227a76`, 2026-09-28):
  - **SEL-CLASSIFIER** (755 passed, 2 deselected): `tests/test_recurring_fixed_debits.py tests/test_unknown_payee_naming.py tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_new_statement_corpus.py tests/test_flagged_positions_payload.py tests/test_obligation_descriptors.py tests/test_known_payee_classification.py tests/test_flag_group_states.py tests/test_classifier_lookups.py tests/test_financing_proceeds_credits.py tests/test_factoring_credits.py tests/test_premium_financing.py tests/test_analysis.py tests/test_batch.py`.
  - **SEL-REGISTRY** (357 passed, 4 skipped): `tests/test_lender_ledger.py tests/test_build_lender_registry.py tests/test_lender_registry_drift.py tests/test_lender_registry_content.py tests/test_classification_registry_groups.py tests/test_payee_matcher.py tests/test_lender_alias_audit.py tests/test_lender_census.py`.
  - **SEL-WEBAPP** (856 passed): `tests/test_flag_groups.py tests/test_flagged_view.py tests/test_webapp_settings.py tests/test_webapp_flagged_positions.py tests/test_webapp_flagged_dashboard.py tests/test_webapp_reanalysis.py tests/test_package_currency.py tests/test_webapp_app.py tests/test_artifact_cache.py tests/test_webapp_revenue_batch.py tests/test_webapp_review_ui.py tests/test_webapp_studio_views.py tests/test_privacy3_boundaries.py`.
  - **SEL-REVENUE** (the new files, as they exist): `tests/test_operating_registry.py tests/test_revenue_text_readers.py tests/test_revenue_rule_helpers.py tests/test_revenue_card_settlements.py tests/test_revenue_platform_payouts.py tests/test_revenue_healthcare_claims.py tests/test_revenue_payer_remittance.py tests/test_revenue_public_payers.py tests/test_revenue_wire_remittance.py tests/test_revenue_non_revenue_55.py tests/test_revenue_recurrence.py tests/test_revenue_census.py tests/test_true_revenue_payload.py tests/test_true_revenue_tiers.py tests/test_webapp_true_revenue.py tests/test_webapp_true_revenue_ui.py`.
  - A task's Step "run the selections" runs the selections its files touch; each count moves only by the task's own new tests and the pin ledger's rows.

## Services, tasks and order

Spec §16's order: S1, then S2, then the 5.5 census (S3), then S4, then S5 and S6 (S6 after S5 here, because its tests read S5's served keys), then the acceptance tasks. One implementer per service task and one independent reviewer per task (the orchestration model policy); the orchestrator checks each report's evidence before accepting it.

| Task | Title | Depends on | Its tests prove |
|---|---|---|---|
| S1.1 | The operating registry and its validator | — | the new entities are typed, the 16-character cuts, the processor gate and its derived table, the structural-lens processors wait (searched read-only), a validator that refuses an untyped entity, a financing collision and a bare alias ahead of its advance product |
| S1.2 | The payout, card-settlement and auction forms | S1.1 | every form compiles, names a typed entity and reads no financing or insurer alias |
| S1.3 | The Blue-plan, healthcare and dealer-funding payer tables | S1.2 | a healthcare alias that is an insurer alias is refused |
| S1.4 | BNPL settlements are payout-credit entities (OQ2) | S1.3 | the five BNPL entities are payout-credit entities and their debits keep their group |
| S1.5 | Ledger admissions (research, then the owner's sign-off) | S1.1 to S1.3 | the bare processor aliases follow the ledger; admitted products, financiers and lenders read as financing; G7's allowlist is the owner's signed-off list |
| S2.1 | The credit revenue readers and the street-LN guard | S1.4 | 68 reader cases in the banks' formats (the holder's own ACH transfer, Santander's originator, the French depot among them) |
| S2.2 | The 5.5 rule vocabulary and the family helpers | S2.1 | each helper on one fabricated row, positives and negatives |
| S2.3 | The 5.5 credit decision | S2.2 | every family's positives and the verifiers' negatives through `classify_transaction`; §7.9's 40 cases, hazard groups G1 to G11, party-name rows and recorded residuals; the ledger gate on Stripe's cut; the glued tax refunds |
| S2.4 | The 5.5 statement passes | S2.3 | recurrence, the pool that never shrinks, the vetoes (FUNDING outside three platforms), auctions and §14.1's §7.8 negatives, property platforms, the counter-debit guard |
| S2.5 | Classification 5.5, analysis stage 24 | S2.4 | the version pins; the full suite |
| S3.1 | The revenue census tool | S2.5 | shares, narrowings (only the five BNPL entities, only a printed third-party originator), demotions (an undeclared one fails), every row and account guard G1 to G17, G7b, G9's four ways, lender moves by cause, the sample, the refusal inside the repo |
| S3.2 | The 5.4 to 5.5 census | S3.1, S1.5 | the measured 5.5 figures, `guards: all hold` |
| S4.1 | The tier vocabulary and the per-row contract | S3.2 accepted | the flags by state and tier, 26 reasons, a record's own tier, a duplicate's tier |
| S4.2 | The true-revenue pass: holds, Q5, Q6, tiers | S4.1 | every reason code, the holds, Q5 and Q6 and their guards, the four-tier identity; refunds, platform capital, the holder's own ACH transfer, paychecks, PPD, title and bank payers, card and auction refunds, and a push-rail wire, each alone and repeated |
| S4.3 | Q7: an auto lender's dealer funding | S4.2 | a listed lender verifies, a lender or insurer outside vehicle financing never does, the credit-union arm needs two |
| S4.4 | Metrics, detection, serialization, serialized views | S4.3 | the tiered metrics and views, the gate in cents, confirm/reject/reset, the tier-less path, the refusals |
| S4.5 | Consumers, docs, classification 5.6, stage 25 | S4.4 | the batch columns, the CLI report, the benchmark's True-revenue row; the version pins; the full suite |
| S5.1 | The served copy and the package figures | S4.5 (and the owner's word on pin row 35) | the package's True revenue, N/A for an older member, the verified total and its aliases N/A together, the served copy of an older payload, the true-revenue mode |
| S5.2 | Exports, review routes, replay | S5.1 | readable by-reason rows, the rule-verified reject and refused confirm, the decision-aware replay; the full suite |
| S6.1 | Cards, credit mix, Held for Review view | S5.2 | the cards in order with N/A, the parity of the reason tables, the held reasons largest first |
| S6.2 | Tags, chips, filters, review controls | S6.1 | the tier tags and reasons, the five filters, the controls the server allows, the page words |
| S6.3 | Monthly Statements, chart, settings, script version | S6.2 | True and Verified columns, the three shades, a month without established revenue; the full suite |
| A1 | The 5.6 census, every guard, G7 | S6.3 | the measured targets, G1 to G17, G7 against the owner's allowlist |
| A2 | The tryout host's census (read-only) | A1 | the host's figures beside the spec's reference |
| A3 | The precision sample | A1 | at least 95% revenue per Verified stratum |
| A4 | The train | all | the full suite, the dashboard in a browser, the main checkout clean |

## File structure

| File | Status | Responsibility | Tasks |
|---|---|---|---|
| `analysis/classification_registry.py` | Modify | the hand-kept operating, form and payer tables; `PAYOUT_CREDIT_ENTITIES` | S1.1 to S1.5 |
| `tools/operating_registry.py` | Create | the validator of those tables (§7.4) | S1.1 to S1.3 |
| `docs/lender-registry-ledger.json`, `docs/lender-registry-evidence.md` | Modify (through the ledger tools) | the ledger admissions | S1.5 |
| `analysis/description_text.py` | Modify | the street-`LN` guard | S2.1 |
| `analysis/transaction_classifier.py` | Modify | the readers, the rule vocabulary and helpers, the credit decision, the statement passes, the record fields, pass 7 wiring, Q7 step 4, the version | S2.1 to S2.5, S4.1 to S4.3, S4.5 |
| `webapp/artifact_cache.py` | Modify | `ANALYSIS_STAGE_VERSION` and its history | S2.5, S4.5 |
| `tools/revenue_census.py` | Create | the census, the guards, the precision sample (local only) | S3.1 |
| `analysis/revenue.py` | Modify | tiers, reasons, flags, the gate, the serialized views and the review writer | S4.1, S4.4 |
| `analysis/true_revenue.py` | Create | statement pass 7: payer facts, holds, Q5, Q6, Q7's credit-union arm, tiers; the census's guard facts | S4.2, S4.3 |
| `analysis/metrics.py`, `analysis/detect.py`, `analysis/serialization.py` | Modify | the tiered metrics and evidence lists | S4.4 |
| `batch.py`, `analyze.py`, `benchmark/run.py`, `benchmark/compare.py` | Modify | the consumers of §13 (`benchmark.compare.true_revenue_row`: True revenue against MoneyThumb's true credits) | S4.5 |
| `docs/transaction-classification.md` | Modify | the revenue section: definition, tiers, precedence, holds, table extension rules | S4.5 |
| `analysis/revenue_view.py` | Create | the served copy's revenue flags and the older payload's nulled True revenue | S5.1 |
| `webapp/app.py` | Modify | `_displayed`, `_package_analysis`, the currency keys (S5.1); the exports and the declared refusals (S5.2) | S5.1, S5.2 |
| `tools/l1s3_surface_census.py` | Modify | the new served reader in the L1-S3 surface census | S5.1 |
| `webapp/reanalysis.py` | Modify | `_awaits_review(record, decision)` | S5.2 |
| `webapp/static/app.js`, `webapp/templates/index.html` | Modify | §10.1 to §10.7 on the page | S6.1 to S6.3 |
| `tests/test_operating_registry.py` | Create | S1.1 to S1.4 | S1.x |
| `tests/test_registry_additions_55.py` | Create | the ledger-admission guard | S1.5 |
| `tests/test_revenue_text_readers.py`, `tests/test_revenue_rule_helpers.py` | Create | the readers; the helpers | S2.1, S2.2 |
| `tests/test_revenue_card_settlements.py`, `…_platform_payouts.py`, `…_healthcare_claims.py`, `…_payer_remittance.py`, `…_public_payers.py`, `…_wire_remittance.py`, `…_non_revenue_55.py` | Create | the families through the decision (and, from S2.4, the passes) | S2.3, S2.4 |
| `tests/test_revenue_recurrence.py` | Create | the recurrence pass | S2.4 |
| `tests/test_revenue_census.py` | Create | the census tool | S3.1, S4.2 |
| `tests/test_true_revenue_payload.py`, `tests/test_true_revenue_tiers.py` | Create | the contract, the pass, Q7, the metrics and views; the consumers (S4.5's section) | S4.1 to S4.5 |
| `tests/test_webapp_true_revenue.py`, `tests/test_webapp_true_revenue_ui.py` | Create | the webapp; the dashboard in node | S5.1, S5.2; S6.1 to S6.3 |

## Spec coverage

| Spec | Where |
|---|---|
| §1, §2 (Q1 to Q8), §3 | the whole plan; Q1 S4.4, S5.1, S6.1; Q2 S2.1 (gate), S4.2 (`no_payer_printed`, `transfer_no_counterparty`); Q3 S2.1, S4.2 (`check_deposit`); Q4 S2.1, S4.2 (`p2p`, `p2p_round_repeat`, `holder_name`); Q5 S2.2/S2.3 (§7.9), S4.2 (`repeat_wire_sender`, `wire_named_sender`, `wire_no_sender`); Q6 S4.2; Q7 S4.3; Q8 S4.2 (`payroll_or_salary`) |
| T1 (tiers beside states) | S4.1 |
| T2 (counted is the default) | S4.2 (`_tier_reason`) |
| T3 (the closed list of holds) | S4.2 (`_first_hold`, §8.10 order) |
| T4 (financing-named payer) | S4.2 (`financing_named`, `_FINANCING_ROOT`) |
| T5 (newly named non-revenue) | S2.2 (patterns), S2.3 (`_NON_REVENUE_CREDIT_PATTERNS`, `_descriptor_proceeds`, return codes) |
| T6 (review of rule-verified rows) | S4.4 (writer), S5.2 (routes, replay), S6.2 (controls) |
| T7 (the gate, integer cents, `REVENUE_REVIEW_HELD_SHARE`) | S4.4 (`revenue_review_gate`), S5.1 (per member), S4.5 (`batch.py`) |
| T8 (True revenue as a selectable withholding basis) | S4.4, S5.1 (R-d deduction) |
| T9 (field names, repointed aliases) | S4.1 (flag), S4.4 (metrics, evidence), S5.1 (package, dropped fallbacks) |
| T10 (older payloads) | S4.4 (tier-less rebuild), S5.1 (`revenue_view.py`), S6.1 (N/A and the note) |
| T11 (numbered companies never verified) | S2.1 (guard), S2.2 (`_refused_by_payer_guards`), S4.2 (`numbered_company_payer`, Q5/Q6 refuse) |
| T12 (government payers under Q6) | S2.2/S2.3 (§7.6 arms), S4.2 (`public_or_healthcare_payer`) |
| T13 (named transfers are person-to-person) | S4.2 (`p2p`, `transfer_account_designation`) |
| T14 (insurers held) | S2.3 (`insurer_customer_payment`), S4.2 (`insurer_payer`, `insurer_named_payer`) |
| T15 (property platforms and their chip) | S1.1, S2.4 (`_apply_property_branch`), S6.2 (chip) |
| T16 (auction forms) | S1.2, S2.4 (`_apply_auction_branch`) |
| T17 (two versions) | S2.5, S4.5 |
| T18 (claim first, on) | S2.1 (`HCCLAIMPMT_CLAIM_FIRST = True`), S2.3 (step 5), S1.3 (`BLUE_PLAN_CLAIM_PAYERS` for the off switch) |
| T19 (third-party book transfers as wires, on) | S2.1 (`THIRD_PARTY_BOOK_TRANSFER_AS_WIRE = True`, `_third_party_book_transfer`), S2.3 (R-d, step 9) |
| §5.1 to §5.4 | S2.1 (terms), S4.1 (fields, flags), S4.4 (identity) |
| §6.1, §6.2, §6.3 | S2.3 (steps 3, 5 to 16), S4.3 (step 4), S2.4 (passes 4 to 6), S4.2 (pass 7), S4.1 (pass 8's tier); §6.3 is checked by the census (S3.1 `NARROWINGS`, A1 G1) |
| §7.0 | S2.1 (revenue text, joined fields), S1.1 (cuts), S2.4 (recurrence fixes) |
| §7.1 | S1.1 (Step 1: the structural lens, searched read-only; the gate table), S1.2, S1.5, S2.2 (the gate in the reader), S2.3 |
| §7.2, §7.3 | S1.1, S1.2, S2.2, S2.3, S2.4 |
| §7.4 | S1.1 to S1.3 (`tools/operating_registry.py`) |
| §7.5 | S2.2, S2.3, S2.4 (counter-debit guard) |
| §7.6 | S2.2, S2.3 |
| §7.7 | S1.3, S2.2, S2.3 |
| §7.8 | S1.1, S1.2, S2.4 (the branch and §14.1's negatives), S4.2 (their tiers) |
| §7.9 | S2.1 (wire labels, Santander's originator), S2.2 (the financing text, the title veto), S2.3 (the 40 cases, the hazard groups, the residuals); the registry side findings S1.5 |
| §7.10 | S1.1, S2.4 |
| §7.11 | S2.1 (street `LN`), S2.2, S2.3 |
| §7.12 | the structural misses the families took in are in the family tasks S2.2 to S2.4 (their tests carry the structural shapes) |
| §8.1 to §8.10 | S4.2, S4.3 |
| §9.1, §9.2, §9.3 | S4.4; S5.1; S2.5 and S4.5 |
| §10.1 to §10.7 | S6.1 to S6.3; the server rules S4.4, S5.1, S5.2 |
| §10.8 | S5.2 |
| §11 | S4.4, S5.1 |
| §12 | S4.4, S5.1, S6.1 |
| §13 | every row of the consumer table is a task above (`analysis/flagged_view.py`, `webapp/jobs.py`, `webapp/storage.py`, `webapp/settings.py`: no change, as the spec says; `tools/lender_census.py` runs as G7 in A1) |
| §14.1 | the fabricated tests of S1 to S6 (G8), §7.8's list in S2.4 and S4.2, §7.9's list (the 40 cases of `simulate_v3.py`, the hazard groups G1 to G11, the party-name rows, the adversarial rows) in S2.3 |
| §14.2, §14.3 | S3.1 (G1 to G14 and the review's G15 to G17, lender and eligible-deposit moves by cause), S3.2, A1, A2 |
| §14.4 | S3.2, A1 |
| §14.5 | S3.1 (`sample`), A3 |
| §15 | not implemented, by design: OQ1's payer-wide review and the deferred items stay out; their rows are counted or held as the tasks above decide them |
| §16 | the order and the review rule above |
| §17, §19 | OQ1 out; OQ2 S1.4; OQ3 S4.2; OQ4 nothing decided; OQ5 S2.1/S2.3; OQ6 S2.1/S2.3 |

## Pin ledger

Every existing assertion this plan moves, measured by running the full suite at each task's commit of the prototype. Line numbers are those of the file as the task finds it. Nothing else may move (Global Constraints, stop rules). The spec's §13 also names `tests/test_factoring_credits.py:47-53` and `tests/l1s3_payloads.py:149-150`; neither moves (Decision 6), so neither is re-pinned. Row 35 is a real-statement assertion: it moves only on the owner's word, asked in Task S5.1's first step (review I7). The review's revision moved no row: every new test sits in a file this plan creates.

| # | Test (file:line) | Today | After | Task | Cause |
|---|---|---|---|---|---|
| 1 | `tests/test_lender_registry_content.py:212-213` | (none) | `("AFFIRM PAYMENT", "AFFIRM", "alternative_position"), ("AFTERPAY PAYMENT", "Afterpay", "alternative_position"), ("GREENSKY PAYMENT", "GreenSky", "a…` | S1.4 | OQ2 (§19): the five BNPL providers are payout-credit entities |
| 2 | `tests/test_lender_registry_content.py:217-219` | `assert registry.PAYOUT_CREDIT_ENTITIES == ("Sezzle Inc", "American First Finance, LLC", "PAYABILITY")` | `assert registry.PAYOUT_CREDIT_ENTITIES == ( "Sezzle Inc", "American First Finance, LLC", "PAYABILITY", "AFFIRM", "Afterpay", "GreenSky", "Klarna In…` | S1.4 | OQ2 (§19): the five BNPL providers are payout-credit entities |
| 3 | `tests/test_revenue_classification.py:63-64` | `("Customer check deposit", None),` | (none) | S2.3 | §6.1 step 9b and Q3: `Customer check deposit` is a check deposit, never verified (it moves from the verified list to the unverified one); `Customer ACH payment` prints no payer word, so the verified fixtures name their payer (`Fabrikam`) |
| 4 | `tests/test_revenue_classification.py:106-107` | (none) | `"Customer check deposit",` | S2.3 | §6.1 step 9b and Q3: `Customer check deposit` is a check deposit, never verified (it moves from the verified list to the unverified one); `Customer ACH payment` prints no payer word, so the verified fixtures name their payer (`Fabrikam`) |
| 5 | `tests/test_revenue_classification.py:208-209` | `_txn("2054-01-02", "Customer ACH payment", 100.0, balance=1100.0), _txn("2054-01-02", "Customer ACH payment", 100.0, balance=1100.0),` | `_txn("2054-01-02", "Fabrikam customer ACH payment", 100.0, balance=1100.0), _txn("2054-01-02", "Fabrikam customer ACH payment", 100.0, balance=1100…` | S2.3 | §6.1 step 9b and Q3: `Customer check deposit` is a check deposit, never verified (it moves from the verified list to the unverified one); `Customer ACH payment` prints no payer word, so the verified fixtures name their payer (`Fabrikam`) |
| 6 | `tests/test_revenue_classification.py:228-230` | `_txn("2054-01-02", "Customer ACH payment", 100.0),` | `_txn("2054-01-02", "Fabrikam customer ACH payment", 100.0),` | S2.3 | §6.1 step 9b and Q3: `Customer check deposit` is a check deposit, never verified (it moves from the verified list to the unverified one); `Customer ACH payment` prints no payer word, so the verified fixtures name their payer (`Fabrikam`) |
| 7 | `tests/test_revenue_classification.py:259-261` | `_txn("2054-01-02", "Customer ACH payment", 100.0),` | `_txn("2054-01-02", "Fabrikam customer ACH payment", 100.0),` | S2.3 | §6.1 step 9b and Q3: `Customer check deposit` is a check deposit, never verified (it moves from the verified list to the unverified one); `Customer ACH payment` prints no payer word, so the verified fixtures name their payer (`Fabrikam`) |
| 8 | `tests/test_revenue_classification.py:297` | `_txn("2054-01-01", "Customer ACH payment", 1000.0),` | `_txn("2054-01-01", "Fabrikam customer ACH payment", 1000.0),` | S2.3 | §6.1 step 9b and Q3: `Customer check deposit` is a check deposit, never verified (it moves from the verified list to the unverified one); `Customer ACH payment` prints no payer word, so the verified fixtures name their payer (`Fabrikam`) |
| 9 | `tests/test_analysis.py:3361` | `assert m.true_revenue == 10000.0` | `assert m.true_revenue == 0.0` | S2.3 | §6.1 step 9b: the bare teller `CUSTOMER DEPOSIT` prints no payer word, so the 5.5 gate leaves it unverified and the verified-only `true_revenue` is 0 until S4.4 |
| 10 | `tests/test_webapp_revenue_batch.py:13` | `ROWS = [(2, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 4200.0),` | `ROWS = [(2, "ACH CREDIT NORTHWIND CUSTOMER PAYMENT", 4200.0),` | S2.3 | §5.2 holder test: a payer named with the holder's first word (`FABRICATED`) is the holder's own money; the fixture's customer names another business |
| 11 | `tests/test_webapp_studio_views.py:17` | `CHECKING_ROWS = [(2, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 4200.0),` | `CHECKING_ROWS = [(2, "ACH CREDIT NORTHWIND CUSTOMER PAYMENT", 4200.0),` | S2.3 | the same holder test, for the shared dashboard fixtures |
| 12 | `tests/test_webapp_studio_views.py:450` | `PENDING_ROWS = [(2, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 4200.0),` | `PENDING_ROWS = [(2, "ACH CREDIT NORTHWIND CUSTOMER PAYMENT", 4200.0),` | S2.3 | the same holder test, for the shared dashboard fixtures |
| 13 | `tests/test_artifact_cache.py:488` | `def test_analysis_stage_version_is_pinned_at_23():` | `def test_analysis_stage_version_is_pinned_at_24():` | S2.5 | §9.3: analysis stage 23 → 24 |
| 14 | `tests/test_artifact_cache.py:497-499` | `2026-09-28: a counted lender, no longer a line of credit) goes 22 -> 23. This is that pin.""" assert ANALYSIS_STAGE_VERSION == 23` | `2026-09-28: a counted lender, no longer a line of credit) goes 22 -> 23. The true-revenue bug fixes (classification 5.5, 2026-09-28) go 23 -> 24. T…` | S2.5 | §9.3: analysis stage 23 → 24 |
| 15 | `tests/test_flag_group_states.py:60-63` | `assert CLASSIFICATION_VERSION == "5.4" assert classify_transaction("FABRICATED ROW", -10.0).classification_version == "5.4" assert ANALYSIS_STAGE_V…` | `assert CLASSIFICATION_VERSION == "5.5" assert classify_transaction("FABRICATED ROW", -10.0).classification_version == "5.5" assert ANALYSIS_STAGE_V…` | S2.5 | §9.3: classification 5.5, stage 24 |
| 16 | `tests/flagged_payloads.py:17-18` | `#: the false-positive release, and 5.3 -> 5.4 with the Idea Financial ruling (2026-09-28). CURRENT_VERSION = "5.4"` | `CURRENT_VERSION = "5.5"` | S2.5 | §9.3: the fixtures' current version is 5.5 |
| 17 | `tests/test_lender_census.py:38` | `assert result["classification_version"] == "5.4"` | `assert result["classification_version"] == "5.5"` | S2.5 | §9.3: the census records classification 5.5 |
| 18 | `tests/test_webapp_reanalysis.py:1060` | `assert {record["classification_version"] for record in records.values()} == {"5.4"}` | `assert {record["classification_version"] for record in records.values()} == {"5.5"}` | S2.5 | §9.3: a re-analysis writes classification 5.5 |
| 19 | `tests/test_revenue_classification.py:290-292` | `] == ["transaction:2"]` | `] == []` | S4.2 | §5.4: only a held credit requires review; the mobile deposit is a counted check deposit |
| 20 | `tests/test_revenue_classification.py:250-252` | `assert metrics.revenue_review_required` | `assert not metrics.revenue_review_required` | S4.4 | 5.6 (T7): the mobile deposit is a counted check deposit, and counted credits never gate review. |
| 21 | `tests/test_revenue_classification.py:664-666` | `assert export_row["needs_review"] == "REVIEW" assert coverage_status(report) == "needs_review"` | `assert export_row["needs_review"] == "" assert coverage_status(report) == "clean"` | S4.4 | 5.6 (T7): the statement's eight unverified deposits are two check deposits and six e-Transfers, all counted, so no credit is held and the revenue gate is clear. |
| 22 | `tests/test_analysis.py:3361-3362` | `# 5.5 (§6.1 step 9b): the bare teller CUSTOMER DEPOSIT prints no payer word, so it is no longer verified. assert m.true_revenue == 0.0` | `assert m.true_revenue == 10000.0 assert m.verified_revenue_total == 0.0` | S4.4 | 5.6 (T9): true_revenue is True revenue; the bare teller CUSTOMER DEPOSIT is counted (no payer printed). |
| 23 | `tests/test_webapp_reanalysis.py:292-293` | (none) | `revenue_tier="non_revenue", revenue_initial_tier="non_revenue", revenue_tier_reason=None,` | S4.4 | §12: a hand-built non-revenue record in a 5.6 payload carries its tier, or the rebuild refuses the payload as tiered in part |
| 24 | `tests/test_artifact_cache.py:488` | `def test_analysis_stage_version_is_pinned_at_24():` | `def test_analysis_stage_version_is_pinned_at_25():` | S4.5 | §9.3: analysis stage 24 → 25 |
| 25 | `tests/test_artifact_cache.py:498-500` | `true-revenue bug fixes (classification 5.5, 2026-09-28) go 23 -> 24. This is that pin.""" assert ANALYSIS_STAGE_VERSION == 24` | `true-revenue bug fixes (classification 5.5, 2026-09-28) go 23 -> 24, and its definitional rules (classification 5.6: the revenue tiers) go 24 -> 25…` | S4.5 | §9.3: analysis stage 24 → 25 |
| 26 | `tests/test_flag_group_states.py:61-64` | `# 5.5/24: the true-revenue bug fixes (2026-09-28 design, §7). assert CLASSIFICATION_VERSION == "5.5" assert classify_transaction("FABRICATED ROW", …` | `assert CLASSIFICATION_VERSION == "5.6" assert classify_transaction("FABRICATED ROW", -10.0).classification_version == "5.6" assert ANALYSIS_STAGE_V…` | S4.5 | §9.3: classification 5.6, stage 25 |
| 27 | `tests/flagged_payloads.py:18-19` | `#: true-revenue bug fixes. CURRENT_VERSION = "5.5"` | `CURRENT_VERSION = "5.6"` | S4.5 | §9.3: the fixtures' current version is 5.6 |
| 28 | `tests/test_lender_census.py:38-39` | `# 5.5: the true-revenue bug fixes (2026-09-28). assert result["classification_version"] == "5.5"` | `assert result["classification_version"] == "5.6"` | S4.5 | §9.3: the census records classification 5.6 |
| 29 | `tests/test_webapp_reanalysis.py:1061-1062` | `# 5.5: the true-revenue bug fixes (2026-09-28). assert {record["classification_version"] for record in records.values()} == {"5.5"}` | `assert {record["classification_version"] for record in records.values()} == {"5.6"}` | S4.5 | §9.3: a re-analysis writes classification 5.6 |
| 30 | `tests/test_package_currency.py:76-79` | (none) | `"true_revenue_total", "counted_flagged_total", "excluded_pending_review_total",` | S5.1 | §9.2: the new money keys and counts join the currency sweep; the tier counts are N/A for members with no ledger rows (§10.4) |
| 31 | `tests/test_package_currency.py:113-115` | (none) | `"true_revenue_count", "counted_flagged_count", "excluded_pending_review_count", "revenue_review_items", REVENUE_TIER_COUNTS = {"true_revenue_count"…` | S5.1 | §9.2: the new money keys and counts join the currency sweep; the tier counts are N/A for members with no ledger rows (§10.4) |
| 32 | `tests/test_package_currency.py:302-307` | `for key in UNIT_FREE_TOTALS:` | `for key in UNIT_FREE_TOTALS - REVENUE_TIER_COUNTS: for key in REVENUE_TIER_COUNTS: assert totals[key] is None` | S5.1 | §9.2: the new money keys and counts join the currency sweep; the tier counts are N/A for members with no ledger rows (§10.4) |
| 33 | `tests/test_package_currency.py:801-805` | `assert len(body["currency"]["refused_total_fields"]) == 34` | `assert len(body["currency"]["refused_total_fields"]) == 37` | S5.1 | §9.2: the new money keys and counts join the currency sweep; the tier counts are N/A for members with no ledger rows (§10.4) |
| 34 | `tests/test_lender_insurance_classification.py:350-353` | `# Still review: the fixture's customer deposit needs revenue review (measured 2026-09-26). assert totals["decision"] == "review_required"` | `assert totals["decision"] == "approved"` | S5.1 | 5.6 (true revenue spec T7): the fixture's customer deposit is counted, and a counted credit never gates review. |
| 35 | `tests/test_new_statement_corpus.py:476-478` | `assert package["totals"]["verified_revenue_total"] == 3563.85` | `assert package["totals"]["verified_revenue_total"] is None assert package["totals"]["revenue_unestablished_documents"] == ["new-corpus-navigant"]` | S5.1 | 5.6 (true revenue spec §9.2, §10.4): navigant's captured credits are not the money its bank total counts (its verified_revenue_established is false, as the Monthly Statements' True deposits already said), so the package's verified total is N/A rather than a sum that includes a partial figure. |
| 36 | `tests/test_webapp_app.py:400-402` | `assert totals["decision"] == "approved"` | `assert totals["verified_revenue_total"] is None assert totals["revenue_unestablished_documents"] == sorted([job1.id, job2.id]) assert totals["decis…` | S5.1 | 5.6 (true revenue spec §9.2): a member with no ledger rows and no verified key has no established verified revenue (the `true_revenue` fallback is gone), so the package's verified total is N/A and it needs review. |
| 37 | `tests/test_privacy3_boundaries.py:1420-1422` | (none) | `"a credit a rule verified can only be marked non-revenue": ( _analysis_with([ _reviewable("p1:r1", revenue_initial_classification="verified_revenue…` | S5.2 | §10.7, §12: the three new declared review refusals |
| 38 | `tests/test_privacy3_boundaries.py:1457-1460` | `# account, and a location held by several accounts with none named). assert len(webapp_app._DECLARED_REVIEW_REFUSALS) == 7` | `assert len(webapp_app._DECLARED_REVIEW_REFUSALS) == 10` | S5.2 | §10.7, §12: the three new declared review refusals |
| 39 | `tests/test_revenue_classification.py:831-835` | `assert "Revenue Upper Bound" in javascript assert "Upper-bound estimate: verified revenue plus unverified deposits" in javascript assert "Confirmed…` | `assert "Revenue Upper Bound" not in javascript assert "Posted credits minus known non-revenue and the deposits held for review" in javascript asser…` | S6.1 | §10.1, §10.5: the Revenue Upper Bound card is removed and the cards carry the new copy |
| 40 | `tests/test_revenue_classification.py:823-825` | `for state in REVENUE_STATES:` | `for state in ("true_revenue", "verified_revenue", "counted_flagged", "excluded_pending_review", "non_revenue"):` | S6.2 | §10.6: the five revenue filters and their pills |
| 41 | `tests/test_revenue_classification.py:829-831` | `assert "Verified Revenue" in html assert "Unverified Deposits" in html` | `assert "True Revenue" in html assert "Held for Review" in html assert "Unverified Deposits" not in javascript` | S6.2 | §10.6: the five revenue filters and their pills |
| 42 | `tests/test_webapp_flagged_dashboard.py:58` | `assert result["credit"] == "Non-Revenue"` | `assert result["credit"] == "Non-revenue"` | S6.2 | §10.6: the tier tags (`Non-revenue`, `Verified revenue`); §10.5: the outdated notice now covers revenue |
| 43 | `tests/test_webapp_flagged_dashboard.py:683` | `assert "Analysed with older lender rules" in notice and 'id="reanalyzeButton"' in notice` | `assert "Analysed with older classification rules" in notice and 'id="reanalyzeButton"' in notice` | S6.2 | §10.6: the tier tags (`Non-revenue`, `Verified revenue`); §10.5: the outdated notice now covers revenue |
| 44 | `tests/test_webapp_flagged_dashboard.py:821` | `revenue: tagged('Verified Revenue')};` | `revenue: tagged('Verified revenue')};` | S6.2 | §10.6: the tier tags (`Non-revenue`, `Verified revenue`); §10.5: the outdated notice now covers revenue |
| 45 | `tests/test_webapp_flagged_dashboard.py:716` | `assert '<script src="/static/app.js?v=lender-detection-2"></script>' in html` | `assert '<script src="/static/app.js?v=true-revenue-1"></script>' in html` | S6.3 | browsers fetch the new script (`?v=true-revenue-1`) |
| 46 | `tests/test_webapp_studio_views.py:348-350` | `"True Deposits Per Month", "Ledger ($)", "NSF", "Action"]` | `"True Deposits Per Month", "Verified ($)", "Ledger ($)", "NSF", "Action"]` | S6.3 | §10.2, §10.3: True Deposits read `true_revenue_total` when `revenue_established`, the new Verified ($) column, the three-shade chart and its legend |
| 47 | `tests/test_webapp_studio_views.py:351-361` | `assert both["rows"][0][2:6] == [whole(january["credits"]), str(january["deposit_count"]), whole(january["verified_revenue_total"]), str(january["ve…` | `assert both["rows"][0][2:7] == [whole(january["credits"]), str(january["deposit_count"]), whole(january["true_revenue_total"]), str(january["true_r…` | S6.3 | §10.2, §10.3: True Deposits read `true_revenue_total` when `revenue_established`, the new Verified ($) column, the three-shade chart and its legend |
| 48 | `tests/test_webapp_studio_views.py:392-397` | `assert len(both["head"]) == 9 assert both["chart"]["values"] == [["shown", whole(jan["credits"])], ["true", whole(jan["verified_revenue_total"])], …` | `assert len(both["head"]) == 10 assert both["chart"]["values"] == [["shown", whole(jan["credits"])], ["true", whole(jan["true_revenue_total"])], ["s…` | S6.3 | §10.2, §10.3: True Deposits read `true_revenue_total` when `revenue_established`, the new Verified ($) column, the three-shade chart and its legend |
| 49 | `tests/test_webapp_studio_views.py:399-403` | `assert true_only["chart"]["values"] == [["shown", whole(jan["verified_revenue_total"])], ["shown", whole(feb["verified_revenue_total"])]] assert "T…` | `assert true_only["chart"]["values"] == [["shown", whole(jan["true_revenue_total"])], ["shown", whole(feb["true_revenue_total"])]] assert "True reve…` | S6.3 | §10.2, §10.3: True Deposits read `true_revenue_total` when `revenue_established`, the new Verified ($) column, the three-shade chart and its legend |
| 50 | `tests/test_webapp_studio_views.py:420-422` | `feb["verified_revenue_established"] = False  # e.g. a credit the classifier left without a revenue state` | `feb["verified_revenue_established"] = feb["revenue_established"] = False` | S6.3 | §10.2, §10.3: True Deposits read `true_revenue_total` when `revenue_established`, the new Verified ($) column, the three-shade chart and its legend |
| 51 | `tests/test_webapp_studio_views.py:428-431` | `assert failed[2:8] == ["N/A"] * 6 and failed[8] == "Unavailable" assert unknown[2] == f"{round(feb['credits']):,}" and unknown[4:6] == ["N/A", "N/A"]` | `assert failed[2:9] == ["N/A"] * 7 and failed[9] == "Unavailable" assert unknown[2] == f"{round(feb['credits']):,}" and unknown[4:7] == ["N/A", "N/A…` | S6.3 | §10.2, §10.3: True Deposits read `true_revenue_total` when `revenue_established`, the new Verified ($) column, the three-shade chart and its legend |
| 52 | `tests/test_webapp_studio_views.py:436-439` | `"""A package row without `verified_revenue_established` (none the server sends today) is not taken as established: True deposits read N/A, Total de…` | `"""A package row without `revenue_established` and `verified_revenue_established` (none the server sends today) is not taken as established: True a…` | S6.3 | §10.2, §10.3: True Deposits read `true_revenue_total` when `revenue_established`, the new Verified ($) column, the three-shade chart and its legend |
| 53 | `tests/test_webapp_studio_views.py:440-441` | (none) | `del package["documents"][0]["revenue_established"]` | S6.3 | §10.2, §10.3: True Deposits read `true_revenue_total` when `revenue_established`, the new Verified ($) column, the three-shade chart and its legend |
| 54 | `tests/test_webapp_studio_views.py:445-447` | `assert row[2] == f"{round(package['documents'][0]['credits']):,}" and row[4:6] == ["N/A", "N/A"]` | `assert row[2] == f"{round(package['documents'][0]['credits']):,}" and row[4:7] == ["N/A", "N/A", "N/A"]` | S6.3 | §10.2, §10.3: True Deposits read `true_revenue_total` when `revenue_established`, the new Verified ($) column, the three-shade chart and its legend |
| 55 | `tests/test_webapp_studio_views.py:507-509` | `trues = {doc["id"]: f"{round(doc['verified_revenue_total']):,}" for doc in package_after["documents"]}` | `trues = {doc["id"]: f"{round(doc['true_revenue_total']):,}" for doc in package_after["documents"]}` | S6.3 | §10.2, §10.3: True Deposits read `true_revenue_total` when `revenue_established`, the new Verified ($) column, the three-shade chart and its legend |
| 56 | `tests/test_webapp_flagged_dashboard.py:716` (row 45's second move) | `assert '<script src="/static/app.js?v=true-revenue-1"></script>' in html` | `assert '<script src="/static/app.js?v=true-revenue-2"></script>' in html` | FW (69486cb) | the final review's A4-2 moved the monthly chart's bars, so browsers fetch the new script (`?v=true-revenue-2`); the settings test of `tests/test_webapp_true_revenue_ui.py`, added by S6.3, moved with it |

## S1: Registry and vocabularies

### Task S1.1: The operating registry and its validator

**Files:**
- Create: `tools/operating_registry.py`
- Create: `tests/test_operating_registry.py`
- Modify: `analysis/classification_registry.py:12-14, 1489-1490, 1498, 1500, 1521, 1534-1535, 1569-1570`

**Depends on:** none (the first task).

**Interfaces:**
- Consumes: `normalize_transaction_description` (`analysis/description_text.py`), the ledger-rendered alias tables of `analysis/classification_registry.py` (`PAYEE_GROUP_REGISTRIES`, `POTENTIAL_LENDER_ALIASES`, `BANK_NAME_ALIASES`, `CARD_ISSUER_CONTEXT_ALIASES`, `DEBT_RELIEF_ALIASES`, `PREMIUM_FINANCE_ALIASES`, `INSURANCE_PROVIDER_ALIASES`), `analysis.flag_groups.FINANCING_STATES`.
- Produces:
  - `OPERATING_REVENUE_SOURCE_ALIASES` and `OPERATING_REVENUE_SOURCE_TYPES` (extended; new types `booking_marketplace`, `transport_marketplace`, `wholesale_auto_auction`, `property_management_payments`)
  - `OPERATING_SOURCES_READ_WITH_VETOES: frozenset[str]`, `OPERATING_ALIASES_READ_WITH_VETOES: frozenset[str]`
  - `OPERATING_SOURCE_CONTEXT_WORDS: dict[str, tuple[str, ...]]`
  - `PROCESSOR_ADVANCE_PRODUCTS: dict[str, tuple[tuple[str, ...], str | None]]`, `PROCESSORS_WITHOUT_ADVANCE_PRODUCT: frozenset[str]`
  - `GATED_PROCESSOR_ALIASES: dict[str, tuple[str, ...]]` (derived, never hand-edited: the bare aliases of every processor the ledger has not cleared, by processor)
  - `OPERATING_ALIAS_CUT = 16`, `_operating_alias_cut(alias: str) -> str | None`, `OPERATING_REVENUE_TRUNCATIONS: dict[str, tuple[str, ...]]`, `OPERATING_REVENUE_READ_ALIASES: dict[str, tuple[str, ...]]` (aliases plus cuts: what the classifier reads from S2.2 on)
  - `tools/operating_registry.py`: `problems() -> list[str]`, `warnings() -> list[str]`, `main(argv: list[str] | None = None) -> int` (`python -m tools.operating_registry --check`)

**Why:** Spec §7.1 to §7.4, §7.8 and §7.10: the processors, marketplaces, vertical software, transport marketplaces, wholesale auctions and property platforms the corpus prints, in the spellings it prints; the reads that carry the platform vetoes; the 16-character cuts (§7.0); the processor gate ("ledger before aliases", §7.1) and the gate table the reader honours (`GATED_PROCESSOR_ALIASES`, review I4: an alias read inside a waiting processor's bare alias names no source); the structural-lens processors searched read-only (Step 1, review I3: none prints a credit spelling, so each waits); and the validator §7.4 asks for. The running classifier reads `OPERATING_REVENUE_SOURCE_ALIASES` at once through today's rules, so some rows start verifying before S2; no existing test moves (measured), and the version moves at S2.5.

- [ ] **Step 1: The structural-lens processors (spec §7.1, review I3).** §7.1 names seventeen processors whose spellings the structural lens fabricated (TSYS / TransFirst, Vantiv, EVO Payments, Paysafe, North American Bancard / Payanywhere, Priority Payment Systems, Payroc, CardConnect, Stax / Fattmerchant, Repay, Paya, NMI, Finix, WePay, TD Merchant Solutions, Desjardins Monetico, Chase QuickAccept): "S1 adds each only in a spelling the corpus or the tryout dump prints, confirmed read-only; a name with no printed spelling waits." Search both, read-only, with this scratch script (Write tool; `C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/s11/structural_processors.py`; it prints the matched processor spelling and counts only):

```python
"""Task S1.1 (scratch, never committed): search the corpus cache and the tryout host's credit dump, read-only, for the
spellings of spec §7.1's seventeen structural-lens processors. Prints the matched processor spelling and counts only,
never the rest of a row.
Usage: python structural_processors.py <webapp_data dir> <fly_credits.json>"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "C:/Users/GustavoPrietodePaula/work/true-revenue")
from analysis.description_text import normalize_transaction_description as normalize  # noqa: E402

PROCESSORS = {
    "TSYS / TransFirst": r"\bTSYS\b|\bTRANSFIRST\b|\bTRANS FIRST\b",
    "Vantiv": r"\bVANTIV\b",
    "EVO Payments": r"\bEVO (?:PAYMENTS|SNAP|MERCHANT|MERCH|DEP|DEPOSIT|SETTLE\w*)\b|\bEVOPAY\w*",
    "Paysafe": r"\bPAYSAFE\b",
    "North American Bancard / Payanywhere": (
        r"\bNORTH AMERICAN BANCARD\b|\bNAB (?:DEP|DEPOSIT|SETTLE\w*|BANKCARD)\b|\bPAYANYWHERE\b|\bPAY ANYWHERE\b"
    ),
    "Priority Payment Systems": r"\bPRIORITY (?:PAYMENT|PMT|PAY|PAYMENTS|TECH)\w*\b",
    "Payroc": r"\bPAYROC\b",
    "CardConnect": r"\bCARDCONNECT\b|\bCARD CONNECT\b",
    "Stax / Fattmerchant": (
        r"\bSTAX (?:PAYMENTS|PAY|DEP|DEPOSIT|SETTLE\w*|BY FATTMERCHANT)\b|\bFATTMERCHANT\b|\bFATT MERCHANT\b"
    ),
    "Repay": r"\bREPAY (?:MANAGEMENT|DEP|DEPOSIT|SETTLE\w*|TECHNOLOGIES)\b|\bREALTIME ELECTRONIC PAYMENTS\b",
    "Paya": r"\bPAYA (?:SERVICES|DEP|DEPOSIT|SETTLE\w*|INC|LLC)\b|\bSAGE PAYMENT\w*",
    "NMI": r"\bNMI (?:DEP|DEPOSIT|SETTLE\w*|PAYMENTS|GATEWAY)\b|\bNETWORK MERCHANTS\b",
    "Finix": r"\bFINIX\b",
    "WePay": r"\bWEPAY\b|\bWE PAY\b",
    "TD Merchant Solutions": r"\bTD MERCHANT\w*|\bTD MERCH\b|\bTDMS\b",
    "Desjardins Monetico": r"\bMONETICO\b|\bDESJARDINS (?:MERCHANT|CARTE|MONETIQUE)\w*",
    "Chase QuickAccept": r"\bQUICKACCEPT\b|\bQUICK ACCEPT\b|\bQUICKACCPT\b",
}
COMPILED = {name: re.compile(pattern) for name, pattern in PROCESSORS.items()}


def _transactions(node):
    """Every transaction of every account payload in one cached analysis."""
    if isinstance(node, dict):
        statement = node.get("statement")
        if isinstance(statement, dict) and isinstance(statement.get("transactions"), list):
            yield from statement["transactions"]
            return
        for value in node.values():
            yield from _transactions(value)
    elif isinstance(node, list):
        for value in node:
            yield from _transactions(value)


def main(data_dir: Path, dump: Path) -> None:
    connection = sqlite3.connect(f"{(data_dir / 'webapp.db').resolve().as_uri()}?mode=ro", uri=True)
    try:
        paths = [row[0] for row in connection.execute(
            "SELECT artifact_path FROM artifact_cache WHERE stage = 'analysis'")]
    finally:
        connection.close()
    found: dict = defaultdict(lambda: [Counter(), 0, 0])
    for relative in paths:
        try:
            payload = json.loads((data_dir / "artifacts" / relative).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for txn in _transactions(payload.get("artifact")):
            text = normalize(txn.get("description") or "")
            for name, pattern in COMPILED.items():
                match = pattern.search(text)
                if match:
                    found[name][0][match.group(0)] += 1
                    found[name][1 if (txn.get("amount") or 0) > 0 else 2] += 1
    print(f"corpus cache ({len(paths)} cached analyses, every copy):")
    for name in PROCESSORS:
        spellings, credits, debits = found.get(name, [Counter(), 0, 0])
        print(f"  {name}: credits {credits}, debits {debits}, spellings {dict(spellings)}")
    host: dict = defaultdict(lambda: [Counter(), 0])
    for group in json.loads(dump.read_text(encoding="utf-8"))["keys"]:
        for text in [group.get("payee_tokens") or "", *(group.get("samples") or [])]:
            hits = [(name, pattern.search(normalize(text))) for name, pattern in COMPILED.items()]
            for name, match in hits:
                if match:
                    host[name][0][match.group(0)] += 1
                    host[name][1] += group.get("rows", 0)
    print("tryout host credit dump:")
    for name in PROCESSORS:
        spellings, rows = host.get(name, [Counter(), 0])
        print(f"  {name}: credit rows {rows}, spellings {dict(spellings)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
```

  Run it (it reads every cached analysis, about ten minutes):

```bash
C:/Python314/python.exe C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/s11/structural_processors.py "C:/Users/GustavoPrietodePaula/OneDrive - Capital Infusion/Desktop/Capital Infusion Projects/bankStatementAnalysis/webapp_data" C:/Users/GustavoPrietodePaula/lender-research/revenue/fly_credits.json
```

  Expected (measured 2026-09-29 over 31,116 cached analyses and the host's credit dump): every processor `credits 0` in the cache (only debits print: `TSYS` 45, `VANTIV` 106, `PAYROC` 15, `TDMS` 135) and `credit rows 0` on the host. So none is an alias: each waits, as the registry comment this task adds records. If any processor now prints a credit spelling (the cache has grown), stop and report it: a new processor's bare alias waits for its advance product in the ledger (§7.1), so it would join `PROCESSOR_ADVANCE_PRODUCTS` and S1.5's research brief, never the registry directly.

- [ ] **Step 2: Write the failing tests.**

Create `tests/test_operating_registry.py`:

```python
"""True revenue spec §7.0 to §7.10 and §7.4 (S1): the operating registry, its sixteen-character cuts, the payout and
card forms, the payer tables and the validator that checks them."""
from __future__ import annotations

import pytest

from analysis import classification_registry as registry
from tools import operating_registry


def test_the_registry_has_no_problem():
    assert operating_registry.problems() == []
    assert operating_registry.main(["--check"]) == 0


def test_every_new_type_is_one_of_the_known_source_types():
    assert set(registry.OPERATING_REVENUE_SOURCE_TYPES.values()) == {
        "known_operating_counterparty", "merchant_processor", "ecommerce_marketplace", "customer_payment_platform",
        "delivery_marketplace", "invoice_and_receivables", "ecommerce_platform", "booking_marketplace",
        "transport_marketplace", "wholesale_auto_auction", "property_management_payments",
    }


@pytest.mark.parametrize(("alias", "cut"), [
    ("FIRST DATA MERCHANT", "FIRST DATA MERCH"),
    ("QUICKBOOKS PAYMENTS", "QUICKBOOKS PAYME"),
    ("AMAZON MARKETPLACE", "AMAZON MARKETPLA"),
    ("HEARTLAND PMT SYS TXNS", None),     # the cut's last word would have two letters
    ("GODADDY PAYMENTS", None),           # sixteen characters: no cut
])
def test_the_sixteen_character_cut(alias, cut):
    assert registry._operating_alias_cut(alias) == cut


def test_a_bare_processor_name_is_not_in_the_registry_until_the_ledger_clears_it():
    read = {alias for aliases in registry.OPERATING_REVENUE_SOURCE_ALIASES.values() for alias in aliases}
    for processor, (bare, product) in registry.PROCESSOR_ADVANCE_PRODUCTS.items():
        if product is None and processor not in registry.PROCESSORS_WITHOUT_ADVANCE_PRODUCT:
            assert not set(bare) & read, processor


def test_the_validator_refuses_a_bare_alias_ahead_of_its_advance_product(monkeypatch):
    aliases = {**registry.OPERATING_REVENUE_SOURCE_ALIASES, "Shift4": ("SHIFT4", "SHIFT4 PAYMENTS")}
    monkeypatch.setattr(registry, "OPERATING_REVENUE_SOURCE_ALIASES", aliases)
    assert any("SHIFT4" in problem and "advance product" in problem for problem in operating_registry.problems())


def test_the_validator_refuses_an_untyped_entity_and_a_financing_collision(monkeypatch):
    aliases = {**registry.OPERATING_REVENUE_SOURCE_ALIASES, "Fabrikam Pay": ("FABRIKAM PAY",),
               "Square": (*registry.OPERATING_REVENUE_SOURCE_ALIASES["Square"], "SQUARE CAPITAL")}
    monkeypatch.setattr(registry, "OPERATING_REVENUE_SOURCE_ALIASES", aliases)
    found = operating_registry.problems()
    assert "operating entity 'Fabrikam Pay' has no source type" in found
    assert any("'SQUARE CAPITAL'" in problem and "financing alias" in problem for problem in found)


def test_a_waiting_processor_s_bare_aliases_are_gated_and_never_read():
    # §7.1, review I4: the gate lists every processor the ledger has not cleared, and none of its bare aliases reads.
    admitted = {entity for group in registry.PAYEE_GROUP_REGISTRIES.values() for entity in group}
    waiting = {
        processor: bare for processor, (bare, product) in registry.PROCESSOR_ADVANCE_PRODUCTS.items()
        if not (product in admitted or processor in registry.PROCESSORS_WITHOUT_ADVANCE_PRODUCT)
    }
    assert registry.GATED_PROCESSOR_ALIASES == waiting
    read = {alias for aliases in registry.OPERATING_REVENUE_READ_ALIASES.values() for alias in aliases}
    assert not read & {alias for bare in waiting.values() for alias in bare}


def test_the_structural_lens_processors_wait_for_a_printed_spelling():
    # §7.1: none of the seventeen prints a credit spelling in the corpus or the tryout dump (Task S1.1, Step 1).
    read = {word for aliases in registry.OPERATING_REVENUE_READ_ALIASES.values() for alias in aliases
            for word in alias.split()}
    for name in ("TSYS", "TRANSFIRST", "VANTIV", "PAYSAFE", "PAYANYWHERE", "PAYROC", "CARDCONNECT", "FATTMERCHANT",
                 "STAX", "REPAY", "PAYA", "NMI", "FINIX", "WEPAY", "TDMS", "MONETICO", "QUICKACCEPT"):
        assert name not in read, name
```

- [ ] **Step 3: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_operating_registry.py -q -p no:cacheprovider`

Expected: FAIL: `1 error`, the first with `ImportError: cannot import name 'operating_registry' from 'tools' (unknown location)`.

- [ ] **Step 4: Implement.**

In `analysis/classification_registry.py` (lines 12-14), replace:

```python
from __future__ import annotations

# --- BEGIN GENERATED
```

with:

```python
from __future__ import annotations

from .description_text import normalize_transaction_description

# --- BEGIN GENERATED
```

In `analysis/classification_registry.py` (lines 1489-1490), replace:

```python
        "AMZN MARKETPLACE",
    ),
```

with:

```python
        "AMZN MARKETPLACE",
        # 5.5 (true revenue spec §7.2): Amazon's real-time-rail payout, verified by recurrence only.
        "RTP CREDIT AMAZON COM",
    ),
```

In `analysis/classification_registry.py` (line 1498), replace:

```python
    "Fiserv": ("FISERV", "FIRST DATA MERCHANT"),
```

with:

```python
    "Fiserv": ("FISERV", "FIRST DATA MERCHANT", "FIRST DATA CANADA"),
```

In `analysis/classification_registry.py` (line 1500), replace:

```python
    "Global Payments": ("GLOBAL PAYMENTS", "GL0BAL PAYMENTS", "GLOBALPAY"),
```

with:

```python
    "Global Payments": ("GLOBAL PAYMENTS", "GL0BAL PAYMENTS", "GLOBALPAY", "GLOBAL PAIEMENTS"),
```

In `analysis/classification_registry.py` (line 1521), replace:

```python
    "Stripe": ("STRIPE", "STR1PE"),
```

with:

```python
    # 5.5 (§7.0, §7.2): Stripe-Treasury payouts of a connected platform (STP FBO) and Stripe Connect's
    # '<platform> - By Stri' cut read as Stripe.
    "Stripe": ("STRIPE", "STR1PE", "STP FBO", "BY STRI", "BY STRIPE"),
```

In `analysis/classification_registry.py` (lines 1534-1535), replace:

```python
    "Worldpay": ("WORLDPAY", "WORLD PAY"),
}
```

with:

```python
    "Worldpay": ("WORLDPAY", "WORLD PAY"),
    # 5.5 (true revenue spec §7.1): card processors, in the spellings the corpus prints. A processor's bare name
    # (SHIFT4, SUMUP, CLEARENT, SMARTTAB, BRAINTREE) and Jobber's cut joins only after its advance product is in
    # the lender ledger (PROCESSOR_ADVANCE_PRODUCTS).
    "Heartland Payment Systems": (
        "HRTLAND PMT SYS TXNS", "HEARTLAND PMT SYS TXNS", "HEARTLAND PAYMENT SYSTEMS", "HEARTLAND PAYMEN",
    ),
    "SpotOn": ("SPOTON", "SPOTON VIA ASTRA"),
    "Clearent": ("CLEARENT LLC", "XPLOR PAY"),
    "Shift4": ("SHIFT4 PAYMENTS", "SHIFT4 PYMT PROC"),
    "SmartTab": ("SMARTTAB PAY",),
    "TapGoods Payments": ("TGPAYMENTS",),
    "Cents": ("TRYCENTS", "TRYCENTS COM"),
    "Esquire Payment Solutions": ("ESQUIRE EPS DAILY DEP", "ESQUIRE EPS HELD DEP"),
    # 5.5 (§7.2, structural S43): vertical software that settles cards, in the spellings the corpus prints.
    # Squarespace Payments and Seamless print no corpus spelling and wait.
    "Vagaro": ("VAGARO",),
    "Mindbody": ("MINDBODY",),
    "Housecall Pro": ("HOUSECALL PRO",),
    "Wix Payments": ("WIX COM",),
    # 5.5 (§7.2): marketplaces and platforms.
    "Whatnot": ("WHATNOT INC", "FBO WHATNOT"),
    "Faire": ("FAIRE WHOLESALE",),
    "TikTok Shop": ("TIKTOK SHOP", "TIKTOK INC", "TIKTOK USA"),
    "eBay": ("EBAY COMMERCE INC",),
    "RepeatMD": ("REPEATMD", "REPEATMD MARKETP"),
    "Snackpass": ("SNACKPASS",),
    "ezCater": ("EZCATER",),
    "Menufy": ("MENUFY", "MENUFY COM"),
    "Groupon": ("GRPN MERCH SVCS",),
    "ClassPass": ("CLASSPASS", "CLASSPASS INC"),
    "Outdoorsy": ("OUTDOORSY",),
    "Brightwheel": ("BRIGHTWHEEL", "BRIGHTWHEE"),
    "Buildertrend": ("BUILDERTREND", "BUILDERTREND SOL"),
    "FieldPulse": ("FIELDPULSE",),
    # 5.5 (§7.3): vehicle-transport marketplaces paying carriers.
    "Super Dispatch": ("SUPER DISPATCH", "SUPERDISPATCH"),
    "Autosled": ("AUTOSLED",),
    # 5.5 (§7.8): dealer-only wholesale auto auctions, read on the originator segment only.
    "Manheim": ("MANHEIM US",),
    "ACV Auctions": ("ACV AUCTIONS",),
    "OPENLANE": ("OPENLANE INC", "BACKLOTCARS"),
    # 5.5 (§7.10): property-management payment platforms, verified by recurrence of their ACH payout only.
    "Buildium": ("BUILDIUM",),
    "AppFolio": ("APPFOLIO",),
    "Landlord Studio": ("LANDLORD STUDIO",),
}
```

In `analysis/classification_registry.py` (lines 1569-1570), replace:

```python
    "Worldpay": "merchant_processor",
}
```

with:

```python
    "Worldpay": "merchant_processor",
    "Heartland Payment Systems": "merchant_processor",
    "SpotOn": "merchant_processor",
    "Clearent": "merchant_processor",
    "Shift4": "merchant_processor",
    "SmartTab": "merchant_processor",
    "TapGoods Payments": "merchant_processor",
    "Cents": "merchant_processor",
    "Esquire Payment Solutions": "merchant_processor",
    "Vagaro": "merchant_processor",
    "Mindbody": "merchant_processor",
    "Housecall Pro": "merchant_processor",
    "Wix Payments": "merchant_processor",
    "Whatnot": "ecommerce_marketplace",
    "Faire": "ecommerce_marketplace",
    "TikTok Shop": "ecommerce_marketplace",
    "eBay": "ecommerce_marketplace",
    "RepeatMD": "ecommerce_marketplace",
    "Snackpass": "delivery_marketplace",
    "ezCater": "delivery_marketplace",
    "Menufy": "delivery_marketplace",
    "Groupon": "booking_marketplace",
    "ClassPass": "booking_marketplace",
    "Outdoorsy": "booking_marketplace",
    "Brightwheel": "customer_payment_platform",
    "Buildertrend": "invoice_and_receivables",
    "FieldPulse": "invoice_and_receivables",
    "Super Dispatch": "transport_marketplace",
    "Autosled": "transport_marketplace",
    "Manheim": "wholesale_auto_auction",
    "ACV Auctions": "wholesale_auto_auction",
    "OPENLANE": "wholesale_auto_auction",
    "Buildium": "property_management_payments",
    "AppFolio": "property_management_payments",
    "Landlord Studio": "property_management_payments",
}

#: 5.5 (§7.2, §7.3): the operating reads that carry the platform vetoes (pay, financing, reversal and
#: person-to-person words): every read of these entities, and these aliases of older entities. A payout form always
#: carries them.
OPERATING_SOURCES_READ_WITH_VETOES: frozenset[str] = frozenset({
    "Whatnot", "Faire", "TikTok Shop", "eBay", "RepeatMD", "Snackpass", "ezCater", "Menufy", "Groupon", "ClassPass",
    "Outdoorsy", "Brightwheel", "Buildertrend", "FieldPulse", "Vagaro", "Mindbody", "Housecall Pro", "Wix Payments",
    "Super Dispatch", "Autosled",
})
OPERATING_ALIASES_READ_WITH_VETOES: frozenset[str] = frozenset({"RTP CREDIT AMAZON COM", "STP FBO"})

#: 5.5 (§7.2, structural S43): extra words that count as payout context for one operating source (read like
#: _OPERATING_CREDIT_CONTEXT_PATTERNS, as whole words).
OPERATING_SOURCE_CONTEXT_WORDS: dict[str, tuple[str, ...]] = {
    "Vagaro": ("DEPOSIT", "PAYOUT"),
    "Mindbody": ("DEPOSIT", "PAYOUT"),
    "Housecall Pro": ("DEPOSIT", "PAYOUT"),
    "Wix Payments": ("DEPOSIT", "PAYOUT"),
}

#: 5.5 (§7.1): a processor whose bare name joins OPERATING_REVENUE_SOURCE_ALIASES only once the lender ledger
#: admits its own advance product (an alternative position) or records, through the ledger's process, that it has
#: none. Keyed by operating entity: (the bare aliases, the ledger entity of the advance product, or None while the
#: ledger holds neither). tools/operating_registry.py refuses a bare alias in OPERATING_REVENUE_SOURCE_ALIASES
#: whose entry here names no admitted ledger entity and is not marked none-recorded.
PROCESSOR_ADVANCE_PRODUCTS: dict[str, tuple[tuple[str, ...], str | None]] = {
    "Shift4": (("SHIFT4",), None),
    "SumUp": (("SUMUP",), None),
    "Jobber Payments": (("JOBBER BY STRI", "JOBBER BY STR", "JOBBER BY STRIPE"), None),
    "Clearent": (("CLEARENT",), None),
    "SmartTab": (("SMARTTAB",), None),
    "Braintree": (("BRAINTREE",), None),
}
#: 5.5 (§7.1): processors the ledger's process found to have no advance product of their own (research round and
#: verdicts recorded in the ledger notes of the entity named there). Empty until S1's research round says so.
PROCESSORS_WITHOUT_ADVANCE_PRODUCT: frozenset[str] = frozenset()
#: 5.5 (§7.1, the ledger gate): the bare aliases of the processors the ledger has not cleared yet, by processor.
#: Derived, never hand-edited. The operating reader refuses an alias read that lies inside one of them ('BY STRI'
#: inside 'JOBBER BY STRI'), so no other entity reads the row while the processor waits.
GATED_PROCESSOR_ALIASES: dict[str, tuple[str, ...]] = {
    processor: bare
    for processor, (bare, product) in PROCESSOR_ADVANCE_PRODUCTS.items()
    if not (
        (product is not None and any(product in group for group in PAYEE_GROUP_REGISTRIES.values()))
        or processor in PROCESSORS_WITHOUT_ADVANCE_PRODUCT
    )
}
#: 5.5 (§7.1, the structural lens): TSYS / TransFirst, Vantiv, EVO Payments, Paysafe, North American Bancard /
#: Payanywhere, Priority Payment Systems, Payroc, CardConnect, Stax / Fattmerchant, Repay, Paya, NMI, Finix, WePay,
#: TD Merchant Solutions, Desjardins Monetico and Chase QuickAccept print no credit spelling in the corpus cache or the
#: tryout host's credit dump (searched read-only, 2026-09-29): none is an alias, and each waits for a printed spelling.

#: 5.5 (§7.0): the width of the bank field that cuts a long originator name. Every operating alias longer than this
#: is also read at its first sixteen characters when the cut keeps two words and its last word has three letters.
OPERATING_ALIAS_CUT = 16


def _operating_alias_cut(alias: str) -> str | None:
    """The sixteen-character cut of one operating alias, or None when it has none (§7.0)."""
    normalized = normalize_transaction_description(alias)
    if len(normalized) <= OPERATING_ALIAS_CUT:
        return None
    cut = normalized[:OPERATING_ALIAS_CUT].rstrip()
    words = cut.split(" ")
    if len(words) < 2 or len(words[-1]) < 3:
        return None
    return cut


#: 5.5 (§7.0): the sixteen-character cuts of the operating aliases, by entity. Derived, never hand-edited;
#: tools/operating_registry.py refuses a cut that equals any other registry or ledger alias.
OPERATING_REVENUE_TRUNCATIONS: dict[str, tuple[str, ...]] = {
    entity: cuts
    for entity, aliases in OPERATING_REVENUE_SOURCE_ALIASES.items()
    if (cuts := tuple(dict.fromkeys(
        cut for alias in aliases
        if (cut := _operating_alias_cut(alias)) is not None
        and cut not in {normalize_transaction_description(other) for other in aliases}
    )))
}

#: What the classifier reads for an operating source: every alias and its sixteen-character cut.
OPERATING_REVENUE_READ_ALIASES: dict[str, tuple[str, ...]] = {
    entity: aliases + OPERATING_REVENUE_TRUNCATIONS.get(entity, ())
    for entity, aliases in OPERATING_REVENUE_SOURCE_ALIASES.items()
}
```

Create `tools/operating_registry.py`:

```python
"""The operating-revenue registry's validator (true revenue spec §7.4).

The operating registry (`OPERATING_REVENUE_SOURCE_ALIASES` and its types, the sixteen-character cuts) is hand-kept
in `analysis/classification_registry.py`. This module says what is wrong with it:

* every operating entity has a source type, and every typed entity has aliases;
* no operating alias or cut equals a financing alias of the ledger or an insurer's;
* a cut equals no other registry or ledger alias;
* a processor's bare alias waits for its advance product (`PROCESSOR_ADVANCE_PRODUCTS`): it is in the registry only
  when the ledger admits that product or the processor is in `PROCESSORS_WITHOUT_ADVANCE_PRODUCT`;

It also WARNS (never fails) when a multi-word operating alias spans the originator/entry boundary a bank prints between
two fields ('HEARTLAND PAYMENT SYSTEMS' printed as 'HEARTLAND DES:PAYMENT'), which a contiguous alias cannot match.

Usage: python -m tools.operating_registry --check   (exit 0 when there is no problem, 1 otherwise)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis import classification_registry as registry  # noqa: E402
from analysis.description_text import normalize_transaction_description as normalize  # noqa: E402
from analysis.flag_groups import FINANCING_STATES  # noqa: E402

#: The entry words a bank prints in its own field after the originator (Bank of America's DES, Chase's CO ENTRY DESCR).
_ENTRY_WORDS = frozenset({"DEPOSIT", "DEP", "PAYMENT", "PAYMENTS", "SETTLEMENT", "PAYOUT", "TRANSFER", "TXNS"})


def _aliases(table: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """{normalized alias: entity} of one table."""
    return {normalize(alias): entity for entity, aliases in table.items() for alias in aliases}


def _financing_aliases() -> dict[str, str]:
    table: dict[str, str] = {}
    for state, group in registry.PAYEE_GROUP_REGISTRIES.items():
        if state in FINANCING_STATES:
            table.update(_aliases(group))
    table.update(_aliases(registry.POTENTIAL_LENDER_ALIASES))
    return table


def _insurer_aliases() -> dict[str, str]:
    return {**_aliases(registry.INSURANCE_PROVIDER_ALIASES), **_aliases(registry.PREMIUM_FINANCE_ALIASES)}


def _ledger_aliases() -> dict[str, tuple[str, str]]:
    """{normalized alias: (group, entity)} of every table the ledger renders."""
    table: dict[str, tuple[str, str]] = {}
    for state, group in registry.PAYEE_GROUP_REGISTRIES.items():
        for alias, entity in _aliases(group).items():
            table[alias] = (state, entity)
    for state, group in (("potential_lender", registry.POTENTIAL_LENDER_ALIASES),
                         ("bank_name", registry.BANK_NAME_ALIASES),
                         ("card_issuer_context", registry.CARD_ISSUER_CONTEXT_ALIASES),
                         ("debt_relief", registry.DEBT_RELIEF_ALIASES),
                         ("premium_financing", registry.PREMIUM_FINANCE_ALIASES)):
        for alias, entity in _aliases(group).items():
            table[alias] = (state, entity)
    return table


def problems() -> list[str]:
    """Every problem of the hand-kept operating registry, as sentences."""
    found: list[str] = []
    aliases = registry.OPERATING_REVENUE_SOURCE_ALIASES
    types = registry.OPERATING_REVENUE_SOURCE_TYPES
    for entity in aliases:
        if entity not in types:
            found.append(f"operating entity {entity!r} has no source type")
    for entity in types:
        if entity not in aliases:
            found.append(f"source type of {entity!r} names no operating entity")
    financing = _financing_aliases()
    insurers = _insurer_aliases()
    ledger = _ledger_aliases()
    own = _aliases(aliases)
    for alias, entity in own.items():
        if alias in financing:
            found.append(f"operating alias {alias!r} of {entity!r} is a financing alias of {financing[alias]!r}")
        if alias in insurers:
            found.append(f"operating alias {alias!r} of {entity!r} is an insurer alias of {insurers[alias]!r}")
    for entity, cuts in registry.OPERATING_REVENUE_TRUNCATIONS.items():
        for cut in cuts:
            other = own.get(cut)
            if other is not None and other != entity:
                found.append(f"the cut {cut!r} of {entity!r} is an operating alias of {other!r}")
            if cut in ledger:
                group, holder = ledger[cut]
                found.append(f"the cut {cut!r} of {entity!r} is a {group} alias of {holder!r}")
            if cut in insurers:
                found.append(f"the cut {cut!r} of {entity!r} is an insurer alias of {insurers[cut]!r}")
    admitted = {
        entity for group in registry.PAYEE_GROUP_REGISTRIES.values() for entity in group
    }
    for processor, (bare, product) in registry.PROCESSOR_ADVANCE_PRODUCTS.items():
        present = [alias for alias in bare if normalize(alias) in own]
        if not present:
            continue
        cleared = (product is not None and product in admitted) or processor in registry.PROCESSORS_WITHOUT_ADVANCE_PRODUCT
        if not cleared:
            found.append(
                f"the bare alias {present[0]!r} of {processor!r} is in the registry before its advance product is in "
                "the lender ledger (PROCESSOR_ADVANCE_PRODUCTS)"
            )
    return found


def warnings() -> list[str]:
    """The operating aliases that span a bank's originator/entry boundary (never a failure)."""
    return [
        f"operating alias {alias!r} of {entity!r} spans the originator/entry boundary"
        for alias, entity in _aliases(registry.OPERATING_REVENUE_SOURCE_ALIASES).items()
        if len(alias.split()) > 1 and any(word in _ENTRY_WORDS for word in alias.split()[1:])
    ]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args != ["--check"]:
        print(__doc__)
        return 2
    for line in warnings():
        print(f"warning: {line}")
    found = problems()
    for line in found:
        print(f"problem: {line}")
    print(f"{len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_operating_registry.py -q -p no:cacheprovider`

Expected: PASS: `12 passed`.

- [ ] **Step 6: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-REGISTRY: `357 passed, 4 skipped`

- [ ] **Step 7: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/classification_registry.py tests/test_operating_registry.py tools/operating_registry.py
git commit -m "registry: the operating sources of the true-revenue fixes and their validator" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S1.2: The payout, card-settlement and auction forms

**Files:**
- Modify: `analysis/classification_registry.py:12-14, 1741`
- Modify: `tools/operating_registry.py:3-4, 7, 19, 82, 123`
- Modify (pins): `tests/test_operating_registry.py:5, 75`

**Depends on:** S1.1.

**Interfaces:**
- Consumes: S1.1's tables and validator.
- Produces:
  - `OPERATING_SOURCE_PAYOUT_FORMS: dict[str, tuple[tuple[str, str], ...]]` (entity -> (label, pattern))
  - `@dataclass(frozen=True) class CardSettlementForm(label: str, pattern: str, entity: str | None = None, refusal: str | None = None, bank: str | None = None)`
  - `CARD_SETTLEMENT_CREDIT_FORMS: tuple[CardSettlementForm, ...]` (labels `bankcard`, `merch_dep`, `mrchntsrvs`, `merch_svcs_setl_code`, `merchant_services_mid`, `brand_dep`, `dep_brand`, `gbl_brand`, `net_settle`, `batch_total`, `intuit_deposit`, `square_checking_sales`, `network_settlement`, `generic_card_sales`, `french_card_settlement`)
  - `WHOLESALE_AUCTION_PAYOUT_FORMS: dict[str, tuple[str, ...]]`, `WHOLESALE_AUCTION_REFUND_NAMES: dict[str, str]`
  - the validator's form checks (`_compiles`, `_check_form`)

**Why:** Spec §7.1 (the card-settlement forms, each with its refusal words, in reading order), §7.2 (the platform payout forms: a match names the entity and is payout context, so one row verifies) and §7.8 (the dealer-only auctions' observed payout forms, and the names a refund pair is found by). Nothing reads them until S2.2; the validator checks each compiles, names a typed entity, and reads no financing or insurer alias.

- [ ] **Step 1: Write the failing tests.**

In `tests/test_operating_registry.py` (line 5), replace:

```python
import pytest
```

with:

```python
import re

import pytest
```

Append to the end of `tests/test_operating_registry.py`:

```python
def test_every_form_compiles_and_names_a_typed_entity():
    for entity, forms in registry.OPERATING_SOURCE_PAYOUT_FORMS.items():
        assert entity in registry.OPERATING_REVENUE_SOURCE_TYPES
        for label, pattern in forms:
            assert re.compile(pattern) and label.endswith("_form")
    labels = [form.label for form in registry.CARD_SETTLEMENT_CREDIT_FORMS]
    assert len(labels) == len(set(labels))
    for form in registry.CARD_SETTLEMENT_CREDIT_FORMS:
        assert form.entity is None or form.entity in registry.OPERATING_REVENUE_SOURCE_TYPES
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_operating_registry.py -q -p no:cacheprovider`

Expected: FAIL: `1 failed, 12 passed`, the first with `AttributeError: module 'analysis.classification_registry' has no attribute 'OPERATING_SOURCE_PAYOUT_FORMS'. Did you mean: 'OPERATING_SOURCE_CONTEXT_WORDS'?`.

- [ ] **Step 3: Implement.**

In `analysis/classification_registry.py` (lines 12-14), replace:

```python
from __future__ import annotations

from .description_text import normalize_transaction_description
```

with:

```python
from __future__ import annotations

from dataclasses import dataclass

from .description_text import normalize_transaction_description
```

In `analysis/classification_registry.py`, after these lines (line 1741):

```python
    for entity, aliases in OPERATING_REVENUE_SOURCE_ALIASES.items()
}
```

insert:

```python
#: 5.5 (§7.2): platform payout forms. Each (label, pattern) names the platform together with its payout rail or
#: field layout, read on the credit's revenue text and on its joined originator and entry fields. A match names
#: the entity AND counts as payout context, so one row verifies.
OPERATING_SOURCE_PAYOUT_FORMS: dict[str, tuple[tuple[str, str], ...]] = {
    "Whatnot": (
        ("whatnot_fbo_form", r"\bFBO WHATNOT\b"),
        ("whatnot_rtp_form", r"\bRTP CREDIT WHATNOT INC\b"),
    ),
    "Faire": (("faire_order_form", r"\bFAIRE WHOLESALE\b.*\bORDER\b"),),
    "eBay": (
        ("ebay_payments_form", r"^(?=.*\bPAYMENTS\b)(?!.*\bRETURN(?:ED)?\b).*\bEBAY COM[A-Z0-9]{8}\b"),
        ("ebay_rtp_form", r"\bRTP (?:CREDIT|RCVD) EBAY COMMERCE INC\b"),
    ),
    "Amazon Marketplace": (
        ("amazon_payments_form",
         r"^(?=.*\bPAYMENTS\b)(?!.*\bRETURN(?:ED)?\b).*\bAMAZON C(?!ORPORATE\b|OM|APITAL|REDIT|ASH\b)[A-Z0-9]{8}\b"),
    ),
    "ClassPass": (("classpass_edi_form", r"\bCLASSPASS INC\b.*\bEDI PYMNTS\b"),),
    "ezCater": (("ezcater_payoneer_form", r"\bPAYONEER\b.*\bEZCATER\b"),),
    "Groupon": (("groupon_merchant_form", r"\bGRPN MERCH SVCS\b"),),
}


@dataclass(frozen=True)
class CardSettlementForm:
    """5.5 (§7.1): one card-settlement form. `pattern` is read on the credit's row before its receiver fields and on
    its joined originator and entry fields; `refusal`, read the same way, refuses the form; `entity` is the
    processor the form names (None for a generic form); `bank` limits the form to one bank's statements."""

    label: str
    pattern: str
    entity: str | None = None
    refusal: str | None = None
    bank: str | None = None


#: 5.5 (§7.1): the card-settlement forms, in reading order. Left boundary (?<![A-Z]) throughout, so a date glued on
#: the left ('01 02BANKCARD DEPOSIT') never blocks a form.
CARD_SETTLEMENT_CREDIT_FORMS: tuple[CardSettlementForm, ...] = (
    CardSettlementForm(
        "bankcard",
        r"^(?!.*\b(?:BANKCARD CTR|BANKCARD CENTER|PREMIER BANKCARD|FIRST BANKCARD|ELAN|CARDMEMBER|CARD SERVICES"
        r"|CARD SVCS|CREDIT CARD)\b)(?=.*(?<![A-Z])(?:BANKCARD|BANKCD|BNKCD|BKCD|BKCRD|BNKCRD)\b)"
        r"(?=.*\b(?:DEP|DEPOSITS?|DEPST|SETTLEMENT|SETTLE|SETLMT|SETL|STLMT|BTOT|MTOT)(?:SEC)?\b)",
        refusal=(
            r"(?<![A-Z])(?:BANKCARD|BANKCD|BNKCD|BKCD|BKCRD|BNKCRD)(?: [A-Z]+){0,2} (?:LLC|INC|CORP|LTD|GROUP"
            r"|HOLDINGS|FUNDING|CAPITAL|FINANCIAL|PARTNERS|SOLUTIONS|SERVICES|SVCS|CO)\b"
        ),
    ),
    CardSettlementForm(
        "merch_dep",
        r"(?<![A-Z])(?:MERCHANT )?MERCH(?: SVCS)? (?:DEP|DEPOSITS?|SETL|SETTLE|SETLMT|STLMT|SETTLEMENT)(?:SEC)?\b",
    ),
    CardSettlementForm("mrchntsrvs", r"\bDESCR MRCHNTSRVS(?:SEC)?\b"),
    CardSettlementForm("merch_svcs_setl_code", r"\bMERCH(?:ANT)? SVCS?(?: DES)? [A-Z0-9]*SETL\b"),
    CardSettlementForm("merchant_services_mid", r"\bMERCHANT SERVI(?:CES?)?\b.*\b(?:MID ?\d{6,}|TRANS SLIP)\b"),
    CardSettlementForm(
        "brand_dep",
        r"(?:^|\b(?:MISC PAYMENT|COMPTE DIVERS|DIRECT DEPOSIT) )(?:(?:VSA|VISA|VI|MC|MCD|MCARD|AMX|AMEX|DSC|DCVR|IDP"
        r"|DEBITCD) )+DEP ?\d|(?<![A-Z])(?:(?:VSA|VISA|VI|MC|MCD|MCARD|AMX|AMEX|DSC|DCVR|IDP|DEBITCD) )+DEP(?:\d"
        r"|\b.*\b(?:MSP|DIV|MERCH SVC)\b)",
    ),
    CardSettlementForm(
        "dep_brand",
        r"(?:^|\b(?:MISC PAYMENT|COMPTE DIVERS|DIRECT DEPOSIT) )DEP (?:VSA|VISA|VI|MC|MCD|MCARD|AMX|AMEX|DSC|DCVR|IDP"
        r"|DEBITCD) ?\d|(?<![A-Z])DEP (?:VSA|VISA|VI|MC|MCD|MCARD|AMX|AMEX|DSC|DCVR|IDP|DEBITCD)\d*\b.*\b(?:MSP|DIV)\b",
    ),
    CardSettlementForm(
        "gbl_brand", r"\b(?:(?:VISA|MC|AMEXO?|IDP|DISC|DCVR) )?GBL (?:VI|MC|AX|IDP|DS|DC)\d*\b",
        entity="Global Payments",
    ),
    CardSettlementForm(
        "net_settle", r"\b(?:DES|DESCR) NET (?:SETTLE|SETLMT|STLMT|SETL)(?:SEC)?\b",
        refusal=r"\b(?:LAW|ATTORNEYS?|ESQ|TRUST|ESCROW|TITLE|CLAIMS?)\b",
    ),
    CardSettlementForm("batch_total", r"\b[BM]TOT DEP\b"),
    CardSettlementForm(
        "intuit_deposit",
        r"\bINTUIT \d{6,}(?: DES)? DEPOSIT\b|\bDEPOSIT FROM INTUIT \d{6,}\b|\bINTUIT PYMT SOLN\b|\bQBOOKS\b"
        r"|\bORIG CO NAME INTUIT \d+\b.*\bDESCR DEPOSIT\b",
        entity="QuickBooks Payments",
        refusal=r"\b(?:TAX|RFND|REFUND|QBC|CAPITAL|LOAN)\b",
    ),
    CardSettlementForm(
        "square_checking_sales", r"^(?:\d+ ACTIVITIES|CARD PAYMENT) SALES$", entity="Square", bank="SQUARE",
    ),
    CardSettlementForm(
        "network_settlement",
        r"\b(?:AMERICAN EXPRESS|DISCOVER NETWORK)\b.*\b(?:SETTLEMENT|SETL)\b|\bAMEXO GBL\b"
        r"|\bMISC PAYMENT AMEX BANK OF CANADA\b",
    ),
    CardSettlementForm(
        "generic_card_sales",
        r"\b(?:VISA ?MC|CARD PROCESSING) (?:DEPOSIT|DEP|SETTLEMENT|SETL|STLM|STLMT)\b"
        r"|^(?!.*\b(?:BALANCE|REFUND|REWARDS?)\b).*\b(?:CREDIT CARD|CR CD|CC) (?:DEPOSIT|DEP|SETTLEMENT|SETL|STLMT)\b",
    ),
    CardSettlementForm("french_card_settlement", r"\bREGLEMENT (?:CARTE|MARCHAND|COMMERCANT)\b|\bDEPOT MARCHAND\b"),
)

#: 5.5 (§7.8): the observed payout forms of the dealer-only wholesale auctions; any other auction row stays
#: unverified. Keyed by operating entity.
WHOLESALE_AUCTION_PAYOUT_FORMS: dict[str, tuple[str, ...]] = {
    "Manheim": (r"\bMANHEIM US (?:DES )?(?:ACH PAYMNT|EDI PYMNTS)\b",),
    "ACV Auctions": (
        r"\bACV AUCTIONS INC PAYMENTS\b",
        r"\bORIG CO NAME ACV AUCTIONS INC\b.*\bCO ENTRY DESCR PAYMENTS SEC CCD\b",
    ),
    "OPENLANE": (
        r"\bORIG CO NAME OPENLANE INC\b.*\bCO ENTRY DESCR OPENLANE SEC CCD\b",
        r"^BACKLOTCARS PAYMENT\b",
    ),
}
#: 5.5 (§7.8): the broad auction names a refund pair is found by, on debits and wire BNF lines.
WHOLESALE_AUCTION_REFUND_NAMES: dict[str, str] = {
    "Manheim": r"\bMANHEIM\b",
    "ACV Auctions": r"\bACV AUCTIONS\b",
    "OPENLANE": r"\bOPENLANE\b|\bBACKLOT ?CARS\b",
}
```

In `tools/operating_registry.py` (lines 3-4), replace:

```python
The operating registry (`OPERATING_REVENUE_SOURCE_ALIASES` and its types, the sixteen-character cuts) is hand-kept
in `analysis/classification_registry.py`. This module says what is wrong with it:
```

with:

```python
The operating registry (`OPERATING_REVENUE_SOURCE_ALIASES` and its types, the sixteen-character cuts, the payout and
card-settlement forms) is hand-kept in `analysis/classification_registry.py`. This module says what is wrong with it:
```

In `tools/operating_registry.py` (line 7), replace:

```python
* no operating alias or cut equals a financing alias of the ledger or an insurer's;
```

with:

```python
* every payout form and card form compiles, and the entity it names is typed;
* no operating alias, cut or form equals (or, for a form, matches) a financing alias of the ledger or an insurer's;
```

In `tools/operating_registry.py` (line 19), replace:

```python
import sys
```

with:

```python
import re
import sys
```

In `tools/operating_registry.py` (line 82), replace:

```python
    own = _aliases(aliases)
```

with:

```python
    own = _aliases(aliases)
    for entity, forms in registry.OPERATING_SOURCE_PAYOUT_FORMS.items():
        if entity not in types:
            found.append(f"payout form entity {entity!r} is not a typed operating entity")
        for label, pattern in forms:
            _check_form(found, f"payout form {label!r}", pattern, financing, insurers)
    for form in registry.CARD_SETTLEMENT_CREDIT_FORMS:
        if form.entity is not None and form.entity not in types:
            found.append(f"card form {form.label!r} names {form.entity!r}, which is not a typed operating entity")
        _check_form(found, f"card form {form.label!r}", form.pattern, financing, insurers)
        if form.refusal is not None:
            _compiles(found, f"card form {form.label!r} refusal", form.refusal)
```

In `tools/operating_registry.py` (line 123), replace:

```python
def main(argv: list[str] | None = None) -> int:
```

with:

```python
def _compiles(found: list[str], name: str, pattern: str) -> re.Pattern[str] | None:
    try:
        return re.compile(pattern)
    except re.error as error:
        found.append(f"{name} does not compile: {error}")
        return None


def _check_form(found: list[str], name: str, pattern: str, financing: dict[str, str], insurers: dict[str, str]) -> None:
    compiled = _compiles(found, name, pattern)
    if compiled is None:
        return
    for alias, entity in (*financing.items(), *insurers.items()):
        if compiled.fullmatch(alias):
            found.append(f"{name} reads the financing or insurer alias {alias!r} of {entity!r}")


def main(argv: list[str] | None = None) -> int:
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_operating_registry.py -q -p no:cacheprovider`

Expected: PASS: `13 passed`.

- [ ] **Step 5: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-REGISTRY: `357 passed, 4 skipped`

- [ ] **Step 6: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/classification_registry.py tests/test_operating_registry.py tools/operating_registry.py
git commit -m "registry: the payout, card-settlement and auction forms" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S1.3: The Blue-plan, healthcare and dealer-funding payer tables

**Files:**
- Modify: `analysis/classification_registry.py:1862`
- Modify: `tools/operating_registry.py:4, 11, 71, 122-124`
- Modify (pins): `tests/test_operating_registry.py:88`

**Depends on:** S1.2.

**Interfaces:**
- Consumes: S1.1 and S1.2.
- Produces:
  - `BLUE_PLAN_CLAIM_PAYERS: tuple[str, ...]` (regex sources)
  - `HEALTHCARE_PAYER_ALIASES: dict[str, tuple[str, ...]]`
  - `DEALER_FUNDING_PAYERS: dict[str, tuple[str, ...]]`
  - the validator's payer-table checks

**Why:** Spec §7.7 (T18: the Blue-plan spellings that escape the insurer registry, read only when claim first is off; the healthcare payers Q6 names as proof) and §8.7 (Q7: the auto lenders that pay dealers). The validator refuses a healthcare alias that is a ledger or insurer alias, and a dealer-funding alias that is a ledger alias outside the vehicle-financing group.

- [ ] **Step 1: Write the failing tests.**

Append to the end of `tests/test_operating_registry.py`:

```python
def test_the_payer_tables_collide_with_no_ledger_or_insurer_alias(monkeypatch):
    monkeypatch.setattr(registry, "HEALTHCARE_PAYER_ALIASES", {"Fabrikam Care": ("BCBSM",)})
    assert any("insurer alias" in problem for problem in operating_registry.problems())
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_operating_registry.py -q -p no:cacheprovider`

Expected: FAIL: `1 failed, 13 passed`, the first with `AttributeError: module 'analysis.classification_registry' has no attribute 'HEALTHCARE_PAYER_ALIASES'`.

- [ ] **Step 3: Implement.**

In `analysis/classification_registry.py`, after these lines (line 1862):

```python
    "OPENLANE": r"\bOPENLANE\b|\bBACKLOT ?CARS\b",
}
```

insert:

```python
#: 5.5 (§7.7, T18): Blue-plan spellings that escape INSURANCE_PROVIDER_ALIASES. Read only while
#: HCCLAIMPMT_CLAIM_FIRST is off, when their HCCLAIMPMT claim payments are held with the insurer's.
BLUE_PLAN_CLAIM_PAYERS: tuple[str, ...] = (
    r"\bBCBS[A-Z]*\b", r"\bBLUE CROSS\b", r"\bBLUE CARE NETWORK\b", r"\bANTHEM BLUE\b", r"\bCAREFIRST\w*\b",
)

#: 5.6 (§7.7): healthcare payers that are not in INSURANCE_PROVIDER_ALIASES: Medicare contractors, state Medicaid
#: programs, TRICARE and VA Community Care, US health plans, pharmacy-benefit managers and claim-payment
#: platforms. Read on the credit's payer region, on a row with an electronic-payment form (Q6).
HEALTHCARE_PAYER_ALIASES: dict[str, tuple[str, ...]] = {
    "Noridian": ("NORIDIAN",),
    "Palmetto GBA": ("PALMETTO GBA",),
    "Novitas Solutions": ("NOVITAS",),
    "WPS Health Solutions": ("WPS",),
    "National Government Services": ("NATIONAL GOVERNMENT SERV",),
    "CGS Administrators": ("CGS ADMINISTRATORS",),
    "First Coast Service Options": ("FIRST COAST SERVICE",),
    "State Medicaid program": ("MEDICAID", "MEDI CAL"),
    "Medicare": ("MEDICARE",),
    "TRICARE": ("TRICARE",),
    "VA Community Care": ("VA CCN",),
    "Aetna": ("AETNA",),
    "Cigna": ("CIGNA",),
    "Humana": ("HUMANA",),
    "UnitedHealthcare": ("UNITEDHEALTHCARE", "UNITED HEALTHCARE", "UHC"),
    "Optum": ("OPTUM", "OPTUMRX", "OPTUMHEALTH"),
    "Molina Healthcare": ("MOLINA HC", "MOLINA HEALTHCARE"),
    "WellCare": ("WELLCARE",),
    "Centene": ("CENTENE",),
    "Anthem": ("ANTHEM",),
    "Express Scripts": ("EXPRESS SCRIPTS",),
    "CVS Caremark": ("CAREMARK",),
    "Zelis": ("ZELIS",),
    "ECHO Health": ("ECHO HEALTH", "HNB ECHO", "PNC ECHO"),
    "InstaMed": ("INSTAMED",),
    "VPay": ("VPAY",),
    "PaySpan": ("PAYSPAN",),
}

#: 5.6 (§8.7, Q7): auto lenders that pay dealers, beside the vehicle_financing registry. A credit from one of them
#: that prints a dealer-funding word is the dealer's revenue. Until S1 admits one into the ledger's
#: vehicle-financing group, its other credits are held (financing_named_payer). Never Westlake Flooring.
DEALER_FUNDING_PAYERS: dict[str, tuple[str, ...]] = {
    "Westlake Financial": ("WESTLAKE FINANCIAL", "WESTLAKE FINANCI", "WESTLAKE PORTFOL"),
    "United Auto Credit": ("UNITED AUTO CREDIT", "UNITED AUTO CRED"),
    "Strike Acceptance": ("STRIKE ACCEPTANCE", "STRIKEACCEPTANCE"),
    "Professional Financial Services (PFS)": ("PROF FIN SER PFS",),
    "Suncoast Credit Union": ("SUNCOAST CREDIT UNION", "SUNCOAST CU"),
    "CU Direct": ("CU DIRECT", "CUDL"),
    "Credit Acceptance": ("CREDIT ACCEPTANCE", "CREDITACCEPTANCE"),
    "Exeter Finance": ("EXETER FINANCE", "EXETERFINANCELLC"),
    "Flagship Credit Acceptance": ("FLAGSHIP CREDIT",),
    "GLS Auto": ("GLS AUTO", "GLOBAL LENDING SERVICES"),
    "Santander Consumer": ("SANTANDER CONSUMER",),
    "Chrysler Capital": ("CHRYSLER CAPITAL",),
    "GM Financial": ("GM FINANCIAL",),
    "Toyota Financial": ("TOYOTA FINANCIAL",),
    "Honda Financial": ("HONDA FINANCIAL", "AMERICAN HONDA FINANCE"),
    "Nissan Motor Acceptance": ("NISSAN MOTOR ACC", "NISSAN MOTOR ACCEPTANCE"),
    "CarMax Auto Finance": ("CARMAX AUTO FINANCE",),
    "Ally": ("ALLY FINANCIAL",),
    "American Credit Acceptance": ("AMERICAN CREDIT ACC", "AMERICAN CREDIT ACCEPTANCE"),
    "Regional Acceptance": ("REGIONAL ACCEPTAN", "REGIONAL ACCEPTANCE"),
    "Nicholas Financial": ("NICHOLAS FINANCIAL",),
    "Lendbuzz": ("LENDBUZZ",),
}
```

In `tools/operating_registry.py` (line 4), replace:

```python
card-settlement forms) is hand-kept in `analysis/classification_registry.py`. This module says what is wrong with it:
```

with:

```python
card-settlement forms) and the two 5.6 payer tables (`HEALTHCARE_PAYER_ALIASES`, `DEALER_FUNDING_PAYERS`) are
hand-kept in `analysis/classification_registry.py`. This module says what is wrong with them:
```

In `tools/operating_registry.py` (line 11), replace:

```python
  when the ledger admits that product or the processor is in `PROCESSORS_WITHOUT_ADVANCE_PRODUCT`;
```

with:

```python
  when the ledger admits that product or the processor is in `PROCESSORS_WITHOUT_ADVANCE_PRODUCT`;
* `HEALTHCARE_PAYER_ALIASES` collides with no ledger alias and no insurer alias;
* `DEALER_FUNDING_PAYERS` collides with no ledger alias outside the vehicle-financing group, which Q7 names on purpose.
```

In `tools/operating_registry.py` (line 71), replace:

```python
    """Every problem of the hand-kept operating registry, as sentences."""
```

with:

```python
    """Every problem of the hand-kept operating registry and the 5.6 payer tables, as sentences."""
```

In `tools/operating_registry.py` (lines 122-124), replace:

```python
                "the lender ledger (PROCESSOR_ADVANCE_PRODUCTS)"
            )
    return found
```

with:

```python
                "the lender ledger (PROCESSOR_ADVANCE_PRODUCTS)"
            )
    for alias, entity in _aliases(registry.HEALTHCARE_PAYER_ALIASES).items():
        if alias in ledger:
            group, holder = ledger[alias]
            found.append(f"healthcare payer alias {alias!r} of {entity!r} is a {group} alias of {holder!r}")
        if alias in insurers:
            found.append(f"healthcare payer alias {alias!r} of {entity!r} is an insurer alias of {insurers[alias]!r}")
    for alias, entity in _aliases(registry.DEALER_FUNDING_PAYERS).items():
        if alias in ledger and ledger[alias][0] != "vehicle_financing":
            group, holder = ledger[alias]
            found.append(f"dealer-funding payer alias {alias!r} of {entity!r} is a {group} alias of {holder!r}")
    return found
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_operating_registry.py -q -p no:cacheprovider`

Expected: PASS: `14 passed`.

- [ ] **Step 5: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-REGISTRY: `357 passed, 4 skipped`

- [ ] **Step 6: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/classification_registry.py tests/test_operating_registry.py tools/operating_registry.py
git commit -m "registry: the Blue-plan, healthcare and dealer-funding payer tables" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S1.4: BNPL settlements are payout-credit entities (owner ruling OQ2)

**Files:**
- Modify: `analysis/classification_registry.py:1466`
- Modify (pins): `tests/test_operating_registry.py:93`
- Modify (pins): `tests/test_lender_registry_content.py:212-213, 217-219`

**Depends on:** S1.3.

**Interfaces:**
- Consumes: `PAYOUT_CREDIT_ENTITIES` (`analysis/classification_registry.py`), the ledger entities `AFFIRM`, `Afterpay`, `GreenSky`, `Klarna Inc`, `Sunbit`.
- Produces:
  - `PAYOUT_CREDIT_ENTITIES` with the five names appended

**Why:** Owner review §19, OQ2: Affirm, Afterpay, GreenSky, Klarna and Sunbit settlements to the merchant are the merchant's own sales, not financing proceeds. Each is an admitted ledger entity of the `alternative_position` group, which `tools/lender_ledger.py` requires of a payout-credit entity. Their credits leave D1 at once (the census's `8_oq2_bnpl_settlement`: 8 rows); under 5.6 they are counted as `payout_credit_entity`. Their debits keep their group.

- [ ] **Step 1: Write the failing tests.**

Append to the end of `tests/test_operating_registry.py`:

```python
def test_the_bnpl_settlements_are_payout_credit_entities():
    assert {"AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit"} <= set(registry.PAYOUT_CREDIT_ENTITIES)
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_operating_registry.py -q -p no:cacheprovider`

Expected: FAIL: `1 failed, 14 passed`, the first with `AssertionError: assert {'AFFIRM', 'A...nc', 'Sunbit'} <= {'American Fi... 'Sezzle Inc'}`.

- [ ] **Step 3: Implement.**

In `analysis/classification_registry.py` (line 1466), replace:

```python
PAYOUT_CREDIT_ENTITIES: tuple[str, ...] = ("Sezzle Inc", "American First Finance, LLC", "PAYABILITY")
```

with:

```python
PAYOUT_CREDIT_ENTITIES: tuple[str, ...] = (
    "Sezzle Inc", "American First Finance, LLC", "PAYABILITY",
    # Owner ruling 2026-09-28 (true revenue spec, OQ2): a buy-now-pay-later provider's settlement to the merchant is
    # the merchant's own sale, so it is revenue, not financing proceeds.
    "AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit",
)
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_operating_registry.py -q -p no:cacheprovider`

Expected: PASS: `15 passed`.

- [ ] **Step 5: Re-pin the assertions this task moves (pin ledger rows 1-2).**

In `tests/test_lender_registry_content.py` (lines 212-213), replace:

```python
    ("PAYABILITY PAYMENT", "PAYABILITY", "confirmed_lender"),
])
```

with:

```python
    ("PAYABILITY PAYMENT", "PAYABILITY", "confirmed_lender"),
    # Owner ruling 2026-09-28 (true revenue spec OQ2): the BNPL providers' settlements to the merchant are revenue.
    ("AFFIRM PAYMENT", "AFFIRM", "alternative_position"),
    ("AFTERPAY PAYMENT", "Afterpay", "alternative_position"),
    ("GREENSKY PAYMENT", "GreenSky", "alternative_position"),
    ("KLARNA PAYMENT", "Klarna Inc", "alternative_position"),
    ("SUNBIT PAYMENT", "Sunbit", "alternative_position"),
])
```

In `tests/test_lender_registry_content.py` (lines 217-219), replace:

```python
    # as revenue (PAYOUT_CREDIT_ENTITIES, a D1 exception); the matcher still gives every row the entity's group.
    assert registry.PAYOUT_CREDIT_ENTITIES == ("Sezzle Inc", "American First Finance, LLC", "PAYABILITY")
    assert BY_NAME[entity].status == "admitted" and BY_NAME[entity].group in FINANCING_STATES
```

with:

```python
    # as revenue (PAYOUT_CREDIT_ENTITIES, a D1 exception); the matcher still gives every row the entity's group.
    assert registry.PAYOUT_CREDIT_ENTITIES == (
        "Sezzle Inc", "American First Finance, LLC", "PAYABILITY", "AFFIRM", "Afterpay", "GreenSky", "Klarna Inc",
        "Sunbit",
    )
    assert BY_NAME[entity].status == "admitted" and BY_NAME[entity].group in FINANCING_STATES
```

- [ ] **Step 6: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-REGISTRY: `362 passed, 4 skipped`
  - SEL-CLASSIFIER: `755 passed, 2 deselected`

- [ ] **Step 7: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/classification_registry.py tests/test_lender_registry_content.py tests/test_operating_registry.py
git commit -m "registry: BNPL settlements are payout-credit entities (owner ruling OQ2)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S1.5: Ledger admissions: the processors' advance products, Parafin, Pipe's cut, the receivables financiers and the dealer-funding lenders

**Files:**
- Create (scratch, never committed): `C:/Users/GustavoPrietodePaula/lender-research/revenue/research/ledger55.json` (written by the research rounds, Steps 1 and 2), `C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/s15/research_ledger.py` (Step 3), `C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/s15/admission_effect.py` and the owner's signed-off list `C:/Users/GustavoPrietodePaula/lender-research/revenue/census/g7_allowlist.json` (Step 6; G7 reads it in Task A1).
- Modify: `docs/lender-registry-ledger.json` (only through the Step 3 script), then `analysis/classification_registry.py` (the GENERATED block, by `python -m tools.build_lender_registry --write`), `docs/lender-registry-evidence.md` (the same command).
- Modify: `analysis/classification_registry.py`: `PROCESSOR_ADVANCE_PRODUCTS`, `PROCESSORS_WITHOUT_ADVANCE_PRODUCT` and, for each processor the ledger clears, its bare aliases in `OPERATING_REVENUE_SOURCE_ALIASES` and its type in `OPERATING_REVENUE_SOURCE_TYPES` (all added by Task S1.1).
- Create: `tests/test_registry_additions_55.py`.

**Depends on:** S1.1 to S1.3. It may run in parallel with S2, and must land before Task S3.2 (the 5.5 census), so the census measures it.

**Interfaces:**
- Consumes: `PROCESSOR_ADVANCE_PRODUCTS: dict[str, tuple[tuple[str, ...], str | None]]` and `PROCESSORS_WITHOUT_ADVANCE_PRODUCT: frozenset[str]` (S1.1); `DEALER_FUNDING_PAYERS` (S1.3); the ledger's schema and its validator (`tools/lender_ledger.py`, `tools/build_lender_registry.py`).
- Produces: ledger entities in the `alternative_position` group (the processors' advance products and Parafin), the `PIPE TECHNOLOGIE` alias of `Pipe Technologies Inc`, the receivables financiers of §7.9 in their groups, and `vehicle_financing` entities or aliases for the dealer-funding lenders the ledger lacks, each only on the owner's sign-off; the bare processor aliases the ledger clears (`GATED_PROCESSOR_ALIASES` then drops them by itself); `g7_allowlist.json` (`{"signed_off": "<date and words of the owner's answer>", "entities": [<ledger entity names>]}`).

**Why:** Spec §7.1 ("Ledger before aliases"): a processor's bare alias (`SHIFT4`, `SUMUP`, `JOBBER BY STRI(PE)`, `CLEARENT`, `SMARTTAB`, `BRAINTREE`) joins the operating registry only after its own advance product is admitted as an alternative position, or after the ledger records that it has none; "if the ledger can neither admit the product nor record that there is none, that processor's bare alias is not added". §7.3 proposes Parafin and Pipe's 16-character cut `PIPE TECHNOLOGIE` for the financing registry. §8.7: "S1 admits the `DEALER_FUNDING_PAYERS` lenders the ledger lacks into its vehicle-financing group, through the ledger's process"; until then their credits that Q7 does not verify are held (`financing_named_payer`, Task S4.2). §7.9 sends its registry side findings to the ledger too: eCapital and Stenn as factors, the printed legal names of FairFigure, GFE, One River Group and Uncapped, and the spaced `SAMSON SERVICING` (a Stenn wire citing an invoice verifies until then: the recorded residual of S2.3's wire tests). Admission follows the ledger's process: a public source and an independent second agent. Nothing here is decided by this plan: the rounds decide, the gate takes only VERIFIED entries, and the owner signs off on every admission that moves a debit (review I2), because guard G7 forbids any debit move the owner has not declared.

Measured on 2026-09-28 (the prototype, `match_known_payee` on each `DEALER_FUNDING_PAYERS` alias): the ledger already reads `CREDITACCEPTANCE`, `EXETERFINANCELLC`, `FLAGSHIP CREDIT`, `CHRYSLER CAPITAL`, `GM FINANCIAL`, `TOYOTA FINANCIAL`, `NISSAN MOTOR ACC`, `CARMAX AUTO FINANCE`, `ALLY FINANCIAL`, `AMERICAN CREDIT ACC` and `REGIONAL ACCEPTAN` as `vehicle_financing`. It lacks Westlake Financial (its entities read only `WESTLAKE PAYMENT` and the Chase CCD form), United Auto Credit, Strike Acceptance, Professional Financial Services (PFS), Suncoast Credit Union, CU Direct's `CU DIRECT` and `CUDL` spellings (the entity `CU Direct Corporation` exists), GLS Auto, `SANTANDER CONSUMER` (the entity `Santander Consumer USA Inc` exists), `HONDA FINANCIAL` and `AMERICAN HONDA FINANCE` (the entity `American Honda Finance Corporation` exists), `NISSAN MOTOR ACCEPTANCE`, `AMERICAN CREDIT ACCEPTANCE`, `REGIONAL ACCEPTANCE`, Nicholas Financial and Lendbuzz.

**Debits move, on purpose, and only on the owner's word (review I2).** An admitted lender's debits become counted rows of its group (an alternative position, a vehicle loan, a factor), so `tools/lender_census.py` shows them as gained, and spec §14.3's G7 asks for zero debit moves against 5.4. So the admission list goes to the owner first (Step 6), with what each admission would move measured on the cache; only the entities the owner signs off are admitted, and G7's check (Task A1, Step 3) reads exactly that list as its declared exceptions. Any other debit move fails G7. Without a sign-off, nothing that moves a debit is admitted: the processors whose bare aliases wait keep waiting, Pipe's cut and the lenders stay out, and their credits stay counted or held as S4.2 decides. The census figures of S3.2 and A1 were measured with no admission; with admissions, both tasks re-measure (S3.2 Step 3, A1 Step 1).

- [ ] **Step 1: The research round (r1).** Dispatch one research agent with web access and this brief (the orchestrator keeps the reply):

  > For each item below, find public sources (the company's own pages, regulator or court filings, reputable trade press) and write one JSON record in the ledger's entity schema (`entity`, `group`, `business_type`, `aliases`, `status`, `short_alias_reason`, `evidence` [`{"source": url, "note": what the page says}`], `verdicts` [`{"round": "r1", "verdict": "proposed", "confirmed": true}`], `where_looked` [urls], `notes`). Aliases are the names as a bank statement prints them, upper case, never a person's name, never a digit run of five or more. `status` is `admitted` for every record proposed for admission (the ledger renders only `admitted` entities into their group; `review` would render it into the potential-lender table and `rejected` nowhere). Items: (a) the advance or capital product of each processor: Shift4 (Shift4 Capital), SumUp (its business cash advance), Jobber (Jobber Capital, paid through Parafin and Stripe), Clearent / Xplor Pay, SmartTab, Braintree; group `alternative_position`, business_type `platform_embedded_financing`; or, where the processor offers none, a record `{"processor": <name>, "none": true, "evidence": [...], "where_looked": [...], "verdicts": [...]}` in `no_product`; (b) Parafin (the capital provider behind several platforms' merchant advances), group `alternative_position`; (c) for the existing ledger entity `Pipe Technologies Inc`, an `entity_updates` record adding the alias `PIPE TECHNOLOGIE` (the 16-character cut of its name); (d) each of these auto lenders as a `vehicle_financing` entity, or as an `entity_updates` alias record for the existing entity named: Westlake Financial, United Auto Credit, Strike Acceptance, Professional Financial Services (PFS), Suncoast Credit Union, CU Direct (`CU Direct Corporation`), GLS Auto, Santander Consumer (`Santander Consumer USA Inc`), American Honda Finance (`American Honda Finance Corporation`), Nissan Motor Acceptance (`Nissan Motor Acceptance Company LLC`), American Credit Acceptance (`American Credit Acceptance, LLC`), Regional Acceptance (`Regional Acceptance Corporation`), Nicholas Financial, Lendbuzz; (e) §7.9's registry side findings: eCapital and Stenn (group `factoring`), and the printed legal names of FairFigure, GFE, One River Group and Uncapped and the spaced `SAMSON SERVICING` (as `entity_updates` of the existing entities, or new entities in the group the sources give). Write `{"new_entities": [...], "entity_updates": [...], "no_product": [...]}` to `C:/Users/GustavoPrietodePaula/lender-research/revenue/research/ledger55.json`.

- [ ] **Step 2: The independent verify round (r2).** Dispatch a second agent, which has not seen round r1's reasoning, with the file only: "For every record, re-open each source and append a verdict `{"round": "r2", "verdict": "upheld" | "corrected" | "refuted" | "unresolved", "confirmed": true | false}` to its `verdicts` (for an `entity_updates` record, to a new `append_verdicts` list). Correct a record only by appending a verdict and a note; never delete a record." The file stays outside the repository.

- [ ] **Step 3: The gate script.** Write `C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/s15/research_ledger.py` with the Write tool:

```python
"""Task S1.5: list the ledger55 research records and whether each is VERIFIED (an r2 verdict upheld or corrected,
confirmed), and add the VERIFIED ones to docs/lender-registry-ledger.json. Prints names, statuses and rounds only.

  python research_ledger.py gate
  python research_ledger.py add "<entity>" ["<entity>" ...]
  python research_ledger.py update "<entity>"
"""
import copy
import json
import sys
from pathlib import Path

RESEARCH = Path("C:/Users/GustavoPrietodePaula/lender-research/revenue/research/ledger55.json")
LEDGER = Path("C:/Users/GustavoPrietodePaula/work/true-revenue/docs/lender-registry-ledger.json")


def _verified(verdicts):
    return next((v for v in verdicts if v["round"] == "r2" and v["verdict"] in ("upheld", "corrected")
                 and v["confirmed"]), None)


def _research():
    return json.loads(RESEARCH.read_text(encoding="utf-8"))


def gate():
    data = _research()
    for record in data.get("new_entities", []):
        found = _verified(record["verdicts"])
        print(f"{'VERIFIED' if found else 'not verified'}: {record['entity']} ({record['group']}, {record['status']})")
    for update in data.get("entity_updates", []):
        found = _verified(update.get("append_verdicts", []))
        print(f"{'VERIFIED' if found else 'not verified'}: update of {update['entity']}")
    for record in data.get("no_product", []):
        found = _verified(record["verdicts"])
        print(f"{'VERIFIED' if found else 'not verified'}: no advance product: {record['processor']}")


def _save(ledger):
    LEDGER.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def add(names):
    records = {record["entity"]: record for record in _research().get("new_entities", [])}
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    present = {entity["entity"] for entity in ledger["entities"]}
    for name in names:
        record = records[name]
        if not _verified(record["verdicts"]):
            raise SystemExit(f"refused: {name} is not VERIFIED")
        if name in present:
            raise SystemExit(f"refused: {name} is already in the ledger")
        ledger["entities"].append(copy.deepcopy(record))
        print(f"added {name} ({record['group']}, {record['status']})")
    _save(ledger)


def update(name):
    [change] = [item for item in _research()["entity_updates"] if item["entity"] == name]
    if not _verified(change.get("append_verdicts", [])):
        raise SystemExit(f"refused: the update of {name} is not VERIFIED")
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    [record] = [item for item in ledger["entities"] if item["entity"] == name]
    record["aliases"] += [alias for alias in change.get("add_aliases", []) if alias not in record["aliases"]]
    record["evidence"] += change.get("append_evidence", [])
    record["where_looked"] += change.get("append_where_looked", [])
    record["verdicts"] += change.get("append_verdicts", [])
    record["notes"] += change.get("append_notes", "")
    _save(ledger)
    print(f"updated {name}")


if __name__ == "__main__":
    {"gate": lambda: gate(), "add": lambda: add(sys.argv[2:]),
     "update": lambda: update(sys.argv[2])}[sys.argv[1]]()
```

  Run `C:/Python314/python.exe C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/s15/research_ledger.py gate` and put its output in the task report. Only VERIFIED lines go further.

- [ ] **Step 4: Write the guard tests.** Create `tests/test_registry_additions_55.py`. These are guards, not failing tests: they read the ledger, so they pass before any admission (nothing is admitted or cleared, so every assertion holds vacuously or on today's tables) and hold whichever records the gate and the owner let through:

```python
"""Task S1.5 (true revenue spec §7.1, §7.3, §8.7): the ledger admissions of the processors' advance products, Parafin,
Pipe's cut and the dealer-funding lenders, as the VERIFIED research carries them. Fabricated rows only; the names are
the registry's business names."""
from __future__ import annotations

import json
from pathlib import Path

from analysis.classification_registry import (
    DEALER_FUNDING_PAYERS,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    PROCESSOR_ADVANCE_PRODUCTS,
    PROCESSORS_WITHOUT_ADVANCE_PRODUCT,
)
from analysis.payee_matcher import match_known_payee
from analysis.transaction_classifier import classify_transaction

LEDGER = json.loads((Path(__file__).resolve().parents[1] / "docs/lender-registry-ledger.json").read_text(
    encoding="utf-8"))
ADMITTED = {entity["entity"]: entity for entity in LEDGER["entities"] if entity["status"] == "admitted"}


def test_a_processor_s_bare_name_is_read_exactly_when_the_ledger_cleared_it():
    read = {alias for aliases in OPERATING_REVENUE_SOURCE_ALIASES.values() for alias in aliases}
    for processor, (bare, product) in PROCESSOR_ADVANCE_PRODUCTS.items():
        cleared = (product is not None and product in ADMITTED) or processor in PROCESSORS_WITHOUT_ADVANCE_PRODUCT
        assert (set(bare) <= read) is cleared, processor
        if cleared:
            assert any(processor == entity for entity in OPERATING_REVENUE_SOURCE_TYPES), processor


def test_an_admitted_advance_product_is_financing_never_a_settlement():
    for processor, (_bare, product) in PROCESSOR_ADVANCE_PRODUCTS.items():
        if product is None:
            continue
        assert ADMITTED[product]["group"] == "alternative_position", product
        alias = ADMITTED[product]["aliases"][0]
        record = classify_transaction(f"{alias} DES:ADVANCE ID:1", 5000.0, direction="credit")
        assert record.revenue_classification == "non_revenue", (processor, record.revenue_match_method)


def test_parafin_and_pipe_s_cut_read_as_financing_once_admitted():
    if "Parafin" in ADMITTED:
        record = classify_transaction("PARAFIN DES:ADVANCE ID:1", 5000.0, direction="credit")
        assert record.revenue_classification == "non_revenue"
    pipe = ADMITTED.get("Pipe Technologies Inc")
    if pipe is not None and "PIPE TECHNOLOGIE" in pipe["aliases"]:
        found = match_known_payee("PIPE TECHNOLOGIE DES:ADVANCE ID:1")
        assert found is not None and found.entity == "Pipe Technologies Inc"


def test_every_dealer_funding_lender_the_ledger_reads_is_vehicle_financing():
    for lender, aliases in DEALER_FUNDING_PAYERS.items():
        for alias in aliases:
            found = match_known_payee(alias)
            assert found is None or found.state == "vehicle_financing", (lender, alias, found)
```

- [ ] **Step 5: Run them.** `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_registry_additions_55.py -q -p no:cacheprovider`. Expected before any admission: 4 passed, by design. The file fails the moment an admission and the code disagree (Step 8 runs it again).

- [ ] **Step 6: The owner's sign-off on the admission list (review I2).** Measure what each VERIFIED record would move, read-only on the cache, with this scratch script (Write tool; `C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/s15/admission_effect.py`; it prints entity names, groups and counts only):

```python
"""Task S1.5 (scratch, never committed): what each VERIFIED admission of the research file would move, measured on the
corpus cache read-only before anything is admitted: the debit and credit rows whose description names one of the
candidate's aliases (whole words, the registry's own matcher), by entity. The owner signs off on this list (review I2).
Prints entity names, groups and counts only.
Usage: python admission_effect.py <webapp_data dir> <ledger55.json> [--limit N]"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "C:/Users/GustavoPrietodePaula/work/true-revenue")
from analysis.description_text import normalize_transaction_description as normalize  # noqa: E402
from analysis.payee_matcher import registry_match  # noqa: E402

sys.path.insert(0, "C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/s15")
from research_ledger import _verified  # noqa: E402


def _accounts(node):
    if isinstance(node, dict):
        statement = node.get("statement")
        if isinstance(statement, dict) and isinstance(statement.get("transactions"), list):
            yield statement
            return
        for value in node.values():
            yield from _accounts(value)
    elif isinstance(node, list):
        for value in node:
            yield from _accounts(value)


def candidates(research: dict) -> dict[str, tuple[str, tuple[str, ...]]]:
    """{entity: (group, aliases)} of the VERIFIED new entities and alias updates."""
    found = {record["entity"]: (record["group"], tuple(record["aliases"]))
             for record in research.get("new_entities", []) if _verified(record["verdicts"])}
    for update in research.get("entity_updates", []):
        if _verified(update.get("append_verdicts", [])):
            found[update["entity"]] = ("update", tuple(update.get("add_aliases", [])))
    return found


def main(data_dir: Path, research_path: Path, limit: int | None) -> None:
    wanted = candidates(json.loads(research_path.read_text(encoding="utf-8")))
    registry = {entity: aliases for entity, (_group, aliases) in wanted.items() if aliases}
    connection = sqlite3.connect(f"{(data_dir / 'webapp.db').resolve().as_uri()}?mode=ro", uri=True)
    try:
        latest = connection.execute(
            "SELECT a.artifact_path FROM artifact_cache a JOIN (SELECT input_sha256, MAX(created_at) AS newest "
            "FROM artifact_cache WHERE stage = 'analysis' GROUP BY input_sha256) b ON a.input_sha256 = b.input_sha256 "
            "AND a.created_at = b.newest WHERE a.stage = 'analysis'"
        ).fetchall()
    finally:
        connection.close()
    counts: dict = defaultdict(lambda: [0, 0, 0])
    for number, (relative,) in enumerate(latest):
        if limit is not None and number >= limit:
            break
        try:
            payload = json.loads((data_dir / "artifacts" / relative).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for statement in _accounts(payload.get("artifact")):
            touched = set()
            for txn in statement["transactions"]:
                found = registry_match(normalize(txn.get("description") or ""), registry)
                if found is None:
                    continue
                counts[found[0]][0 if (txn.get("amount") or 0) < 0 else 1] += 1
                touched.add(found[0])
            for entity in touched:
                counts[entity][2] += 1
    print(f"{len(latest) if limit is None else min(limit, len(latest))} cached analyses read")
    for entity, (group, _aliases) in sorted(wanted.items()):
        debits, credits, statements = counts.get(entity, [0, 0, 0])
        print(f"  {entity} ({group}): debit rows {debits}, credit rows {credits}, statements {statements}")


if __name__ == "__main__":
    arguments = sys.argv[1:]
    cap = int(arguments[arguments.index("--limit") + 1]) if "--limit" in arguments else None
    main(Path(arguments[0]), Path(arguments[1]), cap)
```

  Run `C:/Python314/python.exe C:/Users/GustavoPrietodePaula/lender-research/revenue/work/plan/s15/admission_effect.py "C:/Users/GustavoPrietodePaula/OneDrive - Capital Infusion/Desktop/Capital Infusion Projects/bankStatementAnalysis/webapp_data" C:/Users/GustavoPrietodePaula/lender-research/revenue/research/ledger55.json` (about ten minutes; a fabricated one-record file with `--limit 400` was checked on 2026-09-29). The orchestrator sends the owner the gate's VERIFIED lines (Step 3) with these counts and asks: "May these ledger entities be admitted? Each one's debits become counted rows of its group, which guard G7 then accepts as declared." Write the entities the owner signs off, with the date and the owner's words, to `C:/Users/GustavoPrietodePaula/lender-research/revenue/census/g7_allowlist.json` as `{"signed_off": "<date: the owner's words>", "entities": ["<ledger entity name>", ...]}`. A VERIFIED `no_product` record moves no debit (it only clears a processor's bare aliases, which S3.2 measures on credits) and goes through without a sign-off. Everything the owner does not sign off waits; report it as waiting.

- [ ] **Step 7: Admit the VERIFIED, signed-off records.**
  - For each VERIFIED new entity the owner signed off (Step 6): `C:/Python314/python.exe .../s15/research_ledger.py add "<entity>"`; for each such update: `... update "<entity>"`. Never admit an entity missing from `g7_allowlist.json`.
  - Then `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m tools.build_lender_registry --privacy-review` (read every line: no person's name, no digit run), `--check` (0 problems; the `move:` lines are unchanged from before the edit) and `--write`.
  - For each processor whose advance product was added, set its product in `PROCESSOR_ADVANCE_PRODUCTS` (for example `"Shift4": (("SHIFT4",), "<the admitted entity's name>")`); for each VERIFIED `no_product` record, add the processor to `PROCESSORS_WITHOUT_ADVANCE_PRODUCT` with a comment naming the research file and round (`# SmartTab: research ledger55.json r2, no advance product`).
  - For each processor so cleared, add its bare aliases to `OPERATING_REVENUE_SOURCE_ALIASES` and its type to `OPERATING_REVENUE_SOURCE_TYPES`: `"Shift4": ("SHIFT4", "SHIFT4 PAYMENTS", "SHIFT4 PYMT PROC")`; `"SumUp": ("SUMUP",)` with `"merchant_processor"`; `"Braintree": ("BRAINTREE",)` with `"merchant_processor"`; `"Clearent": ("CLEARENT", "CLEARENT LLC", "XPLOR PAY")`; `"SmartTab": ("SMARTTAB", "SMARTTAB PAY")`; `"Jobber Payments": ("JOBBER BY STRI", "JOBBER BY STR", "JOBBER BY STRIPE")` with `"invoice_and_receivables"`. A processor not cleared keeps today's aliases.
  - Run `C:/Python314/python.exe -m tools.operating_registry --check`: 0 problem(s).

- [ ] **Step 8: Run the tests.** `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_registry_additions_55.py tests/test_operating_registry.py -q -p no:cacheprovider` (and `tests/test_revenue_card_settlements.py` once S2.3 has landed: its `test_a_bare_processor_name_waits_for_its_advance_product` reads the same two tables, so a cleared processor names its entity there too), then SEL-REGISTRY. Expected: all pass; SEL-REGISTRY moves only by the admitted entities' rendered aliases. Any other change stops the task.

- [ ] **Step 9: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add docs/lender-registry-ledger.json docs/lender-registry-evidence.md analysis/classification_registry.py tests/test_registry_additions_55.py
git commit -m "registry: ledger admissions of the processors' advance products, Parafin, Pipe's cut and dealer lenders" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

  With no VERIFIED and signed-off record at all, commit only the test file (`git add tests/test_registry_additions_55.py`, subject `tests: the ledger-admission guard of the true-revenue registry`), write `g7_allowlist.json` with `"entities": []`, and report every item as waiting.

---

## S2: Classifier 5.5

### Task S2.1: The credit revenue readers and the street-LN guard

**Files:**
- Create: `tests/test_revenue_text_readers.py`
- Modify: `analysis/description_text.py:9-10, 24`
- Modify: `analysis/transaction_classifier.py:4, 804`

**Depends on:** S1.4.

**Interfaces:**
- Consumes: `normalize_transaction_description`; the classifier's existing `_payee_region`, `_originator_segment`, `_PAYEE_TEMPLATE_PREFIX`, `_is_reference_token`, `_is_payroll_provider_row`, `_ENTITY_NOISE`, `_CHANNEL_VOCABULARY`, `_BANK_TEMPLATE_WORDS`.
- Produces:
  - `HCCLAIMPMT_CLAIM_FIRST = True`, `THIRD_PARTY_BOOK_TRANSFER_AS_WIRE = True`
  - `revenue_text(text: str) -> str`, `_joined_text(text: str) -> str`, `_before_receiver(text: str) -> str`
  - `payer_region(text: str) -> str`, `payer_name(region: str) -> str`, `entry_fields(text: str) -> str`
  - `account_name_text(account_name: str | None) -> str` (cached), `holder_words(account_name) -> tuple[str, ...]`, `holder_named(region: str, account_name: str | None) -> bool`
  - `numbered_company(text: str, region: str | None = None) -> bool`, `company_form(name: str) -> bool`, `is_round_sum(amount: float) -> bool`
  - `channel_gate(text: str) -> str | None` (`'closed'`, `'push'` or None)
  - `REVENUE_GENERIC_WORDS`, `HOLDER_NOISE`, and the patterns `_CONSUMER_P2P_RAIL`, `_PUSH_RAIL`, `_CHECK_DEPOSIT_FORM`, `_CASH_BRANCH_ATM_FORM`, `_TRANSFER_WORDING`, `_ELECTRONIC_PAYMENT_FORM`, `_NUMBERED_COMPANY_REGION`, `_INCOMING_WIRE_LABEL`, `_BOOK_TRANSFER_FROM`, `_FUNDS_TRANSFER_WIRE_LABEL`, `_THIRD_PARTY_ORIGINATOR`
  - `_third_party_originator(text: str) -> str | None`, `_third_party_book_transfer(text: str) -> bool`
  - `_SANTANDER_WIRE` (groups `bank`, `originator`), `_ACH_ORIGINATOR_FIELD`

**Why:** Spec §5.2 (payer region by channel, payer name, entry fields, the holder test, the numbered-company guard, the company form, the round sum), §6.1 step 9b (the channel gate), §7.0 (the revenue text: Chase's glued `Sec` split; the joined originator and entry fields), §7.11 (the street-`LN` guard in the normaliser: `LN` after a street address is a lane, unless a loan-product word or a loan-payment word says loan). It also sets the owner's two switches (§19: OQ5 and OQ6 yes) and the wire and book-transfer labels the readers need. After the review: a transfer-worded ACH row with no FROM sender reads its originator as its payer (C3), Santander's wire reads its originator after the account number, not its sending bank (I5), and `DEPOT MARCHAND` and `DEPOT DIRECT` are not branch deposits (M3). Every later rule reads these; nothing decides with them yet, except the normaliser, whose change the census lists (G7b).

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_revenue_text_readers.py`:

```python
"""Classification 5.5 (true revenue spec §5.2, §6.1 step 9b, §7.0, §7.11): the credit revenue readers. Fabricated rows
only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis.description_text import normalize_transaction_description as normalize
from analysis.transaction_classifier import (
    _joined_text,
    channel_gate,
    company_form,
    entry_fields,
    holder_named,
    holder_words,
    is_round_sum,
    numbered_company,
    payer_name,
    payer_region,
    revenue_text,
)


def _text(printed: str) -> str:
    return revenue_text(normalize(printed))


def test_revenue_text_splits_chase_glued_sec_code_inside_the_entry_field_only():
    glued = normalize("Orig CO Name:Fabrikam Health Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Hcclaimpmtsec:CCD")
    assert revenue_text(glued).endswith("CO ENTRY DESCR HCCLAIMPMT SEC CCD")
    two_words = normalize("Orig CO Name:Fabrikam Orig ID:1 Desc Date: CO Entry Descr:Vhcl Purchsec:CCD Trace#:1")
    assert "CO ENTRY DESCR VHCL PURCH SEC CCD" in revenue_text(two_words)
    # A word that ends in SEC outside the entry field is untouched.
    assert revenue_text(normalize("FABRIKAM INSEC CCD PAYMENT")) == "FABRIKAM INSEC CCD PAYMENT"


def test_the_joined_text_puts_the_originator_and_the_entry_side_by_side():
    assert _joined_text(normalize("MERCHANT BANKCD DES:DEPOSIT ID:123456")) == "MERCHANT BANKCD DEPOSIT ID 123456"
    chase = _text("Orig CO Name:Merchant Bankcd Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Merch Depsec:CCD")
    assert _joined_text(chase) == "ORIG CO NAME MERCHANT BANKCD MERCH DEP SEC CCD"
    no_date = _text("Orig CO Name:Fabrikam Orig ID:1234567890 Desc Date: CO Entry Descr:Payments Sec:CCD")
    assert _joined_text(no_date) == "ORIG CO NAME FABRIKAM PAYMENTS SEC CCD"


@pytest.mark.parametrize(("printed", "region"), [
    # ACH: template prefixes removed, the receiver fields never read, a leading digit token kept.
    ("FABRIKAM SUPPLY DES:VENDOR PAY ID:123 INDN:CONTOSO BAKERY CO ID:1234567890 CCD", "FABRIKAM SUPPLY"),
    ("7654321 NEW BRUNSWICK INC DES:PAYMENT ID:1", "7654321 NEW BRUNSWICK INC"),
    ("ELECTRONIC DEPOSIT FROM FABRIKAM LLC REF 12345", "FABRIKAM LLC"),
    ("Orig CO Name:Fabrikam Supply Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Payment Sec:CCD",
     "FABRIKAM SUPPLY"),
    # A layout with no entry label: the entry words sit in the region.
    ("FABRIKAM INC DIR DEP 540115 1234567 JOHN SMITH", "FABRIKAM INC DIR DEP"),
    # A wire: the originator after its label, up to the next wire field.
    ("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:20540102 SEQ:1/2 ORIG:FABRIKAM TRADING LLC ID:99 "
     "SND BK:SAMPLE BANK ID:1 PMT DET:INV 1234", "FABRIKAM TRADING LLC"),
    ("FEDWIRE CREDIT VIA: SAMPLE BANK/123 B/O: FABRIKAM TRADING LLC REF: CHASE NYC/CTR/BNF=CONTOSO",
     "FABRIKAM TRADING LLC"),
    # A person-to-person or transfer sender.
    ("ZELLE PAYMENT FROM JOHN SMITH CONF 99", "JOHN SMITH"),
    ("ONLINE TRANSFER FROM SMITH J EVERYDAY CHECKING XXXXXX1234 REF IB0ABCD", "SMITH J EVERYDAY CHECKING"),
    # Check, cash, branch, ATM and bare rows print no payer.
    ("MOBILE DEPOSIT", ""),
    ("COUNTER CREDIT", ""),
    ("DEPOSIT", ""),
])
def test_the_payer_region_is_read_by_channel(printed, region):
    assert payer_region(_text(printed)) == region


def test_the_payer_name_drops_digit_tokens_and_single_letters():
    assert payer_name("7654321 NEW BRUNSWICK INC") == "NEW BRUNSWICK INC"
    assert payer_name("SMITH J EVERYDAY CHECKING") == "SMITH EVERYDAY CHECKING"


@pytest.mark.parametrize(("printed", "entry"), [
    ("FABRIKAM SUPPLY DES:VENDOR PAY ID:123 INDN:CONTOSO BAKERY CO ID:1 CCD", "VENDOR PAY"),
    ("Orig CO Name:Fabrikam Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Hcclaimpmtsec:CCD Trace#:1",
     "HCCLAIMPMT"),
    ("WIRE IN FROM FABRIKAM LLC OBI INVOICE 1234 TRN 99", "INVOICE 1234"),
    ("ZELLE PAYMENT FROM JOHN SMITH MEMO INVOICE PAYMENT CONF 99", "INVOICE PAYMENT"),
])
def test_the_entry_fields(printed, entry):
    assert entry_fields(_text(printed)) == entry


def test_the_holder_words_drop_noise_digits_and_short_words():
    assert holder_words("CONTOSO BAKERY LLC") == ("CONTOSO", "BAKERY")
    assert holder_words("BUSINESS ADVANTAGE FUNDAMENTALS") == ()
    assert holder_words(None) == ()


@pytest.mark.parametrize(("region", "holder", "matches"), [
    ("CONTOSO HOLDINGS LLC", "CONTOSO BAKERY LLC", True),       # the brand-word affiliate
    ("CONTOSO BAKERY LLC", "CONTOSO BAKERY LLC", True),         # the holder itself
    ("FABRIKAM PLUMBING SUPPLY", "SAMPLE PLUMBING LLC", False),  # a supplier sharing a trade word
    ("FIRST FABRIKAM LLC", "FIRST CONTOSO LLC", False),         # a common name-starter is never distinctive
    ("1234567 ONTARIO INC", "1234567 ONTARIO INC", True),       # a numbered company's own number
    ("FABRIKAM LLC", "BUSINESS CHECKING", False),               # a product name holds no holder word
    ("", "CONTOSO BAKERY LLC", False),                          # no payer region, no test
])
def test_the_holder_test(region, holder, matches):
    assert holder_named(region, holder) is matches


@pytest.mark.parametrize(("printed", "numbered"), [
    ("DIRECT DEPOSIT 7654321 CANA AP CC", True),
    ("DIRECT DEPOSIT 1234567", True),
    ("1234567 NOVA SCOTIA LTD DES:VENDOR PAY ID:1", True),
    ("7654321 NEW BRUNSWICK INC DES:PAYMENT ID:1", True),
    ("1234567 ONTA DES:PAYMENT ID:1", True),
    ("1234567 ONTARIOS DES:PAYMENT ID:1", False),
    ("FABRIKAM SUPPLY DES:VENDOR PAY ID:1234567", False),
])
def test_the_numbered_company_guard(printed, numbered):
    assert numbered_company(_text(printed)) is numbered


@pytest.mark.parametrize(("name", "form"), [
    ("FABRIKAM SUPPLY LLC", True), ("FABRIKAM SUPPLY L L C", True), ("SAMPLE UNIVERSITY", True),
    ("FABRIKAM SUPPLY CO", False), ("FABRIKAM FAMILY TRUST", False), ("LLC FABRIKAM", False), ("JOHN SMITH", False),
])
def test_the_company_form(name, form):
    assert company_form(name) is form


def test_a_round_sum_is_a_whole_hundred_of_at_least_one_hundred():
    assert is_round_sum(500.0) and is_round_sum(100.0)
    assert not is_round_sum(50.0) and not is_round_sum(150.0) and not is_round_sum(500.01)


@pytest.mark.parametrize(("printed", "gate"), [
    ("ZELLE PAYMENT FROM FABRIKAM LLC CONF 99", "closed"),
    ("INTERAC E-TRANSFER FROM JOHN SMITH", "closed"),
    ("MOBILE DEPOSIT CUSTOMER PAYMENT REF 1234", "closed"),
    ("CUSTOMER DEPOSIT", "closed"),
    ("BRANCH DEPOSIT", "closed"),
    ("DEPOSIT", "closed"),
    ("RTP CREDIT FROM FABRIKAM LLC INV 1234", "push"),
    ("VISA DIRECT FABRIKAM PAYOUT", "push"),
    ("FABRIKAM SUPPLY DES:VENDOR PAY ID:1", None),
    ("01/02Bankcard Deposit 123456", None),       # a glued date keeps the card word a payer word
    ("WIRE IN DATE 540102 TRN 123", None),        # a wire is tiered, never gated
])
def test_the_channel_gate(printed, gate):
    assert channel_gate(_text(printed)) == gate


@pytest.mark.parametrize(("printed", "region"), [
    ("CONTOSO BAKERY LLC DES:TRANSFER ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD", "CONTOSO BAKERY LLC"),
    ("NORTHWIND BAKERY DES:XFER ID:1", "NORTHWIND BAKERY"),
    ("ORIG CO NAME:CONTOSO BAKERY LLC ORIG ID:1 DESC DATE: CO ENTRY DESCR:TRANSFER SEC:CCD", "CONTOSO BAKERY LLC"),
    ("ONLINE TRANSFER FROM JOHN SMITH CONF 1", "JOHN SMITH"),
    ("VENMO DES:CASHOUT ID:1", ""),
])
def test_a_transfer_worded_ach_row_with_no_sender_reads_its_originator(printed, region):
    # Review C3: with no FROM sender, the ACH originator is the payer, so the holder test and the counter-debit
    # hold read it; a consumer rail's cash-out still prints no sender.
    assert payer_region(_text(printed)) == region


def test_santander_prints_its_sending_bank_before_the_originator():
    # §5.2, §7.9: 'USD WIRE IN FROM <sending bank> ACCT <n> <originator> REF <purpose>' (review I5's own account).
    printed = "USD WIRE IN FROM SAMPLE BANK EUROPE ACCT * 1234 CONTOSO GROUP SP REF PO 4521"
    assert payer_region(_text(printed)) == "CONTOSO GROUP SP"


@pytest.mark.parametrize(("printed", "gate"), [
    ("DEPOT MARCHAND GLOBAL PAIEMENTS 1234567", None),
    ("DEPOT DIRECT FABRIKAM INC", None),
    ("DEPOT 1234 SUCCURSALE", "closed"),
])
def test_a_merchant_or_direct_deposit_depot_is_no_branch_deposit(printed, gate):
    # Review M3: §7.1's DEPOT MARCHAND form and a direct deposit are electronic.
    assert channel_gate(_text(printed)) == gate


@pytest.mark.parametrize(("printed", "normalized"), [
    ("WIRE FROM 12 OAK LN CITY", "WIRE FROM 12 OAK LN CITY"),
    ("ATM DEPOSIT 450 NORTH PINE HILL LN", "ATM DEPOSIT 450 NORTH PINE HILL LN"),
    ("TRUIST LN PYMT", "TRUIST LOAN PYMT"),
    ("1234 COMMERCIAL LN PMT", "1234 COMMERCIAL LOAN PMT"),
    ("000123 AUTO LN DISB", "000123 AUTO LOAN DISB"),
    ("12 OAK LN PAYMENT", "12 OAK LOAN PAYMENT"),
])
def test_a_street_ln_is_a_lane_and_every_other_ln_a_loan(printed, normalized):
    assert normalize(printed) == normalized
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_revenue_text_readers.py -q -p no:cacheprovider`

Expected: FAIL: `1 error`, the first with `ImportError: cannot import name '_joined_text' from 'analysis.transaction_classifier'`.

- [ ] **Step 3: Implement.**

In `analysis/description_text.py` (lines 9-10), replace:

```python
import re
import unicodedata

```

with:

```python
import re
import unicodedata

#: 5.5 (true revenue spec §7.11): a street address ends in LN: a token of digits, then one to three alphabetic
#: tokens, then LN ('12 OAK LN'). Such an LN is a lane, never a loan, unless a loan-product word sits among those
#: tokens or LN is followed by a loan-payment word ('1234 COMMERCIAL LN PMT', '000123 AUTO LN DISB' read LOAN).
_STREET_BEFORE_LN = re.compile(r"(?:^| )\d+((?: [A-Z]+){1,3}) $")
_LOAN_PRODUCT_WORDS = frozenset({
    "COMMERCIAL", "COMM", "AUTO", "BUSINESS", "BUS", "TERM", "PERSONAL", "MORTGAGE", "MTG", "EQUIPMENT", "EQUIP",
    "INSTALLMENT", "INSTL", "CONSUMER", "HOME", "HELOC", "STUDENT", "VEHICLE", "SBA", "BRIDGE", "CONSTRUCTION", "LINE",
})
_LOAN_WORD_AFTER_LN = re.compile(r" (?:PMT|PYMT|PAYMENT|DISB|DISBURSEMENT|ADV|ADVANCE|PROCEEDS|DRAW)\b")
_LN_WORD = re.compile(r"\bLN\b")


def _loan_or_lane(match: re.Match[str]) -> str:
    """LN reads LOAN, except where it ends a street address (5.5, §7.11)."""
    text = match.string
    street = _STREET_BEFORE_LN.search(text[: match.start()])
    if (
        street is not None
        and not _LOAN_WORD_AFTER_LN.match(text[match.end():])
        and not set(street.group(1).split()) & _LOAN_PRODUCT_WORDS
    ):
        return "LN"
    return "LOAN"

```

In `analysis/description_text.py` (line 24), replace:

```python
    normalized = re.sub(r"\bLN\b", "LOAN", normalized)
```

with:

```python
    normalized = _LN_WORD.sub(_loan_or_lane, normalized)
```

In `analysis/transaction_classifier.py` (line 4), replace:

```python
from dataclasses import dataclass, replace
```

with:

```python
from dataclasses import dataclass, replace
from functools import cache
```

In `analysis/transaction_classifier.py`, after these lines (line 804):

```python
    return _matches_any(
        normalize_transaction_description(description),
        _INTERNAL_TRANSFER_CREDIT_PATTERNS,
    )
```

insert:

```python
# ---------------------------------------------------------------------------------------------------------------------
# Classification 5.5 (docs/superpowers/specs/2026-09-28-true-revenue-design.md §5.2, §6.1, §7): the credit revenue
# readers. Every credit revenue rule reads revenue_text(text); D11, normalized_description and every debit rule keep
# the normalized row as it is.
# ---------------------------------------------------------------------------------------------------------------------

#: T18 (owner, 2026-09-28: yes; OQ5): a credit that prints the NACHA claim-payment entry skips the insurer registry, so
#: an insurer's healthcare claim payment to a provider verifies. Off, it is held with the insurer's other credits.
HCCLAIMPMT_CLAIM_FIRST = True
#: T19 (owner, 2026-09-28: yes; OQ6): Chase's BOOK TRANSFER CREDIT B/O <originator> from someone other than the holder,
#: and Bank of America's WIRE TYPE BOOK IN, are incoming wires, not own-account transfers.
THIRD_PARTY_BOOK_TRANSFER_AS_WIRE = True

#: §7.0: Chase glues the SEC code to the entry description ('CO ENTRY DESCR HCCLAIMPMTSEC CCD'). Bounded to the
#: entry-description field, so a word elsewhere that ends in SEC is untouched.
_GLUED_SEC_CODE = re.compile(
    r"(\bCO (?:ENTRY )?DESCR (?:\S+ ){0,2}?\S{2,}?)SEC (CCD|CTX|PPD|WEB|IAT|COR|TEL|POP|BOC|ARC|RCK|CIE)\b"
)
#: §7.0: the fields between Chase's originator and its entry description, and Bank of America's DES label.
_CHASE_FIELDS_BETWEEN = re.compile(r" ORIG ID \S+ DESC DATE(?: \S+)? CO (?:ENTRY )?DESCR ")
_BOFA_DES_FIELD = re.compile(r" DES ")
#: §5.2: the receiver fields, where the bank prints the account holder (PNC labels its RECEIVER NAME).
_CREDIT_RECEIVER_FIELD = re.compile(r"\b(?:INDN|IND NAME|IND ID|RECEIVER NAME)\b")
#: §5.2: the bank's words printed before the payer, removed before the payer is read (with _PAYEE_TEMPLATE_PREFIX).
_REVENUE_TEMPLATE_PREFIX = re.compile(
    r"^(?:BUSINESS TO BUSINESS ACH CREDIT|CCD DEPOSIT|CTX DEPOSIT|ELECTRONIC DEPOSIT FROM|ELECTRONIC DEPOSIT"
    r"|ELECTRONIC CREDIT|ACH CORP CREDIT|ACH DEPOSIT|ACH CREDIT|DEPOSIT FROM|PREAUTHORIZED CREDIT|EFT CREDIT"
    r"|DIRECT DEPOSIT|MISC PAYMENT|BILL PAYMENT)\b ?"
)
#: §5.2: a wire's originator starts after one of these labels (never ORIG CO NAME, ORIG ID or ORIG TO BNF).
_WIRE_ORIGINATOR_LABEL = re.compile(
    r"\b(?:B O|ORIGINATOR(?: NAME)?|ORIG(?! CO NAME\b)(?! ID\b)(?! TO BNF\b)|ORG|WIRE IN FROM|WIRE FROM"
    r"|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER RECEIVED)\b ?"
)
#: §5.2: ... and ends at the next wire field. ID is read as a field too: Bank of America prints 'ORIG:<name> ID:<n>'.
_WIRE_FIELD_END = re.compile(r"\b(?:BNF|NBNF|BENEFICIARY|BBI|OBI|REF|SRF|TRN|RFB|IMAD|ACCT|SND BK|ID)\b")
#: §5.2, §7.9 (Santander's layout): 'USD WIRE IN FROM <sending bank> ACCT <n> <originator> REF <purpose>'. The words
#: after WIRE IN FROM name the sending bank; the originator follows the account number (the field §7.9 cuts at 16).
_SANTANDER_WIRE = re.compile(r"^(?:[A-Z]{3} )?WIRE IN FROM\b(?P<bank>.*?)\bACCT \d+ (?P<originator>.*?)(?=\bREF\b|$)")
#: §5.2: a person-to-person or transfer sender follows FROM and ends at one of these words.
_SENDER_END = re.compile(r"\b(?:ON|REF|CONF|MEMO|TRN|ID|FOR|NOTE|PMT INFO|PAYMENT INFO)\b")
#: §5.2: the entry fields: Bank of America's DES, Chase's CO ENTRY DESCR, a wire's purpose fields, a transfer's memo.
_BOFA_ENTRY_FIELD = re.compile(
    r"\bDES (.*?)(?=\b(?:ID|INDN|CO ID|IND NAME|IND ID|CCD|CTX|PPD|WEB|IAT|TEL|POP|BOC|ARC|RCK|CIE)\b|$)"
)
_CHASE_ENTRY_FIELD = re.compile(
    r"\bCO (?:ENTRY )?DESCR (.*?)(?=\b(?:SEC|TRACE|EED|IND ID|IND NAME|TRN|CCD|CTX|PPD|WEB|IAT)\b|$)"
)
_WIRE_ENTRY_FIELD = re.compile(
    r"\b(?:OBI|RMR|PMT DET|RFB|REF)\b (.*?)(?=\b(?:BNF|NBNF|BBI|OBI|SRF|TRN|IMAD|ACCT|SND BK|RFB|ORIG|B O|ORG)\b|$)"
)
_MEMO_ENTRY_FIELD = re.compile(r"\b(?:MEMO|NOTE|FOR|PMT INFO|PAYMENT INFO)\b (.*?)(?=\b(?:CONF|REF|TRN|ID)\b|$)")

#: §5.2: the generic words of the definition memo's categorize.py, inlined (that file is private).
REVENUE_GENERIC_WORDS: frozenset[str] = frozenset("""
DEPOSIT DEPOSITS CREDIT CREDITS TRNSFR TRANSFER OTHER REAL TIME INCOMING RECEIVED ACH ELECTRONIC DIRECT MEMO MISC BILL
FILE INTERNET BANKING EXTERNAL RECD CR DEP ONLINE MOBILE INSTANT FUNDS ADJUSTMENT ADJ MONEY VISA CORPORATE PREAUTHORIZED
SEQ IN NEW ITEM ITEMS MSP DIV DP FD BR BRANCH RECEIPT RECEIVE PAYMENT DOMESTIC TRANS CUSTOMER DDA SAV SAVINGS CHECKING
CHK ACCOUNT ACCT FR FROM WIRE REF TRN TYPE DATE ET USD TRF WT FED NUMBER NO NOTPROVIDED INTERNATIONAL FX CAD SWIFT IMAD
OMAD SRF RFB OBI PM AM ON AT VIA CARD ID CONF CONFIRMATION TRACE SENT RCVD PMNT PMT AUTHORIZED SEQUENCE
""".split())
#: §5.2: the holder-name noise of the same file, plus the bank-template and product words, the remaining province and
#: territory names and every generic word.
HOLDER_NOISE: frozenset[str] = frozenset("""
BUSINESS CHECKING ACCOUNT LLC INC CORP COMPANY THE OF AND SAVINGS PLATINUM COMPLETE ANALYZED COMMERCIAL ADVANTAGE
FUNDAMENTALS SIMPLE BASIC PREFERRED INTEREST OPERATING PERFORMANCE SELECT ESSENTIALS CHECK TOTAL PREMIUM SMALL STANDARD
FREE DBA USD CAD ACCT PLUS ELITE EVERYDAY BANKING DEPOSIT MONEY MARKET ONTARIO CANADA ALBERTA QUEBEC BRITISH COLUMBIA
SASKATCHEWAN MANITOBA NOVA SCOTIA LTD LIMITED CORPORATION INCORPORATED LLP PLLC GROUP HOLDINGS SERVICES ENTERPRISES USA
AMERICA AMERICAN NATIONAL INTERNATIONAL TRUST SOLUTIONS MANAGEMENT CO LP
COMPTE DIVERS BANK BANQUE CAISSE ENTREPRISE AFFAIRES OPERATIONS CU FCU
BRUNSWICK NEWFOUNDLAND LABRADOR PRINCE EDWARD ISLAND YUKON NORTHWEST TERRITORIES NUNAVUT
""".split()) | REVENUE_GENERIC_WORDS
#: §5.2: common name-starters that are never a holder's or a payer's first distinctive word.
_NAME_STARTERS = frozenset({
    "FIRST", "NORTH", "SOUTH", "EAST", "WEST", "CENTRAL", "UNITED", "GLOBAL", "PREMIER", "ROYAL", "GOLDEN", "GREAT",
    "CITY", "STATE", "COUNTY",
})
#: §5.2: a legal-form word after the payer name's first word, or an institution word. CO is never one (Colorado's
#: state code, D11) and TRUST is never one (a family trust is owner money).
_COMPANY_FORM = re.compile(
    r"^\S+ (?:.* )?(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|COMPANY|LTD|LIMITED|LP|LLP|LLLP|PLLC|ULC|PLC|GMBH|AG"
    r"|SA|SAS|SRL|BV|NV|PTY|DOO|DMCC|SA DE CV)\b"
    r"|\b(?:FOUNDATION|CHURCH|MINISTRIES|UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|HOSPITAL|ASSOCIATION|SOCIETY|COOPERATIVE"
    r"|CO OP)\b"
)
#: §5.2: an ACH or EFT mark: the row is an electronic payment.
_ELECTRONIC_PAYMENT_FORM = re.compile(
    r"\b(?:ORIG CO NAME|CO ENTRY DESCR|DES|CCD|CTX|PPD|IAT|ACH|EFT|ELECTRONIC DEPOSIT|ELECTRONIC CREDIT|ELECTRONIC PMT"
    r"|ELECTRONIC PAYMENT|DIRECT DEPOSIT|MISC PAYMENT|CORPORATE ACH|BILL PAYMENT|EDI|INDN|PREAUTHORIZED CREDIT"
    r"|DEPOSIT FROM|PAID FROM|PAYMENT FROM|CREDIT FROM|MSP DIV|AP CC)\b"
)
#: §5.2, T11: the provinces and territories and CANADA, whole or cut to three or more leading letters, and their
#: postal and common abbreviations.
_PROVINCE_NAMES = (
    "ONTARIO", "QUEBEC", "NOVA SCOTIA", "NEW BRUNSWICK", "MANITOBA", "BRITISH COLUMBIA", "PRINCE EDWARD ISLAND",
    "SASKATCHEWAN", "ALBERTA", "NEWFOUNDLAND AND LABRADOR", "YUKON", "NORTHWEST TERRITORIES", "NUNAVUT", "CANADA",
)
_PROVINCE_ABBREVIATIONS = (
    "ON", "ONT", "QC", "QUE", "NS", "NB", "MB", "MAN", "BC", "B C", "PE", "PEI", "SK", "SASK", "AB", "ALB", "ALTA",
    "NL", "NFLD", "YT", "NT", "NWT", "NU", "CAN",
)
_PROVINCE = "(?:" + "|".join(sorted(
    {name[:length].rstrip() for name in _PROVINCE_NAMES for length in range(3, len(name) + 1)}
    | set(_PROVINCE_ABBREVIATIONS),
    key=lambda value: (-len(value), value),
)) + ")"
#: §5.2, T11: a numbered company. The template form is read on the row before the receiver fields (BMO cuts the name
#: to the field, so the digits alone decide); the payer-region form keeps the region's leading digit token.
_NUMBERED_COMPANY_TEMPLATE = re.compile(
    r"^(?:DIRECT DEPOSIT|ACC(?:OUN)?TS? PAYABLE(?: PMT)?|MISC PAYMENT|BILL PAYMENT) \d{6,}\b"
)
_NUMBERED_COMPANY_REGION = re.compile(
    rf"^\d{{6,}}\b(?: {_PROVINCE}\b| (?:[A-Z]+ ){{0,4}}(?:INC|INCORPORATED|LTD|LIMITED|CORP|CORPORATION|ULC|LLC|LP|CO"
    rf"|COMPANY)\b)"
)
#: §6.1 step 9b: consumer person-to-person rails (never verified by any step), and real-time or push rails (verified
#: by the operating registry only).
_CONSUMER_P2P_RAIL = re.compile(
    r"\b(?:ZELLE|INTERAC|E ?TRANSFER|ETRANSFER|E ?TFR|VIREMENT|VFC|AUTODEPOSIT|VENMO|CASH ?APP|SQUARE CASH|APPLE CASH"
    r"|POPMONEY)\b"
)
_PUSH_RAIL = re.compile(
    r"\b(?:RTP|FEDNOW|REAL TIME (?:TRANSFER|PAYMENT)|INSTANT (?:PMT|PAYMENT|TRANSFER)|VISA DIRECT"
    r"|VISA MONEY TRANSFER|MC SEND|MONEY TRANSFER|PMNT RCVD|PAYMENT RECEIVED)\b"
)
#: §8.3: check deposits (Q3: counted, never verified).
_CHECK_DEPOSIT_FORM = re.compile(
    r"\bMOBILE (?:CHECK |CHEQUE )?(?:DEPOSIT|DEP)\b|\bMOBILE CHE(?:CK|QUE)\b|\bMB DEP\b|\bBKOFAMERICA MOBILE\b"
    r"|\bREMOTE (?:ONLINE )?(?:DEPOSIT|CAPTURE)\b|\bDEPOSIT CAPTURE\b|\bMERCHANT CAPTURE\b"
    r"|\bDESKTOP (?:REMOTE )?DEPOSIT\b|\bEDEPOSIT SCAN\b|\bE ?CHEQUE DEPOSIT\b"
    r"|\b(?:ATM )?CHE(?:CK|QUE)S? (?:DEPOSIT|DEP|RECEIVED)\b|\bMAIL DEPOSIT\b|^REMOTE$|\bIMAGED DEPOSIT\b"
    r"|\bDEPOSITED (?:CHECK|ITEM)\b|\bRDC\b|\bSCAN(?:NED)? DEPOSIT\b|\bLOCKBOX\b|\bLBX DEP\b"
)
#: §8.2: cash, branch and teller, and ATM deposits (Q2: counted, never verified), read only on a row that prints no
#: electronic-payment form and no person-to-person rail.
_CASH_BRANCH_ATM_FORM = re.compile(
    r"\bCASH DEP(?:OSIT)?\b|\bATM CASH\b|\bCPS DEVICE\b|\bCURRENCY PROCESSING\b|\bSMART ?SAFE\b|\bCOIN\b|\bCASH IN\b"
    r"|\bCOUNTER (?:CREDIT|DEPOSIT)\b|\bTELLER\b|\bIN BRANCH\b|\bBRANCH\b|\bBRCH\b|\bDEPOSIT AT BR\b"
    r"|\bDEPOSIT THANK YOU\b|\bMAIN OFFICE\b|\bPRE ?ENCODED\b|\bNIGHT (?:DEP|DROP)\b|\bBANKING CENTRE\b"
    # DEPOT MARCHAND (a card settlement, §7.1) and DEPOT DIRECT (a direct deposit) are electronic, never a branch.
    r"|^GC\b.*\bDEPOSIT\b|\bG DEPOT\b|\bDEPOT\b(?! MARCHAND\b| DIRECT\b)|\bDEPOSIT IBB\b|\bVAULT DEP\w*|\bSTORE DEPOSIT\b"
    r"|\bDEPOSIT MADE IN\b"
    r"|\bATM\b.*\bDEP(?:OSIT)?\b|\bDEP(?:OSIT)?\b.*\bATM\b|\bABM\b"
)
#: §8.2: transfer wording.
_TRANSFER_WORDING = re.compile(
    r"\b(?:TRANSFER|TRNSFR|XFER|TFR|BR TO BR|ONLINE BANKING|INTERNET (?:BANKING|TRANSFER)|FUNDS TRANSFER)\b"
)
#: §5.2: the ACH originator and entry fields (Bank of America's DES, Chase's ORIG CO NAME and CO ENTRY DESCR).
_ACH_ORIGINATOR_FIELD = re.compile(r"\b(?:DES|CO ENTRY DESCR|ORIG CO NAME)\b")


def revenue_text(text: str) -> str:
    """5.5 (§7.0): the text every credit revenue rule reads: the normalized row with Chase's glued SEC code split
    ('CO ENTRY DESCR HCCLAIMPMTSEC CCD' becomes 'CO ENTRY DESCR HCCLAIMPMT SEC CCD')."""
    return _GLUED_SEC_CODE.sub(r"\1 SEC \2", text)


def _joined_text(text: str) -> str:
    """5.5 (§7.0): the originator and the entry description side by side: Bank of America's ' DES ' and Chase's
    'ORIG ID <id> DESC DATE [<date>] CO ENTRY DESCR' removed between them."""
    return _BOFA_DES_FIELD.sub(" ", _CHASE_FIELDS_BETWEEN.sub(" ", text, count=1), count=1)


def _before_receiver(text: str) -> str:
    """5.5 (§5.2): the row up to its first receiver field (INDN, IND NAME, IND ID, RECEIVER NAME)."""
    return _CREDIT_RECEIVER_FIELD.split(text, 1)[0].rstrip()


def _strip_revenue_template(row: str) -> str:
    """5.5 (§5.2): the row with the bank's template words before the payer removed."""
    for _ in range(3):
        stripped = _PAYEE_TEMPLATE_PREFIX.sub("", row, count=1).lstrip()
        stripped = _REVENUE_TEMPLATE_PREFIX.sub("", stripped, count=1).lstrip()
        if stripped == row:
            break
        row = stripped
    return row


def _leading_name_words(region: str) -> str:
    """The region's words up to the first reference token after a name word; leading reference tokens are kept, so a
    numbered company keeps its number (§5.2)."""
    words: list[str] = []
    started = False
    for token in region.split():
        if _is_reference_token(token):
            if started:
                break
        else:
            started = True
        words.append(token)
    return " ".join(words)


def _is_wire_row(text: str) -> bool:
    """5.5 (§7.9 N1, §8.5): the row begins with an incoming-wire label, or (T19) is a third-party book transfer."""
    return _INCOMING_WIRE_LABEL.match(text) is not None or _third_party_book_transfer(text)


def _is_transfer_or_p2p_row(text: str) -> bool:
    """5.5 (§8.4): a person-to-person rail, or transfer wording, on a row that is no wire."""
    row = _before_receiver(text)
    return _CONSUMER_P2P_RAIL.search(row) is not None or _PUSH_RAIL.search(row) is not None or (
        _TRANSFER_WORDING.search(row) is not None
    )


def _wire_payer_region(text: str) -> str:
    """5.5 (§5.2): a wire's originator, after its label, up to the next wire field; on Santander's layout, the words
    after the account number (the words after WIRE IN FROM are the sending bank)."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        return _leading_name_words(santander.group("originator").strip())
    found = _WIRE_ORIGINATOR_LABEL.search(text)
    if found is None:
        return ""
    rest = text[found.end():]
    end = _WIRE_FIELD_END.search(rest)
    return _leading_name_words(rest[: end.start()] if end is not None else rest)


def _sender_payer_region(text: str) -> str:
    """5.5 (§5.2): a person-to-person or transfer sender: the words after FROM, up to ON, REF, CONF, MEMO, TRN, ID,
    FOR or a reference token. Venmo and Cash App cash-outs print no sender."""
    row = _before_receiver(text)
    found = re.search(r"\bFROM\b ?", row)
    if found is None:
        return ""
    rest = row[found.end():]
    end = _SENDER_END.search(rest)
    return _leading_name_words(rest[: end.start()] if end is not None else rest)


def _ach_payer_region(text: str) -> str:
    """5.5 (§5.2): an ACH or EFT payer: the row before its receiver fields, template prefixes removed, originator
    labels removed, cut at the first ACH field, up to the first reference token after a name word."""
    return _leading_name_words(_payee_region(_strip_revenue_template(_before_receiver(text))))


def _prints_no_payer(text: str) -> bool:
    """5.5 (§5.2, §6.1 step 9b): a check, cash, branch, ATM or bare row: a channel that prints no payer."""
    row = _before_receiver(text)
    if _CHECK_DEPOSIT_FORM.search(row):
        return True
    if (
        not _ELECTRONIC_PAYMENT_FORM.search(row)
        and not _CONSUMER_P2P_RAIL.search(row)
        and _CASH_BRANCH_ATM_FORM.search(row)
    ):
        return True
    return _is_bare_row(text)


def _is_bare_row(text: str) -> bool:
    """5.5 (§8.2): a bare deposit, credit or EFT: once the template prefixes, the generic words, the reference tokens
    and single letters are removed, no payer word remains, and the row prints no transfer wording."""
    row = _before_receiver(text)
    if _TRANSFER_WORDING.search(row):
        return False
    return not any(_is_payer_word(token) for token in _strip_revenue_template(row).split())


def _is_payer_word(token: str) -> bool:
    """5.5 (§8.2): a token that may name a payer: not a generic word, a single letter, a masked number or a month.
    A token that holds digits names one only through three or more letters glued to them ('02BANKCARD' after a
    glued date, 'MRCH22064280019')."""
    if token in REVENUE_GENERIC_WORDS or len(token) < 2 or _MASKED_TOKEN.fullmatch(token) or token in _ENTITY_MONTHS:
        return False
    if not any(ch.isdigit() for ch in token):
        return True
    letters = "".join(ch for ch in token if ch.isalpha())
    return len(letters) >= 3 and letters not in REVENUE_GENERIC_WORDS


def payer_region(text: str) -> str:
    """5.5 (§5.2): the payer region of a credit's revenue text, read by its channel: a wire's originator, a
    person-to-person or transfer sender, an ACH or EFT payer, or nothing on a check, cash, branch, ATM or bare row.
    Read before any token is filtered, so a numbered company's leading digits and a legal word are kept."""
    if _is_wire_row(text):
        return _wire_payer_region(text)
    if _is_transfer_or_p2p_row(text):
        sender = _sender_payer_region(text)
        row = _before_receiver(text)
        # A transfer-worded row that prints an ACH originator field and no FROM sender names its payer the ACH way
        # ('CONTOSO BAKERY LLC DES:TRANSFER'), so the holder test and the counter-debit hold read it.
        if (
            not sender
            and _ACH_ORIGINATOR_FIELD.search(row)
            and not _CONSUMER_P2P_RAIL.search(row)
            and not _PUSH_RAIL.search(row)
        ):
            return _ach_payer_region(text)
        return sender
    if _prints_no_payer(text):
        return ""
    return _ach_payer_region(text)


def payer_name(region: str) -> str:
    """5.5 (§5.2): the payer region's words without the tokens that hold a digit and the single letters."""
    return " ".join(
        token for token in region.split() if not any(ch.isdigit() for ch in token) and len(token) > 1
    )


def entry_fields(text: str) -> str:
    """5.5 (§5.2): the words the payer prints about the payment: Bank of America's DES field, Chase's CO ENTRY DESCR
    field, a wire's OBI, RMR, PMT DET, RFB and REF text, a transfer's memo. Empty when the layout has none (its entry
    words sit inside the payer region, which the holds read too)."""
    row = _before_receiver(text)
    fields = []
    for pattern in (_BOFA_ENTRY_FIELD, _CHASE_ENTRY_FIELD):
        found = pattern.search(row)
        if found is not None:
            fields.append(found.group(1).strip())
    if _is_wire_row(text):
        fields.extend(found.group(1).strip() for found in _WIRE_ENTRY_FIELD.finditer(text))
    elif _is_transfer_or_p2p_row(text):
        fields.extend(found.group(1).strip() for found in _MEMO_ENTRY_FIELD.finditer(row))
    return " ".join(field for field in fields if field)


def _distinctive_words(words: Sequence[str]) -> list[str]:
    """5.5 (§5.2): the words that may name a holder or a payer: no noise word, no digit, three letters or more."""
    return [
        word for word in words
        if word not in HOLDER_NOISE and not any(ch.isdigit() for ch in word) and len(word) > 2
    ]


def _first_distinctive_word(words: Sequence[str]) -> str | None:
    """5.5 (§5.2): the first word of four or more letters that is not a common name-starter."""
    return next((word for word in words if len(word) >= 4 and word not in _NAME_STARTERS), None)


@cache
def account_name_text(account_name: str | None) -> str:
    """5.5: the statement's account name, normalized once per name ('' when none is printed), so the holder test
    never re-normalizes it row by row."""
    return normalize_transaction_description(account_name) if account_name else ""


def holder_words(account_name: str | None) -> tuple[str, ...]:
    """5.5 (§5.2): the statement's account name, normalized, without holder noise, digit tokens and short tokens.
    Often empty: account_name is frequently only a product name."""
    return tuple(_distinctive_words(account_name_text(account_name).split()))


def holder_named(region: str, account_name: str | None) -> bool:
    """5.5 (§5.2): the holder test, read on a payer region (never on a check, cash, branch, ATM or bare row, which has
    none). It matches when the payer's first distinctive word is the holder's, when the payer name holds
    min(2, number of holder words) holder words, or when the region prints a run of four or more digits that the
    account name also prints."""
    if not region or not account_name:
        return False
    holder = holder_words(account_name)
    payer = _distinctive_words(payer_name(region).split())
    if holder:
        holder_first = _first_distinctive_word(holder)
        if holder_first is not None and _first_distinctive_word(payer) == holder_first:
            return True
        shared = sum(1 for word in dict.fromkeys(payer) if word in holder)
        if shared >= min(2, len(holder)):
            return True
    printed = account_name_text(account_name)
    return any(
        re.search(rf"(?<!\d){run}(?!\d)", printed) for run in re.findall(r"\d{4,}", region)
    )


def numbered_company(text: str, region: str | None = None) -> bool:
    """5.5 (§5.2, T11): the payer is a Canadian numbered company: a template prefix followed by six or more digits,
    or a payer region that begins with six or more digits and then a province, territory, CANADA or a cut of one, or
    up to four words and a legal form."""
    if _NUMBERED_COMPANY_TEMPLATE.search(_before_receiver(text)):
        return True
    region = payer_region(text) if region is None else region
    return _NUMBERED_COMPANY_REGION.search(region) is not None


def company_form(name: str) -> bool:
    """5.5 (§5.2): a legal-form word after the payer name's first word, or an institution word."""
    return _COMPANY_FORM.search(name) is not None


def is_round_sum(amount: float) -> bool:
    """5.6 (§5.2): at least $100 and a whole multiple of $100, compared in integer cents."""
    cents = round(abs(amount) * 100)
    return cents >= _ROUND_SUM_DOLLARS * 100 and cents % (_ROUND_SUM_DOLLARS * 100) == 0


#: §8.10: the round sum's step, in whole dollars.
_ROUND_SUM_DOLLARS = 100


def channel_gate(text: str) -> str | None:
    """5.5 (§6.1 step 9b), read on a credit's revenue text: 'closed' when a consumer person-to-person rail, a
    check-deposit form, a cash, branch or ATM form, or no payer word at all is printed (no step verifies it);
    'push' for a real-time or push rail (only the operating registry may verify it); None otherwise."""
    row = _before_receiver(text)
    if _CONSUMER_P2P_RAIL.search(row):
        return "closed"
    if _prints_no_payer(text) and not _is_wire_row(text):
        return "closed"
    if _PUSH_RAIL.search(row):
        return "push"
    return None

#: §7.9 N1 and §7.11 (T19): the labels a reader needs to tell an incoming wire, and the originator a book or
#: funds transfer prints after B O, CUSTOMER, ORIGINATOR, ORG, TT, FROM or WIRE FROM.
_THIRD_PARTY_ORIGINATOR = re.compile(r"\b(?:B O|CUSTOMER|ORIGINATOR|ORG|TT|FROM|WIRE FROM)\b ?")
#: §7.9 N1 and §7.11: the incoming-wire labels a row begins with.
_INCOMING_WIRE_LABEL = re.compile(
    r"^(?:WIRE TYPE (?:WIRE|INTL|FX) IN\b|USD WIRE IN\b|[A-Z]{3} WIRE IN\b|FEDWIRE CREDIT\b|CHIPS CREDIT\b|WT FED"
    r"|WIRE TSF\b|WIRE TRANSFER (?:DEPOSIT|CREDIT|IN|INCOMING|FROM)\b|INCOMING WIRE\b|WIRE IN\b|WIRE FROM\b"
    r"|(?:DOMESTIC|INTL|INTERNATIONAL|FOREIGN) (?:INCOMING )?WIRE\b|INCOMING FUNDS TRANSFER\b"
    r"|FUNDS TRANSFER CREDIT TT\b|INBD FUNDS TRANSFER\b|FUNDS TRANSFER WIRE FROM\b)"
)
_BOOK_TRANSFER_FROM = re.compile(r"^(?:BOOK TRANSFER CREDIT B O|WIRE TYPE BOOK IN\b.*\bORIG)\b ?")
#: §7.11: the funds-transfer labels of an incoming wire (the label stands for FROM).
_FUNDS_TRANSFER_WIRE_LABEL = re.compile(
    r"\b(?:INCOMING FUNDS TRANSFER|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER(?: RECEIVED)?|FUNDS TRANSFER WIRE FROM)"
    r"\b ?"
)


def _third_party_originator(text: str) -> str | None:
    """5.5 (§7.11): the originator a book or funds transfer prints (after B O, CUSTOMER, ORIGINATOR, ORG, TT, FROM or
    WIRE FROM, or one of the four funds-transfer wire labels), when it holds a name word; otherwise None."""
    for label in (_FUNDS_TRANSFER_WIRE_LABEL, _THIRD_PARTY_ORIGINATOR):
        for found in label.finditer(text):
            rest = text[found.end():]
            end = _WIRE_FIELD_END.search(rest)
            words = _leading_name_words(rest[: end.start()] if end is not None else rest)
            if any(word not in REVENUE_GENERIC_WORDS and not _is_reference_token(word) for word in words.split()):
                return words
    return None


def _third_party_book_transfer(text: str) -> bool:
    """5.5 (T19): a Chase BOOK TRANSFER CREDIT B/O <originator> or a Bank of America WIRE TYPE BOOK IN that prints an
    originator. Read as an incoming wire only on the owner's yes (THIRD_PARTY_BOOK_TRANSFER_AS_WIRE)."""
    return (
        THIRD_PARTY_BOOK_TRANSFER_AS_WIRE
        and _BOOK_TRANSFER_FROM.match(text) is not None
        and _third_party_originator(text) is not None
    )
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_revenue_text_readers.py -q -p no:cacheprovider`

Expected: PASS: `68 passed`.

- [ ] **Step 5: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-CLASSIFIER: `755 passed, 2 deselected`

- [ ] **Step 6: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/description_text.py analysis/transaction_classifier.py tests/test_revenue_text_readers.py
git commit -m "classifier: the credit revenue readers and the street-LN guard (5.5)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S2.2: The 5.5 rule vocabulary and the family helpers

**Files:**
- Create: `tests/test_revenue_rule_helpers.py`
- Modify: `analysis/transaction_classifier.py:10-17, 22-23, 1255`

**Depends on:** S2.1.

**Interfaces:**
- Consumes: S1.1 to S1.3 (the registry tables), S2.1 (the readers).
- Produces:
  - `@dataclass(frozen=True) class _OperatingSource(entity: str, alias: str, source_type: str | None, payout_form: bool)`
  - `_operating_source(text) -> _OperatingSource | None`, `_operating_read_vetoed(row, entity, alias, payout_form) -> bool`
  - `_card_settlement_form(text, *, bank: str | None) -> CardSettlementForm | None`, `_has_operating_context(text, source, *, bank) -> bool`
  - `_reversal_credit(text) -> bool`, `_card_credit_released(text) -> bool`, `_own_book_or_funds_transfer(text, account_name) -> bool`, `_split_glued_claim(text) -> str`
  - `_refused_by_payer_guards(text, region, account_name) -> 'holder' | 'numbered' | None`
  - `_payer_remittance(text, region, account_name) -> bool`, `_public_payer_remittance(text) -> str | None` (`'treasury_vendor_payment'` or `'public_payer_vendor_or_provider_payment'`)
  - `_wire_remittance_purpose(text, region, account_name) -> bool`, `_wire_vetoed(text, region, account_name) -> bool`, `_cut_financing_originator(region) -> bool`, `_counter_debit_skip_words() -> frozenset[str]`
  - `_read_inside_a_waiting_processor(text, entity, alias) -> bool` and `_GATED_PROCESSOR_PATTERNS` (the ledger gate, review I4)
  - `_wire_financing_text(text) -> str` (channel words and the sending, originating and intermediary bank fields removed; Santander's and Chase's OGB included), `_wire_originator_run(text) -> str | None`, `_TITLE_OR_ESCROW_ORIGINATOR`
  - `_AUCTION_VETO` (§14.1's §7.8 words), `_FUNDING_WORD`, `_FUNDING_SETTLEMENT_ENTITIES = frozenset({"TapGoods Payments", "Braintree", "Buildium"})`
  - the constants the passes read: `_RECURRENCE_VETO`, `_MICRO_DEPOSIT_FLOOR = 1`, `_LEGAL_FORM_HOLDER`, `_OPERATING_POOL_METHODS`, `_CARD_VETO`, `_NET_SETTLE_MIN_CREDITS = 3`, `_RECURRENCE_MIN_CREDITS = 3`, `_RECURRENCE_MIN_BUSINESS_CREDITS = 2`, `_HCCLAIMPMT`, `_RETURN_CODE_CREDIT_PATTERNS`, `_SQUARE_CAPITAL_CREDIT`, `_SQUARE_NAME`, `_SBA_DISBURSEMENT_CREDIT`, `_BOOK_OR_FUNDS_TRANSFER`, `_EFT_FUNDS_TRANSFER`, `_PUBLIC_PAYER_*`, `_TREASURY_BOILERPLATE`, `_WIRE_*`

**Why:** Spec §7.0 to §7.11: the patterns and helpers the credit decision (S2.3) and the statement passes (S2.4) call: the operating-source reader with the platform vetoes, the card-settlement form reader and the card veto, payout context, the reversal rule with its REIMBURSEMENT and card-credit releases, book and funds transfers, the glued claim entry, the payer guards, accounts-payable remittance, public payers, invoice wires and their vetoes, the cut financing originator. Nothing calls them yet, so this task changes no output; its tests call each helper on one fabricated row.

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_revenue_rule_helpers.py`:

```python
"""Classification 5.5 (true revenue spec §7.0 to §7.11): the family helpers the credit decision and the statement
passes call, read on one fabricated row each: the operating-source reader and its vetoes, the card-settlement forms,
payout context, the reversal and card-credit release rules, book and funds transfers, the glued claim entry, the
payer guards, accounts-payable remittance, public payers, invoice wires and their vetoes, and the cut financing
originator. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier as tc
from analysis.description_text import normalize_transaction_description as normalize


def _text(printed: str) -> str:
    return tc.revenue_text(normalize(printed))


def _region(printed: str) -> str:
    return tc.payer_region(_text(printed))


@pytest.mark.parametrize(("printed", "entity", "form"), [
    ("SPOTON VIA ASTRA DES:SETTLEMENT ID:1", "SpotOn", False),
    ("FIRST DATA MERCH DES:SETTLEMENT ID:1", "Fiserv", False),           # the sixteen-character cut
    ("FBO WHATNOT DES:PAYOUT ID:1", "Whatnot", True),                    # a payout form
    ("MANHEIM US DES:ACH PAYMNT ID:1", "Manheim", False),                # an auction, on its originator segment
])
def test_the_operating_source_reader_names_the_source(printed, entity, form):
    found = tc._operating_source(_text(printed))
    assert found is not None and found.entity == entity
    assert found.payout_form is form


@pytest.mark.parametrize("printed", [
    "WHATNOT INC DES:PAYROLL ID:1",          # a pay word on a platform read
    "WHATNOT INC DES:LOAN ID:1",             # a financing word
    "ZELLE PAYMENT FROM WHATNOT INC",        # a person-to-person rail
    "TIKTOK INC DES:DIR DEP ID:1",           # an employer-type alias with DIR DEP
    "SUPER DISPATCH DES:CASHOUT ID:1",       # a transport marketplace's wallet word
    "SAMPLE AUTO MANHEIM FEES",              # an auction name off the originator segment
])
def test_a_vetoed_or_misplaced_read_names_no_source(printed):
    assert tc._operating_source(_text(printed)) is None


@pytest.mark.parametrize(("printed", "label"), [
    ("MERCHANT BANKCD DES:DEPOSIT ID:123456 INDN:FABRIKAM BAKERY CO ID:1234567890 CCD", "bankcard"),
    ("FABRIKAM MERCH DEP 1234567", "merch_dep"),
    ("VSA DEP12345678", "brand_dep"),
    ("MISC PAYMENT 1234567 VISA GBL VI 1234", "gbl_brand"),
    ("FABRIKAM SUPPLY DES:NET SETTLE ID:1", "net_settle"),
    ("REGLEMENT MARCHAND 1234", "french_card_settlement"),
])
def test_the_card_settlement_forms(printed, label):
    form = tc._card_settlement_form(_text(printed), bank=None)
    assert form is not None and form.label == label


@pytest.mark.parametrize("printed", [
    "FABRIKAM BANKCARD LLC DES:DEPOSIT ID:1",     # a company named BANKCARD
    "BANKCARD DEP CB REV",                        # the card veto: a chargeback reversal
    "FABRIKAM LAW GROUP DES:NET SETTLE ID:1",     # NET SETTLE from a law firm
    "INTUIT 12345678 DES:TAX RFND ID:1",          # Intuit's refund
    "CAPITAL ONE CREDIT CARD DEPOSIT 1234",       # the generic card words beside a card issuer
])
def test_a_refused_card_form_is_none(printed):
    assert tc._card_settlement_form(_text(printed), bank=None) is None


def test_the_square_checking_form_reads_only_on_a_square_statement():
    assert tc._card_settlement_form(_text("CARD PAYMENT SALES"), bank="Square").label == "square_checking_sales"
    assert tc._card_settlement_form(_text("CARD PAYMENT SALES"), bank="Sample Bank") is None


@pytest.mark.parametrize(("printed", "context"), [
    ("SQUARE INC DES:SQ540115 ID:1", True),               # a Square payout id
    ("STRIPE DES:TRANSFER ID:ST-A1B2C3D4E5F6", True),      # Stripe's payout id
    ("SQUARE INC DES:CHARGEBACK SQ540115 ID:1", False),    # the card veto
    ("VAGARO DES:DEPOSIT ID:1", True),                     # the entity's own context word
])
def test_the_payout_context(printed, context):
    text = _text(printed)
    assert tc._has_operating_context(text, tc._operating_source(text), bank=None) is context


@pytest.mark.parametrize(("printed", "reversal"), [
    ("ACH RETURN R01 FABRIKAM", True),
    ("FABRIKAM DES:REVERSAL ID:1", True),
    ("MEDICAID DES:REIMBURSEMENT ID:1", False),            # REIMBURSEMENT with a claim signal
    ("DEBIT CARD CREDIT VISA DIRECT FABRIKAM PAYOUT", False),  # a push payout printed as a card credit
    ("DEBIT CARD CREDIT FABRIKAM STORE", True),            # a card refund
])
def test_the_reversal_rule_and_the_card_credit_release(printed, reversal):
    assert tc._reversal_credit(_text(printed)) is reversal


@pytest.mark.parametrize(("printed", "own"), [
    ("BOOK TRANSFER CREDIT B/O: FABRIKAM EXPORTS LLC SAMPLEVILLE", False),   # a third-party originator
    ("BOOK TRANSFER CREDIT B/O: CONTOSO TRADING LLC SAMPLEVILLE", True),      # the holder
    ("FUNDS TRANSFER FROM 1234", True),                                        # no originator name
    ("ELECTRONIC FUNDS TRANSFER DEPOSIT FABRIKAM", False),                     # the EFT channel
])
def test_a_book_or_funds_transfer_is_own_account_only_without_a_third_party(printed, own):
    assert tc._own_book_or_funds_transfer(_text(printed), "CONTOSO TRADING LLC") is own


def test_a_glued_claim_entry_is_split_for_the_lookups():
    assert tc._split_glued_claim("FABRIKAM HEALTH PLHCCLAIMPMT") == "FABRIKAM HEALTH PL HCCLAIMPMT"


def test_the_payer_guards():
    text = _text("CONTOSO BAKERY LLC DES:VENDOR PAY ID:1")
    assert tc._refused_by_payer_guards(text, tc.payer_region(text), "CONTOSO BAKERY LLC") == "holder"
    numbered = _text("1234567 NOVA SCOTIA LTD DES:VENDOR PAY ID:1")
    assert tc._refused_by_payer_guards(numbered, tc.payer_region(numbered), "SAMPLE CAFE LLC") == "numbered"
    clean = _text("FABRIKAM SUPPLY DES:VENDOR PAY ID:1")
    assert tc._refused_by_payer_guards(clean, tc.payer_region(clean), "SAMPLE CAFE LLC") is None


@pytest.mark.parametrize(("printed", "remittance"), [
    ("FABRIKAM SUPPLY DES:ACCTS PAYABLE ID:1", True),
    ("FABRIKAM SUPPLY ACH PMT INV 1234", True),
    ("FABRIKAM SUPPLY BILL COM INV 1234", True),
    ("BILL COM DES:PAYABLES ID:1", False),                   # Bill.com's own PAYABLES
    ("FABRIKAM INSURANCE DES:VENDOR PAY ID:1", False),       # the veto
    ("DEPOSIT INV 1234", False),                             # no payment-channel word
])
def test_the_payer_remittance(printed, remittance):
    text = _text(printed)
    assert tc._payer_remittance(text, tc.payer_region(text), "SAMPLE CAFE LLC") is remittance


@pytest.mark.parametrize(("printed", "rule"), [
    ("TREAS 310 DES:DOD MISC ID:1 CCD", "treasury_vendor_payment"),
    ("SAMPLE COUNTY DES:VENDOR PAY ID:1", "public_payer_vendor_or_provider_payment"),
    ("STATE OF OHIO DES:VENDOR PAY GRANT ID:1", None),
    ("FABRIKAM PLUMBING DES:VENDOR PAY ID:1 SAMPLE COUNTY", None),
])
def test_the_public_payer_arms(printed, rule):
    assert tc._public_payer_remittance(_text(printed)) == rule


BOFA = ("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:20540102001234 SEQ:1234/5678 ORIG:{orig} ID:99887766 "
        "SND BK:SAMPLE BANK ID:0123 PMT DET:{purpose}")


@pytest.mark.parametrize(("orig", "purpose", "verifies"), [
    ("FABRIKAM EXPORTS LLC", "INVOICE 1234", True),
    ("FABRIKAM EXPORTS LLC", "INVOICE 1234 INVESTMENT", False),   # a non-sale purpose
    ("FABRIKAM CAPITAL LLC", "INVOICE 1234", False),              # a financing root
    ("CONTOSO HOLDINGS LLC", "INVOICE 1234", False),              # the holder's brand word
    ("FABRIKAM EXPORTS LLC", "MONEY ORDER 1234", False),          # not an order number
])
def test_the_invoice_wire(orig, purpose, verifies):
    text = _text(BOFA.format(orig=orig, purpose=purpose))
    assert tc._wire_remittance_purpose(text, tc.payer_region(text), "CONTOSO TRADING LLC") is verifies


@pytest.mark.parametrize(("region", "cut"), [
    ("FABRIKAM MERCHAN", True),         # sixteen characters: a proper prefix of MERCHANT
    ("FABRIKAM MERCHANT", False),       # the whole word is no cut
    ("FABRIKAM CAPITA", True),          # fifteen characters: a proper prefix of CAPITAL
    ("FABRIKAM EXPORTS", False),
])
def test_the_cut_financing_originator(region, cut):
    assert tc._cut_financing_originator(region) is cut


def test_an_alias_read_inside_a_waiting_processor_names_no_source():
    # §7.1, review I4: Stripe's BY STRI cut never reads JOBBER BY STRI while Jobber Payments waits for the ledger.
    assert tc._read_inside_a_waiting_processor(_text("JOBBER BY STRI DES:TRANSFER ID:ST-A1B2C3"), "Stripe", "BY STRI")
    assert tc._operating_source(_text("JOBBER BY STRI DES:TRANSFER ID:ST-A1B2C3")) is None
    assert tc._operating_source(_text("FABRIKAM - BY STRI DES:PAYOUT ID:1")).entity == "Stripe"
    assert tc._operating_source(_text("SHIFT4 PAYMENTS DES:DEPOSIT ID:1")).entity == "Shift4"


def test_the_wire_financing_text_drops_the_sending_and_originating_banks():
    # §7.9: the roots are read after the sending (Santander) and originating (Chase's OGB) bank fields go.
    santander = _text("USD WIRE IN FROM BANCO DE CREDIT ACCT * 1234 CONTOSO SRL REF INV 10421")
    assert "CREDIT" not in tc._wire_financing_text(santander) and "CONTOSO SRL" in tc._wire_financing_text(santander)
    assert tc._wire_originator_run(santander) == "CONTOSOSRL"
    chips = _text("CHIPS CREDIT VIA SAMPLE BANK 0959 B O CONTOSO SUPPLY LLC REF NBNF NORTHWIND LABS LLC "
                  "OGB SAMPLE MERCHANTS BANK N A OBI INVOICE 10421")
    assert "MERCHANTS" not in tc._wire_financing_text(chips)


def test_a_wire_from_a_title_or_escrow_firm_is_vetoed():
    # Review I6 (§8.5's senders): a title or escrow firm's wire carries sale, closing or escrow money.
    text = _text("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:1 ORIG:CONTOSO TITLE AGENCY LLC ID:1 "
                 "SND BK:SAMPLE BANK ID:1 PMT DET:INVOICE 1042")
    assert tc._wire_vetoed(text, tc.payer_region(text), "NORTHWIND LABS LLC")


@pytest.mark.parametrize(("printed", "vetoed"), [
    ("MANHEIM US DES:ACH PAYMNT NGC ID:1", True), ("MANHEIM US DES:ACH PAYMNT FLOORPLAN ID:1", True),
    ("MANHEIM US DES:ACH PAYMNT ID:1 PPD", True), ("MANHEIM US DES:ACH PAYMNT ID:1", False),
])
def test_the_auction_veto(printed, vetoed):
    # §7.8, §14.1, review C2.
    assert (tc._AUCTION_VETO.search(_text(printed)) is not None) is vetoed


def test_the_counter_debit_skip_words_hold_the_channel_vocabulary():
    words = tc._counter_debit_skip_words()
    assert {"CHECKCARD", "OVERDRAFT", "WITHDRAW", "PURCHASES"} <= words
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_revenue_rule_helpers.py -q -p no:cacheprovider`

Expected: FAIL: `64 failed`, the first with `AttributeError: module 'analysis.transaction_classifier' has no attribute '_operating_source'`.

- [ ] **Step 3: Implement.**

In `analysis/transaction_classifier.py` (lines 10-17), replace:

```python
from .classification_registry import (
    BANK_NAME_ALIASES,
    BANK_SPECIFIC_LENDER_ALIASES,
    CARD_ISSUER_CONTEXT_ALIASES,
    FIELD_ORDER_PAYEE_FORMS,
    INSURANCE_PROVIDER_ALIASES,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
```

with:

```python
from .classification_registry import (
    BANK_NAME_ALIASES,
    BLUE_PLAN_CLAIM_PAYERS,
    CARD_SETTLEMENT_CREDIT_FORMS,
    CardSettlementForm,
    BANK_SPECIFIC_LENDER_ALIASES,
    CARD_ISSUER_CONTEXT_ALIASES,
    FIELD_ORDER_PAYEE_FORMS,
    GATED_PROCESSOR_ALIASES,
    INSURANCE_PROVIDER_ALIASES,
    OPERATING_ALIASES_READ_WITH_VETOES,
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    OPERATING_SOURCE_CONTEXT_WORDS,
    OPERATING_SOURCE_PAYOUT_FORMS,
    OPERATING_SOURCES_READ_WITH_VETOES,
```

In `analysis/transaction_classifier.py` (lines 22-23), replace:

```python
    REVIEW_FLAG_ENTITIES,
)
```

with:

```python
    REVIEW_FLAG_ENTITIES,
    WHOLESALE_AUCTION_PAYOUT_FORMS,
    WHOLESALE_AUCTION_REFUND_NAMES,
)
```

In `analysis/transaction_classifier.py`, after the end of `_third_party_book_transfer` (line 1255), insert:

```python
# ---------------------------------------------------------------------------------------------------------------------
# Classification 5.5: the credit revenue rules (§6.1 steps 3 to 14, §7.1 to §7.11).
# ---------------------------------------------------------------------------------------------------------------------

#: §7.11: the unambiguous return codes, read on credits only (the debit rules keep _REFUND_REVERSAL_PATTERNS). The
#: reversal-pair pass reads them too.
_RETURN_CODE_CREDIT_PATTERNS = (
    re.compile(
        r"\b(?:RTN|RETN|RFND|REFND|RFD|RVSL|RVRSL|REVSL|RECALL(?:ED)?|UNPAID|REJT|CHBK|CHGBK)\b"
    ),
)
#: §7.11: a claim or provider signal. REIMBURSEMENT on such a row is a provider's claim payment, not a refund.
_CLAIM_OR_PROVIDER_SIGNAL = re.compile(
    r"\b(?:MEDICAID|MEDICARE|MEDI CAL|TRICARE|CHAMPVA|GEMT|EMS|PROV(?:IDER)? ?PAY(?:MENTS?)?|EDI PYMNTS|CLAIM PMT)\b"
    r"|(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b"
)
_REIMBURSEMENT_WORD = re.compile(r"\bREIMBURSEMENT\b")
#: §7.11: push payouts printed as card credits: a push-rail word, or a processor or invoice source with a payout word.
_CARD_CREDIT_LABEL = re.compile(r"\b(?:DEBIT CARD CREDIT|POS CREDIT)\b")
_CARD_CREDIT_PUSH_WORD = re.compile(
    r"\b(?:VISA DIRECT|MC SEND|VISA MONEY TRANSFER|FASTPAY|INSTANT PAY|INSTANT PAYOUT)\b"
)
_CARD_CREDIT_PAYOUT_WORD = re.compile(r"\b(?:PAYOUTS?|INSTANT (?:PAYOUT|PAY|TRANSFER)|SETTLEMENT|DEPOSIT)\b")
#: §7.11 (T5): account verification, Square Capital's SQ CAP, SBA and EIDL disbursements (the tax-refund forms sit
#: in _NON_REVENUE_CREDIT_PATTERNS).
_ACCOUNT_VERIFICATION_CREDIT = re.compile(r"\bACCT ?VERIFY\w*\b|\bMICRO ?DEPOSITS?\b|\bPENNY TEST\b|\bTRIAL DEPOSITS?\b")
_SQUARE_CAPITAL_CREDIT = re.compile(r"\bSQ ?CAP\d*\b")
_SQUARE_NAME = re.compile(r"\bSQ\b|\bSQUARE\b")
_SBA_DISBURSEMENT_CREDIT = re.compile(r"\bSBAD TREAS\b|\bSBA (?:EIDL|LOAN|DISB\w*)\b|\bEIDL\b")
#: §7.11 (T19 and this spec): a book or funds transfer is own-account only when no third-party originator is printed.
_BOOK_OR_FUNDS_TRANSFER = re.compile(r"\b(?:BOOK|FUNDS?) TRANSFER\b")
#: §7.11: the Electronic Funds Transfer channel, never a book or funds transfer between accounts.
_EFT_FUNDS_TRANSFER = re.compile(r"\bELECTRONIC FUNDS TRANSFER DEPOSIT\b")

#: §7.0: the recurrence pass's veto: pay, financing and verification words and the card-credit labels, read on the
#: row before its receiver fields.
_RECURRENCE_VETO = re.compile(
    r"\b(?:LOANS?|CAPITAL|CAP\d*(?:SEC)?|CAPI|CAPIT|CAPITA|FIN|ADVANCE|ADV|FINANC\w*|LEND\w*|MCA|CASH ADV\w*"
    r"|PAYROLL\w*|PAYRLL|PAYROL|PAYRL|DIR ?DEP|DIRDEP|DIRECT DEP|SALARY|SALARIES|REG SAL|WAGES?|NET ?PAY|BONUS"
    r"|REIMB\w*|ACCT ?VERIFY|ACCTVERIFY\w*|VERIFY|VERIFICATION|INSUR\w*)\b"
    r"|\bDEBIT CARD CREDIT\b|\bPOS CREDIT\b"
)
#: §7.0 (review C2): FUNDING vetoes recurrence too, except on the settlements of the platforms that print it there.
_FUNDING_WORD = re.compile(r"\b(?:FUNDING|FUNDED)\b")
_FUNDING_SETTLEMENT_ENTITIES = frozenset({"TapGoods Payments", "Braintree", "Buildium"})
#: §7.0, §7.8, §7.10: the absolute micro-deposit floor, in whole dollars.
_MICRO_DEPOSIT_FLOOR = 1
#: §7.0: a legal-form holder name is a business account for the recurrence rule.
_LEGAL_FORM_HOLDER = re.compile(r"\b(?:LLC|INC|CORP|LTD|LLP|PLLC)\b")
#: §7.0: the operating-source methods whose rows may join the recurrence pool.
_OPERATING_POOL_METHODS = frozenset({
    "operating_source_requires_context", "operating_source_with_credit_context", "recurring_operating_source",
    "operating_source_related_activity", "operating_source_payout_form",
})
#: §7.8, §7.10: the operating methods an auction or property branch may touch.
_OPERATING_SOURCE_METHODS = frozenset({
    "operating_source_requires_context", "recurring_operating_source", "operating_source_related_activity",
    "operating_source_with_credit_context",
})

#: §7.1: the card veto: neither a card form nor the processor payout context fires on a row that prints it.
_CARD_VETO = re.compile(
    r"\b(?:CHBK|CHGBK|CHARGEBACKS?|DISPUTE\w*|ADJ|ADJUSTMENT|BILLING|FEES?|DISC|DISCOUNT|MTHLY|INTERCHANGE|PAYROLL"
    r"|TAX|LOANS?|CAPITAL|ADVANCE|FUNDING|FINANCING|FINANCE|RETURN(?:ED|S)?|ACCT ?VERIFY|ACCTVERIFY\w*|VERIFY"
    r"|VERIFICATION|INSUR\w*|ZELLE|VENMO|CASH ?APP|E ?TRANSFER|INTERAC|REWARDS?|REBATES?|CASH ?BACK|INTEREST|CLAIMS?"
    r"|ADV|ADVN?C?|CAP\d*(?:SEC)?|CAPI|CAPIT|CAPITA|FUNDS?|FUNDED|FNDG|FNDNG|FINANCIAL|FINCL|LEND\w*|PROCEEDS|DISB\w*"
    r"|PURCH\w*|MCA|CONTRIB\w*|OWNERS?|MEMBER|SHAREHOLDER|RTN|RET|REV\d*|RVSL|RVRSL|CB|INTCHG|DUP\w*|CORR\w*"
    r"|OVERPAY\w*|XFER|TFR|SWEEP|ZBA|BOOK)\b"
    r"|\b(?:TRANSFER|XFER|TFR) (?:FROM|TO)\b|\bONLINE TRANSFER\b"
)
#: §7.1: processor payout context, for merchant_processor and invoice_and_receivables sources only (context, never
#: proof on its own).
_PROCESSOR_PAYOUT_CONTEXT = re.compile(
    r"\bSQ ?\d{6}\b|\bMISC PAYMENTS?\b|\bMSP(?: DIV)?\b|\bDAILY DEP\b|\bST [A-Z0-9]{6,}\b"
    r"|\b(?:RTP|FEDNOW|REAL TIME (?:TRANSFER|PAYMENT)|INSTANT (?:PMT|PAYMENT|TRANSFER)|VISA DIRECT|MC SEND"
    r"|PMNT RCVD|PAYMENT RECEIVED)\b"
)
_PROCESSOR_CONTEXT_TYPES = frozenset({"merchant_processor", "invoice_and_receivables"})
#: §7.2: the vetoes on every new operating read (a payout form, and an alias added in 5.5).
_OPERATING_PAY_VETO = re.compile(
    r"\b(?:PAYROLL\w*|PAYRLL|PAYROL|PAYRL|SALARY|SALARIES|REG SAL|WAGES?|DIR ?DEP|DIRDEP|DIRECT DEP|NET ?PAY|BONUS"
    r"|REIMB\w*)\b"
)
_OPERATING_FINANCING_VETO = re.compile(
    r"\b(?:LOANS?|ADVANCE[SD]?|ADV|CAPITAL|LENDING|LENDER|FINANC\w*|FUNDING|FUNDED|PROCEEDS|DRAW)\b"
)
_OPERATING_REVERSAL_VETO = re.compile(
    r"\b(?:RETURN(?:ED|S)?|RTN|REFUND(?:ED|S)?|RFND|REFND|RFD|REVERS(?:AL|ED|E)|VOID(?:ED)?"
    r"|CANCEL(?:LED|ED|LATION)?|CNCL|ADJ|ADJUSTMENT|ADJUSTED|DISPUTE[DS]?|CHARGEBACK|CREDIT MEMO|NSF|REJECT(?:ED)?)\b"
)
_OPERATING_P2P_VETO = re.compile(r"\b(?:ZELLE|VENMO|CASH APP|E ?TRANSFER|ETRANSFER|INTERAC)\b")
#: §7.2: an employer-type alias (TikTok, Amazon's RTP alias) also refuses these pay words, and the TikTok aliases count
#: only on an ACH-shaped row.
_EMPLOYER_PAY_WORDS = re.compile(r"\b(?:DIR DEP|DIRECT DEP|PAYRL|REIMB|EXP REIMB)\b")
_EMPLOYER_TYPE_ALIASES = frozenset({"TIKTOK INC", "TIKTOK USA", "TIKTOK SHOP", "RTP CREDIT AMAZON COM"})
_TIKTOK_ALIASES = frozenset({"TIKTOK INC", "TIKTOK USA", "TIKTOK SHOP"})
_ACH_SHAPED_ROW = re.compile(r"\b(?:ACH|CCD|PPD|ORIG CO NAME|DEPOSIT|PAYMENT|PAYOUT|CORP|CORPORATE)\b")
#: §7.3: a transport marketplace's credit never counts toward recurrence with a wallet, subscription or wire word.
_TRANSPORT_EXTRA_VETO = re.compile(r"\b(?:CASHOUT|CASH OUT|SUBSCRIPTION|MEMBERSHIP|WIRE|WT|FEDWIRE|OBI|BNF)\b")
#: §7.8: an ACV credit printing a buyer-payment reference stays unverified.
_AUCTION_BUYER_PAYMENT = re.compile(r"\bPYMT\d")
#: §7.8, §14.1: an auction credit printing a floor-plan or financing word (NextGear's NGC, AFC's FUNDNG) or a
#: consumer entry (PPD) is never the auction's payout, whatever form it prints.
_AUCTION_VETO = re.compile(
    r"\b(?:FUNDING|FUNDNG|FUNDED|ADVANCES?|ADV|CAPTL|CAPITAL|FLOOR ?PLAN|FLOORPLAN|FINANC\w*|NGC|LOANS?|PPD)\b"
)
#: §7.8: the auction refund pair's window, in days.
_AUCTION_REFUND_WINDOW_DAYS = 14
#: §7.10: owner, distribution and deposit wording on a property-management platform's row, and micro-deposits.
_PROPERTY_PLATFORM_GUARD = re.compile(
    r"\bOWNERS? ?(?:DIST\w*|DISB\w*|DRAWS?\w*|CONT\w*)|\bDISTRIBUT\w*|\bSEC(?:URITY)? ?DEP\w*"
    r"|\bDEP(?:OSIT)? ?(?:RETURN\w*|RTN\w*|RT\w*|REFUND\w*)|\bSD ?(?:RETURN\w*|RTN\w*|RT\w*|REFUND\w*)"
    r"|\bADVANCE\w*|\bORIG CO NAME\b.*\bORIG CO NAME\b"
)
_PROPERTY_MICRO_DEPOSIT = re.compile(
    r"\bACCT ?VERIFY\w*|\bMICRO ?(?:DEP\w*|ENTRY)\b|\bPENNY TEST\b|\bTRIAL (?:DEP\w*|CREDIT)\b"
)
_PROPERTY_PUSH_SHAPE = re.compile(r"\b(?:VISA DIRECT|PMNT RCVD|PAYMENT RECEIVED|RTP)\b")
#: §7.1: an unregistered NET SETTLE originator needs this many NET SETTLE credits in the statement.
_NET_SETTLE_MIN_CREDITS = 3
#: §7.0: the operating recurrence rule.
_RECURRENCE_MIN_CREDITS = 3
_RECURRENCE_MIN_BUSINESS_CREDITS = 2

#: §7.7: the NACHA claim-payment entry. The unbounded branch takes only the full token (never THECLAIMPMT).
_HCCLAIMPMT = re.compile(r"(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b")
#: §7.7: inside the credit decision, the financing, potential-lender and insurer lookups read a glued HCCLAIMPMT
#: split from the name before it, so a sixteen-character funder name glued to the token is still found.
_GLUED_CLAIM_ENTRY = re.compile(r"(?<=[A-Z0-9])(H[CE]?CLAIMPMT)")
#: §8.1 (T14): an insurer's customer-payment wording (a DRP payment, a vendor payment, a commission).
_INSURER_CUSTOMER_PAYMENT = re.compile(
    r"\b(?:DRP|VENDOR ?(?:PMT|PAY|PAYMENT)|COMM?ISS?IONS?|AGT ?COMM|AGENT COMP|AGTEFT|REPAIR)\b"
)
_BLUE_PLAN_CLAIM_PAYER = re.compile("|".join(BLUE_PLAN_CLAIM_PAYERS))

#: §7.5: the payer's accounts-payable remittance (credits only), read on the revenue text and the joined text.
_PAYER_REMITTANCE_CREDIT_PATTERNS = (
    re.compile(r"\bACC(?:OUN)?TS? PAYABLE\b"),
    re.compile(r"^DIRECT DEPOSIT\b(?=.* AP CC$)"),
    re.compile(r"\bA ?P (?:PMTS?|PAYMENTS?|PYMTS?)\b"),
    re.compile(r"\bCO ENTRY DESCR A ?P\b"),
    re.compile(r"\b(?:CCD)?ACC PAY\b"),
    re.compile(r"\bVENDOR ?(?:PMTS?|PAYMENTS?|PAY|PYMTS?)(?:SEC)?\b"),
    re.compile(r"\bTRADE PAY(?:MENTS?)?(?:SEC)?\b"),
    # PAYABLES is Bill.com's payer-side debit wording: never read on a row that prints BILL COM (_payer_remittance).
    re.compile(r"\bPAYABLES\b"),
    re.compile(r"\bPO REMIT(?:TANCE)?\b"),
    re.compile(r"\bAVID ?PAY\b|\bAVIDXCHANGE\b|\bCOUPA PAY\b|\bPAYMODE\b"),
    re.compile(r"\bPAYING BILLS? (?:\d|INV)|\bFOR \d+ BILLS\b"),
    re.compile(r"\bBI ?LL COM (?:INV|MULTIPLE INVOICES|RECEIVABLE)\b|\b(?:DESCR|DES) BI ?LL COM\b"
               r"|\bRECEIVABLE\b(?=.*\bBI ?LL COM\b)"),
    re.compile(r"\bINV(?:OICE)? (?:PMT|PYMT)\b|\b(?:OF|FOR) INVOI ?CES?\b"),
    re.compile(r"\bRMR IV\b"),
    re.compile(r"\bPAIEMENT (?:DE )?FACTURE\b"),
)
_BILL_COM = re.compile(r"\bBI ?LL COM\b")
#: §7.5: the invoice number counts only with a payment-channel word, and never after CREATED FROM or TRANSFER FROM.
_INVOICE_NUMBER = re.compile(r"(?<!\bCREATED FROM )(?<!\bTRANSFER FROM )\bINV(?:OICE)?S?(?: (?:NO|NUM|NUMBER|N))? ?\d")
_PAYMENT_CHANNEL_WORD = re.compile(
    r"\b(?:ACH|PMT|PAYMENTS?|ZELLE|WIRE|FEDWIRE|CHIPS|CCD|CTX|PPD|EFT|RTP|REMIT)\b"
)
#: §7.5: the free-text forms (invoice, bill and 'for invoices') count on a PAYPAL row or a wire from a person only
#: when the sender prints a company form.
_FREE_TEXT_REMITTANCE = re.compile(
    r"\bPAYING BILLS?\b|\bFOR \d+ BILLS\b|\b(?:OF|FOR) INVOI ?CES?\b|\bINV(?:OICE)?S?(?: (?:NO|NUM|NUMBER|N))? ?\d"
)
#: §7.5: the credit posting labels removed before the veto reads the row.
_CREDIT_POSTING_LABELS = re.compile(
    r"\b(?:ELECTRONIC|ACH|RTP|ONLINE|WIRE|BOOK|CORP|CORPORATE|ZELLE|MISC|DIRECT|PAYMENT|DEPOSIT|TRANSFER|MOBILE|EFT"
    r"|CHIPS|FEDWIRE)\s+CREDIT\b|^CREDIT\b"
)
#: §7.5: the veto of the payer remittance rule.
_PAYER_REMITTANCE_VETO = re.compile(
    r"(?:FUND|CAPIT|CAPTL|LOAN|LEND|FINANC|ADVANC|MORTG|ACCEPTANCE|SERVICING|SERVICER|PORTFOL|CREDIT)"
    r"|CRED(?=ORA|IBLY|\b)|CAPI?\b|LEAS(?:E|ES|ING|IN|I)?\b"
    r"|\b(?:CAP|FIN|FINA|FINAN|FI|FINL|FNCL|ADV|MTG|MCA|RTR|SPV|FUN|FUNDI|LOA)\b"
    r"|\b(?:INSUR\w*|INS|ASSURANCE|INVEST\w*|BROKERAGE|SECURITIES|WEALT\w*|TAX(?:ES)?|IRS|CRA|GRANTS?|REBATES?"
    r"|DIVIDENDS?)\b"
    r"|\b(?:PAYROLL|SALARY|WAGES?|REIMB\w*|EXPENSES?|BONUS|COMM?ISS?IONS?|CLAIMS?|MUTUAL|INDEMNITY|CASUALTY"
    r"|UNDERWRIT\w*)\b"
    r"|\b(?:EQUIP\w*|FLOOR\w*|MERCH\w*|VIN)\b"
    r"|\bSBAD?\b|\bEIDL\b"
    r"|\bINTERCO(?:MPANY)?\b|\bDUE FROM\b|\bSHAREHOLDER\b|\bOWNERS?\b|\bZBA\b|\bZERO BAL\w*|\bSWEEP\b"
    r"|\bCONTROLLED DISB\w*|\b(?:TRANSFER|XFER|TFR) FROM\b|\bINTERNAL\b"
    r"|\bRTN\b|\bRETURN(?:ED)? ITEM\b|\bRECALL\w*|\bUNPAID\b|\bADJ\b"
    r"|ACIMA"
)
#: §7.5, §8.1: words that never make a payer's or a debit's first distinctive word: the AP words, the public-payer
#: words, the holder noise (legal suffixes, generic words) and the bank's template and channel words (D11's channel
#: words, D6's channel vocabulary and bank template words, read at call time: _counter_debit_skip_words).
_COUNTER_DEBIT_SKIP_WORDS = frozenset({
    "PAYABLE", "PAYABLES", "ACCOUNTS", "ACCTS", "VENDOR", "TRADE", "REMIT", "REMITTANCE", "STATE", "COUNTY", "CITY",
    "TOWN", "DEPT", "DEPARTMENT", "TREAS", "GOVERNMENT",
    "CHECKCARD", "OVERDRAFT", "TRANF", "CHECKG", "TRANSFERS", "WITHDRAW", "OUTGOING", "PURCHASES",
}) | HOLDER_NOISE


@cache
def _counter_debit_skip_words() -> frozenset[str]:
    return _COUNTER_DEBIT_SKIP_WORDS | frozenset(_ENTITY_NOISE) | _CHANNEL_VOCABULARY | _BANK_TEMPLATE_WORDS

#: §7.6: the public-payer remittance rule. Arm A reads the whole row.
_PUBLIC_PAYER_ARM_A = (
    re.compile(r"^(?!.*\bPPD\b).*\bTREAS \d{3}(?: DES)? DOD MISC\b"),
    re.compile(r"\bTREAS \d{3}\b.*\bMISC PAY(?:SEC)?\b.*\bRMR IV\b"),
)
#: §7.6 arm B: a public payer anchored on the payer name.
_PUBLIC_PAYER_NAME = re.compile(
    r"^((?:\S+ ){0,3})(?:TREAS \d{3}"
    r"|(?:STATE|COUNTY|CITY|TOWN|VILLAGE|TOWNSHIP|BOROUGH|PARISH|DISTRICT|PROVINCE|COMMONWEALTH|GOVERNMENT|GOVT"
    r"|MUNICIPALITY) OF [A-Z]"
    r"|(?<!\bFROM )(?<!\bTO )(?<!\bTHE )(?<!\bOF )(?<!\bAND )(?<!\bINTO )\b[A-Z]{3,} (?:COUNTY|PARISH|TOWNSHIP|BOROUGH)\b"
    r"|(?:DEPT|DEPARTMENT|MINISTRY) OF\b|(?:DHS|DHHS|DSHS|DCF|DCFS|DSS)\b|SCHOOL DIST(?:RICT)?\b|DFAS\b)"
)
_PUBLIC_PAYER_TEMPLATE = re.compile(
    r"^(?:ELECTRONIC (?:CREDIT|DEPOSIT)(?: FROM)?|ACH (?:CORP )?CREDIT|ACH DEPOSIT|CCD DEPOSIT|DEPOSIT FROM"
    r"|PREAUTHORIZED CREDIT|EFT CREDIT)\b ?"
)
_PUBLIC_PAYER_PURPOSE = re.compile(
    r"\bVEN(?:DOR)? ?(?:PAY(?:MENTS?)?|P(?:Y)?MTS?)(?:SEC)?\b|\bPROV(?:IDER)? ?PAY(?:MENTS?)?(?:SEC)?\b"
    r"|\bEDI ?(?:PYMNTS|PAYMENTS?|PMTS?)(?:SEC)?\b"
)
_PUBLIC_PAYER_NAME_VETO = re.compile(
    r"\b(?:DEPT OF REVENUE|DEPARTMENT OF REVENUE|TAXATION|COMPTROLLER|TREASURER|DEPT OF LABOR|UNEMPLOYMENT"
    r"|WORKFORCE)\b|FUNDING|FUNDER|FINANC|CAPITAL|LENDING|LENDER"
)
_TREASURY_BOILERPLATE = re.compile(
    r"\bADDITIONAL INFORMATION IS AVAILABLE FOR THIS PMT CONTACT A TREASURY SALES OFFICER FOR ASSISTANCE\b"
)
#: §7.6: the whole-row veto, by group; §8.1 holds a public payer's non-sale credit on the first groups.
_PUBLIC_PAYER_NON_SALE_WORDS = re.compile(
    r"\b(?:TAX(?:ES)?|TAXRFD|TAX ?REF(?:UND)?S?|REFUNDS?|RFD|STUREFUND|R(?:E)?F(?:U)?ND|EIC|(?:XX)?SOC SEC|SUPP SEC"
    r"|SSI|(?:XX)?VA BEN\w*|BENEF\w*|BEN)\b|[A-Z]*REFUNDS?\b|[A-Z]*RFND\b"
    r"|\b(?:FED SAL|SALARY|PAYROLL|WAGES?|STIPENDS?|PER DIEM|RETIRE\w*|PENSION|ANNUIT\w*)\b"
    r"|\b(?:UNEMPLOY\w*|UI|STIMULUS|GRANTS?|RELIEF|DISASTER|CARES|PPP|SBAD?|EIDL|EIDG|LOANS?|ADVANCES?|ADV"
    r"|FORGIV\w*)\b"
    r"|\b(?:CHI?LD ?SUPP\w*|CHILD ?CTC|CTC|JURY|RESTITUTION|FOSTER|ADOPT\w*|KINSHIP|WORK(?:ERS)? ?COMP)\b"
    r"|\b(?:CLAIMS?|AWARDS?|SUBSID\w*|DISB\w*|PROCEEDS|UNCLAIMED|OVERPA\w*|OVERP(?:Y)?MT|REBATES?|REIMB\w*|BONDS?"
    r"|ESCROW|RETURN(?:ED)?|STABILI[SZ]\w*|OFFSET|RECOVERY|ARPA|RESCUE|ERT?C|INCENTIVES?|TUITION)\b"
    r"|\bASSISTANCE\b"
)
_PUBLIC_PAYER_OTHER_VETO = re.compile(
    r"\b(?:ZELLE|VENMO|CASH ?APP|E ?TRANSFER|INTERAC)\b"
    r"|\b(?:FUNDING|FUNDER|LENDING|LENDER|FINANC\w*|CAPITAL|CREDIT UNION|FCU|MORTGAGE|LEASE|LEASING|FACTOR\w*)\b"
    r"|\bSETTLEMENT\b"
)
_PUBLIC_PAYER_ARM_B_TRANSFER = re.compile(r"\b(?:TRANSFER|XFER|TFR)\b")

_WIRE_PARTY_FIELDS = re.compile(
    r"\bB O\b.*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN)\b|$)|\bN?BNF\b.*?(?=\b(?:REF|OBI|RFB|IMAD|TRN|ORIG)\b|$)"
    r"|\bORIG\b(?! TO BNF).*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN|SND BK|PMT DET)\b|$)|\bACCT \d+\b"
    r"|\bORIGINATOR NAME\b.*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN)\b|$)|\bORG\b.*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN)\b|$)"
)
_WIRE_NON_SALE_PURPOSE = re.compile(
    r"\b(?:INVEST\w*|DISTRIBUTION|DIVIDEND|EQUITY|MEMBERSHIP INTEREST|SHAREHOLDER|STOCK|CONTRIBUTION|PROCEEDS|ESCROW"
    r"|CLOSING|OVER PAYMENT|REBATE|RETURN(?:ED)?|CREDIT MEMO|DUPLICATE|SALARY|PAYROLL|WAGES|TAX|GRANT|DONATION|GIFT"
    r"|INTEREST|REPAY\w*|PRINCIPAL|SECURITY DEPOSIT|INTER ?COMPANY|INTERCO|AFFILIATE|OWNERS?|PERSONAL|COURT|JUDGMENT|INSURANCE"
    r"|CLAIMS?|RETN|RTN|REJT|REJECT(?:ED)?|RECALL(?:ED)?|UNABLE TO APPLY|DRAWS?|DRAWDOWNS?|DISBURS\w*|FEES?|SCF"
    r"|SUPPLY CHAIN|EARLY PAY(?:MENT)?|DISCOUNT(?:ED|ING)?|PAYOFF|SURPLUS|EARNEST|SUBSCRIPTIONS?|COMPENSATION|ADJ"
    r"|ADJUSTMENTS?|RMA|SHORTAGES?|ALLOWANCES?|PROMISSORY|CONVERTIBLE|BRIDGE|SAFE|TRANCHE|DEPOSIT BACK)\b"
)
#: §7.9: the channel and bank fields removed before the financing roots are read on a wire.
_WIRE_CHANNEL_AND_BANK_FIELDS = re.compile(
    r"^(?:WIRE TYPE \S+ IN|USD WIRE IN|[A-Z]{3} WIRE IN|FEDWIRE CREDIT|CHIPS CREDIT|WT FED|WIRE TSF"
    r"|WIRE TRANSFER \S+|INCOMING WIRE|WIRE IN|WIRE FROM|(?:DOMESTIC|INTL|INTERNATIONAL|FOREIGN)(?: INCOMING)? WIRE"
    r"|INCOMING FUNDS TRANSFER|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER|FUNDS TRANSFER WIRE FROM"
    r"|BOOK TRANSFER CREDIT)\b"
    r"|\b(?:SND BK|BBI|VIA|INTERMEDIARY|INT BK|OGB)\b.*?(?=\b(?:B O|ORIG|ORG|REF|OBI|BNF|TRN|IMAD|PMT DET|RFB|RMR|ID)\b|$)"
)
#: §7.9, §8.5: a wire from a title or escrow firm carries sale, closing or escrow money, never a sale of the business.
_TITLE_OR_ESCROW_ORIGINATOR = re.compile(r"\b(?:TITLE|ESCROW)\b")
#: §7.9: a cut originator field: the field widths of Santander (16) and Bank of America (25).
_WIRE_ORIGINATOR_FIELD_WIDTHS = (16, 25)
_FINANCING_FULL_WORDS = (
    "FUNDING", "FINANCIAL", "CAPITAL", "LENDING", "LOANS", "ADVANCE", "MERCHANT", "CREDIT", "LEASING", "SERVICING",
    "FACTORING", "MORTGAGE", "RECEIVABLES", "EQUIPMENT", "ACCEPTANCE", "COLLECTIONS", "RECOVERY", "SETTLEMENT",
    "REMITTANCE", "EQUITIES", "EQUITY", "VENTURES",
)

#: §7.9: the financing and potential aliases, run together, for the cut-originator test.
_FINANCING_RUN_TOGETHER_ALIASES = frozenset(
    normalize_transaction_description(alias).replace(" ", "")
    for state, registry in (*PAYEE_GROUP_REGISTRIES.items(), ("potential_lender", POTENTIAL_LENDER_ALIASES))
    if state in FINANCING_STATES or state == "potential_lender"
    for aliases in registry.values()
    for alias in aliases
)
#: §7.8: each wholesale auction's aliases as a registry of its own, read on the originator segment.
_AUCTION_ALIAS_REGISTRIES = {
    entity: {entity: OPERATING_REVENUE_READ_ALIASES[entity]}
    for entity, source_type in OPERATING_REVENUE_SOURCE_TYPES.items()
    if source_type == "wholesale_auto_auction"
}
_CARD_FORMS = tuple(
    (form, re.compile(form.pattern), re.compile(form.refusal) if form.refusal else None)
    for form in CARD_SETTLEMENT_CREDIT_FORMS
)
_PAYOUT_FORMS = tuple(
    (entity, label, re.compile(pattern))
    for entity, forms in OPERATING_SOURCE_PAYOUT_FORMS.items()
    for label, pattern in forms
)
_AUCTION_PAYOUT_FORMS = {
    entity: tuple(re.compile(pattern) for pattern in patterns)
    for entity, patterns in WHOLESALE_AUCTION_PAYOUT_FORMS.items()
}
_AUCTION_REFUND_NAMES = {entity: re.compile(pattern) for entity, pattern in WHOLESALE_AUCTION_REFUND_NAMES.items()}
_OPERATING_CONTEXT_WORDS = {
    entity: re.compile(r"\b(?:" + "|".join(words) + r")\b") for entity, words in OPERATING_SOURCE_CONTEXT_WORDS.items()
}
#: §7.1 (the ledger gate): each waiting processor's bare aliases, as whole words, longest first.
_GATED_PROCESSOR_PATTERNS = {
    processor: re.compile(r"\b(?:" + "|".join(
        re.escape(normalize_transaction_description(alias)) for alias in sorted(aliases, key=len, reverse=True)
    ) + r")\b")
    for processor, aliases in GATED_PROCESSOR_ALIASES.items()
}
_WIRE_INVOICE_SPLITS = tuple(
    dict.fromkeys(word[:cut] + " " + word[cut:] for word in ("INVOICE", "INVOICES") for cut in range(1, len(word)))
)
_WIRE_SALE_PURPOSE = re.compile(
    r"\b(?:INVOICES?|" + "|".join(_WIRE_INVOICE_SPLITS) + r")\b"
    r"|\bINV(?:OICE)?S? ?(?:NO |NUM |NBR |NUMBER )?\d"
    r"|\bPO ?(?:NO |NUM |NBR |NUMBER )?\d{3,}|\bPURCHASE ORDERS?\b"
    r"|(?<!\bMONEY )(?<!\bSTANDING )(?<!\bPAYMENT )(?<!\bPMT )(?<!\bCOURT )(?<!\bPAY )(?<!\bTRANSFER )(?<!\bSUPPORT )"
    r"(?<!\bBANK )(?<!\bWIRE )\bORDERS? ?(?:NO\b|NUM\b|NBR\b|NUMBER\b|\d)"
    r"|\bPAYMENT FOR GOO(?:DS?)?\b|\bPAGO PROVEEDOR\b|\bFACTURA\b|\bREF INV\b|\bPRO ?FORMA\b|\bCOMPRA (?:DE )?MERCAD\w*"
)


@dataclass(frozen=True)
class _OperatingSource:
    """5.5 (§7.2): what the operating-source reader found on one credit."""

    entity: str
    alias: str
    source_type: str | None
    payout_form: bool


def _operating_read_vetoed(row: str, entity: str, alias: str, payout_form: bool) -> bool:
    """5.5 (§7.2, §7.3): the vetoes of a new operating read (a payout form, or an alias this release added), read on
    the row before its receiver fields: pay, financing, reversal and adjustment, and person-to-person words. An
    employer-type alias also refuses DIR DEP, PAYRL and REIMB, and the TikTok aliases count only on an ACH-shaped row.
    A transport marketplace also refuses wallet, subscription and wire words."""
    new_read = payout_form or entity in OPERATING_SOURCES_READ_WITH_VETOES or alias in OPERATING_ALIASES_READ_WITH_VETOES
    if not new_read:
        return False
    if (
        _OPERATING_PAY_VETO.search(row)
        or _matches_any(row, _PAYROLL_PATTERNS)
        or _is_payroll_provider_row(row)
        or _OPERATING_FINANCING_VETO.search(row)
        or _OPERATING_REVERSAL_VETO.search(row)
        or _OPERATING_P2P_VETO.search(row)
    ):
        return True
    if alias in _EMPLOYER_TYPE_ALIASES and _EMPLOYER_PAY_WORDS.search(row):
        return True
    if alias in _TIKTOK_ALIASES and not _ACH_SHAPED_ROW.search(row):
        return True
    return OPERATING_REVENUE_SOURCE_TYPES.get(entity) == "transport_marketplace" and bool(
        _TRANSPORT_EXTRA_VETO.search(row)
    )


def _read_inside_a_waiting_processor(text: str, entity: str, alias: str) -> bool:
    """5.5 (§7.1, the ledger gate): the operating alias read lies inside the bare alias of another processor the
    ledger has not cleared ('BY STRI' inside 'JOBBER BY STRI'), so it names no source while that processor waits."""
    return any(
        processor != entity and any(alias in found.group(0) for found in pattern.finditer(text))
        for processor, pattern in _GATED_PROCESSOR_PATTERNS.items()
    )


def _operating_source(text: str) -> _OperatingSource | None:
    """5.5 (§7.2): the operating source a credit's revenue text names: a payout form first (it names the entity and
    counts as payout context), else the longest operating alias or its sixteen-character cut. A wholesale-auction
    alias counts only on the originator segment. A new read that a veto of §7.2 refuses names no source, and so does
    an alias read inside a waiting processor's bare alias (§7.1). One helper for step 10 and the recurrence pass."""
    row = _before_receiver(text)
    joined = _joined_text(row)
    for entity, label, pattern in _PAYOUT_FORMS:
        if pattern.search(row) or pattern.search(joined):
            if _operating_read_vetoed(row, entity, label, True):
                return None
            return _OperatingSource(entity, label, OPERATING_REVENUE_SOURCE_TYPES.get(entity), True)
    found = registry_match(text, OPERATING_REVENUE_READ_ALIASES)
    if found is None or _read_inside_a_waiting_processor(text, *found):
        return None
    entity, alias = found
    source_type = OPERATING_REVENUE_SOURCE_TYPES.get(entity)
    if source_type == "wholesale_auto_auction" and registry_match(
        _originator_segment(text), _AUCTION_ALIAS_REGISTRIES[entity]
    ) is None:
        return None
    if _operating_read_vetoed(row, entity, alias, False):
        return None
    return _OperatingSource(entity, alias, source_type, False)


def _card_settlement_form(text: str, *, bank: str | None) -> CardSettlementForm | None:
    """5.5 (§7.1): the first card-settlement form a credit prints, read on the row before its receiver fields and on
    the joined text, unless the form's own refusal or the card veto matches. NET SETTLE is returned too; the caller
    decides it (an unregistered originator needs three such credits, which the recurrence pass counts)."""
    row = _before_receiver(text)
    joined = _joined_text(row)
    if _CARD_VETO.search(row):
        return None
    for form, pattern, refusal in _CARD_FORMS:
        if form.bank is not None and (bank or "").upper() != form.bank:
            continue
        if not (pattern.search(row) or pattern.search(joined)):
            continue
        if refusal is not None and (refusal.search(row) or refusal.search(joined)):
            continue
        # §7.1 (structural S53): the generic credit-card sales words never read on a row that names a card issuer.
        if form.label == "generic_card_sales" and registry_match(row, CARD_ISSUER_CONTEXT_ALIASES) is not None:
            continue
        return form
    return None


def _has_operating_context(text: str, source: _OperatingSource, *, bank: str | None) -> bool:
    """5.5 (§7.1, §7.2): a registry alias verifies one row with payout context: a payout form, the operating-context
    words (read on the row and the joined text), a card-settlement form, the entity's own context words, or, for a
    merchant processor or an invoice platform, the processor payout context. The card veto refuses the last two."""
    if source.payout_form:
        return True
    row = _before_receiver(text)
    joined = _joined_text(row)
    if _matches_any(text, _OPERATING_CREDIT_CONTEXT_PATTERNS) or _matches_any(joined, _OPERATING_CREDIT_CONTEXT_PATTERNS):
        return True
    words = _OPERATING_CONTEXT_WORDS.get(source.entity)
    if words is not None and words.search(row):
        return True
    form = _card_settlement_form(text, bank=bank)
    if form is not None and form.label != "net_settle":
        return True
    return (
        source.source_type in _PROCESSOR_CONTEXT_TYPES
        and not _CARD_VETO.search(row)
        and _PROCESSOR_PAYOUT_CONTEXT.search(row) is not None
    )


def _reversal_credit(text: str) -> bool:
    """5.5 (§6.1 step 3, §7.11): the reversal, cancellation, NSF and provisional-credit rule, with the return codes.
    REIMBURSEMENT never fires on a row that prints a claim or provider signal, and DEBIT CARD CREDIT and POS CREDIT
    never fire on a push payout printed as a card credit (_card_credit_released)."""
    for pattern in _REVERSAL_CANCELLATION_CREDIT_PATTERNS:
        found = pattern.search(text)
        if found is None:
            continue
        if pattern.pattern == _REIMBURSEMENT_WORD.pattern and _CLAIM_OR_PROVIDER_SIGNAL.search(text):
            continue
        if _CARD_CREDIT_LABEL.fullmatch(found.group(0)) and _card_credit_released(text):
            continue
        return True
    return _matches_any(text, _RETURN_CODE_CREDIT_PATTERNS)


def _card_credit_released(text: str) -> bool:
    """5.5 (§7.11): a DEBIT CARD CREDIT or POS CREDIT row that prints a push-rail word, or names a merchant-processor
    or invoice source together with a payout word. Naming another source (a marketplace's card refund) is not
    enough. Such a row is never pooled for recurrence and verifies only by a form or single-row registry context."""
    if not _CARD_CREDIT_LABEL.search(text):
        return False
    if _CARD_CREDIT_PUSH_WORD.search(text):
        return True
    source = _operating_source(text)
    return (
        source is not None
        and source.source_type in _PROCESSOR_CONTEXT_TYPES
        and _CARD_CREDIT_PAYOUT_WORD.search(text) is not None
    )






def _own_book_or_funds_transfer(text: str, account_name: str | None) -> bool:
    """5.5 (§7.11): BOOK TRANSFER and FUNDS TRANSFER are own-account only when no third-party originator is printed,
    or when that originator is the holder (§5.2's holder test). ELECTRONIC FUNDS TRANSFER DEPOSIT is an EFT channel.
    Without the owner's yes to T19, every BOOK TRANSFER stays own-account."""
    found = _BOOK_OR_FUNDS_TRANSFER.search(text)
    if found is None or _EFT_FUNDS_TRANSFER.search(text):
        return False
    if found.group(0).startswith("BOOK") and not THIRD_PARTY_BOOK_TRANSFER_AS_WIRE:
        return True
    originator = _third_party_originator(text)
    return originator is None or holder_named(originator, account_name)


def _split_glued_claim(text: str) -> str:
    """5.5 (§7.7): the text the financing, potential-lender and insurer lookups read: a space before a glued
    HCCLAIMPMT, so a sixteen-character name glued to the token is still found."""
    return _GLUED_CLAIM_ENTRY.sub(r" \1", text)


def _refused_by_payer_guards(text: str, region: str, account_name: str | None) -> str | None:
    """5.5 (§6.1): steps 11 (the customer and invoice descriptors) to 14 refuse a payer the holder test or the
    numbered-company guard matches. Returns 'holder' or 'numbered', or None."""
    if holder_named(region, account_name):
        return "holder"
    if numbered_company(text, region):
        return "numbered"
    return None


def _payer_remittance(text: str, region: str, account_name: str | None) -> bool:
    """5.5 (§7.5): the payer's accounts-payable remittance: an AP pattern, or an invoice number on a row that also
    prints a payment-channel word; the free-text forms count on a PayPal row or a wire only with a company form; the
    veto reads the row with the matched words and the credit posting labels removed."""
    row = _before_receiver(text)
    joined = _joined_text(row)
    matched = None
    for pattern in _PAYER_REMITTANCE_CREDIT_PATTERNS:
        found = pattern.search(row) or pattern.search(joined)
        if found is not None and not (found.group(0) == "PAYABLES" and _BILL_COM.search(row)):
            matched = found.group(0)
            break
    if matched is None:
        found = _INVOICE_NUMBER.search(row)
        if found is not None and _PAYMENT_CHANNEL_WORD.search(row[: found.start()] + " " + row[found.end():]):
            matched = found.group(0)
    if matched is None:
        return False
    if _FREE_TEXT_REMITTANCE.search(matched) and (re.search(r"\bPAYPAL\b", row) or _is_wire_row(text)):
        if not company_form(payer_name(region)):
            return False
    rest = _CREDIT_POSTING_LABELS.sub(" ", row.replace(matched, " "))
    if _PAYER_REMITTANCE_VETO.search(rest) is not None:
        return False
    if _is_wire_row(text) and _wire_vetoed(text, region, account_name):
        return False
    # A public payer's vendor payment also answers to §7.6's whole-row veto (a grant, a refund, a benefit, a
    # settlement, assistance), so a public payer never verifies here what §7.6 refuses.
    whole = _TREASURY_BOILERPLATE.sub(" ", text)
    public = _PUBLIC_PAYER_NAME.match(_PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)) is not None
    return not (public and (_PUBLIC_PAYER_NON_SALE_WORDS.search(whole) or _PUBLIC_PAYER_OTHER_VETO.search(whole)))


def _public_payer_remittance(text: str) -> str | None:
    """5.5 (§7.6): a public payer's remittance: arm A (Treasury vendor codes, whole row) or arm B (a public payer
    anchored on the payer name, with a payer-side purpose). Returns the matched rule, or None. Every veto is read on
    the row after Bank of America's Treasury boilerplate is deleted."""
    whole = _TREASURY_BOILERPLATE.sub(" ", text)
    row = _before_receiver(whole)
    if _PUBLIC_PAYER_NON_SALE_WORDS.search(whole) or _PUBLIC_PAYER_OTHER_VETO.search(whole):
        return None
    if any(pattern.search(whole) for pattern in _PUBLIC_PAYER_ARM_A):
        return "treasury_vendor_payment"
    name = _PUBLIC_PAYER_TEMPLATE.sub("", _payee_region(row).strip(), count=1)
    found = _PUBLIC_PAYER_NAME.match(name)
    if found is None:
        return None
    lead = found.group(1)
    if any(ch.isdigit() for ch in lead) or _PUBLIC_PAYER_PURPOSE.search(name[: found.end()]):
        return None
    if _PUBLIC_PAYER_NAME_VETO.search(name) or _PUBLIC_PAYER_ARM_B_TRANSFER.search(whole):
        return None
    if not _PUBLIC_PAYER_PURPOSE.search(row):
        return None
    return "public_payer_vendor_or_provider_payment"


def _wire_financing_text(text: str) -> str:
    """5.5 (§7.9): the wire row the financing roots are read on: the channel words and the sending, originating and
    intermediary bank fields removed (Santander prints its sending bank after WIRE IN FROM, Chase its originating
    bank after OGB)."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        text = text[: santander.start("bank")] + " " + text[santander.end("bank"):]
    return _WIRE_CHANNEL_AND_BANK_FIELDS.sub(" ", text)


def _wire_originator_run(text: str) -> str | None:
    """5.5 (§7.9): the first six words of a wire's originator field run together (wrap-tolerant, so 'CAPI TAL' reads
    CAPITAL), or None when the row prints no originator label. On Santander's layout the originator follows the
    account number."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        return "".join(santander.group("originator").split()[:6])
    label = _WIRE_ORIGINATOR_LABEL.search(text)
    return None if label is None else "".join(text[label.end():].split()[:6])


def _wire_remittance_purpose(text: str, region: str, account_name: str | None) -> bool:
    """5.5 (§7.9): an incoming wire (N1) whose purpose cites an invoice, a PO, an order or goods, and that no wire veto
    refuses (_wire_vetoed)."""
    if not _is_wire_row(text):
        return False
    purpose_text = _WIRE_PARTY_FIELDS.sub(" ", text)
    holder_text = account_name_text(account_name)
    if len(holder_text) >= 6:
        purpose_text = purpose_text.replace(holder_text, " ")
    if not _WIRE_SALE_PURPOSE.search(purpose_text):
        return False
    return not _wire_vetoed(text, region, account_name)


def _wire_vetoed(text: str, region: str, account_name: str | None) -> bool:
    """5.5 (§7.9): the vetoes of an incoming wire: a non-sale purpose; a financing root after the channel and bank
    fields are removed, or in the first six words after the originator label run together (wrap-tolerant); any known
    payee; the own account (the originator's first two words are the beneficiary's or in the account name); a
    brand-word affiliate (the originator's first distinctive word is the beneficiary's first word or the account
    name's); a cut originator field that starts a financing name; a title or escrow firm (§8.5). The AP rule reads
    them on a wire too (§7.5)."""
    if _WIRE_NON_SALE_PURPOSE.search(text):
        return True
    if _names_financing(_wire_financing_text(text)):
        return True
    run = _wire_originator_run(text)
    if run is not None and _names_financing(run):
        return True
    if match_known_payee(text) is not None:
        return True
    holder_text = account_name_text(account_name)
    originator = region.split()
    beneficiary = re.search(r"\bN?BNF\b (\S+)(?: (\S+))?", text)
    if originator:
        first_two = " ".join(originator[:2])
        if beneficiary is not None and " ".join(word for word in beneficiary.groups() if word) == first_two:
            return True
        if holder_text and len(originator) >= 2 and first_two in holder_text:
            return True
        originator_first = _first_distinctive_word(_distinctive_words(originator))
        holder_first = holder_text.split()[0] if holder_text else None
        if originator_first is not None and (
            (beneficiary is not None and beneficiary.group(1) == originator_first) or originator_first == holder_first
        ):
            return True
        if _cut_financing_originator(region):
            return True
        if _TITLE_OR_ESCROW_ORIGINATOR.search(region):
            return True
    return False


def _cut_financing_originator(region: str) -> bool:
    """5.5 (§7.9): an originator that fills its field to within two characters of the width (Santander 16, Bank of
    America 25), whose run-together name starts a financing or potential alias of six or more characters, or whose
    last word of three or more letters is a proper prefix of a financing word."""
    name = region.strip()
    if not any(width - 2 <= len(name) <= width for width in _WIRE_ORIGINATOR_FIELD_WIDTHS):
        return False
    run = name.replace(" ", "")
    if any(
        len(alias) >= 6 and (alias.startswith(run) or run.startswith(alias)) for alias in _FINANCING_RUN_TOGETHER_ALIASES
    ):
        return True
    last = name.split()[-1] if name.split() else ""
    return len(last) >= 3 and last.isalpha() and any(
        word.startswith(last) and word != last for word in _FINANCING_FULL_WORDS
    )
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_revenue_rule_helpers.py -q -p no:cacheprovider`

Expected: PASS: `64 passed`.

- [ ] **Step 5: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-CLASSIFIER: `755 passed, 2 deselected`

- [ ] **Step 6: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/transaction_classifier.py tests/test_revenue_rule_helpers.py
git commit -m "classifier: the 5.5 rule vocabulary and family helpers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S2.3: The 5.5 credit decision

**Files:**
- Create: `tests/test_revenue_card_settlements.py`
- Create: `tests/test_revenue_platform_payouts.py`
- Create: `tests/test_revenue_healthcare_claims.py`
- Create: `tests/test_revenue_payer_remittance.py`
- Create: `tests/test_revenue_public_payers.py`
- Create: `tests/test_revenue_wire_remittance.py`
- Create: `tests/test_revenue_non_revenue_55.py`
- Modify: `analysis/transaction_classifier.py:663-664, 702, 716-729, 813-816, 1928-2116, 2618-2619`
- Modify (pins): `tests/test_revenue_classification.py:63-64, 106-107, 208-209, 228-230, 259-261, 297`
- Modify (pins): `tests/test_analysis.py:3361`
- Modify (pins): `tests/test_webapp_revenue_batch.py:13`
- Modify (pins): `tests/test_webapp_studio_views.py:17, 450`

**Depends on:** S2.2.

**Interfaces:**
- Consumes: S2.1 and S2.2; the classifier's `_RevenueDecision`, `_insurance_registry_match`, `match_known_payee`, `_names_financing`, `_descriptor_proceeds`.
- Produces:
  - `_classify_credit_revenue(...)` (same signature) deciding by §6.1
  - `_operating_source_decision(text, source, *, account_name, bank) -> _RevenueDecision`, `_business_account(account_name) -> bool`, `_fallback_credit_decision(text) -> _RevenueDecision`
  - new revenue methods: `holder_named_payer`, `insurer_customer_payment`, `payer_remittance_descriptor`, `public_payer_remittance`, `wire_remittance_purpose`; matched rules `card_settlement_form_<label>`, `square_capital_credit`, `sba_disbursement_credit`
  - `_CUSTOMER_INVOICE_DESCRIPTORS` (read by the census, G3)

**Why:** Spec §6.1, steps 3 and 5 to 16, as §7 amends them: the return codes, REIMBURSEMENT and the card-credit release (step 3); the insurer registry with claim first (T18) and the customer-payment hold (T14, step 5); `SQ CAP` and SBA/EIDL as financing proceeds (step 7, T5); the narrowed own-account rule for book and funds transfers (T19) and the new strong non-revenue markers (step 9); the channel gate (9b); the operating registry with its forms, vetoes and cuts (10); the card forms and the narrowed customer and invoice descriptors, refused to a holder or numbered payer (11); accounts-payable remittance (12), public payers (13) and invoice wires (14). R-d's own-account designation (`prints_internal_transfer_designation`) follows the narrowed rule. After the review: the glued tax refunds (`CASTTAXRFD`, `TAXEIC`) join T5 (I6), and the wire tests carry §14.1's §7.9 list (I5): the wire verifier's 40 cases, the false-revenue reviewer's hazard groups G1 to G11 and its party-name rows, and the recorded residuals. The four family tests that need the statement passes join in S2.4.

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_revenue_card_settlements.py`:

```python
"""Classification 5.5 (true revenue spec §7.0, §7.1): card-processor settlements, the card veto, the processor payout
context and the processor registry additions. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis.classification_registry import (
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_TRUNCATIONS,
    PROCESSOR_ADVANCE_PRODUCTS,
    PROCESSORS_WITHOUT_ADVANCE_PRODUCT,
)
from analysis.transaction_classifier import classify_transaction


def _credit(printed: str, *, holder: str | None = None, bank: str | None = None, amount: float = 250.0):
    return classify_transaction(printed, amount, account_name=holder, bank=bank, direction="credit")


@pytest.mark.parametrize(("printed", "label"), [
    ("MERCHANT BANKCD DES:DEPOSIT ID:123456 INDN:FABRIKAM BAKERY CO ID:1234567890 CCD", "bankcard"),
    ("Orig CO Name:Merchant Bankcd Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Merch Depsec:CCD Trace#:1",
     "bankcard"),
    ("01/02Bankcard Deposit 123456", "bankcard"),
    ("BKCD DEPST 1234567", "bankcard"),
    ("BANKCARD BTOT DEP 123456", "bankcard"),
    ("FABRIKAM MERCH DEP 1234567", "merch_dep"),
    ("MERCH SETL 1234567 FABRIKAM", "merch_dep"),
    ("MERCH SVCS DEP 1234567", "merch_dep"),
    ("CO ENTRY DESCR MRCHNTSRVS SEC CCD", "mrchntsrvs"),
    ("MERCHANT SVCS DES 123SETL ID:1", "merch_svcs_setl_code"),
    ("MERCHANT SERVICES MID 1234567 FABRIKAM", "merchant_services_mid"),
    ("VSA DEP12345678", "brand_dep"),
    ("MC DEP 12345678", "brand_dep"),
    ("MISC PAYMENT VSA DEP12345678 FABRIKAM SOLUTIONS", "brand_dep"),
    ("MC VI DEP SAMPLE MERCH SVC FABRIKAM", "brand_dep"),
    ("DEP VSA12345678 DIV", "dep_brand"),
    ("COMPTE DIVERS DEP VSA12345678", "dep_brand"),
    ("MISC PAYMENT 1234567 VISA GBL VI 1234", "gbl_brand"),
    ("BTOT DEP 123456", "batch_total"),
    ("INTUIT 12345678 DES:DEPOSIT ID:1", "intuit_deposit"),
    ("AMERICAN EXPRESS DES:SETTLEMENT ID:1", "network_settlement"),
    ("VISA MC DEPOSIT 1234", "generic_card_sales"),
    ("FABRIKAM CAFE CREDIT CARD DEPOSIT 1234", "generic_card_sales"),
    ("REGLEMENT MARCHAND 1234", "french_card_settlement"),
])
def test_each_card_settlement_form_verifies_one_row(printed, label):
    record = _credit(printed)
    assert record.revenue_classification == "verified_revenue", record.revenue_match_method
    assert record.revenue_matched_rule in (f"card_settlement_form_{label}", "verified_operating_source_credit")


def test_a_form_names_its_processor_and_records_its_label():
    record = _credit("MISC PAYMENT 1234567 IDP GBL IDP1234")
    assert (record.revenue_canonical_entity, record.revenue_matched_alias) == ("Global Payments", "gbl_brand")
    square = _credit("CARD PAYMENT SALES", bank="Square")
    assert (square.revenue_classification, square.revenue_canonical_entity) == ("verified_revenue", "Square")
    assert _credit("CARD PAYMENT SALES", bank="Sample Bank").revenue_classification == "unverified_deposit"


@pytest.mark.parametrize("printed", [
    "FABRIKAM BANKCARD LLC DES:ADV ID:1",
    "FABRIKAM BANKCARD LLC DES:DEPOSIT ID:1",
    "MISC PAYMENT FABRIKAM CAP ADV",
    "TRANSFER FROM SV01",
    "BANKCARD DEP CB REV",
    "OWNER CONTRIB MERCH DEP",
    "ELAN BANKCARD SETTLEMENT CREDIT",
    "VISA DEP JOHN SMITH",
    "CREDIT CARD DEPOSIT 1234",            # every word generic: no payer printed, closed by the channel gate
    "CAPITAL ONE CREDIT CARD DEPOSIT 1234",  # a card issuer is named
    "MOBILE DEP VISA",
    "MERCHANT SERVICES DEPOSIT FABRIKAM",
    "STRIPE DES:CLAIM PAYM ID:ST-A1B2C3D4E5",
    "INTUIT 12345678 DES:TAX RFND ID:1",
])
def test_the_verifiers_negatives_never_verify(printed):
    assert _credit(printed).revenue_classification != "verified_revenue"


@pytest.mark.parametrize("printed", [
    "FABRIKAM LAW GROUP DES:NET SETTLE ID:1",
    "Orig CO Name:Fabrikam Title Co Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Net Settlesec:CCD Trace#:1",
])
def test_net_settle_from_a_law_or_title_firm_never_verifies(printed):
    assert _credit(printed).revenue_classification == "unverified_deposit"


@pytest.mark.parametrize(("printed", "entity", "state"), [
    ("HRTLAND PMT SYS TXNS", "Heartland Payment Systems", "unverified_deposit"),  # recurrence decides it
    ("SPOTON VIA ASTRA SETTLEMENT", "SpotOn", "verified_revenue"),
    ("CLEARENT LLC DES:SETTLEMENT ID:1", "Clearent", "verified_revenue"),
    ("SHIFT4 PAYMENTS DES:PAYOUT ID:1", "Shift4", "verified_revenue"),
    ("SMARTTAB PAY DES:BKCD DEP ID:1", "SmartTab", "verified_revenue"),
    ("TGPAYMENTS DES:SETTLEMENT ID:1", "TapGoods Payments", "verified_revenue"),
    ("TRYCENTS COM DES:PAYOUT ID:1", "Cents", "verified_revenue"),
    ("MISC PAYMENT 12345678901 DP FIRST DATA CANADA J 12", "Fiserv", "verified_revenue"),
])
def test_the_processor_registry_additions_name_the_processor(printed, entity, state):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_canonical_entity) == (state, entity)


@pytest.mark.parametrize(("processor", "printed"), [
    ("Shift4", "SHIFT4 DES:DEPOSIT ID:1"),
    ("SumUp", "SUMUP DES:PAYOUT ID:1"),
    ("Braintree", "BRAINTREE DES:PAYOUT ID:1"),
])
def test_a_bare_processor_name_waits_for_its_advance_product(processor, printed):
    # §7.1: the bare name reads as the processor only once the lender ledger admits its advance product, or records
    # that it has none (Task S1.5); until then it names no source.
    _bare, product = PROCESSOR_ADVANCE_PRODUCTS[processor]
    cleared = product is not None or processor in PROCESSORS_WITHOUT_ADVANCE_PRODUCT
    assert (_credit(printed).revenue_canonical_entity == processor) is cleared


def test_the_sixteen_character_cuts_are_read():
    assert "FIRST DATA MERCH" in OPERATING_REVENUE_TRUNCATIONS["Fiserv"]
    assert "QUICKBOOKS PAYME" in OPERATING_REVENUE_READ_ALIASES["QuickBooks Payments"]
    record = _credit("FIRST DATA MERCH DES:SETTLEMENT ID:1")
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("verified_revenue", "Fiserv")


def test_stripe_connect_s_cut_reads_as_stripe():
    record = _credit("FABRIKAM - BY STRI DES:PAYOUT ID:1")
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("verified_revenue", "Stripe")


def test_a_waiting_processor_s_row_never_reads_as_stripe():
    # §7.1, review I4: JOBBER BY STRI is Jobber Payments' bare alias, which waits for Jobber Capital in the ledger;
    # Stripe's BY STRI cut inside it never reads the row while Jobber waits.
    _bare, product = PROCESSOR_ADVANCE_PRODUCTS["Jobber Payments"]
    cleared = product is not None or "Jobber Payments" in PROCESSORS_WITHOUT_ADVANCE_PRODUCT
    record = _credit("JOBBER BY STRI DES:TRANSFER ID:ST-A1B2C3D4E5F6")
    assert record.revenue_canonical_entity == ("Jobber Payments" if cleared else None)
    assert record.revenue_classification == ("verified_revenue" if cleared else "unverified_deposit")


def test_the_french_merchant_deposit_verifies_through_global_payments():
    # §7.1, review M3: DEPOT MARCHAND is a card settlement, never a branch deposit.
    record = _credit("DEPOT MARCHAND GLOBAL PAIEMENTS 1234567", bank="Desjardins")
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("verified_revenue", "Global Payments")


@pytest.mark.parametrize(("printed", "verified"), [
    ("SQUARE INC DES:SQ540115 ID:1", True),          # a Square payout id is processor payout context
    ("STRIPE DES:TRANSFER ID:ST-A1B2C3D4E5F6", True),  # Stripe's ST- payout id
    ("PAYPAL DES:MSP DIV ID:1", False),               # never for a customer-payment platform
    ("SQUARE INC DES:CHARGEBACK SQ540115 ID:1", False),  # the card veto refuses the context
])
def test_the_processor_payout_context(printed, verified):
    assert (_credit(printed).revenue_classification == "verified_revenue") is verified
```

Create `tests/test_revenue_platform_payouts.py`:

```python
"""Classification 5.5 (true revenue spec §7.2, §7.3): marketplace, platform and transport payouts: the payout forms,
the new aliases and the vetoes on every new read. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction


def _credit(printed: str, *, holder: str | None = None, amount: float = 250.0, direction: str = "credit"):
    return classify_transaction(printed, amount, account_name=holder, direction=direction)


def _statement(rows, *, holder: str | None = None):
    return classify_statement_transactions(Statement(account_name=holder, transactions=[
        Transaction(date=f"2054-03-{day:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for day, text, amount in rows
    ]))


@pytest.mark.parametrize(("printed", "entity", "label"), [
    ("STP FBO WHATNOT INC FROM WHATNOT INC", "Whatnot", "whatnot_fbo_form"),
    ("RTP CREDIT WHATNOT INC SOUTH SAN FRANCISCO", "Whatnot", "whatnot_rtp_form"),
    ("FAIRE WHOLESALE ORDER 1234567", "Faire", "faire_order_form"),
    ("PAYMENTS EBAY COMN1ERKWVF FABRIKAM", "eBay", "ebay_payments_form"),
    ("RTP CREDIT EBAY COMMERCE INC", "eBay", "ebay_rtp_form"),
    ("AMAZON CK12AB34C PAYMENTS 1234", "Amazon Marketplace", "amazon_payments_form"),
    ("CLASSPASS INC DES:EDI PYMNTS ID:1", "ClassPass", "classpass_edi_form"),
    ("PAYONEER 1234 EZCATER PAYMENT STORE", "ezCater", "ezcater_payoneer_form"),
    ("Orig CO Name:Grpn Merch Svcs Orig ID:1234567890 Desc Date: CO Entry Descr:Payment Sec:CCD", "Groupon",
     "groupon_merchant_form"),
])
def test_a_payout_form_names_the_platform_and_verifies_one_row(printed, entity, label):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("verified_revenue", entity)
    assert record.revenue_matched_alias == label
    assert label in record.revenue_reason and "\\b" not in record.revenue_reason


@pytest.mark.parametrize(("printed", "entity"), [
    ("TIKTOK INC DES:PAYMENT ID:1234", "TikTok Shop"),
    ("CORPORATE ACH SNACKPASS 12345 SNACKPASS ST", "Snackpass"),
    ("FIELDPULSE ACH IN", "FieldPulse"),
    ("VAGARO MERCHANT ACH IN", "Vagaro"),
    ("Orig CO Name:Outdoorsy Orig ID:1234567890 Desc Date: CO Entry Descr:Payment Sec:CCD", "Outdoorsy"),
    ("RTP CREDIT AMAZON COM 1234", "Amazon Marketplace"),
])
def test_an_alias_without_a_form_needs_recurrence(printed, entity):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("unverified_deposit", entity)
    assert record.revenue_match_method == "operating_source_requires_context"


def test_three_alias_rows_verify_by_recurrence():
    records = _statement([(2, "RTP CREDIT AMAZON COM 1234", 400.0), (9, "RTP CREDIT AMAZON COM 5678", 410.0),
                          (16, "RTP CREDIT AMAZON COM 9012", 420.0)])
    assert {record.revenue_match_method for record in records} == {"recurring_operating_source"}


@pytest.mark.parametrize("printed", [
    "WHATNOT INC DES:PAYROLL ID:1",
    "WHATNOT INC DES:DIR DEP ID:1",
    "WHATNOT INC PAYRLL 1234",
    "FAIRE WHOLESALE ORDER 1234 LOAN",
    "FAIRE WHOLESALE ORDER 1234 ADVANCE",
    "CLASSPASS INC DES:EDI PYMNTS REFUND ID:1",
    "CLASSPASS INC DES:EDI PYMNTS RTN ID:1",
    "AMAZON CAPITALSV PAYMENTS 1234",
    "AMAZON COMSERVIC PAYMENTS 1234",
    "PAYMENTS EBAY COMN1ERKWVF RETURN",
    "TIKTOK INC DES:DIR DEP ID:1",
    "TIKTOK SHOP 1234567 CULVER CITY CA",
    "ZELLE PAYMENT FROM FABRIKAM FOR WHATNOT INC CONF 99",
])
def test_the_vetoes_of_every_new_read(printed):
    record = _credit(printed)
    assert record.revenue_classification != "verified_revenue"
    assert record.revenue_match_method not in ("operating_source_with_credit_context", "operating_source_requires_context")


def test_three_super_dispatch_payouts_verify_and_one_does_not():
    rows = [(day, "123456789 FROM SUPER DISPATCH INC REF NOREF", 900.0 + day) for day in (2, 9, 16)]
    assert {record.revenue_match_method for record in _statement(rows)} == {"recurring_operating_source"}
    assert _statement(rows[:1])[0].revenue_classification == "unverified_deposit"
```

Create `tests/test_revenue_healthcare_claims.py`:

```python
"""Classification 5.5 (true revenue spec §7.7, T18): healthcare claim payments, the NACHA entry glued on either side,
and the claim-first switch. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.transaction_classifier import classify_transaction


def _credit(printed: str):
    return classify_transaction(printed, 250.0, direction="credit")


@pytest.mark.parametrize("printed", [
    "Orig CO Name:Fabrikam Health Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Hcclaimpmt Sec:CCD Trace#:1",
    "Orig CO Name:Fabrikam Health Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Hcclaimpmtsec:CCD Trace#:1",
    "FABRIKAM HEALTH PHCCLAIMPMT 1234567 TRN 1*123",
    "123456789 HCCLAIMPMT 1234567",
    "FABRIKAM HLTH DES:HECLAIMPMT ID:1",
])
def test_the_nacha_claim_entry_verifies_glued_or_spaced(printed):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_match_method) == (
        "verified_revenue", "operating_income_descriptor")


@pytest.mark.parametrize("printed", [
    "FABRIKAM HEALTHHCLAIMPMT 1234567",
    "FABRIKAM HEALTH DES:HCCLAIMPMT0001 ID:1",
    "FABRIKAM HEALTH DES:HHSPAYMENTSEC ID:1",
    "ASSURANCE OF THECLAIMPMT 123456789 CLAIM 123",
    "Orig CO Name:Fabrikam Health Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Theclaimpmt Sec:CCD",
])
def test_a_token_that_is_not_the_nacha_entry_stays_unverified(printed):
    assert _credit(printed).revenue_classification == "unverified_deposit"


def test_a_blue_plan_claim_verifies_with_claim_first_on(monkeypatch):
    printed = "Orig CO Name:BCBSM Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Hcclaimpmtsec:CCD Trace#:1"
    monkeypatch.setattr(transaction_classifier, "HCCLAIMPMT_CLAIM_FIRST", True)
    assert _credit(printed).revenue_classification == "verified_revenue"
    monkeypatch.setattr(transaction_classifier, "HCCLAIMPMT_CLAIM_FIRST", False)
    held = _credit(printed)
    assert (held.revenue_classification, held.revenue_match_method) == (
        "unverified_deposit", "insurer_customer_payment")
    # Off, an alias-escaping Blue-plan spelling is held with the insurer's credits too.
    spaced = _credit("BCBSF HCCLAIMPMT 123456 123456789012345")
    assert (spaced.revenue_classification, spaced.revenue_match_method) == (
        "unverified_deposit", "insurer_customer_payment")


def test_a_funder_glued_to_the_claim_entry_stays_financing_proceeds():
    record = _credit("RAPID FINANCE HCCLAIMPMT 1234567")
    assert (record.revenue_classification, record.revenue_match_method) == (
        "non_revenue", "financing_proceeds_credit")


@pytest.mark.parametrize("printed", [
    "FABRIKAM HEALTH DES:HCCLAIMPMT MERCHANT CASH ADVANCE ID:1",
    "FABRIKAM HEALTH DES:HCCLAIMPMT LOAN PROCEEDS ID:1",
])
def test_a_claim_entry_with_financing_words_stays_non_revenue(printed):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_match_method) == ("non_revenue", "strong_non_revenue_rule")


def test_an_insurer_s_customer_payment_leaves_non_revenue_for_review():
    record = _credit("STATE FARM DES:DRP PAYMENT ID:1")
    assert (record.revenue_classification, record.revenue_match_method) == (
        "unverified_deposit", "insurer_customer_payment")
    assert _credit("STATE FARM DES:CLAIM PAYMT ID:1").revenue_classification == "non_revenue"
```

Create `tests/test_revenue_payer_remittance.py`:

```python
"""Classification 5.5 (true revenue spec §7.5): the payer's accounts-payable remittance, its free-text gate, its veto,
the numbered-company and holder refusals, and the counter-debit guard. Fabricated rows only."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction


def _credit(printed: str, *, holder: str | None = "SAMPLE CAFE LLC"):
    return classify_transaction(printed, 1200.0, account_name=holder, direction="credit")


@pytest.mark.parametrize("printed", [
    "FABRIKAM SUPPLY DES:ACCTS PAYABLE ID:1",
    "FABRIKAM SUPPLY DES:ACCOUNTS PAYABLE ID:1",
    "FABRIKAM SUPPLY DES:A P PMTS ID:1",
    "Orig CO Name:Fabrikam Supply Orig ID:1234567890 Desc Date:540102 CO Entry Descr:A P Sec:CCD",
    "FABRIKAM SUPPLY DES:CCDACC PAY ID:1",
    "FABRIKAM SUPPLY DES:VENDOR PAY ID:1",
    "Orig CO Name:Fabrikam Supply Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Vendor Pmtsec:CCD",
    "FABRIKAM SUPPLY DES:TRADE PAY ID:1",
    "FABRIKAM SUPPLY DES:PAYABLES ID:1",
    "FABRIKAM SUPPLY DES:PO REMITTANCE ID:1",
    "FABRIKAM SUPPLY AVIDPAY 1234",
    "FABRIKAM SUPPLY DES:PAYMODE ID:1",
    "RAMP FABRIKAM SUPPLY PAYING BILL 1234",
    "FABRIKAM SUPPLY FOR 3 BILLS",
    "FABRIKAM SUPPLY BILL COM INV 1234",
    "FABRIKAM SUPPLY DES:INVOICE PMT ID:1",
    "FABRIKAM SUPPLY PAYMENT OF INVOICES",
    "FABRIKAM SUPPLY DES:CORP PAY ID:1 RMR IV 1234",
    "FABRIKAM SUPPLY ACH PMT INV 1234",
    "FABRIKAM SUPPLY PAIEMENT DE FACTURE 1234",
])
def test_the_payer_remittance_forms_verify(printed):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_match_method) == (
        "verified_revenue", "payer_remittance_descriptor")


@pytest.mark.parametrize("printed", [
    "FABRIKAM FUNDING LLC DES:VENDOR PAY ID:1",
    "FABRIKAM CAPI DES:VENDOR PAY ID:1",
    "FABRIKAM FUN DES:VENDOR PAY ID:1",
    "FABRIKAM FINA DES:VENDOR PAY ID:1",
    "FABRIKAM FINAN DES:VENDOR PAY ID:1",
    "FABRIKAM LOA DES:VENDOR PAY ID:1",
    "FABRIKAM LEASIN DES:VENDOR PAY ID:1",
    "FABRIKAM CAP ADVANTAG DES:VENDOR PAY ID:1",
    "BIZ2CREDIT DES:VENDOR PAY ID:1",
    "FABRIKAM MOTORS DES:PAYABLES ID:1 VIN 1234",
    "FABRIKAM INSURANCE DES:VENDOR PAY ID:1",
    "FABRIKAM HOLDINGS DES:INTERCOMPANY ID:1 VENDOR PAY",
    "ZERO BALANCE TRANSFER CREDIT A P PAYMENTS",
    "ACH RTN VENDOR PAY 1234 R03",
    "BILL COM DES:PAYABLES ID:1",
    "ZELLE PAYMENT FROM JOHN SMITH MEMO PAYING BILLS 1 CONF 99",
    "ZELLE PAYMENT FROM JOHN SMITH INVOICE 1234 CONF 99",
    "DEPOSIT INV 1234",
    "REMOTE ONLINE DEPOSIT 1 INVOICE 55",
    "ONLINE TRANSFER FROM INV 1234567",
])
def test_the_negatives_never_verify(printed):
    assert _credit(printed).revenue_classification != "verified_revenue"


@pytest.mark.parametrize("printed", [
    "DIRECT DEPOSIT 7654321 CANA AP CC",
    "1234567 NOVA SCOTIA LTD DES:VENDOR PAY ID:1",
    "7654321 NEW BRUNSWICK INC DES:PAYMENT ID:1",
])
def test_a_numbered_company_never_verifies(printed):
    assert _credit(printed).revenue_classification == "unverified_deposit"


def test_the_holder_s_own_name_never_verifies():
    record = _credit("CONTOSO BAKERY LLC DES:VENDOR PAY ID:1", holder="CONTOSO BAKERY LLC")
    assert (record.revenue_classification, record.revenue_match_method) == ("unverified_deposit", "holder_named_payer")
```

Create `tests/test_revenue_public_payers.py`:

```python
"""Classification 5.5 (true revenue spec §7.6, T12): public-payer remittances, arms A and B, the payer anchored on the
payer name, every veto group, and the duplicate and reversal passes that still win. Fabricated rows only."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction


def _credit(printed: str, *, holder: str | None = "CONTOSO CLINIC LLC"):
    return classify_transaction(printed, 1400.0, account_name=holder, direction="credit")


@pytest.mark.parametrize(("printed", "rule"), [
    ("TREAS 310 DES:DOD MISC ID:1 CCD", "treasury_vendor_payment"),
    ("Orig CO Name:Treas 310 Orig ID:1 Desc Date: CO Entry Descr:Misc Paysec:CCD Trace#:1 RMR IV 1234",
     "treasury_vendor_payment"),
    ("SAMPLE COUNTY DES:VENDOR PAY ID:1", "public_payer_vendor_or_provider_payment"),
    ("STATE OF OHIO DES:PROV PAY ID:1", "public_payer_vendor_or_provider_payment"),
    ("DEPT OF HEALTH SERVICES DES:EDI PYMNTS ID:1", "public_payer_vendor_or_provider_payment"),
    ("SCHOOL DISTRICT 12 DES:VENDOR PMT ID:1", "public_payer_vendor_or_provider_payment"),
    ("ACH CORP CREDIT CITY OF SAMPLEVILLE VEN PAYMENTS 1234", "public_payer_vendor_or_provider_payment"),
    ("SAMPLE COUNTY DES:VENDOR PAY ADDITIONAL INFORMATION IS AVAILABLE FOR THIS PMT CONTACT A TREASURY SALES "
     "OFFICER FOR ASSISTANCE", "public_payer_vendor_or_provider_payment"),
])
def test_each_arm_verifies(printed, rule):
    record = classify_transaction(printed, 1400.0, account_name="CONTOSO CLINIC", direction="credit")
    assert record.revenue_classification == "verified_revenue"
    assert record.revenue_matched_rule in (rule, "verified_payer_accounts_payable_remittance")


def test_a_county_printed_after_the_payer_is_not_the_payer():
    record = _credit("FABRIKAM PLUMBING DES:VENDOR PAY ID:1 SAMPLE COUNTY")
    assert record.revenue_match_method != "public_payer_remittance"


@pytest.mark.parametrize("printed", [
    "TREAS 310 DES:DOD MISC ID:1 PPD",                               # a consumer entry
    "TRANSFER FROM COUNTY LINE SUPPLY VENDOR PAY",                   # a transfer, and COUNTY LINE is no public payer
    "STATE OF OHIO FUNDING DES:VENDOR PAY ID:1",                     # a financing name
    "STATE OF OHIO DES:VENDOR PAY GRANT ID:1",
    "STATE OF OHIO DES:VENDOR PAY TAX REFUND ID:1",
    "STATE OF OHIO DES:VENDOR PAY STIMULUS ID:1",
    "STATE OF OHIO DES:VENDOR PAY CHILD SUPPORT ID:1",
    "STATE OF OHIO DES:VENDOR PAY CLAIMS ID:1",
    "STATE OF OHIO DES:VENDOR PAY SETTLEMENT ID:1",
    "STATE OF OHIO DES:VENDOR PAY ASSISTANCE ID:1",
    "COMPTROLLER OF MD DES:MDREFUND ID:1",
    "IRS TREAS 310 DES:TAX EIC ID:1",
])
def test_a_veto_or_an_unanchored_payer_never_verifies(printed):
    assert _credit(printed).revenue_classification != "verified_revenue"


def test_a_label_less_holder_name_never_supplies_the_public_payer():
    # Wells Fargo prints the receiver with no label: the holder's own words must not make the payer public.
    record = _credit("FABRIKAM SUPPLY VENDOR PAY 540115 SAMPLE COUNTY PLUMBING", holder="SAMPLE COUNTY PLUMBING")
    assert record.revenue_match_method != "public_payer_remittance"


def test_a_verified_public_payment_is_still_demoted_by_a_duplicate_and_a_returned_item():
    duplicate = classify_statement_transactions(Statement(account_name="CONTOSO CLINIC", transactions=[
        Transaction(date="2054-03-02", description="SAMPLE COUNTY DES:VENDOR PAY ID:1", amount=1400.0,
                    direction="credit", running_balance=5400.0),
        Transaction(date="2054-03-02", description="SAMPLE COUNTY DES:VENDOR PAY ID:1", amount=1400.0,
                    direction="credit", running_balance=5400.0),
    ]))
    assert [record.revenue_classification for record in duplicate] == ["verified_revenue", "non_revenue"]
    returned = classify_statement_transactions(Statement(account_name="CONTOSO CLINIC", transactions=[
        Transaction(date="2054-03-02", description="SAMPLE COUNTY DES:VENDOR PAY ID:1", amount=1400.0,
                    direction="credit"),
        Transaction(date="2054-03-04", description="RETURNED ITEM SAMPLE COUNTY VENDOR PAY", amount=-1400.0,
                    direction="debit"),
    ]))
    assert returned[0].revenue_classification == "non_revenue"
```

Create `tests/test_revenue_wire_remittance.py`:

```python
"""Classification 5.5 (true revenue spec §7.9, T19): incoming wires whose remittance cites an invoice, a PO, an order
or goods; the channel, the purposes, every veto; third-party book transfers read as incoming wires. Fabricated rows
only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction

BOFA = ("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:20540102001234 SEQ:1234/5678 ORIG:{orig} ID:99887766 "
        "SND BK:SAMPLE BANK ID:0123 PMT DET:{purpose}")
CHASE = "FEDWIRE CREDIT VIA: SAMPLE BANK/0123 B/O: {orig} REF: CHASE NYC/CTR/BNF=CONTOSO LLC /OBI={purpose} IMAD: 1"


def _credit(printed: str, *, holder: str | None = "CONTOSO TRADING LLC"):
    return classify_transaction(printed, 25000.0, account_name=holder, direction="credit")


@pytest.mark.parametrize("purpose", [
    "INVOICE 1234", "INV 5678", "INVOIC E 1234", "PO 45210", "PURCHASE ORDER 88", "ORDER NO 1234", "FACTURA 12",
    "PAGO PROVEEDOR", "PAYMENT FOR GOODS", "PRO FORMA 12",
])
def test_an_incoming_wire_citing_a_sale_verifies(purpose):
    for layout in (BOFA, CHASE):
        record = _credit(layout.format(orig="FABRIKAM EXPORTS LLC", purpose=purpose))
        assert record.revenue_classification == "verified_revenue", (layout[:20], purpose)
        assert record.revenue_match_method in ("wire_remittance_purpose", "payer_remittance_descriptor")


@pytest.mark.parametrize(("orig", "purpose"), [
    ("FABRIKAM CAPITAL LLC", "INVOICE 1234"),         # a financing root
    ("FABRIKAM CAPI TAL", "INVOICE 1234"),            # wrapped across a line
    ("FABRIKAM FUN DING", "INVOICE 1234"),
    ("FABRIKAM EXPORTS LLC", "INVOICE 1234 ADJ"),     # an adjustment
    ("FABRIKAM EXPORTS LLC", "INVOICE 1234 INVESTMENT"),
    ("FABRIKAM EXPORTS LLC", "RETURN INVOICE 1234"),
    ("CONTOSO HOLDINGS LLC", "INVOICE 1234"),         # the holder's brand word: an affiliate
    ("FABRIKAM EXPORTS LLC", "MONEY ORDER 1234"),     # not an order number
    ("FABRIKAM EXPORTS LLC PO 4521", "PAYMENT"),       # a PO number in the originator's address is no purpose
])
def test_the_wire_vetoes(orig, purpose):
    assert _credit(BOFA.format(orig=orig, purpose=purpose)).revenue_classification != "verified_revenue"


def test_a_wire_from_a_person_citing_an_invoice_verifies_and_other_channels_do_not():
    assert _credit(BOFA.format(orig="JOHN SMITH", purpose="INVOICE 1234"), holder=None).revenue_classification == (
        "verified_revenue")
    assert _credit("ZELLE PAYMENT FROM JOHN SMITH MEMO WIRE INVOICE 1234 CONF 1").revenue_classification != (
        "verified_revenue")
    assert _credit("UNKNOWN WIRE CREDIT").revenue_classification == "unverified_deposit"


def test_a_returned_wire_is_never_revenue():
    records = classify_statement_transactions(Statement(account_name="CONTOSO TRADING LLC", transactions=[
        Transaction(date="2054-03-02", description="WIRE TRANSFER OUT FABRIKAM EXPORTS LLC INVOICE 1234",
                    amount=-25000.0, direction="debit"),
        Transaction(date="2054-03-04", description=BOFA.format(orig="FABRIKAM EXPORTS LLC", purpose="RTN INVOICE 1234"),
                    amount=25000.0, direction="credit"),
    ]))
    assert records[1].revenue_classification == "non_revenue"


BOOK = "BOOK TRANSFER CREDIT B/O: {orig} SAMPLEVILLE ST 12345 REF: {purpose}"


def test_a_third_party_book_transfer_is_an_incoming_wire_on_the_owner_s_yes(monkeypatch):
    third_party = BOOK.format(orig="FABRIKAM EXPORTS LLC", purpose="INVOICE 1234")
    own = BOOK.format(orig="CONTOSO TRADING LLC", purpose="INVOICE 1234")
    monkeypatch.setattr(transaction_classifier, "THIRD_PARTY_BOOK_TRANSFER_AS_WIRE", True)
    assert _credit(third_party).revenue_classification == "verified_revenue"
    assert _credit(own).revenue_classification == "non_revenue"
    assert _credit("BOOK TRANSFER CREDIT").revenue_classification == "non_revenue"
    monkeypatch.setattr(transaction_classifier, "THIRD_PARTY_BOOK_TRANSFER_AS_WIRE", False)
    assert _credit(third_party).revenue_classification == "non_revenue"


def test_an_incoming_funds_transfer_names_its_sender():
    record = _credit("FUNDS TRANSFER CREDIT TT FABRIKAM EXPORTS LLC REF INVOICE 1234")
    assert record.revenue_classification == "verified_revenue"
    assert _credit("FUNDS TRANSFER FROM SAVINGS 1234").revenue_classification == "non_revenue"


# ---------------------------------------------------------------------------------------------------------------------
# §14.1 (§7.9, review I5): the wire verifier's 40 cases, the false-revenue reviewer's hazard groups G1 to G11 and its
# four party-name rows, and the wire verifier's adversarial rows, transcribed (fabricated names, numbers and amounts;
# the banks' layouts kept). Each is one credit in a statement of its own.
# ---------------------------------------------------------------------------------------------------------------------
FEDWIRE = ("Fedwire Credit Via: Sample Bank/123456789 B/O: {orig} Ref: Chase Nyc/Ctr/Bnf={bnf} Tampa FL 33602 "
           "US/Ac-000012345678 Rfb=Notprovided Obi=/Uri/{obi} Imad: 0105Mmqfmp2B000123 Trn: 1234567890Ff")
BOFA_IN = ("WIRE TYPE:WIRE IN DATE: 540105 TIME:1012 ET TRN:2054010500123456 SEQ:2054010500654321/004512 "
           "ORIG:{orig} ID:1234567890 SND BK:{bank} ID:021000021 PMT DET:{det}")
SANTANDER = "USD WIRE IN FROM {bank} ACCT * 1234 {orig} REF {ref}"
WELLS = "WT Fed#01234 {bank} /Org={orig} Srf# 0123456789Mfp0123 Trn#0123456789 Rfb# {ref}"


def _one(bank: str, holder: str, printed: str):
    [record] = classify_statement_transactions(Statement(
        bank=bank, account_name=holder, account_number="XXXX1234", period_start="2054-01-01",
        period_end="2054-01-31", beginning_balance=1000.0, ending_balance=13345.0,
        transactions=[Transaction(date="2054-01-05", description=printed, amount=12345.0, direction="credit",
                                  running_balance=13345.0)]))
    return record


def _outcome(record) -> str:
    return {"verified_revenue": "verified", "non_revenue": "non_revenue"}.get(record.revenue_classification, "stays")


FORTY = [
    ("verified", "Bank of America", "FABRIKAM FOODS LLC",
     BOFA_IN.format(orig="CONTOSO TRADING INTL", bank="SAMPLE NATIONAL BANK, NA", det="BMG OF 01/05/54 INV10421,10422")),
    ("verified", "Bank of America", "FABRIKAM FOODS LLC",
     BOFA_IN.format(orig="NORTHWIND HARBOR SUITES", bank="SAMPLE CREDIT UNION", det="INVOICE: NW204 MAINTEN ANCE")),
    ("verified", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Supply LLC 12345, US", bnf="Northwind Labs, LLC", obi="Invoice S104")),
    ("verified", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso For Congress Denver CO 80202", bnf="Northwind Media LLC", obi="Invoic E No.: 10421")),
    ("verified", "Chase", "BUSINESS COMPLETE CHECKING",
     "Chips Credit Via: Sample Bank, N.A./0959 B/O: Contoso Marketing Management,Llsampleville CO 80000 Ref: "
     "Nbnf=Northwind Consulting LLC Sampleton FL 33000-1234 US/Ac-000012345678 Org=/000012345678901 Sampleville CO "
     "80000 Ogb=Sample Merchants Bank, N.A. San Francisco CA US Obi=/Uri/Inv Oices 10421 And 10422 Paid "
     "Ssn: 00123456 Trn: 1234567890Fc"),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO DE CREDIT", orig="CONTOSO SRL", ref="/INV/10421/54")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK EUROPE", orig="CONTOSO GROUP SP", ref="PO 4521")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="SAMPLE NBD BANK PJ", orig="CONTOSO GENERAL", ref="Payment for goo")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE SAN J", orig="CONTOSO COSTA", ref="BALANCE ORDER 2")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE S.", orig="CONTOSO TRADING", ref="PAGO PROVEEDOR")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE CONTIN", orig="CONTOSO SRL", ref="/INV/OP.123456789012")),
    # §7.9 drops the bare 'PI <digits>' pro-forma form: the verifier's positive stays unverified.
    ("stays", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE PICHIN", orig="CONTOSO CIA", ref="PI 10421")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE S.A.", orig="CONTOSO ARCHO", ref="COMPRA MERCADE")),
    ("stays", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE S.A.", orig="CONTOSO LENDING SA", ref="/INV/OP.123456789012")),
    ("verified", "Capital One", "FABRIKAM LLC", "Wire transfer deposit CONTOSO GROUP LLC 540105 INV 10421"),
    ("verified", "CIBC", "FABRIKAM LTD", "WIRE TSF 1234567 CONTOSO FROZEN FOODS LTD INV-1042-54"),
    ("stays", "BMO", "FABRIKAM INC", "Incoming Wire Payment, INCOMING WIRE PAYMENT, CA, 1234567 ONTARIO INC"),
    ("stays", "Bluevine", "FABRIKAM LLC", "Incoming Wire from CONTOSO SUPPLY SER"),
    ("stays", "Citizens Bank", "BUSINESS ADVISOR CHECKING",
     "INCOMING WIRE TRANSFER (MTS NO.123456789012) ORIGINATOR NAME : CONTOSO SPE II LLC ORIG TO BNF INFO: "
     "FED ID# : 20540105MMQFMP2N000123"),
    ("stays", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="SAMPLE ASIA BANK", orig="CONTOSO OVERSEAS", ref="ADVANCE PAYMEN")),
    ("stays", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="SAMPLE THAI BANK", orig="CONTOSO HEALTH", ref="COST OF GOODS")),
    ("stays", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Real Estate Services Ll", bnf="Northwind Development Group LLC",
                    obi="Ref: 1234 Sample Foun Dat Ion Draw")),
    ("stays", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Merchant Funding LLC", bnf="Northwind Grocery Corp", obi="Inv 104211")),
    ("stays", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Capital Partners LLC", bnf="Northwind Freight LLC", obi="Invoice 104211")),
    ("stays", "Wells Fargo", "FABRIKAM LLC",
     "WT Fed#01234 Sample Commercial Bank /Org=1/Contoso Road Capital Management I Srf# 0123456789Mfp0123+ "
     "Trn#0123456789 Rfb# Inv 10421"),
    ("non_revenue", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Bank Loan Dept", bnf="Northwind Trucks LLC", obi="Inv 104211")),
    ("stays", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Northwind Industries LLC Jersey City NJ", bnf="Northwind Industries LLC",
                    obi="Inv 104211")),
    ("stays", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK NA", orig="NORTHWIND TRADING", ref="INV 10421")),
    ("non_revenue", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Supply LLC", bnf="Northwind Labs LLC", obi="Refund Inv 104211")),
    ("stays", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Supply LLC", bnf="Northwind Labs LLC", obi="Return of Overpayment Inv 104211")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO HOLDINGS LP", bank="SAMPLE BANK", det="INV 2054 DISTRIBUTION")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO PROPERTIES LLC", bank="SAMPLE BANK", det="INV 1042 INTEREST")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO PROPERTIES LLC", bank="SAMPLE BANK", det="REPAYMENT INV 1042")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO TENANT LLC", bank="SAMPLE BANK", det="SECURITY DEPOSIT INVOICE 1042")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO SISTER CO LLC", bank="SAMPLE BANK", det="INTERCOMPANY INVOICE 1042")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO LAW PLLC", bank="SAMPLE BANK", det="COURT ORDER 1042")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO SERVICING LLC", bank="SAMPLE TRUST", det="INV 104211")),
    ("stays", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK", orig="CONTOSO FUNDING SPV", ref="ORDER 10421")),
    ("non_revenue", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Kapitus LLC", bnf="Northwind Labs LLC", obi="Inv 104211")),
    # Not a wire: §7.5 verifies an ACH credit that prints an invoice number with its channel word.
    ("verified", "Sample Bank", "FABRIKAM LLC", "ACH CREDIT CONTOSO FOODS INV 10421"),
]


@pytest.mark.parametrize(("expected", "bank", "holder", "printed"), FORTY)
def test_the_wire_verifier_s_forty_cases(expected, bank, holder, printed):
    assert _outcome(_one(bank, holder, printed)) == expected


HOLDER = "NORTHWIND LABS LLC"
#: The false-revenue reviewer's hazard rows: none is revenue whose verification the rules may give.
HAZARDS = [
    ("G1 returned wire /RETN/", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO COMPONENTS LTD", bank="SAMPLE BANK NA", det="/RETN/AC04/ INV 10421")),
    ("G1 RTN", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO COMPONENTS LTD", bank="SAMPLE BANK NA", det="RTN WIRE INV 10421 ACCT CLOSED")),
    ("G1 /REJT/", "Bank of America", HOLDER,
     BOFA_IN.format(orig="SAMPLE BANK ASIA", bank="SAMPLE BANK NA", det="/REJT/AC01/ PO 4521")),
    ("G1 recall", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Components Ltd", bnf="Northwind Labs LLC", obi="Recall Of Payment Invoice 10421")),
    ("G1 RTN on Chase", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Sample Bank", bnf="Northwind Labs LLC", obi="Rtn Inv 104211 Beneficiary Acct Closed")),
    ("G1 RTN on Santander", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK EUROPE", orig="CONTOSO GROUP SP", ref="RTN PO 4521")),
    ("G1 unable to apply", "Wells Fargo", HOLDER,
     WELLS.format(bank="Sample Bank", orig="Contoso Components Ltd", ref="Unable To Apply Inv 10421")),
    ("G1 RETURN word", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO COMPONENTS LTD", bank="SAMPLE BANK NA", det="RETURN INV 10421")),
    ("G2 bank draw", "Bank of America", "NORTHWIND DEVELOPMENT LLC",
     BOFA_IN.format(orig="SAMPLE COMMUNITY BANK", bank="SAMPLE COMMUNITY BANK", det="DRAW 3 INV 10421 PLUMBING")),
    ("G2 draw via title", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Title Agency LLC", bnf="Northwind Development LLC",
                    obi="Draw #4 Invoices 10421 10422")),
    ("G2 drawdown", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK NA", orig="SAMPLE BANK NA", ref="DRAWDOWN PO 4521")),
    ("G3 bank SCF", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CITIBANK NA", bank="CITIBANK NA", det="SCF EARLY PAYMENT INV 10421 10422")),
    ("G3 supply chain", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Sample Bank Na Supply Chain", bnf="Northwind Labs LLC", obi="Invoice 10421 Discounted")),
    ("G3 eCapital", "CIBC", "NORTHWIND LTD", "WIRE TSF 1234567 ECAPITAL CORP INV-1042-54"),
    ("G3 C2FO", "Bank of America", HOLDER, BOFA_IN.format(orig="C2FO", bank="SAMPLE BANK", det="EARLY PAY INV 10421")),
    ("G3 Taulia", "Bank of America", HOLDER,
     BOFA_IN.format(orig="TAULIA INC", bank="SAMPLE BANK", det="INVOICE 10421 EARLY PAYMENT")),
    ("G3 factor named Solutions", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Business Solutions LLC", bnf="Northwind Freight LLC",
                    obi="Inv 10421 10422 10423 Less Fee")),
    ("G4 PI settlement", "Bank of America", "NORTHWIND LAW PLLC IOLTA",
     BOFA_IN.format(orig="CONTOSO MUTUAL CO", bank="SAMPLE BANK", det="PI 104211 J SAMPLE")),
    ("G4 PI claim", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Casualty Co", bnf="Northwind Law Group PLLC", obi="PI 1042119 Sample")),
    ("G5 person goods and services", "Bank of America", HOLDER,
     BOFA_IN.format(orig="JOHN Q SAMPLE", bank="SAMPLE BANK", det="GOODS AND SERVICES")),
    ("G6 sister company", "Bank of America", HOLDER,
     BOFA_IN.format(orig="NORTHWIND HOLDINGS LLC", bank="SAMPLE BANK", det="INV 1042")),
    ("G6 foreign parent", "Chase", "BUSINESS COMPLETE CHECKING",
     "Chips Credit Via: Sample Bank/0959 B/O: Northwind Gmbh Hamburg De Ref: Nbnf=Northwind Labs LLC Tampa FL "
     "33602 US/Ac-000012345678 Org=/DE12345678 Ogb=Sample Bank Ag Obi=/Inv/10421 Ssn: 00123456 Trn: 1234567890Fc"),
    ("G6 Santander one-word holder", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK PANAMA", orig="NORTHWIND LATAM", ref="INVOICE 1042")),
    ("G7 compensation", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK EAST", orig="CONTOSO PACKAGING", ref="COMPENSATION PO 4521")),
    ("G7 price adjustment", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO COMPONENTS LTD", bank="SAMPLE BANK", det="PRICE ADJUSTMENT INV 10421")),
    ("G7 RMA", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO COMPONENTS LTD", bank="SAMPLE BANK", det="RMA 5521 INV 10421")),
    ("G7 deposit back", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK EAST", orig="CONTOSO PACKAGING", ref="DEPOSIT BACK PO 4521")),
    ("G7 shortage", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Foods Inc", bnf="Northwind Grocery Corp", obi="Shortage Inv 10421")),
    ("G8 pay order", "Bank of America", HOLDER,
     BOFA_IN.format(orig="JOHN Q SAMPLE", bank="SAMPLE BANK KARACHI", det="PAY ORDER 104211")),
    ("G8 support order", "Bank of America", HOLDER,
     BOFA_IN.format(orig="JOHN Q SAMPLE", bank="SAMPLE BANK", det="SUPPORT ORDER 104211")),
    ("G8 transfer order", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK", orig="JOHN Q SAMPLE", ref="TRANSFER ORDER 1042")),
    ("G9 payoff surplus", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO BANK", bank="SAMPLE BANK", det="PAYOFF SURPLUS INV 10421")),
    ("G9 bridge note", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO PARTNERS LP", bank="SAMPLE BANK", det="BRIDGE NOTE INV 1")),
    ("G9 SAFE", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO VENTURES LP", bank="SAMPLE BANK", det="SAFE INV 2 OF 3")),
    ("G9 subscription order", "Bank of America", HOLDER,
     BOFA_IN.format(orig="JOHN Q SAMPLE", bank="SAMPLE BANK", det="SUBSCRIPTION ORDER 1042 SERIES A")),
    ("G10 Zelle memo wire", "Chase", "BUSINESS COMPLETE CHECKING",
     "Zelle Payment From John Q Sample 1234567 wire inv 1042"),
    ("G10 ACH from a company named WIRE", "Chase", "BUSINESS COMPLETE CHECKING",
     "ORIG CO NAME:CONTOSO WIRE AND CABLE ORIG ID:1234567890 DESC DATE:540105 CO ENTRY DESCR:PAYMENT SEC:CCD "
     "TRACE#:123456789012345 EED:540105 IND ID:1042 IND NAME:NORTHWIND LABS LLC TRN: 1234567890TC INV 10421"),
    ("G10 wire fee rebate", "Bank of America", HOLDER, "WIRE FEE ADJ INV 10421"),
    ("G11 title sale proceeds", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Title Agency LLC", bnf="Northwind Holdings LLC", obi="Invoice 1042 123 Main St Sale")),
    ("G11 earnest money", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Title Agency LLC", bnf="Northwind Holdings LLC", obi="Earnest Money PO 4521")),
    ("party: holder named INVOICE", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Business Group LLC", bnf="Northwind Invoice Services LLC", obi="Deal 104211")),
    ("party: originator GOODS AND SERVICES", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO GOODS AND SERVICES", bank="SAMPLE BANK", det="104211")),
    ("party: originator Invoice Cloud", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO INVOICE CLOUD INC", bank="SAMPLE BANK", det="104211")),
    ("party: originator Order 66", "Bank of America", HOLDER,
     BOFA_IN.format(orig="ORDER 66 HOLDINGS LLC", bank="SAMPLE BANK", det="104211")),
    ("wrapped CAPI TAL", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Capi Tal Partners LLC", bnf="Northwind Labs LLC", obi="Invoice 104211")),
    ("wrapped FUN DING", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Fun Ding Group LLC", bnf="Northwind Labs LLC", obi="Inv 104211")),
    ("sister company sharing its first word", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Northwind Holdings Group LLC", bnf="Northwind Labs LLC", obi="Inv 104211")),
    ("address PO 4521", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Supply LLC PO 4521 Tampa FL", bnf="Northwind Labs LLC", obi="Notprovided")),
    ("INV 1234 ADJ", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO SUPPLY INC", bank="SAMPLE BANK", det="INV 1234 ADJ")),
    ("Zelle memo wire invoice", "Sample Bank", "FABRIKAM LLC",
     "Zelle payment from JOHN Q SAMPLE memo wire for invoice 1042"),
    ("unknown wire credit", "Sample Bank", "FABRIKAM LLC", "Unknown wire credit"),
]


@pytest.mark.parametrize(("label", "bank", "holder", "printed"), HAZARDS)
def test_the_wire_hazards_never_verify(label, bank, holder, printed):
    assert _outcome(_one(bank, holder, printed)) != "verified", label


#: §7.9's recorded residuals: printed words cannot tell these from a sale (the spec states the person's invoice
#: wire; the others are the neutral-name funder, the root-free factor, a template-named holder's own account and
#: the MCA 'purchase price' order). They verify; the precision sample (§14.5) reads their strata, and the ledger
#: round of Task S1.5 carries the receivables financiers (Stenn, eCapital).
RESIDUALS = [
    ("person citing an invoice (stated)", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="1/John Q Sample 2/US/Tampa", bnf="Northwind Labs LLC", obi="Inv 1042")),
    ("person, payment for goods", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE S.A.", orig="JOHN Q SAMPLE", ref="PAYMENT FOR GOODS")),
    ("a person's holding company citing an invoice", "Bank of America", HOLDER,
     BOFA_IN.format(orig="JQS FAMILY HOLDINGS LLC", bank="SAMPLE BANK", det="INV 1042")),
    ("invoice financier with no root, until the ledger lists it", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK UK", orig="STENN ASSETS UK", ref="/INV/10421/54")),
    ("funder name cut before its root", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK", orig="CONTOSO BUSINESS", ref="INV 10421")),
    ("MCA purchase price with an order id", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO VENTURES LLC", bank="SAMPLE BANK", det="PURCHASE PRICE ORDER 10421")),
    ("root-free unregistered factor", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Business Solutions LLC", bnf="Northwind Labs LLC", obi="Inv 104211")),
    ("own account, holder name a product template", "Bank of America", "BUSINESS ADVANTAGE FUNDAMENTALS",
     BOFA_IN.format(orig="FABRIKAM LABS LLC", bank="SAMPLE BANK", det="INV 1234")),
]


@pytest.mark.parametrize(("label", "bank", "holder", "printed"), RESIDUALS)
def test_the_recorded_wire_residuals_verify_and_are_sampled(label, bank, holder, printed):
    assert _outcome(_one(bank, holder, printed)) == "verified", label
```

Create `tests/test_revenue_non_revenue_55.py`:

```python
"""Classification 5.5 (true revenue spec §6.3, §7.11, T5): the narrowed non-revenue rules, the newly named non-revenue,
the tightened CUSTOMER descriptor, and the channel gate's declared demotions. Fabricated rows only."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import (
    classify_statement_transactions,
    classify_transaction,
    prints_internal_transfer_designation,
)


def _credit(printed: str, *, holder: str | None = None):
    return classify_transaction(printed, 300.0, account_name=holder, direction="credit")


@pytest.mark.parametrize("printed", [
    "SAMPLE STATE MEDICAID DES:REIMBURSEMENT ID:1",
    "FABRIKAM HEALTH DES:HCCLAIMPMT REIMBURSEMENT ID:1",
    "SAMPLE COUNTY GEMT REIMBURSEMENT 1234",
])
def test_reimbursement_with_a_claim_signal_leaves_non_revenue(printed):
    assert _credit(printed).revenue_classification != "non_revenue"


@pytest.mark.parametrize("printed", [
    "UNITEDHEALTHCARE DES:REIMBURSEMENT ID:1",
    "STATE OF TEXAS DES:TRAVEL REIMBURSEMENT ID:1",
    "FABRIKAM INC DES:EXPENSE REIMBURSEMENT ID:1",
])
def test_reimbursement_without_a_claim_signal_stays_non_revenue(printed):
    assert _credit(printed).revenue_classification == "non_revenue"


def test_exp_reimb_is_not_the_whole_word_so_it_is_not_non_revenue():
    assert _credit("FABRIKAM INC DES:EXP REIMB ID:1").revenue_classification == "unverified_deposit"


@pytest.mark.parametrize("printed", [
    "WIRE FROM 12 OAK LN SAMPLEVILLE",
    "ATM DEPOSIT 450 PINE HILL LN SAMPLEVILLE",
])
def test_a_street_ln_no_longer_reads_as_a_loan(printed):
    assert _credit(printed).revenue_classification != "non_revenue"


def test_a_loan_ln_still_reads_as_a_loan():
    assert _credit("1234 COMMERCIAL LN PMT").revenue_classification == "non_revenue"
    assert _credit("000123 AUTO LN DISB").revenue_classification == "non_revenue"
    assert classify_transaction("TRUIST LN PYMT", -500.0).normalized_description == "TRUIST LOAN PYMT"


def test_rbc_s_funds_transfer_credit_names_its_sender():
    record = _credit("FUNDS TRANSFER CREDIT TT FABRIKAM SUPPLY LTD SAMPLEVILLE")
    assert record.revenue_classification == "unverified_deposit"
    assert not prints_internal_transfer_designation("FUNDS TRANSFER CREDIT TT FABRIKAM SUPPLY LTD SAMPLEVILLE")
    assert prints_internal_transfer_designation("FUNDS TRANSFER FROM SAVINGS 1234")


@pytest.mark.parametrize(("printed", "state"), [
    ("DEBIT CARD CREDIT VISA DIRECT SQUARE INC", "verified_revenue"),
    ("Debit Card Credit: Stripe Payout", "verified_revenue"),
    ("Debit Card Credit: Stripe", "non_revenue"),
    ("DEBIT CARD CREDIT UBER *TRIP HELP.UBER.COM CA", "non_revenue"),
    ("DEBIT CARD CREDIT DOORDASH*FABRIKAM DELI", "non_revenue"),
    ("POS CREDIT PAYPAL *FABRIKAM STORE", "non_revenue"),
])
def test_a_card_credit_is_released_only_for_a_push_or_a_processor_payout(printed, state):
    assert _credit(printed).revenue_classification == state


def test_three_card_refunds_never_verify_each_other():
    for printed in ("DEBIT CARD CREDIT UBER *TRIP HELP.UBER.COM CA", "DEBIT CARD CREDIT DOORDASH*FABRIKAM DELI",
                    "POS CREDIT PAYPAL *FABRIKAM STORE"):
        records = classify_statement_transactions(Statement(account_name="SAMPLE CAFE LLC", transactions=[
            Transaction(date=f"2054-03-{day:02d}", description=printed, amount=20.0 + day, direction="credit")
            for day in (2, 9, 16)
        ]))
        assert {record.revenue_classification for record in records} == {"non_revenue"}


def test_customer_id_and_a_customer_check_never_verify():
    assert _credit("ACH CORP CREDIT FABRIKAM SUPPLY CUSTOMER ID 12345 PAYMENT").revenue_classification == (
        "unverified_deposit")
    assert _credit("FABRIKAM CUSTOMER CHECK PAYMENT").revenue_classification == "unverified_deposit"
    assert _credit("FABRIKAM CUSTOMER ACH PAYMENT").revenue_classification == "verified_revenue"


@pytest.mark.parametrize(("printed", "rule"), [
    ("FABRIKAM DES:PAYMENT RTN ID:1", "returned_cancelled_reversed_or_provisional_credit"),
    ("FABRIKAM WIRE RECALLED 1234", "returned_cancelled_reversed_or_provisional_credit"),
    ("FABRIKAM DES:CHBK REVSL ID:1", "returned_cancelled_reversed_or_provisional_credit"),
    ("IRS TREAS 310 DES:TAX REF ID:1", "non_operating_credit"),
    ("SAMPLE STATE DES:TAXRFD ID:1", "non_operating_credit"),
    ("FRANCHISE TAX BD DES:CASTTAXRFD ID:1 PPD", "non_operating_credit"),   # glued to the state (review I6)
    ("IRS TREAS 310 DES:TAXEIC ID:1", "non_operating_credit"),
    ("SQUARE INC DES:SQ CAP1234 ID:1", "square_capital_credit"),
    ("SBAD TREAS 310 DES:MISC PAY ID:1", "sba_disbursement_credit"),
    ("EIDL 1234 SAMPLE", "sba_disbursement_credit"),
    ("FABRIKAM DES:ACCTVERIFY ID:1", "non_operating_credit"),
    ("FABRIKAM MICRO DEPOSIT", "non_operating_credit"),
])
def test_the_newly_named_non_revenue(printed, rule):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_matched_rule) == ("non_revenue", rule)


def test_square_capital_and_sba_proceeds_leave_eligible_deposits():
    record = _credit("SQUARE INC DES:SQ CAP1234 ID:1")
    assert record.revenue_match_method == "financing_proceeds_credit"
    assert record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize("printed", [
    "ZELLE PAYMENT FROM JOHN SMITH MEMO INVOICE PAYMENT CONF 99",
    "MOBILE DEPOSIT CUSTOMER PAYMENT REF 1234",
    "CUSTOMER DEPOSIT",
    "ZELLE PAYMENT FROM FABRIKAM SUPPLY LLC CONF 99",
    "RTP CREDIT FROM FABRIKAM LLC INV 1234",
])
def test_the_channel_gate_never_verifies(printed):
    assert _credit(printed).revenue_classification == "unverified_deposit"


def test_a_real_time_payout_verifies_through_the_registry_only():
    records = classify_statement_transactions(Statement(account_name="SAMPLE SHOP LLC", transactions=[
        Transaction(date=f"2054-03-{day:02d}", description=f"RTP CREDIT AMAZON COM {day}", amount=400.0 + day,
                    direction="credit")
        for day in (2, 9, 16)
    ]))
    assert {record.revenue_match_method for record in records} == {"recurring_operating_source"}
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_revenue_card_settlements.py tests/test_revenue_platform_payouts.py tests/test_revenue_healthcare_claims.py tests/test_revenue_payer_remittance.py tests/test_revenue_public_payers.py tests/test_revenue_wire_remittance.py tests/test_revenue_non_revenue_55.py -q -p no:cacheprovider`

Expected: FAIL: `143 failed, 189 passed`, the first with `AssertionError: ambiguous_credit_descriptor`.

- [ ] **Step 3: Implement.**

In `analysis/transaction_classifier.py` (lines 716-729), replace:

```python
_VERIFIED_REVENUE_CREDIT_PATTERNS = (
    re.compile(r"\bMRCH\d{5,}\b"),
    re.compile(r"\bMERCHANT (?:PROCESSOR )?(?:SETTLEMENT|DEPOSIT|PAYOUT)\b"),
    re.compile(r"\bCARD SALES? (?:DEPOSIT|SETTLEMENT|PAYOUT)\b"),
    re.compile(r"\bCUSTOMER\b.*\b(?:ACH|PAYMENT|DEPOSIT|CHECK|CHEQUE)\b"),
    re.compile(r"\b(?:ACH|PAYMENT|DEPOSIT|CHECK|CHEQUE)\b.*\bCUSTOMER\b"),
    re.compile(r"\bINVOICE (?:PAYMENT|PAID|DEPOSIT)\b"),
    re.compile(r"\bACCOUNTS? RECEIVABLE\b"),
    re.compile(r"\bMARKETPLACE (?:PAYOUT|SETTLEMENT)\b"),
    re.compile(r"\bH(?:C|E)?CLAIMPMT\b"),
    re.compile(r"\bEDIRPAY\b"),
    re.compile(r"\bMERCHANT BANK(?:CD|CARD|ED) DEPOSIT\b"),
    re.compile(r"\bMTOT DEP\b"),
)
```

with:

```python
_VERIFIED_REVENUE_CREDIT_PATTERNS = (
    re.compile(r"\bMRCH\d{5,}\b"),
    re.compile(r"\bMERCHANT (?:PROCESSOR )?(?:SETTLEMENT|DEPOSIT|PAYOUT)\b"),
    re.compile(r"\bCARD SALES? (?:DEPOSIT|SETTLEMENT|PAYOUT)\b"),
    re.compile(r"\bMARKETPLACE (?:PAYOUT|SETTLEMENT)\b"),
    # 5.5 (§7.7): the NACHA claim-payment entry, glued on either side (Chase's SEC, a sixteen-character name or
    # digits on the left); its unbounded branch takes only the full token, so THECLAIMPMT stays unmatched.
    re.compile(r"(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b"),
    re.compile(r"\bEDIRPAY\b"),
    re.compile(r"\bMERCHANT BANK(?:CD|CARD|ED) DEPOSIT\b"),
    re.compile(r"\bMTOT DEP\b"),
)
#: 5.5 (§6.1 step 11, §7.11): the customer and invoice descriptors. CUSTOMER is never read in CUSTOMER ID (Truist
#: prints it on every ACH line) and never with CHECK or CHEQUE (Q3). A payer the holder test or the numbered-company
#: guard matches never verifies through them (§5.2).
_CUSTOMER_INVOICE_DESCRIPTORS = (
    re.compile(r"^(?!.*\bCHE(?:CK|QUE)S?\b).*\bCUSTOMER\b(?! ID\b).*\b(?:ACH|PAYMENT|DEPOSIT)\b"),
    re.compile(r"^(?!.*\bCHE(?:CK|QUE)S?\b).*\b(?:ACH|PAYMENT|DEPOSIT)\b.*\bCUSTOMER\b(?! ID\b)"),
    re.compile(r"\bINVOICE (?:PAYMENT|PAID|DEPOSIT)\b"),
    re.compile(r"\bACCOUNTS? RECEIVABLE\b"),
)
```

In `analysis/transaction_classifier.py` (lines 663-664), replace:

```python
_INTERNAL_TRANSFER_CREDIT_PATTERNS = (
    re.compile(r"\b(?:INTERNAL|ACCOUNT|BOOK|FUNDS?) TRANSFER\b"),
```

with:

```python
_INTERNAL_TRANSFER_CREDIT_PATTERNS = (
    # 5.5 (§7.11): BOOK TRANSFER and FUNDS TRANSFER are own-account only without a third-party originator
    # (_own_book_or_funds_transfer).
    re.compile(r"\b(?:INTERNAL|ACCOUNT) TRANSFER\b"),
```

In `analysis/transaction_classifier.py` (line 702), replace:

```python
    re.compile(r"\bTAX REFUND\b"),
```

with:

```python
    re.compile(r"\bTAX REFUND\b"),
    # 5.5 (§7.11, T5): the tax-refund abbreviations (Treasury's TAX REF; a state's glued TAXRFD, and TAXEIC, review
    # I6) and account-verification micro-deposits.
    re.compile(r"\bTAX ?REF(?:UND)?S?\b|[A-Z]*TAXRFD\b|\bTAX RFD\b|\bTAXEIC\b"),
    re.compile(r"\bACCT ?VERIFY\w*\b|\bMICRO ?DEPOSITS?\b|\bPENNY TEST\b|\bTRIAL DEPOSITS?\b"),
```

In `analysis/transaction_classifier.py` (lines 813-816), replace:

```python
    return _matches_any(
        normalize_transaction_description(description),
        _INTERNAL_TRANSFER_CREDIT_PATTERNS,
    )
```

with:

```python
    text = normalize_transaction_description(description)
    # 5.5 (§7.11): a book or funds transfer designates an own account only when it prints no third-party originator.
    return _matches_any(text, _INTERNAL_TRANSFER_CREDIT_PATTERNS) or (
        _BOOK_OR_FUNDS_TRANSFER.search(text) is not None
        and _EFT_FUNDS_TRANSFER.search(text) is None
        and (
            (_BOOK_OR_FUNDS_TRANSFER.search(text).group(0).startswith("BOOK") and not THIRD_PARTY_BOOK_TRANSFER_AS_WIRE)
            or _third_party_originator(text) is None
        )
    )
```

In `analysis/transaction_classifier.py`, replace the whole function `_classify_credit_revenue` (lines 1928-2116) with:

```python
def _classify_credit_revenue(
    text: str,
    amount: float,
    *,
    posted: bool,
    account_name: str | None,
    direction_consistent: bool,
    bank: str | None = None,
) -> _RevenueDecision | None:
    if amount <= 0 or not posted:
        return None
    text = revenue_text(text)

    if not direction_consistent:
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "direction_conflict",
            None,
            "source_direction_conflicts_with_signed_amount",
            0.20,
            "The source direction conflicts with the signed amount, so the credit requires review.",
            context_signals=("positive_amount", "direction_conflict"),
        )
    if _reversal_credit(text):
        return _RevenueDecision(
            "non_revenue",
            None,
            "reversal_cancellation_exclusion",
            None,
            "returned_cancelled_reversed_or_provisional_credit",
            0.99,
            "Credit is a return, cancellation, reversal, refund, correction, chargeback, or provisional credit.",
            context_signals=("credit_direction", "strong_non_revenue_descriptor"),
        )

    # §7.7: the lookups below read a glued HCCLAIMPMT split from the name before it.
    lookup_text = _split_glued_claim(text)
    claim_entry = _HCCLAIMPMT.search(text) is not None
    # A premium-finance credit keeps the insurance credit treatment (spec §4.2). T18: a claim payment skips the
    # insurer registry when the owner's switch is on; T14: an insurer's customer payment is held, not decided.
    insurance_match = _insurance_registry_match(lookup_text)
    if insurance_match is not None and not (claim_entry and HCCLAIMPMT_CLAIM_FIRST):
        entity, alias, _premium_finance = insurance_match
        if claim_entry or _INSURER_CUSTOMER_PAYMENT.search(_before_receiver(text)):
            return _RevenueDecision(
                "unverified_deposit",
                entity,
                "insurer_customer_payment",
                alias,
                "insurer_customer_payment_requires_review",
                0.60,
                (
                    f"Credit matched insurance provider alias '{alias}' with customer-payment or claim-payment "
                    "wording; an analyst decides whether it is revenue."
                ),
                context_signals=("credit_direction", "insurance_provider", "customer_payment_wording"),
            )
        return _RevenueDecision(
            "non_revenue",
            entity,
            "insurance_provider_credit_exclusion",
            alias,
            "insurance_proceeds_or_refund",
            0.99,
            f"Credit matched insurance provider alias '{alias}' and is not operating revenue.",
            context_signals=("credit_direction", "insurance_provider"),
        )
    if claim_entry and not HCCLAIMPMT_CLAIM_FIRST and _BLUE_PLAN_CLAIM_PAYER.search(_before_receiver(text)):
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "insurer_customer_payment",
            None,
            "insurer_customer_payment_requires_review",
            0.60,
            "A Blue-plan claim payment is held with the insurer's credits until the owner rules on claim first.",
            context_signals=("credit_direction", "insurance_provider", "customer_payment_wording"),
        )
    # Spec §4.4 / D1: a credit from a financing group is proceeds. It is decided
    # before the operating-revenue registry, and group aliases are
    # financing-specific (SQUARE CAPITAL, never bare SQUARE), so a platform's
    # sales settlement still reaches the operating registry below. Card-issuer
    # and lease/rental payees never apply to credits, and neither does a
    # payout-credit entity (owner decision 2026-09-25).
    financing_match = _financing_proceeds_payee(lookup_text)
    if financing_match is not None:
        return _RevenueDecision(
            "non_revenue",
            financing_match.entity,
            "financing_proceeds_credit",
            financing_match.alias,
            "financing_proceeds_credit",
            0.99,
            (
                f"Credit matched maintained {_state_words(financing_match.state)} alias "
                f"'{financing_match.alias}'; financing proceeds are not revenue."
            ),
            context_signals=("credit_direction", "financing_proceeds"),
        )
    # D1 by descriptor (owner decisions 2026-09-25; 5.5: Square Capital's SQ CAP, SBA and EIDL). `_descriptor_proceeds`
    # keeps the potential registry and the strong non-revenue rule below ahead of a line-of-credit draw or a
    # floor-plan advance.
    descriptor_proceeds = _descriptor_proceeds(text)
    if descriptor_proceeds is not None:
        rule, names_bank = descriptor_proceeds
        return _RevenueDecision(
            "non_revenue",
            (bank or None) if names_bank else None,
            "financing_proceeds_credit",
            None,
            rule,
            0.97,
            f"The credit's descriptor identifies financing proceeds ({_state_words(rule)}); they are not revenue.",
            context_signals=("credit_direction", "financing_proceeds"),
        )
    potential_lender_match = registry_match(lookup_text, POTENTIAL_LENDER_ALIASES)
    if potential_lender_match is not None:
        entity, alias = potential_lender_match
        return _RevenueDecision(
            "non_revenue",
            entity,
            "potential_lender_registry_credit_exclusion",
            alias,
            "potential_lender_funding_credit",
            0.95,
            f"Credit matched potential lender alias '{alias}' and is excluded from revenue.",
            context_signals=("credit_direction", "potential_lender_source"),
        )
    if _matches_any(text, _NON_REVENUE_CREDIT_PATTERNS) or _own_book_or_funds_transfer(text, account_name):
        return _RevenueDecision(
            "non_revenue",
            None,
            "strong_non_revenue_rule",
            None,
            "non_operating_credit",
            0.97,
            (
                "Credit matched identifiable financing, own-account transfer, reward, "
                "interest, contribution, or other non-operating proceeds evidence."
            ),
            context_signals=("credit_direction", "strong_non_revenue_descriptor"),
        )

    # §6.1 step 9b, the channel gate: a consumer rail, a check, cash, branch or ATM deposit, or a row with no payer
    # word is never verified; a real-time or push rail is verified by the operating registry only.
    gate = channel_gate(text)
    if gate != "closed":
        source_text = _before_receiver(text) if gate == "push" else text
        source = _operating_source(source_text)
        if source is not None:
            return _operating_source_decision(text, source, account_name=account_name, bank=bank)
    if gate is not None:
        return _fallback_credit_decision(text)

    region = payer_region(text)
    form = _card_settlement_form(text, bank=bank)
    if form is not None and form.label != "net_settle":
        return _RevenueDecision(
            "verified_revenue",
            form.entity,
            "operating_income_descriptor",
            form.label,
            f"card_settlement_form_{form.label}",
            0.93,
            f"Credit prints the card-settlement form '{form.label}'.",
            source_type=OPERATING_REVENUE_SOURCE_TYPES.get(form.entity) if form.entity else None,
            context_signals=("credit_direction", "operating_income_descriptor", "card_settlement_form"),
        )
    joined = _joined_text(_before_receiver(text))
    customer_or_invoice = _matches_any(text, _CUSTOMER_INVOICE_DESCRIPTORS) or _matches_any(
        joined, _CUSTOMER_INVOICE_DESCRIPTORS
    )
    if _matches_any(text, _VERIFIED_REVENUE_CREDIT_PATTERNS) or _matches_any(joined, _VERIFIED_REVENUE_CREDIT_PATTERNS):
        return _RevenueDecision(
            "verified_revenue",
            None,
            "operating_income_descriptor",
            None,
            "verified_operating_income_descriptor",
            0.93,
            "Credit has a merchant-settlement, card-sales, claim-payment, or verified business-deposit descriptor.",
            context_signals=("credit_direction", "operating_income_descriptor"),
        )
    guard = _refused_by_payer_guards(text, region, account_name)
    if guard == "holder" and (
        customer_or_invoice
        or _payer_remittance(text, region, account_name)
        or _public_payer_remittance(text) is not None
        or _wire_remittance_purpose(text, region, account_name)
    ):
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "holder_named_payer",
            None,
            "payer_prints_the_holders_name",
            0.40,
            "The payer prints the account holder's own name or brand, so its remittance wording is not proof.",
            context_signals=("credit_direction", "holder_named_payer"),
        )
    if guard is None:
        if customer_or_invoice:
            return _RevenueDecision(
                "verified_revenue",
                None,
                "operating_income_descriptor",
                None,
                "verified_operating_income_descriptor",
                0.93,
                "Credit has a customer-payment or invoice descriptor.",
                context_signals=("credit_direction", "operating_income_descriptor"),
            )
        if _payer_remittance(text, region, account_name):
            return _RevenueDecision(
                "verified_revenue",
                None,
                "payer_remittance_descriptor",
                None,
                "verified_payer_accounts_payable_remittance",
                0.90,
                "The payer prints its accounts-payable remittance: the credit pays an invoice of the business.",
                context_signals=("credit_direction", "payer_remittance"),
            )
        public_rule = _public_payer_remittance(text)
        if public_rule is not None:
            return _RevenueDecision(
                "verified_revenue",
                None,
                "public_payer_remittance",
                None,
                public_rule,
                0.90,
                "A public payer pays a vendor or provider remittance of the business.",
                source_type="government_payer",
                context_signals=("credit_direction", "public_payer_remittance"),
            )
        if _wire_remittance_purpose(text, region, account_name):
            return _RevenueDecision(
                "verified_revenue",
                None,
                "wire_remittance_purpose",
                None,
                "verified_wire_remittance_purpose",
                0.90,
                "The incoming wire's remittance cites an invoice, a purchase order, an order or goods.",
                context_signals=("credit_direction", "wire_remittance_purpose"),
            )
    return _fallback_credit_decision(text)
```

In `analysis/transaction_classifier.py`, after the end of `_classify_credit_revenue` (in text an earlier step of this task wrote), insert:

```python
def _operating_source_decision(
    text: str,
    source: _OperatingSource,
    *,
    account_name: str | None,
    bank: str | None,
) -> _RevenueDecision:
    """5.5 (§6.1 step 10): a credit the operating registry names: verified with payout context, otherwise it needs
    recurrence or related activity. Property-management platforms and wholesale auctions never verify here: the
    recurrence pass decides them."""
    entity, alias, source_type = source.entity, source.alias, source.source_type
    business_account = _business_account(account_name)
    has_context = source_type not in {"property_management_payments", "wholesale_auto_auction"} and (
        _has_operating_context(text, source, bank=bank)
    )
    signals = ["credit_direction", "maintained_operating_source"]
    if source.payout_form:
        signals.append("payout_form")
    if has_context:
        signals.append("settlement_or_payout_descriptor")
    if business_account:
        signals.append("business_account")
    if has_context:
        return _RevenueDecision(
            "verified_revenue",
            entity,
            "operating_source_with_credit_context",
            alias,
            "verified_operating_source_credit",
            0.98 if business_account else 0.96,
            (
                f"Credit matched maintained {source_type or 'operating-source'} "
                f"{'payout form' if source.payout_form else 'alias'} '{alias}' with settlement, payout, or deposit "
                "context."
            ),
            source_type=source_type,
            context_signals=tuple(signals),
        )
    return _RevenueDecision(
        "unverified_deposit",
        entity,
        "operating_source_requires_context",
        alias,
        "operating_source_without_payout_context",
        0.70,
        (
            f"Credit matched maintained {source_type or 'operating-source'} alias "
            f"'{alias}', but the row needs recurrence or related operating activity to verify revenue."
        ),
        source_type=source_type,
        context_signals=tuple(signals),
    )


def _business_account(account_name: str | None) -> bool:
    """§7.0: a business account for the recurrence rule: BUSINESS, COMMERCIAL, OPERATING or MERCHANT, or (5.5) a
    holder name that prints a legal form."""
    name = account_name_text(account_name)
    return _matches_any(name, _BUSINESS_ACCOUNT_PATTERNS) or _LEGAL_FORM_HOLDER.search(name) is not None


def _fallback_credit_decision(text: str) -> _RevenueDecision:
    """§6.1 steps 15 and 16: deposit wording, else an unidentified posted credit."""
    if _matches_any(text, _UNVERIFIED_DEPOSIT_CREDIT_PATTERNS):
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "ambiguous_credit_descriptor",
            None,
            "deposit_source_requires_review",
            0.60,
            "The credit is a deposit or incoming transfer without enough evidence to confirm operating revenue.",
            context_signals=("credit_direction", "generic_deposit_descriptor"),
        )
    return _RevenueDecision(
        "unverified_deposit",
        None,
        "unidentified_posted_credit",
        None,
        "unknown_credit_source_requires_review",
        0.40,
        "The posted credit source is not identified strongly enough to confirm or exclude revenue.",
        context_signals=("credit_direction", "unidentified_source"),
    )
```

In `analysis/transaction_classifier.py` (lines 2618-2619), replace:

```python
    if _BANK_LINE_ADVANCE_CREDIT.search(text):
        return "bank_line_advance_credit", True
```

with:

```python
    if _BANK_LINE_ADVANCE_CREDIT.search(text):
        return "bank_line_advance_credit", True
    # 5.5 (§7.11, T5): Square Capital's SQ CAP spelling on a row that names Square, and SBA and EIDL disbursements.
    if _SQUARE_CAPITAL_CREDIT.search(text) and _SQUARE_NAME.search(text):
        return "square_capital_credit", False
    if _SBA_DISBURSEMENT_CREDIT.search(text):
        return "sba_disbursement_credit", False
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_revenue_card_settlements.py tests/test_revenue_platform_payouts.py tests/test_revenue_healthcare_claims.py tests/test_revenue_payer_remittance.py tests/test_revenue_public_payers.py tests/test_revenue_wire_remittance.py tests/test_revenue_non_revenue_55.py -q -p no:cacheprovider`

Expected: PASS: `332 passed`.

- [ ] **Step 5: Re-pin the assertions this task moves (pin ledger rows 3-12).**

In `tests/test_revenue_classification.py` (lines 63-64), replace:

```python
        ("Card sales deposit", None),
        ("Customer check deposit", None),
```

with:

```python
        ("Card sales deposit", None),
```

In `tests/test_revenue_classification.py` (lines 106-107), replace:

```python
        "Cash deposit",
        "Incoming credit from unknown source",
```

with:

```python
        "Cash deposit",
        # 5.5 (true revenue spec §6.1 step 9b, Q3): a check deposit is never verified, whatever it prints.
        "Customer check deposit",
        "Incoming credit from unknown source",
```

In `tests/test_revenue_classification.py` (lines 208-209), replace:

```python
            _txn("2054-01-02", "Customer ACH payment", 100.0, balance=1100.0),
            _txn("2054-01-02", "Customer ACH payment", 100.0, balance=1100.0),
```

with:

```python
            _txn("2054-01-02", "Fabrikam customer ACH payment", 100.0, balance=1100.0),
            _txn("2054-01-02", "Fabrikam customer ACH payment", 100.0, balance=1100.0),
```

In `tests/test_revenue_classification.py` (lines 228-230), replace:

```python
            _txn("2054-01-02", "Customer ACH payment", 100.0),
            _txn("2054-01-03", "Mobile deposit", 50.0),
            _txn("2054-01-04", "Internal transfer from savings", 25.0),
```

with:

```python
            _txn("2054-01-02", "Fabrikam customer ACH payment", 100.0),
            _txn("2054-01-03", "Mobile deposit", 50.0),
            _txn("2054-01-04", "Internal transfer from savings", 25.0),
```

In `tests/test_revenue_classification.py` (lines 259-261), replace:

```python
            _txn("2054-01-02", "Customer ACH payment", 100.0),
            _txn("2054-01-03", "Mobile deposit", 50.0),
            _txn("2054-01-04", "Debit Card Credit", 25.0),
```

with:

```python
            _txn("2054-01-02", "Fabrikam customer ACH payment", 100.0),
            _txn("2054-01-03", "Mobile deposit", 50.0),
            _txn("2054-01-04", "Debit Card Credit", 25.0),
```

In `tests/test_revenue_classification.py` (line 297), replace:

```python
            _txn("2054-01-01", "Customer ACH payment", 1000.0),
```

with:

```python
            _txn("2054-01-01", "Fabrikam customer ACH payment", 1000.0),
```

In `tests/test_analysis.py` (line 3361), replace:

```python
    assert m.true_revenue == 10000.0
```

with:

```python
    # 5.5 (§6.1 step 9b): the bare teller CUSTOMER DEPOSIT prints no payer word, so it is no longer verified.
    assert m.true_revenue == 0.0
```

In `tests/test_webapp_revenue_batch.py` (line 13), replace:

```python
ROWS = [(2, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 4200.0),
```

with:

```python
ROWS = [(2, "ACH CREDIT NORTHWIND CUSTOMER PAYMENT", 4200.0),
```

In `tests/test_webapp_studio_views.py` (line 17), replace:

```python
CHECKING_ROWS = [(2, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 4200.0),
```

with:

```python
CHECKING_ROWS = [(2, "ACH CREDIT NORTHWIND CUSTOMER PAYMENT", 4200.0),
```

In `tests/test_webapp_studio_views.py` (line 450), replace:

```python
PENDING_ROWS = [(2, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 4200.0),
```

with:

```python
PENDING_ROWS = [(2, "ACH CREDIT NORTHWIND CUSTOMER PAYMENT", 4200.0),
```

- [ ] **Step 6: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-CLASSIFIER: `755 passed, 2 deselected`
  - SEL-WEBAPP: `856 passed`

- [ ] **Step 7: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/transaction_classifier.py tests/test_analysis.py tests/test_revenue_card_settlements.py tests/test_revenue_classification.py tests/test_revenue_healthcare_claims.py tests/test_revenue_non_revenue_55.py tests/test_revenue_payer_remittance.py tests/test_revenue_platform_payouts.py tests/test_revenue_public_payers.py tests/test_revenue_wire_remittance.py tests/test_webapp_revenue_batch.py tests/test_webapp_studio_views.py
git commit -m "classifier: the 5.5 credit decision (spec 6.1, 7.1 to 7.11)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S2.4: The 5.5 statement passes

**Files:**
- Create: `tests/test_revenue_recurrence.py`
- Modify: `analysis/transaction_classifier.py:21-23, 3504-3506, 3519-3522, 3534-3537, 3610-3680, 4393`
- Modify (pins): `tests/test_revenue_platform_payouts.py:86`
- Modify (pins): `tests/test_revenue_payer_remittance.py:80`

**Depends on:** S2.3.

**Interfaces:**
- Consumes: S2.2's constants and helpers, S2.3's decision.
- Produces:
  - `_PAIR_MARKER_PATTERNS`
  - `_recurrence_vetoed(record, text) -> bool`, `_recurrence_veto_word(text, account_name, pattern=_RECURRENCE_VETO) -> bool`, `_in_operating_pool(record) -> bool`
  - `_apply_operating_source_context(records, duplicate_indexes)` (rewritten), `_apply_auction_branch`, `_auction_refund_pair`, `_apply_property_branch`
  - `_payer_key(region: str) -> tuple[str, ...]`, `_payer_first_distinctive_word(region) -> str | None`, `_debit_first_distinctive_word(record) -> str | None`
  - `_apply_payer_remittance_counter_debit_guard(records, duplicate_indexes)` (pass 6; method `payer_remittance_with_counter_debit`)

**Why:** Spec §6.2 passes 4 to 6 and §7.0, §7.3, §7.5, §7.8, §7.10: the reversal pair reads the return codes too; the recurrence pass admits only registry rows, never shrinks the pool, keeps vetoed rows, direction conflicts and sub-$1 rows out, reads a legal-form holder as a business, counts NET SETTLE from an unregistered originator at three credits, and gives property platforms and dealer-only auctions their own branches; the accounts-payable counter-debit guard sends a payer the statement also debits back to unverified. After the review: FUNDING vetoes recurrence outside the three platforms §7.0 names (C2), the auction branch refuses §14.1's financing and consumer words (C2, rule `auction_credit_prints_financing_or_consumer_word`), and the debit side honours the ledger gate (I4). After this task the classifier is 5.5 in all but its number.

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_revenue_recurrence.py`:

```python
"""Classification 5.5 (true revenue spec §7.0, §7.1, §7.8, §7.10): the operating-source recurrence pass: the pool, its
veto, the absolute micro-deposit floor, legal-form holders, NET SETTLE, the wholesale auctions and the property
platforms. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions


def _statement(rows, *, holder: str | None = "SAMPLE CAFE", bank: str | None = None):
    return classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{day:02d}", description=text, amount=amount,
                    direction=direction or ("credit" if amount > 0 else "debit"))
        for day, text, amount, *rest in rows
        for direction in [rest[0] if rest else None]
    ]))


def _methods(records):
    return [record.revenue_match_method for record in records if record.amount > 0]


def test_a_per_row_upgrade_never_shrinks_the_pool():
    # One Square row verifies by its payout id; the other two still count it toward three.
    records = _statement([(2, "SQUARE INC DES:SQ540102 ID:1", 300.0), (9, "SQUARE INC DES:TRANSFER ID:2", 310.0),
                          (16, "SQUARE INC DES:TRANSFER ID:3", 320.0)])
    assert _methods(records) == [
        "operating_source_with_credit_context", "recurring_operating_source", "recurring_operating_source"]


def test_the_recurrence_veto_keeps_financing_and_pay_out_of_the_pool():
    records = _statement([(2, "SQUARE INC DES:TRANSFER ID:1", 300.0), (9, "SQUARE INC DES:TRANSFER ID:2", 310.0),
                          (16, "SQUARE INC DES:SQ CAP1234 ID:3", 5000.0), (20, "SHIFT4 PAYMENTS DES:CAP ADV ID:4", 900.0),
                          (23, "SUMUP DES:CASH ADV ID:5", 800.0)])
    assert [record.revenue_classification for record in records] == [
        "unverified_deposit", "unverified_deposit", "non_revenue", "unverified_deposit", "unverified_deposit"]
    weekly_pay = _statement([(day, "HEARTLAND PAYMENT SYSTEMS DES:PAYROLL ID:1", 700.0) for day in (2, 9, 16, 23)])
    assert {record.revenue_classification for record in weekly_pay} == {"unverified_deposit"}


def test_a_holder_named_like_a_veto_word_keeps_its_own_settlements():
    rows = [(day, f"SQUARE INC DES:TRANSFER ID:{day}", 300.0 + day) for day in (2, 9, 16)]
    assert set(_methods(_statement(rows, holder="FABRIKAM PAYROLL SERVICES LLC"))) == {"recurring_operating_source"}
    # A delivery platform prints the holder's store name in its entry field.
    store = [(day, f"DOORDASH INC DES:FABRIKAM CAPITA ID:ST-A1B2C{day} INDN:FABRIKAM CAPITAL GROUP CO ID:1 CCD",
              200.0 + day) for day in (2, 9, 16)]
    assert set(_methods(_statement(store, holder=None))) == {"recurring_operating_source"}


def test_three_mis_signed_rows_are_never_grouped():
    rows = [(day, "ELAVON DES:DEPOSIT ID:1", 300.0 + day, "debit") for day in (2, 9, 16)]
    assert set(_methods(_statement(rows))) == {"direction_conflict"}


def test_a_micro_deposit_never_counts_and_is_never_lifted():
    rows = [(2, "PAYPAL DES:TRANSFER ID:1", 400.0), (9, "PAYPAL DES:TRANSFER ID:2", 410.0),
            (16, "PAYPAL DES:TRANSFER ID:3", 0.03)]
    records = _statement(rows, holder="SAMPLE CAFE")
    assert [record.revenue_classification for record in records] == ["unverified_deposit"] * 3
    four = _statement([*rows, (23, "PAYPAL DES:TRANSFER ID:4", 420.0)])
    assert [record.revenue_classification for record in four] == [
        "verified_revenue", "verified_revenue", "unverified_deposit", "verified_revenue"]


def test_a_legal_form_holder_is_a_business_account_except_for_a_customer_payment_platform():
    stripe = [(2, "STRIPE DES:TRANSFER ID:1", 400.0), (9, "STRIPE DES:TRANSFER ID:2", 410.0)]
    assert set(_methods(_statement(stripe, holder="SAMPLE CAFE LLC"))) == {"recurring_operating_source"}
    assert set(_methods(_statement(stripe, holder="SAMPLE CAFE"))) == {"operating_source_requires_context"}
    paypal = [(2, "PAYPAL DES:TRANSFER ID:1", 400.0), (9, "PAYPAL DES:TRANSFER ID:2", 410.0)]
    assert set(_methods(_statement(paypal, holder="SAMPLE CAFE LLC"))) == {"operating_source_requires_context"}
    assert set(_methods(_statement(paypal, holder="SAMPLE CAFE BUSINESS CHECKING"))) == {"recurring_operating_source"}


def test_net_settle_from_an_unregistered_originator_needs_three_credits():
    three = [(day, f"FABRIKAM MERCHANT DES:NET SETTLE ID:{day}", 900.0 + day) for day in (2, 9, 16)]
    assert {record.revenue_matched_rule for record in _statement(three)} == {"card_settlement_form_net_settle"}
    assert _statement(three[:1])[0].revenue_classification == "unverified_deposit"


def test_an_auction_verifies_only_its_payout_form():
    records = _statement([(2, "MANHEIM US DES:ACH PAYMNT ID:1", 18000.0),
                          (5, "MANHEIM US DES:ADJUSTMENT ID:2", 150.0),
                          (9, "ACV AUCTIONS INC PAYMENTS 1234", 12000.0),
                          (12, "ACV AUCTIONS INC PAYMENTS PYMT1234567", 8200.0),
                          (16, "BACKLOTCARS PAYMENT 123456 7654321", 9500.0)])
    assert [record.revenue_matched_rule for record in records] == [
        "wholesale_auto_auction_proceeds", "auction_credit_without_payout_form", "wholesale_auto_auction_proceeds",
        "auction_credit_prints_buyer_payment_reference", "wholesale_auto_auction_proceeds"]


def test_an_auction_credit_paired_with_an_equal_auction_debit_stays_unverified():
    records = _statement([(2, "MANHEIM ACH PAYMNT PURCHASE 1234", -18000.0),
                          (9, "MANHEIM US DES:EDI PYMNTS ID:1", 18000.0)])
    assert records[1].revenue_matched_rule == "auction_credit_matches_same_source_debit"


def test_an_auction_alias_outside_the_originator_never_counts():
    for printed in ("ZELLE PAYMENT FROM FABRIKAM FOR MANHEIM US ACH PAYMNT CONF 1",
                    "FABRIKAM MOTORS DES:PAYMENT ID:1 INDN:MANHEIM US CO ID:1 CCD"):
        assert _statement([(2, printed, 5000.0)])[0].revenue_classification == "unverified_deposit"
    assert _statement([(2, "MANHEIM US DES:ACH PAYMNT ID:1", 0.5)])[0].revenue_classification == "unverified_deposit"


def test_a_property_platform_verifies_by_ach_recurrence_only():
    ach = [(day, f"ORIG CO NAME BUILDIUM ORIG ID 123 DESC DATE CO ENTRY DESCR FUNDING SEC CCD TRACE {day}",
            1500.0 + day) for day in (2, 9, 16)]
    records = _statement(ach, holder="SAMPLE PROPERTIES")
    assert {record.revenue_match_method for record in records} == {"recurring_operating_source"}
    assert all("property_management_collections" in record.revenue_context_signals for record in records)
    # One row alone, even with ACH CREDIT context words, stays unverified.
    lone = _statement([(2, "ACH CREDIT BUILDIUM SETTLEMENT", 1500.0)], holder="SAMPLE PROPERTIES")
    assert lone[0].revenue_match_method == "operating_source_requires_context"
    # A fee debit plus one credit is no recurrence.
    fee = _statement([(2, "BUILDIUM DES:FUNDING ID:1", 1500.0), (3, "BUILDIUM PROCESSING FEE", -30.0)])
    assert fee[0].revenue_classification == "unverified_deposit"


def test_a_property_platform_never_pools_push_shapes_micro_deposits_or_owner_wording():
    mixed = _statement([(2, "APPFOLIO VISA DIRECT PAYOUT", 900.0), (9, "APPFOLIO PMNT RCVD", 950.0)],
                       holder="SAMPLE PROPERTIES LLC")
    assert {record.revenue_classification for record in mixed} == {"unverified_deposit"}
    micro = _statement([(2, "APPFOLIO DES:ACCTVERIFY ID:1", 0.12), (3, "APPFOLIO DES:ACCTVERIFY ID:2", 0.21)],
                       holder="SAMPLE PROPERTIES LLC")
    assert {record.revenue_classification for record in micro} == {"non_revenue"}
    owner = _statement([(day, f"BUILDIUM DES:OWNER DIST ID:{day}", 1500.0 + day) for day in (2, 9, 16)])
    assert {record.revenue_matched_rule for record in owner} == {"property_platform_owner_or_deposit_wording"}


# ---------------------------------------------------------------------------------------------------------------------
# §14.1's §7.8 negatives (review I5), and FUNDING outside the three platforms that print it on settlements (review C2).
# ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("word", ["FUNDING", "FUNDNG", "ADVANCE", "CAPTL", "FLOORPLAN", "FLOOR PLAN", "FINANCING",
                                  "NGC", "PPD"])
def test_an_auction_payout_printing_a_financing_or_consumer_word_never_verifies(word):
    records = _statement([(2, f"MANHEIM US DES:ACH PAYMNT {word} ID:1", 18000.0),
                          (9, f"MANHEIM US DES:ACH PAYMNT {word} ID:2", 17000.0),
                          (16, f"MANHEIM US DES:ACH PAYMNT {word} ID:3", 16000.0)], holder="SAMPLE MOTORS LLC")
    assert {record.revenue_classification for record in records} == {"unverified_deposit"}


@pytest.mark.parametrize("printed", [
    "MANHEIM US DES:DEALSHIELD ID:1", "MANHEIM US DES:ARB CREDIT ID:1", "MANHEIM US DES:PAYROLL ID:1",
    "MANHEIM US DES:DIR DEP ID:1", "ACV AUCTIONS INC PAYMENTS PAYROLL", "DEBIT CARD CREDIT MANHEIM US ATLANTA GA",
])
def test_the_auction_s_own_negatives_never_verify(printed):
    records = _statement([(2, printed, 1500.0), (9, printed.replace("ID:1", "ID:2"), 1600.0),
                          (16, printed.replace("ID:1", "ID:3"), 1700.0)], holder="SAMPLE MOTORS LLC")
    assert {record.revenue_classification for record in records} <= {"unverified_deposit", "non_revenue"}


@pytest.mark.parametrize("printed", [
    "FABRIKAM MOTORS DES:PAYMENT ID:1 IND NAME:MANHEIM US", "FABRIKAM MOTORS DES:DISBURSEMENT ID:1 INDN:MANHEIM US",
    "ZELLE PAYMENT FROM JOHN SMITH MEMO MANHEIM US ACH PAYMNT CONF 1",
    "ZELLE PAYMENT TO MANHEIM US ACH PAYMNT DISBURSEMENT CONF 1",
])
def test_an_auction_alias_in_a_receiver_field_a_zelle_field_or_a_memo_never_names_the_auction(printed):
    records = _statement([(2, printed, 1500.0), (9, printed.replace("ID:1", "ID:2"), 1600.0),
                          (16, printed.replace("ID:1", "ID:3"), 1700.0)], holder="SAMPLE MOTORS LLC")
    assert not {record.revenue_canonical_entity for record in records} & {"Manheim", "ACV Auctions", "OPENLANE"}


@pytest.mark.parametrize("printed", ["ACV CAPITAL DES:FUNDING ID:1", "NEXTGEAR CAPITAL DES:ADVANCE ID:1",
                                     "KINETIC ADVANTAGE DES:PAYMENT ID:1", "WESTLAKE FLOORING DES:PAYMENT ID:1"])
def test_the_floor_plan_lenders_stay_financing_proceeds(printed):
    [record] = _statement([(2, printed, 15000.0)], holder="SAMPLE MOTORS LLC")
    assert (record.revenue_classification, record.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")


def test_an_afc_funding_credit_never_verifies():
    [record] = _statement([(2, "AFC FUNDNG DES:PAYMENT ID:1", 15000.0)], holder="SAMPLE MOTORS LLC")
    assert record.revenue_classification != "verified_revenue"


def test_an_auction_credit_paired_with_a_wire_to_the_auction_stays_unverified():
    records = _statement([(2, "WIRE TYPE:WIRE OUT DATE:540302 TIME:0900 ET TRN:1 BNF:MANHEIM US ID:1", -18000.0),
                          (9, "MANHEIM US DES:ACH PAYMNT ID:1", 18000.0)], holder="SAMPLE MOTORS LLC")
    assert records[1].revenue_matched_rule == "auction_credit_matches_same_source_debit"


def test_a_duplicated_auction_payout_is_non_revenue():
    records = classify_statement_transactions(Statement(account_name="SAMPLE MOTORS LLC", transactions=[
        Transaction(date="2054-03-02", description="MANHEIM US DES:ACH PAYMNT ID:1", amount=18000.0,
                    direction="credit", running_balance=19000.0),
        Transaction(date="2054-03-02", description="MANHEIM US DES:ACH PAYMNT ID:1", amount=18000.0,
                    direction="credit", running_balance=19000.0),
    ]))
    assert [record.revenue_classification for record in records] == ["verified_revenue", "non_revenue"]


def test_funding_vetoes_recurrence_except_on_the_three_platforms_that_print_it_on_settlements():
    etsy = _statement([(day, f"ETSY DES:FUNDING ID:{day}", 900.0 + day) for day in (2, 9, 16)])
    assert {record.revenue_classification for record in etsy} == {"unverified_deposit"}
    tapgoods = _statement([(day, f"TGPAYMENTS DES:FUNDING ID:{day}", 900.0 + day) for day in (2, 9, 16)])
    assert {record.revenue_match_method for record in tapgoods} == {"recurring_operating_source"}
```

Append to the end of `tests/test_revenue_platform_payouts.py`:

```python
def test_a_tiktok_card_refund_three_times_never_recurs():
    records = _statement([(2, "TIKTOK SHOP 1234567 CULVER CITY CA", 40.0), (9, "TIKTOK SHOP 1234567 CULVER CITY CA", 41.0),
                          (16, "TIKTOK SHOP 1234567 CULVER CITY CA", 42.0)])
    assert {record.revenue_classification for record in records} == {"unverified_deposit"}


def test_three_mis_signed_form_rows_stay_unverified():
    records = classify_statement_transactions(Statement(account_name="SAMPLE SHOP LLC", transactions=[
        Transaction(date=f"2054-03-{day:02d}", description="STP FBO WHATNOT INC FROM WHATNOT INC", amount=300.0,
                    direction="debit")
        for day in (2, 9, 16)
    ]))
    assert {record.revenue_match_method for record in records} == {"direction_conflict"}


def test_transport_rows_with_a_wallet_or_wire_word_never_recur():
    rows = [(day, f"SUPER DISPATCH CASH OUT {day}", 50.0 + day) for day in (2, 9, 16)]
    assert {record.revenue_classification for record in _statement(rows)} == {"unverified_deposit"}
```

Append to the end of `tests/test_revenue_payer_remittance.py`:

```python
def test_a_payer_the_statement_also_debits_goes_back_to_unverified():
    records = classify_statement_transactions(Statement(account_name="SAMPLE CAFE LLC", transactions=[
        Transaction(date="2054-03-02", description="NORTHWIND SUPPLY DES:VENDOR PAY ID:1", amount=5000.0,
                    direction="credit"),
        *(Transaction(date=f"2054-03-{day:02d}", description="NORTHWIND SUPPLY DES:DEBIT ID:2", amount=-250.0,
                      direction="debit") for day in (3, 4, 5, 6, 9)),
    ]))
    assert records[0].revenue_classification == "unverified_deposit"
    assert records[0].revenue_match_method == "payer_remittance_with_counter_debit"
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_revenue_recurrence.py tests/test_revenue_platform_payouts.py tests/test_revenue_payer_remittance.py -q -p no:cacheprovider`

Expected: FAIL: `31 failed, 86 passed`, the first with `AssertionError: assert ['operating_s...ires_context'] == ['operating_s...ating_source']`.

- [ ] **Step 3: Implement.**

In `analysis/transaction_classifier.py` (lines 21-23), replace:

```python
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
```

with:

```python
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
```

In `analysis/transaction_classifier.py` (lines 3504-3506), replace:

```python


def _apply_reversal_pair_context(
```

with:

```python


#: 5.5 (§6.2 pass 4): the reversal pair reads the credit markers of step 3, return codes included.
_PAIR_MARKER_PATTERNS = (*_REVERSAL_CANCELLATION_CREDIT_PATTERNS, *_RETURN_CODE_CREDIT_PATTERNS)


def _apply_reversal_pair_context(
```

In `analysis/transaction_classifier.py` (lines 3519-3522), replace:

```python
        credit_has_marker = _matches_any(
            credit.normalized_description,
            _REVERSAL_CANCELLATION_CREDIT_PATTERNS,
        )
```

with:

```python
        credit_has_marker = _matches_any(credit.normalized_description, _PAIR_MARKER_PATTERNS)
```

In `analysis/transaction_classifier.py` (lines 3534-3537), replace:

```python
            debit_has_marker = _matches_any(
                debit.normalized_description,
                _REVERSAL_CANCELLATION_CREDIT_PATTERNS,
            )
```

with:

```python
            debit_has_marker = _matches_any(debit.normalized_description, _PAIR_MARKER_PATTERNS)
```

In `analysis/transaction_classifier.py`, replace the whole function `_apply_operating_source_context` (lines 3610-3680) with:

```python
def _recurrence_vetoed(record: TransactionClassification, text: str) -> bool:
    """5.5 (§7.0): a credit that never counts toward recurrence and is never lifted by it: payroll, the recurrence
    veto words and card-credit labels (read on the row before its receiver fields), FUNDING outside the three
    platforms that print it on settlements (review C2), under the $1 floor, or a direction conflict."""
    return (
        record.classification == "payroll"
        or _recurrence_veto_word(text, record.account_name)
        or (
            record.revenue_canonical_entity not in _FUNDING_SETTLEMENT_ENTITIES
            and _recurrence_veto_word(text, record.account_name, _FUNDING_WORD)
        )
        or record.amount < _MICRO_DEPOSIT_FLOOR
        or record.revenue_match_method == "direction_conflict"
        or not record.direction_consistent
    )


def _recurrence_veto_word(text: str, account_name: str | None, pattern: re.Pattern[str] = _RECURRENCE_VETO) -> bool:
    """5.5 (§7.0): the recurrence veto on the row before its receiver fields. A veto word that is one of the holder's
    own words (its account name, or the name the bank prints in the receiver field), or the start of one (four
    letters or more), is not read: a delivery platform prints the merchant's store name, which is the holder's, in
    its entry field ('DOORDASH INC DES:<store> CAPITA ... INDN:<store> CAPITAL GROUP')."""
    holder = set(holder_words(account_name))
    for found in _RECEIVER_FIELD_VALUE.finditer(text):
        holder.update(_distinctive_words(found.group(0).split()[1:]))
    row = _before_receiver(text)
    for found in pattern.finditer(row):
        word = found.group(0)
        if len(word) >= 4 and any(own == word or own.startswith(word) for own in holder):
            continue
        return True
    return False


def _in_operating_pool(record: TransactionClassification) -> bool:
    """5.5 (§7.0): only a credit the operating registry decided, or that an operating-source method or an
    entity-naming card form verified, joins an entity's recurrence pool."""
    if record.revenue_canonical_entity is None:
        return False
    if record.revenue_match_method in _OPERATING_POOL_METHODS:
        return True
    return record.revenue_match_method == "operating_income_descriptor" and (
        record.revenue_matched_rule or ""
    ).startswith("card_settlement_form_")


def _upgrade_by_recurrence(
    record: TransactionClassification,
    *,
    entity: str,
    count: int,
    recurring: bool,
    business: bool,
    related_activity: bool,
    extra_signals: Sequence[str] = (),
) -> TransactionClassification:
    """The recurrence pass's verified record for one pooled credit (today's wording)."""
    signals = list(record.revenue_context_signals)
    if recurring:
        signals.append(f"recurring_source_{count}_credits")
    if business:
        signals.append("business_account")
    if related_activity:
        signals.append("related_platform_fee_or_chargeback")
    signals.extend(extra_signals)
    evidence_text = (
        f"recurs in {count} posted credits"
        if recurring
        else "has a related processing fee, commission, chargeback, or adjustment"
    )
    return _replace_revenue_state(
        record,
        "verified_revenue",
        match_method="recurring_operating_source" if recurring else "operating_source_related_activity",
        matched_rule=(
            "maintained_source_recurs_across_statement"
            if recurring
            else "maintained_source_has_related_operating_debit"
        ),
        confidence_score=0.90 if recurring else 0.88,
        reason=f"Maintained operating source '{entity}' {evidence_text}; the credit is verified as operating revenue.",
        context_signals=signals,
    )


def _apply_operating_source_context(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """Statement pass 5 (§6.2, §7.0): operating-source recurrence and related activity, fixed for every source.

    The pool admits only registry rows and operating-method rows (_in_operating_pool); it counts an entity's credits
    already verified by an operating-source method and upgrades only the unverified ones, so a per-row upgrade never
    shrinks it; a vetoed credit never counts and is never lifted (_recurrence_vetoed). A wholesale auction (§7.8) and
    a property-management platform (§7.10) take their own branches, and an unregistered NET SETTLE originator
    verifies with three such credits (§7.1)."""
    updated = list(records)
    pools: dict[str, list[int]] = {}
    activity_by_entity: dict[str, list[int]] = {}
    net_settle: dict[tuple[str, ...], list[int]] = {}
    for index, record in enumerate(records):
        if index in duplicate_indexes or not record.is_posted:
            continue
        text = revenue_text(record.normalized_description)
        if record.amount < 0:
            found = registry_match(text, OPERATING_REVENUE_READ_ALIASES)
            if found is not None and _read_inside_a_waiting_processor(text, *found):
                found = None
            if found is not None and _matches_any(text, _OPERATING_PLATFORM_DEBIT_CONTEXT_PATTERNS):
                activity_by_entity.setdefault(found[0], []).append(index)
            continue
        if record.amount <= 0 or _recurrence_vetoed(record, text):
            continue
        if _in_operating_pool(record):
            pools.setdefault(record.revenue_canonical_entity, []).append(index)
        elif (
            record.revenue_classification == "unverified_deposit"
            and record.revenue_match_method in {"ambiguous_credit_descriptor", "unidentified_posted_credit"}
            and channel_gate(text) is None
        ):
            form = _card_settlement_form(text, bank=record.bank)
            if form is not None and form.label == "net_settle":
                key = _payer_key(payer_region(text))
                if key:
                    net_settle.setdefault(key, []).append(index)

    for entity, indexes in pools.items():
        source_type = OPERATING_REVENUE_SOURCE_TYPES.get(entity)
        if source_type == "wholesale_auto_auction":
            _apply_auction_branch(updated, records, entity, indexes, duplicate_indexes)
            continue
        if source_type == "property_management_payments":
            _apply_property_branch(updated, records, entity, indexes)
            continue
        business = any(
            _business_account(records[index].account_name)
            if source_type != "customer_payment_platform"
            else _matches_any(
                account_name_text(records[index].account_name), _BUSINESS_ACCOUNT_PATTERNS
            )
            for index in indexes
        )
        count = len(indexes)
        recurring = count >= _RECURRENCE_MIN_CREDITS or (count >= _RECURRENCE_MIN_BUSINESS_CREDITS and business)
        related = bool(activity_by_entity.get(entity))
        if not recurring and not related:
            continue
        for index in indexes:
            record = updated[index]
            if record.revenue_classification != "unverified_deposit":
                continue
            updated[index] = _upgrade_by_recurrence(
                record, entity=entity, count=count, recurring=recurring, business=business, related_activity=related,
            )

    for indexes in net_settle.values():
        if len(indexes) < _NET_SETTLE_MIN_CREDITS:
            continue
        for index in indexes:
            updated[index] = _replace_revenue_state(
                updated[index],
                "verified_revenue",
                match_method="operating_income_descriptor",
                matched_rule="card_settlement_form_net_settle",
                confidence_score=0.90,
                reason=f"One originator's NET SETTLE entry recurs in {len(indexes)} posted credits: card settlements.",
                context_signals=(*updated[index].revenue_context_signals, "card_settlement_form"),
            )
    return updated


def _apply_auction_branch(
    updated: list[TransactionClassification],
    records: list[TransactionClassification],
    entity: str,
    indexes: Sequence[int],
    duplicate_indexes: set[int],
) -> None:
    """5.5 (§7.8): a dealer-only wholesale auction verifies only its observed payout form, never a buyer-payment
    reference, a floor-plan or financing word or a consumer entry (§14.1), and never a credit paired with an equal
    same-auction debit within 14 days (each debit used once)."""
    forms = _AUCTION_PAYOUT_FORMS.get(entity, ())
    refund_name = _AUCTION_REFUND_NAMES.get(entity)
    used_debits: set[int] = set()
    for index in indexes:
        record = updated[index]
        text = revenue_text(record.normalized_description)
        rule, verified = "auction_credit_without_payout_form", False
        if _AUCTION_BUYER_PAYMENT.search(text):
            rule = "auction_credit_prints_buyer_payment_reference"
        elif _AUCTION_VETO.search(_before_receiver(text)):
            rule = "auction_credit_prints_financing_or_consumer_word"
        elif any(form.search(text) for form in forms):
            pair = _auction_refund_pair(records, index, refund_name, used_debits, duplicate_indexes)
            if pair is not None:
                used_debits.add(pair)
                rule = "auction_credit_matches_same_source_debit"
            else:
                rule, verified = "wholesale_auto_auction_proceeds", True
        if verified:
            updated[index] = _replace_revenue_state(
                record,
                "verified_revenue",
                match_method="wholesale_auction_payout_form",
                matched_rule=rule,
                confidence_score=0.90,
                reason=f"A dealer-only wholesale auction ('{entity}') pays out in its observed payout form.",
                context_signals=(*record.revenue_context_signals, "wholesale_auction_payout_form"),
            )
        else:
            updated[index] = _replace_revenue_state(
                record,
                "unverified_deposit",
                match_method="operating_source_requires_context",
                matched_rule=rule,
                confidence_score=0.60,
                reason=f"A credit from the wholesale auction '{entity}' that is not its observed payout form.",
                context_signals=record.revenue_context_signals,
            )


def _auction_refund_pair(
    records: list[TransactionClassification],
    credit_index: int,
    refund_name: re.Pattern[str] | None,
    used: set[int],
    duplicate_indexes: set[int],
) -> int | None:
    """5.5 (§7.8): the index of an unused posted debit that names the auction (on its row or its wire BNF line), for
    the same amount to the cent, within 14 days of the credit; or None."""
    if refund_name is None:
        return None
    credit = records[credit_index]
    credit_date = parse_date(credit.date)
    for index, debit in enumerate(records):
        if (
            index in used or index in duplicate_indexes or debit.amount >= 0 or not debit.is_posted
            or round(abs(debit.amount), 2) != round(credit.amount, 2)
            or not refund_name.search(debit.normalized_description)
            or re.search(r"\bACV CAPITAL\b", debit.normalized_description)
        ):
            continue
        debit_date = parse_date(debit.date)
        if credit_date is not None and debit_date is not None and abs(
            (credit_date - debit_date).days
        ) > _AUCTION_REFUND_WINDOW_DAYS:
            continue
        return index
    return None


def _apply_property_branch(
    updated: list[TransactionClassification],
    records: list[TransactionClassification],
    entity: str,
    indexes: Sequence[int],
) -> None:
    """5.5 (§7.10, T15): a property-management platform verifies by recurrence of its ACH payout shape only (three
    credits, or two in a business account), never by a related fee debit. A row printing owner, distribution or
    deposit wording is left out of the count and stays unverified; micro-deposits never count; a push-shaped row
    stays operating_source_requires_context. A verified row carries the property-management chip."""
    counted: list[int] = []
    for index in indexes:
        record = updated[index]
        text = revenue_text(record.normalized_description)
        row = _before_receiver(text)
        if _PROPERTY_PLATFORM_GUARD.search(row):
            updated[index] = _replace_revenue_state(
                record,
                "unverified_deposit",
                match_method="operating_source_requires_context",
                matched_rule="property_platform_owner_or_deposit_wording",
                confidence_score=0.60,
                reason=f"A '{entity}' credit prints owner, distribution or deposit wording.",
                context_signals=record.revenue_context_signals,
            )
            continue
        if _PROPERTY_MICRO_DEPOSIT.search(row) or _PROPERTY_PUSH_SHAPE.search(row):
            continue
        if not _ELECTRONIC_PAYMENT_FORM.search(row):
            continue
        counted.append(index)
    business = any(_business_account(records[index].account_name) for index in counted)
    count = len(counted)
    if not (count >= _RECURRENCE_MIN_CREDITS or (count >= _RECURRENCE_MIN_BUSINESS_CREDITS and business)):
        return
    for index in counted:
        record = updated[index]
        if record.revenue_classification != "unverified_deposit":
            continue
        updated[index] = _upgrade_by_recurrence(
            record, entity=entity, count=count, recurring=True, business=business, related_activity=False,
            extra_signals=("property_management_collections",),
        )


def _payer_key(region: str) -> tuple[str, ...]:
    """5.6 (§5.2): the payer key: the payer name's words without the generic words, at most the first four."""
    return tuple(word for word in payer_name(region).split() if word not in REVENUE_GENERIC_WORDS)[:4]


def _payer_first_distinctive_word(region: str) -> str | None:
    """5.5 (§7.5, §8.1): the payer's first distinctive word: four or more letters, not an AP, bank-template,
    legal-suffix, generic or public-payer word, and not a common name-starter."""
    words = [word for word in _distinctive_words(payer_name(region).split()) if word not in _counter_debit_skip_words()]
    return _first_distinctive_word(words)


def _debit_first_distinctive_word(record: TransactionClassification) -> str | None:
    """5.5 (§7.5, §8.1): a posted debit's first distinctive word, read on its D11 payee words."""
    words = [
        word for word in _distinctive_words(_unknown_payee_tokens(record.normalized_description))
        if word not in _counter_debit_skip_words()
    ]
    return _first_distinctive_word(words)


def _apply_payer_remittance_counter_debit_guard(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """Statement pass 6 (§6.2, §7.5): a credit the payer-remittance rule verified goes back to unverified when a
    posted debit in the same statement shares the payer's first distinctive word (an own account, an affiliate or a
    funder that collects)."""
    debit_words = {
        word
        for index, record in enumerate(records)
        if index not in duplicate_indexes and record.amount < 0 and record.is_posted
        and (word := _debit_first_distinctive_word(record)) is not None
    }
    updated = list(records)
    for index, record in enumerate(records):
        if record.revenue_match_method != "payer_remittance_descriptor":
            continue
        word = _payer_first_distinctive_word(payer_region(revenue_text(record.normalized_description)))
        if word is None or word not in debit_words:
            continue
        updated[index] = _replace_revenue_state(
            record,
            "unverified_deposit",
            match_method="payer_remittance_with_counter_debit",
            matched_rule="payer_also_debited_in_statement",
            confidence_score=0.50,
            reason="The payer of this accounts-payable remittance is also debited in the statement.",
            context_signals=(*record.revenue_context_signals, "payer_also_debited"),
        )
    return updated
```

In `analysis/transaction_classifier.py` (line 4393), replace:

```python
    records = _apply_operating_source_context(records, set(duplicate_of))
```

with:

```python
    records = _apply_operating_source_context(records, set(duplicate_of))
    records = _apply_payer_remittance_counter_debit_guard(records, set(duplicate_of))
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_revenue_recurrence.py tests/test_revenue_platform_payouts.py tests/test_revenue_payer_remittance.py -q -p no:cacheprovider`

Expected: PASS: `117 passed`.

- [ ] **Step 5: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-CLASSIFIER: `755 passed, 2 deselected`

- [ ] **Step 6: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/transaction_classifier.py tests/test_revenue_payer_remittance.py tests/test_revenue_platform_payouts.py tests/test_revenue_recurrence.py
git commit -m "classifier: the 5.5 statement passes (recurrence, auctions, property, counter-debit)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S2.5: Classification 5.5 and analysis stage 24

**Files:**
- Modify: `analysis/transaction_classifier.py:113-115`
- Modify: `webapp/artifact_cache.py:571-573`
- Modify (pins): `tests/test_artifact_cache.py:488, 497-499`
- Modify (pins): `tests/test_flag_group_states.py:60-63`
- Modify (pins): `tests/flagged_payloads.py:17-18`
- Modify (pins): `tests/test_lender_census.py:38`
- Modify (pins): `tests/test_webapp_reanalysis.py:1060`

**Depends on:** S2.4 (and S1.5 if it has landed).

**Interfaces:**
- Consumes: S2.4.
- Produces:
  - `CLASSIFICATION_VERSION = "5.5"`, `ANALYSIS_STAGE_VERSION = 24`

**Why:** Spec §9.3: "5.5 (the fixes, §7): `CLASSIFICATION_VERSION = "5.5"`, and `ANALYSIS_STAGE_VERSION` 23 → 24 in the same commit." Stored rows change revenue state, so a warm cache keyed on 23 would serve them; a re-analysis recomputes the analysis stage (OCR stays cached), and older saved analyses are marked outdated. The five version pins move with it.

- [ ] **Step 1: Re-pin the assertions this task moves (pin ledger rows 13-18).**

In `tests/test_artifact_cache.py` (line 488), replace:

```python
def test_analysis_stage_version_is_pinned_at_23():
```

with:

```python
def test_analysis_stage_version_is_pinned_at_24():
```

In `tests/test_artifact_cache.py` (lines 497-499), replace:

```python
    2026-09-28: a counted lender, no longer a line of credit) goes 22 -> 23. This
    is that pin."""
    assert ANALYSIS_STAGE_VERSION == 23
```

with:

```python
    2026-09-28: a counted lender, no longer a line of credit) goes 22 -> 23. The
    true-revenue bug fixes (classification 5.5, 2026-09-28) go 23 -> 24. This is
    that pin."""
    assert ANALYSIS_STAGE_VERSION == 24
```

In `tests/test_flag_group_states.py` (lines 60-63), replace:

```python
    # 5.4/23: the owner ruling of 2026-09-28: Idea Financial is a counted lender, no longer a line of credit.
    assert CLASSIFICATION_VERSION == "5.4"
    assert classify_transaction("FABRICATED ROW", -10.0).classification_version == "5.4"
    assert ANALYSIS_STAGE_VERSION == 23
```

with:

```python
    # 5.4/23: the owner ruling of 2026-09-28: Idea Financial is a counted lender, no longer a line of credit.
    # 5.5/24: the true-revenue bug fixes (2026-09-28 design, §7).
    assert CLASSIFICATION_VERSION == "5.5"
    assert classify_transaction("FABRICATED ROW", -10.0).classification_version == "5.5"
    assert ANALYSIS_STAGE_VERSION == 24
```

In `tests/flagged_payloads.py` (lines 17-18), replace:

```python
#: the false-positive release, and 5.3 -> 5.4 with the Idea Financial ruling (2026-09-28).
CURRENT_VERSION = "5.4"
```

with:

```python
#: the false-positive release, 5.3 -> 5.4 with the Idea Financial ruling (2026-09-28), and 5.4 -> 5.5 with the
#: true-revenue bug fixes.
CURRENT_VERSION = "5.5"
```

In `tests/test_lender_census.py` (line 38), replace:

```python
    assert result["classification_version"] == "5.4"
```

with:

```python
    # 5.5: the true-revenue bug fixes (2026-09-28).
    assert result["classification_version"] == "5.5"
```

In `tests/test_webapp_reanalysis.py` (line 1060), replace:

```python
    assert {record["classification_version"] for record in records.values()} == {"5.4"}
```

with:

```python
    # 5.5: the true-revenue bug fixes (2026-09-28).
    assert {record["classification_version"] for record in records.values()} == {"5.5"}
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_artifact_cache.py tests/test_flag_group_states.py tests/test_lender_census.py tests/test_webapp_reanalysis.py -q -p no:cacheprovider`

Expected: FAIL: `4 failed, 212 passed`, the first with `assert 23 == 24`.

- [ ] **Step 3: Implement.**

In `analysis/transaction_classifier.py` (lines 113-115), replace:

```python
#: CREDIT stay Lines of credit, D9). Moves with
#: `webapp.artifact_cache.ANALYSIS_STAGE_VERSION`.
CLASSIFICATION_VERSION = "5.4"
```

with:

```python
#: CREDIT stay Lines of credit, D9). 5.5 (2026-09-28): the true-revenue bug fixes
#: (docs/superpowers/specs/2026-09-28-true-revenue-design.md §7): the revenue
#: text readers, the operating registry, card and payout forms, the recurrence
#: pass, payer remittance, public and healthcare payers, wires that cite an
#: invoice, auctions and property platforms, and the non-revenue narrowings.
#: Moves with `webapp.artifact_cache.ANALYSIS_STAGE_VERSION`.
CLASSIFICATION_VERSION = "5.5"
```

In `webapp/artifact_cache.py` (lines 571-573), replace:

```python
# them; a re-analysis recomputes the analysis stage from the cached reading. OCR
# stays cached. Pinned in the same change (`tests/test_artifact_cache.py`).
ANALYSIS_STAGE_VERSION = 23
```

with:

```python
# them; a re-analysis recomputes the analysis stage from the cached reading. OCR
# stays cached. Pinned in the same change (`tests/test_artifact_cache.py`).
# 23 -> 24: TRUE-REVENUE bug fixes (2026-09-28 design, §7) — classification
# version 5.5: credits move between verified_revenue, unverified_deposit and
# non_revenue (card and payout forms, the recurrence pass, payer remittance,
# public and healthcare payers, invoice wires, the non-revenue narrowings), and
# SQ CAP and SBA or EIDL credits become financing proceeds. Stored rows change
# revenue state, so a warm cache keyed on 23 would serve them; a re-analysis
# recomputes the analysis stage from the cached reading. OCR stays cached.
# Pinned in the same change (`tests/test_artifact_cache.py`).
ANALYSIS_STAGE_VERSION = 24
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_artifact_cache.py tests/test_flag_group_states.py tests/test_lender_census.py tests/test_webapp_reanalysis.py -q -p no:cacheprovider`

Expected: PASS: `216 passed`.

- [ ] **Step 5: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-CLASSIFIER: `755 passed, 2 deselected`
  - SEL-REGISTRY: `362 passed, 4 skipped`
  - SEL-WEBAPP: `856 passed`
  - SEL-REVENUE: `522 passed`

  Then the full suite: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests -q -p no:cacheprovider`. Expected: only the 16 known failures of `C:/Users/GustavoPrietodePaula/lender-research/census/failed-ld-final.txt` (measured at this task's commit: 13,902 passed, 55 skipped, 39 deselected, 16 failed).

- [ ] **Step 6: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/transaction_classifier.py tests/flagged_payloads.py tests/test_artifact_cache.py tests/test_flag_group_states.py tests/test_lender_census.py tests/test_webapp_reanalysis.py webapp/artifact_cache.py
git commit -m "versions: classification 5.5 and analysis stage 24 for the true-revenue fixes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## S3: The census

### Task S3.1: The revenue census tool

**Files:**
- Create: `tools/revenue_census.py`
- Create: `tests/test_revenue_census.py`

**Depends on:** S2.5.

**Interfaces:**
- Consumes: S2.1's readers (`revenue_text`, `payer_region`, `channel_gate`, `holder_named`, `numbered_company`); from S4.2 on, `analysis.true_revenue.guard_facts` (read when present).
- Produces:
  - `python -m tools.revenue_census snapshot --data-dir <dir> | --jobs-db <db> --out <file> [--code-root <dir>] [--limit N]`
  - `python -m tools.revenue_census compare --base <file> --after <file> [--after <file>] --out <file>` (exit 0 when every guard holds, 1 when one fails, 2 when refused)
  - `python -m tools.revenue_census sample --snapshot <file> --out <file>`
  - `snapshot(accounts) -> dict`, `compare(base, afters) -> dict`, `precision_sample(snap, *, per_stratum=20, largest_counted=50, seed=55) -> dict`, `_row_guards(credit) -> dict[str, bool]`, `_account_guards(account, tiered) -> list[dict]`, `NARROWINGS`, `BNPL_ENTITIES`, `DECLARED_DEMOTIONS`, `REGISTRY_VERIFYING_METHODS`, `IDENTITY_METHODS`, `TIER_STATES`, `PRECISION_STRATA`
  - per account: `posted_credit_count`, `posted_credit_cents`, `tier_totals`; per credit: `lender_credit` and the facts `third_party_originator`, `own_transfer`, `pool_candidate`, `pool_vetoed`, `pool_threshold`; per run: `lender_credit_moves_by_cause`, the failure key `undeclared_demotion`

**Why:** Spec §14.2 and §14.3: `tools/revenue_census.py` re-classifies every reconciled, de-duplicated cached analysis (or a copy of the tryout host's job store) with one checkout's code, keeps every `non_revenue` row, masks every digit, and compares a base with later snapshots: shares, $0 statements, medians, tiers and reasons, the move matrix, every row that left `non_revenue` by narrowing, every verified demotion by declared cause, eligible-deposit moves, the gate by held reason, the street-`LN` changes (G7b), and the guards G1 to G14 (G7 is `tools/lender_census.py`; G8 is the suite) with the review's G15 to G17 (refund words, tax refunds and the holder's own ACH transfer in True). After the review (I1): G9 checks every posted credit's tier against its state, the metrics' tier totals, and fails an unmatched account or a classification error; an undeclared verified demotion fails; narrowing 4 needs a printed third-party originator and narrowing 8 one of the five BNPL entities; G10 checks the push-rail half; G13 reads the full numbered-company guard; G12 the credit-union count and the loan-word veto; G14 every row that counted toward a lifted pool; G2 a registry row's own root; and the lender-credit and eligible-deposit moves are reported by cause (M2). `sample` draws §14.5's precision sample. It refuses to write inside the repository. The one test that needs the tiers joins in S4.2.

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_revenue_census.py`:

```python
"""True revenue spec §14.2, §14.3 and §14.5: the revenue census (tools/revenue_census.py) on fabricated snapshots.
The census itself runs only on the local cache and on a copy of the tryout host's job store; these tests feed it
hand-built snapshots and one fabricated statement analysed by the real code."""
from __future__ import annotations

import gzip
import json

import pytest

from tools import revenue_census as census


def _credit(i, cents, state, method, *, tier=None, reason=None, text="FABRICATED ROW", rule=None, entity=None,
            lender_credit=False, **facts):
    return {"i": i, "cents": cents, "state": state, "method": method, "rule": rule, "entity": entity, "tier": tier,
            "reason": reason, "class": "other", "lender_credit": lender_credit, "text": text, "facts": facts}


def _account(credits, *, gated=False, deposits=1000.0):
    return {"bank": "FABRICATED BANK", "rows": 10, "credits": credits,
            "posted_cents": sum(credit["cents"] for credit in credits), "lender_credits": 0.0,
            "posted_credit_count": len(credits), "posted_credit_cents": sum(credit["cents"] for credit in credits),
            "tier_totals": None, "eligible_deposits": deposits, "revenue_review_required": gated}


def _snap(version, accounts, skipped=None):
    return {"classification_version": version, "accounts": accounts, "skipped": skipped or {}}


def _run(base, after):
    return census.compare(base, [after])["runs"][0]


BASE = _snap("5.4", {"a": _account([
    _credit(0, 70000, "verified_revenue", "operating_income_descriptor"),
    _credit(1, 30000, "unverified_deposit", "deposit_source_requires_review"),
    _credit(2, 90000, "unverified_deposit", "deposit_source_requires_review"),
    _credit(3, 10000, "non_revenue", "strong_non_revenue_rule", text="BOOK TRANSFER CREDIT B O FABRIKAM INC"),
])})
AFTER = _snap("5.6", {"a": _account([
    _credit(0, 70000, "verified_revenue", "named_payer_company_form", tier="verified"),
    _credit(1, 30000, "unverified_deposit", "check_deposit_requires_review", tier="counted_flagged",
            reason="check_deposit"),
    _credit(2, 90000, "unverified_deposit", "deposit_source_requires_review", tier="excluded_pending_review",
            reason="financing_named_payer", financing_root=True),
    _credit(3, 10000, "unverified_deposit", "wire_requires_review", tier="counted_flagged",
            reason="wire_named_sender", text="BOOK TRANSFER CREDIT B O FABRIKAM INC", third_party_originator=True),
], gated=True)})


def test_the_summary_reports_true_verified_and_the_reasons():
    report = census.compare(BASE, [AFTER])
    summary = report["runs"][0]["summary"]
    assert (summary["true_share"], summary["verified_share"], summary["held_share"]) == (55.0, 35.0, 45.0)
    assert summary["zero_true_statements"] == 0 and summary["gated_share"] == 100.0
    assert summary["reasons"]["excluded_pending_review/financing_named_payer"] == {"rows": 1, "dollars": 900.0}
    assert report["base"]["true_share"] is None and report["base"]["verified_share"] == 35.0


def test_a_row_that_leaves_non_revenue_names_its_narrowing():
    run = _run(BASE, AFTER)
    assert run["left_non_revenue"] == {"4_book_or_funds_transfer": {"rows": 1, "dollars": 100.0, "statements": 1}}
    assert run["guards"] == {}
    assert run["gated_statements_by_held_reason"] == {"financing_named_payer": 1}


def test_a_row_that_leaves_non_revenue_by_no_narrowing_fails_g1():
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["a"]["credits"][3]["text"] = "FABRICATED ROW"
    assert _run(BASE, after)["guards"]["G1"]["failures"] == 1


def test_a_book_transfer_leaves_non_revenue_only_on_a_third_party_originator():
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["a"]["credits"][3]["facts"]["third_party_originator"] = False
    run = _run(BASE, after)
    assert run["left_non_revenue"] == {"outside_the_narrowings": {"rows": 1, "dollars": 100.0, "statements": 1}}
    assert run["guards"]["G1"]["failures"] == 1


@pytest.mark.parametrize(("entity", "cause"), [("AFFIRM", "8_oq2_bnpl_settlement"),
                                               ("FABRIKAM FUNDING LLC", "outside_the_narrowings")])
def test_only_the_five_bnpl_settlements_leave_d1_by_the_owner_s_ruling(entity, cause):
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "non_revenue", "financing_proceeds_credit", entity=entity,
                                                lender_credit=True)])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                 reason="payout_credit_entity", entity=entity)])})
    run = _run(base, after)
    assert list(run["left_non_revenue"]) == [cause]
    assert ("G1" in run["guards"]) is (cause == "outside_the_narrowings")
    moved = {"8_oq2_bnpl_settlement": "8_oq2_bnpl_settlement", "outside_the_narrowings": "left:x"}[cause]
    assert run["lender_credit_moves_by_cause"][moved]["eligible_deposit_dollars"] == 50.0


@pytest.mark.parametrize(("guard", "credit"), [
    ("G2", _credit(0, 100, "verified_revenue", "named_payer_company_form", tier="verified", financing_root=True)),
    ("G2", _credit(0, 100, "verified_revenue", "recurring_operating_source", tier="verified", registry_root=True)),
    ("G3", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="p2p", holder=True)),
    ("G4", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="p2p",
                   transfer_no_counterparty=True)),
    ("G6", _credit(0, 100, "verified_revenue", "direction_conflict", tier="verified")),
    ("G10", _credit(0, 100, "verified_revenue", "operating_income_descriptor", tier="verified", gate="closed")),
    ("G10", _credit(0, 100, "verified_revenue", "named_payer_repeats", tier="verified", gate="push")),
    ("G11", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="p2p", pay_or_personal=True)),
    ("G12", _credit(0, 100, "verified_revenue", "auto_lender_dealer_funding", tier="verified", q7_payer_ok=False)),
    ("G12", _credit(0, 100, "verified_revenue", "auto_lender_dealer_funding", tier="verified", q7_payer_ok=True,
                    q7_veto_word=True)),
    ("G13", _credit(0, 100, "verified_revenue", "named_payer_company_form", tier="verified", numbered=True)),
    ("G13", _credit(0, 100, "verified_revenue", "recurring_operating_source", tier="verified", numbered_region=True)),
    ("G14", _credit(0, 100, "verified_revenue", "recurring_operating_source", tier="verified",
                    pooled_while_vetoed=True)),
    ("G5", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="p2p", known_financing=True)),
    ("G15", _credit(0, 100, "verified_revenue", "named_payer_repeats", tier="verified",
                    text="FABRIKAM INC DES CUSTREFUNDS ID #")),
    ("G15", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="named_payer_one_off",
                    text="FABRIKAM INC DES PREFUND ID #")),
    ("G16", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="named_payer_one_off",
                    text="FRANCHISE TAX BD DES CASTTAXRFD ID #")),
    ("G16", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="named_payer_one_off",
                    text="IRS TREAS ### DES TAXEIC ID #")),
    ("G17", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="p2p", own_transfer=True)),
])
def test_each_row_guard_fails_on_its_row(guard, credit):
    assert census._row_guards(credit)[guard] is True


def test_the_row_guards_hold_on_clean_rows():
    clean = [
        # A registry row reads G2 on its own root (the holder's words and §7.0's FUNDING settlements aside).
        _credit(0, 100, "verified_revenue", "recurring_operating_source", tier="verified", financing_root=True),
        # A push-rail row the registry verified.
        _credit(0, 100, "verified_revenue", "operating_source_with_credit_context", tier="verified", gate="push"),
        # A refund word the bank prints in the receiver field is the holder's, not the row's.
        _credit(0, 100, "verified_revenue", "named_payer_repeats", tier="verified",
                text="FABRIKAM INC DES PAYMENT INDN REFUNDS DEPT"),
        # A held refund is out of True.
        _credit(0, 100, "unverified_deposit", "x", tier="excluded_pending_review", reason="non_sale_purpose",
                text="FABRIKAM INC DES REFUNDS ID #"),
        # A processor's card settlement printed after BMO's MISC PAYMENT <digits> template: its payer is the processor.
        _credit(0, 100, "verified_revenue", "operating_income_descriptor", tier="verified", numbered=True,
                rule="card_settlement_form_gbl_brand", text="MISC PAYMENT ####### GBL VI"),
    ]
    assert not any(value for credit in clean for value in census._row_guards(credit).values())


def test_a_processor_s_template_row_is_listed_apart_from_g13():
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "unverified_deposit", "x")])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "verified_revenue", "operating_income_descriptor",
                                                 tier="verified", numbered=True, rule="card_settlement_form_gbl_brand",
                                                 text="MISC PAYMENT ####### GBL VI")])})
    run = _run(base, after)
    assert "G13" not in run["guards"]
    assert run["g13_listed_apart"] == {"operating_income_descriptor": {"rows": 1, "dollars": 50.0, "statements": 1}}


def test_the_four_tier_identity_is_checked_on_every_account():
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["a"]["posted_cents"] += 1
    assert _run(BASE, after)["guards"]["G9"]["failures"] >= 1


@pytest.mark.parametrize("breakage", ["tier_state", "no_state", "metrics", "unmatched", "error_skip"])
def test_g9_fails_on_every_way_an_account_can_fall_out_of_the_identity(breakage):
    after = json.loads(json.dumps(AFTER))
    account = after["accounts"]["a"]
    if breakage == "tier_state":
        account["credits"][0]["tier"] = "counted_flagged"
    elif breakage == "no_state":
        account["posted_credit_count"] += 1
    elif breakage == "metrics":
        account["tier_totals"] = {"verified": 70000, "counted_flagged": 40000, "excluded_pending_review": 0,
                                  "non_revenue": 90000}
    elif breakage == "unmatched":
        after["accounts"] = {"b": account}
    else:
        after["skipped"] = {"ValueError": 1}
    assert _run(BASE, after)["guards"]["G9"]["failures"] >= 1


def test_the_metrics_tier_totals_that_agree_hold():
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["a"]["tier_totals"] = {"verified": 70000, "counted_flagged": 40000,
                                             "excluded_pending_review": 90000, "non_revenue": 0}
    assert "G9" not in _run(BASE, after)["guards"]


@pytest.mark.parametrize(("rows", "fails"), [(1, True), (2, False)])
def test_a_credit_union_s_dealer_funding_needs_two_credits(rows, fails):
    credits = [_credit(i, 3000000, "verified_revenue", "auto_lender_dealer_funding", tier="verified",
                       q7_payer_ok=True, q7_credit_union=True, q7_listed=False) for i in range(rows)]
    base = _snap("5.4", {"a": _account([_credit(i, 3000000, "unverified_deposit", "x") for i in range(rows)])})
    assert ("G12" in _run(base, _snap("5.6", {"a": _account(credits)}))["guards"]) is fails


@pytest.mark.parametrize(("vetoed", "fails"), [(2, True), (0, False)])
def test_a_recurrence_lift_needs_its_count_without_the_vetoed_rows(vetoed, fails):
    credits = [_credit(i, 50000 + i, "verified_revenue", "recurring_operating_source", tier="verified",
                       entity="Stripe", pool_candidate=True, pool_vetoed=i < vetoed, pool_threshold=3)
               for i in range(3)]
    base = _snap("5.4", {"a": _account([_credit(i, 50000 + i, "unverified_deposit", "x") for i in range(3)])})
    assert ("G14" in _run(base, _snap("5.6", {"a": _account(credits)}))["guards"]) is fails


def test_a_text_the_street_ln_guard_changed_is_listed_and_never_financing_into_true():
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "non_revenue", "financing_proceeds_credit",
                                                text="DEPOSIT 12 OAK LOAN")])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                 reason="no_payer_printed", text="DEPOSIT 12 OAK LN")])})
    run = _run(base, after)
    assert run["street_ln_changes"][0]["base"] == "non_revenue|financing_proceeds_credit"
    assert run["guards"]["G7b"]["failures"] == 1


def test_a_verified_row_demoted_without_a_declared_cause_fails_the_census():
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "verified_revenue", "operating_income_descriptor")])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                 reason="named_payer_one_off")])})
    run = _run(base, after)
    assert run["verified_demotions"] == {"undeclared": {"rows": 1, "dollars": 50.0, "statements": 1}}
    assert run["guards"]["undeclared_demotion"]["failures"] == 1


def test_the_precision_sample_draws_each_stratum_and_the_largest_counted_rows():
    accounts = {f"s{n}": _account([
        _credit(0, 1000 + n, "verified_revenue", "named_payer_company_form", tier="verified"),
        _credit(1, 500 * n, "unverified_deposit", "x", tier="counted_flagged", reason="p2p"),
        _credit(2, 700, "verified_revenue", "recurring_operating_source", tier="verified", holder=True),
    ]) for n in range(60)}
    accounts["forms"] = _account([
        _credit(0, 900, "verified_revenue", "operating_income_descriptor", tier="verified",
                rule="card_settlement_form_bankcard"),
        _credit(1, 800, "verified_revenue", "operating_source_with_credit_context", tier="verified", numbered=True),
    ])
    accounts["forms"]["credits"][1]["alias"] = "whatnot_fbo_form"
    sample = census.precision_sample(_snap("5.6", accounts))
    assert len(sample["q6b_company_form"]) == 20 and len(sample["holder_test_rows"]) == 20
    assert [row["dollars"] for row in sample["numbered_template_rows"]] == [8.0]
    assert sorted(row["dollars"] for row in sample["card_and_payout_forms"]) == [8.0, 9.0]
    assert [row["dollars"] for row in sample["largest_counted"][:2]] == [295.0, 290.0]
    assert len(sample["largest_counted"]) == 50 and all(row["sort"] == "" for row in sample["largest_counted"])


def test_the_sample_command_writes_outside_the_repository(tmp_path, capsys):
    snapshot = tmp_path / "s56.json.gz"
    snapshot.write_bytes(gzip.compress(json.dumps(_snap("5.6", {"a": _account([
        _credit(0, 5000, "verified_revenue", "named_payer_repeats", tier="verified")])})).encode("utf-8")))
    assert census.main(["sample", "--snapshot", str(snapshot), "--out", str(tmp_path / "sample.json")]) == 0
    assert json.loads((tmp_path / "sample.json").read_text(encoding="utf-8"))["q6a_repeats"][0]["dollars"] == 50.0
    assert census.main(["sample", "--snapshot", str(snapshot), "--out", str(census.ROOT / "sample.json")]) == 2


def test_the_cli_refuses_to_write_inside_the_repository(tmp_path, capsys):
    snapshot = tmp_path / "base.json.gz"
    snapshot.write_bytes(gzip.compress(json.dumps(BASE).encode("utf-8")))
    inside = census.ROOT / "census-output.json"
    assert census.main(["compare", "--base", str(snapshot), "--after", str(snapshot), "--out", str(inside)]) == 2
    assert "inside the repository" in capsys.readouterr().err
    assert not inside.exists()
    outside = tmp_path / "report.json"
    assert census.main(["compare", "--base", str(snapshot), "--after", str(snapshot), "--out", str(outside)]) == 0
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_revenue_census.py -q -p no:cacheprovider`

Expected: FAIL: `1 error`, the first with `ImportError: cannot import name 'revenue_census' from 'tools' (unknown location)`.

- [ ] **Step 3: Implement.**

Create `tools/revenue_census.py`:

```python
"""Revenue census over the local artifact cache or a copy of the tryout host's job store (true revenue spec §14.2).
Local only; never run in CI.

`snapshot` re-classifies every reconciled, de-duplicated cached analysis with the `analysis` package of one checkout
(`--code-root`) and records, per account, every posted credit's revenue decision (state, method, rule, tier, reason,
entity, amount in cents, the digit-masked normalized text) and, where the checkout has them, the guard facts of
§14.3 read with that checkout's readers. `compare` reads a base snapshot and one or two later ones and reports the
shares, the tiers and reasons, the move matrix, every row that left `non_revenue` (by the narrowing of §6.3 that moved
it), every verified row that lost its verification (by declared cause), the lender-credit and eligible-deposit moves
by cause, the package gate, and the guards G1 to G17 (G7 is tools/lender_census.py; G15 to G17 are the review's
refund, tax-refund and own-account-transfer guards). Every figure it prints is a count, a share or a total;
descriptors stay in the output file, digit-masked, outside the repository.

Usage, from the repository root of the checkout that holds this tool:
    python -m tools.revenue_census snapshot --data-dir <webapp_data> --out <file> [--code-root <checkout>] [--limit N]
    python -m tools.revenue_census snapshot --jobs-db <webapp.db copy> --out <file> [--code-root <checkout>]
    python -m tools.revenue_census compare --base <file> --after <file> [--after <file>] --out <file>
    python -m tools.revenue_census sample --snapshot <5.6 file> --out <file>

`sample` draws §14.5's precision sample (up to 20 Verified rows of each stratum, the Verified rows the holder test
matches, and the 50 largest counted rows), digit-masked, with an empty `sort` for the reviewer.

Exit codes: snapshot and sample 0, or 2 when refused. compare 0 when every guard holds, 1 when one fails, 2 when
refused.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_DIGITS = re.compile(r"\d")

#: The non-revenue rules whose rows G1 follows (§14.3): reversal, insurer, D1, descriptor proceeds, potential
#: lender, strong non-revenue and duplicates.
NON_REVENUE_METHODS = frozenset({
    "reversal_cancellation_exclusion", "insurance_provider_credit_exclusion", "financing_proceeds_credit",
    "potential_lender_registry_credit_exclusion", "strong_non_revenue_rule", "duplicate_credit_exclusion",
    "matched_reversal_pair",
})
#: §6.3's narrowings, plus the owner's OQ2 ruling (BNPL settlements join PAYOUT_CREDIT_ENTITIES), in the order the
#: census tests them. Each is (name, whether it may lead to True).
NARROWINGS = (
    ("1_reimbursement_claim_signal", True),
    ("2_hcclaimpmt_insurer", True),
    ("3_insurer_customer_payment", False),
    ("4_book_or_funds_transfer", True),
    ("5_street_ln", True),
    ("6_card_credit_release", True),
    ("7_q7_dealer_funding", True),
    ("8_oq2_bnpl_settlement", True),
)
#: OQ2 (§19): the five BNPL providers whose settlements left D1, by their ledger entity names.
BNPL_ENTITIES = frozenset({"AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit"})
#: The declared causes of a verified row losing its verification (§7.0, §7.11, §7.7), and the two consequences of the
#: recurrence fixes this plan declares (Decisions): a pool that one of its members' re-reading splits between two
#: entities, and a pool left below the recurrence count once a declared veto takes a member out. Any other cause fails.
DECLARED_DEMOTIONS = (
    "square_capital", "square_payroll", "acctverify", "channel_gate", "holder_veto", "customer_id",
    "claim_first_off", "recurrence_veto", "sq_cap_or_sba", "new_non_revenue_marker", "reversal_pair",
    "entity_split", "direction_conflict_pool", "micro_deposit_floor", "pool_below_recurrence_after_a_declared_veto",
)
#: The operating-registry methods (§8.9).
REGISTRY_METHODS = frozenset({
    "operating_source_requires_context", "operating_source_with_credit_context", "recurring_operating_source",
    "operating_source_related_activity", "wholesale_auction_payout_form",
})
#: G10: the methods that may verify a real-time or push-rail row (step 10, the registry, §6.1 step 9b).
REGISTRY_VERIFYING_METHODS = REGISTRY_METHODS - {"operating_source_requires_context"}
#: G3: the rules that verify on the payer's identity or remittance (step 11's descriptors, steps 12 to 14, Q5, Q6).
IDENTITY_METHODS = frozenset({
    "payer_remittance_descriptor", "public_payer_remittance", "wire_remittance_purpose", "repeat_wire_sender",
    "named_payer_repeats", "named_payer_company_form", "public_or_healthcare_payer",
})
#: G9: the four tiers and the state each goes with (§5.4).
TIER_STATES = {"verified": {"verified_revenue"}, "non_revenue": {"non_revenue"},
               "counted_flagged": {"unverified_deposit"}, "excluded_pending_review": {"unverified_deposit"}}
#: G12: a credit union's dealer funding needs this many such credits in the statement (§8.7).
CREDIT_UNION_DEALER_MIN_CREDITS = 2
#: The snapshot skips that are the credit census's filter, not a failure (§14.2).
FILTER_SKIPS = frozenset({"unreconciled", "duplicate"})
_CLAIM_SIGNAL = re.compile(
    r"\b(?:MEDICAID|MEDICARE|MEDI CAL|TRICARE|CHAMPVA|GEMT|EMS|PROV(?:IDER)? ?PAY(?:MENTS?)?|EDI PYMNTS|CLAIM PMT)\b"
    r"|(?:\bH[CE]?|HC)CLAIMPMT"
)
#: The census's own readers (independent of the code under test): the receiver fields, the ACH originator fields.
_RECEIVER = re.compile(r"\b(?:INDN|IND NAME|IND ID|RECEIVER NAME)\b")
_ACH_FIELD = re.compile(r"\b(?:DES|CO ENTRY DESCR|ORIG CO NAME)\b")
#: G15 (review C1): a refund word, glued or not.
_REFUND_WORD = re.compile(r"[A-Z]*REFUND\w*|\bRFND\w*|\bREFND\w*|\bRFD\b")
#: G16 (review I6): a tax refund or an earned-income credit, glued or not.
_TAX_REFUND_WORD = re.compile(r"[A-Z]*TAXRFD\b|\bTAX ?REF\w*|\bTAX ?EIC\b|\bTAX RFD\b")


def mask(text: object) -> str:
    return _DIGITS.sub("#", " ".join(str(text or "").split()))


def _before_receiver(text: str) -> str:
    return _RECEIVER.split(text, 1)[0]


def _account_payloads(node: object) -> Iterator[dict]:
    """Every account payload (a dict whose `statement` holds a `transactions` list), in order."""
    if isinstance(node, dict):
        statement = node.get("statement")
        if isinstance(statement, dict) and isinstance(statement.get("transactions"), list):
            yield node
            return
        for value in node.values():
            yield from _account_payloads(value)
    elif isinstance(node, list):
        for value in node:
            yield from _account_payloads(value)


def cached_accounts(data_dir: Path, limit: int | None = None) -> Iterator[tuple[str, dict]]:
    """(id, account payload) for the latest cached analysis of each input; the cache is opened read-only."""
    database = data_dir / "webapp.db"
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    try:
        latest = connection.execute(
            "SELECT a.input_sha256, a.artifact_path FROM artifact_cache a JOIN ("
            " SELECT input_sha256, MAX(created_at) AS newest FROM artifact_cache"
            " WHERE stage = 'analysis' GROUP BY input_sha256) b"
            " ON a.input_sha256 = b.input_sha256 AND a.created_at = b.newest"
            " WHERE a.stage = 'analysis' ORDER BY a.input_sha256"
        ).fetchall()
    finally:
        connection.close()
    for number, (sha, relative) in enumerate(latest):
        if limit is not None and number >= limit:
            return
        try:
            payload = json.loads((data_dir / "artifacts" / relative).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for index, account in enumerate(_account_payloads(payload.get("artifact"))):
            yield f"c{sha[:12]}.{index}", account


def job_accounts(database: Path) -> Iterator[tuple[str, dict]]:
    """(id, account payload) for every saved job of a copy of the tryout host's job store, opened read-only."""
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    try:
        rows = connection.execute("SELECT id, analysis_json FROM jobs WHERE analysis_json IS NOT NULL").fetchall()
    finally:
        connection.close()
    for job_id, text in rows:
        try:
            analysis = json.loads(text)
        except ValueError:
            continue
        for index, account in enumerate(_account_payloads(analysis)):
            yield f"j{job_id[:8]}.{index}", account


def _fingerprint(statement) -> tuple:
    return (statement.bank, statement.period_start, statement.period_end, statement.beginning_balance,
            statement.ending_balance, len(statement.transactions), statement.account_number)


def _pool_threshold(classifier, record) -> int:
    """§7.0: the recurrence count of the entity's pool: two on a business account (a customer-payment platform reads
    only the business words), three otherwise."""
    from analysis.classification_registry import OPERATING_REVENUE_SOURCE_TYPES

    if OPERATING_REVENUE_SOURCE_TYPES.get(record.revenue_canonical_entity or "") == "customer_payment_platform":
        business = classifier._matches_any(
            classifier.account_name_text(record.account_name), classifier._BUSINESS_ACCOUNT_PATTERNS
        )
    else:
        business = classifier._business_account(record.account_name)
    return classifier._RECURRENCE_MIN_BUSINESS_CREDITS if business else classifier._RECURRENCE_MIN_CREDITS


def _guard_facts(record, text: str) -> dict:
    """The §14.3 guard facts of one posted credit, read with the checkout's own readers when it has them."""
    from analysis import transaction_classifier as classifier

    facts: dict = {}
    if not hasattr(classifier, "revenue_text"):
        return facts
    revenue = classifier.revenue_text(text)
    region = classifier.payer_region(revenue)
    row = _before_receiver(revenue)
    facts["gate"] = classifier.channel_gate(revenue)
    facts["holder"] = classifier.holder_named(region, record.account_name)
    facts["numbered"] = classifier.numbered_company(revenue, region)
    # G1 (review I1): narrowing 4 needs a third-party originator.
    facts["third_party_originator"] = classifier._third_party_originator(revenue) is not None
    # G17 (review C3): the holder's own transfer, read on its ACH originator whatever the payer region says.
    facts["own_transfer"] = bool(
        classifier._TRANSFER_WORDING.search(row) and _ACH_FIELD.search(row)
        and classifier.holder_named(classifier._ach_payer_region(revenue), record.account_name)
    )
    # G14 (review I1): the rows that count toward an entity's recurrence pool, and the count it needs.
    facts["pool_candidate"] = classifier._in_operating_pool(record)
    facts["pool_vetoed"] = bool(classifier._recurrence_vetoed(record, revenue) or facts["gate"] == "closed")
    facts["pool_threshold"] = _pool_threshold(classifier, record)
    try:
        from analysis import true_revenue
    except ImportError:
        return facts
    facts.update(true_revenue.guard_facts(record, revenue))
    return facts


def account_snapshot(account: dict) -> dict:
    """Re-classify one account payload with the `analysis` package on sys.path."""
    from analysis.metrics import compute_metrics
    from analysis.schema import Statement
    from analysis.transaction_classifier import classify_statement_transactions

    statement = Statement.model_validate(account["statement"])
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    credits = []
    posted = [record for record in records if record.amount > 0 and record.is_posted]
    for index, record in enumerate(records):
        if record.amount <= 0 or not record.is_posted or record.revenue_classification is None:
            continue
        credits.append({
            "i": index,
            "cents": round(record.amount * 100),
            "state": record.revenue_classification,
            "method": record.revenue_match_method,
            "rule": record.revenue_matched_rule,
            "entity": record.revenue_canonical_entity,
            "alias": record.revenue_matched_alias,
            "tier": getattr(record, "revenue_tier", None),
            "reason": getattr(record, "revenue_tier_reason", None),
            "class": record.classification,
            "lender_credit": bool(getattr(record, "contributes_to_lender_credit_exclusion", False)),
            "text": mask(record.normalized_description),
            "facts": _guard_facts(record, record.normalized_description),
        })
    tier_totals = None
    if hasattr(metrics, "counted_flagged_total"):
        tier_totals = {
            "verified": round(metrics.verified_revenue_total * 100),
            "counted_flagged": round(metrics.counted_flagged_total * 100),
            "excluded_pending_review": round(metrics.excluded_pending_review_total * 100),
            "non_revenue": round(metrics.non_revenue_total * 100),
        }
    return {
        "bank": statement.bank,
        "rows": len(records),
        "credits": credits,
        "posted_cents": sum(credit["cents"] for credit in credits),
        # G9 (review I1): every posted credit, whatever its state, counted apart from the rows the census kept.
        "posted_credit_count": len(posted),
        "posted_credit_cents": sum(round(record.amount * 100) for record in posted),
        "tier_totals": tier_totals,
        "lender_credits": metrics.lender_credits,
        "eligible_deposits": metrics.legacy_eligible_deposits,
        "revenue_review_required": metrics.revenue_review_required,
    }


def snapshot(accounts: Iterable[tuple[str, dict]]) -> dict:
    """{"classification_version", "accounts": {id: account snapshot}, "skipped": {reason: n}}, over the reconciled,
    de-duplicated accounts (the credit census's filter)."""
    from analysis.schema import Statement
    from analysis.transaction_classifier import CLASSIFICATION_VERSION

    result: dict = {"classification_version": CLASSIFICATION_VERSION, "accounts": {}, "skipped": {}}
    skipped: Counter = Counter()
    seen: set = set()
    for key, account in accounts:
        if not bool((account.get("reconciliation") or {}).get("ok")):
            skipped["unreconciled"] += 1
            continue
        try:
            fingerprint = _fingerprint(Statement.model_validate(account["statement"]))
        except Exception:  # noqa: BLE001  (a stored payload the schema no longer reads)
            skipped["unreadable"] += 1
            continue
        if fingerprint in seen:
            skipped["duplicate"] += 1
            continue
        seen.add(fingerprint)
        try:
            result["accounts"][key] = account_snapshot(account)
        except Exception as error:  # noqa: BLE001
            skipped[type(error).__name__] += 1
    result["skipped"] = dict(sorted(skipped.items()))
    return result


def _share(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def _summary(snap: dict) -> dict:
    """True and Verified shares, $0 statements, the median statement shares, the tiers and reasons."""
    totals: Counter = Counter()
    rows: Counter = Counter()
    tiers: Counter = Counter()
    reasons: dict = defaultdict(lambda: [0, 0])
    zero_verified = zero_true = with_credits = gated = 0
    true_shares, verified_shares = [], []
    for account in snap["accounts"].values():
        posted = account["posted_cents"]
        if posted <= 0:
            continue
        with_credits += 1
        verified = sum(c["cents"] for c in account["credits"] if c["state"] == "verified_revenue")
        counted = sum(c["cents"] for c in account["credits"] if c.get("tier") == "counted_flagged")
        true = verified + counted
        zero_verified += verified == 0
        zero_true += true == 0
        true_shares.append(true / posted)
        verified_shares.append(verified / posted)
        gated += bool(account.get("revenue_review_required"))
        for credit in account["credits"]:
            totals[credit["state"]] += credit["cents"]
            rows[credit["state"]] += 1
            if credit.get("tier"):
                tiers[credit["tier"]] += credit["cents"]
            if credit.get("reason"):
                slot = reasons[f"{credit['tier']}/{credit['reason']}"]
                slot[0] += 1
                slot[1] += credit["cents"]
        totals["posted"] += posted
    true_total = totals["verified_revenue"] + tiers["counted_flagged"]
    return {
        "version": snap.get("classification_version"),
        "statements_with_credits": with_credits,
        "posted_dollars": round(totals["posted"] / 100, 2),
        "verified_share": _share(totals["verified_revenue"], totals["posted"]),
        "unverified_share": _share(totals["unverified_deposit"], totals["posted"]),
        "non_revenue_share": _share(totals["non_revenue"], totals["posted"]),
        "true_share": _share(true_total, totals["posted"]) if tiers else None,
        "held_share": _share(tiers["excluded_pending_review"], totals["posted"]) if tiers else None,
        "zero_verified_statements": zero_verified,
        "zero_true_statements": zero_true if tiers else None,
        "median_statement_true_share": round(100 * statistics.median(true_shares), 1) if tiers and true_shares else None,
        "median_statement_verified_share": round(100 * statistics.median(verified_shares), 1) if verified_shares else None,
        "gated_statements": gated,
        "gated_share": _share(gated, with_credits),
        "rows": dict(rows),
        "reasons": {key: {"rows": value[0], "dollars": round(value[1] / 100, 2)} for key, value in sorted(reasons.items())},
    }


def _narrowing(base: dict, after: dict) -> str | None:
    """Which §6.3 narrowing (or the OQ2 ruling) moved a base non_revenue row out of non_revenue; None for none."""
    text, base_method = after["text"], base["method"]
    facts = after.get("facts") or {}
    if base_method == "reversal_cancellation_exclusion" and "REIMBURSEMENT" in text and _CLAIM_SIGNAL.search(text):
        return "1_reimbursement_claim_signal"
    if base_method == "insurance_provider_credit_exclusion":
        if after["method"] == "insurer_customer_payment" and not re.search(r"H[CE]?CLAIMPMT", after["text"]):
            return "3_insurer_customer_payment"
        if re.search(r"H[CE]?CLAIMPMT", after["text"]):
            return "2_hcclaimpmt_insurer"
        return "3_insurer_customer_payment"
    # Review I1: a book or funds transfer leaves only on a printed third-party originator (T19, §7.11).
    if (
        base_method == "strong_non_revenue_rule"
        and re.search(r"\b(?:BOOK|FUNDS?) TRANSFER\b", text)
        and facts.get("third_party_originator")
    ):
        return "4_book_or_funds_transfer"
    if facts.get("street_ln") or (base["text"] != after["text"] and " LN " in f" {after['text']} "):
        return "5_street_ln"
    if base_method == "reversal_cancellation_exclusion" and re.search(r"\b(?:DEBIT CARD CREDIT|POS CREDIT)\b", text):
        return "6_card_credit_release"
    if base_method == "financing_proceeds_credit" and after["method"] == "auto_lender_dealer_funding":
        return "7_q7_dealer_funding"
    # Review I1: only the five BNPL providers' settlements leave D1 by the OQ2 ruling.
    if (
        base_method == "financing_proceeds_credit"
        and after["method"] != "financing_proceeds_credit"
        and base.get("entity") in BNPL_ENTITIES
    ):
        return "8_oq2_bnpl_settlement"
    return None


def _demotion_cause(base: dict, after: dict) -> str:
    """The declared cause of a base verified row that is no longer verified (§7.0, §7.11), or 'undeclared'."""
    text, method, rule = after["text"], after["method"], after["rule"] or ""
    facts = after.get("facts", {})
    if after["cents"] < 100:
        return "micro_deposit_floor"
    if rule == "square_capital_credit" or rule == "sba_disbursement_credit":
        return "sq_cap_or_sba"
    if method == "matched_reversal_pair":
        return "reversal_pair"
    if method in {"reversal_cancellation_exclusion", "strong_non_revenue_rule"}:
        return "new_non_revenue_marker"
    if re.search(r"\bACCT ?VERIFY", text):
        return "acctverify"
    if method == "holder_named_payer" or facts.get("holder"):
        return "holder_veto"
    if facts.get("gate") == "closed" or (facts.get("gate") == "push" and base["method"] == "operating_income_descriptor"):
        return "channel_gate"
    if re.search(r"\bCUSTOMER ID\b", text):
        return "customer_id"
    if method == "insurer_customer_payment":
        return "claim_first_off"
    if re.search(r"\bPAYROLL|\bPAYRL|\bDIR ?DEP|\bSALAR|\bWAGE|\bBONUS", text) and "SQ" in text or "SQUARE" in text and re.search(r"PAYROLL", text):
        return "square_payroll"
    if re.search(r"\bLOANS?\b|\bCAPITAL\b|\bCAP\d*|\bADV|\bFIN\b|\bFINANC|\bLEND|\bMCA\b|\bPAYROLL|\bPAYRL|\bDIR ?DEP"
                 r"|\bSALAR|\bWAGE|\bNET ?PAY|\bBONUS|\bREIMB|\bVERIF|\bINSUR|\bDEBIT CARD CREDIT|\bPOS CREDIT"
                 r"|\bFUNDING\b|\bFUNDED\b", text):
        return "recurrence_veto"
    if base.get("entity") and after.get("entity") and base["entity"] != after["entity"]:
        return "entity_split"
    if base["method"] == "recurring_operating_source" and method == "operating_source_requires_context":
        return "pool_below_recurrence_after_a_declared_veto"
    return "undeclared"


def _lender_move_cause(base: dict, after: dict) -> str:
    """M2 (§14.2, §11): why a credit entered or left the lender-credit exclusion (and so moved eligible deposits)."""
    if not after.get("lender_credit"):
        return _narrowing(base, after) or f"left:{after['method']}"
    if base["state"] == "verified_revenue":
        return _demotion_cause(base, after)
    return f"entered:{after['rule'] or after['method']}"


def compare(base: dict, afters: list[dict]) -> dict:
    """The census report of §14.2 and the guards of §14.3 (G7 excepted), base against each later snapshot."""
    report: dict = {"base": _summary(base), "runs": []}
    for after in afters:
        moves: dict = defaultdict(lambda: [0, 0, set()])
        left_non_revenue: dict = defaultdict(lambda: [0, 0, set()])
        demoted: dict = defaultdict(lambda: [0, 0, set()])
        deposits: Counter = Counter()
        lender_moves: dict = defaultdict(lambda: [0, 0, set()])
        failures: dict = defaultdict(list)
        street_ln: list = []
        gate: Counter = Counter()
        q6_unlabelled = [0, 0]
        g13_apart: dict = defaultdict(lambda: [0, 0, set()])
        unmatched = 0
        tiered = any(credit.get("tier") for account in after["accounts"].values() for credit in account["credits"])
        # G9 (review I1): an account that failed to classify, or that the base holds and this run lost, fails.
        for reason, count in (after.get("skipped") or {}).items():
            if reason not in FILTER_SKIPS and count != (base.get("skipped") or {}).get(reason, 0):
                failures["G9"].append({"skipped": reason, "count": count})
        for key, old in base["accounts"].items():
            new = after["accounts"].get(key)
            if new is None or new["rows"] != old["rows"]:
                unmatched += 1
                failures["G9"].append({"account": key, "unmatched": True})
                continue
            old_by_index = {credit["i"]: credit for credit in old["credits"]}
            old_deposits, new_deposits = old.get("eligible_deposits"), new.get("eligible_deposits")
            if old_deposits is not None and new_deposits is not None:
                delta = round(new_deposits - old_deposits, 2)
                deposits["unchanged" if delta == 0 else ("up" if delta > 0 else "down")] += 1
            for credit in new["credits"]:
                prior = old_by_index.get(credit["i"])
                if prior is None:
                    continue
                target = credit.get("tier") or credit["state"]
                slot = moves[(f"{prior['state']}|{prior['method']}", f"{target}|{credit.get('reason') or credit['method']}")]
                slot[0] += 1
                slot[1] += credit["cents"]
                slot[2].add(key)
                in_true = credit["state"] == "verified_revenue" or credit.get("tier") == "counted_flagged"
                if prior["state"] == "non_revenue" and credit["state"] != "non_revenue":
                    cause = _narrowing(prior, credit) or "outside_the_narrowings"
                    entry = left_non_revenue[cause]
                    entry[0] += 1
                    entry[1] += credit["cents"]
                    entry[2].add(key)
                    allowed = dict(NARROWINGS).get(cause)
                    if cause == "outside_the_narrowings" or (in_true and allowed is False):
                        failures["G1"].append({"account": key, "i": credit["i"], "cause": cause, "text": credit["text"]})
                if prior["state"] == "verified_revenue" and credit["state"] != "verified_revenue":
                    cause = _demotion_cause(prior, credit)
                    entry = demoted[cause]
                    entry[0] += 1
                    entry[1] += credit["cents"]
                    entry[2].add(key)
                    if cause == "undeclared":
                        failures["undeclared_demotion"].append({"account": key, "i": credit["i"],
                                                                "text": credit["text"]})
                if "lender_credit" in prior and bool(prior["lender_credit"]) != bool(credit.get("lender_credit")):
                    entry = lender_moves[_lender_move_cause(prior, credit)]
                    entry[0] += 1
                    entry[1] += credit["cents"] if credit.get("lender_credit") else -credit["cents"]
                    entry[2].add(key)
                for guard, failed in _row_guards(credit).items():
                    if failed:
                        failures[guard].append({"account": key, "i": credit["i"], "text": credit["text"]})
                if prior["text"] != credit["text"]:
                    # G7b: the street-LN guard is the only 5.5 change to the normalized text.
                    street_ln.append({"account": key, "i": credit["i"], "base": f"{prior['state']}|{prior['method']}",
                                      "after": f"{credit.get('tier') or credit['state']}|{credit['method']}",
                                      "text": credit["text"]})
                    if prior["method"] == "financing_proceeds_credit" and in_true:
                        failures["G7b"].append({"account": key, "i": credit["i"], "text": credit["text"]})
            for failure in _account_guards(new, tiered):
                failures[failure["guard"]].append({"account": key, **failure})
            if new.get("revenue_review_required"):
                for reason in {c["reason"] for c in new["credits"] if c.get("tier") == "excluded_pending_review"}:
                    gate[reason] += 1
            for credit in new["credits"]:
                facts = credit.get("facts") or {}
                if credit.get("reason") == "named_payer_unlabelled" and facts.get("q6_shape"):
                    q6_unlabelled[0] += 1
                    q6_unlabelled[1] += credit["cents"]
                if credit["state"] == "verified_revenue" and facts.get("numbered") and not _row_guards(credit)["G13"]:
                    entry = g13_apart[credit["method"]]
                    entry[0] += 1
                    entry[1] += credit["cents"]
                    entry[2].add(key)
        report["runs"].append({
            "summary": _summary(after),
            "accounts_unmatched": unmatched,
            "move_matrix": [
                {"from": source, "to": target, "rows": value[0], "dollars": round(value[1] / 100, 2),
                 "statements": len(value[2])}
                for (source, target), value in sorted(moves.items(), key=lambda item: -item[1][1])
            ],
            "left_non_revenue": {
                cause: {"rows": value[0], "dollars": round(value[1] / 100, 2), "statements": len(value[2])}
                for cause, value in sorted(left_non_revenue.items())
            },
            "verified_demotions": {
                cause: {"rows": value[0], "dollars": round(value[1] / 100, 2), "statements": len(value[2])}
                for cause, value in sorted(demoted.items())
            },
            "eligible_deposits": dict(deposits),
            # M2 (§14.2, §11): lender credits (so eligible deposits, the other way) by the cause that moved each row.
            "lender_credit_moves_by_cause": {
                cause: {"rows": value[0], "lender_credit_dollars": round(value[1] / 100, 2),
                        "eligible_deposit_dollars": round(-value[1] / 100, 2), "statements": len(value[2])}
                for cause, value in sorted(lender_moves.items())
            },
            "street_ln_changes": street_ln,
            "gated_statements_by_held_reason": dict(gate.most_common()),
            "named_payer_unlabelled_with_q6_shape": {"rows": q6_unlabelled[0],
                                                     "dollars": round(q6_unlabelled[1] / 100, 2)},
            # G13 (review I1): Verified rows the numbered-company template matches that a processor's registry or
            # card form verified (its payer is the processor, §5.2); the precision sample reads them.
            "g13_listed_apart": {
                method: {"rows": value[0], "dollars": round(value[1] / 100, 2), "statements": len(value[2])}
                for method, value in sorted(g13_apart.items())
            },
            "guards": {guard: {"failures": len(items), "sample": items[:25]} for guard, items in sorted(failures.items())},
        })
    return report


def _account_guards(account: dict, tiered: bool) -> list[dict]:
    """The account-level guards of §14.3: G9 (the four-tier identity, each tier with its state, every posted credit
    kept, and the metrics' tier totals), G12's credit-union count and G14's recurrence pools."""
    found: list[dict] = []
    credits = account["credits"]
    posted_count = account.get("posted_credit_count")
    if posted_count is not None and (posted_count != len(credits)
                                     or account.get("posted_credit_cents") != account["posted_cents"]):
        found.append({"guard": "G9", "posted_credits_without_a_revenue_state": posted_count - len(credits)})
    if tiered:
        by_tier: Counter = Counter()
        for credit in credits:
            tier = credit.get("tier")
            if tier not in TIER_STATES or credit["state"] not in TIER_STATES[tier]:
                found.append({"guard": "G9", "i": credit["i"], "tier": tier, "state": credit["state"]})
            by_tier[tier] += credit["cents"]
        if sum(by_tier.values()) != account["posted_cents"]:
            found.append({"guard": "G9", "identity": "rows"})
        totals = account.get("tier_totals")
        if totals is not None and (
            any(abs(totals[tier] - by_tier[tier]) > 1 for tier in TIER_STATES)
            or abs(sum(totals.values()) - account["posted_cents"]) > len(TIER_STATES)
        ):
            found.append({"guard": "G9", "identity": "metrics"})
    unions = [c for c in credits if c["method"] == "auto_lender_dealer_funding"
              and (c.get("facts") or {}).get("q7_credit_union") and not (c.get("facts") or {}).get("q7_listed")]
    if 0 < len(unions) < CREDIT_UNION_DEALER_MIN_CREDITS:
        found.extend({"guard": "G12", "i": c["i"], "credit_union_rows": len(unions)} for c in unions)
    pools: dict = defaultdict(list)
    lifted: dict = defaultdict(list)
    for credit in credits:
        facts = credit.get("facts") or {}
        if credit.get("entity") and facts.get("pool_candidate") and not facts.get("pool_vetoed"):
            pools[credit["entity"]].append(credit)
        if credit["method"] == "recurring_operating_source" and credit.get("entity"):
            lifted[credit["entity"]].append(credit)
    for entity, rows in lifted.items():
        needed = min((row.get("facts") or {}).get("pool_threshold", 2) for row in rows)
        if len(pools.get(entity, [])) < needed:
            found.extend({"guard": "G14", "i": row["i"], "pool": len(pools.get(entity, [])), "needed": needed}
                         for row in rows)
    return found


#: §14.5's Verified strata: stratum -> the revenue methods that fill it.
PRECISION_STRATA = {
    "q5_repeat_wires": lambda credit: credit["method"] == "repeat_wire_sender",
    "q6a_repeats": lambda credit: credit["method"] == "named_payer_repeats",
    "q6b_company_form": lambda credit: credit["method"] == "named_payer_company_form",
    "q6c_government_healthcare": lambda credit: credit["method"] == "public_or_healthcare_payer",
    "ap_remittance": lambda credit: credit["method"] == "payer_remittance_descriptor",
    "public_payers": lambda credit: credit["method"] == "public_payer_remittance",
    "invoice_wires": lambda credit: credit["method"] == "wire_remittance_purpose",
    # §7.1 card forms (rule card_settlement_form_<label>), §7.2 payout forms (alias <platform>_..._form), §7.8.
    "card_and_payout_forms": lambda credit: (
        (credit.get("rule") or "").startswith("card_settlement_form_")
        or (credit.get("alias") or "").endswith("_form")
        or credit["method"] == "wholesale_auction_payout_form"
    ),
    "q7_dealer_funding": lambda credit: credit["method"] == "auto_lender_dealer_funding",
}


def precision_sample(snap: dict, *, per_stratum: int = 20, largest_counted: int = 50, seed: int = 55) -> dict:
    """§14.5: a stratified sample of a 5.6 snapshot, digit-masked: `per_stratum` Verified rows of each stratum
    (every row when it holds fewer), the Verified rows G3 lists (the holder test matched) and G13 lists apart (the
    numbered-company template on a processor's settlement), and the `largest_counted` largest counted rows. Each row carries an empty `sort` for the reviewer: revenue, loan, own_money, refund,
    transfer, insurance, other or cannot_tell."""
    import random

    pools: dict = defaultdict(list)
    counted: list = []
    for key, account in snap["accounts"].items():
        for credit in account["credits"]:
            row = {"account": key, "i": credit["i"], "dollars": round(credit["cents"] / 100, 2),
                   "method": credit["method"], "tier": credit.get("tier"), "reason": credit.get("reason"),
                   "text": credit["text"], "sort": ""}
            if credit["state"] == "verified_revenue":
                for stratum, belongs in PRECISION_STRATA.items():
                    if belongs(credit):
                        pools[stratum].append(row)
                if (credit.get("facts") or {}).get("holder"):
                    pools["holder_test_rows"].append(row)
                if (credit.get("facts") or {}).get("numbered"):
                    pools["numbered_template_rows"].append(row)
            elif credit.get("tier") == "counted_flagged":
                counted.append(row)
    chooser = random.Random(seed)
    sample = {stratum: (rows if len(rows) <= per_stratum else chooser.sample(rows, per_stratum))
              for stratum, rows in sorted(pools.items())}
    sample["largest_counted"] = sorted(counted, key=lambda row: -row["dollars"])[:largest_counted]
    return sample


def _row_guards(credit: dict) -> dict[str, bool]:
    """The row-level guards of §14.3 and the review's G15 to G17 (True means the guard failed)."""
    facts = credit.get("facts") or {}
    tier = credit.get("tier")
    in_true = credit["state"] == "verified_revenue" or tier == "counted_flagged"
    verified = credit["state"] == "verified_revenue"
    method = credit["method"]
    row = _before_receiver(credit["text"])
    guards = {
        # A registry row reads the root with the holder's own words and §7.0's FUNDING settlements aside (review I1).
        "G2": verified and method != "auto_lender_dealer_funding" and bool(
            facts.get("registry_root") if method in REGISTRY_METHODS else facts.get("financing_root")
        ),
        "G3": bool(facts.get("holder")) and (
            (verified and method in IDENTITY_METHODS)
            or (verified and method == "operating_income_descriptor" and bool(facts.get("customer_descriptor")))
            or tier == "counted_flagged"
        ),
        "G4": in_true and bool(facts.get("transfer_no_counterparty")),
        "G6": in_true and method == "direction_conflict",
        # G10 (review I1): a closed row never verifies; a push-rail row verifies through the registry only.
        "G10": verified and (
            facts.get("gate") == "closed" or (facts.get("gate") == "push" and method not in REGISTRY_VERIFYING_METHODS)
        ),
        "G11": in_true and bool(facts.get("pay_or_personal")),
        "G12": method == "auto_lender_dealer_funding" and (
            not facts.get("q7_payer_ok", True) or bool(facts.get("q7_veto_word"))
        ),
        # G13 (review I1): the full numbered-company guard, the DIRECT DEPOSIT <digits> template included, on the
        # rules that read it (§5.2: steps 11 to 14, Q5, Q6); the region form on every Verified row. A processor's
        # settlement printed after BMO's template (MISC PAYMENT <digits> GBL VI) is listed apart (g13_listed_apart).
        "G13": verified and (
            bool(facts.get("numbered_region"))
            or (bool(facts.get("numbered")) and (
                method in IDENTITY_METHODS
                or (method == "operating_income_descriptor" and bool(facts.get("customer_descriptor")))
            ))
        ),
        "G14": bool(facts.get("pooled_while_vetoed")),
        "G15": in_true and _REFUND_WORD.search(row) is not None,
        "G16": in_true and _TAX_REFUND_WORD.search(row) is not None,
        "G17": in_true and bool(facts.get("own_transfer")),
    }
    if facts.get("known_financing") and in_true and method not in {"auto_lender_dealer_funding"}:
        guards["G5"] = not facts.get("payout_or_factoring")
    return guards


def _print(report: dict) -> None:
    def line(summary: dict) -> str:
        parts = [f"classification {summary['version']}", f"statements {summary['statements_with_credits']}",
                 f"verified {summary['verified_share']}%", f"$0-verified {summary['zero_verified_statements']}"]
        if summary.get("true_share") is not None:
            parts += [f"true {summary['true_share']}%", f"held {summary['held_share']}%",
                      f"$0-true {summary['zero_true_statements']}",
                      f"median true {summary['median_statement_true_share']}%"]
        parts.append(f"gated {summary['gated_share']}%")
        return "; ".join(parts)

    print("base: " + line(report["base"]))
    for run in report["runs"]:
        print("after: " + line(run["summary"]) + f"; unmatched {run['accounts_unmatched']}")
        print("  left non_revenue: " + ", ".join(
            f"{cause} {value['rows']} rows/${value['dollars']:,.2f}/{value['statements']} st"
            for cause, value in run["left_non_revenue"].items()))
        print("  verified demotions: " + ", ".join(
            f"{cause} {value['rows']} rows/${value['dollars']:,.2f}/{value['statements']} st"
            for cause, value in run["verified_demotions"].items()))
        print("  eligible deposits: " + ", ".join(f"{name} {count}" for name, count in run["eligible_deposits"].items()))
        print("  lender credits by cause: " + ", ".join(
            f"{cause} {value['rows']} rows/${value['lender_credit_dollars']:,.2f}"
            for cause, value in run["lender_credit_moves_by_cause"].items()))
        print("  guards: " + (", ".join(f"{guard} FAILED {value['failures']}" for guard, value in run["guards"].items())
                              or "all hold"))


def _use_code_root(code_root: Path) -> bool:
    """Put the checkout's `analysis` package first on sys.path; False if another one is already loaded."""
    sys.path.insert(0, str(code_root.resolve()))
    import analysis

    return Path(analysis.__file__).resolve().is_relative_to(code_root.resolve())


def _read(path: Path) -> dict:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot", help="re-classify the cache with one checkout's code")
    snap.add_argument("--data-dir", type=Path, help="the webapp data directory (read-only)")
    snap.add_argument("--jobs-db", type=Path, help="a copy of the tryout host's job store (read-only)")
    snap.add_argument("--out", type=Path, required=True, help="the snapshot to write (outside the repo)")
    snap.add_argument("--code-root", type=Path, default=ROOT, help="the checkout whose analysis package classifies")
    snap.add_argument("--limit", type=int, default=None, help="read only the first N analyses")
    comp = commands.add_parser("compare", help="compare a base snapshot with later ones")
    comp.add_argument("--base", type=Path, required=True)
    comp.add_argument("--after", type=Path, required=True, action="append")
    comp.add_argument("--out", type=Path, required=True, help="the report to write (outside the repo)")
    samp = commands.add_parser("sample", help="draw the precision sample of a 5.6 snapshot (§14.5)")
    samp.add_argument("--snapshot", type=Path, required=True)
    samp.add_argument("--out", type=Path, required=True, help="the sample to write (outside the repo)")
    args = parser.parse_args(argv)

    if args.out.resolve().is_relative_to(ROOT.resolve()):
        print(f"refused: {args.out} is inside the repository; the census holds statement figures", file=sys.stderr)
        return 2
    if args.command == "snapshot":
        if (args.data_dir is None) == (args.jobs_db is None):
            print("refused: name exactly one of --data-dir and --jobs-db", file=sys.stderr)
            return 2
        if args.data_dir is not None and not (args.data_dir / "webapp.db").is_file():
            print(f"refused: {args.data_dir} holds no webapp.db", file=sys.stderr)
            return 2
        if not _use_code_root(args.code_root):
            print(f"refused: another analysis package is already loaded, not {args.code_root}", file=sys.stderr)
            return 2
        accounts = cached_accounts(args.data_dir, args.limit) if args.data_dir else job_accounts(args.jobs_db)
        result = snapshot(accounts)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(gzip.compress(json.dumps(result).encode("utf-8")))
        print(f"classification {result['classification_version']}: {len(result['accounts'])} accounts; "
              f"skipped: {result['skipped']}")
        return 0
    if args.command == "sample":
        sample = precision_sample(_read(args.snapshot))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(sample, indent=1) + "\n", encoding="utf-8")
        print("; ".join(f"{stratum} {len(rows)}" for stratum, rows in sample.items()))
        return 0
    report = compare(_read(args.base), [_read(path) for path in args.after])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, default=list) + "\n", encoding="utf-8")
    _print(report)
    return 1 if any(run["guards"] for run in report["runs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_revenue_census.py -q -p no:cacheprovider`

Expected: PASS: `43 passed`.

- [ ] **Step 5: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-REVENUE: `565 passed`

- [ ] **Step 6: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add tests/test_revenue_census.py tools/revenue_census.py
git commit -m "tools: the revenue census (spec 14.2, 14.3, 14.5)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S3.2: The 5.4 to 5.5 census (acceptance of S1 and S2)

**Files:** none in the repository. Private outputs under `C:/Users/GustavoPrietodePaula/lender-research/revenue/census/` (create the folder): `base54/` (a code copy), `s54.json.gz`, `s55.json.gz`, `cmp55.json`.

**Depends on:** S2.5, S3.1 and S1.5. S4 starts only after the orchestrator accepts this task's report (spec §16).

**Why:** spec §14.2 and T17: 5.5 carries the fixes under today's definition so that the census can measure them alone. Every row that left `non_revenue` must be one of the named narrowings, every verified row that lost its verification must have a declared cause (an undeclared one fails the census), and the guards that can already be read at 5.5 (G1, G4 to G6, G9, G10, G13, G14 and the review's G15 to G17, on verified rows) must hold.

- [ ] **Step 1: The 5.4 code, outside the repository.** A plain copy of `analysis/` at the plan's first commit (no worktree, so the main checkout's git metadata is untouched):

```bash
mkdir -p C:/Users/GustavoPrietodePaula/lender-research/revenue/census/base54
git -C C:/Users/GustavoPrietodePaula/work/true-revenue archive 4227a76 analysis | tar -x -C C:/Users/GustavoPrietodePaula/lender-research/revenue/census/base54
```

- [ ] **Step 2: The two snapshots** (read-only on the cache; each took 9 to 10 minutes in one process on the prototype):

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
DATA="C:/Users/GustavoPrietodePaula/OneDrive - Capital Infusion/Desktop/Capital Infusion Projects/bankStatementAnalysis/webapp_data"
OUT=C:/Users/GustavoPrietodePaula/lender-research/revenue/census
C:/Python314/python.exe -m tools.revenue_census snapshot --data-dir "$DATA" --out $OUT/s54.json.gz --code-root $OUT/base54
C:/Python314/python.exe -m tools.revenue_census snapshot --data-dir "$DATA" --out $OUT/s55.json.gz
C:/Python314/python.exe -m tools.revenue_census compare --base $OUT/s54.json.gz --after $OUT/s55.json.gz --out $OUT/cmp55.json
```

  Each snapshot prints `classification 5.4: 2493 accounts; skipped: {'duplicate': 4579, 'unreconciled': 169}`, then the same line for 5.5 (measured on the cache of 2026-09-28; a cache that has grown since prints larger numbers, which the report states). `compare` exits 0.

- [ ] **Step 3: Read the report against the measured values.** Measured on the revised prototype on 2026-09-29 (the same corpus, without S1.5's admissions; rows exact, dollars rounded). Any difference stops the task, except the one S1.5's admissions explain, measured this way (review I2): if S1.5 admitted or cleared anything, first build `C:/Users/GustavoPrietodePaula/lender-research/revenue/census/noadmit55/` as Step 1 builds `base54` but from `HEAD`, then overwrite its `analysis/classification_registry.py` with the version before S1.5's commit (`git -C C:/Users/GustavoPrietodePaula/work/true-revenue show <S1.5 commit>~1:analysis/classification_registry.py`); snapshot with `--code-root` that folder to `s55_noadmit.json.gz` and compare it with `s54.json.gz`: that report must match the table below. Then `compare --base $OUT/s55_noadmit.json.gz --after $OUT/s55.json.gz`: every row that moved names, in its `entity` or its text, an entity of `g7_allowlist.json` or a processor whose bare aliases S1.5 cleared; list them in the report by entity. Any other moved row stops the task.

| Figure | 5.4 | 5.5 |
|---|---|---|
| Statements with credits | 2,468 | 2,468 (0 unmatched) |
| Verified share of posted credits | 7.17% | 19.59% |
| Statements at $0 verified | 1,819 | 1,271 |
| Statements gated (today's rule, `revenue_review_required`) | 96.6% | 93.80% (2,315) |
| Rows verified / unverified / non-revenue | | 27,521 / 39,754 / 9,890 |

  - **Left `non_revenue`** (every row one of §6.3's narrowings or the OQ2 ruling; `outside_the_narrowings` must be absent): `2_hcclaimpmt_insurer` 177 rows, about $0.91M, 16 statements (T18); `3_insurer_customer_payment` 4 rows, about $0.08M, 4 statements (unverified at 5.5, held at 5.6); `4_book_or_funds_transfer` 425 rows, about $8.41M, 99 statements (T19); `5_street_ln` 7 rows, about $0.02M, 4 statements; `8_oq2_bnpl_settlement` 8 rows, under $300, 6 statements.
  - **Verified demotions** (each a declared cause; `undeclared` must be absent): `channel_gate` 37 rows (10 statements); `customer_id` 37 (11); `micro_deposit_floor` 21 (15); `recurrence_veto` 17 (5); `sq_cap_or_sba` 8 (8); `square_payroll` 7 (4); `pool_below_recurrence_after_a_declared_veto` 4 (3). The last is not in the spec: it is this plan's declared consequence of the recurrence veto (a pool left under its count once a vetoed member leaves it), with `entity_split` (measured 0); see Decision 25.
  - **Eligible deposits:** unchanged 2,474 accounts, down 13 (SQ CAP and SBA become financing proceeds), up 6 (the BNPL settlements leave D1).
  - **Lender credits by cause** (`lender_credit_moves_by_cause`, review M2; eligible deposits move the other way): `sq_cap_or_sba` 8 rows, about $0.15M in, 8 statements (verified at 5.4); `entered:square_capital_credit` 5 rows, about $0.12M in, 5 statements (unverified at 5.4); `8_oq2_bnpl_settlement` 9 rows, under $300 out, 6 statements.
  - **Listed apart:** `g13_listed_apart`: the processors' card and registry settlements printed after BMO's `MISC PAYMENT <digits>` template (their payer is the processor, §5.2): `operating_income_descriptor` 357 rows, about $0.54M, 6 statements; `operating_source_with_credit_context` 83 rows, about $0.13M, 11 statements. A3 samples them.
  - **Guards:** `all hold` (G1 to G14 as they read at 5.5, G15 to G17, and no `undeclared_demotion`).
  - **Targets (§14.4):** Verified after 5.5 "about 14% or more": 19.59%; $0-verified "at most about 1,465": 1,271.

- [ ] **Step 4: Report.** Send the orchestrator the printed lines, the table above filled with the run's values, and the path of `cmp55.json` (private). Nothing is committed.

---

## S4: Classifier and payload 5.6

### Task S4.1: The tier vocabulary and the per-row contract

**Files:**
- Create: `tests/test_true_revenue_payload.py`
- Modify: `analysis/revenue.py:20-22, 41-50, 123-124, 283-284`
- Modify: `analysis/transaction_classifier.py:36, 210, 2563, 2594, 3470, 3481, 4709`

**Depends on:** S3.2 accepted (spec §16: S4 starts after the 5.5 census report is accepted).

**Interfaces:**
- Consumes: `RevenueState`, `REVENUE_STATES` (`analysis/revenue.py`); `_build_record`, `_replace_revenue_state` and the duplicate finalisation of `classify_statement_transactions`.
- Produces:
  - `RevenueTier = Literal["verified", "counted_flagged", "excluded_pending_review", "non_revenue"]`, `REVENUE_TIERS: tuple[RevenueTier, ...]`, `STATE_OF_TIER: dict[str, RevenueState]`
  - `REVENUE_TIER_REASONS: dict[str, tuple[RevenueTier, str]]` (code -> tier and screen label)
  - `revenue_contribution_flags(state: RevenueState | None, tier: str | None = None) -> dict[str, bool]`, `tier_of_state(state: RevenueState | None) -> str | None`
  - `TransactionClassification.revenue_tier`, `.revenue_initial_tier`, `.revenue_tier_reason` (`str | None`), `.contributes_to_counted_flagged`, `.contributes_to_excluded_pending_review` (bool)

**Why:** Spec §5.3 and §5.4, T1, T9: the four tiers and the 26 reason codes live in one table (`REVENUE_TIER_REASONS`); `revenue_contribution_flags` takes the tier, sets the counted and held flags and repoints `contributes_to_true_revenue` to verified plus counted; every record carries `revenue_tier`, `revenue_initial_tier` and `revenue_tier_reason`, the tier its state fixes on its own (verified, non-revenue; an unverified row waits for S4.2's pass), and a proven duplicate is tier `non_revenue`. The serialized rebuild and the review writer pass the state's own tier until S4.4 rewrites them, so their output is unchanged here.

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_true_revenue_payload.py`:

```python
"""Classification 5.6 (true revenue spec §5.1, §5.4, §9.1, §10.7 server rules, §11, §12, T6 to T10): the contribution
flags, the metrics, the detection lists, the serialized views and their rebuild, the review writer, the gate and the
True-revenue withholding mode. Fabricated rows only."""
from __future__ import annotations

from analysis.revenue import REVENUE_TIER_REASONS, revenue_contribution_flags, tier_of_state
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction


def test_the_flags_follow_the_state_and_the_tier():
    assert revenue_contribution_flags("verified_revenue", "verified")["contributes_to_true_revenue"]
    counted = revenue_contribution_flags("unverified_deposit", "counted_flagged")
    assert counted["contributes_to_true_revenue"] and counted["contributes_to_counted_flagged"]
    assert counted["contributes_to_unverified_deposit"] and counted["contributes_to_potential_revenue"]
    held = revenue_contribution_flags("unverified_deposit", "excluded_pending_review")
    assert not held["contributes_to_true_revenue"] and held["contributes_to_excluded_pending_review"]
    assert not revenue_contribution_flags("non_revenue", "non_revenue")["contributes_to_true_revenue"]
    assert not revenue_contribution_flags("verified_revenue", None)["contributes_to_true_revenue"]


def test_every_reason_code_names_a_middle_tier():
    assert {tier for tier, _label in REVENUE_TIER_REASONS.values()} == {"counted_flagged", "excluded_pending_review"}
    assert len(REVENUE_TIER_REASONS) == 26


def test_a_record_carries_the_tier_its_state_fixes():
    assert (tier_of_state("verified_revenue"), tier_of_state("non_revenue"), tier_of_state("unverified_deposit")) == (
        "verified", "non_revenue", None)
    verified = classify_transaction("FABRIKAM MERCH DEP 1234567", 250.0, direction="credit")
    assert (verified.revenue_tier, verified.revenue_initial_tier, verified.revenue_tier_reason) == (
        "verified", "verified", None)
    assert verified.contributes_to_true_revenue
    transfer = classify_transaction("INTERNAL TRANSFER FROM SAVINGS", 100.0, direction="credit")
    assert transfer.revenue_tier == "non_revenue" and not transfer.contributes_to_true_revenue
    assert classify_transaction("CARD PURCHASE FABRIKAM SUPPLY", -120.0, direction="debit").revenue_tier is None


def test_a_proven_duplicate_credit_is_tiered_non_revenue():
    records = classify_statement_transactions(Statement(account_name="CONTOSO BAKERY LLC", transactions=[
        Transaction(date="2054-03-02", description="FABRIKAM MERCH DEP 1234567", amount=250.0, direction="credit",
                    running_balance=1250.0),
        Transaction(date="2054-03-02", description="FABRIKAM MERCH DEP 1234567", amount=250.0, direction="credit",
                    running_balance=1250.0),
    ]))
    assert [record.revenue_tier for record in records] == ["verified", "non_revenue"]
    assert not records[1].contributes_to_true_revenue
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_true_revenue_payload.py -q -p no:cacheprovider`

Expected: FAIL: `1 error`, the first with `ImportError: cannot import name 'REVENUE_TIER_REASONS' from 'analysis.revenue'`.

- [ ] **Step 3: Implement.**

In `analysis/revenue.py` (lines 20-22), replace:

```python
    "non_revenue",
)
WITHHOLDING_DENOMINATOR_MODES = (
```

with:

```python
    "non_revenue",
)
#: 5.6 (true revenue spec §5.3): every posted credit carries exactly one tier. `verified` goes with the state
#: verified_revenue, `non_revenue` with non_revenue, and the two middle tiers with unverified_deposit.
RevenueTier = Literal["verified", "counted_flagged", "excluded_pending_review", "non_revenue"]
REVENUE_TIERS: tuple[RevenueTier, ...] = ("verified", "counted_flagged", "excluded_pending_review", "non_revenue")
STATE_OF_TIER: dict[str, RevenueState] = {
    "verified": "verified_revenue",
    "counted_flagged": "unverified_deposit",
    "excluded_pending_review": "unverified_deposit",
    "non_revenue": "non_revenue",
}
#: 5.6 (§5.3): the reason codes of the counted and held tiers: code -> (tier, the label on screen). Nothing else lists
#: them; the dashboard mirrors them (webapp/static/app.js REVENUE_TIER_REASONS).
REVENUE_TIER_REASONS: dict[str, tuple[RevenueTier, str]] = {
    "direction_conflict": ("excluded_pending_review", "Direction conflicts with the amount"),
    "insurer_payer": ("excluded_pending_review", "Insurance carrier"),
    "insurer_named_payer": ("excluded_pending_review", "Payer name reads as an insurer"),
    "possible_return": ("excluded_pending_review", "Possible return or adjustment"),
    "financing_named_payer": ("excluded_pending_review", "Payer or entry suggests financing"),
    "payer_debited_as_lender": ("excluded_pending_review", "Payer is also debited as a lender"),
    "holder_name": ("excluded_pending_review", "From the holder's own name or brand"),
    "payroll_or_salary": ("excluded_pending_review", "Payroll, salary or employee reimbursement"),
    "personal_income": ("excluded_pending_review", "Benefit or pension"),
    "non_sale_purpose": (
        "excluded_pending_review", "Not a sale: owner money, investment, grant, refund, claim or interest",
    ),
    "payer_also_debited": ("excluded_pending_review", "Payer also debited this account"),
    "wire_no_sender": ("excluded_pending_review", "Wire, no sender printed"),
    "transfer_no_counterparty": ("excluded_pending_review", "Transfer, no counterparty"),
    "transfer_account_designation": ("excluded_pending_review", "Transfer naming an account"),
    "p2p_round_repeat": ("excluded_pending_review", "Repeated round sums from one sender"),
    "wire_named_sender": ("counted_flagged", "Wire from a named sender"),
    "check_deposit": ("counted_flagged", "Check deposit"),
    "no_payer_printed": ("counted_flagged", "No payer printed"),
    "p2p": ("counted_flagged", "Person-to-person"),
    "factoring_payout": ("counted_flagged", "Factoring payout"),
    "payout_credit_entity": ("counted_flagged", "Platform payout (financing partner)"),
    "platform_unconfirmed": ("counted_flagged", "Platform payout, not confirmed"),
    "numbered_company_payer": ("counted_flagged", "Numbered company payer"),
    "named_payer_purpose_refused": ("counted_flagged", "Named payer, purpose not accepted as proof"),
    "named_payer_one_off": ("counted_flagged", "One-off payer"),
    "named_payer_unlabelled": ("counted_flagged", "Payer named, channel not printed"),
}
WITHHOLDING_DENOMINATOR_MODES = (
```

In `analysis/revenue.py`, replace the whole function `revenue_contribution_flags` (lines 41-50) with:

```python
def revenue_contribution_flags(state: RevenueState | None, tier: str | None = None) -> dict[str, bool]:
    """The contribution flags of one record (§5.4). The state decides the three state flags; the tier (5.6) decides
    the counted and held flags and the repointed `contributes_to_true_revenue` (verified or counted). A record with
    no tier contributes to neither middle tier and not to True revenue."""
    return {
        "contributes_to_verified_revenue": state == "verified_revenue",
        "contributes_to_unverified_deposit": state == "unverified_deposit",
        "contributes_to_non_revenue": state == "non_revenue",
        "contributes_to_counted_flagged": tier == "counted_flagged",
        "contributes_to_excluded_pending_review": tier == "excluded_pending_review",
        # Deprecated aliases remain serialized for existing API consumers. They
        # are derived from the canonical state and tier and are never scanned separately.
        # 5.6 (T9): repointed to the new True revenue, verified plus counted.
        "contributes_to_true_revenue": tier in ("verified", "counted_flagged"),
        "contributes_to_potential_revenue": state == "unverified_deposit",
    }


def tier_of_state(state: RevenueState | None) -> str | None:
    """The tier a state fixes on its own: verified for verified_revenue and non_revenue for non_revenue; None for an
    unverified deposit, whose tier the true-revenue pass sets."""
    return {"verified_revenue": "verified", "non_revenue": "non_revenue"}.get(state or "")
```

In `analysis/revenue.py` (lines 123-124), replace:

```python
        flags = revenue_contribution_flags(state)
        record.update(flags)
```

with:

```python
        flags = revenue_contribution_flags(state, tier_of_state(state))
        record.update(flags)
```

In `analysis/revenue.py` (lines 283-284), replace:

```python
    record.update(revenue_contribution_flags(state))
    return record
```

with:

```python
    record.update(revenue_contribution_flags(state, tier_of_state(state)))
    return record
```

In `analysis/transaction_classifier.py` (line 36), replace:

```python
from .revenue import RevenueState, revenue_contribution_flags
```

with:

```python
from .revenue import RevenueState, revenue_contribution_flags, tier_of_state
```

In `analysis/transaction_classifier.py` (line 210), replace:

```python
    potential_payee_label: str | None = None
```

with:

```python
    potential_payee_label: str | None = None
    # 5.6 (true revenue spec §5.4): the per-row contract. Every posted credit carries exactly one tier (verified,
    # counted_flagged, excluded_pending_review, non_revenue); a counted or held row carries its reason code
    # (analysis.revenue.REVENUE_TIER_REASONS). The initial tier is the one the rules gave, which a reset restores.
    revenue_tier: str | None = None
    revenue_initial_tier: str | None = None
    revenue_tier_reason: str | None = None
    contributes_to_counted_flagged: bool = False
    contributes_to_excluded_pending_review: bool = False
```

In `analysis/transaction_classifier.py` (line 2563), replace:

```python
    revenue_flags = revenue_contribution_flags(revenue_state)
```

with:

```python
    revenue_tier = tier_of_state(revenue_state)
    revenue_flags = revenue_contribution_flags(revenue_state, revenue_tier)
```

In `analysis/transaction_classifier.py` (line 2594), replace:

```python
        revenue_initial_classification=revenue_state,
```

with:

```python
        revenue_initial_classification=revenue_state,
        revenue_tier=revenue_tier,
        revenue_initial_tier=revenue_tier,
```

In `analysis/transaction_classifier.py` (line 3470), replace:

```python
        revenue_initial_classification=state,
```

with:

```python
        revenue_initial_classification=state,
        revenue_tier=tier_of_state(state),
        revenue_initial_tier=tier_of_state(state),
        revenue_tier_reason=None,
```

In `analysis/transaction_classifier.py` (line 3481), replace:

```python
        **revenue_contribution_flags(state),
```

with:

```python
        **revenue_contribution_flags(state, tier_of_state(state)),
```

In `analysis/transaction_classifier.py` (line 4709), replace:

```python
            contributes_to_non_revenue=duplicate_revenue,
```

with:

```python
            contributes_to_non_revenue=duplicate_revenue,
            contributes_to_counted_flagged=False,
            contributes_to_excluded_pending_review=False,
            revenue_tier="non_revenue" if duplicate_revenue else None,
            revenue_initial_tier="non_revenue" if duplicate_revenue else None,
            revenue_tier_reason=None,
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_true_revenue_payload.py -q -p no:cacheprovider`

Expected: PASS: `4 passed`.

- [ ] **Step 5: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-CLASSIFIER: `755 passed, 2 deselected`
  - SEL-WEBAPP: `856 passed`

- [ ] **Step 6: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/revenue.py analysis/transaction_classifier.py tests/test_true_revenue_payload.py
git commit -m "revenue: the tier vocabulary and the per-row contract (5.6)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S4.2: The true-revenue pass: holds, Q5, Q6 and the tiers

**Files:**
- Create: `analysis/true_revenue.py`
- Create: `tests/test_true_revenue_tiers.py`
- Modify: `analysis/transaction_classifier.py:39, 4685`
- Modify (pins): `tests/test_revenue_census.py:261`
- Modify (pins): `tests/test_revenue_classification.py:286-287, 290-292`

**Depends on:** S4.1.

**Interfaces:**
- Consumes: S2.1 to S2.4 (readers, helpers, `_payer_key`, `_debit_first_distinctive_word`, `_replace_revenue_state`), S1.3 (`HEALTHCARE_PAYER_ALIASES`, `DEALER_FUNDING_PAYERS`), S4.1.
- Produces:
  - `analysis/true_revenue.py`: `apply_true_revenue_pass(records, duplicate_indexes) -> list[TransactionClassification]`
  - `CreditFacts` (frozen dataclass), `credit_facts(record, text, *, lender_words, debit_words) -> CreditFacts`
  - `financing_named(text, region, entry, account_name) -> bool`, `non_sale_purpose(text, region) -> bool`, `healthcare_payer(region) -> bool`, `government_payer(region) -> bool`, `public_region(text) -> str`, `DEALER_FUNDING_WORDS`, `_dealer_funding_payer(text) -> str | None`
  - `registry_financing(record, text) -> bool`, `registry_financing_root(record, text) -> bool`
  - `guard_facts(record, text) -> dict` (keys `financing_root`, `registry_root`, `registry_financing`, `pay_or_personal`, `transfer_no_counterparty`, `known_financing`, `payout_or_factoring`, `numbered_region`, `customer_descriptor`, `pooled_while_vetoed`, `q6_shape`)
  - new revenue methods `repeat_wire_sender`, `named_payer_repeats`, `named_payer_company_form`, `public_or_healthcare_payer`

**Why:** Spec §8.1 to §8.6, §8.8 to §8.10, T2 to T4, T11 to T14: statement pass 7 (§6.2). For each posted credit it reads the payer facts (channel family, payer region, name and key, entry fields) and the first hold of §8.10's order; verifies a company that wires twice or more (Q5) and a named ACH/EFT payer that repeats, prints a company form or is a government or healthcare payer (Q6), never a row a hold names; then gives every posted credit its tier and reason. A lender of `DEALER_FUNDING_PAYERS` and a row printing a dealer-funding word are held as `financing_named_payer` until S4.3's Q7 verifies the dealer's own funding. After the review: a refund word, glued or not, is a non-sale purpose (C1; the financing root's `(?<!RE)FUND` is declared, Decision 19); a registry row that prints a financing word is never claimed and is held as financing (C2); a consumer entry, a bank and a title or escrow firm never verify by their company form, and PAYCHECK, PR PAY and EMPLOYEE PAY are pay words (I6); VISA, CHECKCARD and PURCHASE CREDIT and an auction's DEALSHIELD or ARB CREDIT are possible returns (M6, §7.8); Q5 never verifies a row the channel gate closes or limits to the registry. It also exposes the census's guard facts.

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_true_revenue_tiers.py`:

```python
"""Classification 5.6 (true revenue spec §5.3, §8, T11 to T14): the tier and reason of every posted credit, the holds,
the channel tiers, and the Q5 and Q6 verifications with their guards. Fabricated rows only, in the banks' printed
formats."""
from __future__ import annotations

import pytest

from analysis.revenue import REVENUE_TIER_REASONS
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions

HOLDER = "CONTOSO BAKERY LLC"


def _records(rows, *, holder: str | None = HOLDER):
    return classify_statement_transactions(Statement(account_name=holder, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


def _one(text: str, amount: float = 1234.0, *, holder: str | None = HOLDER):
    return _records([(text, amount)], holder=holder)[0]


def _tier(record):
    return record.revenue_tier, record.revenue_tier_reason


@pytest.mark.parametrize(("text", "reason"), [
    ("STATE FARM DES:DRP PAYMENT ID:1", "insurer_payer"),
    ("FABRIKAM MUTUAL INSURANCE COMPANY DES:CLAIM PAYMT ID:1", "insurer_named_payer"),
    ("NORTHWIND SUPPLY DES:RETURN ID:1", "possible_return"),
    ("CONTOSO PARTNERS LLC DES:FUNDING ID:1", "financing_named_payer"),
    ("FABRIKAM GROUP LLC DES:CASH ADV ID:1", "financing_named_payer"),
    ("CAPITAL FABRIKAM LLC DES:PAYMENT ID:1", "financing_named_payer"),
    ("FABRIKAM FUNDING LLC DES:PAYMENT ID:1", "financing_named_payer"),
    ("FABRIKAM MERCHANT FUNDING DES:DEAL FUNDING ID:1", "financing_named_payer"),
    ("CONTOSO HOLDINGS LLC DES:PAYMENT ID:1", "holder_name"),
    ("CONTOSO BAKERY LLC DES:VENDOR PAY ID:1", "holder_name"),
    ("ZELLE PAYMENT FROM CONTOSO BAKERY LLC CONF 99", "holder_name"),
    ("FABRIKAM INC DES:BONUS ID:1", "payroll_or_salary"),
    ("FABRIKAM INC DES:PAYRL ID:1", "payroll_or_salary"),
    ("FABRIKAM INC DES:PAYROLL ID:1", "payroll_or_salary"),
    ("FABRIKAM INC DIR DEP 540115 1234567 JOHN SMITH", "payroll_or_salary"),
    ("FABRIKAM INC DES:EXP REIMB ID:1", "payroll_or_salary"),
    ("SSA TREAS 310 DES:XXSOC SEC ID:1", "personal_income"),
    ("FABRIKAM HOLDINGS LLC DES:INVESTMENT ID:1", "non_sale_purpose"),
    ("FABRIKAM PARTNERS LP DES:DISTRIB ID:1", "non_sale_purpose"),
    ("FABRIKAM SUPPLY INC DES:REBATE ID:1", "non_sale_purpose"),
    ("COMPTROLLER OF MD DES:MDREFUND ID:1", "non_sale_purpose"),
    ("IRS TREAS 310 DES:TAX EIC ID:1", "non_sale_purpose"),
    ("STATE OF OHIO DES:GRANT ID:1", "non_sale_purpose"),
    ("DIVIDEND", "non_sale_purpose"),
    ("WIRE IN DATE 540102 TRN 123", "wire_no_sender"),
    ("ONLINE BANKING TRANSFER CREDIT REF 88", "transfer_no_counterparty"),
    ("TELLER TRANSFER", "transfer_no_counterparty"),
    ("ONLINE TRANSFER FROM SMITH J EVERYDAY CHECKING XXXXXX1234 REF IB0ABCD", "transfer_account_designation"),
    ("WIRE IN FROM JOHN SMITH TRN 99", "wire_named_sender"),
    ("MOBILE DEPOSIT", "check_deposit"),
    ("REMOTE ONLINE DEPOSIT 1", "check_deposit"),
    ("COUNTER CREDIT", "no_payer_printed"),
    ("BRANCH DEPOSIT", "no_payer_printed"),
    ("DEPOSIT", "no_payer_printed"),
    ("ZELLE PAYMENT FROM JOHN SMITH CONF 99", "p2p"),
    ("ONLINE TRANSFER FROM JOHN SMITH REF IB0ABCD", "p2p"),
    ("SQUARE INC DES:TRANSFER ID:1", "platform_unconfirmed"),
    ("SEZZLE DES:PAYOUT ID:1", "payout_credit_entity"),
    ("DIRECT DEPOSIT 1234567", "numbered_company_payer"),
    ("1234567 NOVA SCOTIA LTD DES:VENDOR PAY ID:1", "numbered_company_payer"),
    ("NORTHWIND LANDSCAPE DES:SETTLEMENT ID:1", "named_payer_purpose_refused"),
    ("NORTHWIND SUPPLY DES:CREDIT ID:1", "named_payer_one_off"),
    ("NORTHWIND LANDSCAPE", "named_payer_unlabelled"),
])
def test_each_reason_code(text, reason):
    record = _one(text)
    assert _tier(record) == (REVENUE_TIER_REASONS[reason][0], reason)
    assert record.revenue_classification == "unverified_deposit"
    assert record.revenue_review_required is (REVENUE_TIER_REASONS[reason][0] == "excluded_pending_review")


def test_a_direction_conflict_and_a_payer_debited_as_a_lender_or_otherwise_are_held():
    conflict = classify_statement_transactions(Statement(account_name=HOLDER, transactions=[
        Transaction(date="2054-03-02", description="NORTHWIND SUPPLY DES:PAYMENT ID:1", amount=500.0,
                    direction="debit")]))[0]
    assert _tier(conflict) == ("excluded_pending_review", "direction_conflict")
    # An unregistered funder that funds and then collects on a weekly cadence (D6 makes its debits potential).
    lender = classify_statement_transactions(Statement(account_name=HOLDER, transactions=[
        Transaction(date="2054-03-01", description="NORTHWIND VENTURES DES:PAYMENT ID:1", amount=9000.0,
                    direction="credit"),
        *(Transaction(date=f"2054-03-{day:02d}", description="NORTHWIND VENTURES DES:DEBIT ID:2", amount=-300.0,
                      direction="debit") for day in (2, 9, 16, 23)),
    ]))
    assert {record.classification for record in lender[1:]} == {"potential_lender"}
    assert _tier(lender[0]) == ("excluded_pending_review", "payer_debited_as_lender")
    affiliate = _records([("NORTHWIND SUPPLY DES:PAYMENT ID:1", 5000.0), ("NORTHWIND SUPPLY DES:DEBIT ID:2", -250.0)])
    assert _tier(affiliate[0]) == ("excluded_pending_review", "payer_also_debited")
    # The verifier's funder statement: an AP-worded credit and same-name debits no rule classifies as a lender.
    funder = _records([("NORTHWIND SUPPLY DES:VENDOR PAY ID:1", 5000.0),
                       *[("NORTHWIND SUPPLY DES:DEBIT ID:2", -250.0 - day) for day in range(5)]])
    assert _tier(funder[0]) == ("excluded_pending_review", "payer_also_debited")


def test_a_factoring_payout_is_counted_and_keeps_its_flag():
    record = _one("RTS FINANCIAL DES:PAYMENT ID:1")
    assert _tier(record) == ("counted_flagged", "factoring_payout")
    assert record.flagged_group == "factoring"


def test_round_sums_from_one_sender_are_held_on_rails_and_named_transfers_alike():
    rails = _records([("ZELLE PAYMENT FROM JOHN SMITH CONF 1", 500.0), ("ZELLE PAYMENT FROM JOHN SMITH CONF 2", 700.0),
                      ("ZELLE PAYMENT FROM JOHN SMITH CONF 3", 123.0)])
    assert [_tier(record)[1] for record in rails] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]
    one_round = _records([("ZELLE PAYMENT FROM JOHN SMITH CONF 1", 500.0),
                          ("ZELLE PAYMENT FROM JOHN SMITH CONF 2", 123.0)])
    assert [_tier(record)[1] for record in one_round] == ["p2p", "p2p"]
    transfers = _records([("ONLINE TRANSFER FROM JOHN SMITH REF 1", 300.0),
                          ("ONLINE TRANSFER FROM JOHN SMITH REF 2", 300.0)])
    assert [_tier(record)[1] for record in transfers] == ["p2p_round_repeat", "p2p_round_repeat"]


def test_q5_verifies_a_company_that_wires_twice_and_its_guards_refuse():
    wire = "WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:{n} SEQ:1/2 ORIG:{orig} ID:99 SND BK:SAMPLE BANK ID:1"
    twice = _records([(wire.format(n=1, orig="NORTHWIND EXPORTS LLC"), 25000.0),
                      (wire.format(n=2, orig="NORTHWIND EXPORTS LLC"), 26000.0)])
    assert {record.revenue_match_method for record in twice} == {"repeat_wire_sender"}
    once = _records([(wire.format(n=1, orig="NORTHWIND EXPORTS LLC"), 25000.0)])
    assert _tier(once[0]) == ("counted_flagged", "wire_named_sender")
    for orig in ("JOHN SMITH", "SAMPLE BANK NA", "NORTHWIND TITLE LLC", "1234567 ONTARIO INC"):
        rows = _records([(wire.format(n=1, orig=orig), 25000.0), (wire.format(n=2, orig=orig), 26000.0)])
        assert {record.revenue_classification for record in rows} == {"unverified_deposit"}, orig
    investment = _records([(wire.format(n=1, orig="FABRIKAM VENTURES LLC") + " OBI SERIES A INVESTMENT", 50000.0),
                           (wire.format(n=2, orig="FABRIKAM VENTURES LLC") + " OBI SERIES A INVESTMENT", 50000.0)])
    assert {_tier(record) for record in investment} == {("excluded_pending_review", "non_sale_purpose")}
    payroll = _records([(wire.format(n=1, orig="FABRIKAM INC") + " OBI PAYROLL JAN", 9000.0),
                        (wire.format(n=2, orig="FABRIKAM INC") + " OBI PAYROLL JAN", 9000.0)])
    assert {_tier(record) for record in payroll} == {("excluded_pending_review", "payroll_or_salary")}


def test_a_third_party_book_transfer_sweep_is_held():
    rows = _records([("BOOK TRANSFER CREDIT B/O: FABRIKAM HOLDINGS LLC SAMPLEVILLE REF: INTERCO SWEEP", 20000.0)] * 2)
    assert {_tier(record) for record in rows} == {("excluded_pending_review", "non_sale_purpose")}


def test_q6_verifies_a_repeat_a_company_form_and_a_public_or_healthcare_payer():
    repeat = _records([("NORTHWIND SUPPLY DES:PAYMENT ID:1 CCD", 700.0), ("NORTHWIND SUPPLY DES:PAYMENT ID:2 CCD", 710.0)])
    assert {record.revenue_match_method for record in repeat} == {"named_payer_repeats"}
    consumer = _records([("NORTHWIND SUPPLY DES:PAYMENT ID:1 PPD", 700.0),
                         ("NORTHWIND SUPPLY DES:PAYMENT ID:2 PPD", 710.0)])
    assert {record.revenue_classification for record in consumer} == {"unverified_deposit"}
    assert _one("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1").revenue_match_method == "named_payer_company_form"
    assert _one("SAMPLE COUNTY DES:PAYMENT ID:1").revenue_match_method == "public_or_healthcare_payer"
    assert _one("AETNA DES:PAYMENT ID:1").revenue_match_method == "public_or_healthcare_payer"
    assert _tier(_one("AETNA DES:MEMBER REIMB ID:1")) == ("excluded_pending_review", "non_sale_purpose")


def test_a_held_row_never_makes_a_repeat():
    rows = _records([("NORTHWIND SUPPLY DES:RETURN ID:1", 50.0), ("NORTHWIND SUPPLY DES:CREDIT ID:2", 700.0)])
    assert [_tier(record) for record in rows] == [
        ("excluded_pending_review", "possible_return"), ("counted_flagged", "named_payer_one_off")]


def test_a_distributor_and_an_owner_operator_are_customers():
    assert _one("FABRIKAM DISTRIBUTORS INC DES:PAYMENT ID:1").revenue_tier == "verified"
    assert _one("FABRIKAM CARRIERS INC DES:OWNER OP ID:1").revenue_tier == "verified"


def test_the_registry_is_exempt_from_the_holder_test():
    record = _one("SQUARE INC DES:SQ540115 ID:1", holder="SQUARE ONE BAKERY LLC")
    assert _tier(record) == ("verified", None)


def test_the_four_tiers_add_up_to_the_posted_credits():
    records = _records([("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), ("MOBILE DEPOSIT", 300.0),
                        ("FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), ("INTERNAL TRANSFER FROM SAVINGS", 100.0),
                        ("FABRIKAM SUPPLY DES:DEBIT ID:1", -50.0)])
    tiers = {}
    for record in records:
        if record.amount > 0:
            tiers[record.revenue_tier] = tiers.get(record.revenue_tier, 0.0) + record.amount
    assert tiers == {"verified": 700.0, "counted_flagged": 300.0, "excluded_pending_review": 900.0,
                     "non_revenue": 100.0}
    assert records[4].revenue_tier is None


# ---------------------------------------------------------------------------------------------------------------------
# The review's holes (2026-09-29): refunds, platform capital, the holder's own ACH transfer, paychecks, title firms,
# card refunds and the auction's refunds, each alone and repeated.
# ---------------------------------------------------------------------------------------------------------------------
REFUNDS = [
    "FABRIKAM INC DES:REFUNDS ID:1",
    "FABRIKAM INC DES:REFUNDING ID:1",
    "FABRIKAM INC DES:CUST REFUNDS ID:1",
    "FABRIKAM INC DES:REFUNDREQ ID:1",
    "FABRIKAM INC DES:PREFUND ID:1",
    "NORTHWIND SUPPLY DES:REFUNDS ID:1 CCD",
    "ORIG CO NAME:FABRIKAM INC ORIG ID:1 DESC DATE: CO ENTRY DESCR:REFUNDS SEC:CCD",
]


@pytest.mark.parametrize("text", REFUNDS)
def test_a_refund_word_glued_or_not_is_held_alone_and_repeated(text):
    # Review C1: the financing root reads FUND only when RE does not precede it (a refund is no funding), so the
    # refund words hold the row as a non-sale purpose; a repeat or a company form never verifies it.
    alone = _one(text, 250.0)
    assert _tier(alone) == ("excluded_pending_review", "non_sale_purpose")
    repeated = _records([(text, 250.0), (text.replace("ID:1", "ID:2"), 260.0)])
    assert {_tier(record) for record in repeated} == {("excluded_pending_review", "non_sale_purpose")}


@pytest.mark.parametrize("text", [
    "STRIPE DES:CAPITAL ID:1", "SHOPIFY DES:CAPITAL ID:1", "DOORDASH INC DES:CAPITAL ID:1", "TOAST INC DES:CAPITAL ID:1",
    "CLOVER DES:CAPITAL ADV ID:1", "SPOTON DES:ADVANCE ID:1", "HEARTLAND PAYMENT SYSTEMS DES:FUNDING ID:1",
    "UBER DES:ADVANCE ID:1", "ETSY DES:FUNDING ID:1", "MANHEIM US DES:FUNDING ID:1", "MANHEIM US DES:FLOORPLAN ID:1",
    "MANHEIM US DES:ACH PAYMNT NGC ID:1",
])
def test_a_platform_s_capital_or_an_auction_s_floor_plan_credit_is_held(text):
    # Review C2: the registry never claims a row that prints a financing word, so it is held as financing.
    records = _records([(text, 15000.0), (text.replace("ID:1", "ID:2"), 15001.0),
                        (text.replace("ID:1", "ID:3"), 15002.0)], holder="SAMPLE MOTORS LLC")
    assert {_tier(record) for record in records} == {("excluded_pending_review", "financing_named_payer")}


def test_a_platform_s_own_settlement_words_keep_it_counted():
    # §7.0: TapGoods prints FUNDING on its settlements; a delivery platform prints the merchant's store (the
    # holder's own words) in its entry field. Neither is financing.
    tapgoods = _one("TGPAYMENTS DES:FUNDING ID:1", 900.0)
    assert _tier(tapgoods) == ("counted_flagged", "platform_unconfirmed")
    store = _one("DOORDASH INC DES:SAMPLE CAPITA ID:1 INDN:SAMPLE CAPITAL GROUP CO ID:1 CCD", 900.0,
                 holder="SAMPLE CAPITAL GROUP LLC")
    assert _tier(store) == ("counted_flagged", "platform_unconfirmed")


@pytest.mark.parametrize("text", [
    "CONTOSO BAKERY DES:TRANSFER ID:1",
    "CONTOSO BAKERY LLC DES:XFER ID:1 CCD",
    "ORIG CO NAME:CONTOSO BAKERY LLC ORIG ID:1 DESC DATE: CO ENTRY DESCR:TRANSFER SEC:CCD",
])
def test_the_holder_s_own_ach_transfer_is_held(text):
    # Review C3: a transfer-worded ACH row with no FROM sender reads its originator as its payer.
    assert _tier(_one(text, 10000.0)) == ("excluded_pending_review", "holder_name")


def test_an_ach_transfer_from_a_payer_the_statement_also_debits_is_held():
    records = _records([
        ("NORTHWIND BAKERY DES:TRANSFER ID:1 INDN:NORTHWIND BAKERY CO ID:1 CCD", 5000.0),
        ("NORTHWIND BAKERY DES:TRANSFER ID:2 INDN:NORTHWIND BAKERY CO ID:1 CCD", -3000.0),
    ], holder="BUSINESS CHECKING")
    assert _tier(records[0]) == ("excluded_pending_review", "payer_also_debited")


@pytest.mark.parametrize("text", [
    "FABRIKAM INC DES:PAYCHECK ID:1 PPD", "FABRIKAM INC DES:PR PAYMENT ID:1", "FABRIKAM INC DES:EMPLOYEE PAY ID:1 PPD",
])
def test_a_paycheck_is_payroll(text):
    # Review I6: PAYCHECK, PR PAY and EMPLOYEE PAY join Q8's pay words.
    assert _tier(_one(text, 2500.0)) == ("excluded_pending_review", "payroll_or_salary")


@pytest.mark.parametrize("text", [
    "FABRIKAM INC DES:PAYMENT ID:1 PPD",          # a consumer entry never verifies by its company form (review I6)
    "NORTHWIND TITLE LLC DES:PAYMENT ID:1",       # a title firm is no customer (§8.5's senders)
    "SAMPLE COMMUNITY BANK INC DES:PAYMENT ID:1",  # nor is a bank
])
def test_a_consumer_entry_a_title_firm_or_a_bank_never_verifies_by_its_company_form(text):
    assert _tier(_one(text, 2500.0)) == ("counted_flagged", "named_payer_one_off")


@pytest.mark.parametrize("text", [
    "VISA CREDIT FABRIKAM STORE", "CHECKCARD CREDIT FABRIKAM STORE", "PURCHASE CREDIT FABRIKAM STORE",
    "MANHEIM US DES:DEALSHIELD ID:1", "MANHEIM US DES:ARB CREDIT ID:1",
])
def test_a_card_refund_and_an_auction_refund_are_possible_returns(text):
    # Review M6 and §7.8: a card credit's posting label and an auction's guarantee or arbitration refund.
    assert _tier(_one(text, 80.0, holder="SAMPLE MOTORS LLC")) == ("excluded_pending_review", "possible_return")


def test_q5_never_verifies_a_wire_that_prints_a_push_rail():
    # §6.1 step 9b: a real-time or push rail verifies through the registry only, never by Q5's repeats.
    wire = ("WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:{n} ORIG:FABRIKAM EXPORTS LLC ID:1 SND BK:SAMPLE BANK "
            "ID:1 PMT DET:PAYMENT RECEIVED")
    records = _records([(wire.format(n=1), 20000.0), (wire.format(n=2), 21000.0)])
    assert {record.revenue_classification for record in records} == {"unverified_deposit"}
```

Append to the end of `tests/test_revenue_census.py`:

```python
def test_one_fabricated_statement_snapshots_with_its_tiers_and_facts():
    from analysis.serialization import document_report_to_dict
    from tests.test_webapp_studio_views import _report

    rows = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
            (4, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), (5, "INTERNAL TRANSFER FROM SAVINGS", 100.0),
            (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0)]
    payload = document_report_to_dict(_report("CONTOSO BAKERY LLC", "000000001010", 1500.0, rows))
    # A statement of one account is served flat; a document of several carries `accounts`.
    snap = census.snapshot([("s", payload["accounts"][0] if "accounts" in payload else payload)])
    [account] = snap["accounts"].values()
    tiers = sorted((credit["tier"], credit["reason"]) for credit in account["credits"])
    assert tiers == [("counted_flagged", "check_deposit"), ("excluded_pending_review", "financing_named_payer"),
                     ("non_revenue", None), ("verified", None)]
    # Every digit is masked in the census output.
    assert not any(ch.isdigit() for credit in account["credits"] for ch in credit["text"])
    assert account["credits"][2]["facts"]["financing_root"]
    assert account["posted_credit_count"] == 4 and account["posted_credit_cents"] == 200000
    assert _run(snap, snap)["guards"] == {}
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_true_revenue_tiers.py tests/test_revenue_census.py -q -p no:cacheprovider`

Expected: FAIL: `88 failed, 45 passed`, the first with `AssertionError: assert (None, None) == ('excluded_pe...nsurer_payer')`.

- [ ] **Step 3: Implement.**

Create `analysis/true_revenue.py`:

```python
"""Classification 5.6: the true-revenue pass (docs/superpowers/specs/2026-09-28-true-revenue-design.md §5, §8).

Statement pass 7 (§6.2) runs after every verifying rule of `analysis/transaction_classifier.py`. It reads each posted
credit's payer facts (channel family, payer region, payer name and key, entry fields, the holds of §8.1), then runs
the Q5 and Q6 verifications (§8.5, §8.6), which refuse any row a hold names, and last gives every posted credit its
tier and reason (§5.3), in the order of §8.10.

It imports the classifier's readers at call time: the classifier imports this module inside
`classify_statement_transactions`, after both are loaded.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Sequence

from .classification_registry import (
    DEALER_FUNDING_PAYERS,
    HEALTHCARE_PAYER_ALIASES,
    PAYOUT_CREDIT_ENTITIES,
)
from .flag_groups import FINANCING_STATES
from .payee_matcher import match_known_payee, registry_match
from .revenue import revenue_contribution_flags

if TYPE_CHECKING:
    from .transaction_classifier import TransactionClassification

#: §8.1: the posting labels removed before a hold reads a row: §7.5's credit posting labels, the branch, card and
#: batch CREDIT labels, and the channel phrases.
_HOLD_POSTING_LABELS = re.compile(
    r"\b(?:ELECTRONIC|ACH|RTP|ONLINE|WIRE|BOOK|CORP|CORPORATE|ZELLE|MISC|DIRECT|PAYMENT|DEPOSIT|TRANSFER|MOBILE|EFT"
    r"|CHIPS|FEDWIRE|INSTANT|REAL TIME|COUNTER|POS|ATM|TELLER|BRANCH|CARD|BATCH|MERCHANT|VISA|CHECKCARD|PURCHASE)"
    r"\s+CREDIT\b|^CREDIT\b"
    r"|\bCREDIT FROM\b|\bFUNDS (?:TRANSFER|AVAILABLE)\b|\bINSTANT FUNDS\b"
)
#: §8.1, T4: the credit-side financing roots. A whole-word CREDIT counts only inside a payer name, next to another
#: name word; glued, it always counts.
_FINANCING_ROOT = re.compile(
    r"(?:(?<!RE)FUND|CAPIT|CAPTL|LOAN|LEND|FINANC|ADVANC|MORTG|ACCEPTANCE|SERVICING|SERVICER|LEASING|PORTFOL)"
    r"|CRED(?=ORA|IBLY)|[A-Z]CREDIT|CREDIT[A-Z]"
    r"|\b(?:CAP|CAPI|FIN|FINA|FINAN|FINL|FNCL|ADV|MTG|MCA|RTR|SPV|LEASE)\b"
)
_WHOLE_CREDIT = re.compile(r"\bCREDITS?\b")
#: §8.7: the dealer-funding words.
DEALER_FUNDING_WORDS = re.compile(
    r"\bVHCL PURCH\w*|\bVEHICLE PURCHASE\b|\bDEAL ?FUND\w*|\bFUNDLOAN\b|\bDEALER (?:FUND\w*|FND|PMT|PAY\w*)\b"
    r"|\bDLR PMT\b|\bAUTODLRPMT\b|\bCONTRACT FUND\w*|\bVADMIN FEE\b"
)
#: §8.1: an insurer's name on the payer region.
_INSURER_NAME = re.compile(r"\bINSUR\w*|\bASSURANCE\b|\bMUTUAL\b|\bCASUALTY\b|\bINDEMNITY\b|\bUNDERWRIT\w*")
_CLAIM_WORD = re.compile(r"\bCLAIMS?\b")
_POSSIBLE_RETURN = re.compile(
    r"\bRETURN(?:ED|S)?\b|\bADJ(?:USTMENT|USTED)?\b|\bDISPUTE[DS]?\b|\bCREDIT MEMO\b|\bOVERPA\w*"
    # §7.8: an auction's guarantee or arbitration refund of a vehicle the dealer bought.
    r"|\bDEALSHIELD\b|\bARB(?:ITRATION)? CREDIT\b"
)
#: §8.1, §7.11: a card credit's posting labels (a refund to the card unless a form or the registry verified it).
_CARD_CREDIT_LABEL = re.compile(r"\b(?:DEBIT CARD CREDIT|POS CREDIT|VISA CREDIT|CHECKCARD CREDIT|PURCHASE CREDIT)\b")
#: §8.1 (Q8): pay wording, read on the row before its receiver fields.
_PAY_WORDS = re.compile(
    r"\bPAYROLL\w*|\bPAYRLL\b|\bPAYROL\b|\bPAYRL\b|\bSALARY\b|\bSALARIES\b|\bREG SAL\b|\bWAGES?\b|\bNET ?PAY\b"
    r"|\bBONUS(?:ES)?\b|\bPAY PAY\b|\bPAIE\b|\bSALAIRES?\b|\bPAYCHECKS?\b|\bPAYCHK\b|\bPR PAY\w*|\bEMPLOYEE PAY\w*"
    r"|\bEMP PAY\b"
    r"|\bDIR ?DEP\b|\bDIRDEP\b|\bDIRECT DEP\b(?!OSIT)|\b(?:DES|CO ENTRY DESCR) DIRECT DEPOSIT\b"
    r"|\bEXP(?:ENSE)? REIMB\w*"
)
#: §8.1: benefit and pension credits.
_PERSONAL_INCOME = re.compile(
    r"\b(?:XX)?SOC SEC\b|\bSSA\b|\bSSI\b|\bSUPP SEC\b|\b(?:XX)?VA BEN\w*|\bUNEMPLOY\w*|\bUI BEN\w*"
    r"|\bCHI?LD ?SUPP\w*\b|\bCHILD ?CTC\b|\bPENSION\b|\bANNUIT\w*|\bRETIRE\w*"
)
#: §8.1: a non-sale purpose.
_NON_SALE_PURPOSE = re.compile(
    r"\bINVEST\w*|\bDISTRIB(?!UTORS?\b|UTING\b)\w*|\bDIVIDENDS?\b|\bEQUITY\b|\bCONTRIB\w*|\bSHAREHOLDER\w*"
    r"|\bOWNERS?\b(?! OP\b| OPERATORS?\b)|\bSTOCK\b|\bINTERCO\w*|\bINTER COMPANY\b|\bDUE FROM\b|\bSWEEP\b|\bZBA\b"
    r"|\bZERO BAL\w*"
    r"|\bREPAY\w*|\bPRINCIPAL\b|\bPAYOFF\b|\bPROMISSORY\b|\bCONVERTIBLE\b|\bTRANCHE\b|\bDRAWS?\b|\bDRAWDOWNS?\b"
    r"|\bDISBURS\w*"
    r"|\bESCROW\b|\bEARNEST\b|\bSECURITY DEPOSIT\b|\bDEPOSIT BACK\b|\bSURPLUS\b"
    r"|\bGRANTS?\b|\bDONATION\w*|\bGIFT\b(?! CARD\b)|\bCOURT\b|\bJUDGMENT\b"
    r"|\bREBATES?\b|\bREIMB\w*|\bINTEREST\b|\bREWARDS?\b|\bCASH ?BACK\b"
    r"|[A-Z]*REFUND\w*|\bRFND\w*|\bREFND\w*"
)
#: §8.1: a healthcare payer's member or premium credit.
_HEALTHCARE_MEMBER_WORDS = re.compile(r"\bREIMB\w*|\bMEMBER\b|\bMBR\b|\bSUBSCRIBER\b|\bPREMIUM\b")
#: §8.4, T13: an account designation printed by a named transfer.
_ACCOUNT_DESIGNATION = re.compile(
    r"\b(?:CHECKING|CHK|CHKG|SAVINGS|SAVING|SAV|SVGS|MONEY MARKET|MMA|DDA|ACCOUNT|ACCT|EVERYDAY)\b"
    r"|\bX{2,}\d{2,}\b|\bENDING (?:IN )?\d{3,}\b"
)
_ACCOUNT_WORDS = frozenset({
    "CHECKING", "CHK", "CHKG", "SAVINGS", "SAVING", "SAV", "SVGS", "MONEY", "MARKET", "MMA", "DDA", "ACCOUNT", "ACCT",
    "EVERYDAY",
})
#: §8.5: the loose wire words, for tiering only.
_LOOSE_WIRE = re.compile(r"\bWIRE\b|\bFEDWIRE\b|\bFED WIRE\b|\bIWT\b|\bCHIPS CREDIT\b|\bSWIFT\b|\bFOREIGN REMITTANCE\b"
                         r"|\bWT FED\b|\bFED REF\b")
#: §8.5: a sender that names a bank, a title or an escrow firm never verifies by repetition.
_BANK_OR_TITLE_SENDER = re.compile(
    r"\b(?:BANK|BANCO|BANCORP|N A|TRUST COMPANY|CREDIT UNION|FCU|SAVINGS|TITLE|ESCROW|CLOSING|SETTLEMENT)\b"
)
#: §8.6: the verification-only words: sales wording often enough to count, never proof.
_VERIFICATION_ONLY = re.compile(
    r"\bSETTLEMENT\b|\bTAX(?:ES)?\b|\bIRS\b|\bCRA\b|\bFEES?\b|\bSUBSCRIPTIONS?\b|\bDISCOUNT\w*|\bCOMM?ISS?IONS?\b"
    r"|\bCOMPENSATION\b|\bEXPENSES?\b|\bAFFILIATE\b|\bPERSONAL\b|\bCLOSING\b|\bSCF\b|\bSUPPLY CHAIN\b"
    r"|\bEARLY PAY(?:MENT)?\b|\bALLOWANCES?\b|\bSHORTAGES?\b|\bRMA\b"
)
_ENTRY_VERIFICATION_ONLY = re.compile(r"\bFLOOR ?PLAN\b|\bFLOORPLAN\b|\bVIN\b|\bEQUIP\w*")
_CONSUMER_ENTRY = re.compile(r"\b(?:PPD|WEB)\b")
#: §8.6 method names.
_Q6_METHODS = ("named_payer_repeats", "named_payer_company_form", "public_or_healthcare_payer")
#: §8.1 (review C2): the financing words on a registry row: the recurrence veto's financing words (§7.0), the
#: new-read financing veto (§7.2) and the auction's financing words (§7.8). A platform's or processor's capital,
#: advance or loan credit and an auction's floor-plan or NextGear credit are never claimed by the registry.
_REGISTRY_FINANCING_WORDS = re.compile(
    r"\b(?:LOANS?|CAPITAL|CAP\d*(?:SEC)?|CAPI|CAPIT|CAPITA|CAPTL|FIN|FINANC\w*|LEND\w*|ADVANCE[SD]?|ADVN?C?|ADV|MCA"
    r"|CASH ADV\w*|FUNDING|FUNDNG|FUNDED|PROCEEDS|DRAW|FLOOR ?PLAN|FLOORPLAN|NGC)\b"
)
#: G2 (review I1): a financing root glued inside a word of a registry row (STRIPECAPITAL, SHOPIFYCAPITAL).
_GLUED_FINANCING_ROOT = re.compile(r"CAPITAL|CAPTL|FINANC|FUNDING|FUNDNG|LENDING|LENDER|LOAN")
#: The registry-family methods: a platform, processor or payout the operating registry named (§8.9).
_REGISTRY_METHODS = frozenset({
    "operating_source_requires_context", "operating_source_with_credit_context", "recurring_operating_source",
    "operating_source_related_activity", "wholesale_auction_payout_form",
})
#: §5.3: tiers by revenue state; the two middle tiers are unverified.
_TIER_OF_STATE = {"verified_revenue": "verified", "non_revenue": "non_revenue"}
#: §8.10: the lender and financing debit states payer_debited_as_lender reads.
_LENDER_DEBIT_STATES = frozenset({"confirmed_lender", "potential_lender"}) | FINANCING_STATES
_HEALTHCARE_INDEX = {"": HEALTHCARE_PAYER_ALIASES}


@dataclass(frozen=True)
class CreditFacts:
    """§8: one posted credit's payer facts."""

    channel: str
    region: str
    name: str
    key: tuple[str, ...]
    entry: str
    hold: str | None
    claimed: bool
    wire_n1: bool
    company_form: bool
    public_or_healthcare: bool
    healthcare: bool
    numbered: bool
    electronic: bool
    refused_word: bool
    round_sum: bool
    consumer_entry: bool
    transfer_no_counterparty: bool
    account_designation: bool


def _classifier():
    from . import transaction_classifier

    return transaction_classifier


def healthcare_payer(region: str) -> bool:
    """§5.2: a payer region that matches HEALTHCARE_PAYER_ALIASES."""
    return bool(region) and registry_match(region, HEALTHCARE_PAYER_ALIASES) is not None


def government_payer(region: str) -> bool:
    """§5.2: a payer region the public-payer patterns of §7.6 match at its start, and the payer-name veto does not."""
    classifier = _classifier()
    if not region:
        return False
    name = classifier._PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)
    found = classifier._PUBLIC_PAYER_NAME.match(name)
    return (
        found is not None
        and not any(ch.isdigit() for ch in found.group(1))
        and classifier._PUBLIC_PAYER_NAME_VETO.search(name) is None
    )


def public_region(text: str) -> str:
    """§5.2: the region a government payer is read on: the payee region of the row before its receiver fields, with
    the template prefixes removed, before the digit cut, so 'TREAS 310' keeps its digits."""
    classifier = _classifier()
    return classifier._payee_region(classifier._strip_revenue_template(classifier._before_receiver(text))).strip()


def _public_named(region: str) -> bool:
    """§8.1: the payer region matches a §7.6 payer pattern or the payer-name veto (a public payer of any kind)."""
    classifier = _classifier()
    if not region:
        return False
    name = classifier._PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)
    return classifier._PUBLIC_PAYER_NAME.match(name) is not None or bool(
        re.search(r"\b(?:DEPT OF REVENUE|DEPARTMENT OF REVENUE|TAXATION|COMPTROLLER|TREASURER|DEPT OF LABOR"
                  r"|UNEMPLOYMENT|WORKFORCE)\b", name)
    )


def _hold_text(text: str) -> str:
    """§8.1: the row before its receiver fields with the posting labels removed."""
    classifier = _classifier()
    return _HOLD_POSTING_LABELS.sub(" ", classifier._before_receiver(text))


def financing_named(text: str, region: str, entry: str, account_name: str | None) -> bool:
    """§8.1, T4: a financing root in the payer region or the entry fields (posting labels removed, and a run equal to
    the holder's whole account name removed first), or, on a row with no payer region, in the row before its
    receiver fields. A whole-word CREDIT counts only inside a payer name, next to another name word."""
    classifier = _classifier()
    holder = classifier.account_name_text(account_name)
    parts = []
    if region:
        payer = _HOLD_POSTING_LABELS.sub(" ", region)
        if len(holder.split()) >= 2:
            payer = payer.replace(holder, " ")
        parts.append(payer)
        name_words = classifier.payer_name(payer).split()
        if len(name_words) >= 2 and _WHOLE_CREDIT.search(" ".join(name_words)):
            return True
        if entry:
            parts.append(_HOLD_POSTING_LABELS.sub(" ", entry))
    else:
        row = _hold_text(text)
        if len(holder.split()) >= 2:
            row = row.replace(holder, " ")
        parts.append(row)
    return any(_FINANCING_ROOT.search(part) for part in parts)


def non_sale_purpose(text: str, region: str) -> bool:
    """§8.1: a non-sale purpose, a public payer's refund or benefit, or a healthcare payer's member or premium credit."""
    classifier = _classifier()
    row = _hold_text(text)
    claim_entry = classifier._HCCLAIMPMT.search(text) is not None
    healthcare = healthcare_payer(region)
    purpose = _NON_SALE_PURPOSE.search(row)
    if purpose is not None:
        return True
    if _CLAIM_WORD.search(row) and not claim_entry and not (healthcare and re.search(r"\bCLAIM PMT\b", row)):
        return True
    if _public_named(public_region(text)) and classifier._PUBLIC_PAYER_NON_SALE_WORDS.search(
        classifier._TREASURY_BOILERPLATE.sub(" ", text)
    ):
        return True
    return healthcare and _HEALTHCARE_MEMBER_WORDS.search(row) is not None


def _dealer_funding_payer(text: str) -> str | None:
    """§8.7: the listed auto lender the originator segment names: a vehicle_financing registry entity or a
    DEALER_FUNDING_PAYERS entry; or None."""
    classifier = _classifier()
    segment = classifier._originator_segment(text)
    known = match_known_payee(segment)
    if known is not None and known.state == "vehicle_financing":
        return known.entity
    found = registry_match(segment, DEALER_FUNDING_PAYERS)
    return found[0] if found is not None else None


def _first_word(region: str) -> str | None:
    return _classifier()._payer_first_distinctive_word(region)


def _debit_words(records: Sequence[TransactionClassification], duplicates: set[int]) -> tuple[set[str], set[str]]:
    """The first distinctive words of the statement's posted debits: (lender and financing debits, the others)."""
    classifier = _classifier()
    lender: set[str] = set()
    other: set[str] = set()
    for index, record in enumerate(records):
        if index in duplicates or record.amount >= 0 or not record.is_posted:
            continue
        word = classifier._debit_first_distinctive_word(record)
        if word is None:
            continue
        (lender if record.classification in _LENDER_DEBIT_STATES else other).add(word)
    return lender, other


def _channel(text: str) -> str:
    """§5.2: the channel family: wire, ach_eft, person_to_person, check, cash_branch_atm or other."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    if classifier._is_wire_row(text):
        return "wire"
    if classifier._CONSUMER_P2P_RAIL.search(row) or classifier._PUSH_RAIL.search(row):
        return "person_to_person"
    if classifier._CHECK_DEPOSIT_FORM.search(row):
        return "check"
    if (not classifier._ELECTRONIC_PAYMENT_FORM.search(row) and classifier._CASH_BRANCH_ATM_FORM.search(row)):
        return "cash_branch_atm"
    if classifier._TRANSFER_WORDING.search(row):
        return "person_to_person"
    if _LOOSE_WIRE.search(row):
        return "wire"
    if classifier._ELECTRONIC_PAYMENT_FORM.search(row):
        return "ach_eft"
    return "other"


def _own_words(record: TransactionClassification, text: str) -> set[str]:
    """§7.0: the holder's own words, as the recurrence veto reads them: the account name's distinctive words and the
    name the bank prints in the receiver field (a delivery platform prints the merchant's store there)."""
    classifier = _classifier()
    own = set(classifier.holder_words(record.account_name))
    for found in classifier._RECEIVER_FIELD_VALUE.finditer(text):
        own.update(classifier._distinctive_words(found.group(0).split()[1:]))
    return own


def _own_word(word: str, own: set[str]) -> bool:
    """§7.0: a word of four letters or more that is one of the holder's own words or the start of one."""
    return len(word) >= 4 and any(mine == word or mine.startswith(word) for mine in own)


def registry_financing(record: TransactionClassification, text: str) -> bool:
    """§8.1 (review C2): a registry row whose row before its receiver fields prints a financing word, the holder's own
    words aside (§7.0) and FUNDING aside on the settlements of the three platforms §7.0 names. Such a row is not
    claimed by the registry: it is held as financing_named_payer."""
    if record.revenue_match_method not in _REGISTRY_METHODS:
        return False
    classifier = _classifier()
    own = _own_words(record, text)
    for found in _REGISTRY_FINANCING_WORDS.finditer(classifier._before_receiver(text)):
        word = found.group(0)
        if _own_word(word, own):
            continue
        if word in {"FUNDING", "FUNDED"} and record.revenue_canonical_entity in classifier._FUNDING_SETTLEMENT_ENTITIES:
            continue
        return True
    return False


def _claimed(record: TransactionClassification, text: str) -> bool:
    """§8.1, §8.9: the operating registry, a payout-credit entity or a factoring payee claimed the row. A registry row
    that prints a financing word is not claimed (review C2)."""
    if record.revenue_match_method in _REGISTRY_METHODS:
        return not registry_financing(record, text)
    if record.classification == "factoring":
        return True
    known = match_known_payee(text)
    return known is not None and known.entity in PAYOUT_CREDIT_ENTITIES


def _transfer_counterparty_words(text: str) -> list[str]:
    """§8.2: the payer words a transfer prints once template prefixes, generic words, account words and reference
    tokens are removed."""
    classifier = _classifier()
    row = classifier._strip_revenue_template(classifier._before_receiver(text))
    return [
        token for token in row.split()
        if classifier._is_payer_word(token) and token not in _ACCOUNT_WORDS
        and not classifier._TRANSFER_WORDING.fullmatch(token)
        and token not in {"TRANSFER", "TRNSFR", "XFER", "TFR", "BR", "TO", "BANKING", "INTERNET"}
    ]


def credit_facts(
    record: TransactionClassification,
    text: str,
    *,
    lender_words: set[str],
    debit_words: set[str],
) -> CreditFacts:
    """§8.1 to §8.9: one posted credit's payer facts, including the first hold of §8.10's order 2 to 11."""
    classifier = _classifier()
    region = classifier.payer_region(text)
    name = classifier.payer_name(region)
    entry = classifier.entry_fields(text)
    channel = _channel(text)
    row = classifier._before_receiver(text)
    claimed = _claimed(record, text)
    healthcare = healthcare_payer(region) and bool(classifier._ELECTRONIC_PAYMENT_FORM.search(row))
    public = government_payer(public_region(text))
    transfer_words = _transfer_counterparty_words(text) if channel == "person_to_person" else []
    transfer_row = (
        classifier._TRANSFER_WORDING.search(row) is not None
        and classifier._CONSUMER_P2P_RAIL.search(row) is None
        and classifier._PUSH_RAIL.search(row) is None
    )
    hold = _first_hold(
        record, text, region=region, entry=entry, claimed=claimed, lender_words=lender_words,
        debit_words=debit_words,
    )
    return CreditFacts(
        channel=channel,
        region=region,
        name=name,
        key=classifier._payer_key(region),
        entry=entry,
        hold=hold,
        claimed=claimed,
        wire_n1=classifier._INCOMING_WIRE_LABEL.match(text) is not None or classifier._third_party_book_transfer(text),
        company_form=classifier.company_form(name),
        public_or_healthcare=public or healthcare,
        healthcare=healthcare,
        numbered=classifier.numbered_company(text, region),
        electronic=classifier._ELECTRONIC_PAYMENT_FORM.search(row) is not None,
        refused_word=bool(
            _VERIFICATION_ONLY.search(entry) or _VERIFICATION_ONLY.search(region)
            or _ENTRY_VERIFICATION_ONLY.search(entry)
        ),
        round_sum=classifier.is_round_sum(record.amount),
        consumer_entry=_CONSUMER_ENTRY.search(text) is not None,
        transfer_no_counterparty=transfer_row and not transfer_words,
        account_designation=transfer_row and bool(transfer_words) and _ACCOUNT_DESIGNATION.search(row) is not None,
    )


def _first_hold(
    record: TransactionClassification,
    text: str,
    *,
    region: str,
    entry: str,
    claimed: bool,
    lender_words: set[str],
    debit_words: set[str],
) -> str | None:
    """§8.1 in §8.10's order (2 to 11): the first hold that names the row, or None. A row the registry, a payout
    entity or a factoring payee claimed takes only the insurer, possible-return, pay and benefit holds; a registry row
    that prints a financing word is held as financing_named_payer (review C2)."""
    classifier = _classifier()
    row = _hold_text(text)
    if record.revenue_match_method == "insurer_customer_payment":
        return "insurer_payer"
    claim_entry = classifier._HCCLAIMPMT.search(text) is not None
    if not claimed and region and (
        _INSURER_NAME.search(region)
        or (_CLAIM_WORD.search(region) and not claim_entry and not healthcare_payer(region))
    ):
        return "insurer_named_payer"
    if record.revenue_match_method != "reversal_cancellation_exclusion" and (
        _POSSIBLE_RETURN.search(row) or (_CARD_CREDIT_LABEL.search(text) and record.revenue_classification != "verified_revenue")
    ):
        return "possible_return"
    if not claimed and (
        financing_named(text, region, entry, record.account_name)
        or registry_financing(record, text)
        or _dealer_funding_payer(text) is not None
        or DEALER_FUNDING_WORDS.search(row) is not None
    ):
        return "financing_named_payer"
    word = _first_word(region) if region else None
    if not claimed and word is not None and word in lender_words:
        return "payer_debited_as_lender"
    if not claimed and region and classifier.holder_named(region, record.account_name):
        return "holder_name"
    if _PAY_WORDS.search(classifier._before_receiver(text)) or classifier._is_payroll_provider_row(
        classifier._before_receiver(text)
    ):
        return "payroll_or_salary"
    if _PERSONAL_INCOME.search(classifier._before_receiver(text)):
        return "personal_income"
    if not claimed and non_sale_purpose(text, region):
        return "non_sale_purpose"
    if not claimed and (
        record.revenue_match_method == "payer_remittance_with_counter_debit"
        or (word is not None and word in debit_words)
    ):
        return "payer_also_debited"
    return None


def _wire_verifies(record: TransactionClassification, text: str, facts: CreditFacts, repeats: int) -> bool:
    """§8.5 (Q5): the same company wires twice or more, and the row passes every veto of §7.9."""
    classifier = _classifier()
    if not facts.wire_n1 or facts.hold is not None or not facts.region or facts.numbered:
        return False
    if classifier.channel_gate(text) is not None:
        return False
    if not (facts.company_form or facts.public_or_healthcare) or repeats < 2:
        return False
    if _BANK_OR_TITLE_SENDER.search(facts.name) or facts.refused_word:
        return False
    if classifier._WIRE_NON_SALE_PURPOSE.search(text):
        return False
    if classifier._names_financing(classifier._wire_financing_text(text)):
        return False
    run = classifier._wire_originator_run(text)
    if run is not None and classifier._names_financing(run):
        return False
    if match_known_payee(text) is not None or classifier._cut_financing_originator(facts.region):
        return False
    holder = classifier.account_name_text(record.account_name)
    words = facts.region.split()
    if len(words) >= 2 and holder and " ".join(words[:2]) in holder:
        return False
    first = classifier._first_distinctive_word(classifier._distinctive_words(words))
    beneficiary = re.search(r"\bN?BNF\b (\S+)", text)
    if first is not None and (
        (beneficiary is not None and beneficiary.group(1) == first) or (holder and holder.split()[0] == first)
    ):
        return False
    return True


def _q6_method(facts: CreditFacts, repeats: int, all_consumer: bool) -> str | None:
    """§8.6 (Q6): the verifying method of an eligible named ACH or EFT payer, or None. A PPD or WEB entry never
    verifies by repetition alone (a) or by its company form (b, review I6), and neither does a bank or a title or
    escrow firm's company form (§8.5's senders)."""
    if repeats >= 2 and not all_consumer:
        return "named_payer_repeats"
    if facts.company_form and not facts.consumer_entry and not _BANK_OR_TITLE_SENDER.search(facts.name):
        return "named_payer_company_form"
    if facts.public_or_healthcare:
        return "public_or_healthcare_payer"
    return None


def _q6_eligible(record: TransactionClassification, text: str, facts: CreditFacts) -> bool:
    """§8.6: an unverified posted credit with an electronic-payment form and a payer region, which the channel gate
    leaves open, no transfer wording in its entry fields, no wire, no registry, payout or factoring claim, no hold,
    and no numbered company."""
    classifier = _classifier()
    return (
        facts.electronic and bool(facts.region) and facts.channel == "ach_eft"
        and classifier.channel_gate(text) is None
        and not classifier._TRANSFER_WORDING.search(facts.entry)
        and not facts.wire_n1 and not facts.claimed and facts.hold is None and not facts.numbered
    )


def _tier_reason(record: TransactionClassification, text: str, facts: CreditFacts, round_repeat: bool) -> tuple[str, str]:
    """§8.10: the tier and reason of an unverified posted credit, in order."""
    classifier = _classifier()
    if record.revenue_match_method == "direction_conflict":
        return "excluded_pending_review", "direction_conflict"
    if facts.hold is not None:
        return "excluded_pending_review", facts.hold
    if facts.channel == "wire" and not facts.claimed:
        if not facts.region:
            return "excluded_pending_review", "wire_no_sender"
        if facts.refused_word:
            return "counted_flagged", "named_payer_purpose_refused"
        return "counted_flagged", "wire_named_sender"
    if facts.transfer_no_counterparty and not facts.claimed:
        return "excluded_pending_review", "transfer_no_counterparty"
    if facts.account_designation and not facts.claimed:
        return "excluded_pending_review", "transfer_account_designation"
    if facts.channel == "check":
        return "counted_flagged", "check_deposit"
    if facts.channel == "cash_branch_atm":
        return "counted_flagged", "no_payer_printed"
    if facts.channel == "person_to_person" and not facts.claimed:
        return ("excluded_pending_review", "p2p_round_repeat") if round_repeat else ("counted_flagged", "p2p")
    if record.revenue_match_method in _REGISTRY_METHODS:
        return "counted_flagged", "platform_unconfirmed"
    if record.classification == "factoring":
        return "counted_flagged", "factoring_payout"
    known = match_known_payee(text)
    if known is not None and known.entity in PAYOUT_CREDIT_ENTITIES:
        return "counted_flagged", "payout_credit_entity"
    if facts.numbered:
        return "counted_flagged", "numbered_company_payer"
    if facts.region and facts.refused_word:
        return "counted_flagged", "named_payer_purpose_refused"
    if facts.region and facts.electronic:
        return "counted_flagged", "named_payer_one_off"
    if facts.region and not classifier._is_bare_row(text):
        return "counted_flagged", "named_payer_unlabelled"
    return "counted_flagged", "no_payer_printed"


def _with_tier(record: TransactionClassification, tier: str, reason: str | None) -> TransactionClassification:
    """A record with its 5.6 tier, initial tier, reason and contribution flags. The review flag is set for a held
    row only; a counted row is reviewable, not required."""
    return replace(
        record,
        revenue_tier=tier,
        revenue_initial_tier=tier,
        revenue_tier_reason=reason,
        revenue_review_required=tier == "excluded_pending_review",
        **revenue_contribution_flags(record.revenue_classification, tier),
    )


def _verify(record: TransactionClassification, method: str, reason: str, confidence: float) -> TransactionClassification:
    classifier = _classifier()
    return classifier._replace_revenue_state(
        record,
        "verified_revenue",
        match_method=method,
        matched_rule=f"verified_{method}",
        confidence_score=confidence,
        reason=reason,
        context_signals=(*record.revenue_context_signals, method),
    )


def apply_true_revenue_pass(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """Statement pass 7 (§6.2): payer facts, the Q5 and Q6 verifications, then the tiers."""
    classifier = _classifier()
    updated = list(records)
    credits = [
        index for index, record in enumerate(records)
        if index not in duplicate_indexes and record.amount > 0 and record.is_posted
        and record.revenue_classification is not None
    ]
    lender_words, debit_words = _debit_words(records, duplicate_indexes)
    texts = {index: classifier.revenue_text(updated[index].normalized_description) for index in credits}
    facts = {
        index: credit_facts(updated[index], texts[index], lender_words=lender_words, debit_words=debit_words)
        for index in credits
    }
    # §5.2: repeats count a verified credit, or an unverified one no hold names; never a held or conflicting one.
    counting = Counter()
    consumer_only: dict[tuple[str, tuple[str, ...]], bool] = {}
    for index in credits:
        record, fact = updated[index], facts[index]
        if not fact.key or record.revenue_classification == "non_revenue":
            continue
        if record.revenue_match_method == "direction_conflict" or (
            record.revenue_classification == "unverified_deposit" and fact.hold is not None
        ):
            continue
        group = (fact.channel, fact.key)
        counting[group] += 1
        consumer_only[group] = consumer_only.get(group, True) and fact.consumer_entry
    # §8.4: a sender with two or more round sums on the rails or through named transfers.
    round_sums = Counter(
        facts[index].key for index in credits
        if facts[index].channel == "person_to_person" and facts[index].round_sum and facts[index].key
    )
    for index in credits:
        record, fact, text = updated[index], facts[index], texts[index]
        if record.revenue_classification != "unverified_deposit":
            continue
        group = (fact.channel, fact.key)
        repeats = counting[group] if fact.key else 0
        if fact.channel == "wire" and _wire_verifies(record, text, fact, repeats):
            updated[index] = _verify(record, "repeat_wire_sender",
                                     "The same company wires the business twice or more in the statement.", 0.85)
            continue
        if _q6_eligible(record, text, fact) and not fact.refused_word:
            method = _q6_method(fact, repeats, consumer_only.get(group, True))
            if method is not None:
                updated[index] = _verify(record, method, _Q6_REASONS[method], 0.85)
    for index in credits:
        record, fact = updated[index], facts[index]
        tier = _TIER_OF_STATE.get(record.revenue_classification)
        if tier is not None:
            updated[index] = _with_tier(record, tier, None)
            continue
        round_repeat = fact.round_sum and bool(fact.key) and round_sums[fact.key] >= 2
        tier, reason = _tier_reason(record, texts[index], fact, round_repeat)
        updated[index] = _with_tier(record, tier, reason)
    return updated


_Q6_REASONS = {
    "named_payer_repeats": "The same named payer pays the business twice or more in the statement.",
    "named_payer_company_form": "A named company pays the business by ACH or EFT.",
    "public_or_healthcare_payer": "A government or healthcare payer pays the business.",
}


def registry_financing_root(record: TransactionClassification, text: str) -> bool:
    """G2 (§14.3, review I1) on a registry row: a registry financing word (registry_financing), or a financing root
    glued inside a word of the row before its receiver fields, the holder's own words and §7.0's FUNDING settlements
    aside. A root inside a place name (a city whose name holds LEND) is not one: the registry's reads are whole
    words."""
    classifier = _classifier()
    if registry_financing(record, text):
        return True
    own = _own_words(record, text)
    for word in classifier._before_receiver(text).split():
        if _own_word(word, own):
            continue
        if word in {"FUNDING", "FUNDED"} and record.revenue_canonical_entity in classifier._FUNDING_SETTLEMENT_ENTITIES:
            continue
        if _GLUED_FINANCING_ROOT.search(word):
            return True
    return False


def guard_facts(record: TransactionClassification, text: str) -> dict:
    """The census's §14.3 facts of one posted credit (tools/revenue_census.py), read with these readers."""
    classifier = _classifier()
    region = classifier.payer_region(text)
    entry = classifier.entry_fields(text)
    row = classifier._before_receiver(text)
    known = match_known_payee(text)
    return {
        "financing_root": financing_named(text, region, entry, record.account_name),
        "registry_root": registry_financing_root(record, text),
        "registry_financing": registry_financing(record, text),
        "pay_or_personal": bool(_PAY_WORDS.search(row) or _PERSONAL_INCOME.search(row)),
        "transfer_no_counterparty": (
            classifier._TRANSFER_WORDING.search(row) is not None
            and not classifier._CONSUMER_P2P_RAIL.search(row) and not classifier._PUSH_RAIL.search(row)
            and not _transfer_counterparty_words(text)
        ),
        "known_financing": known is not None and known.state in FINANCING_STATES,
        "payout_or_factoring": known is not None and (known.entity in PAYOUT_CREDIT_ENTITIES or known.state == "factoring"),
        "numbered_region": classifier._NUMBERED_COMPANY_REGION.search(region) is not None,
        "customer_descriptor": classifier._matches_any(text, classifier._CUSTOMER_INVOICE_DESCRIPTORS),
        "pooled_while_vetoed": (
            record.revenue_match_method in {"recurring_operating_source", "operating_source_related_activity"}
            and classifier._recurrence_vetoed(record, text)
        ),
        # §14.2: a named payer whose channel is not printed, and whose name alone Q6 (b) or (c) would verify.
        "q6_shape": (
            classifier.company_form(classifier.payer_name(region))
            or government_payer(public_region(text)) or healthcare_payer(region)
        ),
    }
```

In `analysis/transaction_classifier.py` (line 39), replace:

```python
from .payee_matcher import PayeeMatch, match_debt_relief_payee, match_known_payee, registry_match
```

with:

```python
from .payee_matcher import PayeeMatch, match_debt_relief_payee, match_known_payee, registry_match
# 5.6: the true-revenue pass reads this module's readers at call time, so it imports nothing from here at load.
from .true_revenue import apply_true_revenue_pass
```

In `analysis/transaction_classifier.py` (line 4685), replace:

```python
    records = _apply_payer_remittance_counter_debit_guard(records, set(duplicate_of))
```

with:

```python
    records = _apply_payer_remittance_counter_debit_guard(records, set(duplicate_of))
    # 5.6 (§6.2 pass 7): payer facts, the Q5 and Q6 verifications, then the tiers.
    records = apply_true_revenue_pass(records, set(duplicate_of))
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_true_revenue_tiers.py tests/test_revenue_census.py -q -p no:cacheprovider`

Expected: PASS: `133 passed`.

- [ ] **Step 5: Re-pin the assertions this task moves (pin ledger row 19).**

In `tests/test_revenue_classification.py` (lines 286-287), replace:

```python
    assert metrics["revenue_reconciles"]
    assert [
```

with:

```python
    assert metrics["revenue_reconciles"]
    # 5.6 (§5.4): only a held credit requires review; the mobile deposit is a counted check deposit.
    assert [
```

In `tests/test_revenue_classification.py` (lines 290-292), replace:

```python
        if record.get("revenue_review_required")
    ] == ["transaction:2"]
    assert len(analysis["detection"]["unverified_deposit_evidence"]) == 1
```

with:

```python
        if record.get("revenue_review_required")
    ] == []
    assert len(analysis["detection"]["unverified_deposit_evidence"]) == 1
```

- [ ] **Step 6: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-CLASSIFIER: `755 passed, 2 deselected`
  - SEL-REVENUE: `659 passed`

- [ ] **Step 7: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/transaction_classifier.py analysis/true_revenue.py tests/test_revenue_census.py tests/test_revenue_classification.py tests/test_true_revenue_tiers.py
git commit -m "revenue: the true-revenue pass, its holds and the Q5 and Q6 verifications (5.6)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S4.3: Q7: an auto lender's dealer funding

**Files:**
- Modify: `analysis/true_revenue.py:4-6, 49-50, 261, 443-444, 598, 605-606, 703`
- Modify: `analysis/transaction_classifier.py:41, 1996, 3265-3266, 4688`
- Modify (pins): `tests/test_true_revenue_tiers.py:2, 172-174`

**Depends on:** S4.2.

**Interfaces:**
- Consumes: S4.2 (`_dealer_funding_payer`, `DEALER_FUNDING_WORDS`, `_verify`, the pass), `match_known_payee`, `POTENTIAL_LENDER_ALIASES`, `_insurance_registry_match`.
- Produces:
  - `dealer_funding(text: str) -> str | None` (`'listed'`, `'credit_union'` or None)
  - `CREDIT_UNION_DEALER_MIN_CREDITS = 2`
  - revenue methods `auto_lender_dealer_funding` and `credit_union_vehicle_purchase`
  - the guard facts `q7_payer_ok`, `q7_listed`, `q7_credit_union`, `q7_veto_word` (G12)

**Why:** Spec §6.1 step 4 and §8.7 (Q7): a listed auto lender (a `vehicle_financing` registry entity or a `DEALER_FUNDING_PAYERS` lender, read on the originator segment) that prints a dealer-funding word pays the dealer's revenue: `verified_revenue`, method `auto_lender_dealer_funding`, source type `auto_dealer_funding`, never financing proceeds (it leaves `lender_credits`). A credit union's `VHCL PURCH` entry is verified by the pass when the statement holds two or more; one alone is held. Never on a row that names a lender outside vehicle financing, a potential lender or an insurer, that prints a loan, proceeds, advance or refund word, or that the channel gate closes.

- [ ] **Step 1: Write the failing tests.**

In `tests/test_true_revenue_tiers.py` (line 2), replace:

```python
the channel tiers, and the Q5 and Q6 verifications with their guards.
```

with:

```python
the channel tiers, and the Q5, Q6 and Q7 verifications with their guards.
```

In `tests/test_true_revenue_tiers.py` (lines 172-174), replace:

```python


def test_the_four_tiers_add_up_to_the_posted_credits():
```

with:

```python


def test_q7_dealer_funding_from_a_listed_auto_lender():
    record = _one("WESTLAKE FINANCI DES:PAYABLES ID:EFT1234567 INDN:SAMPLE MOTORS LLC CO ID:1 CCD", holder="SAMPLE MOTORS LLC")
    assert (record.revenue_match_method, record.revenue_source_type) == (
        "auto_lender_dealer_funding", "auto_dealer_funding")
    assert not record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize("text", [
    "KAPITUS DES:CONTRACT FUNDING ID:1",
    "ONDECK CAPITAL DES:DEAL FUND ID:1",
    "GEICO DES:VEHICLE PURCHASE ID:1",
])
def test_q7_never_fires_on_a_lender_or_insurer_outside_vehicle_financing(text):
    assert _one(text).revenue_classification == "non_revenue"


def test_q7_refuses_a_loan_word_and_the_credit_union_arm_needs_two_credits():
    loan = _one("SUNCOAST CREDIT UNION DES:VHCL PURCH LOAN PROCEEDS ID:1")
    assert loan.revenue_classification != "verified_revenue"
    union = "Orig CO Name:Sample CU Orig ID:1 Desc Date: CO Entry Descr:Vhcl Purchsec:CCD Trace#:{n}"
    two = _records([(union.format(n=1), 18000.0), (union.format(n=2), 21000.0)], holder="SAMPLE MOTORS LLC")
    assert {record.revenue_match_method for record in two} == {"auto_lender_dealer_funding"}
    lone = _records([(union.format(n=1), 18000.0)], holder="SAMPLE MOTORS LLC")
    assert _tier(lone[0]) == ("excluded_pending_review", "financing_named_payer")


def test_the_four_tiers_add_up_to_the_posted_credits():
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_true_revenue_tiers.py -q -p no:cacheprovider`

Expected: FAIL: `2 failed, 92 passed`, the first with `AssertionError: assert ('unidentifie...credit', None) == ('auto_lender...aler_funding')`.

- [ ] **Step 3: Implement.**

In `analysis/true_revenue.py` (lines 4-6), replace:

```python
credit's payer facts (channel family, payer region, payer name and key, entry fields, the holds of §8.1), then runs
the Q5 and Q6 verifications (§8.5, §8.6), which refuse any row a hold names, and last gives every posted credit its
tier and reason (§5.3), in the order of §8.10.
```

with:

```python
credit's payer facts (channel family, payer region, payer name and key, entry fields, the holds of §8.1), then runs
Q7's credit-union arm (§8.7) and the Q5 and Q6 verifications (§8.5, §8.6), which refuse any row a hold names, and last
gives every posted credit its tier and reason (§5.3), in the order of §8.10.
```

In `analysis/true_revenue.py` (lines 49-50), replace:

```python
    r"|\bDLR PMT\b|\bAUTODLRPMT\b|\bCONTRACT FUND\w*|\bVADMIN FEE\b"
)
```

with:

```python
    r"|\bDLR PMT\b|\bAUTODLRPMT\b|\bCONTRACT FUND\w*|\bVADMIN FEE\b"
)
_DEALER_PAYABLES_WORDS = re.compile(r"\bPAYABLES\b|\bTRADE PAY\w*|\bACCT FUND\w*")
_DEALER_FUNDING_VETO = re.compile(
    r"\bLOANS?\b|\bPROCEEDS\b|\bADVANCES?\b|\bADV\b|\bMCA\b|\bCASH ADV\w*"
    r"|\b(?:REFUND|RFND|REFND|RFD|RETURN|RTN|REVERSAL|RVSL|CHARGEBACK|CHBK)\b"
)
_CREDIT_UNION_PAYER = re.compile(r"\bCU\b|\bCREDIT UNION\b|\bFCU\b|\bCU DIRECT\b|\bCUDL\b")
_VEHICLE_PURCHASE_ENTRY = re.compile(r"\bVHCL PURCH(?:ASE)?\b")
#: §8.7: a statement's credit-union dealer funding needs this many credits.
CREDIT_UNION_DEALER_MIN_CREDITS = 2
```

In `analysis/true_revenue.py`, after the end of `_dealer_funding_payer` (line 261), insert:

```python
def dealer_funding(text: str) -> str | None:
    """§6.1 step 4 (Q7): 'listed' when a listed auto lender pays dealer-funding words, 'credit_union' when a credit
    union (or CU Direct) prints the VHCL PURCH entry (the statement pass decides it), or None. Never on a row that
    names a lender outside vehicle financing, a potential lender or an insurer, that prints a loan, proceeds,
    advance or refund word, or that the channel gate closes."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    if _DEALER_FUNDING_VETO.search(row) or classifier.channel_gate(text) == "closed":
        return None
    known = match_known_payee(text)
    if known is not None and known.state in FINANCING_STATES and known.state != "vehicle_financing":
        return None
    if registry_match(text, classifier.POTENTIAL_LENDER_ALIASES) is not None:
        return None
    if classifier._insurance_registry_match(text) is not None:
        return None
    if _dealer_funding_payer(text) is not None and (
        DEALER_FUNDING_WORDS.search(row) or _DEALER_PAYABLES_WORDS.search(row)
    ):
        return "listed"
    region = classifier.payer_region(text)
    if _CREDIT_UNION_PAYER.search(region) and _VEHICLE_PURCHASE_ENTRY.search(classifier.entry_fields(text) or row):
        return "credit_union"
    return None
```

In `analysis/true_revenue.py` (lines 443-444), replace:

```python
        or _dealer_funding_payer(text) is not None
        or DEALER_FUNDING_WORDS.search(row) is not None
```

with:

```python
        or (_dealer_funding_payer(text) is not None and record.revenue_match_method != "auto_lender_dealer_funding")
        or (DEALER_FUNDING_WORDS.search(row) and record.revenue_match_method != "auto_lender_dealer_funding")
        or record.revenue_match_method == "credit_union_vehicle_purchase"
```

In `analysis/true_revenue.py` (line 598), replace:

```python
    """Statement pass 7 (§6.2): payer facts, the Q5 and Q6 verifications, then the tiers."""
```

with:

```python
    """Statement pass 7 (§6.2): payer facts, Q7's credit-union arm, the Q5 and Q6 verifications, then the tiers."""
```

In `analysis/true_revenue.py` (lines 605-606), replace:

```python
    ]
    lender_words, debit_words = _debit_words(records, duplicate_indexes)
```

with:

```python
    ]
    # §8.7: the credit-union arm needs two or more such credits in the statement.
    union_rows = [index for index in credits if records[index].revenue_match_method == "credit_union_vehicle_purchase"]
    if len(union_rows) >= CREDIT_UNION_DEALER_MIN_CREDITS:
        for index in union_rows:
            updated[index] = replace(
                _verify(updated[index], "auto_lender_dealer_funding",
                        "A credit union funds the dealer's indirect auto loans (VHCL PURCH, two or more).", 0.90),
                revenue_source_type="auto_dealer_funding",
            )
    lender_words, debit_words = _debit_words(records, duplicate_indexes)
```

In `analysis/true_revenue.py` (line 703), replace:

```python
        "customer_descriptor": classifier._matches_any(text, classifier._CUSTOMER_INVOICE_DESCRIPTORS),
```

with:

```python
        "customer_descriptor": classifier._matches_any(text, classifier._CUSTOMER_INVOICE_DESCRIPTORS),
        "q7_payer_ok": _dealer_funding_payer(text) is not None or bool(_CREDIT_UNION_PAYER.search(region)),
        "q7_listed": _dealer_funding_payer(text) is not None,
        "q7_credit_union": bool(_CREDIT_UNION_PAYER.search(region))
        and bool(_VEHICLE_PURCHASE_ENTRY.search(entry or row)),
        "q7_veto_word": bool(_DEALER_FUNDING_VETO.search(row)),
```

In `analysis/transaction_classifier.py` (line 41), replace:

```python
from .true_revenue import apply_true_revenue_pass
```

with:

```python
from .true_revenue import apply_true_revenue_pass, dealer_funding
```

In `analysis/transaction_classifier.py` (line 4688), replace:

```python
    # 5.6 (§6.2 pass 7): payer facts, the Q5 and Q6 verifications, then the tiers.
```

with:

```python
    # 5.6 (§6.2 pass 7): payer facts, Q7's credit-union arm, the Q5 and Q6 verifications, then the tiers.
```

In `analysis/transaction_classifier.py` (line 1996), replace:

```python
    # §7.7: the lookups below read a glued HCCLAIMPMT split from the name before it.
```

with:

```python
    # §6.1 step 4 (Q7, 5.6): a dealer's funding from a listed auto lender is revenue; a credit union's VHCL PURCH
    # entry waits for the statement pass, which verifies two or more of them.
    dealer = dealer_funding(text)
    if dealer == "listed":
        return _RevenueDecision(
            "verified_revenue",
            None,
            "auto_lender_dealer_funding",
            None,
            "verified_auto_lender_dealer_funding",
            0.90,
            "A listed auto lender pays the dealer's vehicle funding: the dealer's revenue.",
            source_type="auto_dealer_funding",
            context_signals=("credit_direction", "auto_lender_dealer_funding"),
        )
    if dealer == "credit_union":
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "credit_union_vehicle_purchase",
            None,
            "credit_union_vehicle_purchase_requires_statement_count",
            0.60,
            "A credit union prints the VHCL PURCH entry; two or more in the statement are dealer funding.",
            source_type="auto_dealer_funding",
            context_signals=("credit_direction", "credit_union_vehicle_purchase"),
        )
    # §7.7: the lookups below read a glued HCCLAIMPMT split from the name before it.
```

In `analysis/transaction_classifier.py` (lines 3265-3266), replace:

```python
        if known_payee.state in FINANCING_STATES and known_payee.entity not in PAYOUT_CREDIT_ENTITIES:
            return _financing_proceeds_credit_record(common, amount, known_payee)
```

with:

```python
        if (
            known_payee.state in FINANCING_STATES
            and known_payee.entity not in PAYOUT_CREDIT_ENTITIES
            # 5.6 (Q7): a listed auto lender's dealer funding is revenue, never financing proceeds.
            and dealer_funding(revenue_text(text)) != "listed"
        ):
            return _financing_proceeds_credit_record(common, amount, known_payee)
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_true_revenue_tiers.py -q -p no:cacheprovider`

Expected: PASS: `94 passed`.

- [ ] **Step 5: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-CLASSIFIER: `755 passed, 2 deselected`
  - SEL-REVENUE: `664 passed`

- [ ] **Step 6: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/transaction_classifier.py analysis/true_revenue.py tests/test_true_revenue_tiers.py
git commit -m "revenue: Q7, an auto lender's dealer funding is the dealer's revenue (5.6)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S4.4: Metrics, detection, serialization and the serialized views

**Files:**
- Modify: `analysis/revenue.py:62-68, 138-152, 157-160, 175-191, 205-215, 217-223, 225-235, 246-251, 259-260, 312-317, 319-333, 335-338`
- Modify: `analysis/metrics.py:28-32, 107-111, 314-319, 331-334, 377-380, 433-443, 446-452, 454-458, 465-469, 581-584`
- Modify: `analysis/detect.py:91-95, 314-317, 334-338`
- Modify: `analysis/serialization.py:202-207`
- Modify (pins): `tests/test_true_revenue_payload.py:4-8, 46-47`
- Modify (pins): `tests/test_revenue_classification.py:250-252, 664-666`
- Modify (pins): `tests/test_analysis.py:3361-3362`
- Modify (pins): `tests/test_webapp_reanalysis.py:292-293`

**Depends on:** S4.3.

**Interfaces:**
- Consumes: S4.1 to S4.3.
- Produces:
  - `TIER_METRIC_KEYS`, `TIER_DETECTION_KEYS`, `REVENUE_REVIEW_HELD_SHARE = 10`, `WITHHOLDING_DENOMINATOR_MODES` with `true_revenue`
  - `revenue_review_gate(*, direction_conflict: bool, held_total: float, posted_total: float, reconciles: bool) -> bool`
  - `Metrics.true_revenue_total`, `.true_revenue_count`, `.counted_flagged_total`, `.counted_flagged_count`, `.excluded_pending_review_total`, `.excluded_pending_review_count`, `.counted_flagged_by_reason`, `.excluded_pending_review_by_reason` (`{reason: {"count": int, "total": float}}`), `.revenue_review_items`, `.counted_flagged_evidence`, `.excluded_pending_review_evidence`
  - the same keys in a serialized account's `metrics` and `detection`
  - the refusals `"every posted credit carries a revenue tier, or none does"`, `"every posted credit's revenue state must agree with its tier"`, `"a credit a rule verified can only be marked non-revenue"`

**Why:** Spec §5.1, §9.1, §10.7 (the server's review rules), §11, §12, T6 to T10: the metrics carry True revenue and its counted and held parts with their by-reason figures and evidence, check that every posted credit's tier agrees with its state and that the four tiers add up, repoint `true_revenue` and `true_revenue_evidence`, and set `revenue_review_required` by T7's gate; the True-revenue withholding mode is selectable; the serialized rebuild does the same on a payload, refuses a payload tiered only in part, and takes the tier-less path for one analysed before 5.6; the review writer lets an analyst reject a rule-verified credit, refuses its confirm ("a credit a rule verified can only be marked non-revenue"), and moves the tier with the state.

- [ ] **Step 1: Write the failing tests.**

In `tests/test_true_revenue_payload.py` (lines 4-8), replace:

```python
from __future__ import annotations

from analysis.revenue import REVENUE_TIER_REASONS, revenue_contribution_flags, tier_of_state
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction


```

with:

```python
from __future__ import annotations

import copy
from dataclasses import asdict

import pytest

from analysis.metrics import compute_metrics
from analysis.revenue import (
    REVENUE_REVIEW_HELD_SHARE,
    REVENUE_TIER_REASONS,
    apply_serialized_revenue_review,
    rebuild_serialized_revenue_views,
    record_serialized_revenue_review,
    revenue_contribution_flags,
    revenue_review_gate,
    tier_of_state,
)
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction

ROWS = [
    ("2054-03-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0),     # verified (Q6 company form)
    ("2054-03-03", "MOBILE DEPOSIT", 300.0),                            # counted: check deposit
    ("2054-03-04", "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0),     # held: financing-named payer
    ("2054-03-05", "INTERNAL TRANSFER FROM SAVINGS", 100.0),            # non-revenue
    ("2054-03-06", "FABRIKAM SUPPLY DES:DEBIT ID:1", -50.0),
]


def _statement(rows=ROWS):
    return Statement(account_name="CONTOSO BAKERY LLC", currency="USD", transactions=[
        Transaction(date=day, description=text, amount=amount, direction="credit" if amount > 0 else "debit")
        for day, text, amount in rows
    ])


def _payload(rows=ROWS) -> dict:
    statement = _statement(rows)
    records = classify_statement_transactions(statement)
    return rebuild_serialized_revenue_views({
        "statement": {"currency": "USD", "transactions": [
            {**transaction.model_dump(), "classification": asdict(record)}
            for transaction, record in zip(statement.transactions, records)
        ]},
        "metrics": {}, "detection": {},
    })


```

In `tests/test_true_revenue_payload.py` (lines 46-47), replace:

```python
    assert [record.revenue_tier for record in records] == ["verified", "non_revenue"]
    assert not records[1].contributes_to_true_revenue
```

with:

```python
    assert [record.revenue_tier for record in records] == ["verified", "non_revenue"]
    assert not records[1].contributes_to_true_revenue

def test_the_metrics_carry_the_four_tiers_and_true_revenue():
    statement = _statement()
    metrics = compute_metrics(statement, classifications=classify_statement_transactions(statement))
    assert (metrics.verified_revenue_total, metrics.counted_flagged_total, metrics.excluded_pending_review_total,
            metrics.non_revenue_total) == (700.0, 300.0, 900.0, 100.0)
    assert metrics.true_revenue_total == metrics.true_revenue == 1000.0
    assert metrics.true_revenue_count == 2
    assert metrics.maximum_revenue == 1900.0
    assert metrics.counted_flagged_by_reason == {"check_deposit": {"count": 1, "total": 300.0}}
    assert metrics.excluded_pending_review_by_reason == {"financing_named_payer": {"count": 1, "total": 900.0}}
    assert metrics.revenue_review_items == 1
    assert metrics.revenue_reconciles
    assert [record.revenue_tier for record in metrics.true_revenue_evidence] == ["verified", "counted_flagged"]


def test_a_record_whose_tier_disagrees_with_its_state_is_refused():
    statement = _statement()
    records = classify_statement_transactions(statement)
    from dataclasses import replace
    records[1] = replace(records[1], revenue_tier="verified")
    with pytest.raises(ValueError, match="agree with its tier"):
        compute_metrics(statement, classifications=records)


@pytest.mark.parametrize(("held", "posted", "gated"), [
    (99.99, 1000.0, False),      # just under ten percent, in cents
    (100.0, 1000.0, True),       # exactly ten percent
    (0.0, 0.0, False),           # nothing posted, nothing held
])
def test_the_gate_compares_the_held_share_in_integer_cents(held, posted, gated):
    assert REVENUE_REVIEW_HELD_SHARE == 10
    assert revenue_review_gate(direction_conflict=False, held_total=held, posted_total=posted, reconciles=True) is gated
    assert revenue_review_gate(direction_conflict=True, held_total=0.0, posted_total=posted, reconciles=True)
    assert revenue_review_gate(direction_conflict=False, held_total=0.0, posted_total=posted, reconciles=False)


def test_the_serialized_views_carry_the_tiers_and_repoint_true_revenue():
    payload = _payload()
    metrics, detection = payload["metrics"], payload["detection"]
    assert (metrics["true_revenue_total"], metrics["counted_flagged_total"], metrics["excluded_pending_review_total"]) == (
        1000.0, 300.0, 900.0)
    assert metrics["true_revenue"] == 1000.0 and metrics["confirmed_true_revenue_total"] == 700.0
    assert metrics["revenue_review_required"]            # 900 of 2000 posted is held
    assert metrics["revenue_review_items"] == 1
    assert len(detection["true_revenue_evidence"]) == 2
    assert len(detection["counted_flagged_evidence"]) == len(detection["excluded_pending_review_evidence"]) == 1
    assert [record["source_location"] for record in detection["manual_review"]
            if record.get("revenue_review_required")] == ["transaction:3"]


def test_confirm_reject_and_reset_move_the_tier():
    payload = _payload()
    confirmed = apply_serialized_revenue_review(copy.deepcopy(payload), source_location="transaction:3",
                                                decision="confirm")
    record = confirmed["statement"]["transactions"][2]["classification"]
    assert (record["revenue_classification"], record["revenue_tier"], record["revenue_tier_reason"]) == (
        "verified_revenue", "verified", "financing_named_payer")
    assert confirmed["metrics"]["true_revenue_total"] == 1900.0
    rejected = apply_serialized_revenue_review(copy.deepcopy(payload), source_location="transaction:2",
                                               decision="reject")
    assert rejected["statement"]["transactions"][1]["classification"]["revenue_tier"] == "non_revenue"
    reset = apply_serialized_revenue_review(rejected, source_location="transaction:2", decision="reset")
    reset_record = reset["statement"]["transactions"][1]["classification"]
    assert (reset_record["revenue_tier"], reset_record["revenue_review_status"]) == ("counted_flagged", "pending")
    assert not reset_record["revenue_review_required"]


def test_a_rule_verified_credit_can_be_rejected_but_not_confirmed():
    payload = _payload()
    with pytest.raises(ValueError, match="a credit a rule verified can only be marked non-revenue"):
        record_serialized_revenue_review(copy.deepcopy(payload), source_location="transaction:1", decision="confirm")
    rejected = apply_serialized_revenue_review(payload, source_location="transaction:1", decision="reject")
    record = rejected["statement"]["transactions"][0]["classification"]
    assert (record["revenue_classification"], record["revenue_tier"]) == ("non_revenue", "non_revenue")
    reset = apply_serialized_revenue_review(rejected, source_location="transaction:1", decision="reset")
    record = reset["statement"]["transactions"][0]["classification"]
    assert (record["revenue_tier"], record["revenue_review_status"]) == ("verified", "not_required")
    with pytest.raises(ValueError, match="only automatically unverified deposits"):
        record_serialized_revenue_review(reset, source_location="transaction:4", decision="reject")


def _untiered(payload: dict) -> dict:
    old = copy.deepcopy(payload)
    for transaction in old["statement"]["transactions"]:
        record = transaction["classification"]
        for key in ("revenue_tier", "revenue_initial_tier", "revenue_tier_reason"):
            record.pop(key, None)
    return old


def test_a_payload_analysed_before_5_6_takes_the_tier_less_path():
    old = rebuild_serialized_revenue_views(_untiered(_payload()))
    metrics = old["metrics"]
    assert metrics["true_revenue"] is None and metrics["true_revenue_evidence"] is None
    assert metrics["true_revenue_total"] is None and metrics["counted_flagged_by_reason"] is None
    assert metrics["verified_revenue_total"] == 700.0
    assert metrics["revenue_review_required"]                # a pending unverified deposit, today's rule
    assert all("contributes_to_true_revenue" not in transaction["classification"]
               for transaction in old["statement"]["transactions"] if transaction["amount"] > 0)
    # Its review follows today's rules: only an unverified deposit is reviewable, and no tier is written.
    confirmed = apply_serialized_revenue_review(old, source_location="transaction:2", decision="confirm")
    assert "revenue_tier" not in confirmed["statement"]["transactions"][1]["classification"]
    with pytest.raises(ValueError, match="only automatically unverified deposits"):
        record_serialized_revenue_review(old, source_location="transaction:1", decision="reject")


def test_a_payload_tiered_only_in_part_is_refused():
    mixed = _payload()
    mixed["statement"]["transactions"][1]["classification"].pop("revenue_tier")
    with pytest.raises(ValueError, match="carries a revenue tier, or none does"):
        rebuild_serialized_revenue_views(mixed)


def test_true_revenue_is_a_selectable_withholding_denominator_never_the_default():
    statement = _statement()
    records = classify_statement_transactions(statement)
    legacy = compute_metrics(statement, classifications=records)
    assert legacy.withholding_denominator_mode == "legacy_eligible_deposits"
    true = compute_metrics(statement, classifications=records, withholding_denominator_mode="true_revenue")
    assert (true.eligible_deposits, true.withholding_denominator_label) == (1000.0, "True revenue")
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_true_revenue_payload.py -q -p no:cacheprovider`

Expected: FAIL: `1 error`, the first with `ImportError: cannot import name 'REVENUE_REVIEW_HELD_SHARE' from 'analysis.revenue'`.

- [ ] **Step 3: Implement.**

In `analysis/revenue.py` (lines 62-68), replace:

```python
    "named_payer_unlabelled": ("counted_flagged", "Payer named, channel not printed"),
}
WITHHOLDING_DENOMINATOR_MODES = (
    "legacy_eligible_deposits",
    "verified_revenue",
)
LEGACY_REVENUE_STATE_MAP = {
```

with:

```python
    "named_payer_unlabelled": ("counted_flagged", "Payer named, channel not printed"),
}
#: 5.6 (§12): the tier figures a payload analysed before 5.6 cannot have. Its rebuild and its served copy
#: (analysis/revenue_view.py) set every one to None.
TIER_METRIC_KEYS = (
    "true_revenue", "true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
    "excluded_pending_review_total", "excluded_pending_review_count", "counted_flagged_by_reason",
    "excluded_pending_review_by_reason", "revenue_review_items", "true_revenue_evidence",
    "counted_flagged_evidence", "excluded_pending_review_evidence",
)
TIER_DETECTION_KEYS = ("true_revenue_evidence", "counted_flagged_evidence", "excluded_pending_review_evidence")
#: 5.6 (T7): a statement needs revenue review when its held credits are this share, in percent, or more of its
#: posted credits (non-revenue included), compared in integer cents.
REVENUE_REVIEW_HELD_SHARE = 10
WITHHOLDING_DENOMINATOR_MODES = (
    "legacy_eligible_deposits",
    "verified_revenue",
    # 5.6 (T8): True revenue is selectable, never the default.
    "true_revenue",
)
LEGACY_REVENUE_STATE_MAP = {
```

In `analysis/revenue.py` (lines 138-152), replace:

```python


def _rebuild_account_revenue_views(analysis: dict) -> dict:
    """One ACCOUNT's serialized revenue views, rebuilt in place."""
    statement = analysis["statement"]
    transactions = statement.get("transactions") or []
    evidence: dict[str, list[dict]] = {state: [] for state in REVENUE_STATES}
    totals: dict[str, float] = {state: 0.0 for state in REVENUE_STATES}
    counts: dict[str, int] = {state: 0 for state in REVENUE_STATES}
    posted_total = 0.0
    posted_count = 0
    serialized_records: list[dict] = []

    for transaction in transactions:
        amount = _number(transaction.get("amount"))
```

with:

```python


def _tiered(records: list[dict]) -> bool:
    """5.6 (§12): whether the posted credits carry tiers. A payload analysed before 5.6 carries none, and one whose
    records carry a tier only in part is refused, as a missing state is."""
    carrying = {isinstance(record.get("revenue_tier"), str) for record in records}
    if len(carrying) > 1:
        raise ValueError(_MIXED_TIERS)
    return carrying != {False}  # an account with no posted credit has nothing to be tier-less about


#: The fixed refusals of the rebuild and the review writer (webapp/app.py _DECLARED_REVIEW_REFUSALS lists them).
_MIXED_TIERS = "every posted credit carries a revenue tier, or none does"
_TIER_DISAGREES = "every posted credit's revenue state must agree with its tier"
_ALREADY_VERIFIED = "a credit a rule verified can only be marked non-revenue"


def _rebuild_account_revenue_views(analysis: dict) -> dict:
    """One ACCOUNT's serialized revenue views, rebuilt in place. A 5.6 payload is rebuilt on its four tiers; a payload
    analysed before 5.6 takes the tier-less path (§12): today's three states, no tier totals, no agreement check, and
    no True revenue (its `true_revenue` and `true_revenue_evidence` are None and no row carries
    `contributes_to_true_revenue`)."""
    statement = analysis["statement"]
    transactions = statement.get("transactions") or []
    evidence: dict[str, list[dict]] = {state: [] for state in REVENUE_STATES}
    tier_evidence: dict[str, list[dict]] = {tier: [] for tier in REVENUE_TIERS}
    totals: dict[str, float] = {state: 0.0 for state in REVENUE_STATES}
    counts: dict[str, int] = {state: 0 for state in REVENUE_STATES}
    tier_totals: dict[str, float] = {tier: 0.0 for tier in REVENUE_TIERS}
    tier_counts: dict[str, int] = {tier: 0 for tier in REVENUE_TIERS}
    by_reason: dict[str, dict[str, list]] = {"counted_flagged": {}, "excluded_pending_review": {}}
    posted_total = 0.0
    posted_count = 0
    direction_conflict = False
    serialized_records: list[dict] = []

    posted_records = []
    for transaction in transactions:
        amount = _number(transaction.get("amount"))
```

In `analysis/revenue.py` (lines 157-160), replace:

```python
                    "every posted credit must have an authoritative classification record"
                )
            continue
        if amount <= 0 or record.get("is_posted") is False:
```

with:

```python
                    "every posted credit must have an authoritative classification record"
                )
            continue
        if amount > 0 and record.get("is_posted") is not False:
            posted_records.append(record)
    tiered = _tiered(posted_records)

    for transaction in transactions:
        amount = _number(transaction.get("amount"))
        record = transaction.get("classification")
        if not isinstance(record, dict):
            continue
        if amount <= 0 or record.get("is_posted") is False:
```

In `analysis/revenue.py` (lines 175-191), replace:

```python
            initial_state,
        )
        flags = revenue_contribution_flags(state, tier_of_state(state))
        record.update(flags)
        serialized_records.append(deepcopy(record))
        totals[state] += amount
        counts[state] += 1
        evidence[state].append(deepcopy(record))

    posted_total = round(posted_total, 2)
    for state in REVENUE_STATES:
        totals[state] = round(totals[state], 2)
    classified_total = round(sum(totals.values()), 2)
    classified_count = sum(counts.values())
    delta = round(classified_total - posted_total, 2)

    metrics = analysis.setdefault("metrics", {})
```

with:

```python
            initial_state,
        )
        tier = record.get("revenue_tier") if tiered else None
        if tiered and STATE_OF_TIER.get(tier) != state:
            raise ValueError(_TIER_DISAGREES)
        record.update(revenue_contribution_flags(state, tier))
        if not tiered:
            record.pop("contributes_to_true_revenue", None)
        if record.get("revenue_match_method") == "direction_conflict":
            direction_conflict = True
        serialized_records.append(deepcopy(record))
        totals[state] += amount
        counts[state] += 1
        evidence[state].append(deepcopy(record))
        if tiered:
            tier_totals[tier] += amount
            tier_counts[tier] += 1
            tier_evidence[tier].append(deepcopy(record))
            if tier in by_reason:
                slot = by_reason[tier].setdefault(record.get("revenue_tier_reason") or "", [0, 0.0])
                slot[0] += 1
                slot[1] += amount

    posted_total = round(posted_total, 2)
    for state in REVENUE_STATES:
        totals[state] = round(totals[state], 2)
    for tier in REVENUE_TIERS:
        tier_totals[tier] = round(tier_totals[tier], 2)
    classified_total = round(sum(totals.values()), 2)
    classified_count = sum(counts.values())
    if tiered:
        classified_total = round(sum(tier_totals.values()), 2)
        classified_count = sum(tier_counts.values())
    delta = round(classified_total - posted_total, 2)
    reconciles = delta == 0.0 and classified_count == posted_count
    true_total = round(tier_totals["verified"] + tier_totals["counted_flagged"], 2) if tiered else None
    true_evidence = (
        [deepcopy(record) for record in serialized_records if record.get("contributes_to_true_revenue")]
        if tiered else None
    )

    metrics = analysis.setdefault("metrics", {})
```

In `analysis/revenue.py` (lines 205-215), replace:

```python
        "revenue_classified_count": classified_count,
        "revenue_reconciliation_delta": delta,
        "revenue_reconciles": delta == 0.0 and classified_count == posted_count,
        "revenue_review_required": counts["unverified_deposit"] > 0,
        "verified_revenue_evidence": evidence["verified_revenue"],
        "unverified_deposit_evidence": evidence["unverified_deposit"],
        "non_revenue_evidence": evidence["non_revenue"],
        # Deprecated aggregate aliases, all derived from canonical records.
        "true_revenue": totals["verified_revenue"],
        "confirmed_true_revenue": totals["verified_revenue"],
        "confirmed_true_revenue_total": totals["verified_revenue"],
```

with:

```python
        "revenue_classified_count": classified_count,
        "revenue_reconciliation_delta": delta,
        "revenue_reconciles": reconciles,
        "verified_revenue_evidence": evidence["verified_revenue"],
        "unverified_deposit_evidence": evidence["unverified_deposit"],
        "non_revenue_evidence": evidence["non_revenue"],
        # Deprecated aggregate aliases, all derived from canonical records. 5.6 (T9): `true_revenue` and
        # `true_revenue_evidence` are True revenue; None on a payload analysed before 5.6 (§12).
        "true_revenue": true_total,
        "confirmed_true_revenue": totals["verified_revenue"],
        "confirmed_true_revenue_total": totals["verified_revenue"],
```

In `analysis/revenue.py` (lines 217-223), replace:

```python
        "potential_revenue_total": totals["unverified_deposit"],
        "potential_revenue_count": counts["unverified_deposit"],
        "true_revenue_evidence": evidence["verified_revenue"],
        "potential_revenue_evidence": evidence["unverified_deposit"],
    })

    denominator_mode = normalize_withholding_denominator_mode(
```

with:

```python
        "potential_revenue_total": totals["unverified_deposit"],
        "potential_revenue_count": counts["unverified_deposit"],
        "true_revenue_evidence": true_evidence,
        "potential_revenue_evidence": evidence["unverified_deposit"],
    })
    if tiered:
        metrics.update({
            "true_revenue_total": true_total,
            "true_revenue_count": tier_counts["verified"] + tier_counts["counted_flagged"],
            "counted_flagged_total": tier_totals["counted_flagged"],
            "counted_flagged_count": tier_counts["counted_flagged"],
            "excluded_pending_review_total": tier_totals["excluded_pending_review"],
            "excluded_pending_review_count": tier_counts["excluded_pending_review"],
            "counted_flagged_by_reason": _by_reason(by_reason["counted_flagged"]),
            "excluded_pending_review_by_reason": _by_reason(by_reason["excluded_pending_review"]),
            "revenue_review_items": tier_counts["excluded_pending_review"],
            "revenue_review_required": revenue_review_gate(
                direction_conflict=direction_conflict,
                held_total=tier_totals["excluded_pending_review"],
                posted_total=posted_total,
                reconciles=reconciles,
            ),
            "counted_flagged_evidence": tier_evidence["counted_flagged"],
            "excluded_pending_review_evidence": tier_evidence["excluded_pending_review"],
        })
    else:
        # §12: no tier figure, and the gate is the rule the payload was analysed under.
        metrics.update({key: None for key in TIER_METRIC_KEYS})
        metrics["revenue_review_required"] = (
            counts["unverified_deposit"] > 0 or direction_conflict or not reconciles
        )

    denominator_mode = normalize_withholding_denominator_mode(
```

In `analysis/revenue.py` (lines 225-235), replace:

```python
    )
    metrics["withholding_denominator_mode"] = denominator_mode
    if denominator_mode == "verified_revenue":
        denominator = totals["verified_revenue"]
        metrics["eligible_deposits"] = denominator
        metrics["withholding_denominator"] = denominator
        metrics["potential_withholding_denominator"] = denominator
        metrics["withholding_denominator_label"] = "Verified revenue"
        metrics["eligible_deposit_definition"] = "verified classified revenue"
        numerator = _number(metrics.get("withholding_numerator"))
        potential_numerator = _number(metrics.get("potential_withholding_numerator"))
```

with:

```python
    )
    metrics["withholding_denominator_mode"] = denominator_mode
    denominator = None
    if denominator_mode == "verified_revenue":
        denominator = totals["verified_revenue"]
        metrics["withholding_denominator_label"] = "Verified revenue"
        metrics["eligible_deposit_definition"] = "verified classified revenue"
    elif denominator_mode == "true_revenue" and true_total is not None:
        denominator = true_total
        metrics["withholding_denominator_label"] = "True revenue"
        metrics["eligible_deposit_definition"] = "true revenue: verified plus counted credits"
    if denominator is not None:
        metrics["eligible_deposits"] = denominator
        metrics["withholding_denominator"] = denominator
        metrics["potential_withholding_denominator"] = denominator
        numerator = _number(metrics.get("withholding_numerator"))
        potential_numerator = _number(metrics.get("potential_withholding_numerator"))
```

In `analysis/revenue.py` (lines 246-251), replace:

```python
    detection["unverified_deposit_evidence"] = evidence["unverified_deposit"]
    detection["non_revenue_evidence"] = evidence["non_revenue"]
    detection["true_revenue_evidence"] = evidence["verified_revenue"]
    detection["potential_revenue_evidence"] = evidence["unverified_deposit"]
    detection["manual_review"] = [
        deepcopy(record)
```

with:

```python
    detection["unverified_deposit_evidence"] = evidence["unverified_deposit"]
    detection["non_revenue_evidence"] = evidence["non_revenue"]
    detection["true_revenue_evidence"] = deepcopy(true_evidence)
    detection["potential_revenue_evidence"] = evidence["unverified_deposit"]
    if tiered:
        detection["counted_flagged_evidence"] = tier_evidence["counted_flagged"]
        detection["excluded_pending_review_evidence"] = tier_evidence["excluded_pending_review"]
    else:
        detection.update({key: None for key in TIER_DETECTION_KEYS})
    detection["manual_review"] = [
        deepcopy(record)
```

In `analysis/revenue.py` (lines 259-260), replace:

```python
    ]
    return analysis


```

with:

```python
    ]
    return analysis


def _by_reason(slots: dict[str, list]) -> dict[str, dict[str, float | int]]:
    return {reason: {"count": count, "total": round(total, 2)} for reason, (count, total) in sorted(slots.items())}


def revenue_review_gate(*, direction_conflict: bool, held_total: float, posted_total: float, reconciles: bool) -> bool:
    """T7: a statement needs revenue review when a credit's direction conflicts with its amount, when its held
    credits are REVENUE_REVIEW_HELD_SHARE percent or more of all its posted credits (non-revenue included), compared
    in integer cents, or when its revenue does not reconcile. Counted, flagged credits never gate."""
    held_cents = round(held_total * 100)
    posted_cents = round(posted_total * 100)
    held_share = held_cents > 0 and held_cents * 100 >= REVENUE_REVIEW_HELD_SHARE * posted_cents
    return direction_conflict or held_share or not reconciles


```

In `analysis/revenue.py` (lines 312-317), replace:

```python
    initial_state = record.get("revenue_initial_classification")
    initial_state = LEGACY_REVENUE_STATE_MAP.get(initial_state, initial_state)
    if initial_state != "unverified_deposit":
        raise ValueError("only automatically unverified deposits can be reviewed")

    if decision == "confirm":
```

with:

```python
    initial_state = record.get("revenue_initial_classification")
    initial_state = LEGACY_REVENUE_STATE_MAP.get(initial_state, initial_state)
    # 5.6 (T6, §10.7): a counted or held deposit, and a credit a rule verified, are reviewable; a credit a
    # non-revenue rule decided is not. A payload analysed before 5.6 carries no tier and keeps today's rule.
    tiered = isinstance(record.get("revenue_tier"), str)
    reviewable = {"unverified_deposit", "verified_revenue"} if tiered else {"unverified_deposit"}
    if initial_state not in reviewable:
        raise ValueError("only automatically unverified deposits can be reviewed")
    if decision == "confirm" and initial_state == "verified_revenue":
        raise ValueError(_ALREADY_VERIFIED)

    if decision == "confirm":
```

In `analysis/revenue.py` (lines 319-333), replace:

```python
        status = "confirmed"
        note = "Reviewer confirmed this credit as operating revenue."
    elif decision == "reject":
        state = "non_revenue"
        status = "rejected"
        note = "Reviewer rejected this credit as operating revenue."
    else:
        state = "unverified_deposit"
        status = "pending"
        note = None

    record["revenue_classification"] = state
    record["revenue_review_required"] = state == "unverified_deposit"
    record["revenue_review_status"] = status
    record["revenue_review_note"] = note
```

with:

```python
        status = "confirmed"
        note = "Reviewer confirmed this credit as operating revenue."
        tier = "verified"
    elif decision == "reject":
        state = "non_revenue"
        status = "rejected"
        note = "Reviewer rejected this credit as operating revenue."
        tier = "non_revenue"
    else:
        state = initial_state
        status = "pending" if initial_state == "unverified_deposit" else "not_required"
        note = None
        tier = record.get("revenue_initial_tier")

    record["revenue_classification"] = state
    if tiered:
        record["revenue_tier"] = tier
        record["revenue_review_required"] = tier == "excluded_pending_review"
    else:
        tier = None
        record["revenue_review_required"] = state == "unverified_deposit"
    record["revenue_review_status"] = status
    record["revenue_review_note"] = note
```

In `analysis/revenue.py` (lines 335-338), replace:

```python
        None if decision == "reset" else reviewed_at or datetime.now(UTC).isoformat()
    )
    record.update(revenue_contribution_flags(state, tier_of_state(state)))
    return record

```

with:

```python
        None if decision == "reset" else reviewed_at or datetime.now(UTC).isoformat()
    )
    record.update(revenue_contribution_flags(state, tier))
    if not tiered:
        record.pop("contributes_to_true_revenue", None)
    return record

```

In `analysis/metrics.py` (lines 28-32), replace:

```python
)
from .revenue import (
    WITHHOLDING_DENOMINATOR_MODES,
    normalize_withholding_denominator_mode,
)

```

with:

```python
)
from .revenue import (
    STATE_OF_TIER,
    WITHHOLDING_DENOMINATOR_MODES,
    normalize_withholding_denominator_mode,
    revenue_review_gate,
)

```

In `analysis/metrics.py` (lines 107-111), replace:

```python
    unverified_deposit_evidence: list[TransactionClassification] = field(default_factory=list)
    non_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    # Deprecated aliases retained for consumers of the version 3.0 API.
    true_revenue: float = 0.0
    confirmed_true_revenue: float = 0.0
```

with:

```python
    unverified_deposit_evidence: list[TransactionClassification] = field(default_factory=list)
    non_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    # 5.6 (true revenue spec §5.1, §9.1): True revenue is verified plus counted; the held credits wait for an analyst.
    true_revenue_total: float = 0.0
    true_revenue_count: int = 0
    counted_flagged_total: float = 0.0
    counted_flagged_count: int = 0
    excluded_pending_review_total: float = 0.0
    excluded_pending_review_count: int = 0
    counted_flagged_by_reason: dict[str, dict[str, float | int]] = field(default_factory=dict)
    excluded_pending_review_by_reason: dict[str, dict[str, float | int]] = field(default_factory=dict)
    revenue_review_items: int = 0
    counted_flagged_evidence: list[TransactionClassification] = field(default_factory=list)
    excluded_pending_review_evidence: list[TransactionClassification] = field(default_factory=list)
    # Deprecated aliases retained for consumers of the version 3.0 API. 5.6 (T9): `true_revenue` and
    # `true_revenue_evidence` are repointed to True revenue (verified plus counted).
    true_revenue: float = 0.0
    confirmed_true_revenue: float = 0.0
```

In `analysis/metrics.py` (lines 314-319), replace:

```python
    if withholding_denominator_mode not in WITHHOLDING_DENOMINATOR_MODES:
        raise ValueError(
            "withholding_denominator_mode must be legacy_eligible_deposits "
            "or verified_revenue"
        )
    m = Metrics()
```

with:

```python
    if withholding_denominator_mode not in WITHHOLDING_DENOMINATOR_MODES:
        raise ValueError(
            "withholding_denominator_mode must be legacy_eligible_deposits, "
            "verified_revenue or true_revenue"
        )
    m = Metrics()
```

In `analysis/metrics.py` (lines 331-334), replace:

```python
    flagged_credited_totals: dict[str, float] = {}
    flagged_payees: dict[str, set[str]] = {}
    for t, classification in zip(stmt.transactions, records):
        if t.amount >= 0:
```

with:

```python
    flagged_credited_totals: dict[str, float] = {}
    flagged_payees: dict[str, set[str]] = {}
    by_reason: dict[str, dict[str, list]] = {"counted_flagged": {}, "excluded_pending_review": {}}
    direction_conflict = False
    for t, classification in zip(stmt.transactions, records):
        if t.amount >= 0:
```

In `analysis/metrics.py` (lines 377-380), replace:

```python
                    "every posted credit must contribute to exactly one revenue state"
                )
            m.total_posted_credits += t.amount
            m.total_posted_credit_count += 1
```

with:

```python
                    "every posted credit must contribute to exactly one revenue state"
                )
            # 5.6 (§5.4): every posted credit carries exactly one tier, and its tier agrees with its state.
            tier = classification.revenue_tier
            if tier is None or STATE_OF_TIER.get(tier) != classification.revenue_classification:
                raise ValueError("every posted credit's revenue state must agree with its tier")
            if classification.revenue_match_method == "direction_conflict":
                direction_conflict = True
            if tier in by_reason:
                slot = by_reason[tier].setdefault(classification.revenue_tier_reason or "", [0, 0.0])
                slot[0] += 1
                slot[1] += t.amount
            if tier == "counted_flagged":
                m.counted_flagged_total += t.amount
                m.counted_flagged_count += 1
                m.counted_flagged_evidence.append(classification)
            elif tier == "excluded_pending_review":
                m.excluded_pending_review_total += t.amount
                m.excluded_pending_review_count += 1
                m.excluded_pending_review_evidence.append(classification)
            m.total_posted_credits += t.amount
            m.total_posted_credit_count += 1
```

In `analysis/metrics.py` (lines 433-443), replace:

```python
    m.unverified_deposit_total = round(m.unverified_deposit_total, 2)
    m.non_revenue_total = round(m.non_revenue_total, 2)
    m.confirmed_true_revenue_total = m.verified_revenue_total
    m.confirmed_true_revenue_count = m.verified_revenue_count
    m.confirmed_true_revenue = m.verified_revenue_total
    m.true_revenue = m.verified_revenue_total
    m.potential_revenue_total = m.unverified_deposit_total
    m.potential_revenue_count = m.unverified_deposit_count
    m.true_revenue_evidence = m.verified_revenue_evidence
    m.potential_revenue_evidence = m.unverified_deposit_evidence
    m.maximum_revenue = round(
```

with:

```python
    m.unverified_deposit_total = round(m.unverified_deposit_total, 2)
    m.non_revenue_total = round(m.non_revenue_total, 2)
    m.counted_flagged_total = round(m.counted_flagged_total, 2)
    m.excluded_pending_review_total = round(m.excluded_pending_review_total, 2)
    m.true_revenue_total = round(m.verified_revenue_total + m.counted_flagged_total, 2)
    m.true_revenue_count = m.verified_revenue_count + m.counted_flagged_count
    m.counted_flagged_by_reason = {
        reason: {"count": count, "total": round(total, 2)}
        for reason, (count, total) in sorted(by_reason["counted_flagged"].items())
    }
    m.excluded_pending_review_by_reason = {
        reason: {"count": count, "total": round(total, 2)}
        for reason, (count, total) in sorted(by_reason["excluded_pending_review"].items())
    }
    m.revenue_review_items = m.excluded_pending_review_count
    m.confirmed_true_revenue_total = m.verified_revenue_total
    m.confirmed_true_revenue_count = m.verified_revenue_count
    m.confirmed_true_revenue = m.verified_revenue_total
    m.true_revenue = m.true_revenue_total
    m.potential_revenue_total = m.unverified_deposit_total
    m.potential_revenue_count = m.unverified_deposit_count
    m.true_revenue_evidence = [
        record for record in records
        if record.contributes_to_verified_revenue or record.contributes_to_counted_flagged
    ]
    m.potential_revenue_evidence = m.unverified_deposit_evidence
    m.maximum_revenue = round(
```

In `analysis/metrics.py` (lines 446-452), replace:

```python
    )
    m.total_posted_credits = round(m.total_posted_credits, 2)
    m.revenue_classified_total = round(
        m.verified_revenue_total
        + m.unverified_deposit_total
        + m.non_revenue_total,
        2,
```

with:

```python
    )
    m.total_posted_credits = round(m.total_posted_credits, 2)
    # 5.6 (§5.1): the four-tier identity, verified + counted + held + non-revenue = posted credits.
    m.revenue_classified_total = round(
        m.verified_revenue_total
        + m.counted_flagged_total
        + m.excluded_pending_review_total
        + m.non_revenue_total,
        2,
```

In `analysis/metrics.py` (lines 454-458), replace:

```python
    m.revenue_classified_count = (
        m.verified_revenue_count
        + m.unverified_deposit_count
        + m.non_revenue_count
    )
```

with:

```python
    m.revenue_classified_count = (
        m.verified_revenue_count
        + m.counted_flagged_count
        + m.excluded_pending_review_count
        + m.non_revenue_count
    )
```

In `analysis/metrics.py` (lines 465-469), replace:

```python
        and m.revenue_classified_count == m.total_posted_credit_count
    )
    m.revenue_review_required = m.unverified_deposit_count > 0
    m.lenders_detected = len(confirmed_entities)
    m.potential_lenders_detected = len(potential_entities)
```

with:

```python
        and m.revenue_classified_count == m.total_posted_credit_count
    )
    m.revenue_review_required = revenue_review_gate(
        direction_conflict=direction_conflict,
        held_total=m.excluded_pending_review_total,
        posted_total=m.total_posted_credits,
        reconciles=m.revenue_reconciles,
    )
    m.lenders_detected = len(confirmed_entities)
    m.potential_lenders_detected = len(potential_entities)
```

In `analysis/metrics.py` (lines 581-584), replace:

```python
        m.eligible_deposit_definition = "verified classified revenue"
        m.withholding_denominator_label = "Verified revenue"
    else:
        m.eligible_deposits = m.legacy_eligible_deposits
```

with:

```python
        m.eligible_deposit_definition = "verified classified revenue"
        m.withholding_denominator_label = "Verified revenue"
    elif withholding_denominator_mode == "true_revenue":
        m.eligible_deposits = m.true_revenue_total
        m.eligible_deposit_definition = "true revenue: verified plus counted credits"
        m.withholding_denominator_label = "True revenue"
    else:
        m.eligible_deposits = m.legacy_eligible_deposits
```

In `analysis/detect.py` (lines 91-95), replace:

```python
    verified_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    unverified_deposit_evidence: list[TransactionClassification] = field(default_factory=list)
    # Deprecated aliases for version 3.0 API consumers.
    true_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    potential_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
```

with:

```python
    verified_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    unverified_deposit_evidence: list[TransactionClassification] = field(default_factory=list)
    # 5.6 (true revenue spec §9.1): the counted and the held credits.
    counted_flagged_evidence: list[TransactionClassification] = field(default_factory=list)
    excluded_pending_review_evidence: list[TransactionClassification] = field(default_factory=list)
    # Deprecated aliases for version 3.0 API consumers. 5.6 (T9): true_revenue_evidence is True revenue's rows,
    # verified plus counted.
    true_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    potential_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
```

In `analysis/detect.py` (lines 314-317), replace:

```python
    ]
    non_revenue_evidence = [record for record in records if record.contributes_to_non_revenue]
    manual_review = [
        record
```

with:

```python
    ]
    non_revenue_evidence = [record for record in records if record.contributes_to_non_revenue]
    counted_flagged_evidence = [record for record in records if record.contributes_to_counted_flagged]
    excluded_pending_review_evidence = [
        record for record in records if record.contributes_to_excluded_pending_review
    ]
    true_revenue_evidence = [
        record for record in records
        if record.contributes_to_verified_revenue or record.contributes_to_counted_flagged
    ]
    # 5.6: a row's revenue_review_required is set for a held credit only (§5.4).
    manual_review = [
        record
```

In `analysis/detect.py` (lines 334-338), replace:

```python
        verified_revenue_evidence=verified_revenue_evidence,
        unverified_deposit_evidence=unverified_deposit_evidence,
        true_revenue_evidence=verified_revenue_evidence,
        potential_revenue_evidence=unverified_deposit_evidence,
        non_revenue_evidence=non_revenue_evidence,
```

with:

```python
        verified_revenue_evidence=verified_revenue_evidence,
        unverified_deposit_evidence=unverified_deposit_evidence,
        counted_flagged_evidence=counted_flagged_evidence,
        excluded_pending_review_evidence=excluded_pending_review_evidence,
        true_revenue_evidence=true_revenue_evidence,
        potential_revenue_evidence=unverified_deposit_evidence,
        non_revenue_evidence=non_revenue_evidence,
```

In `analysis/serialization.py` (lines 202-207), replace:

```python
                asdict(item) for item in detection.non_revenue_evidence
            ],
            "true_revenue_evidence": [
                asdict(item) for item in detection.verified_revenue_evidence
            ],
            "potential_revenue_evidence": [
```

with:

```python
                asdict(item) for item in detection.non_revenue_evidence
            ],
            # 5.6 (§9.1): the counted and held credits; true_revenue_evidence is repointed to verified plus counted.
            "counted_flagged_evidence": [
                asdict(item) for item in detection.counted_flagged_evidence
            ],
            "excluded_pending_review_evidence": [
                asdict(item) for item in detection.excluded_pending_review_evidence
            ],
            "true_revenue_evidence": [
                asdict(item) for item in detection.true_revenue_evidence
            ],
            "potential_revenue_evidence": [
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_true_revenue_payload.py -q -p no:cacheprovider`

Expected: PASS: `15 passed`.

- [ ] **Step 5: Re-pin the assertions this task moves (pin ledger rows 20-23).**

In `tests/test_revenue_classification.py` (lines 250-252), replace:

```python
    assert metrics.revenue_reconciles
    assert metrics.revenue_review_required
    assert len(metrics.verified_revenue_evidence) == 1
```

with:

```python
    assert metrics.revenue_reconciles
    # 5.6 (T7): the mobile deposit is a counted check deposit, and counted credits never gate review.
    assert not metrics.revenue_review_required
    assert len(metrics.verified_revenue_evidence) == 1
```

In `tests/test_revenue_classification.py` (lines 664-666), replace:

```python
    assert export_row["non_revenue_total"] == "1880.25"
    assert export_row["needs_review"] == "REVIEW"
    assert coverage_status(report) == "needs_review"

```

with:

```python
    assert export_row["non_revenue_total"] == "1880.25"
    # 5.6 (T7): the statement's eight unverified deposits are two check deposits and six e-Transfers, all counted,
    # so no credit is held and the revenue gate is clear.
    assert export_row["needs_review"] == ""
    assert coverage_status(report) == "clean"

```

In `tests/test_analysis.py` (lines 3361-3362), replace:

```python
    # 5.5 (§6.1 step 9b): the bare teller CUSTOMER DEPOSIT prints no payer word, so it is no longer verified.
    assert m.true_revenue == 0.0
```

with:

```python
    # 5.6 (T9): true_revenue is True revenue; the bare teller CUSTOMER DEPOSIT is counted (no payer printed).
    assert m.true_revenue == 10000.0
    assert m.verified_revenue_total == 0.0
```

In `tests/test_webapp_reanalysis.py` (lines 292-293), replace:

```python
        revenue_classification="non_revenue", revenue_initial_classification="non_revenue",
        revenue_review_required=False, revenue_review_status="not_required",
```

with:

```python
        revenue_classification="non_revenue", revenue_initial_classification="non_revenue",
        revenue_tier="non_revenue", revenue_initial_tier="non_revenue", revenue_tier_reason=None,
        revenue_review_required=False, revenue_review_status="not_required",
```

- [ ] **Step 6: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-CLASSIFIER: `755 passed, 2 deselected`
  - SEL-WEBAPP: `856 passed`
  - SEL-REVENUE: `675 passed`

- [ ] **Step 7: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/detect.py analysis/metrics.py analysis/revenue.py analysis/serialization.py tests/test_analysis.py tests/test_revenue_classification.py tests/test_true_revenue_payload.py tests/test_webapp_reanalysis.py
git commit -m "revenue: the tiered metrics, detection lists and serialized views (5.6)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S4.5: The consumers, the docs, classification 5.6 and analysis stage 25

**Files:**
- Modify: `batch.py:36-40, 102-106, 123-126`
- Modify: `analyze.py:70-73, 75-80`
- Modify: `benchmark/run.py:94-97`
- Modify: `benchmark/compare.py:538-541, 552-557, 561-566, 579-584`
- Modify: `docs/transaction-classification.md:104-107, 498-505`
- Modify: `analysis/transaction_classifier.py:119-121`
- Modify: `webapp/artifact_cache.py:580-581`
- Modify (pins): `tests/test_artifact_cache.py:488, 498-500`
- Modify (pins): `tests/test_flag_group_states.py:61-64`
- Modify (pins): `tests/flagged_payloads.py:18-19`
- Modify (pins): `tests/test_lender_census.py:38-39`
- Modify (pins): `tests/test_webapp_reanalysis.py:1061-1062`
- Modify (pins): `tests/test_true_revenue_payload.py:210`

**Depends on:** S4.4.

**Interfaces:**
- Consumes: S4.4.
- Produces:
  - `CLASSIFICATION_VERSION = "5.6"`, `ANALYSIS_STAGE_VERSION = 25`
  - `batch.py` columns `true_revenue_total`, `counted_flagged_total`, `excluded_pending_review_total`
  - `benchmark.compare.true_revenue_row(set_name, field_name, metrics, mt_summary) -> ComparisonRow` (field `<prefix>true_revenue`, not material)

**Why:** Spec §13 and §9.3: `batch.py` gains the True, counted and held columns and its review flag reads the gate; `analyze.py` prints True, Verified, Counted and Held; the benchmark compares MoneyThumb's subtraction-based `true_credits` with `true_revenue_total` in a row of its own, Verified beside it (review M1, with a test for each consumer); `docs/transaction-classification.md` states the definition, the tiers, the precedence, the holds and how to extend each table; and the version moves: "5.6 (the definition, §5, §8): `CLASSIFICATION_VERSION = "5.6"`, and `ANALYSIS_STAGE_VERSION` 24 → 25 in the same commit."

- [ ] **Step 1: Write the failing tests.**

Append to the end of `tests/test_true_revenue_payload.py`:

```python
# ---------------------------------------------------------------------------------------------------------------- S4.5
def _document_report(rows=None):
    from tests.test_webapp_studio_views import _report
    return _report("CONTOSO BAKERY LLC", "000000001010", 1500.0, rows or [
        (2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
        (4, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), (5, "INTERNAL TRANSFER FROM SAVINGS", 100.0),
        (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0)])


def test_the_batch_csv_carries_true_revenue_and_its_counted_and_held_parts():
    from pathlib import Path

    import batch

    row = batch._row(Path("fabricated.pdf"), _document_report().accounts[0])
    assert batch.FIELDS.index("true_revenue_total") < batch.FIELDS.index("verified_revenue_total")
    assert (row["true_revenue_total"], row["counted_flagged_total"], row["excluded_pending_review_total"],
            row["verified_revenue_total"]) == ("1000.00", "300.00", "900.00", "700.00")
    assert row["needs_review"] == "REVIEW"   # the held credit is 45% of the posted credits (T7)


def test_the_cli_report_prints_true_verified_counted_and_held():
    import analyze

    text = analyze._render(_document_report().accounts[0])
    lines = [line.strip() for line in text.splitlines()]
    true_line = next(line for line in lines if line.startswith("True revenue"))
    assert "$1,000.00" in true_line
    assert lines.index(true_line) < lines.index(next(line for line in lines if line.startswith("Verified revenue")))
    assert any(line.startswith("Counted, not verified") and "$300.00" in line for line in lines)
    assert any(line.startswith("Held for review") and "$900.00" in line for line in lines)


def test_the_benchmark_compares_true_revenue_with_moneythumb_s_true_credits():
    from benchmark.compare import true_revenue_row
    from benchmark.normalize import MTStatementRow

    row = true_revenue_row("fabricated_set", "s1.true_revenue",
                           {"true_revenue_total": 1000.0, "verified_revenue_total": 700.0},
                           MTStatementRow(raw={}, true_credits=1000.0))
    assert (row.field, row.ours, row.mt) == ("s1.true_revenue", 1000.0, 1000.0)
    assert "Verified revenue beside it: 700.0" in row.rationale
    missing = true_revenue_row("fabricated_set", "s1.true_revenue", {"true_revenue_total": None}, None)
    assert (missing.ours, missing.mt) == (None, None)
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_true_revenue_payload.py -q -p no:cacheprovider`

Expected: FAIL: `3 failed, 15 passed`, the first with `ValueError: list.index(x): x not in list`.

- [ ] **Step 3: Implement.**

In `batch.py` (lines 36-40), replace:

```python
    "file", "bank", "account", "period_start", "period_end",
    "summary_reconciles", "average_daily_balance", "total_deposits", "total_debits",
    "total_posted_credits", "verified_revenue_total", "verified_revenue_count",
    "unverified_deposit_total", "unverified_deposit_count", "non_revenue_total",
    "non_revenue_count", "maximum_revenue", "revenue_reconciles",
```

with:

```python
    "file", "bank", "account", "period_start", "period_end",
    "summary_reconciles", "average_daily_balance", "total_deposits", "total_debits",
    "total_posted_credits", "true_revenue_total", "counted_flagged_total", "excluded_pending_review_total",
    "verified_revenue_total", "verified_revenue_count",
    "unverified_deposit_total", "unverified_deposit_count", "non_revenue_total",
    "non_revenue_count", "maximum_revenue", "revenue_reconciles",
```

In `batch.py` (lines 102-106), replace:

```python
    s, r, m, d = report.statement, report.reconciliation, report.metrics, report.detection
    # A statement needs human review when the bank's own summary doesn't reconcile
    # (mis-extracted or internally inconsistent) — the figures can't be trusted.
    needs_review = (
        report.quality.corporate_use == "manual_review_required"
```

with:

```python
    s, r, m, d = report.statement, report.reconciliation, report.metrics, report.detection
    # A statement needs human review when the bank's own summary doesn't reconcile
    # (mis-extracted or internally inconsistent) — the figures can't be trusted —
    # or when its revenue gate is set (5.6, T7: a direction conflict, held credits
    # of ten percent or more of its posted credits, or revenue that does not reconcile).
    needs_review = (
        report.quality.corporate_use == "manual_review_required"
```

In `batch.py` (lines 123-126), replace:

```python
        "total_debits": f"{m.effective_total_withdrawals:.2f}",
        "total_posted_credits": f"{m.total_posted_credits:.2f}",
        "verified_revenue_total": f"{m.verified_revenue_total:.2f}",
        "verified_revenue_count": m.verified_revenue_count,
```

with:

```python
        "total_debits": f"{m.effective_total_withdrawals:.2f}",
        "total_posted_credits": f"{m.total_posted_credits:.2f}",
        # 5.6 (true revenue spec §5.1): True revenue and its counted and held parts.
        "true_revenue_total": f"{m.true_revenue_total:.2f}",
        "counted_flagged_total": f"{m.counted_flagged_total:.2f}",
        "excluded_pending_review_total": f"{m.excluded_pending_review_total:.2f}",
        "verified_revenue_total": f"{m.verified_revenue_total:.2f}",
        "verified_revenue_count": m.verified_revenue_count,
```

In `analyze.py` (lines 70-73), replace:

```python
        wd += f"   | line items ${m.total_withdrawals:,.2f} ({m.num_withdrawals})"
    L.append(wd)
    L.append(
        f"  Verified revenue      : ${m.verified_revenue_total:,.2f}  "
```

with:

```python
        wd += f"   | line items ${m.total_withdrawals:,.2f} ({m.num_withdrawals})"
    L.append(wd)
    # 5.6 (true revenue spec §5.1): True revenue first, then its verified part, the counted and held credits.
    L.append(
        f"  True revenue          : ${m.true_revenue_total:,.2f}  "
        f"({m.true_revenue_count} credit(s))"
    )
    L.append(
        f"  Verified revenue      : ${m.verified_revenue_total:,.2f}  "
```

In `analyze.py` (lines 75-80), replace:

```python
    )
    L.append(
        f"  Unverified deposits   : ${m.unverified_deposit_total:,.2f}  "
        f"({m.unverified_deposit_count} credit(s); review required)"
    )
    L.append(
```

with:

```python
    )
    L.append(
        f"  Counted, not verified : ${m.counted_flagged_total:,.2f}  "
        f"({m.counted_flagged_count} credit(s))"
    )
    L.append(
        f"  Held for review       : ${m.excluded_pending_review_total:,.2f}  "
        f"({m.excluded_pending_review_count} credit(s))"
    )
    L.append(
        f"  Unverified deposits   : ${m.unverified_deposit_total:,.2f}  "
        f"({m.unverified_deposit_count} credit(s): counted plus held)"
    )
    L.append(
```

In `benchmark/run.py` (lines 94-97), replace:

```python
        "max_balance": metrics.get("max_balance"),
        "cash_flow": metrics.get("cash_flow"),
        "verified_revenue_total": metrics.get("verified_revenue_total"),
        "unverified_deposit_total": metrics.get("unverified_deposit_total"),
```

with:

```python
        "max_balance": metrics.get("max_balance"),
        "cash_flow": metrics.get("cash_flow"),
        "true_revenue_total": metrics.get("true_revenue_total"),
        "verified_revenue_total": metrics.get("verified_revenue_total"),
        "unverified_deposit_total": metrics.get("unverified_deposit_total"),
```

In `benchmark/compare.py` (lines 538-541), replace:

```python
            set_name, field("revenue_taxonomy"),
            {
                "verified_revenue": metrics.get("verified_revenue_total"),
                "verified_count": metrics.get("verified_revenue_count"),
```

with:

```python
            set_name, field("revenue_taxonomy"),
            {
                # 5.6: True revenue is the subtraction-based figure MoneyThumb's true credits are; Verified beside it.
                "true_revenue": metrics.get("true_revenue_total"),
                "true_count": metrics.get("true_revenue_count"),
                "verified_revenue": metrics.get("verified_revenue_total"),
                "verified_count": metrics.get("verified_revenue_count"),
```

In `benchmark/compare.py` (lines 552-557), replace:

```python
            },
            different_definition={
                "ours": "three-state evidence-gated revenue classification "
                "(verified / unverified / non-revenue) with conservation "
                "identity and review loop",
                "moneythumb": "binary true / non-true credit split with no "
```

with:

```python
            },
            different_definition={
                "ours": "true revenue (posted credits minus known non-revenue minus the "
                "credits held for review) with its verified part, over four tiers "
                "(verified / counted / held / non-revenue) with conservation "
                "identity and review loop",
                "moneythumb": "binary true / non-true credit split with no "
```

In `benchmark/compare.py` (lines 561-566), replace:

```python
            "row; the taxonomies themselves are not forced into a winner.",
        )
    )
    rows.append(
        classify(
            set_name, field("gross_posted_credits"),
```

with:

```python
            "row; the taxonomies themselves are not forced into a winner.",
        )
    )
    rows.append(true_revenue_row(set_name, field("true_revenue"), metrics, mt_summary))
    rows.append(
        classify(
            set_name, field("gross_posted_credits"),
```

In `benchmark/compare.py` (lines 579-584), replace:

```python
    )

    return rows


def build_revenue_statistics_row(
```

with:

```python
    )

    return rows


def true_revenue_row(set_name: str, field_name: str, metrics: dict[str, Any],
                     mt_summary: MTStatementRow | None) -> ComparisonRow:
    """5.6 (true revenue spec §13): MoneyThumb's true credits are subtraction-based, so they are compared with True
    revenue (posted credits minus known non-revenue minus the credits held for review); Verified is reported beside
    it, never compared. Not material: the two definitions are not forced into a winner."""
    verified = metrics.get("verified_revenue_total")
    return classify(
        set_name, field_name,
        metrics.get("true_revenue_total"),
        mt_summary.true_credits if mt_summary else None,
        material=False,
        note=f"Verified revenue beside it: {verified if verified is not None else 'N/A'}.",
    )


def build_revenue_statistics_row(
```

In `docs/transaction-classification.md` (lines 104-107), replace:

```markdown
reviewed. Own-account transfers are excluded when the description identifies
the internal account or self-service transfer channel.

Cancellation and reversal rows are matched to opposite-direction transactions
```

with:

```markdown
reviewed. Own-account transfers are excluded when the description identifies
the internal account or self-service transfer channel.

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
`REVENUE_TIER_REASONS`, which the dashboard mirrors.

**Precedence.** One credit's decision (`_classify_credit_revenue`) takes the
first match: a direction conflict, a reversal, an auto lender paying a dealer,
an insurer, the financing-proceeds rules, the strong non-revenue rules and
own-account transfers, the channel gate, the operating registry, the
card-settlement forms, the verified descriptors (the holder's own name never
verifies), customer and invoice wording, payer accounts-payable remittance,
public payers, wire remittance, then the fallback. The statement passes then run
in order: duplicates, reversal pairs, the recurrence pass (pooled operating
sources verify by recurrence; the pool never shrinks and a veto word keeps a
row out), the auction and property branches, the payer-remittance counter-debit
guard, and last the true-revenue pass (`analysis/true_revenue.py`), which tiers
every posted credit. A `non_revenue` credit stays `non_revenue` except where a
rule narrows a non-revenue pattern (spec §6.3); a held credit enters True
revenue only when an analyst confirms it.

**Holds.** The true-revenue pass holds a credit (tier
`excluded_pending_review`) in this order: insurer payer, insurer-named payer,
possible return, financing-named payer, payer debited as a lender, the holder's
own name, payroll or salary, personal income, a non-sale purpose, a payer also
debited this account; then by channel: a wire with no sender, a transfer with no
counterparty or naming an account, and repeated round person-to-person sums.
Every other unverified credit is counted (`counted_flagged`) with its reason. A
statement needs revenue review (`revenue_review_required`) when it has a
direction conflict, when its held credits are ten percent or more of its posted
credits (compared in integer cents, `REVENUE_REVIEW_HELD_SHARE`), or when its
revenue does not reconcile.

**Extending the tables.** Every table below is checked by
`python tools/operating_registry.py --check` and by its tests.
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
  is the dealer's sale. A credit union's vehicle-purchase entry is counted, never
  verified.
- `PAYOUT_CREDIT_ENTITIES`: a platform whose payout is the business's sales but
  whose name is also its financing partner (buy-now-pay-later settlements
  included since 2026-09-28); its credits are counted, never verified.

Cancellation and reversal rows are matched to opposite-direction transactions
```

In `docs/transaction-classification.md` (lines 498-505), replace:

```markdown
`verified revenue + unverified deposits + non-revenue = total posted credits`

Reviewer confirmation changes an unverified row to `verified_revenue`; rejection
changes it to `non_revenue`. Reset restores `unverified_deposit`. The
API, package aggregation, filters, evidence tables, and exports are rebuilt from
the updated record.

Credits, funding deposits, duplicates proven by a repeated printed running
```

with:

```markdown
`verified revenue + unverified deposits + non-revenue = total posted credits`

and, since 5.6, by tier:

`verified + counted + held + non-revenue = total posted credits`, with
`True revenue = verified + counted`.

Reviewer confirmation changes a held or counted row to `verified_revenue` (tier
`verified`); rejection changes it to `non_revenue` (tier `non_revenue`). A credit
a rule verified can be rejected, never confirmed. Reset restores the row's first
state and tier. The API, package aggregation, filters, evidence tables, and
exports are rebuilt from the updated record. An analysis saved before 5.6
carries no tier: its review follows the three-state rules and its True revenue
is not established.

Credits, funding deposits, duplicates proven by a repeated printed running
```

In `analysis/transaction_classifier.py` (lines 119-121), replace:

```python
#: invoice, auctions and property platforms, and the non-revenue narrowings.
#: Moves with `webapp.artifact_cache.ANALYSIS_STAGE_VERSION`.
CLASSIFICATION_VERSION = "5.5"
```

with:

```python
#: invoice, auctions and property platforms, and the non-revenue narrowings.
#: 5.6 (2026-09-28): the definitional rules (§8): every posted credit carries a
#: revenue tier, True revenue and its counted and held parts, and the review gate.
#: Moves with `webapp.artifact_cache.ANALYSIS_STAGE_VERSION`.
CLASSIFICATION_VERSION = "5.6"
```

In `webapp/artifact_cache.py` (lines 580-581), replace:

```python
# Pinned in the same change (`tests/test_artifact_cache.py`).
ANALYSIS_STAGE_VERSION = 24
```

with:

```python
# Pinned in the same change (`tests/test_artifact_cache.py`).
# 24 -> 25: TRUE-REVENUE definitional rules (2026-09-28 design, §8) —
# classification version 5.6: every posted credit carries revenue_tier,
# revenue_initial_tier and revenue_tier_reason, the metrics gain True revenue and
# its counted and held parts, true_revenue is repointed, and
# revenue_review_required follows the held share (T7). A payload-shape change:
# a warm cache keyed on 24 would serve tier-less rows; a re-analysis recomputes
# the analysis stage from the cached reading. OCR stays cached. Pinned in the
# same change (`tests/test_artifact_cache.py`).
ANALYSIS_STAGE_VERSION = 25
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_true_revenue_payload.py -q -p no:cacheprovider`

Expected: PASS: `18 passed`.

- [ ] **Step 5: Re-pin the assertions this task moves (pin ledger rows 24-29).**

In `tests/test_artifact_cache.py` (line 488), replace:

```python
def test_analysis_stage_version_is_pinned_at_24():
```

with:

```python
def test_analysis_stage_version_is_pinned_at_25():
```

In `tests/test_artifact_cache.py` (lines 498-500), replace:

```python
    true-revenue bug fixes (classification 5.5, 2026-09-28) go 23 -> 24. This is
    that pin."""
    assert ANALYSIS_STAGE_VERSION == 24
```

with:

```python
    true-revenue bug fixes (classification 5.5, 2026-09-28) go 23 -> 24, and its
    definitional rules (classification 5.6: the revenue tiers) go 24 -> 25. This
    is that pin."""
    assert ANALYSIS_STAGE_VERSION == 25
```

In `tests/test_flag_group_states.py` (lines 61-64), replace:

```python
    # 5.5/24: the true-revenue bug fixes (2026-09-28 design, §7).
    assert CLASSIFICATION_VERSION == "5.5"
    assert classify_transaction("FABRICATED ROW", -10.0).classification_version == "5.5"
    assert ANALYSIS_STAGE_VERSION == 24
```

with:

```python
    # 5.5/24: the true-revenue bug fixes (2026-09-28 design, §7). 5.6/25: its definitional rules (§8).
    assert CLASSIFICATION_VERSION == "5.6"
    assert classify_transaction("FABRICATED ROW", -10.0).classification_version == "5.6"
    assert ANALYSIS_STAGE_VERSION == 25
```

In `tests/flagged_payloads.py` (lines 18-19), replace:

```python
#: true-revenue bug fixes.
CURRENT_VERSION = "5.5"
```

with:

```python
#: true-revenue bug fixes, and 5.5 -> 5.6 with its revenue tiers.
CURRENT_VERSION = "5.6"
```

In `tests/test_lender_census.py` (lines 38-39), replace:

```python
    # 5.5: the true-revenue bug fixes (2026-09-28).
    assert result["classification_version"] == "5.5"
```

with:

```python
    # 5.5: the true-revenue bug fixes (2026-09-28); 5.6: its revenue tiers.
    assert result["classification_version"] == "5.6"
```

In `tests/test_webapp_reanalysis.py` (lines 1061-1062), replace:

```python
    # 5.5: the true-revenue bug fixes (2026-09-28).
    assert {record["classification_version"] for record in records.values()} == {"5.5"}
```

with:

```python
    # 5.5: the true-revenue bug fixes (2026-09-28); 5.6: its revenue tiers.
    assert {record["classification_version"] for record in records.values()} == {"5.6"}
```

- [ ] **Step 6: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-CLASSIFIER: `755 passed, 2 deselected`
  - SEL-REGISTRY: `362 passed, 4 skipped`
  - SEL-WEBAPP: `856 passed`
  - SEL-REVENUE: `678 passed`

  Then the full suite: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests -q -p no:cacheprovider`. Expected: only the 16 known failures of `C:/Users/GustavoPrietodePaula/lender-research/census/failed-ld-final.txt` (measured at this task's commit: 14,058 passed, 55 skipped, 39 deselected, 16 failed).

- [ ] **Step 7: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/transaction_classifier.py analyze.py batch.py benchmark/compare.py benchmark/run.py docs/transaction-classification.md tests/flagged_payloads.py tests/test_artifact_cache.py tests/test_flag_group_states.py tests/test_lender_census.py tests/test_true_revenue_payload.py tests/test_webapp_reanalysis.py webapp/artifact_cache.py
git commit -m "versions: classification 5.6 and analysis stage 25 for true revenue" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## S5: Webapp serving, package, review and exports

### Task S5.1: The served copy and the package figures

**Files:**
- Create: `analysis/revenue_view.py`
- Create: `tests/test_webapp_true_revenue.py`
- Modify: `webapp/app.py:31-34, 37-40, 219-221, 721-724, 1124-1128, 1170-1173, 1365-1369, 1374-1377, 1439-1448, 1469-1475, 1488-1491, 1531-1535, 1540-1543, 1722-1725, 1763-1767, 1918-1922, 2077-2080, 2101-2104, 2117-2120, 2153-2157, 2165-2169`
- Modify: `tools/l1s3_surface_census.py:157-159, 183-186`
- Modify (pins): `tests/test_package_currency.py:76-79, 113-115, 302-307, 801-805`
- Modify (pins): `tests/test_lender_insurance_classification.py:350-353`
- Modify (pins): `tests/test_new_statement_corpus.py:476-478`
- Modify (pins): `tests/test_webapp_app.py:400-402`

**Depends on:** S4.5; its commit waits for the owner's word on pin-ledger row 35 (Step 1).

**Interfaces:**
- Consumes: S4.4's keys, `apply_flagged_groups_to_payload`, `payload_accounts`, `assert_payload_shape`.
- Produces:
  - `analysis/revenue_view.py`: `revenue_flags(account) -> tuple[bool, bool]`, `apply_revenue_view(payload) -> object`
  - `_displayed(...)` returns `apply_revenue_view(apply_flagged_groups_to_payload(...))`
  - package document keys `revenue_established`, `true_revenue_total`, `true_revenue_count`, `counted_flagged_total`, `counted_flagged_count`, `excluded_pending_review_total`, `excluded_pending_review_count`, `counted_flagged_by_reason`, `excluded_pending_review_by_reason`, `revenue_review_required`; totals keys the same plus `revenue_review_items` and `revenue_unestablished_documents`; top-level and `detection` `true_revenue_evidence`, `counted_flagged_evidence`, `excluded_pending_review_evidence`

**Why:** Spec §9.2, §10.4, §11, §12: `analysis/revenue_view.py` sets each account's `verified_revenue_established` and `revenue_established` in the served copy, and on a payload analysed before 5.6 nulls every tier figure and `true_revenue_evidence` and drops `contributes_to_true_revenue` (the stored job is untouched). `_package_analysis` gains the True, counted and held totals and their by-reason figures, the members whose revenue is not established (their totals N/A), T7's gate per member (today's rule for an outdated member), the repointed `true_revenue_evidence`, the new currency keys, and the True-revenue withholding mode, which deducts only the R-d internal-transfer credits a member counted; the two `metrics["true_revenue"]` fallbacks are dropped; `confirmed_true_revenue_total` and `confirmed_true_revenue` are N/A with the verified total they alias (T9, review M4). Its commit waits for the owner's word on pin-ledger row 35 (review I7; Step 1).

- [ ] **Step 1: The owner's word on pin-ledger row 35 (review I7).** This task moves one real-statement assertion: `tests/test_new_statement_corpus.py:476-478`, the package's `verified_revenue_total` for the new-corpus navigant statement, goes from its measured figure to `None` (spec §9.2 and §10.4: the member's captured credits are not the money its bank total counts, so the package's verified total is N/A). The Global Constraints forbid re-pinning a real-statement test without the owner, and spec §13 does not list this one. Before the commit (the last step), the orchestrator asks the owner, quoting the row, the cause and the rule: "May the package's verified total for the navigant statement read N/A (None) instead of its partial figure, as spec §9.2 and §10.4 say?" Record the answer and its date in the task report. With a yes, the task goes on. Without one, stop before the commit and report: the other tasks do not depend on this row, but S5.1 does not land.

- [ ] **Step 2: Write the failing tests.**

Create `tests/test_webapp_true_revenue.py`:

```python
"""True revenue spec §9.2, §10.4, §10.7, §10.8, §11, §12 (S5): the package's True revenue, the N/A rules, the served
copy of an older payload, the gate, the True-revenue withholding mode, the exports, the review routes and the replay.
Fabricated statements only, analysed by the real analysis path."""
from __future__ import annotations

import copy

from tests.test_webapp_studio_views import _report

ROWS = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
        (4, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), (5, "INTERNAL TRANSFER FROM SAVINGS", 100.0),
        (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0)]


def _payload(rows=ROWS, month=3):
    from analysis.serialization import document_report_to_dict
    return document_report_to_dict(_report("CONTOSO BAKERY LLC", "000000001010", 1500.0, rows, month))


def _untiered(payload):
    old = copy.deepcopy(payload)
    for transaction in old["statement"]["transactions"]:
        record = transaction.get("classification") or {}
        for key in ("revenue_tier", "revenue_initial_tier", "revenue_tier_reason"):
            record.pop(key, None)
        record["classification_version"] = "5.4"
    return old


def _package(*payloads):
    from webapp.app import _package_analysis
    from webapp.jobs import Job
    return _package_analysis([Job(id=f"job-{index}", filename=f"statement-{index}.pdf", status="done", analysis=payload)
                              for index, payload in enumerate(payloads, start=1)])


def test_a_package_member_carries_its_true_revenue_and_parts():
    package = _package(_payload())
    document, totals = package["documents"][0], package["totals"]
    assert document["revenue_established"] and document["verified_revenue_established"]
    assert (document["true_revenue_total"], document["counted_flagged_total"],
            document["excluded_pending_review_total"]) == (1000.0, 300.0, 900.0)
    assert document["excluded_pending_review_by_reason"] == {"financing_named_payer": {"count": 1, "total": 900.0}}
    assert (totals["true_revenue_total"], totals["true_revenue"], totals["verified_revenue_total"]) == (
        1000.0, 1000.0, 700.0)
    assert totals["revenue_review_items"] == 1 and totals["revenue_review_required"]
    assert totals["revenue_unestablished_documents"] == []
    assert len(package["true_revenue_evidence"]) == 2
    assert package["detection"]["true_revenue_evidence"] == package["true_revenue_evidence"]
    assert len(package["counted_flagged_evidence"]) == len(package["excluded_pending_review_evidence"]) == 1


def test_counted_credits_never_gate_the_package():
    rows = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 7000.0), (3, "MOBILE DEPOSIT", 3000.0),
            (4, "ZELLE PAYMENT FROM JOHN SMITH CONF 1", 123.0)]
    totals = _package(_payload(rows))["totals"]
    assert not totals["revenue_review_required"]
    assert totals["decision"] == "approved"


def test_an_older_member_leaves_the_package_true_revenue_not_established():
    package = _package(_payload(), _untiered(_payload(month=4)))
    totals = package["totals"]
    assert totals["true_revenue_total"] is None and totals["counted_flagged_total"] is None
    assert totals["verified_revenue_total"] == 1400.0
    assert totals["revenue_unestablished_documents"] == ["job-2"]
    assert package["true_revenue_evidence"] is None
    older = package["documents"][1]
    assert not older["revenue_established"] and older["true_revenue_total"] is None
    # Its gate is the rule it was analysed under: a pending unverified deposit needs review.
    assert older["revenue_review_required"]


def test_the_verified_aliases_are_n_a_with_the_verified_total():
    # Review M4 (T9): confirmed_true_revenue_total and confirmed_true_revenue alias the verified total, so a member
    # whose verified revenue is not established leaves all three N/A.
    partial = _payload()
    partial["statement"]["transactions"][0]["classification"]["revenue_classification"] = None
    totals = _package(_payload(month=4), partial)["totals"]
    assert totals["verified_revenue_total"] is None
    assert totals["confirmed_true_revenue_total"] is None and totals["confirmed_true_revenue"] is None
    assert totals["revenue_unestablished_documents"] == ["job-2"]


def test_the_served_copy_of_an_older_payload_nulls_true_revenue():
    from webapp.app import _displayed
    served = _displayed(_untiered(_payload()), settings={})
    assert served["metrics"]["revenue_established"] is False
    assert served["metrics"]["verified_revenue_established"] is True
    assert served["metrics"]["true_revenue"] is None and served["metrics"]["true_revenue_total"] is None
    assert served["detection"]["true_revenue_evidence"] is None
    assert all("contributes_to_true_revenue" not in transaction["classification"]
               for transaction in served["statement"]["transactions"] if transaction["amount"] > 0)
    assert served["metrics"]["verified_revenue_total"] == 700.0
    fresh = _displayed(_payload(), settings={})
    assert fresh["metrics"]["revenue_established"] is True


def test_the_true_revenue_mode_deducts_only_counted_internal_transfer_credits():
    from analysis.pipeline import AccountRosterEntry, DocumentReport, identify_internal_transfers
    from analysis.serialization import document_report_to_dict

    checking = _report("CONTOSO BAKERY LLC", "000000001010", 1500.0,
                       [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 4000.0),
                        (4, "ONLINE TRANSFER FROM CHK 2020", 500.0)]).accounts[0]
    savings = _report("CONTOSO BAKERY SAVINGS", "000000002020", 9000.0,
                      [(4, "ONLINE TRANSFER TO CHK 1010", -500.0)]).accounts[0]
    transfers, notes = identify_internal_transfers([checking, savings])
    roster = [AccountRosterEntry("CONTOSO BAKERY LLC", "checking", "1010", "published", published_index=0),
              AccountRosterEntry("CONTOSO BAKERY SAVINGS", "savings", "2020", "published", published_index=1)]
    payload = document_report_to_dict(DocumentReport(accounts=[checking, savings], internal_transfers=transfers,
                                                     integrity_notes=notes, account_roster=roster,
                                                     document_period=("2031-03-01", "2031-03-28")))
    from analysis.revenue import rebuild_serialized_revenue_views
    for account in payload["accounts"]:
        account["metrics"]["withholding_denominator_mode"] = "true_revenue"
    rebuild_serialized_revenue_views(payload)
    assert [account["metrics"]["withholding_denominator"] for account in payload["accounts"]] == [4000.0, 0.0]
    package = _package(payload)
    totals = package["totals"]
    assert (totals["withholding_denominator_mode"], totals["withholding_denominator_label"]) == (
        "true_revenue", "True revenue")
    # The pair's credit is an own-account transfer, non-revenue, so True revenue never held it: nothing comes off.
    assert totals["withholding_denominator"] == 4000.0
    assert totals["true_revenue_total"] == 4000.0
```

- [ ] **Step 3: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_webapp_true_revenue.py -q -p no:cacheprovider`

Expected: FAIL: `6 failed`, the first with `KeyError: 'revenue_established'`.

- [ ] **Step 4: Implement.**

Create `analysis/revenue_view.py`:

```python
"""Revenue figures as the dashboard presents them (true revenue spec §10.4, §12).

A presentation step, like `analysis/flagged_view.py`: it works on a COPY of a published payload and never refuses. On
every account it sets the two flags the dashboard reads before it prints a revenue figure:

* `verified_revenue_established`: every captured credit carries a revenue state, and the captured credits are the
  money the statement's Total counts (the line items are the Total's source, or they add up to the bank's own total);
  a statement that captured no credit and whose Total is zero took in nothing, and is established at zero;
* `revenue_established`: that, and every posted credit carries a 5.6 tier.

A payload analysed before 5.6 carries no tier. Its served copy nulls True revenue and every tier figure
(`true_revenue`, `true_revenue_total` and the counted and held totals, counts and reasons), nulls every
`true_revenue_evidence`, and drops `contributes_to_true_revenue` from every row, so no reader takes the old
verified meaning of those names for the new one (T9, T10). Its verified figures stay as stored.
"""
from __future__ import annotations

import copy
from collections.abc import Mapping

from analysis.payload_shape import (
    ACCOUNTS_KEY,
    DOCUMENT_SHAPE,
    PayloadShapeError,
    assert_payload_shape,
    payload_accounts,
)
from analysis.revenue import REVENUE_STATES, TIER_DETECTION_KEYS, TIER_METRIC_KEYS

_SURFACE = "analysis/revenue_view.py::apply_revenue_view"
def _number(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def revenue_flags(account: Mapping) -> tuple[bool, bool]:
    """`(verified_revenue_established, revenue_established)` of one account payload (§10.4)."""
    statement = account.get("statement") if isinstance(account.get("statement"), Mapping) else {}
    metrics = account.get("metrics") if isinstance(account.get("metrics"), Mapping) else {}
    rows = [row for row in statement.get("transactions") or [] if isinstance(row, Mapping)]
    positive = [row for row in rows if _number(row.get("amount")) > 0]
    classified = [row for row in positive if isinstance(row.get("classification"), Mapping)]
    posted = [row for row in classified if row["classification"].get("is_posted") is not False]
    states_complete = (
        any(isinstance(row.get("classification"), Mapping) for row in rows)
        and len(classified) == len(positive)
        and all(row["classification"].get("revenue_classification") in REVENUE_STATES for row in posted)
    )
    deposit_total = _number(metrics.get("effective_total_deposits"))
    line_item_total = _number(metrics.get("total_deposits"))
    totals_agree = (
        str(metrics.get("deposits_source") or "line_items") == "line_items"
        or abs(line_item_total - deposit_total) < 0.005
    )
    verified = (states_complete and totals_agree) or (bool(statement) and not positive and deposit_total == 0)
    tiered = all(isinstance(row["classification"].get("revenue_tier"), str) for row in posted)
    return verified, verified and tiered


def _served_account(account: Mapping) -> dict:
    result = dict(account)
    verified, established = revenue_flags(account)
    statement = result.get("statement")
    rows = statement.get("transactions") if isinstance(statement, Mapping) else None
    posted = [
        row["classification"] for row in rows or []
        if isinstance(row, Mapping) and isinstance(row.get("classification"), Mapping)
        and _number(row.get("amount")) > 0 and row["classification"].get("is_posted") is not False
    ]
    tiered = bool(posted) and all(isinstance(record.get("revenue_tier"), str) for record in posted)
    metrics = copy.deepcopy(dict(result.get("metrics") or {}))
    metrics["verified_revenue_established"] = verified
    metrics["revenue_established"] = established and (tiered or not posted)
    if posted and not tiered:
        for key in TIER_METRIC_KEYS:
            metrics[key] = None
        transactions = copy.deepcopy(rows)
        for row in transactions:
            if isinstance(row, dict) and isinstance(row.get("classification"), dict):
                row["classification"].pop("contributes_to_true_revenue", None)
        result["statement"] = {**statement, "transactions": transactions}
        detection = copy.deepcopy(dict(result.get("detection") or {}))
        for key in TIER_DETECTION_KEYS:
            detection[key] = None
        result["detection"] = detection
    result["metrics"] = metrics
    return result


def apply_revenue_view(payload: object) -> object:
    """A copy of a published analysis payload with each account's revenue flags set and, before 5.6, its True
    revenue nulled (§10.4, §12). The input is never mutated; a payload of neither published shape is returned as
    it is."""
    try:
        shape = assert_payload_shape(payload, surface=_SURFACE)
        accounts = payload_accounts(payload, surface=_SURFACE)
    except PayloadShapeError:
        return payload
    if shape == DOCUMENT_SHAPE:
        return {**payload, ACCOUNTS_KEY: [_served_account(account) for account in accounts]}
    return _served_account(payload)
```

In `webapp/app.py` (lines 31-34), replace:

```python
    normalize_withholding_denominator_mode,
    REVENUE_STATES,
)
from analysis.nsf_days import apply_nsf_basis_to_payload
```

with:

```python
    normalize_withholding_denominator_mode,
    REVENUE_STATES,
    revenue_review_gate,
)
from analysis.nsf_days import apply_nsf_basis_to_payload
```

In `webapp/app.py` (lines 37-40), replace:

```python
from analysis.flag_groups import FLAG_GROUP_BY_KEY, FLAG_GROUPS
from analysis.flagged_view import apply_flagged_groups_to_payload, enabled_group_keys
from .jobs import JobStore
from .settings import DEFAULTS as SETTINGS_DEFAULTS, load_settings, save_settings
```

with:

```python
from analysis.flag_groups import FLAG_GROUP_BY_KEY, FLAG_GROUPS
from analysis.flagged_view import apply_flagged_groups_to_payload, enabled_group_keys
from analysis.revenue_view import apply_revenue_view
from .jobs import JobStore
from .settings import DEFAULTS as SETTINGS_DEFAULTS, load_settings, save_settings
```

In `webapp/app.py` (lines 219-221), replace:

```python
        carry_over = settings.get("nsf_carry_over", SETTINGS_DEFAULTS["nsf_carry_over"])
    rebased = apply_nsf_basis_to_payload(analysis, carry_over=carry_over, list_days=not export)
    return apply_flagged_groups_to_payload(rebased, enabled=settings)


```

with:

```python
        carry_over = settings.get("nsf_carry_over", SETTINGS_DEFAULTS["nsf_carry_over"])
    rebased = apply_nsf_basis_to_payload(analysis, carry_over=carry_over, list_days=not export)
    # 5.6 (true revenue spec §10.4, §12): each account's revenue flags, and an older payload's True revenue nulled.
    return apply_revenue_view(apply_flagged_groups_to_payload(rebased, enabled=settings))


```

In `webapp/app.py` (lines 721-724), replace:

```python
    "total_posted_credits",
    "true_revenue",
    "unverified_deposit_total",
    "verified_revenue_total",
```

with:

```python
    "total_posted_credits",
    "true_revenue",
    # 5.6 (§9.2): True revenue and its counted and held parts.
    "true_revenue_total",
    "counted_flagged_total",
    "excluded_pending_review_total",
    "unverified_deposit_total",
    "verified_revenue_total",
```

In `webapp/app.py` (lines 1124-1128), replace:

```python
        "non_revenue_total": 0.0,
        "non_revenue_count": 0,
        # Deprecated aliases for version 3.0 API consumers.
        "true_revenue": 0.0,
        "confirmed_true_revenue": 0.0,
```

with:

```python
        "non_revenue_total": 0.0,
        "non_revenue_count": 0,
        # 5.6 (§9.2): True revenue, verified plus counted, and the held credits. None when a completed member's
        # revenue is not established (below).
        "true_revenue_total": 0.0,
        "true_revenue_count": 0,
        "counted_flagged_total": 0.0,
        "counted_flagged_count": 0,
        "excluded_pending_review_total": 0.0,
        "excluded_pending_review_count": 0,
        "revenue_review_items": 0,
        # Deprecated aliases for version 3.0 API consumers. 5.6 (T9): true_revenue is True revenue.
        "true_revenue": 0.0,
        "confirmed_true_revenue": 0.0,
```

In `webapp/app.py` (lines 1170-1173), replace:

```python
        state: [] for state in REVENUE_STATES
    }
    #: (group key, payee) -> the running roll-up of the ticked flag groups (lender detection §8.3).
    flagged_rollup: dict[tuple[str, str], dict] = {}
```

with:

```python
        state: [] for state in REVENUE_STATES
    }
    # 5.6 (§9.2): the counted and held credits' evidence, and the members whose revenue is not established.
    package_tier_evidence: dict[str, list[dict]] = {"counted_flagged": [], "excluded_pending_review": []}
    package_by_reason: dict[str, dict[str, dict]] = {"counted_flagged": {}, "excluded_pending_review": {}}
    unestablished_verified: list[str] = []
    unestablished_revenue: list[str] = []
    any_member_gated = False
    #: (group key, payee) -> the running roll-up of the ticked flag groups (lender detection §8.3).
    flagged_rollup: dict[tuple[str, str], dict] = {}
```

In `webapp/app.py` (lines 1365-1369), replace:

```python
        # records, a failed member), and the table says N/A rather than show it as the month's revenue. A member
        # that captured no credit and whose Total is zero took in nothing, and its True deposits are zero.
        revenue_established = ready and (
            (
                revenue_rows_are_authoritative
```

with:

```python
        # records, a failed member), and the table says N/A rather than show it as the month's revenue. A member
        # that captured no credit and whose Total is zero took in nothing, and its True deposits are zero.
        verified_revenue_established = ready and (
            (
                revenue_rows_are_authoritative
```

In `webapp/app.py` (lines 1374-1377), replace:

```python
            )
            or (bool(statement) and not positive_statement_rows and credits == 0)
        )
        if authoritative_rows:
```

with:

```python
            )
            or (bool(statement) and not positive_statement_rows and credits == 0)
        )
        # 5.6 (§9.2, §10.4): True revenue is established when the verified figure is and every posted credit carries
        # a tier; a payload analysed before 5.6 carries none (§12).
        tiered = revenue_rows_are_authoritative and all(
            isinstance(row["classification"].get("revenue_tier"), str) for row in posted_credit_rows
        )
        revenue_established = verified_revenue_established and (tiered or not posted_credit_rows)
        tier_rows = {
            tier: [row for row in posted_credit_rows if row["classification"].get("revenue_tier") == tier]
            for tier in ("verified", "counted_flagged", "excluded_pending_review")
        } if tiered else {}
        tier_totals = {tier: round(sum(_num(row.get("amount")) for row in rows), 2) for tier, rows in tier_rows.items()}
        member_by_reason: dict[str, dict[str, dict]] = {"counted_flagged": {}, "excluded_pending_review": {}}
        for tier in member_by_reason:
            for row in tier_rows.get(tier, []):
                reason = row["classification"].get("revenue_tier_reason") or ""
                slot = member_by_reason[tier].setdefault(reason, {"count": 0, "total": 0.0})
                slot["count"] += 1
                slot["total"] = round(slot["total"] + _num(row.get("amount")), 2)
        direction_conflict = any(
            row["classification"].get("revenue_match_method") == "direction_conflict" for row in posted_credit_rows
        )
        if authoritative_rows:
```

In `webapp/app.py` (lines 1439-1448), replace:

```python
                _num(metrics.get("total_posted_credit_count"), metrics.get("effective_num_deposits") or 0)
            )
            verified_fallback = _num(
                metrics.get("verified_revenue_total"),
                _num(
                    metrics.get("confirmed_true_revenue_total"),
                    _num(metrics.get("true_revenue"), posted_credit_total),
                ),
            )
            revenue_totals = {
```

with:

```python
                _num(metrics.get("total_posted_credit_count"), metrics.get("effective_num_deposits") or 0)
            )
            # 5.6 (§9.2): `true_revenue` is True revenue now, never a verified figure; without either verified key the
            # member's verified figure is not established (verified_revenue_established is false on this path).
            verified_fallback = _num(
                metrics.get("verified_revenue_total"),
                _num(metrics.get("confirmed_true_revenue_total")),
            )
            revenue_totals = {
```

In `webapp/app.py` (lines 1469-1475), replace:

```python
                "non_revenue": int(_num(metrics.get("non_revenue_count"))),
            }
        eligible_deposits = _num(
            metrics.get("withholding_denominator"),
            _num(metrics.get("true_revenue"), credits),
        )
        denominator_mode = normalize_withholding_denominator_mode(
```

with:

```python
                "non_revenue": int(_num(metrics.get("non_revenue_count"))),
            }
        # 5.6 (§9.2): without a stored denominator, the legacy eligible deposits (never `true_revenue`).
        eligible_deposits = _num(
            metrics.get("withholding_denominator"),
            _num(metrics.get("legacy_eligible_deposits"), credits),
        )
        denominator_mode = normalize_withholding_denominator_mode(
```

In `webapp/app.py` (lines 1488-1491), replace:

```python
            # would remove money the denominator never held.
            eligible_deposits = round(max(eligible_deposits - excluded_credits, 0.0), 2)
        denominator_modes.add(str(denominator_mode))
        nsf_count = int(_num(metrics.get("effective_nsf_count"), 0.0))
```

with:

```python
            # would remove money the denominator never held.
            eligible_deposits = round(max(eligible_deposits - excluded_credits, 0.0), 2)
        elif excluded_positions and denominator_mode == "true_revenue":
            # 5.6 (§11): an R-d pair can hold a credit this member counted (a named transfer between two members), so
            # the True-revenue denominator loses the pair's credits that it holds: verified or counted, and only those.
            counted_transfer_credits = round(sum(
                _num(raw_transactions[position].get("amount"))
                for position in excluded_positions
                if position < len(raw_transactions) and isinstance(raw_transactions[position], dict)
                and _num(raw_transactions[position].get("amount")) > 0
                and ((raw_transactions[position].get("classification") or {}).get("revenue_tier")
                     in ("verified", "counted_flagged"))
            ), 2)
            eligible_deposits = round(max(eligible_deposits - counted_transfer_credits, 0.0), 2)
        denominator_modes.add(str(denominator_mode))
        nsf_count = int(_num(metrics.get("effective_nsf_count"), 0.0))
```

In `webapp/app.py` (lines 1531-1535), replace:

```python
        totals["confirmed_true_revenue_total"] = totals["verified_revenue_total"]
        totals["confirmed_true_revenue"] = totals["verified_revenue_total"]
        totals["true_revenue"] = totals["verified_revenue_total"]
        totals["confirmed_true_revenue_count"] = totals["verified_revenue_count"]
        totals["potential_revenue_total"] = totals["unverified_deposit_total"]
```

with:

```python
        totals["confirmed_true_revenue_total"] = totals["verified_revenue_total"]
        totals["confirmed_true_revenue"] = totals["verified_revenue_total"]
        totals["confirmed_true_revenue_count"] = totals["verified_revenue_count"]
        totals["potential_revenue_total"] = totals["unverified_deposit_total"]
```

In `webapp/app.py` (lines 1540-1543), replace:

```python
        )
        totals["non_revenue_count"] += revenue_counts["non_revenue"]
        totals["total_debits"] = round(totals["total_debits"] + debits, 2)
        totals["cash_flow"] = round(totals["cash_flow"] + cash_flow, 2)
```

with:

```python
        )
        totals["non_revenue_count"] += revenue_counts["non_revenue"]
        if ready and not verified_revenue_established:
            unestablished_verified.append(job.id if account_index is None else f"{job.id}#account_{account_index}")
        if ready and not revenue_established:
            unestablished_revenue.append(job.id if account_index is None else f"{job.id}#account_{account_index}")
        member_reconciles = round(sum(revenue_totals.values()), 2) == posted_credit_total
        if tiered:
            member_gated = revenue_review_gate(
                direction_conflict=direction_conflict,
                held_total=tier_totals["excluded_pending_review"],
                posted_total=posted_credit_total,
                reconciles=member_reconciles,
            )
            totals["true_revenue_total"] = round(
                totals["true_revenue_total"] + tier_totals["verified"] + tier_totals["counted_flagged"], 2
            )
            totals["true_revenue_count"] += len(tier_rows["verified"]) + len(tier_rows["counted_flagged"])
            totals["counted_flagged_total"] = round(totals["counted_flagged_total"] + tier_totals["counted_flagged"], 2)
            totals["counted_flagged_count"] += len(tier_rows["counted_flagged"])
            totals["excluded_pending_review_total"] = round(
                totals["excluded_pending_review_total"] + tier_totals["excluded_pending_review"], 2
            )
            totals["excluded_pending_review_count"] += len(tier_rows["excluded_pending_review"])
            totals["revenue_review_items"] += len(tier_rows["excluded_pending_review"])
            for tier, reasons in member_by_reason.items():
                for reason, slot in reasons.items():
                    item = package_by_reason[tier].setdefault(reason, {"count": 0, "total": 0.0})
                    item["count"] += slot["count"]
                    item["total"] = round(item["total"] + slot["total"], 2)
        else:
            # §12: a member analysed before 5.6 is gated by the rule it was analysed under.
            member_gated = (
                any(row["classification"].get("revenue_classification") == "unverified_deposit"
                    and row["classification"].get("revenue_review_status") == "pending"
                    for row in posted_credit_rows)
                or direction_conflict
                or not member_reconciles
            )
        any_member_gated = any_member_gated or (ready and member_gated)
        totals["total_debits"] = round(totals["total_debits"] + debits, 2)
        totals["cash_flow"] = round(totals["cash_flow"] + cash_flow, 2)
```

In `webapp/app.py` (lines 1722-1725), replace:

```python
            if revenue_state in REVENUE_STATES and _num(tx.get("amount")) > 0:
                package_revenue_evidence[revenue_state].append(evidence)

        doc_row = {
```

with:

```python
            if revenue_state in REVENUE_STATES and _num(tx.get("amount")) > 0:
                package_revenue_evidence[revenue_state].append(evidence)
                if classification.get("revenue_tier") in package_tier_evidence:
                    package_tier_evidence[classification["revenue_tier"]].append(evidence)

        doc_row = {
```

In `webapp/app.py` (lines 1763-1767), replace:

```python
            "verified_revenue_total": revenue_totals["verified_revenue"],
            "verified_revenue_count": revenue_counts["verified_revenue"],
            "verified_revenue_established": revenue_established,
            "unverified_deposit_total": revenue_totals["unverified_deposit"],
            "unverified_deposit_count": revenue_counts["unverified_deposit"],
```

with:

```python
            "verified_revenue_total": revenue_totals["verified_revenue"],
            "verified_revenue_count": revenue_counts["verified_revenue"],
            "verified_revenue_established": verified_revenue_established,
            # 5.6 (§9.2): True revenue and its parts; None for a member whose revenue is not established.
            "revenue_established": revenue_established,
            "true_revenue_total": (
                round(tier_totals["verified"] + tier_totals["counted_flagged"], 2) if tiered else None
            ),
            "true_revenue_count": (
                len(tier_rows["verified"]) + len(tier_rows["counted_flagged"]) if tiered else None
            ),
            "counted_flagged_total": tier_totals["counted_flagged"] if tiered else None,
            "counted_flagged_count": len(tier_rows["counted_flagged"]) if tiered else None,
            "excluded_pending_review_total": tier_totals["excluded_pending_review"] if tiered else None,
            "excluded_pending_review_count": len(tier_rows["excluded_pending_review"]) if tiered else None,
            "counted_flagged_by_reason": member_by_reason["counted_flagged"] if tiered else None,
            "excluded_pending_review_by_reason": member_by_reason["excluded_pending_review"] if tiered else None,
            "revenue_review_required": member_gated,
            "unverified_deposit_total": revenue_totals["unverified_deposit"],
            "unverified_deposit_count": revenue_counts["unverified_deposit"],
```

In `webapp/app.py` (lines 1918-1922), replace:

```python
        and totals["revenue_classified_count"] == totals["total_posted_credit_count"]
    )
    totals["revenue_review_required"] = totals["unverified_deposit_count"] > 0
    package_withholding_raw = (
        abs(totals["withholding_numerator"]) / totals["withholding_denominator"] * 100
```

with:

```python
        and totals["revenue_classified_count"] == totals["total_posted_credit_count"]
    )
    # 5.6 (T7, §9.2): the gate applied to each member; a package needs revenue review when one of them does.
    totals["revenue_review_required"] = any_member_gated
    totals["counted_flagged_by_reason"] = package_by_reason["counted_flagged"]
    totals["excluded_pending_review_by_reason"] = package_by_reason["excluded_pending_review"]
    totals["revenue_unestablished_documents"] = sorted(set(unestablished_revenue) | set(unestablished_verified))
    totals["true_revenue"] = totals["true_revenue_total"]
    if unestablished_revenue:
        # §10.4: a package's True, Counted and Held figures stand only when every completed member's revenue does.
        for key in ("true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
                    "excluded_pending_review_total", "excluded_pending_review_count", "true_revenue",
                    "counted_flagged_by_reason", "excluded_pending_review_by_reason"):
            totals[key] = None
    if unestablished_verified:
        # T9: confirmed_true_revenue_total and confirmed_true_revenue alias the verified total, so they are N/A with it.
        for key in ("verified_revenue_total", "confirmed_true_revenue_total", "confirmed_true_revenue"):
            totals[key] = None
    package_withholding_raw = (
        abs(totals["withholding_numerator"]) / totals["withholding_denominator"] * 100
```

In `webapp/app.py` (lines 2077-2080), replace:

```python
            "Verified revenue"
            if denominator_modes == {"verified_revenue"}
            else "Legacy eligible deposits"
            if denominator_modes == {"legacy_eligible_deposits"}
```

with:

```python
            "Verified revenue"
            if denominator_modes == {"verified_revenue"}
            else "True revenue"
            if denominator_modes == {"true_revenue"}
            else "Legacy eligible deposits"
            if denominator_modes == {"legacy_eligible_deposits"}
```

In `webapp/app.py` (lines 2101-2104), replace:

```python
        for key in _CROSS_CURRENCY_TOTAL_KEYS:
            published_totals[key] = None
        for item in (
            *package_funders,
```

with:

```python
        for key in _CROSS_CURRENCY_TOTAL_KEYS:
            published_totals[key] = None
        # 5.6 (§9.2): the by-reason money is refused with the totals; the counts stay.
        for key in ("counted_flagged_by_reason", "excluded_pending_review_by_reason"):
            if isinstance(published_totals.get(key), dict):
                published_totals[key] = {
                    reason: {**slot, "total": None} for reason, slot in published_totals[key].items()
                }
        for item in (
            *package_funders,
```

In `webapp/app.py` (lines 2117-2120), replace:

```python
        published_totals["decision"] = "review_required"

    return {
        "totals": published_totals,
```

with:

```python
        published_totals["decision"] = "review_required"

    true_revenue_evidence = None if unestablished_revenue else [
        evidence for evidence in (*package_revenue_evidence["verified_revenue"], *package_tier_evidence["counted_flagged"])
    ]
    return {
        "totals": published_totals,
```

In `webapp/app.py` (lines 2153-2157), replace:

```python
        "verified_revenue_evidence": package_revenue_evidence["verified_revenue"],
        "unverified_deposit_evidence": package_revenue_evidence["unverified_deposit"],
        "true_revenue_evidence": package_revenue_evidence["verified_revenue"],
        "potential_revenue_evidence": package_revenue_evidence["unverified_deposit"],
        "non_revenue_evidence": package_revenue_evidence["non_revenue"],
```

with:

```python
        "verified_revenue_evidence": package_revenue_evidence["verified_revenue"],
        "unverified_deposit_evidence": package_revenue_evidence["unverified_deposit"],
        # 5.6 (§9.2, T9): True revenue's evidence is the members' verified plus counted rows; None when a member's
        # revenue is not established.
        "true_revenue_evidence": true_revenue_evidence,
        "counted_flagged_evidence": package_tier_evidence["counted_flagged"],
        "excluded_pending_review_evidence": package_tier_evidence["excluded_pending_review"],
        "potential_revenue_evidence": package_revenue_evidence["unverified_deposit"],
        "non_revenue_evidence": package_revenue_evidence["non_revenue"],
```

In `webapp/app.py` (lines 2165-2169), replace:

```python
            "verified_revenue_evidence": package_revenue_evidence["verified_revenue"],
            "unverified_deposit_evidence": package_revenue_evidence["unverified_deposit"],
            "true_revenue_evidence": package_revenue_evidence["verified_revenue"],
            "potential_revenue_evidence": package_revenue_evidence["unverified_deposit"],
            "non_revenue_evidence": package_revenue_evidence["non_revenue"],
```

with:

```python
            "verified_revenue_evidence": package_revenue_evidence["verified_revenue"],
            "unverified_deposit_evidence": package_revenue_evidence["unverified_deposit"],
            "true_revenue_evidence": true_revenue_evidence,
            "counted_flagged_evidence": package_tier_evidence["counted_flagged"],
            "excluded_pending_review_evidence": package_tier_evidence["excluded_pending_review"],
            "potential_revenue_evidence": package_revenue_evidence["unverified_deposit"],
            "non_revenue_evidence": package_revenue_evidence["non_revenue"],
```

In `tools/l1s3_surface_census.py` (lines 157-159), replace:

```python
    ("webapp/reanalysis.py", "replay_reviews", "per_account",
     "a decision names one posting of one account; every account is searched through payload_accounts"),
)

```

with:

```python
    ("webapp/reanalysis.py", "replay_reviews", "per_account",
     "a decision names one posting of one account; every account is searched through payload_accounts"),
    ("analysis/revenue_view.py", "apply_revenue_view", "per_account",
     "the revenue flags and an older payload's nulled True revenue are served per account ledger; every account is "
     "shown, a malformed document passes untouched"),
)

```

In `tools/l1s3_surface_census.py` (lines 183-186), replace:

```python
    "webapp/reanalysis.py::_records": "one ACCOUNT's records; `replay_reviews` hands it each account from `payload_accounts`",
    "analysis/nsf_days.py::_rebased_account": "one ACCOUNT's ledger and postings; `apply_nsf_basis_to_payload` hands it each account from `payload_accounts`",
    # A developer utility that publishes nothing. Handed a document payload it
    # falls back to the payload itself and `Statement.model_validate` refuses
```

with:

```python
    "webapp/reanalysis.py::_records": "one ACCOUNT's records; `replay_reviews` hands it each account from `payload_accounts`",
    "analysis/nsf_days.py::_rebased_account": "one ACCOUNT's ledger and postings; `apply_nsf_basis_to_payload` hands it each account from `payload_accounts`",
    "analysis/revenue_view.py::_served_account": "one ACCOUNT's revenue view; `apply_revenue_view` hands it each account from `payload_accounts`",
    "analysis/revenue_view.py::revenue_flags": "one ACCOUNT's revenue flags; reached through `_served_account` with that account in hand",
    # A developer utility that publishes nothing. Handed a document payload it
    # falls back to the payload itself and `Statement.model_validate` refuses
```

- [ ] **Step 5: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_webapp_true_revenue.py -q -p no:cacheprovider`

Expected: PASS: `6 passed`.

- [ ] **Step 6: Re-pin the assertions this task moves (pin ledger rows 30-36).**

In `tests/test_package_currency.py` (lines 76-79), replace:

```python
    "total_posted_credits",
    "true_revenue",
    "unverified_deposit_total",
    "verified_revenue_total",
```

with:

```python
    "total_posted_credits",
    "true_revenue",
    # 5.6 (true revenue spec §9.2): True revenue and its counted and held parts.
    "true_revenue_total",
    "counted_flagged_total",
    "excluded_pending_review_total",
    "unverified_deposit_total",
    "verified_revenue_total",
```

In `tests/test_package_currency.py` (lines 113-115), replace:

```python
    "unverified_deposit_count",
    "verified_revenue_count",
}


```

with:

```python
    "unverified_deposit_count",
    "verified_revenue_count",
    # 5.6 (§9.2): the tier counts and the held-row count.
    "true_revenue_count",
    "counted_flagged_count",
    "excluded_pending_review_count",
    "revenue_review_items",
}
#: 5.6 (§9.2, §10.4): the tier counts are unit-free, and None whenever a completed member's revenue is not
#: established, as every metrics-only member of these fixtures is.
REVENUE_TIER_COUNTS = {"true_revenue_count", "counted_flagged_count", "excluded_pending_review_count"}


```

In `tests/test_package_currency.py` (lines 302-307), replace:

```python
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    totals = package["totals"]
    for key in UNIT_FREE_TOTALS:
        assert totals[key] is not None, f"{key} is unit-free and must survive"
    assert totals["documents"] == 2
    assert totals["completed"] == 2
```

with:

```python
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    totals = package["totals"]
    for key in UNIT_FREE_TOTALS - REVENUE_TIER_COUNTS:
        assert totals[key] is not None, f"{key} is unit-free and must survive"
    # The members print no ledger rows, so their revenue is not established and the tier counts are N/A (§10.4);
    # the currency refusal is not what nulls them.
    for key in REVENUE_TIER_COUNTS:
        assert totals[key] is None
    assert totals["documents"] == 2
    assert totals["completed"] == 2
```

In `tests/test_package_currency.py` (lines 801-805), replace:

```python
    # The code that WAS declared is still reported as evidence.
    assert body["currency"]["currencies"] == ["USD"]
    assert len(body["currency"]["refused_total_fields"]) == 34
    assert body["totals"]["cross_currency_totals_refused"] is True
    assert body["totals"]["currency"] is None
```

with:

```python
    # The code that WAS declared is still reported as evidence.
    assert body["currency"]["currencies"] == ["USD"]
    assert len(body["currency"]["refused_total_fields"]) == 37
    assert body["totals"]["cross_currency_totals_refused"] is True
    assert body["totals"]["currency"] is None
```

In `tests/test_lender_insurance_classification.py` (lines 350-353), replace:

```python
    assert not totals["potential_withholding_review_required"]
    # Still review: the fixture's customer deposit needs revenue review (measured 2026-09-26).
    assert totals["decision"] == "review_required"
    assert package["potential_lender_evidence"] == []
```

with:

```python
    assert not totals["potential_withholding_review_required"]
    # 5.6 (true revenue spec T7): the fixture's customer deposit is counted, and a counted credit never gates review.
    assert totals["decision"] == "approved"
    assert package["potential_lender_evidence"] == []
```

In `tests/test_new_statement_corpus.py` (lines 476-478), replace:

```python
    assert package["totals"]["average_daily_balance"] == 1957.43
    assert package["totals"]["verified_revenue_total"] == 3563.85
    assert package["totals"]["unverified_deposit_total"] == 114144.70
```

with:

```python
    assert package["totals"]["average_daily_balance"] == 1957.43
    # 5.6 (true revenue spec §9.2, §10.4): navigant's captured credits are not the money its bank total counts (its
    # verified_revenue_established is false, as the Monthly Statements' True deposits already said), so the
    # package's verified total is N/A rather than a sum that includes a partial figure.
    assert package["totals"]["verified_revenue_total"] is None
    assert package["totals"]["revenue_unestablished_documents"] == ["new-corpus-navigant"]
    assert package["totals"]["unverified_deposit_total"] == 114144.70
```

In `tests/test_webapp_app.py` (lines 400-402), replace:

```python
    assert totals["package_withholding_rate"] == 6.82
    assert totals["decision"] == "approved"
    assert body["funders"] == [{"funder": "ONDECK", "documents": 2, "total_debited": 1500.0}]
```

with:

```python
    assert totals["package_withholding_rate"] == 6.82
    # 5.6 (true revenue spec §9.2): a member with no ledger rows and no verified key has no established verified
    # revenue (the `true_revenue` fallback is gone), so the package's verified total is N/A and it needs review.
    assert totals["verified_revenue_total"] is None
    assert totals["revenue_unestablished_documents"] == sorted([job1.id, job2.id])
    assert totals["decision"] == "review_required"
    assert body["funders"] == [{"funder": "ONDECK", "documents": 2, "total_debited": 1500.0}]
```

- [ ] **Step 7: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-WEBAPP: `856 passed`
  - SEL-REVENUE: `684 passed`

- [ ] **Step 8: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add analysis/revenue_view.py tests/test_lender_insurance_classification.py tests/test_new_statement_corpus.py tests/test_package_currency.py tests/test_webapp_app.py tests/test_webapp_true_revenue.py tools/l1s3_surface_census.py webapp/app.py
git commit -m "webapp: the served revenue flags and the package's true revenue (5.6)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S5.2: Exports, the review routes and the replay

**Files:**
- Modify: `webapp/app.py:387-392, 395-398, 404-406, 441-445, 451-455, 2598-2600`
- Modify: `webapp/reanalysis.py:151-157, 196-200`
- Modify (pins): `tests/test_privacy3_boundaries.py:1420-1422, 1457-1460`
- Modify (pins): `tests/test_webapp_true_revenue.py:125`

**Depends on:** S5.1.

**Interfaces:**
- Consumes: S5.1, S4.4's writer and refusals.
- Produces:
  - `_TIER_REASON_KEYS`, `_tier_reason_rows(figures, section="revenue_tier") -> list[tuple[str, str, object]]`
  - `_DECLARED_REVIEW_REFUSALS` (ten)
  - `webapp/reanalysis.py`: `_awaits_review(record, decision) -> bool`

**Why:** Spec §10.7 and §10.8: the by-reason figures are exported as readable rows (section `revenue_tier`, field `<tier>.<reason>.count` / `.total`) in the statement and package CSV/XLSX; the three new refusals are declared review refusals; and `_awaits_review(record, decision)` replays an analyst's reject of a rule-verified row while a confirm of one is reported as decided by the rules.

- [ ] **Step 1: Write the failing tests.**

Append to the end of `tests/test_webapp_true_revenue.py`:

```python
def test_the_exports_write_the_by_reason_figures_as_readable_rows():
    from webapp.app import _analysis_rows, _package_rows
    rows = _analysis_rows(_payload())
    assert ("revenue_tier", "excluded_pending_review.financing_named_payer.total", 900.0) in rows
    assert ("revenue_tier", "counted_flagged.check_deposit.count", 1) in rows
    assert not any(field == "counted_flagged_by_reason" for _section, field, _value in rows)
    package_rows = _package_rows(_package(_payload()))
    assert ("revenue_tier", "excluded_pending_review.financing_named_payer.total", 900.0) in package_rows
    assert ("document_1.revenue_tier", "counted_flagged.check_deposit.total", 300.0) in package_rows


def test_the_review_routes_reject_a_rule_verified_credit_and_refuse_its_confirm():
    from webapp.app import app, store
    job = store.create("true-revenue.pdf")
    store.set_result(job.id, "# Fabricated", "<p>Fabricated</p>", analysis=_payload())
    client = app.test_client()
    refused = client.post(f"/analysis/{job.id}/revenue-review",
                          json={"source_location": "transaction:1", "decision": "confirm"})
    assert refused.status_code == 400
    assert refused.get_json()["error"] == "a credit a rule verified can only be marked non-revenue"
    rejected = client.post(f"/analysis/{job.id}/revenue-review",
                           json={"source_location": "transaction:1", "decision": "reject"})
    record = rejected.get_json()["analysis"]["statement"]["transactions"][0]["classification"]
    assert (record["revenue_classification"], record["revenue_tier"]) == ("non_revenue", "non_revenue")
    confirmed = client.post(f"/analysis/{job.id}/revenue-reviews",
                            json={"decisions": [{"source_location": "transaction:3", "decision": "confirm"}]})
    metrics = confirmed.get_json()["analysis"]["metrics"]
    assert (metrics["verified_revenue_total"], metrics["excluded_pending_review_total"]) == (900.0, 0.0)


def test_a_rule_verified_row_awaits_only_a_reject_on_replay():
    import json
    from webapp.reanalysis import _awaits_review, replay_reviews

    payload = _payload()
    verified = payload["statement"]["transactions"][0]["classification"]
    assert _awaits_review(verified, "reject") and not _awaits_review(verified, "confirm")
    counted = payload["statement"]["transactions"][1]["classification"]
    assert _awaits_review(counted, "confirm") and _awaits_review(counted, "reject")
    prior = json.dumps(verified)
    history = [{"id": 7, "source_location": "transaction:1", "decision": "reject", "prior_state": prior,
                "decided_at": "2031-04-01T00:00:00+00:00"},
               {"id": 8, "source_location": "transaction:1", "decision": "confirm", "prior_state": prior,
                "decided_at": "2031-03-31T00:00:00+00:00"}]
    replay = replay_reviews(_payload(), history[:1])
    assert replay.replayed == (7,)
    assert replay.analysis["statement"]["transactions"][0]["classification"]["revenue_tier"] == "non_revenue"
    ruled = replay_reviews(_payload(), history[1:])
    assert (ruled.replayed, ruled.not_replayed, ruled.decided_by_rules) == ((), (), (8,))
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_webapp_true_revenue.py -q -p no:cacheprovider`

Expected: FAIL: `3 failed, 6 passed`, the first with `AssertionError: assert ('revenue_tier', 'excluded_pending_review.financing_named_payer.total', 900.0) in [('statement', 'bank', 'FABRICATED COMMUNITY BANK'), ('statement', 'account_name', 'CONTOSO …`.

- [ ] **Step 3: Implement.**

In `webapp/app.py` (lines 387-392), replace:

```python
                if (section, key) in _EXPORT_SUPPRESSED_KEYS:
                    continue
                if section == "metrics" and key == "adb":
                    continue  # emitted as its own section below
                if isinstance(item, (dict, list)):
                    item = json.dumps(item)
```

with:

```python
                if (section, key) in _EXPORT_SUPPRESSED_KEYS:
                    continue
                if section == "metrics" and key in ("adb", *_TIER_REASON_KEYS):
                    continue  # emitted as their own sections below
                if isinstance(item, (dict, list)):
                    item = json.dumps(item)
```

In `webapp/app.py` (lines 395-398), replace:

```python
    if isinstance(metrics, dict):
        rows.extend(_adb_rows(metrics))
    detection = analysis.get("detection")
    if isinstance(detection, dict):
```

with:

```python
    if isinstance(metrics, dict):
        rows.extend(_adb_rows(metrics))
        rows.extend(_tier_reason_rows(metrics))
    detection = analysis.get("detection")
    if isinstance(detection, dict):
```

In `webapp/app.py` (lines 404-406), replace:

```python
            rows.append(("detection", key, "" if item is None else item))
        rows.extend(_flagged_position_rows(detection.get("flagged_positions")))
    return rows

```

with:

```python
            rows.append(("detection", key, "" if item is None else item))
        rows.extend(_flagged_position_rows(detection.get("flagged_positions")))
    return rows


#: 5.6 (true revenue spec §10.8): the by-reason figures of the counted and held tiers, exported as readable rows.
_TIER_REASON_KEYS = ("counted_flagged_by_reason", "excluded_pending_review_by_reason")


def _tier_reason_rows(figures: dict, section: str = "revenue_tier") -> list[tuple[str, str, object]]:
    """One row per tier, reason and figure: `(revenue_tier, <tier>.<reason>.count | .total, value)`. A reason code
    is a constant of analysis/revenue.py; the rows still reach a file only through `_escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    for key in _TIER_REASON_KEYS:
        reasons = figures.get(key)
        tier = key[: -len("_by_reason")]
        for reason, slot in (reasons.items() if isinstance(reasons, dict) else ()):
            for field in ("count", "total"):
                value = slot.get(field) if isinstance(slot, dict) else None
                rows.append((section, f"{tier}.{reason}.{field}", "" if value is None else value))
    return rows

```

In `webapp/app.py` (lines 441-445), replace:

```python
    totals = package.get("totals") or {}
    for key, value in totals.items():
        rows.append(("totals", key, "" if value is None else value))
    # CURRENCY DOCTRINE §F: a refusal that only exists in the JSON payload is
    # invisible to the underwriter reading the sheet, who would see the empty
```

with:

```python
    totals = package.get("totals") or {}
    for key, value in totals.items():
        if key in _TIER_REASON_KEYS:
            continue  # emitted as readable rows below
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append(("totals", key, "" if value is None else value))
    rows.extend(_tier_reason_rows(totals))
    # CURRENCY DOCTRINE §F: a refusal that only exists in the JSON payload is
    # invisible to the underwriter reading the sheet, who would see the empty
```

In `webapp/app.py` (lines 451-455), replace:

```python
    for idx, document in enumerate(package.get("documents") or [], start=1):
        for key, value in document.items():
            rows.append((f"document_{idx}", key, "" if value is None else value))
    # D-3: duplicate content must survive into the export an underwriter reads,
    # not only the JSON payload the dashboard renders.
```

with:

```python
    for idx, document in enumerate(package.get("documents") or [], start=1):
        for key, value in document.items():
            if key in _TIER_REASON_KEYS:
                continue  # emitted as readable rows below
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            rows.append((f"document_{idx}", key, "" if value is None else value))
        rows.extend(_tier_reason_rows(document, f"document_{idx}.revenue_tier"))
    # D-3: duplicate content must survive into the export an underwriter reads,
    # not only the JSON payload the dashboard renders.
```

In `webapp/app.py` (lines 2598-2600), replace:

```python
    "account was not found",
    "transaction source location is in more than one account; name the account",
)

```

with:

```python
    "account was not found",
    "transaction source location is in more than one account; name the account",
    # 5.6 (true revenue spec §10.7, §12): a confirm on a rule-verified credit; a record whose state and tier disagree;
    # a payload whose posted credits carry a tier only in part.
    "a credit a rule verified can only be marked non-revenue",
    "every posted credit's revenue state must agree with its tier",
    "every posted credit carries a revenue tier, or none does",
)

```

In `webapp/reanalysis.py` (lines 151-157), replace:

```python


def _awaits_review(record: Mapping) -> bool:
    """The row is a deposit the analyst decides, not one a rule decided: the review writer refuses any other
    (analysis/revenue.py), so the analyst could not redo a decision on it."""
    initial = record.get("revenue_initial_classification")
    return LEGACY_REVENUE_STATE_MAP.get(initial, initial) == "unverified_deposit"


```

with:

```python


def _awaits_review(record: Mapping, decision: object) -> bool:
    """The row awaits this decision (true revenue spec §10.7): a deposit the rules left unverified awaits any
    decision, as it always has; a credit a rule verified (5.6, a record with a tier) awaits only a reject, because the
    analyst's word wins over a rule. A confirm on a rule-verified row, or any decision on a row a non-revenue rule
    decided, does not await review: the review writer would refuse it (analysis/revenue.py), so it is reported as
    decided by the rules, never as needing redoing."""
    initial = record.get("revenue_initial_classification")
    initial = LEGACY_REVENUE_STATE_MAP.get(initial, initial)
    if initial == "unverified_deposit":
        return True
    return initial == "verified_revenue" and decision == "reject" and isinstance(record.get("revenue_tier"), str)


```

In `webapp/reanalysis.py` (lines 196-200), replace:

```python
            continue
        number, record = places[0]
        if not _awaits_review(record):
            ruled.append(index)
            continue
```

with:

```python
            continue
        number, record = places[0]
        if not _awaits_review(record, history[index].get("decision")):
            ruled.append(index)
            continue
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_webapp_true_revenue.py -q -p no:cacheprovider`

Expected: PASS: `9 passed`.

- [ ] **Step 5: Re-pin the assertions this task moves (pin ledger rows 37-38).**

In `tests/test_privacy3_boundaries.py` (lines 1420-1422), replace:

```python
        "p1:r1", "confirm",
    ),
}

```

with:

```python
        "p1:r1", "confirm",
    ),
    # 5.6 (true revenue spec §10.7, §12): a confirm on a credit a rule verified, a record whose tier disagrees with
    # its state, and a payload whose posted credits carry a tier only in part.
    "a credit a rule verified can only be marked non-revenue": (
        _analysis_with([
            _reviewable("p1:r1", revenue_initial_classification="verified_revenue",
                        revenue_classification="verified_revenue", revenue_tier="verified",
                        revenue_initial_tier="verified"),
        ]),
        "p1:r1", "confirm",
    ),
    "every posted credit's revenue state must agree with its tier": (
        _analysis_with([
            _reviewable("p1:r1", revenue_tier="counted_flagged", revenue_initial_tier="counted_flagged"),
            {"amount": 250.0, "classification": {
                "source_location": "p1:r2", "revenue_classification": "unverified_deposit",
                "revenue_tier": "verified", "is_posted": True,
            }},
        ]),
        "p1:r1", "confirm",
    ),
    "every posted credit carries a revenue tier, or none does": (
        _analysis_with([
            _reviewable("p1:r1", revenue_tier="counted_flagged", revenue_initial_tier="counted_flagged"),
            _reviewable("p1:r2"),
        ]),
        "p1:r1", "confirm",
    ),
}

```

In `tests/test_privacy3_boundaries.py` (lines 1457-1460), replace:

```python
    assert "rebuild_serialized_revenue_views(analysis)" in source
    # Five, and two more since the review can name its account (a missing
    # account, and a location held by several accounts with none named).
    assert len(webapp_app._DECLARED_REVIEW_REFUSALS) == 7


```

with:

```python
    assert "rebuild_serialized_revenue_views(analysis)" in source
    # Five, and two more since the review can name its account (a missing
    # account, and a location held by several accounts with none named), and
    # three more since 5.6's tiers (a confirm on a rule-verified credit, a tier
    # that disagrees with its state, a payload tiered only in part).
    assert len(webapp_app._DECLARED_REVIEW_REFUSALS) == 10


```

- [ ] **Step 6: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-WEBAPP: `859 passed`
  - SEL-REVENUE: `687 passed`

  Then the full suite: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests -q -p no:cacheprovider`. Expected: only the 16 known failures of `C:/Users/GustavoPrietodePaula/lender-research/census/failed-ld-final.txt` (measured at this task's commit: 14,070 passed, 55 skipped, 39 deselected, 16 failed).

- [ ] **Step 7: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add tests/test_privacy3_boundaries.py tests/test_webapp_true_revenue.py webapp/app.py webapp/reanalysis.py
git commit -m "webapp: true-revenue exports, review refusals and the decision-aware replay (5.6)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## S6: Dashboard

### Task S6.1: The revenue cards, the credit mix and the Held for Review view

**Files:**
- Create: `tests/test_webapp_true_revenue_ui.py`
- Modify: `webapp/static/app.js:174-181, 188-193, 1364-1372, 1445, 1458, 1570-1577, 1594-1601, 1850-1874, 2312-2329, 2671-2677, 2687-2690, 2708-2713, 3229-3234, 3245-3246, 3275-3282, 3354, 3724-3728`
- Modify: `webapp/templates/index.html:42-44, 80-82, 444, 510, 632, 925, 965`
- Modify (pins): `tests/test_revenue_classification.py:831-835`

**Depends on:** S5.2.

**Interfaces:**
- Consumes: S5.1's served keys and flags; `REVENUE_TIER_REASONS` (for the parity test).
- Produces:
  - `REVENUE_METRIC_COPY` (`trueRevenue`, `verifiedRevenue`, `countedFlagged`, `heldForReview`, `nonRevenue`)
  - `REVENUE_TIER_REASONS` (JS: code -> [tier, label, sentence]), `revenueReasonLabel(record)`
  - `revenueCardItems(source, currency, {established, verifiedEstablished, note, unestablishedNote, counts})`, `packageRevenueFlags(totals)`, `packageUnestablishedNote(totals, outdated)`, `heldReasonEntries(source)`
  - the chip tone `teal` and the CSS tokens `--teal`, `--teal-soft`, `--verified`

**Why:** Spec §10.1, §10.4, §10.5, §10.7: True Revenue is the first and larger card, Verified beside it with its share of True, then Counted, Held and Non-Revenue (the Unverified Deposits and Revenue Upper Bound cards go); every True, Counted and Held figure reads N/A unless the server set `revenue_established`, Verified unless `verified_revenue_established`; an outdated statement says "Re-analyze to compute true revenue" and a package names its unestablished members; the credit mix shows the four tiers; the Revenue evidence panel lists the held reasons, largest first (the Held for Review view); the badge counts the held credits (`revenue_review_items`). The reason table mirrors `REVENUE_TIER_REASONS`.

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_webapp_true_revenue_ui.py`:

```python
"""True revenue spec §10 (S6): the dashboard's revenue cards and their N/A rules, the credit mix and the Held for Review
view, the ledger's tags, chips, filters and review controls, the Monthly Statements and the chart. The whole
webapp/static/app.js runs in node on a fake page (tests/webapp_js_harness.py). Fabricated statements only, analysed
by the real analysis path; every amount is whole dollars."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from tests.test_webapp_studio_views import CELLS, _package, _serve
from tests.test_webapp_true_revenue import _payload, _untiered
from tests.webapp_js_harness import NODE, run_dashboard

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

METRIC_ROWS = r"""
const metricRows = (html) => [...html.matchAll(/<(button|div) class="metric-row([^"]*)"[^>]*>([\s\S]*?)<\/\1>/g)]
  .map((m) => ({headline: m[2].includes("metric-headline"),
    label: (m[3].match(/<span class="metric-label">([^<]*)<\/span>/) || [])[1],
    value: (m[3].match(/<span class="metric-value[^"]*">([^<]*)<\/span>/) || [])[1],
    note: (m[3].match(/<span class="metric-note">([^<]*)<\/span>/) || [])[1] || ""}));
const cells = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)]
  .map((row) => [...row[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)].map((cell) => cell[1].replace(/<[^>]+>/g, "").trim()));
"""


def _served(payload):
    from webapp.app import _displayed
    return _displayed(payload, settings={})


def _open(job_id, payload):
    return _serve(**{job_id: payload}) + f"""
currentJobId = '{job_id}'; currentJobIds = ['{job_id}']; loadResults('{job_id}'); await settle();
"""


# ---------------------------------------------------------------- S6.1: cards, N/A, credit mix, Held for Review view

def _js_reasons():
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    block = source[source.index("const REVENUE_TIER_REASONS = Object.freeze({"):]
    block = block[:block.index("});")]
    return {code: (tier, label) for code, tier, label, _sentence in re.findall(
        r'^\s*([a-z_0-9]+): \["([a-z_]+)", "([^"]+)", "([^"]+)"\],$', block, re.M)}


def test_the_dashboard_reason_table_mirrors_the_analysis():
    from analysis.revenue import REVENUE_TIER_REASONS

    assert _js_reasons() == {code: tuple(entry) for code, entry in REVENUE_TIER_REASONS.items()}


@needs_node
def test_a_statement_shows_true_revenue_first_and_its_parts():
    result = run_dashboard(METRIC_ROWS + _open("s", _served(_payload())) + """
console.log(JSON.stringify({rows: metricRows(els.metricsGrid.innerHTML), meta: els.creditsMeta.innerHTML,
  badge: [els.reviewCount.hidden, els.reviewCount.textContent], evidence: cells(els.revenueTable.innerHTML)}));
""")
    rows = result["rows"]
    labels = [row["label"] for row in rows]
    assert labels[:7] == ["True Revenue", "Verified Revenue", "Counted, Not Verified", "Held for Review", "Non-Revenue",
                          "Total Credits", "ACH Credits"]
    assert "Unverified Deposits" not in labels and "Revenue Upper Bound" not in labels
    figures = {row["label"]: row for row in rows}
    assert figures["True Revenue"]["headline"] and not figures["Verified Revenue"]["headline"]
    assert [figures[label]["value"] for label in ("True Revenue", "Verified Revenue", "Counted, Not Verified",
                                                  "Held for Review", "Non-Revenue")] == [
        "$1,000.00", "$700.00", "$300.00", "$900.00", "$100.00"]
    assert figures["Verified Revenue"]["note"].startswith("70.0% of true revenue · Revenue with proof")
    assert figures["True Revenue"]["note"] == "Posted credits minus known non-revenue and the deposits held for review"
    assert "True revenue" in result["meta"] and "$1,000.00" in result["meta"]
    assert result["badge"] == [False, "1"]  # the held credit, not every unverified deposit
    evidence = result["evidence"]
    assert [row[0] for row in evidence] == ["True Revenue", "Verified Revenue", "Counted, Not Verified",
                                            "Held for Review", "Payer or entry suggests financing", "Non-Revenue"]
    assert evidence[4][1:3] == ["1", "$900.00"]


@needs_node
def test_an_older_statement_reads_n_a_for_true_counted_and_held():
    older = {**_served(_untiered(_payload())), "analysis_rules_outdated": True}
    result = run_dashboard(METRIC_ROWS + _open("o", older) + """
console.log(JSON.stringify({rows: metricRows(els.metricsGrid.innerHTML), mix: els.creditMixRows.innerHTML,
  bar: els.creditMixBar.getAttribute('aria-label'), badge: els.reviewCount.textContent}));
""")
    figures = {row["label"]: row for row in result["rows"]}
    assert [figures[label]["value"] for label in ("True Revenue", "Counted, Not Verified", "Held for Review")] == [
        "N/A"] * 3
    assert figures["True Revenue"]["note"] == "Re-analyze to compute true revenue"
    assert figures["Verified Revenue"]["value"] == "$700.00"  # the stored figure, under the outdated notice
    assert result["bar"] == "Credit mix unavailable"
    assert result["badge"] == "2"  # before 5.6 the badge counts the deposits left unverified


@needs_node
def test_a_statement_whose_credits_are_not_its_total_reads_n_a():
    payload = _served(_payload())
    payload["metrics"]["revenue_established"] = payload["metrics"]["verified_revenue_established"] = False
    result = run_dashboard(METRIC_ROWS + _open("n", payload) + """
console.log(JSON.stringify({rows: metricRows(els.metricsGrid.innerHTML)}));
""")
    figures = {row["label"]: row["value"] for row in result["rows"]}
    assert [figures[label] for label in ("True Revenue", "Verified Revenue", "Counted, Not Verified",
                                         "Held for Review")] == ["N/A"] * 4
    assert figures["Non-Revenue"] == "$100.00"


@needs_node
def test_a_package_with_an_older_member_names_it_and_reads_n_a(tmp_path, monkeypatch):
    package = _package({"new": _payload(), "old": _untiered(_payload(month=4))}, tmp_path, monkeypatch)
    package["analysis_rules_outdated"] = True
    result = run_dashboard(METRIC_ROWS + f"""
currentJobIds = ['new', 'old']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{grid: els.metricsGrid.innerHTML, rows: metricRows(els.metricsGrid.innerHTML)}}));
""")
    figures = {row["label"]: row["value"] for row in result["rows"]}
    assert [figures[label] for label in ("True Revenue", "Counted, Not Verified", "Held for Review")] == ["N/A"] * 3
    assert figures["Verified Revenue"] == "$1,400.00"
    assert "1 of 2 statements has no established revenue · Re-analyze to compute true revenue" in result["grid"]
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_webapp_true_revenue_ui.py -q -p no:cacheprovider`

Expected: FAIL: `5 failed`, the first with `ValueError: substring not found`.

- [ ] **Step 3: Implement.**

In `webapp/static/app.js` (lines 174-181), replace:

```javascript
const REVENUE_METRIC_COPY = Object.freeze({
  totalCredits: "All posted credit transactions",
  verifiedRevenue: "Confirmed operating revenue",
  unverifiedDeposits: "Deposits requiring analyst review",
  nonRevenue: "Excluded from revenue analysis",
  revenueUpperBound: "Upper-bound estimate: verified revenue plus unverified deposits",
  achCredits: "Posted ACH credit transactions",
});
```

with:

```javascript
// 5.6 (true revenue spec §10.5): the note under each revenue figure.
const REVENUE_METRIC_COPY = Object.freeze({
  totalCredits: "All posted credit transactions",
  trueRevenue: "Posted credits minus known non-revenue and the deposits held for review",
  verifiedRevenue: "Revenue with proof: settlements, platform payouts, repeat or institutional payers, invoices, and deposits you confirmed",
  countedFlagged: "Counted in true revenue without proof of the payer: cash, checks, person-to-person, one-off payers",
  heldForReview: "Kept out of true revenue until you confirm it",
  nonRevenue: "Own-account transfers, funding, refunds and other known non-revenue",
  achCredits: "Posted ACH credit transactions",
});

// 5.6 (true revenue spec §5.3, §10.6): the reason codes of the two middle tiers, code -> [tier, label, sentence]. It
// mirrors analysis/revenue.py REVENUE_TIER_REASONS (code -> tier and label); tests/test_webapp_true_revenue_ui.py
// holds the two equal. The sentence is the ledger's one line on the code.
const REVENUE_TIER_REASONS = Object.freeze({
  direction_conflict: ["excluded_pending_review", "Direction conflicts with the amount", "The bank prints this row in the other direction from its amount."],
  insurer_payer: ["excluded_pending_review", "Insurance carrier", "An insurance carrier paid it: a claim or a refund unless you confirm it pays for a sale."],
  insurer_named_payer: ["excluded_pending_review", "Payer name reads as an insurer", "The payer's name reads as an insurer."],
  possible_return: ["excluded_pending_review", "Possible return or adjustment", "The row reads as a return, a reversal or an adjustment of an earlier item."],
  financing_named_payer: ["excluded_pending_review", "Payer or entry suggests financing", "The payer or the entry names funding, a loan or an advance."],
  payer_debited_as_lender: ["excluded_pending_review", "Payer is also debited as a lender", "This payer is also debited from the account as a lender."],
  holder_name: ["excluded_pending_review", "From the holder's own name or brand", "The credit comes from the account holder's own name or brand."],
  payroll_or_salary: ["excluded_pending_review", "Payroll, salary or employee reimbursement", "The entry reads as payroll, salary or an employee reimbursement."],
  personal_income: ["excluded_pending_review", "Benefit or pension", "The entry reads as a benefit or a pension."],
  non_sale_purpose: ["excluded_pending_review", "Not a sale: owner money, investment, grant, refund, claim or interest", "The entry names owner money, an investment, a grant, a refund, a claim or interest."],
  payer_also_debited: ["excluded_pending_review", "Payer also debited this account", "The same payer is also debited from this account."],
  wire_no_sender: ["excluded_pending_review", "Wire, no sender printed", "A wire with no sender printed."],
  transfer_no_counterparty: ["excluded_pending_review", "Transfer, no counterparty", "A transfer that names no counterparty."],
  transfer_account_designation: ["excluded_pending_review", "Transfer naming an account", "A transfer that names an account, not a payer."],
  p2p_round_repeat: ["excluded_pending_review", "Repeated round sums from one sender", "Round sums repeated by one person-to-person sender."],
  wire_named_sender: ["counted_flagged", "Wire from a named sender", "A wire from a named sender, counted without proof of the sale."],
  check_deposit: ["counted_flagged", "Check deposit", "A check deposit: the payer is not printed."],
  no_payer_printed: ["counted_flagged", "No payer printed", "A cash, branch, ATM or bare deposit: no payer is printed."],
  p2p: ["counted_flagged", "Person-to-person", "A person-to-person payment."],
  factoring_payout: ["counted_flagged", "Factoring payout", "A factor's payout of the business's own invoices."],
  payout_credit_entity: ["counted_flagged", "Platform payout (financing partner)", "A payout from a platform's financing partner."],
  platform_unconfirmed: ["counted_flagged", "Platform payout, not confirmed", "A registered platform's payout without the context that confirms it."],
  numbered_company_payer: ["counted_flagged", "Numbered company payer", "A numbered company paid it: counted, never verified."],
  named_payer_purpose_refused: ["counted_flagged", "Named payer, purpose not accepted as proof", "A named payer whose printed purpose is not accepted as proof."],
  named_payer_one_off: ["counted_flagged", "One-off payer", "A named payer seen once on this statement."],
  named_payer_unlabelled: ["counted_flagged", "Payer named, channel not printed", "A named payer on a channel the bank does not print."],
});

function revenueReasonLabel(record) {
  const entry = REVENUE_TIER_REASONS[record && record.revenue_tier_reason];
  return entry ? entry[1] : "Reason not recorded";
}
```

In `webapp/static/app.js` (lines 188-193), replace:

```javascript
      ["Total Credits", "N/A", REVENUE_METRIC_COPY.totalCredits, "CR", "green"],
      ["Verified Revenue", "N/A", REVENUE_METRIC_COPY.verifiedRevenue, "REV", "green"],
      ["Unverified Deposits", "N/A", REVENUE_METRIC_COPY.unverifiedDeposits, "?", "amber"],
      ["Non-Revenue", "N/A", REVENUE_METRIC_COPY.nonRevenue, "X", "neutral"],
      ["Revenue Upper Bound", "N/A", REVENUE_METRIC_COPY.revenueUpperBound, "MAX", "neutral"],
      ["ACH Credits", "N/A", REVENUE_METRIC_COPY.achCredits, "ACH", "neutral"],
```

with:

```javascript
      ["True Revenue", "N/A", REVENUE_METRIC_COPY.trueRevenue, "REV", "green", { headline: true }],
      ["Verified Revenue", "N/A", REVENUE_METRIC_COPY.verifiedRevenue, "VER", "green"],
      ["Counted, Not Verified", "N/A", REVENUE_METRIC_COPY.countedFlagged, "CNT", "teal"],
      ["Held for Review", "N/A", REVENUE_METRIC_COPY.heldForReview, "?", "amber"],
      ["Non-Revenue", "N/A", REVENUE_METRIC_COPY.nonRevenue, "X", "neutral"],
      ["Total Credits", "N/A", REVENUE_METRIC_COPY.totalCredits, "CR", "neutral"],
      ["ACH Credits", "N/A", REVENUE_METRIC_COPY.achCredits, "ACH", "neutral"],
```

In `webapp/static/app.js` (lines 1364-1372), replace:

```javascript
  renderRevenueEvidence({
    total_posted_credit_count: 0,
    verified_revenue_count: 0,
    verified_revenue_total: 0,
    unverified_deposit_count: 0,
    unverified_deposit_total: 0,
    non_revenue_count: 0,
    non_revenue_total: 0,
  });
```

with:

```javascript
  renderRevenueEvidence({
    total_posted_credit_count: 0,
    revenue_established: true,
    verified_revenue_established: true,
    true_revenue_count: 0,
    true_revenue_total: 0,
    verified_revenue_count: 0,
    verified_revenue_total: 0,
    counted_flagged_count: 0,
    counted_flagged_total: 0,
    excluded_pending_review_count: 0,
    excluded_pending_review_total: 0,
    non_revenue_count: 0,
    non_revenue_total: 0,
  });
```

In `webapp/static/app.js` (line 1445), replace:

```javascript
  MAX: ["", "Upper Bound"],
```

with:

```javascript
  VER: ["✓", "Verified"],
  CNT: ["+", "Counted"],
```

In `webapp/static/app.js` (line 1458), replace:

```javascript
const CHIP_TONES = { green: "success", red: "error", blue: "info", amber: "warning", violet: "violet", neutral: "neutral" };
```

with:

```javascript
const CHIP_TONES = { green: "success", red: "error", blue: "info", amber: "warning", violet: "violet", teal: "teal", neutral: "neutral" };
```

In `webapp/static/app.js` (lines 1570-1577), replace:

```javascript
function renderMetricCard([label, value, sub, icon, tone, action]) {
  const actionable = action && action.revenueFilter;
  const tag = actionable ? "button" : "article";
  const attributes = actionable
    ? ` type="button" data-revenue-filter="${escapeHtml(action.revenueFilter)}" aria-label="Show exact ${escapeHtml(label)} transactions"`
    : "";
  return `
    <${tag} class="metric${actionable ? " metric-action" : ""}"${attributes}>
```

with:

```javascript
function renderMetricCard([label, value, sub, icon, tone, action]) {
  const actionable = action && action.revenueFilter;
  const tag = actionable ? "button" : "article";
  const attributes = actionable
    ? ` type="button" data-revenue-filter="${escapeHtml(action.revenueFilter)}" aria-label="Show exact ${escapeHtml(label)} transactions"`
    : "";
  const headline = action && action.headline ? " metric-headline" : "";
  return `
    <${tag} class="metric${actionable ? " metric-action" : ""}${headline}"${attributes}>
```

In `webapp/static/app.js` (lines 1594-1601), replace:

```javascript
function metricRowHtml([label, value, sub, , tone, action]) {
  const actionable = action && action.revenueFilter;
  const tag = actionable ? "button" : "div";
  const attributes = actionable
    ? ` type="button" data-revenue-filter="${escapeHtml(action.revenueFilter)}" aria-label="Show exact ${escapeHtml(label)} transactions"`
    : "";
  return `
    <${tag} class="metric-row"${attributes}>
```

with:

```javascript
function metricRowHtml([label, value, sub, , tone, action]) {
  const actionable = action && action.revenueFilter;
  const tag = actionable ? "button" : "div";
  const attributes = actionable
    ? ` type="button" data-revenue-filter="${escapeHtml(action.revenueFilter)}" aria-label="Show exact ${escapeHtml(label)} transactions"`
    : "";
  // 5.6 (true revenue spec §10.1): True Revenue is the headline, first and larger.
  const headline = action && action.headline ? " metric-headline" : "";
  return `
    <${tag} class="metric-row${headline}"${attributes}>
```

In `webapp/static/app.js` (lines 1850-1874), replace:

```javascript
const revenueRows = [
  ["verified_revenue", "Verified Revenue", "REV", "Verified", "green"],
  ["unverified_deposit", "Unverified Deposits", "?", "Review Required", "amber"],
  ["non_revenue", "Non-Revenue", "X", "Excluded", "neutral"],
];

function revenueEvidenceRowsHtml(metrics = {}, currency = "USD", modal = false) {
  return revenueRows.map(([state, label, glyph, status, tone]) => {
    const countKey = state === "verified_revenue"
      ? "verified_revenue_count"
      : `${state}_count`;
    const totalKey = state === "verified_revenue"
      ? "verified_revenue_total"
      : `${state}_total`;
    const filterAttribute = modal ? "data-modal-revenue-filter" : "data-revenue-filter";
    return `
      <tr>
        <td><button class="evidence-link" type="button" ${filterAttribute}="${state}" aria-label="Show exact ${escapeHtml(label)} transactions">${escapeHtml(label)}</button></td>
        <td>${escapeHtml(formatNumber(metrics[countKey]))}</td>
        <td>${escapeHtml(formatMoney(metrics[totalKey], currency))}</td>
        <td>${glassChip(glyph, status, tone)}</td>
      </tr>
    `;
  }).join("");
}
```

with:

```javascript
// 5.6 (true revenue spec §10.1, §10.7): the Revenue evidence rows, [filter, label, glyph, status, tone, which flag
// establishes the figure]. Held for Review is followed by its reasons, largest total first: the Held for Review view.
const revenueRows = [
  ["true_revenue", "True Revenue", "REV", "Revenue", "green", "revenue_established"],
  ["verified_revenue", "Verified Revenue", "VER", "Verified", "green", "verified_revenue_established"],
  ["counted_flagged", "Counted, Not Verified", "CNT", "Counted", "teal", "revenue_established"],
  ["excluded_pending_review", "Held for Review", "?", "Review Required", "amber", "revenue_established"],
  ["non_revenue", "Non-Revenue", "X", "Excluded", "neutral", null],
];

// The held credits of a statement or a package by reason, largest total first (ties by code), or [] where they are
// not established.
function heldReasonEntries(source = {}) {
  const byReason = source && source.revenue_established === true && source.excluded_pending_review_by_reason
    && typeof source.excluded_pending_review_by_reason === "object" ? source.excluded_pending_review_by_reason : {};
  return Object.entries(byReason)
    .map(([reason, figures]) => ({ reason, count: figures && figures.count, total: numberOrNull(figures && figures.total) }))
    .sort((a, b) => (b.total ?? 0) - (a.total ?? 0) || a.reason.localeCompare(b.reason));
}

function revenueEvidenceRowsHtml(metrics = {}, currency = "USD", modal = false) {
  const filterAttribute = modal ? "data-modal-revenue-filter" : "data-revenue-filter";
  return revenueRows.map(([filter, label, glyph, status, tone, flag]) => {
    const shown = flag === null || metrics[flag] === true;
    const row = `
      <tr>
        <td><button class="evidence-link" type="button" ${filterAttribute}="${filter}" aria-label="Show exact ${escapeHtml(label)} transactions">${escapeHtml(label)}</button></td>
        <td>${escapeHtml(shown ? formatNumber(metrics[`${filter}_count`]) : "N/A")}</td>
        <td>${escapeHtml(shown ? formatMoney(metrics[`${filter}_total`], currency) : "N/A")}</td>
        <td>${glassChip(glyph, status, tone)}</td>
      </tr>
    `;
    if (filter !== "excluded_pending_review") return row;
    return row + heldReasonEntries(metrics).map(({ reason, count, total }) => `
      <tr class="evidence-subrow">
        <td><button class="evidence-link" type="button" ${filterAttribute}="excluded_pending_review:${escapeHtml(reason)}" aria-label="Show the held ${escapeHtml(revenueReasonLabel({ revenue_tier_reason: reason }))} transactions">${escapeHtml(revenueReasonLabel({ revenue_tier_reason: reason }))}</button></td>
        <td>${escapeHtml(formatNumber(count))}</td>
        <td>${escapeHtml(formatMoney(total, currency))}</td>
        <td></td>
      </tr>
    `).join("");
  }).join("");
}
```

In `webapp/static/app.js` (lines 2312-2329), replace:

```javascript
const CREDIT_MIX = [
  ["verified_revenue", "Verified revenue", "dot-green"],
  ["unverified_deposit", "Unverified deposits", "dot-amber"],
  ["non_revenue", "Non-revenue", "dot-muted"],
];

// The three revenue classes of the posted credits, each as its share of the three together. A row is a
// button to that class's transactions, like the Revenue evidence rows.
function renderCreditMix(source = {}, currency = "USD") {
  const parts = CREDIT_MIX.map(([state, label, dot]) => ({
    state,
    label,
    dot,
    count: source[`${state}_count`],
    total: source[`${state}_total`],
    size: Math.max(numberOrNull(source[`${state}_total`]) || 0, 0),
  }));
  const sum = parts.reduce((total, part) => total + part.size, 0);
```

with:

```javascript
// 5.6 (true revenue spec §10.1): the four tiers of the posted credits.
const CREDIT_MIX = [
  ["verified_revenue", "Verified revenue", "dot-green"],
  ["counted_flagged", "Counted, not verified", "dot-teal"],
  ["excluded_pending_review", "Held for review", "dot-amber"],
  ["non_revenue", "Non-revenue", "dot-muted"],
];

// The four tiers of the posted credits, each as its share of the four together. A row is a button to that tier's
// transactions, like the Revenue evidence rows. Where revenue is not established the tiers are not known, so the
// counted and held rows read N/A and no share is drawn (§10.4).
function renderCreditMix(source = {}, currency = "USD") {
  const established = source.revenue_established === true;
  const parts = CREDIT_MIX.map(([state, label, dot]) => {
    const known = established || state === "non_revenue"
      || (state === "verified_revenue" && source.verified_revenue_established === true);
    return {
      state,
      label,
      dot,
      count: known ? source[`${state}_count`] : null,
      total: known ? source[`${state}_total`] : null,
      size: Math.max(numberOrNull(known ? source[`${state}_total`] : null) || 0, 0),
    };
  });
  const sum = established ? parts.reduce((total, part) => total + part.size, 0) : 0;
```

In `webapp/static/app.js` (lines 2671-2677), replace:

```javascript
  renderCredits({
    label: "Total credits",
    value: formatMoney(totalCredits, currency),
    meta: `${escapeHtml(formatNumber(metrics.total_posted_credit_count))} credit transactions · Revenue upper bound `
      + `<span class="mono">${escapeHtml(formatMoney(metrics.maximum_revenue, currency))}</span>`,
  });
  renderCreditMix(metrics, currency);
```

with:

```javascript
  const revenueEstablished = metrics.revenue_established === true;
  renderCredits({
    label: "Total credits",
    value: formatMoney(totalCredits, currency),
    meta: `${escapeHtml(formatNumber(metrics.total_posted_credit_count))} credit transactions · True revenue `
      + `<span class="mono">${escapeHtml(revenueEstablished ? formatMoney(metrics.true_revenue_total, currency) : "N/A")}</span>`,
  });
  renderCreditMix(metrics, currency);
```

In `webapp/static/app.js` (lines 2687-2690), replace:

```javascript
  setReviewCount(metrics.unverified_deposit_count);

  setStatusRows([
    ["OCR completed", "Yes"],
```

with:

```javascript
  // 5.6 (true revenue spec §10.7): the badge counts the held credits; an analysis saved before 5.6 has none, and keeps
  // counting its deposits left unverified.
  setReviewCount(metrics.revenue_review_items ?? metrics.unverified_deposit_count);

  setStatusRows([
    ["OCR completed", "Yes"],
```

In `webapp/static/app.js` (lines 2708-2713), replace:

```javascript
        ["Total Credits", formatMoney(totalCredits, currency), REVENUE_METRIC_COPY.totalCredits, "CR", "neutral"],
        ["Verified Revenue", formatMoney(metrics.verified_revenue_total, currency), REVENUE_METRIC_COPY.verifiedRevenue, "REV", "green", { revenueFilter: "verified_revenue" }],
        ["Unverified Deposits", formatMoney(metrics.unverified_deposit_total, currency), REVENUE_METRIC_COPY.unverifiedDeposits, "?", "amber", { revenueFilter: "unverified_deposit" }],
        ["Non-Revenue", formatMoney(metrics.non_revenue_total, currency), REVENUE_METRIC_COPY.nonRevenue, "X", "neutral", { revenueFilter: "non_revenue" }],
        ["Revenue Upper Bound", formatMoney(metrics.maximum_revenue, currency), REVENUE_METRIC_COPY.revenueUpperBound, "MAX", "neutral"],
        ["ACH Credits", formatNumber(metrics.ach_credit_count), REVENUE_METRIC_COPY.achCredits, "ACH", "neutral"],
```

with:

```javascript
        ...revenueCardItems(metrics, currency, {
          established: revenueEstablished,
          verifiedEstablished: metrics.verified_revenue_established === true,
          unestablishedNote: report.analysis_rules_outdated === true ? "Re-analyze to compute true revenue" : "",
        }),
        ["Total Credits", formatMoney(totalCredits, currency), REVENUE_METRIC_COPY.totalCredits, "CR", "neutral"],
        ["ACH Credits", formatNumber(metrics.ach_credit_count), REVENUE_METRIC_COPY.achCredits, "ACH", "neutral"],
```

In `webapp/static/app.js` (lines 3229-3234), replace:

```javascript
    meta: refusalNote
      ? escapeHtml(refusalNote)
      : `Avg monthly credits <span class="mono">${escapeHtml(formatMoney(totals.avg_monthly_credits, currency))}</span>`
        + ` · Revenue upper bound <span class="mono">${escapeHtml(formatMoney(totals.maximum_revenue, currency))}</span>`,
  });
  renderCreditMix(totals, currency);
```

with:

```javascript
    meta: refusalNote
      ? escapeHtml(refusalNote)
      : `Avg monthly credits <span class="mono">${escapeHtml(formatMoney(totals.avg_monthly_credits, currency))}</span>`
        + ` · True revenue <span class="mono">${escapeHtml(formatMoney(totals.true_revenue_total, currency))}</span>`,
  });
  renderCreditMix(packageRevenueFlags(totals), currency);
```

In `webapp/static/app.js` (lines 3245-3246), replace:

```javascript
  setReviewCount(totals.unverified_deposit_count);
  if (els.packageProcessingNote) {
```

with:

```javascript
  setReviewCount(totals.revenue_review_items ?? totals.unverified_deposit_count);
  if (els.packageProcessingNote) {
```

In `webapp/static/app.js` (lines 3275-3282), replace:

```javascript
      sub: `${formatNumber(totals.statement_periods ?? totals.months)} statement periods`,
      items: [
        ["Total Credits", formatMoney(totals.total_credits, currency), moneyNote(REVENUE_METRIC_COPY.totalCredits), "CR", "neutral"],
        ["Verified Revenue", formatMoney(totals.verified_revenue_total, currency), moneyNote(REVENUE_METRIC_COPY.verifiedRevenue), "REV", "green", { revenueFilter: "verified_revenue" }],
        ["Unverified Deposits", formatMoney(totals.unverified_deposit_total, currency), moneyNote(REVENUE_METRIC_COPY.unverifiedDeposits), "?", "amber", { revenueFilter: "unverified_deposit" }],
        ["Non-Revenue", formatMoney(totals.non_revenue_total, currency), moneyNote(REVENUE_METRIC_COPY.nonRevenue), "X", "neutral", { revenueFilter: "non_revenue" }],
        ["Revenue Upper Bound", formatMoney(totals.maximum_revenue, currency), moneyNote(REVENUE_METRIC_COPY.revenueUpperBound), "MAX", "neutral"],
        ["Avg Monthly Credits",
```

with:

```javascript
      sub: [`${formatNumber(totals.statement_periods ?? totals.months)} statement periods`,
        packageUnestablishedNote(totals, pkg.analysis_rules_outdated === true)].filter(Boolean).join(" · "),
      items: [
        ...revenueCardItems(totals, currency, { ...packageRevenueFlags(totals), note: moneyNote }),
        ["Total Credits", formatMoney(totals.total_credits, currency), moneyNote(REVENUE_METRIC_COPY.totalCredits), "CR", "neutral"],
        ["Avg Monthly Credits",
```

In `webapp/static/app.js` (lines 3724-3728), replace:

```javascript
    ["Total Credits", formatMoney(metrics.effective_total_deposits, currency), REVENUE_METRIC_COPY.totalCredits, "CR", "green"],
    ["Verified Revenue", `${formatNumber(metrics.verified_revenue_count)} / ${formatMoney(metrics.verified_revenue_total, currency)}`, REVENUE_METRIC_COPY.verifiedRevenue, "REV", "green", { revenueFilter: "verified_revenue" }],
    ["Unverified Deposits", `${formatNumber(metrics.unverified_deposit_count)} / ${formatMoney(metrics.unverified_deposit_total, currency)}`, REVENUE_METRIC_COPY.unverifiedDeposits, "?", "amber", { revenueFilter: "unverified_deposit" }],
    ["Non-Revenue", `${formatNumber(metrics.non_revenue_count)} / ${formatMoney(metrics.non_revenue_total, currency)}`, REVENUE_METRIC_COPY.nonRevenue, "X", "neutral", { revenueFilter: "non_revenue" }],
    ["Revenue Upper Bound", formatMoney(metrics.maximum_revenue, currency), REVENUE_METRIC_COPY.revenueUpperBound, "MAX", "neutral"],
```

with:

```javascript
    ...revenueCardItems(metrics, currency, {
      established: metrics.revenue_established === true,
      verifiedEstablished: metrics.verified_revenue_established === true,
      unestablishedNote: report.analysis_rules_outdated === true ? "Re-analyze to compute true revenue" : "",
      counts: true,
    }),
    ["Total Credits", formatMoney(metrics.effective_total_deposits, currency), REVENUE_METRIC_COPY.totalCredits, "CR", "neutral"],
```

In `webapp/static/app.js` (in text an earlier step of this task wrote), replace:

```javascript
function revenueReasonLabel(record) {
  const entry = REVENUE_TIER_REASONS[record && record.revenue_tier_reason];
  return entry ? entry[1] : "Reason not recorded";
}
```

with:

```javascript
function revenueReasonLabel(record) {
  const entry = REVENUE_TIER_REASONS[record && record.revenue_tier_reason];
  return entry ? entry[1] : "Reason not recorded";
}

// The revenue cards of true revenue spec §10.1, in order: True Revenue (the headline), Verified Revenue with its share
// of True, Counted, Held and Non-Revenue, each a button to its rows. `source` is a statement's metrics or a package's
// totals. A True, Counted or Held figure reads N/A unless `established`, a Verified one unless `verifiedEstablished`
// (§10.4). `note` wraps each note (a package's currency refusal replaces them); `unestablishedNote` replaces the True
// note where revenue is not established; `counts` prints "count / total", as the statement window does.
function revenueCardItems(source, currency, {
  established, verifiedEstablished, note = (text) => text, unestablishedNote = "", counts = false,
}) {
  const figure = (kind, shown) => {
    if (!shown) return "N/A";
    const total = formatMoney(source[`${kind}_total`], currency);
    return counts ? `${formatNumber(source[`${kind}_count`])} / ${total}` : total;
  };
  const trueTotal = numberOrNull(source.true_revenue_total);
  const verifiedTotal = numberOrNull(source.verified_revenue_total);
  const share = established && verifiedEstablished && trueTotal !== null && trueTotal > 0 && verifiedTotal !== null
    ? `${((verifiedTotal / trueTotal) * 100).toFixed(1)}% of true revenue · ` : "";
  const trueNote = !established && unestablishedNote ? unestablishedNote : REVENUE_METRIC_COPY.trueRevenue;
  return [
    ["True Revenue", figure("true_revenue", established), note(trueNote), "REV", "green", { revenueFilter: "true_revenue", headline: true }],
    ["Verified Revenue", figure("verified_revenue", verifiedEstablished), note(share + REVENUE_METRIC_COPY.verifiedRevenue), "VER", "green", { revenueFilter: "verified_revenue" }],
    ["Counted, Not Verified", figure("counted_flagged", established), note(REVENUE_METRIC_COPY.countedFlagged), "CNT", "teal", { revenueFilter: "counted_flagged" }],
    ["Held for Review", figure("excluded_pending_review", established), note(REVENUE_METRIC_COPY.heldForReview), "?", "amber", { revenueFilter: "excluded_pending_review" }],
    ["Non-Revenue", figure("non_revenue", true), note(REVENUE_METRIC_COPY.nonRevenue), "X", "neutral", { revenueFilter: "non_revenue" }],
  ];
}

// A package's two revenue flags (§10.4): the server nulls its True, Counted and Held totals when any completed member
// is not established, and its Verified total when any member's verified revenue is not.
function packageRevenueFlags(totals = {}) {
  return {
    ...totals,
    established: totals.true_revenue_total !== null && totals.true_revenue_total !== undefined,
    verifiedEstablished: totals.verified_revenue_total !== null && totals.verified_revenue_total !== undefined,
    revenue_established: totals.true_revenue_total !== null && totals.true_revenue_total !== undefined,
    verified_revenue_established: totals.verified_revenue_total !== null && totals.verified_revenue_total !== undefined,
  };
}

// The note under a package's revenue totals: how many completed statements have no established revenue, and, when a
// member was analysed before 5.6, what to do about it. "" when every member is established.
function packageUnestablishedNote(totals = {}, outdated = false) {
  const listed = Array.isArray(totals.revenue_unestablished_documents) ? totals.revenue_unestablished_documents : [];
  const statements = new Set(listed.map((id) => String(id).split("#")[0])).size;
  if (!statements) return "";
  const completed = numberOrNull(totals.completed) ?? statements;
  const noun = completed === 1 ? "statement" : "statements";
  return `${formatNumber(statements)} of ${formatNumber(completed)} ${noun} ${statements === 1 ? "has" : "have"} no established revenue`
    + (outdated ? " · Re-analyze to compute true revenue" : "");
}
```

In `webapp/templates/index.html` (lines 42-44), replace:

```html
    --violet: #b69cff;
    --violet-soft: rgba(182, 156, 255, .13);
    --track: #2e2e2e;
```

with:

```html
    --violet: #b69cff;
    --violet-soft: rgba(182, 156, 255, .13);
    --teal: #5eead4;
    --teal-soft: rgba(94, 234, 212, .13);
    --verified: #10b46a;
    --track: #2e2e2e;
```

In `webapp/templates/index.html` (lines 80-82), replace:

```html
    --violet: #6a47c9;
    --violet-soft: rgba(110, 70, 210, .1);
    --track: #d2d2cc;
```

with:

```html
    --violet: #6a47c9;
    --violet-soft: rgba(110, 70, 210, .1);
    --teal: #0f766e;
    --teal-soft: rgba(15, 118, 110, .12);
    --verified: #07703f;
    --track: #d2d2cc;
```

In `webapp/templates/index.html` (line 444), replace:

```html
  .dot-amber { background: var(--amber); }
```

with:

```html
  .dot-amber { background: var(--amber); }
  .dot-teal { background: var(--teal); }
```

In `webapp/templates/index.html` (line 510), replace:

```html
  .tone-violet { color: var(--violet); }
```

with:

```html
  .tone-violet { color: var(--violet); }
  .tone-teal { color: var(--teal); }
  /* 5.6: True Revenue is the headline figure of the Credits cards. */
  .metric-row.metric-headline .metric-value, .metric.metric-headline .metric-value { font-size: 20px; font-weight: 600; }
  .evidence-subrow td:first-child { padding-left: 20px; }
```

In `webapp/templates/index.html` (line 632), replace:

```html
  .glass-chip.violet { background: var(--violet-soft); color: var(--violet); }
```

with:

```html
  .glass-chip.violet { background: var(--violet-soft); color: var(--violet); }
  .glass-chip.teal { background: var(--teal-soft); color: var(--teal); }
```

In `webapp/templates/index.html` (line 965), replace:

```html
<span class="side-badge" id="reviewCount" title="Unverified deposits awaiting review" hidden>0</span>
```

with:

```html
<span class="side-badge" id="reviewCount" title="Deposits held for review" hidden>0</span>
```

In `webapp/templates/index.html` (line 925), replace:

```html
Unverified deposits can be confirmed or excluded from the Review column.</p>
```

with:

```html
Deposits held for review, and counted deposits, can be confirmed or excluded from the Review column.</p>
```

In `webapp/static/app.js` (line 3354), replace:

```javascript
  renderRevenueEvidence(pkg.totals || {}, currency);
```

with:

```javascript
  renderRevenueEvidence(packageRevenueFlags(pkg.totals || {}), currency);
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_webapp_true_revenue_ui.py -q -p no:cacheprovider`

Expected: PASS: `5 passed`.

- [ ] **Step 5: Re-pin the assertions this task moves (pin ledger row 39).**

In `tests/test_revenue_classification.py` (lines 831-835), replace:

```python
    assert "Revenue Upper Bound" in javascript
    assert "Upper-bound estimate: verified revenue plus unverified deposits" in javascript
    assert "Confirmed operating revenue" in javascript
    assert "Deposits requiring analyst review" in javascript
    assert "Excluded from revenue analysis" in javascript
```

with:

```python
    assert "Revenue Upper Bound" not in javascript
    assert "Posted credits minus known non-revenue and the deposits held for review" in javascript
    assert "Kept out of true revenue until you confirm it" in javascript
    assert "Own-account transfers, funding, refunds and other known non-revenue" in javascript
```

- [ ] **Step 6: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-WEBAPP: `859 passed`
  - SEL-REVENUE: `692 passed`

- [ ] **Step 7: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add tests/test_revenue_classification.py tests/test_webapp_true_revenue_ui.py webapp/static/app.js webapp/templates/index.html
git commit -m "dashboard: true revenue cards, the four-tier credit mix and the held reasons" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S6.2: Ledger tags, chips, filters and review controls

**Files:**
- Modify: `webapp/static/app.js:597-608, 652-655, 778-782, 811-813, 832-838, 840-842, 984, 4098-4099`
- Modify: `webapp/templates/index.html:1188, 1191-1192, 1405-1407, 1649-1651`
- Modify (pins): `tests/test_revenue_classification.py:823-825, 829-831`
- Modify (pins): `tests/test_webapp_flagged_dashboard.py:58, 683, 821`
- Modify (pins): `tests/test_webapp_true_revenue_ui.py:125`

**Depends on:** S6.1.

**Interfaces:**
- Consumes: S6.1's reason table.
- Produces:
  - `REVENUE_TIER_TAGS`, `REVENUE_FILTERS`, `heldReasonFilter(filter)`, `revenueSourceChip(tx)`, `revenueReviewKind(record) -> "both" | "reject" | ""`
  - `data-transaction-filter` / `data-modal-transaction-filter` values `true_revenue`, `verified_revenue`, `counted_flagged`, `excluded_pending_review`, `non_revenue`

**Why:** Spec §10.6 and §10.7's controls: a credit's tag is its tier (Verified revenue, Counted: <reason>, Held: <reason>, Non-revenue), with the reason's sentence under it; a property-management payout carries its chip (T15); the filter pills are True Revenue, Verified, Counted, Held for Review and Non-Revenue, and a held reason filters as `excluded_pending_review:<reason>`; a held or counted row offers Confirm and Mark, a rule-verified row Mark Non-Revenue only, a decided row its decision and Reset; the Revenue review view opens on the held credits; the page's words follow §10.5.

- [ ] **Step 1: Write the failing tests.**

Append to the end of `tests/test_webapp_true_revenue_ui.py`:

```python
# ---------------------------------------------------------------- S6.2: tags, chips, filters, review controls

def _record(tier, *, reason=None, state=None, initial=None, status="not_required", signals=()):
    state = state or {"verified": "verified_revenue", "non_revenue": "non_revenue"}.get(tier, "unverified_deposit")
    record = {"classification": "other", "revenue_classification": state, "revenue_tier": tier,
              "revenue_tier_reason": reason, "revenue_initial_classification": initial or state,
              "revenue_review_status": status, "source_location": "transaction:1",
              "contributes_to_true_revenue": tier in ("verified", "counted_flagged"),
              "revenue_context_signals": list(signals)}
    if tier is None:
        for key in ("revenue_tier", "revenue_tier_reason", "contributes_to_true_revenue"):
            record.pop(key)
    return {"date": "2031-03-02", "description": "FABRICATED ROW", "amount": 500.0, "source_job": "j",
            "classification": record}


@needs_node
def test_each_tier_has_its_tag_and_a_middle_tier_names_its_reason():
    rows = [_record("verified"), _record("counted_flagged", reason="check_deposit"),
            _record("excluded_pending_review", reason="financing_named_payer"), _record("non_revenue"),
            _record(None, state="unverified_deposit")]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
console.log(JSON.stringify({{tags: rows.map(transactionCategory), reasons: rows.map(revenueReviewReason)}}));
""")
    assert result["tags"] == [
        {"label": "Verified revenue", "glyph": "VER", "tone": "green"},
        {"label": "Counted: Check deposit", "glyph": "CNT", "tone": "teal"},
        {"label": "Held: Payer or entry suggests financing", "glyph": "?", "tone": "amber"},
        {"label": "Non-revenue", "glyph": "X", "tone": "neutral"},
        {"label": "Unverified deposit", "glyph": "?", "tone": "amber"},
    ]
    assert result["reasons"][1] == "Check deposit. A check deposit: the payer is not printed."
    assert result["reasons"][2] == ("Payer or entry suggests financing. The payer or the entry names funding, a loan or "
                                    "an advance.")
    assert result["reasons"][0] == result["reasons"][3] == ""
    assert result["reasons"][4] == "Unable to determine whether this deposit represents operating revenue."


@needs_node
def test_the_revenue_filters_find_their_rows():
    rows = [_record("verified"), _record("counted_flagged", reason="p2p"),
            _record("excluded_pending_review", reason="holder_name"),
            _record("excluded_pending_review", reason="wire_no_sender"), _record("non_revenue")]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
const found = (filter) => filterTransactions(rows, filter).map((tx) => rows.indexOf(tx));
console.log(JSON.stringify(Object.fromEntries(["true_revenue", "verified_revenue", "counted_flagged",
  "excluded_pending_review", "non_revenue", "excluded_pending_review:wire_no_sender"].map((f) => [f, found(f)]))));
""")
    assert result == {"true_revenue": [0, 1], "verified_revenue": [0], "counted_flagged": [1],
                      "excluded_pending_review": [2, 3], "non_revenue": [4],
                      "excluded_pending_review:wire_no_sender": [3]}


@needs_node
def test_the_review_controls_follow_the_server_rules():
    rows = [_record("excluded_pending_review", reason="holder_name"), _record("counted_flagged", reason="p2p"),
            _record("verified"), _record("verified", initial="unverified_deposit", status="confirmed"),
            _record("non_revenue", initial="verified_revenue", status="rejected"), _record("non_revenue"),
            _record(None, state="verified_revenue")]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
const actions = (html) => [...html.matchAll(/data-revenue-review-action="([a-z]+)"/g)].map((m) => m[1]);
console.log(JSON.stringify({{controls: rows.map((tx) => actions(revenueReviewControls(tx))),
  pickable: rows.map((tx) => pendingReviewTarget(tx) !== null)}}));
""")
    assert result["controls"] == [["confirm", "reject"], ["confirm", "reject"], ["reject"], ["reset"], ["reset"], [],
                                  []]
    # The multi-select offers the credits left unverified and not yet decided.
    assert result["pickable"] == [True, True, False, False, False, False, False]


@needs_node
def test_a_property_management_payout_carries_its_chip():
    row = _record("verified", signals=["recurring_source_3_credits", "property_management_collections"])
    result = run_dashboard(f"""
console.log(JSON.stringify({{chip: revenueSourceChip({json.dumps(row)}),
  none: revenueSourceChip({json.dumps(_record("verified"))})}}));
""")
    assert "Property-management collections" in result["chip"] and result["none"] == ""


@needs_node
def test_the_review_view_opens_on_the_held_credits():
    result = run_dashboard(_open("s", _served(_payload())) + """
navigate('review');
console.log(JSON.stringify({filter: transactionFilter}));
""")
    assert result["filter"] == "excluded_pending_review"


def test_the_page_carries_the_true_revenue_words():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    assert 'title="Deposits held for review"' in html
    assert "Deposits held for review, and counted deposits, can be confirmed or excluded from the Review column." in html
    assert "Analysed with older classification rules." in html
    for value, label in (("true_revenue", "True Revenue"), ("verified_revenue", "Verified"),
                         ("counted_flagged", "Counted"), ("excluded_pending_review", "Held for Review"),
                         ("non_revenue", "Non-Revenue")):
        assert f'data-transaction-filter="{value}">{label}</button>' in html
        assert f'data-modal-transaction-filter="{value}">{label}</button>' in html
    assert 'data-transaction-filter="unverified_deposit"' not in html
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_webapp_true_revenue_ui.py -q -p no:cacheprovider`

Expected: FAIL: `6 failed, 5 passed`, the first with `AssertionError: assert [{'label': 'V...ne': 'amber'}] == [{'label': 'V...ne': 'amber'}]`.

- [ ] **Step 3: Implement.**

In `webapp/static/app.js` (lines 597-608), replace:

```javascript
function transactionCategory(tx) {
  const record = transactionClassification(tx);
  const revenueState = record.revenue_classification;
  if (txAmount(tx) > 0 && revenueState === "verified_revenue") {
    return { label: "Verified Revenue", glyph: "REV", tone: "green" };
  }
  if (txAmount(tx) > 0 && revenueState === "unverified_deposit") {
    return { label: "Unverified Deposit", glyph: "?", tone: "amber" };
  }
  if (txAmount(tx) > 0 && revenueState === "non_revenue") {
    return { label: "Non-Revenue", glyph: "X", tone: "neutral" };
  }
```

with:

```javascript
// 5.6 (true revenue spec §10.6): a credit's tag is its tier, a middle tier naming its reason. An analysis saved before
// 5.6 carries no tier, so its credits keep their revenue state's tag.
const REVENUE_TIER_TAGS = Object.freeze({
  verified: () => ({ label: "Verified revenue", glyph: "VER", tone: "green" }),
  counted_flagged: (record) => ({ label: `Counted: ${revenueReasonLabel(record)}`, glyph: "CNT", tone: "teal" }),
  excluded_pending_review: (record) => ({ label: `Held: ${revenueReasonLabel(record)}`, glyph: "?", tone: "amber" }),
  non_revenue: () => ({ label: "Non-revenue", glyph: "X", tone: "neutral" }),
});

function transactionCategory(tx) {
  const record = transactionClassification(tx);
  const revenueState = record.revenue_classification;
  if (txAmount(tx) > 0 && REVENUE_TIER_TAGS[record.revenue_tier]) {
    return REVENUE_TIER_TAGS[record.revenue_tier](record);
  }
  if (txAmount(tx) > 0 && revenueState === "verified_revenue") {
    return { label: "Verified revenue", glyph: "VER", tone: "green" };
  }
  if (txAmount(tx) > 0 && revenueState === "unverified_deposit") {
    return { label: "Unverified deposit", glyph: "?", tone: "amber" };
  }
  if (txAmount(tx) > 0 && revenueState === "non_revenue") {
    return { label: "Non-revenue", glyph: "X", tone: "neutral" };
  }
```

In `webapp/static/app.js` (lines 652-655), replace:

```javascript
// A row of a flagged group ticked in Settings: the server marks it (flag_shown) when it serves the analysis.
function flaggedChip(tx) {
  return transactionClassification(tx).flag_shown === true ? glassChip("FLG", "Flagged", "blue", "flag-chip") : "";
}
```

with:

```javascript
// A row of a flagged group ticked in Settings: the server marks it (flag_shown) when it serves the analysis.
function flaggedChip(tx) {
  return transactionClassification(tx).flag_shown === true ? glassChip("FLG", "Flagged", "blue", "flag-chip") : "";
}

// 5.5 (true revenue spec §7.10, T15): a property-management platform's verified payout says so beside its tag.
function revenueSourceChip(tx) {
  const record = transactionClassification(tx);
  const signals = Array.isArray(record.revenue_context_signals) ? record.revenue_context_signals : [];
  return record.revenue_classification === "verified_revenue" && signals.includes("property_management_collections")
    ? glassChip("PM", "Property-management collections", "blue", "flag-chip") : "";
}

// 5.6 (true revenue spec §10.6): the revenue filters, value -> test of a row's classification record. A row analysed
// before 5.6 carries no tier (and its served copy no contributes_to_true_revenue), so only Verified and Non-Revenue
// find it.
const REVENUE_FILTERS = Object.freeze({
  true_revenue: (record) => record.contributes_to_true_revenue === true,
  verified_revenue: (record) => record.revenue_classification === "verified_revenue",
  counted_flagged: (record) => record.revenue_tier === "counted_flagged",
  excluded_pending_review: (record) => record.revenue_tier === "excluded_pending_review",
  non_revenue: (record) => record.revenue_classification === "non_revenue",
});

// The ledger filter behind one reason of the Held for Review view is "excluded_pending_review:<reason>". Null for any
// other filter.
function heldReasonFilter(filter) {
  const match = /^excluded_pending_review:([a-z_0-9]+)$/.exec(String(filter || ""));
  return match ? match[1] : null;
}
```

In `webapp/static/app.js` (lines 778-782), replace:

```javascript
  if (["verified_revenue", "unverified_deposit", "non_revenue"].includes(filter)) {
    matched = transactions.filter(
      (tx) => transactionClassification(tx).revenue_classification === filter
    );
  }
```

with:

```javascript
  if (REVENUE_FILTERS[filter]) {
    matched = transactions.filter((tx) => txAmount(tx) > 0 && REVENUE_FILTERS[filter](transactionClassification(tx)));
  }
  const heldReason = heldReasonFilter(filter);
  if (heldReason) {
    matched = transactions.filter((tx) => {
      const record = transactionClassification(tx);
      return record.revenue_tier === "excluded_pending_review" && record.revenue_tier_reason === heldReason;
    });
  }
```

In `webapp/static/app.js` (lines 811-813), replace:

```javascript
function revenueReviewControls(tx, fallbackJobId = null, fallbackAccount = null) {
  const record = transactionClassification(tx);
  if (record.revenue_initial_classification !== "unverified_deposit") return "";
```

with:

```javascript
// The review a credit may take (true revenue spec §10.7), as the server allows it: "both" (Confirm Revenue and Mark
// Non-Revenue) for a credit the classifier left unverified (held or counted), "reject" (Mark Non-Revenue only) for a
// credit a rule verified, "" for anything else. An analysis saved before 5.6 carries no tier and keeps its rules: only
// a credit left unverified is reviewed.
function revenueReviewKind(record) {
  if (record.revenue_initial_classification === "unverified_deposit") return "both";
  if (record.revenue_initial_classification === "verified_revenue" && typeof record.revenue_tier === "string") return "reject";
  return "";
}

function revenueReviewControls(tx, fallbackJobId = null, fallbackAccount = null) {
  const record = transactionClassification(tx);
  const kind = revenueReviewKind(record);
  if (!kind) return "";
```

In `webapp/static/app.js` (lines 832-838), replace:

```javascript
  return `
    <div class="revenue-review-actions">
      <button class="table-action review-confirm" type="button" ${common} data-revenue-review-action="confirm" aria-label="Confirm this deposit as operating revenue">Confirm Revenue</button>
      <button class="table-action review-reject" type="button" ${common} data-revenue-review-action="reject" aria-label="Exclude this deposit from operating revenue">Mark Non-Revenue</button>
    </div>
  `;
}
```

with:

```javascript
  const confirm = kind === "both"
    ? `<button class="table-action review-confirm" type="button" ${common} data-revenue-review-action="confirm" aria-label="Confirm this deposit as operating revenue">Confirm Revenue</button>`
    : "";
  return `
    <div class="revenue-review-actions">
      ${confirm}
      <button class="table-action review-reject" type="button" ${common} data-revenue-review-action="reject" aria-label="Exclude this deposit from operating revenue">Mark Non-Revenue</button>
    </div>
  `;
}
```

In `webapp/static/app.js` (lines 840-842), replace:

```javascript
function revenueReviewReason(tx) {
  const record = transactionClassification(tx);
  if (txAmount(tx) <= 0 || record.revenue_classification !== "unverified_deposit") return "";
```

with:

```javascript
function revenueReviewReason(tx) {
  const record = transactionClassification(tx);
  if (txAmount(tx) <= 0) return "";
  // 5.6 (true revenue spec §10.6): a counted or held credit names its reason, and one sentence on it.
  const entry = REVENUE_TIER_REASONS[record.revenue_tier_reason];
  if (entry && (record.revenue_tier === "counted_flagged" || record.revenue_tier === "excluded_pending_review")) {
    return `${entry[1]}. ${entry[2]}`;
  }
  if (typeof record.revenue_tier === "string" || record.revenue_classification !== "unverified_deposit") return "";
```

In `webapp/static/app.js` (line 984), replace:

```javascript
        <td>${glassChip(category.glyph, category.label, category.tone)}${flaggedChip(tx)}${reviewReasonHtml}</td>
```

with:

```javascript
        <td>${glassChip(category.glyph, category.label, category.tone)}${flaggedChip(tx)}${revenueSourceChip(tx)}${reviewReasonHtml}</td>
```

In `webapp/static/app.js` (lines 4098-4099), replace:

```javascript
    revealOpenAnalysis("review");
    showMainRevenueEvidence("unverified_deposit");
```

with:

```javascript
    revealOpenAnalysis("review");
    // 5.6 (true revenue spec §10.7): what needs review now is the held credits.
    showMainRevenueEvidence("excluded_pending_review");
```

In `webapp/templates/index.html` (lines 1405-1407), replace:

```html
            <button class="transaction-filter" type="button" data-transaction-filter="verified_revenue">Verified Revenue</button>
            <button class="transaction-filter" type="button" data-transaction-filter="unverified_deposit">Unverified Deposits</button>
            <button class="transaction-filter" type="button" data-transaction-filter="non_revenue">Non-Revenue</button>
```

with:

```html
            <button class="transaction-filter" type="button" data-transaction-filter="true_revenue">True Revenue</button>
            <button class="transaction-filter" type="button" data-transaction-filter="verified_revenue">Verified</button>
            <button class="transaction-filter" type="button" data-transaction-filter="counted_flagged">Counted</button>
            <button class="transaction-filter" type="button" data-transaction-filter="excluded_pending_review">Held for Review</button>
            <button class="transaction-filter" type="button" data-transaction-filter="non_revenue">Non-Revenue</button>
```

In `webapp/templates/index.html` (lines 1649-1651), replace:

```html
          <button class="transaction-filter" type="button" data-modal-transaction-filter="verified_revenue">Verified Revenue</button>
          <button class="transaction-filter" type="button" data-modal-transaction-filter="unverified_deposit">Unverified Deposits</button>
          <button class="transaction-filter" type="button" data-modal-transaction-filter="non_revenue">Non-Revenue</button>
```

with:

```html
          <button class="transaction-filter" type="button" data-modal-transaction-filter="true_revenue">True Revenue</button>
          <button class="transaction-filter" type="button" data-modal-transaction-filter="verified_revenue">Verified</button>
          <button class="transaction-filter" type="button" data-modal-transaction-filter="counted_flagged">Counted</button>
          <button class="transaction-filter" type="button" data-modal-transaction-filter="excluded_pending_review">Held for Review</button>
          <button class="transaction-filter" type="button" data-modal-transaction-filter="non_revenue">Non-Revenue</button>
```

In `webapp/templates/index.html` (line 1188), replace:

```html
        <!-- A saved statement analysed with older lender rules (analysis_rules_outdated, set when it is served). -->
```

with:

```html
        <!-- A saved statement analysed with older classification rules (analysis_rules_outdated, set when it is served). -->
```

In `webapp/templates/index.html` (lines 1191-1192), replace:

```html
            <strong id="rulesOutdatedTitle">Analysed with older lender rules.</strong>
            Its lenders and flagged positions follow the rules it was analysed with, not the current ones.
```

with:

```html
            <strong id="rulesOutdatedTitle">Analysed with older classification rules.</strong>
            Its lenders, flagged positions and revenue follow the rules it was analysed with, not the current ones.
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_webapp_true_revenue_ui.py -q -p no:cacheprovider`

Expected: PASS: `11 passed`.

- [ ] **Step 5: Re-pin the assertions this task moves (pin ledger rows 40-44).**

In `tests/test_revenue_classification.py` (lines 823-825), replace:

```python
    for state in REVENUE_STATES:
        assert f'data-transaction-filter="{state}"' in html
        assert f'data-modal-transaction-filter="{state}"' in html
```

with:

```python
    for state in ("true_revenue", "verified_revenue", "counted_flagged", "excluded_pending_review", "non_revenue"):
        assert f'data-transaction-filter="{state}"' in html
        assert f'data-modal-transaction-filter="{state}"' in html
```

In `tests/test_revenue_classification.py` (lines 829-831), replace:

```python
    assert "Verified Revenue" in html
    assert "Unverified Deposits" in html
    assert "Revenue Upper Bound" not in javascript
```

with:

```python
    assert "True Revenue" in html
    assert "Held for Review" in html
    assert "Revenue Upper Bound" not in javascript
    assert "Unverified Deposits" not in javascript
```

In `tests/test_webapp_flagged_dashboard.py` (line 58), replace:

```python
    assert result["credit"] == "Non-Revenue"
```

with:

```python
    assert result["credit"] == "Non-revenue"
```

In `tests/test_webapp_flagged_dashboard.py` (line 683), replace:

```python
    assert "Analysed with older lender rules" in notice and 'id="reanalyzeButton"' in notice
```

with:

```python
    assert "Analysed with older classification rules" in notice and 'id="reanalyzeButton"' in notice
```

In `tests/test_webapp_flagged_dashboard.py` (line 821), replace:

```python
  revenue: tagged('Verified Revenue')};
```

with:

```python
  revenue: tagged('Verified revenue')};
```

- [ ] **Step 6: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-WEBAPP: `859 passed`
  - SEL-REVENUE: `698 passed`

- [ ] **Step 7: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add tests/test_revenue_classification.py tests/test_webapp_flagged_dashboard.py tests/test_webapp_true_revenue_ui.py webapp/static/app.js webapp/templates/index.html
git commit -m "dashboard: tier tags, reason chips, revenue filters and the review controls" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task S6.3: Monthly Statements, the chart, the settings text and the script version

**Files:**
- Modify: `webapp/static/app.js:2675-2681, 2693-2702, 2718-2724, 3574-3583, 3595-3599`
- Modify: `webapp/templates/index.html:494-496, 1521-1522, 1678`
- Modify (pins): `tests/test_webapp_flagged_dashboard.py:716`
- Modify (pins): `tests/test_webapp_studio_views.py:348-350, 351-361, 392-397, 399-403, 420-422, 428-431, 436-439, 440-441, 445-447, 507-509`
- Modify (pins): `tests/test_webapp_true_revenue_ui.py:230`

**Depends on:** S6.2.

**Interfaces:**
- Consumes: S5.1's document keys.
- Produces:
  - `trueDeposits(doc)`, `trueDepositCount(doc)`, `verifiedDeposits(doc)`
  - the chart classes `bar-part-verified`, `bar-value-verified`, `legend-swatch-verified`

**Why:** Spec §10.2 and §10.3: True Deposits read `true_revenue_total` when `revenue_established`, a new Verified ($) column reads `verified_revenue_total` when `verified_revenue_established`; each Total bar holds its True part and the True part its Verified part, in three shades (in the True view the bar is True with its Verified part shaded), and a month without established revenue draws neither; the Settings text says what True revenue is; browsers fetch the new script (`?v=true-revenue-1`).

- [ ] **Step 1: Write the failing tests.**

Append to the end of `tests/test_webapp_true_revenue_ui.py`:

```python
# ---------------------------------------------------------------- S6.3: Monthly Statements and the chart

CHART_PARTS = r"""
const chartParts = () => ({
  labels: [...els.monthlyChart.innerHTML.matchAll(/<span class="bar-value( bar-value-true| bar-value-verified)?">([^<]*)<\/span>/g)]
    .map((m) => [m[1] ? m[1].trim() : "bar-value", m[2]]),
  parts: [...els.monthlyChart.innerHTML.matchAll(/<div class="bar-part( bar-part-verified)?" style="height: ([0-9.]+)%">/g)]
    .map((m) => [m[1] ? "verified" : "true", m[2]]),
  legend: els.monthlyChart.innerHTML.match(/<span class="chart-legend">([\s\S]*?)<\/span>\s*<\/div>/)[1],
});
"""


@needs_node
def test_the_monthly_statements_show_true_revenue_and_its_verified_part(tmp_path, monkeypatch):
    package = _package({"mar": _payload()}, tmp_path, monkeypatch)
    result = run_dashboard(CELLS + CHART_PARTS + f"""
currentJobIds = ['mar']; renderPackageAnalysis({json.dumps(package)});
const both = {{...monthly(), chart: chartParts()}};
setMonthlyDepositsView('true');
console.log(JSON.stringify({{both, trueOnly: {{...monthly(), chart: chartParts()}}}}));
""")
    both, true_only = result["both"], result["trueOnly"]
    # 2,000 posted: 1,000 True (700 verified, 300 counted), 900 held and 100 non-revenue.
    assert both["rows"][0][2:7] == ["2,000", "4", "1,000", "2", "700"]
    assert true_only["head"][2:5] == ["Monthly Deposits ($)", "Deposits Per Month", "Verified ($)"]
    assert true_only["rows"][0][2:5] == ["1,000", "2", "700"]
    assert both["chart"]["labels"] == [["bar-value", "2,000"], ["bar-value-true", "1,000"],
                                       ["bar-value-verified", "700"]]
    assert both["chart"]["parts"] == [["true", "50.0"], ["verified", "35.0"]]
    assert all(word in both["chart"]["legend"] for word in ("Total deposits", "True revenue", "of which verified"))
    assert true_only["chart"]["parts"] == [["verified", "70.0"]]


@needs_node
def test_a_month_without_established_revenue_draws_no_true_or_verified_part(tmp_path, monkeypatch):
    package = _package({"old": _untiered(_payload())}, tmp_path, monkeypatch)
    result = run_dashboard(CELLS + CHART_PARTS + f"""
currentJobIds = ['old']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{...monthly(), chart: chartParts()}}));
""")
    assert result["rows"][0][4:7] == ["N/A", "N/A", "700"]  # Verified stands on its own condition
    assert result["chart"]["parts"] == []
    assert result["chart"]["labels"][1:] == [["bar-value-true", "N/A"], ["bar-value-verified", "N/A"]]


def test_the_settings_say_what_true_revenue_is():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    text = " ".join(html.split())
    assert ("<strong>True revenue:</strong> every posted credit except known non-revenue (own-account transfers, "
            "funding, refunds) and the deposits held for review. The verified part, with positive proof, is shown "
            "beside it.") in text
    assert '<script src="/static/app.js?v=true-revenue-1"></script>' in html
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_webapp_true_revenue_ui.py -q -p no:cacheprovider`

Expected: FAIL: `3 failed, 11 passed`, the first with `AssertionError: assert ['2,000', '4'... '1', '3,257'] == ['2,000', '4'...', '2', '700']`.

- [ ] **Step 3: Implement.**

In `webapp/static/app.js` (lines 3574-3583), replace:

```javascript
// A statement's True deposits (the verified revenue), or null — shown N/A — unless the package established them:
// not for a failed statement, nor for one whose captured credits are not all classified or are not the money its
// Total counts (webapp/app.py `verified_revenue_established`; a payload that does not say reads as not established).
function trueDeposits(doc) {
  return doc.verified_revenue_established === true ? monthFigure(doc, doc.verified_revenue_total) : null;
}

function trueDepositCount(doc) {
  return doc.verified_revenue_established === true ? monthFigure(doc, doc.verified_revenue_count) : null;
}
```

with:

```javascript
// 5.6 (true revenue spec §10.2): a statement's True deposits (its True revenue), or null — shown N/A — unless the
// package established its revenue: not for a failed statement, nor for one analysed before 5.6, nor for one whose
// captured credits are not all tiered or are not the money its Total counts (webapp/app.py `revenue_established`; a
// payload that does not say reads as not established).
function trueDeposits(doc) {
  return doc.revenue_established === true ? monthFigure(doc, doc.true_revenue_total) : null;
}

function trueDepositCount(doc) {
  return doc.revenue_established === true ? monthFigure(doc, doc.true_revenue_count) : null;
}

// Its Verified part, established on its own condition (`verified_revenue_established`, the tier aside).
function verifiedDeposits(doc) {
  return doc.verified_revenue_established === true ? monthFigure(doc, doc.verified_revenue_total) : null;
}
```

In `webapp/static/app.js` (lines 3595-3599), replace:

```javascript
  if (view === "true") return [["Monthly Deposits ($)", revenue[0], "amount"], ["Deposits Per Month", revenue[1], "count"]];
  return [
    ["Total Deposits ($)", total[0], "amount"], ["Total Deposits Per Month", total[1], "count"],
    ["True Deposits ($)", revenue[0], "amount"], ["True Deposits Per Month", revenue[1], "count"],
  ];
```

with:

```javascript
  if (view === "true") {
    return [["Monthly Deposits ($)", revenue[0], "amount"], ["Deposits Per Month", revenue[1], "count"],
      ["Verified ($)", verifiedDeposits, "amount"]];
  }
  return [
    ["Total Deposits ($)", total[0], "amount"], ["Total Deposits Per Month", total[1], "count"],
    ["True Deposits ($)", revenue[0], "amount"], ["True Deposits Per Month", revenue[1], "count"],
    ["Verified ($)", verifiedDeposits, "amount"],
  ];
```

In `webapp/static/app.js` (lines 2675-2681), replace:

```javascript
// The monthly chart follows the Monthly Statements basis (Settings) like the table beside it, so the page never shows
// two different figures as a month's deposits: Total deposits, True deposits, or both (each Total bar holding its
// True part).
function renderMonthlyChart(rows, mixedCurrencies, view = "both") {
  if (!els.monthlyChart) return;
  const both = view === "both";
  const plotted = view === "true" ? trueDeposits : totalDeposits;
```

with:

```javascript
// The monthly chart follows the Monthly Statements basis (Settings) like the table beside it, so the page never shows
// two different figures as a month's deposits: Total deposits, True revenue, or both. 5.6 (true revenue spec §10.3):
// each Total bar holds its True part and the True part its Verified part, in three shades; in the True view the bar is
// True revenue with its Verified part shaded. A statement whose revenue is not established draws neither part.
function renderMonthlyChart(rows, mixedCurrencies, view = "both") {
  if (!els.monthlyChart) return;
  const both = view === "both";
  const nested = view !== "total";
  const plotted = view === "true" ? trueDeposits : totalDeposits;
```

In `webapp/static/app.js` (lines 2693-2702), replace:

```javascript
    const part = both ? numberOrNull(trueDeposits(doc)) : null;
    const share = part !== null && value > 0 ? Math.min(Math.max(part, 0) / value, 1) : 0;
    return `
      <div class="bar-col">
        <span class="bar-value">${escapeHtml(withUnit(formatWhole(plotted(doc))))}</span>
        ${both ? `<span class="bar-value bar-value-true">${escapeHtml(withUnit(formatWhole(trueDeposits(doc))))}</span>` : ""}
        <div class="bar${both ? " bar-total" : value !== null && value === largest && largest > 0 ? " peak" : ""}" style="height: ${heightPx.toFixed(1)}px">${
          share > 0 ? `<div class="bar-part" style="height: ${(share * 100).toFixed(1)}%"></div>` : ""}</div>
      </div>
    `;
```

with:

```javascript
    const truePart = nested ? numberOrNull(trueDeposits(doc)) : null;
    // The Verified part stands only inside an established True part.
    const verifiedPart = truePart !== null ? numberOrNull(verifiedDeposits(doc)) : null;
    const shareOf = (part) => (part !== null && value > 0 ? Math.min(Math.max(part, 0) / value, 1) : 0);
    const trueShare = both ? shareOf(truePart) : 0;
    const verifiedShare = shareOf(verifiedPart);
    const verifiedLabel = nested ? withUnit(formatWhole(truePart !== null ? verifiedDeposits(doc) : null)) : null;
    return `
      <div class="bar-col">
        <span class="bar-value">${escapeHtml(withUnit(formatWhole(plotted(doc))))}</span>
        ${both ? `<span class="bar-value bar-value-true">${escapeHtml(withUnit(formatWhole(trueDeposits(doc))))}</span>` : ""}
        ${nested ? `<span class="bar-value bar-value-verified">${escapeHtml(verifiedLabel)}</span>` : ""}
        <div class="bar${both ? " bar-total" : value !== null && value === largest && largest > 0 ? " peak" : ""}" style="height: ${heightPx.toFixed(1)}px">${
          trueShare > 0 ? `<div class="bar-part" style="height: ${(trueShare * 100).toFixed(1)}%"></div>` : ""}${
          verifiedShare > 0 ? `<div class="bar-part bar-part-verified" style="height: ${(verifiedShare * 100).toFixed(1)}%"></div>` : ""}</div>
      </div>
    `;
```

In `webapp/static/app.js` (lines 2718-2724), replace:

```javascript
  const legend = both
    ? `<span><i class="legend-swatch" aria-hidden="true"></i>Total deposits</span>`
      + `<span><i class="legend-swatch legend-swatch-true" aria-hidden="true"></i>True deposits (revenue only)</span>`
    : `<span>${view === "true" ? "True deposits (revenue only)" : "Total deposits (everything going in)"}`
      + " and ledger (average daily balance) per statement</span>";
  const described = { both: "total and true deposits", true: "true deposits (revenue only)", total: "total deposits" }[view]
    || "total deposits";
```

with:

```javascript
  const verifiedSwatch = `<span><i class="legend-swatch legend-swatch-verified" aria-hidden="true"></i>of which verified</span>`;
  const legend = both
    ? `<span><i class="legend-swatch" aria-hidden="true"></i>Total deposits</span>`
      + `<span><i class="legend-swatch legend-swatch-true" aria-hidden="true"></i>True revenue</span>` + verifiedSwatch
    : view === "true"
      ? `<span><i class="legend-swatch legend-swatch-true" aria-hidden="true"></i>True revenue</span>` + verifiedSwatch
        + "<span>and ledger (average daily balance) per statement</span>"
      : "<span>Total deposits (everything going in) and ledger (average daily balance) per statement</span>";
  const described = {
    both: "total deposits, true revenue and its verified part",
    true: "true revenue and its verified part",
    total: "total deposits",
  }[view] || "total deposits";
```

In `webapp/templates/index.html` (lines 494-496), replace:

```html
  .bar-value-true { margin-top: -6px; color: var(--accent-text); }
  .legend-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 3px; background: var(--border-2); }
  .legend-swatch-true { background: var(--accent); }
```

with:

```html
  .bar-value-true { margin-top: -6px; color: var(--accent-text); }
  /* 5.6: the Verified part of a True part (or of a True bar), in the third shade. */
  .bar-part-verified { background: var(--verified); }
  .bar-value-verified { margin-top: -6px; color: var(--verified); }
  .legend-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 3px; background: var(--border-2); }
  .legend-swatch-true { background: var(--accent); }
  .legend-swatch-verified { background: var(--verified); }
```

In `webapp/templates/index.html` (lines 1521-1522), replace:

```html
funding included. <strong>True monthly deposits:</strong> revenue only, the verified revenue and the
                  deposits you confirm; no transfers, no funding, and no deposit still awaiting review.
```

with:

```html
funding included. <strong>True revenue:</strong> every posted credit except known non-revenue
                  (own-account transfers, funding, refunds) and the deposits held for review. The verified part, with
                  positive proof, is shown beside it.
```

In `webapp/templates/index.html` (line 1678), replace:

```html
<script src="/static/app.js?v=lender-detection-2"></script>
```

with:

```html
<script src="/static/app.js?v=true-revenue-1"></script>
```

- [ ] **Step 4: Run the tests again.**

Run: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests/test_webapp_true_revenue_ui.py -q -p no:cacheprovider`

Expected: PASS: `14 passed`.

- [ ] **Step 5: Re-pin the assertions this task moves (pin ledger rows 45-55).**

In `tests/test_webapp_flagged_dashboard.py` (line 716), replace:

```python
    assert '<script src="/static/app.js?v=lender-detection-2"></script>' in html
```

with:

```python
    assert '<script src="/static/app.js?v=true-revenue-1"></script>' in html
```

In `tests/test_webapp_studio_views.py` (lines 348-350), replace:

```python
    assert both["head"] == ["Month", "Year", "Total Deposits ($)", "Total Deposits Per Month", "True Deposits ($)",
                            "True Deposits Per Month", "Ledger ($)", "NSF", "Action"]
    assert both["count"] == "2 statements"
```

with:

```python
    assert both["head"] == ["Month", "Year", "Total Deposits ($)", "Total Deposits Per Month", "True Deposits ($)",
                            "True Deposits Per Month", "Verified ($)", "Ledger ($)", "NSF", "Action"]
    assert both["count"] == "2 statements"
```

In `tests/test_webapp_studio_views.py` (lines 351-361), replace:

```python
    january = documents["jan"]
    assert both["rows"][0][2:6] == [whole(january["credits"]), str(january["deposit_count"]),
                                    whole(january["verified_revenue_total"]), str(january["verified_revenue_count"])]
    # One basis alone keeps the CRM's own headers and names the basis beside the count.
    for view, shown, amount, count in ((true_only, "True monthly deposits: revenue only", "verified_revenue_total",
                                        "verified_revenue_count"),
                                       (total_only, "Total monthly deposits: everything going in", "credits",
                                        "deposit_count")):
        assert view["head"] == ["Month", "Year", "Monthly Deposits ($)", "Deposits Per Month", "Ledger ($)", "NSF",
                                "Action"]
        assert view["count"] == f"2 statements · {shown}"
```

with:

```python
    january = documents["jan"]
    assert both["rows"][0][2:7] == [whole(january["credits"]), str(january["deposit_count"]),
                                    whole(january["true_revenue_total"]), str(january["true_revenue_count"]),
                                    whole(january["verified_revenue_total"])]
    # One basis alone keeps the CRM's own headers and names the basis beside the count; the True view adds Verified.
    for view, shown, amount, count, extra in (
            (true_only, "True monthly deposits: revenue only", "true_revenue_total", "true_revenue_count",
             ["Verified ($)"]),
            (total_only, "Total monthly deposits: everything going in", "credits", "deposit_count", [])):
        assert view["head"] == ["Month", "Year", "Monthly Deposits ($)", "Deposits Per Month", *extra, "Ledger ($)",
                                "NSF", "Action"]
        assert view["count"] == f"2 statements · {shown}"
```

In `tests/test_webapp_studio_views.py` (lines 392-397), replace:

```python
    both, true_only, total_only = result["both"], result["trueOnly"], result["totalOnly"]
    assert len(both["head"]) == 9
    assert both["chart"]["values"] == [["shown", whole(jan["credits"])], ["true", whole(jan["verified_revenue_total"])],
                                       ["shown", whole(feb["credits"])], ["true", whole(feb["verified_revenue_total"])]]
    assert "Total deposits" in both["chart"]["legend"] and "True deposits (revenue only)" in both["chart"]["legend"]
    # Storage refused the choice; the page still took it.
```

with:

```python
    both, true_only, total_only = result["both"], result["trueOnly"], result["totalOnly"]
    assert len(both["head"]) == 10
    assert both["chart"]["values"] == [["shown", whole(jan["credits"])], ["true", whole(jan["true_revenue_total"])],
                                       ["shown", whole(feb["credits"])], ["true", whole(feb["true_revenue_total"])]]
    assert "Total deposits" in both["chart"]["legend"] and "True revenue" in both["chart"]["legend"]
    assert "of which verified" in both["chart"]["legend"]
    # Storage refused the choice; the page still took it.
```

In `tests/test_webapp_studio_views.py` (lines 399-403), replace:

```python
    assert true_only["count"] == "2 statements · True monthly deposits: revenue only"
    assert true_only["chart"]["values"] == [["shown", whole(jan["verified_revenue_total"])],
                                            ["shown", whole(feb["verified_revenue_total"])]]
    assert "True deposits (revenue only) and ledger" in true_only["chart"]["legend"]
    assert total_only["chart"]["values"] == [["shown", whole(jan["credits"])], ["shown", whole(feb["credits"])]]
```

with:

```python
    assert true_only["count"] == "2 statements · True monthly deposits: revenue only"
    assert true_only["chart"]["values"] == [["shown", whole(jan["true_revenue_total"])],
                                            ["shown", whole(feb["true_revenue_total"])]]
    assert "True revenue" in true_only["chart"]["legend"]
    assert "and ledger (average daily balance) per statement" in true_only["chart"]["legend"]
    assert total_only["chart"]["values"] == [["shown", whole(jan["credits"])], ["shown", whole(feb["credits"])]]
```

In `tests/test_webapp_studio_views.py` (lines 420-422), replace:

```python
    jan, feb = sorted(package["documents"], key=lambda doc: doc["id"] != "jan")
    feb["verified_revenue_established"] = False  # e.g. a credit the classifier left without a revenue state
    jan["status"] = "failed"
```

with:

```python
    jan, feb = sorted(package["documents"], key=lambda doc: doc["id"] != "jan")
    # e.g. a credit the classifier left without a revenue state: neither revenue flag stands.
    feb["verified_revenue_established"] = feb["revenue_established"] = False
    jan["status"] = "failed"
```

In `tests/test_webapp_studio_views.py` (lines 428-431), replace:

```python
    # A failed statement has no figures at all, not a month of zeros.
    assert failed[2:8] == ["N/A"] * 6 and failed[8] == "Unavailable"
    assert unknown[2] == f"{round(feb['credits']):,}" and unknown[4:6] == ["N/A", "N/A"]
    # The chart says what the table says: nothing for the failed month, no True deposits for the other.
```

with:

```python
    # A failed statement has no figures at all, not a month of zeros.
    assert failed[2:9] == ["N/A"] * 7 and failed[9] == "Unavailable"
    assert unknown[2] == f"{round(feb['credits']):,}" and unknown[4:7] == ["N/A", "N/A", "N/A"]
    # The chart says what the table says: nothing for the failed month, no True deposits for the other.
```

In `tests/test_webapp_studio_views.py` (lines 436-439), replace:

```python
def test_true_deposits_of_a_payload_that_does_not_say_read_n_a(tmp_path, monkeypatch):
    """A package row without `verified_revenue_established` (none the server sends today) is not taken as
    established: True deposits read N/A, Total deposits stand."""
    package = _package({"jan": _single(1)}, tmp_path, monkeypatch)
```

with:

```python
def test_true_deposits_of_a_payload_that_does_not_say_read_n_a(tmp_path, monkeypatch):
    """A package row without `revenue_established` and `verified_revenue_established` (none the server sends
    today) is not taken as established: True and Verified deposits read N/A, Total deposits stand."""
    package = _package({"jan": _single(1)}, tmp_path, monkeypatch)
```

In `tests/test_webapp_studio_views.py` (lines 440-441), replace:

```python
    del package["documents"][0]["verified_revenue_established"]
    result = run_dashboard(CELLS + CHART + f"""
```

with:

```python
    del package["documents"][0]["verified_revenue_established"]
    del package["documents"][0]["revenue_established"]
    result = run_dashboard(CELLS + CHART + f"""
```

In `tests/test_webapp_studio_views.py` (lines 445-447), replace:

```python
    row = result["rows"][0]
    assert row[2] == f"{round(package['documents'][0]['credits']):,}" and row[4:6] == ["N/A", "N/A"]
    assert result["chart"]["values"][1] == ["true", "N/A"]
```

with:

```python
    row = result["rows"][0]
    assert row[2] == f"{round(package['documents'][0]['credits']):,}" and row[4:7] == ["N/A", "N/A", "N/A"]
    assert result["chart"]["values"][1] == ["true", "N/A"]
```

In `tests/test_webapp_studio_views.py` (lines 507-509), replace:

```python
    assert after["hidden"] is True and after["selected"] == 0 and after["boxes"] == 1
    trues = {doc["id"]: f"{round(doc['verified_revenue_total']):,}" for doc in package_after["documents"]}
    assert after["trueAfter"] == [trues["a"], trues["b"]] and after["trueAfter"] != start["trueBefore"]
```

with:

```python
    assert after["hidden"] is True and after["selected"] == 0 and after["boxes"] == 1
    trues = {doc["id"]: f"{round(doc['true_revenue_total']):,}" for doc in package_after["documents"]}
    assert after["trueAfter"] == [trues["a"], trues["b"]] and after["trueAfter"] != start["trueBefore"]
```

- [ ] **Step 6: Run the selections.** Each is listed under Global Constraints. Expected at this task's commit (the baseline plus this task's tests and pins):

  - SEL-WEBAPP: `859 passed`
  - SEL-REVENUE: `701 passed`

  Then the full suite: `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests -q -p no:cacheprovider`. Expected: only the 16 known failures of `C:/Users/GustavoPrietodePaula/lender-research/census/failed-ld-final.txt` (measured at this task's commit: 14,084 passed, 55 skipped, 39 deselected, 16 failed).

- [ ] **Step 7: Commit.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
git add tests/test_webapp_flagged_dashboard.py tests/test_webapp_studio_views.py tests/test_webapp_true_revenue_ui.py webapp/static/app.js webapp/templates/index.html
git commit -m "dashboard: monthly true and verified deposits, the three-shade chart and the new script version" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Acceptance

### Task A1: The 5.6 census, every guard, and the lender census (G7)

**Files:** none in the repository. Private outputs under `C:/Users/GustavoPrietodePaula/lender-research/revenue/census/`: `s56.json.gz`, `cmp56.json`, `lc54.json`, `lc56.json`, `lc_cmp.json`.

**Depends on:** S4.5, S5.2, S6.3 (the classifier is final at S4.5; A1 runs on the train's code).

**Why:** spec §14.2 to §14.4: the 5.6 run of the census, every guard of §14.3 (and the review's G15 to G17) as an automated check, and the measured targets. G7 is `tools/lender_census.py`, read against the owner's signed-off admission list.

- [ ] **Step 1: The 5.6 snapshot and the report** (S3.2 left `s54.json.gz` and `s55.json.gz` in place):

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
DATA="C:/Users/GustavoPrietodePaula/OneDrive - Capital Infusion/Desktop/Capital Infusion Projects/bankStatementAnalysis/webapp_data"
OUT=C:/Users/GustavoPrietodePaula/lender-research/revenue/census
C:/Python314/python.exe -m tools.revenue_census snapshot --data-dir "$DATA" --out $OUT/s56.json.gz
C:/Python314/python.exe -m tools.revenue_census compare --base $OUT/s54.json.gz --after $OUT/s55.json.gz --after $OUT/s56.json.gz --out $OUT/cmp56.json
```

  Expected: `classification 5.6: 2493 accounts; skipped: {'duplicate': 4579, 'unreconciled': 169}`, and `compare` exits 0 with `guards: all hold` on both runs. If S1.5 admitted or cleared anything, first reproduce this task's figures on an admission-free copy of the tree, as S3.2 Step 3 does (`noadmit56/`, `s56_noadmit.json.gz`), then attribute every row that moves from it to HEAD's snapshot to an entity of `g7_allowlist.json` or a cleared processor; any other move stops the release.

- [ ] **Step 2: The guards, one by one.** `compare` checks each on every posted credit and every account and lists failures by guard in `cmp56.json` (`runs[1].guards`); an empty dict is the pass. Expected: empty. `g13_listed_apart` and the G3 holder rows are listed for A3, not failures.

| Guard | How the census decides it (`tools/revenue_census.py`) | Expected |
|---|---|---|
| G1 | a base `non_revenue` row that is not `non_revenue` at 5.6 is named by `_narrowing`: narrowing 4 only when the row prints a third-party originator (`third_party_originator`), narrowing 8 only for the five BNPL entities (`BNPL_ENTITIES`); `outside_the_narrowings`, or a narrowing that may not lead to True (3) with the row in True, fails | 0 failures; `left_non_revenue` as in Step 4 |
| G2 | a Verified row with a financing root: T4's roots (`financing_root`) on a non-registry row; on a registry row, the registry's financing words or a root glued inside a word, the holder's own words and §7.0's FUNDING settlements aside (`registry_root`); a Q7 row is G12's | 0 |
| G3 | a row the holder test matches that is `counted_flagged`, or Verified by the customer/invoice descriptors, steps 12 to 14, Q5 or Q6 (`IDENTITY_METHODS`) | 0 |
| G4 | a row in True with transfer wording and no counterparty | 0 |
| G5 | a row in True that `match_known_payee` places in a financing group, other than a payout-credit entity, a factoring payee or Q7 | 0 |
| G6 | a row in True whose method is `direction_conflict` | 0 |
| G7 | Step 3 (the lender census and the owner's allowlist) | as Step 3 |
| G7b | every row whose normalized text the street-`LN` guard changed (`street_ln_changes`); a base financing-proceeds row among them that reaches True fails | 7 rows listed, 0 failures |
| G8 | the fabricated negatives: the full suite (Task A4) | pass |
| G9 | per account: every posted credit kept with a revenue state (`posted_credit_count`, `posted_credit_cents`), every tier one of the four and agreeing with its state, the tiers adding up to the posted credits, and the metrics' own tier totals (`tier_totals`) equal to the rows' within a cent; an account the base holds and the run lost, or a classification error among the snapshot's skips, fails | 0 |
| G10 | a Verified row the channel gate closes, or a Verified push-rail row that the registry did not verify (`REGISTRY_VERIFYING_METHODS`) | 0 |
| G11 | a row in True that prints Q8's pay words or the personal-income words | 0 |
| G12 | an `auto_lender_dealer_funding` row whose payer is neither a listed auto lender nor a credit union, or that prints a loan, proceeds, advance or refund word (`q7_veto_word`); an account with fewer than two credit-union rows verified by the credit-union arm | 0 |
| G13 | a Verified row whose payer region the numbered-company form matches, or that the full guard (the `DIRECT DEPOSIT <digits>` template included) matches and an identity rule verified; a processor's settlement after the template is listed apart (`g13_listed_apart`) | 0; 440 rows (about $0.68M) listed apart |
| G14 | a pooled row the recurrence veto or a card-credit label names (`pooled_while_vetoed`); an entity whose recurrence lift has fewer non-vetoed pool rows than its count (`pool_candidate`, `pool_vetoed`, `pool_threshold`) | 0 |
| G15 | a row in True that prints a refund word, glued or not (review C1) | 0 |
| G16 | a row in True that prints a tax refund or an earned-income credit, glued or not (review I6) | 0 |
| G17 | a row in True whose ACH originator, on a transfer-worded row, is the holder (review C3) | 0 |
| demotions | a verified 5.4 row that is no longer verified with no declared cause (`undeclared_demotion`) | 0 |

- [ ] **Step 3: G7, the lender census** (debits unchanged against 5.4). With `base54` from S3.2:

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
DATA="C:/Users/GustavoPrietodePaula/OneDrive - Capital Infusion/Desktop/Capital Infusion Projects/bankStatementAnalysis/webapp_data"
OUT=C:/Users/GustavoPrietodePaula/lender-research/revenue/census
C:/Python314/python.exe -m tools.lender_census snapshot --data-dir "$DATA" --out $OUT/lc54.json --code-root $OUT/base54
C:/Python314/python.exe -m tools.lender_census snapshot --data-dir "$DATA" --out $OUT/lc56.json
C:/Python314/python.exe -m tools.lender_census compare --before $OUT/lc54.json --after $OUT/lc56.json --out $OUT/lc_cmp.json
```

  Each lender-census snapshot reads every cached analysis (7,241) and takes longer than a revenue snapshot. `compare` reports lenders gained and lost and each group's rows after the change, not a per-row difference, so check the rows with this scratch script (Write tool; `C:/Users/GustavoPrietodePaula/lender-research/revenue/census/g7_check.py`; it prints counts, state names and entity names only). A moved row is allowed only when its known payee, read on the cache with the worktree's matcher, is an entity of the owner's signed-off list (`g7_allowlist.json`, S1.5 Step 6); with no list, nothing may move (review I2):

```python
"""Task A1 (scratch): G7 on two lender-census snapshots. Every analysis's row states, lender rows and flagged debit
counts and totals must be equal, except the rows whose known payee is an entity on the owner's signed-off admission
list of Task S1.5 (the allowlist; without one, nothing may move). A moved row's payee is read from the cache with the
checkout's own `match_known_payee`. Prints counts, state names and entity names only.
Usage: python g7_check.py <lc54.json> <lc56.json> [--data-dir <webapp_data> --allowlist <g7_allowlist.json>]"""
import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "C:/Users/GustavoPrietodePaula/work/true-revenue")


def _account_payloads(node):
    if isinstance(node, dict):
        statement = node.get("statement")
        if isinstance(statement, dict) and isinstance(statement.get("transactions"), list):
            yield node
            return
        for value in node.values():
            yield from _account_payloads(value)
    elif isinstance(node, list):
        for value in node:
            yield from _account_payloads(value)


class Payees:
    """The known payee of a moved row, read from the cache (read-only) with the checkout's matcher."""

    def __init__(self, data_dir: Path):
        from analysis.description_text import normalize_transaction_description
        from analysis.payee_matcher import match_known_payee

        self.normalize, self.match = normalize_transaction_description, match_known_payee
        self.data_dir = data_dir
        connection = sqlite3.connect(f"{(data_dir / 'webapp.db').resolve().as_uri()}?mode=ro", uri=True)
        try:
            self.paths = dict(connection.execute(
                "SELECT a.input_sha256, a.artifact_path FROM artifact_cache a JOIN (SELECT input_sha256, "
                "MAX(created_at) AS newest FROM artifact_cache WHERE stage = 'analysis' GROUP BY input_sha256) b "
                "ON a.input_sha256 = b.input_sha256 AND a.created_at = b.newest WHERE a.stage = 'analysis'"
            ).fetchall())
        finally:
            connection.close()

    def entity(self, key: str, row: int) -> str | None:
        sha, index = key.rsplit(":", 1)
        payload = json.loads((self.data_dir / "artifacts" / self.paths[sha]).read_text(encoding="utf-8"))
        account = list(_account_payloads(payload.get("artifact")))[int(index)]
        found = self.match(self.normalize(account["statement"]["transactions"][row]["description"] or ""))
        return None if found is None else found.entity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--allowlist", type=Path)
    args = parser.parse_args()
    before = json.load(open(args.before, encoding="utf-8"))["accounts"]
    after = json.load(open(args.after, encoding="utf-8"))["accounts"]
    allowed = set(json.loads(args.allowlist.read_text(encoding="utf-8"))["entities"]) if args.allowlist else set()
    payees = Payees(args.data_dir) if allowed else None
    moves, declared, flags, lenders = Counter(), Counter(), Counter(), 0
    for key, old in before.items():
        new = after[key]
        explained, account_declared = True, False
        for row, (was, now) in enumerate(zip(old["states"], new["states"])):
            if was == now:
                continue
            entity = payees.entity(key, row) if payees else None
            if entity in allowed:
                declared[(entity, was, now)] += 1
                account_declared = True
            else:
                moves[(was, now)] += 1
                explained = False
        old_lenders = {(row, entity) for row, entity, _alias in old["lenders"]}
        new_lenders = {(row, entity) for row, entity, _alias in new["lenders"]}
        if any(entity not in allowed for _row, entity in old_lenders ^ new_lenders):
            lenders += 1
        old_flags = {group: figures[:2] for group, figures in old["flagged"].items()}
        new_flags = {group: figures[:2] for group, figures in new["flagged"].items()}
        for group in set(old_flags) | set(new_flags):
            if old_flags.get(group) != new_flags.get(group) and not (explained and account_declared):
                flags[group] += 1
    print(f"analyses {len(before)}; state moves {sum(moves.values())}; analyses whose lender rows differ {lenders}; "
          f"flag groups whose debits differ {dict(flags)}; declared moves {sum(declared.values())}")
    for (was, now), count in moves.most_common():
        print(f"  {was} -> {now}: {count}")
    for (entity, was, now), count in declared.most_common():
        print(f"  declared {entity}: {was} -> {now}: {count}")
    return 1 if moves or lenders or flags else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

  Run `C:/Python314/python.exe $OUT/g7_check.py $OUT/lc54.json $OUT/lc56.json --data-dir "$DATA" --allowlist $OUT/g7_allowlist.json` (without S1.5's list, drop the last two options). It was run on the prototype's snapshots, and on a fabricated one-row move with and without a one-entity allowlist (refused without it, declared with it).

  Expected (measured on the revised prototype, without S1.5's admissions): `lenders gained: 0`, `lenders lost: 0`, `lenders gained through a generic word: 0` from `compare`, and from the script `analyses 7241; state moves 0; analyses whose lender rows differ 0; flag groups whose debits differ {}; declared moves 0` (the lender census reads every cached analysis, 7,241, without the revenue census's de-duplication). `compare` also prints eligible deposits down 39, unchanged 7,188, up 14 (the `SQ CAP`/SBA credits that become financing proceeds and the BNPL settlements that leave D1, counted over every cached copy) and withholding rates down 3, up 14, not comparable 65, unchanged 7,159, which follow from those deposit moves. The only declared exceptions are the entities the owner signed off in Task S1.5: the script prints their moves as `declared <entity>: <state> -> <state>`; any other move stops the release.

- [ ] **Step 4: The measured targets (§14.4).** Measured on the revised prototype on 2026-09-29 (rows exact, dollars rounded, shares of $276.9M of posted credits in 2,468 statements):

| Figure | Base (5.4) | Measured | Target |
|---|---|---|---|
| Verified, after 5.5 | 7.17% | 19.59% | about 14% or more |
| $0-verified statements, after 5.5 | 1,819 | 1,271 | at most about 1,465 |
| True, after 5.6 | — | 67.58% | §14.4's formula: 69.70% ± 3 (below) |
| $0-True statements, after 5.6 | 1,819 | 113 | about 107 |
| Median statement True share | 0% | 85.2% | about 87% |
| Verified, after 5.6 | 7.17% | 27.23% | 22% to 29% |
| $0-verified statements, after 5.6 | 1,819 | 1,094 | 945 to 1,281 |
| Package revenue gate (statements gated) | 96.6% | 30.06% (742) | about 28% to 32% |
| Held share of posted credits | — | 18.69% | (report) |

  **True, term by term (§14.4, review I8).** The target is "71.3% ± 3 … plus up to 2.3 points if the owner accepts T19 and 0.3 with T18, plus 0.8 for the funds-transfer wires; less the T5 moves and the holds the memo's rows cannot show". Measure it, as shares of posted credits, with this scratch script (Write tool; `C:/Users/GustavoPrietodePaula/lender-research/revenue/census/true_breakdown.py`; it prints figures only), run as `C:/Python314/python.exe $OUT/true_breakdown.py $OUT/s54.json.gz $OUT/s56.json.gz`:

```python
"""Task A1 (scratch, never committed): the spec's True-share formula, term by term, on a base (5.4) and a 5.6 census snapshot:
71.3 +- 3, plus what reached True from non_revenue (T19's book transfers, T18, the funds-transfer wires, the other
narrowings), less the T5 moves out of the unverified pool, less the holds the memo's rows could not show. Shares of
posted credits, in points. Prints figures only.
Usage: python true_breakdown.py <base> <s56>"""
from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter

sys.path.insert(0, "C:/Users/GustavoPrietodePaula/work/true-revenue")
from tools.revenue_census import _narrowing  # noqa: E402

UNSEEN = ("payer_also_debited", "possible_return", "payer_debited_as_lender", "insurer_payer")


def main(base_path: str, after_path: str) -> None:
    base = json.load(gzip.open(base_path, "rt", encoding="utf-8"))["accounts"]
    after = json.load(gzip.open(after_path, "rt", encoding="utf-8"))["accounts"]
    posted = sum(account["posted_cents"] for account in after.values())
    terms: Counter = Counter()
    true_total = 0
    for key, account in after.items():
        prior = {credit["i"]: credit for credit in base[key]["credits"]}
        for credit in account["credits"]:
            old = prior[credit["i"]]
            in_true = credit["state"] == "verified_revenue" or credit.get("tier") == "counted_flagged"
            true_total += credit["cents"] if in_true else 0
            if old["state"] == "non_revenue" and in_true:
                cause = _narrowing(old, credit) or "outside"
                if cause == "4_book_or_funds_transfer":
                    cause += ":book" if re.search(r"\bBOOK TRANSFER\b", credit["text"]) else ":funds"
                terms[f"+ reached True from non_revenue: {cause}"] += credit["cents"]
            if old["state"] != "non_revenue" and credit["state"] == "non_revenue":
                terms[f"- left the unverified or verified pool for non_revenue: {credit['rule'] or credit['method']}"] += (
                    credit["cents"])
            if credit.get("reason") in UNSEEN:
                terms[f"- held, not visible to the memo's rows: {credit['reason']}"] += credit["cents"]
    print(f"True {100 * true_total / posted:.2f}% of ${posted / 100:,.0f} posted")
    for name, cents in sorted(terms.items()):
        print(f"  {name}: {100 * cents / posted:.2f} pt (${cents / 100:,.0f})")
    added = sum(cents for name, cents in terms.items() if name.startswith("+"))
    t5 = sum(cents for name, cents in terms.items() if name.startswith("- left"))
    unseen = sum(cents for name, cents in terms.items() if name.startswith("- held"))
    print(f"  total added {100 * added / posted:.2f} pt; T5 and other non-revenue moves {100 * t5 / posted:.2f} pt; "
          f"unseen holds {100 * unseen / posted:.2f} pt")
    print(f"  spec formula: 71.3 + {100 * added / posted:.2f} - {100 * t5 / posted:.2f} - {100 * unseen / posted:.2f} = "
          f"{71.3 + 100 * (added - t5 - unseen) / posted:.2f} (band +- 3)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

  Measured on the revised prototype:
  - reached True from non-revenue: +2.53 points: T19's book transfers +1.81, the funds-transfer wires +0.38, T18's claim payments +0.33, the street `LN` +0.01, the BNPL settlements under 0.01;
  - left the unverified or verified pool for non-revenue: −0.14 points: Square Capital's `SQ CAP` −0.10, the widened reversal pairs −0.02, the tax refunds, account verification and return codes −0.02;
  - the holds the memo's rows could not show: −4.00 points: `payer_also_debited` −3.71, `possible_return` −0.21 (the released card credits among them), `payer_debited_as_lender` −0.05, `insurer_payer` −0.03.

  71.3 + 2.53 − 0.14 − 4.00 = 69.70, so the band is 66.70% to 72.70%, and the measured 67.58% is inside it. **The band is the stop condition:** a run outside it stops the release unless §4 names the cause. **Drift detection:** a run more than one point from 67.58% is reported with its causes before anything else, although it is not by itself a spec failure.

  The reasons (5.6, rows and share of posted credits): counted `no_payer_printed` 5,740 (11.76%), `wire_named_sender` 654 (6.35%), `check_deposit` 3,346 (5.26%), `named_payer_unlabelled` 3,419 (4.73%), `p2p` 12,048 (4.56%), `numbered_company_payer` 389 (4.13%, T11), `named_payer_one_off` 943 (2.13%), `factoring_payout` 391 (0.81%), `named_payer_purpose_refused` 500 (0.45%), `platform_unconfirmed` 193 (0.13%), `payout_credit_entity` 95 (0.03%); held `transfer_no_counterparty` 977 (5.75%), `wire_no_sender` 314 (4.83%), `payer_also_debited` 2,829 (3.71%), `financing_named_payer` 566 (1.19%, T4), `payroll_or_salary` 429 (1.10%), `p2p_round_repeat` 1,223 (0.61%), `non_sale_purpose` 423 (0.50%), `insurer_named_payer` 526 (0.38%), `possible_return` 276 (0.21%), `transfer_account_designation` 769 (0.20%, T13), `holder_name` 198 (0.11%), `payer_debited_as_lender` 55 (0.05%), `insurer_payer` 4 (0.03%), `personal_income` 28 (0.03%).
  Statements gated, by the held reason they carry: `payer_also_debited` 243, `p2p_round_repeat` 136, `transfer_no_counterparty` 133, `payroll_or_salary` 123, `financing_named_payer` 115, `wire_no_sender` 86, `non_sale_purpose` 73, `transfer_account_designation` 66, `possible_return` 54, `insurer_named_payer` 43, `holder_name` 18, `personal_income` 14, `payer_debited_as_lender` 9, `insurer_payer` 4. `named_payer_unlabelled` rows whose payer name alone Q6 (b) or (c) would verify: 238 rows, about $0.74M.
  Verified by method at 5.6 (rows): `operating_income_descriptor` 11,907; `operating_source_with_credit_context` 8,077; `recurring_operating_source` 6,521; `named_payer_repeats` 3,070; `payer_remittance_descriptor` 778; `auto_lender_dealer_funding` 215; `wholesale_auction_payout_form` 138; `wire_remittance_purpose` 80; `repeat_wire_sender` 63; `named_payer_company_form` 56; `public_payer_remittance` 20; `public_or_healthcare_payer` 15.
  `left_non_revenue` and the verified demotions at 5.6 are those of S3.2, except `customer_id` 32 rows (8 statements): five rows 5.5 demoted are verified again by Q6. Eligible deposits: unchanged 2,474, down 13, up 6; lender credits by cause as in S3.2. `g13_listed_apart`: 440 rows (about $0.68M), as in S3.2.

- [ ] **Step 5: Report** the printed lines, both tables filled with the run's values, `lc_cmp.json`'s summary, and the private paths. Nothing is committed.

### Task A2: The tryout host's census (read-only)

**Files:** Create (scratch, never committed) `C:/Users/GustavoPrietodePaula/lender-research/revenue/census/fly_jobs_copy.py`; private outputs `fly_jobs.db`, `fly54.json.gz`, `fly56.json.gz`, `fly_cmp.json` in the same folder.

**Depends on:** A1. Needs the owner's flyctl login on this machine (`C:/Users/GustavoPrietodePaula/.fly/bin/flyctl.exe`). Nothing is deployed and nothing on the host is written: the remote side opens `/data/webapp.db` read-only and prints one line.

**Why:** spec §14.2: the same census, read-only, against a copy of the host's job store, the per-row dump the government and AP verifiers asked for.

- [ ] **Step 1: The copy script.** Write it with the Write tool:

```python
"""Task A2 (scratch, never committed): copy the tryout host's saved analyses into a private SQLite file. The remote
side opens /data/webapp.db read-only and prints one gzip+base64 JSON line; nothing is written on the host.
Usage: python fly_jobs_copy.py <out.db>"""
import base64
import gzip
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

FLYCTL = "C:/Users/GustavoPrietodePaula/.fly/bin/flyctl.exe"
APP = "bank-statement-tryout"
REMOTE = """
import base64, gzip, json, sqlite3, sys
db = sqlite3.connect("file:/data/webapp.db?mode=ro", uri=True)
rows = db.execute("SELECT id, analysis_json FROM jobs WHERE analysis_json IS NOT NULL").fetchall()
db.close()
sys.stdout.write(base64.b64encode(gzip.compress(json.dumps(rows).encode("utf-8"))).decode("ascii"))
"""


def main(out: Path) -> None:
    script = base64.b64encode(REMOTE.encode("utf-8")).decode("ascii")
    command = f"sh -c 'echo {script} | base64 -d | python3 -'"
    result = subprocess.run([FLYCTL, "ssh", "console", "-a", APP, "-C", command], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=900)
    if result.returncode != 0:
        raise SystemExit(f"flyctl failed ({result.returncode}); nothing copied")
    line = max((part.strip() for part in result.stdout.splitlines()), key=len)
    rows = json.loads(gzip.decompress(base64.b64decode(line)))
    out.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(out)
    connection.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, analysis_json TEXT)")
    connection.executemany("INSERT OR REPLACE INTO jobs VALUES (?, ?)", rows)
    connection.commit()
    connection.close()
    print(f"{len(rows)} saved analyses copied")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
```

- [ ] **Step 2: Copy, then run the census on the copy.** Wake the machine first (`curl -s https://bank-statement-tryout.fly.dev/healthz`).

```bash
OUT=C:/Users/GustavoPrietodePaula/lender-research/revenue/census
C:/Python314/python.exe $OUT/fly_jobs_copy.py $OUT/fly_jobs.db
cd C:/Users/GustavoPrietodePaula/work/true-revenue
C:/Python314/python.exe -m tools.revenue_census snapshot --jobs-db $OUT/fly_jobs.db --out $OUT/fly54.json.gz --code-root $OUT/base54
C:/Python314/python.exe -m tools.revenue_census snapshot --jobs-db $OUT/fly_jobs.db --out $OUT/fly56.json.gz
C:/Python314/python.exe -m tools.revenue_census compare --base $OUT/fly54.json.gz --after $OUT/fly56.json.gz --out $OUT/fly_cmp.json
```

  Expected: `guards: all hold`. The census keeps only reconciled, de-duplicated accounts, so its base may differ from the spec's 111 uploads. Report the host's True and Verified shares beside the spec's reference (§14.4: True about 77%, Verified about 26%, base 13.4% verified with 67 uploads at $0); the plan did not measure the host, so a figure away from the reference is reported to the owner with its five largest reasons, not a stop. Without flyctl access, the report says `tryout host: not run (no flyctl access)` and the orchestrator runs Steps 1 and 2 as the first check after the release.

- [ ] **Step 3: Delete the copy** (`fly_jobs.db` holds customer statements) once the report is accepted: `rm $OUT/fly_jobs.db`. The snapshots are digit-masked and stay private.

### Task A3: The precision sample (before merge)

**Files:** none in the repository. Private: `C:/Users/GustavoPrietodePaula/lender-research/revenue/census/sample56.json` and the reviewer's sorted copy `sample56_sorted.json`.

**Depends on:** A1.

**Why:** spec §14.5: the census proves nothing moved outside the declared paths, not that what a new rule verifies is revenue.

- [ ] **Step 1: Draw the sample.**

```bash
cd C:/Users/GustavoPrietodePaula/work/true-revenue
OUT=C:/Users/GustavoPrietodePaula/lender-research/revenue/census
C:/Python314/python.exe -m tools.revenue_census sample --snapshot $OUT/s56.json.gz --out $OUT/sample56.json
```

  It prints one count per stratum. Expected (the revised prototype's 5.6 snapshot): 20 rows in each of `q5_repeat_wires`, `q6a_repeats`, `q6b_company_form`, `ap_remittance`, `public_payers`, `invoice_wires`, `card_and_payout_forms`, `q7_dealer_funding`, `holder_test_rows` and `numbered_template_rows` (G13's rows listed apart), every row of `q6c_government_healthcare` (15), and `largest_counted` 50: about 215 Verified rows and 50 counted rows.

- [ ] **Step 2: The independent sort.** Dispatch a reviewer who has not written or reviewed any task of this plan, with `sample56.json` only, and this brief: "For every row, set `sort` to `revenue`, `loan`, `own_money`, `refund`, `transfer`, `insurance`, `other` or `cannot_tell`, from the digit-masked text alone; write the file back as `sample56_sorted.json`."

- [ ] **Step 3: The bar.** In each Verified stratum at least 95% of the rows are `revenue`, and none is `loan`, `own_money`, `refund` or `transfer`; among the 50 largest counted rows none is `loan`, `transfer`, `own_money` or `refund`. Every row that misses the bar gets a named rule, hold or registry entry with a fabricated test (a new task, reviewed like the others) before merge, and its stratum is drawn again (`sample` with the new snapshot). Report the per-stratum tallies only.

### Task A4: The train: full suite, dashboard check, and the main checkout

**Files:** none.

**Depends on:** every task above.

- [ ] **Step 1: The full suite.** `cd C:/Users/GustavoPrietodePaula/work/true-revenue && C:/Python314/python.exe -m pytest tests -q -p no:cacheprovider`. Expected: only the 16 known failures of `C:/Users/GustavoPrietodePaula/lender-research/census/failed-ld-final.txt` (sandbox symlink and external-root tests; `test_corpus_gate_outcomes.py::test_every_production_caller_of_the_analysis_is_classified`; `test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`; `test_stated_counts.py::test_the_observer_is_not_wired_into_any_production_module`; `test_extraction_quality_admission.py::test_router_implementation_preserves_phase2_extraction_quality_exclusion`). Measured on the revised prototype at S6.3: 14,084 passed, 55 skipped, 39 deselected, 16 failed; S1.5's guard file adds 4 passing tests (14,088). Compare the failed ids with `comm -23 <(grep ^FAILED … | sort) <(sort …/failed-ld-final.txt)`: empty.
- [ ] **Step 2: The selections.** SEL-CLASSIFIER, SEL-REGISTRY, SEL-WEBAPP and SEL-REVENUE (Global Constraints); expected counts (the revised prototype at S6.3): SEL-CLASSIFIER `755 passed, 2 deselected`, SEL-REGISTRY `362 passed, 4 skipped`, SEL-WEBAPP `859 passed`, SEL-REVENUE `701 passed` (S1.5's admissions may add rendered aliases to SEL-REGISTRY's parametrized cases; report the difference).
- [ ] **Step 3: The dashboard in a browser.** Seed a scratch data folder (never the corpus cache) with two fabricated saved analyses, one analysed under 5.6 and one shaped as before 5.6, with this scratch script (Write tool; the scratchpad folder, never the repository):

```python
"""Task A4 (scratch): seed a scratch WEBAPP_DATA_DIR with two fabricated saved analyses for the browser check.
Usage: python seed_true_revenue.py <data dir>"""
import os
import sys

os.environ["WEBAPP_DATA_DIR"] = sys.argv[1]
sys.path.insert(0, "C:/Users/GustavoPrietodePaula/work/true-revenue")

from tests.test_webapp_true_revenue import _payload, _untiered  # noqa: E402
from webapp.app import store  # noqa: E402

for name, analysis in (("fabricated-march.pdf", _payload()), ("fabricated-april-older.pdf", _untiered(_payload(month=4)))):
    job = store.create(name)
    store.set_result(job.id, "# Fabricated", "<p>Fabricated</p>", analysis=analysis)
    print(job.id, name)
```

  Then start the app from the worktree with that folder (`cd C:/Users/GustavoPrietodePaula/work/true-revenue && WEBAPP_DATA_DIR=<the folder> WEBAPP_PORT=5057 C:/Python314/python.exe -m webapp.app`), open `http://127.0.0.1:5057/`, and check: the True Revenue card first and larger, Verified beside it with "70.0% of true revenue"; Counted, Not Verified $300.00 and Held for Review $900.00; the side badge 1, titled "Deposits held for review", and the Revenue review view opening on the held credit with its reason ("Payer or entry suggests financing"); the held row's Confirm Revenue and Mark Non-Revenue; the rule-verified row's Mark Non-Revenue only; the package of both statements: the Monthly Statements' Verified ($) column and the three-shade chart, the older month N/A with "1 of 2 statements has no established revenue · Re-analyze to compute true revenue". Click with real mouse events; restart Flask after any template edit. Screenshots show fabricated data only. Stop the server afterwards.
- [ ] **Step 4: The main checkout.** `git -C "C:/Users/GustavoPrietodePaula/OneDrive - Capital Infusion/Desktop/Capital Infusion Projects/bankStatementAnalysis" status --short --branch` prints only `## lender-detection`.
- [ ] **Step 5: Merge readiness.** The branch merges only after every review closes, A1 to A3 pass, and the owner has read both census reports (spec §16). The tryout host is not updated unless the owner asks.

## Decisions this plan takes where the spec leaves room

Each was taken during prototyping; the owner or a reviewer may overrule any of them.

1. **G7 and S1.5 (review I2).** §14.3 asks for zero lender, potential-lender and flag changes on debits against 5.4, while §8.7, §7.1, §7.3 and §7.9 ask S1 to admit dealer lenders, processors' advance products, Parafin and receivables financiers into the ledger, which changes those payees' debits. The owner signs off on the admission list with each entity's measured effect (S1.5 Step 6, `g7_allowlist.json`); G7's only declared exceptions are the signed-off entities, and `g7_check.py` traces every moved row to its payee on the cache (A1 Step 3). Without a sign-off, nothing that moves a debit is admitted, and G7 is measured as stated (0 moves, measured).
2. **S1.5 is research, then the owner's word.** Which products and lenders are admitted is decided by the research and verify rounds and the owner's sign-off, not by the plan; the bare processor aliases join only for a cleared processor (the gate table drops them by itself), and the guard test `tests/test_registry_additions_55.py` holds whatever the gate lets through. The census expectations were measured without any admission; with admissions, S3.2 and A1 first reproduce them on an admission-free copy of the tree and then attribute every moved row to an admitted entity (S3.2 Step 3, A1 Step 1).
3. **The wire and book-transfer labels live with the readers.** The channel gate (§6.1 step 9b) must know an incoming wire, so `_INCOMING_WIRE_LABEL`, `_BOOK_TRANSFER_FROM`, `_FUNDS_TRANSFER_WIRE_LABEL`, `_THIRD_PARTY_ORIGINATOR`, `_third_party_originator` and `_third_party_book_transfer` are added in S2.1 with the two owner switches, not in S2.2.
4. **The healthcare and dealer-funding tables ship in S1** (spec §16 gives them to S1) although only 5.6 reads them; they are inert until S4.2.
5. **An intermediate pin.** `tests/test_analysis.py:3361` (`m.true_revenue == 10000.0`) moves to `0.0` at S2.3 (the bare teller `CUSTOMER DEPOSIT` prints no payer word, so the 5.5 channel gate leaves it unverified, and `true_revenue` is still the verified total), and back to `10000.0` with `verified_revenue_total == 0.0` at S4.4 (the repointed True revenue counts it). The spec's §13 names only the second move. Both are pin-ledger rows.
6. **Spec-predicted pins that do not move.** §13 names `tests/test_factoring_credits.py:47-53` and `tests/l1s3_payloads.py:149-150`. The RTS test classifies one row with `classify_transaction`, which runs no statement pass, so the row stays `unverified_deposit` with no tier read (the pass counts it as `factoring_payout` in a statement); the L1-S3 fixture's `true_revenue_evidence: []` is data no assertion reads with the new meaning. Neither is re-pinned.
7. **The Held for Review view.** §10.7's "a Held for Review view groups them by reason, largest total first" is the Revenue evidence panel's per-reason rows under Held for Review (each a button to `excluded_pending_review:<reason>`), and the side navigation's Revenue review opens the ledger on the held credits. No separate page.
8. **The multi-select batch.** The server's batch route takes the same decisions as the single route, a reject of a rule-verified credit included (S4.4, S5.2). The dashboard offers the batch checkbox only for held and counted credits not yet decided, because a batch Confirm that reached a rule-verified credit would be refused as a whole ("a credit a rule verified can only be marked non-revenue").
9. **"Verified, with its share of True"** is printed in the Verified card's note ("70.0% of true revenue · …"). The statement page's credit line printed "Revenue upper bound"; with that card gone it prints "True revenue" (N/A when not established). `maximum_revenue` stays in the payload and the exports.
10. **The chart's labels.** Each bar keeps its Total label and (in Both) its True label, and gains a Verified label (`bar-value-verified`); a month whose revenue is not established reads N/A in both and draws no part.
11. **S6 runs after S5, not beside it** (spec §16 allows parallel). The dashboard's tests read the served flags and package keys S5 adds.
12. **Older payloads.** A payload analysed before 5.6 is gated by today's rule (a pending unverified deposit, a direction conflict, or revenue that does not reconcile); its `revenue_review_items` is None and the badge falls back to its unverified count; its review writer writes no tier; `_awaits_review` lets only unverified rows await, as today.
13. **The census population.** The census de-duplicates by statement fingerprint and keeps reconciled accounts: 2,493 accounts, 2,468 with credits, $276.9M of posted credits. Its gate base is 96.6% of statements with credits (the spec's 95.6% is of all 2,493); the shares match the spec's (7.17% verified, 17.0% non-revenue, 1,819 at $0).
14. **True inside the spec's band, term by term (review I8).** §14.4's target is 71.3% ± 3, plus what reaches True from non-revenue (T19's book transfers, T18, the funds-transfer wires), less the T5 moves and the holds the memo's rows cannot show. Measured (A1 Step 4): +2.53 points reached True from non-revenue (book transfers 1.81, funds-transfer wires 0.38, T18 0.33, street `LN` 0.01), −0.14 left the unverified or verified pool for non-revenue (SQ CAP 0.10, reversal pairs 0.02, tax refunds and other markers 0.02), −4.00 are the unseen holds (`payer_also_debited` 3.71, `possible_return` 0.21, `payer_debited_as_lender` 0.05, `insurer_payer` 0.03): 71.3 + 2.53 − 0.14 − 4.00 = 69.70, band 66.70 to 72.70. Measured True is 67.58%, inside it. The band is the stop condition; a run more than one point from 67.58% is drift to explain, not a spec failure. T4's hold measures $3.29M (1.19%) against the memo's $2.1M: the census reads the payer region and entry fields of every row, the memo only its deposit types.
15. **The tryout host is not measured by this plan.** Measuring it means copying customer statements off the host; A2 does that read-only as an acceptance step and reports the host's figures beside the spec's reference, without a numeric stop.
16. **`REVENUE_TIER_REASONS` has a JS mirror.** §5.3 says nothing else lists the codes, and §10.6 asks for one JS table mirroring them; the mirror adds one sentence per code and a parity test (S6.1) holds the two equal.
17. **Parafin's group** is proposed as `alternative_position` / `platform_embedded_financing`, the group the ledger gives Square Capital and Stripe Capital; the verify round decides.
18. **Test files.** §14.1 puts the fabricated tests in `tests/test_revenue_classification.py` "unless stated". This plan gives each family and each 5.6 part its own file (the File structure table), so that every task's tests are one reviewable file and `tests/test_revenue_classification.py` changes only by its pin-ledger rows.
19. **`(?<!RE)FUND` in T4's roots (review C1).** §8.1 lists the root `FUND`; the plan reads `(?<!RE)FUND`, so a refund is never held as financing. Refunds are held instead as `non_sale_purpose`: `[A-Z]*REFUND\w*`, `\bRFND\w*` and `\bREFND\w*` join `_NON_SALE_PURPOSE`'s last group (a glued `PREFUND`, `CUSTREFUND`, Maryland's `MDREFUND` included, which §7.6 already holds there). The reversal rule still decides `REFUND` and `REFUNDED` first, as today. G15 checks that no row in True prints a refund word.
20. **A registry row with a financing word is not claimed (review C2).** §8.1 skips every row the registry claimed, which let a platform's capital or advance credit (`STRIPE DES:CAPITAL`, `SPOTON DES:ADVANCE`, `MANHEIM US DES:FLOORPLAN`) count as `platform_unconfirmed`. The plan reads the financing words of the recurrence veto (§7.0), the new-read veto (§7.2) and the auction's words (§7.8) on a registry row, the holder's own words aside as the recurrence veto reads them, and holds such a row as `financing_named_payer`. This is a departure from §8.1's wording, recorded for the owner. Measured at 5.6: 17 rows, about $14K, 5 statements.
21. **FUNDING vetoes recurrence outside three platforms (review C2).** §7.0 keeps `FUNDING` out of the recurrence veto because TapGoods, Braintree and Buildium print it on real settlements. The plan narrows that exception to those three entities (`_FUNDING_SETTLEMENT_ENTITIES`): three `ETSY DES:FUNDING` rows no longer verify each other. Measured: no row verified at 5.4 loses its verification by it.
22. **The auction branch refuses §14.1's words (review C2).** `_AUCTION_VETO` (`FUNDING`, `FUNDNG`, `FUNDED`, `ADVANCE`, `ADV`, `CAPTL`, `CAPITAL`, `FLOOR PLAN`, `FLOORPLAN`, `FINANC…`, `NGC`, `LOAN`, `PPD`) keeps an auction credit that prints its payout form unverified (rule `auction_credit_prints_financing_or_consumer_word`); at 5.6 the financing ones are held and the PPD one counted. `DEALSHIELD` and `ARB CREDIT` are held as `possible_return` (an auction's refund of a vehicle the dealer bought).
23. **The holder's own ACH transfer (review C3).** §5.2 reads a transfer row's payer after `FROM`; a transfer-worded row that prints an ACH originator field (`DES`, `CO ENTRY DESCR`, `ORIG CO NAME`) and no `FROM` sender now reads its originator the ACH way, so the holder test and the counter-debit hold see it. It keeps the named-transfer tier. G17 reads the holder test on that originator independently of the payer region.
24. **Santander's wire layout (review I5).** §5.2 reads a wire's originator after `WIRE IN FROM`; Santander prints its sending bank there (`USD WIRE IN FROM <sending bank> ACCT <n> <originator> REF <purpose>`), so the payer region, the own-account, brand-word and cut-field vetoes and Q5's repeats read the bank. The plan reads the originator after the account number (`_SANTANDER_WIRE`) and removes the sending bank, and Chase's originating bank (`OGB`), before the financing roots are read (`_wire_financing_text`). §7.9's 40 cases need it (a Santander own-account wire verified without it). Measured: 11 rows, about $0.98M, 3 statements move, True +0.14 points.
25. **Two demotion causes this plan declares.** `pool_below_recurrence_after_a_declared_veto` (a pool left under its count once a declared veto takes a member out: 4 rows, 3 statements) and `entity_split` (a pool split by an entity's re-reading: measured 0) follow from §7.0's declared recurrence fixes. The census lists them; any other cause is `undeclared` and fails it.
26. **The review's guards G15 to G17.** No row in True prints a refund word (G15), a tax refund or an earned-income credit (G16), or is the holder's own ACH transfer (G17). They read the census's own patterns and facts, not the pass's.
27. **G2 and G13 on registry and form rows (review I1).** §14.3's G2 reads T4's roots; on a registry row the plan reads the registry's financing words and a root glued inside a word (`STRIPECAPITAL`), the holder's own words and §7.0's FUNDING settlements aside, because T4's substring roots read a root inside a city's name on real DoorDash payouts. G13 reads the numbered-company region form on every Verified row and the full guard (the `DIRECT DEPOSIT <digits>` template included) on the rules that read it (§5.2: steps 11 to 14, Q5, Q6); a processor's settlement printed after BMO's `MISC PAYMENT <digits>` template is listed apart (`g13_listed_apart`: 440 rows, about $0.68M) and sampled (A3, `numbered_template_rows`).
28. **Q5 honours the channel gate.** §6.1 step 9b says Q5 never verifies a row the gate closes or limits to the registry; the prototype's Q5 did not check it. `_wire_verifies` now refuses a gated row (G10's push-rail half checks it).
29. **Title, escrow and bank payers never verify by name (review I6).** Q5 refuses a sender naming a bank or a title or escrow firm (§8.5); the plan applies the same list to Q6 (b)'s company form, and refuses a title or escrow originator in §7.9's wire vetoes (read by §7.5 and §7.9). A PPD or WEB entry never verifies by its company form (S50's block extended to Q6 (b); measured: 71 rows, about $0.21M, 15 statements, now counted as `named_payer_one_off`). `PAYCHECK`, `PR PAY` and `EMPLOYEE PAY` are pay words; the glued tax refunds `<STATE>TAXRFD` and `TAXEIC` join T5 (the spaced `TAX EIC` stays held as `non_sale_purpose`, as §14.1 asks).
30. **§7.9's purposes as the verifier's cases need them (review I5).** `PAYMENT FOR GOO(DS)` (a cut field), `COMPRA (DE) MERCAD…`, the glued `INTERCOMPANY` and `INTERCO` veto; the bare `PI <digits>` stays dropped (the 40th case expects `stays`). The wire tests pin §7.9's recorded residuals (a person's invoice wire, a person's holding company, a neutral-name funder, the MCA "purchase price" order, a root-free factor, a template-named holder's own account, and Stenn until the ledger lists it): they verify, and A3 samples them.
31. **The ledger gate is read by the reader (review I4).** `GATED_PROCESSOR_ALIASES` is derived from `PROCESSOR_ADVANCE_PRODUCTS`, and an operating alias read inside another waiting processor's bare alias (`BY STRI` inside `JOBBER BY STRI`) names no source. The validator is not changed: it compares whole aliases, and the reader closes the hole for every contained alias. Q6 still reads a waiting processor's repeated rows as any payer's (4 `MISC PAYMENT JOBBER BY STR` rows verify as `named_payer_repeats`): the gate governs the registry, not Q6 (open for the owner).
32. **M7 is not done.** §5.2 cuts a sender before a sending bank's name, but a printed sender does not mark where the bank's name starts (`JOHN SMITH SAMPLE BANK`), and `BANK_NAME_ALIASES` holds loan and product spellings, not the banks' printed names. The sender feeds only the holder test, the round-sum key and the counted tiers, never a verification; a trailing bank word leaves those as they are or splits a sender's key (the safe direction for the round-sum hold is lost only when the same person pays from two banks). Recorded, not fixed.

## Revision after review (2026-09-29)

The review of this plan returned "changes needed": three critical findings (refunds, platform capital and the holder's own ACH transfers could reach True, and the census could not see them), eight important ones and seven minor ones. This revision applies every critical and important finding and six of the seven minor ones; M7 is declined with its reason. Each change was made in the prototype first, with fabricated tests; the per-task clone was rebuilt from `4227a76`; and every figure of the plan was measured again (each task's tests before and after, the selections at every task, the full suite at four tasks, the census at 5.4, 5.5 and 5.6, and G7).

### What changed, finding by finding

| Finding | What changed | Where |
|---|---|---|
| C1 refunds verified or counted | `[A-Z]*REFUND\w*`, `\bRFND\w*`, `\bREFND\w*` hold a row as `non_sale_purpose` (`COMPTROLLER OF MD DES:MDREFUND` stays there); the `(?<!RE)FUND` departure is declared; each of the review's refund rows is tested alone and repeated; G15 fails any refund word in True | S4.2; S3.1; Decision 19 |
| C2 platform capital and floor plan counted, an NGC credit verified | a registry row that prints a financing word is not claimed and is held as `financing_named_payer`; the auction branch refuses §14.1's words (`FUNDING` … `NGC`, and `PPD`); FUNDING vetoes recurrence outside the three platforms §7.0 names; G2 fails on a registry row's own root; every row of the review is tested; recorded for the owner | S2.2, S2.4, S4.2, S3.1; Decisions 20 to 22, 27 |
| C3 the holder's own ACH transfer lost its payer | a transfer-worded row with an ACH originator field and no FROM sender reads its originator as its payer (it keeps the named-transfer tier); the holder's own transfer is held `holder_name` and a transfer pair `payer_also_debited`; G17 reads the holder test on the originator independently | S2.1, S4.2, S3.1; Decision 23 |
| I1 weak census guards | G9 checks every posted credit's tier against its state, the metrics' tier totals and fails an unmatched account or a classification error; an undeclared demotion fails the census; the plan's own causes are declared; narrowing 8 needs a BNPL entity and narrowing 4 a third-party originator; G10 checks the push-rail half; G13 the full guard; G12 the credit-union count and the loan-word veto; G14 every row that counted toward a lifted pool; G15 to G17 added | S3.1, A1; Decisions 25 to 27 |
| I2 G7 against S1.5 | the owner signs off on the admission list, with each entity's measured effect (`admission_effect.py`); only signed-off entities are admitted; `g7_check.py` reads that list as its only declared exceptions and traces every moved row to its payee on the cache; without a sign-off nothing that moves a debit is admitted; S3.2 and A1 re-measure against an admission-free copy of the tree | S1.5 Steps 6 and 7, S3.2 Step 3, A1 Steps 1 and 3; Decisions 1 and 2 |
| I3 the structural-lens processors | a read-only search of the cache (31,116 analyses) and the host's dump: none of the seventeen prints a credit spelling, so each waits; the registry records it and a test holds it | S1.1 Step 1 |
| I4 the Jobber gate bypassed by `BY STRI` | `GATED_PROCESSOR_ALIASES` (derived) and a reader that refuses an alias read inside a waiting processor's bare alias, on credits and on the fee debits of the recurrence pass; tested | S1.1, S2.2, S2.4, S2.3; Decision 31 |
| I5 G8 not claimable | §14.1's §7.8 negatives (the financing words, the alias in IND NAME, INDN, a Zelle field and a memo, pay and PPD, DEALSHIELD and ARB CREDIT, card credits, the wire-paid pair, the D1 controls, the duplicate) and §7.9's list (the 40 cases, the hazard groups G1 to G11, the party-name rows, the adversarial rows, the recorded residuals) are fabricated tests. They forced five fixes: Santander's originator, the originating bank (`OGB`) removed before the roots, the glued `INTERCOMPANY`, the cut `PAYMENT FOR GOO` and `COMPRA MERCADE`, and a title or escrow originator vetoed; S1.5's brief carries §7.9's receivables financiers | S2.1 to S2.4, S4.2, S1.5; Decisions 24, 29, 30 |
| I6 spec gaps | a PPD or WEB entry, a bank and a title or escrow firm never verify by their company form; `PAYCHECK`, `PR PAY`, `EMPLOYEE PAY` are pay words; `<STATE>TAXRFD` and `TAXEIC` join T5; G16 fails any tax refund in True; raised for the owner below | S2.3, S4.2, S3.1; Decision 29 |
| I7 a real-statement re-pin | pin-ledger row 35 moves only on the owner's word, asked in S5.1's first step; the stop rule names it | S5.1 Step 1, Global Constraints |
| I8 the True-share explanation | the spec's formula term by term (A1 Step 4): the band is the stop condition, and the one-point check against the measured value is drift detection | A1 Step 4; Decision 14 |
| M1 consumers untested | tests for the batch columns and review flag, the CLI report, and a benchmark row comparing True revenue with MoneyThumb's true credits (`true_revenue_row`), Verified beside it | S4.5 |
| M2 moves only counted | `lender_credit_moves_by_cause` (lender credits and eligible deposits by the cause that moved each row) | S3.1, S3.2, A1 |
| M3 `DEPOT` closed the French forms | `DEPOT MARCHAND` and `DEPOT DIRECT` are not branch deposits; `DEPOT MARCHAND GLOBAL PAIEMENTS` verifies through Global Payments | S2.1, S2.3 |
| M4 the verified aliases | `confirmed_true_revenue_total` and `confirmed_true_revenue` are N/A with the verified total | S5.1 |
| M5 the S1.5 brief | records carry `"status": "admitted"`; Step 4 writes guard tests that pass by design | S1.5 |
| M6 card refunds as financing | `VISA`, `CHECKCARD` and `PURCHASE CREDIT` are posting labels and possible returns | S4.2 |
| M7 the sending bank in a sender | declined (Decision 32) | — |

### Where this revision departs from the review's wording, and why

1. **G2 on registry rows (C2, I1).** The review asked G2 to fail on a registry row that carries a financing root. Read with T4's substring roots, G2 failed on 86 real DoorDash payouts whose row prints a city whose name holds `LEND`. A registry row is read by the registry's financing words and a root glued inside a word, the holder's own words and §7.0's FUNDING settlements aside (Decision 27); that reading fails every row of the review's C2 list.
2. **G13's template form (I1).** The full guard matches 440 Verified rows (about $0.68M) that the processors' card forms and registry verified after BMO's `MISC PAYMENT <digits>` template: Global Payments, Fiserv and Elavon settlements whose payer is the processor, which §5.2 exempts from the guard. G13 fails the template only on the rules that read the guard, lists the rest apart and samples them (A3's `numbered_template_rows`).
3. **The gate lives in the reader (I4).** The review offered the validator or the reader. The reader closes the hole for every contained alias; the validator compares whole aliases and cannot. Q6 still verifies a waiting processor's repeated rows as any payer's (4 corpus rows), which is outside the gate's scope: open for the owner.
4. **Beyond the review's lists.** Transcribing §14.1 found holes the review did not name, and each is fixed and measured here: Santander's layout (Decision 24), Q5's missing channel-gate check (Decision 28), FUNDING in three statements of one platform verifying by recurrence (Decision 21), and a title firm's invoice wire verified by §7.5 (Decision 29).
5. **I2's two options.** The plan does both: it asks the owner to sign off the list (G7 reads it), and without a sign-off it defers every admission that moves a debit.
6. **I7.** The re-pin is kept, because §9.2 and §10.4 require it, but it waits for the owner's word; S5.1 stops before its commit without it.

### What the re-measurement changed

| Figure | Before the review | After |
|---|---|---|
| 5.5 Verified share; $0-verified statements | 19.50%; 1,266 | 19.59%; 1,271 |
| 5.5 statements gated (today's rule) | 93.72% | 93.80% |
| 5.6 True share; held share | 67.46%; 18.82% | 67.58%; 18.69% |
| 5.6 Verified share; $0-verified; $0-True; median True | 27.19%; 1,083; 112; 85.2% | 27.23%; 1,094; 113; 85.2% |
| 5.6 statements gated | 30.06% (742) | 30.06% (742) |
| Full suite at S6.3 (passed; the 16 known failures) | 13,873 | 14,084 |
| G7 (analyses; state moves; lender rows; flag groups) | 7,241; 0; 0; none | 7,241; 0; 0; none (the same, with the new check) |

At 5.6, against the plan as reviewed (rows, dollars, statements): Santander's originator 11 rows, about $0.98M, 3 statements (True +0.14 points; Q5 and §7.9 now read the originator); the PPD company-form block 71 rows, about $0.21M, 15 statements, verified to counted; the Jobber gate 36 rows, about $94K, 12 statements, verified to counted (none was verified at 5.4); the holder's and payer's ACH transfers 50 rows, about $21K, 10 statements (12 held `payer_also_debited`, 34 `insurer_named_payer`); platform capital 17 rows, about $14K, 5 statements, held; refund words 4 rows, about $12K, held or non-revenue; a title firm's wire, a glued tax refund and a French direct deposit, one row each. G15 to G17 hold on the corpus: no refund word, tax refund or holder's own ACH transfer is left in True.

### Open for the owner

1. §8.1's registry skip does not cover a registry row that prints a financing word (Decision 20); FUNDING vetoes recurrence outside TapGoods, Braintree and Buildium (Decision 21); Santander's originator is read after its account number (Decision 24). Each departs from the spec's wording.
2. The spec gaps of review I6, fixed narrowly (Decision 29): a PPD or WEB company form, a bank's or a title firm's company form, paychecks and glued tax refunds no longer verify or count.
3. Pin-ledger row 35 (S5.1 Step 1) and S1.5's admission list (S1.5 Step 6).
4. §7.9's recorded residuals verify (a person's or a holding company's invoice wire, a neutral-name funder, an MCA "purchase price" order, a root-free factor, a template-named holder's own account, Stenn until the ledger lists it); A3 samples their strata.
5. Q6 verifies a waiting processor's repeated rows (`MISC PAYMENT JOBBER BY STR`, 4 rows) as any payer's (Decision 31).
6. M7 is declined (Decision 32).

## Self-review

- **The review (2026-09-29).** Every finding maps to a change and a task in "Revision after review": C1 to S4.2 and G15; C2 to S2.2, S2.4, S4.2 and G2; C3 to S2.1, S4.2 and G17; I1 to S3.1 and A1; I2 to S1.5, S3.2 and A1; I3 to S1.1 Step 1; I4 to S1.1, S2.2 and S2.4; I5 to S2.1 to S2.4, S4.2 and S1.5; I6 to S2.3, S4.2 and G16; I7 to S5.1 Step 1; I8 to A1 Step 4; M1 to S4.5; M2 to S3.1; M3 to S2.1; M4 to S5.1; M5 to S1.5; M6 to S4.2; M7 declined (Decision 32).
- **Spec coverage.** Every section of the spec maps to a task in the Spec coverage table above: §1 to §3 (the plan's goal and every service), §4 T1 to T19 (each row names its task; T18 and T19 ship on per §19), §5 (S2.1, S4.1, S4.4), §6 (S2.3, S2.4, S4.2, S4.3; §6.3 through the census's `NARROWINGS` and G1), §7.0 to §7.12 (S1.1 to S1.5, S2.1 to S2.4), §8 (S4.2, S4.3), §9 (S4.4, S5.1, S2.5, S4.5), §10 (S6.1 to S6.3 with the server rules in S4.4, S5.1, S5.2), §11 (S4.4, S5.1), §12 (S4.4, S5.1, S6.1), §13 (every consumer row, including the "none" rows), §14 (S3.1, S3.2, A1 to A4), §15 (out of scope, nothing implemented), §16 (the order), §17 and §19 (OQ1 out, OQ2 S1.4, OQ3 S4.2, OQ4 nothing decided, OQ5 and OQ6 on).
- **Placeholders.** Every code step carries its full code, taken from the prototype commit that ran it (the rebuilt clone after the review); every run step carries its command and the output measured at that commit. The research task (S1.5) carries the brief, the gate script, the guard tests and the code changes for each outcome; what it admits is the research's to decide, not a gap in the plan.
- **Names and types.** The interfaces blocks name each function and constant with its signature; later tasks use them as defined (for example `revenue_contribution_flags(state, tier)` from S4.1 in S4.2's `_with_tier` and S4.4's rebuild; `_payer_key` and `_debit_first_distinctive_word` from S2.4 in S4.2; `dealer_funding` from S4.3 in `classify_transaction`; `apply_revenue_view` from S5.1 in `_displayed`; `REVENUE_TIER_REASONS` in `analysis/revenue.py` and its JS mirror in S6.1, held equal by a test; the review's names: `GATED_PROCESSOR_ALIASES` from S1.1 in S2.2's `_GATED_PROCESSOR_PATTERNS`; `_SANTANDER_WIRE` from S2.1 in S2.2's `_wire_financing_text` and `_wire_originator_run`, read by S4.2's `_wire_verifies`; `_FUNDING_SETTLEMENT_ENTITIES` from S2.2 in S2.4's `_recurrence_vetoed` and S4.2's `registry_financing`; `registry_financing` and `registry_financing_root` from S4.2 in the census facts `registry_financing` and `registry_root`; the Q7 facts from S4.3 in G12). The prototype ran every task in order, so a name used before it is defined would have failed its task's tests.
