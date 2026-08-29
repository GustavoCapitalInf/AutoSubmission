# L-1 / CU-SUFFIX ruling packet (batch 9, cell `L1INV`)

READ-ONLY investigation. No production file changed, nothing registered, nothing moved.
Every number below is produced by a committed instrument under `tools/l1_*.py`, run over the
run of record `discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`
and its cold cache `.claude/recovery/webapp_data_train8_cold`, and reproduces from them.
No printed value, name, account number, amount or date appears anywhere in this packet or in
the instruments: the tables count shapes, gate names, sections, closures and content sha16s.

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
```

---

## 0. The headline, before the detail

Three measured findings change the shape of the question the card asked.

1. **The L-1 rule is not what blocks most of the 176.** Of the 176 CU-suffix documents, **65
   print two or more POSTING account sections**. **79 print exactly one**, and 32 yield no
   located partition at all. For those 111 the single-account schema is not the obstacle —
   they are unclaimed layouts, and a reader would publish them today without any ruling.
   The census's `+25 to +95` therefore covers two different problems, and only the smaller
   half needs Gustavo.
2. **The population does share an architecture, but not a family.** Keyed on all seven
   mechanisms at once (boundary, caption, identity form, equation form, grid column shape,
   per-section daily, cross-account total) there are **63 distinct structural families
   over 214 documents**; 39
   of them have three or more members and cover 182. Almost no two census groups share a
   fine-grained family. What they DO share is a small closed set of MECHANICS: 4 boundary
   mechanisms, 9 roll-up caption classes, 5 identity forms, 4 equation forms, and grid shapes
   built from 13 column tokens. That is exactly the shape `core_processor_*` already has for
   banks — one shared template family with per-issue markers — and not 37 readers.
3. **Validating each account on its own works, and it is measured rather than assumed.**
   A read-only prototype that splits at the printed boundaries and hands each section to the
   EXISTING `reconcile` + `compute_average_daily_balance`, unchanged, closes **97 of 392
   sections**; **23 documents close on every section located** (19 of them multi-section, 12
   with the roll-up also reproducing every section's closing). Whole families close end to
   end: `guardian_cu` 8/8 documents, `goldenwest_cu` 4/4, `altra_fcu` 3/3, `hudson_valley` 3/3.
   Every one of those numbers is a **LOWER BOUND** (§4.1).

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
| `DECL:capital_one` | `capital_one` | 6 | 6 | **6** | 0 | emergent — 3 printed `Previous Balance` summary blocks ×6 |
| `DECL:consumers` | `consumers` | 3 | 3 | **3** | 0 | `_primary_checking_section` (CONS-L1) ×3 |
| | | **36** | **36** | **24** | **12** | |

This reproduces the WAVE2 batch-7 escalation's counts (4 / 7 / 4 / 6 / 3) from evidence.
**`capital_one` is the exception worth naming**: its module states no L-1 gate in code. The
refusal is emergent — `_native_summary` matches ONE summary block and the six declining
documents print three. It is recorded here as `capital_one:emergent`, never as a gate the
module contains.

### 1.2 The pinned corpus

109 pinned paths, all on disk. 80 are in the run of record; **29 are not in the run at all**
(measured, not assumed — their content sha appears in no row). Those 29 are NOT surveyed
structurally: this instrument does not reach around `ocr/native_text.py`'s ladder to read them
a second way (`tests/test_native_rung_parity.py` forbids it, and a structure read through
different text would not be the structure production read). The pinned structural finding
below therefore covers 80 documents, and the 29 are a named gap.

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
corroboration of the probe rather than a new finding.

---

## 2. Root cause

`analysis/schema.py::Statement` carries ONE account: `account_name`, `account_number`, one
`transactions` list, one opening, one closing, one daily-balance series. A member statement
prints several. Publishing one of them and silently dropping the others is a correctness
defect — the rule MASTER_PLAN calls L-1 — so a reader that recognises such a document
refuses it. `analysis/symitar.py` (lines 13–45) carries the one ratified exception:
a DORMANT deposit sibling — `No Transactions This Period`, or a section whose every posting
is the account's own dividend, bounded by the platform's own `Dividends` column — is not a
second ledger and may be skipped. Both skips are silent today; the visible surface
(SIBLING-OMISSION-SURFACE) was carded in batch 8 and is not built.

The root cause is therefore **not extraction and not arithmetic**. §4 measures that the
arithmetic closes per account on documents the platform refuses. It is a **publication-model
gap**: the schema cannot say "this statement covers three accounts", the payload cannot say
"a section existed and was not published", and no rule says which account is THE account.

---

## 3. Structure — what varies, and what is shared

`tools/l1_structure_census.py`, 214 documents.

### 3.1 How account boundaries are established from printed evidence

| mechanism | documents | is there a cross-account ORACLE? |
|---|---:|---|
| `rollup-oracle` — the document enumerates its accounts with a balance each, and each enumerated identity reappears as a section heading | **103** | **YES** — the roll-up states figures the sections must reproduce |
| `section-identity` — no enumerating table, but each section opens with a heading carrying its own identity (`… Suffix 0050 Activity Summary Previous Balance …`) | **38** | no — the partition is printed, the cross-check is not |
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
| roll-up column header | 4 (+ none) | `type_prev_dep_wd_end` 15, `type_begin_end` 8, `begin_end` 7; none 184 |
| identity form | 5 (+ none) | `product_name_only` 71, `bare_digits` 54, `suffix_word` 8, `paren_digits` 7, `id_word` 1; none 73 |
| equation form (modal section) | 4 (+ none) | `open_close_pair` 114, `open_only` 34, `explicit_six_figure` 5, `explicit_equation` 4; none 57 |
| grid column shape | ~49 distinct orderings, built from **13 column tokens** | every ordering ends in a balance column; they differ only in how the movement columns before it are named and in which date columns open the row |

The grid shape is the only mechanism with many values, and it differs in ONE way that counts:
where the running balance sits relative to the amount column. That is readable from the
printed header, which is why §4 needs no per-issuer row grammar at all.

### 3.3 Per-section facts (442 located sections)

| fact | sections | share |
|---|---:|---:|
| prints its own opening AND closing | 208 | 47.1% |
| prints its own ledger grid header | 273 | 61.8% |
| carries at least one dated row | 327 | 74.0% |
| prints its own counts / totals | 79 | 17.9% |
| prints its own daily-balance table | 75 | 17.0% |
| prints an explicit no-activity declaration | 31 | 7.0% |

**Only 17% of sections print their own daily balances.** Under the ratified ADB doctrine the
canonical ADB is reconstructed over the printed period's calendar days from the ledger, which
these sections do print — but any per-account ADB rests on the reconstructed series, not on
bank-printed daily evidence, for 83% of them.

### 3.4 The roll-up as an oracle

| oracle strength | documents |
|---|---:|
| the roll-up states TWO balances per account (opening AND closing) | 60 |
| the roll-up states at least ONE balance per account | 117 |
| the roll-up closes with a cross-account total row | 37 |

### 3.5 The L-1 exposure, counted

Posting sections per document (a section with two or more dated ledger rows):

| posting sections | CU-SUFFIX | DECL-L1-CANDIDATE | ATB | all |
|---:|---:|---:|---:|---:|
| 0 | 32 | 13 | 2 | 47 |
| 1 | 79 | 7 | 0 | 86 |
| 2 | 48 | 9 | 0 | 57 |
| 3 | 13 | 7 | 0 | 20 |
| 4 | 2 | 0 | 0 | 2 |
| 5 | 2 | 0 | 0 | 2 |
| **>= 2 (the L-1 population)** | **65** | **16** | **0** | **81** |

This is finding (1) of §0 in its measured form: **79 of the 176 print exactly one posting
account**. They are refused by nothing except the absence of a reader.

### 3.6 How many share ONE structural family

63 distinct fine-grained families over 214 documents; 39 with three or more members covering
182. The largest:

| n | census groups | family key |
|---:|---|---|
| 13 | `DECL:huntington`, `FAM:rbfcu_business_member_statement` | `none then no-rollup then no-identity then no-equation then no-grid then no-daily then no-total-row` |
| 9 | `FAM:mountain_america_cu_dot_leader` | `rollup-oracle:bare_digits then account_summary then bare_digits then open_close_pair then post_date\|desc\|amount\|balance then no-daily then total-row` |
| 8 | `DECL:huntington`, `FAM:greater_nevada_cu` | `section-equation-scan then no-rollup then no-identity then open_close_pair then no-grid then daily then no-total-row` |
| 8 | `FAM:space_coast_cu_member_statement` | `rollup-oracle:product_name_only then statement_summary then product_name_only then open_close_pair then txn_date\|eff_date\|desc\|money_in\|money_out\|balance then daily then no-total-row` |
| 7 | `DECL:community_section` | `rollup-oracle:product_name_only then summary_of_accounts then product_name_only then open_close_pair then post_date\|desc\|debit\|credit\|balance then daily then no-total-row` |
| 6 | `FAM:cu_idaho_equation_summary` | `section-identity:account_no_mask then no-rollup then no-identity then open_only then eff_date\|post_date\|desc\|deposit\|balance\|withdrawal then daily then no-total-row` |
| 6 | `FAM:cu_summary_of_accounts_date_posted` | `rollup-oracle:product_name_only then summary_of_accounts then product_name_only then open_only then date\|desc\|debit\|credit\|balance then no-daily then no-total-row` |
| 6 | `FAM:guardian_cu_statement_summary` | `rollup-oracle:suffix_word then statement_summary then suffix_word then open_close_pair then txn_date\|post_date\|desc\|withdrawal\|deposit\|balance\|date then no-daily then total-row` |
| 6 | `DECL:capital_one` | `section-equation-scan then account_summary then no-identity then open_close_pair then date\|desc\|deposit\|credit\|withdrawal\|debit\|balance then no-daily then no-total-row` |

**The honest answer to Gustavo's question:** the 176 do NOT share one structural family — a
census group and a structural family are very nearly the same partition, and two institutions
almost never coincide. They share one structural ARCHITECTURE: enumerate → identify → bound →
reconstruct → validate, with each stage drawing from a closed vocabulary of a handful of
printed forms. A shared template module with per-issue markers is therefore the right shape;
37 readers is not.

---

## 4. Expected safe gain — MEASURED

`tools/l1_split_prototype.py`. For every located section: the section's own printed opening
and closing (or the roll-up's row for that account, where both are printed they must agree to
the cent), a ledger reconstructed by a self-validating balance-chain walk, and then
`analysis/reconcile.py::reconcile` and `analysis/adb.py::compute_average_daily_balance`
called **unchanged**. A section CLOSES when both return `ok`.

### 4.1 Why every number here is a LOWER bound

* The prototype has **no per-family row grammar at all**. It accepts a transaction only where
  the document prints BOTH the movement and the balance it lands on and
  `previous ± amount = balance` holds to the cent. A section whose grid prints an amount
  without a running balance is refused outright, even though a family-specific grammar would
  read it. 77 sections fail on `walk-did-not-reach-the-printed-closing` for this class of
  reason.
* It reads the period from a generic date-range grammar; 27 sections are lost to
  `document-prints-no-resolvable-period`, which is a defect of the probe, not of the document.
* It supplies no `source_markdown` to the ADB, so the production check
  `posting_dates_cover_source` is NOT applied. That check can only LOWER a count, so it is
  named here as an unpaid debt for the implementation (§7), not as a number in this table.

### 4.2 Headline

| measure | value |
|---|---:|
| documents in the population | 214 |
| sections reconstructed and offered to the validator | 392 |
| **sections that CLOSE (`recon.ok` and `adb.ok`)** | **97** |
| **documents whose EVERY located section closes** | **23** |
| … of those, documents with two or more sections | 19 |
| … whose roll-up ALSO reproduces every section's closing | 12 |

All 23 fully-closing documents are `CU-SUFFIX`. None is a `DECL:*` document, and neither
`WH:atb` document closes.

### 4.3 By boundary mechanism

| boundary | docs | sections offered | closed | docs fully closing | roll-up also reproduces |
|---|---:|---:|---:|---:|---:|
| `rollup-oracle` | 103 | 212 | 52 | 16 | 12 |
| `section-identity` | 38 | 89 | 21 | 3 | 0 |
| `section-equation-scan` | 35 | 84 | 24 | 4 | 0 |
| `none` | 38 | 7 | 0 | 0 | 0 |

### 4.4 The L-1 question in its own terms

Documents with two or more POSTING sections — the ones the single-account schema refuses:

| band | docs with >= 2 posting sections | every section closes | roll-up also reproduces |
|---|---:|---:|---:|
| `CU-SUFFIX` | 65 | **11** | **6** |
| `DECL-L1-CANDIDATE` | 16 | 0 | 0 |
| `ATB` | 0 | 0 | 0 |
| **total** | **81** | **11** | **6** |

### 4.5 Per family — where the gain is, today, with no new row grammar

| docs | sections | closed | docs fully closing | census group |
|---:|---:|---:|---:|---|
| 8 | 18 | 18 | **8** | `FAM:guardian_cu_statement_summary` |
| 4 | 13 | 13 | **4** | `FAM:goldenwest_cu_member_account_statement` |
| 3 | 6 | 6 | **3** | `FAM:altra_fcu_statement_summary` |
| 3 | 6 | 6 | **3** | `FAM:hudson_valley_fcu` |
| 5 | 10 | 5 | **2** | `FAM:wescom_cu_equation_summary` |
| 8 | 13 | 4 | **2** | `FAM:wpcu_summary_of_account_by_transaction` |
| 4 | 6 | 3 | **1** | `FAM:ornl_fcu_oak_ridge` |
| 4 | 12 | 8 | 0 | `FAM:vystar_balance_summary_transactional_detail` |
| 8 | 12 | 5 | 0 | `FAM:cu_idaho_equation_summary` |
| 8 | 16 | 4 | 0 | `FAM:space_coast_cu_member_statement` |
| 4 | 8 | 4 | 0 | `FAM:cu_statement_summary_prev_new_balance_unbranded` |
| 8 | 14 | 5 | 0 | `FAM:cu_unq_clt_trailing_minus_totals` |
| 4 | 8 | 4 | 0 | `FAM:security_service_fcu_asterisk_sections` |
| 3 | 8 | 3 | 0 | `FAM:champion_cu_statement_summary` |
| 13 | 44 | 1 | 0 | `FAM:cu_summary_of_accounts_date_posted` |
| 9 | 21 | 0 | 0 | `FAM:mountain_america_cu_dot_leader` |
| 5 | 15 | 0 | 0 | `FAM:beem_credit_union_bc` |
| 12 | 8 | 2 | 0 | `DECL:huntington` |
| 6 | 18 | 0 | 0 | `DECL:capital_one` |
| 9 | 9 | 0 | 0 | `DECL:community_section` |
| 6 | 16 | 0 | 0 | `DECL:navy_federal` |
| 3 | 7 | 1 | 0 | `DECL:consumers` |
| 2 | 2 | 0 | 0 | `WH:atb` |

(the full 43-row table is the instrument's own `## By census group` output)

