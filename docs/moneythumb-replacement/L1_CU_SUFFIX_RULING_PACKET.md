# L-1 / CU-SUFFIX ruling packet (batch 9, cell `L1INV`) — corrected after adversarial review

READ-ONLY investigation. No production file changed, nothing registered, nothing moved.
Every number below is produced by a committed instrument under `tools/l1_*.py`, run over the
run of record `discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`
and its cold cache `.claude/recovery/webapp_data_train8_cold`, and reproduces from them.
No printed value, name, account number, amount or date appears anywhere in this packet or in
the instruments: the tables count shapes, gate names, sections, closures and content sha16s.

**This is the second version.** The first was reviewed independently
(`docs/moneythumb-replacement/reviews/BATCH9_L1INV_REVIEW.md`), every published figure
reproduced to the digit, and the verdict was UNSOUND: two of the load-bearing claims meant
something other than what they said, and both erred in favour of the answer the packet
recommended. The instruments have been corrected, everything was re-measured, and §11 is the
ledger of what each correction cost. **The headline moved a long way and it moved DOWN.**
Read §11 before §8 if you read the first version.

Instruments and the commands that produced every table:

```
python -m tools.l1_census            --census-dir docs/moneythumb-replacement/census_batch9 \
                                     --rows <run>/rows.csv --data-dir <cold cache>
python -m tools.l1_structure_census  --census-dir docs/moneythumb-replacement/census_batch9 \
                                     --data-dir <cold cache>
python -m tools.l1_structure_census  --pinned --rows <run>/rows.csv --data-dir <cold cache> \
                                     --census-dir docs/moneythumb-replacement/census_batch9
python -m tools.l1_split_prototype   --census-dir docs/moneythumb-replacement/census_batch9 \
                                     --data-dir <cold cache>
python -m tools.l1_split_prototype   --idle-siblings \
                                     --census-dir docs/moneythumb-replacement/census_batch9 \
                                     --data-dir <cold cache>
```

---

## 0. The headline, before the detail

