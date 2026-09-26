# S2 Classifier and Analysis Payload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the classifier count as lenders only MCA funders and equipment financing. Put the eleven other groups into flags: ten obligation groups get flag-group states, and premium financing stays insurance and carries its flag. Find the lenders the classifier misses today (card-paid, check-paid, unknown fixed daily/weekly debits), publish the flagged groups in the analysis payload (`metrics.flagged_groups`, `detection.flagged_positions`) without touching lender math, and ship the before/after census that proves it (spec §9).

**Architecture:**
- `analysis/transaction_classifier.py` gains nine states and two record fields (C4). It routes every payee lookup through S1's compiled matchers (C3) and applies the spec's rule order:
  - every lookup is compiled once (§4.6);
  - a credit from a financing group is proceeds (D1, §4.4);
  - the known payee comes after fee/transfer/tax/payroll/utility, with the D8 POS exception and the D9 LOC override;
  - the insurance rule consults `PREMIUM_FINANCE_ALIASES` first and flags premium financing (§4.2);
  - obligation descriptors cover unnamed payees (D4, D5);
  - D11 naming, D10 servicers and the D6 recurrence tier follow.
- `analysis/metrics.py` sums flagged rows into `metrics.flagged_groups`; `analysis/detect.py` groups them into `FlaggedPositionMatch` entries with a cadence from the new `analysis/cadence.py`, and its recurring-debit view also lists the D6 rows; `analysis/serialization.py` publishes them (C5).
- The CLI (`batch.py`, `analyze.py`), the MoneyThumb benchmark and the docs follow. `CLASSIFICATION_VERSION` becomes `"5.0"` and `ANALYSIS_STAGE_VERSION` becomes 19 in the first commit that changes classifier output.
- `tools/lender_census.py` re-classifies the local artifact cache with the code before and after the change and compares the two (local only).

**Tech Stack:** Python 3.14 (`C:\Python314\python.exe`), pytest 9, dataclasses, `re`, `sqlite3`; no new dependency.

## Global Constraints

- Only MCA/revenue-based funders and equipment financing are lenders (`confirmed_lender`). Nothing else enters `lender_*`, `withholding_*`, `eligible_deposits` (except the D1 proceeds exclusion) or the package `decision`.
- Every flag group has a Settings key, default `True`, applied at serving time. Unticking hides only (D7).
- Counterparty names and aliases live **only** in `analysis/classification_registry.py`. The guard is `tests/test_no_statement_hardcodes.py:85-87`, and there is no second exempt module.
- **Privacy:**
  - Tests use fabricated descriptors only.
  - Never commit statement text, amounts, account numbers, dates or customer names.
  - Commit messages quote no statement values.
  - Re-pinned regression expectations use derived totals only.
- `CLASSIFICATION_VERSION = "5.0"` and `ANALYSIS_STAGE_VERSION = 19` land in the same commit as the classifier change (S2).
- Run tests with `C:\Python314\python.exe -m pytest tests/<files> -q -p no:cacheprovider`. **Always pass paths under `tests/`**: a bare `pytest` also collects `discovery_reports/`.
- Known failure that predates this work, and must not be attributed to it: `tests/test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`.
- Write or patch Python with the Write/Edit tools, not with Bash heredocs (the Bash tool mangles backslashes here). Restart Flask after template edits.
- Subagents: Opus 5.5 only, never Fable. Each service runs on its own branch, and only the orchestrator merges.
- No payee or brand literals in `webapp/static/app.js` (`tests/test_revenue_classification.py:812-844`, `tests/test_lender_insurance_classification.py:566-584`). Every `formatMoney(` call passes an explicit currency (`tests/test_package_currency.py:773-796`).

**S2-specific constraints**

- **Branch.** Work on `ld-s2-classifier`, created from `lender-detection` after S1 has merged. Never merge or push; the orchestrator does.
- **S1 and the ledger own the lists.** S2 consumes C1-C3 exactly as the master plan states them. Since C10, S1 renders every alias table from the curated ledger `docs/lender-registry-ledger.json`, which the orchestrator produces, and S1's drift test holds the rendered block equal to that ledger. S2 never edits `analysis/flag_groups.py`, `analysis/payee_matcher.py`, the ledger, S1's renderer and validator (`tools/build_lender_registry.py`), or any alias table.
  - The one exception is the classifier's retired inputs. These are today's lists, kept verbatim for the pre-S2 classifier and not rendered from the ledger: `LEASE_PROVIDER_ALIASES`, `LEGACY_CONFIRMED_LENDER_ALIASES` and `LEGACY_POTENTIAL_LENDER_ALIASES`, with their "Deprecated" header comment, in `analysis/classification_registry.py`.
  - Task 5 removes their last readers, so Task 6 deletes each one that is present (C2 removes `LEASE_PROVIDER_ALIASES`). Task 6 then re-runs S1's tests, drift test included.
  - This plan cites S1 by contract (C1-C3, C10) and by file or test name, never by S1 task number: S1 is revised in parallel, and its numbers move.
- **S1's facts are prerequisites.** The section "Prerequisites from S1" lists every S1 fact this plan's code and pins rely on: facts about S1's code, and facts about the content of the C10 ledger. Task 0 checks each one, and any FAIL line stops S2. The orchestrator settles a failed fact (a code fact in S1, a content fact in the ledger, which S1 then re-renders) or gives S2 the ruled values. S2 never works around one.
- **Group registries are read through `PAYEE_GROUP_REGISTRIES` / `match_known_payee` only.** `BANK_NAME_ALIASES` and `CARD_ISSUER_CONTEXT_ALIASES` are read only by the step-8 descriptor rule. `PREMIUM_FINANCE_ALIASES` is not a group registry (C2); it is read only by the insurance rule (Task 7). `INSURANCE_PROVIDER_ALIASES`, `PREMIUM_FINANCE_ALIASES`, `POTENTIAL_LENDER_ALIASES`, `OPERATING_REVENUE_SOURCE_ALIASES` and `BANK_SPECIFIC_LENDER_ALIASES` go through `registry_match`.
- **New fabricated test amounts are whole dollars** (the privacy canaries flag cent figures; `tests/test_webapp_studio_views.py:16`).
- **One stage-19 change set.** Task 2 is the first commit that changes classifier output, so it carries both version bumps and the cache pin. Tasks 4-14 change output further under the same stage 19; the branch merges as one unit and no intermediate commit is ever served.
- **Real-statement re-pins are measured, not guessed.** The derived totals below come from two measurements:
  - read-only probes on 2026-09-24/25 that ran today's code and registry plus this plan's rules (BDC out, BlueVine to lines of credit, NMEF in, D6 with this plan's payee words);
  - a dry run of this whole plan on 2026-09-25, on a scratch copy of the pre-C10 S1 revision. Its builder had built the registry (eleven groups) from the research files. The dry run reproduced every value in the pin ledger, including the two variants that registry selected (the 2026-09-25 decisions leave one: see "Prerequisites from S1", fact 8).

  A probe after the owner's amendment found no premium-finance, floor-plan or factoring wording in any pinned statement.

  C10 replaced that builder's inputs with the curated ledger, so S1's merged tables can differ from the dry run's. The owner delegated every open ledger question on 2026-09-25, and the orchestrator's decisions are owner rulings (the S2 amendments of that date). Read-only probes of 2026-09-25/26 measured the pinned statements again on the revised ledger's rendering (S1 at `b69d12e`), counts and derived totals only. Every value below that moved with those decisions is that measurement. The derived totals depend only on which rows of the pinned statements the tables claim, and Task 0 measures exactly that on S1's merged tree:
  - no FAIL line: the pin ledger holds;
  - a FAIL line: the orchestrator settles the ledger entry, or gives S2 new derived values ("Prerequisites from S1").

  If a pinned test moves to any value this plan does not list, **stop and report the test id to the orchestrator; never re-pin to whatever the code produces.**
- **Commits.** Each commit step gives the exact `git add` paths and the subject line. The subject names no statement value. The attribution lines follow as a second `-m`, as the S4 and S5 plans do:
  - The `Co-Authored-By` line is fixed for an Opus 5.5 (1M context) cell.
  - The `Claude-Session` URL belongs to the session that commits. Take it from that session's system reminder, which is the only place it exists, and put it where the step shows `<the Claude-Session URL from your system reminder>`.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `analysis/cadence.py` | Create | `describe_cadence`: names a payee's payment rhythm for display (C5). |
| `analysis/transaction_classifier.py` | Modify | States, record fields and flags (C4); compiled lookups (§4.6); financing-proceeds credits (§4.4); the premium-financing flag in the insurance rule (§4.2); rule order (§4.3); potential tier (§4.5); `flagged_payee`. |
| `analysis/metrics.py` | Modify | `Metrics.flagged_groups` (C5). |
| `analysis/detect.py` | Modify | `FlaggedPositionMatch`, `find_flagged_positions`, `DetectionResult.flagged_positions`; the recurring-debit view lists D6 rows. |
| `analysis/serialization.py` | Modify | `detection.flagged_positions` in the payload (C5). |
| `analysis/classification_registry.py` | Modify only if S1 left them | Delete the retired classifier inputs `LEASE_PROVIDER_ALIASES`, `LEGACY_CONFIRMED_LENDER_ALIASES`, `LEGACY_POTENTIAL_LENDER_ALIASES` and their "Deprecated" header comment (Task 6). |
| `webapp/artifact_cache.py` | Modify | `ANALYSIS_STAGE_VERSION = 19` and its changelog entry. |
| `batch.py` | Modify | `flagged_positions` CSV column. |
| `analyze.py` | Modify | "Flagged positions" block in the text report. |
| `benchmark/lenders.py` | Modify | `flagged_lender_groups` replaces `NON_MCA_SCOPE`. |
| `benchmark/compare.py` | Modify | MoneyThumb lenders we flag are "flagged here", not misses. |
| `tools/lender_census.py` | Create | The before/after census over the local artifact cache (spec §9); local only. A gained lender passes only when the C10 ledger admits it as a lender. |
| `docs/transaction-classification.md` | Modify | State list, precedence, naming, metrics, extension rule for version 5.0. |
| `docs/moneythumb-replacement/R1_HARDCODE_LOG.md` | Modify | Item 12a amendment: Intuit moved to alternative positions. |
| `tests/flag_group_fixtures.py` | Create | Fabricated rows, fake payees, fake insurers and a report builder shared by the S2 tests (not collected: no `test_` prefix). |
| `tests/test_cadence.py` | Create | `describe_cadence` table. |
| `tests/test_flag_group_states.py` | Create | States, versions, record flags, statement-pass clearing. |
| `tests/test_classifier_lookups.py` | Create | One normalization per row; the compiled ACH token; the 300-row synthetic statement. |
| `tests/test_financing_proceeds_credits.py` | Create | D1 in both classification and revenue; floor-plan and factoring credits; credits that say they are proceeds; payout credits and platform settlements stay revenue. |
| `tests/test_known_payee_classification.py` | Create | Step 7, D8, D9, owner-ruled payees (floor plan and factoring included), the overdraft-charge fee, the membership and top-up exception, payout credits, card payments, the `analysis/lenders.py` helpers, the retired inputs. |
| `tests/test_premium_financing.py` | Create | Premium financing stays insurance and carries its flag (§4.2), by payee or by wording. |
| `tests/test_obligation_descriptors.py` | Create | Step 8 (the own-account guard, floor-plan payoffs, LOC, mortgage, vehicle, student loans, D5, lease, cards, D4). |
| `tests/test_unknown_payee_naming.py` | Create | D11 naming, D10 servicers and the unnamed loan payment (D5). |
| `tests/test_recurring_fixed_debits.py` | Create | D6 recurrence tier and the recurring-debit view. |
| `tests/test_flagged_positions_payload.py` | Create | `metrics.flagged_groups`, `detection.flagged_positions`, CLI output. |
| `tests/test_lender_census.py` | Create | The census over a fabricated cache, fabricated snapshots and a fabricated C10 ledger. |
| `tests/test_artifact_cache.py` | Modify | Stage pin 18 -> 19. |
| `tests/test_lender_insurance_classification.py` | Modify | Order table, named-alias, unidentified-loan, Lily Advance and own-loan, Audit Bank, potential-serialization, duplicate-potential and TD CMCA pins. |
| `tests/test_transaction_classifier.py` | Modify | ATB November lender and potential pins. |
| `tests/test_revenue_classification.py` | Modify | ATB November lender and potential pins; NETCREDIT row (check only). |
| `tests/test_analysis.py` | Modify | SBA, Affirm card purchase and De Lage Landen pins. |
| `tests/test_r1_hardcodes.py` | Modify | Item 12a pins: AFC Funding and Intuit. |
| `tests/test_new_statement_corpus.py` | Modify | first_farmers and navigant lender tuples, relay channels; the first_farmers BlueVine test. |
| `tests/test_benchmark_harness.py` | Modify | Flagged-here benchmark tests. |

`analysis/lenders.py` needs no edit: it reads `CONFIRMED_LENDER_ALIASES`, which C2 keeps as the name of `LENDER_ALIASES`, and its helpers call `classify_transaction`. Task 5 guards its behavior.

### Pin ledger (every existing assertion this plan moves)

Line numbers are those verified on `lender-detection` at `4f219cd`. S1 may have edited some of these lines to keep its own tree green; each task below says what the line must **read** after S2, whatever it reads when you start.

| # | Location | Today | After S2 | Task | Cause |
|---|---|---|---|---|---|
| 1 | `tests/test_lender_insurance_classification.py:52-60` (order table) | NMEF, Navitas, Balboa, Progressive Leasing, Econolease, Clover, SmartPay as `lease_or_equipment_financing`; ATB Mastercard and Capital One rows with entity `None` | rows leave the order table. `tests/test_known_payee_classification.py` pins NMEF/Navitas/Balboa and Econolease `confirmed_lender`, Progressive Leasing `lease_or_rental`, the card rows `credit_cards`, and `SmartPay Sol debitpmt` unflagged (`other`, no entity; SmartPay itself is pinned by a fabricated `SMARTPAY LEASING payment`). `tests/test_obligation_descriptors.py` (Task 8) pins `Clover equipment rent/leases` as `lease_or_rental` by its lease wording, with no entity | 5 (Clover: 8) | §2, §4.1, §4.3; owner decisions 2026-09-25 (Econolease a lender, Clover Equipment in review, SMARTPAY SOL is SmartPay Solutions) |
| 2 | same file `:108` | SNAP Finance `potential_lender` | `lease_or_rental`, `SNAP Finance` | 5 | §2 (lease-to-own) |
| 3 | same file `:111` | BDC `confirmed_lender` | `alternative_position`, `BDC` | 5 | §2 |
| 4 | `tests/test_r1_hardcodes.py:536-539` | Intuit `confirmed_lender` | `alternative_position`, flagged group `alternative_positions` | 5 | §7 (Item 12a amended) |
| 5 | `tests/test_r1_hardcodes.py:541-545` | software charge not lender/potential | also not `alternative_position` | 5 | §5 alias rule |
| 6 | `tests/test_analysis.py:3348-3364` | `SBA LOAN PAYMENT` implicitly `potential_lender` | row is `alternative_position`; potential count 0; `flagged_groups == {"alternative_positions": {"count": 1, "total": 750.0, "payees": 1}}` (the test's own fabricated row) | 5, 11 | §9 |
| 7 | `tests/test_analysis.py:3572-3579` | Affirm card purchases `pos`, `pos_count == 2` | both `alternative_position`; `pos_count == 0`; `find_known_funders == []` | 5 | D8 |
| 8 | `tests/test_analysis.py:3582-3588` | funders `["FUNDWORKS"]` | `["FUNDWORKS", "De Lage Landen"]` | 5 | §2 equipment financing; §9 lists De Lage Landen |
| 9 | `tests/test_transaction_classifier.py:314-316, 329, 347-348, 367-369` | ATB Nov lenders 3 / 43 rows / 8658.91; funders {BDC, CanaCap, Forward Funding} | 3 / 45 / 9757.26; {CanaCap, Econolease, Forward Funding}; one `alternative_position` row | 5 | §2 (BDC); owner decision 2026-09-25 (Econolease is equipment finance: its three rows join the lenders) |
| 10 | `tests/test_transaction_classifier.py:317-326, 333-346, 349, 351-360, 370-374, 376-385` | ATB Nov potential 1 lender / 1 row / 571.88 / 0.96, `Unidentified lender obligation` | 2 potential lenders / 22 rows / 3178.19 / 5.36, every row `candidate_lender_alias`: `MERCH PAD (probably Merchant Growth)` 21 rows / 2606.31 and `LOANS FC` 1 row / 571.88 | 5 | C10 ledger: MERCH PAD (owner decision 2026-09-25) and LOANS FC are review entities of `POTENTIAL_LENDER_ALIASES`, read at step 11 once Task 5 reads the rendered table. D6 then finds nothing left to promote on this statement |
| 11 | `tests/test_revenue_classification.py:402-404` | ATB Nov 3 / 43 / 8658.91 | 3 / 45 / 9757.26 | 5 | as row 9 |
| 12 | `tests/test_revenue_classification.py:405` | potential 571.88 | 3178.19 | 5 | as row 10 |
| 13 | `tests/test_revenue_classification.py:168` | NETCREDIT revenue entity `NETCREDIT` | stays `NETCREDIT` (financing proceeds); restore it if S1 changed it | 4 | D1 |
| 14 | `tests/test_new_statement_corpus.py:122` | first_farmers `(1, 100.00, 0, 0.00)` | `(0, 0.00, 0, 0.00)`; new test: first_farmers has no `line_of_credit` row and `lenders_detected == 0` (its BlueVine-named row is unflagged `other`) | 5, 11 | owner decision 2026-09-25: the bare `BLUEVINE` alias is dropped; the row pays another business that banks with Bluevine |
| 15 | `tests/test_new_statement_corpus.py:153` | navigant `(0, 0.00, 1, 1191.00)` | `(0, 0.00, 4, 1299.00)` (Task 10). **Bank-name variant** (Task 0 prints `navigant: open loan debits naming a listed bank` of 1 or more): `(0, 0.00, 0, 0.00)` in Task 8, then `(0, 0.00, 3, 108.00)` in Task 10. The revised ledger selects the variant (Task 0 reads 2: Beacon Bank loan payments). navigant's three Comenity card debits (Task 0's card line reads 3) are `other` today and become `credit_card_payment`, and so do its Wayfair and Amazon Store Card debits (card-group known payees, which Task 0 leaves out of its non-card count). None of them is one of D6's three rows, so the tuple does not move | 10 (variant: 8, 10) | D6 (and D5) |
| 16 | `tests/test_artifact_cache.py:487-493` | stage 18 | stage 19 | 2 | §6 versions |
| 17 | `tests/test_new_statement_corpus.py:181` | relay channels `(2, 8, 66, 9, 0, 0)` | `(2, 8, 59, 9, 0, 0)`: seven card-paid personal-loan rows (Klover 5, Tilt 2) leave POS | 5 | D8; the C10 ledger admits relay's personal-loan payees (Task 0 reads 8 claimed rows, 7 of them POS) |
| 18 | `tests/test_r1_hardcodes.py:530-534` | AFC FUNDING CORP `confirmed_lender`, in withholding | `floor_plan_financing`, flagged group `floor_plan`, not in withholding | 5 | owner decision 2026-09-25: AFC Funding Corporation funds dealer floor plans (Item 12a amended) |
| 19 | `tests/test_lender_insurance_classification.py:105-107` | CMCA Finance (two rows) and Lily Advance `potential_lender` | `confirmed_lender`, entities `CMCA Finance` and `Lily Advance` | 5 | owner decision 2026-09-25: both are MCA funders |
| 20 | same file `:130-145` | `Direct Debit Loans FC` is the unidentified direct-debit loan | the rule is pinned on the fabricated `Direct Debit Loans`; `Direct Debit Loans FC` is the review entity `LOANS FC` (`candidate_lender_alias`) | 5 | C10 ledger: LOANS FC is a review entity (it predates the 2026-09-25 decisions) |
| 21 | same file `:196` and `:199-204` | the three Lily Advance rows `potential_lender`; `PAYMENT - AUTOMATIC LOAN PYMT W/D` `potential_lender`, `Unidentified lender obligation` | Lily Advance `confirmed_lender` (Task 5); the automatic loan payment `bank_loan`, no entity, `own_bank_loan_payment` (Task 8) | 5, 8 | owner decision 2026-09-25 (Lily Advance); the decisions' D5 own-loan wording (`d5_own_loan_wording_en`) |
| 22 | same file `:275-364` (Audit Bank fixture) | 2 lenders / 3 rows / 2235.0 / 13.23; CMCA Finance potential 1 row / 125.0 | 4 lenders (CanaCap, CAN Capital, CMCA Finance, Econolease) / 5 rows / 2660.0 / 15.74; no potential lender; the package decision stays `review_required` (its customer deposit needs revenue review, measured 2026-09-26) | 5 | owner decisions 2026-09-25 (CMCA Finance and Econolease are lenders) |
| 23 | same file `:367-380` | serializes the fixture's CMCA Finance candidate | the fixture plus one fabricated `Direct Debit Loans` row supplies the candidate; the package's stale-candidate rebuild (from row 25) moves here | 5 | as row 22 |
| 24 | same file `:405-422` | duplicate CMCA Finance rows stay out of the potential totals | the same rows with the fabricated `Direct Debit Loans` descriptor, same counts | 5 | as row 19 |
| 25 | same file `:474-563` (TD CMCA) | potential 1 / 20 rows / 2235.0 / exposure 13.23; withholding 0 | lender 1 (`CMCA Finance`) / 20 rows / 2235.0 / withholding 13.23; no potential lender; the package decision stays `review_required` (revenue review, measured 2026-09-26) | 5 | as row 19 |
| — | ATB Dec (`tests/test_revenue_classification.py:599-676`), ATB Aug (`tests/test_transaction_classifier.py:289-304`), RBC Jan (`tests/test_transaction_classifier.py:245-272`) | — | no edit: none of these tests reads lender or potential figures. They move unasserted (probe of 2026-09-26 on the revised ledger, counts only): BDC leaves the ATB Aug and ATB Dec lenders (one row each) and Econolease joins them (three rows each); the review tier takes MERCH PAD's registry rows (22 on ATB Aug, 19 on ATB Dec) and ATB Aug's `LOANS FC` row; D6 adds `recurring_fixed_debit` review rows, all named `Unidentified lender obligation`, only on RBC Jan (6). The owner sees these counts in the Task 17 report. | — | — |
| — | Altana (`tests/test_analysis.py:1342`) | `lender_debits > 0` | no edit: Affirm leaves, NMEF (2/1/4 rows) joins, so it stays true | — | — |
| — | Amendment groups (floor plan, factoring, premium financing) and the rules of the 2026-09-25 decisions on every statement above | — | no edit: the probes found none of their wording in these statements, apart from navigant's two loan-payment rows that the bank-name rule claims first, and no existing test names one of their payees; Task 0 re-checks against S1's tables | — | — |

---

## Prerequisites from S1 (notes for S1 and the orchestrator)

S2's code and pins rely on the S1 facts below. Task 0 checks each one on S1's merged tree, and any FAIL line stops S2.

- **Two kinds of fact.**
  - **Code facts:** facts 7 and 10 and the code half of fact 1 are about S1's code.
  - **Content facts:** all the others are about the content of the C10 ledger (`docs/lender-registry-ledger.json`), because S1 renders every alias table from it. They cover which entities are `admitted`, in which `group`, under which `entity` spelling, and with which aliases.
- **Who settles a failure.**
  - The orchestrator settles a failed code fact in S1.
  - It settles a failed content fact in the ledger, which it produces (C10). S1 then re-renders the tables, and S1's drift test and `tools/build_lender_registry.py --check` must pass again.
  - Or the orchestrator gives S2 the ruled values.
  - S2 never works around a fact, and never edits the ledger or a rendered table.
- **Why Task 0 checks more than C10's validator.** S1's validator (`tools/build_lender_registry.py --check`, normative for the ledger per the master plan's C10) already refuses a ledger in which any owner-named payee of spec §2 does not resolve to its group, in every group (`OWNER_NAMED_PAYEES`): the equipment lenders, the owner-named payees of the amendment groups, the lease-to-own names and Truist included. It also keeps today's `entity` name on the entity that holds today's first alias. Task 0 re-checks some of those facts on the merged tree. The validator does not check the following:
  - the `entity` spelling of every payee a test pins by name, beyond the first-alias rule, and that each rendered table is keyed by the ledger's `entity` (fact 9);
  - NETCREDIT in a `FINANCING_STATES` group, Econolease, CMCA Finance and Lily Advance admitted as lenders, and Clover Equipment in the review tier (fact 6);
  - that the bare `BLUEVINE` and `SMARTPAY SOL` claim nothing, and that `EBF HOLDINGS` is no entity of its own (facts 3, 4 and 9);
  - that no alias claims `ACH CAPITAL ONE ... PMT` card payments (fact 5);
  - the reach of the rendered tables, and of the rules the 2026-09-25 decisions added, into the pinned statements, at the counts the pin ledger holds (fact 8), and the navigant variant it selects;
  - the code anchors Tasks 3-5 replace (fact 7).

  S1's content test (`tests/test_lender_registry_content.py`) restates facts 1-6 and 9 on S1's committed registry. Facts 7, 8 and 10 are checked only by Task 0 (S1's validator also refuses a `PAYOUT_CREDIT_ENTITIES` name that is not an admitted entity of a `FINANCING_STATES` group), and Task 0 checks every fact again on the merged tree.
- **History.**
  - S1's first plan draft (2026-09-24) contradicted facts 1-5.
  - The pre-C10 S1 revision of 2026-09-25, whose builder read the research files, carried all of them. This plan's dry run ran Task 0 on that tree: 0 failures, before the C10 checks were added.
  - On 2026-09-25 the owner delegated every open ledger question to the orchestrator, whose decisions are owner rulings. They re-pinned facts 3, 4, 6, 8 and 9 and added fact 10. The orchestrator's `prereq_check.py` checks them on the revised ledger (206 checks, 0 failures). Task 0's reach section was replayed on its rendering (S1 at `b69d12e`), and `EXPECTED` holds those measurements.
  - No C10 ledger has been through Task 0 itself yet.

| # | S1 fact | Why S2 needs it | Task 0 check | If it fails |
|---|---|---|---|---|
| 1 | Code: C1 and C2 as the master plan states them after the owner's amendment: eleven flag groups; `FLOOR_PLAN_ALIASES`, `FACTORING_ALIASES` and `PREMIUM_FINANCE_ALIASES`; `PAYEE_GROUP_REGISTRIES` with ten keys in C2 order, without the premium-finance table; `FINANCING_STATES` including floor plan and factoring. Ledger: the owner-named NextGear Capital (`floor_plan_financing`), RTS Financial (`factoring`), IPFS and First Insurance Funding (`premium_financing`) are `admitted`, with aliases that match `NEXTGEAR CAPITAL`, `RTS FINANCIAL`, `IPFS` and `FIRST INSURANCE FUNDING` | Spec §2 amendment, §4.1, §4.2; every group loop in Tasks 2-14; the owner-named tests of Tasks 4, 5 and 7 | the table-existence, key-order and `FINANCING_STATES` lines; the NextGear, RTS, IPFS and First Insurance Funding lines | S1 amends its code to the master contract. The orchestrator admits the four payees the owner named in spec §2. S2 needs no change. |
| 2 | Ledger: De Lage Landen is an `admitted` `confirmed_lender`, with an alias that matches `DELAGELANDEN` (a spaced `DE LAGE LANDEN` does, by C3's run-together rule) | Spec §2 (equipment financing is a lender), §4.1 (equipment financing becomes `confirmed_lender`), §9 (De Lage Landen is a pin that moves) | `'DIRECT DEB DELAGELANDEN LEASE' -> De Lage Landen / confirmed_lender` | The orchestrator admits De Lage Landen in `confirmed_lender`. If the owner rules instead that it stays a lease, the orchestrator gives S2 these ruled values: the Task 0 line expects `lease_or_rental`, and pin-ledger row 8 stays `["FUNDWORKS"]`. |
| 3 | Ledger: the `admitted` `line_of_credit` entity `BLUEVINE` holds `BLUEVINE CAPITAL` (the owner-named spelling) and `BLUEVINE LOAN`, and no bare `BLUEVINE` | Spec §2 (BlueVine is a line of credit). Owner decision 2026-09-25: the bare alias took Bluevine Bill Pay payments and receipts between other businesses and transfers to or from Bluevine checking accounts, not the line of credit (S1's alias audit denied all five such payee keys). first_farmers' one BlueVine-named debit is such a payment, so it leaves the lenders and is unflagged (§9's first_farmers move). §5's transfer sentence is settled by dropping the alias; S2's rule order still keeps transfers at step 6, ahead of the matcher (`test_fee_and_transfer_precedence_survives_the_real_matcher`) | `'BLUEVINE loan payment' -> BLUEVINE / line_of_credit`; `'BLUEVINE CAPITAL' -> BLUEVINE / line_of_credit`; `first_farmers: non-card debit rows claimed = 0` | The orchestrator restores the ledger to the owner decision, and S1 re-renders. S2 never re-admits the bare alias. |
| 4 | Ledger: the `admitted` `lease_or_rental` entity `SmartPay` (SmartPay Leasing, the lease-to-own company) holds `SMARTPAY LEASING`. `SMARTPAY SOL` belongs to the rejected SmartPay Solutions, LLC (S1's `REATTRIBUTED_REGISTRY_ALIASES`), so no rendered alias claims it | Spec §2 names SmartPay under Leases & rentals. Owner decision 2026-09-25: the `SMARTPAY SOL DEBITPMT` rows are SmartPay Solutions' insurance premium billing, so they stay unflagged. §5's SmartPay/Atlas collision needs only the bare alias left out | `'SMARTPAY LEASING payment' -> SmartPay / lease_or_rental`; `'SmartPay Sol debitpmt' matches no known payee and no potential alias` | The orchestrator restores the ledger to the owner decision, and S1 re-renders. |
| 5 | Ledger: no entity carries today's lender alias `ACH CAPITAL`, or any other alias that `ACH CAPITAL ONE ... PMT` card payments contain | Step 7 now runs before the card rules. `ACH CAPITAL` (11 characters) is the longest alias in `ACH CAPITAL ONE ... PMT`, so it would count Capital One card payments as lender debits | `'ACH Capital One TYPE: ONLINE PMT' is not claimed by a lender or financing alias` | The orchestrator drops the alias from the ledger (the entity `rejected`, or a narrower alias) and records why in the entity's `notes`. |
| 6 | Ledger: `NETCREDIT` is an `admitted` entity of a `FINANCING_STATES` group; Econolease (equipment finance), CMCA Finance and Lily Advance (merchant cash advance funders) are `admitted` `confirmed_lender` entities and no potential-lender entity; Clover Equipment renders into `POTENTIAL_LENDER_ALIASES` (status `review`) and is no known payee; Truist is an `admitted` `bank_name`; no bare platform name is an alias outside the operating registry (C10's validator refuses one) | Pin-ledger rows 1, 9, 11, 13 and 19-25 (owner decisions 2026-09-25); spec §5 and §9 (acceptance 4). Every Clover Equipment alias carries lease or rental wording, which step 8 reads before the potential tier, so its rows are `lease_or_rental` with no entity (Task 8) | one line each | The orchestrator restores the entry in the ledger. |
| 7 | Code: the classifier as S1 leaves it: the legacy lists under their `LEGACY_*` names, `from .payee_matcher import registry_match` after the revenue import, and a delegating `_registry_match` | Tasks 3-5 replace these exact lines | the `classifier anchor ... appears once` lines | S1 restores those edits, or the orchestrator gives S2 the new anchors. |
| 8 | Ledger: the rendered tables reach no other row of the pinned statements: known-payee claims, lender rows and totals, POS rows, new financing credits, potential-registry hits, card-issuer context and bank names, at the counts in Task 0 (measured on the revised ledger, 2026-09-25/26). Nor do the rules of the 2026-09-25 decisions (Tasks 4, 5 and 7-9), apart from navigant's two loan-payment rows, which the bank-name rule claims first | Every real-statement pin in the pin ledger | the per-statement lines | The orchestrator decides whether the new reach is intended. If it is, it gives S2 derived re-pin values; if not, it changes the ledger. One variant is pre-measured: navigant's bank-name rows (pin-ledger row 15), which the revised ledger selects (Task 0 reads 2). relay's card-paid personal-loan payees are no longer a variant: the revised ledger claims 8 of relay's debits, 7 of them POS (pin-ledger row 17). |
| 9 | Ledger: each payee a test pins by name keeps today's canonical spelling as its `entity`, or the spelling the owner decisions of 2026-09-25 gave it, and each rendered table is keyed by the ledger's `entity` (S2's reading of C10's rendering; Task 0 checks it on the lender table): `NMEF`, `Navitas Credit Corp`, `Balboa Capital`, `De Lage Landen`, `FORA FINANCIAL`, `ONDECK`, `CanaCap`, `CAN Capital`, `Forward Funding`, `Forward Financing`, `RAPID FINANCE`, `KAPITUS`, `FUNDWORKS`, `Econolease`, `CMCA Finance`, `Lily Advance`, `PAYABILITY`, `EVEREST BUSINESS FUNDING` (which holds the merged `EBF HOLDINGS`), `BDC`, `AFFIRM`, `INTUIT FINANCING`, `SQUARE CAPITAL`, `SHOPIFY CAPITAL`, `PAYPAL WORKING CAPITAL`, `CAPITAL INFUSION`, `Sezzle Inc`, `BLUEVINE`, `FUNDBOX`, `KABBAGE`, `AFC FUNDING CORP` (floor plan), `SNAP Finance`, `Progressive Leasing`, `SmartPay`, `NETCREDIT`, `FIRST Insurance Funding` (premium finance), and the review entities `Clover Equipment`, `LOANS FC` and `MERCH PAD (probably Merchant Growth)` | The existing pins and S2's new tests compare `canonical_entity` exactly (for example ATB November's funder and candidate sets, the De Lage Landen funder list, Item 12a's `INTUIT FINANCING` and `AFC FUNDING CORP`), and the census traces every gained lender to a ledger `entity` (Task 15) | the entity names in the owner-ruled, `PAYOUT_CREDIT_ENTITIES`, NETCREDIT, Clover, EBF, `LOANS FC`/`MERCH PAD` and `FIRST INSURANCE DES INSURANCE` lines; `every LENDER_ALIASES entity is an admitted confirmed_lender entity of the ledger` | The orchestrator restores the ruled spelling in the ledger. Or it rules a new spelling and gives S2 the re-pin values of every test that names the entity. |
| 10 | Code: `analysis.classification_registry.PAYOUT_CREDIT_ENTITIES` (owner decision 2026-09-25) names `Sezzle Inc`, `American First Finance, LLC` and `PAYABILITY`, each an entity of a `FINANCING_STATES` group registry | The D1 payout-credit exception (Task 4) reads it: those entities' credits are the account holder's own sales settled by the platform, so they are revenue, and their debits keep their group | `classification_registry.PAYOUT_CREDIT_ENTITIES exists`; `every PAYOUT_CREDIT_ENTITIES name is an entity of a FINANCING_STATES group registry` | S1 restores the name (its validator refuses a name that is not an admitted entity of such a group); the orchestrator restores the ledger entry. |

---

### Task 0: Preconditions (read-only, no commit)

**Files:**
- Create (scratch, never committed): `<your scratchpad>/s2_preconditions.py`

**Interfaces:**
- Consumes: C1 (`analysis.flag_groups`), C2 (`analysis.classification_registry`), C3 (`analysis.payee_matcher`), exactly as the master plan states them, and the C10 ledger `docs/lender-registry-ledger.json` (read only: its schema, and each entry's `entity`, `group` and `status`).
- Produces: nothing in the repo. A pass/fail printout you keep for the final report, and the navigant variant choice (pin-ledger row 15).

- [ ] **Step 1: Check the branch.**

Run: `git branch --show-current`
Expected: `ld-s2-classifier`. If it prints anything else, run `git switch -c ld-s2-classifier lender-detection` and confirm that `git log --oneline -3 lender-detection` shows S1's merge commit at the top.

- [ ] **Step 2: Record the baseline.**

Run each selection and write down every failure:
```
C:\Python314\python.exe -m pytest tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_r1_hardcodes.py tests/test_webapp_settings.py tests/test_package_currency.py tests/test_webapp_app.py -q -p no:cacheprovider
C:\Python314\python.exe -m pytest tests/test_no_statement_hardcodes.py tests/test_new_statement_corpus.py tests/test_webapp_accounts_view.py tests/test_webapp_studio_views.py tests/test_webapp_review_ui.py -q -p no:cacheprovider
C:\Python314\python.exe -m pytest tests/test_analysis.py tests/test_artifact_cache.py tests/test_benchmark_harness.py tests/test_batch.py -q -p no:cacheprovider
```
Expected: the known pre-existing failure `tests/test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`, plus nothing else (the dry run's pre-C10 S1 tree gave `404 passed`; `146 passed, 1 failed`; `306 passed`). If S1 left other red tests for S2 (for example pins in the pin ledger above), list them; the tasks below settle every pin-ledger row.

- [ ] **Step 3: Write the precondition script** to `<your scratchpad>/s2_preconditions.py`:

```python
"""S2 Task 0 (read-only): the S1 facts this plan's code and re-pins depend on.

Prints one line per fact and exits non-zero on any FAIL. It prints fabricated
descriptors, registry names and counts only, never statement text or amounts."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

import analysis.transaction_classifier  # noqa: E402,F401  (must import on S1's tree)
from analysis import classification_registry as registry  # noqa: E402
from analysis.flag_groups import (  # noqa: E402,F401
    FINANCING_STATES,
    FLAG_GROUP_BY_KEY,
    FLAG_GROUP_BY_STATE,
    FLAG_GROUPS,
    FLAG_SETTING_KEYS,
)
from analysis.payee_matcher import AliasIndex, PayeeMatch, match_known_payee, registry_match  # noqa: E402,F401
from analysis.transaction_classifier import normalize_transaction_description as normalize  # noqa: E402

failures: list[str] = []


def check(label: str, ok: bool) -> None:
    print(("ok    " if ok else "FAIL  ") + label)
    if not ok:
        failures.append(label)


# --- The code S2 edits: every anchor Tasks 2-6 replace exists exactly once on S1's tree.
classifier_source = (ROOT / "analysis" / "transaction_classifier.py").read_text(encoding="utf-8")
matcher_source = (ROOT / "analysis" / "payee_matcher.py").read_text(encoding="utf-8")
check(
    "analysis/payee_matcher.py does not import the classifier (no import cycle)",
    "transaction_classifier" not in matcher_source,
)
for anchor in (
    "from .classification_registry import (\n",
    "    OPERATING_REVENUE_SOURCE_TYPES,\n)\n",
    "from .dates import parse_date\n",
    "from .payee_matcher import registry_match\n",
    "def _contains_alias(text: str, alias: str) -> bool:\n",
    "def _registry_match(\n",
    "def match_verified_lender_alias(description: str) -> tuple[str, str] | None:\n",
    "def _classify_credit_revenue(\n",
    "def classify_transaction(\n",
    '        is_ach=_contains_alias(text, "ACH"),\n',
):
    check(f"classifier anchor {anchor.strip()!r} appears once", classifier_source.count(anchor) == 1)
check(
    "the classifier reads today's lists under S1's deprecated names",
    all(name in classifier_source for name in (
        "LEGACY_CONFIRMED_LENDER_ALIASES", "LEGACY_POTENTIAL_LENDER_ALIASES", "LEASE_PROVIDER_ALIASES",
    )),
)

# --- C1 and C2 as the master plan states them (eleven flag groups).
for name in (
    "LENDER_ALIASES", "ALTERNATIVE_POSITION_ALIASES", "LINE_OF_CREDIT_ALIASES",
    "CARD_ISSUER_ALIASES", "VEHICLE_FINANCE_ALIASES", "MORTGAGE_SERVICER_ALIASES",
    "LEASE_RENTAL_ALIASES", "PERSONAL_LOAN_ALIASES", "FLOOR_PLAN_ALIASES", "FACTORING_ALIASES",
    "PREMIUM_FINANCE_ALIASES", "BANK_NAME_ALIASES",
    "CARD_ISSUER_CONTEXT_ALIASES", "POTENTIAL_LENDER_ALIASES", "INSURANCE_PROVIDER_ALIASES",
    "OPERATING_REVENUE_SOURCE_ALIASES", "OPERATING_REVENUE_SOURCE_TYPES",
    "PAYEE_GROUP_REGISTRIES", "CONFIRMED_LENDER_ALIASES", "BANK_SPECIFIC_LENDER_ALIASES",
    "PAYOUT_CREDIT_ENTITIES",
):
    check(f"classification_registry.{name} exists", hasattr(registry, name))
check(
    "CONFIRMED_LENDER_ALIASES is LENDER_ALIASES",
    getattr(registry, "CONFIRMED_LENDER_ALIASES", None) is getattr(registry, "LENDER_ALIASES", object()),
)
group_registries = getattr(registry, "PAYEE_GROUP_REGISTRIES", {})
check(
    "PAYEE_GROUP_REGISTRIES keys are in the C2 order",
    list(group_registries) == [
        "confirmed_lender", "alternative_position", "line_of_credit", "vehicle_financing",
        "mortgage", "personal_loan", "floor_plan_financing", "factoring", "lease_or_rental",
        "credit_card_payment",
    ],
)
premium_registry = getattr(registry, "PREMIUM_FINANCE_ALIASES", {})
check(
    "PREMIUM_FINANCE_ALIASES is not a group registry and shares no entity with one",
    all(table is not premium_registry for table in group_registries.values())
    and not any(entity in table for table in group_registries.values() for entity in premium_registry),
)
check(
    "FLAG_GROUPS keys are in the C1 order",
    [group.key for group in FLAG_GROUPS] == [
        "alternative_positions", "lines_of_credit", "credit_cards", "vehicle_financing", "bank_loans",
        "mortgages", "leases_rentals", "personal_loans", "floor_plan", "factoring", "premium_financing",
    ],
)
check(
    "premium financing is the one flag group without a state",
    [group.key for group in FLAG_GROUPS if group.state is None] == ["premium_financing"],
)
check(
    "FINANCING_STATES is the C1 set",
    FINANCING_STATES == {
        "confirmed_lender", "alternative_position", "line_of_credit", "bank_loan", "vehicle_financing",
        "mortgage", "personal_loan", "floor_plan_financing", "factoring",
    },
)
# Owner decision 2026-09-25: these entities' credits are the holder's own sales settled by the
# platform, so D1 does not make them proceeds (Task 4). Each must be a financing-group payee.
payout_entities = tuple(getattr(registry, "PAYOUT_CREDIT_ENTITIES", ()))
check(
    "every PAYOUT_CREDIT_ENTITIES name is an entity of a FINANCING_STATES group registry",
    bool(payout_entities) and all(
        any(name in table for state, table in group_registries.items() if state in FINANCING_STATES)
        for name in payout_entities
    ),
)
for name in ("LEASE_PROVIDER_ALIASES", "LEGACY_CONFIRMED_LENDER_ALIASES", "LEGACY_POTENTIAL_LENDER_ALIASES"):
    print(f"info  {name} still defined:", hasattr(registry, name))

# --- C10: the curated ledger the tables are rendered from. The census (Task 15) reads it,
# and S2 reads each rendered table as keyed by the ledger's `entity`.
try:
    ledger = json.loads((ROOT / "docs" / "lender-registry-ledger.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    ledger = None
ledger_entries = ledger.get("entities") if isinstance(ledger, dict) else None
check(
    "docs/lender-registry-ledger.json is a schema-1 ledger (C10)",
    isinstance(ledger, dict) and ledger.get("schema") == 1 and isinstance(ledger_entries, list),
)
admitted_lenders = {
    entry.get("entity")
    for entry in (ledger_entries if isinstance(ledger_entries, list) else [])
    if isinstance(entry, dict) and entry.get("status") == "admitted" and entry.get("group") == "confirmed_lender"
}
check(
    "every LENDER_ALIASES entity is an admitted confirmed_lender entity of the ledger",
    bool(admitted_lenders) and set(getattr(registry, "LENDER_ALIASES", {})) <= admitted_lenders,
)


def known(description: str) -> PayeeMatch | None:
    return match_known_payee(normalize(description))


# --- The owner-ruled payees (spec section 2, and the owner decisions of 2026-09-25) and the S1
# facts in "Prerequisites from S1".
OWNER_RULED = (
    ("NMEF Funding 2025A payment", "NMEF", "confirmed_lender"),
    ("Navitas Credit Corp payment", "Navitas Credit Corp", "confirmed_lender"),
    ("Balboa Capital payment", "Balboa Capital", "confirmed_lender"),
    ("DIRECT DEB DELAGELANDEN LEASE", "De Lage Landen", "confirmed_lender"),
    ("CHECKCARD 0102 NMEF FUNDING", "NMEF", "confirmed_lender"),
    ("CHECK 1234 FORA FINANCIAL", "FORA FINANCIAL", "confirmed_lender"),
    ("CHECKCARD 0102 ONDECK CAPITAL", "ONDECK", "confirmed_lender"),
    ("Canacap payment", "CanaCap", "confirmed_lender"),
    ("CAN Capital loan payment", "CAN Capital", "confirmed_lender"),
    ("Direct Debit Business PAD Forward Funding", "Forward Funding", "confirmed_lender"),
    ("Direct Debit Business PAD Forward Financing", "Forward Financing", "confirmed_lender"),
    ("ACH DEBIT RAPID FINANCE PAYMENT", "RAPID FINANCE", "confirmed_lender"),
    ("Orig CO Name:Kapitus Descr:Payment ACH Debit", "KAPITUS", "confirmed_lender"),
    ("ACH DEBIT THE FUNDWORKS LLC PMT", "FUNDWORKS", "confirmed_lender"),
    ("VLFC-Econolease finance payment", "Econolease", "confirmed_lender"),
    ("CMCA Finance BUS payment", "CMCA Finance", "confirmed_lender"),
    ("Lily Advance", "Lily Advance", "confirmed_lender"),
    ("EBF HOLDINGS DEBIT 0001", "EVEREST BUSINESS FUNDING", "confirmed_lender"),
    ("AFC FUNDING CORP XPRESS PAY", "AFC FUNDING CORP", "floor_plan_financing"),
    ("BDC loan payment", "BDC", "alternative_position"),
    ("CARD PURCHASE AFFIRMCOM 0001", "AFFIRM", "alternative_position"),
    ("ACH DEBIT INTUIT FINANCING 0001", "INTUIT FINANCING", "alternative_position"),
    ("SQUARE CAPITAL", "SQUARE CAPITAL", "alternative_position"),
    ("SHOPIFY CAPITAL PAYOUT", "SHOPIFY CAPITAL", "alternative_position"),
    ("PAYPAL WORKING CAPITAL", "PAYPAL WORKING CAPITAL", "alternative_position"),
    ("CAPITAL INFUSION PAYMENT", "CAPITAL INFUSION", "alternative_position"),
    ("BLUEVINE loan payment", "BLUEVINE", "line_of_credit"),
    ("BLUEVINE CAPITAL", "BLUEVINE", "line_of_credit"),
    ("FUNDBOX payment", "FUNDBOX", "line_of_credit"),
    ("KABBAGE payment", "KABBAGE", "line_of_credit"),
    ("External Withdrawal SNAP FINANCE - PAYMENT", "SNAP Finance", "lease_or_rental"),
    ("Progressive Leasing recurring purchase", "Progressive Leasing", "lease_or_rental"),
    ("SMARTPAY LEASING payment", "SmartPay", "lease_or_rental"),
)
for description, entity, state in OWNER_RULED:
    match = known(description)
    check(
        f"{description!r} -> {entity} / {state}",
        match is not None and match.entity == entity and match.state == state,
    )
for description in ("SBA LOAN PAYMENT", "SBA EIDL LOAN PAYMENT"):
    match = known(description)
    check(f"{description!r} -> alternative_position", match is not None and match.state == "alternative_position")
# The owner's amendment (spec section 2): one named payee per new group. The C10 ledger names the entities.
for description, state in (
    ("NEXTGEAR CAPITAL PAYMENT", "floor_plan_financing"),
    ("RTS FINANCIAL PAYMENT", "factoring"),
):
    match = known(description)
    check(f"{description!r} -> {state}", match is not None and match.state == state)
for description in ("IPFS CORP PMT", "FIRST INSURANCE FUNDING PMT"):
    check(
        f"{description!r} is a premium-finance payee and no known payee",
        registry_match(normalize(description), premium_registry) is not None and known(description) is None,
    )
for description in ("SQUARE", "SHOPIFY", "PAYPAL", "STRIPE", "AMAZON", "CARD PURCHASE INTUIT QUICKBOOKS 0001"):
    check(f"bare platform {description!r} is no known payee", known(description) is None)
# The known-payee matcher now runs before the rent and card rules (spec section 4.3 step 7).
# A lender alias that is a prefix of a card issuer or a landlord would take those rows:
# today's lender alias `ACH CAPITAL` claims `ACH CAPITAL ONE ... PMT` card payments.
for description in ("ACH Capital One TYPE: ONLINE PMT", "ATB Mastercard payment", "Office rent payment"):
    match = known(description)
    check(
        f"{description!r} is not claimed by a lender or financing alias",
        match is None or match.state == "credit_card_payment",
    )
netcredit = known("NETCREDIT CCBANK-NTC loan proceeds")
check(
    "NETCREDIT is a financing payee named NETCREDIT",
    netcredit is not None and netcredit.entity == "NETCREDIT" and netcredit.state in FINANCING_STATES,
)
# Owner decisions of 2026-09-25: Econolease, CMCA Finance and Lily Advance are lenders (OWNER_RULED
# above) and no potential-lender entity; Clover Equipment is in review and no known payee; the
# SMARTPAY SOL rows are SmartPay Solutions' premium billing and match nothing; EBF HOLDINGS is merged
# into EVEREST BUSINESS FUNDING, so it is no entity of its own.
clover = registry_match(normalize("Clover equipment rent/leases"), registry.POTENTIAL_LENDER_ALIASES)
check(
    "Clover Equipment is a potential-lender alias (review) and no known payee",
    clover is not None and clover[0] == "Clover Equipment" and known("Clover equipment rent/leases") is None,
)
check(
    "'SmartPay Sol debitpmt' matches no known payee and no potential alias",
    known("SmartPay Sol debitpmt") is None
    and registry_match(normalize("SmartPay Sol debitpmt"), registry.POTENTIAL_LENDER_ALIASES) is None,
)
check(
    "CMCA Finance and Lily Advance are no potential-lender entity",
    not {"CMCA Finance", "Lily Advance"} & set(registry.POTENTIAL_LENDER_ALIASES),
)
check(
    "EBF HOLDINGS is no lender-table entity (merged into EVEREST BUSINESS FUNDING)",
    "EBF HOLDINGS" not in getattr(registry, "LENDER_ALIASES", {}),
)
# Fact 9: names S2's new pins compare exactly. ATB November's review candidates, and the premium
# financier that the bare FIRST INSURANCE originator names (owner decision 2026-09-25).
check(
    "LOANS FC and MERCH PAD (probably Merchant Growth) are potential-lender entities",
    {"LOANS FC", "MERCH PAD (probably Merchant Growth)"} <= set(registry.POTENTIAL_LENDER_ALIASES),
)
first_insurance = registry_match(normalize("FIRST INSURANCE DES INSURANCE"), premium_registry)
check(
    "'FIRST INSURANCE DES INSURANCE' is a premium-finance payee of FIRST Insurance Funding",
    first_insurance is not None and first_insurance[0] == "FIRST Insurance Funding",
)
check(
    "Truist is on the bank-name list",
    registry_match(normalize("TRUIST LN 0001 PYMT"), registry.BANK_NAME_ALIASES) is not None,
)

# --- S1's reach into the real statements whose pins this plan re-derives. Counts only.
from analysis.pipeline import analyze_markdown  # noqa: E402
from ocr.native_text import parse_native_td_canada  # noqa: E402
from tests.test_new_statement_corpus import _source_report  # noqa: E402
from tests.test_transaction_classifier import _real_statement_report  # noqa: E402

td_pdf = ROOT / "Bank Statements" / "TD Can" / "Jan_30-Feb_27_2026 (3).pdf"
td_report = analyze_markdown(
    parse_native_td_canada(td_pdf.read_bytes(), source_file=td_pdf.name).to_markdown(),
    parse_mode="deterministic",
)
reports = {
    "ATB Nov": _real_statement_report("ATB/ATB Nov 2023.pdf"),
    "RBC Jan": _real_statement_report("RBC/Chequing Statement-JAN+.pdf"),
    "Navy Fed June": _real_statement_report("Navy Fed/JUNE 2026.pdf"),
    "TD CMCA": td_report,
    "first_farmers": _source_report("first_farmers"),
    "navigant": _source_report("navigant"),
    "relay": _source_report("relay"),
}
#: (non-card debit rows the matcher claims, lender rows, lender total, debit rows the
#: potential registry matches), measured 2026-09-25/26 on the rendering of the ledger that
#: carries the owner decisions of 2026-09-25 (S1 at b69d12e). ATB Nov: Econolease's three
#: rows join the lenders; MERCH PAD's 21 rows and the LOANS FC row are review entities.
#: RBC Jan: the sixth claimed row is stored as a fee (step 6 keeps it one). Navy Fed June:
#: PAID TO TILT is a personal loan. TD CMCA: CMCA Finance is a lender. first_farmers: the
#: bare BLUEVINE is dropped. relay: three personal-loan payees (Klover, Tilt, Cashli).
#: None of these statements carries floor-plan, factoring or premium-finance wording.
EXPECTED = {
    "ATB Nov": (46, 45, 9757.26, 22),
    "RBC Jan": (6, 6, None, 0),
    "Navy Fed June": (1, 0, 0.0, 0),
    "TD CMCA": (20, 20, 2235.0, 0),
    "first_farmers": (0, 0, 0.0, 0),
    "navigant": (0, 0, 0.0, 0),
    "relay": (8, 0, 0.0, 0),
}
#: POS rows a known payee claims (D8 moves them out of POS; pin-ledger row 17). relay's seven
#: are card-paid personal loans, and every relay row the matcher claims is a personal loan.
POS_CLAIMED = {"relay": 7}
#: The statements whose lender or potential figures a test pins. The step-8 card and
#: bank-name rules must claim none of their open rows, except navigant's: its three Comenity
#: card payments (owner decision 2026-09-25: they are card payments) and its bank-name rows,
#: which pick the variant pins of pin-ledger row 15 (see Step 4).
POTENTIAL_PINNED = ("ATB Nov", "TD CMCA", "first_farmers", "navigant", "relay")
CARD_HITS = {"navigant": 3}
#: S2's card-issuer context wording (Task 8 Step 6), with the decisions' PAYMNT and the payment
#: word glued to a SEC label.
CARD_WORDING = (
    re.compile(r"\b(?:CREDIT CARD|CRCARD|CRD|CARD|CARDMEMBER)\b"),
    re.compile(
        r"\b(?:AUTOPAY|AUTO PAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT|PAYMNT)\b"
        r"|\b(?:AUTOPAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT|PAYMNT)SEC\b"
    ),
)
#: S2's loan wording for the bank-name rule (Task 8): LOAN or LOANS, and French PRET or PRETS.
LOAN_WORD = re.compile(r"\bLOANS?\b|\bPRETS?\b")
#: The words the rules of the owner decisions of 2026-09-25 read (Tasks 5 and 7-9): on debits,
#: the overdraft-charge fee, premium-finance wording, the own-account transfer guard,
#: floor-plan payoffs, home-equity and student loans, French and English own-loan wording,
#: commercial-loan billing, unnamed loan payments, the widened card-payment forms and MCA
#: SERVICING; on credits, per-vehicle floor-plan advances, the bank's own line advance and
#: line-of-credit draws. Measured 2026-09-26: none reaches a pinned statement, apart from
#: navigant's two loan-payment rows, which the bank-name rule claims first.
NEW_DEBIT_RULES = tuple(re.compile(pattern) for pattern in (
    r"\bOVERDRAFT CHARGES?\b",
    r"\bPREM(?:IUM)? ?FIN(?:ANCE|ANCING)?\b", r"\bINSPREMFIN\b",
    r"^TRANSFER (?:TO|FROM) .+ (?:ACCOUNT )?TRANSFER (?:OUT|IN)$",
    r"^PAYOFF (?:19|20)\d\d .*\bVIN\b",
    r"HOME ?EQUITY ?LOANS?\b",
    r"\bSTUDENT ?LOANS?\b", r"\bSTDNT ?LOANS?\b", r"\bSTUDNT ?LOANS?\b", r"\bSTUDENT LN\b",
    r"\bPRETS?\b",
    r"\bORIG CO NAME COMMERCIAL LOAN\b", r"\bSAVINGS BANK LOAN (?:PAYMENT|PMT|PYMT)\b",
    r"\bAUTOMATIC LOAN (?:PAYMENT|PMT|PYMT|PAY)\b", r"\bAUTOMATED LOAN PAYMENT\b",
    r"\bPAYMENT TO (?:CMML |COMMERCIAL )?LOAN\b",
    r"\b(?:INTEREST|PRINCIPAL|LATE CHARGE) PAYMENT CUSTOMER \d+ OBLIGATION \d+",
    r"\bLOANS? (?:PAYMENT|PAYMENTS|PYMT|PMT|REPAYMENT)\b",
    r"\bCREDIT CARD ECS (?:PAYMENT|PMT|PYMT)\b",
    r"\b(?:VISA|MASTER ?CARD) DES (?:PAYMENT|PMT|PYMT|EPAYMENT)\b",
    r"\bORIG CO NAME (?:VISA|MASTER ?CARD) ORIG ID\b.*?\bCO ENTRY DESCR (?:PAYMENT|PMT|PYMT|EPAYMENT)\b",
    r"\b(?:PAYMENT|PMT|PYMT) TO (?:CRD|CREDIT CARD|VSA)\b",
    r"\b(?:PMT|PYMT) TO (?:VISA|MASTER ?CARD|AMEX|AMERICAN EXPRESS)\b",
    r"\bPAYMNT\b", r"\b(?:AUTOPAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT|PAYMNT)SEC\b",
    r"\bMCA SERVICING\b",
))
NEW_CREDIT_RULES = tuple(re.compile(pattern) for pattern in (
    r"^ADVANCE (?:19|20)\d\d .*\bVIN\b",
    r"^LOAN CREDIT$",
    r"\b(?:LOC|LINE OF CREDIT) (?:ADVANCE|ADV|DRAW)\b",
    r"\bADVANCE FROM (?:LOC|LINE OF CREDIT)\b",
    r"\bDRAW (?:ON|FROM) (?:LOC|LINE OF CREDIT)\b",
))
#: The membership and top-up words Task 5 reads right after an alternative-position alias.
MEMBERSHIP_OR_TOP_UP = (r" (?:PLUS|PLU|MEM|MEMB|MEMBER|MEMBERSHIP)\b", r" BALANCE TOP ?(?:UP|U)\b")
for label, report in reports.items():
    records = report.classifications
    debits = [r for r in records if r.amount < 0]
    claimed = [(r, m) for r in debits if (m := match_known_payee(r.normalized_description)) is not None]
    non_card = [pair for pair in claimed if pair[1].state != "credit_card_payment"]
    lenders = [r for r, m in claimed if m.state == "confirmed_lender"]
    pos_claimed = [r for r, _ in claimed if r.classification == "pos"]
    new_proceeds = [
        r for r in records
        if r.amount > 0 and r.classification == "other" and not r.contributes_to_lender_credit_exclusion
        and (m := match_known_payee(r.normalized_description)) is not None and m.state in FINANCING_STATES
    ]
    potential_hits = sum(
        1 for r in debits if registry_match(r.normalized_description, registry.POTENTIAL_LENDER_ALIASES) is not None
    )
    open_rows = [r for r in debits if r.classification in ("other", "potential_lender")]
    card_hits = sum(
        1 for r in open_rows
        if registry_match(r.normalized_description, registry.CARD_ISSUER_CONTEXT_ALIASES) is not None
        and any(pattern.search(r.normalized_description) for pattern in CARD_WORDING)
    )
    bank_hits = sum(
        1 for r in open_rows
        if LOAN_WORD.search(r.normalized_description)
        and registry_match(r.normalized_description, registry.BANK_NAME_ALIASES) is not None
    )
    new_rule_rows = sum(
        1 for r in debits
        if any(pattern.search(r.normalized_description) for pattern in NEW_DEBIT_RULES)
        and not (
            LOAN_WORD.search(r.normalized_description)
            and registry_match(r.normalized_description, registry.BANK_NAME_ALIASES) is not None
        )
    ) + sum(
        1 for r, m in claimed
        if m.state == "alternative_position"
        and any(re.search(rf"\b{re.escape(m.alias)}{tail}", r.normalized_description) for tail in MEMBERSHIP_OR_TOP_UP)
    ) + sum(
        1 for r in records
        if r.amount > 0 and (
            any(pattern.search(r.normalized_description) for pattern in NEW_CREDIT_RULES)
            or ((m := match_known_payee(r.normalized_description)) is not None and m.entity in payout_entities)
        )
    )
    want_claimed, want_lenders, want_total, want_potential = EXPECTED[label]
    check(f"{label}: non-card debit rows claimed = {len(non_card)} (want {want_claimed})", len(non_card) == want_claimed)
    want_pos = POS_CLAIMED.get(label, 0)
    check(f"{label}: POS rows claimed = {len(pos_claimed)} (want {want_pos})", len(pos_claimed) == want_pos)
    if want_pos:
        check(f"{label}: every claimed debit row is a personal loan", {m.state for _, m in non_card} == {"personal_loan"})
    check(f"{label}: lender rows = {len(lenders)} (want {want_lenders})", len(lenders) == want_lenders)
    if want_total is not None:
        total = round(sum(abs(r.amount) for r in lenders), 2)
        check(f"{label}: lender total matches the plan", total == want_total)
    check(f"{label}: credits newly claimed as financing proceeds = {len(new_proceeds)} (want 0)", not new_proceeds)
    check(
        f"{label}: debit rows the potential registry matches = {potential_hits} (want {want_potential})",
        potential_hits == want_potential,
    )
    premium_rows = sum(1 for r in records if registry_match(r.normalized_description, premium_registry) is not None)
    check(f"{label}: premium-finance rows = {premium_rows} (want 0)", premium_rows == 0)
    card_line = f"{label}: open debit rows naming a card issuer with payment wording = {card_hits}"
    if label in POTENTIAL_PINNED:
        want_cards = CARD_HITS.get(label, 0)
        check(card_line + f" (want {want_cards})", card_hits == want_cards)
    else:
        print("info  " + card_line)
    bank_line = f"{label}: open loan debits naming a listed bank = {bank_hits}"
    if label == "navigant":
        print("info  " + bank_line)
    else:
        check(bank_line + " (want 0)", bank_hits == 0)
    check(
        f"{label}: rows the rules of the 2026-09-25 decisions reach = {new_rule_rows} (want 0)",
        new_rule_rows == 0,
    )

print(f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
```

- [ ] **Step 4: Run it.**

Run: `C:\Python314\python.exe <your scratchpad>\s2_preconditions.py`
Expected: every check line `ok` and `0 failure(s)`. Besides the checks it prints:
- three `... still defined:` lines, `True` or `False` (Task 6 handles either; the pre-C10 S1 tree printed `True` for all three);
- `info` lines for the card-issuer count on RBC Jan and Navy Fed June (no test reads the figures those rows would move; the revised ledger reads 3 and 0);
- `info  navigant: open loan debits naming a listed bank = N`. When N is 1 or more, use pin-ledger row 15's bank-name variant (Task 8 Step 11 and Task 10 Step 8). The revised ledger reads 2 (Beacon Bank loan payments), as did the dry run's pre-C10 S1 tree.

The C10 ledger decides the navigant line; it only selects which listed pins apply.

If **any** `FAIL` line prints, stop. Report the FAIL lines to the orchestrator (they carry no statement text) and wait: "Prerequisites from S1" says what settles each fact, and whether the fix belongs in S1's code or in the ledger.

---

### Task 1: The cadence helper

**Files:**
- Create: `analysis/cadence.py`
- Test: `tests/test_cadence.py`

**Interfaces:**
- Consumes: nothing.
- Produces (C5): `analysis.cadence.describe_cadence(dates: Sequence[date]) -> tuple[str, float | None]`, returning one of `"daily" | "weekly" | "biweekly" | "monthly" | "irregular" | "single"` and the mean gap in days rounded to one decimal (`None` for `"single"`). `transaction_classifier.classify_cadence` is untouched.

- [ ] **Step 1: Write the failing test** `tests/test_cadence.py`:

```python
from __future__ import annotations

from datetime import date

import pytest

from analysis.cadence import describe_cadence
from analysis.transaction_classifier import classify_cadence


def _days(*isos: str) -> list[date]:
    return [date.fromisoformat(value) for value in isos]


@pytest.mark.parametrize(
    ("dates", "expected"),
    [
        ([], ("single", None)),
        (_days("2054-01-05"), ("single", None)),
        (_days("2054-01-05", "2054-01-05"), ("single", None)),
        (_days("2054-01-05", "2054-01-06", "2054-01-07", "2054-01-08", "2054-01-09"), ("daily", 1.0)),
        (_days("2054-01-05", "2054-01-12", "2054-01-19", "2054-01-26"), ("weekly", 7.0)),
        (_days("2054-01-19", "2054-01-05", "2054-01-12"), ("weekly", 7.0)),
        (_days("2054-01-01", "2054-01-15", "2054-01-29"), ("biweekly", 14.0)),
        (_days("2054-01-15", "2054-02-15", "2054-03-15"), ("monthly", 29.5)),
        (_days("2054-01-05", "2054-02-04"), ("monthly", 30.0)),
        (_days("2054-01-01", "2054-01-03", "2054-01-20"), ("irregular", 9.5)),
    ],
)
def test_describe_cadence_names_the_rhythm_of_a_payees_dates(dates, expected):
    assert describe_cadence(dates) == expected


def test_the_promotion_cadence_is_unchanged_for_a_monthly_series():
    # classify_cadence gates potential-lender promotion (daily/weekly only) and must not move.
    assert classify_cadence(_days("2054-01-15", "2054-02-15", "2054-03-15")) == ("irregular", 29.5)
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_cadence.py -q -p no:cacheprovider`
Expected: FAIL at collection, `ModuleNotFoundError: No module named 'analysis.cadence'`.

- [ ] **Step 3: Write** `analysis/cadence.py`:

```python
"""The rhythm of a flagged payee's payments (lender-detection design, spec §6).

`describe_cadence` names a payee's debit rhythm for display: the Flagged
positions panel, its exports and the package roll-up. It is deliberately
separate from `transaction_classifier.classify_cadence`, whose daily/weekly
answer gates potential-lender promotion and must not move.
"""
from __future__ import annotations

from datetime import date
from statistics import mean, pstdev
from typing import Sequence


def describe_cadence(dates: Sequence[date]) -> tuple[str, float | None]:
    """One of daily, weekly, biweekly, monthly, irregular or single, and the mean gap.

    Dates are de-duplicated and sorted first. One distinct date is `single`
    with no gap. The mean gap is in days, rounded to one decimal.
    """
    ordered = sorted(set(dates))
    if len(ordered) < 2:
        return "single", None
    gaps = [(later - earlier).days for earlier, later in zip(ordered, ordered[1:])]
    average = mean(gaps)
    spread = pstdev(gaps) if len(gaps) > 1 else 0.0
    rounded = round(float(average), 1)
    if average <= 1.6 and spread <= 1.5:
        return "daily", rounded
    if 5 <= average <= 9 and spread <= 2.5:
        return "weekly", rounded
    if 12 <= average <= 16 and spread <= 3:
        return "biweekly", rounded
    if 26 <= average <= 35 and spread <= 5:
        return "monthly", rounded
    return "irregular", rounded
```

- [ ] **Step 4: Run the test and the layer guard.**

Run: `C:\Python314\python.exe -m pytest tests/test_cadence.py tests/test_no_statement_hardcodes.py -q -p no:cacheprovider`
Expected: PASS, except the known pre-existing `test_no_literal_account_numbers_in_ocr`.

- [ ] **Step 5: Commit.**

```
git add analysis/cadence.py tests/test_cadence.py
git commit -m "analysis: describe_cadence names a flagged payee's payment rhythm" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 2: Flag-group states, record fields, versions

**Files:**
- Modify: `analysis/transaction_classifier.py` (states `:26-62`, version `:64`, `TransactionClassification` `:80-139`, `_build_record` `:800-887`, reversal clearing `:1373-1383`, duplicate clearing `:1543-1555`; add an import after `:19`)
- Modify: `webapp/artifact_cache.py:524`
- Modify: `tests/test_artifact_cache.py:487-493`
- Create: `tests/flag_group_fixtures.py`
- Test: `tests/test_flag_group_states.py`

**Interfaces:**
- Consumes (C1): `FLAG_GROUP_BY_STATE`, `FLAG_GROUPS`.
- Produces (C4): the nine new states in `ClassificationState` and `CLASSIFICATION_STATES` (with `lease_or_equipment_financing` kept); `TransactionClassification.flagged_group: str | None = None` and `TransactionClassification.contributes_to_flagged_totals: bool = False`; `CLASSIFICATION_VERSION = "5.0"`. Produces `ANALYSIS_STAGE_VERSION = 19`.

- [ ] **Step 1: Create the shared fixtures module** `tests/flag_group_fixtures.py`:

```python
"""Fabricated rows and payees for the lender-detection classifier tests (spec §9).

Every descriptor, name and amount here is fabricated: no statement text, no
real amount, no customer name. Amounts are whole dollars.
"""
from __future__ import annotations

from analysis.schema import Transaction


def txn(day: str, description: str, amount: float, *, balance: float | None = None) -> Transaction:
    return Transaction(
        date=day,
        description=description,
        amount=amount,
        direction="credit" if amount >= 0 else "debit",
        running_balance=balance,
    )
```

- [ ] **Step 2: Write the failing test** `tests/test_flag_group_states.py`:

```python
from __future__ import annotations

from typing import get_args

import pytest

from analysis.flag_groups import FLAG_GROUPS
from analysis.schema import Statement
from analysis.transaction_classifier import (
    CLASSIFICATION_STATES,
    CLASSIFICATION_VERSION,
    ClassificationState,
    _build_record,
    classify_statement_transactions,
    classify_transaction,
)
from tests.flag_group_fixtures import txn
from webapp.artifact_cache import ANALYSIS_STAGE_VERSION

#: The flag groups that are classification states. Premium financing is the one
#: group without a state: its rows stay insurance and a rule sets the flag (C1).
STATE_GROUPS = [group for group in FLAG_GROUPS if group.state is not None]


def _record(state: str, amount: float, *, posted: bool = True):
    return _build_record(
        description="FABRICATED ROW",
        text="FABRICATED ROW",
        classification=state,
        amount=amount,
        date_value="2054-01-05",
        bank=None,
        account=None,
        account_name=None,
        source_direction="debit" if amount < 0 else "credit",
        direction_consistent=True,
        source_page=None,
        source_location="transaction:1",
        match_method="test",
        confidence_score=0.9,
        reason="Fabricated test row.",
        is_posted=posted,
    )


def test_the_state_list_carries_every_flag_group_and_the_retired_lease_state():
    assert get_args(ClassificationState) == CLASSIFICATION_STATES
    assert len(set(CLASSIFICATION_STATES)) == len(CLASSIFICATION_STATES)
    for group in STATE_GROUPS:
        assert group.state in CLASSIFICATION_STATES
    assert [group.key for group in FLAG_GROUPS if group.state is None] == ["premium_financing"]
    # Retired in 5.0 but kept, so records stored before 5.0 still validate.
    assert "lease_or_equipment_financing" in CLASSIFICATION_STATES


def test_the_classification_and_analysis_stage_versions_move_together():
    assert CLASSIFICATION_VERSION == "5.0"
    assert classify_transaction("FABRICATED ROW", -10.0).classification_version == "5.0"
    assert ANALYSIS_STAGE_VERSION == 19


@pytest.mark.parametrize("group", STATE_GROUPS, ids=lambda group: group.state)
def test_a_posted_flag_group_debit_contributes_to_flagged_totals_only(group):
    record = _record(group.state, -100.0)
    assert record.flagged_group == group.key
    assert record.contributes_to_flagged_totals
    assert not record.contributes_to_lender_count
    assert not record.contributes_to_lender_totals
    assert not record.contributes_to_withholding_rate
    assert not record.contributes_to_potential_lender_totals
    assert not record.contributes_to_potential_withholding_exposure
    assert not record.contributes_to_insurance_totals


@pytest.mark.parametrize("group", STATE_GROUPS, ids=lambda group: group.state)
def test_a_flag_group_credit_or_unposted_debit_never_contributes(group):
    credit = _record(group.state, 100.0)
    unposted = _record(group.state, -100.0, posted=False)
    assert credit.flagged_group == unposted.flagged_group == group.key
    assert not credit.contributes_to_flagged_totals
    assert not unposted.contributes_to_flagged_totals


@pytest.mark.parametrize(
    "state",
    ["confirmed_lender", "potential_lender", "insurance", "lease_or_equipment_financing", "rent", "other"],
)
def test_a_state_outside_the_flag_groups_carries_no_flag(state):
    record = _record(state, -100.0)
    assert record.flagged_group is None
    assert not record.contributes_to_flagged_totals


def test_a_proven_duplicate_flagged_debit_leaves_the_flagged_totals():
    statement = Statement(
        transactions=[
            txn("2054-01-02", "CREDIT CARD PAYMENT FABRICATED", -250.0, balance=750.0),
            txn("2054-01-02", "CREDIT CARD PAYMENT FABRICATED", -250.0, balance=750.0),
        ]
    )
    first, duplicate = classify_statement_transactions(statement)
    assert first.flagged_group == duplicate.flagged_group == "credit_cards"
    assert first.contributes_to_flagged_totals
    assert duplicate.duplicate_of == "transaction:1"
    assert not duplicate.contributes_to_flagged_totals


def test_a_settlement_reversed_flagged_debit_leaves_the_flagged_totals():
    statement = Statement(
        transactions=[
            txn("2054-01-02", "ACH CREDIT CARD PAYMENT FABRICATED", -250.0),
            txn("2054-01-04", "RETURNED ACH CREDIT CARD PAYMENT FABRICATED", 250.0),
        ]
    )
    debit, credit = classify_statement_transactions(statement)
    assert debit.flagged_group == "credit_cards"
    assert credit.settlement_reversal
    assert debit.reversed_by == "transaction:2"
    assert not debit.contributes_to_flagged_totals
```

- [ ] **Step 3: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_flag_group_states.py -q -p no:cacheprovider`
Expected: FAIL. `test_the_state_list...` fails because `alternative_position` is not in `CLASSIFICATION_STATES`; the record tests fail with `AttributeError: 'TransactionClassification' object has no attribute 'flagged_group'`; the version test fails on `"4.1" == "5.0"`.

- [ ] **Step 4: Replace the state `Literal` and tuple** in `analysis/transaction_classifier.py` (the block from `ClassificationState = Literal[` through `CLASSIFICATION_VERSION = "4.1"`) with:

```python
ClassificationState = Literal[
    "confirmed_lender",
    "potential_lender",
    "insurance",
    "alternative_position",
    "line_of_credit",
    "vehicle_financing",
    "bank_loan",
    "mortgage",
    "lease_or_rental",
    "personal_loan",
    "floor_plan_financing",
    "factoring",
    # Retired in classification version 5.0: no rule produces it, but records
    # stored before 5.0 carry it and must still validate (spec §4.1).
    "lease_or_equipment_financing",
    "fee",
    "transfer",
    "credit_card_payment",
    "payroll",
    "tax",
    "utility",
    "rent",
    "pos",
    "atm",
    "nsf_or_return",
    "refund_or_reversal",
    "other",
]

CLASSIFICATION_STATES: tuple[ClassificationState, ...] = (
    "confirmed_lender",
    "potential_lender",
    "insurance",
    "alternative_position",
    "line_of_credit",
    "vehicle_financing",
    "bank_loan",
    "mortgage",
    "lease_or_rental",
    "personal_loan",
    "floor_plan_financing",
    "factoring",
    "lease_or_equipment_financing",
    "fee",
    "transfer",
    "credit_card_payment",
    "payroll",
    "tax",
    "utility",
    "rent",
    "pos",
    "atm",
    "nsf_or_return",
    "refund_or_reversal",
    "other",
)

CLASSIFICATION_VERSION = "5.0"
```

- [ ] **Step 5: Import the flag groups.** In the import block, after the line `from .dates import parse_date`, add:

```python
from .flag_groups import FLAG_GROUP_BY_STATE
```

- [ ] **Step 6: Add the two record fields.** In `TransactionClassification`, replace

```python
    review_required: bool = False
    revenue_classification: RevenueState | None = None
```
with
```python
    review_required: bool = False
    # Spec §4.2: the FlagGroup.key of a flag-group state, otherwise None.
    flagged_group: str | None = None
    revenue_classification: RevenueState | None = None
```
and replace
```python
    contributes_to_insurance_totals: bool = False
    contributes_to_verified_revenue: bool = False
```
with
```python
    contributes_to_insurance_totals: bool = False
    # Spec §4.2: a posted flag-group debit; cleared for proven duplicates and
    # settlement-reversed debits. Never read by lender, withholding or revenue math.
    contributes_to_flagged_totals: bool = False
    contributes_to_verified_revenue: bool = False
```

- [ ] **Step 7: Set the fields in `_build_record`.** Replace

```python
    contributes_insurance = classification == "insurance" and is_debit and is_posted
```
with
```python
    contributes_insurance = classification == "insurance" and is_debit and is_posted
    flag_group = FLAG_GROUP_BY_STATE.get(classification)
    contributes_flagged = flag_group is not None and is_debit and is_posted
```
then, in the `TransactionClassification(...)` call of `_build_record`, replace
```python
        review_required=review_required,
        revenue_classification=revenue_state,
```
with
```python
        review_required=review_required,
        flagged_group=flag_group.key if flag_group is not None else None,
        revenue_classification=revenue_state,
```
and replace
```python
        contributes_to_insurance_totals=contributes_insurance,
        **revenue_flags,
```
with
```python
        contributes_to_insurance_totals=contributes_insurance,
        contributes_to_flagged_totals=contributes_flagged,
        **revenue_flags,
```

- [ ] **Step 8: Clear the flag in both statement passes.** In `_apply_reversal_pair_context`, replace

```python
                contributes_to_insurance_totals=False,
            )
    return updated
```
with
```python
                contributes_to_insurance_totals=False,
                contributes_to_flagged_totals=False,
            )
    return updated
```
In the duplicate finalisation loop of `classify_statement_transactions`, replace
```python
            contributes_to_insurance_totals=False,
            contributes_to_lender_credit_exclusion=False,
```
with
```python
            contributes_to_insurance_totals=False,
            contributes_to_flagged_totals=False,
            contributes_to_lender_credit_exclusion=False,
```

- [ ] **Step 9: Bump the analysis stage.** In `webapp/artifact_cache.py`, replace the line `ANALYSIS_STAGE_VERSION = 18` with:

```python
# 18 -> 19: LENDER-DETECTION (2026-09-24 design, service S2) — classification
# version 5.0: ten flag-group states, the premium-financing flag on insurance
# rows, and the `flagged_group` / `contributes_to_flagged_totals` record
# fields; the reordered payee rules (known-payee matcher, card-paid lenders,
# LOC wording); financing-proceeds credits; obligation descriptors;
# unknown-payee naming and the fixed-debit
# review tier; `metrics.flagged_groups` and `detection.flagged_positions` join
# the payload. The classifier's registry is not key material, so a warm cache
# keyed on 18 would serve the old lender groups. OCR stays cached. Pinned in the
# same commit (`tests/test_artifact_cache.py`).
ANALYSIS_STAGE_VERSION = 19
```

- [ ] **Step 10: Move the cache pin.** In `tests/test_artifact_cache.py`, replace the whole function `test_analysis_stage_version_is_pinned_at_18` (`:487-493`) with:

```python
def test_analysis_stage_version_is_pinned_at_19():
    """LENDER-DETECTION (2026-09-24 design, S2): classification version 5.0 moves
    lender groups and adds the flagged-position payload, and the classifier's
    registry is not key material, so ANALYSIS_STAGE_VERSION goes 18 -> 19 in the
    same commit as the classifier change. This is that pin."""
    assert ANALYSIS_STAGE_VERSION == 19
```

- [ ] **Step 11: Run the new tests and the neighbours.**

Run: `C:\Python314\python.exe -m pytest tests/test_flag_group_states.py tests/test_artifact_cache.py tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py -q -p no:cacheprovider`
Expected: PASS, apart from any baseline failure recorded in Task 0 Step 2 (the pin-ledger rows settled by later tasks).

- [ ] **Step 12: Commit.**

```
git add analysis/transaction_classifier.py webapp/artifact_cache.py tests/test_artifact_cache.py tests/flag_group_fixtures.py tests/test_flag_group_states.py
git commit -m "classifier: flag-group states and record fields; classification 5.0, analysis stage 19" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 3: The classifier compiles its lookups once (§4.6)

**Files:**
- Modify: `analysis/transaction_classifier.py`:
  - `_contains_alias` through the end of S1's delegating `_registry_match` (S1 tree `:173-189`);
  - every `_registry_match(` call (S1 tree: `match_verified_lender_alias`, `match_insurance_provider`, `_classify_credit_revenue`, `classify_transaction`, `_apply_operating_source_context`);
  - the `is_ach` line of `_build_record` (S1 tree `:858`).
- Test: `tests/test_classifier_lookups.py`

**Interfaces:**
- Consumes: C3 `registry_match(normalized_text, registry) -> tuple[str, str] | None` (S1 already imports it into the classifier).
- Produces: `_ACH_TOKEN`, a compiled pattern. `_contains_alias` and `_registry_match` are removed; every lookup calls `registry_match`. No classification changes in this task. The test helper `synthetic_statement(rows_per_kind: int = 100) -> Statement` (Task 17 reuses it).

- [ ] **Step 1: Write the failing test** `tests/test_classifier_lookups.py`:

```python
from __future__ import annotations

from analysis import transaction_classifier
from analysis.schema import Statement
from tests.flag_group_fixtures import txn


def synthetic_statement(rows_per_kind: int = 100) -> Statement:
    """300 fabricated rows: customer credits, vendor ACH debits and card purchases."""
    transactions = []
    for index in range(rows_per_kind):
        day = f"2054-01-{index % 28 + 1:02d}"
        transactions.append(txn(day, f"ACH CREDIT FABRICATED CUSTOMER {index:04d}", float(100 + index)))
        transactions.append(txn(day, f"ACH DEBIT FABRICATED VENDOR {index:04d}", -float(50 + index)))
        transactions.append(txn(day, f"POS PURCHASE FABRICATED STORE {index:04d}", -float(10 + index)))
    return Statement(transactions=transactions)


def test_each_row_is_normalized_exactly_once(monkeypatch):
    """Spec §4.6 speed: aliases are compiled once, so classifying a row never
    re-normalizes an alias. No row here matches an operating-revenue alias, so no
    account name is normalized either."""
    calls: list[str] = []
    original = transaction_classifier.normalize_transaction_description

    def counting(value: str) -> str:
        calls.append(value)
        return original(value)

    monkeypatch.setattr(transaction_classifier, "normalize_transaction_description", counting)
    records = transaction_classifier.classify_statement_transactions(synthetic_statement())
    assert len(records) == 300
    assert len(calls) == len(records)


def test_the_ach_flag_needs_the_ach_token_on_its_own():
    assert transaction_classifier.classify_transaction("ACH DEBIT FABRICATED VENDOR", -50.0).is_ach
    assert not transaction_classifier.classify_transaction("CACHE FABRICATED VENDOR", -50.0).is_ach
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_classifier_lookups.py -q -p no:cacheprovider`
Expected: `test_each_row_is_normalized_exactly_once` FAILS with `assert 600 == 300`: S1's `_registry_match` already delegates, but `_contains_alias(text, "ACH")` still normalizes the alias `ACH` on every row. The ACH-token test passes (it guards the rewrite).

- [ ] **Step 3: Replace the slow helpers.** Replace everything from `def _contains_alias(text: str, alias: str) -> bool:` through the end of S1's `_registry_match` (its line `    return registry_match(text, registry)`) with:

```python
#: The ACH token, compiled once (it used to be re-normalized on every row).
_ACH_TOKEN = re.compile(r"(?<![A-Z0-9])ACH(?![A-Z0-9])")
```

- [ ] **Step 4: Call the compiled lookup everywhere.** In `analysis/transaction_classifier.py`, replace every `_registry_match(` with `registry_match(` (same arguments: the normalized text and the registry). Then:

Run: `git grep -n "_registry_match\|_contains_alias" -- analysis/transaction_classifier.py`
Expected: no output.

- [ ] **Step 5: Compile the ACH flag once.** In `_build_record`, replace `        is_ach=_contains_alias(text, "ACH"),` with `        is_ach=_ACH_TOKEN.search(text) is not None,`.

- [ ] **Step 6: Run the tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_classifier_lookups.py tests/test_flag_group_states.py tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_payee_matcher.py tests/test_classifier_speed.py -q -p no:cacheprovider`
Expected: PASS, apart from any baseline failure recorded in Task 0 Step 2. No classification moved: S1's parity test (`tests/test_classifier_speed.py`) swaps the module's `registry_match` for the legacy matcher and compares every record. If `tests/test_payee_matcher.py` or `tests/test_classifier_speed.py` does not exist on your tree, drop it from the command.

- [ ] **Step 7: Commit.**

```
git add analysis/transaction_classifier.py tests/test_classifier_lookups.py
git commit -m "classifier: every lookup uses the compiled registry index" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 4: Credits from a financing group are proceeds (D1, §4.4)

**Files:**
- Modify: `analysis/transaction_classifier.py`:
  - the `from .classification_registry import (` block (one line added);
  - the `from .flag_groups import` line (Task 2) and S1's `from .payee_matcher import registry_match` line;
  - `_classify_credit_revenue` (whole function, S1 tree `:564-739`), and its call in `_build_record`;
  - new helpers directly before `def classify_transaction(`;
  - one credit branch in `classify_transaction`, before its lease-registry block.
- Modify: `tests/flag_group_fixtures.py` (replace the file)
- Modify: `tests/test_revenue_classification.py:168` (check only)
- Test: `tests/test_financing_proceeds_credits.py`

**Interfaces:**
- Consumes: C1 `FINANCING_STATES`; C2 `POTENTIAL_LENDER_ALIASES`, `INSURANCE_PROVIDER_ALIASES`, `OPERATING_REVENUE_SOURCE_ALIASES`, `OPERATING_REVENUE_SOURCE_TYPES`; S1's `PAYOUT_CREDIT_ENTITIES` (fact 10); C3 `match_known_payee(normalized_text) -> PayeeMatch | None`, `registry_match`, `PayeeMatch(entity, state, alias)`.
- Produces (C4): a credit from a `FINANCING_STATES` payee is `classification="other"`, `canonical_entity=<entity>`, `match_method="financing_proceeds_credit"`, `matched_rule="financing_proceeds_credit"`, `contributes_to_lender_credit_exclusion=True`, revenue `non_revenue` with `revenue_match_method="financing_proceeds_credit"`. Card-issuer and lease/rental payees never apply to credits.
- Produces the owner decisions of 2026-09-25 on credits:
  - **Payout credits (a D1 exception).** A credit whose known payee is an entity of `PAYOUT_CREDIT_ENTITIES` (Sezzle Inc, American First Finance, LLC, PAYABILITY) is the account holder's own sales, settled by the platform. D1 does not apply: the credit takes the operating-revenue path, with no `financing_proceeds_credit` and no `contributes_to_lender_credit_exclusion`. Debits keep their group (Task 5).
  - **D1 by descriptor.** Three credits whose own words say they are financing proceeds get the same record and revenue decision as a financing payee's credit, with `matched_rule` (and `revenue_matched_rule`) naming the rule:
    - `bank_line_advance_credit`: a credit whose whole descriptor is `LOAN CREDIT` (an advance from the statement bank's own operating line), decided with the financing-group check, ahead of the strong non-revenue rule that claims it today; entity the statement bank.
    - `loc_draw_credit`: a line-of-credit draw (`LOC` or `LINE OF CREDIT` with `ADVANCE`, `ADV` or `DRAW`, `ADVANCE FROM LOC`, `DRAW ON/FROM LOC`); entity the statement bank.
    - `floor_plan_advance_credit`: a per-vehicle floor-plan advance (`ADVANCE`, a four-digit model year, `VIN`); no entity.
    - The last two apply only when no potential alias and no strong non-revenue rule (an own-account transfer, for example) claims the credit. None of the three carries a flag.
- Also produces `_state_words(state: str) -> str`, `_financing_proceeds_payee(text: str) -> PayeeMatch | None`, `_descriptor_proceeds(text: str) -> tuple[str, bool] | None`, `_financing_proceeds_credit_record(common, amount, match) -> TransactionClassification`, `_descriptor_proceeds_credit_record(common, amount, proceeds, bank) -> TransactionClassification`, the keyword `_classify_credit_revenue(..., bank: str | None = None)`, and the test fixtures `FAKE_PAYEES`, `fake_match`, `fake_payees`.

- [ ] **Step 1: Replace** `tests/flag_group_fixtures.py` with:

```python
"""Fabricated rows and payees for the lender-detection classifier tests (spec §9).

Every descriptor, name and amount here is fabricated: no statement text, no
real amount, no customer name. Amounts are whole dollars.
"""
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.payee_matcher import PayeeMatch
from analysis.schema import Transaction


def txn(day: str, description: str, amount: float, *, balance: float | None = None) -> Transaction:
    return Transaction(
        date=day,
        description=description,
        amount=amount,
        direction="credit" if amount >= 0 else "debit",
        running_balance=balance,
    )


#: alias -> (canonical entity, classification state); at least one payee per group.
FAKE_PAYEES: dict[str, tuple[str, str]] = {
    "FABRICATED LENDER": ("Fabricated Lender", "confirmed_lender"),
    "FABRICATED ALT": ("Fabricated Alt Capital", "alternative_position"),
    "FABRICATED BNPL": ("Fabricated BNPL", "alternative_position"),
    "FABRICATED LINE": ("Fabricated Line", "line_of_credit"),
    "FABRICATED CARMAKER FINANCIAL": ("Fabricated Carmaker Financial", "vehicle_financing"),
    "FABRICATED MORTGAGE CO": ("Fabricated Mortgage Co", "mortgage"),
    "FABRICATED PERSONAL": ("Fabricated Personal Loans", "personal_loan"),
    "FABRICATED FLOORPLAN": ("Fabricated Floorplan Finance", "floor_plan_financing"),
    "FABRICATED FACTOR": ("Fabricated Factor", "factoring"),
    "FABRICATED RENTALS": ("Fabricated Rentals", "lease_or_rental"),
    "FABRICATED ISSUER": ("Fabricated Issuer", "credit_card_payment"),
}


def fake_match(normalized_text: str) -> PayeeMatch | None:
    """A stand-in for S1's matcher over FAKE_PAYEES: the longest alias found wins."""
    for alias in sorted(FAKE_PAYEES, key=len, reverse=True):
        if alias in normalized_text:
            entity, state = FAKE_PAYEES[alias]
            return PayeeMatch(entity=entity, state=state, alias=alias)
    return None


@pytest.fixture
def fake_payees(monkeypatch):
    """Route the classifier's known-payee lookups to FAKE_PAYEES for one test."""
    monkeypatch.setattr(transaction_classifier, "match_known_payee", fake_match)
    return FAKE_PAYEES
```

- [ ] **Step 2: Write the failing test** `tests/test_financing_proceeds_credits.py`:

```python
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.flag_groups import FINANCING_STATES
from analysis.metrics import compute_metrics
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import FAKE_PAYEES, fake_payees, txn  # noqa: F401  (fixture)

PAYEE_ROWS = [(alias, *FAKE_PAYEES[alias]) for alias in FAKE_PAYEES]


@pytest.mark.parametrize(("alias", "entity", "state"), PAYEE_ROWS)
def test_a_known_payee_credit_is_proceeds_only_for_a_financing_group(fake_payees, alias, entity, state):
    record = classify_transaction(f"{alias} DEPOSIT 0001", 5000.0)
    assert record.flagged_group is None
    assert not record.contributes_to_flagged_totals
    if state in FINANCING_STATES:
        assert record.classification == "other"
        assert record.canonical_entity == entity
        assert record.match_method == "financing_proceeds_credit"
        assert record.matched_rule == "financing_proceeds_credit"
        assert record.contributes_to_lender_credit_exclusion
        assert record.revenue_classification == "non_revenue"
        assert record.revenue_match_method == "financing_proceeds_credit"
        assert record.revenue_canonical_entity == entity
    else:
        assert record.matched_rule != "financing_proceeds_credit"
        assert not record.contributes_to_lender_credit_exclusion
        assert record.revenue_classification == "unverified_deposit"


@pytest.mark.parametrize("description", ["NEXTGEAR CAPITAL PAYMENT", "RTS FINANCIAL PAYMENT"])
def test_owner_named_floor_plan_and_factoring_credits_are_financing_proceeds(description):
    """Spec §2 amendment and §4.2: D1 covers floor-plan and factoring credits."""
    record = classify_transaction(description, 100.0)
    assert record.matched_rule == "financing_proceeds_credit"
    assert record.contributes_to_lender_credit_exclusion
    assert record.revenue_classification == "non_revenue"


def test_platform_financing_credits_are_proceeds_but_platform_sales_stay_revenue():
    statement = Statement(
        bank="Fabricated Bank",
        account_name="Business Checking",
        transactions=[
            txn("2054-01-02", "SQUARE CAPITAL", 5000.0),
            txn("2054-01-09", "SQUARE CAPITAL", 5000.0),
            txn("2054-01-16", "SQUARE CAPITAL", 5000.0),
            txn("2054-01-17", "SQUARE SETTLEMENT", 800.0),
            txn("2054-01-18", "SHOPIFY CAPITAL PAYOUT", 900.0),
        ],
    )
    records = classify_statement_transactions(statement)
    assert [record.revenue_classification for record in records] == [
        "non_revenue", "non_revenue", "non_revenue", "verified_revenue", "non_revenue",
    ]
    assert {records[index].revenue_match_method for index in (0, 1, 2, 4)} == {"financing_proceeds_credit"}
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.lender_credits == 15900.0
    assert metrics.verified_revenue_total == 800.0
    assert metrics.legacy_eligible_deposits == 800.0


@pytest.fixture
def fabricated_payout_entity(monkeypatch):
    """Owner decision 2026-09-25: the credits of a PAYOUT_CREDIT_ENTITIES payee are the
    account holder's own sales, settled by the platform."""
    monkeypatch.setattr(transaction_classifier, "PAYOUT_CREDIT_ENTITIES", ("Fabricated BNPL",))


def test_a_payout_credit_entitys_credit_is_revenue_not_proceeds(fake_payees, fabricated_payout_entity):
    payout = classify_transaction("FABRICATED BNPL MERCHANT PAYOUT 0001", 900.0)
    assert payout.matched_rule != "financing_proceeds_credit"
    assert not payout.contributes_to_lender_credit_exclusion
    assert payout.revenue_classification == "verified_revenue"
    assert payout.revenue_match_method != "financing_proceeds_credit"
    # Another alternative position's credit is still proceeds.
    assert classify_transaction("FABRICATED ALT DEPOSIT 0001", 900.0).matched_rule == "financing_proceeds_credit"


@pytest.mark.parametrize(
    ("description", "rule", "entity"),
    [
        ("LOAN CREDIT", "bank_line_advance_credit", "Fabricated Bank"),
        ("LOC ADVANCE 0001", "loc_draw_credit", "Fabricated Bank"),
        ("ADVANCE FROM LINE OF CREDIT 0001", "loc_draw_credit", "Fabricated Bank"),
        ("ADVANCE 2054 FABRICATED MODEL VIN 0001", "floor_plan_advance_credit", None),
    ],
)
def test_a_credit_whose_words_say_financing_proceeds_is_proceeds(description, rule, entity):
    """Owner decisions 2026-09-25: the bank's own line advance, a line-of-credit draw and a
    per-vehicle floor-plan advance are financing proceeds (D1), with no flag."""
    record = classify_transaction(description, 900.0, bank="Fabricated Bank")
    assert record.classification == "other"
    assert (record.match_method, record.matched_rule, record.canonical_entity) == (
        "financing_proceeds_credit",
        rule,
        entity,
    )
    assert record.contributes_to_lender_credit_exclusion
    assert record.flagged_group is None
    assert record.revenue_classification == "non_revenue"
    assert (record.revenue_match_method, record.revenue_matched_rule) == ("financing_proceeds_credit", rule)
    assert record.revenue_canonical_entity == entity


def test_only_the_exact_bank_line_posting_is_proceeds_by_its_words():
    record = classify_transaction("LOAN CREDIT MEMO 0001", 900.0, bank="Fabricated Bank")
    assert record.revenue_match_method == "strong_non_revenue_rule"
    assert not record.contributes_to_lender_credit_exclusion
```

- [ ] **Step 3: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_financing_proceeds_credits.py -q -p no:cacheprovider`
Expected: FAIL.
- Every `fake_payees` test errors at setup with `AttributeError: <module 'analysis.transaction_classifier' ...> has no attribute 'match_known_payee'`.
- The NextGear and RTS credits fail on `matched_rule` (no rule claims them yet), and so do the four descriptor credits.
- The platform test fails on `revenue_match_method`: today's lender-registry credit exclusion names its own method.
- `test_only_the_exact_bank_line_posting_is_proceeds_by_its_words` passes: it guards the rule's exact posting.

- [ ] **Step 4: Import what the credit rule reads.** In `analysis/transaction_classifier.py`:
  - in the `from .classification_registry import (` block, replace
    ```python
        OPERATING_REVENUE_SOURCE_TYPES,
    )
    ```
    with
    ```python
        OPERATING_REVENUE_SOURCE_TYPES,
        PAYOUT_CREDIT_ENTITIES,
        POTENTIAL_LENDER_ALIASES,
    )
    ```
  - replace the line `from .flag_groups import FLAG_GROUP_BY_STATE` (Task 2) with `from .flag_groups import FINANCING_STATES, FLAG_GROUP_BY_STATE`;
  - replace S1's line `from .payee_matcher import registry_match` with `from .payee_matcher import PayeeMatch, match_known_payee, registry_match`.

- [ ] **Step 5: Replace `_classify_credit_revenue`** (the whole function, from `def _classify_credit_revenue(` through its final `return _RevenueDecision(...)`) with:

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
    if _matches_any(text, _REVERSAL_CANCELLATION_CREDIT_PATTERNS):
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

    insurance_match = registry_match(text, INSURANCE_PROVIDER_ALIASES)
    if insurance_match is not None:
        entity, alias = insurance_match
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
    # Spec §4.4 / D1: a credit from a financing group is proceeds. It is decided
    # before the operating-revenue registry, and group aliases are
    # financing-specific (SQUARE CAPITAL, never bare SQUARE), so a platform's
    # sales settlement still reaches the operating registry below. Card-issuer
    # and lease/rental payees never apply to credits, and neither does a
    # payout-credit entity (owner decision 2026-09-25).
    financing_match = _financing_proceeds_payee(text)
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
    # D1 by descriptor (owner decisions 2026-09-25). `_descriptor_proceeds` keeps
    # the potential registry and the strong non-revenue rule below ahead of a
    # line-of-credit draw or a floor-plan advance.
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
    potential_lender_match = registry_match(text, POTENTIAL_LENDER_ALIASES)
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
    if _matches_any(text, _NON_REVENUE_CREDIT_PATTERNS):
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

    revenue_match = registry_match(text, OPERATING_REVENUE_SOURCE_ALIASES)
    if revenue_match is not None:
        entity, alias = revenue_match
        source_type = OPERATING_REVENUE_SOURCE_TYPES.get(entity)
        has_operating_context = _matches_any(text, _OPERATING_CREDIT_CONTEXT_PATTERNS)
        business_account = _matches_any(
            normalize_transaction_description(account_name or ""),
            _BUSINESS_ACCOUNT_PATTERNS,
        )
        signals = ["credit_direction", "maintained_operating_source"]
        if has_operating_context:
            signals.append("settlement_or_payout_descriptor")
        if business_account:
            signals.append("business_account")
        if has_operating_context:
            return _RevenueDecision(
                "verified_revenue",
                entity,
                "operating_source_with_credit_context",
                alias,
                "verified_operating_source_credit",
                0.98 if business_account else 0.96,
                (
                    f"Credit matched maintained {source_type or 'operating-source'} alias "
                    f"'{alias}' with settlement, payout, or deposit context."
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
    if _matches_any(text, _VERIFIED_REVENUE_CREDIT_PATTERNS):
        return _RevenueDecision(
            "verified_revenue",
            None,
            "operating_income_descriptor",
            None,
            "verified_operating_income_descriptor",
            0.93,
            "Credit has a customer-payment, merchant-settlement, card-sales, invoice, or verified business-deposit descriptor.",
            context_signals=("credit_direction", "operating_income_descriptor"),
        )
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

- [ ] **Step 6: Pass the statement bank to the revenue rule.** In `_build_record`, in its call `revenue = _classify_credit_revenue(...)`, replace

```python
        posted=is_posted,
        account_name=account_name,
```
with
```python
        posted=is_posted,
        bank=bank,
        account_name=account_name,
```

- [ ] **Step 7: Add the proceeds helpers.** Directly before `def classify_transaction(`, insert:

```python
def _state_words(state: str) -> str:
    return state.replace("_", " ")


def _financing_proceeds_payee(text: str) -> PayeeMatch | None:
    """D1: the known payee whose credit is financing proceeds, or None.

    Owner decision 2026-09-25: the credits of a payout-credit entity
    (PAYOUT_CREDIT_ENTITIES) are the account holder's own sales settled by the
    platform, so they are revenue; that entity's debits keep their group.
    """
    match = match_known_payee(text)
    if match is None or match.state not in FINANCING_STATES or match.entity in PAYOUT_CREDIT_ENTITIES:
        return None
    return match


#: D1 by descriptor (owner decisions 2026-09-25): credits whose own words say they
#: are financing proceeds, with no registry payee named. Credits only.
_BANK_LINE_ADVANCE_CREDIT = re.compile(r"^LOAN CREDIT$")
_LOC_DRAW_CREDIT_PATTERNS = (
    re.compile(r"\b(?:LOC|LINE OF CREDIT) (?:ADVANCE|ADV|DRAW)\b"),
    re.compile(r"\bADVANCE FROM (?:LOC|LINE OF CREDIT)\b"),
    re.compile(r"\bDRAW (?:ON|FROM) (?:LOC|LINE OF CREDIT)\b"),
)
_FLOOR_PLAN_ADVANCE_CREDIT = re.compile(r"^ADVANCE (?:19|20)\d\d .*\bVIN\b")


def _descriptor_proceeds(text: str) -> tuple[str, bool] | None:
    """D1 by descriptor: (rule, whether the statement bank is the lender), or None.

    Read after the known-payee check. The bank's own line advance (exactly
    LOAN CREDIT) is decided there, ahead of the strong non-revenue rule that
    would otherwise claim it. A line-of-credit draw or a per-vehicle floor-plan
    advance counts only when no potential alias and no strong non-revenue rule
    (an own-account transfer, for example) claims the credit.
    """
    if _BANK_LINE_ADVANCE_CREDIT.search(text):
        return "bank_line_advance_credit", True
    if registry_match(text, POTENTIAL_LENDER_ALIASES) is not None or _matches_any(
        text, _NON_REVENUE_CREDIT_PATTERNS
    ):
        return None
    if _matches_any(text, _LOC_DRAW_CREDIT_PATTERNS):
        return "loc_draw_credit", True
    if _FLOOR_PLAN_ADVANCE_CREDIT.search(text):
        return "floor_plan_advance_credit", False
    return None


def _financing_proceeds_credit_record(
    common: dict[str, object],
    amount: float,
    match: PayeeMatch,
) -> TransactionClassification:
    """D1: a credit from a financing group is proceeds, excluded from eligible deposits."""
    return _build_record(
        **common,
        classification="other",
        canonical_entity=match.entity,
        match_method="financing_proceeds_credit",
        matched_alias=match.alias,
        matched_rule="financing_proceeds_credit",
        confidence_score=0.97,
        reason=(
            f"Matched maintained {_state_words(match.state)} alias '{match.alias}' on a credit; "
            "financing proceeds are excluded from lender debits and eligible deposits."
        ),
        contributes_to_lender_credit_exclusion=amount > 0,
    )


def _descriptor_proceeds_credit_record(
    common: dict[str, object],
    amount: float,
    proceeds: tuple[str, bool],
    bank: str | None,
) -> TransactionClassification:
    """D1 by descriptor: the credit's own words say it is financing proceeds."""
    rule, names_bank = proceeds
    return _build_record(
        **common,
        classification="other",
        canonical_entity=(bank or None) if names_bank else None,
        match_method="financing_proceeds_credit",
        matched_rule=rule,
        confidence_score=0.95,
        reason=(
            f"The credit's descriptor identifies financing proceeds ({_state_words(rule)}); they are "
            "excluded from lender debits and eligible deposits."
        ),
        contributes_to_lender_credit_exclusion=amount > 0,
    )


```

- [ ] **Step 8: Decide credits at step 7 of the rule order.** In `classify_transaction`, directly before the two lines

```python
    lease_match = registry_match(text, LEASE_PROVIDER_ALIASES)
    if lease_match is not None or _matches_any(text, _LEASE_PATTERNS):
```
insert
```python
    # Spec §4.3 step 7 / D1: a credit from a financing-group payee is proceeds,
    # and so is a credit whose own words say so (owner decisions 2026-09-25).
    # (Task 5 moves debits to the same step.)
    if amount > 0:
        financing_payee = _financing_proceeds_payee(text)
        if financing_payee is not None:
            return _financing_proceeds_credit_record(common, amount, financing_payee)
        descriptor_proceeds = _descriptor_proceeds(text)
        if descriptor_proceeds is not None:
            return _descriptor_proceeds_credit_record(common, amount, descriptor_proceeds, bank)

```

- [ ] **Step 9: Check the NETCREDIT row** (pin-ledger row 13). In `tests/test_revenue_classification.py`, the parametrized row at `:168` must read `("NETCREDIT CCBANK-NTC loan proceeds", "NETCREDIT"),`. It needs no edit on S1's tree (Task 0 checked that NETCREDIT is a financing payee named `NETCREDIT`); if S1 changed it, restore that line.

- [ ] **Step 10: Run the tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_financing_proceeds_credits.py tests/test_classifier_lookups.py tests/test_flag_group_states.py tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_new_statement_corpus.py -q -p no:cacheprovider`
Expected: PASS, apart from any baseline failure recorded in Task 0 Step 2. Debits are untouched (Task 5), so no lender pin moves here, and Task 0 found no descriptor-proceeds or payout credit on a pinned statement. The payout credits of the real registry's Sezzle and PAYABILITY are pinned in Task 5: until then S1's legacy lender list still reads PAYABILITY's credits as lender credits.

- [ ] **Step 11: Commit.**

```
git add analysis/transaction_classifier.py tests/flag_group_fixtures.py tests/test_financing_proceeds_credits.py
git commit -m "classifier: credits from a financing group are proceeds (D1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```
If Step 9 restored the NETCREDIT line, also `git add tests/test_revenue_classification.py` before committing.

---

### Task 5: The known payee decides debit groups (step 7, D8, D9)

**Files:**
- Modify: `analysis/transaction_classifier.py`:
  - the `from .classification_registry import (` block (whole);
  - `match_verified_lender_alias` (S1 tree `:191-192`);
  - new D9 constants, `_known_payee_debit_record` and `_is_membership_or_top_up` after `_state_words` (Task 4);
  - `_FEE_PATTERNS` (S1 tree `:268-274`, one pattern added);
  - `classify_transaction` (whole function).
- Modify: `tests/test_lender_insurance_classification.py:40-86, :102-117, :130-145, :196, :230-380, :405-422, :474-563`
- Modify: `tests/test_r1_hardcodes.py:530-545`
- Modify: `tests/test_analysis.py:13, :3348-3364, :3572-3579, :3582-3588`
- Modify: `tests/test_transaction_classifier.py:3` (one import) and `:306-386` (the ATB November test)
- Modify: `tests/test_revenue_classification.py:402-405`
- Modify: `tests/test_new_statement_corpus.py:122, :181` and append one test
- Test: `tests/test_known_payee_classification.py`

**Interfaces:**
- Consumes: C1 `FINANCING_STATES`, `FLAG_GROUP_BY_STATE`; C2 `PAYEE_GROUP_REGISTRIES`, `INSURANCE_PROVIDER_ALIASES`, `POTENTIAL_LENDER_ALIASES`, `OPERATING_REVENUE_SOURCE_ALIASES`, `OPERATING_REVENUE_SOURCE_TYPES`, `BANK_SPECIFIC_LENDER_ALIASES`; S1's `PAYOUT_CREDIT_ENTITIES`; C3 `match_known_payee`, `registry_match`, `PayeeMatch`; Task 4 `_state_words`, `_financing_proceeds_credit_record`, `_descriptor_proceeds`, `_descriptor_proceeds_credit_record`; the fixtures `FAKE_PAYEES`, `fake_payees`.
- Produces (C4): a debit to a known payee takes `PayeeMatch.state` (lenders keep `match_method="verified_lender_alias"`, `matched_rule="confirmed_lender_registry"`; other groups `match_method="known_payee_alias"`, `matched_rule=f"{state}_registry"`); D9 gives `line_of_credit` with `matched_rule="line_of_credit_descriptor_override"`; POS and ATM skip a known payee (D8). Also produces `_LINE_OF_CREDIT_PATTERNS` (Task 8 reuses it) and `_known_payee_debit_record(common, text, match) -> TransactionClassification`. `analysis/lenders.py` needs no edit: it reads `CONFIRMED_LENDER_ALIASES`, which C2 keeps as the name of `LENDER_ALIASES`, and its helpers call `classify_transaction`.
- Produces the owner decisions of 2026-09-25 at steps 5-7:
  - **An overdraft charge is a fee** (step 6): `_FEE_PATTERNS` reads `OVERDRAFT CHARGE(S)`, so the bank's charge for an item is a fee even when it prints the item's payee (S1's alias audit denied the two such Zip rows). A refund of the charge stays `refund_or_reversal` (step 3).
  - **A membership or balance top-up is not a repayment** (steps 5 and 7): `_is_membership_or_top_up(text, match) -> bool`. A debit whose known payee is an `alternative_position` payee, and which prints `PLUS`, `PLU`, `MEM`, `MEMB`, `MEMBER` or `MEMBERSHIP`, or `BALANCE TOP UP`, right after the matched alias, matches no known payee. So D8 does not bypass POS for it, and it never takes the payee's group. The rule reads the matched alias, so no payee name is written in the classifier. On the cache it claims exactly the 42 Klarna Inc rows the decision names (31 Klarna Plus membership, 11 balance top-up) and no other payee's row. Limiting it to alternative positions keeps it off personal-loan memberships, which no decision covers.
  - **Payout credits** (step 7): a payout-credit entity's credit is not proceeds (Task 4's exception, now in the rule order too), and the descriptor-proceeds credits of Task 4 keep their place after the known-payee check.

- [ ] **Step 1: Write the failing test** `tests/test_known_payee_classification.py`:

```python
from __future__ import annotations

import pytest

from analysis.flag_groups import FLAG_GROUP_BY_STATE
from analysis.lenders import find_lender_match, has_false_lender_keyword
from analysis.transaction_classifier import classify_transaction
from tests.flag_group_fixtures import FAKE_PAYEES, fake_payees  # noqa: F401  (fixture)

PAYEE_ROWS = [(alias, *FAKE_PAYEES[alias]) for alias in FAKE_PAYEES]


def _group_key(state: str) -> str | None:
    group = FLAG_GROUP_BY_STATE.get(state)
    return group.key if group is not None else None


@pytest.mark.parametrize(("alias", "entity", "state"), PAYEE_ROWS)
def test_a_known_payee_debit_takes_its_group(fake_payees, alias, entity, state):
    record = classify_transaction(f"ACH DEBIT {alias} 0001", -500.0)
    assert record.classification == state
    assert record.canonical_entity == entity
    assert record.matched_alias == alias
    assert record.flagged_group == _group_key(state)
    assert record.contributes_to_flagged_totals is (_group_key(state) is not None)
    assert record.contributes_to_withholding_rate is (state == "confirmed_lender")
    assert not record.contributes_to_potential_lender_totals


def test_a_card_paid_known_payee_is_classified_by_who_was_paid(fake_payees):
    paid = classify_transaction("CARD PURCHASE FABRICATED ALT", -80.0)
    store = classify_transaction("CARD PURCHASE FABRICATED STORE", -80.0)
    assert paid.classification == "alternative_position"
    assert not paid.is_pos_purchase
    assert store.classification == "pos"


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("FABRICATED LENDER TRANSFER FEE", "fee"),
        # Owner decision 2026-09-25: the bank's overdraft charge for an item is a fee,
        # even when it prints the item's payee.
        ("OVERDRAFT CHARGE FABRICATED ALT 0001", "fee"),
        ("FABRICATED LINE ONLINE TRANSFER", "transfer"),
        ("FABRICATED LENDER PAYROLL", "payroll"),
        ("CHECK 1001 FABRICATED LENDER", "confirmed_lender"),
        ("FABRICATED LENDER SUBSCRIPTION", "confirmed_lender"),
        ("FABRICATED ALT RENT", "alternative_position"),
    ],
)
def test_fees_and_transfers_keep_precedence_but_checks_no_longer_hide_a_payee(fake_payees, description, state):
    assert classify_transaction(description, -500.0).classification == state


def test_an_overdraft_charge_is_a_fee_and_its_refund_a_reversal():
    assert classify_transaction("OVERDRAFT CHARGE 0001", -35.0).classification == "fee"
    assert classify_transaction("OVERDRAFT CHARGE REVERSAL 0001", 35.0).classification == "refund_or_reversal"


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("FABRICATED BNPL PLUS MEMBERSHIP", "other"),
        ("FABRICATED BNPL BALANCE TOP UP", "other"),
        ("CARD PURCHASE FABRICATED BNPL PLUS", "pos"),
        ("FABRICATED BNPL PAYMENT", "alternative_position"),
        ("FABRICATED PERSONAL PLUS", "personal_loan"),
    ],
)
def test_a_membership_or_balance_top_up_is_not_a_repayment(fake_payees, description, state):
    """Owner decision 2026-09-25 (Klarna Inc): an alternative-position payee's paid membership,
    or a top-up of the customer's own balance with it, matches no known payee, so D8 does not
    apply and it never takes the payee's group. Other groups are not affected."""
    record = classify_transaction(description, -20.0)
    assert record.classification == state
    assert record.flagged_group == _group_key(state)


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("ACH DEBIT FABRICATED LENDER LOC PMT", "line_of_credit"),
        ("ACH DEBIT FABRICATED ALT LINE OF CREDIT", "line_of_credit"),
        ("ACH DEBIT FABRICATED LINE LOC", "line_of_credit"),
        ("ACH DEBIT FABRICATED CARMAKER FINANCIAL LOC", "vehicle_financing"),
        ("ACH DEBIT FABRICATED FLOORPLAN LOC", "floor_plan_financing"),
        ("ACH DEBIT FABRICATED ISSUER LINE OF CREDIT", "credit_card_payment"),
    ],
)
def test_loc_wording_moves_lender_and_alternative_payees_to_lines_of_credit(fake_payees, description, state):
    record = classify_transaction(description, -500.0)
    assert record.classification == state
    assert not record.contributes_to_withholding_rate


@pytest.mark.parametrize(
    ("description", "state", "entity"),
    [
        # The NMEF, Navitas, Balboa, Econolease and Progressive Leasing descriptors move here unchanged
        # from the order table of tests/test_lender_insurance_classification.py; the others are fabricated.
        ("NMEF Funding 2025A payment", "confirmed_lender", "NMEF"),
        ("Navitas Credit Corp payment", "confirmed_lender", "Navitas Credit Corp"),
        ("Balboa Capital payment", "confirmed_lender", "Balboa Capital"),
        ("CHECKCARD 0102 NMEF FUNDING", "confirmed_lender", "NMEF"),
        ("CHECK 1234 FORA FINANCIAL", "confirmed_lender", "FORA FINANCIAL"),
        # Owner decisions 2026-09-25: Econolease is equipment finance, a lender; EBF Holdings
        # is Everest Business Funding, one funder counted once.
        ("VLFC-Econolease finance payment", "confirmed_lender", "Econolease"),
        ("EBF HOLDINGS DEBIT 0001", "confirmed_lender", "EVEREST BUSINESS FUNDING"),
        ("BDC loan payment", "alternative_position", "BDC"),
        ("ACH DEBIT INTUIT FINANCING 0001", "alternative_position", "INTUIT FINANCING"),
        ("CARD PURCHASE AFFIRMCOM 0001", "alternative_position", "AFFIRM"),
        # Owner ruling 2026-09-25: Capital Infusion (the house) is flagged, never counted.
        ("CAPITAL INFUSION PAYMENT", "alternative_position", "CAPITAL INFUSION"),
        ("BLUEVINE loan payment", "line_of_credit", "BLUEVINE"),
        ("BLUEVINE CAPITAL", "line_of_credit", "BLUEVINE"),
        ("FUNDBOX payment", "line_of_credit", "FUNDBOX"),
        ("KABBAGE payment", "line_of_credit", "KABBAGE"),
        ("Progressive Leasing recurring purchase", "lease_or_rental", "Progressive Leasing"),
        ("SMARTPAY LEASING payment", "lease_or_rental", "SmartPay"),
    ],
)
def test_owner_ruled_payees_take_their_groups(description, state, entity):
    record = classify_transaction(description, -100.0)
    assert (record.classification, record.canonical_entity) == (state, entity)
    assert record.contributes_to_withholding_rate is (state == "confirmed_lender")
    assert record.flagged_group == _group_key(state)


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("NEXTGEAR CAPITAL PAYMENT", "floor_plan_financing"),
        ("RTS FINANCIAL PAYMENT", "factoring"),
    ],
)
def test_owner_named_floor_plan_and_factoring_payees_take_their_groups(description, state):
    """Spec §2 amendment: floor plan and factoring are flagged like alternative positions."""
    record = classify_transaction(description, -100.0)
    assert record.classification == state
    assert record.flagged_group == _group_key(state)
    assert record.contributes_to_flagged_totals
    assert not record.contributes_to_withholding_rate


def test_smartpay_solutions_premium_billing_is_not_the_lease_to_own_smartpay():
    """Owner decision 2026-09-25: SMARTPAY SOL rows are SmartPay Solutions' premium billing,
    not the lease-to-own SmartPay Leasing, so they stay unflagged."""
    # Moves here unchanged from the order table of tests/test_lender_insurance_classification.py.
    record = classify_transaction("SmartPay Sol debitpmt", -100.0)
    assert (record.classification, record.canonical_entity, record.flagged_group) == ("other", None, None)


@pytest.mark.parametrize(
    ("debit", "credit", "state", "entity"),
    [
        ("SEZZLE PAYMENT 0001", "SEZZLE MERCHANT PAYOUT 0001", "alternative_position", "Sezzle Inc"),
        ("PAYABILITY PAYMENT 0001", "PAYABILITY MARKETPLACE PAYOUT 0001", "confirmed_lender", "PAYABILITY"),
    ],
)
def test_a_payout_credit_entity_keeps_its_group_on_debits_and_its_payouts_are_revenue(debit, credit, state, entity):
    """Owner decision 2026-09-25 (PAYOUT_CREDIT_ENTITIES): the platform settles the account
    holder's own sales, so its credits are revenue, not financing proceeds."""
    paid = classify_transaction(debit, -100.0)
    assert (paid.classification, paid.canonical_entity) == (state, entity)
    assert paid.contributes_to_withholding_rate is (state == "confirmed_lender")
    payout = classify_transaction(credit, 900.0)
    assert payout.matched_rule != "financing_proceeds_credit"
    assert not payout.contributes_to_lender_credit_exclusion
    assert payout.revenue_classification == "verified_revenue"
    assert payout.revenue_match_method != "financing_proceeds_credit"


@pytest.mark.parametrize(
    "description",
    # The ATB Mastercard and Capital One descriptors move here unchanged from the order table of
    # tests/test_lender_insurance_classification.py; the third is fabricated.
    ["ATB Mastercard payment", "ACH Capital One TYPE: ONLINE PMT", "CREDIT CARD PAYMENT FABRICATED"],
)
def test_card_payments_are_flagged_credit_cards_never_lenders(description):
    record = classify_transaction(description, -100.0)
    assert record.classification == "credit_card_payment"
    assert record.flagged_group == "credit_cards"
    assert record.contributes_to_flagged_totals
    assert not record.contributes_to_withholding_rate
    assert not record.contributes_to_potential_lender_totals


@pytest.mark.parametrize(("description", "state"), [("ONDECK TRANSFER FEE", "fee"), ("BLUEVINE ONLINE TRANSFER", "transfer")])
def test_fee_and_transfer_precedence_survives_the_real_matcher(description, state):
    assert classify_transaction(description, -100.0).classification == state


@pytest.mark.parametrize(
    "description",
    # A fabricated card purchase of Intuit software: a bare platform name with no financing wording.
    ["SQUARE", "SHOPIFY", "PAYPAL", "STRIPE", "CARD PURCHASE INTUIT QUICKBOOKS 0001"],
)
def test_bare_platform_names_are_never_a_flagged_payee(description):
    record = classify_transaction(description, -100.0)
    assert record.flagged_group is None
    assert record.classification not in ("confirmed_lender", "alternative_position")


def test_the_lenders_compatibility_helpers_follow_the_new_groups():
    """analysis/lenders.py reads the lender table through its C2 compatibility name."""
    assert find_lender_match("NMEF FUNDING payment")[0] == "NMEF"
    assert find_lender_match("BDC loan payment") is None
    assert has_false_lender_keyword("BDC loan payment")
    assert not has_false_lender_keyword("Canacap payment")
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_known_payee_classification.py -q -p no:cacheprovider`
Expected: FAIL.
- The `fake_payees` debit tests fail on the state: debits still go through S1's legacy lists, which know no fabricated payee. That includes the overdraft-charge row (`other`, not yet a fee) and the `FABRICATED BNPL PAYMENT` and `FABRICATED PERSONAL PLUS` membership cases; the other membership cases already pass.
- The owner-ruled NMEF/Balboa/Navitas/Econolease/EBF/BDC/Intuit/Affirm/Capital Infusion/BlueVine/Fundbox/Kabbage/SmartPay Leasing rows, the NextGear/RTS rows and the card-paid rows fail on the state or the entity.
- `SmartPay Sol debitpmt` fails as `lease_or_equipment_financing` (S1's legacy lease list still holds `SMARTPAY SOL`), and `OVERDRAFT CHARGE 0001` is `other`.
- The Sezzle debit fails on the state; the PAYABILITY credit fails on `contributes_to_lender_credit_exclusion` (S1's legacy lender list still reads it as a lender credit).
- `test_the_lenders_compatibility_helpers_follow_the_new_groups` fails with `TypeError: 'NoneType' object is not subscriptable` (NMEF is still a lease).

- [ ] **Step 3: Replace the classifier's registry import block.** Replace the whole `from .classification_registry import (...)` block (every line from `from .classification_registry import (` through its closing `)`) with:

```python
from .classification_registry import (
    BANK_SPECIFIC_LENDER_ALIASES,
    INSURANCE_PROVIDER_ALIASES,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    PAYEE_GROUP_REGISTRIES,
    PAYOUT_CREDIT_ENTITIES,
    POTENTIAL_LENDER_ALIASES,
)
```

- [ ] **Step 4: Point the lender helper at the lender group.** Replace the whole `match_verified_lender_alias` function with:

```python
def match_verified_lender_alias(description: str) -> tuple[str, str] | None:
    return registry_match(
        normalize_transaction_description(description),
        PAYEE_GROUP_REGISTRIES["confirmed_lender"],
    )
```

- [ ] **Step 5: Add the step-7 debit builder.** Directly after the `_state_words` function (Task 4), insert:

```python


#: D9: LOC wording. Also the first step-8 descriptor rule (Task 8).
_LINE_OF_CREDIT_PATTERNS = (
    re.compile(r"\bLOC\b"),
    re.compile(r"\bLINE OF CREDIT\b"),
)
#: D9: known-payee groups that LOC wording moves to lines of credit.
_LOC_OVERRIDE_STATES = frozenset({"confirmed_lender", "alternative_position", "line_of_credit"})


def _known_payee_debit_record(
    common: dict[str, object],
    text: str,
    match: PayeeMatch,
) -> TransactionClassification:
    """Spec §4.3 step 7 and D9: a debit to a known payee takes the payee's group."""
    if match.state in _LOC_OVERRIDE_STATES and _matches_any(text, _LINE_OF_CREDIT_PATTERNS):
        return _build_record(
            **common,
            classification="line_of_credit",
            canonical_entity=match.entity,
            match_method="known_payee_alias",
            matched_alias=match.alias,
            matched_rule="line_of_credit_descriptor_override",
            confidence_score=0.97,
            reason=(
                f"Matched maintained {_state_words(match.state)} alias '{match.alias}', and the "
                "descriptor says LOC or line of credit, so the row is a line of credit (D9)."
            ),
        )
    if match.state == "confirmed_lender":
        return _build_record(
            **common,
            classification="confirmed_lender",
            canonical_entity=match.entity,
            match_method="verified_lender_alias",
            matched_alias=match.alias,
            matched_rule="confirmed_lender_registry",
            confidence_score=0.99,
            reason=f"Matched maintained lender alias '{match.alias}' after all strong exclusions.",
        )
    return _build_record(
        **common,
        classification=match.state,
        canonical_entity=match.entity,
        match_method="known_payee_alias",
        matched_alias=match.alias,
        matched_rule=f"{match.state}_registry",
        confidence_score=0.97,
        reason=(
            f"Matched maintained {_state_words(match.state)} alias '{match.alias}'; "
            "it is a flagged obligation and never enters lender math."
        ),
    )


#: Owner decision 2026-09-25 (Klarna Inc): an alternative-position payee's paid
#: membership, or a top-up of the customer's own balance with it, printed right
#: after the payee's alias, is not a repayment. The words are read after the
#: matched alias, so no payee name is written here.
_MEMBERSHIP_OR_TOP_UP_AFTER_ALIAS = (
    r" (?:PLUS|PLU|MEM|MEMB|MEMBER|MEMBERSHIP)\b",
    r" BALANCE TOP ?(?:UP|U)\b",
)


def _is_membership_or_top_up(text: str, match: PayeeMatch) -> bool:
    """True when a debit to an alternative-position payee is its membership or a balance top-up."""
    if match.state != "alternative_position":
        return False
    alias = re.escape(match.alias)
    return any(re.search(rf"\b{alias}{tail}", text) for tail in _MEMBERSHIP_OR_TOP_UP_AFTER_ALIAS)
```

- [ ] **Step 6: Make an overdraft charge a fee.** In `_FEE_PATTERNS`, replace

```python
    re.compile(r"\bMONTHLY CHARGE\b"),
)
```
with
```python
    re.compile(r"\bMONTHLY CHARGE\b"),
    # Owner decision 2026-09-25: the bank's overdraft charge for an item is a fee,
    # even when it prints the item's payee (step 6 runs before the known payee).
    re.compile(r"\bOVERDRAFT CHARGES?\b"),
)
```

- [ ] **Step 7: Replace `classify_transaction`** (the whole function) with:

```python
def classify_transaction(
    description: str,
    amount: float,
    *,
    date: str = "",
    bank: str | None = None,
    account: str | None = None,
    account_name: str | None = None,
    direction: str | None = None,
    source_page: int | None = None,
    source_location: str | None = None,
    posted: bool = True,
) -> TransactionClassification:
    text = normalize_transaction_description(description)
    derived_direction = "credit" if amount >= 0 else "debit"
    source_direction = str(direction or derived_direction).strip().lower()
    direction_consistent = source_direction == derived_direction
    common: dict[str, object] = {
        "description": description,
        "text": text,
        "amount": amount,
        "date_value": date,
        "bank": bank,
        "account": account,
        "account_name": account_name,
        "source_direction": source_direction,
        "direction_consistent": direction_consistent,
        "source_page": source_page,
        "source_location": source_location,
    }

    if not posted or _matches_any(text, _NON_POSTED_PATTERNS):
        return _build_record(
            **common,
            classification="other",
            match_method="posting_status",
            matched_rule="non_posted_item",
            confidence_score=1.0,
            reason="The row is pending, memo-posted, or otherwise not a posted transaction.",
            is_posted=False,
        )

    if _matches_any(text, _NSF_PATTERNS):
        return _build_record(
            **common,
            classification="nsf_or_return",
            match_method="ordered_rule",
            matched_rule="nsf_or_return",
            confidence_score=0.99,
            reason="An NSF, insufficient-funds, or returned-item rule matched before lender detection.",
        )

    if _matches_any(text, _REFUND_REVERSAL_PATTERNS):
        return _build_record(
            **common,
            classification="refund_or_reversal",
            match_method="ordered_rule",
            matched_rule="refund_or_reversal",
            confidence_score=0.98,
            reason="A refund, reversal, void, cancellation, or returned-payment rule matched.",
        )

    insurance_match = registry_match(text, INSURANCE_PROVIDER_ALIASES)
    if insurance_match is not None:
        provider, alias = insurance_match
        return _build_record(
            **common,
            classification="insurance",
            canonical_entity=provider,
            match_method="insurance_provider_alias",
            matched_alias=alias,
            matched_rule="verified_insurance_provider",
            confidence_score=0.99,
            reason=f"Matched maintained insurance provider alias '{alias}'.",
        )

    if _matches_any(text, _INSURANCE_TERM_PATTERNS):
        return _build_record(
            **common,
            classification="insurance",
            canonical_entity="Insurance provider not identified",
            match_method="insurance_descriptor",
            matched_rule="insurance_term",
            confidence_score=0.95,
            reason="Matched an insurance-specific provider or policy/premium descriptor.",
        )

    # Spec §4.6: one lookup over every group registry. A known payee is excepted
    # from the POS and ATM rules (D8) and takes its group at step 7 below.
    known_payee = match_known_payee(text)
    # Owner decision 2026-09-25: a membership or balance top-up debit of an
    # alternative-position payee matches no known payee (steps 5 and 7).
    if known_payee is not None and amount < 0 and _is_membership_or_top_up(text, known_payee):
        known_payee = None

    if (
        amount < 0
        and known_payee is None
        and _matches_any(text, _POS_PATTERNS)
        and not _matches_any(text, _POS_EXCLUSION_PATTERNS)
        and (
            "TRANSFER" not in text
            or _matches_any(text, _EXPLICIT_CARD_PURCHASE_PATTERNS)
        )
        and not _matches_any(text, _LEASE_PATTERNS)
    ):
        return _build_record(
            **common,
            classification="pos",
            match_method="ordered_rule",
            matched_rule="point_of_sale_purchase",
            confidence_score=0.98,
            reason="The posted debit is explicitly identified as a point-of-sale purchase.",
        )

    if (
        amount < 0
        and known_payee is None
        and _matches_any(text, _ATM_PATTERNS)
        and not _matches_any(text, _FEE_PATTERNS)
    ):
        return _build_record(
            **common,
            classification="atm",
            match_method="ordered_rule",
            matched_rule="atm_withdrawal",
            confidence_score=0.98,
            reason="The posted debit is explicitly identified as an ATM cash withdrawal.",
        )

    if _matches_any(text, _FEE_PATTERNS):
        return _build_record(
            **common,
            classification="fee",
            match_method="strong_non_lender_exclusion",
            matched_rule="bank_or_processing_fee",
            confidence_score=0.97,
            reason="A bank, ACH, transfer, service, or merchant-processing fee rule matched.",
        )

    if _matches_any(text, _TRANSFER_PATTERNS):
        return _build_record(
            **common,
            classification="transfer",
            match_method="strong_non_lender_exclusion",
            matched_rule="transfer",
            confidence_score=0.96,
            reason="The descriptor identifies an account, online, or person-to-person transfer.",
        )

    if _matches_any(text, _TAX_PATTERNS):
        return _build_record(
            **common,
            classification="tax",
            match_method="strong_non_lender_exclusion",
            matched_rule="tax_payment",
            confidence_score=0.96,
            reason="The descriptor identifies a tax authority or tax payment.",
        )

    if _matches_any(text, _PAYROLL_PATTERNS):
        return _build_record(
            **common,
            classification="payroll",
            match_method="strong_non_lender_exclusion",
            matched_rule="payroll",
            confidence_score=0.96,
            reason="The descriptor identifies payroll, wages, or a payroll provider.",
        )

    if _matches_any(text, _UTILITY_PATTERNS):
        return _build_record(
            **common,
            classification="utility",
            match_method="strong_non_lender_exclusion",
            matched_rule="utility_payment",
            confidence_score=0.94,
            reason="The descriptor identifies a utility payment.",
        )

    # Step 7: the known payee's group (D9 inside). A credit is proceeds only
    # for a financing group (D1), and never for a payout-credit entity (owner
    # decision 2026-09-25: its credits are the holder's own sales); a card-issuer
    # or lease/rental payee on a credit falls through to the rules below.
    if known_payee is not None:
        if amount < 0:
            return _known_payee_debit_record(common, text, known_payee)
        if known_payee.state in FINANCING_STATES and known_payee.entity not in PAYOUT_CREDIT_ENTITIES:
            return _financing_proceeds_credit_record(common, amount, known_payee)
    # D1 by descriptor (owner decisions 2026-09-25): the bank's own line advance,
    # a line-of-credit draw or a per-vehicle floor-plan advance. Credits only.
    if amount > 0:
        descriptor_proceeds = _descriptor_proceeds(text)
        if descriptor_proceeds is not None:
            return _descriptor_proceeds_credit_record(common, amount, descriptor_proceeds, bank)

    if _matches_any(text, _LEASE_PATTERNS):
        return _build_record(
            **common,
            classification="lease_or_equipment_financing",
            match_method="strong_non_lender_exclusion",
            matched_rule="lease_or_equipment_financing",
            confidence_score=0.95,
            reason="The descriptor identifies a lease, vehicle lease, or equipment-financing obligation.",
        )

    if _matches_any(text, _RENT_PATTERNS):
        return _build_record(
            **common,
            classification="rent",
            match_method="strong_non_lender_exclusion",
            matched_rule="rent",
            confidence_score=0.95,
            reason="The descriptor identifies rent or a landlord payment.",
        )

    if _matches_any(text, _CREDIT_CARD_PATTERNS):
        return _build_record(
            **common,
            classification="credit_card_payment",
            match_method="strong_non_lender_exclusion",
            matched_rule="credit_card_payment",
            confidence_score=0.97,
            reason="The descriptor identifies a credit-card account payment.",
        )

    if _matches_any(text, _CHECK_PATTERNS):
        return _build_record(
            **common,
            classification="other",
            match_method="strong_non_lender_exclusion",
            matched_rule="check",
            confidence_score=0.94,
            reason="The row is a check or cheque and has no separate verified lender evidence.",
        )

    if _matches_any(text, _SUBSCRIPTION_PATTERNS):
        return _build_record(
            **common,
            classification="other",
            match_method="strong_non_lender_exclusion",
            matched_rule="subscription",
            confidence_score=0.93,
            reason="The row is a subscription or membership payment with no verified lender evidence.",
        )

    bank_registry = BANK_SPECIFIC_LENDER_ALIASES.get((bank or "").upper())
    bank_match = registry_match(text, bank_registry) if bank_registry and amount < 0 else None
    if bank_match is not None:
        lender, alias = bank_match
        return _build_record(
            **common,
            classification="confirmed_lender",
            canonical_entity=lender,
            match_method="bank_specific_lender_rule",
            matched_alias=alias,
            matched_rule=f"{bank}_lender_registry",
            confidence_score=0.98,
            reason=f"Matched lender alias or transaction code '{alias}' for {bank}.",
        )

    potential_match = registry_match(text, POTENTIAL_LENDER_ALIASES)
    if potential_match is not None and amount < 0:
        lender, alias = potential_match
        return _build_record(
            **common,
            classification="potential_lender",
            canonical_entity=lender,
            match_method="candidate_lender_alias",
            matched_alias=alias,
            matched_rule="potential_lender_registry",
            confidence_score=0.82,
            reason=f"Matched maintained candidate alias '{alias}'; confirmation requires review.",
            review_required=True,
        )

    if amount < 0 and _matches_any(text, _DIRECT_DEBIT_LOAN_PATTERNS):
        return _build_record(
            **common,
            classification="potential_lender",
            canonical_entity="Unidentified lender obligation",
            match_method="unidentified_loan_obligation",
            matched_rule="direct_debit_loan_without_verified_counterparty",
            confidence_score=0.78,
            reason=(
                "The posted debit explicitly identifies a loan obligation, but no verified "
                "lender counterparty is available."
            ),
            review_required=True,
        )

    explicit_repayment = _matches_any(text, _EXPLICIT_REPAYMENT_PATTERNS)
    financing_signal = _matches_any(text, _FINANCING_SIGNAL_PATTERNS)
    payment_marker = _matches_any(text, _PAYMENT_MARKER_PATTERNS)
    candidate = _canonical_unknown_entity(text) if financing_signal else None
    if amount < 0 and explicit_repayment:
        return _build_record(
            **common,
            classification="potential_lender",
            canonical_entity=candidate or "Unidentified lender obligation",
            match_method="explicit_financing_repayment",
            matched_rule="unknown_explicit_repayment",
            confidence_score=0.78,
            reason="The debit has an explicit financing-repayment descriptor, but the counterparty is not verified.",
            review_required=True,
        )

    if amount < 0 and financing_signal and payment_marker:
        return _build_record(
            **common,
            classification="other",
            canonical_entity=candidate,
            match_method="financing_keyword_review",
            matched_rule="financing_keyword_without_verified_entity",
            confidence_score=0.35,
            reason="Financing language alone is insufficient; recurrence and counterparty evidence are required.",
            review_required=True,
        )

    return _build_record(
        **common,
        classification="other",
        match_method="default",
        matched_rule="no_classification_rule",
        confidence_score=0.60,
        reason="No verified lender, insurance, or operational-category rule matched.",
    )
```

- [ ] **Step 8: Run the new tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_known_payee_classification.py tests/test_financing_proceeds_credits.py tests/test_classifier_lookups.py tests/test_flag_group_states.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 9: Settle the order table** (pin-ledger row 1). In `tests/test_lender_insurance_classification.py`, replace the whole `test_ordered_non_lender_rules_precede_lender_detection` (decorator and body, `:40-86`) with:

```python
@pytest.mark.parametrize(
    ("description", "expected_state", "entity"),
    [
        ("Cooperators monthly debit", "insurance", "Co-operators"),
        ("C0-OPERAT0RS commercial policy", "insurance", "Co-operators"),
        ("INTACT insurance premium", "insurance", "Intact Insurance"),
        ("Aviva business insurance", "insurance", "Aviva"),
        ("Wawanesa vehicle insurance", "insurance", "Wawanesa"),
        ("TD Insurance policy", "insurance", "TD Insurance"),
        ("RBC Insurance premium", "insurance", "RBC Insurance"),
        ("Desjardins Assurances policy", "insurance", "Desjardins Insurance"),
        ("PROGRESSIVE INS 800-776-4737", "insurance", "Progressive"),
        # Lease, equipment-financing and card rows moved to
        # tests/test_known_payee_classification.py, and the Clover row to
        # tests/test_obligation_descriptors.py (lender-detection design §2;
        # owner decisions 2026-09-25).
        ("ACH fee", "fee", None),
        ("INTERAC e-transfer fee", "fee", None),
        ("Merchant-processing fee", "fee", None),
        ("Internal transfer to savings", "transfer", None),
        ("ADP payroll", "payroll", None),
        ("IRS tax payment", "tax", None),
        ("Electric utility payment", "utility", None),
        ("Office rent payment", "rent", None),
        ("NSF returned item fee", "nsf_or_return", None),
        ("Payment reversal", "refund_or_reversal", None),
    ],
)
def test_ordered_non_lender_rules_precede_lender_detection(
    description: str,
    expected_state: str,
    entity: str | None,
):
    result = classify_transaction(description, -100.0)
    assert result.classification == expected_state
    assert result.canonical_entity == entity
    assert not result.contributes_to_lender_count
    assert not result.contributes_to_lender_totals
    assert not result.contributes_to_withholding_rate
    assert not result.contributes_to_potential_lender_totals
    assert not result.contributes_to_potential_withholding_exposure
    assert result.contributes_to_insurance_totals is (expected_state == "insurance")
    assert result.flagged_group is None
    assert not result.contributes_to_flagged_totals
```

- [ ] **Step 10: Settle the named aliases** (pin-ledger rows 2, 3 and 19). In `test_named_financing_aliases` (`:102-117`), these rows must read:
  ```python
          ("CMCA Finance BUS payment", "confirmed_lender", "CMCA Finance"),
          ("CMCAFINANCE debit", "confirmed_lender", "CMCA Finance"),
          ("91003457252 EFT Payment xxxxxx1111 Lily Advance 8008545315", "confirmed_lender", "Lily Advance"),
          ("External Withdrawal SNAP FINANCE - PAYMENT", "lease_or_rental", "SNAP Finance"),
  ```
  and the BDC row must read `("BDC loan payment", "alternative_position", "BDC"),`. Leave the two Forward rows as they are.

- [ ] **Step 11: Settle Item 12a** (pin-ledger rows 4, 5 and 18). In `tests/test_r1_hardcodes.py`, replace `test_afc_funding_confirmed_lender`, `test_intuit_financing_confirmed_lender` and `test_intuit_software_purchase_is_not_a_lender` (`:530-545`) with:

```python
    def test_afc_funding_is_floor_plan_financing(self):
        # Owner decision 2026-09-25 (lender-detection design §2): AFC Funding Corporation
        # funds dealer floor plans, so Item 12a's AFC FUNDING CORP is flagged Floor plan.
        record = classify_transaction("AFC FUNDING CORP XPRESS PAY", -4229.99)
        assert record.classification == "floor_plan_financing"
        assert record.canonical_entity == "AFC FUNDING CORP"
        assert record.flagged_group == "floor_plan"
        assert not record.contributes_to_withholding_rate

    def test_intuit_financing_is_an_alternative_position(self):
        # Owner ruling 2026-09-24 (lender-detection design §2) moved Item 12a's
        # INTUIT FINANCING out of the lenders: it is a flagged alternative position.
        record = classify_transaction("INTUIT FINANCING QBC_PMTS", -632.24)
        assert record.classification == "alternative_position"
        assert record.canonical_entity == "INTUIT FINANCING"
        assert record.flagged_group == "alternative_positions"
        assert not record.contributes_to_withholding_rate

    def test_intuit_software_purchase_is_not_a_lender(self):
        # H-2 negative evidence: the $37.10 QuickBooks software charge.
        record = classify_transaction("VSA PUR INTUIT QBOOKS ONLINE CL.INT", -37.10)
        assert record.classification not in (
            "confirmed_lender",
            "potential_lender",
            "alternative_position",
        )
        assert record.canonical_entity != "INTUIT FINANCING"
```

- [ ] **Step 12: Settle `tests/test_analysis.py`** (pin-ledger rows 6-8).
  - After the import line `from analysis.detect import detect, find_known_funders, find_recurring_debits` (`:13`), add `from analysis.transaction_classifier import classify_statement_transactions`.
  - In `test_metrics_computes_true_revenue_cash_flow_lender_pos_and_loan_counts`, after its final assertion `assert m.loan_count == 1`, add:
    ```python
        # Owner ruling 2026-09-24: SBA is an alternative position, never a potential lender.
        assert classify_statement_transactions(s)[4].classification == "alternative_position"
        assert m.potential_lender_debit_count == 0
    ```
  - Replace the body of `test_detect_affirm_without_space` after the `s = Statement(...)` block with:
    ```python
        matches = find_known_funders(s)
        assert matches == []
        # D8: a card-paid Affirm instalment is classified by who was paid.
        assert [record.classification for record in classify_statement_transactions(s)] == [
            "alternative_position",
            "alternative_position",
        ]
        assert compute_metrics(s).pos_count == 0
    ```
  - In `test_detect_expanded_lender_keyword_aliases`, the last line must read `assert [m.funder for m in matches] == ["FUNDWORKS", "De Lage Landen"]`.

- [ ] **Step 13: Settle ATB November** (pin-ledger rows 9-12). The lender lines move with BDC (an alternative position) and Econolease (a lender). The potential lines move here, not in Task 10: from this task on the classifier reads the rendered `POTENTIAL_LENDER_ALIASES`, whose review entities `MERCH PAD (probably Merchant Growth)` and `LOANS FC` claim the statement's 21 fixed daily debits and its direct-debit loan at step 11. Task 10's D6 then finds nothing left to promote on this statement (probe of 2026-09-26). In `tests/test_transaction_classifier.py`, directly before `from pathlib import Path` (`:3`), add `from collections import Counter`, and replace the whole function `test_atb_november_lender_and_potential_obligation_regression` (`:306-386`) with:

```python
def test_atb_november_lender_and_potential_obligation_regression():
    report = _real_statement_report("ATB/ATB Nov 2023.pdf")
    metrics = report.metrics

    assert report.statement.period_start == "2023-11-01"
    assert report.statement.period_end == "2023-11-30"
    assert report.reconciliation.ok
    # Owner rulings 2026-09-24/25: BDC is an alternative position, and Econolease
    # (equipment finance) is a lender. Derived totals only.
    assert metrics.lenders_detected == 3
    assert metrics.lender_debit_count == 45
    assert metrics.lender_debits == 9757.26
    # The C10 ledger's review tier (spec section 4.3 step 11): MERCH PAD's fixed
    # daily debits and the LOANS FC direct debit.
    assert metrics.potential_lenders_detected == 2
    assert metrics.potential_lender_debit_count == 22
    assert metrics.potential_lender_debit_total == 3178.19
    assert metrics.eligible_deposits == 59310.74
    assert metrics.potential_withholding_numerator == 3178.19
    assert metrics.potential_withholding_denominator == 59310.74
    assert metrics.potential_withholding_exposure == pytest.approx(
        3178.19 / 59310.74 * 100
    )
    assert round(metrics.potential_withholding_exposure, 2) == 5.36

    known_funders = {match.funder: match for match in report.detection.known_funders}
    assert set(known_funders) == {"CanaCap", "Econolease", "Forward Funding"}
    assert known_funders["Forward Funding"].debit_count == 21
    assert known_funders["Forward Funding"].total_debited == 4305.0
    assert known_funders["Econolease"].debit_count == 3
    # Owner ruling 2026-09-24: BDC is an alternative position, not a lender.
    assert sum(record.classification == "alternative_position" for record in report.classifications) == 1

    assert [match.funder for match in report.detection.potential_lenders] == [
        "MERCH PAD (probably Merchant Growth)",
        "LOANS FC",
    ]
    merch_pad, loans_fc = report.detection.potential_lenders
    assert (merch_pad.debit_count, merch_pad.total_debited) == (21, 2606.31)
    assert (loans_fc.debit_count, loans_fc.total_debited) == (1, 571.88)
    for potential in (merch_pad, loans_fc):
        assert potential.eligible_deposit_denominator == 59310.74
        assert potential.potential_withholding_exposure == pytest.approx(
            potential.total_debited / 59310.74 * 100
        )
        assert potential.review_required
    assert [transaction.description for transaction in loans_fc.transactions] == [
        "Direct Debit Loans FC"
    ]
    assert [transaction.amount for transaction in loans_fc.transactions] == [-571.88]
    assert len(report.detection.lender_evidence) == 45
    assert round(sum(abs(record.amount) for record in report.detection.lender_evidence), 2) == 9757.26
    assert len(report.detection.potential_lender_evidence) == 22
    assert Counter(record.match_method for record in report.detection.potential_lender_evidence) == {
        "candidate_lender_alias": 22,
    }
    assert not any(record.contributes_to_lender_totals for record in report.detection.potential_lender_evidence)

    payload = report_to_dict(report)
    serialized = {item["funder"]: item for item in payload["detection"]["potential_lenders"]}
    assert serialized["LOANS FC"]["debit_count"] == 1
    assert serialized["LOANS FC"]["total_debited"] == 571.88
    assert serialized["LOANS FC"]["eligible_deposit_denominator"] == 59310.74
    assert serialized["LOANS FC"]["potential_withholding_exposure"] == pytest.approx(
        571.88 / 59310.74 * 100
    )
    assert serialized["LOANS FC"]["status"] == "review_required"
    assert serialized["MERCH PAD (probably Merchant Growth)"]["debit_count"] == 21
    assert serialized["MERCH PAD (probably Merchant Growth)"]["total_debited"] == 2606.31

    package = _package_analysis(
        [Job(id="atb-nov", filename="ATB Nov 2023.pdf", status="done", analysis=payload)]
    )
    totals = package["totals"]
    assert totals["lenders_detected"] == 3
    assert totals["lender_debit_count"] == 45
    assert totals["lender_debits"] == 9757.26
    assert totals["potential_lenders_detected"] == 2
    assert totals["potential_lender_debit_count"] == 22
    assert totals["potential_lender_debit_total"] == 3178.19
    assert totals["eligible_deposits"] == 59310.74
    assert totals["potential_withholding_exposure"] == 5.36
    assert totals["decision"] == "review_required"

    package_candidates = {item["funder"]: item for item in package["potential_lenders"]}
    assert list(package_candidates) == ["LOANS FC", "MERCH PAD (probably Merchant Growth)"]
    package_candidate = package_candidates["LOANS FC"]
    assert package_candidate["debit_count"] == 1
    assert package_candidate["total_debited"] == 571.88
    assert package_candidate["eligible_deposit_denominator"] == 59310.74
    assert package_candidate["status"] == "review_required"
    assert package_candidates["MERCH PAD (probably Merchant Growth)"]["debit_count"] == 21
    assert Counter(row["match_method"] for row in package["potential_lender_evidence"]) == {
        "candidate_lender_alias": 22,
    }
```

  In `tests/test_revenue_classification.py::test_atb_november_true_revenue_regression_from_exact_evidence`, lines `:402-405` must read:
  ```python
      assert metrics.lenders_detected == 3
      assert metrics.lender_debit_count == 45
      assert metrics.lender_debits == 9757.26
      assert metrics.potential_lender_debit_total == 3178.19
  ```

- [ ] **Step 14: Settle the other pins the ledger moves in `tests/test_lender_insurance_classification.py`** (pin-ledger rows 20-25). CMCA Finance and Econolease are lenders (owner decisions 2026-09-25), and the ledger holds `LOANS FC` as a review entity.
  - In `test_unidentified_direct_debit_loan_is_potential_and_requires_review` (`:130-145`), replace `result = classify_transaction("Direct Debit Loans FC", -571.88)` with `result = classify_transaction("Direct Debit Loans", -571.88)`, and add as its last lines:
    ```python
        # The C10 ledger holds LOANS FC as a review entity: the potential registry names it.
        named = classify_transaction("Direct Debit Loans FC", -571.88)
        assert (named.classification, named.canonical_entity) == ("potential_lender", "LOANS FC")
        assert (named.match_method, named.matched_rule) == ("candidate_lender_alias", "potential_lender_registry")
        assert named.review_required
        assert not named.contributes_to_withholding_rate
    ```
  - In `test_recurring_counterparty_normalization_removes_ids_not_business_name`, the line `assert {record.classification for record in records} == {"potential_lender"}` (`:196`) must read `assert {record.classification for record in records} == {"confirmed_lender"}`. Its `PAYMENT - AUTOMATIC LOAN PYMT W/D` block stays until Task 8.
  - Replace the line `def _audit_report() -> Report:` (`:230`) with `def _audit_report(*extra: Transaction) -> Report:`, and in its `transactions=[...]` list replace the last row `            _txn("2054-01-12", "BDC payment returned NSF", -200.0),` with:
    ```python
                _txn("2054-01-12", "BDC payment returned NSF", -200.0),
                *extra,
    ```
  - In `test_metrics_api_tables_filters_and_withholding_share_exact_evidence` (`:275-364`), replace everything from `    assert metrics["lenders_detected"] == 2` through `    assert package["potential_lenders"][0]["total_debited"] == 125.0` with:
    ```python
        # Owner decisions 2026-09-25: CMCA Finance and Econolease are lenders.
        assert metrics["lenders_detected"] == 4
        assert metrics["potential_lenders_detected"] == 0
        assert metrics["lender_debit_count"] == len(lender_filter_rows) == len(lender_evidence) == 5
        assert metrics["lender_debits"] == metrics["withholding_numerator"] == 2660.0
        assert sum(abs(row["amount"]) for row in lender_filter_rows) == 2660.0
        assert sum(abs(row["amount"]) for row in lender_evidence) == 2660.0
        assert metrics["withholding_denominator"] == metrics["eligible_deposits"] == 16898.73
        assert metrics["withholding_rate"] == pytest.approx(2660.0 / 16898.73 * 100)
        assert round(metrics["withholding_rate"], 2) == 15.74

        assert metrics["potential_lender_debit_count"] == len(potential_filter_rows) == 0
        assert metrics["potential_lender_debit_total"] == metrics["potential_lender_debits"] == 0.0
        assert not metrics["potential_withholding_review_required"]
        assert potential_lender_evidence == []

        assert metrics["insurance_count"] == len(insurance_filter_rows) == len(insurance_evidence) == 2
        assert metrics["insurance_total"] == 600.0
        assert sum(abs(row["amount"]) for row in insurance_filter_rows) == 600.0
        assert {item["funder"] for item in payload["detection"]["known_funders"]} == {
            "CanaCap",
            "CAN Capital",
            "CMCA Finance",
            "Econolease",
        }
        assert payload["detection"]["potential_lenders"] == []
        assert {item["provider"] for item in payload["detection"]["insurance_providers"]} == {
            "Co-operators",
            "Intact Insurance",
        }
        assert payload["classifications"] == [row["classification"] for row in transactions]

        package = _package_analysis(
            [Job(id="audit", filename="audit.pdf", status="done", analysis=payload)]
        )
        totals = package["totals"]
        assert totals["lenders_detected"] == 4
        assert totals["potential_lenders_detected"] == 0
        assert totals["lender_debit_count"] == 5
        assert totals["lender_debits"] == totals["withholding_numerator"] == 2660.0
        assert totals["withholding_denominator"] == 16898.73
        assert totals["package_withholding_rate"] == 15.74
        assert len(package["lender_evidence"]) == 5
        assert totals["potential_lender_debit_count"] == 0
        assert totals["potential_lender_debit_total"] == totals["potential_lender_debits"] == 0.0
        assert not totals["potential_withholding_review_required"]
        # Still review: the fixture's customer deposit needs revenue review (measured 2026-09-26).
        assert totals["decision"] == "review_required"
        assert package["potential_lender_evidence"] == []
    ```
    and keep its three insurance lines after that block (`assert totals["insurance_count"] == 2` and the two after it).
  - Replace the whole `test_potential_funder_serialization_rebuilds_values_from_authoritative_evidence` (`:367-380`) with:
    ```python
    def test_potential_funder_serialization_rebuilds_values_from_authoritative_evidence():
        # CMCA Finance is a lender since the owner decision of 2026-09-25, so a fabricated
        # unnamed direct-debit loan is the audit fixture's potential row here.
        report = _audit_report(_txn("2054-01-13", "Direct Debit Loans", -125.0))
        candidate = report.detection.potential_lenders[0]
        assert candidate.funder == "Unidentified lender obligation"
        candidate.debit_count = 0
        candidate.total_debited = 0.0
        candidate.potential_withholding_exposure = None

        payload = report_to_dict(report)
        serialized = payload["detection"]["potential_lenders"][0]
        assert serialized["debit_count"] == serialized["potential_lender_debit_count"] == 1
        assert serialized["total_debited"] == serialized["potential_lender_debit_total"] == 125.0
        assert serialized["eligible_deposit_denominator"] == 16898.73
        assert serialized["potential_withholding_exposure"] == pytest.approx(
            125.0 / 16898.73 * 100
        )

        # The package rebuilds a stale candidate from the same evidence (moved here from
        # the TD CMCA test, whose candidate is now a lender).
        stale_payload = deepcopy(payload)
        stale_candidate = stale_payload["detection"]["potential_lenders"][0]
        for key in (
            "debit_count",
            "potential_lender_debit_count",
            "potential_lender_debit_total",
            "eligible_deposit_denominator",
            "potential_withholding_exposure",
        ):
            stale_candidate.pop(key, None)
        stale_candidate["total_debited"] = 0.0
        rebuilt_package = _package_analysis(
            [Job(id="audit-stale", filename="audit.pdf", status="done", analysis=stale_payload)]
        )
        rebuilt_candidate = rebuilt_package["potential_lenders"][0]
        assert rebuilt_candidate["debit_count"] == 1
        assert rebuilt_candidate["total_debited"] == 125.0
        assert rebuilt_candidate["eligible_deposit_denominator"] == 16898.73
        assert rebuilt_candidate["potential_withholding_exposure"] == pytest.approx(
            125.0 / 16898.73 * 100
        )
        assert rebuilt_package["totals"]["potential_lender_debit_total"] == 125.0
    ```
  - In `test_duplicate_potential_lender_row_is_excluded_from_potential_totals` (`:405-422`), replace the descriptor `"CMCA Finance BUS payment"` with `"Direct Debit Loans"` in all three rows, and add directly under the `def` line the comment `    # CMCA Finance is a lender since 2026-09-25; an unnamed direct-debit loan stays potential.` Every assertion stays.
  - Replace the whole `test_td_cmca_fixture_reports_potential_amount_and_exposure_without_promotion` (`:474-563`) with:
    ```python
    def test_td_cmca_fixture_counts_cmca_finance_as_a_lender():
        """Owner decision 2026-09-25: CMCA Finance is a merchant cash advance funder, a counted lender."""
        root = Path(__file__).resolve().parents[1]
        pdf = root / "Bank Statements" / "TD Can" / "Jan_30-Feb_27_2026 (3).pdf"
        document = parse_native_td_canada(pdf.read_bytes(), source_file=pdf.name)
        assert document is not None

        report = analyze_markdown(document.to_markdown(), parse_mode="deterministic")
        payload = report_to_dict(report)
        metrics = payload["metrics"]
        lender_rows = [
            transaction
            for transaction in payload["statement"]["transactions"]
            if transaction["classification"]["contributes_to_withholding_rate"]
        ]

        assert payload["statement"]["bank"] == "TD Canada Trust"
        assert payload["statement"]["currency"] == "CAD"
        assert metrics["lenders_detected"] == 1
        assert metrics["lender_debit_count"] == len(lender_rows) == 20
        assert metrics["lender_debits"] == metrics["withholding_numerator"] == 2235.0
        assert sum(abs(row["amount"]) for row in lender_rows) == 2235.0
        assert metrics["eligible_deposits"] == metrics["withholding_denominator"] == 16898.73
        assert metrics["withholding_rate"] == pytest.approx(2235.0 / 16898.73 * 100)
        assert round(metrics["withholding_rate"], 2) == 13.23
        assert metrics["potential_lenders_detected"] == 0
        assert metrics["potential_lender_debit_count"] == 0
        assert metrics["potential_lender_debit_total"] == 0.0
        assert not metrics["potential_withholding_review_required"]
        assert {row["description"] for row in lender_rows} == {"CMCA Finance BUS"}
        assert {row["amount"] for row in lender_rows} == {-111.75}
        assert {row["classification"]["canonical_entity"] for row in lender_rows} == {"CMCA Finance"}

        funders = payload["detection"]["known_funders"]
        assert [funder["funder"] for funder in funders] == ["CMCA Finance"]
        funder = funders[0]
        assert funder["classification"] == "confirmed_lender"
        assert funder["debit_count"] == 20
        assert funder["total_debited"] == 2235.0
        assert len(funder["transactions"]) == len(funder["evidence"]) == 20
        assert len(payload["detection"]["lender_evidence"]) == 20
        assert payload["detection"]["potential_lenders"] == []
        assert payload["detection"]["potential_lender_evidence"] == []

        package = _package_analysis(
            [Job(id="td-cmca", filename=pdf.name, status="done", analysis=payload)]
        )
        totals = package["totals"]
        assert totals["lenders_detected"] == 1
        assert totals["lender_debit_count"] == 20
        assert totals["lender_debits"] == totals["withholding_numerator"] == 2235.0
        assert totals["withholding_denominator"] == 16898.73
        assert totals["package_withholding_rate"] == 13.23
        assert totals["potential_lender_debit_count"] == 0
        assert totals["potential_lender_debit_total"] == 0.0
        assert not totals["potential_withholding_review_required"]
        # Still review: the statement's unverified deposits need revenue review (measured 2026-09-26).
        assert totals["decision"] == "review_required"
        assert len(package["lender_evidence"]) == 20
        assert [(item["funder"], item["debit_count"], item["total_debited"]) for item in package["funders"]] == [
            ("CMCA Finance", 20, 2235.0)
        ]
    ```

- [ ] **Step 15: Settle first_farmers** (pin-ledger row 14). In `tests/test_new_statement_corpus.py`, the first_farmers `"lenders"` entry (`:122`) must read `"lenders": (0, 0.00, 0, 0.00),`, and append at the end of the file:

```python
def test_first_farmers_bluevine_named_row_is_not_flagged():
    """Owner decision 2026-09-25: the bare BLUEVINE alias is dropped. first_farmers' one
    BlueVine-named debit pays another business that banks with Bluevine, so it is no
    lender, no line of credit and no flagged row."""
    report = _source_report("first_farmers")
    assert not any(record.classification == "line_of_credit" for record in report.classifications)
    assert not any(record.canonical_entity == "BLUEVINE" for record in report.classifications)
    assert report.metrics.lenders_detected == 0
```

- [ ] **Step 16: Settle relay** (pin-ledger row 17). The relay `"channels"` entry of `EXPECTED` in `tests/test_new_statement_corpus.py` (`:181`) must read `"channels": (2, 8, 59, 9, 0, 0),`: D8 moves the seven card-paid personal-loan rows (Klover 5, Tilt 2; Task 0 reads `relay: POS rows claimed = 7`) out of POS. relay's `"lenders"` entry stays `(0, 0.00, 0, 0.00)`: personal loans are flagged, never lenders or potential lenders.

- [ ] **Step 17: Run the core and wider selections.**

Run:
```
C:\Python314\python.exe -m pytest tests/test_known_payee_classification.py tests/test_financing_proceeds_credits.py tests/test_classifier_lookups.py tests/test_flag_group_states.py tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_r1_hardcodes.py tests/test_new_statement_corpus.py -q -p no:cacheprovider
C:\Python314\python.exe -m pytest tests/test_analysis.py -q -p no:cacheprovider -k "altana or ibc_source or withholding or lender or funder or affirm or expanded_lender or recurring or metrics"
```
Expected: PASS. Any other failure: stop and report the test id.

- [ ] **Step 18: Commit.**

```
git add analysis/transaction_classifier.py tests/test_known_payee_classification.py tests/test_lender_insurance_classification.py tests/test_r1_hardcodes.py tests/test_analysis.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_new_statement_corpus.py
git commit -m "classifier: the known-payee matcher decides debit groups (D8, D9)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 6: Delete the retired classifier inputs

**Files:**
- Modify (only for the names Task 0 printed as `still defined: True`): `analysis/classification_registry.py`. Delete the `LEASE_PROVIDER_ALIASES`, `LEGACY_CONFIRMED_LENDER_ALIASES` and `LEGACY_POTENTIAL_LENDER_ALIASES` tables, and S1's "Deprecated" header comment above them.
- Modify: `tests/test_known_payee_classification.py` (append)

**Interfaces:**
- Consumes: nothing new. After Task 5 no module reads the three tables.
- Produces: C2 as the master plan states it (`LEASE_PROVIDER_ALIASES` removed). Both `LEGACY_*` tables go with it: they exist only for the pre-S2 classifier, and no contract name refers to them.

- [ ] **Step 1: Append the failing test** to `tests/test_known_payee_classification.py`:

```python


@pytest.mark.parametrize(
    "name",
    ["LEASE_PROVIDER_ALIASES", "LEGACY_CONFIRMED_LENDER_ALIASES", "LEGACY_POTENTIAL_LENDER_ALIASES"],
)
def test_the_retired_classifier_inputs_are_gone(name):
    from analysis import classification_registry

    assert not hasattr(classification_registry, name)
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_known_payee_classification.py -q -p no:cacheprovider -k retired`
Expected: FAIL for each name Task 0 printed as `still defined: True`, one failure per name (the pre-C10 S1 tree kept all three, which gave three failures). If Task 0 printed `False` for all three, the test passes here; skip Step 3 and commit the test alone in Step 5.

- [ ] **Step 3: Delete the tables.** For each name Task 0 printed as `still defined: True`, delete its whole assignment from `analysis/classification_registry.py` (from `<NAME>: dict[str, tuple[str, ...]] = {` through its closing `}`):
  - `LEASE_PROVIDER_ALIASES`
  - `LEGACY_CONFIRMED_LENDER_ALIASES`
  - `LEGACY_POTENTIAL_LENDER_ALIASES`

  If present, also delete S1's "Deprecated" comment block above them (on the pre-C10 S1 tree it starts `# --- Deprecated: the inputs of the classifier as it stands before S2 ---`), down to the line before the next assignment. Delete nothing else: never touch the block S1 renders from the C10 ledger, or S1's owner-ruling constants just above that comment (`PREMIUM_FINANCE_INSURER_ALIASES`, `MERGED_REGISTRY_ENTITIES`, `REATTRIBUTED_REGISTRY_ALIASES`, and `PAYOUT_CREDIT_ENTITIES`, which the classifier reads). If one of the three tables sits inside that rendered block, stop and report it to the orchestrator; deleting it would break S1's drift test. Then confirm no reader is left:

Run: `git grep -n "LEASE_PROVIDER_ALIASES\|LEGACY_CONFIRMED_LENDER_ALIASES\|LEGACY_POTENTIAL_LENDER_ALIASES" -- analysis webapp benchmark batch.py analyze.py`
Expected: no output. Test files and `tools/` may still name them: S1's tests read the legacy lists through `getattr` and skip once they are gone (that is how the pre-C10 S1 tree's tests behaved).

- [ ] **Step 4: Run the new test and S1's tests.**

Run, in PowerShell from the repository root:
```powershell
C:\Python314\python.exe -m pytest tests/test_known_payee_classification.py tests/test_no_statement_hardcodes.py -q -p no:cacheprovider
$s1Tests = git diff --name-only --diff-filter=A 4f219cd lender-detection -- "tests/test_*.py"
$s1Tests
C:\Python314\python.exe -m pytest $s1Tests -q -p no:cacheprovider
```
Expected:
- The first command passes, except the known pre-existing `test_no_literal_account_numbers_in_ocr`.
- `$s1Tests` lists every test file S1 added to `lender-detection`: its C1 and C3 tests, the C10 validator and drift tests, the speed test and the alias-audit tests. S1's current plan adds nine (its File Structure; `tests/lender_ledger_fixture.py` is a helper, not a `test_*.py` file, so the filter leaves it out):
  - `tests/test_flag_groups.py`
  - `tests/test_classification_registry_groups.py`
  - `tests/test_payee_matcher.py`
  - `tests/test_classifier_speed.py`
  - `tests/test_lender_ledger.py`
  - `tests/test_build_lender_registry.py`
  - `tests/test_lender_registry_drift.py`
  - `tests/test_lender_registry_content.py`
  - `tests/test_lender_alias_audit.py`

  The pre-C10 S1 tree added seven of them (not `tests/test_lender_ledger.py` or `tests/test_lender_registry_drift.py`). If the list differs from these nine, run what git lists and report the difference. If it lists nothing, stop: S1 has not merged into `lender-detection`, so `pytest` would collect the whole repository.
- The last command passes. Only S1's legacy-list checks may report as skipped, by S1's design. S1's own Task 9 counts 223 passed before S2; after this task, its legacy-list checks skip. The pre-C10 tree gave `308 passed, 4 skipped` over its seven files. Any failure: stop and report the test id.

- [ ] **Step 5: Commit.**

```
git add analysis/classification_registry.py tests/test_known_payee_classification.py
git commit -m "registry: delete the classifier inputs retired by version 5.0" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 7: Premium financing stays insurance and carries its flag (§4.2, §4.3 step 4)

**Files:**
- Modify: `analysis/transaction_classifier.py`:
  - the `from .classification_registry import (` block;
  - two new definitions after `match_insurance_provider`;
  - the `_build_record` signature and its flag lines (Task 2);
  - the insurance block of `_classify_credit_revenue` (Task 4);
  - the insurance block of `classify_transaction` (Task 5).
- Modify: `tests/flag_group_fixtures.py` (append)
- Test: `tests/test_premium_financing.py`

**Interfaces:**
- Consumes: C1 `FLAG_GROUPS` (`premium_financing` is the group whose `state` is None); C2 `PREMIUM_FINANCE_ALIASES` and `INSURANCE_PROVIDER_ALIASES`; C3 `registry_match(normalized_text, registry) -> tuple[str, str] | None`.
- Produces (C4): an insurance row whose insurer match is a `PREMIUM_FINANCE_ALIASES` payee has:
  - `classification="insurance"`, `canonical_entity=<premium-finance entity>`, `match_method="insurance_provider_alias"`, `matched_rule="premium_finance_provider"`;
  - `contributes_to_insurance_totals` exactly as any insurance debit;
  - on a debit, `flagged_group="premium_financing"` and `contributes_to_flagged_totals` (posted debits only; cleared for duplicates and settlement reversals by Task 2's passes).
- A premium-finance credit keeps the insurance credit treatment (revenue `non_revenue`, `revenue_match_method="insurance_provider_credit_exclusion"`) and carries no flag.
- Produces the owner decisions of 2026-09-25 on premium financing:
  - **Premium-finance wording** (`premium_finance_wording`). A row that no premium-finance alias claimed, and whose descriptor says premium finance (`PREM FIN`, `PREMIUM FINANCE`, `PREMIUM FINANCING`, `INSPREMFIN`), is insurance with `matched_rule="premium_finance_descriptor"` and the same flag on a debit. Its entity is the insurer when `INSURANCE_PROVIDER_ALIASES` names one (`match_method="insurance_provider_alias"`), else `Insurance provider not identified` (`match_method="insurance_descriptor"`). A credit keeps the insurance credit treatment: its revenue still reads only the two registries.
  - **FIRST INSURANCE is FIRST Insurance Funding.** The bare ACH company name `FIRST INSURANCE` is also a premium-finance alias of `FIRST Insurance Funding` (S1's `PREMIUM_FINANCE_INSURER_ALIASES`). This rule reads `PREMIUM_FINANCE_ALIASES` first, so those rows stay insurance and are flagged premium financing with no code of their own. The hand-kept insurer `First Insurance` is unchanged.
- Also produces: the keyword `_build_record(..., flagged_group: str | None = None)`; `_insurance_registry_match(text: str) -> tuple[str, str, bool] | None`; `_PREMIUM_FINANCE_WORDING_PATTERNS`; the test fixture `fake_premium_finance`.

- [ ] **Step 1: Append the fake insurers** to `tests/flag_group_fixtures.py`:

```python


@pytest.fixture
def fake_premium_finance(monkeypatch):
    """Route the insurance rule's two registries to fabricated insurers for one test.

    `FABRICATED INSURER FUNDING` (premium finance) contains the shorter insurer
    alias `FABRICATED INSURER`, as a premium financier's name can contain an
    insurer's.
    """
    monkeypatch.setattr(
        transaction_classifier,
        "INSURANCE_PROVIDER_ALIASES",
        {"Fabricated Insurer": ("FABRICATED INSURER",)},
    )
    monkeypatch.setattr(
        transaction_classifier,
        "PREMIUM_FINANCE_ALIASES",
        {
            "Fabricated Premium Finance": ("FABRICATED PFC",),
            "Fabricated Insurer Funding": ("FABRICATED INSURER FUNDING",),
        },
    )
```

- [ ] **Step 2: Write the failing test** `tests/test_premium_financing.py`:

```python
from __future__ import annotations

import pytest

from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import fake_premium_finance, txn  # noqa: F401  (fixture)


def test_a_premium_finance_debit_stays_insurance_and_is_flagged(fake_premium_finance):
    record = classify_transaction("ACH DEBIT FABRICATED PFC 0001", -300.0)
    assert record.classification == "insurance"
    assert (record.canonical_entity, record.matched_alias) == ("Fabricated Premium Finance", "FABRICATED PFC")
    assert record.matched_rule == "premium_finance_provider"
    assert record.flagged_group == "premium_financing"
    assert record.contributes_to_flagged_totals
    assert record.contributes_to_insurance_totals
    assert not record.contributes_to_lender_count
    assert not record.contributes_to_withholding_rate
    assert not record.contributes_to_potential_lender_totals


def test_a_premium_financier_wins_over_a_shorter_insurer_alias(fake_premium_finance):
    record = classify_transaction("FABRICATED INSURER FUNDING PMT", -300.0)
    assert (record.classification, record.canonical_entity) == ("insurance", "Fabricated Insurer Funding")
    assert record.flagged_group == "premium_financing"


def test_an_ordinary_insurer_carries_no_flag(fake_premium_finance):
    record = classify_transaction("FABRICATED INSURER PMT", -300.0)
    assert (record.classification, record.canonical_entity) == ("insurance", "Fabricated Insurer")
    assert record.matched_rule == "verified_insurance_provider"
    assert record.flagged_group is None
    assert not record.contributes_to_flagged_totals
    assert record.contributes_to_insurance_totals


def test_a_premium_finance_credit_keeps_the_insurance_credit_treatment(fake_premium_finance):
    record = classify_transaction("FABRICATED PFC 0001", 300.0)
    assert record.classification == "insurance"
    assert record.flagged_group is None
    assert not record.contributes_to_flagged_totals
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "insurance_provider_credit_exclusion"
    assert record.revenue_canonical_entity == "Fabricated Premium Finance"
    assert not record.contributes_to_lender_credit_exclusion


def test_a_proven_duplicate_premium_finance_debit_leaves_the_flagged_totals(fake_premium_finance):
    statement = Statement(
        transactions=[
            txn("2054-01-02", "ACH DEBIT FABRICATED PFC", -300.0, balance=700.0),
            txn("2054-01-02", "ACH DEBIT FABRICATED PFC", -300.0, balance=700.0),
        ]
    )
    first, duplicate = classify_statement_transactions(statement)
    assert first.contributes_to_flagged_totals
    assert duplicate.flagged_group == "premium_financing"
    assert not duplicate.contributes_to_flagged_totals
    assert not duplicate.contributes_to_insurance_totals


@pytest.mark.parametrize(
    "description",
    # The last is fabricated: the bare ACH company name FIRST INSURANCE is FIRST Insurance
    # Funding (owner decision 2026-09-25).
    ["IPFS CORP PMT", "FIRST INSURANCE FUNDING PMT", "FIRST INSURANCE DES INSURANCE"],
)
def test_owner_named_premium_financiers_are_insurance_and_flagged(description):
    record = classify_transaction(description, -300.0)
    assert record.classification == "insurance"
    assert record.flagged_group == "premium_financing"
    assert record.contributes_to_insurance_totals


def test_the_bare_first_insurance_originator_is_first_insurance_funding():
    record = classify_transaction("FIRST INSURANCE DES INSURANCE", -300.0)
    assert (record.canonical_entity, record.matched_alias) == ("FIRST Insurance Funding", "FIRST INSURANCE")
    assert record.matched_rule == "premium_finance_provider"
    assert record.contributes_to_flagged_totals


@pytest.mark.parametrize(
    ("description", "entity", "alias", "method"),
    [
        ("FABRICATED INSURER PREMIUM FINANCE 0001", "Fabricated Insurer", "FABRICATED INSURER", "insurance_provider_alias"),
        ("ACH DEBIT PREM FIN 0001", "Insurance provider not identified", None, "insurance_descriptor"),
        ("INSPREMFIN 0001", "Insurance provider not identified", None, "insurance_descriptor"),
    ],
)
def test_premium_finance_wording_is_premium_financing_under_the_insurer_it_names(
    fake_premium_finance, description, entity, alias, method
):
    """Owner decision 2026-09-25: premium-finance wording with no premium-finance payee named."""
    record = classify_transaction(description, -300.0)
    assert (record.classification, record.canonical_entity, record.matched_alias) == ("insurance", entity, alias)
    assert (record.match_method, record.matched_rule) == (method, "premium_finance_descriptor")
    assert record.flagged_group == "premium_financing"
    assert record.contributes_to_flagged_totals
    assert record.contributes_to_insurance_totals


def test_a_premium_finance_wording_credit_carries_no_flag(fake_premium_finance):
    record = classify_transaction("PREM FIN 0001", 300.0)
    assert record.classification == "insurance"
    assert record.flagged_group is None
    assert not record.contributes_to_flagged_totals
```

- [ ] **Step 3: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_premium_financing.py -q -p no:cacheprovider`
Expected: FAIL.
- Every `fake_premium_finance` test errors at setup with `AttributeError: <module 'analysis.transaction_classifier' ...> has no attribute 'PREMIUM_FINANCE_ALIASES'`.
- The three owner-named rows fail on `flagged_group`, which is None. The `FIRST INSURANCE FUNDING` row may already be `insurance` through a shorter insurer alias, and the `FIRST INSURANCE DES INSURANCE` row is `insurance` through the hand-kept insurer `First Insurance`, so `test_the_bare_first_insurance_originator_is_first_insurance_funding` fails on the entity.

- [ ] **Step 4: Import the premium-finance table.** In the `from .classification_registry import (` block, replace

```python
    POTENTIAL_LENDER_ALIASES,
)
```
with
```python
    POTENTIAL_LENDER_ALIASES,
    PREMIUM_FINANCE_ALIASES,
)
```

- [ ] **Step 5: Add the insurer lookup and the premium-finance wording.** Directly after the `match_insurance_provider` function (which Task 3 left calling `registry_match`), add:

```python


#: The flag group of an insurance row whose insurer is a premium-finance payee
#: (C1: the one flag group that is not a classification state).
_PREMIUM_FINANCING_GROUP = "premium_financing"


def _insurance_registry_match(text: str) -> tuple[str, str, bool] | None:
    """Spec §4.3 step 4: the insurer of an insurance row, as (entity, alias, premium_finance).

    Premium-finance payees (`PREMIUM_FINANCE_ALIASES`, spec §4.2) are consulted
    first, so a premium financier whose name contains an insurer's name is still
    the premium financier.
    """
    premium = registry_match(text, PREMIUM_FINANCE_ALIASES)
    if premium is not None:
        return premium[0], premium[1], True
    insurer = registry_match(text, INSURANCE_PROVIDER_ALIASES)
    if insurer is not None:
        return insurer[0], insurer[1], False
    return None


#: Owner decision 2026-09-25 (premium_finance_wording): premium-finance wording on
#: a row no premium-finance alias claimed is premium financing too. Read by the
#: insurance rule of `classify_transaction` only; credit revenue reads the registries.
_PREMIUM_FINANCE_WORDING_PATTERNS = (
    re.compile(r"\bPREM(?:IUM)? ?FIN(?:ANCE|ANCING)?\b"),
    re.compile(r"\bINSPREMFIN\b"),
)
```

- [ ] **Step 6: Let a rule pass the premium-financing group to `_build_record`.** In the `_build_record` signature, replace

```python
    review_required: bool = False,
    contributes_to_lender_credit_exclusion: bool = False,
) -> TransactionClassification:
```
with
```python
    review_required: bool = False,
    contributes_to_lender_credit_exclusion: bool = False,
    flagged_group: str | None = None,
) -> TransactionClassification:
```
In its body, replace the two lines Task 2 added
```python
    flag_group = FLAG_GROUP_BY_STATE.get(classification)
    contributes_flagged = flag_group is not None and is_debit and is_posted
```
with
```python
    flag_group = FLAG_GROUP_BY_STATE.get(classification)
    # A flag-group state names its own group. Premium financing is the one group
    # a rule passes in, on an insurance row (C1, C4).
    group_key = flag_group.key if flag_group is not None else flagged_group
    contributes_flagged = group_key is not None and is_debit and is_posted
```
and in its `TransactionClassification(...)` call replace `        flagged_group=flag_group.key if flag_group is not None else None,` with `        flagged_group=group_key,`.

- [ ] **Step 7: Keep the insurance credit treatment for premium-finance credits.** In `_classify_credit_revenue`, replace

```python
    insurance_match = registry_match(text, INSURANCE_PROVIDER_ALIASES)
    if insurance_match is not None:
        entity, alias = insurance_match
        return _RevenueDecision(
```
with
```python
    # A premium-finance credit keeps the insurance credit treatment (spec §4.2).
    insurance_match = _insurance_registry_match(text)
    if insurance_match is not None:
        entity, alias, _premium_finance = insurance_match
        return _RevenueDecision(
```

- [ ] **Step 8: Flag premium financing in the insurance rule.** In `classify_transaction`, replace

```python
    insurance_match = registry_match(text, INSURANCE_PROVIDER_ALIASES)
    if insurance_match is not None:
        provider, alias = insurance_match
        return _build_record(
            **common,
            classification="insurance",
            canonical_entity=provider,
            match_method="insurance_provider_alias",
            matched_alias=alias,
            matched_rule="verified_insurance_provider",
            confidence_score=0.99,
            reason=f"Matched maintained insurance provider alias '{alias}'.",
        )
```
with
```python
    insurance_match = _insurance_registry_match(text)
    # Owner decision 2026-09-25: premium-finance wording on a row no premium-finance
    # alias claimed is premium financing too, under the insurer when one is named.
    premium_wording = (insurance_match is None or not insurance_match[2]) and _matches_any(
        text, _PREMIUM_FINANCE_WORDING_PATTERNS
    )
    if insurance_match is not None or premium_wording:
        provider, alias, premium_finance = insurance_match or ("Insurance provider not identified", None, False)
        if premium_finance:
            rule = "premium_finance_provider"
            reason = (
                f"Matched maintained premium-finance alias '{alias}'; the row stays insurance "
                "and is also flagged as premium financing."
            )
        elif premium_wording:
            rule = "premium_finance_descriptor"
            reason = (
                "The descriptor says premium finance; the row stays insurance and is also "
                "flagged as premium financing."
            )
        else:
            rule = "verified_insurance_provider"
            reason = f"Matched maintained insurance provider alias '{alias}'."
        return _build_record(
            **common,
            classification="insurance",
            canonical_entity=provider,
            match_method="insurance_provider_alias" if alias is not None else "insurance_descriptor",
            matched_alias=alias,
            matched_rule=rule,
            confidence_score=0.99 if alias is not None else 0.95,
            reason=reason,
            # Spec §4.2: premium financing keeps the insurance state and the
            # insurance totals, and also carries its flag, on debits only.
            flagged_group=(
                _PREMIUM_FINANCING_GROUP if (premium_finance or premium_wording) and amount < 0 else None
            ),
        )
```

- [ ] **Step 9: Run the tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_premium_financing.py tests/test_flag_group_states.py tests/test_known_payee_classification.py tests/test_financing_proceeds_credits.py tests/test_lender_insurance_classification.py tests/test_revenue_classification.py tests/test_no_statement_hardcodes.py -q -p no:cacheprovider`
Expected: PASS, except the known pre-existing `test_no_literal_account_numbers_in_ocr`.

- [ ] **Step 10: Commit.**

```
git add analysis/transaction_classifier.py tests/flag_group_fixtures.py tests/test_premium_financing.py
git commit -m "classifier: premium financing stays insurance and carries its flag" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 8: Obligation descriptors for unnamed payees (step 8, D4, D5)

**Files:**
- Modify: `analysis/transaction_classifier.py` (import block; `_LEASE_PATTERNS` definition `:338-343`; `_CREDIT_CARD_PATTERNS` `:319-327`; new constants after `CLASSIFICATION_VERSION`; new patterns after `_CREDIT_CARD_PATTERNS`; new helpers after `_descriptor_proceeds_credit_record` (Task 4); `classify_transaction` lease/card blocks)
- Modify: `tests/test_lender_insurance_classification.py:199-204`
- Modify (bank-name variant only): `tests/test_new_statement_corpus.py:153`
- Test: `tests/test_obligation_descriptors.py`

**Interfaces:**
- Consumes: C2 `BANK_NAME_ALIASES`, `CARD_ISSUER_CONTEXT_ALIASES`; C3 `registry_match`.
- Produces: debit-only step-8 records: `line_of_credit`, `mortgage`, `vehicle_financing`, `bank_loan` (bank-name route: `match_method="bank_name_alias"`, entity and alias from `BANK_NAME_ALIASES`; own-loan transfer: `matched_rule="own_bank_loan_transfer"`, entity = the statement bank or `None`), `lease_or_rental`, `credit_card_payment` (entity from `CARD_ISSUER_CONTEXT_ALIASES` when listed), and D4 `potential_lender` with `match_method="unnamed_equipment_financing"`. Produces the constant `UNIDENTIFIED_LENDER_OBLIGATION = "Unidentified lender obligation"`. `lease_or_equipment_financing` is no longer produced.
- Produces the step-8 rules of the owner decisions of 2026-09-25, in the order the rules' own placement gives them. Every one is debit-only, and steps 1-7 keep precedence:
  1. **The own-account guard** (`step8_own_account_transfer_guard`): a debit whose whole descriptor is a fintech transfer between the holder's own accounts (`TRANSFER TO <nickname> [ACCOUNT] TRANSFER OUT`) takes no step-8 rule and continues to steps 9-11 as today. On one fintech bank the holder named a sub-account with auto-loan words, and its 408 cache rows would otherwise be vehicle financing.
  2. **Floor-plan payoffs** (`floor_plan_per_vehicle`, the debit half): `PAYOFF`, a four-digit model year and `VIN` is `floor_plan_financing`, `matched_rule="floor_plan_payoff_descriptor"`, no entity.
  3. LOC wording (unchanged).
  4. Mortgage wording, now with **home-equity loans** (`mortgage_home_equity_loan`: `HOME EQUITY LOAN`, with no leading word boundary, so a run-together payee nickname matches). `HOME EQUITY LINE OF CREDIT` stays a line of credit because the LOC rule runs first (D9).
  5. Vehicle wording (unchanged; `vehicle_wording_confirmed`).
  6. **Student loans** (`student_loan_wording`): `personal_loan`, `matched_rule="student_loan_descriptor"`, no entity.
  7. The bank-name rule, whose loan wording now also reads **French `PRET` or `PRETS`** (`d5_french_loan_wording` (a)).
  8. The own-loan transfer (unchanged).
  9. **Another bank's unnamed loan** (`d5_outside_bank_unnamed_loan`): a generic commercial-loan or savings-bank originator with loan-payment wording. It is `bank_loan` with no entity, because the statement bank is not the lender.
  10. **The statement bank's own loan-payment wording** (`d5_own_loan_wording_en`): `AUTOMATIC LOAN PAYMENT`, `AUTOMATED LOAN PAYMENT`, `PAYMENT TO (COMMERCIAL) LOAN`. It is `bank_loan`, `matched_rule="own_bank_loan_payment"`, entity the statement bank.
  11. **Commercial-loan billing** (`d5_commercial_loan_billing`): an interest, principal or late-charge payment on a customer/obligation number. `bank_loan`, `matched_rule="commercial_loan_billing"`, entity the statement bank.
  12. **The statement bank's own French loan wording** (`d5_french_loan_wording` (b)): `VERSEMENT PRET`, `INTERETS SUR PRET`, `VERS/INT P A TERME`, `PMT PRET`, `PRET PMT`. `bank_loan`, `matched_rule="french_loan_wording"`, entity the statement bank. A bare `PRET` is never enough.
  13. The unnamed loan payment (`d5_unnamed_loan_payment`) comes here. It needs D11's payee words, so Task 9 adds it.
  14. Lease or rental (unchanged).
  15. The card rule, widened by four decisions:
      - `credit-card-ecs-payment` reads `CREDIT CARD ECS PAYMENT`;
      - `card-network-originator-payment` reads a `VISA` or `MASTERCARD` originator with a `PAYMENT` entry in the Bank of America `DES` or Chase `CO ENTRY DESCR` field;
      - `card-payment-to-card-account` reads `PAYMENT`, `PMT` or `PYMT` `TO CRD`, `CREDIT CARD`, `VSA`, `VISA`, `MASTERCARD` or `AMEX`;
      - `card-context-wording-paymnt-glued-sec` adds `PAYMNT`, and a payment word glued to its SEC label, to the card-issuer context wording.
  16. D4 (unchanged).

- [ ] **Step 1: Write the failing test** `tests/test_obligation_descriptors.py`:

```python
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.transaction_classifier import classify_transaction


@pytest.mark.parametrize(
    ("description", "state", "group"),
    [
        ("LINE OF CREDIT PAYMENT 0001", "line_of_credit", "lines_of_credit"),
        ("LOAN PMT LINE OF CREDIT", "line_of_credit", "lines_of_credit"),
        ("ACH DEBIT LOC PAYMENT", "line_of_credit", "lines_of_credit"),
        ("ACH DEBIT FABRICATED HOME MORTGAGE PMT", "mortgage", "mortgages"),
        ("VEHICLE LOAN PAYMENT 0001", "vehicle_financing", "vehicle_financing"),
        ("AUTO LN PMT 0001", "vehicle_financing", "vehicle_financing"),
        ("AUTO LEASE FABRICATED", "vehicle_financing", "vehicle_financing"),
        ("VEHICLE PAYMENT FABRICATED", "vehicle_financing", "vehicle_financing"),
        ("EQUIPMENT RENTAL FABRICATED", "lease_or_rental", "leases_rentals"),
        ("FABRICATED LEASING PMT", "lease_or_rental", "leases_rentals"),
        ("LEASE PAYMENT FABRICATED", "lease_or_rental", "leases_rentals"),
        ("CHECKCARD 0102 EQUIPMENT LEASE", "lease_or_rental", "leases_rentals"),
        ("CREDIT CARD PAYMENT FABRICATED", "credit_card_payment", "credit_cards"),
        # Owner decisions 2026-09-25 (fabricated rows).
        ("PAYOFF 2054 FABRICATED MODEL VIN 0001", "floor_plan_financing", "floor_plan"),
        ("WEB PMT HOME EQUITY LOAN 0001", "mortgage", "mortgages"),
        ("WEB PMT FABRICATEDHOMEEQUITYLOAN 0001", "mortgage", "mortgages"),
        ("STUDENT LOAN PAYMENT 0001", "personal_loan", "personal_loans"),
        ("ORIG CO NAME COMMERCIAL LOAN ORIG ID 0001", "bank_loan", "bank_loans"),
        ("SAVINGS BANK LOAN PMT 0001", "bank_loan", "bank_loans"),
        ("CREDIT CARD ECS PAYMENT 0001", "credit_card_payment", "credit_cards"),
        ("VISA DES PAYMENT ID 0001", "credit_card_payment", "credit_cards"),
        ("ORIG CO NAME MASTERCARD ORIG ID 0001 CO ENTRY DESCR PAYMENT SEC CCD", "credit_card_payment", "credit_cards"),
        ("ONLINE BANKING PMT TO CRD 0001", "credit_card_payment", "credit_cards"),
        ("PAYMENT TO VSA 0001", "credit_card_payment", "credit_cards"),
    ],
)
def test_an_unnamed_obligation_debit_takes_its_descriptor_group(description, state, group):
    record = classify_transaction(description, -400.0)
    assert record.classification == state
    assert record.flagged_group == group
    assert record.contributes_to_flagged_totals
    assert record.canonical_entity is None
    assert not record.contributes_to_withholding_rate
    assert not record.contributes_to_potential_lender_totals


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("Office rent payment", "rent"),
        ("PROPERTY RENTAL PAYMENT", "rent"),
        ("AUTO PAYMENT FABRICATED GYM", "other"),
        ("FABRICATED BANK PAYMENT 0001", "other"),
        ("FABRICATED PRET CAFE 0001", "other"),
    ],
)
def test_rent_autopay_and_a_bare_pret_are_not_flagged(description, state):
    """Landlord rent (D3), autopay wording and a bare PRET (also a restaurant's name) are no
    flagged obligation. An unnamed LOAN PAYMENT is the statement bank's loan since the owner
    decision of 2026-09-25 (D5); Task 9 pins it."""
    record = classify_transaction(description, -400.0)
    assert record.classification == state
    assert record.flagged_group is None


def test_a_transfer_between_the_holders_own_accounts_takes_no_step_8_rule():
    """Owner decision 2026-09-25: a fintech transfer to a sub-account the holder named with
    auto-loan words is no vehicle loan; an unnamed auto-loan bill payment still is."""
    moved = classify_transaction("TRANSFER TO CAR LOAN TRANSFER OUT", -400.0)
    assert (moved.classification, moved.flagged_group) == ("other", None)
    assert classify_transaction("AUTO LOAN BILL PAYMENT 0001", -400.0).classification == "vehicle_financing"


@pytest.mark.parametrize(
    ("description", "rule"),
    [
        ("PAYMENT - AUTOMATIC LOAN PMT 0001", "own_bank_loan_payment"),
        ("AUTOMATED LOAN PAYMENT 0001", "own_bank_loan_payment"),
        ("PAYMENT TO COMMERCIAL LOAN 0001", "own_bank_loan_payment"),
        ("INTEREST PAYMENT CUSTOMER 0001 OBLIGATION 0002", "commercial_loan_billing"),
        ("VERSEMENT PRET 0001", "french_loan_wording"),
        ("INT P A TERME 0001", "french_loan_wording"),
    ],
)
def test_the_statement_banks_own_loan_wording_is_its_bank_loan(description, rule):
    """Owner decisions 2026-09-25 (D5): the statement bank's own loan wording, no lender named."""
    record = classify_transaction(description, -900.0, bank="Fabricated Bank")
    assert (record.classification, record.canonical_entity, record.matched_rule) == (
        "bank_loan",
        "Fabricated Bank",
        rule,
    )
    assert record.flagged_group == "bank_loans"
    assert not record.review_required


def test_another_banks_unnamed_loan_names_no_bank():
    """Owner decision 2026-09-25 (D5): a generic savings-bank or commercial-loan originator is
    another bank's loan, so the statement bank is not named."""
    record = classify_transaction("SAVINGS BANK LOAN PMT 0001", -900.0, bank="Fabricated Bank")
    assert (record.classification, record.canonical_entity) == ("bank_loan", None)
    assert record.matched_rule == "outside_bank_loan_payment"


def test_a_review_tier_payee_with_lease_wording_is_a_lease_by_its_wording():
    """Owner decision 2026-09-25: Clover Equipment is in review, never counted. Every one of its
    aliases carries lease or rental wording, which step 8 reads before the potential tier."""
    # Moves here unchanged from the order table of tests/test_lender_insurance_classification.py.
    record = classify_transaction("Clover equipment rent/leases", -100.0)
    assert (record.classification, record.canonical_entity) == ("lease_or_rental", None)
    assert record.flagged_group == "leases_rentals"
    assert not record.contributes_to_withholding_rate
    assert not record.contributes_to_potential_lender_totals


@pytest.fixture
def fabricated_bank(monkeypatch):
    monkeypatch.setattr(
        transaction_classifier,
        "BANK_NAME_ALIASES",
        {"Fabricated Bank": ("FABRICATED BANK",)},
    )


def test_a_listed_bank_with_loan_wording_is_a_bank_loan(fabricated_bank):
    record = classify_transaction("FABRICATED BANK LOAN PYMT 0001", -900.0)
    assert (record.classification, record.canonical_entity, record.matched_alias) == (
        "bank_loan",
        "Fabricated Bank",
        "FABRICATED BANK",
    )
    assert record.match_method == "bank_name_alias"
    assert record.flagged_group == "bank_loans"
    assert classify_transaction("FABRICATED BANK PAYMENT 0001", -900.0).classification == "other"


def test_a_listed_bank_with_french_loan_wording_is_a_bank_loan(fabricated_bank):
    """Owner decision 2026-09-25: PRET is loan wording for the bank-name rule (D5)."""
    record = classify_transaction("FABRICATED BANK PRET 0001", -900.0)
    assert (record.classification, record.canonical_entity, record.match_method) == (
        "bank_loan",
        "Fabricated Bank",
        "bank_name_alias",
    )


def test_a_transfer_to_the_statement_banks_own_loan_is_a_bank_loan():
    named = classify_transaction("TRANSFER TO LOAN 0001", -900.0, bank="Fabricated Bank")
    unnamed = classify_transaction("TRANSFER TO LOAN 0001", -900.0)
    assert (named.classification, named.canonical_entity) == ("bank_loan", "Fabricated Bank")
    assert named.matched_rule == "own_bank_loan_transfer"
    assert (unnamed.classification, unnamed.canonical_entity) == ("bank_loan", None)


def test_the_owner_truist_example_is_a_bank_loan():
    record = classify_transaction("TRUIST LN 0001 PYMT", -900.0)
    assert record.classification == "bank_loan"
    assert record.flagged_group == "bank_loans"


def test_a_listed_card_issuer_needs_payment_wording(monkeypatch):
    monkeypatch.setattr(
        transaction_classifier,
        "CARD_ISSUER_CONTEXT_ALIASES",
        {"Fabricated Issuer": ("FABRICATED ISSUER",)},
    )
    paid = classify_transaction("FABRICATED ISSUER EPAYMENT 0001", -300.0)
    bare = classify_transaction("FABRICATED ISSUER 0001", -300.0)
    assert (paid.classification, paid.canonical_entity, paid.matched_alias) == (
        "credit_card_payment",
        "Fabricated Issuer",
        "FABRICATED ISSUER",
    )
    assert bare.classification == "other"


@pytest.mark.parametrize("description", ["FABRICATED ISSUER PAYMNT 0001", "FABRICATED ISSUER EPAYMENTSEC CCD"])
def test_card_issuer_wording_reads_paymnt_and_a_payment_word_glued_to_its_sec_label(monkeypatch, description):
    """Owner decision 2026-09-25: Synchrony prints PAYMNT, and Chase's field layout can glue
    the payment word to its SEC label."""
    monkeypatch.setattr(
        transaction_classifier,
        "CARD_ISSUER_CONTEXT_ALIASES",
        {"Fabricated Issuer": ("FABRICATED ISSUER",)},
    )
    record = classify_transaction(description, -300.0)
    assert (record.classification, record.canonical_entity) == ("credit_card_payment", "Fabricated Issuer")


def test_unnamed_equipment_financing_is_a_potential_lender_for_review():
    record = classify_transaction("ACH DEBIT EQUIPMENT FINANCE", -600.0)
    assert record.classification == "potential_lender"
    assert record.canonical_entity == "Unidentified lender obligation"
    assert record.match_method == "unnamed_equipment_financing"
    assert record.review_required
    assert record.contributes_to_potential_lender_totals
    assert not record.contributes_to_withholding_rate
    assert record.flagged_group is None


@pytest.mark.parametrize("description", ["LINE OF CREDIT ADVANCE", "CREDIT CARD PAYMENT RECEIVED", "LEASE DEPOSIT FABRICATED"])
def test_obligation_descriptors_never_apply_to_credits(description):
    record = classify_transaction(description, 500.0)
    assert record.classification == "other"
    assert record.flagged_group is None


@pytest.mark.parametrize("amount", [-400.0, 400.0])
@pytest.mark.parametrize(
    "description",
    [
        "LEASE PAYMENT FABRICATED",
        "EQUIPMENT RENT FABRICATED",
        "VEHICLE PAYMENT FABRICATED",
        "AUTO LEASE FABRICATED",
        "EQUIPMENT FINANCING FABRICATED",
    ],
)
def test_the_retired_lease_state_is_never_produced(description, amount):
    assert classify_transaction(description, amount).classification != "lease_or_equipment_financing"
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_obligation_descriptors.py -q -p no:cacheprovider`
Expected: FAIL. LOC and mortgage rows are `potential_lender`/`other`; lease and vehicle rows, and the Clover row, are `lease_or_equipment_financing`; the floor-plan payoff, home-equity, student-loan, D5-wording and widened card rows are `other` or `potential_lender`; the `fabricated_bank` fixture raises `AttributeError: ... has no attribute 'BANK_NAME_ALIASES'`, and the card-issuer monkeypatches raise the same for `CARD_ISSUER_CONTEXT_ALIASES`.

- [ ] **Step 3: Import the two step-8 tables.** In the `from .classification_registry import (` block, add the lines `    BANK_NAME_ALIASES,` (before `BANK_SPECIFIC_LENDER_ALIASES,`) and `    CARD_ISSUER_CONTEXT_ALIASES,` (after `BANK_SPECIFIC_LENDER_ALIASES,`).

- [ ] **Step 4: Name the unidentified entity once.** Directly after `CLASSIFICATION_VERSION = "5.0"`, add:

```python

#: The entity of an unknown obligation whose descriptor names no organisation (D11).
UNIDENTIFIED_LENDER_OBLIGATION = "Unidentified lender obligation"
```
In `classify_transaction`, replace `canonical_entity="Unidentified lender obligation",` with `canonical_entity=UNIDENTIFIED_LENDER_OBLIGATION,` and replace `canonical_entity=candidate or "Unidentified lender obligation",` with `canonical_entity=candidate or UNIDENTIFIED_LENDER_OBLIGATION,`.

- [ ] **Step 5: Rename the POS lease guard.** Replace the definition line `_LEASE_PATTERNS = (` with:

```python
#: POS precedence is unchanged (spec §4.3 step 5): a card row with lease,
#: equipment-financing or vehicle wording is not a POS purchase. These rows are
#: then decided by the step-8 descriptors.
_POS_LEASE_EXCLUSION_PATTERNS = (
```
and in the POS condition of `classify_transaction` replace `        and not _matches_any(text, _LEASE_PATTERNS)` with `        and not _matches_any(text, _POS_LEASE_EXCLUSION_PATTERNS)`.

- [ ] **Step 6: Add the step-8 patterns.** Directly after the `_CREDIT_CARD_PATTERNS = (...)` tuple, add:

```python
#: Owner decision 2026-09-25 (step8_own_account_transfer_guard): a fintech transfer
#: between the holder's own accounts takes no step-8 rule, whatever the holder
#: named the sub-account.
_OWN_ACCOUNT_TRANSFER_GUARD = re.compile(r"^TRANSFER (?:TO|FROM) .+ (?:ACCOUNT )?TRANSFER (?:OUT|IN)$")
#: Owner decision 2026-09-25 (floor_plan_per_vehicle): a per-vehicle floor-plan payoff.
_FLOOR_PLAN_PAYOFF_PATTERN = re.compile(r"^PAYOFF (?:19|20)\d\d .*\bVIN\b")
#: A home-equity loan is a second mortgage (owner decision 2026-09-25). It has no
#: leading word boundary, so a run-together payee nickname matches too.
_MORTGAGE_PATTERNS = (re.compile(r"\bMORTGAGES?\b"), re.compile(r"HOME ?EQUITY ?LOANS?\b"))
#: "AUTO PAYMENT" is a bank's autopay wording, not a car payment, so AUTO needs
#: loan, lease or finance wording while VEHICLE may carry PAYMENT.
_VEHICLE_FINANCING_PATTERNS = (
    re.compile(r"\b(?:AUTO|CAR) (?:LOAN|LOANS|LEASE|FINANCE|FINANCING)\b"),
    re.compile(r"\bVEHICLE (?:LOAN|LEASE|PAYMENT|PMT|PYMT|FINANCE|FINANCING)\b"),
)
#: Owner decision 2026-09-25 (student_loan_wording): an unnamed student-loan payee.
_STUDENT_LOAN_PATTERNS = (
    re.compile(r"\bSTUDENT ?LOANS?\b"),
    re.compile(r"\bSTDNT ?LOANS?\b"),
    re.compile(r"\bSTUDNT ?LOANS?\b"),
    re.compile(r"\bSTUDENT LN\b"),
)
#: D5 loan wording for the bank-name rule. French PRET is loan wording too (owner
#: decision 2026-09-25).
_LOAN_WORD_PATTERNS = (re.compile(r"\bLOANS?\b"), re.compile(r"\bPRETS?\b"))
#: D5: a transfer to the statement bank's own loan account.
_OWN_LOAN_TRANSFER_PATTERNS = (
    re.compile(r"\b(?:TRANSFER|TFR) TO (?:MY |YOUR )?LOAN\b"),
    re.compile(r"\bLOAN (?:TRANSFER|TFR)\b"),
)
#: D5, owner decisions 2026-09-25. Another bank's loan whose originator is only a
#: generic bank or loan name: the statement bank is not the lender.
_OUTSIDE_BANK_LOAN_PATTERNS = (
    re.compile(r"\bORIG CO NAME COMMERCIAL LOAN\b"),
    re.compile(r"\bSAVINGS BANK LOAN (?:PAYMENT|PMT|PYMT)\b"),
)
#: The statement bank's own loan-payment wording, commercial-loan billing and
#: French loan wording, with no lender named. A bare PRET is never enough: it is
#: also a restaurant's name and a named funder's term-loan word.
_OWN_LOAN_PAYMENT_PATTERNS = (
    re.compile(r"\bAUTOMATIC LOAN (?:PAYMENT|PMT|PYMT|PAY)\b"),
    re.compile(r"\bAUTOMATED LOAN PAYMENT\b"),
    re.compile(r"\bPAYMENT TO (?:CMML |COMMERCIAL )?LOAN\b"),
)
_COMMERCIAL_LOAN_BILLING_PATTERNS = (
    re.compile(r"\b(?:INTEREST|PRINCIPAL|LATE CHARGE) PAYMENT CUSTOMER \d+ OBLIGATION \d+"),
)
_FRENCH_OWN_LOAN_PATTERNS = (
    re.compile(r"\bVERSEMENT PRET\b"),
    re.compile(r"\bINTERETS? SUR PRET\b"),
    re.compile(r"\b(?:VERS|INT) P A TERME\b"),
    re.compile(r"\bPMT PRET\b"),
    re.compile(r"\bPRET PMT\b"),
)
#: D3: PROPERTY RENTAL is landlord rent, never a flagged rental.
_LEASE_RENTAL_PATTERNS = (
    re.compile(r"\bLEAS(?:E|ES|ED|ING)\b"),
    re.compile(r"(?<!PROPERTY )\bRENTALS?\b"),
    re.compile(r"\bEQUIPMENT (?:RENT|PAYMENT)\b"),
)
#: A listed card issuer (CARD_ISSUER_CONTEXT_ALIASES) counts only with card or payment
#: wording. Owner decision 2026-09-25: Synchrony's PAYMNT, and a payment word glued to
#: the SEC label in Chase's field layout, are payment wording too.
_CARD_PAYMENT_CONTEXT_PATTERNS = (
    re.compile(r"\b(?:CREDIT CARD|CRCARD|CRD|CARD|CARDMEMBER)\b"),
    re.compile(
        r"\b(?:AUTOPAY|AUTO PAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT|PAYMNT)\b"
        r"|\b(?:AUTOPAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT|PAYMNT)SEC\b"
    ),
)
#: D4: equipment financing with no named company.
_EQUIPMENT_FINANCING_PATTERNS = (re.compile(r"\bEQUIPMENT (?:FINANCING|FINANCE)\b"),)
```

- [ ] **Step 7: Widen the card-payment patterns** (owner decisions 2026-09-25: `credit-card-ecs-payment`, `card-network-originator-payment`, `card-payment-to-card-account`). Replace the whole `_CREDIT_CARD_PATTERNS = (...)` tuple (from `_CREDIT_CARD_PATTERNS = (` through its closing `)`) with:

```python
_CREDIT_CARD_PATTERNS = (
    # One bank prints its ECS channel word between CREDIT CARD and PAYMENT.
    re.compile(r"\bCREDIT CARD (?:ECS )?(?:PAYMENT|PMT|PYMT)\b"),
    re.compile(r"\bCARDMEMBER SERVICES?\b"),
    re.compile(r"\b(?:VISA|MASTER ?CARD|AMEX|AMERICAN EXPRESS) (?:PAYMENT|PMT|PYMT|EPAYMENT)\b"),
    # The card network itself as the ACH originator, with a PAYMENT entry in its own
    # field (Bank of America's DES field; Chase's CO ENTRY DESCR field).
    re.compile(r"\b(?:VISA|MASTER ?CARD) DES (?:PAYMENT|PMT|PYMT|EPAYMENT)\b"),
    re.compile(r"\bORIG CO NAME (?:VISA|MASTER ?CARD) ORIG ID\b.*?\bCO ENTRY DESCR (?:PAYMENT|PMT|PYMT|EPAYMENT)\b"),
    re.compile(r"\bATB MASTER ?CARD\b"),
    re.compile(r"\bCAPITAL ONE\b.*\b(?:ONLINE PMT|CARD PAYMENT|PAYMENT)\b"),
    re.compile(r"\bCAPITAL ?ON ?TAP\b"),
    # A payment to a card account named only by its type.
    re.compile(r"\b(?:PAYMENT|PMT|PYMT) TO (?:CRD|CREDIT CARD|VSA|VISA|MASTER ?CARD|AMEX|AMERICAN EXPRESS)\b"),
)
```

- [ ] **Step 8: Add the step-8 rule.** Directly after the end of `_descriptor_proceeds_credit_record` (Task 4), add:

```python
def _obligation_fields(
    state: str,
    rule: str,
    reason: str,
    *,
    entity: str | None = None,
    alias: str | None = None,
    match_method: str = "obligation_descriptor",
) -> dict[str, object]:
    return {
        "classification": state,
        "canonical_entity": entity,
        "match_method": match_method,
        "matched_alias": alias,
        "matched_rule": rule,
        "confidence_score": 0.95,
        "reason": f"{reason} It is a flagged obligation and never enters lender math.",
    }


def _descriptor_obligation(text: str, bank: str | None) -> dict[str, object] | None:
    """Spec §4.3 step 8: obligation descriptors on a debit no known payee claimed.

    The rules run in the spec's order, with the rules of the owner decisions of
    2026-09-25 where their own placement puts them, and the first match wins.
    Returns the `_build_record` keyword arguments, or None when no descriptor
    rule matches.
    """
    # A transfer between the holder's own accounts takes no step-8 rule.
    if _OWN_ACCOUNT_TRANSFER_GUARD.search(text):
        return None
    if _FLOOR_PLAN_PAYOFF_PATTERN.search(text):
        return _obligation_fields(
            "floor_plan_financing",
            "floor_plan_payoff_descriptor",
            "The descriptor is a per-vehicle floor-plan payoff.",
        )
    if _matches_any(text, _LINE_OF_CREDIT_PATTERNS):
        return _obligation_fields(
            "line_of_credit", "line_of_credit_descriptor", "The descriptor says LOC or line of credit."
        )
    if _matches_any(text, _MORTGAGE_PATTERNS):
        return _obligation_fields(
            "mortgage", "mortgage_descriptor", "The descriptor identifies a mortgage or home-equity loan payment."
        )
    if _matches_any(text, _VEHICLE_FINANCING_PATTERNS):
        return _obligation_fields(
            "vehicle_financing",
            "vehicle_financing_descriptor",
            "The descriptor identifies a vehicle loan, lease or payment.",
        )
    if _matches_any(text, _STUDENT_LOAN_PATTERNS):
        return _obligation_fields(
            "personal_loan", "student_loan_descriptor", "The descriptor identifies a student-loan payment."
        )
    bank_match = registry_match(text, BANK_NAME_ALIASES)
    if bank_match is not None and _matches_any(text, _LOAN_WORD_PATTERNS):
        entity, alias = bank_match
        return _obligation_fields(
            "bank_loan",
            "bank_name_loan_payment",
            f"A listed bank ('{alias}') with loan wording is a bank loan (D5).",
            entity=entity,
            alias=alias,
            match_method="bank_name_alias",
        )
    if _matches_any(text, _OWN_LOAN_TRANSFER_PATTERNS):
        return _obligation_fields(
            "bank_loan",
            "own_bank_loan_transfer",
            "The descriptor is a transfer to the statement bank's own loan (D5).",
            entity=bank or None,
        )
    if _matches_any(text, _OUTSIDE_BANK_LOAN_PATTERNS):
        return _obligation_fields(
            "bank_loan",
            "outside_bank_loan_payment",
            "The descriptor is another bank's loan payment, with no lender named (D5).",
        )
    if _matches_any(text, _OWN_LOAN_PAYMENT_PATTERNS):
        return _obligation_fields(
            "bank_loan",
            "own_bank_loan_payment",
            "The descriptor is the statement bank's own loan-payment wording (D5).",
            entity=bank or None,
        )
    if _matches_any(text, _COMMERCIAL_LOAN_BILLING_PATTERNS):
        return _obligation_fields(
            "bank_loan",
            "commercial_loan_billing",
            "The descriptor is the statement bank's commercial-loan billing (D5).",
            entity=bank or None,
        )
    if _matches_any(text, _FRENCH_OWN_LOAN_PATTERNS):
        return _obligation_fields(
            "bank_loan",
            "french_loan_wording",
            "The descriptor is the statement bank's own French loan wording (D5).",
            entity=bank or None,
        )
    if _matches_any(text, _LEASE_RENTAL_PATTERNS):
        return _obligation_fields(
            "lease_or_rental",
            "lease_or_rental_descriptor",
            "The descriptor identifies a lease, rental or lease-to-own payment.",
        )
    issuer = registry_match(text, CARD_ISSUER_CONTEXT_ALIASES)
    if _matches_any(text, _CREDIT_CARD_PATTERNS) or (
        issuer is not None and _matches_any(text, _CARD_PAYMENT_CONTEXT_PATTERNS)
    ):
        entity, alias = issuer if issuer is not None else (None, None)
        return _obligation_fields(
            "credit_card_payment",
            "credit_card_payment",
            "The descriptor identifies a credit-card account payment.",
            entity=entity,
            alias=alias,
        )
    if _matches_any(text, _EQUIPMENT_FINANCING_PATTERNS):
        named = _canonical_unknown_entity(_EQUIPMENT_FINANCING_PATTERNS[0].sub(" ", text))
        return {
            "classification": "potential_lender",
            "canonical_entity": named or UNIDENTIFIED_LENDER_OBLIGATION,
            "match_method": "unnamed_equipment_financing",
            "matched_rule": "equipment_financing_without_verified_entity",
            "confidence_score": 0.72,
            "reason": (
                "Equipment financing with no named, verified company is a potential "
                "lender; it requires review (D4)."
            ),
            "review_required": True,
        }
    return None
```

- [ ] **Step 9: Put step 8 in the rule order.** In `classify_transaction`, replace the Task 5 block

```python
    if _matches_any(text, _LEASE_PATTERNS):
        return _build_record(
            **common,
            classification="lease_or_equipment_financing",
            match_method="strong_non_lender_exclusion",
            matched_rule="lease_or_equipment_financing",
            confidence_score=0.95,
            reason="The descriptor identifies a lease, vehicle lease, or equipment-financing obligation.",
        )
```
with
```python
    # Step 8: obligation descriptors, debits only (D1: these never apply to credits).
    if amount < 0:
        obligation = _descriptor_obligation(text, bank)
        if obligation is not None:
            return _build_record(**common, **obligation)
```
and delete the card block that follows the rent block:
```python
    if _matches_any(text, _CREDIT_CARD_PATTERNS):
        return _build_record(
            **common,
            classification="credit_card_payment",
            match_method="strong_non_lender_exclusion",
            matched_rule="credit_card_payment",
            confidence_score=0.97,
            reason="The descriptor identifies a credit-card account payment.",
        )
```

- [ ] **Step 10: Settle the automatic loan payment** (pin-ledger row 21, owner decision 2026-09-25 `d5_own_loan_wording_en`). In `tests/test_lender_insurance_classification.py::test_recurring_counterparty_normalization_removes_ids_not_business_name`, replace the block (`:199-204`)

```python
    unidentified = classify_transaction("PAYMENT - AUTOMATIC LOAN PYMT W/D", -370.17)
    assert unidentified.classification == "potential_lender"
    assert unidentified.canonical_entity == "Unidentified lender obligation"
    assert unidentified.review_required
    assert unidentified.contributes_to_potential_lender_count
    assert not unidentified.contributes_to_lender_count
```
with
```python
    # The statement bank's own loan-payment wording is its bank loan (D5, owner decision 2026-09-25).
    own_loan = classify_transaction("PAYMENT - AUTOMATIC LOAN PYMT W/D", -370.17)
    assert (own_loan.classification, own_loan.canonical_entity) == ("bank_loan", None)
    assert own_loan.matched_rule == "own_bank_loan_payment"
    assert own_loan.flagged_group == "bank_loans"
    assert not own_loan.review_required
    assert not own_loan.contributes_to_potential_lender_count
    assert not own_loan.contributes_to_lender_count
```

- [ ] **Step 11: Settle navigant, only in the bank-name variant** (pin-ledger row 15). If Task 0 printed `navigant: open loan debits naming a listed bank = N` with N of 1 or more (the revised ledger reads 2), the D5 bank-name rule now makes navigant's loan row a bank loan, so the navigant `"lenders"` entry of `EXPECTED` in `tests/test_new_statement_corpus.py` (`:153`) must read `"lenders": (0, 0.00, 0, 0.00),` until Task 10. Otherwise leave it at `(0, 0.00, 1, 1191.00)`. navigant's three Comenity debits become `credit_card_payment` here; no pinned figure counts them.

- [ ] **Step 12: Run the tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_obligation_descriptors.py tests/test_known_payee_classification.py tests/test_flag_group_states.py tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_r1_hardcodes.py tests/test_new_statement_corpus.py tests/test_no_statement_hardcodes.py -q -p no:cacheprovider`
Expected: PASS, except the known pre-existing `test_no_literal_account_numbers_in_ocr`.

- [ ] **Step 13: Commit.**

```
git add analysis/transaction_classifier.py tests/test_obligation_descriptors.py tests/test_lender_insurance_classification.py
git commit -m "classifier: obligation descriptors for unnamed payees (D4, D5)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```
If Step 11 changed the navigant entry, also `git add tests/test_new_statement_corpus.py` before committing.

---

### Task 9: Unknown-payee naming and servicers (D11, D10)

**Files:**
- Modify: `analysis/transaction_classifier.py` (entity block `_ENTITY_NOISE` through `_canonical_unknown_entity`, `:767-797`; new `_SERVICER_COLLECTOR_PATTERNS`, `_BANK_TEMPLATE_WORDS` and `_UNNAMED_LOAN_PAYMENT_PATTERNS` after `_DIRECT_DEBIT_LOAN_PATTERNS` `:372-375`; one branch in `_descriptor_obligation` (Task 8) before its lease/rental rule; new branch in `classify_transaction` before the direct-debit-loan rule)
- Test: `tests/test_unknown_payee_naming.py`

**Interfaces:**
- Consumes: `UNIDENTIFIED_LENDER_OBLIGATION`, `_descriptor_obligation` and `_obligation_fields` (Task 8).
- Produces: `_unknown_payee_tokens(text: str) -> tuple[str, ...]`, `_unknown_payee_name(tokens: Sequence[str]) -> str | None`, `_canonical_unknown_entity(text: str) -> str | None` (same name, D11 behavior); D10 records with `match_method="unknown_servicer_or_collector"`, now also for `MCA SERVICING` (owner decision 2026-09-25, `d10_mca_servicing`; the two words stay out of every alias table).
- Produces the unnamed loan payment (owner decision 2026-09-25, `d5_unnamed_loan_payment`, spec D5 widened). A debit with loan-payment wording (`LOAN PAYMENT`, `LOAN PMT`, `LOAN PYMT`, `LOAN REPAYMENT`; normalization reads `LN` as `LOAN`) that prints no payee is the statement bank's own loan:
  - `bank_loan`, `matched_rule="unnamed_loan_payment"`, entity the statement bank or `None`;
  - it is the last D5 rule of step 8, after the bank-name rule, the own-loan transfer and the D5 wording rules of Task 8;
  - "prints no payee" means every D11 payee word is a bank-template word (`NO`, `BR`, `AUTOMATED`, `COMPTE`, `DIVERS`), or there is none;
  - a loan payment that prints a lender, a servicer, a person or another bank keeps the potential-lender rules.
  - It needs D11's payee words, so it lands here rather than in Task 8. On the cache it takes 842 debits that are `potential_lender` today.

- [ ] **Step 1: Write the failing test** `tests/test_unknown_payee_naming.py`:

```python
from __future__ import annotations

import pytest

from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import txn

UNIDENTIFIED = "Unidentified lender obligation"


@pytest.mark.parametrize(
    ("description", "entity"),
    [
        ("WEB PMT NORTHSTAR FINANCE INDN:PAT EXAMPLE CO ID:0000 CCD", "Northstar Finance"),
        (
            "ORIG CO NAME:NORTHSTAR FINANCE ORIG ID:0000 DESC DATE:0101 CO ENTRY DESCR:PAYMENT "
            "SEC:CCD TRACE#:0000 EED:0101 IND ID:0000 IND NAME:PAT EXAMPLE",
            "Northstar Finance",
        ),
        ("NORTHSTAR FINANCE DES:PAYMENT ID:XXXX0000 INDN:PAT EXAMPLE CO ID:0000 CCD", "Northstar Finance"),
        ("NORTHSTAR FINANCE PAYMENT 0101 0000000 PAT EXAMPLE", "Northstar Finance"),
        ("ACH DEBIT FABRICATED FUNDING LLC", "Fabricated Funding LLC"),
        ("ACH PMT PAT EXAMPLE FAMILY LOAN", UNIDENTIFIED),
        ("ADVANCE PAT EXAMPLE PMT", UNIDENTIFIED),
    ],
)
def test_a_financing_keyword_row_is_named_from_organisation_words_only(description, entity):
    record = classify_transaction(description, -90.0)
    assert record.classification == "other"
    assert record.match_method == "financing_keyword_review"
    assert record.canonical_entity == entity


@pytest.mark.parametrize(
    "description",
    [
        "LOAN PAYMENT PAT EXAMPLE",
        "WITHDRAWAL ADVANCE PAYMENT PAT EXAMPLE 0000",
        "DEBIT MEMO FUNDING PMT PAT EXAMPLE",
    ],
)
def test_a_repayment_to_an_unknown_person_is_never_named_after_them(description):
    record = classify_transaction(description, -90.0)
    assert record.classification == "potential_lender"
    assert record.canonical_entity == UNIDENTIFIED


def test_generic_financing_words_alone_name_no_payee():
    record = classify_transaction("ACH Debit Funder 0102", -450.0)
    assert record.match_method == "financing_keyword_review"
    assert record.canonical_entity is None


def test_a_financing_payee_keeps_one_name_across_dated_descriptors():
    statement = Statement(
        transactions=[
            txn(f"2054-01-{day:02d}", f"NORTHSTAR FINANCE PAYMENT JAN {day}", -90.0)
            for day in (5, 6, 7, 8, 9)
        ]
    )
    records = classify_statement_transactions(statement)
    assert {record.canonical_entity for record in records} == {"Northstar Finance"}
    assert {record.classification for record in records} == {"potential_lender"}


@pytest.mark.parametrize(
    ("description", "entity"),
    [
        ("ACH DEBIT FABRICATED CAPITAL EQUIPMENT FINANCE", "Fabricated Capital"),
        ("ACH DEBIT FABRICATED EQUIPMENT FINANCE", UNIDENTIFIED),
    ],
)
def test_unnamed_equipment_financing_keeps_only_an_organisation_name(description, entity):
    record = classify_transaction(description, -600.0)
    assert record.match_method == "unnamed_equipment_financing"
    assert record.canonical_entity == entity


@pytest.mark.parametrize(
    ("description", "entity"),
    [
        ("ACH DEBIT FABRICATED LOAN SERVICING", UNIDENTIFIED),
        ("ACH DEBIT FABRICATED SERVICER LLC", "Fabricated Servicer LLC"),
        ("FABRICATED DEBT COLLECTORS INC", "Fabricated Debt Collectors Inc"),
        # Owner decision 2026-09-25: an MCA servicing company whose funder is not named.
        ("ACH DEBIT MCA SERVICING 0001", UNIDENTIFIED),
    ],
)
def test_an_unknown_servicer_or_collector_is_a_potential_lender(description, entity):
    record = classify_transaction(description, -250.0)
    assert record.classification == "potential_lender"
    assert record.match_method == "unknown_servicer_or_collector"
    assert record.canonical_entity == entity
    assert record.review_required
    assert not record.contributes_to_withholding_rate


@pytest.mark.parametrize("description", ["LOAN PAYMENT", "LOAN PAYMENT BR 0001", "COMPTE DIVERS LOAN PAYMENT 0001"])
def test_a_loan_payment_that_names_no_payee_is_the_statement_banks_loan(description):
    """Owner decision 2026-09-25 (D5): a LOAN PAYMENT with no lender printed is the statement
    bank's own loan, not a potential lender."""
    named = classify_transaction(description, -500.0, bank="Fabricated Bank")
    unnamed = classify_transaction(description, -500.0)
    assert (named.classification, named.canonical_entity, named.matched_rule) == (
        "bank_loan",
        "Fabricated Bank",
        "unnamed_loan_payment",
    )
    assert (unnamed.classification, unnamed.canonical_entity) == ("bank_loan", None)
    assert named.flagged_group == "bank_loans"
    assert not named.review_required
    assert not named.contributes_to_potential_lender_totals


def test_a_loan_payment_that_prints_a_payee_keeps_the_potential_rules():
    # LOAN PAYMENT PAT EXAMPLE (a person) stays potential too: see the repayment test above.
    assert classify_transaction("LOAN PAYMENT NORTHSTAR FINANCE 0001", -500.0).classification == "potential_lender"
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_unknown_payee_naming.py -q -p no:cacheprovider`
Expected: FAIL. Today's naming keeps ACH field segments and person names (for example `"Northstar Finance Indn Pat Example Id"`, `"Pat Example"`), the dated rows split into five entities, and the servicer rows (the MCA SERVICING row included) are `other` or `unidentified_loan_obligation`. The unnamed loan payments are still `potential_lender`. `test_a_loan_payment_that_prints_a_payee_keeps_the_potential_rules` passes: it guards the rule's edge.

- [ ] **Step 3: Replace the entity block.** Replace everything from `_ENTITY_NOISE = {` through the end of `_canonical_unknown_entity` (its `return " ".join(rendered)` line) with:

```python
#: Channel and payment words that never name a payee (D11).
_ENTITY_NOISE = {
    "ACH", "EFT", "DEBIT", "DIRECT", "DEB", "EXTERNAL", "WITHDRAWAL", "ELECTRONIC",
    "PREAUTHORIZED", "PREAUTH", "AUTOMATIC", "AUTO", "ORIG", "ORIGINATOR", "NAME",
    "DESCR", "DESCRIPTION", "ENTRY", "DETAIL", "PAYMENT", "PAYMENTS", "PAY", "PMT",
    "PYMT", "REPAYMENT", "REMITTANCE", "PAD", "BUSINESS", "ONLINE", "WEB", "CCD", "PPD",
    "LOAN", "MCA", "TO", "FROM", "FOR", "TFR", "XFER", "TRANSFER", "MISC",
}
#: Financing words that describe the payment, not the payee, when they lead the name.
_GENERIC_ENTITY_WORDS = {"FINANCE", "FINANCING", "FUNDING", "CAPITAL", "FUNDER", "ADVANCE"}
#: D11: a name is published only when one of these organisation cues survives.
#: The last eight are the registry-style company tokens (legal-form suffixes).
_ORGANISATION_CUES = {
    "LLC", "INC", "CORP", "CO", "FUNDING", "CAPITAL", "FINANCIAL", "FINANCE", "BANK",
    "CREDIT", "LENDING", "ADVANCE", "GROUP", "HOLDINGS", "SERVICES",
    "CORPORATION", "COMPANY", "INCORPORATED", "LTD", "LIMITED", "LP", "LLP", "PLLC",
}
_ENTITY_MONTHS = {
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "SEPT", "OCT", "NOV",
    "DEC", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
    "OCTOBER", "NOVEMBER", "DECEMBER",
}
_ENTITY_ACRONYMS = {"ACH", "BDC", "CMCA", "EFT", "LLC", "LLP", "LP", "MCA", "PLLC", "SBA", "SNAP"}
#: Labels that introduce the originator's name: the label goes, the name stays.
_ENTITY_NAME_LABELS = re.compile(r"\b(?:ORIG CO NAME|ORIGINATOR NAME|COMPANY NAME|CO NAME)\b")
#: D11: ACH field segments. Everything from the first one on is dropped, so a
#: name is never built from ID, INDN, IND NAME, CO ID, TRACE or similar fields.
_ACH_FIELD_SEGMENT = re.compile(
    r"\b(?:DES|DESC|DESCR|ORIG ID|CO ID|IND ID|IND NAME|INDN|IND|ID|TRACE|SEC|EED|TRN|"
    r"CONF|REF|MEMO|CUST|TYPE)\b"
)
_MASKED_TOKEN = re.compile(r"X{2,}[A-Z0-9]*")
_MAX_ENTITY_TOKENS = 4


def _is_reference_token(token: str) -> bool:
    return (
        any(character.isdigit() for character in token)
        or _MASKED_TOKEN.fullmatch(token) is not None
        or token in _ENTITY_MONTHS
    )


def _unknown_payee_tokens(text: str) -> tuple[str, ...]:
    """D11: the payee words of an unknown counterparty, at most four.

    Removes originator-name labels, cuts at the first ACH field segment, drops
    channel words, single letters and leading financing words, and stops at the
    first reference token (digits, a masked number or a month) once a name has
    started, so a person's name printed after the references never joins it.
    """
    text = _ENTITY_NAME_LABELS.sub(" ", text)
    segment = _ACH_FIELD_SEGMENT.search(text)
    if segment is not None:
        text = text[: segment.start()]
    tokens: list[str] = []
    for token in text.split():
        if token in _ENTITY_NOISE or len(token) == 1:
            continue
        if _is_reference_token(token):
            if tokens:
                break
            continue
        if not tokens and token in _GENERIC_ENTITY_WORDS:
            continue
        tokens.append(token)
        if len(tokens) == _MAX_ENTITY_TOKENS:
            break
    return tuple(tokens)


def _unknown_payee_name(tokens: Sequence[str]) -> str | None:
    """D11: the published name, the unidentified label, or None when no payee is named."""
    if not tokens:
        return None
    if not any(token in _ORGANISATION_CUES for token in tokens):
        return UNIDENTIFIED_LENDER_OBLIGATION
    return " ".join(token if token in _ENTITY_ACRONYMS else token.title() for token in tokens)


def _canonical_unknown_entity(text: str) -> str | None:
    return _unknown_payee_name(_unknown_payee_tokens(text))
```

- [ ] **Step 4: Add the D10 patterns.** Directly after the `_DIRECT_DEBIT_LOAN_PATTERNS = (...)` tuple, add:

```python
#: D10: a loan servicer or debt collector whose funder is not in a registry.
#: (A servicer whose funder is known is an alias of that funder in the registry, via the C10 ledger.)
#: MCA SERVICING: owner decision 2026-09-25 (the words stay out of every alias table).
_SERVICER_COLLECTOR_PATTERNS = (
    re.compile(r"\bSERVICER\b"),
    re.compile(r"\bLOAN SERVICING\b"),
    re.compile(r"\bMCA SERVICING\b"),
    re.compile(r"\bDEBT (?:COLLECTION|COLLECTIONS|COLLECTOR|COLLECTORS)\b"),
    re.compile(r"\bCOLLECTION AGENCY\b"),
)
#: D5, owner decision 2026-09-25 (d5_unnamed_loan_payment): loan-payment wording
#: (normalization already reads LN as LOAN and PAYMT as PAYMENT) ...
_UNNAMED_LOAN_PAYMENT_PATTERNS = (re.compile(r"\bLOANS? (?:PAYMENT|PAYMENTS|PYMT|PMT|REPAYMENT)\b"),)
#: ... on a row whose D11 payee words are only a bank's template words, or none:
#: the payment names no lender, so it is the statement bank's own loan.
_BANK_TEMPLATE_WORDS = frozenset({"NO", "BR", "AUTOMATED", "COMPTE", "DIVERS"})
```

- [ ] **Step 5: Add the D10 rule.** In `classify_transaction`, directly before `    if amount < 0 and _matches_any(text, _DIRECT_DEBIT_LOAN_PATTERNS):`, insert:

```python
    if amount < 0 and _matches_any(text, _SERVICER_COLLECTOR_PATTERNS):
        return _build_record(
            **common,
            classification="potential_lender",
            canonical_entity=_canonical_unknown_entity(text) or UNIDENTIFIED_LENDER_OBLIGATION,
            match_method="unknown_servicer_or_collector",
            matched_rule="servicer_or_collector_without_verified_funder",
            confidence_score=0.74,
            reason=(
                "The payee is a loan servicer or debt collector whose funder is not "
                "identified; it is potential only and requires review (D10)."
            ),
            review_required=True,
        )

```

- [ ] **Step 6: Add the unnamed loan payment to step 8** (owner decision 2026-09-25, D5). In `_descriptor_obligation` (Task 8), directly before the line `    if _matches_any(text, _LEASE_RENTAL_PATTERNS):`, insert:

```python
    # D5 (owner decision 2026-09-25): a loan payment that prints no payee is the
    # statement bank's own loan, not a potential lender. The last D5 rule.
    if _matches_any(text, _UNNAMED_LOAN_PAYMENT_PATTERNS) and (
        set(_unknown_payee_tokens(text)) <= _BANK_TEMPLATE_WORDS
    ):
        return _obligation_fields(
            "bank_loan",
            "unnamed_loan_payment",
            "The descriptor is a loan payment that names no lender: the statement bank's own loan (D5).",
            entity=bank or None,
        )
```

- [ ] **Step 7: Run the tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_unknown_payee_naming.py tests/test_obligation_descriptors.py tests/test_known_payee_classification.py tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_new_statement_corpus.py tests/test_no_statement_hardcodes.py -q -p no:cacheprovider`
Expected: PASS, except the known pre-existing `test_no_literal_account_numbers_in_ocr`. navigant's two loan-payment rows are claimed first by the bank-name rule (Task 8), so no pinned figure moves.

- [ ] **Step 8: Commit.**

```
git add analysis/transaction_classifier.py tests/test_unknown_payee_naming.py
git commit -m "classifier: unknown payees are never named from ACH fields or persons (D10, D11); unnamed loan payments are bank loans (D5)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 10: Fixed daily or weekly debits of unknown payees (D6)

**Files:**
- Modify: `analysis/transaction_classifier.py` (new `_TRANSFER_WORD_PATTERNS` and `_promotion_cadence` before `classify_statement_transactions`; the recurrence block of `classify_statement_transactions`, `:1499-1535`)
- Modify: `analysis/detect.py` (`find_recurring_debits` `:168-183`)
- Modify: `tests/test_new_statement_corpus.py:153`
- Test: `tests/test_recurring_fixed_debits.py`
- No ATB November edit: Task 5 already pinned its potential lines, and D6 finds nothing left to promote there (Step 7).

**Interfaces:**
- Consumes: `_unknown_payee_tokens`, `_unknown_payee_name` (Task 9); `classify_cadence` (unchanged).
- Produces: `potential_lender` records with `match_method="recurring_fixed_debit"`, `matched_rule=f"{cadence}_fixed_debit_{average_gap}_day_average"`, review required, the three potential flags on. The financing-keyword promotion (`recurring_financing_counterparty`) now groups by payee words. `detect.find_recurring_debits` (unchanged signature) now also lists the D6 rows, so `detection.recurring_debits`, the `analyze.py` "Recurring fixed debits" lines and the `batch.py` `recurring_debit_groups` count include them.

- [ ] **Step 1: Write the failing test** `tests/test_recurring_fixed_debits.py`:

```python
from __future__ import annotations

import pytest

from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions
from tests.flag_group_fixtures import txn

UNIDENTIFIED = "Unidentified lender obligation"


def _statement(rows) -> Statement:
    return Statement(transactions=[txn(day, description, amount) for day, description, amount in rows])


def test_fixed_weekly_debits_of_an_unknown_payee_become_a_potential_lender():
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", f"ACH DEBIT FABRICATED WIDGETS LLC {day:04d}", -400.0) for day in (2, 9, 16, 23)]
    ))
    assert {record.classification for record in records} == {"potential_lender"}
    assert {record.match_method for record in records} == {"recurring_fixed_debit"}
    # classify_cadence (unchanged) renders an integral mean gap without a decimal.
    assert {record.matched_rule for record in records} == {"weekly_fixed_debit_7_day_average"}
    assert {record.canonical_entity for record in records} == {"Fabricated Widgets LLC"}
    assert all(record.review_required for record in records)
    assert all(
        record.contributes_to_potential_lender_totals and record.contributes_to_potential_withholding_exposure
        for record in records
    )
    assert not any(record.contributes_to_withholding_rate for record in records)


def test_fixed_daily_debits_without_an_organisation_name_stay_unidentified():
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", "ACH DEBIT PAT EXAMPLE", -150.0) for day in (5, 6, 7, 8, 9)]
    ))
    assert {(record.classification, record.canonical_entity) for record in records} == {
        ("potential_lender", UNIDENTIFIED)
    }


NOT_PROMOTED = {
    "two rows": [
        ("2054-01-02", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0),
        ("2054-01-09", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0),
    ],
    "monthly": [(day, "ACH DEBIT FABRICATED WIDGETS LLC", -400.0) for day in ("2054-01-05", "2054-02-05", "2054-03-05")],
    "different amounts": [
        (f"2054-01-{day:02d}", "ACH DEBIT FABRICATED WIDGETS LLC", amount)
        for day, amount in ((2, -100.0), (9, -110.0), (16, -120.0))
    ],
    "transfer wording": [(f"2054-01-{day:02d}", "TRANSFER TO PAT EXAMPLE", -300.0) for day in (2, 9, 16)],
    "channel words only": [(f"2054-01-{day:02d}", f"AB{day:02d} TFR TO 0000000", -300.0) for day in (2, 9, 16)],
    "no payee words": [(f"2054-01-{day:02d}", f"ACH DEBIT {day:04d}", -300.0) for day in (2, 9, 16)],
    "credits": [(f"2054-01-{day:02d}", "FABRICATED WIDGETS LLC", 400.0) for day in (2, 9, 16)],
}


@pytest.mark.parametrize("rows", list(NOT_PROMOTED.values()), ids=list(NOT_PROMOTED))
def test_recurrence_without_a_fixed_daily_or_weekly_unknown_payee_is_not_promoted(rows):
    records = classify_statement_transactions(_statement(rows))
    assert not any(record.classification == "potential_lender" for record in records)


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("CARD PURCHASE FABRICATED STORE", "pos"),
        ("ONLINE TRANSFER TO SAVINGS", "transfer"),
        ("MONTHLY SERVICE FEE", "fee"),
        ("ADP PAYROLL FABRICATED", "payroll"),
        ("IRS TAX PAYMENT FABRICATED", "tax"),
        ("ELECTRIC UTILITY FABRICATED", "utility"),
        ("RENT FABRICATED LANDLORD", "rent"),
        ("FABRICATED INSURANCE PREMIUM", "insurance"),
        ("CHECK FABRICATED CLEANING", "other"),
    ],
)
def test_recurring_rows_a_rule_already_claimed_are_never_promoted(description, state):
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", description, -300.0) for day in (2, 9, 16, 23)]
    ))
    assert {record.classification for record in records} == {state}


def test_proven_duplicates_do_not_make_a_recurring_group():
    statement = Statement(
        transactions=[
            txn("2054-01-02", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0, balance=600.0),
            txn("2054-01-02", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0, balance=600.0),
            txn("2054-01-09", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0, balance=200.0),
        ]
    )
    records = classify_statement_transactions(statement)
    assert not any(record.classification == "potential_lender" for record in records)


def test_financing_keyword_rows_of_two_unnamed_payees_are_not_merged():
    records = classify_statement_transactions(_statement([
        ("2054-01-02", "ADVANCE PAT EXAMPLE PMT", -200.0),
        ("2054-01-09", "ADVANCE LEE SAMPLE PMT", -200.0),
        ("2054-01-16", "ADVANCE PAT EXAMPLE PMT", -200.0),
        ("2054-01-23", "ADVANCE LEE SAMPLE PMT", -200.0),
    ]))
    assert {record.match_method for record in records} == {"financing_keyword_review"}


def test_fixed_debits_join_the_recurring_debit_view():
    """The CLI's "Recurring fixed debits" lines and batch.py's recurring_debit_groups
    read detect.find_recurring_debits, so the D6 rows must reach it."""
    from analysis.detect import find_recurring_debits

    statement = _statement(
        [(f"2054-01-{day:02d}", f"ACH DEBIT FABRICATED WIDGETS LLC {day:04d}", -400.0) for day in (2, 9, 16, 23)]
    )
    [recurring] = find_recurring_debits(statement)
    assert (recurring.description_key, recurring.amount, recurring.count, recurring.cadence) == (
        "Fabricated Widgets LLC",
        400.0,
        4,
        "weekly",
    )
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_recurring_fixed_debits.py -q -p no:cacheprovider`
Expected: FAIL. The two promotion tests stay `other`; `test_financing_keyword_rows_of_two_unnamed_payees_are_not_merged` fails because today's grouping merges both unnamed payees under one entity and promotes all four rows; `test_fixed_debits_join_the_recurring_debit_view` fails with `ValueError: not enough values to unpack (expected 1, got 0)`.

- [ ] **Step 3: Add the recurrence helpers.** Directly before `def classify_statement_transactions(`, add:

```python
#: D6 skips a row whose own words say it is a transfer, even when no transfer
#: rule claimed it (a transfer to a person is not an MCA remittance).
_TRANSFER_WORD_PATTERNS = (re.compile(r"\b(?:TRANSFER|XFER|TFR)\b"),)


def _promotion_cadence(
    records: list[TransactionClassification],
    indexes: list[int],
    min_recurring_count: int,
) -> tuple[str, float | None] | None:
    """The daily or weekly cadence of a same-amount group, or None when it does not promote."""
    if len(indexes) < min_recurring_count:
        return None
    dates = [parsed for index in indexes if (parsed := parse_date(records[index].date)) is not None]
    cadence, average_gap = classify_cadence(dates)
    if cadence not in {"daily", "weekly"}:
        return None
    return cadence, average_gap
```

- [ ] **Step 4: Replace the recurrence block.** In `classify_statement_transactions`, replace everything from the line `    groups: dict[tuple[str, float], list[int]] = {}` down to (not including) the line `    records = _apply_reversal_pair_context(records, set(duplicate_of))` with:

```python
    # Recurrence (spec §4.3 statement pass 2). Both kinds group by payee words
    # and amount, so two unnamed payees are never merged (D11).
    keyword_groups: dict[tuple[tuple[str, ...], float], list[int]] = {}
    fixed_debit_groups: dict[tuple[tuple[str, ...], float], list[int]] = {}
    for index, record in enumerate(records):
        if index in duplicate_of or record.amount >= 0 or record.classification != "other":
            continue
        payee = _unknown_payee_tokens(record.normalized_description)
        if not payee:
            continue
        key = (payee, round(abs(record.amount), 2))
        if record.match_method == "financing_keyword_review" and record.canonical_entity:
            keyword_groups.setdefault(key, []).append(index)
        elif record.match_method == "default" and not _matches_any(
            record.normalized_description,
            _TRANSFER_WORD_PATTERNS,
        ):
            fixed_debit_groups.setdefault(key, []).append(index)

    for indexes in keyword_groups.values():
        promotion = _promotion_cadence(records, indexes, min_recurring_count)
        if promotion is None:
            continue
        cadence, average_gap = promotion
        for index in indexes:
            records[index] = replace(
                records[index],
                classification="potential_lender",
                match_method="recurring_financing_counterparty",
                matched_rule=f"{cadence}_fixed_debit_{average_gap}_day_average",
                confidence_score=0.76,
                reason=(
                    f"An unverified financing-related counterparty repeats on a {cadence} cadence; "
                    "it is potential only and requires review."
                ),
                review_required=True,
                contributes_to_potential_lender_count=True,
                contributes_to_potential_lender_totals=True,
                contributes_to_potential_withholding_exposure=True,
            )

    # D6: an unknown payee (a row no rule claimed) with fixed daily or weekly
    # debits joins the review tier. Nothing is counted without a named lender.
    for (payee, _), indexes in fixed_debit_groups.items():
        promotion = _promotion_cadence(records, indexes, min_recurring_count)
        if promotion is None:
            continue
        cadence, average_gap = promotion
        entity = _unknown_payee_name(payee) or UNIDENTIFIED_LENDER_OBLIGATION
        for index in indexes:
            records[index] = replace(
                records[index],
                classification="potential_lender",
                canonical_entity=entity,
                match_method="recurring_fixed_debit",
                matched_rule=f"{cadence}_fixed_debit_{average_gap}_day_average",
                confidence_score=0.70,
                reason=(
                    f"An unknown payee repeats the same debit on a {cadence} cadence (D6); "
                    "it is potential only and requires review."
                ),
                review_required=True,
                contributes_to_potential_lender_count=True,
                contributes_to_potential_lender_totals=True,
                contributes_to_potential_withholding_exposure=True,
            )

```

- [ ] **Step 5: List the D6 rows in the recurring-debit view.** In `analysis/detect.py`, directly before `def find_recurring_debits(`, add:

```python
#: The recurrence tier's match methods (spec §4.3 statement pass 2): the
#: financing-keyword promotion and D6's fixed daily or weekly debits.
_RECURRING_MATCH_METHODS = frozenset({"recurring_financing_counterparty", "recurring_fixed_debit"})


```
and in `find_recurring_debits` replace
```python
            and record.match_method == "recurring_financing_counterparty"
```
with
```python
            and record.match_method in _RECURRING_MATCH_METHODS
```

- [ ] **Step 6: Run the new test.**

Run: `C:\Python314\python.exe -m pytest tests/test_recurring_fixed_debits.py tests/test_unknown_payee_naming.py tests/test_lender_insurance_classification.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 7: Check that ATB November does not move** (pin-ledger rows 10 and 12). Leave `tests/test_transaction_classifier.py` and `tests/test_revenue_classification.py` as Task 5 left them. The 21 fixed daily debits that the 2026-09-24 dry run's D6 promoted as `recurring_fixed_debit` are MERCH PAD's review alias since the owner decision of 2026-09-25. The potential registry claims them at step 11, before this statement pass, so D6 finds no other group on this statement (probe of 2026-09-26). Step 9 runs the Task 5 pins again: 22 rows / 3178.19 / 5.36, every one `candidate_lender_alias`.

- [ ] **Step 8: Re-pin navigant** (pin-ledger row 15). In `tests/test_new_statement_corpus.py`, the navigant `"lenders"` entry (`:153`) must read `"lenders": (0, 0.00, 4, 1299.00),`. If Task 0 printed `navigant: open loan debits naming a listed bank = 1` or more (the revised ledger reads 2), it must read `"lenders": (0, 0.00, 3, 108.00),` instead: the D5 bank-name rule (Task 8) then claims the loan row, and only D6's rows stay potential. D6's three rows are not navigant's Comenity card payments, which step 8 claims (probe of 2026-09-26).

- [ ] **Step 9: Run the regression selections.**

Run:
```
C:\Python314\python.exe -m pytest tests/test_recurring_fixed_debits.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_new_statement_corpus.py tests/test_lender_insurance_classification.py -q -p no:cacheprovider
C:\Python314\python.exe -m pytest tests/test_analysis.py tests/test_batch.py -q -p no:cacheprovider
```
Expected: PASS. If another fixture's potential figures move because of D6, stop and report the test id; do not re-pin it.

- [ ] **Step 10: Commit.**

```
git add analysis/transaction_classifier.py analysis/detect.py tests/test_recurring_fixed_debits.py tests/test_new_statement_corpus.py
git commit -m "classifier: fixed daily or weekly debits of unknown payees are potential lenders (D6)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 11: `metrics.flagged_groups`

**Files:**
- Modify: `analysis/transaction_classifier.py` (flag-group import; new `flagged_payee` after `classify_cadence`)
- Modify: `analysis/metrics.py` (imports `:23-26`; `Metrics` after `insurance_total` `:91`; `compute_metrics` loop `:318-346` and rounding `:398`)
- Modify: `tests/flag_group_fixtures.py` (append)
- Modify: `tests/test_analysis.py` (SBA test), `tests/test_transaction_classifier.py` (ATB Nov), `tests/test_new_statement_corpus.py` (the first_farmers BlueVine test)
- Test: `tests/test_flagged_positions_payload.py`

**Interfaces:**
- Consumes: C1 `FLAG_GROUPS`, `FLAG_GROUP_BY_KEY`.
- Produces (C5): `Metrics.flagged_groups: dict[str, dict[str, float | int]]` = `{"<group key>": {"count": int, "total": float, "payees": int}}`, only groups with a contributing row, in `FLAG_GROUPS` order, totals rounded to 2 decimals. Produces `transaction_classifier.flagged_payee(record: TransactionClassification) -> str` (the canonical entity, else the group label).

- [ ] **Step 1: Append the shared flagged fixture** to `tests/flag_group_fixtures.py`:

```python


#: One statement with four flagged groups, one lender (all via FAKE_PAYEES or
#: descriptors) and one deposit. Transaction numbers follow the tuple order.
FLAGGED_ROWS: tuple[tuple[str, str, float], ...] = (
    ("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
    ("2054-01-06", "ACH DEBIT FABRICATED ALT 0001", -700.0),
    ("2054-01-13", "ACH DEBIT FABRICATED ALT 0002", -700.0),
    ("2054-01-08", "ACH DEBIT FABRICATED BNPL 0001", -900.0),
    ("2054-01-05", "MORTGAGE PMT FABRICATED HOME", -1200.0),
    ("2054-02-05", "MORTGAGE PMT FABRICATED HOME", -1200.0),
    ("2054-01-10", "CREDIT CARD PAYMENT", -300.0),
    ("2054-01-20", "CREDIT CARD PAYMENT", -500.0),
    ("2054-01-12", "EQUIPMENT RENTAL FABRICATED", -200.0),
    ("2054-01-15", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
)

FLAGGED_GROUPS_EXPECTED: dict[str, dict[str, float | int]] = {
    "alternative_positions": {"count": 3, "total": 2300.0, "payees": 2},
    "credit_cards": {"count": 2, "total": 800.0, "payees": 1},
    "mortgages": {"count": 2, "total": 2400.0, "payees": 1},
    "leases_rentals": {"count": 1, "total": 200.0, "payees": 1},
}


def flagged_statement(rows: tuple[tuple[str, str, float], ...] = FLAGGED_ROWS):
    from analysis.schema import Statement

    return Statement(
        bank="Fabricated Bank",
        account_number="0000",
        transactions=[txn(day, description, amount) for day, description, amount in rows],
    )
```

- [ ] **Step 2: Write the failing test** `tests/test_flagged_positions_payload.py`:

```python
from __future__ import annotations

import pytest

from analysis.metrics import compute_metrics
from analysis.schema import Statement
from tests.flag_group_fixtures import (  # noqa: F401  (fake_payees and fake_premium_finance are fixtures)
    FLAGGED_GROUPS_EXPECTED,
    FLAGGED_ROWS,
    fake_payees,
    fake_premium_finance,
    flagged_statement,
    txn,
)

#: Two premium-finance debits and one ordinary insurance debit (fake_premium_finance).
PREMIUM_ROWS: tuple[tuple[str, str, float], ...] = (
    ("2054-01-05", "ACH DEBIT FABRICATED PFC", -300.0),
    ("2054-02-05", "ACH DEBIT FABRICATED PFC", -300.0),
    ("2054-01-09", "FABRICATED INSURER PMT", -100.0),
)


def test_metrics_sum_flagged_rows_per_group_in_flag_group_order(fake_payees):
    metrics = compute_metrics(flagged_statement())
    assert metrics.flagged_groups == FLAGGED_GROUPS_EXPECTED
    assert list(metrics.flagged_groups) == list(FLAGGED_GROUPS_EXPECTED)


def test_flagged_groups_never_move_lender_withholding_or_eligible_deposits(fake_payees):
    lender_and_deposit = tuple(row for row in FLAGGED_ROWS if "FABRICATED LENDER" in row[1] or row[2] > 0)
    without = compute_metrics(flagged_statement(lender_and_deposit))
    with_flagged = compute_metrics(flagged_statement())
    assert without.flagged_groups == {}
    for name in (
        "lender_debits", "lender_debit_count", "lenders_detected", "lender_credits",
        "eligible_deposits", "legacy_eligible_deposits", "withholding_numerator",
        "withholding_denominator", "withholding_rate", "potential_lender_debit_total",
        "potential_lender_debit_count", "potential_withholding_exposure",
    ):
        assert getattr(with_flagged, name) == getattr(without, name), name
    assert with_flagged.withholding_rate == pytest.approx(10.0)


def test_a_proven_duplicate_flagged_row_is_counted_once():
    statement = Statement(
        transactions=[
            txn("2054-01-02", "CREDIT CARD PAYMENT FABRICATED", -250.0, balance=750.0),
            txn("2054-01-02", "CREDIT CARD PAYMENT FABRICATED", -250.0, balance=750.0),
        ]
    )
    assert compute_metrics(statement).flagged_groups == {
        "credit_cards": {"count": 1, "total": 250.0, "payees": 1}
    }


def test_premium_financing_counts_as_insurance_and_as_its_flagged_group(fake_premium_finance):
    metrics = compute_metrics(flagged_statement(PREMIUM_ROWS))
    assert (metrics.insurance_count, metrics.insurance_total) == (3, 700.0)
    assert metrics.flagged_groups == {"premium_financing": {"count": 2, "total": 600.0, "payees": 1}}
```

- [ ] **Step 3: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_flagged_positions_payload.py -q -p no:cacheprovider`
Expected: FAIL with `AttributeError: 'Metrics' object has no attribute 'flagged_groups'`.

- [ ] **Step 4: Add `flagged_payee` to the classifier.** Change the import `from .flag_groups import FINANCING_STATES, FLAG_GROUP_BY_STATE` to `from .flag_groups import FINANCING_STATES, FLAG_GROUP_BY_KEY, FLAG_GROUP_BY_STATE`, and directly after the `classify_cadence` function add:

```python
def flagged_payee(record: TransactionClassification) -> str:
    """The payee a flagged row is grouped under: its entity, else its group's label (spec §6)."""
    if record.canonical_entity:
        return record.canonical_entity
    group = FLAG_GROUP_BY_KEY.get(record.flagged_group or "")
    return group.label if group is not None else (record.flagged_group or "")
```

- [ ] **Step 5: Add the metric.** In `analysis/metrics.py`:
  - replace the import block
    ```python
    from .transaction_classifier import (
        TransactionClassification,
        classify_statement_transactions,
    )
    ```
    with
    ```python
    from .flag_groups import FLAG_GROUPS
    from .transaction_classifier import (
        TransactionClassification,
        classify_statement_transactions,
        flagged_payee,
    )
    ```
  - in `Metrics`, replace
    ```python
        insurance_total: float = 0.0
    ```
    with
    ```python
        insurance_total: float = 0.0
        # Spec §6 (C5): {group key: {"count", "total", "payees"}} over rows marked
        # contributes_to_flagged_totals. It never feeds lender_*, withholding_*,
        # eligible_deposits or potential_* figures.
        flagged_groups: dict[str, dict[str, float | int]] = field(default_factory=dict)
    ```
  - in `compute_metrics`, replace
    ```python
        potential_entities: set[str] = set()
    ```
    with
    ```python
        potential_entities: set[str] = set()
        flagged_counts: dict[str, int] = {}
        flagged_totals: dict[str, float] = {}
        flagged_payees: dict[str, set[str]] = {}
    ```
  - in the per-row loop, replace
    ```python
            if classification.contributes_to_insurance_totals:
                m.insurance_count += 1
                m.insurance_total += abs(t.amount)
                m.insurance_evidence.append(classification)
    ```
    with
    ```python
            if classification.contributes_to_insurance_totals:
                m.insurance_count += 1
                m.insurance_total += abs(t.amount)
                m.insurance_evidence.append(classification)
            if classification.contributes_to_flagged_totals and classification.flagged_group:
                group_key = classification.flagged_group
                flagged_counts[group_key] = flagged_counts.get(group_key, 0) + 1
                flagged_totals[group_key] = flagged_totals.get(group_key, 0.0) + abs(t.amount)
                flagged_payees.setdefault(group_key, set()).add(flagged_payee(classification))
    ```
  - replace
    ```python
        m.insurance_total = round(m.insurance_total, 2)
    ```
    with
    ```python
        m.insurance_total = round(m.insurance_total, 2)
        m.flagged_groups = {
            group.key: {
                "count": flagged_counts[group.key],
                "total": round(flagged_totals[group.key], 2),
                "payees": len(flagged_payees[group.key]),
            }
            for group in FLAG_GROUPS
            if group.key in flagged_counts
        }
    ```

- [ ] **Step 6: Add the flagged assertions to the moved pins** (pin-ledger rows 6, 9, 14).
  - `tests/test_analysis.py::test_metrics_computes_true_revenue_cash_flow_lender_pos_and_loan_counts`: after `assert m.potential_lender_debit_count == 0` add
    ```python
        assert m.flagged_groups == {"alternative_positions": {"count": 1, "total": 750.0, "payees": 1}}
    ```
  - `tests/test_transaction_classifier.py::test_atb_november_lender_and_potential_obligation_regression`: after the Task 5 line `assert sum(record.classification == "alternative_position" ...) == 1` add
    ```python
        # BDC's row, and the two funders that stayed lenders, make up today's lender total.
        alternative = metrics.flagged_groups["alternative_positions"]
        assert alternative["count"] == alternative["payees"] == 1
        assert round(
            known_funders["CanaCap"].total_debited
            + known_funders["Forward Funding"].total_debited
            + alternative["total"],
            2,
        ) == 8658.91
        assert metrics.flagged_groups["credit_cards"]["count"] == 1
    ```
  - `tests/test_new_statement_corpus.py::test_first_farmers_bluevine_named_row_is_not_flagged`: add as its last line
    ```python
        assert "lines_of_credit" not in report.metrics.flagged_groups
    ```

- [ ] **Step 7: Run the tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_flagged_positions_payload.py tests/test_transaction_classifier.py tests/test_new_statement_corpus.py tests/test_lender_insurance_classification.py tests/test_revenue_classification.py tests/test_no_statement_hardcodes.py -q -p no:cacheprovider`
then `C:\Python314\python.exe -m pytest tests/test_analysis.py -q -p no:cacheprovider -k "metrics or withholding or lender"`
Expected: PASS, except the known pre-existing `test_no_literal_account_numbers_in_ocr`.

- [ ] **Step 8: Commit.**

```
git add analysis/transaction_classifier.py analysis/metrics.py tests/flag_group_fixtures.py tests/test_flagged_positions_payload.py tests/test_analysis.py tests/test_transaction_classifier.py tests/test_new_statement_corpus.py
git commit -m "metrics: flagged_groups per flag group, outside lender math" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 12: `detection.flagged_positions` in the payload

**Files:**
- Modify: `analysis/detect.py` (module docstring `:1`; imports `:4-12`; new dataclass after `RecurringDebit` `:41-49`; `DetectionResult` `:52-67`; new function after `find_insurance` `:145-165`; `detect` `:205-248`)
- Modify: `analysis/serialization.py` (new `_flagged_dict` after `_insurance_dict` `:76-87`; `report_to_dict` detection block `:165-191`)
- Modify: `tests/flag_group_fixtures.py` (append)
- Modify: `tests/test_flagged_positions_payload.py` (append)

**Interfaces:**
- Consumes: `describe_cadence` (Task 1), `flagged_payee` (Task 11), C1 `FLAG_GROUPS`.
- Produces (C5): `FlaggedPositionMatch(group, payee, matched_alias, count, total_debited, cadence, avg_gap_days, first_date, last_date, source_locations)`; `find_flagged_positions(stmt: Statement, classifications: list[TransactionClassification] | None = None) -> list[FlaggedPositionMatch]`; `DetectionResult.flagged_positions: list[FlaggedPositionMatch]` (default `[]`); payload `detection.flagged_positions`, a list of objects with exactly the C5 keys, sorted by group in `FLAG_GROUPS` order, then `total_debited` descending, then `payee`.

- [ ] **Step 1: Append the report builder** to `tests/flag_group_fixtures.py`:

```python


def flagged_report():
    """A full Report for FLAGGED_ROWS. Call it with the fake_payees fixture active."""
    from analysis.detect import detect
    from analysis.metrics import compute_metrics
    from analysis.pipeline import DocumentIntegrity, Quality, Report
    from analysis.reconcile import reconcile
    from analysis.transaction_classifier import classify_statement_transactions

    statement = flagged_statement()
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    return Report(
        statement=statement,
        reconciliation=reconcile(statement),
        metrics=metrics,
        detection=detect(statement, classifications=records, eligible_deposits=metrics.eligible_deposits),
        quality=Quality(
            level="transaction_level",
            transaction_detail_reliable=True,
            summary_totals_reliable=True,
            corporate_use="approved",
        ),
        integrity=DocumentIntegrity(risk_level="clear", flags=[], notes=[]),
        model_used="fabricated-test",
        escalated=False,
        classifications=records,
    )
```

- [ ] **Step 2: Append the failing tests** to `tests/test_flagged_positions_payload.py`:

```python


EXPECTED_POSITIONS = [
    {
        "group": "alternative_positions", "payee": "Fabricated Alt Capital", "matched_alias": "FABRICATED ALT",
        "count": 2, "total_debited": 1400.0, "cadence": "weekly", "avg_gap_days": 7.0,
        "first_date": "2054-01-06", "last_date": "2054-01-13",
        "source_locations": ["transaction:2", "transaction:3"],
    },
    {
        "group": "alternative_positions", "payee": "Fabricated BNPL", "matched_alias": "FABRICATED BNPL",
        "count": 1, "total_debited": 900.0, "cadence": "single", "avg_gap_days": None,
        "first_date": "2054-01-08", "last_date": "2054-01-08",
        "source_locations": ["transaction:4"],
    },
    {
        "group": "credit_cards", "payee": "Credit cards", "matched_alias": None,
        "count": 2, "total_debited": 800.0, "cadence": "irregular", "avg_gap_days": 10.0,
        "first_date": "2054-01-10", "last_date": "2054-01-20",
        "source_locations": ["transaction:7", "transaction:8"],
    },
    {
        "group": "mortgages", "payee": "Mortgages", "matched_alias": None,
        "count": 2, "total_debited": 2400.0, "cadence": "monthly", "avg_gap_days": 31.0,
        "first_date": "2054-01-05", "last_date": "2054-02-05",
        "source_locations": ["transaction:5", "transaction:6"],
    },
    {
        "group": "leases_rentals", "payee": "Leases & rentals", "matched_alias": None,
        "count": 1, "total_debited": 200.0, "cadence": "single", "avg_gap_days": None,
        "first_date": "2054-01-12", "last_date": "2054-01-12",
        "source_locations": ["transaction:9"],
    },
]


def test_detection_groups_flagged_rows_by_group_then_total(fake_payees):
    from analysis.detect import find_flagged_positions
    from analysis.transaction_classifier import classify_statement_transactions

    statement = flagged_statement()
    positions = find_flagged_positions(statement, classify_statement_transactions(statement))
    assert [(position.group, position.payee) for position in positions] == [
        (entry["group"], entry["payee"]) for entry in EXPECTED_POSITIONS
    ]


def test_the_payload_publishes_flagged_positions_and_the_row_fields(fake_payees):
    from analysis.serialization import report_to_dict
    from tests.flag_group_fixtures import flagged_report

    payload = report_to_dict(flagged_report())
    assert payload["detection"]["flagged_positions"] == EXPECTED_POSITIONS
    assert payload["metrics"]["flagged_groups"] == FLAGGED_GROUPS_EXPECTED
    for transaction in payload["statement"]["transactions"]:
        assert "flagged_group" in transaction["classification"]
        assert "contributes_to_flagged_totals" in transaction["classification"]
    assert payload["metrics"]["lender_debits"] == 1000.0


def test_a_detection_result_without_flagged_rows_publishes_an_empty_list():
    from analysis.detect import DetectionResult

    assert DetectionResult().flagged_positions == []


def test_a_premium_financier_is_a_flagged_position_under_its_own_name(fake_premium_finance):
    from analysis.detect import find_flagged_positions
    from analysis.transaction_classifier import classify_statement_transactions

    statement = flagged_statement(PREMIUM_ROWS)
    [position] = find_flagged_positions(statement, classify_statement_transactions(statement))
    assert (position.group, position.payee, position.matched_alias) == (
        "premium_financing",
        "Fabricated Premium Finance",
        "FABRICATED PFC",
    )
    assert (position.count, position.total_debited, position.cadence) == (2, 600.0, "monthly")
    assert position.source_locations == ["transaction:1", "transaction:2"]
```

- [ ] **Step 3: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_flagged_positions_payload.py -q -p no:cacheprovider`
Expected: FAIL with `ImportError: cannot import name 'find_flagged_positions' from 'analysis.detect'` (in the tests that import it), `KeyError: 'flagged_positions'` (the payload test) and `AttributeError` on `DetectionResult().flagged_positions`.

- [ ] **Step 4: Extend `analysis/detect.py`.**
  - Replace the module docstring line with `"""Authoritative lender, potential-lender, insurance and flagged-position evidence views."""`.
  - Replace the import block (from `from dataclasses import dataclass, field` through the `from .transaction_classifier import (...)` block) with:
    ```python
    from dataclasses import dataclass, field
    from datetime import date

    from .cadence import describe_cadence
    from .dates import parse_date
    from .flag_groups import FLAG_GROUPS
    from .schema import Statement, Transaction
    from .transaction_classifier import (
        TransactionClassification,
        classify_cadence,
        classify_statement_transactions,
        flagged_payee,
    )
    ```
  - After the `RecurringDebit` dataclass, add:
    ```python
    @dataclass
    class FlaggedPositionMatch:
        """One payee of one flagged group (spec §6): never a lender, never in lender math."""

        group: str
        payee: str
        matched_alias: str | None
        count: int = 0
        total_debited: float = 0.0
        cadence: str = "single"
        avg_gap_days: float | None = None
        first_date: str | None = None
        last_date: str | None = None
        source_locations: list[str] = field(default_factory=list)
    ```
  - In `DetectionResult`, replace
    ```python
        insurance_providers: list[InsuranceMatch] = field(default_factory=list)
    ```
    with
    ```python
        insurance_providers: list[InsuranceMatch] = field(default_factory=list)
        flagged_positions: list[FlaggedPositionMatch] = field(default_factory=list)
    ```
  - After the `find_insurance` function, add:
    ```python
    def find_flagged_positions(
        stmt: Statement,
        classifications: list[TransactionClassification] | None = None,
    ) -> list[FlaggedPositionMatch]:
        """Spec §6: one entry per flagged group and payee, over rows marked
        contributes_to_flagged_totals, sorted by group (FLAG_GROUPS order), then
        total debited (descending), then payee."""
        records = _records(stmt, classifications)
        matches: dict[tuple[str, str], FlaggedPositionMatch] = {}
        dates: dict[tuple[str, str], list[date]] = {}
        for index, record in enumerate(records):
            if not record.contributes_to_flagged_totals or not record.flagged_group:
                continue
            payee = flagged_payee(record)
            key = (record.flagged_group, payee)
            match = matches.get(key)
            if match is None:
                match = FlaggedPositionMatch(
                    group=record.flagged_group,
                    payee=payee,
                    matched_alias=record.matched_alias,
                )
                matches[key] = match
                dates[key] = []
            match.count += 1
            match.total_debited += abs(record.amount)
            match.source_locations.append(record.source_location or f"transaction:{index + 1}")
            parsed = parse_date(record.date)
            if parsed is not None:
                dates[key].append(parsed)
        for key, match in matches.items():
            match.total_debited = round(match.total_debited, 2)
            match.cadence, match.avg_gap_days = describe_cadence(dates[key])
            if dates[key]:
                match.first_date = min(dates[key]).isoformat()
                match.last_date = max(dates[key]).isoformat()
        order = {group.key: position for position, group in enumerate(FLAG_GROUPS)}
        return sorted(
            matches.values(),
            key=lambda item: (order.get(item.group, len(order)), -item.total_debited, item.payee),
        )
    ```
  - In `detect`, replace
    ```python
            insurance_providers=find_insurance(stmt, records),
    ```
    with
    ```python
            insurance_providers=find_insurance(stmt, records),
            flagged_positions=find_flagged_positions(stmt, records),
    ```

- [ ] **Step 5: Publish it in `analysis/serialization.py`.** After the `_insurance_dict` function add:

```python
def _flagged_dict(match) -> dict:
    """Spec §6 (C5): one flagged position, exactly the contract's keys."""
    return {
        "group": match.group,
        "payee": match.payee,
        "matched_alias": match.matched_alias,
        "count": match.count,
        "total_debited": match.total_debited,
        "cadence": match.cadence,
        "avg_gap_days": match.avg_gap_days,
        "first_date": match.first_date,
        "last_date": match.last_date,
        "source_locations": list(match.source_locations),
    }
```
and in `report_to_dict`, replace
```python
            "insurance_providers": [_insurance_dict(match) for match in detection.insurance_providers],
```
with
```python
            "insurance_providers": [_insurance_dict(match) for match in detection.insurance_providers],
            "flagged_positions": [_flagged_dict(match) for match in detection.flagged_positions],
```

- [ ] **Step 6: Run the tests and the payload neighbours.**

Run: `C:\Python314\python.exe -m pytest tests/test_flagged_positions_payload.py tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_new_statement_corpus.py tests/test_webapp_worker.py tests/test_document_report.py tests/test_webapp_app.py tests/test_package_currency.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 7: Commit.**

```
git add analysis/detect.py analysis/serialization.py tests/flag_group_fixtures.py tests/test_flagged_positions_payload.py
git commit -m "detection: flagged_positions in the analysis payload" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 13: Flagged positions in `batch.py` and `analyze.py`

**Files:**
- Modify: `batch.py` (`FIELDS` `:49`; `_row` `:161`)
- Modify: `analyze.py` (imports `:12-13`; `_render` before `return "\n".join(L)` `:171`)
- Modify: `tests/test_flagged_positions_payload.py` (append)

**Interfaces:**
- Consumes: `DetectionResult.flagged_positions` (Task 12), C1 `FLAG_GROUP_BY_KEY`.
- Produces: CSV column `flagged_positions` = `"; ".join(f"{group}:{payee}")` in detection order; a text block headed `## Flagged positions (not lenders; outside lender math)`. Neither reads Settings.

- [ ] **Step 1: Append the failing tests** to `tests/test_flagged_positions_payload.py`:

```python


def test_the_batch_row_lists_flagged_positions_as_group_and_payee(fake_payees):
    from pathlib import Path

    import batch
    from tests.flag_group_fixtures import flagged_report

    row = batch._row(Path("fabricated.pdf"), flagged_report())
    assert "flagged_positions" in batch.FIELDS
    assert row["flagged_positions"] == (
        "alternative_positions:Fabricated Alt Capital; alternative_positions:Fabricated BNPL; "
        "credit_cards:Credit cards; mortgages:Mortgages; leases_rentals:Leases & rentals"
    )
    assert row["mca_funders"] == "Fabricated Lender"


def test_the_text_report_prints_a_flagged_positions_block(fake_payees):
    from analyze import _render
    from tests.flag_group_fixtures import flagged_report

    rendered = _render(flagged_report())
    assert "## Flagged positions (not lenders; outside lender math)" in rendered
    assert "  - Alternative positions: Fabricated Alt Capital: 2 debit(s), $1,400.00 (weekly)" in rendered
    assert "  - Mortgages: Mortgages: 2 debit(s), $2,400.00 (monthly)" in rendered


def test_the_text_report_says_none_without_flagged_rows():
    from analyze import _render
    from analysis.detect import detect
    from analysis.metrics import compute_metrics
    from analysis.pipeline import DocumentIntegrity, Quality, Report
    from analysis.reconcile import reconcile

    statement = Statement(transactions=[txn("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 500.0)])
    report = Report(
        statement=statement,
        reconciliation=reconcile(statement),
        metrics=compute_metrics(statement),
        detection=detect(statement),
        quality=Quality(level="transaction_level", transaction_detail_reliable=True, summary_totals_reliable=True),
        integrity=DocumentIntegrity(risk_level="clear", flags=[], notes=[]),
        model_used="fabricated-test",
        escalated=False,
    )
    assert "  Flagged positions: none" in _render(report)
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_flagged_positions_payload.py -q -p no:cacheprovider -k "batch or text_report"`
Expected: FAIL with `KeyError: 'flagged_positions'` and missing block text.

- [ ] **Step 3: Add the CSV column.** In `batch.py`:
  - in `FIELDS`, replace `    "debit_coverage", "nsf", "mca_funders", "recurring_debit_groups",` with `    "debit_coverage", "nsf", "mca_funders", "flagged_positions", "recurring_debit_groups",`;
  - in `_row`, replace
    ```python
            "mca_funders": "; ".join(fm.funder for fm in d.known_funders),
    ```
    with
    ```python
            "mca_funders": "; ".join(fm.funder for fm in d.known_funders),
            # Spec §7: flagged obligations as group:payee, never lenders. Analysis
            # time only; the webapp's Settings never reach this CSV.
            "flagged_positions": "; ".join(f"{fp.group}:{fp.payee}" for fp in d.flagged_positions),
    ```

- [ ] **Step 4: Add the text block.** In `analyze.py`, after `from analysis.serialization import document_report_to_dict` add `from analysis.flag_groups import FLAG_GROUP_BY_KEY`, and in `_render` replace

```python
    else:
        L.append("  Recurring fixed debits: none with a regular cadence")
    return "\n".join(L)
```
with
```python
    else:
        L.append("  Recurring fixed debits: none with a regular cadence")

    # Spec §7: flagged obligations, analysis time only (no Settings are read).
    L.append("\n## Flagged positions (not lenders; outside lender math)")
    if d.flagged_positions:
        for fp in d.flagged_positions:
            group = FLAG_GROUP_BY_KEY.get(fp.group)
            label = group.label if group is not None else fp.group
            L.append(
                f"  - {label}: {fp.payee}: {fp.count} debit(s), "
                f"${fp.total_debited:,.2f} ({fp.cadence})"
            )
    else:
        L.append("  Flagged positions: none")
    return "\n".join(L)
```

- [ ] **Step 5: Run the tests and the CLI neighbours.**

Run: `C:\Python314\python.exe -m pytest tests/test_flagged_positions_payload.py tests/test_batch.py tests/test_revenue_classification.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 6: Commit.**

```
git add batch.py analyze.py tests/test_flagged_positions_payload.py
git commit -m "cli: flagged positions in batch and analyze" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 14: The benchmark reports flagged lenders as "flagged here"

**Files:**
- Modify: `benchmark/lenders.py` (imports `:9-11`; delete `NON_MCA_SCOPE` `:52-57`; add `flagged_lender_groups` after `canonical_lender`)
- Modify: `benchmark/compare.py` (import `:25`; `build_mca_rows` `:620-854`)
- Modify: `tests/test_benchmark_harness.py` (append)

**Interfaces:**
- Consumes: payload `detection.flagged_positions` (C5), C1 `FLAG_GROUP_BY_KEY`.
- Produces: `benchmark.lenders.flagged_lender_groups(detections: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]` (canonical key -> `{"group", "count", "total"}`); `NON_MCA_SCOPE` removed. A MoneyThumb lender that our payload flags gets `DIFFERENT_DEFINITION` rows (not `for_ocean`), and the aggregate names it as flagged here.

- [ ] **Step 1: Append the failing tests** to `tests/test_benchmark_harness.py`:

```python


# --------------------------------------------------------------------------
# Lender detection (2026-09-24, spec §7): flagged lenders are not misses.
# --------------------------------------------------------------------------

class TestFlaggedHere:
    @staticmethod
    def _set(flagged_positions):
        from benchmark.normalize import MTSet
        from benchmark.ourside import OurFileResult, OurSetResult

        mt = MTSet(
            name="synthetic", ok=True, http_status=200, uploaded_at=None,
            source_files=[], stub_message=None,
            response={"scorecard": {"mca_transactions": [
                {"lender": "FABRICATED ALT CAPITAL", "amount": "-100.00", "date": "2054-01-02"},
                {"lender": "FABRICATED ALT CAPITAL", "amount": "-100.00", "date": "2054-01-09"},
            ]}},
            paths=set(), summary_rows=[], result_rows=[],
        )
        payload = {
            "statement": {"transactions": []},
            "metrics": {},
            "detection": {
                "known_funders": [],
                "potential_lenders": [],
                "flagged_positions": flagged_positions,
            },
        }
        ours = OurSetResult(
            set_name="synthetic",
            files=[OurFileResult(relative_path="synthetic.pdf", source_type="digital/native",
                                 markdown="", payload=payload)],
        )
        return ours, mt

    def test_a_flagged_moneythumb_lender_is_flagged_here_not_missed(self):
        from benchmark.compare import build_mca_rows

        ours, mt = self._set([{
            "group": "alternative_positions", "payee": "FABRICATED ALT CAPITAL",
            "matched_alias": "FABRICATED ALT CAPITAL", "count": 2, "total_debited": 200.0,
            "cadence": "weekly", "avg_gap_days": 7.0, "first_date": "2054-01-02",
            "last_date": "2054-01-09", "source_locations": ["transaction:1", "transaction:2"],
        }])
        rows = {row.field: row for row in build_mca_rows("synthetic", ours, mt)}
        count_row = rows["mca.FABRICATED ALT CAPITAL.withdrawal_count"]
        assert count_row.outcome is Outcome.DIFFERENT_DEFINITION
        assert not count_row.for_ocean
        assert (count_row.ours, count_row.mt) == (2, 2)
        assert "flagged here" in count_row.rationale
        aggregate = rows["mca_lender_set"]
        assert aggregate.outcome is Outcome.DIFFERENT_DEFINITION
        assert "FABRICATED ALT CAPITAL" in aggregate.rationale

    def test_an_unflagged_moneythumb_lender_is_still_a_miss(self):
        from benchmark.compare import build_mca_rows

        ours, mt = self._set([])
        rows = {row.field: row for row in build_mca_rows("synthetic", ours, mt)}
        count_row = rows["mca.FABRICATED ALT CAPITAL.withdrawal_count"]
        assert count_row.outcome is not Outcome.DIFFERENT_DEFINITION
        assert count_row.for_ocean

    def test_the_old_non_mca_scope_set_is_gone(self):
        import benchmark.lenders as lenders

        assert not hasattr(lenders, "NON_MCA_SCOPE")
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_benchmark_harness.py -q -p no:cacheprovider -k TestFlaggedHere`
Expected: FAIL: the flagged row is `UNRESOLVED` with `for_ocean`, and `NON_MCA_SCOPE` still exists.

- [ ] **Step 3: Update `benchmark/lenders.py`.**
  - Replace `import re` (the import line after `from __future__ import annotations`) with:
    ```python
    import re
    from typing import Any, Iterable
    ```
  - Delete the `NON_MCA_SCOPE` comment and assignment (`:52-57`).
  - After the `canonical_lender` function add:
    ```python
    def flagged_lender_groups(detections: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Canonical key -> {"group", "count", "total"} over ``detection.flagged_positions``.

        Replaces the old NON_MCA_SCOPE set (owner ruling 2026-09-24): a
        counterparty our payload carries as a flagged position is outside lender
        math by ruling, so a MoneyThumb lender that matches one is reported as
        flagged here, never as a miss.
        """
        flagged: dict[str, dict[str, Any]] = {}
        for detection in detections:
            for position in detection.get("flagged_positions") or []:
                canonical = canonical_lender(position.get("payee"))
                entry = flagged.setdefault(
                    canonical, {"group": position.get("group"), "count": 0, "total": 0.0}
                )
                entry["count"] += int(position.get("count") or 0)
                entry["total"] = round(
                    entry["total"] + abs(float(position.get("total_debited") or 0.0)), 2
                )
        return flagged
    ```

- [ ] **Step 4: Update `benchmark/compare.py`.**
  - Replace `from .lenders import NON_MCA_SCOPE, canonical_lender, ledger_tokens` with:
    ```python
    from analysis.flag_groups import FLAG_GROUP_BY_KEY

    from .lenders import canonical_lender, flagged_lender_groups, ledger_tokens
    ```
  - In `build_mca_rows`, replace
    ```python
        mt_lenders: dict[str, MTLender] = {}
    ```
    with
    ```python
        # Counterparties our payload flags (owner ruling 2026-09-24) are not
        # lenders here, and a MoneyThumb lender matching one is no miss.
        our_flagged = flagged_lender_groups(our_file.detection for our_file in ours.files)

        mt_lenders: dict[str, MTLender] = {}
    ```
  - Replace
    ```python
            our_count = our_entry["count"] if our_entry else None
            our_total = our_entry["total"] if our_entry else None
    ```
    with
    ```python
            flagged_entry = our_flagged.get(canonical) if our_entry is None else None
            tracked = our_entry or flagged_entry
            our_count = tracked["count"] if tracked else None
            our_total = tracked["total"] if tracked else None
    ```
  - Replace the scope block
    ```python
            scope_note = ""
            different_definition = None
            if our_entry and not mt_entry and canonical in NON_MCA_SCOPE:
                different_definition = {
                    "ours": "general financing/lender detection (registry-backed, "
                    "includes BNPL / SBA / consumer-finance counterparties)",
                    "moneythumb": "MCA-specific lender list (mca_transactions)",
                }
                scope_note = (
                    f"'{canonical}' is a financing counterparty outside MCA scope; "
                    "MT's list is MCA-specific, so its absence there is a scope "
                    "difference, not an extraction miss."
                )
    ```
    with
    ```python
            scope_note = ""
            different_definition = None
            if flagged_entry is not None and mt_entry is not None:
                group = flagged_entry["group"]
                label = FLAG_GROUP_BY_KEY[group].label if group in FLAG_GROUP_BY_KEY else str(group)
                different_definition = {
                    "ours": f"flagged here as {label}: a financing obligation outside "
                    "lender math (owner ruling 2026-09-24)",
                    "moneythumb": "MCA-specific lender list (mca_transactions)",
                }
                scope_note = f"'{canonical}' is flagged here ({label}), not a missed lender."
    ```
  - Replace everything from the line `    # Aggregate lender-set row.` through the function's final `    return rows` with:
    ```python
        # Aggregate lender-set row.
        our_confirmed = sorted(
            canonical for canonical, entry in our_lenders.items() if entry["kind"] == "confirmed"
        )
        mt_detected = sorted(mt_lenders)
        ours_only = [c for c in our_confirmed if c not in mt_lenders]
        # A MoneyThumb lender our payload carries as a flagged position is not a
        # miss: the owner ruled it out of lender math (2026-09-24).
        mt_flagged = [c for c in mt_detected if c not in our_lenders and c in our_flagged]
        mt_only = [c for c in mt_detected if c not in our_lenders and c not in our_flagged]
        flagged_note = (
            f" MoneyThumb lenders flagged here, not missed: {mt_flagged}." if mt_flagged else ""
        )
        mt_only_corroborated = [c for c in mt_only if ledger_debits(c)]
        mt_only_deposit_only = [
            c for c in mt_only if (mt_lenders[c].withdrawal_count or 0) == 0
        ]
        if mt_flagged and not mt_only and not ours_only:
            rows.append(
                classify(
                    set_name, "mca_lender_set", our_confirmed, mt_detected,
                    different_definition={
                        "ours": "lenders are MCA and equipment-financing funders; other "
                        "financing obligations are flagged positions (owner ruling 2026-09-24)",
                        "moneythumb": "MCA-specific lender list (mca_transactions)",
                    },
                    note=flagged_note.strip(),
                )
            )
            return rows
        if mt_only and not ours_only and all(
            c in mt_only_deposit_only for c in mt_only
        ) and all(ledger_credits(c) for c in mt_only):
            # MT counts a position on the funding deposit alone; we recognized the
            # same deposit as a lender funding credit (non-revenue) but list a
            # lender only once withholding debits exist.
            aggregate = classify(
                set_name, "mca_lender_set", our_confirmed, mt_detected,
                different_definition={
                    "ours": "lender listed when registry-confirmed withholding "
                    "debits exist (funding credits tracked separately as "
                    "lender_credits/non-revenue)",
                    "moneythumb": "lender listed on a funding deposit alone "
                    "(no withdrawals required)",
                },
                note=f"MT-only {mt_only} are deposit-only entries; our ledger "
                "recognizes the same funding credit(s) - see the "
                "funding_deposits row(s)." + flagged_note,
            )
            rows.append(aggregate)
            return rows
        if not ours_only and not mt_only:
            outcome_note = (
                "Identical canonical lender sets; per-lender rows carry the "
                "count/total evidence."
            )
            aggregate = classify(
                set_name, "mca_lender_set", our_confirmed, mt_detected,
                source_value=our_confirmed,
                source_evidence={"kind": "ledger_rows",
                                 "detail": "per-lender ledger evidence (see mca.* rows)"},
                note=outcome_note,
            )
        elif mt_only_corroborated and not ours_only:
            aggregate = ComparisonRow(
                set_name=set_name, field="mca_lender_set",
                outcome=Outcome.MONEYTHUMB_CORRECT,
                ours=our_confirmed, mt=mt_detected,
                evidence={"kind": "ledger_rows",
                          "detail": f"ledger corroborates MT-only lenders {mt_only_corroborated}"},
                rationale=(
                    "MoneyThumb detected financing counterparties "
                    f"{mt_only_corroborated} that our registry missed (ledger rows "
                    "corroborate). Registry additions require an Ocean ruling."
                ),
                for_ocean=True,
            )
        elif ours_only and not mt_only:
            aggregate = ComparisonRow(
                set_name=set_name, field="mca_lender_set",
                outcome=Outcome.OUR_SYSTEM_CORRECT,
                ours=our_confirmed, mt=mt_detected,
                evidence={"kind": "ledger_rows",
                          "detail": f"registry-confirmed ledger evidence for {ours_only}"},
                rationale=(
                    f"We detected MCA-scope lenders {ours_only} that MoneyThumb "
                    "missed; the reconciled ledger rows are the evidence."
                ),
            )
        else:
            aggregate = classify(
                set_name, "mca_lender_set", our_confirmed, mt_detected,
                note=f"ours-only={ours_only}, mt-only={mt_only}.",
            )
        aggregate.rationale += flagged_note
        rows.append(aggregate)

        return rows
    ```

- [ ] **Step 5: Run the harness tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_benchmark_harness.py -q -p no:cacheprovider`
Expected: PASS (the manifest smoke test may skip, by name, when the corpus is absent).

- [ ] **Step 6: Confirm nothing else read the old set.**

Run: `git grep -n "NON_MCA_SCOPE" -- benchmark tests analysis webapp tools`
Expected: two lines only: the `flagged_lender_groups` docstring in `benchmark/lenders.py` and the `hasattr` test line in `tests/test_benchmark_harness.py`.

- [ ] **Step 7: Commit.**

```
git add benchmark/lenders.py benchmark/compare.py tests/test_benchmark_harness.py
git commit -m "benchmark: MoneyThumb lenders we flag are reported as flagged here" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 15: The before/after lender census (spec §9)

**Files:**
- Create: `tools/lender_census.py`
- Test: `tests/test_lender_census.py`

**Interfaces:**
- Consumes: the classifier and metrics of whichever checkout `--code-root` names (`classify_statement_transactions`, `compute_metrics`, `CLASSIFICATION_VERSION`, `Metrics.flagged_groups` when present); `analysis.schema.Statement`; the artifact cache layout S1's audit reads (`webapp.db` table `artifact_cache`, stage `analysis`); the C10 ledger `docs/lender-registry-ledger.json`, of which it reads the `schema` and each entry's `entity`, `group` and `status`; the `fake_payees` fixture (tests only).
- Produces:
  - `DEFAULT_LEDGER: Path` (`docs/lender-registry-ledger.json`)
  - `GENERIC_WORDS: frozenset[str]`
  - `admitted_lenders(ledger: object) -> frozenset[str]`: the entities with `status` `admitted` and `group` `confirmed_lender`. It raises `ValueError` for anything but a schema-1 ledger.
  - `cached_accounts(data_dir: Path, limit: int | None = None) -> Iterator[tuple[str, int, dict]]`
  - `account_snapshot(account: dict) -> dict` with keys `rows`, `states`, `lenders` (`[index, entity, alias]`), `flagged` (`{group key: [count, total]}`), `lender_debits`, `eligible_deposits`, `withholding_rate`
  - `snapshot(accounts) -> dict` (`classification_version`, `accounts` keyed `"<sha>:<index>"`, `skipped`)
  - `compare(before: dict, after: dict, admitted: Collection[str], merged: Mapping[str, str] | None = None) -> dict`. Each gained lender carries `"admitted": bool`. `merged` is S1's `MERGED_REGISTRY_ENTITIES` (owner decision 2026-09-25: EBF HOLDINGS is merged into EVEREST BUSINESS FUNDING). The census reads a merged entity as its target, so a merge is one lender, not one lost and one gained. `main` passes it on `compare`, the one subcommand that loads no other checkout.
  - `main(argv) -> int` with the subcommands `snapshot` and `compare` and exit codes 0, 1 and 2.
- The census runs locally only. Its snapshot and comparison files hold statement figures, so the tool refuses any output path inside the repository; the printed lines carry counts, registry entity names and aliases only. Master plan step 4 runs it on the full cache after S2 merges.
- **Spec §9, acceptance 1** reads "every gained lender traces to an admitted ledger entity". C10 makes that checkable: the census reads the ledger's JSON, not the evidence document rendered from it. A gained lender passes only when its `canonical_entity` is an `admitted` `confirmed_lender` `entity` of the ledger. A name that appears in the ledger only as `review`, `owner_ruling`, `rejected` or another group does not pass.

- [ ] **Step 1: Write the failing test** `tests/test_lender_census.py`:

```python
"""tools/lender_census.py over a fabricated artifact cache, fabricated snapshots and a fabricated C10 ledger (spec section 9)."""
from __future__ import annotations

import json

import pytest

from tests.flag_group_fixtures import fake_payees  # noqa: F401  (fixture)
from tools import lender_census as census
from webapp.artifact_cache import ArtifactCache


def _row(day: str, description: str, amount: float) -> dict:
    return {"date": day, "description": description, "amount": amount,
            "direction": "credit" if amount >= 0 else "debit", "running_balance": None}


def _cache(tmp_path):
    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("a" * 64, "settings", {"statement": {"transactions": [
        _row("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
        _row("2054-01-05", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
        _row("2054-01-06", "ACH DEBIT FABRICATED ALT 0001", -700.0),
    ]}})
    cache.put_analysis("b" * 64, "settings", {"document": {}, "accounts": [
        {"statement": {"transactions": [_row("2054-01-05", "MORTGAGE PMT FABRICATED HOME", -1200.0)]}},
        {"statement": {"transactions": [
            {"date": "2054-01-06", "description": "FABRICATED ROW", "amount": "not a number", "direction": "debit"},
        ]}},
    ]})
    return tmp_path / "data"


def test_a_snapshot_records_states_lenders_flags_and_withholding_per_account(tmp_path, fake_payees):
    result = census.snapshot(census.cached_accounts(_cache(tmp_path)))
    assert result["classification_version"] == "5.0"
    first = result["accounts"]["a" * 64 + ":0"]
    assert first["states"] == ["other", "confirmed_lender", "alternative_position"]
    assert first["lenders"] == [[1, "Fabricated Lender", "FABRICATED LENDER"]]
    assert first["flagged"] == {"alternative_positions": [1, 700.0]}
    assert first["withholding_rate"] == pytest.approx(10.0)
    assert result["accounts"]["b" * 64 + ":0"]["flagged"] == {"mortgages": [1, 1200.0]}
    assert "b" * 64 + ":1" not in result["accounts"]
    assert result["skipped"] == {"ValidationError": 1}


def _account(states, lenders, flagged, rate):
    return {"rows": len(states), "states": states, "lenders": lenders, "flagged": flagged,
            "lender_debits": 0.0, "eligible_deposits": 1000.0, "withholding_rate": rate}


BEFORE = {"classification_version": "4.1", "accounts": {
    "s1:0": _account(["other", "confirmed_lender", "confirmed_lender"],
                     [[1, "Quillon Funding", "QUILLON FUNDING"], [2, "Brambleway Capital", "BRAMBLEWAY CAPITAL"]],
                     {}, 30.0),
    "s2:0": _account(["confirmed_lender"], [[0, "Quillon Funding", "QUILLON FUNDING"]], {}, 12.0),
}}
AFTER = {"classification_version": "5.0", "accounts": {
    "s1:0": _account(["confirmed_lender", "confirmed_lender", "alternative_position"],
                     [[0, "Tarnmoor Funding", "FUNDING"], [1, "Quillon Funding", "QUILLON FUNDING"]],
                     {"alternative_positions": [1, 100.0]}, 25.0),
    "s2:0": _account(["confirmed_lender"], [[0, "Quillon Funding", "QUILLON FUNDING"]], {}, 12.0),
}}


def _ledger(*entries: tuple[str, str, str]) -> dict:
    """A fabricated C10 ledger, one (entity, group, status) per entry: the three fields the census reads."""
    return {"schema": 1, "entities": [
        {"entity": entity, "group": group, "status": status} for entity, group, status in entries
    ]}


def test_admitted_lenders_are_the_admitted_confirmed_lender_entities():
    ledger = _ledger(
        ("Quillon Funding", "confirmed_lender", "admitted"),
        ("Tarnmoor Funding", "confirmed_lender", "review"),
        ("Brambleway Capital", "alternative_position", "admitted"),
        ("Fenwold Advance", "confirmed_lender", "rejected"),
    )
    assert census.admitted_lenders(ledger) == frozenset({"Quillon Funding"})


@pytest.mark.parametrize("ledger", ["| Quillon Funding | lender |", {"schema": 2, "entities": []}, {"schema": 1}])
def test_admitted_lenders_refuse_anything_but_a_schema_1_ledger(ledger):
    with pytest.raises(ValueError):
        census.admitted_lenders(ledger)


def test_compare_reports_gains_losses_generic_words_flags_and_withholding():
    report = census.compare(BEFORE, AFTER, admitted=frozenset({"Quillon Funding"}))
    assert report["accounts_compared"] == 2
    assert report["gained"] == {
        "Tarnmoor Funding": {"analyses": 1, "rows": 1, "aliases": {"FUNDING": 1}, "admitted": False},
    }
    assert report["lost"] == {"Brambleway Capital": {"analyses": 1, "rows_now": {"alternative_position": 1}}}
    assert report["gained_through_generic_words"] == [{"entity": "Tarnmoor Funding", "alias": "FUNDING", "rows": 1}]
    assert report["flagged"] == {"alternative_positions": {"analyses": 1, "rows": 1}}
    assert report["withholding"] == {"down": 1, "unchanged": 1}
    assert report["largest_withholding_moves"]["down"] == ["s1:0"]


def test_compare_reads_a_merged_entity_as_the_entity_that_absorbed_it():
    """Owner decision 2026-09-25 (MERGED_REGISTRY_ENTITIES): a merge is one lender, not a loss and a gain."""
    before = {"classification_version": "4.1", "accounts": {
        "s1:0": _account(["confirmed_lender"], [[0, "Quillon Holdings", "QUILLON HOLDINGS"]], {}, 12.0),
    }}
    after = {"classification_version": "5.0", "accounts": {
        "s1:0": _account(["confirmed_lender"], [[0, "Quillon Funding", "QUILLON HOLDINGS"]], {}, 12.0),
    }}
    merged = census.compare(before, after, admitted=frozenset({"Quillon Funding"}),
                            merged={"Quillon Holdings": "Quillon Funding"})
    assert (merged["gained"], merged["lost"]) == ({}, {})
    plain = census.compare(before, after, admitted=frozenset({"Quillon Funding"}))
    assert (set(plain["gained"]), set(plain["lost"])) == ({"Quillon Funding"}, {"Quillon Holdings"})


def _files(tmp_path, before, after, ledger):
    paths = {}
    for name, content in (("before", before), ("after", after), ("ledger", ledger)):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(content), encoding="utf-8")
    return paths


def _compare_argv(paths, tmp_path):
    return ["compare", "--before", str(paths["before"]), "--after", str(paths["after"]),
            "--ledger", str(paths["ledger"]), "--out", str(tmp_path / "report.json")]


def _gain_through_a_named_alias():
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["s1:0"]["lenders"][0] = [0, "Tarnmoor Funding", "TARNMOOR FUNDING"]
    return after


def test_the_census_calls_generic_every_word_the_ledger_validator_calls_generic():
    """Spec section 9 acceptance 5 and C10's generic-word rule share one definition: every word S1's validator
    refuses as a bare generic alias is generic to the census too."""
    from tools.lender_ledger import GENERIC_WORDS as LEDGER_GENERIC_WORDS

    assert LEDGER_GENERIC_WORDS <= census.GENERIC_WORDS
    assert {"BANK", "HOLDINGS", "LENDER", "MERCHANT", "SOLUTIONS", "SERVICING", "FUNDER"} <= census.GENERIC_WORDS


def test_compare_fails_on_a_gain_through_a_generic_word_even_when_admitted(tmp_path, capsys):
    ledger = _ledger(("Quillon Funding", "confirmed_lender", "admitted"),
                     ("Tarnmoor Funding", "confirmed_lender", "admitted"))
    paths = _files(tmp_path, BEFORE, AFTER, ledger)
    assert census.main(_compare_argv(paths, tmp_path)) == 1
    printed = capsys.readouterr().out
    assert "! Tarnmoor Funding via 'FUNDING': 1 rows" in printed
    assert "- Brambleway Capital: 1 analyses; rows now: alternative_position 1" in printed
    assert "NOT AN ADMITTED LENDER" not in printed


def test_compare_passes_when_every_gain_is_an_admitted_ledger_lender(tmp_path):
    paths = _files(tmp_path, BEFORE, _gain_through_a_named_alias(),
                   _ledger(("Tarnmoor Funding", "confirmed_lender", "admitted")))
    assert census.main(_compare_argv(paths, tmp_path)) == 0


@pytest.mark.parametrize(
    ("group", "status"),
    [("confirmed_lender", "review"), ("confirmed_lender", "owner_ruling"), ("alternative_position", "admitted")],
)
def test_compare_fails_on_a_gain_the_ledger_does_not_admit_as_a_lender(tmp_path, capsys, group, status):
    paths = _files(tmp_path, BEFORE, _gain_through_a_named_alias(), _ledger(("Tarnmoor Funding", group, status)))
    assert census.main(_compare_argv(paths, tmp_path)) == 1
    assert "+ Tarnmoor Funding: 1 analyses, 1 rows  NOT AN ADMITTED LENDER IN THE LEDGER" in capsys.readouterr().out


def test_compare_refuses_a_ledger_that_is_missing_or_not_the_c10_json(tmp_path):
    paths = _files(tmp_path, BEFORE, AFTER, {"schema": 2, "entities": []})
    assert census.main(_compare_argv(paths, tmp_path)) == 2
    paths["ledger"].write_text("| Quillon Funding | lender |", encoding="utf-8")
    assert census.main(_compare_argv(paths, tmp_path)) == 2
    paths["ledger"].unlink()
    assert census.main(_compare_argv(paths, tmp_path)) == 2
    assert not (tmp_path / "report.json").exists()


def test_the_census_refuses_output_inside_the_repository_and_a_directory_without_a_cache(tmp_path):
    inside = census.ROOT / "lender-census-must-not-exist.json"
    assert census.main(["snapshot", "--data-dir", str(_cache(tmp_path)), "--out", str(inside)]) == 2
    assert not inside.exists()
    assert census.main(["snapshot", "--data-dir", str(tmp_path / "empty"), "--out", str(tmp_path / "s.json")]) == 2


def test_a_snapshot_run_writes_the_file_it_names(tmp_path, fake_payees):
    out = tmp_path / "local" / "after.json"
    assert census.main(["snapshot", "--data-dir", str(_cache(tmp_path)), "--out", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(written["accounts"]) == ["a" * 64 + ":0", "b" * 64 + ":0"]
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_lender_census.py -q -p no:cacheprovider`
Expected: FAIL at collection with `ImportError: cannot import name 'lender_census' from 'tools'`.

- [ ] **Step 3: Write** `tools/lender_census.py`:

```python
"""Before/after lender census over the local artifact cache (spec section 9). Local only; never run in CI.

`snapshot` re-classifies every cached analysis with the `analysis` package of one checkout and
records, per account: each row's state, the lender rows (index, entity, alias), the flagged groups
and the withholding figures. `compare` reads two snapshots, taken with the code before and after
the lender-detection change, and reports lenders gained and lost, flagged groups and withholding
moves. It prints counts, registry entity names and aliases only: no descriptor text, no amount.
Both snapshots and the comparison hold figures from customer statements, so they stay outside the
repository.

Usage, from the repository root of the checkout that holds this tool:
    python -m tools.lender_census snapshot --data-dir <webapp_data> --out <file> [--code-root <checkout>] [--limit N]
    python -m tools.lender_census compare --before <file> --after <file> --out <file> [--ledger <file>]

`--code-root` names the checkout whose `analysis` package classifies (default: this one), so the
"before" snapshot runs the code as it stood before the change. `--ledger` is the curated registry
ledger the alias tables are rendered from (master plan C10; default docs/lender-registry-ledger.json).

Exit codes: snapshot 0, or 2 when refused. compare 0 when the ledger admits every gained lender as a
lender (status `admitted`, group `confirmed_lender`) and none was gained through a generic word,
1 otherwise, 2 when refused (including a ledger that is missing or not schema 1).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = ROOT / "docs" / "lender-registry-ledger.json"

#: Words that never identify a lender on their own (spec section 9, acceptance 5). Every word of the C10
#: validator's `tools.lender_ledger.GENERIC_WORDS`, plus FUNDER, so an alias the validator refuses as generic
#: is generic here too (tests/test_lender_census.py pins the superset). Written out rather than imported:
#: importing tools.lender_ledger loads this checkout's `analysis` package, and `snapshot --code-root` must load
#: the other checkout's.
GENERIC_WORDS = frozenset({
    "ACH", "ADVANCE", "ADVANCES", "AND", "AUTO", "BANK", "BUSINESS", "CAPITAL", "CARD", "CO", "COMPANY",
    "CORP", "CORPORATION", "CREDIT", "DEBIT", "EQUIPMENT", "FINANCE", "FINANCIAL", "FINANCING", "FUND",
    "FUNDER", "FUNDING", "FUNDS", "GROUP", "HOLDINGS", "INC", "INSURANCE", "LEASE", "LEASING", "LENDER",
    "LENDING", "LLC", "LOAN", "LOANS", "LTD", "MCA", "MERCHANT", "MORTGAGE", "OF", "PAYMENT", "PAYMENTS", "PMT",
    "SERVICES", "SERVICING", "SOLUTIONS", "THE",
})


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def admitted_lenders(ledger: object) -> frozenset[str]:
    """The entities the C10 ledger admits as lenders: status `admitted` and group `confirmed_lender`.

    Raises ValueError for anything but a schema-1 ledger with an `entities` list."""
    if not isinstance(ledger, dict) or ledger.get("schema") != 1 or not isinstance(ledger.get("entities"), list):
        raise ValueError("not a schema-1 lender registry ledger")
    return frozenset(
        entry["entity"]
        for entry in ledger["entities"]
        if isinstance(entry, dict)
        and entry.get("status") == "admitted"
        and entry.get("group") == "confirmed_lender"
        and isinstance(entry.get("entity"), str)
    )


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


def cached_accounts(data_dir: Path, limit: int | None = None) -> Iterator[tuple[str, int, dict]]:
    """(input sha, account index, account payload) for the latest cached analysis of each input.
    Opens the cache database read-only and never writes to the data directory."""
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
            yield sha, index, account


def account_snapshot(account: dict) -> dict:
    """Re-classify one account payload with the `analysis` package on sys.path."""
    from analysis.metrics import compute_metrics
    from analysis.schema import Statement
    from analysis.transaction_classifier import classify_statement_transactions

    statement = Statement.model_validate(account["statement"])
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    return {
        "rows": len(records),
        "states": [record.classification for record in records],
        "lenders": [
            [index, record.canonical_entity, record.matched_alias]
            for index, record in enumerate(records)
            if record.contributes_to_lender_totals
        ],
        "flagged": {
            key: [group["count"], group["total"]]
            for key, group in (getattr(metrics, "flagged_groups", None) or {}).items()
        },
        "lender_debits": metrics.lender_debits,
        "eligible_deposits": metrics.eligible_deposits,
        "withholding_rate": metrics.withholding_rate,
    }


def snapshot(accounts: Iterable[tuple[str, int, dict]]) -> dict:
    """{"classification_version", "accounts": {"<sha>:<index>": account snapshot}, "skipped": {reason: n}}."""
    from analysis.transaction_classifier import CLASSIFICATION_VERSION

    result: dict = {"classification_version": CLASSIFICATION_VERSION, "accounts": {}, "skipped": {}}
    skipped: Counter = Counter()
    for sha, index, account in accounts:
        try:
            result["accounts"][f"{sha}:{index}"] = account_snapshot(account)
        except Exception as error:  # noqa: BLE001  (a stored payload the schema no longer reads)
            skipped[type(error).__name__] += 1
    result["skipped"] = dict(sorted(skipped.items()))
    return result


def _generic(alias: str | None) -> bool:
    words = [word for word in re.split(r"[^A-Z0-9]+", (alias or "").upper()) if word]
    return bool(words) and all(word in GENERIC_WORDS for word in words)


def compare(
    before: dict,
    after: dict,
    admitted: Collection[str],
    merged: Mapping[str, str] | None = None,
) -> dict:
    """Lenders gained and lost, generic-word gains, flagged groups and withholding moves.

    `admitted` holds the ledger's admitted lender entities (`admitted_lenders`). `merged` maps an
    entity of the registry before the change to the ledger entity that absorbed it (S1's
    MERGED_REGISTRY_ENTITIES): the two are one lender, so a merge is neither a gain nor a loss."""
    merged = merged or {}

    def one_lender(entity: str) -> str:
        return merged.get(entity, entity)

    gained: dict = defaultdict(lambda: {"analyses": set(), "rows": 0, "aliases": Counter()})
    lost: dict = defaultdict(lambda: {"analyses": set(), "rows_now": Counter()})
    generic: Counter = Counter()
    flagged: dict = defaultdict(lambda: {"analyses": set(), "rows": 0})
    withholding: Counter = Counter()
    moves: list[tuple[float, str]] = []
    unmatched = 0
    for key, old in sorted(before["accounts"].items()):
        new = after["accounts"].get(key)
        if new is None or new["rows"] != old["rows"]:
            unmatched += 1
            continue
        sha = key.split(":")[0]
        old_entities = {one_lender(entity) for _, entity, _ in old["lenders"]}
        new_entities = {one_lender(entity) for _, entity, _ in new["lenders"]}
        for _, entity, alias in new["lenders"]:
            if one_lender(entity) not in old_entities:
                slot = gained[entity]
                slot["analyses"].add(sha)
                slot["rows"] += 1
                slot["aliases"][alias] += 1
                if _generic(alias):
                    generic[(entity, alias)] += 1
        for index, entity, _ in old["lenders"]:
            if one_lender(entity) not in new_entities:
                slot = lost[entity]
                slot["analyses"].add(sha)
                slot["rows_now"][new["states"][index]] += 1
        for group, (count, _total) in new["flagged"].items():
            flagged[group]["analyses"].add(sha)
            flagged[group]["rows"] += count
        old_rate, new_rate = old["withholding_rate"], new["withholding_rate"]
        if old_rate is None or new_rate is None:
            withholding["not_comparable"] += 1
        elif round(new_rate - old_rate, 6) == 0:
            withholding["unchanged"] += 1
        else:
            withholding["up" if new_rate > old_rate else "down"] += 1
            moves.append((round(new_rate - old_rate, 4), key))
    moves.sort()
    return {
        "before_version": before.get("classification_version"),
        "after_version": after.get("classification_version"),
        "accounts_compared": len(before["accounts"]) - unmatched,
        "accounts_unmatched": unmatched,
        "gained": {
            entity: {
                "analyses": len(slot["analyses"]),
                "rows": slot["rows"],
                "aliases": dict(slot["aliases"]),
                "admitted": entity in admitted,
            }
            for entity, slot in sorted(gained.items())
        },
        "lost": {
            entity: {"analyses": len(slot["analyses"]), "rows_now": dict(slot["rows_now"])}
            for entity, slot in sorted(lost.items())
        },
        "gained_through_generic_words": [
            {"entity": entity, "alias": alias, "rows": rows} for (entity, alias), rows in sorted(generic.items())
        ],
        "flagged": {
            group: {"analyses": len(slot["analyses"]), "rows": slot["rows"]} for group, slot in sorted(flagged.items())
        },
        "withholding": dict(sorted(withholding.items())),
        "largest_withholding_moves": {"down": [key for _, key in moves[:10]], "up": [key for _, key in moves[-10:][::-1]]},
    }


def _print_comparison(report: dict) -> None:
    print(f"classification {report['before_version']} -> {report['after_version']}; accounts compared: "
          f"{report['accounts_compared']}; unmatched: {report['accounts_unmatched']}")
    print(f"lenders gained: {len(report['gained'])}")
    for entity, slot in report["gained"].items():
        note = "" if slot["admitted"] else "  NOT AN ADMITTED LENDER IN THE LEDGER"
        print(f"  + {entity}: {slot['analyses']} analyses, {slot['rows']} rows{note}")
    print(f"lenders lost: {len(report['lost'])}")
    for entity, slot in report["lost"].items():
        now = ", ".join(f"{state} {count}" for state, count in sorted(slot["rows_now"].items()))
        print(f"  - {entity}: {slot['analyses']} analyses; rows now: {now}")
    print(f"lenders gained through a generic word: {len(report['gained_through_generic_words'])}")
    for entry in report["gained_through_generic_words"]:
        print(f"  ! {entry['entity']} via {entry['alias']!r}: {entry['rows']} rows")
    print("flagged groups: " + ", ".join(
        f"{group} {slot['analyses']} analyses/{slot['rows']} rows" for group, slot in report["flagged"].items()
    ))
    print("withholding rate: " + ", ".join(f"{name} {count}" for name, count in report["withholding"].items()))


def _use_code_root(code_root: Path) -> bool:
    """Put the checkout's `analysis` package first on sys.path; False if another one is already loaded."""
    sys.path.insert(0, str(code_root.resolve()))
    import analysis

    return Path(analysis.__file__).resolve().is_relative_to(code_root.resolve())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot", help="re-classify the cache with one checkout's code")
    snap.add_argument("--data-dir", type=Path, required=True, help="the webapp data directory (read-only)")
    snap.add_argument("--out", type=Path, required=True, help="the snapshot to write (outside the repo)")
    snap.add_argument("--code-root", type=Path, default=ROOT, help="the checkout whose analysis package classifies")
    snap.add_argument("--limit", type=int, default=None, help="read only the first N analyses")
    comp = commands.add_parser("compare", help="compare a before and an after snapshot")
    comp.add_argument("--before", type=Path, required=True)
    comp.add_argument("--after", type=Path, required=True)
    comp.add_argument("--out", type=Path, required=True, help="the comparison to write (outside the repo)")
    comp.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="the C10 registry ledger (JSON)")
    args = parser.parse_args(argv)

    if _inside(args.out, ROOT):
        print(f"refused: {args.out} is inside the repository; the census holds statement figures", file=sys.stderr)
        return 2
    if args.command == "snapshot":
        if not (args.data_dir / "webapp.db").is_file():
            print(f"refused: {args.data_dir} holds no webapp.db", file=sys.stderr)
            return 2
        if not _use_code_root(args.code_root):
            print(f"refused: another analysis package is already loaded, not {args.code_root}", file=sys.stderr)
            return 2
        result = snapshot(cached_accounts(args.data_dir, args.limit))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result) + "\n", encoding="utf-8")
        print(f"classification {result['classification_version']}: {len(result['accounts'])} accounts; "
              f"skipped: {sum(result['skipped'].values())}")
        return 0
    try:
        admitted = admitted_lenders(json.loads(args.ledger.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        print(f"refused: {args.ledger} is not a readable C10 ledger ({error})", file=sys.stderr)
        return 2
    # `compare` loads no other checkout, so this one's registry may be imported here.
    from analysis.classification_registry import MERGED_REGISTRY_ENTITIES

    report = compare(
        json.loads(args.before.read_text(encoding="utf-8")),
        json.loads(args.after.read_text(encoding="utf-8")),
        admitted,
        merged=MERGED_REGISTRY_ENTITIES,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print_comparison(report)
    failed = report["gained_through_generic_words"] or not all(slot["admitted"] for slot in report["gained"].values())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_lender_census.py tests/test_no_statement_hardcodes.py -q -p no:cacheprovider`
Expected: PASS (16 census tests), except the known pre-existing `test_no_literal_account_numbers_in_ocr`.

- [ ] **Step 5: Smoke-run it on 60 cached analyses** (read-only; nothing is committed). In PowerShell, from the repository root of `ld-s2-classifier`:

```powershell
$local = "C:\Users\GustavoPrietodePaula\AppData\Local\Temp\lender-s2-census"
$webappData = "C:\Users\GustavoPrietodePaula\OneDrive - Capital Infusion\Desktop\Capital Infusion Projects\bankStatementAnalysis\webapp_data"
New-Item -ItemType Directory -Force $local | Out-Null
git worktree add --detach "$local\before" lender-detection
C:\Python314\python.exe -m tools.lender_census snapshot --data-dir $webappData --out "$local\before.json" --code-root "$local\before" --limit 60
C:\Python314\python.exe -m tools.lender_census snapshot --data-dir $webappData --out "$local\after.json" --limit 60
C:\Python314\python.exe -m tools.lender_census compare --before "$local\before.json" --after "$local\after.json" --out "$local\compare.json"
git worktree remove "$local\before"
```

Expected: the two snapshot lines read `classification 4.1: N accounts` and `classification 5.0: N accounts` with the same N (60 in the dry run, which took under 10 s per snapshot; a cached document with several accounts adds one per account), and `compare` prints its summary: the first line reads `classification 4.1 -> 5.0; accounts compared: N; unmatched: 0`, then `lenders gained through a generic word: 0`, and the exit code is 0.
- `compare` reads the C10 ledger of this checkout (`docs/lender-registry-ledger.json`, which S1 merged).
- The pre-C10 dry run printed the same summary and exit code 0 against the evidence document that S1's builder rendered then. Against C10's ledger, a gained lender passes only when the ledger admits it as a `confirmed_lender`.
- Report the exit code and the summary's counts only (not the gained or lost names) to the orchestrator.
- A `NOT AN ADMITTED LENDER IN THE LEDGER` line, or a generic-word gain, is a finding for the orchestrator (a ledger question). S2 does not fix it. The full run (no `--limit`, about 20 minutes per snapshot) is the orchestrator's, after S2 merges (master plan step 4).
- The owner decisions of 2026-09-25 move these lines of the full run (s2 amendments, section D):
  - **Renamed funders.** Torro Funding LLC, Sheaves Capital, 2M7 Financial Solutions and Iruka Capital Group LLC appear as admitted gains, with their old names lost. So does Rockstone Funding Group Inc, which takes Credora Capital's rows.
  - **The merge.** EBF HOLDINGS is silent: `compare` reads it as EVEREST BUSINESS FUNDING.
  - **Lenders lost to flagged groups.** CAPITAL INFUSION (0 cached rows), AFC FUNDING CORP (Floor plan), LADCO Leasing and Finova's lease product (Leases & rentals).
  - **Revenue.** It rises in PAYABILITY's 12 analyses, whose payout credits are revenue now. Legacy eligible deposits drop in the 79 analyses whose `LOAN CREDIT` rows are bank-line proceeds, so withholding goes up there.
  - **Fees.** Overdraft charges become fees (228 debits in 52 analyses).
  - **Premium financing.** FIRST INSURANCE rows are flagged premium financing (159 debits in 129 analyses). 3 of them are the bank's overdraft fee for a FIRST INSURANCE item (see the self-review, item 12).
  - **The review tier.** It gains MERCH PAD, ACCOUNT SERVICIN[G] and TFG. It loses PAID TO TILT, PULL TILT and PULL DAVE to admitted personal loans, and ALBERT DES EDI PYMNTS, whose rows are now unflagged.

- [ ] **Step 6: Commit.**

```
git add tools/lender_census.py tests/test_lender_census.py
git commit -m "tools: before/after lender census over the local artifact cache" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 16: Documentation

**Files:**
- Modify: `docs/transaction-classification.md` (whole file)
- Modify: `docs/moneythumb-replacement/R1_HARDCODE_LOG.md` (insert after `:160`)

**Interfaces:**
- Consumes: the behavior of Tasks 2-12.
- Produces: the written contract for classification version 5.0 and the Item 12a amendment.

- [ ] **Step 1: Replace** `docs/transaction-classification.md` with:

````markdown
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
`confirmed_lender`. Eleven groups are flagged instead. They never enter lender
counts, lender totals, withholding, eligible deposits or potential exposure:

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

The group list lives in `analysis/flag_groups.py`. A flagged row carries
`flagged_group`; a posted flagged debit also sets
`contributes_to_flagged_totals`, which proven duplicates and settlement-reversed
debits clear. The web app hides unticked groups at serving time; the stored
record never changes.

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
   `Insurance provider not identified`. A premium-finance credit is treated as
   any insurance credit.
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
   mortgages, personal loans, floor plan, factoring) is financing proceeds:
   `other`, revenue `non_revenue`, excluded from eligible deposits (D1). The
   exception is a payout-credit entity (`PAYOUT_CREDIT_ENTITIES`, owner ruling),
   whose credits are the account holder's own sales and stay revenue; its
   debits keep its group. Three credits are proceeds by their own words: the
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
`potential_lender`, review only, two kinds of same-amount debit groups with at
least three rows on a daily or weekly cadence: financing-keyword rows of one
payee (`recurring_financing_counterparty`), and rows no rule claimed (`other`,
match method `default`) whose descriptor names a payee and carries no transfer
wording (`recurring_fixed_debit`, D6). Recurrence never makes a counted lender:
nothing is counted without a named lender. The recurring-debit view
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
- `flagged_groups`: per flagged group key, `{count, total, payees}` over rows
  marked `contributes_to_flagged_totals`; only groups with a contributing row
  appear, in flag-group order. It never feeds lender, withholding,
  eligible-deposit or potential figures.
- `detection.flagged_positions`: one entry per flagged group and payee (`group`,
  `payee`, `matched_alias`, `count`, `total_debited`, `cadence`,
  `avg_gap_days`, `first_date`, `last_date`, `source_locations`), in flag-group
  order, then by total. The payee is the canonical entity, or the group label
  when the descriptor names none; the cadence (`daily`, `weekly`, `biweekly`,
  `monthly`, `irregular` or `single`) comes from
  `analysis.cadence.describe_cadence`.
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
lines of credit, bank loans, vehicle financing, mortgages, personal loans, floor
plan and factoring).
They are excluded because they are financing proceeds, not operating deposits.
D1 reads the payee registries, except a payout-credit entity
(`PAYOUT_CREDIT_ENTITIES`), whose credits are the account holder's own sales and
stay in eligible deposits. It also reads three descriptors: the statement bank's
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

Add provider and counterparty knowledge in `analysis/classification_registry.py`:
lenders (MCA funders and equipment financing) in `LENDER_ALIASES`; each flagged
group in its own table, listed in `PAYEE_GROUP_REGISTRIES`; premium-finance
payees in `PREMIUM_FINANCE_ALIASES`, which only the insurance rule reads; banks
for the D5 bank-loan rule in `BANK_NAME_ALIASES`; card issuers that need
payment wording in `CARD_ISSUER_CONTEXT_ALIASES`; financing-group payees whose
credits are the holder's own sales in `PAYOUT_CREDIT_ENTITIES` (owner ruling
only). An alias names the financing business, never a
bare platform or a brand that also sells goods. Cover aliases, OCR variants,
token boundaries, precedence, both directions, and contribution flags in tests.
Do not add statement-specific description checks in parsers, metrics, API
routes, or frontend code.
````

- [ ] **Step 2: Amend Item 12a.** In `docs/moneythumb-replacement/R1_HARDCODE_LOG.md`, directly after the line `  is asserted non-lender.` (`:160`), insert:

```markdown
- **Amended 2026-09-24 and 2026-09-25 (owner rulings, lender-detection design §2):**
  `INTUIT FINANCING` is no longer a lender. It moved from the lender registry
  to `ALTERNATIVE_POSITION_ALIASES` and is classified `alternative_position`:
  a flagged position, outside lender count, lender totals and withholding. The
  two-word alias and the negative software case are unchanged; the fixture now
  asserts `alternative_position`. `AFC FUNDING CORP` moved to Floor plan (owner
  ruling 2026-09-25): it is not a lender, and it is flagged like an alternative
  position. Its fixture now asserts `floor_plan_financing`.
```

- [ ] **Step 3: Check the docs name only real code.**

Run: `git grep -n "lease_or_equipment_financing\|NON_MCA_SCOPE\|LEASE_PROVIDER_ALIASES\|LEGACY_" -- docs/transaction-classification.md`
Expected: exactly one line, the retired-state sentence for `lease_or_equipment_financing`.

- [ ] **Step 4: Commit.**

```
git add docs/transaction-classification.md docs/moneythumb-replacement/R1_HARDCODE_LOG.md
git commit -m "docs: classification contract 5.0 and the Item 12a rulings" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 17: Verification before handing back (no commit unless a fix is needed)

**Files:**
- Create (scratch, never committed): `<your scratchpad>/s2_speed.py`, `<your scratchpad>/s2_reach.py`

**Interfaces:**
- Consumes: the whole branch; `synthetic_statement` (Task 3).
- Produces: the evidence for the orchestrator's review.

- [ ] **Step 1: Run the S2 tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_cadence.py tests/test_flag_group_states.py tests/test_classifier_lookups.py tests/test_financing_proceeds_credits.py tests/test_known_payee_classification.py tests/test_premium_financing.py tests/test_obligation_descriptors.py tests/test_unknown_payee_naming.py tests/test_recurring_fixed_debits.py tests/test_flagged_positions_payload.py tests/test_lender_census.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 2: Run the three orchestrator selections and S1's tests.**

Run the Core, Guards/JS and Wider commands from Task 0 Step 2, then S1's tests: the `$s1Tests = ...` line and the `pytest $s1Tests` line of Task 6 Step 4. That list includes S1's alias-audit and C10 drift tests.
Expected: PASS, except the known pre-existing `tests/test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`; S1's legacy-list checks skip by design. The JS harness tests need `node` on PATH; if they skip, say so in the report.

- [ ] **Step 3: Measure the speed** with `<your scratchpad>/s2_speed.py`:

```python
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from analysis.transaction_classifier import classify_statement_transactions  # noqa: E402
from tests.test_classifier_lookups import synthetic_statement  # noqa: E402

statement = synthetic_statement()
classify_statement_transactions(statement)  # warm the compiled indexes
timings = []
for _ in range(5):
    start = time.perf_counter()
    classify_statement_transactions(statement)
    timings.append(time.perf_counter() - start)
best = min(timings)
print(f"300-row synthetic statement: {best:.3f} s (target <= 0.319 s: 10x under the 3.19 s measured 2026-09-24)")
```
Run: `C:\Python314\python.exe <your scratchpad>\s2_speed.py`
Expected: at most 0.319 s. Report the number either way. The absolute figure moves with host load: the 2026-09-24 dry run read 0.21-0.52 s on a busy host with a naive stand-in matcher. If it prints more than 0.319 s, re-run it when no other test run is active, and report both numbers.

Then run S1's relative benchmark, which times today's matcher against the compiled one on the same host in the same run:
`C:\Python314\python.exe -m pytest tests/test_classifier_speed.py -q -p no:cacheprovider`
Expected: PASS. If the file does not exist on your tree, run S1's speed test from the Task 6 Step 4 list (`$s1Tests`) under the name S1 gave it, and name it in the report.

- [ ] **Step 4: Scan what the branch adds for statement values.**

Run: `git log lender-detection..HEAD --format=%B`
Expected: no money figure, account number, date or payee from a statement in any message.

Run: `git diff lender-detection...HEAD -U0 -- tests | findstr /R "^+.*[0-9][0-9]*\.[0-9][0-9]"` (or the `grep -nE '^\+.*[0-9]+\.[0-9]{2}'` equivalent)
Expected: every figure with cents on an added line is one of these (the dry run's diff added the first list's figures of 2026-09-24/25; the owner decisions of 2026-09-25 added the rest):
- derived totals from the pin ledger: `3178.19`, `59310.74` and `16898.73` (unchanged denominators on rewritten lines), `5.36`, `8658.91`, `0.00`, and `1299.00` or, in the bank-name variant, `108.00`; since the 2026-09-25 decisions also `9757.26` (ATB November's lenders), `2606.31` (MERCH PAD's ATB November rows), `13.23` (TD CMCA's withholding) and `15.74` (the Audit Bank fixture's withholding);
- whole-dollar fabricated figures written with cents: `100.00` (the benchmark test), `1,400.00` and `2,400.00` (the `analyze.py` report test);
- a value S2 moved without changing it, if the diff shows the line as added: `-632.24`, `-37.10`, `571.88` and `-571.88`, `-4229.99` (the AFC Funding fixture), `-370.17` (the automatic loan payment fixture) and `-111.75` (TD CMCA's CMCA Finance rows).

Anything else: **stop and report** the file and line to the orchestrator. Never delete an assertion to clear the scan.

- [ ] **Step 5: Measure D6's reach on the unpinned statements** with `<your scratchpad>/s2_reach.py` (counts only):

```python
"""Counts only: potential rows by match method and lender rows on the real statements no test pins for them."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from tests.test_revenue_classification import _atb_december_report  # noqa: E402
from tests.test_transaction_classifier import _real_statement_report  # noqa: E402

for label, make in (
    ("ATB Aug", lambda: _real_statement_report("ATB/ATB August 2023.pdf")),
    ("ATB Dec", _atb_december_report),
    ("RBC Jan", lambda: _real_statement_report("RBC/Chequing Statement-JAN+.pdf")),
):
    report = make()
    potential = Counter(r.match_method for r in report.classifications if r.contributes_to_potential_lender_totals)
    unnamed = sum(
        1 for r in report.classifications
        if r.contributes_to_potential_lender_totals and r.canonical_entity == "Unidentified lender obligation"
    )
    print(f"{label}: potential rows by method {dict(sorted(potential.items()))}; unnamed {unnamed}; "
          f"lender rows {report.metrics.lender_debit_count}")
```
Run: `C:\Python314\python.exe <your scratchpad>\s2_reach.py`
Expected (probe of 2026-09-26 on the revised ledger, counts only): on ATB Aug and ATB Dec, the fixed daily debits that the 2026-09-24 dry run's D6 promoted (22 and 19) are MERCH PAD's review alias. They show as `candidate_lender_alias`, not `recurring_fixed_debit`, and are not unnamed; ATB Aug also shows its `LOANS FC` row as `candidate_lender_alias`. On RBC Jan, `recurring_fixed_debit` is 6, every one unnamed, and the lender rows are 5. These are review rows no test pins; the owner sees them before merge.

- [ ] **Step 6: Report to the orchestrator.** Include:
  - the Task 0 printout (FAIL-free) and the variant it selected (pin-ledger row 15);
  - the three selection results and S1's test result;
  - the speed number and S1's benchmark result;
  - the Task 15 smoke-run summary counts and exit code;
  - the Step 5 counts, marked "for the owner: D6 review rows on statements no test pins";
  - the list of commits.

---

## Self-Review

**Spec coverage (the sections S2 owns):**
- **§2, with the owner's amendment** (floor plan, factoring, premium financing):
  - the two new states, and every group loop over `FLAG_GROUPS` (Task 2);
  - floor-plan and factoring payees through the matcher, fake and owner-named: credits in Task 4, debits in Task 5;
  - premium financing stays insurance and carries its flag (Task 7);
  - its metrics and position (Tasks 11 and 12), the census groups (Task 15) and the docs table (Task 16).
- **§4.1 states:** Task 2 adds the nine states. `credit_card_payment` is kept. `lease_or_equipment_financing` is retained but never produced; Task 8 proves "never produced".
- **§4.2 fields:**
  - Task 2: `flagged_group`, `contributes_to_flagged_totals`, and the clearing for duplicates and settlement reversals; the table keys come from C1.
  - Task 7: premium financing, the one flag group that is not a state.
- **§4.3 rule order:**
  - Steps 1-3 are unchanged (Task 5 code). Step 4 is insurance, with premium finance looked up first, and premium-finance wording (Task 7).
  - Step 5: D8, POS and ATM skip a known payee, except an alternative position's membership or balance top-up (Task 5). Step 6 gains the overdraft-charge fee (Task 5).
  - Step 7: the known payee and the D9 LOC override (Task 5); a financing payee's credit is proceeds, except a payout-credit entity's, and three descriptors are proceeds too (Task 4).
  - Step 8 (Task 8, and the unnamed loan payment in Task 9): the own-account guard, floor-plan payoffs, LOC, mortgage with home-equity loans, vehicle, student loans, D5 bank name (with `PRET`) or own-loan transfer, another bank's unnamed loan, the statement bank's own English, billing and French loan wording, the unnamed loan payment, lease/rental, cards widened through `CARD_ISSUER_CONTEXT_ALIASES` and the decisions' card forms, and D4.
  - Step 9: rent (D3, Task 8 test). Step 10: check and subscription (Task 5; a known payee now wins over a check).
  - Step 11: the potential rules, with D11 naming and D10 servicers, `MCA SERVICING` included (Task 9).
  - Statement passes: duplicates; recurrence plus D6, and the recurring-debit view (Task 10); reversal pairs and duplicate finalisation, which clear the flag (Task 2, and Task 7 for premium financing); operating-source context through `registry_match` (Task 3).
- **§4.4 credits** (Task 4):
  - `_classify_credit_revenue` checks `FINANCING_STATES` payees before the operating registry; these include floor plan and factoring.
  - `classify_transaction` gives the C4 record with `contributes_to_lender_credit_exclusion`.
  - Owner decisions of 2026-09-25: a payout-credit entity's credits stay revenue (`PAYOUT_CREDIT_ENTITIES`), and the bank's own line advance, a line-of-credit draw and a per-vehicle floor-plan advance are proceeds by their own words.
  - Platform settlements stay revenue: the existing `tests/test_revenue_classification.py:440-523`, plus the new Square/Shopify test.
  - Premium-finance credits keep the insurance credit treatment (Task 7).
- **§4.5 potential tier:** D11 naming (Task 9), D6 (Task 10), D10 (Task 9).
- **§4.6 speed (S2's share):** every classifier lookup goes through the compiled index, one normalization per row (Task 3); measured in Task 17 with S1's relative benchmark.
- **§6 payload:** `metrics.flagged_groups` (Task 11), `detection.flagged_positions` and `FlaggedPositionMatch` (Task 12), `describe_cadence` (Task 1), versions 5.0 / 19 with the cache pin (Task 2).
- **§7:**
  - `batch.py` column and `analyze.py` block (Task 13); the recurring-debit view now includes D6 rows (Task 10);
  - benchmark flagged scope replacing `NON_MCA_SCOPE` (Task 14);
  - `docs/transaction-classification.md` and the R1 log amendment (Task 16);
  - `analysis/lenders.py` needs no edit (it reads the C2 compatibility name); Task 5 guards its helpers.
- **§9 proof items:**
  - classification tables for every group in both directions (Tasks 4, 5, 7, 8);
  - the D8/D9/D5/D4/D6/D11 tests;
  - credit proceeds and platform revenue (Task 4);
  - the pins that move (pin ledger, with one pre-measured variant);
  - the before/after census `tools/lender_census.py` (Task 15), which reports acceptance criteria 1, 2 and 5 and exits non-zero on 1 or 5. It checks criterion 1 against the C10 ledger's admitted lenders. Criterion 3 is S1's alias audit, and criterion 4 is the owner's NMEF probe (master plan step 4); the full census run is the orchestrator's;
  - the speed evidence (Task 3 normalization count, Task 17 measurement and S1's relative benchmark).

**Placeholder scan:**
- Every code step shows the full code, and every run step names the command and the expected result.
- There is no "TBD", "TODO" or "similar to Task N".
- The conditional steps each state the check that decides them and give the concrete outcomes:
  - Task 3 Step 6 (an S1 test file that does not exist);
  - Task 6 Step 4 (S1's test files come from `git diff --diff-filter=A`, and an empty list stops the step);
  - Task 4 Step 9 (the NETCREDIT line, only if S1 changed it);
  - Task 6 Steps 2-3 (which retired tables S1 left);
  - Task 8 Step 11 and Task 10 Step 8 (navigant's bank-name variant).
- The only value the executor supplies at run time is the committing session's URL in the `Claude-Session` line (Global Constraints, Commits).

**Contract-name consistency:**
- **C1 names used:** the `FlagGroup` fields via `FLAG_GROUPS` (including the stateless `premium_financing` group), `FLAG_GROUP_BY_STATE`, `FLAG_GROUP_BY_KEY` and `FINANCING_STATES`. `FLAG_SETTING_KEYS` appears only in the Task 0 import check.
- **C2 names used:**
  - `PAYEE_GROUP_REGISTRIES`, in the amended order with `floor_plan_financing` and `factoring`;
  - `PREMIUM_FINANCE_ALIASES`, read only by the insurance rule, never as a group registry;
  - `BANK_NAME_ALIASES` and `CARD_ISSUER_CONTEXT_ALIASES` (step 8 only), `POTENTIAL_LENDER_ALIASES`, `INSURANCE_PROVIDER_ALIASES`, `OPERATING_REVENUE_SOURCE_ALIASES`, `OPERATING_REVENUE_SOURCE_TYPES`;
  - the existing `BANK_SPECIFIC_LENDER_ALIASES`;
  - `CONFIRMED_LENDER_ALIASES`, only through `analysis/lenders.py` (unchanged) and Task 0's identity check;
  - `FLOOR_PLAN_ALIASES`, `FACTORING_ALIASES` and every other table name in Task 0's existence check;
  - S1's owner-ruling constants of 2026-09-25: `PAYOUT_CREDIT_ENTITIES` (Tasks 4 and 5) and `MERGED_REGISTRY_ENTITIES` (the census, Task 15). `PREMIUM_FINANCE_INSURER_ALIASES` and `REATTRIBUTED_REGISTRY_ALIASES` are read only by S1's validator; S2 relies on their effect (facts 1 and 4).
- **C3 names used:** `match_known_payee`, `registry_match` and `PayeeMatch(entity, state, alias)`. `AliasIndex` appears only in the Task 0 import check.
- **C4:**
  - the nine states and `flagged_group`, `contributes_to_flagged_totals`;
  - premium financing: `classification="insurance"`, `flagged_group="premium_financing"`, contributing on posted debits only;
  - the financing-proceeds credit: `classification="other"`, `matched_rule="financing_proceeds_credit"`, `revenue_match_method="financing_proceeds_credit"`, `contributes_to_lender_credit_exclusion=True`;
  - `CLASSIFICATION_VERSION = "5.0"`.
- **C5:** the `metrics.flagged_groups` shape and ordering; the `detection.flagged_positions` keys and sort order; `describe_cadence(dates) -> tuple[str, float | None]` with its six values.
- **Names this plan defines and later tasks use:**
  - `_ACH_TOKEN` and the test helper `synthetic_statement` (Task 3; Task 17 uses the helper);
  - `_state_words`, `_financing_proceeds_payee`, `_descriptor_proceeds`, `_financing_proceeds_credit_record` and `_descriptor_proceeds_credit_record` (Task 4; used in Tasks 5 and 8);
  - `_LINE_OF_CREDIT_PATTERNS`, `_known_payee_debit_record` and `_is_membership_or_top_up` (Task 5; Task 8 reuses the patterns);
  - `_insurance_registry_match`, `_PREMIUM_FINANCE_WORDING_PATTERNS` and the `_build_record(..., flagged_group=...)` keyword (Task 7);
  - `UNIDENTIFIED_LENDER_OBLIGATION`, `_obligation_fields` and `_descriptor_obligation` (Task 8, used in Tasks 9 and 10);
  - `_unknown_payee_tokens` / `_unknown_payee_name` (Task 9, used in Task 10; the unnamed loan payment of step 8 reads the tokens);
  - `_RECURRING_MATCH_METHODS` (Task 10);
  - `flagged_payee` (Task 11, used in Task 12);
  - `FlaggedPositionMatch` / `find_flagged_positions` (Task 12, used in Task 13);
  - `flagged_lender_groups` (Task 14);
  - `DEFAULT_LEDGER`, `GENERIC_WORDS`, `admitted_lenders`, `cached_accounts`, `account_snapshot`, `snapshot`, `compare`, `main` (Task 15);
  - the test helpers in `tests/flag_group_fixtures.py`: `txn` (Task 2); `FAKE_PAYEES`, `fake_match`, `fake_payees` (Task 4; used in Tasks 5, 11, 12, 13 and 15); `fake_premium_finance` (Task 7; used in Tasks 11 and 12); `FLAGGED_ROWS`, `FLAGGED_GROUPS_EXPECTED`, `flagged_statement` (Task 11); `flagged_report` (Task 12; used in Task 13);
  - `PREMIUM_ROWS` in `tests/test_flagged_positions_payload.py` (Task 11, used in Task 12).

**Ambiguities this plan resolved (for the orchestrator):**
1. `describe_cadence` returns `"single"` for fewer than two distinct dates. C5 lists that value; §6 does not.
2. **Retired tables.** C2 says `LEASE_PROVIDER_ALIASES` is removed. The pre-C10 S1 plan kept it, and also `LEGACY_CONFIRMED_LENDER_ALIASES` and `LEGACY_POTENTIAL_LENDER_ALIASES`, until S2 rewires the classifier, and left all three for S2 to delete. Task 6 deletes whichever are present, outside the block S1 renders from the C10 ledger. S1's legacy-list tests skip by design once they are gone.
3. **Step-8 descriptors apply to debits only.** Today's card and lease patterns also tagged credits. D1 says the card and lease lists never apply to credits, and this rule keeps `flagged_group` off credits, so no credit shows a "Flagged" chip. A lease or rental payee's credit therefore loses today's lease credit exclusion and is reviewed like any other credit (D1's last sentence).
4. **D6 promotes only rows no rule claimed** (`other` with match method `default`), and it skips rows with transfer wording (TRANSFER/XFER/TFR). Without that skip, TD's `TFR TO` rows would join the review tier and move a pinned potential count.
5. **D6's reach.** In the dry run it moved two pinned statements the tests map did not foresee: ATB November potential (1 row → 22; 3178.19; exposure 5.36) and navigant (1 row → 4; 1299.00, or 3 rows and 108.00 in the bank-name variant). It also added review rows no test pins, all named `Unidentified lender obligation`: 22 on ATB Aug, 19 on ATB Dec and 6 on RBC Jan. On the revised C10 ledger (probe of 2026-09-26), ATB's fixed daily debits are MERCH PAD's review alias. The potential registry claims them at step 11, in Task 5, before D6 runs. So ATB November's 22 / 3178.19 / 5.36 is pinned in Task 5 as two review entities (MERCH PAD and LOANS FC), and D6 is left with navigant's 3 rows and RBC Jan's 6. Task 17 Step 5 re-measures the unpinned statements for the owner before merge.
6. **"AUTO … PAYMENT" (step 8)** is read as AUTO LOAN/LEASE/FINANCE and VEHICLE PAYMENT. A bare "AUTO PAYMENT" is autopay wording and stays unflagged.
7. **Transfers stay ahead of the own-bank loan transfer.** The spec puts transfers at step 6 and the own-bank loan transfer at step 8, so "ONLINE TRANSFER TO LOAN" stays `transfer` and only a plain "TRANSFER TO LOAN" becomes a bank loan. This is raised for the owner rather than changed.
8. **"A registry-style company token"** is read as a legal-form suffix (CORPORATION, COMPANY, INCORPORATED, LTD, LIMITED, LP, LLP, PLLC). Leading financing words are dropped from names, so "ADVANCE PAYMENT <person>" never publishes the person.
9. **Version bump.** The bump rides the first commit that changes output (Task 2). Later S2 commits share stage 19, because the branch merges as one unit.
10. **One lookup per credit.** A credit uses the single longest-alias lookup. If a credit's longest alias is a card or lease alias, it falls through even when a shorter financing alias also matches. This edge was accepted rather than building a second index.
11. **Alias prefixes.** The spec's order puts the known-payee matcher (step 7) ahead of rent, card patterns, checks and subscriptions, so a lender alias that is a prefix of another business takes that business's rows. Today's `ACH CAPITAL` is one (Prerequisite 5). Fixing an alias is a change to the C10 ledger, with S1's collision audit (§5) as the evidence. Task 0 stops if the pinned rows show one.
12. **Premium financing (amendment):**
    - The insurance rule looks up `PREMIUM_FINANCE_ALIASES` before `INSURANCE_PROVIDER_ALIASES`. A premium financier whose name contains an insurer's name (`FIRST INSURANCE FUNDING` against `FIRST INSURANCE`) is therefore the premium financier, and a premium-finance payee is insurance even when its descriptor has no insurance word.
    - **Rows that name only the insurer.** Before 2026-09-25 they stayed plain insurance. That no longer holds for the bare `FIRST INSURANCE`: the owner ruled that this ACH company name is FIRST Insurance Funding. `FIRST INSURANCE` is now also a premium-finance alias of that entity (S1's `PREMIUM_FINANCE_INSURER_ALIASES`), so its rows stay insurance and are flagged premium financing (159 cache debits in 129 analyses). The hand-kept insurer `First Insurance` is unchanged and no longer claims such a row. The longer Canadian spellings stay with FIRST Insurance Funding of Canada.
    - **Residual, accepted.** 3 of those 159 rows (3 analyses) are the statement bank's overdraft fee for a `FIRST INSURANCE` item: the fee row prints the item's originator. They were `insurance` already, because the insurance rule (step 4) runs before the fee rule (step 6), and now they also carry the flag. No ledger spelling separates them, and a wording exception inside the insurance rule would need exact fee wording that no probe has measured. S2 accepts the 3 rows, and the census shows them. Rows of other groups are not affected this way: their item-fee rows stay `fee`, because step 6 runs before step 7.
    - **Premium-finance wording** (owner decision 2026-09-25). A row with `PREM FIN`, `PREMIUM FINANCE` or `INSPREMFIN` and no premium-finance alias is premium financing: 6 cache debits in 6 analyses, `insurance` today by the term rule. Its entity is the insurer the descriptor names, else `Insurance provider not identified`. The rule is read by `classify_transaction` only, so a credit's revenue treatment does not move.
    - The record keeps `match_method="insurance_provider_alias"` and gets `matched_rule="premium_finance_provider"` (or `"premium_finance_descriptor"` for the wording); C4 names none of these values.
    - `flagged_group="premium_financing"` is set on debits only, as for every other group (item 3). A premium-finance credit carries no flag and keeps the insurance credit exclusion, which is "today's insurance treatment" in §4.2.
    - S3's conformance test (the S3 task "Conformance with S2's real payload, and the re-run after S2") builds such a row from the first `PREMIUM_FINANCE_ALIASES` alias, and a floor-plan and a factoring row from the first alias of their tables. The dry run classified all six of its rows as S3 expects. Those rows exist only if the C10 ledger admits a payee in each table (Prerequisite 1).
13. **Floor plan and factoring take no descriptor rule.** The amendment adds registries only; spec §4.3 step 8 is unchanged. D9's LOC override still covers only lenders, alternative positions and lines of credit, so a floor-plan payee with LOC wording stays floor plan (a Task 5 test pins this).
14. **S1's classifier imports.** S1 adds `from .description_text import normalize_transaction_description` and `from .payee_matcher import registry_match` after the registry and revenue imports (the pre-C10 S1 tree did; Task 0's anchor lines check it on the merged tree). Task 4 widens the second line to `PayeeMatch, match_known_payee, registry_match`, and Task 5 replaces only the `from .classification_registry import (...)` block, so the classifier imports the matcher once.
15. **D1 reaches registry payees, and three descriptors the owner ruled.** C4 and §4.4 make a credit proceeds when its payee is in a `FINANCING_STATES` registry. No registry holds banks (`BANK_NAME_ALIASES` is D5's debit rule), so no credit is bank-loan proceeds by payee. This plan routed the extension to unnamed credits to the owner, because it moves eligible deposits (the withholding denominator), which §11 keeps out of scope. The owner decided it on 2026-09-25 for three exact descriptors only, which Task 4 builds:
    - the statement bank's own line advance (exactly `LOAN CREDIT`: 368 cache credits in 79 analyses, `non_revenue` today, so revenue does not move while legacy eligible deposits drop there);
    - a line-of-credit draw (`LOC ADVANCE`, `ADVANCE FROM LINE OF CREDIT` and the like: 8 credits, unverified deposits today);
    - a per-vehicle floor-plan advance (`ADVANCE`, a model year, `VIN`: 54 credits of one dealer).

    Any other unnamed credit keeps today's revenue rule: "LOAN PROCEEDS" stays `non_revenue` by the strong non-revenue rule without the eligible-deposit exclusion. The same day the owner narrowed D1 once: a payout-credit entity's credits (`PAYOUT_CREDIT_ENTITIES`) are the holder's own sales and stay revenue (Sezzle 140 cache credits, American First Finance 3, PAYABILITY 174). The residual the checkers noted: a merchant paid out by another BNPL platform (Klarna, Credit Key) would still have its settlements made proceeds. No such credit is in the corpus, and adding one is an owner ruling in S1's constant, not an S2 change.
16. **The recurring-debit view groups by entity and amount**, as before. Two D6 groups that are both `Unidentified lender obligation` with the same amount show as one recurring line; the classification records stay separate.
17. **The census compares by account and row position.** Both snapshots read the same cached payload, so a row keeps its index; an account whose row count differs between the two is reported as unmatched, never guessed.
18. **C10, the curated registry ledger.** It changes how S1 fills the C2 tables, not their names or C3, so no classifier, metrics or payload code changes. It changes three things in this plan:
    - **Prerequisites are ledger content.** S2's facts about entities, groups, aliases and `entity` spellings are now facts about `docs/lender-registry-ledger.json`. S1's validator, normative for the ledger per the master plan's C10, requires every owner-named payee of spec §2 in its group; Task 0 checks the facts it does not cover ("Why Task 0 checks more than C10's validator"). Two lines were added: the ledger is schema 1, and the lender table's entities are its admitted `confirmed_lender` entities. The latter is S2's reading that each table is keyed by the ledger's `entity`.
    - **The census reads the ledger's JSON.** Spec §9's "traces to an admitted ledger entity" is checked against `status` and `group`, not as a substring of the rendered evidence document. That document also names entities that are in no table, such as those awaiting an owner ruling.
    - **S2 never edits the ledger or the rendered block.** A failed content fact goes to the orchestrator.
19. **The owner-delegated decisions of 2026-09-25.** The owner delegated every open ledger question to the orchestrator, whose decisions are owner rulings. They move this plan in four ways.
    - **Facts and Task 0.** Facts 3, 4, 6, 8 and 9 were re-pinned and fact 10 added. `EXPECTED` holds the measurements on the revised ledger. relay's reach is exact now, no longer a variant.
    - **Pins.** Pin-ledger rows 1, 9-12, 14, 15 and 17 changed, and rows 18-25 are new. Some of them move because of C10 ledger content that predates these decisions: the `LOANS FC` review entity (row 20, and ATB November's candidate) and relay's personal-loan payees.
    - **New rules.** They are placed where the spec's rule order puts them:
      - payout credits and three descriptor credits (Task 4);
      - the overdraft-charge fee and the membership/top-up exception (Task 5);
      - premium-finance wording (Task 7);
      - the step-8 rules and card forms (Task 8), with the unnamed loan payment (Task 9);
      - `MCA SERVICING` as a servicer (Task 9);
      - the census reading a merge as one lender (Task 15).
    - **Choices made in writing them:**
      - **The membership/top-up exception reads the matched alias.** The decision names Klarna Inc. The rule keeps payee names out of the classifier, so it reads membership or top-up words right after the alias of any `alternative_position` payee. On the cache it claims exactly the Klarna rows the decision's Klarna-worded patterns claim (42, 2026-09-26 probe). Without the group limit it would also take personal-loan memberships (Brigit, Bright Money, Klover: 53 rows), which no decision covers.
      - **The unnamed loan payment is built in Task 9.** It needs D11's payee words, and Task 8 runs before them. Task 8's `LOAN PAYMENT` case therefore moves to Task 9's tests, as `bank_loan`.
      - **Step-8 order.** It follows the merged list of the decisions (s2 amendments C). Another bank's unnamed loan comes after the own-loan transfer; the two claim disjoint rows.
      - **Clover Equipment is pinned in Task 8.** Its rows reach `lease_or_rental` through step 8's lease wording, which Task 8 builds.
      - **TD CMCA's stale-candidate rebuild moved.** Its candidate is now a lender, so the check moved to the Audit Bank serialization test, which gains a fabricated unnamed direct-debit loan.
      - **The FIRST INSURANCE residual is accepted** (item 12).
    - S1's plan, its content test and the spec change separately (s2 amendments E); this plan cites S1 by contract and names only the S1 constants it reads.

**Dry run (2026-09-25).**
- **It predates the owner decisions of 2026-09-25.** The replay of 2026-09-26 below covers them.
- **Replay on the revised ledger (2026-09-26).** A scratch export of S1 at `b69d12e` with the revised ledger's rendered registry, never the working tree:
  - Task 0: `0 failure(s)`; navigant's bank-name line reads 2, and the card-issuer info lines read 3 (RBC Jan) and 0 (Navy Fed June).
  - A replay script applied the code blocks and edits of Tasks 1-11 and 15, as amended for these decisions, task by task, and each replace target matched exactly once. Tasks 12-14 and 16 were not replayed: the decisions left Tasks 12-14 unchanged and changed only Task 16's documentation text.
  - Red phases of Tasks 4, 5, 7, 8 and 9 (each task's test file on the tree the earlier tasks leave): every new test failed or passed as its "watch it fail" step says.
  - After Task 15: the new S2 test files, every re-pinned test file, the three selections of Task 0 Step 2 and S1's registry, matcher, speed and alias-audit tests gave `1177 passed, 3 skipped` (S1's legacy-list checks, by design), with the known `test_no_literal_account_numbers_in_ocr` failure deselected.
  - Task 17 Step 4's scan of the replayed test diff found only figures with cents that step lists.
- **Setup.** A scratch copy of the pre-C10 S1 revision's trial tree, never the working tree: `lender-detection` at `4f219cd` with S1's plan applied as revised on 2026-09-25. It held its builder's registry (eleven groups, built from the research files) and its classifier edits. A replay script applied every code block of this plan file, task by task, and each replace target matched exactly once.
- **Task 0 on that tree:** 0 failures. It selected both variants: navigant's bank-name rows (2 loan debits name a listed bank) and relay's personal-loan payees.
- **Red phases.** Every task's new tests failed as its "watch it fail" step says. Task 3 failed on `600 == 300`; Task 15 failed at collection.
- **Results after Tasks 1-15:**
  - S2's new tests: 210 passed (218 after the C10 alignment below: the census has 14 tests, up from 6).
  - Core: 395 passed (404 before, minus the 9 order-table rows that moved).
  - Guards/JS: 147 passed (146 before, plus the new BlueVine test), plus the known pre-existing failure.
  - Wider: 309 passed (306 before, plus the three benchmark tests).
  - The payload neighbours (`tests/test_webapp_worker.py`, `tests/test_document_report.py`): 37 passed.
  - S1's tests: `308 passed, 4 skipped` over S1's seven test files, `tests/test_lender_alias_audit.py` included; the skips are the legacy-list checks, by S1's design. The six-file command this plan carried before gave `298 passed, 4 skipped`, because it left the alias-audit file out (`10 passed` on its own). Task 6 Step 4 now takes the list from git.
- **Re-pins.** Every pin-ledger value reproduced, including ATB November (2 / 42 / 7497.0 and 22 / 3178.19 / 5.36) and both variants: navigant `(0, 0.00, 0, 0.00)` after Task 8 and `(0, 0.00, 3, 108.00)` after Task 10; relay channels `(2, 8, 64, 9, 0, 0)` after Task 5. The 2026-09-24 dry run, on stand-ins for S1 without those registry entries, reproduced the base values (navigant `(0, 0.00, 4, 1299.00)`, relay unchanged).
- **Census.** The Task 15 smoke run over 60 cached analyses took under 10 s per snapshot and exited 0: 60 accounts compared, 0 unmatched, 0 lenders gained through a generic word (counts only).
- **C10 alignment re-check (2026-09-25).** On a fresh copy of the same pre-C10 tree, the replay applied this revision of the plan with every target matched once. Results:
  - S2's new tests: 218 passed; census 14.
  - Core: 395 passed.
  - Guards/JS: 147 passed, plus the known pre-existing failure.
  - S1's seven test files: 308 passed, 4 skipped.
  - **Task 0.** That tree has no C10 ledger, so Task 0 printed exactly two FAIL lines, the two ledger lines, and nothing else. With a scratch stand-in ledger (every lender-table entity an admitted `confirmed_lender`, never committed), it printed `0 failure(s)` and the same variant lines.
  - **Census.** The smoke run's `compare` against that stand-in exited 0: 60 accounts compared, 0 unmatched, 0 generic-word gains. Without a ledger it refused with exit 2.
  - **Not proven here.** No real C10 ledger exists yet, so none of this proves the content facts (Prerequisites 1-6, 8 and 9). Task 0 on S1's merged tree is the first check of them.
- **Speed.** The 300-row synthetic statement classified in 0.23 s on that tree (Task 17 Step 3, host otherwise idle), under the 0.319 s target, and S1's relative benchmark passed. The 2026-09-24 dry run, with a naive stand-in matcher on a busy host, read 0.18-0.52 s against 3.9 s for today's code.
- **Cross-plan consistency check (2026-09-25), after the runs above.**
  - The census's `GENERIC_WORDS` is now every word of S1's `tools.lender_ledger.GENERIC_WORDS` plus `FUNDER`, and one census test pins the superset: 15 census tests. The words are written out, not imported, because importing `tools.lender_ledger` loads this checkout's `analysis` package before `snapshot --code-root` can load the other checkout's, and `_use_code_root` would then refuse. With the widened set, the census's own test data classify as before: `FUNDING` is generic, and `TARNMOOR FUNDING`, `QUILLON FUNDING` and `BRAMBLEWAY CAPITAL` are not (checked on a scratch script).
  - Task 6 Step 4 lists S1's nine current test files, and "Why Task 0 checks more than C10's validator" lists only what S1's validator does not check.