The seven families in the top block already close on the unchanged validator with a generic
splitter. **A per-family marker set plus the family's own row grammar is what turns the
partially-closing families (`vystar`, `space_coast`, `cu_idaho`, `cu_summary_of_accounts`,
`mountain_america`) into full documents**, and those five alone are 42 documents.

### 4.6 Ambiguity classes the prototype fails closed on

| class | sections | what it means |
|---|---:|---|
| `section-prints-no-opening-and-no-roll-up-states-one` | 78 | the section's opening cannot be read anywhere; no partition arithmetic is possible |
| `walk-did-not-reach-the-printed-closing` | 77 | the reconstructed chain does not land on the section's own printed closing |
| `section-prints-neither-an-opening-nor-a-closing` | 52 | the section prints no equation of its own |
| `document-prints-no-resolvable-period` | 27 | probe limitation (§4.1) |
| `no-figures-in-ledger` | 20 | the located span carries no figures — a mis-located boundary, refused |
| `section-prints-no-closing-and-no-roll-up-states-one` | 17 | as above, closing side |
| `section-and-rollup-disagree-on-the-pair` | **16** | **the section's own figures contradict the table that enumerates it** — the sharpest refusal in the list |
| `offered-but-validator-refused` | 8 | the chain closed, `reconcile`/ADB still said no |