1. **The L-1 rule is not what blocks most of the 176 — but the other half is not free
   either.** Of the 176 CU-suffix documents, **65 print two or more POSTING account
   sections**, **79 print exactly one**, and 32 yield no located partition. That much
   survives. What does NOT survive is the conclusion drawn from it. Publishing the 79 means
   treating every other printed section as an idle sibling, and under the RATIFIED
   idle-sibling rule (`analysis/symitar.py` 13-45, applied section by section by calling that
   module's own predicates) **not one of those documents qualifies**: of their 103 sibling
   sections, 4 print the ratified declaration, 0 satisfy the yield-only arithmetic, and
   **26 documents carry a sibling that POSTED a dated row and declares nothing at all**.
   The 79 are not a no-ruling population. They are the same L-1 question arriving through a
   door marked "no ruling needed" (§4).
2. **The population shares an architecture, not a family.** Keyed on all seven mechanisms at
   once there are **62 distinct structural families over 214 documents**; 39 of them have
   three or more members and cover 183. What they DO share is a small closed set of
   MECHANICS: 4 boundary mechanisms, 9 roll-up caption classes, 5 identity forms, 4 equation
   forms, and grid shapes built from 13 column tokens. That is the shape `core_processor_*`
   already has for banks — one shared template family with per-issue markers — and not 37
   readers. This finding is unchanged by the review and by the re-measurement (§3).
3. **Validating each account on its own is demonstrated on two documents, not on
   twenty-three.** The corrected prototype splits at the printed boundaries and hands each
   section to the EXISTING `reconcile` + `compute_average_daily_balance` unchanged, with the
   section's own stated counts, totals and daily balances in hand and the production
   source-coverage check applied. **29 of 392 sections close. 2 documents close on every
   located section** — both `FAM:guardian_cu_statement_summary`, both with two or more
   posting sections, both with the enumerating table's own CLOSING column reproducing every
   section's closing. The first version reported 97 / 23 / 12 and its own L-1 floor as 11
   documents and 6 with the oracle; the true figures under its own stated conditions are
   **2 and 2** (§5, §11).

**Nothing in §5 is a lower bound any more.** The first version told the reader three times to
treat every number as a floor. For the class the review found, that instruction was exactly
backwards: a section that "closed" having read nothing at all is an upward artefact, and 23
sections were doing it.

---

## 1. Population

`tools/l1_census.py`. 214 documents, named by content sha16 in the instrument's own output.

| band | census groups | documents |
|---|---:|---:|
| `CU-SUFFIX` (the census `FAM-CU-SUFFIX-CORE` reservoir) | 37 | 176 |
| `DECL-L1-CANDIDATE` (huntington, community_section, navy_federal, capital_one, consumers) | 5 | 36 |
| `ATB` (`WH:atb`, consolidated statements) | 1 | 2 |
| **total** | **43** | **214** |

### 1.1 The `DECL:*` refusals — each reader's OWN gate, re-run

Not repeated from the batch-7 escalation: each reader's gate was re-run on the run-of-record
cached text, and a document is `L-1-refused` only where the gate that fires is the one whose
comment in that module cites the single-account schema. 36 declines, 36 confirmed by calling
the reader's own `parse` entry point.

| group | reader | docs | declines confirmed | L-1-refused | other | gates that fired |
|---|---|---:|---:|---:|---:|---|
| `DECL:huntington` | `huntington` | 12 | 12 | **4** | 8 | `_LINE_OF_CREDIT_RE` ×4; grammar (period/summary/blocks/validate) ×8 |
| `DECL:community_section` | `community_section` | 9 | 9 | **7** | 2 | `len(parsed)!=1` (>1 posting section) ×7; `len(parsed)!=1` (0 posting sections) ×2 |
| `DECL:navy_federal` | `navy_federal` | 6 | 6 | **4** | 2 | `_checking_account` (>1 checking product) ×4; downstream ×2 |
| `DECL:capital_one` | `capital_one` | 6 | 6 | **6** | 0 | emergent — the nine-cell summary pattern does not match ×6 |
| `DECL:consumers` | `consumers` | 3 | 3 | **3** | 0 | `_primary_checking_section` (CONS-L1) ×3 |
| | | **36** | **36** | **24** | **12** | |

This reproduces the WAVE2 batch-7 escalation's counts (4 / 7 / 4 / 6 / 3) from evidence.

**`capital_one` is the exception, and the first version described it backwards.** It said
`_native_summary` matches ONE of the several summary blocks these documents print. A search
that matched one of several would not refuse anything — it would publish the first one. The
instrument now calls the module's own helpers and counts what they return:

| fact, over the six declining documents | documents |
|---|---:|
| print more than one summary-block prefix | 6 |
| the NINE-CELL `_native_summary` pattern MATCHED | **0** |
| the transaction-detail caption is present | 6 |
| `_native_transactions` returned at least one row | **6** |
| rows returned — min / median / max | 1 / 28 / 41 |

The refusal is the ABSENCE of a match on a strict nine-cell pattern (opening figure, cycle-day
count, credit count and total, debit count and total, an averaged balance, a service charge,
closing figure, in that printed order). It leaves `beginning_balance` and `ending_balance`
unset and the parser returns None — **while its transaction grammar, anchored on a different
caption entirely, harvests rows spanning the document's several accounts.** That is a
materially worse fragility than the one first described, and it points the wrong way: anyone
who relaxes or re-orders that pattern to match one of the blocks gets a statement whose stated
summary comes from ONE account and whose ledger comes from ALL of them. It is recorded as
`capital_one:emergent`, never as a gate the module contains.

### 1.2 The pinned corpus

109 pinned paths, all on disk. 80 are in the run of record; **29 are not in the run at all**
(measured, not assumed — their content sha appears in no row). Those 29 are NOT surveyed
structurally: this instrument does not reach around `ocr/native_text.py`'s ladder to read them
a second way (`tests/test_native_rung_parity.py` forbids it, and a structure read through
different text would not be the structure production read). The pinned structural finding
below therefore covers 80 documents, and the 29 are a named gap — the same 29 the branch
privacy scan cannot scan against, which is stated in §10 rather than left in a JSON file.

Pinned documents claimed by a reader that carries an L-1 rule today — **10**, and this is the
regression surface any publication-model change must clear (a registration id is not a module:
`community_section` publishes under `community_section`, `dakota_west` and `mission_valley`,
and it is `dakota_west` that holds a pinned document):

| parser_id | module | pinned documents | sha16 |
|---|---|---:|---|
| `capital_one` | `capital_one` | 4 | `393547C0407F1A87` `4FC7799B53D746E8` `C5C39D466437059F` `C6D4DAC2278D866F` |
| `navy_federal` | `navy_federal` | 4 | `4A08F2D63DC07545` `70F228655AC4E584` `92D121974762A444` `CA5A47F1FE231B62` |
| `consumers` | `consumers` | 1 | `05E246C0ED6678E6` (the CONS-L1 / CONS-HARDCODE document) |
| `dakota_west` | `community_section` | 1 | `F748A799FDC7F25E` |

`symitar` and `atb` claim no pinned document. `huntington` claims none.

Structurally, **12 of the 80 surveyed pinned documents print two or more posting sections** —
but the strength of that finding differs by mechanism and is reported that way, because the
weakest mechanism over-collects:

| how the partition was established | pinned documents | weight |
|---|---:|---|
| `rollup-oracle` (the document enumerates its accounts with balances) | 4 | strong |
| `section-identity` (headings carry their own identity, no oracle) | 1 | strong |
| `section-equation-scan` (opening figures only) | 7 | WEAK — treat as unproven |

`05E246C0ED6678E6`, the known CONS-L1 pinned document, is in the strong class, which is a
corroboration of the probe rather than a new finding. **12 is the number; §7 of the first
version printed 16 in its regression surface, which reproduced from nothing (MAJOR-1).**

---

## 2. Root cause

`analysis/schema.py::Statement` carries ONE account: `account_name`, `account_number`, one
`transactions` list, one opening, one closing, one daily-balance series. A member statement
prints several. Publishing one of them and silently dropping the others is a correctness
defect — the rule MASTER_PLAN calls L-1 — so a reader that recognises such a document
refuses it. `analysis/symitar.py` (lines 13-45) carries the one ratified exception:
a DORMANT deposit sibling — the printed declaration `_DORMANT_RE`, or a section whose every
posting is the account's own dividend, credited rather than paid out, whose own arithmetic
closes, whose last printed balance equals the ending balance the document's own summary states
for that account, and (where the platform's six-figure equation row is printed) whose skipped
postings are accounted for by that row's own dividend column with its deposit column at zero —
is not a second ledger and may be skipped. Both skips are silent today; the visible surface
(SIBLING-OMISSION-SURFACE) was carded in batch 8 and is not built.

The root cause is therefore **not extraction and not arithmetic**. §5 measures that the
arithmetic closes per account on two documents the platform refuses today. It is a
**publication-model gap**: the schema cannot say "this statement covers three accounts", the
payload cannot say "a section existed and was not published", and no rule says which account
is THE account. What the re-measurement adds is that the gap is wider than the first version
made it look: the arithmetic closes far less often than reported, and the ratified exception
covers far less of the population than assumed.

---

## 3. Structure — what varies, and what is shared

`tools/l1_structure_census.py`, 214 documents. **This section survived the review and the
re-run**, with one correction inside it, named at §3.3.

### 3.1 How account boundaries are established from printed evidence

| mechanism | documents | is there a cross-account ORACLE? |
|---|---:|---|
| `rollup-oracle` — the document enumerates its accounts with a balance each, and each enumerated identity reappears as a section heading | **103** | **YES** — the roll-up states figures the sections must reproduce |
| `section-identity` — no enumerating table, but each section opens with a heading carrying its own identity | **38** | no — the partition is printed, the cross-check is not |
| `section-equation-scan` — no identity; boundaries inferred from the sections' own opening figures | **35** | no — WEAKEST, diagnostic only |
| `none` — no partition established; fails closed | **38** | n/a |

Fail-closed reasons for the 38: `no-rollup-caption` 22, `rollup-enumerated-but-no-section-reappearance`
11, `rollup-enumerates-one-account` 5. The last five are a correct answer, not a failure: the
document really does cover one account.

**Answer to "whether account boundaries can be established from explicit statement evidence":
yes for 141 of 214 (103 + 38) from printed identity, of which 103 also carry the oracle.**

### 3.2 The shared mechanics (closed sets)

| mechanism | distinct values measured | leading values (documents) |
|---|---:|---|
| roll-up caption class | 9 (+ none) | `account_summary` 52, `summary_of_accounts` 42, `statement_summary` 26, `balances_at_a_glance` 11, `account_balances` 8, `accounts_summary` 5, `your_account_summary` 4, `summary_of_deposit_account_activity` 4; none 62 |
| roll-up COLUMN caption | 3 (+ none) | `type_prev_dep_wd_end` 15, `type_begin_end` 8, `begin_end` 7; **none 184** |
| identity form | 5 (+ none) | `product_name_only` 71, `bare_digits` 54, `suffix_word` 8, `paren_digits` 7, `id_word` 1; none 73 |
| equation form (modal section) | 4 (+ none) | `open_close_pair` 114, `open_only` 34, `explicit_six_figure` 5, `explicit_equation` 4; none 57 |
| grid column shape | ~49 distinct orderings, built from **13 column tokens** | every ordering ends in a balance column; they differ only in how the movement columns before it are named and in which date columns open the row |

**The roll-up COLUMN caption row is the one to read twice. Only 30 of 214 documents print
one at all.** On the other 184 the enumerating table prints a name and some figures and never
says which figure is the opening and which is the closing. The first version of the prototype
assumed the first figure opened the row; one issue in this population prints the ENDING figure
there, and that assumption is what produced the false closures §11 describes. It is now a
fail-closed condition (§6.5) and not a detail.

### 3.3 Per-section facts (442 located sections)

| fact | sections | share |
|---|---:|---:|
| prints its own opening AND closing | 208 | 47.1% |
| prints its own ledger grid header | 273 | 61.8% |
| carries at least one dated row | 327 | 74.0% |
| prints its own counts / totals | 79 | 17.9% |
| **prints its own daily-balance TABLE** | **24** | **5.4%** |
| prints an explicit no-activity declaration | 31 | 7.0% |

**Corrected in this version.** The first said 75 sections (17.0%) print their own daily
balances. Its predicate matched the caption of the AVERAGED daily balance a summary block
prints, which is one figure and not a table. The predicate now requires the table's rows, and
the honest figure is 24. The consequence for the ADB is the same in kind and worse in degree:
**a per-account ADB rests on a reconstructed daily series, not on bank-printed daily evidence,
for 95% of these sections.**

### 3.4 The roll-up as an oracle

| oracle strength | documents |
|---|---:|
| the roll-up states TWO balances per account (opening AND closing) | 60 |
| the roll-up states at least ONE balance per account | 117 |
| the roll-up closes with a cross-account total row | 37 |
| the roll-up prints a COLUMN CAPTION saying which figure is which | **30** |

### 3.5 The L-1 exposure, counted at both thresholds

Posting sections per document, where a posting section carries two or more dated ledger rows —
the threshold the census used:

| posting sections | CU-SUFFIX | DECL-L1-CANDIDATE | ATB | all |
|---:|---:|---:|---:|---:|
| 0 | 32 | 13 | 2 | 47 |
| 1 | 79 | 7 | 0 | 86 |
| 2 | 48 | 9 | 0 | 57 |
| 3 | 13 | 7 | 0 | 20 |
| 4 | 2 | 0 | 0 | 2 |
| 5 | 2 | 0 | 0 | 2 |
| **>= 2 (the L-1 population)** | **65** | **16** | **0** | **81** |

The same census at the threshold the packet's own fail-closed condition states — "no section
with **a dated ledger row** may be dropped", one row, not two:

| posting sections | CU-SUFFIX | DECL-L1-CANDIDATE | ATB | all |
|---:|---:|---:|---:|---:|
| 0 | 29 | 13 | 2 | 44 |
| 1 | **54** | 5 | 0 | 59 |
| 2 | 68 | 10 | 0 | 78 |
| 3 | 21 | 1 | 0 | 22 |
| 4 | 2 | 7 | 0 | 9 |
| 5 | 2 | 0 | 0 | 2 |
| **>= 2** | **93** | **18** | **0** | **111** |

**The 79 and the 81 are threshold artefacts, and the threshold chosen was the looser one in
both directions.** At the condition's own threshold the single-posting population is 54 and
the multi-posting population is 111. Both pairs are printed here because the ruling has to be
made on one of them and the choice is the owner's, not a cell's.

### 3.6 How many share ONE structural family

**62 distinct fine-grained families over 214 documents; 39 with three or more members
covering 183.** (63 / 39 / 182 in the first version; the difference is the daily-table
correction of §3.3, which moves a component of the family key.) The largest:

| n | census groups | family key |
|---:|---|---|
| 13 | `DECL:huntington`, `FAM:rbfcu_business_member_statement` | `none then no-rollup then no-identity then no-equation then no-grid then no-daily then no-total-row` |
| 9 | `FAM:mountain_america_cu_dot_leader` | `rollup-oracle:bare_digits then account_summary then bare_digits then open_close_pair then post_date\|desc\|amount\|balance then no-daily then total-row` |
| 8 | `FAM:greater_nevada_cu`, `FAM:security_service_fcu_asterisk_sections` | `section-equation-scan then no-rollup then no-identity then open_close_pair then no-grid then no-daily then no-total-row` |
| 8 | `FAM:space_coast_cu_member_statement` | `rollup-oracle:product_name_only then statement_summary then product_name_only then open_close_pair then txn_date\|eff_date\|desc\|money_in\|money_out\|balance then no-daily then no-total-row` |
| 7 | `FAM:cu_summary_of_accounts_date_posted` | `rollup-oracle:product_name_only then summary_of_accounts then product_name_only then open_only then date\|desc\|debit\|credit\|balance then no-daily then no-total-row` |
| 7 | `DECL:community_section` | `rollup-oracle:product_name_only then summary_of_accounts then product_name_only then open_close_pair then post_date\|desc\|debit\|credit\|balance then daily then no-total-row` |
| 6 | `FAM:cu_idaho_equation_summary` | `section-identity:account_no_mask then no-rollup then no-identity then open_only then eff_date\|post_date\|desc\|deposit\|balance\|withdrawal then no-daily then no-total-row` |
| 6 | `FAM:guardian_cu_statement_summary` | `rollup-oracle:suffix_word then statement_summary then suffix_word then open_close_pair then txn_date\|post_date\|desc\|withdrawal\|deposit\|balance\|date then no-daily then total-row` |
| 6 | `DECL:capital_one` | `section-equation-scan then account_summary then no-identity then open_close_pair then date\|desc\|deposit\|credit\|withdrawal\|debit\|balance then no-daily then no-total-row` |

**The honest answer to Gustavo's question:** the 176 do NOT share one structural family — a
census group and a structural family are very nearly the same partition, and two institutions
almost never coincide. They share one structural ARCHITECTURE: enumerate → identify → bound →
reconstruct → validate, with each stage drawing from a closed vocabulary of a handful of
printed forms. A shared template module with per-issue markers is therefore the right shape;
37 readers is not.

### 3.7 Three populations the condition list has to cover, measured

| population | documents |
|---|---:|
| enumerating tables that list a facility rather than a deposit account | **19** |
| ... of them with two or more posting sections | **4**, all `FAM:goldenwest_cu_member_account_statement` |
| ... of them ALSO printing a cross-account total row | **7** |
| enumerating tables naming TWO denominations (`FAM:community_savings_bc`, 12 sections) | **4** |
| documents printing a cross-account total row at all | 43 |
| documents resolving two LOCATED sections to the same identity token | **0** |
| enumerating tables printing the same identity token twice | 44 |

That row class is the one the first version had no condition for at all, and it is not latent:
**7 documents print both a facility row and a cross-account total**, and a total that includes
a facility can never be reproduced by summing the deposit sections. Nor does it bite on nothing:
**4 of the 19 carry two or more posting sections, and all four are
`FAM:goldenwest_cu_member_account_statement`** — the family with the most accounts per document
in this population, and the family a Stage-2 implementation would reach for next. The
vocabulary's completeness is a table in the instrument's own output and not a sentence here:
ten classes were tried, three are counted, and the classes that fire and are NOT counted are
named with the reason (a brand word alone is not proof of an account row, and a debit card is
the access device of a deposit account rather than a facility — counting it would put 11
further documents into a condition that must not hold them). The identity condition, by
contrast, is satisfied on this population — 0 documents resolve two sections to one token —
and the residual hazard there is the locator, not the condition.

---

## 4. The 79 single-posting documents, against the RATIFIED idle-sibling rule

`tools/l1_split_prototype.py --idle-siblings`. This is the section the first version did not
have, and it is the reason its Stage 1 cannot be built as scoped.

Publishing a single-posting document means treating every OTHER printed section as an idle
sibling. `analysis/symitar.py` 13-45 licenses that on exactly two printed grounds and the
instrument applies both by calling that module's own code — `_DORMANT_RE` for the declaration,
`_yield_only` for the arithmetic with its summary-equality test. A sibling satisfies the rule
AS WRITTEN under one of those two and under nothing else.

At the census's threshold (a posting section is one with two or more dated rows):

| the single-posting population | documents |
|---|---:|
| documents with exactly one posting section | 86 |
| ... of them `CU-SUFFIX` — which reproduces the first version's 79 | **79** |

| their 103 sibling sections, classified | sections |
|---|---:|
| print the ratified declaration | **4** |
| satisfy the yield-only arithmetic as written | **0** |
| POSTED a dated row and declare nothing | **30** |
| empty and silent — no declaration of any kind | 62 |
| declare idle in some other wording | 7 |

| the Stage-1 question | documents |
|---|---:|
| **EVERY sibling satisfies the ratified rule as written** | **0** |
| carry a sibling that POSTED and declares nothing (the L-1 defect itself) | **26** (24 `CU-SUFFIX`) |
| `CU-SUFFIX` documents carrying at least one sibling that fails the rule | **63** |
| no sibling section LOCATED at all — which is not the same as having no sibling | 16 |

At the packet's own third condition instead (one dated row, not two): 59 documents have
exactly one posting section, 54 of them `CU-SUFFIX`; their 52 siblings are 50 empty-and-silent
and 2 other-wording; **0 satisfy**. At that threshold a sibling has no postings at all, so
`_yield_only` cannot apply by construction and the printed declaration is the only licence
left — and it is printed on none of them.

**What this means for the recommendation.** "Publish the 79, treating every other section as
an idle sibling under the ratified rule" would, on this evidence, silently drop a section that
printed activity on **26** documents and extend a ratified rule to the rest on no printed
evidence at all. The population that needs NO ruling is **0 documents**. There are three
separable populations here and they must not be merged:

| population | documents | what it needs |
|---|---:|---|
| every sibling satisfies the ratified rule | **0** | nothing — it is empty |
| every sibling is empty and silent, or declares idle in another wording | 44 (of the 86) | ruling (5): may the ratified rule be GENERALISED to a declaration this population does print, or to arithmetic on an empty section |
| a sibling POSTED and declares nothing | 26 | the L-1 ruling itself — these are multi-account documents that the two-row threshold hid |
| no sibling section located | 16 | a boundary-layer answer first; "not located" is not "not there" |

---

## 5. Expected safe gain — RE-MEASURED

`tools/l1_split_prototype.py`. For every located section: the section's own printed opening and
closing (or, where the enumerating table prints a COLUMN CAPTION naming its columns, that
account's row), a ledger reconstructed by a self-validating balance-chain walk, the section's
OWN stated counts, totals and daily balances where it prints them, and then
`analysis/reconcile.py::reconcile` and `analysis/adb.py::compute_average_daily_balance` called
**unchanged**, the ADB with the SECTION's text as its source so the production
`posting_dates_cover_source` check applies.

**A section CLOSES when all of these hold:** its chain is not empty; no dated row inside the
span the chain walked is unaccounted for; its boundary was PRINTED rather than inferred; the
evidence it prints about itself was readable and was fed; and both oracles return ok.

### 5.1 What was offered

| measure | value |
|---|---:|
| documents in the population | 214 |
| sections LOCATED by the structure census | **442** |
| documents printing no resolvable period | 27 |
| ... the sections they carry, which are never offered | 77 |
| pseudo-sections standing for those documents, one each | 27 |
| **objects the validator was offered** | **392** |

That is the reconciliation the first version never printed: 442 − 77 + 27 = 392, and the
refusal class named "27 sections" is 27 DOCUMENTS (MINOR-1).

### 5.2 The closure ladder — each rung a review finding

| rung | sections |
|---|---:|
| the walk reached the section's own printed closing | 109 |
| ... arriving with an EMPTY chain, the section printing no dated row — TRIVIALLY IDLE, never a closure | **21** |
| ... arriving with an EMPTY chain over PRINTED dated rows — the false closure | **23** |
| non-empty chain | 65 |
| + no dated row unaccounted for INSIDE the span the chain walked | 54 |
| + boundary PRINTED rather than inferred (condition 1) | 48 |
| + its own stated counts / totals / daily balances readable and fed | 48 |
| + `reconcile.ok` | 37 |
| + `adb.ok`, source-coverage check applied (condition 6) | **29** |
| + nothing dated printed AFTER the chain reached the closing (a STRICTER bound) | **16** |

The last rung is reported and is not a gate. A section's span runs to the next section
heading, so the LAST section of a document runs to the end of the document and carries its
trailing tables, and the dated-row pattern cannot tell a trailing fee table from a truncated
ledger. The production check for a ledger that stops early is `posting_dates_cover_source`,
which is deliberately quiet on that furniture and IS applied above, and the section's own
printed counts are the second. **29 and 16 are the two honest bounds and both are in the
table.**

### 5.3 Headline

| measure | value |
|---|---:|
| **sections that CLOSE** | **29** |
| ... and print nothing dated after their own chain | 16 |
| sections that are TRIVIALLY idle (no row printed, nothing read) | 21 |
| **documents whose EVERY LOCATED section closes** | **2** |
| ... of those, documents with two or more located sections | 2 |
| ... whose table's own CLOSING column reproduces every section's closing | **2** |

Both are `FAM:guardian_cu_statement_summary` (`7C7956EB5E93DB1D`, `E38FA786106F752E`).

**And the 2 is a floor of a floor.** A trivially idle section is a class here and never a
closure, so a document carrying a genuinely DORMANT sibling cannot reach "every located section
closes" however well its posting sections reconstruct. Allowing such a section to be OMITTED
rather than counted — which is exactly what the ratified idle-sibling rule licenses, and
exactly what ruling (5) is about:

| measure | documents |
|---|---:|
| every section either CLOSES on the corrected test or is trivially idle | **8** |
| ... their census group | `FAM:guardian_cu_statement_summary`, all of them |
| ... carrying two or more posting sections | 2 |
| ... with the table's own closing column reproducing, over the sections that would be PUBLISHED | **8** |

So the demonstrated population is **2 today and 8 under a ruling that lets a dormant sibling be
omitted** — on one family, with the table reproducing on all eight. That is the number that
sizes ruling (5), and §9.1 states it there.

**MINOR-6, stated rather than implied: "every LOCATED section" is not "every PRINTED
section".** 38 documents have no located partition at all and 11 more enumerate accounts none
of which reappear as a heading. A document whose third account the boundary layer missed
cannot fail here, because it was never offered. The figure is a statement about the sections
this probe found.

### 5.4 By boundary mechanism

| boundary | docs | sections offered | closed | docs fully closing | table reproduces |
|---|---:|---:|---:|---:|---:|
| `rollup-oracle` | 103 | 212 | 19 | 2 | 2 |
| `section-identity` | 38 | 89 | 10 | 0 | 0 |
| `section-equation-scan` | 35 | 84 | 0 | 0 | 0 |
| `none` | 38 | 7 | 0 | 0 | 0 |

`section-equation-scan` closes nothing, which is the packet's own first condition doing its
work rather than an accident: an inferred boundary is refused before the validator sees it.

### 5.5 The L-1 question in its own terms

| band | docs with >= 2 posting sections | every located section closes | table reproduces |
|---|---:|---:|---:|
| `CU-SUFFIX` | 65 | **2** | **2** |
| `DECL-L1-CANDIDATE` | 16 | 0 | 0 |
| `ATB` | 0 | 0 | 0 |
| **total** | **81** | **2** | **2** |

At the one-dated-row threshold: 111 documents, of which **2** close on every located section.

### 5.6 Per family, and the families the first version said close end to end

| docs | sections offered | closed | docs fully closing | census group | the first version's claim |
|---:|---:|---:|---:|---|---|
| 8 | 18 | 12 | **2** | `FAM:guardian_cu_statement_summary` | 8/8 |
| 3 | 6 | 1 | 0 | `FAM:altra_fcu_statement_summary` | 3/3 |
| 4 | 13 | 0 | 0 | `FAM:goldenwest_cu_member_account_statement` | 4/4 |
| 3 | 6 | 0 | 0 | `FAM:hudson_valley_fcu` | 3/3 |
| 5 | 10 | 0 | 0 | `FAM:wescom_cu_equation_summary` | 2/5 |
| 8 | 13 | 0 | 0 | `FAM:wpcu_summary_of_account_by_transaction` | 2/8 |
| 4 | 6 | 0 | 0 | `FAM:ornl_fcu_oak_ridge` | 1/4 |
| 8 | 12 | 5 | 0 | `FAM:cu_idaho_equation_summary` | 0 |
| 8 | 16 | 4 | 0 | `FAM:space_coast_cu_member_statement` | 0 |
| 4 | 11 | 2 | 0 | `FAM:access_fcu_member_statement_of_account` | 0 |
| 4 | 8 | 2 | 0 | `FAM:suncoast_cu_account_statement` | 0 |
| 13 | 44 | 1 | 0 | `FAM:cu_summary_of_accounts_date_posted` | 0 |
| 4 | 12 | 1 | 0 | `FAM:vystar_balance_summary_transactional_detail` | 0 |
| 3 | 8 | 1 | 0 | `FAM:champion_cu_statement_summary` | 0 |

(the full 43-row table is the instrument's own `## By census group` output)

**"Whole families close end to end" was the claim that broke hardest.** `hudson_valley` 3/3 and
`goldenwest` 4/4 were sections that published an empty ledger over 2 and 62 to 67 printed
dated rows apiece, on an enumerating table whose first figure the probe took for an opening and
which is that issue's CLOSING. Under the corrected column rule those documents no longer even
get an opening from that table at all, and nothing on them closes. The empty-ledger class is
and it is worth naming so nobody re-derives the same number: `vystar` 7, `wescom` 5,
`goldenwest` 4, `security_service` 4, `DECL:huntington` 2, `psecu` 1.

### 5.7 Money moved between a member's own accounts

| measure | value |
|---|---:|
| documents with two or more non-empty reconstructed ledgers | 11 |
| ... carrying same-day, same-magnitude, opposite-signed pairs across two of them | **7** |
| such pairs in total | **47** |

That is the printed signature of money moved between the member's own accounts, and it means
the same money stands in two ledgers of one document. A package that sums per-account deposits
over such a document double-counts every internal movement: gross deposit totals, deposit
counts, and any revenue or NSF derivation built on them. **The first version's ten conditions
said nothing about it.** It is now condition 11.

### 5.8 The two oracles are one oracle and a restatement

| | sections |
|---|---:|
| walks handed to both `reconcile` and the ADB | 48 |
| refused by `reconcile` | 11 |
| refused by the ADB | 10 |

The walk accepts a movement only where the paper prints the balance it lands on and the two
agree to the cent, so ledger continuity is exact BY CONSTRUCTION and the sum identity
telescopes to `end − begin` BY CONSTRUCTION. In the first version — which passed `None` for
every stated count and total — `reconcile` refused **0 of 105** successful walks, and "handed
to the validator, closing when both oracles agree" read as two independent checks passing when
it was one check and a restatement of the walk. It refuses 11 of 48 now, and the reason it can
is precisely the evidence the first version measured and then discarded: the sections' own
printed counts and totals (79 sections print them) and their own daily balances (24 do).

### 5.9 Fail-closed classes

| class | sections |
|---|---:|
| `section-prints-neither-an-opening-nor-a-closing` | 104 |
| `walk-did-not-reach-the-printed-closing` | 59 |
| `section-prints-no-opening-and-no-roll-up-states-one` | 54 |
| `closed` | 29 |
| `document-prints-no-resolvable-period` | 27 |
| `vacuous-empty-ledger-over-printed-rows` | 23 |
| `trivially-idle-opening-equals-closing-and-no-row-printed` | 21 |
| `offered-but-a-validator-refused` | 19 |
| `no-figures-in-ledger` | 19 |
| `section-prints-no-closing-and-no-roll-up-states-one` | 18 |
| `chain-leaves-a-hole-inside-the-span-it-walked` | 11 |
| `boundary-inferred-not-printed` | 6 |
| `section-and-rollup-disagree-on-the-pair` | **2** |

The first version called that last class "the sharpest refusal in the list" at 16 sections. It
is **2**. The other 14 were the section's own opening compared against whichever figure came
first in the table's row — a comparison against a column whose role was assumed, not printed.
The refusal is still the right one and its measured population is 2.

---

## 6. Fail-closed conditions (the exact list, for whichever option is ruled)

A multi-account document may be published ONLY when all of the following hold; any one failing
refuses the document, and none of them may be relaxed to gain coverage. **Thirteen, not ten:
three are new and one is rewritten, each because this population contains its counterexample.**

1. **The partition is printed.** Every published section is bounded by printed evidence — an
   enumerating roll-up whose identities reappear as section headings, or section headings that
   each carry their own identity. An inferred boundary (`section-equation-scan`) is never
   sufficient. *(103 + 38 documents qualify; 35 do not.)*
2. **The published sections PARTITION the document.** They must be disjoint and must cover the
   document's ledger region completely. A page-break reprint that omits the continuation word
   is a reappearance satisfying condition 1, and nothing else in this list forbids publishing
   it twice.
3. **The identities are distinct.** Two sections resolving to the same identity, or a
   `product_name_only` identity shared by two sections, refuses: two accounts of one product
   cannot be told apart by a name. *(Measured: 0 documents violate it; 44 enumerating tables
   print a repeated token, which is a hazard for the LOCATOR, not for this condition.)*
4. **Every posting section is accounted for.** No section with a dated ledger row may be
   dropped. A section may be OMITTED only under the ratified idle-sibling rule
   (`analysis/symitar.py` 13-45), applied AS WRITTEN — the printed declaration, or the
   yield-only arithmetic with its summary-equality test — and, when it is, the omission is
   SURFACED in the payload, never silently, which is the batch-8 SIBLING-OMISSION-SURFACE
   debt. *(Measured: over the 86 single-posting documents, 0 have every sibling satisfying it
   and 26 carry a sibling that posted and declares nothing — §4.)*
5. **The enumerating table's COLUMN ROLES are printed.** Where a published section takes its
   opening or its closing from the table rather than from its own captions, the table must
   print a column caption saying which column is which. Position is not evidence: one issue
   here prints the ENDING figure first. *(Measured: 30 of 214 documents print such a caption;
   184 print none.)* **NEW — this is the condition whose absence produced the first version's
   false closures.**
6. **Each published section states its own opening and closing**, or the table states them for
   it under condition 5. Where both are printed they must agree to the cent. *(Measured: 2
   sections fail exactly here and must stay refused.)*
7. **No published section may close on an empty or partial ledger.** A section that prints a
   dated ledger row may not publish zero transactions, and the published ledger must account
   for every dated row inside the span it read. *(Measured: 23 sections would close vacuously
   without this, and 11 more leave a hole inside their own span.)* **NEW.**
8. **Each published section's ledger closes.** `reconcile(section).ok` — the unchanged
   reconciler, on the section's own figures, WITH the section's own stated counts and totals
   supplied wherever it prints them. Passing `None` there disables the coverage checks that
   are the only ones capable of seeing a truncated ledger. No relaxation, no tolerance
   widening. *(Measured: 79 of 442 sections print their own counts or totals.)*
9. **Each published section's ADB is computable under the ratified doctrine.**
   `compute_average_daily_balance(section).ok`, calendar days over the printed period, with
   the production `posting_dates_cover_source` check applied against the SECTION's text, and
   with the section's own printed daily balances supplied where it prints them. **The period
   is the DOCUMENT's**: `find_period` is resolved once per document and the same pair is
   handed to every section, which is defensible on a member statement printing one cycle for
   all of a member's accounts and is why 27 documents lose every section at once. Where an
   issue prints a per-account activity range instead, this condition must say whose period it
   means before it becomes code. *(Measured: 24 of 442 sections print their own daily-balance
   table, so 95% rest on a reconstructed series.)*
10. **The roll-up reproduces.** Where the document prints an enumerating table, every published
    section's closing must appear in that account's roll-up row under condition 5's column
    roles, and where a cross-account total is printed the published sections must sum to it. A
    mismatch refuses the DOCUMENT, not the section.
11. **No money moved between the member's own accounts may be counted twice.** Where two
    published sections carry same-day, same-magnitude, opposite-signed movements, the package
    layer must not sum their deposits, deposit counts or any derivation built on them. *(
    Measured: 7 of the 11 documents with two non-empty reconstructed ledgers carry such pairs,
    47 pairs in total.)* **NEW.**
12. **A facility is not a deposit ledger.** A facility enumerated on the table is never
    published as a section, and condition 10's cross-account total is not required — and cannot
    be satisfied — where the total includes one. *(Measured: **19** documents enumerate one,
    **4** of them carrying two or more posting sections and all four
    `FAM:goldenwest_cu_member_account_statement`; 7 of the 19 also print a cross-account
    total.)* The class of a row must be established from the row, not from a word in it: the
    instrument counts three classes and names the ones it will not count, and an implementation
    has to confirm what the row IS before excluding it. **NEW.**
13. **One currency, established per SECTION.** Every published section must carry the same
    denomination, established by the currency doctrine's evidence hierarchy at the level of
    the section rather than the document — the doctrine resolves a denomination per DOCUMENT
    and `jurisdiction_default` is affirmative evidence at the institution level, so a member
    statement carrying one foreign-denominated sub-account that prints no code would otherwise
    be silently denominated across all its sections. A document printing two denominated
    columns is refused. *(Measured: 4 documents, one census group, 12 sections.)*

And two standing conditions that are not about this population:

14. **No statement-specific constant anywhere in the split.** The boundary vocabulary is
    institution furniture (captions, identity forms, column tokens); an account number, a
    product name or a memorized heading is R-1 and forbidden — which is also the standing
    defect in `analysis/consumers.py`.
15. **Zero inference.** Deterministic only, $0, no model call.

---

## 7. Publication model — the four options

For each: what moves on the protected 2,596 (must be nothing), the fail-closed conditions, the
surfaces touched, the per-document inference cost, and the regression surface.

### Option A — refuse every multi-active statement (today)

* **Movement on the protected 2,596:** none. This is the base.
* **Gain:** 0 on the 81 L-1 documents. And, corrected: the 79 single-posting CU documents are
  NOT reachable without a ruling either — §4 measures that publishing them means generalising
  the ratified idle-sibling rule to a population none of which satisfies it.
* **Fail-closed conditions:** already in force — `huntington:_LINE_OF_CREDIT_RE`,
  `community_section:len(parsed)!=1`, `navy_federal:_checking_account`,
  `consumers:_primary_checking_section`, `capital_one` emergent.
* **Surfaces:** none. **Inference cost:** zero.
* **Cost of keeping it:** the silent-skip debt stays (symitar's two ratified skips leave no
  trace in the payload), and `consumers` keeps selecting its ledger by a memorized account
  number on a pinned audited document (CONS-HARDCODE).

### Option B — publish ONE account under a printed PRIMARY rule, siblings SURFACED

Publish the account a printed rule identifies as primary, and record in the payload that other
posting sections existed and were not published (`unpublished_sibling_sections` + an integrity
NOTE — the batch-8 SIBLING-OMISSION-SURFACE design).

* **Which printed evidence would mark one account as primary — MEASURED this time**, over the
  81 multi-posting documents:

  | candidate rule | documents |
  |---|---:|
  | "the section the table names first" — UNDEFINED, no enumerating table | 30 of 81 |
  | "the only transaction share" — UNDEFINED, no such heading | 24 of 81 |
  | "the only transaction share" — AMBIGUOUS, two or more of them post | 9 of 81 |
  | "the only transaction share" — decides the document | 48 of 81 |
  | the table prints a cross-account TOTAL (the platform ranking the accounts alike) | 11 of 81 |
  | identity is a bare product designation on a multi-posting table document | 22 of 43 |

  No candidate is defined on the whole population, one is actively ambiguous on 9, and where
  the identity is a bare product designation two accounts of one product could not be told
  apart even if a rule existed. *"A product name"* is an R-1 vocabulary and forbidden outright.
* **Movement on the protected 2,596:** none IF the rule is additive-only. But it is not free:
  applying a primary rule to `consumers` **changes WHICH of three ledgers a pinned audited
  document reports** (`05E246C0ED6678E6`) — truth-set movement, a ceremony.
* **Fail-closed conditions it would need:** refuse when more than one section satisfies the
  primary rule; refuse when the primary section does not close; refuse when the roll-up does
  not reproduce it; refuse when any section is in a different currency.
* **Surfaces:** `analysis/schema.py` (one additive list field + one integrity flag),
  `analysis/pipeline.py` integrity block, the webapp/report note. No package math change.
* **Inference cost:** zero.
* **Verdict:** the SURFACE half of this option is unconditionally good and independently
  valuable (it repays the symitar silent-skip debt, which §4 shows is owed on more documents
  than anyone thought). The PRIMARY half has no printed evidence behind it in this population.

### Option C — a multi-account payload (`accounts: list[Statement]`)

* **Movement on the protected 2,596:** must be none, and it can be none only if the existing
  single-account fields keep their exact current meaning for every document that has one
  account. That is achievable (a one-account statement publishes a one-element list and the
  scalar fields unchanged), but it is a payload-shape change on every document in the archive
  and therefore an archive-sweep-scale proof, not a cell-scale one.
* **Gain (MEASURED, and no longer offered as a floor):** **2** of the 81 L-1 documents close on
  every located section today with a generic splitter, both with the table's own closing
  column reproducing. 29 of 392 sections close. Which families a per-family row grammar would
  convert is an ESTIMATE and is flagged as one; the MEASURED figure is 2.
* **Fail-closed conditions:** every one in §6.
* **Surfaces:** `analysis/schema.py`; `analysis/reconcile.py` — the identity itself untouched,
  only what it is called on; `analysis/adb.py` (one ADB per account; the ADB doctrine says ONE
  user-facing metric, so a multi-account document needs a ruling on what the single published
  ADB IS), `analysis/metrics.py`, `analysis/count_semantics.py` (any per-section stated-count
  reading has to declare a mapping there), `analysis/revenue.py`, the package layer,
  `webapp/`, the report, `corpus_gate.py`'s pinned expectations, every audit CSV shape.
* **Inference cost:** zero.
* **Verdict:** still the correct shape, and now visibly larger than the demonstrated benefit.
  It forces a doctrine question (§9, Q2) that is Gustavo's to answer, not a cell's.

### Option D — hybrid: (C) internally, one declared primary externally

Parse and validate every account (C), publish one as the document's headline account and carry
the rest in the payload.

* Inherits (C)'s schema work and (B)'s unsolved primary problem. Its one claimed advantage was
  that the primary rule could be evidence-bounded — "the only section that posts, everything
  else a ratified idle sibling" — which is symitar's existing rule generalised. **§4 removes
  that advantage: 0 documents satisfy the rule as written**, so the "evidence-bounded" variant
  is bounded by evidence this population does not print.
* **Movement on the protected 2,596:** none, same conditions as (C).
* **Verdict:** (D) is (C) plus a compatibility shim plus the same unresolved ruling. It is not
  a way around the ruling.

---

## 8. Regression surface

| surface | what is at risk | how it is proved |
|---|---|---|
| `analysis/huntington.py:659` `_LINE_OF_CREDIT_RE` | 4 documents refused today; the reader's validated cohort (38 replayed identical at base) | `cohort_replay --parser huntington` at base and closure |
| `analysis/community_section.py:990` `len(parsed)!=1` | the largest sectioned family; 3 registrations (`community_section`, `dakota_west`, `mission_valley`); 1 pinned document | `cohort_replay --parser` per registration id; corpus gate |
| `analysis/navy_federal.py::_checking_account` | 4 refusals + 4 pinned documents | `cohort_replay --parser navy_federal`; corpus gate |
| `analysis/capital_one.py` | 6 emergent refusals + 4 pinned documents; the reader has NO explicit L-1 gate, and its refusal is the ABSENCE of a nine-cell match standing in front of a row grammar that already returns 1 to 41 rows spanning several accounts (§1.1) — a widening there is easy to make silently wrong in the dangerous direction | `cohort_replay --parser capital_one`; a mutation table on any new gate |
| `analysis/consumers.py` (CONS-L1 / CONS-HARDCODE) | a pinned audited document whose PUBLISHED LEDGER would change | truth-set ceremony; not a parser fix |
| `analysis/symitar.py` ratified skip | the dormant + yield-only rules and their measured bound; §4 proposes GENERALISING them, which is a ruling and not a refactor | `cohort_replay --parser symitar --expect-identical` |
| `analysis/schema.py` | every payload in the archive | archive sweep `regfp_zero_movement_sweep` over the whole range, at the final tree |
| `analysis/count_semantics.py` | any per-section stated-count reading must declare its mapping there | `tests/test_count_semantics.py` in the canonical conformance set |
| `analysis/adb.py`, `analysis/metrics.py`, packages, `webapp/`, the report | the one published ADB, package math, every rendered surface | corpus gate GREEN + the pinned 109 + the currency/provenance surfaces |
| the package layer, specifically | 7 documents carry same-day opposite-signed pairs across two ledgers (47 pairs); per-account package math double-counts them (§5.7) | a per-document check in the package layer, with those 7 named by sha as its killers |
| the pinned 109 | 10 documents claimed by an L-1-carrying reader (§1.2); **12** print two or more posting sections (4 strong, 1 strong, 7 weak) | `corpus_gate.py` GREEN 105/3/1 unchanged |
| the protected 2,596 | any `validated -> anything` is BLOCKING | `cohort_replay` per touched registration + the archive sweep |

---

## 9. Recommendation

### 9.1 What to build, in order

**The card cannot be split the way the first version split it.** Its Stage 1 — "publish the 79
single-posting CU documents, no ruling needed" — rests on an idle-sibling rule that **0 of
those documents satisfy**, and 26 of them carry a sibling that posted a dated row and declares
nothing. There is no half of this reservoir that can be taken without a ruling.

**Step 1 — the one thing that needs no ruling and repays a standing debt.** Build
SIBLING-OMISSION-SURFACE: the additive payload field and the integrity flag that say a deposit
section existed and was not published. It changes no reader's decision, moves no document
across the ladder, and it is owed today by symitar's two silent skips whatever is ruled
here. Everything else in this packet is easier to argue about once a skip is visible.

**Step 2 — take ruling (5) first, because it is the cheapest thing on this list and it is
worth more than the headline.** Ask whether the ratified idle-sibling rule may be generalised,
and to what. **Sized on the family this packet actually demonstrates: 2 documents close today,
and 8 close if a section that prints no dated row and reads nothing may be omitted rather than
counted — all eight `FAM:guardian_cu_statement_summary`, all eight with the table's own closing
column reproducing over the sections that would be published (§5.3).** Two printed facts put
the ruling exactly where it bites: the 4 sibling sections in the whole population that print
the ratified declaration are all one census group, and every one of `guardian_cu`'s six
single-posting documents has a sibling that is EMPTY AND SILENT — the weakest evidence class in
the sibling table. So the ruling is not about a wording symitar nearly reads; it is about
whether silence plus arithmetic is evidence at all.

Beyond that one family the same ruling governs the rest of the single-posting reservoir: 44 of
the 86 documents have siblings that are empty and silent or declare idle in a wording symitar
does not read, and it decides whether 54 to 79 documents are reachable at all. It is a ruling
about EVIDENCE and it is cheap to answer.

**Step 3 — Option C for the multi-posting population, and size it honestly.** A multi-account
payload gated by all thirteen conditions in §6. **Measured today: 2 documents close on every
located section**, both `FAM:guardian_cu_statement_summary`, both with the table's own closing
column reproducing. 29 of 392 sections close. The reachable set beyond that depends on
per-family row grammars and on a better boundary layer — both are estimates, and this
packet declines to put a number on them after what happened to the last one.

Not Option A as a permanent answer: it forecloses a demonstrated 2 and keeps two open doctrine
obligations. Not B: this population supplies no printed evidence for a primary rule (§7), and
applying one moves a pinned audited document's published ledger. Not D: its evidence-bounded
primary rule is bounded by evidence that is not printed.

### 9.2 Proof plan

* `cohort_replay --expect-identical` at base for every registration of every module touched —
  huntington, community_section (×3 ids), navy_federal, capital_one, consumers, symitar — then
  again at closure.
* `cohort_replay --group` over each `FAM-CU-SUFFIX-CORE` census group the new module claims,
  before and after.
* A MUTATION TABLE for every condition in §6 that becomes code: each gets a mutant that removes
  it and a named killer test. The conditions with a measured population in this packet must
  have their killers drawn from it by sha — §6.5 → the 184 documents printing no column
  caption; §6.6 → 2 sections; §6.7 → 23 + 11 sections; condition 11 → 7 documents; condition 12 → 19
  documents, 4 of them multi-posting and 7 with a cross-account total; condition 13 → 4 documents; §6.4 → the 26
  documents whose sibling posted.
* `tools/regfp_zero_movement_sweep` over the WHOLE archive range at the final tree — mandatory
  for Step 3 because a schema shape change touches every payload.
* `corpus_gate.py` GREEN (105 PASS / 3 WITHHELD / 1 REFUSED) with the pinned 109 unmoved, and
  the corpus-marked 30.
* `privacy_scan_branch.py` = 0 against the whole named population.

### 9.3 What needs Gustavo's ruling before any code is written

1. **The idle-sibling rule's scope — and this is now FIRST, not fifth.** May symitar's
   ratified dormant + yield-only skip be generalised beyond the wording it reads? Measured: 4
   sibling sections in this whole population print the ratified declaration; 0 satisfy the
   yield-only arithmetic; 62 are empty and silent; 7 declare idle in another wording; 30 posted
   a dated row and declare nothing. Nothing in the reservoir is publishable without an answer.
2. **Multi-account payload (C), or the L-1 refusal stands (A)?** Everything else follows from
   it, and it must be decided knowing the demonstrated population is 2 documents rather
   than 11.
3. **The posting threshold itself.** "A section that posts" is 2 dated rows in the census and
   1 in the packet's own condition. The populations are 79 / 81 at the first and 54 / 111 at
   the second. The ruling has to name one.
4. **On a multi-account document, WHAT is the one published ADB?** The ADB doctrine
   (RATIFIED 2026-08-15) says one user-facing metric over the calendar-day printed period.
   Three candidate readings — per-account ADBs with no document-level figure; the sum of the
   per-account ADBs; the ADB of the summed daily balances (identical to the sum when every
   account covers the same period, and refusable when they do not). Note 95% of sections print
   no daily-balance table of their own, so whichever is chosen rests on a reconstructed series.
5. **Package math, including transfers.** If a package contains a multi-account statement, does
   each account become its own statement in the package, or does the document stay one member
   with several ledgers? Either way condition 11 has a measured population: 7 documents, 47 pairs.
   The currency doctrine already forbids cross-currency package math, which is why the 4
   two-currency documents must refuse under any answer.
6. **CONS-L1 / CONS-HARDCODE.** Repairing `analysis/consumers.py` honestly changes WHICH ledger
   a pinned audited document publishes. That is a truth-set ceremony and needs an explicit
   authorisation before it is touched, under either option.
7. **ATB.** Both `WH:atb` documents are consolidated multi-account statements with no located
   partition under any mechanism here. They stay refused under every option, and they belong to
   the ATB ceremony, not to this template.

---

## 10. Provenance

* Run of record `2026-08-28T22:46:40.553059+00:00-cda8882d` (3,380 shas; validated 2,596),
  cold cache `.claude/recovery/webapp_data_train8_cold` (OCR v4, analysis v16, registry
  fingerprint at `7185633`). Both read-only; nothing was written to either.
* Census `docs/moneythumb-replacement/census_batch9/{clusters.json, per_sha.csv,
  opportunity_estimates.json}`, `CENSUS_BATCH9.md`.
* Branch `wave9-l1inv`, base `train9` at `38a94aa`. No production file, no registration, no
  test wiring. `tools/l1_split_prototype.py` is imported by nothing.
* Instruments: `tools/l1_census.py`, `tools/l1_structure_census.py`,
  `tools/l1_split_prototype.py`.
* Review: `docs/moneythumb-replacement/reviews/BATCH9_L1INV_REVIEW.md` (2 BLOCK / 6 MAJOR /
  6 MINOR, verdict UNSOUND). Closure record: W3 `§L1INV.8`.

---

## 11. What the review found, and what each correction cost

Every row is a finding, the correction applied, and the number it moved. The commits are listed
in W3 `§L1INV.8`.

| finding | the correction | measured effect |
|---|---|---|
| **BLOCK-1** the chain walk closed a section on an EMPTY ledger whenever its opening figure already equalled its closing | the empty arrival is its own class and never a closure; a chain must account for every dated row inside the span it walked; an inferred boundary is refused under condition 1; the enumerating table's columns are read from its printed COLUMN CAPTION and never from position | 23 sections were closing over printed rows and 21 more are trivially idle; sections closing 97 → **29**; documents fully closing 23 → **2**; the L-1 floor 11 → **2**, with the oracle 6 → **2**; `hudson_valley` 3/3 → 0/3 and `goldenwest` 4/4 → 0/4 |
| **BLOCK-2** the "79 single-posting" population was a threshold, not the ratified rule | `--idle-siblings` applies `analysis/symitar.py`'s own `_DORMANT_RE` and `_yield_only` to every sibling of every single-posting document | 103 siblings: 4 declaration, 0 yield-only, 30 posted-and-silent, 62 empty-and-silent, 7 other wording; **0 documents** qualify; **26** carry a sibling that posted; the "no ruling needed" population is empty |
| **MAJOR-1** §7 printed a pinned exposure of 16 that §1.2 measured as 12 | the regression surface takes its number from the instrument | **12** (4 strong / 1 strong / 7 weak) |
| **MAJOR-2** `capital_one`'s refusal described backwards | the probe calls the module's own `_native_summary` and `_native_transactions` | nine-cell pattern matched **0 of 6**; rows returned on **6 of 6**, 1 / 28 / 41 |
| **MAJOR-3** `reconcile` satisfied by construction; "two oracles" was one | the counts each oracle refused are reported separately, and the stated evidence that lets `reconcile` do work is now supplied | it refused **0 of 105** before and **11 of 48** now |
| **MAJOR-4** the sections' own counts, totals and daily balances were measured and then passed as `None` | they are read and fed, the ADB is given the section's own text so `posting_dates_cover_source` applies, and a section printing them in an unreadable form is refused | the daily-table predicate was also wrong: 75 sections (17.0%) → **24 (5.4%)**; 13 of the 15 documents surviving the review's own chain are removed by this gate and the row-coverage gate together |
| **MAJOR-5** no condition about money moved between a member's own accounts | measured and added as condition 11 | **7** documents of the 11 with two non-empty ledgers, **47** pairs |
| **MAJOR-6** no deposit-versus-loan condition | measured and added as condition 12 | **19** documents enumerate one (corrected from 15 by MAJOR-A), **4** of them multi-posting and all four `FAM:goldenwest_cu_member_account_statement`, **7** also printing a cross-account total — the collision is live, not latent |
| **MINOR-1** 442 located vs 392 offered never reconciled; "27 sections" was 27 documents | the instrument prints the reconciliation | 442 − 77 + 27 = 392 |
| **MINOR-2** the ADB ran on the DOCUMENT's period and the condition never said so | stated in the instrument's own docstring and in §6.9 | 27 documents lose every section at once for this reason |
| **MINOR-3** Option B rejected by argument where the measurement was available | measured over the 81 multi-posting documents | first-named UNDEFINED on 30; transaction-share UNDEFINED on 24, AMBIGUOUS on 9, decides 48; 11 print a cross-account total; identity is a bare product designation on 22 of 43 |
| **MINOR-4** the guard named on the handoff does not cover `tools/` | recorded rather than fixed: adding a `tools/` clause to `tests/test_experiments_are_not_wired.py` is a production test change and this card owns no test | the property holds and is held by a grep: nothing outside `tools/l1_*` references any of the three instruments (verified at this tip). The card's "the guard applies" was not true as written and is not claimed here |
| **MINOR-5** the privacy number predated the tip, and 29 documents are not scanned against | re-run at this tip, and the 29 stated next to the zero | §12 |
| **MINOR-6** "every located section closes" is not "every printed section closes" | stated in §5.3 and printed by the instrument | 38 documents have no located partition; 11 enumerate accounts that never reappear |

**The review's own corrected figures, adjudicated rather than asserted.** Its chain was a
printed partition, no ledger published EMPTY over printed rows, and the source-coverage check
— without the row-coverage gate and without the sections' own stated evidence, neither of which
its arithmetic had. Its rule deliberately left a section that prints no dated row and reads
nothing standing as a closure, which is a dormant sibling. Implemented exactly that way on this
run, it gives **15** documents where it reported 11, an L-1 floor of **4** where it reported 3,
and **2** with the oracle, which it reported. The two gaps have different causes and only one
of them is the column fix:

* **The L-1 figure is the column fix.** `9B8E7D807228DA2B` was refused as a pair disagreement
  between a section and the table's first figure, and that comparison was against a column
  whose role was assumed rather than printed. With the roles read from the caption it closes
  under the review's conditions, so its floor is 4 and not 3. 14 of the old 16 "contradicts its
  own table" sections were the same false refusal, which is why that class is now 2.
* **The document figure is definitional.** A document carrying a dormant sibling can never
  reach "every located section closes" here, because a trivially idle section is a class and
  not a closure; under the review's rule it can. 15 documents qualify under its rule (8
  `guardian_cu`, 3 `altra_fcu`, 3 `cu_summary_of_accounts_date_posted`, 1 `DECL:consumers`),
  and a document whose ONLY located section is idle is excluded from both counts, because a
  document that publishes nothing is not a document that closes.

**Nothing in §5's headline depends on either.** The 2 is reached by a stricter route that does
not pass through the review's rule at all. Its transfer measurement (6 documents, 44 pairs)
measures **7 and 47** here, because the corrected walk reconstructs a different set of ledgers.
Its idle-sibling counts reproduce exactly: 4 sibling sections print the ratified declaration,
0 documents qualify, and 63 `CU-SUFFIX` documents carry a sibling that fails the rule.

---

## 12. Proof floor

| proof | result |
|---|---|
| canonical guards (5 files) | 255 passed — EXIT=0 |
| `tests/test_experiments_are_not_wired.py` | passes; guards `experiments/` and not `tools/` (MINOR-4) |
| nothing outside `tools/l1_*` references the three instruments | grep over the tree, no hits |
| no production file differs from base | `git diff --stat 38a94aa -- analysis ocr webapp discovery telemetry corpus_gate.py` empty |
| branch privacy scan vs the whole population | **hit_count 0** over 4,712 added lines and 3,351 documents, all four classes zero — EXIT=0. The scan reads 3,351 of the 3,380 shas; the 29 with no cached text are the same 29 the pinned survey reports as NOT SURVEYED, and nothing on this branch is scanned against them |
| the three instruments re-run from the run of record | EXIT=0 each; every number in this packet is in one of their outputs |

The full suite, the canonical conformance set, the corpus gate and the fidelity replay were
measured at `a86f183` (6,858 / 1,270 / GREEN 105-3-1 / 179 of 179 identical) and are not
re-run here: `git diff 38a94aa..<tip> --stat` is the packet, the W3 section, the review and
`tools/l1_{census,structure_census,split_prototype}.py`. No production file, no test and no
registry entry differs from base. That is a structural argument, not a re-measurement, and it
is offered as such.

No mutation table and no archive sweep are owed: this card adds no gate and no grammar to
production.
