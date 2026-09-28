# False Potential Lenders (classification 5.3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. Every task is sized for one implementer and one independent reviewer.

**Goal:** Take the ~4,900 false or misrouted rows out of the Potential Lenders tab (the 2026-09-27 hunt, workflow `wf_f924027d-6f4`), without hiding a real funder and without touching lender math, in one release: classification **5.3**, analysis stage **22**.

**Architecture:**
- **Part 0** builds the shared helpers every new rule reads: a prefix-tolerant financing veto, the payee-word readers (payee region, text before the receiver fields, leading payee words, originator segment) and the channel-vocabulary rule. D6's admission test becomes one named function, `_d6_skip`.
- **Part A** adds D6-only skips. The rows stay `other` / `default` / `no_classification_rule`; only the review tier loses them.
- **Part B** extends existing rules, so rows change state: fee/NSF wording, cheque spellings, field-order payee forms (Amex loans and Amex card payments), card-payment wording, payroll and benefit administrators, mortgage and own-loan wording, POS labels and related-party loans.
- **Part C** fixes the registry, the matcher, D11 naming and the tab. Review entities of flag groups go to their flag, marked unconfirmed, with the credit side unchanged. The ledger gets renames, the matcher reads glued digits, the naming bugs are fixed, and unnamed payees are grouped on the Potential Lenders tab.
- **Part D** adds the twelfth flag group, **Debt relief**, end to end.
- **Part E** adds the missing registry entries from the research files, taking only VERIFIED entries.
- **Part F** moves the versions and their pins, updates the docs and runs the final verification.

**Spec:** `docs/superpowers/specs/2026-09-24-lender-detection-design.md` (decisions D1-D12). Part F adds the 2026-09-27 (5.3) amendment and clarifications to it.

**Tech Stack:** Python 3.14 (`C:/Python314/python.exe`), pytest 9, `re`, dataclasses; vanilla JS (`webapp/static/app.js`, tested in node through `tests/webapp_js_harness.py`). No new dependency.

**Sources (PRIVATE: they hold real payee words; never copy a person's name or a statement value out of them):**
- `C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/REPORT.md` (summary), `digest_families.md`, `digest_other.md`, `workflow_result.json` (full text), `all_keys.json` (every payee key with masked samples).
- Per-family full dumps written for this plan: `C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/famNN_<family>.noev.txt`, `structural_full.txt`, `side_naming_*.txt`, `side_registry.txt`.
- Pattern prototypes that this plan's regexes were checked with (fabricated rows only): `.../work/plan53/proto/proto_patterns.py`, `proto_patterns2.py`, and the pytest plugin `proto_plugin.py`, which measured the existing tests each generic rule moves.
- The research files of Part E (VERIFIED entries only): `C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/research/funders.json` and `research/debt_relief.json`. Since 2026-09-28 each carries the independent verify round's verdicts (round `r7`) and a `verify_round` block that lists what Part E may use.
- The Part C, D and E prototype: `.../work/plan53/proto/apply_c_classifier.py`, `apply_c_rest.py`, `apply_ledger.py`, `apply_pins_js.py`, with `run_builder.py` and the pytest plugin `git_baseline_plugin.py` (the copy is not a git checkout).
- Collision checker for any new name or word pattern: `.../work/plan53/collision_check.py "<regex>" ...`. It prints registry and ledger entity names and key ids only.
- The plan review of 2026-09-28 and its re-run: `.../work/plan53/rev/` (`probe.py` classifies fabricated weekly rows on any tree; `apply_research_r7.py` recorded the verify round in the research files; `rebuild_proto_ledger.py` rebuilt the prototype ledger through the revised E0 gate with the real r7 verdicts; `apply_tests_rev.py` carries the review's test changes).

## Owner decisions this plan implements (2026-09-27)

1. Ship all three parts in one release, classification 5.3 / `ANALYSIS_STAGE_VERSION` 22:
   - (A) D6-only skips where rows stay `other`;
   - (B) extensions of existing rules that change a row's state: fee/NSF, cheque, card payment, the Amex loans field-order alias, payroll/benefits, mortgage MTG, and POS labels where right;
   - (C) registry, naming and UI:
     - route review entities of flag groups (vehicle, mortgage, personal loan, lease) to their flags, marked unconfirmed, WITHOUT changing the credit side;
     - ledger renames and the missing funders;
     - the glued-digit matcher gap;
     - the naming bugs: Truist ACH CORP DEBIT, the CO cue, the legal-form position, wires' beneficiary, the D10 label;
     - the Potential Lenders tab grouping unnamed payees by payee key.
2. A new 12th flag group, **Debt relief** (Settings checkbox, default ON, never lender math, shown like the other flags). It covers debt-settlement dedicated-account processors and debtor-side debt-relief firms: RAM Payments / Reliant, Global Holdings GHLLC, Tayne Law Group, Resolve Capital, and well-known debt-relief brands printed by name.
3. Add the missing real funders after a research check: Flexibility Capital, Merit Business Funding, Essentia Funding, National Funding's `NFSPV<d>COLLECTION` spelling, and GOAT ADVANCE's glued digits (through the matcher). Samson Servicing is added only as a review alias, unless a source ties it to a funder.

## Global Constraints

- **Where you work.** Only in the worktree `C:/Users/GustavoPrietodePaula/work/ld-fp53` (branch `ld-fp53`, from `lender-detection` at `0935061`). A shell starts in the MAIN checkout, so every command starts with `cd C:/Users/GustavoPrietodePaula/work/ld-fp53 &&` or uses `git -C C:/Users/GustavoPrietodePaula/work/ld-fp53`. Never edit, stage, commit, check out, stash or reset anything in the main checkout. Check `git status` in the main checkout after each task.
- **Scope of lender math.** Only MCA/revenue-based funders, online term lenders and equipment financing are lenders (`confirmed_lender`). No task changes `lender_*`, `withholding_*`, `eligible_deposits` or the package `decision`, with three exceptions, which the owner ruled: the new registry funders of Part E, the glued-digit matcher (C4, GOAT ADVANCE), and the Amex field-order debits, which become an alternative position rather than a potential lender (B3).
- **Credits stay as they are.** Every task keeps the credit side unchanged. The review-flag routing (C1) keeps the routed entities in `POTENTIAL_LENDER_ALIASES`, so `_classify_credit_revenue` (`analysis/transaction_classifier.py:812`) and `_descriptor_proceeds` (`:1231`) keep today's exclusion. The field-order forms (B3) apply to debits only. Debt relief (Part D) is not in `FINANCING_STATES`.
- **Every new D6 skip carries the shared financing veto** (Task 0.1). It is read on the whole normalized row, with the skip's own matched words removed. Skips read the payee words, never a receiver field. Each task says which reader it uses:
  - D11 payee words;
  - the payee region;
  - the row before the receiver fields;
  - the leading payee words.
- **Privacy.**
  - Tests use FABRICATED descriptors only. They keep the bank's printed format and invent the names, amounts and dates. Dates are in 2054, and amounts are whole dollars: the privacy canaries flag cent figures (`tests/test_webapp_studio_views.py:16`).
  - Never commit statement text, amounts, account numbers, dates or customer names. Commit messages carry no real statement value. Scan every message before committing.
  - Business names of funders, processors and banks are fine.
- **Versions.** `CLASSIFICATION_VERSION` becomes `"5.3"` and `ANALYSIS_STAGE_VERSION` becomes 22 in Task F1, together with every pin. The branch merges as one unit and no intermediate commit is served, so Parts 0-E commit at 5.2 and change output freely.
- **Stop rules.**
  - If a pinned real-statement test moves to a value this plan does not list (for example `tests/test_new_statement_corpus.py`, the ATB/RBC/TD pins in `tests/test_transaction_classifier.py` and `tests/test_revenue_classification.py`, or `tests/test_analysis.py`), stop and report the test id to the orchestrator. Never re-pin to whatever the code produces.
  - If a research file is missing, or has no VERIFIED entry for an owner-named payee, stop Part E and report.
- **Tooling.**
  - Write or patch Python with the Write/Edit tools, never with Bash heredocs: the Bash tool mangles backslashes here, and every regex below has them.
  - Restart Flask after template edits.
  - Run tests with `C:/Python314/python.exe -m pytest tests/<files> -q -p no:cacheprovider`. Always pass paths under `tests/`: a bare `pytest` also collects `discovery_reports/`.
- **Guards that stay green.**
  - No payee or brand literal in `webapp/static/app.js` (`tests/test_revenue_classification.py:812-844`, `tests/test_lender_insurance_classification.py:566-584`).
  - Every `formatMoney(` call passes an explicit currency (`tests/test_package_currency.py:773-796`).
  - No exact-cent literal of 1.00 or more in `analysis/` code (`tests/test_no_statement_hardcodes.py::test_no_exact_amount_constants_anywhere_in_analysis` and `::test_closing_the_docstring_hole_flags_no_module`): an amount constant is a whole number (`25`, never `25.00`). The Part C prototype's full suite caught this on A10 and A11.
  - Registry entity names live in `analysis/classification_registry.py`, or in the ledger it is rendered from. A new counterparty entity name is never a literal in the classifier. The D6 vocabularies of non-lender brands live in the classifier, as `_PAYROLL_PATTERNS` and `_TRANSFER_PATTERNS` already do. Spec §5 gains a bullet that says so (F2), and a name joins such a tuple only after `collision_check.py` prints no registry or ledger hit.
- **Commits.** Each commit step gives the exact `git add` paths and the subject. The attribution goes in a second `-m`: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Test selections** (baselines measured at `0935061`, 2026-09-27):
  - **SEL-CLASSIFIER** (751 passed, 2 deselected): `tests/test_recurring_fixed_debits.py tests/test_unknown_payee_naming.py tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_new_statement_corpus.py tests/test_flagged_positions_payload.py tests/test_obligation_descriptors.py tests/test_known_payee_classification.py tests/test_flag_group_states.py tests/test_classifier_lookups.py tests/test_financing_proceeds_credits.py tests/test_factoring_credits.py tests/test_premium_financing.py tests/test_analysis.py tests/test_batch.py`. The new files `tests/test_d6_helpers.py`, `tests/test_d6_skips.py` and `tests/test_rule_extensions_53.py` join it once they exist.
  - **SEL-REGISTRY** (334 passed, 4 skipped): `tests/test_lender_ledger.py tests/test_build_lender_registry.py tests/test_lender_registry_drift.py tests/test_lender_registry_content.py tests/test_classification_registry_groups.py tests/test_payee_matcher.py tests/test_lender_alias_audit.py tests/test_lender_census.py`.
  - **SEL-WEBAPP** (597 passed): `tests/test_flag_groups.py tests/test_flagged_view.py tests/test_webapp_settings.py tests/test_webapp_flagged_positions.py tests/test_webapp_flagged_dashboard.py tests/test_webapp_reanalysis.py tests/test_package_currency.py tests/test_webapp_app.py tests/test_artifact_cache.py`.

## Families and the verifiers' changes

Every family of `digest_families.md` is covered, with the fix as amended by its two verifiers (lender-risk and evidence). A REQUIRED change is applied, and a refuted part is dropped. Each optional change is decided below, with the reason in one line.

| Family (rows / account occurrences) | Task | REQUIRED changes applied | Optional changes: decision and why |
|---|---|---|---|
| card_purchase_format (917 / 130) | A1, B7, 0.1, 0.3 | The veto becomes a two-part check on the whole row: the prefix-tolerant roots, including the verifier's SETTLE, CRED(?=IT\|ORA\|IBLY\|\b) and ACCEPT (Task 0.1), plus the organisation cues and financing-organisation words. The channel-vocabulary rule (0.3) carries the same organisation-cue guard, so it never hides a card-format row the veto keeps (plan review 2026-09-28). | **Location suffix scoped to Bluevine and Lead Bank (Found): yes**, since it is verified card-only on those two banks. **Wealthsimple clause kept only with the widened veto: yes**, because the funder guard is the veto. **c00148 WF 'Recurring Payment authorized on … Card nnnn' skipped on format: yes**, the same treatment POS already gives 'Purchase authorized on'; the owner is told. **c00082 annotated as hidden on format: yes** (spec note). **Chase 'Payment Sent … Card nnnn' (c00022) as its own card clause: no**, because A2's PAYMENT SENT rail covers it. **Bluevine glued 'CITY, NYUS' recorded as a non-match: yes** (comment and spec). **Cleared rows leave the recurring-debit view, pinned by a test: yes.** **Brand-only residual logged as accepted policy: yes** (spec). **Square 'Transfer out' funder pulls: no**, a separate family for the backlog. |
| other_flag_group (260 / 151) | C1, C2, B6 | Credits unchanged: the routed entities stay in `POTENTIAL_LENDER_ALIASES`, and only debits read the derived `REVIEW_FLAG_ENTITIES`. Routing is narrowed: `business_type` 'unknown…' is never routed (WOW FACTOR, DW Rentals), and Table Rock moves to the `potential_lender` group. `ORIG CO NAME WESTLAKE ORIG` is split into its own `confirmed_lender` review entity. The marker: `review_required` on flagged positions and an "Unconfirmed" line on the flag tab. | **FleetLogic kept in the potential tier: yes** (moved to the `potential_lender` group), matching the PACCAR/Daimler convention until the owner rules. **An unconfirmed flag payee kept visible when its group is unticked: no.** It contradicts the owner's D7 ruling (a setting only hides), so it goes to the owner as an open question. **One longest-match lookup instead of 'new table first': yes, by design** (one table, one lookup). **LOANS? in the own-loan transfer (c00198): yes** (B6). **MTG PYMT descriptor: yes** (B6). |
| p2p_payment_app (369 / 101) | A2, A3 | The new rails are guarded by the financing veto. The glued transfer form sits under the veto and the unidentified-payee guard, and `_TRANSFER_WORD_PATTERNS` stays unchanged. | **Collision shapes (RBC 'Virement par Banque en direct', CIBC 'INTERNET TRANSFER<ref>') added as NOT_PROMOTED: yes.** **FINWISE and WISE CHOICE controls: yes.** **Spec wording for VIREMENT and the glued form: yes.** **PNC alias 'ZEL TO GLOBAL FUNDING': no**: it is not in the owner's list, and the veto already keeps 'Zel To … Funding' in review. **D11 template words PMNT/SENT/ZEL/VIREMENT/ENVOYE: partly.** They join the channel vocabulary (0.3), and PMNT SENT and PAYMENT SENT join the prefix list (C6), but not `_ENTITY_NOISE`, which would move every D6 key. |
| supplier_or_vendor (252 / 71) | A6 | The lending guard is widened: the shared prefix-tolerant veto plus PAD. It includes FINANCIAL, CREDIT and FACTOR, so c00243 stays. Bare MFG and WHOLESALE are dropped. The vocabulary is read on the D11 payee words and, as a fallback, the originator segment (so C5's legal-form cut keeps the 'Inc Invoices' rows), never a receiver field, and there is a holder-name guard. Plan review (2026-09-28): the fallback is read only on a bounded row (an ACH field, or a reference after the name, ends the payee's words), and on a row that is one run of words (Regions '<funder> ACHPMT <receiver>', Bluevine '<funder> PAY PAYMENT TO <receiver>') with the holder's name unknown, the vendor word must be the payee's first word. | **The four guard-miss controls as tests: yes.** **Spec lists the vocabulary verbatim and notes that DISTRIBUT\* also clears owner distributions: yes.** **BLACKBULL review → rejected: no**, an owner call not in the rulings. **c00153 WT FED: yes**, as naming (C7), never a wire skip. |
| credit_card_payment (828 / 62) | B3, B4 | P1 cannot span a second originator block: it is the negative-lookahead form, carried as a field-order form of the admitted Amex card entity, so the rows are named. P4 skips a row only when the issuer IS the payee: the context alias's tokens are a prefix of the D11 payee words. | **Chase Amex rows named 'American Express [credit card payment]': yes**, through the field-order form (B3). **C10 contract and registry docstring amended for the negative reading of `card_issuer_context`: yes** (B4, F2). **Validator rule forbidding an issuer alias inside a lender alias: no**, because P4 reads only a payee-word prefix and also carries the financing veto (added here), so an issuer token cannot hide a funder. **R1 (Atlas Smart Pay) and R2 (RTS Carrier Services) as card-context entities: yes, only if VERIFIED**; neither research file carries them (Part E), so c00207 and c00120 stay in review for the owner (open question 9). |
| bank_fee_or_charge (264 / 49) | B1 | none (the lender-risk verdict: ship as proposed) | **FRAIS guarded against loan and LOC words: yes.** **The stop-payment rule split, deposited items going to refund_or_reversal: yes.** **Test of a returned funder debit's credit: yes.** **Optional SANS PROVISION: no**: it moves the evidence-only `nsf_count` on French accounts without a ruling, and no potential row needs it. |
| internal_transfer (357 / 32) | A3 | The skip splits in two: today's TRANSFER/XFER/TFR skip stays unconditional, and the new templates skip only an unnamed payee with no financing words. The Atlas pattern is narrowed to SMARTSAVE with ATLASFIN. | **TRSF and TRANSFR dropped; TRNSFR (140 corpus rows) and TRSFR kept: yes.** **P2 'TO <account type> <number>' kept and recorded for the owner: yes**; the owner may strike it (c00069, 54 rows, then stays). **Docs line 169 updated: yes** (F3). **The transfer rule running before the known payee: an owner question.** |
| alternative_position_platform (45 / 42) | B3 | The Chase field sequence is spelled out, and the Truist form is anchored at the start. | **Debits only: yes**. The credit wiring would move 30 credits into `lender_credits`, which the owner has not ruled on; it goes to the owner as an open question. **A distinct `matched_rule` (`*_field_order`) and reason: yes.** **The entity names move to a hand-kept registry constant validated against the ledger: yes.** |
| other_non_lender (455 / 40) | A4 | The cash, batch and FACTS patterns are narrowed so that a payee name can never fill the gap. | **Every narrowed pattern and every control test: yes.** **Cash withdrawals as the `atm` state: no**: the spec keeps ATM "unchanged" (§4.3 step 5), so this is an owner question. |
| debt_settlement_or_collection (143 / 37) | Part D, E3 | Generic DEBT RELIEF/SETTLEMENT dropped. | **Owner ruled a flag group instead of a skip: yes** (Part D). The payees are registry aliases (`RAM PAYMENTS`, `RAM PAYMENT`, `RAM PMT`, `ORIG CO NAME RAM ORIG`, `GHLLC`, `TAYNE LAW`, `RESOLVE CAPITAL`, and named brands), never classifier words. Debt relief is a table and an index of its own, read after the known payee on the row without its receiver fields (the debt-relief research's verified hazard; Part D). The index is built with `run_together=True`, so FORTHPAY and RAMPAYMENTS are read (the debt-relief verifier). The verifier's negative controls (settlement words beside a funder or a law office, RAM Capital) are pinned in E3. **The PPD lookahead on the Chase RAM form: no**: an alias cannot carry a lookahead, and a CCD originator named exactly RAM is not plausible. |
| savings_or_investment (374 / 36) | A5 | none (verdict: confirmed) | **Precedence tests (Albert Genius, GLOBAL MER EDI PYMNTS): yes.** **Forward brands ACORNS, ROBINHOOD, COINBASE, BETTERMENT, WEALTHFRONT: yes.** `collision_check.py` printed 0 registry, 0 ledger and 0 key hits (2026-09-27), and the structural critic rates the shape high. |
| subscription_or_software (94 / 24) | A10 | The floor applies only to a payee with no organisation cue. The evidence verifier's note: the floor's groups also leave `detect.find_recurring_debits`, the CLI's 'Recurring fixed debits' lines, `batch.py`'s `recurring_debit_groups` and `detection.recurring_debits` (pinned in A10; stated in F1's comment and F2's D6 bullet). | **Strict comparison, $25.00 still promotes: yes.** **No $50 floor: yes.** **RECOVERY and COLLECTIONS as organisation cues: no**, a naming change with a wide effect. The floor instead carries the shared financing veto, so a no-suffix 'X Recovery' collector stays in review. The cost is c00102 (its payee name prints CREDIT), which stays. |
| check_payment (188 / 33) | B2 | All three patterns require the instrument's number (`^DRAFT WITHDRAWAL DRAFT ?[0-9]`). | **Spec step 10 names the spellings: yes.** **Controls for BUS CHQ and SHARE DRAFT: yes.** |
| tax_or_government_payment (72 / 18) | A7 | none (verdict: confirmed) | **Read on the payee region, never on DES/entry fields: yes.** **Unidentified-payee guard: yes.** **Evidence-only list: no**: the synonyms stay, the structural agencies join under the guard, and USATAXPYMT is dropped as redundant. **CCRA into the tax rule: no**: tax is not in the owner's list of state changes. **SBA TREAS 310 alias: no**, a registry follow-up. |
| payroll_or_benefits_provider (66 / 19) | B5 | N1: provider and benefit names are read on the originator segment. N2: a financing word suppresses the new patterns. | **N3 (drop 401K): yes.** **Glued PAYROLLTAX into tax: no**: it keeps the tax rule, which has no guard and outranks step 7, untouched; no metric reads either state. **Evidence-only brand list: yes**: ISOLVED, INSPERITY, TRINET and JUSTWORKS are dropped. **Fly raw rescan: yes** (F4 Step 6, where access allows: a pattern scan of the tryout host's saved rows). |
| child_support_or_garnishment (47 / 11) | A8 | none (verdicts: confirmed) | **Read before the receiver fields: yes.** **Applied before the keyword/default split: yes.** **Regression controls (FAMILY SUPPORT CAPITAL LLC, CHILDS CAPITAL LLC): yes.** |
| platform_or_processor_fee (19 / 5) | A11 | An amount cap of $50. | **Guard hardening (SQ CAP, SQ LOAN, LENDING): yes.** **Placement: classifier constants plus a spec §5 bullet: yes.** **A ledger evidence note on the Intuit payer side: no**, not needed for the rule. |
| compensation_to_person (154 / 18) | A9 | A payout is skipped only when its named recipient is not an organisation and not the platform. | **A sibling tuple, not `_COMPENSATION_WORD_PATTERNS`: yes.** **Wise in the same tuple: no**: Wise stays a p2p rail (A2). |
| insurance_premium (9 / 3) | A12 | Read on the D11 payee words only. | **Insurance-term widening (alternative A) or a NEXT INSUR insurer alias (B): no** (both refused by the verifiers). **Step 4 before the known payee: an owner question.** |
| utility_or_telecom (6 / 2) | A13 | Anchored on the leading payee words (`.match`, never `.search`). | **Bill-payment prefix words: yes.** **METRO BY T MOBILE: yes.** **The optional coverage-only prefix words (PC, TEL, PAID, PULL, SVCS, CORP, SINGLE): no**: none reaches a potential row, and CORP interacts with C6. **ATT narrowed to its bill and payment forms: yes.** **VERIZON lookahead left as is and documented: yes.** |

**Naming side items** (verified summaries in `side_naming_*.txt`). All are applied:
- the Truist prefix strip with the stricter 16-character legal-form gate (C6);
- C1/C2: a legal form counts only after the first word, a name made only of cue words is unidentified, and CO is dropped (C5);
- N1, a legal-form cut, plus N2, trailing connectors (C5), and N3, printed 'NAME, CITY, ST' (C8);
- N1', a cue cut, on the wire path only (C7);
- T2, wire beneficiaries, with SRF, RFB, IMAD and INSTR added as field segments (C7);
- the prefix list for bank templates (C6);
- the D10 fixed label (C9);
- the tab grouping (C10);
- PAID and a leading AND as name noise (C5).

**Registry side items** (`side_registry.txt`):
- the NFSPV alias with a digit read from the local cache (E2);
- the glued-digit matcher, scoped to the known-payee index, with at least three letters in the alias's last word (C4);
- Flexibility Capital, Merit Business Funding and Essentia Funding from `research/funders.json` (E1);
- Samson Servicing as a review alias unless tied to a funder (E4);
- Resolve Capital under Debt relief (E3);
- GOAT and Bell Rock ledger notes corrected (C4).

Not done, because the owner's list does not include them:
- the SST phone-number matcher;
- the IDEALOAN alias;
- KIKOFFCCBX;
- BLACKBULL.

## Structural misfires (the critics' fabricated shapes)

**Added** (high or medium, each with a narrow, guarded rule and fabricated tests):
- A1 card labels: PIN DEBIT, RECURRING DEBIT CARD, CARD TRANSACTION, DEBIT PURCH / CARD ENDING IN, and DDA PUR (low, trivial);
- B7 POS labels: PIN PURCHASE, MOBILE PURCHASE, RETAIL PURCHASE and the French card forms the corpus prints: C/ACHAT, ACHAT AU DETAIL, ACHAT INTERAC, ACHAT PAR CARTE and ACHAT EN LIGNE (never a bare ACHAT, which also opens a factor's 'ACHAT DE CREANCES');
- the channel-vocabulary rule (0.3), which covers:
  - teller, branch and bare CASH WITHDRAWAL, ATM DEBIT;
  - payees that are only channel words (BILL, RECURRING, AUTOPAY, MISCELLANEOUS);
  - the speculative card labels that print no merchant;
- A3 transfer abbreviations TRF/XFR/TRSFR/TRNSFR and the RTP/Real Time Payment/FedNow rails (guarded);
- B2 anchored CHK/CK cheques;
- B1 fees: FRAIS, and CHG/charge wording outside FEE;
- A9 owner draws, member/partner/shareholder distributions, dividends, per diem and guaranteed payments;
- B5 payroll: the corpus-evidenced providers and French PAIE/SALAIRE;
- A7 tax and government agencies without TAX, and, in the keyword recurrence, government finance departments and ADVANCE AUTO PARTS / ADVANCE STORES;
- A5 recurring investment apps;
- A6:
  - church giving;
  - uniform, linen, janitorial, landscaping and pest-control vendors;
  - ad platforms without a star;
  - tolls;
  - franchise royalties and ad funds;
  - betting and lottery;
- A4 daycare and tuition;
- B8 shareholder, owner and director loans;
- B6 LOAN INTEREST (own-bank) and MTG/MTGE payment wording;
- Part D/E: debt-relief brands printed by name, through the registry.

**Left out, and why:**
1. **Sister-company sweeps (high).** No vocabulary separates an affiliate from a funder. The fix is the out-of-scope "analyst marks a payee" project (spec §11).
2. **Garnishment, levy, legal order (medium).** The child-support verifier keeps them in review: an MCA judgment creditor collects through a law office or a marshal.
3. **Acronym-only support conduits (SDU, SCDU, CSPC, DCSS).** No corpus row, and the verifier kept them out.
4. **Own-account savings at another bank printed without a transfer word (ALLY BANK, EQ BANK, CHIME…, medium).** This conflicts with the standing ruling that keeps a bank's or credit union's own-banking pulls in D6 review (Grow Financial). It needs the owner.
5. **Insurance abbreviations INS/PREM/WC and carrier names (medium).** The insurance verifier refused widening the step-4 term rule, which runs before the known payee and would hide a counted lender. Only the D6 truncation skip (A12) ships.
6. **Generic 401K/HSA words (medium).** Payroll N3: they are read in holder names. Only named administrators ship.
7. **Generic debt-relief words (DEBT RELIEF/SETTLEMENT, CREDIT COUNSELING, medium).** Both debt-relief verifiers dropped them. Brands come by name through the registry (E3).
8. **ADVANCE PAYMENT as a vendor prepayment (medium/low).** An MCA remittance is itself an advance payment, so the words cannot separate the two. 0 corpus rows.
9. **Low-rated shapes:**
   - utilities named POWER/ENERGY/GAS/WATER;
   - French MARGE DE CREDIT, CARTE DE CREDIT and ASSURANCE;
   - NELNET/GOODLEAP (registry research, not a rule);
   - SWEEP/ZBA/TO SAVINGS and OVERDRAFT PROTECTION ADVANCE (a LOC reading that needs a ruling);
   - fleet fuel cards and food distributors beyond SYSCO/US FOODS;
   - the speculative card labels (the channel rule covers the ones that print no merchant).
10. **SUREPAYROLL, RIPPLING, JUSTWORKS, TRINET, INSPERITY, ISOLVED.** No corpus row. The payroll verifier's evidence-only choice applies, so each is added after a printed form is seen.
11. **D11 name noise CHG/ADS/WIRE/INVOICE/ROYALTY (medium, cosmetic).** The rows mostly leave through the skips. Only a leading AND and PAID ship (C5).

## Unclear keys (`digest_other.md`, UNCLEAR)

No rule targets them:
- c00033 'Other Debit', c00136 'Bank Debit' and c00242 'Preauthorized Wd': the channel vocabulary leaves out OTHER, BANK and WD on purpose;
- c00042, c00055, c00080, c00081, c00091, c00098, c00117, c00132, c00138, c00139, c00175, c00190, c00196, c00231, c00232, c00233 and c00235.

Some change only their published name: c00098 'Review Inc' (C5), c00138 HIP (C6), c00190 wire beneficiary (C7) and c00175 'Bokf National Bank' (C5). F4 lists them among the keys expected to remain.

## Open questions this plan hands to the owner (nothing here is implemented)

1. An unconfirmed flag payee under an unticked group is hidden (D7). Should it stay visible, or fall back to the potential tab?
2. The Amex field-order credits: should the 30 Chase/Truist loan-disbursement credits become financing proceeds (`lender_credits` up, eligible deposits down)?
3. The transfer rule (step 6) runs before the known payee (step 7), so a registered funder paid by spaced e-Transfer or Zelle is `transfer` (the GLOBAL FUNDING alias is unreachable).
4. Step 4 (insurance terms) runs before the known payee, so a holder named '… Insurance' hides its funder.
5. Cash withdrawals as the `atm` state (+2,905 corpus rows to `atm`).
6. P2 of A3 (a BofA banking-centre 'TO CHKG <n>' with no counterparty) stops being reviewed. Is that wanted?
7. c00148, WF 'Recurring Payment authorized on … Card nnnn' to a person plus a website, is skipped on format.
8. Stop-payment returns as `nsf_or_return` (B1), which moves the evidence-only `nsf_count`.
9. RTS Carrier Services (c00120) and Atlas Smart Pay (c00207) stay in review: neither research file carries a card-context entry for them (Part E).
10. KIKOFFCCBX (c00105), BLACKBULL (c00060), IDEALOAN (f00002) and States Resources (c00065): not in this release.
11. Merit Business Funding's alias `MERIT BUSINESS`, the only spelling that reaches its rows (the Truist originator, tryout host only). The verify round (r7) requires the owner's explicit choice before it is committed: BUSINESS is a generic word, so its only distinctive word is MERIT, and the matcher reads the whole row. It would count as Merit obligations a debit to any other payee printing the two words and another originator's debit whose receiver, the account holder, is named 'Merit Business …' (INDN / IND NAME), and it would read a same-named payee's credit as financing proceeds. The research file now carries `MERIT BUSINESS FUNDING` only (its `owner_pending_aliases` holds the choice). E1 adds `MERIT BUSINESS` only on the owner's yes, with the notes sentence `Owner choice <date>: …` (E0's `owner-alias`); without it the Truist rows stay D6 review rows, unnamed after C6.
12. Essentia Funding's rows carry a 'Real Estate Loan Payment' memo. As a counted alias, step 7 counts them before step 8's mortgage wording.
13. Bell Rock Income Fund's monthly rows (72 corpus rows in 12 accounts, the funders verifier's count): 57 glue one digit to FD, the two-letter last word of its alias BELL ROCK IN FD, which C4's three-letter rule leaves strict; 15 more print a different cut (BELL ROCK INCOME FUN…), which no alias or glued rule reaches and which would need a second cut alias (for the mortgage cell). Widen the rule to two letters (after re-scanning the 46 aliases ending in a one- or two-letter word), add the spellings, or leave them?
14. Debt relief: bare FORTH as an alias (every corpus row printing it is Forth Pay, but it is an English word); the card form DELANCEY STREET NEW YORK (27 card rows read as Delancey Street Debt Relief; the verify round found all 30 matched card rows in one bank's 12 accounts, 27 POS and 3 insurance today, so look at one statement before accepting it); and whether the escrow refunds (RAM PMT and New Leaf credits) become non_revenue.
15. Resolve Capital: admit it as debt relief, keep it under review (this release), or keep it a potential lender? The verify round found a second Palm Beach County 'Resolve' debt-relief firm (MCA Resolve LLC) whose old domain now redirects to a consolidation-loan lender, and no source that ties either firm, or any funder, to the printed Chase originator.
16. D6's daily ceiling (a 1.6-day average gap) misses a new daily position whose first three or four business days straddle a weekend (GOAT's March rows). A D6 design question, not in this release.

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `analysis/transaction_classifier.py` | Modify | Part 0 helpers and `_d6_skip`/`_keyword_recurrence_skip`; Part A skips; Part B rule extensions; C1 routing at step 11; C5-C9 naming; C10 `potential_payee_label`; D1 the `debt_relief` state; D3 the debt-relief step; F1 version |
| `analysis/payee_matcher.py` | Modify | C4: glued digits on the last word of a multi-word alias, known-payee index only; D3: the debt-relief index and `match_debt_relief_payee` |
| `analysis/classification_registry.py` | Modify | the GENERATED block, re-rendered (C1 `REVIEW_FLAG_ENTITIES`, C3, C4, D2 `DEBT_RELIEF_ALIASES`, Part E); B3 hand-kept `FIELD_ORDER_PAYEE_FORMS`; E1 and E3 `OWNER_NAMED_PAYEES` (the three funders, the `debt_relief` key). `PAYEE_GROUP_REGISTRIES` does not change |
| `analysis/flag_groups.py` | Modify | D1: the twelfth group |
| `analysis/detect.py` | Modify | C2 `FlaggedPositionMatch.review_required`; C10 grouping of unnamed potential payees |
| `analysis/metrics.py` | Modify | C10 `potential_lenders_detected` counts labels |
| `analysis/serialization.py` | Modify | C2 `_flagged_dict` carries `review_required` |
| `tools/lender_ledger.py` | Modify | C1 `ROUTED_REVIEW_GROUPS`, `review_flag_entities`; B3 the field-order validator; D2 the `debt_relief` table, its generic words and collision check; D4 the routing of its review entities |
| `tools/lender_census.py` | Modify | D2 the generic words |
| `tools/build_lender_registry.py` | Modify | C1 renders `REVIEW_FLAG_ENTITIES` and its admission sentence |
| `docs/lender-registry-ledger.json` | Modify | C1 (Table Rock, FleetLogic, Westlake split), C3 renames, C4 notes, Part E entities |
| `docs/lender-registry-evidence.md` | Regenerate | `python -m tools.build_lender_registry --write` after every ledger edit |
| `webapp/app.py` | Modify | C2 the package and export `review_required`; C10 the package potential rows key by label |
| `webapp/static/app.js` | Modify | C2 the "Unconfirmed" line; C10 the ledger filter reads the label; D1 the Debt relief label and tag |
| `webapp/templates/index.html` | Modify | F1 the script version `?v=lender-detection-2` |
| `webapp/artifact_cache.py` | Modify | F1 `ANALYSIS_STAGE_VERSION = 22` |
| `docs/superpowers/specs/2026-09-24-lender-detection-design.md`, `docs/superpowers/plans/2026-09-24-lender-detection.md`, `docs/transaction-classification.md` | Modify | F2, F3 |
| `tests/test_d6_helpers.py` | Create | 0.1, 0.2 |
| `tests/test_d6_skips.py` | Create | 0.3, A1-A13 |
| `tests/test_rule_extensions_53.py` | Create | B1, B2, B4, B6, B7, B8 |
| `tests/test_field_order_payees.py` | Create | B3 |
| `tests/test_payroll_providers.py` | Create | B5 |
| `tests/test_unconfirmed_flag_payees.py` | Create | C1, C2 |
| `tests/test_payee_naming_53.py` | Create | C5-C8 |
| `tests/test_potential_payee_labels.py` | Create | C9, C10 |
| `tests/test_debt_relief_group.py` | Create | D1-D4 |
| `tests/test_registry_additions_53.py` | Create | E1-E4 |
| `C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/e/research_ledger.py` | Create (scratch, never committed) | E0: the VERIFIED gate and the ledger additions |
| `C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/family_drops.py` | Exists (scratch) | F4: rows of each family before and after |
| existing tests | Modify | the pins below |

## Pin ledger (every existing assertion this plan moves)

Line numbers are those at `0935061`.

| # | Location | Today | After | Task | Cause |
|---|---|---|---|---|---|
| 1 | `tests/test_recurring_fixed_debits.py:190-192` (`_d6_methods`, amount `-10.0`) | seven `test_words_that_only_look_like_compensation_stay_in_d6` cases promote at $10 | the helper uses `-100.0`; every case still promotes | A10 | the $25 floor for unnamed payees (measured: exactly these 15 tests move, 2026-09-27) |
| 2 | same file `:310-313` and `:340-344` (`test_weekly_push_payments_to_one_masked_recipient_are_still_promoted`, `test_only_the_recipient_with_three_weekly_dates_is_promoted`, `-10.0` rows) | promote at $10 | the rows use `-100.0` | A10 | as row 1 |
| 3 | `tests/test_unknown_payee_naming.py:87` | `("ACH DEBIT MCA SERVICING 0001", UNIDENTIFIED)` | `("ACH DEBIT MCA SERVICING 0001", "MCA servicer (funder not identified)")` | C9 | the D10 fixed label |
| 4 | `tests/test_flag_groups.py:16-45` | eleven groups; `len(FLAG_GROUP_BY_STATE) == 10` | twelve groups, `debt_relief` last; 11 states | D1 | owner ruling (2) |
| 5 | `tests/test_flagged_view.py:29-37` | eleven keys | twelve, `debt_relief` last | D1 | as row 4 |
| 6 | `tests/test_webapp_settings.py:17-27` | eleven `flag_*` keys | plus `"flag_debt_relief": True` | D1 | as row 4 |
| 7 | `tests/test_webapp_flagged_dashboard.py:465-466` `GROUP_KEYS` | eleven | plus `"debt_relief"` | D1 | as row 4 |
| 8 | `tests/test_webapp_flagged_dashboard.py:712` | `app.js?v=lender-detection-1` | `app.js?v=lender-detection-2` | F1 | `app.js` changes (C2, C10, D1) |
| 9 | `tests/test_webapp_reanalysis.py:983, 1049-1050` (wording) and `:1059` | "eleven flag groups"; version `5.2` | "twelve"; `5.3` | D1, F1 | as row 4; F1 |
| 10 | `tests/test_classification_registry_groups.py:12-29, 76-81` (extended, not moved) | 16 tables | plus `DEBT_RELIEF_ALIASES` in `GROUP_TABLES` and in the out-of-the-matcher list; `PAYEE_GROUP_REGISTRIES` and its test unchanged | D2 | debt relief is a table of its own, never a known-payee registry |
| 11 | `tests/test_build_lender_registry.py:361-367` | ten owner-named groups | plus `"debt_relief"` | E3 | owner ruling (2) names four payees; three are admitted (Resolve Capital stays under review) |
| 12 | `tests/test_lender_registry_drift.py:23` | `render_block(render_tables(entities))` | `render_block(render_tables(entities), lender_ledger.review_flag_entities(entities))` | C1 | the new rendered map |
| 13 | `tests/test_webapp_flagged_positions.py:643-644` `C5_POSITION_KEYS` | twelve keys | plus `"review_required"` | C2 | the unconfirmed marker |
| 14 | `tests/test_flag_group_states.py:57-61`, `tests/test_artifact_cache.py:487-496`, `tests/test_lender_census.py:36-37`, `tests/flagged_payloads.py:15-17` | 5.2 / 21 | 5.3 / 22 | F1 | versions |
| 15 | `tests/flag_group_fixtures.py:26-38` `FAKE_PAYEES` | one payee per ten states | plus `"FABRICATED DEBT RELIEF": ("Fabricated Debt Relief", "debt_relief")` | D1 | every state has a fabricated payee (`fake_match` stands in for the D3 index too) |
| 16 | `tests/test_new_statement_corpus.py:153` (navigant `"lenders"`) | `(0, 0.00, 3, 108.00)` | `(0, 0.00, 0, 0.00)` | B5 | its three D6 rows are a payroll provider's weekly billing, now `payroll` (measured on the committed fixture, 2026-09-27; the three rows were `potential_lender` / weekly fixed debit and become `payroll` / `payroll`; its channel counts do not move) |
| 17 | `tests/test_lender_insurance_classification.py:364` | `candidate.funder == "Unidentified lender obligation"` | `"Unidentified lender obligation (125.00)"` | C10 | an unnamed payee's line carries its amount |
| 18 | `tests/test_flagged_positions_payload.py:65-101` `EXPECTED_POSITIONS` | twelve keys per position | plus `"review_required": False` | C2 | the unconfirmed marker |
| 19 | `tests/test_factoring_credits.py:151-154` | the C5 key list | plus `"review_required"` last | C2 | as row 18 |
| 20 | `tests/test_webapp_flagged_positions.py:636-637` | the package item key list | plus `"review_required"` last | C2 | as row 18 |
| 21 | `tests/flagged_payloads.py:112-128` (`with_flagged_rows`) | positions without the marker | each position carries `review_required` | C2 | the fixtures follow the contract |
| 22 | `tests/test_build_lender_registry.py:68` (the name only) | `…_defines_fourteen_empty_tables` | `…_defines_fifteen_empty_tables` | D2 | wording |

How these rows were measured:
- The pattern prototypes in `.../work/plan53/proto/proto_plugin.py` ran SEL-CLASSIFIER with each generic rule in memory. The floor moved exactly rows 1-2. The channel-vocabulary rule, the Part B patterns and the naming rules C1/C2/N1/N2 moved nothing (757-894 passed).
- A scratch copy of the tree with Parts 0, A and B applied as this plan writes them (`.../work/plan53/protorepo`, not a git checkout) ran SEL-CLASSIFIER plus the new test files. The only moves were rows 1, 2 and 16: 1,074 tests, all passing once those were re-pinned.
- The same copy with Parts C, D and E applied (E's entities carrying a fabricated verify verdict, in the copy only) moved exactly rows 3-7, 11-13 and 15-21 (rows 9, 10 and 22 are wording or extensions, and rows 8 and 14 are F1's). SEL-CLASSIFIER, SEL-REGISTRY, SEL-WEBAPP and every new file: 2,211 passed (with `tests/test_no_statement_hardcodes.py`, whose one known failure stays). The copy's full suite failed only the 16 known tests, six tests that need a git checkout (the copy is none), and the two exact-cent guards that A10's and A11's constants tripped; this plan writes those constants as whole numbers.
- Re-run after the plan review (2026-09-28): the copy carries the review's code (0.1's roots, 0.3's organisation-cue guard, A6's bound, B7's anchored ACHAT, D3's explicit `run_together=True`) and tests, and its ledger was rebuilt from `0935061` through the revised E0 gate with the research files' real r7 verdicts (no fabricated verdict). The same selections and every new file: 2,251 passed, and only the one known failure of `tests/test_no_statement_hardcodes.py`. No existing assertion outside this pin ledger moved. The review's new cases fail on the first draft's code (19 of them) and pass on the revision.

If a task moves any other existing assertion, stop and report it.

## Task order and dependencies

Tasks run **in this order on one branch**. Most of them touch `analysis/transaction_classifier.py`, so they are never run in parallel. "Needs" lists the tasks that must be merged into the branch first.

| Task | Needs | Task | Needs |
|---|---|---|---|
| 0.1 veto | none | B5 payroll | 0.1, 0.2 |
| 0.2 readers | 0.1 | B6 mortgage/own-loan/interest | none |
| 0.3 `_d6_skip`, channel words | 0.1, 0.2 | B7 POS labels | A1 |
| A1 card formats | 0.3 | B8 related-party loans | none |
| A2 p2p rails | 0.3 | C1 routing | none |
| A3 transfer templates | 0.3 | C2 unconfirmed marker | C1 |
| A4 cash, batch, tuition | 0.3 | C3 renames | none |
| A5 savings | 0.3 | C4 glued digits | none |
| A6 vendors and named non-lenders | 0.3 | C5 cue rules, legal-form cut | 0.1, 0.2 |
| A7 government | 0.3 | C6 template prefixes, Truist | C5 |
| A8 family support | 0.3, A7 | C7 wires | C6 |
| A9 owner pay, Payoneer | 0.3 | C8 printed NAME, CITY, ST | C5, A1 |
| A10 floor | 0.3 | C9 D10 label | none |
| A11 processor fees | 0.3 | C10 tab grouping | C8, C9 |
| A12 truncated insurers | 0.3 | D1 group and state; D2 table; D3 payee step; D4 routing | D1: none; D2: D1; D3: D2, B3; D4: C1, D2 |
| A13 telecom | 0.2, 0.3 | E0 gate; E1-E4 | C1-C4 and D2 (E3 also D3, D4), and VERIFIED research entries |
| B1 fee/NSF | none | F1 versions | every task above |
| B2 cheques | none | F2, F3 docs | F1 |
| B3 field-order payees | none | F4 verification | F1-F3 |
| B4 card wording, issuer-alone skip | B3, 0.3 | | |

Each task ends with an independent review against this plan. The orchestrator re-runs the task's commands before accepting it.

---

## Part 0 — Shared helpers

### Task 0.1: The prefix-tolerant financing veto

**Files:**
- Modify: `analysis/transaction_classifier.py`: new constants and two helpers directly after the `_MASKED_RECIPIENT_PATTERN` block (`:2098-2105`), before `def _has_ach_field_mark(` (`:2108`).
- Create: `tests/test_d6_helpers.py`

**Why:** Funders are paid by card, Zelle, Interac, bill pay and wire, so every 5.3 D6 skip needs one veto that never fires on a row naming financing. The card lender-risk verifier measured the whole-word veto missing 94 of 286 counted lenders. It also missed run-together and cut spellings the corpus prints (KOVOCREDIT, CONSTRULOANS, BYZFUNDER, FUNDIN, CAPITA, CLICKLEASE), and every collector named "Recovery", "Receivables" or "Collections". The roots therefore have no left word boundary.

The card verifier's REQUIRED alternation also carries SETTLE, CRED(?=IT|ORA|IBLY|\b) and ACCEPT, and the plan review (2026-09-28) restored them: the first draft left them out, and its prototype hid 'FAB DEBT SETTLEMENT, BROOKLYN, NY' (Bluevine), 'FAB DEBT SETTLEMENT Card spend', 'CREDIBLYCO, BROOKLYN, NY' and 'ZEL TO FAB SETTLEMENT …', which 5.2 reviews. SETTLE matters more with the Debt relief group: an unregistered settlement payee paid by card, Zelle or Interac stays reviewed, and only the registry (E3) names it debt relief. CRED is a root only before IT, ORA, IBLY or a word end (CREDIBLY, CREDORA, a cut CRED), never in INCREDIBLE. ACCEPT replaces ACCEPTANC. A4's own-batch templates ('BUS ONLINE ACH SETTLEMENT', 'ACH SETTLMT REL DATE FUND') still skip, because `_skips` removes the matched template text before the veto reads the row.

The veto reads the whole normalized row. The account holder's name is included on purpose: a holder named like a funder keeps its rows in review, which is the safe direction. The words a skip itself matched are removed first, so a skip's own template (STASH CAPITAL, DATE FUND, SMARTSAVE … ATLASFINANCIAL) never vetoes it.

- [ ] **Step 1: Write the failing test** `tests/test_d6_helpers.py`:

```python
"""5.3 (2026-09-27): the shared helpers every new D6 skip and rule reads. Fabricated descriptors only."""
from __future__ import annotations

import re

import pytest

from analysis.description_text import normalize_transaction_description as normalize
from analysis.transaction_classifier import _LEGAL_FORM_SUFFIXES, _names_financing, _skips


@pytest.mark.parametrize(
    "printed",
    [
        "FABRIKAM KOVOCREDIT", "FAB CONSTRULOANS", "FAB BYZFUNDER", "FAB GRP FUNDIN INVOICE", "FAB CAPITA INVOICES",
        "FABCO RECOVERY LLC", "FAB RECEIVABLES", "FAB COLLECTIONS", "FAB CLICKLEASE", "FAB LENDINGSERVICES",
        "FAB CAP LLC", "FAB MCA", "FAB RTR PMT", "FAB DAILY PMT", "FAB FINL", "FAB ACCEPTANCE CORP",
        "FAB MORTGAGE SERV", "FAB EQUIP", "FAB FACTORING", "FAB MERCHANT SVCS", "FAB REMITTANCE",
        # the card verifier's REQUIRED roots: a settlement payee, CRED-prefixed names, ACCEPT
        "FAB DEBT SETTLEMENT", "FAB SETTLE", "CREDIBLYCO", "CREDORA", "FAB CRED", "FAB ACCEPT CORP",
        "FAB DEBT SETTLEMENT, BROOKLYN, NY", "FAB DEBT SETTLEMENT Card spend", "CREDIBLYCO, BROOKLYN, NY",
        "ZEL TO FAB SETTLEMENT PNCAA0X7654321",
    ],
)
def test_the_veto_reads_run_together_cut_and_collector_names(printed):
    assert _names_financing(normalize(printed))


@pytest.mark.parametrize(
    "printed",
    ["FAB MART SPRINGFIELD IL", "CINTAS CORP", "PAT EXAMPLE", "FAB STREAMING CO", "ZEL TO PAT EXAMPLE", "KOODO MOBILE",
     "FAB INCREDIBLE PIZZA"],  # CRED is a root only before IT, ORA, IBLY or a word end
)
def test_rows_that_name_no_financing_are_not_vetoed(printed):
    assert not _names_financing(normalize(printed))


def test_the_skips_own_words_never_veto_it():
    text = normalize("Orig CO Name:Stash Capital Orig ID:0000 Ind Name:Pat Example")
    assert _names_financing(text)
    assert not _names_financing(text, besides="STASH CAPITAL")


def test_a_skip_fires_on_its_region_only_when_the_rest_of_the_row_names_no_financing():
    patterns = (re.compile(r"\bFAB WORD\b"),)
    assert _skips("FAB WORD 0001", patterns, "FAB WORD 0001 PAT EXAMPLE")
    assert not _skips("FAB WORD 0001", patterns, "FAB WORD 0001 FAB CAPITAL LLC")
    assert not _skips("NOTHING HERE", patterns, "NOTHING HERE FAB WORD")  # read on the region, not the row


def test_the_legal_form_suffixes():
    assert _LEGAL_FORM_SUFFIXES == frozenset({
        "LLC", "INC", "CORP", "CORPORATION", "COMPANY", "INCORPORATED", "LTD", "LIMITED", "LP", "LLP", "PLLC",
    })
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe -m pytest tests/test_d6_helpers.py -q -p no:cacheprovider`
Expected: FAIL with `ImportError: cannot import name '_LEGAL_FORM_SUFFIXES'`.

- [ ] **Step 3: Add the veto.** In `analysis/transaction_classifier.py`, directly before `def _has_ach_field_mark(`, insert:

```python
#: 5.3 (2026-09-27): the financing veto every 5.3 D6 skip reads. Funders ARE paid by card, Zelle, Interac, bill pay
#: and wire, so no skip fires on a row that names financing. The roots have no left word boundary, so a
#: run-together or cut name hits (KOVOCREDIT, CONSTRULOANS, BYZFUNDER, FUNDIN, CAPITA, FINANC, CLICKLEASE), and so
#: does a collector of MCA debt (RECOVERY, RECEIVABLES, COLLECTIONS). The card verifier's roots: SETTLE (an
#: unregistered debt-settlement payee stays reviewed; the registry alone names it debt relief), CRED before IT, ORA,
#: IBLY or a word end (CREDIBLY, CREDORA, a cut CRED; never INCREDIBLE) and ACCEPT (ACCEPTANCE). A skip's own matched
#: words are removed before the veto reads the row (_skips), so A4's 'BUS ONLINE ACH SETTLEMENT' template still skips.
#: The short abbreviations are whole words. Known over-reach, in the safe direction (the row stays in review):
#: CALENDAR, RELEASE, REFUNDABLE, FUNDRAISER, a processor's SETTLEMENT wording, ACCEPTED.
_FINANCING_ROOT_PATTERN = re.compile(
    r"(?:FUND|CAPITA|CAPTL|CRED(?=IT|ORA|IBLY|\b)|LOAN|LEND|FINANC|ADVANC|MERCH|RECOVER|RECEIVAB|COLLECT"
    r"|SERVICING|SERVICER|FACTOR|LEASE|LEASING|EQUIP|MORTG|ACCEPT|REMIT|SETTLE)"
    r"|\b(?:CAP|FIN|FINL|FNCL|ADV|MTG|MCA|RTR|SPV|DLY|DAILY|WKLY|WEEKLY)\b"
)
#: D11 and 5.3: the legal-form suffixes. A legal form names an organisation only after the name's first word.
_LEGAL_FORM_SUFFIXES = frozenset({
    "LLC", "INC", "CORP", "CORPORATION", "COMPANY", "INCORPORATED", "LTD", "LIMITED", "LP", "LLP", "PLLC",
})


def _names_financing(text: str, *, besides: str = "") -> bool:
    """5.3: whether a normalized row names financing anywhere but in `besides`, the words a D6 skip matched.

    Read on the whole row, the account holder's name included: a holder named like a funder keeps its rows in
    review, which is the safe direction. The skip's own words are removed first, so they never veto the skip."""
    rest = text.replace(besides, " ") if besides else text
    return _FINANCING_ROOT_PATTERN.search(rest) is not None


def _skips(region: str, patterns: Sequence[re.Pattern[str]], text: str) -> bool:
    """5.3: a D6 skip fires when one of `patterns` is found in `region` (the part of the row the skip reads) and
    the rest of the whole row `text` names no financing (`_names_financing`)."""
    for pattern in patterns:
        found = pattern.search(region)
        if found is not None and not _names_financing(text, besides=found.group(0)):
            return True
    return False
```

- [ ] **Step 4: Run the test.** Same command as Step 2. Expected: PASS (41 tests).

- [ ] **Step 5: Run SEL-CLASSIFIER.** Expected: 751 passed, 2 deselected (nothing reads the helpers yet).

- [ ] **Step 6: Commit.**

```
git -C C:/Users/GustavoPrietodePaula/work/ld-fp53 add analysis/transaction_classifier.py tests/test_d6_helpers.py
git -C C:/Users/GustavoPrietodePaula/work/ld-fp53 commit -m "classifier: the shared financing veto for 5.3 D6 skips" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 0.2: The payee-word readers

**Files:**
- Modify: `analysis/transaction_classifier.py`:
  - new constants after `_MAX_ENTITY_TOKENS = 4` (`:949`);
  - four readers directly after `def _is_reference_token(` (`:952-957`), before `def _unknown_payee_tokens(` (`:960`);
  - `_unknown_payee_tokens`'s own label-and-segment cut (`:968-971`) is replaced by a call to `_payee_region` (a pure refactor).
- Modify: `tests/test_d6_helpers.py`

**Why:** A skip reads the payee's words, never a receiver field, so an account holder whose own name (INDN / IND NAME) carries a skip word can never hide its funder. The readers are:
- `_payee_region`: D11's region, the text with originator labels removed, cut at the first ACH field segment;
- `_row_before_receiver`: the row up to its first receiver field. It keeps DES/entry fields, where 'DES:FACTS', 'DES:CHILD SUPP' and 'DES:SQ260512' print;
- `_leading_payee_words`: the payee's leading words after channel and bill-payment prefix words. The telecom verifier requires them: a carrier printed after the payee's own name, a wireless-dealer receiver in a label-less format, never decides;
- `_originator_segment`: D11's reading without the four-word cap and keeping channel words. Payroll N1 requires it: provider names are read there, never in receiver fields.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_d6_helpers.py`:

```python
from analysis.transaction_classifier import (  # noqa: E402
    _leading_payee_words,
    _originator_segment,
    _payee_region,
    _row_before_receiver,
    _unknown_payee_tokens,
)


def test_the_payee_region_drops_the_originator_label_and_stops_at_the_first_ach_field():
    text = normalize("Orig CO Name:Fabricated Widgets Orig ID:0000 Desc Date: CO Entry Descr:Payment")
    assert _payee_region(text).split() == ["FABRICATED", "WIDGETS"]


def test_the_row_before_the_receiver_keeps_the_entry_description_and_drops_the_holder():
    text = normalize("FAB SCHOOL DES:FACTS ID:0001 INDN:PAT EXAMPLE CO ID:0002 WEB")
    assert _row_before_receiver(text).split() == ["FAB", "SCHOOL", "DES", "FACTS", "ID", "0001"]
    assert _row_before_receiver("NO RECEIVER FIELD HERE") == "NO RECEIVER FIELD HERE"


@pytest.mark.parametrize(
    ("printed", "leading"),
    [
        ("PRE-AUTHORIZED PAYMENT FIDO MOBILE PAP", "FIDO MOBILE PAP"),
        ("ONLINE BANKING PAYMENT 1234 ROGERS WIRELESS", "ROGERS WIRELESS"),
        ("ELECTRONIC WITHDRAWAL TO ATT", "ATT"),
        ("RECURRING PAYMENT AUTHORIZED ON 01/05 VZWRLSS*APOCC VISB CARD 1234", "VZWRLSS APOCC VISB CARD"),
        ("ACH CORP DEBIT 00012345 FAB PARTNERS LLC BOOST MOBILE CUSTOMER ID 1", "CORP DEBIT"),
    ],
)
def test_the_leading_payee_words_skip_channel_and_prefix_words_and_stop_at_a_reference(printed, leading):
    assert _leading_payee_words(normalize(printed)) == leading


@pytest.mark.parametrize(
    ("printed", "segment"),
    [
        ("ACH DEBIT DATAPAY IN 1234 C 5678 BILLING 9", "ACH DEBIT DATAPAY IN"),
        ("PATRIOT SOFTWARE DES:PAYROLLTAX ID:0001 INDN:FAB HOLDER CO ID:0002 CCD", "PATRIOT SOFTWARE"),
        ("FABRIKAM FUNDER DES:PAYMENT ID:0001 INDN:TASC BUILDERS INC CO ID:0002 CCD", "FABRIKAM FUNDER"),
        # Wells Fargo's label-less form: the holder follows the date, which ends the originator.
        ("FABRIKAM FUNDER DEBIT CCD 0105 TASC BUILDERS INC", "FABRIKAM FUNDER DEBIT CCD"),
    ],
)
def test_the_originator_segment_never_reads_a_receiver_field(printed, segment):
    assert _originator_segment(normalize(printed)).split() == segment.split()


def test_the_d11_payee_words_are_unchanged_by_the_refactor():
    assert _unknown_payee_tokens(normalize("ACH DEBIT FABRICATED WIDGETS LLC 0001")) == ("FABRICATED", "WIDGETS", "LLC")
    assert _unknown_payee_tokens(normalize("FAB WIDGETS DES:PAYMENT ID:0001 INDN:PAT EXAMPLE")) == ("FAB", "WIDGETS")
```

- [ ] **Step 2: Run it and watch it fail.** Same command as Task 0.1. Expected: FAIL (`ImportError: cannot import name '_leading_payee_words'`).

- [ ] **Step 3: Add the constants.** After `_MAX_ENTITY_TOKENS = 4`, insert:

```python
#: 5.3: the receiver fields. The account holder's own name prints there (Bank of America INDN, Chase IND NAME).
_RECEIVER_NAME_FIELD = re.compile(r"\b(?:INDN|IND NAME|IND ID)\b")
#: 5.3: bill-payment prefix words a bank prints before the payee. The leading payee words start after them.
_LEADING_PREFIX_WORDS = frozenset({
    "BILL", "BILLS", "PRE", "AUTHORIZED", "AUTHORISED", "RECURRING", "RECUR", "INTERNET", "BANKING", "PAIEMENT",
    "FACTURE", "BM", "CABLE", "TV", "TELEPHONE", "PCS", "SVC", "ON",
})
```

- [ ] **Step 4: Add the readers.** Directly before `def _unknown_payee_tokens(`, insert:

```python
def _payee_region(text: str) -> str:
    """D11: the payee part of a normalized row: originator-name labels removed, cut at the first ACH field segment
    (so never an ID, INDN, IND NAME, CO ID or TRACE field). `_unknown_payee_tokens` reads its words."""
    text = _ENTITY_NAME_LABELS.sub(" ", text)
    segment = _ACH_FIELD_SEGMENT.search(text)
    return text[: segment.start()] if segment is not None else text


def _row_before_receiver(text: str) -> str:
    """5.3: the normalized row up to its first receiver field, so the account holder's own name never decides a D6
    skip. The entry-description fields stay (DES:FACTS, DES:CHILD SUPP). A row with no receiver field is read whole:
    a label-less format prints the holder unmarked, which the payee-word readers cover instead."""
    return _RECEIVER_NAME_FIELD.split(text, 1)[0]


def _leading_payee_words(text: str) -> str:
    """5.3: the payee's leading words: the payee region after channel words, bill-payment prefix words and any
    leading reference, up to the next reference token. A word printed after the payee's own name (a receiver in a
    label-less format) is never a leading word."""
    words: list[str] = []
    for token in _payee_region(text).split():
        if not words:
            if token in _ENTITY_NOISE or token in _LEADING_PREFIX_WORDS or _is_reference_token(token):
                continue
        elif _is_reference_token(token):
            break
        words.append(token)
    return " ".join(words)


def _originator_segment(text: str) -> str:
    """5.3 (payroll N1): D11's reading of the originator without the four-word cap and keeping channel words: the
    payee region up to the first reference token after a name word. Provider and benefit-administrator names are
    read here, never in a receiver field."""
    words: list[str] = []
    started = False
    for token in _payee_region(text).split():
        if _is_reference_token(token):
            if started:
                break
            continue
        words.append(token)
        started = started or (token not in _ENTITY_NOISE and len(token) > 1)
    return " ".join(words)
```

- [ ] **Step 5: Refactor `_unknown_payee_tokens`.** Replace its first four statements

```python
    text = _ENTITY_NAME_LABELS.sub(" ", text)
    segment = _ACH_FIELD_SEGMENT.search(text)
    if segment is not None:
        text = text[: segment.start()]
```

with

```python
    text = _payee_region(text)
```

- [ ] **Step 6: Run the tests.** `tests/test_d6_helpers.py`: PASS. SEL-CLASSIFIER: 751 passed, 2 deselected (a pure refactor plus new helpers).

- [ ] **Step 7: Commit.**

```
git -C C:/Users/GustavoPrietodePaula/work/ld-fp53 add analysis/transaction_classifier.py tests/test_d6_helpers.py
git -C C:/Users/GustavoPrietodePaula/work/ld-fp53 commit -m "classifier: payee-word readers for 5.3 skips (payee region, before receiver, leading words, originator)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 0.3: `_d6_skip`, `_keyword_recurrence_skip` and the channel-vocabulary rule

**Files:**
- Modify: `analysis/transaction_classifier.py`:
  - new `_CHANNEL_VOCABULARY`, `_names_only_channel_words`, `_d6_skip` and `_keyword_recurrence_skip` directly after `def _masked_recipient(` (`:2124-2127`), before `def _promotion_cadence(` (`:2130`);
  - the grouping loop of `classify_statement_transactions` (`:2202-2210`).
- Create: `tests/test_d6_skips.py`

**Why:** D6's payee key keeps bank channel words (CARD, PIN, PURCH, CASH, TELLER, BRANCH, CHK, BILL, RECURRING, AUTOPAY…) as a "payee". So every card, cash, cheque or bill-pay posting of one amount merges into one unnamed potential lender. Both structural critics named this the shared root: a group whose payee words are all channel vocabulary names no payee.

`OTHER`, `BANK` and the bare withdrawal abbreviations (`WD`, `WDL`, `WDRL`) stay out of the vocabulary on purpose. The hunt could not tell what 'Other Debit' (c00033), 'Bank Debit' (c00136) and 'Preauthorized Wd' (c00242) pay, so they stay in review. The veto still applies: 'RECURRING PAYMENT 0105 FAB CAPITAL' keeps its D6 review.

The rule also carries the card veto's organisation-cue guard, read on the payee region (plan review, 2026-09-28). D11's key stops at the first reference token once a name has started, so in every format that prints a reference before the merchant the key IS the template while the merchant is printed: 'Recurring Payment authorized on 01/02 Fab Holdings LLC Card 4321' keys as RECURRING AUTHORIZED ON, 'ONLINE BILL PAYMENT 1234567 TO FAB HOLDINGS LLC' as BILL, 'DEBIT CARD PURCH CARD ENDING IN 1234 FAB HOLDINGS LLC' as CARD PURCH CARD ENDING. Without the guard the first draft's prototype hid all three, which 5.2 reviews, and overrode the card veto's organisation part (A1). So a channel-word key is no payee only when no word of the payee region is an organisation cue (`_ORGANISATION_CUES`); a card, cash or bill-pay row that prints a company's name stays in review.

The admission test moves into one named function, so each Part A task adds one clause and the spec's D6 list stays readable. `_keyword_recurrence_skip` is the same hook for the financing-keyword recurrence (A7, A8).

- [ ] **Step 1: Write the failing test** `tests/test_d6_skips.py`:

```python
"""5.3 (2026-09-27): what D6 no longer takes (spec D6, clarified 2026-09-27 for 5.3). Fabricated descriptors only:
each keeps the bank's printed shape with invented names, amounts and dates."""
from __future__ import annotations

import pytest

from analysis.description_text import normalize_transaction_description as normalize
from analysis.schema import Statement
from analysis.transaction_classifier import (
    _d6_skip,
    _unknown_payee_tokens,
    classify_statement_transactions,
    classify_transaction,
)
from tests.flag_group_fixtures import txn

WEEKLY = (2, 9, 16, 23)
D6 = {("potential_lender", "recurring_fixed_debit")}
OTHER = {("other", "default")}


def _states(description: str, amount: float = -100.0, *, bank: str | None = None, account_name: str | None = None,
            days: tuple[int, ...] = WEEKLY) -> set[tuple[str, str]]:
    statement = Statement(
        bank=bank,
        account_name=account_name,
        transactions=[txn(f"2054-01-{day:02d}", description, amount) for day in days],
    )
    return {(record.classification, record.match_method) for record in classify_statement_transactions(statement)}


def _reason(description: str, amount: float = -100.0) -> str | None:
    record = classify_transaction(description, amount)
    return _d6_skip(record, _unknown_payee_tokens(record.normalized_description))


@pytest.mark.parametrize(
    ("description", "reason"),
    [
        ("TRANSFER TO PAT EXAMPLE", "transfer_word"),
        ("ACH DEBIT FABRICATED COMMISSION", "compensation"),
        ("TST*FABRICATED GRILL AUSTIN TX", "card_purchase_posting"),
        ("ACH DEBIT FABRICATED WIDGETS LLC", None),
    ],
)
def test_the_5_2_skips_keep_their_reasons(description, reason):
    assert _reason(description) == reason


CHANNEL_ONLY = [
    "WITHDRAWAL MADE IN A BRANCH/STORE",
    "CASH WITHDRAWAL",
    "TELLER WITHDRAWAL",
    "ATM DEBIT 1234 FAB MAIN ST",
    "ONLINE BILL PAYMENT 1234567",
    "RECURRING PAYMENT",
    "AUTOPAY",
    "MISCELLANEOUS DEBIT",
    "DEBIT CARD PURCH CARD ENDING IN 1234 FAB MART",
    "COUNTER WITHDRAWAL",
]


@pytest.mark.parametrize("description", CHANNEL_ONLY)
def test_a_group_whose_payee_words_are_all_channel_words_is_no_payee(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "Other Debit",           # the intake lost the payee: the hunt could not tell (c00033's shape)
        "Bank Debit",            # a bank template with no payee: unclear (c00136's shape)
        "Preauthorized Wd",      # prints no payee at all: unclear (c00242's shape)
        "RECURRING PAYMENT 0105 FAB CAPITAL",  # channel words only, but the row names financing
        # D6's key stops at the first reference, so it is the template; the payee region names an organisation
        "Recurring Payment authorized on 01/02 Fab Holdings LLC Card 4321",
        "ONLINE BILL PAYMENT 1234567 TO FAB HOLDINGS LLC",
        "MOBILE PAYMENT 1234 FAB HOLDINGS GROUP LLC",
        "DEBIT CARD PURCH CARD ENDING IN 1234 FAB HOLDINGS LLC",
        "ACH DEBIT PAT EXAMPLE",
    ],
)
def test_unclear_templates_and_vetoed_rows_stay_in_review(description):
    assert _states(description) == D6
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe -m pytest tests/test_d6_skips.py -q -p no:cacheprovider`
Expected: FAIL (`ImportError: cannot import name '_d6_skip'`).

- [ ] **Step 3: Add the rule and the two hooks.** Directly after the body of `def _masked_recipient(`, insert:

```python
#: 5.3 (2026-09-27): bank channel vocabulary. A D6 group whose payee words are all channel words names no payee:
#: a card, cash, cheque or bill-pay posting printed without its merchant or recipient. OTHER, BANK and the bare
#: withdrawal abbreviations (WD, WDL, WDRL) are left out on purpose: 'Other Debit', 'Bank Debit' and 'Preauthorized
#: Wd' rows stay in review, because the 2026-09-27 hunt could not tell what they pay.
_CHANNEL_VOCABULARY = frozenset({
    # card postings
    "CARD", "CARDS", "CRD", "DBT", "DBCRD", "PIN", "PURCH", "PURCHASE", "PUR", "POS", "DDA", "VISA", "MASTERCARD",
    "MC", "TRANSACTION", "SPEND", "RETAIL", "ACHAT", "AUTHORIZED", "AUTHORISED", "ON", "ENDING",
    # cash
    "ATM", "ABM", "CASH", "TELLER", "COUNTER", "BRANCH", "STORE", "MADE", "IN", "NETWORK", "WITHDRWL", "RETRAIT",
    # cheques and items
    "CHK", "CK", "CHQ", "DRAFT", "SHARE", "ITEM",
    # bill pay, push and banking channels
    "BILL", "BILLS", "BILLPAY", "RECURRING", "RECUR", "AUTOPAY", "MISCELLANEOUS", "INTERNET", "MOBILE", "PHONE",
    "TELEPHONE", "SENT", "PMNT", "VIREMENT", "ENVOYE", "PAID",
})


def _names_only_channel_words(payee: Sequence[str], text: str) -> bool:
    """5.3: the D6 payee words are all channel words and the payee region of the normalized row `text` prints no
    organisation cue. D11's key stops at the first reference token once a name has started, so a format that prints
    a reference before the merchant keys as its template ('RECURRING PAYMENT AUTHORIZED ON 01 02 FAB HOLDINGS LLC
    CARD 4321' keys as RECURRING AUTHORIZED ON): the cue keeps such a row in review, as the card veto does (A1)."""
    return (
        bool(payee)
        and all(token in _CHANNEL_VOCABULARY for token in payee)
        and not any(token in _ORGANISATION_CUES for token in _payee_region(text).split())
    )


def _d6_skip(record: TransactionClassification, payee: tuple[str, ...]) -> str | None:
    """Why D6 (spec D6 and its clarifications) does not take this default debit, or None when it may.

    `payee` is the row's D11 payee words (`_unknown_payee_tokens`). Every clause added in 5.3 reads the payee's
    words (never a receiver field) and carries the shared financing veto (`_names_financing`)."""
    text = record.normalized_description
    if _matches_any(text, _TRANSFER_WORD_PATTERNS):
        return "transfer_word"
    if _matches_any(text, _COMPENSATION_WORD_PATTERNS):
        return "compensation"
    if _is_card_purchase_posting(record):
        return "card_purchase_posting"
    if _names_only_channel_words(payee, text) and not _names_financing(text):
        return "channel_words_only"
    return None


def _keyword_recurrence_skip(record: TransactionClassification) -> str | None:
    """Why the financing-keyword recurrence (recurring_financing_counterparty) does not take this row, or None.

    Its rows carry a financing word by definition (LOAN, ADVANCE, FINANCE, FUNDING…), so these clauses carry no
    financing veto; each names a payee that is never a lender (A7, A8)."""
    return None
```

- [ ] **Step 4: Use them in the grouping loop.** In `classify_statement_transactions`, replace

```python
        if record.match_method == "financing_keyword_review" and record.canonical_entity:
            keyword_groups.setdefault(key, []).append(index)
        elif (
            record.match_method == "default"
            and not _matches_any(record.normalized_description, _TRANSFER_WORD_PATTERNS)
            and not _matches_any(record.normalized_description, _COMPENSATION_WORD_PATTERNS)
            and not _is_card_purchase_posting(record)
        ):
            fixed_debit_groups.setdefault((*key, _masked_recipient(record)), []).append(index)
```

with

```python
        if record.match_method == "financing_keyword_review" and record.canonical_entity:
            if _keyword_recurrence_skip(record) is None:
                keyword_groups.setdefault(key, []).append(index)
        elif record.match_method == "default" and _d6_skip(record, payee) is None:
            fixed_debit_groups.setdefault((*key, _masked_recipient(record)), []).append(index)
```

- [ ] **Step 5: Run the tests.** `tests/test_d6_skips.py`: PASS (23 tests). SEL-CLASSIFIER: 751 passed, 2 deselected. The in-memory prototype of this rule moved no existing test on 2026-09-27; the organisation-cue guard only keeps more rows in review.

- [ ] **Step 6: Commit.**

```
git -C C:/Users/GustavoPrietodePaula/work/ld-fp53 add analysis/transaction_classifier.py tests/test_d6_skips.py
git -C C:/Users/GustavoPrietodePaula/work/ld-fp53 commit -m "d6: one named skip test; a payee made only of bank channel words is no payee" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Part A — D6-only skips (rows stay `other` / `default`)

Every Part A task follows the same steps:
1. Append its fabricated tests to `tests/test_d6_skips.py`.
2. Run that file and watch the new tests fail.
3. Add its constants directly above `def _d6_skip(`.
4. Add one clause to `_d6_skip` (or to `_keyword_recurrence_skip`), directly before `return None`.
5. Run `tests/test_d6_skips.py` (PASS), then SEL-CLASSIFIER. Expect no failure outside the task's pin-ledger rows.
6. Commit.

The run command is `cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe -m pytest tests/test_d6_skips.py -q -p no:cacheprovider`. The reach figures are the hunt's measurements on the 7,241-account corpus plus the tryout host (`digest_families.md`), in rows and account occurrences. The cache holds some statements 2-3 times, so occurrences overstate distinct businesses.

### Task A1: Card postings the POS rule does not read (card_purchase_format)

**Files:** Modify `analysis/transaction_classifier.py` (new constants above `def _d6_skip(`; the body of `_is_card_purchase_posting`, `:2115-2121`); append to `tests/test_d6_skips.py`.

**Needs:** 0.3.

**Why:** 917 rows / 130 occurrences, 28 keys. With the widened veto the card lender-risk verifier measured about 854 corpus rows leaving. c00120 (RTS Carrier Services, SERVICES), c00159 (CORP), c00149 ('Capital …') and c00175 (a bank) stay in review.
- MOBILE, RETAIL and PIN PURCHASE and ACHAT go into the POS rule itself (B7), so they are not in this list.
- Chase 'Payment Sent … Card nnnn' (c00022) leaves through A2's PAYMENT SENT rail.
- Known non-match, recorded: Bluevine's glued 'CITY, NYUS' variant.
- The veto's SETTLE, CRED and ACCEPT roots (0.1) keep a debt-settlement or CRED-prefixed payee paid by card in review (plan review 2026-09-28: 'FAB DEBT SETTLEMENT, BROOKLYN, NY', 'CREDIBLYCO, BROOKLYN, NY').
- Known policy (spec): an unregistered funder printed with no financing root and no organisation word, collecting by debit card in one of these formats, is hidden. So is every unregistered funder printed 'DEBIT CARD PURCHASE' today. The registry, not D6, is the control for that case.

- [ ] **Step 1: Tests.** Append:

```python
# --- A1: card postings the POS rule does not read -----------------------------------------------------------------

CARD_POSTINGS = [
    ("Fabricated Donuts Card spend", None),                                        # Square Checking
    ("DEBIT CARD RECURRING PYMT FAB.COM/BILL 01-05 CA 4321", None),                # Truist
    ("Debit Card Debit", None),
    ("Card", None),                                                                # a type-only export row
    ("FAB MART 1234 01/05 1234567890 PURCHASE FAB MIAMI FL", None),                # BofA merchant-first
    ("DBT CRD 0105 01/05/54 FAB C12345", None),
    ("Recurring Payment authorized on 01/02 Fab Web S123456789012345 Card 4321", None),  # Wells Fargo (c00148's shape)
    ("PIN DEBIT FAB MART SPRINGFIELD IL", None),
    ("RECURRING DEBIT CARD FAB STREAMING 800-555-0100 CA", None),                  # PNC
    ("DEBIT CARD TRANSACTION FAB MART SPRINGFIELD IL", None),                      # Regions
    ("VISA DDA PUR AP FAB MART SPRINGFIELD IL", None),                             # TD Bank without its star
    ("FAB DINER42, SPRINGFIELD, IL", "Bluevine"),
    ("Fab Mart 1234567, TOWNVILLE , CA , USA", "Lead Bank (Found)"),
    ("Fabricated Donuts", "Wealthsimple"),                                          # a bare merchant
]


@pytest.mark.parametrize(("description", "bank"), CARD_POSTINGS)
def test_card_postings_in_every_bank_format_are_never_a_d6_recurrence(description, bank):
    assert _states(description, bank=bank) == OTHER


@pytest.mark.parametrize(
    ("description", "bank"),
    [
        ("Capital Fuel Card spend", None),                                           # a financing root
        ("Fabricated Holdings LLC Card spend", None),                                # an organisation word
        ("DEBIT CARD RECURRING PYMT FAB EQUITIES LLC 800-555-0100 NY 4321", "Truist"),
        ("Recurring Payment authorized on 01/02 Fabcreditacceptance NY S123456789012345 Card 4321", None),
        ("FABCO RECOVERY LLC, BROOKLYN, NY", "Bluevine"),
        ("FAB DEBT SETTLEMENT, BROOKLYN, NY", "Bluevine"),                         # a settlement payee
        ("FAB DEBT SETTLEMENT Card spend", None),
        ("CREDIBLYCO, BROOKLYN, NY", "Bluevine"),                                  # a CRED-prefixed name
        ("FABRICATED, INC., NEW YORK, NY", "Bluevine"),
        ("FAB NATIONAL A BANK OF TULSA, TULSA, OK", "Bluevine"),                     # a bank: stays reviewed
        ("FAB DINER42, SPRINGFIELD, IL", "Wells Fargo"),                             # the suffix is read on two banks only
        ("Pre-authorized Debit to FABRICATED WIDGETS", "Wealthsimple"),              # a Wealthsimple channel label
        ("Fab Credit Union", "Wealthsimple"),
        ("ACH DEBIT FABRICATED WIDGETS LLC", None),
        ("FABRICATED WIDGETS DES:PURCHASE ID:0000 INDN:PAT EXAMPLE CO ID:0000 CCD", None),
        ("PURCHASE FABRICATED FUNDING", None),                                       # an ACH entry description first
    ],
)
def test_card_formats_never_hide_a_row_that_names_financing_or_an_organisation(description, bank):
    assert _states(description, bank=bank) == D6


def test_a_card_posting_leaves_the_recurring_debit_view():
    from analysis.detect import find_recurring_debits

    statement = Statement(transactions=[txn(f"2054-01-{day:02d}", "Fabricated Donuts Card spend", -100.0)
                                        for day in WEEKLY])
    assert find_recurring_debits(statement) == []
```

- [ ] **Step 2: Run.** Expected: the 14 `CARD_POSTINGS` cases and the recurring-view test FAIL (they are D6 today).

- [ ] **Step 3: Constants.** Above `def _d6_skip(`, insert:

```python
#: 5.3 (2026-09-27): card-posting labels the POS rule does not read, read on the normalized row with no ACH guard,
#: as _POS_PATTERNS are. MOBILE, RETAIL and PIN PURCHASE and the French ACHAT join the POS rule itself (B7).
_CARD_POSTING_LABEL_PATTERNS = (
    re.compile(r"\b\d{2} \d{2} \d{6,} (?:MOBILE )?PURCHASE\b"),        # Bank of America merchant-first card row
    re.compile(r"\bDE?BI?T CRD\b"),                                     # DBT CRD, DEBIT CRD
    re.compile(r"^DEBIT CARD\b"),                                       # Truist DEBIT CARD RECURRING PYMT / MISC DEBIT
    re.compile(r"^CARD$"),                                              # a type-only card row (CSV export)
    re.compile(r"\bCARD SPEND$"),                                       # Square Checking '<merchant> Card spend'
    re.compile(r"\bAUTHORI[ZS]ED ON \d{2} \d{2}\b.*\bCARD \d{4}$"),     # Wells Fargo '... authorized on mm/dd ... Card nnnn'
    re.compile(r"\bPIN DEBIT\b"),
    re.compile(r"\bRECURRING (?:DEBIT )?CARD\b"),                       # PNC RECURRING DEBIT CARD
    re.compile(r"\bCARD TRANSACTION\b"),                                # Regions
    re.compile(r"\bPURCH\b"),                                           # Citi DEBIT PURCH
    re.compile(r"\bCARD ENDING IN\b"),
    re.compile(r"\bDDA PUR\b"),                                         # TD Bank VISA DDA PUR (without its star)
)
#: 5.3: Wealthsimple Chequing prints a card purchase as the bare merchant; its other debits carry one of these words
#: (seen in 32 corpus accounts; its bill-payment print form is unverified: re-check when one arrives).
_WEALTHSIMPLE_CHANNEL_PATTERN = re.compile(
    r"\b(?:TRANSFER|TRANSFERT|INTERAC|PRE ?AUTHORI[ZS]ED|PAD|DEBIT|BILL|PAYMENT|EFT|WITHDRAWAL|DEPOSIT|CHEQUE|CHECK|"
    r"LOAN|WIRE|FEE)\b"
)
#: 5.3: the card network's merchant location, 'NAME, CITY, ST' (Bluevine) or 'NAME ###, CITY , ST , USA' (Found),
#: read on the printed text of those two banks' rows only, and only without an ACH field mark. Bluevine's glued
#: 'CITY, NYUS' variant is a known non-match.
_CARD_LOCATION_SUFFIX_PATTERN = re.compile(
    r",\s*[A-Za-z][A-Za-z .'-]*?\s*,\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|"
    r"MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|PR|GU|VI|AB|BC|MB|NB|NL|NS|NT|NU|"
    r"ON|PE|QC|SK|YT)\s*(?:,\s*USA)?\s*$"
)
_CARD_LOCATION_SUFFIX_BANKS = frozenset({"Bluevine", "Lead Bank (Found)"})
#: 5.3: besides the shared roots, a card-format skip never fires on a row that names a bank, an investment firm or an
#: organisation (an organisation cue or a financing-organisation word): funders ARE paid by debit card in these
#: formats (card lender-risk verifier: Dakota Financial on Bluevine, Hillcrest and CNAC on Square 'Card spend').
_CARD_POSTING_VETO_PATTERN = re.compile(
    r"(?:BANK|BANQUE|INVEST)"
    r"|\b(?:HOLDINGS?|PARTNERS?|VENTURES?|EQUITIES|GROUP|SOLUTIONS?|ENTERPRISES?|RESOURCES?|LP)\b"
)


def _card_posting_vetoed(text: str) -> bool:
    return (
        _names_financing(text)
        or _CARD_POSTING_VETO_PATTERN.search(text) is not None
        or any(token in _ORGANISATION_CUES for token in text.split())
    )
```

- [ ] **Step 4: Extend `_is_card_purchase_posting`.** Replace its body with the following. The two 5.1 marks are unchanged, and the new clauses follow them:

```python
def _is_card_purchase_posting(record: TransactionClassification) -> bool:
    if _CARD_PURCHASE_POSTING_PATTERN.match(record.normalized_description):
        return True
    if _PROCESSOR_MERCHANT_MARK_PATTERN.search(record.original_description or "") and not _has_ach_field_mark(record):
        return True
    # 5.3 (2026-09-27): the bank card formats the POS rule does not read, never on a row that names financing,
    # a bank or an organisation (read on the whole row, not on the D11 payee words, which are the card template).
    text = record.normalized_description
    if _card_posting_vetoed(text):
        return False
    if _matches_any(text, _CARD_POSTING_LABEL_PATTERNS):
        return True
    if record.bank == "Wealthsimple" and not _WEALTHSIMPLE_CHANNEL_PATTERN.search(text):
        return True
    return bool(
        record.bank in _CARD_LOCATION_SUFFIX_BANKS
        and _CARD_LOCATION_SUFFIX_PATTERN.search(record.original_description or "")
        and not _has_ach_field_mark(record)
    )
```

`_d6_skip` already calls `_is_card_purchase_posting`, so no clause is added. The constants move above `def _is_card_purchase_posting(` if the reviewer prefers them next to their reader. Keep them above `def _d6_skip(` or directly above `_is_card_purchase_posting`, but in one place.

Note for C5: `_ORGANISATION_CUES` loses `CO` in C5. A Bluevine card row in Colorado ('…, DENVER, CO') is vetoed until then and skipped after it, which is the intended end state.

- [ ] **Step 5: Run** `tests/test_d6_skips.py` (PASS) and SEL-CLASSIFIER (751 passed, 2 deselected). `tests/test_recurring_fixed_debits.py::test_card_purchase_postings_are_never_a_d6_recurrence` and the star-mark tests must still pass unchanged.

- [ ] **Step 6: Commit.**

```
git -C C:/Users/GustavoPrietodePaula/work/ld-fp53 add analysis/transaction_classifier.py tests/test_d6_skips.py
git -C C:/Users/GustavoPrietodePaula/work/ld-fp53 commit -m "d6: card postings in the bank formats the POS rule does not read, never over financing or an organisation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task A2: Person-to-person and wallet rails (p2p_payment_app)

**Files:** Modify `analysis/transaction_classifier.py` (constants above `def _d6_skip(`; one clause); append to `tests/test_d6_skips.py`.

**Needs:** 0.3.

**Why:** 369 rows / 101 occurrences, 15 keys, plus 38 collision rows that are transfers: RBC 'Virement par Banque en direct' (c00096) and CIBC glued 'INTERNET TRANSFER<ref>' (c00128). They are D6-only on purpose: the transfer rule runs before the known payee, so widening `_TRANSFER_PATTERNS` would hide CanaCap. The glued transfer form and RTP are in A3, under the unidentified-payee guard as well. Every rail sits behind the financing veto, because funders are paid by Zelle and Interac ('Zel To … Global Funding' stays in review, and since the review's SETTLE root so does a settlement payee paid by Zelle).

- [ ] **Step 1: Tests.** Append:

```python
# --- A2: person-to-person, wallet and card-push rails -------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "Virement envoye Pat Example",
        "Virement par Banque en direct - 1234",                    # RBC's French online-banking transfer
        "Zel To Pat Example PNCAA0X7654321",
        "PMNT SENT 0105 APPLE CASH 1234 CA",
        "Payment Sent 01/05 Pat Example CA Card 4321",            # Chase's card push (c00022's shape)
        "FAB GOODS IAT PAYPAL",
        "WISE US INC DES:WISE ID:0001",
        "GREENLIGHT DES:APP ID:0001",
    ],
)
def test_person_to_person_and_wallet_rails_are_not_d6_payees(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "Virement envoye Fabrique Funding Inc",
        "Zel To Fabricated Global Funding PNCAA0X7654321",
        "PMNT SENT 0105 FABRICATED FUNDING LLC",
        "WISE CHOICE LLC",                                         # bare WISE is never a rail
        "ZEL TO FAB SETTLEMENT PNCAA0X7654321",                    # a settlement payee paid by Zelle
        "FINWISE DES:LOANPMT ID:0001",
    ],
)
def test_a_rail_that_names_financing_stays_in_review(description):
    assert _states(description) == D6
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS. 'PMNT SENT … APPLE CASH' and 'Payment Sent …' may already pass through 0.3's channel rule, which is fine.

- [ ] **Step 3: Constants.**

```python
#: 5.3 (2026-09-27): person-to-person, wallet and card-push rails the transfer rule does not read. D6 only: the
#: transfer rule runs before the known payee (step 6 before 7), so widening it would hide a counted funder paid by
#: e-Transfer. VIREMENT covers every French RBC transfer line (Interac e-Transfer, 'Virement envoye', 'Virement par
#: Banque en direct'). Bare WISE is never a rail (WISE CHOICE, FINWISE).
_P2P_RAIL_PATTERNS = (
    re.compile(r"\bVIREMENTS?\b"),
    re.compile(r"\bZEL (?:TO|FROM)\b"),
    re.compile(r"^(?:PMNT|PAYMENT) SENT \d{2} ?\d{2}\b"),
    re.compile(r"\bAPPLE (?:CASH|WALLET)\b"),
    re.compile(r"\b(?:WISE (?:INC|US INC)|TRANSFERWISE)\b|\bDES WISE\b"),
    re.compile(r"\bIAT PAYPAL\b"),
    re.compile(r"\bGREENLIGHT DES APP\b"),
)
```

- [ ] **Step 4: Clause** in `_d6_skip`, before `return None`:

```python
    if _skips(_row_before_receiver(text), _P2P_RAIL_PATTERNS, text):
        return "p2p_rail"
```

- [ ] **Step 5: Run** the file and SEL-CLASSIFIER.

- [ ] **Step 6: Commit** `"d6: person-to-person, wallet and card-push rails, never over financing"` (same `git add` paths as A1).

---

### Task A3: Transfer templates (internal_transfer, the glued transfer word, RTP)

**Files:** as A2. **Needs:** 0.3.

**Why:** 357 rows / 32 occurrences, 8 keys. The lender-risk verifier split the skip in two:
- today's `TRANSFER|XFER|TFR` skip stays unconditional (5.2);
- the new templates skip only a payee that names no organisation, and only a row that names no financing.

TRSF and TRANSFR are dropped (no evidence). TRNSFR (Chase 'EXT TRNSFR', 140 corpus rows) and TRSFR stay. The Atlas sweep needs SMARTSAVE with ATLASFIN.

P2 ('TO <account type> <number>', the BofA banking-centre template, c00069, 54 rows) extends the 5.2 transfer policy to a row printing no transfer word. It is listed for the owner, and striking it keeps c00069 in review.

The structural critic's RTP / Real Time Payment / FedNow rails (medium) join here, under the same guards. An RTP to a company stays in review.

- [ ] **Step 1: Tests.** Append:

```python
# --- A3: transfer templates -----------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "TRF DT INTERNET 12345",
        "INTERNET XFR TO CHECKG x1234",
        "Internet/Phone Trsfr",
        "EXT TRNSFR 12345",
        "INTERNET TRANSFER123456789012 TO: 12345",               # CIBC, transfer word glued to its reference
        "E-TRANSFER104567890123 Pat Example",
        "BKOFAMERICA BC 01/05 12345 TO CHKG 12345 FAB ST",        # P2: owner may strike it
        "Internet Withdrawal",
        "ACH Web Smartsave 12345 Atlasfinancial 999",
        "RTP SENT PAT EXAMPLE",
        "Real Time Payment To Pat Example",
    ],
)
def test_transfer_templates_of_an_unnamed_payee_are_not_d6_payees(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "E-TRANSFER104567890123 Fabrique Capital Inc",
        "INTERNET XFR TO FABRICATED CAPITAL LLC",
        "OUTGOING WIRE TRF FABRICATED CAPITAL LLC",
        "FABRICATED CAPITAL DES:TRF ID:0001 CCD",                  # a funder's own entry description
        "SMART SAVE FUNDING LLC",
        "RTP SENT FABCO LLC",                                      # an organisation: stays reviewed
    ],
)
def test_a_transfer_template_never_hides_a_named_or_financing_payee(description):
    assert _states(description) == D6
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS.

- [ ] **Step 3: Constants.**

```python
#: 5.3 (2026-09-27): transfer templates the 5.2 transfer-word skip does not read. Each fires only for a payee that
#: names no organisation (D11 would publish 'Unidentified lender obligation') and a row that names no financing.
_TRANSFER_TEMPLATE_PATTERNS = (
    re.compile(r"\b(?:XFR|TRF|TRSFR|TRNSFR)\b|\b(?:TRANSFER|XFER|TFR)(?=\d)"),      # abbreviations; glued digits
    re.compile(r"\bTO (?:CHKG|CHK|CHECKG|CHECKING|SAV|SAVINGS|SVGS|SHARES?|MMA)(?: ACCOUNT| ACCT)? X*\d{2,}\b"),
    re.compile(r"^(?:INTERNET|ONLINE|PHONE|TELEPHONE|MOBILE|WEB) (?:WITHDRAWAL|WDRL|WDL)$"),
    re.compile(r"\bSMART ?SAVE\b.*\bATLAS ?FIN\w*|\bATLAS ?FIN\w*.*\bSMART ?SAVE\b"),  # Atlas's Smart Save sweep
    re.compile(r"\b(?:RTP SENT|REAL TIME PAYMENT TO|FEDNOW (?:PAYMENT|PMT) TO)\b"),
)
```

- [ ] **Step 4: Clause:**

```python
    if _unknown_payee_name(payee) in (None, UNIDENTIFIED_LENDER_OBLIGATION) and _skips(
        _row_before_receiver(text), _TRANSFER_TEMPLATE_PATTERNS, text
    ):
        return "transfer_template"
```

- [ ] **Step 5: Run.** **Step 6: Commit** `"d6: transfer templates of an unnamed payee (abbreviations, glued digits, account-type recipients, RTP)"`.

---

### Task A4: Cash withdrawals, own ACH-batch offsets, school and childcare billing (other_non_lender)

**Files:** as A2. **Needs:** 0.3.

**Why:** 455 rows / 40 occurrences, 8 keys. The lender-risk verifier narrowed every pattern so a payee name can never fill the gap: only reference tokens or NETWORK may sit between ATM/ABM and the withdrawal word. The Huntington reading (the holder's own portal batch) is inferred from the row shape, not verified. It is acceptable because D11 already drops the batch name from the review entry. The structural critic's daycare and tuition shape (high) joins here. 0.3's channel rule covers the bare teller, branch and cash withdrawals. The veto's SETTLE root (0.1) never blocks the two own-batch templates: `_skips` removes the matched template (its SETTLEMENT or SETTLMT and FUND) before the veto reads the rest of the row, and a test pins it.

- [ ] **Step 1: Tests.** Append:

```python
# --- A4: cash, own ACH-batch offsets, school and childcare ---------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "BKOFAMERICA ATM 01/05 #000123 WITHDRWL FAB BRANCH",
        "ATM NETWORK CASH WITHDRAWAL",
        "ABM WITHDRAWAL FAB TOWN ON",
        "GC 1234-CASH WITHDRA",
        "G/RETRAIT",
        "RETRAIT PAR GA 1234",
        "ACH SETTLMT REL DATE_FUND HNB HVACH PAT EXAMPLE",
        "BUS ONLINE ACH SETTLEMENT",
        "FAB SCHOOL DES:FACTS ID:0001 INDN:PAT EXAMPLE CO ID:0002 WEB",
        "KINDERCARE 1234567",
        "FAB ACADEMY TUITION 1234",
    ],
)
def test_cash_own_batches_and_school_billing_are_not_d6_payees(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "FAKE QUICK CASH WITHDRAWAL",
        "ABM FUNDING WITHDRAWAL",
        "ATM FAKE CAPITAL WITHDRAWAL",
        "WITHDRAWAL ABM FAKE CAPITAL",
        "RETRAIT GA FAKE CAPITAL",
        "ACH SETTLEMENT ACH BATCH FAKE CAPITAL LLC",
    ],
)
def test_a_payee_name_never_fills_a_cash_template(description):
    assert _states(description) == D6
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS, except for rows the channel rule already takes.

- [ ] **Step 3: Constants.**

```python
#: 5.3 (2026-09-27): rows whose own words say they cannot pay a funder: the holder's cash withdrawal in the formats
#: the ATM rule does not read (only reference tokens or NETWORK may sit between ATM/ABM and the withdrawal word, so a
#: payee name never fills the gap), the offset of an ACH batch the holder sent from its own bank's portal (inferred
#: from the row shape; D11 already drops the batch name from the review entry), and school, tuition and childcare
#: billing.
_NON_REMITTANCE_WORD_PATTERNS = (
    re.compile(
        r"\b(?:ATM|ABM)\b(?:\s+(?:\S*\d\S*|NETWORK)){0,3}\s+(?:CASH\s+)?"
        r"(?:WITHDRAWALS?|WITHDRAW|WITHDRWLS?|WDRLS?|WDL|W D|WD)\b"
    ),
    re.compile(r"\bWITHDRAWALS? (?:ATM|ABM)(?:\s+\S*\d\S*|$)"),
    re.compile(r"\bWITHDRWLS?\b"),
    re.compile(r"(?:^|(?<=\d )|\b(?:ATM|ABM|NETWORK|TELLER|COUNTER|BRANCH|LARGE|NON \S+)\s)CASH WITHDRA\w*"),
    re.compile(r"\bRETRAITS? (?:GAB|DAB|ATM|ABM|PAR GA|AU GUICHET|AU COMPTOIR)\b"),
    re.compile(r"^G RETRAIT\b"),
    re.compile(r"^(?:BUS ONLINE ACH SETTLEMENT|ACH SETTLMT REL DATE FUND)\b"),
    re.compile(r"\bDES FACTS\b|\bPAYMENT FACTS\b|\bFACTS(?: \d+)?$"),
    re.compile(r"\b(?:TUITION|DAYCARE|CHILD ?CARE|PRESCHOOL|MONTESSORI|KINDERCARE|BRIGHTWHEEL|PROCARE)\b"),
)
```

- [ ] **Step 4: Clause:**

```python
    if _skips(_row_before_receiver(text), _NON_REMITTANCE_WORD_PATTERNS, text):
        return "not_a_remittance"
```

- [ ] **Step 5: Run.** **Step 6: Commit** `"d6: cash withdrawals, own ACH-batch offsets, school and childcare billing"`.

---

### Task A5: Named savings and investing originators (savings_or_investment)

**Files:** as A2. **Needs:** 0.3.

**Why:** 374 rows / 36 occurrences, 4 keys. This is a closed list of verified non-funder ACH names, never a category rule by resemblance. The forward brands (ACORNS, ROBINHOOD, COINBASE, BETTERMENT, WEALTHFRONT) joined after `collision_check.py` printed 0 registry, 0 ledger and 0 key hits (2026-09-27). Any later name must pass the same check first.

- [ ] **Step 1: Tests.** Append:

```python
# --- A5: named savings and investing originators --------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "Orig CO Name:Stash Capital (S Orig ID:0001 Desc Date: CO Entry Descr:ACH Sec:Web Ind ID:0002 Ind Name:Pat Example",
        "Orig CO Name:Alinea Orig ID:0001 CO Entry Descr:Payment Sec:PPD",
        "Fid Bkg Svc LLC Moneyline 1234567 Pat Example",
        "Paid To - Albert Edi Pymnts Chk 1234567",
        "ALBERT DES:EDI PYMNTS ID:0001 INDN:PAT EXAMPLE CO ID:0002 WEB",
        "ACORNS INVEST DES:1234 ID:0001",
        "ROBINHOOD DEBITS 1234",
        "COINBASE INC 1234",
        "BETTERMENT 1234",
        "WEALTHFRONT 1234",
    ],
)
def test_named_savings_and_investing_originators_are_not_d6_payees(description):
    assert _states(description) == OTHER


def test_a_savings_brand_beside_financing_words_stays_in_review():
    assert _states("ALINEA CAPITAL DAILY PMT") == D6


def test_the_savings_names_never_reach_a_registered_payee():
    # The admitted Albert Corporation alias is a known payee (step 7), and a potential alias with EDI PYMNTS stays
    # a candidate: the skip only reads rows no rule claimed.
    assert classify_transaction("ALBERT GENIUS EDI PYMNTS", -100.0).classification == "personal_loan"
    assert classify_transaction("GLOBAL MER EDI PYMNTS", -100.0).match_method == "candidate_lender_alias"
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS.

- [ ] **Step 3: Constants.**

```python
#: 5.3 (2026-09-27): named consumer savings and investing originators: a closed list of verified non-funder ACH
#: names, never a category by resemblance. A name joins only after collision_check.py (registry tables, the whole
#: ledger, all_keys.json) prints no hit. Bare VANGUARD, INVEST, SAVINGS, FIDELITY and MONEYLINE stay out.
_SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS = (
    re.compile(r"\bSTASH (?:CAPITAL|INVEST(?:MENTS?)?)\b"),
    re.compile(r"\bALINEA\b"),
    re.compile(r"\bFID BKG SVC\b"),                                   # Fidelity Brokerage Services MoneyLine
    re.compile(r"\bALBERT (?:SAVINGS )?(?:DES )?EDI PYMNTS\b"),         # Albert's money movement, not its advances
    re.compile(r"\b(?:ACORNS|ROBINHOOD|COINBASE|BETTERMENT|WEALTHFRONT)\b"),
)
```

- [ ] **Step 4: Clause:**

```python
    if _skips(_row_before_receiver(text), _SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS, text):
        return "savings_or_investment"
```

- [ ] **Step 5: Run.** **Step 6: Commit** `"d6: named savings and investing originators (closed list)"`.

---

### Task A6: Vendors and other named non-lender payees (supplier_or_vendor plus structural shapes)

**Files:** as A2. **Needs:** 0.3.

**Why:** 252 rows / 71 occurrences, 11 keys. With the widened guard the vendor verifier measured 175 rows / 41 occurrences leaving. c00243 (FINANCIAL) stays, and c00060, c00075, c00104 and c00153 are out of this rule.

The design rules, with their evidence:
- The vocabulary is read on the D11 payee words and, as a fallback, on the originator segment (Task 0.2), never on a receiver field. 102 Credibly rows name a holder '… Distributions'. The fallback keeps a vendor word printed after the payee's legal form ('FABRIKAM MFG INC INVOICES 1234567', c00131's shape), which C5's legal-form cut removes from the D11 words (found by the Part C prototype).
- **Bounded rows only** (plan review, 2026-09-28). `_originator_segment` runs to the end of the row when nothing ends it, and in the label-less formats the telecom verifier listed (Regions '<funder> ACHPMT <receiver>', Bluevine '<funder> PAY PAYMENT TO <receiver>') the end of the row is the account holder's name. The first draft's prototype hid 'KAPIFAB LLC ACHPMT FAB UNIFORMS LLC' and 'KAPIFAB PAY PAYMENT TO FAB LANDSCAPING LLC' whenever the parser left `account_name` None (the second through the D11 words themselves, whose four-word cap reaches the receiver when the funder's name has no legal form). So:
  - the fallback reads the originator segment only on a bounded row: an ACH field, or a reference token after the payee's first name word, ends the payee's words before the row does (`_payee_words_are_bounded`); every vendor key of the hunt prints such a boundary except one that prints a single word;
  - on a row that is one run of words, with the holder's name unknown (no word of four letters or more), the vendor word must be the payee's first word (a one-word 'UNIFIRST' row still skips; a receiver is never first);
  - with the holder's name known, the holder guard reads the D11 words as before.
  - Residual, recorded in the spec: a label-less row that prints the receiver and then a reference ('<funder> ACHPMT <receiver> <ref>'), with the holder unknown, is still read through the D11 words. No hunt key has that shape.
- Entry-description wording is never read: 305 SBFS/Rapid Finance rows print 'Vendor Pay'.
- Ad platforms are anchored to the start: 'PROGRESSIVELEASE FACEBK' is a lease.
- A holder-name guard stops Southside, First Farmers, Columbia and Texas First from printing the holder inside the payee words.

The lending guard is the shared veto plus PAD. The structural critic's high and medium shapes join under the same reading and guards: uniform and linen route vendors, ad platforms without a star, church giving, tolls, franchise royalties and ad funds, and betting and lottery. `collision_check.py` printed 0 registry and 0 ledger hits for every name below (2026-09-27). DISTRIBUT\* also clears recurring owner 'DISTRIBUTION' draws, which is intended and noted in the spec.

- [ ] **Step 1: Tests.** Append:

```python
# --- A6: vendors and other named non-lender payees -------------------------------------------------------------------

@pytest.mark.parametrize(
    ("description", "account_name"),
    [
        ("FAB BOOKKEEPING LLC DES:BILL ID:0001 INDN:FAB HOLDER CO ID:0002 CCD", None),
        ("CINTAS CORP 123 DES:CINTAS ID:0001", None),
        ("FABRIKAM MFG INC INVOICES 1234567", None),                 # the originator segment, ended by its reference
        ("FAB FOODSERVICE VENDOR PAY 0001", None),
        ("UNIFIRST", None),                                          # one word: the vendor word is the first
        ("FAB FOODSERVICE VENDOR PAY", "FABRIKAM TRADING LLC"),      # a run of words, the holder known
        ("FACEBK ADS 12345", None),
        ("Bill.com Fab Supplies Inc - Inv 1234", None),
        ("ARAMARK UNIFORM SERVICES 1234567", None),
        ("SUBWAY ROYALTY DES:ROYALTY ID:0001", None),
        ("PUSHPAY 1234567", None),
        ("E ZPASS 1234567", None),
        ("DRAFTKINGS 1234567", None),
        ("FAB MARKETING FUND LLC 0001", None),
    ],
)
def test_vendors_and_named_non_lenders_are_not_d6_payees(description, account_name):
    assert _states(description, account_name=account_name) == OTHER


@pytest.mark.parametrize(
    ("description", "account_name"),
    [
        ("PMTS FABLEASE FACEBK", None),                            # an ad word after a lessor's name
        ("Bill.com Fab Credit Corp - Inv 1234", None),
        ("FAB FINANCIAL INVOICE 12345", None),
        ("FAB GRP FUNDIN INVOICE", None),
        ("FAB CAPITA INVOICES", None),
        ("MFG LLC DES:PAYMENT ID:0001 CCD", None),                  # a funder's own abbreviation
        ("FAB WHOLESALE PMT", None),
        ("FAB FACTORING INVOICE", None),
        ("FAB LLC DAILY INVOICE", None),
        ("FAB LLC RTR INVOICE", None),
        ("BUSINESS PAD FAB INVOICES", None),
        ("PAYMENT FABRIKAM CCD FAB DISTRIBUTING LLC", "FAB DISTRIBUTING LLC"),  # the holder's own trade word
        # label-less rows that are one run of words, the holder unknown: the receiver may be the holder
        ("KAPIFAB LLC ACHPMT FAB UNIFORMS LLC", None),                # Regions
        ("KAPIFAB ACHPMT FAB UNIFORMS LLC", None),
        ("KAPIFAB PAY PAYMENT TO FAB LANDSCAPING LLC", None),         # Bluevine
        ("FAB FOODSERVICE VENDOR PAY", None),
    ],
)
def test_a_vendor_word_never_hides_a_financing_payee_or_reads_the_holder(description, account_name):
    assert _states(description, account_name=account_name) == D6
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS.

- [ ] **Step 3: Constants.**

```python
#: 5.3 (2026-09-27): vendors and other payees that never lend, read on the D11 payee words only (never an entry
#: description: SBFS/Rapid Finance prints 'Vendor Pay'; never the holder: a holder named '... Distributions' pays
#: Credibly), guarded by the lending words below and by the holder's own name. DISTRIBUT* also clears recurring owner
#: distributions. Names join only after collision_check.py prints no registry or ledger hit.
_VENDOR_PAYEE_PATTERNS = (
    re.compile(r"\bBOOKK\w*"),
    re.compile(r"\b(?:DISTR|DISTRIBUT\w*|FOODSERVICE)\b"),
    re.compile(r"\bMANUFACTURING\b"),
    re.compile(r"\bINVOICES?\b"),
    re.compile(r"\b(?:CINTAS\w*|UNIFIRST|ARAMARK|SYSCO|ALSCO)\b|\bUS FOODS\b"),
    re.compile(r"^(?:FACEBOOK|FACEBK|META ADS|META PLATFORMS|GOOGLE ADS|TIKTOK ADS|YELP|ANGI|HOMEADVISOR|THUMBTACK)\b"),
    re.compile(r"\b(?:UNIFORMS?|LINEN|JANITORIAL|LANDSCAP\w*|LAWN|PEST CONTROL)\b"),
    re.compile(r"\bROYALT(?:Y|IES)\b|\bFRANCHIS\w*|\b(?:AD|MARKETING|ADVERTISING) FUND\b"),
    re.compile(r"\bTITHE\w*|\bCHURCH\b|\bMINISTRIES\b|\bDONATIONS?\b|\b(?:PUSHPAY|GIVELIFY|VANCO|SUBSPLASH|EASYTITHE)\b"),
    re.compile(r"\b(?:EZPASS|ZPASS|SUNPASS|FASTRAK|TXTAG|NTTA|HCTRA|PEACH PASS|IPASS|BESTPASS|PREPASS|TOLLS?|TOLLWAY)\b"),
    re.compile(r"\b(?:DRAFTKINGS|FANDUEL|BETMGM|LOTTERY|OLG|CASINO)\b"),
)
#: 5.3: a Bill.com or Melio payment is a vendor's only when the row prints an invoice number.
_BILL_PAY_PLATFORM_PATTERN = re.compile(r"^(?:BILL COM|MELIO)\b")
_INVOICE_NUMBER_PATTERN = re.compile(r"\bINV \d")
#: 5.3: the vendor skip's lending guard: the shared roots plus the Canadian pre-authorized-debit channel word.
_VENDOR_LENDING_GUARD = re.compile(_FINANCING_ROOT_PATTERN.pattern + r"|\bPAD\b")
#: 5.3: the account holder's name words, read without the module normalizer: classifying a row normalizes exactly
#: one text (tests/test_classifier_lookups.py::test_each_row_is_normalized_exactly_once).
_HOLDER_WORD = re.compile(r"[A-Z0-9]+")


def _payee_words_are_bounded(text: str) -> bool:
    """5.3 (plan review 2026-09-28): whether an ACH field, or a reference token after the payee's first name word,
    ends the payee's words before the normalized row `text` ends. A row that is one run of words (Regions '<funder>
    ACHPMT <receiver>', Bluevine '<funder> PAY PAYMENT TO <receiver>') can end with the account holder's name."""
    labelled = _ENTITY_NAME_LABELS.sub(" ", text)
    if _ACH_FIELD_SEGMENT.search(labelled) is not None:
        return True
    started = False
    for token in labelled.split():
        if _is_reference_token(token):
            if started:
                return True
            continue
        started = started or (token not in _ENTITY_NOISE and len(token) > 1)
    return False


def _is_vendor_payee(payee: Sequence[str], text: str, account_name: str | None) -> bool:
    """5.3: the D11 payee words (or, on a bounded row, the originator segment, which then never reads a receiver
    field) name a vendor or another payee that never lends, the row prints no lending word (outside the matched vendor
    words), and those words carry none of the account holder's own name words. On a row that is one run of words the
    segment is never read, and when the holder's name is unknown the vendor word must be the payee's first word."""
    words = " ".join(payee)
    bounded = _payee_words_are_bounded(text)
    segment = _originator_segment(text) if bounded else ""
    found = next(
        (match for source in (words, segment) for pattern in _VENDOR_PAYEE_PATTERNS if (match := pattern.search(source))),
        None,
    )
    if found is None and _BILL_PAY_PLATFORM_PATTERN.search(words) and _INVOICE_NUMBER_PATTERN.search(text):
        found = _BILL_PAY_PLATFORM_PATTERN.search(words)
    if found is None:
        return False
    holder = {
        word for word in _HOLDER_WORD.findall((account_name or "").upper())
        if len(word) >= 4 and word not in _LEGAL_FORM_SUFFIXES
    }
    if not bounded and not holder and found.start() > 0:
        return False  # a label-less run of words may end with the holder's name, which is unknown here
    if holder & (set(payee) | set(segment.split())):
        return False
    return _VENDOR_LENDING_GUARD.search(text.replace(found.group(0), " ")) is None
```

- [ ] **Step 4: Clause:**

```python
    if _is_vendor_payee(payee, text, record.account_name):
        return "named_non_lender"
```

- [ ] **Step 5: Run.** **Step 6: Commit** `"d6: vendors and named non-lender payees, read on the payee words with a lending and holder guard"`.

---

### Task A7: Tax and government payees; government finance departments in the keyword recurrence

**Files:** as A2 (the keyword clause goes into `_keyword_recurrence_skip`). **Needs:** 0.3.

**Why:** 72 rows / 18 occurrences, 3 keys (tax_or_government_payment). The tax verifier's optional narrowing is adopted: the patterns read the payee region (cut at the first ACH field segment), so a funder's DES:CCRA or memo never skips. They fire only for a payee that names no organisation.

The structural critic's agencies printed without TAX (high) join under the same guards: NYS DTF, EDD, DEPT OF REVENUE, DOR, TAXATION, COMPTROLLER, state treasuries, Revenu Québec and the workers'-compensation boards. USATAXPYMT is dropped: it is redundant, because real rows also print IRS. The rows stay `other`, not `tax`: the tax rule has no amount guard and runs before the known payee.

The structural critic's government finance departments and ADVANCE AUTO PARTS / ADVANCE STORES (medium) promote through the keyword recurrence (0.76). `_keyword_recurrence_skip` stops that recurrence, and the single rows stay `other` / `financing_keyword_review` as today.

- [ ] **Step 1: Tests.** Append:

```python
# --- A7: tax and government payees -------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "Online Payment 1234 To United States Treasury",
        "PAD CCRA CANADA",
        "STATE OF FABSTATE SOS EFT",
        "NYS DTF WT DES:NYS DTF WT ID:0001 INDN:FABRIKAM CORP CO ID:0002 CCD",
        "MI TREASURY 1234",
        "PAD WSIB",
        "EFTPS PAYMENT 1234",
    ],
)
def test_tax_and_government_payees_are_not_d6_payees(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    ["TREASURY CAPITAL GROUP LLC", "ACH DEBIT CCRA HOLDINGS LLC", "FABRICATED WIDGETS DES:CCRA ID:0001"],
)
def test_a_government_word_never_hides_a_named_payee_or_reads_an_entry_field(description):
    assert _states(description) == D6


@pytest.mark.parametrize(
    "description",
    ["BUSINESS PAD FABTOWN MIN OF FINANCE", "FAB CITY DEPT OF FINANCE PARKING ACH DEBIT", "ADVANCE AUTO PARTS ACH DEBIT"],
)
def test_government_finance_departments_and_a_named_retailer_are_no_keyword_recurrence(description):
    assert _states(description) == {("other", "financing_keyword_review")}


def test_a_financing_keyword_payee_still_recurs():
    assert _states("ACH DEBIT FABRICATED FUNDING LLC") == {("potential_lender", "recurring_financing_counterparty")}
```

- [ ] **Step 2: Run.** Expected: the first and third parametrizations FAIL.

- [ ] **Step 3: Constants.**

```python
#: 5.3 (2026-09-27): tax authorities and government agencies printed without TAX, IRS or CRA, read on the payee
#: region only (never an entry description or memo) and only for a payee that names no organisation. The row stays
#: 'other': the tax rule has no amount guard and runs before the known payee, so it is not widened.
_GOVERNMENT_PAYEE_PATTERNS = (
    re.compile(r"\b(?:UNITED STATES|U ?S) (?:(?:DEPT|DEPARTMENT) OF (?:THE )?)?TREAS(?:URY)?\b"),
    re.compile(r"\bEFTPS\b"),
    re.compile(r"\bCCRA\b"),
    re.compile(r"\bRECEIVER GENERAL\b"),
    re.compile(r"\bSECRETARY OF STATE\b"),
    re.compile(r"\bSTATE OF [A-Z]+(?: [A-Z]+)? (?:SOS|DMV)\b"),
    re.compile(r"\b(?:DEPT|DEPARTMENT) OF MOTOR VEHICLES?\b"),
    re.compile(r"\b(?:DTF|EDD|DOR|TAXATION|COMPTROLLER)\b"),
    re.compile(r"\b(?:DEPT|DEPARTMENT) (?:OF )?REV(?:ENUE)?\b"),
    re.compile(r"\bTREASURER OF STATE\b|\b[A-Z]{2} TREASURY\b"),
    re.compile(r"\bREVENU QUEBEC\b|\bMINISTRE DU REVENU\b"),
    re.compile(r"\b(?:WSIB|WORKSAFE\w*|WCB|EHT|CNESST)\b"),
)
#: 5.3: payees the financing-keyword recurrence never promotes: a government finance department (FINANCE is its
#: name, not a loan) and a retailer named ADVANCE. Their single rows stay 'other' / financing_keyword_review.
_GOVERNMENT_FINANCE_DEPARTMENT_PATTERNS = (
    re.compile(r"\b(?:DEPT|DEPARTMENT|MINISTRY|MIN|MINISTERE|DIV) (?:OF |DES )?FINANCES?\b"),
    re.compile(r"\bFINANCE DEPT\b"),
)
_RETAILER_ADVANCE_PATTERNS = (re.compile(r"\bADVANCE (?:AUTO PARTS|STORES)\b"),)
```

- [ ] **Step 4: Clauses.** In `_d6_skip`:

```python
    if _unknown_payee_name(payee) in (None, UNIDENTIFIED_LENDER_OBLIGATION) and _skips(
        _payee_region(text), _GOVERNMENT_PAYEE_PATTERNS, text
    ):
        return "government_payee"
```

In `_keyword_recurrence_skip`, replace `return None` with:

```python
    region = _row_before_receiver(record.normalized_description)
    if _matches_any(region, _GOVERNMENT_FINANCE_DEPARTMENT_PATTERNS):
        return "government_finance_department"
    if _matches_any(region, _RETAILER_ADVANCE_PATTERNS):
        return "retailer_named_advance"
    return None
```

- [ ] **Step 5: Run.** **Step 6: Commit** `"d6: tax and government payees; no keyword recurrence for finance departments or a retailer named ADVANCE"`.

---

### Task A8: Family support (child_support_or_garnishment)

**Files:** as A2 (clauses in both `_d6_skip` and `_keyword_recurrence_skip`). **Needs:** 0.3, A7.

**Why:** 47 rows / 11 occurrences (39 corpus, 8 tryout). Both verifier hardenings are adopted:
- read before the receiver fields, so a holder named '… Child Support Svcs' never silences its funder, while 'DES:CHILD SUPP' and 'CO ENTRY DESCR:CHLD SUPP' still count;
- applied before the keyword/default split.

GARNISH, LEVY, LEGAL ORDER, bare SDU and CSE stay out: an MCA judgment creditor collects through a law office or a marshal. The keyword clause carries no veto, because keyword rows name financing by definition. The D6 clause carries the veto.

A sibling-group effect is documented in the spec: a same-payee, same-amount row without the words loses its promotion when the skipped rows carried the qualifying dates.

- [ ] **Step 1: Tests.** Append:

```python
# --- A8: family support ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "FS CHILD SUPPORT DES:PAYMENT ID:0001",
        "CO FAM SUPP REG 1234",
        "FB SDU DES:CHILD SUPP ID:0001 INDN:FABRIKAM CORP CO ID:0002 CCD",
        "Orig CO Name:Fab SDU Orig ID:0001 Desc Date: CO Entry Descr:Chld Supp Sec:CCD",
        "STATE DISBURSEMENT UNIT ACH DEBIT",
    ],
)
def test_family_support_payments_are_not_d6_payees(description):
    assert _states(description) == OTHER


def test_family_support_words_in_a_financing_row_stop_the_keyword_recurrence():
    assert _states("ACH DEBIT CHILD SUPPORT ADVANCE 0000") == {("other", "financing_keyword_review")}


@pytest.mark.parametrize(
    "description",
    [
        "FABRICATED RIVER CAPITAL DES:PAYMENT ID:0001 INDN:CHILD SUPPORT SVCS LLC CO ID:0002 CCD",  # the holder
        "ACH DEBIT FAMILY SUPPORT CAPITAL LLC",
        "ACH DEBIT CHILDS CAPITAL LLC",
    ],
)
def test_a_family_support_word_never_hides_a_funder(description):
    assert _states(description) == D6
```

- [ ] **Step 2: Run.** Expected: the first parametrization and the keyword test FAIL.

- [ ] **Step 3: Constants.**

```python
#: 5.3 (2026-09-27): a court-ordered family-support payment through a state conduit is not an MCA remittance. Read
#: before the receiver fields (a holder named '... Child Support Svcs' never silences its funder). GARNISH, LEVY,
#: LEGAL ORDER, bare SDU and CSE stay out: an MCA judgment creditor collects through a law office or a marshal.
_FAMILY_SUPPORT_WORD_PATTERNS = (
    re.compile(r"\bCHI?LD ?SUPP(?:ORT|T)?\b"),
    re.compile(r"\bFAM(?:ILY)? SUPP(?:ORT)? (?:REG(?:ISTRY)?|PAYMENT CENTER|PMT CTR|PAYMENT CTR)\b"),
    re.compile(r"\bSTATE DISBURSEMENT UNIT\b"),
)
```

- [ ] **Step 4: Clauses.** In `_d6_skip`:

```python
    if _skips(_row_before_receiver(text), _FAMILY_SUPPORT_WORD_PATTERNS, text):
        return "family_support"
```

In `_keyword_recurrence_skip`, before its last `return None`:

```python
    if _matches_any(region, _FAMILY_SUPPORT_WORD_PATTERNS):
        return "family_support"
```

- [ ] **Step 5: Run.** **Step 6: Commit** `"d6: family-support payments are not recurring remittances (both recurrence kinds)"`.

---

### Task A9: Owner pay and platform payouts to a person (compensation_to_person plus structural shapes)

**Files:** as A2. **Needs:** 0.3.

**Why:** Payoneer payouts: 154 rows / 18 occurrences, one business. The lender-risk verifier requires the narrowing: skip only when the named recipient is not an organisation and not the platform itself. Payoneer's Capital Advance is collected by ACH bank debit (an alternative position), and an empty or organisation recipient stays in review. The rule lives in its own helper, not in `_COMPENSATION_WORD_PATTERNS`, whose comment says "words that name compensation".

The structural critic's owner money (high) and per diem (medium) join as a new tuple. The 5.2 tuple stays untouched, and the new one carries the veto ('DIVIDEND FINANCE' is a solar lender). The words are OWNER/MEMBER/PARTNER/SHAREHOLDER DRAW or DISTRIBUTION, DIVIDEND, PER DIEM and GUARANTEED PAYMENT. DISTRIBUTION is qualified, because 'DISTRIBUTIONS LLC' is a vendor in 300 WF rows.

- [ ] **Step 1: Tests.** Append:

```python
# --- A9: owner pay and platform payouts to a person -----------------------------------------------------------------

PAYONEER = ("Orig CO Name:Payoneer Inc Orig ID:0001 Desc Date: CO Entry Descr:Payment Sec:WEB Ind Name:Fab Holder "
            "Trn: 0001 Payoneer ID: 0001 Pay To: {} Payment Date: 01/05")


@pytest.mark.parametrize(
    "description",
    ["OWNERS DRAW PAT EXAMPLE", "ACH DEBIT OWNER DRAW", "MEMBER DISTRIBUTION", "PARTNER DRAW", "PER DIEM WEEK 12",
     "GUARANTEED PAYMENT PAT EXAMPLE", PAYONEER.format("Pat Example")],
)
def test_owner_pay_and_a_platform_payout_to_a_person_are_not_d6_payees(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "DIVIDEND FINANCE 0001",                          # a financing word: stays reviewed
        PAYONEER.format("Fabricated Capital LLC"),        # an organisation recipient
        PAYONEER.format("Payoneer Inc"),                  # the platform collecting for itself
        "Orig CO Name:Payoneer Inc Orig ID:0001 Payoneer ID: 0001",  # no recipient printed
        "BILL PAY TO PAYONEER INC",                       # a payment to Payoneer
    ],
)
def test_owner_pay_words_and_payouts_never_hide_a_financing_or_organisation_payee(description):
    assert _states(description) == D6
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS.

- [ ] **Step 3: Constants.**

```python
#: 5.3 (2026-09-27): owner money is not an MCA remittance: a draw or distribution to an owner, member, partner or
#: shareholder, a dividend, a per diem, a guaranteed payment. Read before the receiver fields, with the veto
#: (DIVIDEND FINANCE is a lender); a bare DISTRIBUTION is a vendor's name.
_OWNER_PAY_WORD_PATTERNS = (
    re.compile(r"\b(?:OWNERS?|MEMBERS?|PARTNERS?|SHAREHOLDERS?) (?:DRAWS?|DISTRIBUTIONS?)\b"),
    re.compile(r"\bPER DIEM\b"),
    re.compile(r"\bGUARANTEED PAYMENTS?\b"),
    re.compile(r"\bDIVIDENDS?\b"),
)
#: 5.3: a payments platform paying a recipient it names ('Pay To: <name>'): the platform is the originator, not a
#: creditor. Only a person recipient is skipped: Payoneer's Capital Advance is collected by ACH bank debit (an
#: alternative position), so an organisation recipient, the platform itself or no recipient stays reviewed.
_PLATFORM_PAYOUT_PATTERN = re.compile(r"\bPAYONEER\b.*\bPAY TO\b(?P<recipient>.*?)(?:\bPAYMENT DATE\b|\bTRN\b|$)")


def _is_platform_payout_to_person(text: str) -> bool:
    found = _PLATFORM_PAYOUT_PATTERN.search(text)
    if found is None:
        return False
    recipient = [token for token in found.group("recipient").split()
                 if len(token) > 1 and not _is_reference_token(token)]
    return bool(recipient) and not any(
        token in _ORGANISATION_CUES or token == "PAYONEER" for token in recipient
    ) and not _names_financing(" ".join(recipient))
```

- [ ] **Step 4: Clauses:**

```python
    if _skips(_row_before_receiver(text), _OWNER_PAY_WORD_PATTERNS, text):
        return "owner_pay"
    if _is_platform_payout_to_person(text):
        return "platform_payout_to_person"
```

- [ ] **Step 5: Run.** **Step 6: Commit** `"d6: owner draws, distributions, per diem and platform payouts to a person"`.

---

### Task A10: The $25 floor for unnamed payees (subscription_or_software)

**Files:** Modify `analysis/transaction_classifier.py` (a constant above `def _d6_skip(`; the D6 promotion loop, `:2236-2241`); modify `tests/test_recurring_fixed_debits.py` (pin-ledger rows 1-2); append to `tests/test_d6_skips.py`.

**Needs:** 0.3.

**Why:** 94 rows / 24 occurrences, 4 keys. Across other keys, 203 groups / 1,047 rows overlap other families.
- The lender-risk verifier narrowed the floor to payees D6 cannot name, and the comparison is strict (a collector's daily settlement seen in the corpus sits exactly on the edge).
- The floor also carries the shared veto, so a no-suffix 'X Recovery' collector below $25 stays in review. The cost is c00102 (its payee name prints CREDIT).
- The floor lives in the promotion loop, where the name is known.
- The cleared groups also leave the recurring-debit view (`detect.find_recurring_debits`, which reads D6's promotions) and everything built on it: the CLI's 'Recurring fixed debits' lines, `batch.py`'s `recurring_debit_groups` and the payload's `detection.recurring_debits` (the subscription evidence verifier; a test pins the view, and F1's comment and F2's D6 bullet say so).

- [ ] **Step 1: Tests.** Append:

```python
# --- A10: the $25 floor for unnamed payees ------------------------------------------------------------------------------

def test_a_fixed_debit_under_25_dollars_to_an_unnamed_payee_is_not_promoted():
    assert _states("ACH DEBIT PAT EXAMPLE", -24.0) == OTHER


def test_an_unnamed_group_under_the_floor_leaves_the_recurring_debit_view():
    from analysis.detect import find_recurring_debits

    statement = Statement(transactions=[txn(f"2054-01-{day:02d}", "ACH DEBIT PAT EXAMPLE", -24.0) for day in WEEKLY])
    assert find_recurring_debits(statement) == []


def test_the_floor_is_strict():
    assert _states("ACH DEBIT PAT EXAMPLE", -25.0) == D6


@pytest.mark.parametrize(
    "description",
    [
        "FABRICATED CAPITAL DES:ACH PMT ID:0001 CCD",                                 # a named payee
        "< Business to Business ACH Debit - Fabricated Recovery L Fab Co Inc",       # a collector's words
    ],
)
def test_a_named_or_financing_payee_promotes_at_any_amount(description):
    assert _states(description, -20.0) == D6


def test_the_floor_never_reaches_the_keyword_recurrence():
    assert _states("ACH DEBIT FABRICATED FUNDING LLC", -20.0) == {
        ("potential_lender", "recurring_financing_counterparty")
    }
```

- [ ] **Step 2: Re-pin the fixtures (pin-ledger rows 1-2).** In `tests/test_recurring_fixed_debits.py`:
  - `_d6_methods` (`:190-192`) builds its rows with `-100.0` instead of `-10.0`;
  - in `test_weekly_push_payments_to_one_masked_recipient_are_still_promoted` (`:312`) and `test_only_the_recipient_with_three_weekly_dates_is_promoted` (`:342-343`), the `-10.0` amounts become `-100.0`.

  Nothing else in the file changes: every other `-10.0` test names an organisation or expects no promotion.

- [ ] **Step 3: Run** both files. Expected: the new floor tests FAIL. The re-pinned tests pass before and after.

- [ ] **Step 4: Constant** above `def _d6_skip(`:

```python
#: 5.3 (2026-09-27): D6 does not take a same-amount group under this amount whose payee names no organisation (it
#: would publish as 'Unidentified lender obligation') and whose row names no financing. Strict: a 25-dollar debit
#: promotes. A named payee promotes at any amount. A whole number: analysis/ carries no exact-cent literal
#: (tests/test_no_statement_hardcodes.py).
_D6_MIN_FIXED_DEBIT = 25
```

- [ ] **Step 5: The promotion loop.** Replace

```python
    for (payee, _, _), indexes in fixed_debit_groups.items():
        promotion = _promotion_cadence(records, indexes, min_recurring_count)
        if promotion is None:
            continue
        cadence, average_gap = promotion
        entity = _unknown_payee_name(payee) or UNIDENTIFIED_LENDER_OBLIGATION
```

with

```python
    for (payee, amount, _), indexes in fixed_debit_groups.items():
        entity = _unknown_payee_name(payee) or UNIDENTIFIED_LENDER_OBLIGATION
        if (
            entity == UNIDENTIFIED_LENDER_OBLIGATION
            and amount < _D6_MIN_FIXED_DEBIT
            and not _names_financing(records[indexes[0]].normalized_description)
        ):
            continue
        promotion = _promotion_cadence(records, indexes, min_recurring_count)
        if promotion is None:
            continue
        cadence, average_gap = promotion
```

- [ ] **Step 6: Run** `tests/test_d6_skips.py`, `tests/test_recurring_fixed_debits.py` and SEL-CLASSIFIER. Expected: PASS. The measured in-memory prototype moved exactly pin-ledger rows 1-2.

- [ ] **Step 7: Commit** (`git add analysis/transaction_classifier.py tests/test_d6_skips.py tests/test_recurring_fixed_debits.py`) `"d6: no promotion of an unnamed payee's fixed debit under 25 dollars"`.

---

### Task A11: A processor's own small account charge (platform_or_processor_fee)

**Files:** as A2. **Needs:** 0.3.

**Why:** 19 stored rows (13 unique plus 6 duplicate copies) / 5 occurrences, 2 keys. The lender-risk verifier requires a $50 cap. The rails are amount-blind, and Intuit Payment Solutions also carries invoice payments in the thousands, so a fixed debit above the cap through Square's or Intuit's rail stays in review. The guard is hardened with Square's glued loan codes (SQ CAP, SQ LOAN) and LENDING. The brand words live in the classifier, with a spec §5 bullet (F2).

- [ ] **Step 1: Tests.** Append:

```python
# --- A11: a processor's own small account charge -------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("description", "amount"),
    [
        ("ACH CORP DEBIT SQ540512 SQUARE INC CUSTOMER ID 0001", -10.0),
        ("ACH Pull: INTUIT PYMT SOLN", -25.0),
        ("INTUIT PYMT SOLN DES:INTUITPMTS ID:0001", -49.0),
    ],
)
def test_a_processors_small_account_charge_is_not_a_d6_payee(description, amount):
    assert _states(description, amount) == OTHER


@pytest.mark.parametrize(
    ("description", "amount"),
    [
        ("ACH Pull: INTUIT PYMT SOLN", -450.0),                          # above the cap: the payee is unknown
        ("ACH CORP DEBIT SQ540512 SQUARE INC CUSTOMER ID 0001", -1250.0),
        ("SQUARE INC DES:SQ540512 ID:SQCAP1201", -30.0),                 # Square's glued loan code
        ("SQUARE INC DES:SQ540512 LENDING", -30.0),
    ],
)
def test_a_processor_rail_above_the_cap_or_naming_financing_stays_in_review(description, amount):
    assert _states(description, amount) == D6
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS.

- [ ] **Step 3: Constants.**

```python
#: 5.3 (2026-09-27): a payment processor's own small charge to its merchant, through its merchant-services
#: spelling: Square's seller-account entry code (SQ + the entry date yymmdd) and Intuit Payment Solutions. Capped at
#: 50 dollars (Intuit's fees and chargebacks, Square's small charges): these rails also carry invoice payments to
#: third parties in the thousands, so a fixed debit above the cap stays in review. Never with loan or capital
#: wording, including Square's glued loan codes (SQCAP, SQ LOAN). A whole number
#: (tests/test_no_statement_hardcodes.py).
_PROCESSOR_ACCOUNT_DEBIT_PATTERNS = (
    re.compile(r"\bSQUARE\b.*\bSQ ?\d{6}\b|\bSQ ?\d{6}\b.*\bSQUARE\b"),
    re.compile(r"\bINTUIT (?:PYMT|PMT|PAYMENTS?) SOL(?:N|NS|UTIONS?)?\b"),
)
_PROCESSOR_DEBIT_FINANCING_GUARD = re.compile(
    r"\bLOANS?\b|\bADVANCE\b|\bFINANC(?:E|ING|IAL)\b|\bFUND(?:ER|ING)\b|\bCAP(?:ITAL)?(?![A-Z])|\bMCA\b"
    r"|\bSQ ?CAP|\bSQ ?LOAN|\bLENDING\b"
)
_PROCESSOR_ACCOUNT_CHARGE_MAX = 50


def _is_processor_account_charge(record: TransactionClassification) -> bool:
    text = record.normalized_description
    return (
        abs(record.amount) <= _PROCESSOR_ACCOUNT_CHARGE_MAX
        and _matches_any(text, _PROCESSOR_ACCOUNT_DEBIT_PATTERNS)
        and _PROCESSOR_DEBIT_FINANCING_GUARD.search(text) is None
    )
```

- [ ] **Step 4: Clause:**

```python
    if _is_processor_account_charge(record):
        return "processor_account_charge"
```

- [ ] **Step 5: Run.** **Step 6: Commit** `"d6: a processor's own account charge of 50 dollars or less"`.

---

### Task A12: Insurers cut short by the ACH field (insurance_premium)

**Files:** as A2. **Needs:** 0.3.

**Why:** 9 rows / 3 occurrences, 1 key. The lender-risk verifier requires the read on the D11 payee words: a holder insurance agency named '… Bros Insuran' in INDN never silences its funder, and an 'ID:INSU-0001' reference is not read. Widening the step-4 insurance term (alternative A) or adding a NEXT INSUR insurer alias (B) was refused by the verifiers.

- [ ] **Step 1: Tests.** Append:

```python
# --- A12: insurers cut short by the ACH field ---------------------------------------------------------------------------

@pytest.mark.parametrize("cut", ["INSU", "INSUR", "INSURA", "INSURAN", "INSURANC"])
def test_an_insurer_cut_short_is_not_a_d6_payee(cut):
    assert _states(f"FABNEXT {cut} (AP I DES:FABNEXT {cut} ID:0001 INDN:FAB HOLDER CO ID:0002 WEB") == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "FABRIKAM LLC DES:PAYMENT ID:0077 INDN:ZORVEX BROS INSURAN CO ID:0009 CCD",   # the holder is the agency
        "ACH DEBIT FABRICATED INSURED CAPITAL",
        "ACH DEBIT FABRIKAM SERVICES ID:INSU-0001 CCD",
        "FAB PENINSULA INSULATION CO",
    ],
)
def test_a_cut_insurance_word_outside_the_payee_words_never_skips(description):
    assert _states(description) == D6
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS.

- [ ] **Step 3: Constant.**

```python
#: 5.3 (2026-09-27): an insurer whose name the ACH field cut short (INSU, INSUR, INSURA, INSURAN, INSURANC: the
#: 16-character company name or the 10-character entry description). Read on the D11 payee words only: the holder's
#: name (INDN, IND NAME, or unlabeled) never decides. INSURED, INSURER and the bare INS stay out.
_TRUNCATED_INSURANCE_WORD_PATTERN = re.compile(r"\bINSU(?:R|RA|RAN|RANC)?\b")
```

- [ ] **Step 4: Clause:**

```python
    if _skips(" ".join(payee), (_TRUNCATED_INSURANCE_WORD_PATTERN,), text):
        return "truncated_insurer"
```

- [ ] **Step 5: Run.** **Step 6: Commit** `"d6: insurers cut short by the ACH field, read on the payee words"`.

---

### Task A13: Phone and cable carriers (utility_or_telecom)

**Files:** as A2. **Needs:** 0.2, 0.3.

**Why:** 6 rows / 2 occurrences, 1 key. The lender-risk verifier requires the anchored form: the carrier must be the payee's LEADING name. A label-less receiver that is a wireless dealer (Truist, Wells Fargo, Capital One, Bluevine, Symitar, Regions formats) never hides its funder. The rows stay `other`, not `utility`: step 6 runs before the known payee.
- The list is brand names only, never MOBILE, WIRELESS or CELLULAR alone.
- BELL, ROGERS, SHAW and SPRINT need their telecom word.
- ATT is narrowed to its bill and payment forms.
- The VERIZON lookahead covers the registry's Verizon Visa alias only. A 'SYNCB VERIZON' card payment reaching `other` hides no funder.

- [ ] **Step 1: Tests.** Append:

```python
# --- A13: phone and cable carriers ----------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "KOODO MOBILE ABC123", "BILL PAYMENT BELL CANADA", "PRE-AUTHORIZED PAYMENT FIDO MOBILE PAP",
        "CABLE TV BILL PMT SHAW CABLE TV", "ONLINE BANKING PAYMENT 1234 ROGERS WIRELESS",
        "VERIZON WIRELESS DES:PAYMENTS ID:0001", "Orig CO Name:AT&T Orig ID:0001", "T-MOBILE PCS SVC",
        "ACH WEB RECUR PCS SVC T MOBILE", "ACH WITHDRAWAL ATT PAYMENT 1234 FAB BUSINESS", "ELECTRONIC WITHDRAWAL TO ATT",
        "RECURRING PAYMENT AUTHORIZED ON 01/05 VZWRLSS*APOCC VISB CARD 1234", "METRO BY T MOBILE 1234",
    ],
)
def test_a_carrier_bill_is_not_a_d6_payee(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "ACH CORP DEBIT 00012345 FAB PARTNERS LLC BOOST MOBILE CUSTOMER ID 1",
        "Business to Business ACH Debit - FAB PARTNERS PAYMENT PAT DBA CRICKET WIRELESS LLC",
        "FAB MOBILE TIRE LLC",
        "MINT MOBILE FUNDING LLC",
        "FABRICATED CAPITAL DES:PAYMENT ID:0001 INDN:FAB T-MOBILE STORE LLC CO ID:0002 CCD",
    ],
)
def test_a_carrier_word_after_the_payees_own_name_never_skips(description):
    assert _states(description) == D6
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS, except for rows the channel rule already takes.

- [ ] **Step 3: Constants.**

```python
#: 5.3 (2026-09-27): phone and cable carriers, matched at the START of the payee's leading words
#: (_leading_payee_words), so a carrier printed after the payee's own name (a receiver that is a wireless dealer)
#: never decides. Brand names only; BELL, ROGERS, SHAW and SPRINT need their telecom word; ATT only in its bill and
#: payment forms. The VERIZON lookahead covers the registry's Verizon Visa alias only (a 'SYNCB VERIZON' card
#: payment in 'other' hides no funder).
_TELECOM_CARRIER_PATTERNS = (
    re.compile(r"(?:KOODO|FIDO|TELUS|VIDEOTRON|SASKTEL|EASTLINK|CHATR|COGECO)\b"),
    re.compile(r"(?:FREEDOM|VIRGIN|PUBLIC|LUCKY|BOOST|MINT|T) ?MOBILE\b"),
    re.compile(r"VIRGIN PLUS\b"),
    re.compile(r"BELL (?:CANADA|MOBILITY|MTS|ALIANT)\b"),
    re.compile(r"ROGERS (?:WIRELESS|COMMUNICATIONS?|CABLE)\b"),
    re.compile(r"SHAW (?:CABLE|COMMUNICATIONS?|DIRECT)\b"),
    re.compile(r"VERIZON\b(?! (?:CREDIT|VISA))"),
    re.compile(r"(?:VZWRLSS|AT AND T|METRO ?PCS|METRO BY T MOBILE|TRACFONE|COMCAST|XFINITY|CENTURYLINK|WINDSTREAM|"
               r"DIRECTV)\b"),
    re.compile(r"ATT\b(?= (?:BILL|PAYMENT|MOBILITY|UVERSE|WIRELESS)\b|\s*$)"),
    re.compile(r"(?:SPRINT|CRICKET|TOTAL) WIRELESS\b"),
    re.compile(r"(?:US|U S|CONSUMER) CELLULAR\b|USCELLULAR\b"),
    re.compile(r"(?:CHARTER|COX|FRONTIER) COMM(?:UNICATIONS?)?\b"),
    re.compile(r"DISH NETWORK\b"),
)
```

- [ ] **Step 4: Clause:**

```python
    leading = _leading_payee_words(text)
    carrier = next((found for pattern in _TELECOM_CARRIER_PATTERNS if (found := pattern.match(leading))), None)
    if carrier is not None and not _names_financing(text, besides=carrier.group(0)):
        return "telecom_carrier"
```

- [ ] **Step 5: Run.** **Step 6: Commit** `"d6: phone and cable carriers, read on the payee's leading words"`.

---

## Part B — Rule extensions (rows change state)

The Part B tests go to a new file, `tests/test_rule_extensions_53.py` (B1, B2, B4, B6, B7, B8), or to their own file (B3, B5). Create `tests/test_rule_extensions_53.py` in B1 with this header:

```python
"""5.3 (2026-09-27): existing rules read the bank wording they missed, so these rows change state. Fabricated
descriptors only."""
from __future__ import annotations

import pytest

from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import fake_payees, txn  # noqa: F401  (fixture)

WEEKLY = (2, 9, 16, 23)


def _state(description: str, amount: float = -100.0, *, bank: str | None = None) -> tuple[str, str, str | None]:
    record = classify_transaction(description, amount, bank=bank)
    return record.classification, record.matched_rule, record.canonical_entity
```

Run command for Part B: `cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe -m pytest tests/test_rule_extensions_53.py -q -p no:cacheprovider`, then SEL-CLASSIFIER.

### Task B1: Bank charges and returned items in abbreviated and French wording (bank_fee_or_charge plus structural CHG shapes)

**Files:** Modify `analysis/transaction_classifier.py`: `_NSF_PATTERNS` (`:268-276`), `_REFUND_REVERSAL_PATTERNS` (`:277-297`) and `_FEE_PATTERNS` (`:330-339`). Create `tests/test_rule_extensions_53.py`.

**Needs:** none.

**Why:** 264 rows / 49 occurrences, 8 keys. The rows become `fee` or `nsf_or_return`, which the spec already keeps out of D6. The `fee` state has no metric consumer; `nsf_or_return` feeds only the evidence-only `nsf_count` and the NSF fees chip. The underwriting NSF count (negative-ending days) does not move. Stop-payment returns become `nsf_or_return`, which is flagged for the owner.

The applied changes:
- A deposited item returned under a stop payment goes to `refund_or_reversal`, as RETURNED DEPOSIT does (evidence verifier).
- FRAIS never fires beside French loan or LOC words.
- The structural critic's charge wording outside FEE (EXTENDED OVERDRAFT CHG, OD CHARGE, PAID ITEM CHARGE, UNCOLLECTED FUNDS CHARGE…) joins. A bare CHARGE or CHG stays out: Capital One prints 'CHARGE <merchant>'.
- SANS PROVISION is not added.

Like today's FEES?, these words at step 6 outrank the known payee. The corpus has 0 rows where one sits next to a registered payee.

- [ ] **Step 1: Tests.** Create the file with the header above, then add:

```python
# --- B1: bank charges and returned items --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "OVERDRAWN HANDLING CHGS", "WIRE TRANS SVC CHARGE 0001", "INTERAC-SC-1234", "ACH BATCH CHARGE, ACH CHARGE SBIB",
        "W/D SVC 01/05 FAB PAI ATM", "FRAIS DECOUVERT 01/05", "FRAIS, CHEQUE SANS PROVISION", "EXTENDED OVERDRAFT CHG",
        "OD CHARGE", "PAID ITEM CHARGE", "UNCOLLECTED FUNDS CHARGE", "MERCHANT SERVICES CHG",
    ],
)
def test_bank_charges_in_abbreviated_and_french_wording_are_fees(description):
    assert _state(description, -5.0)[:2] == ("fee", "bank_or_processing_fee")


@pytest.mark.parametrize("description", ["RTN STOP PAYT 1234", "FR. EFFET RET.", "RETURNED STOP PAYMENT 1234"])
def test_returned_items_in_abbreviated_and_french_wording_are_nsf_or_return(description):
    assert _state(description, -100.0)[0] == "nsf_or_return"


def test_a_deposited_item_returned_under_a_stop_payment_is_a_reversal():
    assert _state("Deposited Item Returned Stop Payment 1234", 700.0)[0] == "refund_or_reversal"


def test_french_loan_wording_after_frais_stays_a_bank_loan():
    assert _state("FRAIS INTERETS SUR PRET 1234", -50.0, bank="Fabricated Bank")[:2] == ("bank_loan", "french_loan_wording")


def test_a_returned_funder_debit_credit_keeps_its_financing_proceeds_revenue(fake_payees):
    record = classify_transaction("FABRICATED LENDER ACH DEBIT RETURNED STOP PAYMENT", 400.0)
    assert record.classification == "nsf_or_return"
    assert record.revenue_match_method == "financing_proceeds_credit"
    assert record.contributes_to_lender_credit_exclusion
```

- [ ] **Step 2: Run.** Expected: FAIL (the rows are `other` today).

- [ ] **Step 3: Patterns.**
  - Append to `_NSF_PATTERNS`:

```python
    # 5.3 (2026-09-27): a returned item in the banks' abbreviated and French wording: TD's stop-payment return of
    # the business's own debit, and the French returned-item charge. A deposited item returned under a stop payment
    # is a reversal (_REFUND_REVERSAL_PATTERNS), as RETURNED DEPOSIT is.
    re.compile(r"\bRTN STOP PAY(?:T|MT|MENT)?\b|(?<!\bITEM )\bRETURNED STOP PAY(?:T|MT|MENT)?\b"),
    re.compile(r"\bEFFETS? (?:RET|RETOUR|RETOURNES?)\b"),
```

  - Append to `_REFUND_REVERSAL_PATTERNS`:

```python
    re.compile(r"\bDEPOSITED ITEM RETURNED\b"),
```

  - Append to `_FEE_PATTERNS`:

```python
    # 5.3 (2026-09-27): bank charges printed without FEE: the SVC/SERV/CHG abbreviations, charges whose CHARGE is
    # not next to SERVICE/MONTHLY/OVERDRAFT/PROCESSING, RBC's Interac service-charge code SC, the ATM withdrawal
    # service charge, and the French FRAIS, never beside French loan or line-of-credit words. A bare CHARGE or CHG
    # is never a fee word (Capital One prints 'CHARGE <merchant>').
    re.compile(r"\b(?:SVC|SRVC?|SERV|SERVICES?) (?:CHARGES?|CHGS?|CHRGS?)\b|\bSERVICE (?:CHGS?|CHRGS?)\b"),
    re.compile(r"\b(?:OVERDRAWN|OVERDRAFT|HANDLING|BATCH) (?:CHARGES?|CHGS?|CHRGS?)\b"),
    re.compile(
        r"\b(?:EXTENDED OVERDRAFT|CONTINUOUS OD|OD|OVERDRAFT ITEM|PAID ITEM|PER ITEM|UNCOLLECTED FUNDS|COURTESY PAY"
        r"|WIRE|ACH ORIGINATION|CURRENCY HANDLING) (?:CHARGES?|CHGS?)\b"
    ),
    re.compile(r"\bINTERAC SC\b"),
    re.compile(r"\bW D SVC\b"),
    re.compile(r"^FRAIS\b(?!.*\b(?:FINANCEMENT|INTERETS?|PRET|MARGE|MCR)\b)"),
```

- [ ] **Step 4: Run** the file (PASS) and SEL-CLASSIFIER. The in-memory prototype of Part B moved no existing test (2026-09-27).

- [ ] **Step 5: Commit** (`git add analysis/transaction_classifier.py tests/test_rule_extensions_53.py`) `"fee and nsf: abbreviated and French bank charges and returned items"`.

---

### Task B2: Cheque spellings (check_payment plus structural CHK/CK)

**Files:** Modify `analysis/transaction_classifier.py`: `_CHECK_PATTERNS` (`:474-477`). Append to `tests/test_rule_extensions_53.py`.

**Needs:** none.

**Why:** 188 rows / 33 occurrences, 3 keys. Every new pattern is anchored at the start and requires the instrument's number (both verifiers: `^DRAFT WITHDRAWAL DRAFT ?[0-9]`). Anchoring keeps out:
- CHQ as an account label ('BUS CHQ');
- '… SHARE DRAFT' printed as an ACH label;
- Navy Federal's 'Paid To - <funder> Chk ####' inside a real funder's rows.

The structural critic's CHK/CK (medium) join in the same anchored form. Bare DRAFT stays out: AUTO DRAFT, WEB DRAFT and ACH DRAFT are lender collection wording. The rows stay `other` (`matched_rule` `check`), so `check_count` rises by about 2,223 rows (Scotiabank, TD, Consumers CU, Symitar). A registered known payee printed after the number is still read at step 7. A potential-registry alias printed after it is excluded, exactly as 'CHECK nnnn <alias>' is today.

- [ ] **Step 1: Tests.** Append:

```python
# --- B2: cheque spellings ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    ["CHQ 123", "CHQ#123", "SHARE DRAFT (12345)", "Draft Withdrawal Draft # 1234", "CHK 1234", "IMAGE CHK 1234", "CK #1234"],
)
def test_canadian_and_credit_union_cheque_spellings_are_cheques(description):
    record = classify_transaction(description, -500.0)
    assert (record.classification, record.matched_rule, record.is_check) == ("other", "check", True)


@pytest.mark.parametrize(
    "description",
    ["PRE-AUTHORIZED PAYMENT BUS CHQ FAB CAPITAL", "ACH DEBIT FAB CAPITAL SHARE DRAFT",
     "Draft Withdrawal ACH FAB CAPITAL LLC", "PAID TO - FAB CAPITAL CHK 1234567"],
)
def test_a_cheque_word_that_is_not_the_instrument_never_claims_the_row(description):
    assert classify_transaction(description, -500.0).matched_rule != "check"


def test_a_known_payee_after_the_cheque_number_is_still_named(fake_payees):
    assert classify_transaction("CHQ 417 FABRICATED LENDER", -500.0).classification == "confirmed_lender"
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS.

- [ ] **Step 3: Patterns.** Append to `_CHECK_PATTERNS`:

```python
    # 5.3 (2026-09-27): the Canadian, credit-union and short cheque spellings, anchored at the start and with the
    # instrument's number, so a label ('BUS CHQ', '... SHARE DRAFT', Navy Federal's 'Paid To - <payee> Chk nnn')
    # never makes a row a cheque. Bare DRAFT is lender collection wording (AUTO DRAFT, WEB DRAFT).
    re.compile(r"^CHQ ?[0-9]"),
    re.compile(r"^SHARE DRAFTS? ?[0-9]"),
    re.compile(r"^DRAFT WITHDRAWAL DRAFT ?[0-9]"),
    re.compile(r"^(?:IMAGE |PAID )?CHK ?[0-9]"),
    re.compile(r"^CK ?[0-9]"),
```

- [ ] **Step 4: Run.** **Step 5: Commit** `"checks: Canadian, credit-union and short cheque spellings, anchored and numbered"`.

---

### Task B3: Field-order payee forms: Amex loans and Amex card payments (alternative_position_platform; P1 of credit_card_payment)

**Files:**
- Modify `analysis/classification_registry.py`: a new hand-kept `FIELD_ORDER_PAYEE_FORMS`, directly after `PAYOUT_CREDIT_ENTITIES` (`:1381`).
- Modify `analysis/transaction_classifier.py`:
  - the import block (`:9-20`);
  - three helpers and `_field_order_debit_record` directly before `def _known_payee_debit_record(` (`:1124`);
  - `classify_transaction` after the membership check (`:1577-1578`) and at step 7 (`:1671-1673`).
- Modify `tools/lender_ledger.py` (`Rules`, `current_rules`, a new `field_order_problems`, `_unmasked_problems`).
- Modify `docs/lender-registry-ledger.json`: the notes of `American Express Loans` and `American Express [credit card payment]`.
- Re-render `analysis/classification_registry.py` and `docs/lender-registry-evidence.md`.
- Create `tests/test_field_order_payees.py`.
- Modify `tests/test_lender_ledger.py`.

**Needs:** none.

**Why:**
- Amex loans: 45 rows / 42 occurrences, 2 keys.
- Amex card payments: c00010, 594 rows / 27 occurrences, plus about 1,765 Chase-layout Amex card rows that are `other` today. They become Credit cards, named 'American Express [credit card payment]'.

The admitted aliases need consecutive tokens, but Chase prints the originator and the entry description in separate fields, and Truist prints the entry description first. The entity names live in the registry, validated against the ledger (evidence verifier). The applied changes:
- The Chase loan form spells the field sequence out.
- The card form's span cannot cross another `CO ENTRY` field.
- Both Chase forms refuse any row that holds two originator blocks: a merged row is a parse artifact that stays in review, in either order.
- The Truist form is anchored at the start.
- Debits only: the 30 loan-disbursement credits keep today's treatment, and the owner decides the credit side.
- A field-order hit has its own `match_method` (`known_payee_field_order`) and `matched_rule` (`<state>_field_order`), and no `matched_alias`, so no record claims an alias its text does not print.

The fixed daily Amex ACH PMT series may be Amex Merchant Financing (card lender-risk). Either reading is never lender math: card payments are a flag, and Amex financing is an alternative position. The owner is told.

- [ ] **Step 1: Write the failing tests** `tests/test_field_order_payees.py`:

```python
"""5.3 (owner ruling 2026-09-27): admitted payees printed in the bank's field order (FIELD_ORDER_PAYEE_FORMS).
Fabricated descriptors in the Chase and Truist layouts; the payees are the registry's admitted American Express
entities."""
from __future__ import annotations

import pytest

from analysis.classification_registry import FIELD_ORDER_PAYEE_FORMS, PAYEE_GROUP_REGISTRIES
from analysis.transaction_classifier import classify_transaction

CHASE_LOAN = ("Orig CO Name:American Express Orig ID:1234567890 Desc Date:540105 CO Entry Descr:Loan Pmt Sec:CCD "
              "Trace#:1234 Ind Name:Fab Holder")
CHASE_LOAN_GLUED = "Orig CO Name:American Express Orig ID:1234567890 Desc Date: CO Entry Descr:Loan PmtSec:CCD"
TRUIST_LOAN = "ACH CORP DEBIT LOAN PMT AMERICAN EXPRESS FAB HOLDER CUSTOMER ID 0001"
CHASE_CARD = "Orig CO Name:American Express Orig ID:1234567890 Desc Date:540105 CO Entry Descr:ACH Pmt Sec:PPD"


@pytest.mark.parametrize("description", [CHASE_LOAN, CHASE_LOAN_GLUED, TRUIST_LOAN])
def test_amex_loan_payments_in_field_order_are_an_alternative_position(description):
    record = classify_transaction(description, -500.0)
    assert (record.classification, record.canonical_entity, record.flagged_group) == (
        "alternative_position", "American Express Loans", "alternative_positions")
    assert (record.match_method, record.matched_rule, record.matched_alias) == (
        "known_payee_field_order", "alternative_position_field_order", None)
    assert not record.contributes_to_potential_lender_totals and not record.contributes_to_withholding_rate


def test_a_chase_amex_card_payment_is_a_named_credit_card_payment():
    record = classify_transaction(CHASE_CARD, -500.0)
    assert (record.classification, record.canonical_entity, record.flagged_group) == (
        "credit_card_payment", "American Express [credit card payment]", "credit_cards")


@pytest.mark.parametrize(
    "description",
    [
        # a merged row, in either order: the other originator's LOAN PMT stays in review
        "Orig CO Name:American Express Orig ID:1 Desc Date:540105 CO Entry Descr:ACH Pmt Sec:CCD "
        "Orig CO Name:Fab Funding Orig ID:2 Desc Date:540105 CO Entry Descr:Loan Pmt Sec:CCD",
        "Orig CO Name:American Express Orig ID:1 Desc Date:540105 CO Entry Descr:Loan Pmt Sec:CCD "
        "Orig CO Name:Fab Funding Orig ID:2 Desc Date:540105 CO Entry Descr:ACH Pmt Sec:CCD",
        # a wire memo that names Amex: the payee is the beneficiary
        "A/C: Fabricated Funding Ref: Loan Payment American Express Card",
    ],
)
def test_a_merged_row_or_a_memo_never_becomes_an_amex_payment(description):
    assert classify_transaction(description, -500.0).classification == "potential_lender"


def test_credits_keep_todays_rules():
    record = classify_transaction(
        "Orig CO Name:American Express Orig ID:1234567890 Desc Date:540105 CO Entry Descr:Loan Sec:CCD", 3000.0)
    assert record.classification == "other"
    assert record.revenue_match_method == "strong_non_revenue_rule"
    assert not record.contributes_to_lender_credit_exclusion


def test_every_field_order_entity_is_a_known_payee_entity():
    entities = {entity for registry in PAYEE_GROUP_REGISTRIES.values() for entity in registry}
    assert set(FIELD_ORDER_PAYEE_FORMS) <= entities
```

- [ ] **Step 2: Run** `tests/test_field_order_payees.py`. Expected: FAIL (`ImportError: cannot import name 'FIELD_ORDER_PAYEE_FORMS'`).

- [ ] **Step 3: The registry constant.** After `PAYOUT_CREDIT_ENTITIES` in `analysis/classification_registry.py`, add:

```python

#: Owner ruling 2026-09-27 (classification 5.3): the printed forms, in the bank's field order, of admitted payees whose
#: bank prints the originator and the entry description apart, so no contiguous alias can match them (Chase's
#: 'ORIG CO NAME ... CO ENTRY DESCR' fields; Truist's entry description first). Keyed by ledger entity; each value is
#: a regular expression read on the normalized row, on DEBITS ONLY, when no alias matched. The Chase forms refuse a
#: row that holds two originator blocks (a merged row stays in review). tools/lender_ledger.py refuses an entity
#: that is not admitted in a known-payee group.
FIELD_ORDER_PAYEE_FORMS: dict[str, tuple[str, ...]] = {
    "American Express Loans": (
        r"^(?!.*\bORIG CO NAME\b.*\bORIG CO NAME\b).*\bORIG CO NAME AMERICAN EXPRESS ORIG ID [A-Z0-9]+ DESC DATE"
        r"(?: [A-Z0-9]+)? CO ENTRY DESCR LOAN(?: (?:PMT|PYMT|PAYMENT))?(?:SEC)?\b",
        r"^(?:ACH CORP (?:DEBIT|CREDIT) )?LOAN(?: (?:PMT|PYMT|PAYMENT))? AMERICAN EXPRESS\b",
    ),
    "American Express [credit card payment]": (
        r"^(?!.*\bORIG CO NAME\b.*\bORIG CO NAME\b).*\bORIG CO NAME AMERICAN EXPRESS ORIG ID\b"
        r"(?:(?!\bCO ENTRY\b).)*?\bCO ENTRY (?:[0-9]+ )?DESCR (?:ACH |RETRY )?(?:PAYMENT|PMT|PYMT|EPAYMENT)(?:SEC)?\b",
    ),
}
```

The constant is not in the GENERATED block: `--write` never touches it.

- [ ] **Step 4: The classifier.**
  - Add `FIELD_ORDER_PAYEE_FORMS,` to the `from .classification_registry import (` block, alphabetically after `CARD_ISSUER_CONTEXT_ALIASES,`.
  - Directly before `def _known_payee_debit_record(`, insert:

```python
def _compile_field_order_forms() -> tuple[tuple[re.Pattern[str], PayeeMatch], ...]:
    """FIELD_ORDER_PAYEE_FORMS compiled once, each with its payee's group (PAYEE_GROUP_REGISTRIES)."""
    state_of = {entity: state for state, registry in PAYEE_GROUP_REGISTRIES.items() for entity in registry}
    return tuple(
        (re.compile(form), PayeeMatch(entity, state_of[entity], ""))
        for entity, forms in FIELD_ORDER_PAYEE_FORMS.items()
        if entity in state_of
        for form in forms
    )


_FIELD_ORDER_FORMS = _compile_field_order_forms()


def _field_order_payee(text: str) -> PayeeMatch | None:
    """5.3 (owner ruling 2026-09-27): the admitted payee a debit prints in the bank's field order, or None."""
    return next((match for pattern, match in _FIELD_ORDER_FORMS if pattern.search(text)), None)


def _field_order_debit_record(
    common: dict[str, object],
    text: str,
    match: PayeeMatch,
) -> TransactionClassification:
    """A debit to a payee read from the bank's fields: its group (D9's LOC wording still wins), with no alias."""
    if match.state in _LOC_OVERRIDE_STATES and _matches_any(text, _LINE_OF_CREDIT_PATTERNS):
        state, rule = "line_of_credit", "line_of_credit_descriptor_override"
    else:
        state, rule = match.state, f"{match.state}_field_order"
    return _build_record(
        **common,
        classification=state,
        canonical_entity=match.entity,
        match_method="known_payee_field_order",
        matched_rule=rule,
        confidence_score=0.97,
        reason=(
            f"The bank printed the originator and the entry description of {match.entity} in separate fields; "
            f"read from those fields, the row is {_state_words(state)}."
        ),
    )
```

  - In `classify_transaction`, directly after

```python
    if known_payee is not None and amount < 0 and _is_membership_or_top_up(text, known_payee):
        known_payee = None
```

add

```python
    # 5.3 (owner ruling 2026-09-27): an admitted payee printed in the bank's field order, on a debit no alias
    # matched (FIELD_ORDER_PAYEE_FORMS). Credits keep today's rules.
    field_order_payee = _field_order_payee(text) if known_payee is None and amount < 0 else None
    if field_order_payee is not None:
        known_payee = field_order_payee
```

  - At step 7, replace

```python
        if amount < 0:
            return _known_payee_debit_record(common, text, known_payee)
```

with

```python
        if amount < 0:
            if field_order_payee is not None:
                return _field_order_debit_record(common, text, known_payee)
            return _known_payee_debit_record(common, text, known_payee)
```

- [ ] **Step 5: The validator.** In `tools/lender_ledger.py`:
  - `Rules` gains a last field, `field_order: Mapping[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)` (import `dataclasses`), so the fixtures that build `Rules` without it still work.
  - `current_rules()` passes `field_order=registry.FIELD_ORDER_PAYEE_FORMS`.
  - Add, after `payout_credit_problems`:

```python
def field_order_problems(entities: list[LedgerEntity], forms: Mapping[str, tuple[str, ...]]) -> list[str]:
    """The owner's field-order ruling (FIELD_ORDER_PAYEE_FORMS, 2026-09-27): each entity is an admitted ledger entity
    of a known-payee group, and each form compiles."""
    named = _by_name(entities)
    problems = []
    for name, patterns in forms.items():
        entity = named.get(name)
        if entity is None or entity.status != "admitted" or entity.group not in PAYEE_STATES:
            problems.append(f"FIELD_ORDER_PAYEE_FORMS names {_shown(name)}, which is not an admitted ledger entity of "
                            f"a known-payee group")
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error:
                problems.append(f"FIELD_ORDER_PAYEE_FORMS has a form of {_shown(name)} that does not compile")
    return problems
```

  - Call it in `_unmasked_problems` directly after `payout_credit_problems(...)`: `problems.extend(field_order_problems(entities, rules.field_order))`.
  - In `tests/test_lender_ledger.py`, add two tests that use the module's `ledger()` and `RULES` fixtures: a `dataclasses.replace(RULES, field_order={"Nonexistent Payee": ("X",)})` gives exactly one problem naming `FIELD_ORDER_PAYEE_FORMS`, and a form `"("` gives the compile problem.

- [ ] **Step 6: The ledger notes.** In `docs/lender-registry-ledger.json`:
  - The `American Express Loans` notes replace the sentence saying the Chase field form "stays unmatched" with: `Since classification 5.3 (owner ruling 2026-09-27), FIELD_ORDER_PAYEE_FORMS reads the Chase field layout (ORIG CO NAME AMERICAN EXPRESS ... CO ENTRY DESCR LOAN [PMT]) and Truist's reversed order (LOAN PMT AMERICAN EXPRESS) on debits; credits keep their rules.`
  - The `American Express [credit card payment]` notes gain: `Since 5.3, FIELD_ORDER_PAYEE_FORMS reads the Chase field layout (ORIG CO NAME AMERICAN EXPRESS ... CO ENTRY DESCR [ACH |RETRY ]PMT) on debits.`

  Then run `cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe -m tools.build_lender_registry --check`: 0 problems, and the move lines are unchanged from before the edit. Then run it with `--write`.

- [ ] **Step 7: Run** `tests/test_field_order_payees.py` (PASS), SEL-REGISTRY (no failure) and SEL-CLASSIFIER.

- [ ] **Step 8: Commit** (`git add analysis/classification_registry.py analysis/transaction_classifier.py tools/lender_ledger.py docs/lender-registry-ledger.json docs/lender-registry-evidence.md tests/test_field_order_payees.py tests/test_lender_ledger.py`) `"known payee: admitted payees printed in the bank's field order (Amex loans, Amex card payments), debits only"`.

---

### Task B4: Card-payment wording, and an issuer printed alone (credit_card_payment P2-P4)

**Files:** Modify `analysis/transaction_classifier.py`:
- `_CARD_PAYMENT_CONTEXT_PATTERNS[0]` (`:466`);
- `_CREDIT_CARD_PATTERNS` (`:387-401`);
- a new D6 clause and its helper above `def _d6_skip(`.

Append to `tests/test_rule_extensions_53.py`.

**Needs:** B3, 0.3.

**Why:**
- P2: the run-together CREDITCARD counts as card wording, which closes the ledger's Barclays gap. c00158 becomes `credit_card_payment`.
- P3: Navy Federal's 'CREDIT CARD RECUR' memo (c00039, 48 rows).
- P4: a row whose payee IS a listed card issuer printed alone (TD 'VISA TD' / 'VISA DESJARD' / 'CAPTL ONE MC' bill payments, 'APPLECARD GSBANK') stays unflagged `other`, as C10 says. Now D6 does not review it either.

P4 is narrowed by both verifiers: the issuer alias's words must lead the D11 payee words. A funder whose name merely contains an issuer token (SYF, WEX BANK, PC FINANCIAL) keeps its review, and the shared veto is added on top. P4 changes the contract of `card_issuer_context` (a second, negative reading), so F2 amends the C10 contract and the registry docstring. Atlas Smart Pay and RTS Carrier Services would need card-context entries first; no research file carries them, so they stay in review (open question 9).

- [ ] **Step 1: Tests.** Append:

```python
# --- B4: card-payment wording, and an issuer printed alone --------------------------------------------------------

def test_the_run_together_creditcard_is_card_payment_wording():
    assert _state("BARCLAYCARD US DES:CREDITCARD ID:0001 INDN:FAB HOLDER CO ID:0002 PPD") == (
        "credit_card_payment", "credit_card_payment", "Barclays Bank Delaware [credit card payment]")


def test_a_recurring_card_payment_memo_is_a_card_payment():
    assert _state("NFCU ACH 0001 CREDIT CARD RECUR")[:2] == ("credit_card_payment", "credit_card_payment")


def _d6_states(description: str) -> set[tuple[str, str]]:
    statement = Statement(transactions=[txn(f"2054-01-{day:02d}", description, -300.0) for day in WEEKLY])
    return {(record.classification, record.match_method) for record in classify_statement_transactions(statement)}


@pytest.mark.parametrize("description", ["VISA TD ABC123", "CAPTL ONE MC ABC123", "Electronic Withdrawal To APPLECARD GSBANK"])
def test_an_issuer_printed_alone_stays_unflagged_and_is_not_a_d6_payee(description):
    assert _d6_states(description) == {("other", "default")}


@pytest.mark.parametrize("description", ["FABRICATED SYF CAPITAL LLC", "SYF FAB CAPITAL LLC"])
def test_an_issuer_token_inside_a_funder_name_never_hides_it(description):
    assert _d6_states(description) == {("potential_lender", "recurring_fixed_debit")}
```

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Wording.**
  - `_CARD_PAYMENT_CONTEXT_PATTERNS[0]` becomes `re.compile(r"\b(?:CREDIT CARD|CREDITCARD|CRCARD|CRD|CARD|CARDMEMBER)\b"),`.
  - Append to `_CREDIT_CARD_PATTERNS`:

```python
    # 5.3 (2026-09-27): Navy Federal's memo for a recurring card payment.
    re.compile(r"\bCREDIT CARD RECUR(?:RING)?\b"),
```

- [ ] **Step 4: The D6 clause.** Above `def _d6_skip(`:

```python
#: 5.3 (2026-09-27): each card_issuer_context alias's normalized words, computed once.
_CARD_ISSUER_CONTEXT_WORDS = {
    alias: tuple(normalize_transaction_description(alias).split())
    for aliases in CARD_ISSUER_CONTEXT_ALIASES.values()
    for alias in aliases
}


def _names_card_issuer(payee: Sequence[str], text: str) -> bool:
    """5.3: the payee IS a listed card issuer printed alone (C10 keeps that row unflagged): the issuer alias's words
    lead the D11 payee words, and the rest of the row names no financing. An issuer token inside a longer name
    (FABRICATED SYF CAPITAL) is never enough."""
    found = registry_match(" ".join(payee), CARD_ISSUER_CONTEXT_ALIASES)
    if found is None:
        return False
    words = _CARD_ISSUER_CONTEXT_WORDS.get(found[1], ())
    return bool(words) and tuple(payee[: len(words)]) == words and not _names_financing(
        text, besides=" ".join(words)
    )
```

In `_d6_skip`:

```python
    if _names_card_issuer(payee, text):
        return "card_issuer_alone"
```

- [ ] **Step 5: Run.** The pin at `tests/test_obligation_descriptors.py:170-176` (an issuer alone stays unflagged) must still pass unchanged.

- [ ] **Step 6: Commit** `"cards: CREDITCARD and CREDIT CARD RECUR wording; an issuer printed alone is not a D6 payee"`.

---

### Task B5: Payroll providers and benefit administrators (payroll_or_benefits_provider plus structural)

**Files:** Modify `analysis/transaction_classifier.py`:
- new constants after `_PAYMENT_MARKER_PATTERNS` (`:529-538`);
- a helper directly before `def _unknown_payee_tokens(` (after 0.2's readers);
- the payroll rule at `:1645-1653`.

Create `tests/test_payroll_providers.py`. Modify `tests/test_new_statement_corpus.py:153` (pin-ledger row 16).

**Needs:** 0.1, 0.2.

**Why:** 66 rows / 19 occurrences, 3 keys become `payroll`. About 443 corpus rows change state in all: the payroll state has no metric consumer, and credit revenue is unchanged. The lender-risk verifier's REQUIRED changes are applied:
- N1: provider and benefit-administrator names are read on the originator segment, never in INDN, IND NAME or a label-less holder field;
- N2: nothing new fires on a row that names financing. The shared veto, which is stronger than N2's word list, is used;
- N3: 401(k) is dropped.

The list is evidence-only: providers with corpus rows (Paycor, OnPay, Payworks, Paycom, Paylocity, Patriot Software, Datapay) and named benefit administrators. French PAIE and SALAIRE (structural, medium) join, read the same way. Glued PAYROLLTAX becomes `payroll`, not `tax`, which keeps the unguarded tax rule untouched.

- [ ] **Step 1: Write the failing test** `tests/test_payroll_providers.py`:

```python
"""5.3 (2026-09-27): payroll providers and benefit administrators are payroll, read on the originator only, never in a
receiver field, and never on a row that names financing. Fabricated descriptors only."""
from __future__ import annotations

import pytest

from analysis.transaction_classifier import classify_transaction
from tests.flag_group_fixtures import fake_payees  # noqa: F401  (fixture)


@pytest.mark.parametrize(
    "description",
    [
        "PATRIOT SOFTWARE DES:PAYROLLTAX ID:0001 INDN:FAB HOLDER CO ID:0002 CCD",
        "ACH DEBIT DATAPAY IN 1234 C 5678 BILLING 9",
        "HEALTHEQUITY INC HEALTHEQUI 1234",
        "ONPAY INC PAYROLLTS 1234",
        "PAYCOR INC PAYCOR 123456",
        "Paie Pat Example",
    ],
)
def test_payroll_providers_and_benefit_administrators_are_payroll(description):
    assert classify_transaction(description, -100.0).classification == "payroll"


@pytest.mark.parametrize(
    "description",
    [
        "FABRICATED LENDER DES:PAYMENT ID:0001 INDN:TASC BUILDERS INC CO ID:0002 CCD",
        "Orig CO Name:Fabricated Lender Orig ID:0001 CO Entry Descr:Payment Ind Name:Human Interest Media LLC",
        "FABRICATED LENDER DEBIT CCD 0105 TASC BUILDERS INC",
        "FABRICATED LENDER DES:PAYMENT ID:0001 INDN:FAB 401K ADVISORS LLC CO ID:0002 CCD",
    ],
)
def test_a_holder_named_like_a_provider_never_hides_its_lender(fake_payees, description):
    assert classify_transaction(description, -100.0).classification == "confirmed_lender"


def test_the_lenders_proceeds_credit_keeps_its_treatment(fake_payees):
    record = classify_transaction("FABRICATED LENDER DES:PAYMENT ID:0001 INDN:TASC BUILDERS INC CO ID:0002 CCD", 5000.0)
    assert record.revenue_match_method == "financing_proceeds_credit"


@pytest.mark.parametrize(
    "description",
    ["TASC INC LOAN PAYMENT", "HEALTH EQUITY CAPITAL LLC DEBIT CCD", "PAYCOR FUNDING DES:PAYMENT ID:0001",
     "ACH DEBIT FAB WIDGETS 401K 0001"],
)
def test_a_provider_word_beside_financing_or_a_bare_401k_is_not_payroll(description):
    assert classify_transaction(description, -100.0).classification != "payroll"
```

- [ ] **Step 2: Run.** Expected: the first parametrization FAILS.

- [ ] **Step 3: Constants.** After `_PAYMENT_MARKER_PATTERNS`:

```python
#: 5.3 (2026-09-27): PAYROLL glued to an ACH entry-description suffix (a closed list, so a receiver name that only
#: contains PAYROLL is not read), payroll providers seen in the corpus, benefit administrators and retirement-plan
#: recordkeepers, and the French pay words. Provider, administrator and French words are read on the originator
#: segment only (_originator_segment): a holder named like one of them in INDN or IND NAME never hides its lender.
#: No new pattern fires on a row that names financing. 401(k) is left out (it prints in holder names).
_PAYROLL_GLUED_PATTERN = re.compile(r"\bPAYROLL(?:TAX(?:ES)?|TX|TS|DDS?|DEP|FEES?)\b")
_PAYROLL_PROVIDER_PATTERNS = (
    re.compile(r"\b(?:PATRIOT SOFTWARE|DATAPAY|PAYCOR|ONPAY|PAYWORKS|PAYCOM|PAYLOCITY)\b"),
    re.compile(r"\b(?:HEALTH ?EQUI(?:TY)?|WAGEWORKS|TASC|ASCENSUS|HUMAN INTEREST|GUIDELINE RETIRE(?:MENT)?)\b"),
    re.compile(r"\bPAIE\b|\bSALAIRES?\b"),
)
```

- [ ] **Step 4: Helper**, directly before `def _unknown_payee_tokens(`:

```python
def _is_payroll_provider_row(text: str) -> bool:
    """5.3: a payroll provider, benefit administrator or French pay row (payroll N1 and N2)."""
    if _names_financing(text):
        return False
    return _PAYROLL_GLUED_PATTERN.search(text) is not None or _matches_any(
        _originator_segment(text), _PAYROLL_PROVIDER_PATTERNS
    )
```

- [ ] **Step 5: The rule.** Replace `if _matches_any(text, _PAYROLL_PATTERNS):` with `if _matches_any(text, _PAYROLL_PATTERNS) or _is_payroll_provider_row(text):`. Its reason becomes `"The descriptor identifies payroll, wages, a payroll provider or an employee-benefits administrator."`.

- [ ] **Step 6: Re-pin navigant (pin-ledger row 16).** In `tests/test_new_statement_corpus.py`, the navigant entry's `"lenders": (0, 0.00, 3, 108.00),` (`:153`) becomes `"lenders": (0, 0.00, 0, 0.00),`, with a comment: `# 5.3: its three fixed weekly debits are a payroll provider's billing (payroll), no longer a potential lender.` Nothing else in the entry moves. If anything else moves, stop and report it.

- [ ] **Step 7: Run** the file (PASS) and SEL-CLASSIFIER. `tests/test_classifier_lookups.py::test_each_row_is_normalized_exactly_once` must pass: the helper normalizes nothing.

- [ ] **Step 8: Commit** (`git add analysis/transaction_classifier.py tests/test_payroll_providers.py tests/test_new_statement_corpus.py`) `"payroll: providers and benefit administrators, read on the originator, never beside financing"`.

---

### Task B6: Mortgage payment wording, a transfer to the bank's loans, the bank's own loan interest

**Files:** Modify `analysis/transaction_classifier.py`:
- `_MORTGAGE_PATTERNS` (`:410`);
- `_OWN_LOAN_TRANSFER_PATTERNS[0]` (`:429`);
- `_UNNAMED_LOAN_PAYMENT_PATTERNS` (`:509`);
- `_BANK_TEMPLATE_WORDS` (`:512`).

Append to `tests/test_rule_extensions_53.py`.

**Needs:** none.

**Why:**
- MTG PYMT(S) / MTGE PAYMENT: 58 corpus rows, the FREEDOM key c00201 included, plus the structural critic's MTG/MTGE (medium). Mortgage servicers also leave D10: 'LAKEVIEW LOAN SERVICING DES:MTG PYMT' becomes a mortgage (naming verifier).
- `TRANSFER TO LOANS`: c00198, 3 rows. The only verified path, per the evidence verifier.
- The statement bank's own LOAN INTEREST (structural, medium) becomes a bank loan, but only when the row names no payee (the D5 unnamed-loan guard). INTEREST, CHARGE and CHARGED join that guard's template words.

- [ ] **Step 1: Tests.** Append:

```python
# --- B6: mortgage wording, a transfer to the bank's loans, the bank's own loan interest ----------------------------

@pytest.mark.parametrize("description", ["FAB SERVICER DES:MTG PYMTS ID:0001", "MTGE PAYMENT 1234", "MTG PYMT 1234"])
def test_mortgage_payment_abbreviations_are_mortgages(description):
    assert _state(description, -900.0)[:2] == ("mortgage", "mortgage_descriptor")


def test_a_transfer_to_the_banks_loans_is_its_own_loan():
    assert _state("Loan payment ICPAYMENT TRANSFER TO LOANS 1234", -300.0, bank="Fabricated Bank") == (
        "bank_loan", "own_bank_loan_transfer", "Fabricated Bank")


def test_the_banks_own_loan_interest_is_a_bank_loan():
    assert _state("LOAN INTEREST CHARGE", -100.0, bank="Fabricated Bank") == (
        "bank_loan", "unnamed_loan_payment", "Fabricated Bank")


def test_loan_interest_that_names_a_payee_is_not_the_banks():
    assert _state("FAB CAPITAL LOAN INTEREST", -100.0)[0] != "bank_loan"
```

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Patterns.**
  - `_MORTGAGE_PATTERNS` becomes:

```python
_MORTGAGE_PATTERNS = (
    re.compile(r"\bMORTGAGES?\b"),
    re.compile(r"HOME ?EQUITY ?LOANS?\b"),
    # 5.3 (2026-09-27): the mortgage payment abbreviations (MTG PYMT, MTGE PAYMENT).
    re.compile(r"\bMTGE? (?:PYMTS?|PMTS?|PAYMENTS?)\b"),
)
```

  - `_OWN_LOAN_TRANSFER_PATTERNS[0]` becomes `re.compile(r"\b(?:TRANSFER|TFR) TO (?:MY |YOUR )?LOANS?\b"),`.
  - `_UNNAMED_LOAN_PAYMENT_PATTERNS` becomes:

```python
_UNNAMED_LOAN_PAYMENT_PATTERNS = (
    re.compile(r"\bLOANS? (?:PAYMENT|PAYMENTS|PYMT|PMT|REPAYMENT)\b"),
    # 5.3 (2026-09-27): the statement bank's own loan interest, with no payee printed.
    re.compile(r"\bLOAN INTEREST\b"),
)
```

  - `_BANK_TEMPLATE_WORDS` becomes `frozenset({"NO", "BR", "AUTOMATED", "COMPTE", "DIVERS", "INTEREST", "CHARGE", "CHARGED"})`.

- [ ] **Step 4: Run.** **Step 5: Commit** `"obligations: MTG payment wording, transfers to the bank's loans, the bank's own loan interest"`.

---

### Task B7: POS labels where right (card_purchase_format's explicit labels; structural PIN PURCHASE)

**Files:** Modify `analysis/transaction_classifier.py`: `_POS_PATTERNS` (`:298-313`). Append to `tests/test_rule_extensions_53.py`.

**Needs:** A1 (A1 leaves these four labels to the POS rule).

**Why:** These labels are card-purchase-only wording of the same kind the POS rule already reads (CARD, DEBIT, INTERAC, CONTACTLESS, TAP PURCHASE):
- BofA MOBILE PURCHASE;
- CIBC RETAIL PURCHASE, which also takes the misfiled Cooper Equipment candidate rows (c00230);
- Regions PIN PURCHASE (structural, high);
- the French card-purchase forms: the card deep-dive's C/ACHAT (c00086), ACHAT AU DETAIL (c00135) and ACHAT INTERAC, and BMO's ACHAT PAR CARTE and ACHAT EN LIGNE, which a read-only corpus scan of every row printing ACHAT found on 2026-09-28 (6 more RBC rows print another word after ACHAT and stay `other`, as at 5.2; no corpus row prints ACHAT DE). A bare ACHAT is not read (plan review): it also opens a French factor's or lessor's pre-authorized-debit wording ('ACHAT DE CREANCES', 'ACHAT DE COMPTES CLIENTS'), and POS (step 5) runs before the potential producers, so an unregistered receivables buyer would become `pos`.

`pos_count` rises on those banks, as the card deep-dive measured. A known payee paid by card keeps D8: it is named, never POS. CARD SPEND stays out of POS: it would swallow the Hillcrest Acceptance candidate (c00047), which C1 routes to its flag instead.

- [ ] **Step 1: Tests.** Append:

```python
# --- B7: POS labels ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    ["MOBILE PURCHASE 0105 FAB MART MIAMI FL", "RETAIL PURCHASE 123456789012 FAB GAS",
     "PIN PURCHASE FAB MART SPRINGFIELD IL 0109", "C/ACHAT 12345678901 FAB EPICERIE", "ACHAT AU DETAIL FAB EPICERIE",
     "ACHAT PAR CARTE 0105 FAB EPICERIE", "DEBIT ACHAT EN LIGNE FAB BOUTIQUE"],
)
def test_bank_card_purchase_labels_are_pos_purchases(description):
    assert _state(description, -10.0)[:2] == ("pos", "point_of_sale_purchase")


def test_a_french_receivables_purchase_is_not_a_pos_purchase():
    # ACHAT alone is also a factor's or lessor's wording: only the evidenced card forms are POS
    assert _state("ACHAT DE CREANCES FAB AFFACTURAGE", -900.0)[0] != "pos"


def test_a_known_payee_paid_by_card_keeps_its_group(fake_payees):
    assert _state("MOBILE PURCHASE 0105 FABRICATED LENDER", -100.0)[0] == "confirmed_lender"
```

- [ ] **Step 2: Run.** Expected: the label parametrization FAILS; the ACHAT DE CREANCES control and the known-payee test pass before and after (they pin what the new patterns must not do).

- [ ] **Step 3: Patterns.** Append to `_POS_PATTERNS`:

```python
    # 5.3 (2026-09-27): bank card-purchase labels of the same kind (BofA MOBILE PURCHASE, CIBC RETAIL PURCHASE,
    # Regions PIN PURCHASE) and the French card-purchase forms the corpus prints (C/ACHAT, CIBC ACHAT AU DETAIL,
    # RBC ACHAT INTERAC, BMO ACHAT PAR CARTE and ACHAT EN LIGNE). A bare ACHAT is never read: 'ACHAT DE CREANCES'
    # is a factor's wording.
    re.compile(r"\b(?:RETAIL|MOBILE|PIN) PURCHASE\b"),
    re.compile(r"\bC ACHAT\b|\bACHAT (?:AU DETAIL|INTERAC|PAR CARTE|EN LIGNE)\b"),
```

- [ ] **Step 4: Run** the file and SEL-CLASSIFIER. If a real-statement `pos_count` pin moves, stop and report it (the Part B prototype moved none).

- [ ] **Step 5: Commit** `"pos: bank card-purchase labels MOBILE, RETAIL and PIN PURCHASE, and French ACHAT"`.

---

### Task B8: A loan from the business's own shareholder, owner or director (structural, medium)

**Files:** Modify `analysis/transaction_classifier.py`: a constant after `_PAYMENT_MARKER_PATTERNS`, and one rule in `classify_transaction` directly after the potential-registry block (`:1736-1749`), before the D10 servicer rule (`:1751`). Append to `tests/test_rule_extensions_53.py`.

**Needs:** none.

**Why:** 'SHAREHOLDER LOAN REPAYMENT' and 'DUE TO OWNER' pay the business's own people and name no lender. Today every row of them is a single-row potential lender (explicit repayment or direct-debit loan). The row stays `other` (`strong_non_lender_exclusion`, `related_party_loan`), debits only, and only when it names no organisation. The credit side already reads SHAREHOLDER LOAN as non-revenue. MEMBER and PARTNER are left out, because a funder can be named '… Partners'.

- [ ] **Step 1: Tests.** Append:

```python
# --- B8: related-party loans -----------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description", ["SHAREHOLDER LOAN REPAYMENT 1234567", "ACH DEBIT OWNER LOAN REPAYMENT", "DUE TO SHAREHOLDER 1234"]
)
def test_a_loan_from_the_businesss_own_people_names_no_lender(description):
    assert _state(description, -1000.0)[:2] == ("other", "related_party_loan")


def test_a_named_payee_with_owner_loan_words_keeps_the_potential_rules():
    assert _state("FAB CAPITAL OWNER LOAN PMT", -1000.0)[0] == "potential_lender"
```

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Constant and rule.**

```python
#: 5.3 (2026-09-27): a loan from the business's own shareholder, owner or director, repaid to them: no lender is
#: named. The loan producers never take it (debits only, and only when the row names no organisation). MEMBER and
#: PARTNER are left out: a funder can be named '... Partners'.
_RELATED_PARTY_LOAN_PATTERNS = (
    re.compile(r"\b(?:SHAREHOLDERS?|OWNERS?|DIRECTORS?) LOANS?\b"),
    re.compile(r"\bDUE TO (?:SHAREHOLDERS?|OWNERS?)\b"),
)
```

In `classify_transaction`, directly before `if amount < 0 and _matches_any(text, _SERVICER_COLLECTOR_PATTERNS):`:

```python
    if (
        amount < 0
        and _matches_any(text, _RELATED_PARTY_LOAN_PATTERNS)
        and _canonical_unknown_entity(text) in (None, UNIDENTIFIED_LENDER_OBLIGATION)
    ):
        return _build_record(
            **common,
            classification="other",
            match_method="strong_non_lender_exclusion",
            matched_rule="related_party_loan",
            confidence_score=0.90,
            reason=(
                "The descriptor names a loan from the business's own shareholder, owner or director; it names "
                "no lender."
            ),
        )
```

- [ ] **Step 4: Run.** **Step 5: Commit** `"potential tier: a shareholder, owner or director loan names no lender"`.

---

## Part C — Registry, matcher, naming and the tab

Part C was prototyped on a scratch copy of the tree with Parts 0, A and B applied (`.../work/plan53/protorepo`, the apply scripts `.../work/plan53/proto/apply_c_*.py`). Every code block below is the prototype's code, and every test passed there (2026-09-27, and again after the plan review on 2026-09-28).

### Task C1: Review entities of flag groups take their flag, marked unconfirmed (other_flag_group)

**Files:**
- Modify `tools/lender_ledger.py`: `ROUTED_REVIEW_GROUPS` and `review_flag_entities` directly before the `# --- today's registry (spec section 9)` rule (`:358`).
- Modify `tools/build_lender_registry.py`: `render_block` (`:41-62`), the admission text (`:146-148`) and `main`'s write (`:275`).
- Modify `docs/lender-registry-ledger.json`: Table Rock and FleetLogic, and the Westlake split.
- Re-render `analysis/classification_registry.py` and `docs/lender-registry-evidence.md`.
- Modify `analysis/transaction_classifier.py`: the registry import (`:9-20`) and step 11 (`:1736-1749`).
- Create `tests/test_unconfirmed_flag_payees.py`. Modify `tests/test_lender_ledger.py`, `tests/test_build_lender_registry.py` and `tests/test_lender_registry_drift.py` (pin-ledger row 12).

**Needs:** none. Do the steps in order: the registry must render `REVIEW_FLAG_ENTITIES` before the classifier imports it.

**Why:** 260 rows / 151 occurrences, 17 keys. A ledger entity under review renders into `POTENTIAL_LENDER_ALIASES` whatever its group, so unconfirmed car, mortgage, personal-loan and lease payees sit on the Potential Lenders tab. The owner ruled (2026-09-27) that they go to their flag, marked unconfirmed, with the credit side unchanged. Both verifiers' REQUIRED changes are applied:
- **Credits unchanged.** The routed entities stay in `POTENTIAL_LENDER_ALIASES`, so `_classify_credit_revenue` (`:812`) and `_descriptor_proceeds` (`:1231`) keep today's exclusion (`non_revenue` / `potential_lender_registry_credit_exclusion`). Only the debit branch at step 11 reads the derived map. This is the evidence verifier's option (a), and it is also one longest-match lookup (the lender-risk verifier's precedence recommendation): the potential alias that wins decides, and its entity's group decides the state.
- **Narrowed routing.** An entity whose `business_type` starts `unknown` (WOW FACTOR RLS, DW Rentals) is never routed, and Table Rock (which also makes business and hard-money loans) moves to the `potential_lender` group.
- **FleetLogic** also moves to `potential_lender`: a full-service truck lease is a counted reading under the PACCAR/Daimler convention, until the owner rules.
- **Westlake split.** `ORIG CO NAME WESTLAKE ORIG` (a trucking business's CCD entry, c00191) becomes its own review entity in `confirmed_lender` (`equipment_finance`) and stays potential; `WESTLAKE PAYMENT` keeps the vehicle flag.
- The review entities of `confirmed_lender`, `potential_lender`, `alternative_position` and `factoring` keep the potential tier (each has a counted reading, for example Primary Capital's fixed instalments).

`LedgerEntity.table` and `.place` do not change, so no move line changes and no `Move:` sentence is needed. With this task's ledger edits, the routed set is 18 entities; some are pre-empted on debits by step 8 or the check rule, as their ledger notes already say (MORTGAGE words, CAF DIRECT CHECK).

- [ ] **Step 1: Ledger and builder tests.** Append to `tests/test_lender_ledger.py`:

```python


# --- 5.3 (owner ruling 2026-09-27): review entities routed to their flag ------------------------------------------


def test_review_entities_of_the_routed_flag_groups_are_the_review_flag_entities():
    entities = _entities((6, "status", "review"), (7, "status", "review"), (8, "status", "review"),
                         (8, "business_type", "unknown"), (9, "status", "review"), (11, "status", "review"))
    # Westfen's business type is unknown; Loxley is factoring and Heldco a lender: all three keep the potential tier.
    assert lender_ledger.review_flag_entities(entities) == {
        "Kelder Loans": "personal_loan", "Penwick Mortgage": "mortgage", "Rivett Motor Credit": "vehicle_financing",
    }


def test_the_routing_keeps_every_routed_alias_in_the_potential_table():
    entities = _entities((6, "status", "review"))
    tables = lender_ledger.render_tables(entities)
    assert tables["POTENTIAL_LENDER_ALIASES"]["Rivett Motor Credit"] == ("RIVETT MOTOR CREDIT",)
    assert "Rivett Motor Credit" not in tables["VEHICLE_FINANCE_ALIASES"]
```

Append to `tests/test_build_lender_registry.py`:

```python


def test_the_block_renders_the_review_flag_entities_when_given():
    entities = _entities((6, "status", "review"))
    block = builder.render_block(builder.render_tables(entities), lender_ledger.review_flag_entities(entities))
    assert max(len(line) for line in block.split("\n")) <= 110
    namespace: dict = {}
    exec(compile(block, "block", "exec"), namespace)
    assert [name for name in namespace if name.isupper()] == [*TABLE_NAMES, "REVIEW_FLAG_ENTITIES"]
    assert namespace["REVIEW_FLAG_ENTITIES"] == {"Rivett Motor Credit": "vehicle_financing"}
    assert "REVIEW_FLAG_ENTITIES: dict[str, str] = {}\n" in builder.render_block(builder.render_tables([]), {})
```

- [ ] **Step 2: Run** `tests/test_lender_ledger.py tests/test_build_lender_registry.py`. Expected: FAIL (`AttributeError: module 'tools.lender_ledger' has no attribute 'review_flag_entities'`).

- [ ] **Step 3: The ledger tool.** In `tools/lender_ledger.py`, directly before `# --- today's registry (spec section 9) ---…`, insert:

```python
#: 5.3 (owner ruling 2026-09-27): the flag groups whose review entities take their flag on debits, marked
#: unconfirmed (REVIEW_FLAG_ENTITIES). A review entity of the lender, potential, alternative-position or factoring
#: group keeps the potential tier: each has a plausible counted reading.
ROUTED_REVIEW_GROUPS = ("vehicle_financing", "mortgage", "lease_or_rental", "personal_loan")


def review_flag_entities(entities: list[LedgerEntity]) -> dict[str, str]:
    """5.3 (owner ruling 2026-09-27): entity -> group of each review entity of a routed flag group whose business
    type is known, in name order. The classifier sends such an entity's debits to its flag, marked unconfirmed; its
    aliases stay in POTENTIAL_LENDER_ALIASES, so its credits keep the potential tier's exclusion. A business type
    starting 'unknown' (a payee read from a payment code alone) is never routed."""
    routed = [
        entity for entity in entities
        if entity.status == "review" and entity.group in ROUTED_REVIEW_GROUPS
        and not entity.business_type.startswith("unknown")
    ]
    return {entity.entity: entity.group for entity in sorted(routed, key=lambda e: (e.entity.casefold(), e.entity))}
```

- [ ] **Step 4: The builder.** In `tools/build_lender_registry.py`:
  - `render_block` takes the map and renders it last, only when it is given, so the existing block tests keep their table list:

```python
def render_block(tables: dict[str, dict[str, tuple[str, ...]]], review_flags: dict[str, str] | None = None) -> str:
    """The GENERATED block: one typed dict literal per C2 table, in TABLES order, then (5.3) REVIEW_FLAG_ENTITIES
    when `review_flags` is given, with "\\n" line endings."""
```

   and, directly before `    lines.append(END_MARKER)`:

```python
    if review_flags is not None:
        lines.append("#: 5.3 (owner ruling 2026-09-27): review entities whose debits take their flag, unconfirmed.")
        if not review_flags:
            lines += ["REVIEW_FLAG_ENTITIES: dict[str, str] = {}", ""]
        else:
            lines.append("REVIEW_FLAG_ENTITIES: dict[str, str] = {")
            for name, group in review_flags.items():
                line = f"    {json.dumps(name)}: {json.dumps(group)},"
                lines += [line] if len(line) <= 110 else [f"    {json.dumps(name)}:", f"        {json.dumps(group)},"]
            lines += ["}", ""]
```

  - In `render_evidence`, after the admission bullet that ends `"is under review.",`, add the bullet:

```python
        "- Since classification 5.3 (owner ruling 2026-09-27), the debits of a review entity of the vehicle, "
        "mortgage, lease or personal-loan group take that flag group, marked unconfirmed "
        "(`REVIEW_FLAG_ENTITIES`), unless its business type is unknown. Its credits keep the potential tier's "
        "exclusion.",
```

  - In `main`, replace `    args.registry.write_bytes(replace_block(source, render_block(tables)).encode("utf-8"))` with:

```python
    block = render_block(tables, lender_ledger.review_flag_entities(entities))
    args.registry.write_bytes(replace_block(source, block).encode("utf-8"))
```

  - Pin-ledger row 12: in `tests/test_lender_registry_drift.py:23` the expected block becomes `builder.render_block(builder.render_tables(entities), lender_ledger.review_flag_entities(entities))`.

- [ ] **Step 5: The ledger edits.** Edit `docs/lender-registry-ledger.json` with a scratch Python script under `C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/` that loads it, changes the records below and writes it back exactly as it is stored: `json.dumps(data, indent=1, ensure_ascii=False) + "\n"` (check first that re-dumping the unchanged file reproduces it byte for byte). Never hand-edit the JSON.
  - `Table Rock Investments LLC`: `group` → `"potential_lender"`; notes gain ` Kept in the potential tier by the 5.3 routing (2026-09-27): the company also makes business and hard-money loans, a counted reading, so its debits are not sent to the personal-loan flag.`
  - `FleetLogic (probably Fleet Logic, LLC dba Velocity Truck Rental and Leasing)`: `group` → `"potential_lender"`; notes gain ` Kept in the potential tier by the 5.3 routing (2026-09-27): a full-service truck lease is a counted equipment-financing reading under the PACCAR and Daimler convention, until the owner rules.`
  - `WESTLAKE (probably Westlake Financial Services)`: `aliases` → `["WESTLAKE PAYMENT"]`; notes gain ` The Chase CCD form ORIG CO NAME WESTLAKE ORIG was split into its own review entity on 2026-09-27 (classification 5.3), so only the card and consumer form takes the vehicle flag.`
  - Directly after it, a new record: a deep copy of the Westlake record (its evidence, verdicts and where_looked) with `entity` `"WESTLAKE (Chase CCD form; possibly Westlake commercial vehicle financing)"`, `group` `"confirmed_lender"`, `business_type` `"equipment_finance"`, `aliases` `["ORIG CO NAME WESTLAKE ORIG"]`, `status` `"review"` and notes `Split on 2026-09-27 (classification 5.3) from the WESTLAKE review entity: a business-to-business (CCD) entry from a trucking business may be Westlake's commercial-vehicle financing, which the ledger's truck convention (Daimler, PACCAR) counts, so this form stays in the potential tier until a source confirms it. Bare WESTLAKE is not used.`

  Then run `cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe -m tools.build_lender_registry --check`. Expected: `ledger ok`, 0 problems, and the `move:` lines identical to those before the edit (save both outputs under the scratch folder and `diff` them). Then run it with `--write`. The GENERATED block now ends with `REVIEW_FLAG_ENTITIES` (18 entities at 0935061's ledger plus these edits).

- [ ] **Step 6: The classifier test.** Create `tests/test_unconfirmed_flag_payees.py`:

```python
"""5.3 (owner ruling 2026-09-27): a review entity of a flag group takes its flag on debits, marked unconfirmed, and
keeps the potential tier's credit exclusion. Fabricated descriptors; the payee names are the registry's business
names, or fabricated ones through a patched registry."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.classification_registry import POTENTIAL_LENDER_ALIASES, REVIEW_FLAG_ENTITIES
from analysis.detect import find_flagged_positions
from analysis.flag_groups import FLAG_GROUP_BY_STATE
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import fake_payees, txn  # noqa: F401  (fixture)

#: Fabricated review entities, one per routed group, and one whose business type the ledger does not know.
FABRICATED_REVIEW = {
    "FABRIKAM AUTO CR (probable)": ("FABRIKAM AUTO CR",),
    "FABRIKAM HOME SERVICER (unconfirmed)": ("FABRIKAM HOME SVCR",),
    "FABRIKAM TOOLHIRE (probable)": ("FABRIKAM TOOLHIRE",),
    "FABRIKAM CONSUMER LOANS (probable)": ("FABRIKAM CONS LN",),
    "FABRIKAM UNKNOWN PAD (unidentified)": ("FABRIKAM UNK PAD",),
}
FABRICATED_ROUTES = {
    "FABRIKAM AUTO CR (probable)": "vehicle_financing",
    "FABRIKAM HOME SERVICER (unconfirmed)": "mortgage",
    "FABRIKAM TOOLHIRE (probable)": "lease_or_rental",
    "FABRIKAM CONSUMER LOANS (probable)": "personal_loan",
}


@pytest.fixture
def review_payees(monkeypatch):
    monkeypatch.setattr(transaction_classifier, "POTENTIAL_LENDER_ALIASES", FABRICATED_REVIEW)
    monkeypatch.setattr(transaction_classifier, "REVIEW_FLAG_ENTITIES", FABRICATED_ROUTES)


@pytest.mark.parametrize(("entity", "state"), sorted(FABRICATED_ROUTES.items()))
def test_a_review_payee_of_a_flag_group_takes_its_flag_marked_unconfirmed(review_payees, entity, state):
    alias = FABRICATED_REVIEW[entity][0]
    record = classify_transaction(f"ACH DEBIT {alias} 0001", -400.0)
    assert (record.classification, record.canonical_entity, record.matched_alias) == (state, entity, alias)
    assert (record.match_method, record.matched_rule) == ("unconfirmed_flag_payee_alias", f"{state}_review_registry")
    assert record.review_required and record.confidence_score == 0.82
    assert record.flagged_group == FLAG_GROUP_BY_STATE[state].key and record.contributes_to_flagged_totals
    assert not record.contributes_to_potential_lender_totals and not record.contributes_to_lender_totals


@pytest.mark.parametrize("entity", sorted(FABRICATED_REVIEW))
def test_a_review_payees_credit_keeps_the_potential_tiers_exclusion(review_payees, entity):
    record = classify_transaction(f"{FABRICATED_REVIEW[entity][0]} DEPOSIT 0001", 900.0)
    assert (record.revenue_classification, record.revenue_match_method) == (
        "non_revenue", "potential_lender_registry_credit_exclusion")
    assert record.flagged_group is None and not record.contributes_to_lender_credit_exclusion


def test_a_review_payee_the_ledger_does_not_route_stays_a_potential_lender(review_payees):
    record = classify_transaction("ACH DEBIT FABRIKAM UNK PAD 0001", -400.0)
    assert (record.classification, record.match_method) == ("potential_lender", "candidate_lender_alias")


def test_every_routed_entity_is_a_potential_table_entity():
    assert REVIEW_FLAG_ENTITIES and set(REVIEW_FLAG_ENTITIES) <= set(POTENTIAL_LENDER_ALIASES)
    assert set(REVIEW_FLAG_ENTITIES.values()) <= {
        "vehicle_financing", "mortgage", "lease_or_rental", "personal_loan", "debt_relief"}


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("Misc Payment National Money", "personal_loan"),
        ("iA Auto CAB 0001", "vehicle_financing"),
        ("Hillcrest Acceptance Card spend", "vehicle_financing"),
        ("UAS DES:EPAYMENT ID:0001 INDN:FAB HOLDER CO ID:0002 PPD", "personal_loan"),
        ("WESTLAKE PAYMENT, LOS ANGELES, CA", "vehicle_financing"),
        # Kept in the potential tier on purpose (the verifiers' changes): a counted reading exists.
        ("Orig CO Name:Westlake Orig ID:0001 Desc Date: CO Entry Descr:Payment Sec:CCD", "potential_lender"),
        ("TABLE ROCK INVST DES:PAYMENT ID:0001 PPD", "potential_lender"),
        ("Fleetlogic Cons Coll 0001", "potential_lender"),
        # A business type read from a payment code alone is never routed.
        ("Pre-Authorized Payment, WOW FACTOR RLS/LOY", "potential_lender"),
    ],
)
def test_the_registrys_review_payees_in_their_printed_forms(description, state):
    assert classify_transaction(description, -300.0).classification == state
```

- [ ] **Step 7: Run it.** Expected: FAIL: the routed rows are still `potential_lender` (Step 5 rendered the map, so the import works).

- [ ] **Step 8: The classifier.** Add `REVIEW_FLAG_ENTITIES,` to the `from .classification_registry import (` block after `PREMIUM_FINANCE_ALIASES,`. At step 11, replace

```python
    potential_match = registry_match(text, POTENTIAL_LENDER_ALIASES)
    if potential_match is not None and amount < 0:
        lender, alias = potential_match
        return _build_record(
```

with

```python
    potential_match = registry_match(text, POTENTIAL_LENDER_ALIASES)
    if potential_match is not None and amount < 0:
        lender, alias = potential_match
        # 5.3 (owner ruling 2026-09-27): a review entity of a flag group takes its flag, marked unconfirmed. Its
        # aliases stay in POTENTIAL_LENDER_ALIASES, so its credits keep the potential tier's exclusion.
        routed = REVIEW_FLAG_ENTITIES.get(lender)
        if routed is not None:
            return _build_record(
                **common,
                classification=routed,
                canonical_entity=lender,
                match_method="unconfirmed_flag_payee_alias",
                matched_alias=alias,
                matched_rule=f"{routed}_review_registry",
                confidence_score=0.82,
                reason=(
                    f"Matched maintained candidate alias '{alias}' of an unconfirmed {_state_words(routed)} payee: "
                    "it is flagged, marked unconfirmed, and never enters lender math."
                ),
                review_required=True,
            )
        return _build_record(
```

- [ ] **Step 9: Run** the new file, SEL-REGISTRY and SEL-CLASSIFIER. Expected: PASS, with pin-ledger row 12 re-pinned. `tests/test_lender_registry_content.py::test_review_tier_payees_are_potential_lender_aliases_and_no_known_payee` (Clover Equipment) stays green: the table does not change.

- [ ] **Step 10: Commit** (`git add tools/lender_ledger.py tools/build_lender_registry.py docs/lender-registry-ledger.json docs/lender-registry-evidence.md analysis/classification_registry.py analysis/transaction_classifier.py tests/test_unconfirmed_flag_payees.py tests/test_lender_ledger.py tests/test_build_lender_registry.py tests/test_lender_registry_drift.py`) `"flag groups: unconfirmed payees of a flag group take their flag on debits; credits keep the potential exclusion"`.

---

### Task C2: The "unconfirmed" marker on flagged positions

**Files:**
- Modify `analysis/detect.py`: `FlaggedPositionMatch` (`:57-76`) and `find_flagged_positions` (`:227`).
- Modify `analysis/serialization.py`: `_flagged_dict` (`:90-105`).
- Modify `webapp/app.py`: `_flagged_position_rows` (`:420`), `_add_flagged_rows` (`:587-615`) and `_published_flagged_positions` (`:621-660`).
- Modify `webapp/static/app.js`: `flaggedPositionRowsHtml` (`:1786-1826`).
- Modify `tests/flagged_payloads.py` (`with_flagged_rows`, `:112-128`) so the fabricated payloads follow the contract.
- Modify the pins: rows 13, 18, 19 and 20 of the pin ledger.
- Append to `tests/test_unconfirmed_flag_payees.py`, `tests/test_webapp_flagged_positions.py` and `tests/test_webapp_flagged_dashboard.py`.

**Needs:** C1.

**Why:** Both verifiers REQUIRED it: a routed payee must say, on the flag tab and in the exports, that its identity is unconfirmed. The position carries `review_required` (true when any counted row of the payee requires review, which today only a routed row does), appended last to every key list the contract publishes (C5 positions, C6 package items, the CSV and XLSX sections). The keep-visible-when-unticked option is not taken: it contradicts the owner's D7 ruling (open question 1).

- [ ] **Step 1: Tests.** Append to `tests/test_unconfirmed_flag_payees.py`:

```python


def test_a_flagged_position_of_a_routed_payee_is_marked_unconfirmed(review_payees, fake_payees):
    statement = Statement(bank="Fabricated Bank", transactions=[
        txn("2054-01-05", "ACH DEBIT FABRIKAM AUTO CR 0001", -400.0),
        txn("2054-01-12", "ACH DEBIT FABRIKAM AUTO CR 0001", -400.0),
        txn("2054-01-06", "ACH DEBIT FABRICATED CARMAKER FINANCIAL 0001", -500.0),
    ])
    positions = find_flagged_positions(statement, classify_statement_transactions(statement))
    assert [(position.payee, position.review_required) for position in positions] == [
        ("FABRIKAM AUTO CR (probable)", True), ("Fabricated Carmaker Financial", False)]
```

Append to `tests/test_webapp_flagged_positions.py`:

```python


# --- 5.3 (owner ruling 2026-09-27): an unconfirmed flagged payee --------------------------------------------------

def test_an_unconfirmed_flagged_payee_is_marked_in_the_package_and_its_export(settings_file):
    from webapp.app import _package_analysis, _package_csv

    row = flagged_row("vehicle_financing", payee="FABRICATED REVIEW AUTO")
    row["classification"]["review_required"] = True
    known = flagged_row("vehicle_financing", payee="FABRICATED KNOWN AUTO", date="2054-01-06")
    package = _package_analysis([_member("a", with_flagged_rows(account_payload(0), [row, known]))])
    items = {item["payee"]: item["review_required"] for item in package["flagged_positions"]["vehicle_financing"]}
    assert items == {"FABRICATED REVIEW AUTO": True, "FABRICATED KNOWN AUTO": False}
    cells = _csv_cells(_package_csv(package))
    assert sorted(value for (section, field), value in cells.items()
                  if section.startswith("flagged_vehicle_financing_") and field == "review_required") == ["False", "True"]
```

Append to `tests/test_webapp_flagged_dashboard.py`:

```python


# ---------------------------------------------------------------- 5.3: an unconfirmed flagged payee says so

@needs_node
def test_an_unconfirmed_flagged_payee_says_so_under_its_name():
    entries = [
        {"group": "vehicle_financing", "payee": "FABRICATED REVIEW AUTO", "count": 1, "total_debited": 400.0,
         "count_credited": 0, "total_credited": 0.0, "cadence": "single", "review_required": True},
        {"group": "vehicle_financing", "payee": "FABRICATED KNOWN AUTO", "count": 1, "total_debited": 300.0,
         "count_credited": 0, "total_credited": 0.0, "cadence": "single", "review_required": False},
    ]
    result = run_dashboard(f"""
console.log(JSON.stringify({{html: flaggedPositionRowsHtml({json.dumps(entries)}, "USD")}}));
""")
    [unconfirmed, known] = result["html"].split("</tr>")[:2]
    assert "Unconfirmed: identity under review" in unconfirmed
    assert "Unconfirmed" not in known
```

- [ ] **Step 2: Run** the three files. Expected: FAIL (`AttributeError: 'FlaggedPositionMatch' object has no attribute 'review_required'`; `KeyError: 'review_required'`; no "Unconfirmed" line).

- [ ] **Step 3: Detection and the payload.**
  - `FlaggedPositionMatch` gains a last field, after `source_locations`:

```python
    # 5.3 (owner ruling 2026-09-27): the payee is a review entity of the ledger routed to its flag, unconfirmed.
    review_required: bool = False
```

  - In `find_flagged_positions`, directly before `match.source_locations.append(...)`: `match.review_required = match.review_required or record.review_required`.
  - `_flagged_dict` gains a last key: `"review_required": match.review_required,`.

- [ ] **Step 4: The package and the exports.** In `webapp/app.py`:
  - `_add_flagged_rows`: the roll-up item gains `"review_required": False` (after `"dates": []`), and, directly after the `rollup.setdefault(...)` call, `item["review_required"] = item["review_required"] or classification.get("review_required") is True`.
  - `_published_flagged_positions`: each item gains a last key `"review_required": item["review_required"],` (after `"last_date"`). Its docstring's key list gains `review_required`.
  - `_flagged_position_rows`: the field tuple becomes `("payee", "count", "total_debited", "count_credited", "total_credited", "cadence", "review_required")`.

- [ ] **Step 5: The dashboard.** In `flaggedPositionRowsHtml`, directly after `const statements = …;`, add:

```js
    // 5.3 (owner ruling 2026-09-27): a payee the ledger has not confirmed says so under its name.
    const unconfirmed = entry.review_required === true
      ? '<div class="table-cell-detail">Unconfirmed: identity under review</div>'
      : "";
```

  and in the payee cell, append `${unconfirmed}` after the closing `</button>` (before `</td>`).

- [ ] **Step 6: The fixture and the pins.**
  - `tests/flagged_payloads.py` `with_flagged_rows`: each entry gains, after `"source_locations"`, `"review_required": any(row["classification"].get("review_required") is True for row in members),`.
  - Row 13: `C5_POSITION_KEYS` (`tests/test_webapp_flagged_positions.py:643-644`) gains `"review_required"`.
  - Row 18: every dict of `EXPECTED_POSITIONS` (`tests/test_flagged_positions_payload.py:65-101`) gains `"review_required": False,` after `"source_locations"`.
  - Row 19: the key list at `tests/test_factoring_credits.py:151-154` gains `"review_required"` last.
  - Row 20: the package item key list at `tests/test_webapp_flagged_positions.py:636-637` gains `"review_required"` last.

- [ ] **Step 7: Run** the three files, SEL-CLASSIFIER and SEL-WEBAPP. Expected: PASS; no other assertion moves.

- [ ] **Step 8: Commit** (`git add analysis/detect.py analysis/serialization.py webapp/app.py webapp/static/app.js tests/flagged_payloads.py tests/test_unconfirmed_flag_payees.py tests/test_webapp_flagged_positions.py tests/test_webapp_flagged_dashboard.py tests/test_flagged_positions_payload.py tests/test_factoring_credits.py`) `"flagged positions: review_required marks an unconfirmed payee on the tab, the payload and the exports"`.

---

### Task C3: Ledger renames (registry naming items)

**Files:** Modify `docs/lender-registry-ledger.json`; re-render `analysis/classification_registry.py` and `docs/lender-registry-evidence.md`.

**Needs:** none (after C1, the `REVIEW_FLAG_ENTITIES` map picks up the UAS rename by itself).

**Why:** These published names come from the ledger's `entity` field, not from D11, and some carry bank codes or claim more than the ledger shows. The naming verifier confirmed each and refuted the triage for two (c00046's CLN is the Payments Canada Commercial Loans code; c00185's name is an honest review label), which keep their names. No alias changes, and none of these entities is in today's registry at the baseline revision, so no move line changes.

| Today's `entity` | New `entity` | Why |
|---|---|---|
| `Meridian RLS payee (probably Meridian OneCap Credit Corp)` | `Meridian (RLS rent/lease PAD; probably Meridian OneCap Credit Corp)` | RLS is the Payments Canada rent/lease code, not the payee |
| `UAS DES EPAYMENT (probably University Accounting Service)` | `UAS (probably University Accounting Service)` | DES is Bank of America's field label |
| `Future Funding LLC` | `FUTURE FUNDING (legal entity not identified)` | the ledger says the legal entity is not identified |
| `NATIONWIDECREDIT` | `Nationwide Credit (debt collector; creditor not printed)` | the run-together originator is not a name |
| `ACCOUNT SERVICIN[G]` | `Unidentified account servicer (ACCOUNT SERVICIN[G])` | optional in the verifier's list; taken, because the tab shows a label, not a name |

- [ ] **Step 1: Test.** Append to `tests/test_lender_registry_content.py`:

```python


@pytest.mark.parametrize(
    ("descriptor", "entity"),
    [
        ("MERIDIAN RLS LOY 0001", "Meridian (RLS rent/lease PAD; probably Meridian OneCap Credit Corp)"),
        ("FUTURE FUNDING DES:PAYMENT ID:0001", "FUTURE FUNDING (legal entity not identified)"),
        ("NATIONWIDECREDIT TELECHK 0001", "Nationwide Credit (debt collector; creditor not printed)"),
        ("ORIG CO NAME ACCOUNT SERVICIN ORIG ID 0001", "Unidentified account servicer (ACCOUNT SERVICIN[G])"),
    ],
)
def test_review_payees_are_published_under_names_that_say_what_the_ledger_knows(descriptor, entity):
    found = registry_match(normalize(descriptor), registry.POTENTIAL_LENDER_ALIASES)
    assert found is not None and found[0] == entity, found
```

- [ ] **Step 2: Run** it. Expected: FAIL (the old names).

- [ ] **Step 3: Rename** the five `entity` values with the scratch-script method of C1 Step 5, then run `--check` (0 problems; the move lines unchanged) and `--write`.

- [ ] **Step 4: Run** SEL-REGISTRY and SEL-CLASSIFIER (no other test names these entities; checked with `grep` on 2026-09-27).

- [ ] **Step 5: Commit** (`git add docs/lender-registry-ledger.json docs/lender-registry-evidence.md analysis/classification_registry.py tests/test_lender_registry_content.py`) `"registry: review payees named for what the ledger knows (Meridian, UAS, Future Funding, Nationwide Credit, account servicer)"`.

---

### Task C4: The known-payee matcher reads digits glued to an alias's last word (GOAT ADVANCE)

**Files:**
- Modify `analysis/payee_matcher.py`: `_TOKEN` (`:22`), `AliasIndex.__init__` (`:44-70`), `AliasIndex.match` (`:72-89`) and `_DEFAULT_INDEX` (`:92`).
- Modify `docs/lender-registry-ledger.json`: the notes of `GOAT ADVANCE LLC` and `Bell Rock Income Fund 1 LLC`; re-render the evidence page.
- Append to `tests/test_payee_matcher.py`.

**Needs:** none.

**Why:** GOAT ADVANCE LLC's debits print `GOAT ADVANCE` with digits glued on (`GOAT ADVANCE1234`), which the token-boundary matcher never reaches: 84 rows are D6 potentials and 9 are plain `other` (c00095). The owner ruled the matcher fix, which makes those 93 rows counted lender rows (lender math). Both registry verifiers' conditions apply:
- **Scope:** the known-payee index only (`match_known_payee`). `registry_match` (the insurance, premium, operating-revenue, bank-name, card-context and potential tables) stays strict, which leaves out the one extra reach the verifier found (a card-context alias followed by a glued phone number).
- **Three letters:** the glued letters must equal the alias's last word, and that word must have at least three letters. The 46 aliases ending in a one- or two-letter cut (KM CAPITAL C, SOUND ADVANCE L, BELL ROCK IN FD) stay strict.

Consequence, recorded for the owner (open question 13): Bell Rock Income Fund's alias ends in FD, so its 57 glued monthly rows stay unreached, and 15 more print another cut no alias reaches. The research file's r6 Bell Rock note assumed the looser rule; the verify round (r7) found it false under the three-letter floor, and both notes below are the research file's r7 wording, committed here in the matcher's own commit (the verifier: never before or without the matcher change). Its corpus scan found no other newly reached alias in the known-payee groups.

- [ ] **Step 1: Tests.** Append to `tests/test_payee_matcher.py`:

```python


# --- 5.3 (owner ruling 2026-09-27): digits glued to the last word of a multi-word alias --------------------------

GLUED = {
    "confirmed_lender": {"Quillon Advance": ("QUILLON ADVANCE",), "Brisk": ("BRISK",)},
    "mortgage": {"Tarnmoor Fund": ("TARNMOOR IN FD",)},
}


@pytest.mark.parametrize(
    ("text", "entity"),
    [
        ("ACH DEBIT QUILLON ADVANCE1234 ACHDEBIT", "Quillon Advance"),
        ("QUILLON ADVANCE1234", "Quillon Advance"),
        ("QUILLON ADVANCE 1234", "Quillon Advance"),
        # a single-word alias stays strict, and so does a last word of fewer than three letters
        ("BRISK1234 PAYMENT", None),
        ("TARNMOOR IN FD1234", None),
        # the digits must be glued to the whole last word, and a longer word is another word
        ("QUILLON ADV1234", None),
        ("QUILLON ADVANCES1234", None),
    ],
)
def test_the_known_payee_index_reads_digits_glued_to_the_last_word_of_a_multi_word_alias(text, entity):
    found = AliasIndex(GLUED, glued_digits=True).match(normalize(text))
    assert (found.entity if found else None) == entity


def test_only_the_known_payee_index_reads_glued_digits():
    assert AliasIndex(GLUED).match("QUILLON ADVANCE1234") is None
    assert registry_match("QUILLON ADVANCE1234", GLUED["confirmed_lender"]) is None


def test_the_live_known_payee_index_reads_goat_advances_glued_debits():
    found = match_known_payee(normalize("GOAT ADVANCE1234 DES:ACHDEBIT ID:0001 INDN:FAB HOLDER CO ID:0002 CCD"))
    assert found is not None and (found.entity, found.state) == ("GOAT ADVANCE LLC", "confirmed_lender")
```

- [ ] **Step 2: Run** `tests/test_payee_matcher.py`. Expected: FAIL (`TypeError: ... unexpected keyword argument 'glued_digits'`).

- [ ] **Step 3: The matcher.**
  - After `_TOKEN = re.compile(r"[A-Z0-9]+")`:

```python
#: 5.3 (owner ruling 2026-09-27): a description token of letters with digits glued on (ADVANCE1234). Its letters
#: may stand for the LAST word of a multi-word alias whose last word is at least three letters, in the
#: known-payee index only.
_GLUED_DIGITS = re.compile(r"([A-Z]{3,})[0-9]+")
```

  - `AliasIndex.__init__` gains the keyword `glued_digits: bool = False` after `run_together`, a table `glued: dict[tuple[str, ...], _Entry] = {}` beside `table`, and, directly after `table.setdefault(tokens, entry)`:

```python
                    if glued_digits and len(tokens) > 1 and tokens[-1].isalpha() and len(tokens[-1]) >= 3:
                        glued.setdefault(tokens, entry)
```

    and `self._glued = glued` after `self._table = table`. Add one sentence to the class docstring: `With glued_digits, the last word of a multi-word alias whose last word has three letters or more also matches that word with digits glued on (5.3).`
  - In `match`, directly after `entry = self._table.get(tuple(tokens))`:

```python
                if entry is None and self._glued and position > start:
                    split = _GLUED_DIGITS.fullmatch(tokens[-1])
                    if split is not None:
                        entry = self._glued.get((*tokens[:-1], split.group(1)))
```

  - `_DEFAULT_INDEX = AliasIndex(PAYEE_GROUP_REGISTRIES, glued_digits=True)`.

- [ ] **Step 4: The ledger notes** (scratch-script method of C1 Step 5):
  - `GOAT ADVANCE LLC` notes become the research file's r7 `replace_notes`: `The ACH debits print GOAT ADVANCE followed directly by digits (entry descriptions ACHDEBIT and RETRY_ACH). Since classification 5.3 (owner ruling 2026-09-27) the known-payee matcher also reads a multi-word alias whose last word, of three letters or more, has digits glued to it, which reaches these debits with this alias and no new one. A spaced ACH debit or credit printing GOAT ADVANCE is still read by the alias as before. Correction 2026-09-27: the only spaced printings in the corpus are Zelle credits from GOAT ADVANCE LLC and a Zelle 'Loan pay off' debit to it, which the transfer rule claims before the known-payee step. No other safe alias covers the rows: bare GOAT also prints on a sneaker marketplace and a barber shop.`
  - `Bell Rock Income Fund 1 LLC` notes gain the research file's r7 `append_notes`: ` Matcher note 2026-09-27: 57 of the fund's monthly rows print one digit glued to FD, the two-letter last word of the cut name BELL ROCK IN FD, and 15 more print a different cut (BELL ROCK INCOME FUN...). The 5.3 glued-digit reading needs a last word of three letters or more, so this alias still reaches none of these rows; the owner decides whether to widen the rule or add the second cut as an alias.`
  - If a later change moves the floor, both notes change with it in the same commit.

  Run `--check` then `--write`.

- [ ] **Step 5: Run** `tests/test_payee_matcher.py` (PASS), SEL-REGISTRY and SEL-CLASSIFIER. `test_match_known_payee_is_the_index_over_payee_group_registries` stays green: its texts print no glued digits.

- [ ] **Step 6: Commit** (`git add analysis/payee_matcher.py docs/lender-registry-ledger.json docs/lender-registry-evidence.md tests/test_payee_matcher.py`) `"matcher: the known-payee index reads digits glued to the last word of a multi-word alias"`.

---

### Task C5: D11 cues by position, the legal-form cut, connectors, PAID and a leading AND

**Files:** Modify `analysis/transaction_classifier.py`: `_ENTITY_NOISE` (`:918-924`), `_ORGANISATION_CUES` (`:929-933`), a constant after `_MAX_ENTITY_TOKENS = 4` (`:949`), `_unknown_payee_tokens` (`:960-985`) and `_unknown_payee_name` (`:988-994`). Create `tests/test_payee_naming_53.py`.

**Needs:** 0.1 (`_LEGAL_FORM_SUFFIXES`), 0.2.

**Why:** The naming verifier confirmed the mechanisms (c00136, c00159, f00008, c00098, c00131, c00157, c00175):
- A cue word that is not the payee's legal form made a name publishable: 'Bank' (a template word alone), 'Corp <name> Consult <city>' (CORP first, c00159), 'Co Fam Supp Reg' (CO is Colorado). C1: a legal form counts only after the first word, and a name made only of cue words is unidentified. C2: CO is no cue; COMPANY stays one. Both can only reduce what is published, so they are D11-safe. The accepted cost: a '<Name> Co' business becomes unidentified.
- N1: the name ends at its first legal form after the first word ('Review Inc Purchase' → 'Review Inc'). N1' (cut at any cue) is refused globally as lossy ('FIRST CAPITAL FUNDING LLC' → 'First Capital'); it is used only on the wire path (C7).
- N2: a trailing OF, AND, THE, DE, DU or DES left by the four-word cap is dropped ('Bokf National Bank Of').
- PAID (Navy Federal's 'Paid To -') and a leading AND are name noise (the structural critic's cosmetic item; the only two of that list shipped).

After this task the card-format veto of A1 no longer reads CO as an organisation cue: a Colorado merchant's 'NAME, CITY, CO' card line is no longer vetoed.

- [ ] **Step 1: Tests.** Create `tests/test_payee_naming_53.py`:

```python
"""5.3 (2026-09-27): the D11 naming fixes: organisation cues by position, the legal-form cut, trailing connectors,
bank template prefixes, Truist's company field, wire beneficiaries and the printed 'NAME, CITY, ST' line.
Fabricated descriptors only, in each bank's printed format."""
from __future__ import annotations

import pytest

from analysis.description_text import normalize_transaction_description as normalize
from analysis.schema import Statement
from analysis.transaction_classifier import (
    UNIDENTIFIED_LENDER_OBLIGATION as UNIDENTIFIED,
    _canonical_unknown_entity,
    _unknown_payee_tokens,
    classify_statement_transactions,
)
from tests.flag_group_fixtures import txn

WEEKLY = ("2054-01-05", "2054-01-12", "2054-01-19", "2054-01-26")


def _name(printed: str) -> str | None:
    return _canonical_unknown_entity(normalize(printed))


# --- C5: cues by position, the legal-form cut, connectors, PAID and a leading AND --------------------------------

@pytest.mark.parametrize(
    ("printed", "name"),
    [
        # a legal form printed first is no cue; a name made only of cue words names no one
        ("ACH DEBIT CORP FABRIKAM CONSULT 0001", UNIDENTIFIED),
        ("BANK DEBIT", UNIDENTIFIED),
        # CO is Colorado's state code, never a cue (COMPANY stays one)
        ("Electronic Withdrawal To CO FAM SUPP REG", UNIDENTIFIED),
        ("ACH DEBIT FABRICATED TRADING CO 0001", UNIDENTIFIED),
        ("ACH DEBIT FABRICATED TRADING COMPANY 0001", "Fabricated Trading Company"),
        # the name ends at its first legal form after the first word
        ("FAB REVIEW INC PURCHASE", "Fab Review Inc"),
        ("ACH DEBIT FABRIKAM WIDGETS LLC INVOICES 0001", "Fabrikam Widgets LLC"),
        # a connector left by the four-word cap is dropped
        ("ACH DEBIT FABRIKAM NATIONAL A BANK OF OKLAHOMA 0001", "Fabrikam National Bank"),
        ("ACH DEBIT AND FAB FUNDING LLC", "Fab Funding LLC"),
        # multi-cue names keep every word up to the legal form
        ("ACH DEBIT FABRIKAM CAPITAL FUNDING LLC 0001", "Fabrikam Capital Funding LLC"),
    ],
)
def test_the_cue_rules_and_the_legal_form_cut(printed, name):
    assert _name(printed) == name


def test_paid_is_a_channel_word_not_part_of_the_payee():
    assert _unknown_payee_tokens(normalize("PAID TO - FAB CAPITAL GROUP 0001")) == ("FAB", "CAPITAL", "GROUP")
```

- [ ] **Step 2: Run** it. Expected: FAIL (for example 'Corp Fabrikam Consult' is published).

- [ ] **Step 3: The constants.**
  - `_ENTITY_NOISE` gains, as its last line: `    # 5.3: the paid-to label a bank prints before the payee (Navy Federal "Paid To -").` and `    "PAID",`.
  - `_ORGANISATION_CUES` loses `"CO"`, and its comment gains the line `#: 5.3 (2026-09-27): CO is no cue (it is also Colorado's state code: 'NAME, CITY, CO'); COMPANY stays one.`
  - After `_MAX_ENTITY_TOKENS = 4`:

```python
#: 5.3: connectors that never end a name (a name cut by the four-word cap: 'BOKF NATIONAL BANK OF').
_TRAILING_CONNECTORS = frozenset({"OF", "AND", "THE", "DE", "DU", "DES"})
```

- [ ] **Step 4: The payee words.** In `_unknown_payee_tokens`, replace the loop from `for token in text.split():` to `return tuple(tokens)` with:

```python
    for token in text.split():
        if token in _ENTITY_NOISE or len(token) == 1:
            continue
        if _is_reference_token(token):
            if tokens:
                break
            continue
        if not tokens and (token in _GENERIC_ENTITY_WORDS or token == "AND"):
            continue
        tokens.append(token)
        if len(tokens) > 1 and token in _LEGAL_FORM_SUFFIXES:
            break
        if len(tokens) == _MAX_ENTITY_TOKENS:
            break
    while tokens and tokens[-1] in _TRAILING_CONNECTORS:
        tokens.pop()
    return tuple(tokens)
```

  and add to its docstring: `5.3 (2026-09-27): a name ends at its first legal-form word after the first word; a leading AND and a trailing connector are dropped.`

- [ ] **Step 5: The published name.** Replace `_unknown_payee_name` with:

```python
def _names_an_organisation(tokens: Sequence[str]) -> bool:
    """D11 and 5.3 (2026-09-27): a cue names an organisation, except a legal-form word printed first (CORP of
    'CORP FABRIKAM ...'); a name made only of cue words ('BANK', 'CORP') names none."""
    if all(token in _ORGANISATION_CUES for token in tokens):
        return False
    return any(
        token in _ORGANISATION_CUES and (position > 0 or token not in _LEGAL_FORM_SUFFIXES)
        for position, token in enumerate(tokens)
    )


def _unknown_payee_name(tokens: Sequence[str]) -> str | None:
    """D11: the published name, the unidentified label, or None when no payee is named."""
    if not tokens:
        return None
    if not _names_an_organisation(tokens):
        return UNIDENTIFIED_LENDER_OBLIGATION
    return " ".join(token if token in _ENTITY_ACRONYMS else token.title() for token in tokens)
```

- [ ] **Step 6: Run** the file (PASS), SEL-CLASSIFIER and `tests/test_d6_skips.py`. The pattern prototype moved no existing test with these rules (2026-09-27). A6's vendor rule reads the originator segment of a bounded row too, so 'FABRIKAM MFG INC INVOICES 1234567' stays skipped after the cut (see A6).

- [ ] **Step 7: Commit** (`git add analysis/transaction_classifier.py tests/test_payee_naming_53.py`) `"d11: cues by position, CO is no cue, names end at their legal form, trailing connectors dropped"`.

---

### Task C6: Bank template prefixes, and Truist's company field

**Files:** Modify `analysis/transaction_classifier.py`: `_ACH_FIELD_SEGMENT` (`:944-947`), constants after `_TRAILING_CONNECTORS` (C5), `_unknown_payee_tokens`'s first statement, `_canonical_unknown_entity` (`:997-998`) and the D6 promotion loop (`:2240-2241`). Append to `tests/test_payee_naming_53.py`.

**Needs:** C5.

**Why:**
- **Templates** (confirmed, c00006, c00022, c00126, c00138, c00041, c00189): the bank's template words became the D6 payee key, so different recipients paid through one template merged and promoted together, and templates were published ('Hip Credit Sent Pro'). The start-anchored prefix list is removed before the payee words start: PMNT/PAYMENT SENT, CORPORATE ACH, DOMESTIC ASSIST WIRE, HIP CREDIT SENT (TO), RETAIL PURCHASE, and TD's DBCRD PUR AP (AUT) with its VISA DDA PUR AP repeat. INSTR joins the ACH field segments. This is a grouping fix: a single recipient repeating weekly still promotes, as the verifier showed (the rails of A2 and the POS labels of B7 are what remove those rows).
- **Truist** (c00053, c00071, c00166, f00011): all 1,811 'ACH CORP DEBIT' rows were published through CORP, and 64 potential rows carried the holder's business name. The verifier refuted the report's fix (a strip alone publishes originator + holder, as in a fabricated 'Merit Fabco Widgets LLC') and required the stricter gate applied here: after the prefix is stripped, a Truist name is published only when a whole legal-form word lies inside the first 16 characters of the payee words, Truist's unpadded company field. CUSTOMER ID joins the segments. The results: 'Square Inc' and 'Kapitus LLC' stay named; 'PayPal Capital G…', AMERICAN EXPRESS, 'Merit Business' and 'Fleet Financial' become unidentified.

- [ ] **Step 1: Tests.** Append to `tests/test_payee_naming_53.py`:

```python


# --- C6: bank template prefixes and Truist's company field ----------------------------------------------------------

@pytest.mark.parametrize(
    ("printed", "payee"),
    [
        ("PMNT SENT 0105 FAB RECIPIENT ONE", ("FAB", "RECIPIENT", "ONE")),
        ("Payment Sent 01/05 Fab Funding LLC Card 1234", ("FAB", "FUNDING", "LLC")),
        ("Corporate ACH Payment Fab Capital LLC", ("FAB", "CAPITAL", "LLC")),
        ("HIP Credit SENT to Fab Advance LLC", ("FAB", "ADVANCE", "LLC")),
        ("DOMESTIC ASSIST WIRE FAB HOLDINGS LLC", ("FAB", "HOLDINGS", "LLC")),
        ("DBCRD PUR AP, AUT 010554 VISA DDA PUR AP 123456 FAB MART MIAMI FL", ("FAB", "MART", "MIAMI", "FL")),
    ],
)
def test_a_bank_template_prefix_never_names_the_payee(printed, payee):
    assert _unknown_payee_tokens(normalize(printed)) == payee


def test_two_recipients_of_one_template_are_two_payees():
    # FUNDING keeps both off the p2p rail (A2's veto), so only the payee key decides.
    statement = Statement(bank="Fabricated Bank", transactions=[
        *(txn(day, "PMNT SENT 0105 FAB FUNDING ONE", -300.0) for day in WEEKLY[:2]),
        *(txn(day, "PMNT SENT 0105 FAB FUNDING TWO", -300.0) for day in WEEKLY[2:]),
    ])
    records = classify_statement_transactions(statement)
    assert {record.classification for record in records} == {"other"}


@pytest.mark.parametrize(
    ("printed", "name"),
    [
        ("ACH CORP DEBIT SQ540512 SQUARE INC FAB YOGA STUDIO LL CUSTOMER ID 0001", "Square Inc"),
        ("ACH CORP DEBIT KAPIFAB LLC FAB HOLDER CUSTOMER ID 0001", "Kapifab LLC"),
        # a short originator lets the receiver's words into the 16-character field: no name is published
        ("ACH CORP DEBIT DEBIT FABPAY CAPITAL GROWTH LLC CUSTOMER ID 0001", UNIDENTIFIED),
        ("ACH CORP DEBIT 0012345678 FAB BUSINESS FABCO WIDGETS LLC CUSTOMER ID 0001", UNIDENTIFIED),
        ("ACH CORP DEBIT LOAN PMT FABRIKAM EXPRESS FAB HOLDER CUSTOMER ID 0001", UNIDENTIFIED),
    ],
)
def test_a_truist_name_is_published_only_through_its_company_field(printed, name):
    assert _name(printed) == name
```

- [ ] **Step 2: Run** it. Expected: FAIL (the template words are the payee; the Truist rows publish 'Corp …').

- [ ] **Step 3: The segments and constants.**
  - `_ACH_FIELD_SEGMENT`'s last line becomes `    r"CONF|REF|MEMO|CUST|TYPE|CUSTOMER ID|INSTR)\b"`, with the comment `# 5.3 (2026-09-27): Truist's receiver field label and Huntington's instruction field.` above that line.
  - After `_TRAILING_CONNECTORS`:

```python
#: 5.3 (2026-09-27): bank template words printed before the payee: removed before the payee words start, so two
#: recipients paid through one template are never one payee (D11) and a template is never a name. Read at the start
#: of the normalized row. 'ACH CORP DEBIT' is Truist's; its name then passes _truist_name_is_published.
_PAYEE_TEMPLATE_PREFIX = re.compile(
    r"^(?:(?:PMNT|PAYMENT) SENT|CORPORATE ACH|DOMESTIC ASSIST WIRE|HIP CREDIT SENT(?: TO)?|RETAIL PURCHASE"
    r"|DBCRD PUR AP(?: AUT)?(?: [0-9]+)?(?: VISA DDA PUR(?: AP)?)?|ACH CORP (?:DEBIT|CREDIT))\b"
)
_TRUIST_CORP_PREFIX = re.compile(r"^ACH CORP (?:DEBIT|CREDIT)\b")
#: 5.3: Truist prints no padding, so a short originator lets the receiver's words into the 16-character company
#: field. A Truist name is published only when a whole legal-form word lies inside those 16 characters.
_TRUIST_COMPANY_FIELD = 16
```

- [ ] **Step 4: The payee words and the published name.**
  - `_unknown_payee_tokens`'s first statement `text = _payee_region(text)` becomes `text = _payee_region(_PAYEE_TEMPLATE_PREFIX.sub(" ", text, count=1))`, and its docstring gains `A bank template prefix is removed first.`
  - Replace `_canonical_unknown_entity` with:

```python
def _truist_name_is_published(text: str) -> bool:
    """5.3 (2026-09-27): on a Truist 'ACH CORP DEBIT' row, whether a whole legal-form word lies inside the first 16
    characters of the payee words, the width of the company-name field. True for every other row."""
    if not _TRUIST_CORP_PREFIX.match(text):
        return True
    words: list[str] = []
    for token in _payee_region(_PAYEE_TEMPLATE_PREFIX.sub(" ", text, count=1)).split():
        if not words and (token in _ENTITY_NOISE or len(token) == 1 or _is_reference_token(token)):
            continue
        words.append(token)
    printed = " ".join(words)
    field = printed[:_TRUIST_COMPANY_FIELD].split()
    if len(printed) > _TRUIST_COMPANY_FIELD and printed[_TRUIST_COMPANY_FIELD] != " ":
        field = field[:-1]  # the field's edge cut the last word
    return any(word in _LEGAL_FORM_SUFFIXES for word in field)


def _unknown_entity_for_text(text: str, tokens: Sequence[str]) -> str | None:
    """D11: the published name of the payee words `tokens` read from the normalized row `text` (5.3: a Truist name
    only through its company field)."""
    name = _unknown_payee_name(tokens)
    if name not in (None, UNIDENTIFIED_LENDER_OBLIGATION) and not _truist_name_is_published(text):
        return UNIDENTIFIED_LENDER_OBLIGATION
    return name


def _canonical_unknown_entity(text: str) -> str | None:
    return _unknown_entity_for_text(text, _unknown_payee_tokens(text))
```

  - In the D6 promotion loop, `entity = _unknown_payee_name(payee) or UNIDENTIFIED_LENDER_OBLIGATION` becomes:

```python
        entity = _unknown_entity_for_text(records[indexes[0]].normalized_description, payee) or (
            UNIDENTIFIED_LENDER_OBLIGATION
        )
```

- [ ] **Step 5: Run** the file (PASS), SEL-CLASSIFIER and `tests/test_d6_skips.py`. The Part B field-order forms (B3) are unaffected: they read the row, not the payee words.

- [ ] **Step 6: Commit** (`git add analysis/transaction_classifier.py tests/test_payee_naming_53.py`) `"d11: bank template prefixes are no payee; a Truist name only through its 16-character company field"`.

---

### Task C7: Wires are named by their beneficiary

**Files:** Modify `analysis/transaction_classifier.py`: `_ACH_FIELD_SEGMENT`, a constant after `_TRUIST_COMPANY_FIELD` (C6), a helper before `_unknown_payee_tokens`, and `_unknown_payee_tokens`. Append to `tests/test_payee_naming_53.py`.

**Needs:** C6.

**Why:** Confirmed (c00153, c00190, f00003; c00051/c00184/c00192 are registry matches, whose census key alone was wrong). Wells Fargo 'WT Fed#… /Bnf=<name> Srf#', Bank of America 'WIRE TYPE:WIRE OUT … BNF:<name>' and Chase 'Wire Transfer Via: <bank> A/C: <beneficiary>' gave the keys 'WT FED', 'WIRE' and 'DOMESTIC WIRE VIA <bank>', so beneficiaries of one amount merged and none was named. The payee words are read after BNF (or BNF FFC), else after Chase's A/C, and SRF, RFB and IMAD join the segments. On this path only, a name ends at its first cue after the first word (N1'), so the city and state after a Chase beneficiary never join it; the owner accepts the known loss for multi-cue names on wires ('Fab Advance Group LLC' → 'Fab Advance'). A person beneficiary stays unidentified, CO included (C5).

- [ ] **Step 1: Tests.** Append:

```python


# --- C7: wire beneficiaries ---------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("printed", "name"),
    [
        ("WT Fed#01R23 Fab Bank /Ftr/Bnf=Fab Advance Group LLC Srf# 0001 Trn#0001 Rfb# 0001", "Fab Advance"),
        ("WIRE TYPE:WIRE OUT DATE:540105 TIME:1200 ET TRN:0001 SERVICE REF:0001 BNF:FAB FUNDING LLC ID:0001",
         "Fab Funding"),
        ("Online Domestic Wire Transfer Via: Fab CU/123456789 A/C: Fab Funding Sampletown NY 00001 US Ref: Loan "
         "Imad: 0001 Trn: 0001", "Fab Funding"),
        # a person beneficiary, anywhere, is never published
        ("WT Fed#01R23 Fab Bank /Ftr/Bnf=Pat Example Srf# 0001", UNIDENTIFIED),
        ("Online Domestic Wire Transfer Via: Fab CU/123456789 A/C: Pat Example Denver CO 00002 US Ref: Rent "
         "Imad: 0001 Trn: 0001", UNIDENTIFIED),
    ],
)
def test_a_wire_is_named_by_its_beneficiary(printed, name):
    assert _name(printed) == name


def test_two_beneficiaries_of_one_wire_format_are_two_payees():
    statement = Statement(bank="Wells Fargo", transactions=[
        *(txn(day, "WT Fed#01R23 Fab Bank /Ftr/Bnf=Fab One LLC Srf# 0001", -900.0) for day in WEEKLY[:2]),
        *(txn(day, "WT Fed#01R23 Fab Bank /Ftr/Bnf=Fab Two LLC Srf# 0001", -900.0) for day in WEEKLY[2:]),
    ])
    assert {record.classification for record in classify_statement_transactions(statement)} == {"other"}
```

- [ ] **Step 2: Run** it. Expected: FAIL.

- [ ] **Step 3: Code.**
  - `_ACH_FIELD_SEGMENT`'s last line becomes `    r"CONF|REF|MEMO|CUST|TYPE|CUSTOMER ID|INSTR|SRF|RFB|IMAD)\b"`, and its comment line reads `# 5.3 (2026-09-27): Truist's receiver field label, Huntington's instruction field and the wire fields.`
  - After `_TRUIST_COMPANY_FIELD = 16`:

```python
#: 5.3: a wire's beneficiary starts after BNF (Wells Fargo /Bnf=, Bank of America BNF:), else after the account
#: label of Chase's 'Wire Transfer Via: <bank> A/C: <beneficiary>'.
_WIRE_BENEFICIARY_PATTERNS = (
    re.compile(r"\bBNF(?: FFC)?\b"),
    re.compile(r"\bWIRE TRANSFER VIA\b.*?\bA C\b"),
)
```

  - Directly before `def _unknown_payee_tokens(`:

```python
def _wire_beneficiary(text: str) -> str | None:
    """5.3 (2026-09-27): the text after a wire's beneficiary label, or None for a row that is no such wire."""
    for pattern in _WIRE_BENEFICIARY_PATTERNS:
        found = pattern.search(text)
        if found is not None:
            return text[found.end():]
    return None
```

  - In `_unknown_payee_tokens`, the first statement becomes

```python
    beneficiary = _wire_beneficiary(text)
    region = _payee_region(beneficiary if beneficiary is not None else _PAYEE_TEMPLATE_PREFIX.sub(" ", text, count=1))
```

    the loop reads `for token in region.split():`, and the legal-form stop becomes

```python
        if len(tokens) > 1 and (
            token in _LEGAL_FORM_SUFFIXES or (beneficiary is not None and token in _ORGANISATION_CUES)
        ):
            break
```

    The docstring gains `A wire is read from its beneficiary, where a name ends at its first organisation cue after the first word.`

- [ ] **Step 4: Run** the file (PASS) and SEL-CLASSIFIER. An incoming 'WIRE IN … ORIG:' row has no BNF and is unaffected.

- [ ] **Step 5: Commit** (`git add analysis/transaction_classifier.py tests/test_payee_naming_53.py`) `"d11: a wire is named by its beneficiary; city and state never join the name"`.

---

### Task C8: The printed 'NAME, CITY, ST' line (N3)

**Files:** Modify `analysis/transaction_classifier.py`: a helper directly before `def classify_statement_transactions(` (`:2151`), and the grouping loop (`:2198`). Append to `tests/test_payee_naming_53.py`.

**Needs:** A1 (`_CARD_LOCATION_SUFFIX_PATTERN`), C5.

**Why:** The naming verifier recommended N1 plus this printed-text rule instead of a global cue cut: a card network's 'NAME, CITY, ST' line put the city into the name ('Rts Carrier Services Overland', c00120; c00159's city). D6's payee words of such a line are the printed name before the first comma, read without the module normalizer (a row is normalized exactly once). It applies to any bank, only without an ACH field mark. The A1 card skip still removes most of these rows on Bluevine and Found; this names the rows its veto keeps (organisation words).

- [ ] **Step 1: Test.** Append:

```python


# --- C8: the printed 'NAME, CITY, ST' line ----------------------------------------------------------------------------

def test_a_card_networks_city_never_joins_the_d6_name():
    statement = Statement(bank="Bluevine", transactions=[
        txn(day, "FAB CARRIER SERVICES, OVERLAND PARK, KS", -700.0) for day in WEEKLY
    ])
    records = classify_statement_transactions(statement)
    assert {(record.classification, record.canonical_entity) for record in records} == {
        ("potential_lender", "Fab Carrier Services")}
```

- [ ] **Step 2: Run** it. Expected: FAIL ('Fab Carrier Services Overland').

- [ ] **Step 3: Code.** Directly before `def classify_statement_transactions(`:

```python
#: 5.3 (2026-09-27): the D6 payee words of a card network's 'NAME, CITY, ST' line are the printed name before the
#: first comma (the city never joins the name), read without the module normalizer.
_PRINTED_NAME_WORD = re.compile(r"[A-Z0-9]+")


def _record_payee_tokens(record: TransactionClassification) -> tuple[str, ...]:
    """D6's payee words for one row: D11's words, or, on a 'NAME, CITY, ST' line with no ACH field mark, the words of
    the printed name before the first comma (5.3, 2026-09-27)."""
    printed = record.original_description or ""
    if _CARD_LOCATION_SUFFIX_PATTERN.search(printed) and not _has_ach_field_mark(record):
        return _unknown_payee_tokens(" ".join(_PRINTED_NAME_WORD.findall(printed.split(",", 1)[0].upper())))
    return _unknown_payee_tokens(record.normalized_description)
```

  In the grouping loop, `payee = _unknown_payee_tokens(record.normalized_description)` becomes `payee = _record_payee_tokens(record)`.

- [ ] **Step 4: Run** the file, SEL-CLASSIFIER and `tests/test_d6_skips.py` (the A1 location-suffix tests stay green: they skip before naming). `tests/test_classifier_lookups.py::test_each_row_is_normalized_exactly_once` must pass.

- [ ] **Step 5: Commit** (`git add analysis/transaction_classifier.py tests/test_payee_naming_53.py`) `"d6: a card network's NAME, CITY, ST line is named by the printed name alone"`.

---

### Task C9: The fixed D10 label of an MCA SERVICING payee

**Files:** Modify `analysis/transaction_classifier.py`: a constant after `UNIDENTIFIED_LENDER_OBLIGATION` (`:98`), a pattern before `_SERVICER_COLLECTOR_PATTERNS` (`:500`) and the D10 rule (`:1751-1757`). Create `tests/test_potential_payee_labels.py`. Re-pin pin-ledger row 3.

**Needs:** none.

**Why:** D10 servicer rows lost the servicer's words: 'Corporate ACH … Mca Servicing' gave the key CORPORATE, and TD's '… MCA SERVICING LLC' gave 'Servicing LLC' (MCA is noise). The verifier verified that the words name two unrelated funders (the ledger's decision of 2026-09-25), so it preferred a fixed label over a D11 name: 'MCA servicer (funder not identified)'. The owner's no-alias ruling stands.

- [ ] **Step 1: Test.** Create `tests/test_potential_payee_labels.py`:

```python
"""5.3 (2026-09-27): the Potential Lenders tab lists each unnamed payee key on its own line, and D10 names an MCA
SERVICING payee with one fixed label. Fabricated descriptors; every amount is whole dollars."""
from __future__ import annotations

import json

import pytest

from analysis.detect import find_potential_lenders
from analysis.metrics import compute_metrics
from analysis.schema import Statement
from analysis.serialization import report_to_dict
from analysis.transaction_classifier import (
    UNIDENTIFIED_MCA_SERVICER,
    classify_statement_transactions,
    classify_transaction,
)
from tests.flag_group_fixtures import txn
from tests.webapp_js_harness import NODE, run_dashboard

WEEKLY = ("2054-01-05", "2054-01-12", "2054-01-19", "2054-01-26")
UNIDENTIFIED = "Unidentified lender obligation"


def _statement(*rows):
    return Statement(bank="Fabricated Bank", transactions=[txn(day, text, amount) for day, text, amount in rows])


def test_an_mca_servicing_payee_carries_the_fixed_d10_label():
    for printed in ("ACH DEBIT MCA SERVICING 0001", "ACH DEBIT MCA SERVICING LLC 0001",
                    "Corporate ACH Payment Mca Servicing"):
        record = classify_transaction(printed, -250.0)
        assert (record.classification, record.canonical_entity) == ("potential_lender", UNIDENTIFIED_MCA_SERVICER)
```

- [ ] **Step 2: Run** it. Expected: FAIL (`ImportError: cannot import name 'UNIDENTIFIED_MCA_SERVICER'`).

- [ ] **Step 3: Code.**
  - After `UNIDENTIFIED_LENDER_OBLIGATION = …`:

```python
#: 5.3 (2026-09-27): the fixed D10 name of an MCA SERVICING payee. The two words print for two unrelated funders
#: (ledger decision of 2026-09-25), so no D11 name is ever built from them.
UNIDENTIFIED_MCA_SERVICER = "MCA servicer (funder not identified)"
```

  - Before `_SERVICER_COLLECTOR_PATTERNS = (`:

```python
#: 5.3 (2026-09-27): the MCA SERVICING words, named by the fixed UNIDENTIFIED_MCA_SERVICER label (D10).
_MCA_SERVICING_PATTERN = re.compile(r"\bMCA SERVICING\b")
```

  - In the D10 rule, `canonical_entity=_canonical_unknown_entity(text) or UNIDENTIFIED_LENDER_OBLIGATION,` becomes:

```python
            canonical_entity=(
                UNIDENTIFIED_MCA_SERVICER
                if _MCA_SERVICING_PATTERN.search(text)
                else _canonical_unknown_entity(text) or UNIDENTIFIED_LENDER_OBLIGATION
            ),
```

  - Pin-ledger row 3: `tests/test_unknown_payee_naming.py:87` becomes `("ACH DEBIT MCA SERVICING 0001", "MCA servicer (funder not identified)"),` with the comment `# 5.3 (2026-09-27): its fixed D10 label, because the words print for two unrelated funders.` under the existing owner-decision comment.

- [ ] **Step 4: Run** the new file and SEL-CLASSIFIER (row 3 moves; nothing else).

- [ ] **Step 5: Commit** (`git add analysis/transaction_classifier.py tests/test_potential_payee_labels.py tests/test_unknown_payee_naming.py`) `"d10: an MCA SERVICING payee carries one fixed label"`.

---

### Task C10: One Potential Lenders line per unnamed payee key

**Files:**
- Modify `analysis/transaction_classifier.py`: `TransactionClassification` (a last field after `classification_version`, `:178`), a helper beside `_record_payee_tokens` (C8), and one call in `classify_statement_transactions` directly before `records = _apply_reversal_pair_context(…)` (`:2260`).
- Modify `analysis/detect.py` `_group_funders` (`:108-137`), `analysis/metrics.py` (`:351`), `webapp/app.py` (`:1586-1590`) and `webapp/static/app.js` `filterTransactions` (`:692`).
- Append to `tests/test_potential_payee_labels.py`. Re-pin pin-ledger row 17.

**Needs:** C8, C9.

**Why:** Confirmed (c00015, c00132, c00067, c00125, c00180, c00030, c00033, c00095): every unnamed payee of a statement shared the canonical entity 'Unidentified lender obligation', so the tab showed one line with mixed amounts, and `potential_lenders_detected` counted one. Of 789 corpus accounts with such a line, 215 merged two or more groups (356 groups hidden). Each payee key (entity, rule, D6 payee words, amount, masked recipient) now gets its own label, which names the entity, the recurrence cadence and the amount, never a payee word (D11): 'Unidentified lender obligation (weekly, 450.00)'. A second key with the same label gets ' #2'. `canonical_entity` does not change. The tag of each ledger row keeps its entity (the row shows its own amount); the tab, the metric, the package and the tab's click filter read the label. Named potential payees keep their name and no label. A package joins the same label across its members, as it joins a name.

- [ ] **Step 1: Tests.** Append to `tests/test_potential_payee_labels.py`:

```python


def test_two_unnamed_weekly_payees_are_two_lines_and_two_potential_lenders():
    statement = _statement(
        *((day, "ACH DEBIT FAB KEEPER 0001", -450.0) for day in WEEKLY),
        *((day, "OTHER DEBIT FAB 0002", -1200.0) for day in WEEKLY),
    )
    records = classify_statement_transactions(statement)
    assert {record.canonical_entity for record in records} == {UNIDENTIFIED}
    lines = find_potential_lenders(statement, records)
    assert [(line.funder, line.debit_count, line.total_debited) for line in lines] == [
        (f"{UNIDENTIFIED} (weekly, 1,200.00)", 4, 4800.0),
        (f"{UNIDENTIFIED} (weekly, 450.00)", 4, 1800.0),
    ]
    assert compute_metrics(statement, classifications=records).potential_lenders_detected == 2


def test_a_single_unnamed_row_is_labelled_by_its_amount_and_a_repeated_label_is_numbered():
    statement = _statement(
        ("2054-01-05", "DIRECT DEBIT LOANS", -125.0),
        ("2054-01-20", "ACH DEBIT LOAN PAYMENT FAB 0001", -125.0),
    )
    labels = [record.potential_payee_label for record in classify_statement_transactions(statement)]
    assert labels == [f"{UNIDENTIFIED} (125.00)", f"{UNIDENTIFIED} (125.00) #2"]


def test_a_named_potential_payee_keeps_its_name_and_no_label():
    statement = _statement(*((day, "ACH DEBIT FABRIKAM FUNDING LLC 0001", -600.0) for day in WEEKLY))
    records = classify_statement_transactions(statement)
    assert {(record.canonical_entity, record.potential_payee_label) for record in records} == {
        ("Fabrikam Funding LLC", None)}


def test_the_payload_publishes_the_label_on_each_row_and_its_line():
    from tests.flag_group_fixtures import flagged_report

    payload = report_to_dict(flagged_report(tuple((day, "ACH DEBIT FAB KEEPER 0001", -450.0) for day in WEEKLY)))
    label = f"{UNIDENTIFIED} (weekly, 450.00)"
    assert [line["funder"] for line in payload["detection"]["potential_lenders"]] == [label]
    assert {row["classification"]["potential_payee_label"] for row in payload["statement"]["transactions"]} == {label}


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


@needs_node
def test_a_click_on_an_unnamed_line_shows_only_that_payees_rows():
    rows = [
        {"date": "2054-01-05", "description": "ACH DEBIT FAB KEEPER 0001", "amount": -450.0,
         "classification": {"classification": "potential_lender", "canonical_entity": UNIDENTIFIED,
                            "potential_payee_label": f"{UNIDENTIFIED} (weekly, 450.00)",
                            "contributes_to_potential_lender_totals": True}},
        {"date": "2054-01-06", "description": "OTHER DEBIT FAB 0002", "amount": -1200.0,
         "classification": {"classification": "potential_lender", "canonical_entity": UNIDENTIFIED,
                            "potential_payee_label": f"{UNIDENTIFIED} (weekly, 1,200.00)",
                            "contributes_to_potential_lender_totals": True}},
        {"date": "2054-01-07", "description": "ACH DEBIT FABRIKAM FUNDING LLC", "amount": -600.0,
         "classification": {"classification": "potential_lender", "canonical_entity": "Fabrikam Funding LLC",
                            "contributes_to_potential_lender_totals": True}},
    ]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
console.log(JSON.stringify({{
  unnamed: filterTransactions(rows, "potential", "{UNIDENTIFIED} (weekly, 450.00)").map((tx) => tx.date),
  named: filterTransactions(rows, "potential", "Fabrikam Funding LLC").map((tx) => tx.date),
}}));
""")
    assert result == {"unnamed": ["2054-01-05"], "named": ["2054-01-07"]}
```

- [ ] **Step 2: Run** it. Expected: FAIL (one merged line; no `potential_payee_label`).

- [ ] **Step 3: The record field and the labels.**
  - `TransactionClassification` gains, after `classification_version`:

```python
    # 5.3 (2026-09-27): the Potential Lenders line of an unnamed potential payee, one per payee key within the
    # statement ('Unidentified lender obligation (weekly, 450.00)'). None for every other row, whose line is its
    # canonical_entity.
    potential_payee_label: str | None = None
```

  - Directly after `_record_payee_tokens` (C8):

```python
#: 5.3 (2026-09-27): the names D11 and D10 publish for a payee they cannot name. The Potential Lenders tab lists
#: each payee key of them on its own line (potential_payee_label), never one line for all.
_UNNAMED_POTENTIAL_ENTITIES = frozenset({UNIDENTIFIED_LENDER_OBLIGATION, UNIDENTIFIED_MCA_SERVICER})
_RECURRENCE_CADENCE = re.compile(r"^(daily|weekly)_fixed_debit_")


def _label_unnamed_potential_payees(records: list[TransactionClassification]) -> list[TransactionClassification]:
    """5.3 (2026-09-27): one Potential Lenders line per unnamed payee of a statement. The rows of one payee key
    (entity, rule, payee words, amount and masked recipient) share a label that names the entity, the cadence of a
    recurrence and the amount, never a payee word (D11): 'Unidentified lender obligation (weekly, 450.00)'. A second
    key with the same label gets ' #2'. canonical_entity is unchanged."""
    groups: dict[tuple[object, ...], list[int]] = {}
    for index, record in enumerate(records):
        if record.classification == "potential_lender" and record.canonical_entity in _UNNAMED_POTENTIAL_ENTITIES:
            key = (record.canonical_entity, record.match_method, _record_payee_tokens(record),
                   round(abs(record.amount), 2), _masked_recipient(record))
            groups.setdefault(key, []).append(index)
    labelled = list(records)
    used: dict[str, int] = {}
    for (entity, _method, _payee, amount, _recipient), indexes in groups.items():
        cadence = _RECURRENCE_CADENCE.match(records[indexes[0]].matched_rule or "")
        label = f"{entity} ({cadence.group(1)}, {amount:,.2f})" if cadence else f"{entity} ({amount:,.2f})"
        used[label] = used.get(label, 0) + 1
        if used[label] > 1:
            label = f"{label} #{used[label]}"
        for index in indexes:
            labelled[index] = replace(records[index], potential_payee_label=label)
    return labelled
```

  - In `classify_statement_transactions`, directly before `records = _apply_reversal_pair_context(records, set(duplicate_of))`: `records = _label_unnamed_potential_payees(records)`.

- [ ] **Step 4: The consumers.**
  - `analysis/detect.py` `_group_funders`: directly after the `continue` guard, `name = record.potential_payee_label or record.canonical_entity` (with the comment `# 5.3 (2026-09-27): an unnamed potential payee is listed under its own label, one per payee key.`); `matches.get(name)`, `FunderMatch(funder=name, …)` and `matches[name] = match` replace the three uses of `record.canonical_entity`.
  - `analysis/metrics.py:351`: `potential_entities.add(classification.potential_payee_label or classification.canonical_entity)`.
  - `webapp/app.py:1589`: `name = (classification.get("potential_payee_label") or classification.get("canonical_entity") or "Unknown candidate")`.
  - `webapp/static/app.js` `filterTransactions`, its last line becomes:

```js
  // 5.3: an unnamed potential payee is listed under its own label (potential_payee_label), one per payee key.
  return matched.filter((tx) => {
    const record = transactionClassification(tx);
    return (record.potential_payee_label || record.canonical_entity) === canonicalEntity;
  });
```

  - Pin-ledger row 17: `tests/test_lender_insurance_classification.py:364` becomes `assert candidate.funder == "Unidentified lender obligation (125.00)"`, with the comment `# 5.3 (2026-09-27): an unnamed payee's line carries its amount, one line per payee key.`

- [ ] **Step 5: Run** the file, SEL-CLASSIFIER and SEL-WEBAPP. Only row 17 moves. Real-statement pins name their potential lenders (MERCH PAD, LOANS FC…), which keep their names.

- [ ] **Step 6: Commit** (`git add analysis/transaction_classifier.py analysis/detect.py analysis/metrics.py webapp/app.py webapp/static/app.js tests/test_potential_payee_labels.py tests/test_lender_insurance_classification.py`) `"potential lenders: one line per unnamed payee key, labelled by cadence and amount"`.

---

## Part D — The twelfth flag group, Debt relief

The owner ruled (2026-09-27) a new flag group for debt-settlement account processors and debtor-side debt-relief firms, shown like the other flags: a Settings checkbox, default ON, never lender math. Its design follows the debt-relief research (`research/debt_relief.json`, `proposed_group`), including its REQUIRED hazard, which it verified with a prototype (`work/dr_holder_guard.py`, 22 of 22 cases):
- **Its own table and its own index, never a known-payee peer.** The known-payee matcher reads the whole row, receiver fields included. As a longest-alias peer, a debt-relief alias in the holder's own name (a law firm or negotiator can itself be an MCA applicant) would outrank the funder: 'ONDECK DES:PAYMENT … INDN:TAYNE LAW GROUP PC' would become debt relief. So `DEBT_RELIEF_ALIASES` is rendered as its own table (like `BANK_NAME_ALIASES`), stays out of `PAYEE_GROUP_REGISTRIES`, and is read only when no known payee matched, on the row with its receiver fields cut out.
- **Run-together forms are read** (the debt-relief verifier). The table is read through its own `AliasIndex` built with `run_together=True`, as the known-payee index is, never through `registry_match` (which the insurance, premium and potential tables use and which never reads glued forms). So FORTHPAY and RAMPAYMENTS reach their payees, step 5's POS exception reads the same index (the match stands in for the known payee), and D2's extension of the validator's run-together collision check to this table is warranted: a glued debt-relief alias can never equal a lender's alias or its glued form.
- **Debits only; credits unchanged.** A credit from these payees is the debtor's own money back from the escrow (28 corpus 'RAM PMT' credits, 6 New Leaf credits), never financing proceeds. The group is not in `FINANCING_STATES`, and debt relief never applies to a credit (open question 14 asks whether those refunds become non_revenue later).
- **Order.** Step 6 still claims fees first ('Wire fee for … Tayne Law Group' stays a fee). The POS and ATM exceptions (D8) let a card purchase at a debt-relief firm reach the flag (Delancey Street's card rows). A registered lender printed in the DES field of a RAM or Global row still wins.
- The generic words (DEBT, RELIEF, SETTLEMENT, CONSOLIDATION, RESOLUTION, NEGOTIATION, PROGRAM, LAW) join the validator's generic-word list, so a phrase such as DEBT RELIEF alone can never be an alias. Both debt-relief verifiers dropped the generic classifier words.

The payees themselves come through the registry in Part E (E3). Until then the table is empty and the group carries no row.

The funders research (`research/funders.json`, `debt_relief_group_proposal`) proposed appending `debt_relief` to `PAYEE_STATES` instead; the debt-relief research's verified hazard decides against it.

### Task D1: The group, its state and its dashboard tag

**Files:**
- Modify `analysis/flag_groups.py` (`FLAG_GROUPS`, `:32`).
- Modify `analysis/transaction_classifier.py`: `ClassificationState` (`:44`) and `CLASSIFICATION_STATES` (`:74`).
- Modify `webapp/static/app.js`: `FLAG_GROUP_LABELS` (`:309-321`) and `transactionCategory` (`:533`).
- Modify `tests/flag_group_fixtures.py` (`FAKE_PAYEES`, pin-ledger row 15).
- Re-pin rows 4, 5, 6, 7 and the wording of row 9. Create `tests/test_debt_relief_group.py`; extend `tests/test_webapp_flagged_dashboard.py`.

**Needs:** none. `webapp/settings.py` needs no change: `DEFAULTS` is built from `FLAG_SETTING_KEYS`, so `flag_debt_relief: True` appears by itself.

- [ ] **Step 1: Tests.** Create `tests/test_debt_relief_group.py`:

```python
"""5.3 (owner ruling 2026-09-27): the twelfth flag group, Debt relief. Fabricated descriptors and a fabricated
debt-relief table; every amount is whole dollars."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.detect import find_flagged_positions
from analysis.flag_groups import FINANCING_STATES, FLAG_GROUP_BY_KEY
from analysis.payee_matcher import AliasIndex
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import fake_payees, txn  # noqa: F401  (fixture)

FABRICATED_RELIEF = {"Fabrikam Settlement Payments": ("FABRIKAM SETTLE PMT", "FABRIKAM DEBT RELIEF")}


def test_the_group_is_a_flag_and_never_financing():
    group = FLAG_GROUP_BY_KEY["debt_relief"]
    assert (group.state, group.setting, group.label) == ("debt_relief", "flag_debt_relief", "Debt relief")
    assert "debt_relief" not in FINANCING_STATES
```

  In `tests/test_webapp_flagged_dashboard.py`, `test_every_new_state_has_its_own_tag_and_the_retired_state_keeps_one`'s `states` list gains, after the `("factoring", None, "Factoring"),` line:

```python
        # 5.3 (owner ruling 2026-09-27): the twelfth group.
        ("debt_relief", "FABRICATED SETTLEMENT CO", "FABRICATED SETTLEMENT CO (Debt relief)"),
        ("debt_relief", None, "Debt relief"),
```

- [ ] **Step 2: Run** both files. Expected: FAIL (`KeyError: 'debt_relief'`; the dashboard labels the state 'Other Debit').

- [ ] **Step 3: The group and the state.**
  - Append to `FLAG_GROUPS`, after the premium-financing group:

```python
    # Owner ruling 2026-09-27 (classification 5.3): debt-settlement account processors and debtor-side debt-relief
    # firms. Never lender math, and not in FINANCING_STATES: its payees never lend.
    FlagGroup("debt_relief", "debt_relief", "flag_debt_relief", "Debt relief"),
```

  - `ClassificationState` and `CLASSIFICATION_STATES` each gain `"debt_relief",` directly after `"factoring",`.

- [ ] **Step 4: The dashboard.** `FLAG_GROUP_LABELS` gains `  debt_relief: "Debt relief",` after `premium_financing`; `transactionCategory`'s table gains, after the `factoring` entry:

```js
    debt_relief: { label: entity ? `${entity} (Debt relief)` : "Debt relief", glyph: "DRP", tone: "neutral" },
```

- [ ] **Step 5: The pins.**
  - Row 4 (`tests/test_flag_groups.py:16-45`): `EXPECTED` gains `("debt_relief", "debt_relief", "flag_debt_relief", "Debt relief"),` last (with the comment `# Owner ruling 2026-09-27 (classification 5.3): the twelfth group.`); the test is renamed `test_the_twelve_groups_match_the_spec_table_in_order`; `len(FLAG_GROUP_BY_STATE) == 10` becomes `== 11`.
  - Row 5 (`tests/test_flagged_view.py:29-37`): the key tuple gains `"debt_relief"` last; the test is renamed `test_the_view_reads_the_twelve_contract_groups`.
  - Row 6 (`tests/test_webapp_settings.py:17-27`): `EXPECTED_DEFAULTS` gains `"flag_debt_relief": True,` last.
  - Row 7 (`tests/test_webapp_flagged_dashboard.py:465-466`): `GROUP_KEYS` gains `"debt_relief"` last.
  - Row 9, wording only (`tests/test_webapp_reanalysis.py:983, 1049-1050`): "eleven" becomes "twelve" in `_every_group_rows`'s docstring and the comment before `flagged = …`; the assertions derive from `FLAG_GROUPS` and move by themselves.
  - Row 15 (`tests/flag_group_fixtures.py:26-38`): `FAKE_PAYEES` gains `"FABRICATED DEBT RELIEF": ("Fabricated Debt Relief", "debt_relief"),`. `fake_match` then stands in for the D3 index too (the known-payee path gives the same record), so the reanalysis test that pays every group keeps a payee for the twelfth.

- [ ] **Step 6: Run** the two files, SEL-CLASSIFIER and SEL-WEBAPP. Expected: PASS; the parametrized tests over `FLAG_GROUPS` (exports, settings, flagged view) gain a debt-relief case each and pass. No other assertion moves.

- [ ] **Step 7: Commit** (`git add analysis/flag_groups.py analysis/transaction_classifier.py webapp/static/app.js tests/flag_group_fixtures.py tests/test_debt_relief_group.py tests/test_flag_groups.py tests/test_flagged_view.py tests/test_webapp_settings.py tests/test_webapp_flagged_dashboard.py tests/test_webapp_reanalysis.py`) `"flag groups: the twelfth group, Debt relief, with its state, Settings switch and tag"`.

---

### Task D2: The ledger's Debt relief table

**Files:**
- Modify `tools/lender_ledger.py`: `TABLES` (`:68`), `GENERIC_WORDS` (`:91-95`) and `_collision_problems` (`:653`).
- Modify `tools/lender_census.py`: `GENERIC_WORDS` (`:39-49`).
- Re-render `analysis/classification_registry.py` and `docs/lender-registry-evidence.md`.
- Append to `tests/test_lender_ledger.py`; extend `tests/test_classification_registry_groups.py` (`GROUP_TABLES` and the out-of-the-matcher list); rename one test in `tests/test_build_lender_registry.py` (`:68`).

**Needs:** D1.

- [ ] **Step 1: Tests.** Append to `tests/test_lender_ledger.py`:

```python


# --- 5.3 (owner ruling 2026-09-27): the Debt relief group --------------------------------------------------------


def _with(*records):
    data = ledger()
    data["entities"] += list(records)
    return data


SETTLEMENT = entity("Fabrikam Settlement Payments", "debt_relief", ["FABRIKAM SETTLE PMT"],
                    business_type="debt_settlement_dedicated_account_processor")


def test_an_admitted_debt_relief_entity_renders_into_its_own_table_and_never_the_matcher():
    data = _with(SETTLEMENT)
    assert lender_ledger.validate(data, RULES) == []
    entities, _problems = lender_ledger.parse_ledger(data)
    tables = lender_ledger.render_tables(entities)
    assert tables["DEBT_RELIEF_ALIASES"] == {"Fabrikam Settlement Payments": ("FABRIKAM SETTLE PMT",)}
    assert "debt_relief" not in lender_ledger.PAYEE_STATES


def test_debt_relief_words_alone_are_generic():
    generic = entity("Fabrikam Relief", "debt_relief", ["DEBT RELIEF PROGRAM"], business_type="debt_settlement_company")
    assert any("only generic words" in problem for problem in lender_ledger.validate(_with(generic), RULES))


def test_a_debt_relief_aliases_run_together_form_may_not_be_a_lenders_alias():
    clash = entity("Quillon Settlement", "debt_relief", ["QUILLON FUND"], business_type="debt_settlement_company")
    assert any("run-together form" in problem for problem in lender_ledger.validate(_with(clash), RULES))
```

  In `tests/test_classification_registry_groups.py`, `GROUP_TABLES` gains `"DEBT_RELIEF_ALIASES",` after `"FACTORING_ALIASES",`, and the tuple in `test_the_context_bank_potential_and_premium_tables_stay_out_of_the_known_payee_matcher` gains `"DEBT_RELIEF_ALIASES"`. `PAYEE_GROUP_REGISTRIES` and its test do not change.

- [ ] **Step 2: Run** them. Expected: FAIL (`debt_relief` is no ledger group; `DEBT_RELIEF_ALIASES` does not exist).

- [ ] **Step 3: The ledger tool.**
  - `TABLES` gains, directly after the factoring row:

```python
    ("debt_relief", "DEBT_RELIEF_ALIASES",
     "Debt relief: debt-settlement account processors and debt-relief firms (flagged, never lender math)"),
```

  - `GENERIC_WORDS` gains the line `DEBT RELIEF SETTLEMENT CONSOLIDATION RESOLUTION NEGOTIATION PROGRAM LAW` before the closing `""".split())`. The same eight words join `tools/lender_census.py` `GENERIC_WORDS`, after `"THE",`, with the comment `# 5.3 (2026-09-27): the debt-relief words tools.lender_ledger.GENERIC_WORDS gained.` (`tests/test_lender_census.py` pins the superset). No alias of the ledger is made only of these words and the old ones (checked 2026-09-27).
  - `_collision_problems`: `matcher = [e for e in entities if e.status == "admitted" and e.group in (*PAYEE_STATES, "debt_relief")]`, so a run-together form of a debt-relief alias can never be a known payee's alias (the research's validator change; warranted because D3's index reads run-together forms).
  - `PAYEE_STATES`, `CONTEXT_ONLY_GROUPS` and `ORG_CUES` do not change. The research proposed LAW as an organisation cue; it is not taken, because the privacy review is safer listing more names, not fewer.

- [ ] **Step 4: Render.** `--check` (0 problems, the move lines unchanged), then `--write`. The block gains an empty `DEBT_RELIEF_ALIASES: dict[str, tuple[str, ...]] = {}` after the factoring table, and the evidence page a Debt relief section ("None.").

- [ ] **Step 5: Wording.** `tests/test_build_lender_registry.py::test_the_block_of_an_empty_ledger_defines_fourteen_empty_tables` is renamed `…_defines_fifteen_empty_tables` (its assertion derives from `TABLES`).

- [ ] **Step 6: Run** SEL-REGISTRY. Expected: PASS.

- [ ] **Step 7: Commit** (`git add tools/lender_ledger.py tools/lender_census.py analysis/classification_registry.py docs/lender-registry-evidence.md tests/test_lender_ledger.py tests/test_classification_registry_groups.py tests/test_build_lender_registry.py`) `"registry: the Debt relief table, its generic words and its run-together collision check"`.

---

### Task D3: The debt-relief payee step

**Files:**
- Modify `analysis/payee_matcher.py`: the registry import (`:17`), a second index after `_DEFAULT_INDEX` (`:92`) and `match_debt_relief_payee` before `def registry_match(` (`:102`).
- Modify `analysis/transaction_classifier.py`: the matcher import (`:26`), a constant after `_RECEIVER_NAME_FIELD` (Task 0.2), and `classify_transaction` after the field-order lines (B3).
- Append to `tests/test_debt_relief_group.py`.

**Needs:** D2 (the table must exist before the matcher imports it), B3.

- [ ] **Step 1: Tests.** Append to `tests/test_debt_relief_group.py`:

```python


@pytest.fixture
def relief_payees(monkeypatch):
    index = AliasIndex({"debt_relief": FABRICATED_RELIEF}, run_together=True)
    monkeypatch.setattr(transaction_classifier, "match_debt_relief_payee", index.match)


@pytest.mark.parametrize(
    "printed",
    [
        "FABRIKAM SETTLE PMT 0001",
        "Electronic Withdrawal To FABRIKAM SETTLE PMT",
        "FABRIKAMSETTLEPMT DES:DEPOSIT ID:0001",                      # the run-together form
        "Orig CO Name:Fabrikam Debt Relief Orig ID:0001 Desc Date: CO Entry Descr:Pmt Sec:PPD Ind Name:Pat Example",
        # a card purchase at a debt-relief firm is that firm's (the POS exception, D8)
        "Debit Card Purchase: 0105 PURCHASE 12 FABRIKAM DEBT RELIEF NEW YORK NY",
    ],
)
def test_a_debit_to_a_debt_relief_payee_is_flagged_debt_relief(relief_payees, printed):
    record = classify_transaction(printed, -400.0)
    assert (record.classification, record.canonical_entity, record.flagged_group) == (
        "debt_relief", "Fabrikam Settlement Payments", "debt_relief")
    assert (record.match_method, record.matched_rule) == ("known_payee_alias", "debt_relief_registry")
    assert record.contributes_to_flagged_totals
    assert not record.contributes_to_lender_totals and not record.contributes_to_potential_lender_totals


def test_the_account_holders_own_name_never_makes_a_row_debt_relief(relief_payees, fake_payees):
    funder = classify_transaction(
        "FABRICATED LENDER DES:PAYMENT ID:0001 INDN:FABRIKAM DEBT RELIEF CO ID:0002 CCD", -400.0)
    assert (funder.classification, funder.canonical_entity) == ("confirmed_lender", "Fabricated Lender")
    unknown = classify_transaction("FAB UNLISTED ADVANCE DES:DEBIT ID:0001 INDN:FABRIKAM DEBT RELIEF CO ID:1 CCD",
                                   -400.0)
    assert unknown.classification != "debt_relief"


def test_a_known_payee_outranks_a_debt_relief_alias_on_the_same_row(relief_payees, fake_payees):
    record = classify_transaction("FABRIKAM SETTLE PMT DES:FABRICATED LENDER ID:0001 PPD", -400.0)
    assert record.classification == "confirmed_lender"


def test_credits_and_fees_keep_todays_rules(relief_payees):
    refund = classify_transaction("FABRIKAM SETTLE PMT 0001", 400.0)
    assert refund.classification != "debt_relief" and refund.flagged_group is None
    assert classify_transaction("WIRE FEE FOR WIRE TRANSFER TO FABRIKAM DEBT RELIEF", -25.0).classification == "fee"


def test_debt_relief_rows_are_a_flagged_position_and_never_a_d6_payee(relief_payees):
    statement = Statement(bank="Fabricated Bank", transactions=[
        txn(day, "FABRIKAM SETTLE PMT 0001", -300.0) for day in ("2054-01-05", "2054-01-12", "2054-01-19")
    ])
    records = classify_statement_transactions(statement)
    assert {record.classification for record in records} == {"debt_relief"}
    [position] = find_flagged_positions(statement, records)
    assert (position.group, position.payee, position.count, position.cadence) == (
        "debt_relief", "Fabrikam Settlement Payments", 3, "weekly")
```

- [ ] **Step 2: Run** it. Expected: FAIL (`AttributeError: … has no attribute 'match_debt_relief_payee'`).

- [ ] **Step 3: The index.** In `analysis/payee_matcher.py`:
  - the import becomes `from .classification_registry import DEBT_RELIEF_ALIASES, PAYEE_GROUP_REGISTRIES`;
  - after `_DEFAULT_INDEX = …`:

```python
#: 5.3 (owner ruling 2026-09-27): the debt-relief payees, an index of their own. They are read only after no known
#: payee matched, never as a longest-alias peer of the known-payee groups. Run-together forms are read (FORTHPAY,
#: RAMPAYMENTS), as in the known-payee index; registry_match never reads them.
_DEBT_RELIEF_INDEX = AliasIndex({"debt_relief": DEBT_RELIEF_ALIASES}, run_together=True)
```

  - before `def registry_match(`:

```python
def match_debt_relief_payee(normalized_text: str) -> PayeeMatch | None:
    """5.3 (owner ruling 2026-09-27): the longest debt-relief alias (state "debt_relief"), or None."""
    return _DEBT_RELIEF_INDEX.match(normalized_text)
```

- [ ] **Step 4: The classifier.**
  - The matcher import becomes `from .payee_matcher import PayeeMatch, match_debt_relief_payee, match_known_payee, registry_match`.
  - After `_RECEIVER_NAME_FIELD = …` (Task 0.2):

```python
#: 5.3 (owner ruling 2026-09-27): a receiver-name field with its value, up to the next ACH field, removed before the
#: debt-relief table is read: the account holder's own name never makes a row debt relief.
_RECEIVER_FIELD_VALUE = re.compile(
    r"\b(?:INDN|IND NAME|RECEIVER NAME|RECV NAME)\b.*?(?=\b(?:CO ID|TRN|TRACE|PPD|CCD|WEB|CTX|TEL|ARC|BOC)\b|$)"
)
```

  - In `classify_transaction`, directly after B3's `if field_order_payee is not None: known_payee = field_order_payee`:

```python
    # 5.3 (owner ruling 2026-09-27): a debt-relief payee, on a debit no known payee claimed, read without the row's
    # receiver fields (the account holder may itself be a debt-relief firm). It then stands in for the known payee:
    # the POS and ATM exceptions (D8) and step 7 treat it as one. Credits keep today's rules.
    if known_payee is None and amount < 0:
        known_payee = match_debt_relief_payee(_RECEIVER_FIELD_VALUE.sub(" ", text))
```

  Step 7's `_known_payee_debit_record` gives the record: state `debt_relief`, `known_payee_alias`, rule `debt_relief_registry`, the group's flag.

- [ ] **Step 5: Run** the file, SEL-CLASSIFIER and SEL-REGISTRY. `tests/test_classifier_lookups.py` must pass: the receiver cut is a regex on the already normalized row.

- [ ] **Step 6: Commit** (`git add analysis/payee_matcher.py analysis/transaction_classifier.py tests/test_debt_relief_group.py`) `"debt relief: its own index, read on debits no known payee claimed, never on the holder's name"`.

---

### Task D4: Review entities of Debt relief take the flag, marked unconfirmed

**Files:** Modify `tools/lender_ledger.py` (`ROUTED_REVIEW_GROUPS`, C1) and `tools/build_lender_registry.py` (C1's admission bullet); re-render the evidence page. Append to `tests/test_lender_ledger.py` and `tests/test_debt_relief_group.py`.

**Needs:** C1, D2.

**Why:** A review entity of a flag group goes to its flag, unconfirmed (C1). The research keeps Resolve Capital under review (E3): its printed originator cannot be tied to the negotiator. Its aliases stay in `POTENTIAL_LENDER_ALIASES`, so its credits keep the potential exclusion; the corpus has none.

- [ ] **Step 1: Tests.** Append to `tests/test_lender_ledger.py`:

```python


def test_a_review_entity_of_debt_relief_is_routed_to_its_flag():
    negotiator = entity("Fabrikam Negotiators", "debt_relief", ["FABRIKAM NEGOTIATORS"], status="review",
                        business_type="mca_debt_relief_negotiator", evidence=[], verdicts=UNRESOLVED)
    entities, problems = lender_ledger.parse_ledger(_with(negotiator))
    assert problems == []
    assert lender_ledger.review_flag_entities(entities) == {"Fabrikam Negotiators": "debt_relief"}
```

  Append to `tests/test_debt_relief_group.py`:

```python


def test_a_review_debt_relief_payee_takes_the_flag_marked_unconfirmed(monkeypatch):
    monkeypatch.setattr(transaction_classifier, "POTENTIAL_LENDER_ALIASES",
                        {"FABRIKAM NEGOTIATORS (unconfirmed)": ("FABRIKAM NEGOTIATORS",)})
    monkeypatch.setattr(transaction_classifier, "REVIEW_FLAG_ENTITIES",
                        {"FABRIKAM NEGOTIATORS (unconfirmed)": "debt_relief"})
    record = classify_transaction("ACH DEBIT FABRIKAM NEGOTIATORS 0001", -900.0)
    assert (record.classification, record.flagged_group, record.review_required, record.match_method) == (
        "debt_relief", "debt_relief", True, "unconfirmed_flag_payee_alias")
```

- [ ] **Step 2: Run** them. Expected: the ledger test FAILS (`{}`); the classifier test passes already (C1's step 11 is generic).

- [ ] **Step 3: Code.** `ROUTED_REVIEW_GROUPS` gains `"debt_relief"` last. In the admission bullet C1 added to `render_evidence`, "vehicle, mortgage, lease or personal-loan group" becomes "vehicle, mortgage, lease, personal-loan or debt-relief group". Run `--check`, then `--write` (only the evidence page changes while no debt-relief entity is under review).

- [ ] **Step 4: Run** SEL-REGISTRY and the file. Expected: PASS.

- [ ] **Step 5: Commit** (`git add tools/lender_ledger.py tools/build_lender_registry.py docs/lender-registry-evidence.md tests/test_lender_ledger.py tests/test_debt_relief_group.py`) `"debt relief: an unconfirmed debt-relief payee takes the flag, marked for review"`.

---

## Part E — Registry additions from the research files (VERIFIED entries only)

Sources: `C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/research/funders.json` (four new entities, three entity updates) and `research/debt_relief.json` (24 debt-relief entities). Both are private working files. Their entity names, aliases, public sources and notes are business facts and go into the ledger as they stand. Never copy a statement value from them; the NFSPV alias's vehicle digit is taken from the file by script, and this plan never writes it.

**What VERIFIED means.** The research rounds proposed these entries; their own verdicts (`r6` in `funders.json`, none in `debt_relief.json`) do not verify them. An entry is VERIFIED when it carries a verdict from an independent verify round (any `round` other than the proposing one):
- an admitted entity, or an alias added to an admitted entity: a verdict `upheld` or `corrected` with `confirmed: true`;
- a review entity: any verdict of that round (`upheld`, `corrected` or `unresolved`): the round re-checked it and kept it under review (most of the ledger's review entities carry `unresolved` verdicts).

The verify round appends its verdict to the entry's `verdicts` (for an entity update, to an `append_verdicts` list), after re-fetching the sources. The ledger validator then admits the entity on that verdict (C10: admitted needs an upheld or corrected verdict that confirms it).

**The verify round r7 (2026-09-27, recorded in the research files on 2026-09-28).** Both files carry its verdicts and required changes, and a `verify_round` block that lists what Part E may use. Every entry is VERIFIED:
- `funders.json`: Flexibility Capital, Inc., Merit Business Funding and Essentia Funding (r7 upheld, confirmed; E1); the NATIONAL FUNDING update, alias `NFSPV<d> COLLECTION` (r7 upheld, confirmed; E2); Samson Servicing as a review entity (r7 unresolved; E4). Merit carries only `MERIT BUSINESS FUNDING`: `MERIT BUSINESS` waits for the owner (`owner_pending_aliases`, open question 11). Essentia gained a public company's 2026 10-Q as evidence; Samson's evidence no longer cites the 2017 filing (it names a guarantor; it stays under where_looked).
- `debt_relief.json`: the 23 admitted entities (13 r7 upheld and 10 r7 corrected, all confirmed) and Resolve Capital as a review entity (r7 unresolved; E3). COASTAL DEBT was dropped from Coastal Debt Resolve (it would read a creditor-side 'Coastal Debt Recovery'), and the notes of RAM Payment, Global Holdings, Set Forth, the five credit-counselling agencies, Rise Alliance and Resolve Capital were corrected to what their sources say.

Part E stops only if an owner-named payee loses its VERIFIED status (global stop rule).

Left out: the card-context entries for Atlas Smart Pay and RTS Carrier Services (c00207, c00120). Neither research file carries them, so those keys stay in review (open question 9). Also not Part E's: the funders file's GOAT and Bell Rock notes, which C4 writes in the matcher's own commit; the verify round aligned their research wording with the three-letter rule C4 ships (the r6 Bell Rock note was false under it).

### Task E0: The verify gate and the ledger script

**Files:** Create (scratch, never committed) `C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/e/research_ledger.py`.

**Needs:** C1-C4, D2 (the ledger tool knows the debt-relief group).

- [ ] **Step 1: Write the script** with the Write tool:

```python
"""Part E of the 5.3 plan: list the research entries and whether each is VERIFIED, and add the VERIFIED ones the
caller names to docs/lender-registry-ledger.json. Prints entity names, statuses and verdict rounds only.

  python research_ledger.py gate
  python research_ledger.py add <funders.json|debt_relief.json> "<entity>" ["<entity>" ...]
  python research_ledger.py update funders.json "<entity>"
  python research_ledger.py owner-alias funders.json "<entity>" <yyyy-mm-dd>   # ONLY on the owner's explicit yes
"""
import copy
import json
import sys
from pathlib import Path

RESEARCH = Path("C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/research")
LEDGER = Path("C:/Users/GustavoPrietodePaula/work/ld-fp53/docs/lender-registry-ledger.json")
#: The rounds that proposed the entries: their verdicts never verify them.
PROPOSING = {"funders.json": {"r6"}, "debt_relief.json": set()}


def _research(name):
    return json.loads((RESEARCH / name).read_text(encoding="utf-8"))


def _independent(verdicts, proposing, admitted):
    """The first verdict of an independent round that verifies the entry: for an admitted entity (or an alias added
    to one) an upheld or corrected verdict that confirms it; for a review entity any verdict of that round (it
    re-checked the entry and kept it under review)."""
    for verdict in verdicts:
        if verdict["round"] in proposing:
            continue
        if admitted and verdict["verdict"] in ("upheld", "corrected") and verdict["confirmed"]:
            return verdict
        if not admitted and verdict["verdict"] in ("upheld", "corrected", "unresolved"):
            return verdict
    return None


def gate():
    for name, proposing in PROPOSING.items():
        data = _research(name)
        for record in data.get("new_entities", []) + data.get("entities", []):
            found = _independent(record["verdicts"], proposing, record["status"] == "admitted")
            print(f"{name}: {'VERIFIED' if found else 'not verified'}: {record['entity']} "
                  f"({record['group']}, {record['status']})" + (f" by {found['round']}" if found else ""))
        for update in data.get("entity_updates", []):
            if "append_verdicts" not in update:
                print(f"{name}: not Part E: update of {update['entity']} ({update.get('written_by', '')[:40]})")
                continue
            found = _independent(update["append_verdicts"], proposing, True)
            print(f"{name}: {'VERIFIED' if found else 'not verified'}: update of {update['entity']}"
                  + (f" by {found['round']}" if found else ""))
        for entity, pending in data.get("owner_pending_aliases", {}).items():
            print(f"{name}: waits for the owner: alias {pending['alias']} of {entity}")


def _save(data):
    LEDGER.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def add(name, entities):
    research = _research(name)
    records = {record["entity"]: record for record in research.get("new_entities", []) + research.get("entities", [])}
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    present = {entity["entity"] for entity in ledger["entities"]}
    for entity in entities:
        record = records[entity]
        if not _independent(record["verdicts"], PROPOSING[name], record["status"] == "admitted"):
            raise SystemExit(f"refused: {entity} is not VERIFIED")
        if entity in present:
            raise SystemExit(f"refused: {entity} is already in the ledger")
        ledger["entities"].append(copy.deepcopy(record))
        print(f"added {entity} ({record['group']}, {record['status']})")
    _save(ledger)


def update(name, entity):
    [change] = [item for item in _research(name)["entity_updates"] if item["entity"] == entity]
    if not _independent(change.get("append_verdicts", []), PROPOSING[name], True):
        raise SystemExit(f"refused: the update of {entity} is not VERIFIED")
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    [record] = [item for item in ledger["entities"] if item["entity"] == entity]
    record["aliases"] += change.get("add_aliases", [])
    record["evidence"] += change.get("append_evidence", [])
    record["where_looked"] += change.get("append_where_looked", [])
    record["verdicts"] += change.get("append_verdicts", [])
    record["notes"] += change.get("append_notes", "")
    _save(ledger)
    print(f"updated {entity}")


def owner_alias(name, entity, date):
    """The owner's explicit yes to an alias the verify round left to the owner (owner_pending_aliases): the alias
    and its dated notes sentence. Never run without that yes, given in the owner's own words."""
    pending = _research(name)["owner_pending_aliases"][entity]
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    [record] = [item for item in ledger["entities"] if item["entity"] == entity]
    if pending["alias"] in record["aliases"]:
        raise SystemExit(f"refused: {pending['alias']} is already an alias of {entity}")
    record["aliases"].append(pending["alias"])
    record["notes"] += (f" Owner choice {date}: {pending['alias']} is admitted as the printed originator, accepting "
                        f"that a same-named payee or receiver is read as {entity}.")
    _save(ledger)
    print(f"added {pending['alias']} to {entity} (owner choice {date})")


if __name__ == "__main__":
    {"gate": lambda: gate(), "add": lambda: add(sys.argv[2], sys.argv[3:]),
     "update": lambda: update(sys.argv[2], sys.argv[3]),
     "owner-alias": lambda: owner_alias(sys.argv[2], sys.argv[3], sys.argv[4])}[sys.argv[1]]()
```

- [ ] **Step 2: Run the gate.** `C:/Python314/python.exe C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/e/research_ledger.py gate`. Record the output in the task report. Expected (the research files as the r7 round left them, checked with the same gate on 2026-09-28): 28 `VERIFIED` entity lines (4 in `funders.json`, Samson as a review entity; 24 in `debt_relief.json`, Resolve Capital as a review entity), `VERIFIED: update of NATIONAL FUNDING by r7`, `not Part E` for the GOAT and Bell Rock updates, and `waits for the owner: alias MERIT BUSINESS of Merit Business Funding`. If `RAM Payment LLC (Reliant)`, `Global Holdings LLC` or `Tayne Law Group` (owner-named, E3) is not VERIFIED, E3 stops and reports; the other tasks take whatever is VERIFIED and report the rest as waiting.

- [ ] **Step 3:** No commit (the script lives outside the repository).

---

### Task E1: The missing funders (Flexibility Capital, Merit Business Funding, Essentia Funding)

**Files:** Modify `docs/lender-registry-ledger.json` (through E0's script) and `analysis/classification_registry.py` (`OWNER_NAMED_PAYEES["confirmed_lender"]`, `:1278-1290`, after `:1289`); re-render. Create `tests/test_registry_additions_53.py`.

**Needs:** E0.

**Why:** Owner decision 3 names them after a research check. The research found each a revenue-based or MCA funder on its own site and a sales-based-financing registration; each alias reaches only its own hunt key (f00007, f00011, f00003), and no cached corpus row prints FLEXIBILIT, MERIT BUS or ESSENTIA (Fly rows only). These rows become counted lender rows (lender math, ruled). Essentia's wires carry a real-estate memo (open question 12); the verify round added a public company's 2026 10-Q describing a sale-of-future-receipts agreement with Essentia Funding. E1 takes each entry exactly as the VERIFIED research carries it, and each admitted funder joins `OWNER_NAMED_PAYEES` so the validator keeps the owner's ruling.

Merit Business Funding carries only `MERIT BUSINESS FUNDING`. `MERIT BUSINESS`, the Truist rows' printed originator and the only spelling that reaches them, waits for the owner's explicit choice (the funders verifier; open question 11): BUSINESS is a generic word, so the alias's only distinctive word is MERIT, and the matcher reads the whole row. It would count as Merit's a debit to a same-named payee and another originator's debit whose receiver, the account holder, is named 'Merit Business …', and it would read a same-named payee's credit as financing proceeds. Without it the Truist rows stay D6 review rows (unnamed after C6).

- [ ] **Step 1: Tests.** Create `tests/test_registry_additions_53.py` (drop a parametrized case whose entity is not VERIFIED, and say so in the task report):

```python
"""5.3 (owner ruling 2026-09-27): the registry entries the false-positive hunt added, in their printed forms.
Fabricated descriptors in each bank's layout; the payee names are the registry's business names."""
from __future__ import annotations

import pytest

from analysis.classification_registry import (
    LENDER_ALIASES,
    OWNER_NAMED_PAYEES,
    POTENTIAL_LENDER_ALIASES,
    REVIEW_FLAG_ENTITIES,
)
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import txn

WEEKLY = (2, 9, 16, 23)


def _weekly_states(description: str) -> set[tuple[str, str]]:
    statement = Statement(bank="Fabricated Bank", transactions=[
        txn(f"2054-01-{day:02d}", description, -300.0) for day in WEEKLY])
    return {(record.classification, record.match_method) for record in classify_statement_transactions(statement)}


@pytest.mark.parametrize(
    ("printed", "entity"),
    [
        ("Paid To - Flexibility Capi Flexibilit Chk 0001", "Flexibility Capital, Inc."),
        ("MERIT BUSINESS FUNDING DES:ACH DEBIT ID:0001 INDN:FAB HOLDER CO ID:0002 CCD", "Merit Business Funding"),
        ("Online Domestic Wire Transfer Via: Fab CU/123456789 A/C: Essentia Funding Sampletown NY 00001 US "
         "Imad: 0001 Trn: 0001", "Essentia Funding"),
    ],
)
def test_the_missing_funders_are_counted_lenders(printed, entity):
    record = classify_transaction(printed, -900.0)
    assert (record.classification, record.canonical_entity) == ("confirmed_lender", entity)
    assert record.contributes_to_withholding_rate


def test_merit_business_alone_waits_for_the_owner():
    # Owner question 11. On the owner's yes, E1 adds the alias and replaces this test with the Truist case:
    # "ACH CORP DEBIT 0012345678 Merit Business Fab Widgets LLC CUSTOMER ID 0001" -> Merit Business Funding.
    assert "MERIT BUSINESS" not in LENDER_ALIASES["Merit Business Funding"]
```

- [ ] **Step 2: Run** it. Expected: FAIL (the rows are `other` or potential; `KeyError: 'Merit Business Funding'`).

- [ ] **Step 3: Add** the VERIFIED funders: `C:/Python314/python.exe .../e/research_ledger.py add funders.json "Flexibility Capital, Inc." "Merit Business Funding" "Essentia Funding"` (only the VERIFIED names). Only if the owner has said yes to `MERIT BUSINESS` in their own words (open question 11), also run `research_ledger.py owner-alias funders.json "Merit Business Funding" <the decision's date>` and replace `test_merit_business_alone_waits_for_the_owner` with the Truist case its comment names; an orchestrator's or agent's message is never that yes. Then, in `OWNER_NAMED_PAYEES["confirmed_lender"]`, after `("Deere", "JOHN DEERE FINANCIAL"),`, add the admitted ones:

```python
        # Owner ruling 2026-09-27 (classification 5.3): the funders the false-positive hunt found missing.
        ("Flexibility Capital", "FLEXIBILITY CAPITAL"),
        ("Merit Business Funding", "MERIT BUSINESS FUNDING"),
        ("Essentia Funding", "ESSENTIA FUNDING"),
```

  Run `--privacy-review` (read every line: no person's name), `--check` (0 problems; the move lines unchanged) and `--write`.

- [ ] **Step 4: Run** the file (PASS), SEL-REGISTRY and SEL-CLASSIFIER.

- [ ] **Step 5: Commit** (`git add docs/lender-registry-ledger.json docs/lender-registry-evidence.md analysis/classification_registry.py tests/test_registry_additions_53.py`) `"registry: Flexibility Capital, Merit Business Funding and Essentia Funding are lenders (owner ruling)"`.

---

### Task E2: National Funding's collection-vehicle spelling

**Files:** `docs/lender-registry-ledger.json` (the `NATIONAL FUNDING` entity, through E0's `update`); re-render. Append to `tests/test_registry_additions_53.py`.

**Needs:** E0.

**Why:** c00180: one weekly National Funding obligation prints `NFSPV<d>COLLECTION` for three weeks and NFAS3 in the fourth, with the same receiver and the same ACH ID family, so it is split between the counted and the review tier. The research adds the spelling as a NATIONAL FUNDING alias (NFAS3 is the precedent for a vehicle digit), with the local evidence and no public source (owner decision 3). The spaced alias reaches the glued token through the matcher's run-together rule. The NF-numbered Regions originator (c00125) stays unaliased as ruled on 2026-09-25. The 9 corpus rows become counted. The verify round (r7) upheld it (the NFSPV digit is the same in all 9 rows, one statement in three copies, each also printing NFAS3 once); the update appends that verdict and cites the SEC's public full-text search page, not its API endpoint.

- [ ] **Step 1: Test.** Append:

```python


def test_national_fundings_collection_vehicle_spelling_is_national_funding():
    # The alias is read from the registry: this file never writes the vehicle's digit.
    [alias] = [alias for alias in LENDER_ALIASES["NATIONAL FUNDING"] if alias.startswith("NFSPV")]
    record = classify_transaction(f"{alias.replace(' ', '')} EDI PYMNTS 0001 FAB HOLDER", -900.0)
    assert (record.classification, record.canonical_entity) == ("confirmed_lender", "NATIONAL FUNDING")
```

- [ ] **Step 2: Run** it. Expected: FAIL (`ValueError: not enough values to unpack`).
- [ ] **Step 3: Update** the entity: `research_ledger.py update funders.json "NATIONAL FUNDING"`, then `--privacy-review` (one expected line: the alias shares no word with the name, like NFAS3), `--check`, `--write`.
- [ ] **Step 4: Run** the file and SEL-REGISTRY.
- [ ] **Step 5: Commit** (`git add docs/lender-registry-ledger.json docs/lender-registry-evidence.md analysis/classification_registry.py tests/test_registry_additions_53.py`) `"registry: National Funding's second collection-vehicle spelling"`.

---

### Task E3: The Debt relief payees

**Files:** `docs/lender-registry-ledger.json` (through E0's `add`) and `analysis/classification_registry.py` (`OWNER_NAMED_PAYEES`, a new `"debt_relief"` key after `"premium_financing"`, `:1341-1345`); re-render. Re-pin pin-ledger row 11. Append to `tests/test_registry_additions_53.py`.

**Needs:** E0, D3, D4.

**Why:** Owner decision 2 names RAM Payments / Reliant, Global Holdings (GHLLC), Tayne Law Group, Resolve Capital and well-known debt-relief brands printed by name. The research proposes 24 entities: three dedicated-account processors (RAM, Global Holdings, Forth), CFTPay, two debtor-side law firms, eight consumer settlement brands and credit-counselling agencies, three MCA debt-relief negotiators, and Resolve Capital under review (its printed originator is not tied to the negotiator, and the weekly amount also fits a reverse-consolidation advance). Every alias is a full name or a printed form; bare RAM, RELIANT, GLOBAL, FREEDOM, NATIONAL, RESOLVE, COASTAL DEBT and the generic words never are (the research's collision table: 0 collisions with every registry table and ledger alias; the verify round reproduced it). Corpus effect, measured by the research with the real matcher and reproduced by the verify round: about 336 debits become debt relief, about 149 of them potential lenders today; 34 credits keep today's path.

The verify round (r7) changed the research before E3 takes it: COASTAL DEBT is dropped (a creditor-side 'Coastal Debt Recovery' would read as debt relief; no corpus row prints it), and the notes of RAM Payment (the Reliant lineage), Global Holdings, Set Forth, the five credit-counselling agencies, Rise Alliance (it also brokers financing) and Resolve Capital (a second Palm Beach 'Resolve' firm) say only what their sources say. Its negative controls are pinned below with fabricated names: settlement words beside a funder or a law office, and RAM Capital (a different company, once an MCA funder), are never debt relief. Its expectation that Navy Federal's 'Paid To - Ram Pmt Chk …' stays a cheque is consciously updated: under the flag design step 7b reads the RAM PMT alias before the cheque rule, so a cheque payable to the processor is debt relief. The run-together forms (FORTHPAY, RAMPAYMENTS) are read through D3's index.

The research's open questions stay with the owner (open question 14): bare FORTH, the card form DELANCEY STREET NEW YORK (taken, as VERIFIED; its rows come from one bank), and the escrow refunds.

- [ ] **Step 1: Tests.** Append:

```python


@pytest.mark.parametrize(
    ("printed", "entity"),
    [
        ("RAM PMT 482913 0001", "RAM Payment LLC (Reliant)"),
        ("Electronic Withdrawal To RAM PAYMENTS", "RAM Payment LLC (Reliant)"),
        ("RAM PAYMENTS DES:RELIANT ID:0001 INDN:PAT EXAMPLE CO ID:0002 PPD", "RAM Payment LLC (Reliant)"),
        ("RAMPAYMENTS DES:PMT ID:0001 INDN:PAT EXAMPLE CO ID:0002 PPD", "RAM Payment LLC (Reliant)"),
        # a cheque payable to the processor: step 7b reads it before the cheque rule (the verifier's 'check'
        # expectation, updated for the flag design)
        ("Paid To - Ram Pmt Chk 1234", "RAM Payment LLC (Reliant)"),
        ("GLOBAL GHLLC.COM DES:FABPROGRAM ID:0001 INDN:PAT EXAMPLE CO ID:0002 PPD", "Global Holdings LLC"),
        ("Tayne Law Group", "Tayne Law Group"),
        ("FORTHPAY DES:DEPOSIT ID:0001 INDN:PAT EXAMPLE CO ID:0002 PPD", "Set Forth LLC (Forth Pay)"),
    ],
)
def test_the_debt_relief_payees_are_flagged_debt_relief(printed, entity):
    record = classify_transaction(printed, -300.0)
    assert (record.classification, record.canonical_entity, record.flagged_group) == (
        "debt_relief", entity, "debt_relief")


@pytest.mark.parametrize(
    ("printed", "state"),
    [
        # the debt-settlement verifier's negative controls: settlement words beside a funder or a law office, and
        # RAM Capital, never the RAM Payment processor
        ("FABRICATED FUNDING LLC DEBT SETTLEMENT", ("potential_lender", "recurring_fixed_debit")),
        ("FAB LAW GROUP DEBT SETTLEMENT", ("potential_lender", "recurring_fixed_debit")),
        ("LAW OFFICES OF PAT EXAMPLE", ("potential_lender", "recurring_fixed_debit")),
        ("ACH DEBIT RAM CAPITAL FUNDING", ("potential_lender", "recurring_financing_counterparty")),
        ("RAM CAPITAL", ("potential_lender", "recurring_fixed_debit")),
    ],
)
def test_settlement_words_and_ram_capital_are_never_debt_relief(printed, state):
    assert _weekly_states(printed) == {state}


def test_a_chase_ram_capital_originator_is_not_the_ram_payment_processor():
    record = classify_transaction(
        "Orig CO Name:Ram Capital Fundi Orig ID:0001 Desc Date: CO Entry Descr:Payment Sec:CCD Ind Name:Fab Holder",
        -300.0)
    assert record.classification == "potential_lender"


def test_resolve_capital_is_debt_relief_marked_unconfirmed():
    [entity] = [name for name in POTENTIAL_LENDER_ALIASES if name.startswith("Resolve Capital")]
    assert REVIEW_FLAG_ENTITIES[entity] == "debt_relief"
    record = classify_transaction(
        "Orig CO Name:Resolve Capital Orig ID:0001 Desc Date: CO Entry Descr:0001 Sec:CCD", -9000.0)
    assert (record.classification, record.review_required) == ("debt_relief", True)


def test_the_owner_named_debt_relief_payees_are_listed():
    assert [label for label, _spelling in OWNER_NAMED_PAYEES["debt_relief"]] == [
        "RAM Payments / Reliant", "Global Holdings", "Tayne Law Group"]
```

- [ ] **Step 2: Run** it. Expected: the debt-relief parametrization, the Resolve Capital test and the owner-named list FAIL; the six negative controls pass before and after (they pin what the aliases must not claim).

- [ ] **Step 3: Add** every VERIFIED debt-relief entity: `research_ledger.py add debt_relief.json "<entity>" …` with the names the gate printed as VERIFIED (all 24 on 2026-09-28). Then add to `OWNER_NAMED_PAYEES`, after the `"premium_financing"` entry:

```python
    # Owner ruling 2026-09-27 (classification 5.3): the Debt relief group. Resolve Capital, also named, is under
    # review (its printed originator is not tied to the negotiator), so it is not listed here.
    "debt_relief": (
        ("RAM Payments / Reliant", "RAM PAYMENTS"),
        ("Global Holdings", "GHLLC"),
        ("Tayne Law Group", "TAYNE LAW GROUP"),
    ),
```

  `owner_named_problems` then requires each spelling to match no known payee and to match `DEBT_RELIEF_ALIASES` (the branch for a group outside `PAYEE_STATES`). Row 11: `tests/test_build_lender_registry.py:361-367`'s key set gains `"debt_relief"`. Run `--privacy-review`, `--check` (0 problems: the 2026-09-28 prototype, rebuilt through the revised E0 gate with the real r7 verdicts, validated all 24 entities and the four funders' entries; its registry differs from the first prototype's by exactly two aliases, COASTAL DEBT and MERIT BUSINESS, both gone), then `--write`. `REVIEW_FLAG_ENTITIES` gains Resolve Capital (D4).

- [ ] **Step 4: Run** the file, SEL-REGISTRY, SEL-CLASSIFIER and `tests/test_debt_relief_group.py`.

- [ ] **Step 5: Commit** (`git add docs/lender-registry-ledger.json docs/lender-registry-evidence.md analysis/classification_registry.py tests/test_registry_additions_53.py tests/test_build_lender_registry.py`) `"registry: the Debt relief payees (owner ruling), Resolve Capital under review"`.

---

### Task E4: Samson Servicing as a review alias

**Files:** `docs/lender-registry-ledger.json` (through E0's `add`); re-render. Append to `tests/test_registry_additions_53.py`.

**Needs:** E0.

**Why:** Owner decision 3: a review alias only, unless a source ties Samson Servicing to a funder. The research found none (a Samson MCA registrant and a Samson Funding site, but no public link to the SAMSONSERVICING originator), and the verify round (r7, unresolved) found none either: the SEC's full-text search has no 'Samson Servicing', and a 2017 agreement naming a third-party servicer for a 'Samson Funding' contract says nothing about the 2026 originator (it names a guarantor, so it is listed under where_looked, never cited as evidence). So the rows (Fly only: BofA CCD, weekly, 10 accounts) are named on the Potential Lenders tab instead of 'Unidentified lender obligation', and never counted. The entity is `confirmed_lender` / review, so C1 does not route it.

- [ ] **Step 1: Test.** Append:

```python


def test_samson_servicing_is_named_on_the_potential_tab_only():
    record = classify_transaction("SAMSONSERVICING DES:ACHPAYMENT ID:0001 INDN:FAB HOLDER CO ID:0002 CCD", -900.0)
    assert record.classification == "potential_lender" and record.canonical_entity.startswith("Samson Servicing")
    assert not record.contributes_to_withholding_rate
```

- [ ] **Step 2: Run** it (FAIL). **Step 3:** `research_ledger.py add funders.json "Samson Servicing (probably Samson MCA / Samson Funding)"` (VERIFIED as a review entry), `--privacy-review`, `--check`, `--write`. **Step 4: Run** the file and SEL-REGISTRY.
- [ ] **Step 5: Commit** (`git add docs/lender-registry-ledger.json docs/lender-registry-evidence.md analysis/classification_registry.py tests/test_registry_additions_53.py`) `"registry: Samson Servicing named in the review tier"`.

---

## Part F — Versions, docs and the final verification

### Task F1: Classification 5.3 and analysis stage 22, with every pin

**Files:**
- Modify `analysis/transaction_classifier.py:88-95` (`CLASSIFICATION_VERSION` and its comment).
- Modify `webapp/artifact_cache.py:538-553` (`ANALYSIS_STAGE_VERSION` and its comment).
- Modify `webapp/templates/index.html:1662` (the script version).
- Re-pin rows 8, 9 (version) and 14 of the pin ledger.

**Needs:** every task of Parts 0-E.

**Why:** Parts 0-E change stored rows (D6 promotions, states, names, labels, a new state and new record fields), so a warm cache keyed on stage 21 would serve 5.2 rows. The two versions move together in one commit, as at 5.0, 5.1 and 5.2. `app.js` changed (C2, C10, D1), so browsers must fetch the new script.

- [ ] **Step 1: Re-pin first** (they fail until Step 2):
  - Row 14: `tests/test_flag_group_states.py:57-61` asserts `"5.3"` twice and `ANALYSIS_STAGE_VERSION == 22`, with the comment line `# 5.3/22: the false-positive release (2026-09-27): D6 skips, rule extensions, routing, naming, Debt relief.`; `tests/test_artifact_cache.py:487-496` is renamed `test_analysis_stage_version_is_pinned_at_22`, its docstring gains `The false-positive release (classification 5.3, 2026-09-27) goes 21 -> 22.`, and it asserts `== 22`; `tests/test_lender_census.py:36-37` asserts `"5.3"` (comment: `…, then from 5.2 by the 5.3 release (2026-09-27).`); `tests/flagged_payloads.py:15-17` `CURRENT_VERSION = "5.3"` (comment: `…, and 5.2 -> 5.3 with the false-positive release.`).
  - Row 9: `tests/test_webapp_reanalysis.py:1059` asserts `{"5.3"}` (comment: `…, the second one (2026-09-27) 5.2, the false-positive release 5.3.`).
  - Row 8: `tests/test_webapp_flagged_dashboard.py:712` expects `app.js?v=lender-detection-2`.

- [ ] **Step 2: The versions.**
  - `CLASSIFICATION_VERSION = "5.3"`, and its comment gains `5.3 (2026-09-27): the false-potential-lender release: D6 skips, rule extensions, the routing of unconfirmed flag payees, the D11 naming fixes, the tab's payee labels and the Debt relief group.`
  - `ANALYSIS_STAGE_VERSION = 22`, with the comment block:

```python
# 21 -> 22: LENDER-DETECTION false-potential release (2026-09-27) —
# classification version 5.3: new D6 skips, fee/NSF, cheque, card, payroll,
# mortgage and POS wording, admitted payees in the bank's field order, unconfirmed
# flag payees routed to their flag, D11 naming fixes, one Potential Lenders line
# per unnamed payee key (potential_payee_label), and the Debt relief group (a new
# state). The groups D6 no longer promotes (the skips and the $25 floor for
# unnamed payees) also leave detect.find_recurring_debits, so the CLI's
# 'Recurring fixed debits' lines, batch.py's recurring_debit_groups and the
# payload's detection.recurring_debits lose them too. Stored rows change state,
# entity and fields, so a warm cache keyed on 21 would serve them; a re-analysis
# recomputes the analysis stage from the cached reading. OCR stays cached.
# Pinned in the same change (`tests/test_artifact_cache.py`).
```

  - `index.html`: `<script src="/static/app.js?v=lender-detection-2"></script>`.

- [ ] **Step 3: Run** SEL-CLASSIFIER, SEL-REGISTRY, SEL-WEBAPP and every new file. Expected: all pass; nothing but rows 8, 9 and 14 moves.

- [ ] **Step 4: Commit** (`git add analysis/transaction_classifier.py webapp/artifact_cache.py webapp/templates/index.html tests/test_flag_group_states.py tests/test_artifact_cache.py tests/test_lender_census.py tests/flagged_payloads.py tests/test_webapp_reanalysis.py tests/test_webapp_flagged_dashboard.py`) `"versions: classification 5.3 and analysis stage 22 for the false-potential release"`.

---

### Task F2: The spec amendment and the master plan's contracts

**Files:** Modify `docs/superpowers/specs/2026-09-24-lender-detection-design.md` and `docs/superpowers/plans/2026-09-24-lender-detection.md`.

**Needs:** F1.

- [ ] **Step 1: The spec.**
  - **§2**, after the 2026-09-26 amendment: `*Amendment (owner, 2026-09-27; classification 5.3):*` with three bullets, one per owner decision of this plan's "Owner decisions" section (the release and its three parts; the twelfth group, Debt relief, and who is in it; the missing funders and Samson as a review alias). Add a Debt relief row to the §2 table: `| Flag: **Debt relief** | No; flagged, never lender math | Debt-settlement dedicated-account processors (RAM Payment / Reliant, Global Holdings, Forth, CFTPay), debtor-side debt-relief firms and law firms (Tayne Law Group, Delancey Street, Rise Alliance), credit-counselling debt-management plans |`.
  - **§3 D6**, a new clarification bullet "(2026-09-27, classification 5.3)" listing, one sub-bullet each: the channel-vocabulary rule, its left-out words and its organisation-cue guard on the payee region (0.3); the card formats (A1: labels, the Wealthsimple clause, the location suffix of Bluevine and Found; the Bluevine 'CITY, NYUS' non-match; c00148's WF 'Recurring Payment authorized on … Card' skipped on format, flagged to the owner; the brand-only residual accepted); the p2p rails (A2, with VIREMENT and the glued transfer word); the transfer templates (A3, with P2 recorded for the owner); cash, own-batch offsets, tuition and childcare (A4); savings and investing apps (A5); vendors and named non-lenders, whose vocabulary is listed verbatim and read on the payee words and, on a bounded row only, the originator segment, never the holder; on a row that is one run of words with the holder's name unknown, the vendor word must be the payee's first word (the recorded residual: a label-less row printing the receiver before a reference); DISTRIBUT* also clears owner distributions (A6); tax and government payees, and the keyword-recurrence exclusions (A7); family support (A8); owner pay and platform payouts to a person (A9); the $25 floor for unnamed payees, whose groups also leave the recurring-debit view, the CLI's 'Recurring fixed debits' lines, `batch.py`'s `recurring_debit_groups` and `detection.recurring_debits` (A10); a processor's own charge of $50 or less (A11); truncated insurers (A12); phone and cable carriers (A13). Close it with: `Every 5.3 skip reads the payee's words, never a receiver field, and none fires on a row that names financing (the shared veto: prefix-tolerant roots, so KOVOCREDIT, CAPITA and FUNDIN veto too, and so do SETTLE, CRED before IT, ORA, IBLY or a word end, and ACCEPT).`
  - **§3 D10:** `An MCA SERVICING payee carries the fixed name 'MCA servicer (funder not identified)' (5.3): the words print for two unrelated funders.`
  - **§3 D11:** the 5.3 rules: a legal form counts as a cue only after the first word; a name made only of cue words, and CO, name no organisation; the name ends at its first legal form after the first word; trailing connectors, PAID and a leading AND are dropped; bank template prefixes are removed; a Truist 'ACH CORP DEBIT' name is published only through its 16-character company field; a wire is named by its beneficiary (ending at its first cue); a card network's 'NAME, CITY, ST' line is named by the printed name alone.
  - **§4.1:** the state `debt_relief` (5.3). **§4.2:** the field `potential_payee_label` (5.3, C10). The versions line (`:183`) gains `, and "5.3" with the false-potential release of 2026-09-27`.
  - **§4.3** (the spec's numbering): step 2's returned-item wording and step 3's deposited item returned (B1); step 5's POS labels (B7: RETAIL, MOBILE and PIN PURCHASE and the French C/ACHAT, ACHAT AU DETAIL, ACHAT INTERAC, ACHAT PAR CARTE and ACHAT EN LIGNE, never a bare ACHAT) and its exception for a debt-relief payee (D3); step 6's fee wording (B1) and payroll providers and benefit administrators (B5); step 7's field-order payees (B3), the glued-digit reading (C4) and the debt-relief payee, read after no known payee matched, on debits, without the receiver fields (D3); step 8's MTG wording, the transfer to the bank's LOANS and its LOAN INTEREST (B6), and the card-payment wording (B4); step 10's cheque spellings (B2); step 11's related-party loans (B8), the routing of an unconfirmed flag payee to its flag (C1) and D10's fixed MCA SERVICING label (C9). The statement pass's D6 gains B4's issuer-alone skip.
  - **§4.5:** one Potential Lenders line per unnamed payee key, labelled by cadence and amount (C10). **§4.6:** the glued-digit rule, known-payee index only, three letters (C4); the debt-relief index of its own, which reads run-together forms (D3).
  - **§5:** the Debt relief table, `REVIEW_FLAG_ENTITIES` and its rule (review entity of a routed flag group, business type known; credits keep the potential exclusion), `FIELD_ORDER_PAYEE_FORMS` (hand-kept, validated against the ledger, debits only), the negative reading of `card_issuer_context` (B4: an issuer alias that is the payee's leading words is a card payment printed alone), and this bullet: `The D6 vocabularies of non-lender brands (savings apps, vendors, government agencies, payroll providers, telecom carriers) live in the classifier, as _PAYROLL_PATTERNS and _TRANSFER_PATTERNS already do; a name joins only after a collision check against every registry table and ledger alias prints no hit.` Line 269's sentence (unresolved entities go to `POTENTIAL_LENDER_ALIASES`) gains: `Since 5.3, the debits of a review entity of the vehicle, mortgage, lease, personal-loan or debt-relief group whose business type is known take that flag, marked unconfirmed (REVIEW_FLAG_ENTITIES); its credits keep the potential tier's exclusion.`
  - **§6:** the payload fields `review_required` (flagged positions, package items, exports) and `potential_payee_label` (records), and the version bullet `The false-potential release (2026-09-27) changes stored rows: CLASSIFICATION_VERSION = "5.3" and ANALYSIS_STAGE_VERSION 21 → 22, together.`
  - **§8.1:** twelve checkboxes. **§8.5:** the "Unconfirmed: identity under review" line, the DRP tag, and the tab's labelled lines.
- [ ] **Step 2: The master plan's contracts.** In `docs/superpowers/plans/2026-09-24-lender-detection.md`:
  - C1 (`:63`): the twelfth `FlagGroup`.
  - C2 (`:102`): `DEBT_RELIEF_ALIASES` (not a known-payee registry), `REVIEW_FLAG_ENTITIES`, `FIELD_ORDER_PAYEE_FORMS`.
  - C3 (`:142`): `AliasIndex(..., glued_digits=True)` for `_DEFAULT_INDEX` only; `match_debt_relief_payee`.
  - C4 (`:168`): the state `debt_relief`; the field `potential_payee_label`; the match methods `unconfirmed_flag_payee_alias` and `known_payee_field_order`.
  - C5 (`:205`): `review_required` last in each flagged position; `detection.potential_lenders[].funder` is the label for an unnamed payee.
  - C6 (`:226`): `review_required` last in each package flagged item.
  - C10 (`:280`): the routing rule, the Debt relief group, the generic-word additions, and the field-order validator.
  Add a dated line to each: `(Amended 2026-09-27, classification 5.3: docs/superpowers/plans/2026-09-27-false-potential-lenders.md.)`
- [ ] **Step 3: Commit** (`git add docs/superpowers/specs/2026-09-24-lender-detection-design.md docs/superpowers/plans/2026-09-24-lender-detection.md`) `"docs: the 5.3 amendment of the lender-detection spec and its contracts"`.

---

### Task F3: The transaction classification contract

**Files:** Modify `docs/transaction-classification.md`.

**Needs:** F1.

- [ ] **Step 1: Edit.**
  - After the 5.2 paragraph (`:14-16`): `Version 5.3 (2026-09-27) is the false-potential-lender release: more D6 skips, fee, NSF, cheque, card, payroll, mortgage and POS wording, admitted payees printed in the bank's field order, unconfirmed flag payees routed to their flag, D11 naming fixes, one Potential Lenders line per unnamed payee key, and the Debt relief group.`
  - "States and precedence": add `debt_relief` to the state list; "Eleven groups" becomes "Twelve groups"; the table gains `| debt_relief | debt_relief | Debt relief |`; the credits paragraph adds debt-relief payees to those that never apply to credits (their credits are escrow refunds).
  - The precedence list (`:95-151`): the same additions as the spec's §4.3 (F2), in this document's step numbering: 1 (B1), 3 (B7; D8 includes the debt-relief payee), 4 (B1, B5), 5 (B3, C4, D3), 6 (B4, B6), 8 (B2), 9 (B8, C1, C9).
  - The statement-pass paragraph (`:163-189`, the "line 169" the internal-transfer verifier asked to update): after the compensation sentence, one sentence per Part A skip group and the $25 floor, in the words of the spec's D6 bullet; and the keyword recurrence's exclusions (A7, A8).
  - The D11 paragraph (`:191-203`): the organisation cues lose CO; the 5.3 naming rules of the spec's D11 (F2); the tab's labels (C10).
  - "Normalization and registries": the glued-digit rule of the known-payee index, the debt-relief index, `FIELD_ORDER_PAYEE_FORMS` and `REVIEW_FLAG_ENTITIES`.
  - "Metric definitions": `potential_lenders_detected` counts distinct Potential Lenders lines (a named payee's entity, or an unnamed payee's label); `detection.flagged_positions` gains `review_required`.
- [ ] **Step 2: Commit** (`git add docs/transaction-classification.md`) `"docs: the classification contract at 5.3"`.

---

### Task F4: Final verification (full suite, census, NMEF probe, potential dump and families)

**Files:** none in the repository. Every output goes under `C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/` (private: the snapshots hold real payee words and figures). The corpus is the main checkout's `webapp_data`, read-only: `DATA="C:/Users/GustavoPrietodePaula/OneDrive - Capital Infusion/Desktop/Capital Infusion Projects/bankStatementAnalysis/webapp_data"`.

**Needs:** F1-F3.

- [ ] **Step 1: The full suite.** `cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe -m pytest tests -q -p no:cacheprovider > C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/fullsuite.txt 2>&1` (about 15 minutes). Expected: exactly the 16 known failures of `C:/Users/GustavoPrietodePaula/lender-research/census/failed-ld-final.txt`, and nothing else:
  - `tests/test_corpus_gate_outcomes.py::test_every_production_caller_of_the_analysis_is_classified`
  - `tests/test_extraction_quality_admission.py::test_router_implementation_preserves_phase2_extraction_quality_exclusion`
  - `tests/test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`
  - `tests/test_private_artifacts.py`: `test_checkout_symlink_outside_is_still_refused`, `test_child_symlink_cannot_escape_root[False]`, `test_child_symlink_cannot_escape_root[True]`, `test_cli_defaults_external_and_retains_source_overlap_refusal`, `test_root_symlink_into_checkout_is_refused`
  - `tests/test_stated_counts.py::test_the_observer_is_not_wired_into_any_production_module`
  - `tests/test_visual_pair_judgment.py`: `test_run_keeps_content_private_and_uses_customer_scope_and_offline_analysis`, `test_symlink_escape_and_duplicate_documents_refused`
  - `tests/test_visual_pair_judgment_review.py`: `test_artifact_symlink_cannot_escape_run`, `test_build_renders_only_bound_pdfs_with_all_states_and_held_status`, `test_optional_native_evidence_cannot_escape_run`
  - `tests/test_visual_pair_synthetic_cli.py`: `test_checkout_output_and_symlink_alias_are_refused_before_creation`, `test_default_synthetic_output_uses_configured_external_root`

  Compare the sorted FAILED lines with the file's (`diff`); any other failure stops F4. `tests/test_no_statement_hardcodes.py::test_no_exact_amount_constants_anywhere_in_analysis` in particular must pass (A10, A11).

- [ ] **Step 2: A base copy of 5.2.** `mkdir -p .../f4/base && git -C C:/Users/GustavoPrietodePaula/work/ld-fp53 archive --format=tar 0935061 analysis | tar -x -C C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/base`. (A plain copy: no worktree, no change to any checkout.)

- [ ] **Step 3: The census.** From the worktree:

```
cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe -m tools.lender_census snapshot --data-dir "$DATA" --out C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/census_before.json --code-root C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/base
cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe -m tools.lender_census snapshot --data-dir "$DATA" --out C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/census_after.json
cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe -m tools.lender_census compare --before C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/census_before.json --after C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/census_after.json --out C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/census_compare.json
```

  Expected (the prototype's corpus run, see "Expected results" below):
  - `classification 5.2 -> 5.3`, 7,241 accounts compared, 0 unmatched.
  - **Lenders gained:** GOAT ADVANCE LLC (C4) only, admitted, through no generic word. National Funding's NFSPV rows join an entity already present in those accounts, so they are no gain. Flexibility, Merit and Essentia print in no corpus row. Exit code 0.
  - **Lenders lost: none.** Any loss stops F4 and is reported with its `rows_now` states.
  - **Flagged groups:** the changes of the census table under "Expected results" (Debt relief 336 debit rows when E3 is VERIFIED; credit cards +2,659; bank loans +93; vehicle +110; personal loans +69; alternative positions +45; mortgages +3; the other groups unchanged).
  - **Withholding:** up in the 12 accounts that gained GOAT or NFSPV rows, and nowhere else; any other move is reported with its account keys.
  - **Eligible deposits:** unchanged in every account (measured: B1's reversal wording moves no counted credit in the corpus).

- [ ] **Step 4: The NMEF probe.** `C:/Python314/python.exe C:/Users/GustavoPrietodePaula/lender-research/census/nmef_probe.py C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/base "$DATA" > .../f4/nmef_before.txt` and the same with `C:/Users/GustavoPrietodePaula/work/ld-fp53` into `nmef_after.txt`. Expected (measured on the prototype): the same 9 accounts before and after, each NMEF CHECKCARD row `confirmed_lender` NMEF, and the Truist rows of those accounts `bank_loan` (6) in both. Anything else stops F4.

- [ ] **Step 5: The potential dump.** `cd C:/Users/GustavoPrietodePaula/work/ld-fp53 && C:/Python314/python.exe C:/Users/GustavoPrietodePaula/lender-research/census/potential_dump.py cache "$DATA" C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/potential_after.json`. Compare its `totals` with the hunt's 5.2 dump (`fp-hunt/corpus_potential.json`): the potential rows fall from 10,137 to 5,451 (the prototype's figure, measured again after the plan review on 2026-09-28; every research entry is VERIFIED by r7); list the ten largest remaining keys by match method and account count (key text stays in the private file; the report quotes counts and methods only).

- [ ] **Step 6: The tryout host (where access allows).** The payroll verifiers could not read the tryout host's raw rows (the hunt saw only its 14 potential keys), so the new rules were never checked against them. Where the session has flyctl access (the owner's login; `C:/Users/GustavoPrietodePaula/.fly/bin/flyctl.exe`, not on PATH), run the read-only pattern scan. Nothing is deployed and the app's code and data are never written: a small script, generated locally with every rule regular expression (`*_PATTERN`, `*_PATTERNS`) the 5.3 classifier module holds and the 5.2 module does not, is piped gzip+base64 into `/tmp` on the machine, runs from `/app` with the deployed 5.2 classifier against `/data/webapp.db` opened read-only, and is removed. It prints counts, pattern names and job-id prefixes only (the generator was checked on a fabricated jobs database on 2026-09-28).

```
C:/Python314/python.exe C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/fly_rule_scan_make.py C:/Users/GustavoPrietodePaula/work/ld-fp53 C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/base C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/fly_scan_remote.py C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/fly_scan_command.txt
```

  Wake the machine (`curl -s https://bank-statement-tryout.fly.dev/healthz`), then run the command that `fly_scan_command.txt` holds, with stdin from `/dev/null`, into `f4/fly_scan.json`. Expected: none of the patterns that claim a row before the known payee (the new `_NSF_PATTERNS`, `_REFUND_REVERSAL_PATTERNS`, `_FEE_PATTERNS` and `_PAYROLL_*` entries) finds a row that is `confirmed_lender`, `alternative_position` or a flag state at 5.2 (`counted_state_jobs` names none of them); a POS pattern may (a known payee paid by card keeps its group, D8). Part A patterns finding `potential_lender` rows are the release's purpose and are reported as counts. A hit of a pre-known-payee pattern on a counted row is reported (pattern, 5.2 state, count, job-id prefixes) and stops F4 until the orchestrator has looked at it. Without access, the report says `tryout host: not scanned (no flyctl access)`, and the orchestrator runs this scan, and `potential_dump.py jobs` by the same documented method, as the first check after the release deploys, comparing the dump with `fp-hunt/fly_potential.json` (expected: f00012 becomes debt relief, f00001 is named Samson Servicing, f00003 and f00007 become counted lenders, f00011 stays unnamed unless the owner admitted MERIT BUSINESS).

- [ ] **Step 7: The families.** The scratch script `C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/family_drops.py` (written with this plan; it prints counts, family names and key ids only):

```
C:/Python314/python.exe C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/family_drops.py snapshot C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/base "$DATA" C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/families_before.json
C:/Python314/python.exe C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/family_drops.py snapshot C:/Users/GustavoPrietodePaula/work/ld-fp53 "$DATA" C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/families_after.json
C:/Python314/python.exe C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/family_drops.py compare C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/families_before.json C:/Users/GustavoPrietodePaula/lender-research/fp-hunt/work/plan53/f4/families_after.json
```

  Expected: the per-family figures of the table below, within the tolerance it states. A family that keeps more potential rows than its "may stay" column, outside the listed keys, stops F4: report the family, the key ids and the rows' current states.

- [ ] **Step 8: Scan the commit messages.** `git -C C:/Users/GustavoPrietodePaula/work/ld-fp53 log 0935061..HEAD --format=%B` piped to `grep -nE "[0-9][0-9,]*\.[0-9]{2}|[0-9]{5,}"`: expected no output (no statement figure or long digit run in any message). A hit is reported, and rewriting a pushed message needs the owner's force-push approval.

- [ ] **Step 9: Report** to the orchestrator: the full-suite FAILED list (16), the census summary lines, the NMEF lines (states and counts only), the potential totals before and after, the tryout-host scan (counts, or 'not scanned'), and the family table. Quote no descriptor, amount, date or customer name. Check `git status` of the main checkout (clean) and of the worktree (clean after the commits).

- [ ] **Step 10:** No commit.

#### Expected results

Measured on 2026-09-27 over the corpus cache (7,241 accounts) with the scratch copy of the tree carrying Parts 0-E as this plan writes them, and F1 not applied (the copy still said 5.2). Re-measured on 2026-09-28 after the plan review, with the review's code (0.1's roots, 0.3's guard, A6's bound, B7's anchored ACHAT forms, D3's explicit run-together index) and the ledger rebuilt through the revised E0 gate from the research files' real r7 verdicts: every row of the 7,241 accounts has the same state as in the first measurement, so every figure below stands. The review's fixes move only the fabricated shapes its reviewers built, all toward review; the first anchored ACHAT form would have left BMO's 63 'ACHAT PAR CARTE' rows `other`, which the corpus scan behind B7 added. Every research entry is VERIFIED (r7); an entry E leaves out moves its own rows (for example, without E3 the 140 debt-settlement rows stay potential), and MERIT BUSINESS prints in no corpus row. Tolerance: the real run may differ by the rows of an entry E leaves out, and by nothing else.

**Potential Lenders rows:** 10,137 → 5,451 (−4,686). Lender rows lost: 0. Lender rows gained: 102 (GOAT ADVANCE LLC's 93 glued debits, 84 of them potential and 9 `other` today, and National Funding's 9 NFSPV rows). Debt-relief rows after: 336.

| Family (5.2 corpus rows) | Rows that leave the tab, and their new state | Rows that stay potential, and why |
|---|---|---|
| card_purchase_format (914) | 868: `other` 783, `pos` 85 | 46, all kept by A1's veto (an organisation or financing word): c00124 10 of 24, c00149 15, c00159 12, c00165 9 |
| credit_card_payment (828) | 712: `credit_card_payment` 654 (B3's Amex form, B4's wording), `other` 58 (B4's issuer-alone skip) | 116: c00120 (104) and c00207 (12), no card-context entry (open question 9) |
| other_non_lender (455) | 455 `other` | 0 |
| savings_or_investment (374) | 374 `other` | 0 |
| p2p_payment_app (369) | 369 `other` | 0 |
| internal_transfer (348) | 348 `other` | 0 |
| bank_fee_or_charge (264) | 264: `fee` 224, `nsf_or_return` 40 | 0 |
| other_flag_group (257) | 185: `vehicle_financing` 110, `personal_loan` 69, `bank_loan` 3 (B6's TRANSFER TO LOANS), `mortgage` 3 (B6's MTG wording) | 72, by design: c00049 FleetLogic 21 and c00059 Table Rock 12 (moved to the potential group), c00111 WOW FACTOR 18 (business type unknown), c00105 21 (not in this release, open question 10) |
| supplier_or_vendor (252) | 175 `other` | 77, as the vendor verifier measured: c00243 (3, FINANCIAL), c00060 (11, BLACKBULL), c00075 (30), c00104 (21), c00153 (12, a wire, which C7 now names) |
| check_payment (188) | 188 `other` | 0 |
| compensation_to_person (154) | 154 `other` | 0 |
| debt_settlement_or_collection (140) | 140 `debt_relief` | 0 |
| subscription_or_software (94) | 70 `other` | 24: c00102 (CREDIT in its name, the floor's veto) |
| tax_or_government_payment (72) | 72 `other` | 0 |
| payroll_or_benefits_provider (66) | 66 `payroll` | 0 |
| alternative_position_platform (45) | 45 `alternative_position` | 0 |
| child_support_or_garnishment (39) | 39 `other` | 0 |
| platform_or_processor_fee (19) | 19 `other` | 0 |
| insurance_premium (9) | 9 `other` | 0 |
| utility_or_telecom (6) | 6 `other` | 0 |
| rows of no family (5,244) | 128: `confirmed_lender` 93 (GOAT and NFSPV), `other` 22, `debt_relief` 9 (Resolve Capital, c00168), `pos` 4 | 5,116 |

Where the 5.2 potential rows went, all together: still `potential_lender` 5,451; `other` 3,141; `credit_card_payment` 654; `fee` 224; `debt_relief` 149; `vehicle_financing` 110; `confirmed_lender` 93; `pos` 89; `personal_loan` 69; `payroll` 66; `alternative_position` 45; `nsf_or_return` 40; `bank_loan` 3; `mortgage` 3.

**Census** (`tools/lender_census`, the same copy against 0935061; the 2026-09-28 re-run after the review printed the same lines): 7,241 accounts compared, 0 unmatched. Lenders gained: GOAT ADVANCE LLC only (9 analyses, 93 rows), admitted, through no generic word; National Funding's NFSPV rows join an entity those accounts already count. Lenders lost: 0. Eligible deposits: unchanged in all 7,241 accounts. Withholding: up in 12 accounts (the GOAT and NFSPV accounts), unchanged in 7,164, not comparable in 65 (as before). Flagged-group debit rows, 5.2 → 5.3:

| Group | 5.2 | 5.3 | Change | From |
|---|---:|---:|---:|---|
| credit_cards | 16,919 | 19,578 | +2,659 | B3's Chase-layout Amex payments, B4's wording |
| bank_loans | 1,414 | 1,507 | +93 | B6's own loan interest and transfers to the bank's loans |
| alternative_positions | 11,411 | 11,456 | +45 | B3's Amex loan payments |
| vehicle_financing | 2,300 | 2,410 | +110 | C1 |
| personal_loans | 3,189 | 3,258 | +69 | C1 |
| mortgages | 958 | 961 | +3 | B6's MTG wording |
| debt_relief | none | 336 | +336 | D3 with E3's payees |
| lines_of_credit, leases_rentals, floor_plan, factoring, premium_financing | 1,737; 2,405; 1,554; 114; 721 | unchanged | 0 | |

A real run that differs from these figures by more than the rows of an entry E left out stops F4 and is reported.

## Revision after the plan review (2026-09-28)

The plan review (changes needed: one critical, three important, three minor findings) and the verify round of both research files (r7, each approved with changes) are applied:
- **Privacy (critical).** C6 had quoted a tryout-host customer's business name (a real receiver) and echoed it in a test descriptor; both now carry fabricated words, and the unpushed plan commit was amended so no commit holds the name. Two descriptors derived from real payees (A6's manufacturer row, and C5's CORP-first row and C8's city) were replaced as well. A word scan (plan words of six or more letters that the private sample dumps print and that no tracked file at `0935061` prints; `.../work/plan53/rev/privacy_scan.py`) now returns 20 words, all brand, funder, processor, bank or template words: ACHPAYMENT, ALINEA, BKOFAMERICA, CHECKG, DATAPAY, ENVOYE, ESSENTIA, FLEXIBILIT, FOODSERVICE, GREENLIGHT, HEALTHEQUI, HEALTHEQUITY, IDEALOAN, MONEYLINE, PAYONEER, PAYROLLTAX, SAMSONSERVICING, SETTLMT, SMARTSAVE, THUMBTACK.
- **0.1:** the card verifier's REQUIRED roots SETTLE, CRED(?=IT|ORA|IBLY|\b) and ACCEPT, with the reviewer's rows in the veto test, A1 and A2.
- **0.3:** the channel rule carries the card veto's organisation-cue guard on the payee region; the reviewer's four template-keyed rows stay in review.
- **A6:** the originator-segment fallback reads only a bounded row, and on a run of words with the holder unknown the vendor word must come first (the Regions and Bluevine shapes are must-stay controls).
- **B7:** ACHAT only in the corpus's card forms (C/ACHAT, AU DETAIL, INTERAC, PAR CARTE, EN LIGNE), with an ACHAT DE CREANCES control.
- **A10, F1, F2:** the floor's groups leave the recurring-debit view, the CLI lines, the batch metric and the payload (a test and the two notes). **F4:** Step 6 scans the tryout host's saved rows where access allows, or right after the deploy.
- **D3, E3:** the debt-relief index reads run-together forms explicitly (FORTHPAY, RAMPAYMENTS), and the debt-settlement verifier's negative controls are pinned; its cheque-to-RAM expectation is consciously updated to debt relief.
- **Part E:** the r7 verdicts are in the research files (every entry VERIFIED; `verify_round` in each file), E0's gate accepts a review entity on any independent verdict, MERIT BUSINESS waits for the owner (E0's `owner-alias`), C4 commits the aligned GOAT and Bell Rock notes, Essentia gained the 10-Q, Samson's evidence no longer cites a filing that names a guarantor, COASTAL DEBT is dropped, and the debt-relief notes say only what their sources say.
- **Re-measured:** the three selections and every new file pass (2,251); every corpus row keeps the state of the first measurement, so F4's expected figures stand (see "Expected results").

## Self-review (2026-09-27)

- **Coverage.** Every family of `digest_families.md` maps to a task in the families table, every REQUIRED verifier change is applied there, and every optional change carries a one-line decision. The naming and registry side items map to C1-C10 and E1-E4. The structural misfires added and left out are listed with reasons. The three owner decisions: (1) Parts A, B and C; (2) Part D and E3; (3) E1, E2, C4 and E4.
- **Credits.** No task changes a credit's treatment except B1's deposited item returned under a stop payment (a reversal, as RETURNED DEPOSIT already is) and the owner-ruled funders of E1/E2, whose funding credits become financing proceeds when the corpus prints them (it does not). C1 keeps the routed aliases in the potential table, B3 and D3 read debits only.
- **Prototype.** Every code block of Parts 0-E ran in a scratch copy of the tree (`.../work/plan53/protorepo`): the three selections and every new file pass (2,211 tests; 2,251 after the plan review). The copy's full suite fails only the 16 known tests plus six that need a git checkout, once A10's and A11's constants are whole numbers (the one real finding of the full run, now in the plan and in the guards list). The corpus figures of F4's "Expected results" come from that copy.
- **Choices where the sources disagreed**, each with its reason in the task: debt relief is its own table and index, not a known-payee registry (the research's verified hazard); the tab's labels leave each ledger row's tag unchanged (the row shows its own amount); C4 keeps the verifier's three-letter condition, so Bell Rock stays unreached (open question 13); E4 is Samson, and the Atlas/RTS card-context entries are not in this release (no research entry).
- **Names across tasks.** `_names_financing`, `_payee_region`, `_originator_segment`, `_payee_words_are_bounded`, `_record_payee_tokens`, `_unknown_entity_for_text`, `REVIEW_FLAG_ENTITIES`, `ROUTED_REVIEW_GROUPS`, `match_debt_relief_payee`, `potential_payee_label` and `review_required` are each defined in the task that first uses them, and later tasks use the same spelling and signature.
- **Privacy.** Every test descriptor is fabricated in the bank's format, with whole-dollar amounts and 2054 dates. The plan quotes no statement value, account number, date or customer name; the payee names it uses are funders', processors', banks' and debt-relief firms' business names. (The first draft broke this once, in C6; the plan review caught it, and the revision above records the fix and the word scan that now checks it.) The NFSPV vehicle digit is never written: E2 reads it from the research file by script, and its test reads it from the registry.
- **Placeholders.** None: every step names its files, anchors, code, commands and expected result. Part E takes only VERIFIED entries; since 2026-09-28 the research files carry the verify round's r7 verdicts, and MERIT BUSINESS waits for the owner.