Plus, measured separately: **4 documents (`FAM:community_savings_bc`) print their roll-up in
TWO CURRENCY COLUMNS (CDN and USD)**. Under `CURRENCY_DOCTRINE` there is no cross-currency
package math and one denominated ADB, so a multi-account payload spanning two denominations is
a refusal, not a feature. That is a measured population of 4, not a hypothetical.

---

## 5. Publication model — the four options

For each: what moves on the protected 2,596 (must be nothing), the fail-closed conditions, the
surfaces touched, the per-document inference cost, and the regression surface.

### Option A — refuse every multi-active statement (today)

* **Movement on the protected 2,596:** none. This is the base.
* **Gain:** 0 on the 81 L-1 documents. The 79 single-posting CU documents are still reachable
  by ordinary reader work with no ruling at all.
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

* **Which printed evidence would mark one account as primary, measured:** none of it does so
  safely. The candidate rules and why each fails on the evidence —
  * *"the only checking/draft share with member activity"* — 57 documents print exactly two
    posting sections and 24 print three or more; the census does not tell us how many of those
    pairs are checking+checking, but `consumers` alone is documented (module docstring) as
    printing TWO active checking accounts on a pinned document. A rule that assumes one is
    unproven on the class it is meant to decide.
  * *"the section the roll-up names first"* — print order is a layout fact, not a statement
    about the member's money. 37 documents print a cross-account total, which is the platform
    saying the accounts rank alike.
  * *"a product name"* — an R-1 vocabulary, forbidden.
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
  valuable (it repays the symitar silent-skip debt). The PRIMARY half has no printed evidence
  behind it in this population and would be a guess wearing a rule.

### Option C — a multi-account payload (`accounts: list[Statement]`)

* **Movement on the protected 2,596:** must be none, and it can be none only if the existing
  single-account fields keep their exact current meaning for every document that has one
  account. That is achievable (a one-account statement publishes a one-element list and the
  scalar fields unchanged), but it is a payload-shape change on every document in the archive
  and therefore an archive-sweep-scale proof, not a cell-scale one.
* **Gain (measured, lower bound):** 11 of the 81 L-1 documents close on every posting section
  today with a generic splitter; 23 documents close on every located section. With per-family
  row grammars for the five partially-closing families, the reachable set is 42 more documents
  — but that number is an ESTIMATE and is flagged as such; the MEASURED figure is 11 (6 with
  the roll-up oracle also reproducing).
* **Fail-closed conditions:** every one in §6.
* **Surfaces:** `analysis/schema.py`; `analysis/reconcile.py` — the identity itself is
  untouched, only what it is called on; `analysis/adb.py` (one ADB per account; the ADB
  doctrine says ONE user-facing metric, so a multi-account document needs a ruling on what the
  single published ADB IS), `analysis/metrics.py`, `analysis/revenue.py`, the package layer,
  `webapp/`, the report, `corpus_gate.py`'s pinned expectations, every audit CSV shape.
* **Inference cost:** zero.
* **Verdict:** correct, large, and it forces a doctrine question (§8, Q2) that is Gustavo's to
  answer, not a cell's.

### Option D — hybrid: (C) internally, one declared primary externally

Parse and validate every account (C), publish one as the document's headline account and carry
the rest in the payload.

* Inherits (C)'s schema work and (B)'s unsolved primary problem. Its one real advantage is
  that the primary rule may then be **evidence-bounded rather than guessed**: an account can be
  declared primary only when it is the ONLY section that posts, everything else being a
  ratified idle sibling — which is precisely symitar's existing rule, generalised, and which
  moves the 79 single-posting-section documents rather than the 81 multi-posting ones.
* **Movement on the protected 2,596:** none, same conditions as (C).
* **Verdict:** (D) with the primary rule restricted to "exactly one posting section" is
  (C) plus a compatibility shim, and it is the only variant of the primary idea this
  population supports.

---

## 6. Fail-closed conditions (the exact list, for whichever option is ruled)

A multi-account document may be published ONLY when all of the following hold; any one failing
refuses the document, and none of them may be relaxed to gain coverage.

1. **The partition is printed.** Every published section is bounded by printed evidence — an
   enumerating roll-up whose identities reappear as section headings, or section headings that
   each carry their own identity. An inferred boundary (`section-equation-scan`) is never
   sufficient. *(103 + 38 documents qualify; 35 do not.)*
2. **The identities are distinct.** Two sections resolving to the same identity, or a
   `product_name_only` identity shared by two sections, refuses: two accounts of one product
   cannot be told apart by a name.
3. **Every posting section is accounted for.** No section with a dated ledger row may be
   dropped. A section may be OMITTED only under the ratified idle-sibling rule
   (`analysis/symitar.py` 13–45: `No Transactions This Period`, or dividend-only bounded by
   the platform's own `Dividends` column) and, when it is, the omission is SURFACED in the
   payload — never silently, which is the batch-8 SIBLING-OMISSION-SURFACE debt.
4. **Each published section states its own opening and closing**, or the roll-up states them
   for it. Where both are printed they must agree to the cent. *(16 sections in this population
   fail exactly here and must stay refused.)*
5. **Each published section's ledger closes.** `reconcile(section).ok` — the unchanged
   reconciler, on the section's own figures. No relaxation, no tolerance widening.
6. **Each published section's ADB is computable under the ratified doctrine.**
   `compute_average_daily_balance(section).ok`, calendar days over the printed period, with
   the production `posting_dates_cover_source` check applied against the SECTION's text.
7. **The roll-up reproduces.** Where the document prints an enumerating table, every published
   section's closing must appear in that account's roll-up row, and where a cross-account total
   is printed the published sections must sum to it. A mismatch refuses the DOCUMENT, not the
   section.
8. **One currency.** Every published section must carry the same denomination, established by
   the currency doctrine's evidence hierarchy. A document printing two denominated columns is
   refused. *(Measured: 4 documents.)*
9. **No statement-specific constant anywhere in the split.** The boundary vocabulary is
   institution furniture (captions, identity forms, column tokens); an account number, a
   product name or a memorized heading is R-1 and forbidden — which is also the standing
   defect in `analysis/consumers.py`.
10. **Zero inference.** Deterministic only, $0, no model call.

---

## 7. Regression surface

| surface | what is at risk | how it is proved |
|---|---|---|
| `analysis/huntington.py:659` `_LINE_OF_CREDIT_RE` | 4 documents refused today; the reader's validated cohort (38 replayed identical at base) | `cohort_replay --parser huntington` at base and closure |
| `analysis/community_section.py:990` `len(parsed)!=1` | the largest sectioned family; 3 registrations (`community_section`, `dakota_west`, `mission_valley`); 1 pinned document | `cohort_replay --parser` per registration id; corpus gate |
| `analysis/navy_federal.py::_checking_account` | 4 refusals + 4 pinned documents | `cohort_replay --parser navy_federal`; corpus gate |
| `analysis/capital_one.py` | 6 emergent refusals + 4 pinned documents; the reader has NO explicit L-1 gate, so a widening there is easy to make silently wrong | `cohort_replay --parser capital_one`; a mutation table on any new gate |
| `analysis/consumers.py` (CONS-L1 / CONS-HARDCODE) | a pinned audited document whose PUBLISHED LEDGER would change | truth-set ceremony; not a parser fix |
| `analysis/symitar.py` ratified skip | the dormant + yield-only rules and their measured bound | `cohort_replay --parser symitar --expect-identical` |
| `analysis/schema.py` | every payload in the archive | archive sweep `regfp_zero_movement_sweep` over the whole range, at the final tree |
| `analysis/adb.py`, `analysis/metrics.py`, packages, `webapp/`, the report | the one published ADB, package math, every rendered surface | corpus gate GREEN + the pinned 109 + the currency/provenance surfaces |
| the pinned 109 | 10 documents claimed by an L-1-carrying reader (§1.2); 16 print two or more posting sections | `corpus_gate.py` GREEN 105/3/1 unchanged |
| the protected 2,596 | any `validated -> anything` is BLOCKING | `cohort_replay` per touched registration + the archive sweep |

---

## 8. Recommendation

### 8.1 What to build, in order

**Split the card in two, because the census's reservoir is two problems.**

**Stage 1 — no ruling needed, and it is the larger half.** A shared CU member-statement
template module (`analysis/cu_member_statement.py`, the `core_processor_*` pattern) that
publishes the **79 CU documents with exactly one posting section**, treating every other
printed section as an idle sibling under the ratified symitar rule and SURFACING the omission.
This needs no schema change, no publication-model ruling, and no truth-set movement. It also
pays the SIBLING-OMISSION-SURFACE debt, which is currently owed by symitar's two silent skips.
Start with the families §4.5 shows already closing: `guardian_cu`, `goldenwest_cu`,
`altra_fcu`, `hudson_valley`, `wescom_cu`, `wpcu`, `ornl_fcu`.

**Stage 2 — needs the ruling.** Option **C** (a multi-account payload), built on Stage 1's
splitter, for the **81 documents with two or more posting sections**, gated by all ten
conditions in §6. Measured floor today: **11 documents** close on every posting section with a
generic splitter and no row grammar; **6** of those also reproduce against the roll-up.

Not Option A (it forecloses a measured 11+ and keeps two open doctrine obligations). Not B: this
population supplies no printed evidence for a primary rule, and applying one moves a pinned
audited document's published ledger. Option D only as C-plus-a-shim if the webapp cannot show
more than one account at launch.

### 8.2 Proof plan

* `cohort_replay --expect-identical` at base for every registration of every module touched —
  huntington, community_section (×3 ids), navy_federal, capital_one, consumers, symitar — then
  again at closure.
* `cohort_replay --group` over each `FAM-CU-SUFFIX-CORE` census group the new module claims,
  before and after.
* A MUTATION TABLE for every gate in §6 that becomes code: each condition gets a mutant that
  removes it and a named killer test. The four conditions with a measured population in this
  packet (§6.4 → 16 sections, §6.8 → 4 documents, §6.2, §6.7) must have their killers drawn
  from that population by sha.
* `tools/regfp_zero_movement_sweep` over the WHOLE archive range at the final tree — mandatory
  for Stage 2 because a schema shape change touches every payload.
* `corpus_gate.py` GREEN (105 PASS / 3 WITHHELD / 1 REFUSED) with the pinned 109 unmoved, and
  the corpus-marked 30.
* `privacy_scan_branch.py` = 0 against the whole named population.

### 8.3 What needs Gustavo's ruling before any code is written

1. **Multi-account payload (C), or the L-1 refusal stands (A)?** Everything else follows
   from this. Stage 1 above does not depend on it.
2. **On a multi-account document, WHAT is the one published ADB?** The ADB doctrine
   (RATIFIED 2026-08-15) says one user-facing metric over the calendar-day printed period.
   Three candidate readings — per-account ADBs with no document-level figure; the sum of the
   per-account ADBs; the ADB of the summed daily balances (identical to the sum when every
   account covers the same period, and refusable when they do not). This is a doctrine
   question, not an implementation choice.
3. **Package math.** If a package contains a multi-account statement, does each account become
   its own statement in the package, or does the document stay one member with several
   ledgers? The currency doctrine already forbids cross-currency package math, which is why the
   4 two-currency documents must refuse either way.
4. **CONS-L1 / CONS-HARDCODE.** Repairing `analysis/consumers.py` honestly changes WHICH ledger
   a pinned audited document publishes. That is a truth-set ceremony and needs an explicit
   authorisation before it is touched, under either option.
5. **The idle-sibling rule's scope.** Stage 1 generalises symitar's ratified dormant + dividend
   -only skip to every issue in this template family. That is an extension of a ratified rule
   to a much larger population and should be ratified again on the measured evidence rather
   than inherited silently — 31 of 442 sections print an explicit no-activity declaration, and
   the rest of the "idle" sections would be declared idle by arithmetic.
6. **ATB.** Both `WH:atb` documents are consolidated multi-account statements with no located
   partition under any mechanism here. They stay refused under every option, and they
   belong to the ATB ceremony, not to this template.

---

## 9. Provenance

* Run of record `2026-08-28T22:46:40.553059+00:00-cda8882d` (3,380 shas; validated 2,596),
  cold cache `.claude/recovery/webapp_data_train8_cold` (OCR v4, analysis v16, registry
  fingerprint at `7185633`). Both read-only; nothing was written to either.
* Census `docs/moneythumb-replacement/census_batch9/{clusters.json, per_sha.csv,
  opportunity_estimates.json}`, `CENSUS_BATCH9.md`.
* Branch `wave9-l1inv`, base `train9` at `38a94aa`. No production file, no registration, no
  test wiring. `tools/l1_split_prototype.py` is imported by nothing.
* Instruments: `tools/l1_census.py`, `tools/l1_structure_census.py`,
  `tools/l1_split_prototype.py`.
