# COUNTS-P1 — the stated-count integrity measurement (PHASE 1, OBSERVE ONLY)

Card: `docs/agent-handoffs/COUNTS-P1.md`. Binding law: the 2026-08-10
**STATED-COUNT CHECK: GUSTAVO ARCHITECTURAL SIGN-OFF** entry in
`WAVE2_EXECUTION_LOG.md`. Design under measurement: `PROPOSAL_STATED_COUNTS.md`,
as amended by the sign-off's closed vocabulary.

**Phase 1 landed ZERO production-path change.** `analysis/`, `ocr/`, `webapp/`
and `discovery/` are byte-identical to base (`§8.1`). Nothing flags, nothing
withholds, no outcome class moved, no payload was written, no cache version
changed. Everything below is a read of artifacts that already existed: no OCR,
no model call, `$0.00` of vendor spend.

- Base: `2f394bf3407ff4ba0f34342f648f5ba2304933b8` · branch `wave3-stated-counts-p1`
- Observer: `telemetry/stated_counts.py` (`OBSERVER_VERSION = 1`), tests
  `tests/test_stated_counts.py`
- Source of truth: the D-3 analysis artifact cache at `webapp_data/`, joined to
  discovery run `2026-08-09T025430.480419-0000-52b4b2b2` (the newest full run),
  analysis settings key `1D945CEE…E829` (`ANALYSIS_STAGE_VERSION = 5`,
  `parse_mode=deterministic`)

```
python -m telemetry.stated_counts \
    --run discovery_reports/2026-08-09T025430.480419-0000-52b4b2b2 \
    --data-dir webapp_data \
    --corpus-audit docs/adb-audit-results.csv --corpus-root "Bank Statements"
```

---

## 1. Coverage — how much of the archive can be checked at all

3,506 processed rows collapse to **3,380 distinct documents** by
`content_sha256`; every rate below is per distinct document, because the same
bytes appear under several paths and counting them twice would inflate
everything.

| Population | Documents | Note |
|---|---|---|
| Distinct documents in the run | **3,380** | 3,506 rows, 126 duplicate hashes |
| With a cached analysis payload | **1,690** (50.0%) | 1,622 validated / 58 withheld / 10 review |
| **Without** a payload → `check_unavailable` | **1,690** (50.0%) | 1,677 unclaimed-or-failed, 13 deferred |
| Payload present, **no printed count in either direction** → `not_printed` | 544 | the parser reads none, or the bank prints none |
| Payload present, **a printed count in at least one direction** | **1,146** | 1,145 both directions, 1 credit-only |
| **At least one direction actually comparable** (`match`/`mismatch`) | **1,095** (32.4% of 3,380; 64.8% of analysed) | |
| **Both** directions comparable | 350 | |

**The honest headline: the check is available on 1,095 of 3,380 documents, and
the single largest reason it is not available is that half the archive has no
analysis payload at all.** `cached_analysis` stores only successful results
(`webapp/artifact_cache.py:580-600`), so an unclaimed document — 1,677 of the
3,380 failed `no_parser_matched`, plus 13 deferred — leaves no artifact behind. That is
not a defect in this check; it is the deterministic-coverage gap measured from
a different angle, and it is why `check_unavailable` is 50.0% of all direction
results and must never be read as "the check passed".

Direction results (two per document, 6,760 total):

| Result | Directions | Share |
|---|---|---|
| `match` | 1,396 | 20.7% |
| `mismatch` | **49** | 0.7% |
| `not_printed` | 1,089 | 16.1% |
| `semantics_incomparable` | 846 | 12.5% |
| `check_unavailable` | 3,380 | 50.0% |

---

## 2. Per parser

`C:` = credit direction, `D:` = debit direction. `(unclaimed)` is the 1,690
documents with no payload; all 3,380 of their direction results are
`check_unavailable`. Parsers with no printed count on either direction are
collapsed into §2.1.

| parser | docs | C:match | C:mismatch | C:not_printed | C:incomparable | D:match | D:mismatch | D:not_printed | D:incomparable |
|---|---|---|---|---|---|---|---|---|---|
| chase | 389 | 388 | 0 | 1 | 0 | 0 | 0 | 2 | 387 |
| bank_of_america | 360 | 344 | 0 | 16 | 0 | 0 | 0 | 16 | 344 |
| rbc | 153 | 147 | **6** | 0 | 0 | 147 | **6** | 0 | 0 |
| scotiabank | 80 | 76 | **4** | 0 | 0 | 76 | **4** | 0 | 0 |
| td_canada_native | 73 | 63 | **10** | 0 | 0 | 63 | **10** | 0 | 0 |
| us_bank | 40 | 0 | 0 | 0 | 40 | 0 | 0 | 0 | 40 |
| mission_valley | 17 | 17 | 0 | 0 | 0 | 17 | 0 | 0 | 0 |
| capital_one | 12 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 12 |
| wilson_muir | 8 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 8 |
| first_farmers | 6 | 6 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| linkbank | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| altana | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 3 |
| apex_scanned | 3 | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| dakota_west | 3 | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| first_community | 3 | 3 | 0 | 0 | 0 | 0 | **3** | 0 | 0 |
| midflorida | 3 | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| atb | 2 | 0 | **2** | 0 | 0 | 0 | **2** | 0 | 0 |
| southside_scanned | 2 | 1 | **1** | 0 | 0 | 1 | **1** | 0 | 0 |
| ibc | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| texas_bank | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

**Match rate where the check runs: 1,396 / 1,445 = 96.6% of comparable
directions; 1,069 / 1,095 = 97.6% of comparable documents.**

### 2.1 Parsers that print nothing this check can read

Every direction `not_printed`, so the whole population is out of scope until a
parser card reads the counts these banks do print:
`wells_fargo` (221), `navy_federal` (48), `truist` (48), `pnc` (45),
`td_us` (30), `bluevine` (29), `regions` (24), `relay` (22),
`american_express` (12), `citizens` (8), `desjardins` (6), `bmo` (4),
`chase_export` (4), `navigant` (4), `secu` (4), `b1` (3), `banco_popular` (3),
`farmers_merchants` (3), `santander` (3), `cibc_french` (2), `consumers` (2),
`columbia_bank` (1), `first_citizens` (1). Total **527 documents** — plus
16 `bank_of_america` and 1 `chase` document whose layout printed no summary,
which is the 544 in §1.

Two of those entries are proposal §3.4 and open question D6 verbatim: **Wells
(221 documents) and PNC (45) are the two banks with the strongest printed count
oracles in the archive and both report `not_printed` because no parser assigns
the field.** `farmers_merchants` and `chase_export` are worth a separate look —
both modules *do* assign the field, so `not_printed` there means the printed
block did not match on these particular layouts.

---

## 3. The semantics mapping table

Encoded as data with provenance in `telemetry/stated_counts.SEMANTICS`, keyed
by registry parser id × direction. A parser absent from the table falls to
`UNSURVEYED`, which is **incomparable** — the observer refuses to compare
semantics nobody has read rather than defaulting to equality. That default is
what makes the table's completeness auditable rather than assumed.

| parser | credit | debit | argument |
|---|---|---|---|
| atb, demo_national, farmers_merchants, first_community, first_farmers, ibc, linkbank, midflorida, rbc, rbc_french, scotiabank, td_canada, td_canada_native, mission_valley, dakota_west, apex_scanned, southside_scanned | comparable | comparable | one printed figure per direction meaning "every row in this direction" |
| capital_one | comparable | **incomparable** | `service_charge_excluded_from_printed_debit_count` |
| texas_bank | comparable | **incomparable** | `service_charge_excluded_from_printed_debit_count` |
| chase, chase_export | comparable | **incomparable** | `category_subtotal_sum` |
| bank_of_america | comparable | **incomparable** | `cheques_excluded_from_printed_debits` |
| altana | **incomparable** | **incomparable** | `label_scoped_subset` |
| us_bank | **incomparable** | **incomparable** | `category_subtotal_sum_split_by_sign` |
| wilson_muir | **incomparable** | **incomparable** | `multi_category_sum` |
| pnc, wells_fargo | — | — | `SECTION_LEVEL_ORACLES`: printed evidence exists, the schema cannot hold it (§5) |

### 3.1 BofA — comparable-with-mapping vs incomparable, decided

The card asks for a decision with a justification. **Decision: incomparable for
phase 1, and the mapping is rejected — because the measurement shows the
mapping makes it worse.**

BofA prints `# of withdrawals/debits` and, separately, `Total # of checks`, and
the Checks section's rows are recorded by the parser as debits. Three BofA
summary readers disagree about what to store:

| reader | `analysis/bofa.py` | stores |
|---|---|---|
| native summary | `:391-393` | the raw printed figure |
| table summary | `:515-516` | the raw printed figure |
| repair | `:589` | `debit_count + (check_count or 0)` |

The payload does not record which path ran, so the expected side means two
different things across one bank's 360 documents. The counterfactual, measured
over all 344 BofA documents that print a debit count:

| form of the expected side | would-be `match` | would-be `mismatch` |
|---|---|---|
| raw `# of withdrawals/debits` | **237** | 107 |
| `+ check_count` (the repair path's mapping) | 153 | **191** |

The mapping one third of the parser already applies would be **wrong on 191 of
344 documents** — worse than doing nothing. Asserting either form as *the*
expected side would manufacture between 107 and 191 mismatches on a bank whose
credit direction is 344/344 clean. This is the sign-off's "cheques folded into
debit categories" class exactly, and the correct phase-2 move is a BofA parser
card that makes the three readers agree on one documented scope — not a
platform mapping.

### 3.2 The service-charge class — capital_one and texas_bank

Both banks print a debit count and a *separate* service-charge line with no
count of its own, whose money is nonetheless inside the printed debit total.
The parsers record the service charge as a debit **row**.

- `capital_one`: `'N Checks/Debits ($x)'` and `'Service Charges ($y)'` are
  distinct summary lines (`analysis/capital_one.py:20-28`, `:189-197`).
- `texas_bank`: the parser proves it on itself — its acceptance gate is
  `debit_sum == debits + service_charge` (`analysis/texas_bank.py:108`,
  `:111-112`), i.e. it *requires* the service-charge row to be a debit row
  whose money sits outside the printed `Checks/Debits` figure.

Measured: **12 of 12 capital_one documents and 1 of 1 texas_bank document
disagree by exactly +1 captured debit**, every one with a non-zero
`stated_service_charge`, every one with `debit_coverage == 1.0` and
`sum_delta == 0.0`. The rows are right; the scopes differ by one printed line.
`stated_debit_count + 1 where a service charge is printed` is the mapping a
phase-2 parser card should encode. **Phase 1 does not encode it**: changing the
expected side is exactly what phase 1 may not do, and doing so would have
produced 13 mismatches — 4 of them on pinned-corpus PASS documents (§7).

### 3.3 The empirically-clean incomparables

The sign-off named category subtotals and three-way sums as classes where a
mismatch must never be forced. The vocabulary honours that. The counterfactual
says those classes are, in this archive, exact:

| parser | direction | would-be `match` | would-be `mismatch` |
|---|---|---|---|
| chase | debit (closed label-list sum) | **387** | 0 |
| us_bank | credit + debit (category sums split by sign) | **40 + 40** | 0 |
| wilson_muir | credit + debit (two- and three-way sums) | **8 + 8** | 0 |

**This is the single most useful number in the document for phase 2.** Chase is
the largest parser in the archive and its category-subtotal debit sum
reproduces the rows on 387 of 387 documents. The risk R1 named ("an
exact-equality check across twenty parsers is a bet") is real in shape and, for
these three, empirically zero. A phase-2 card can promote chase/us_bank/
wilson_muir to comparable **on this evidence**, with the caveat that a
label-list sum is only as complete as its label list, so a new Chase layout is
a silent under-count of the *expected* side rather than a loud failure.

`altana` is the opposite: 3 of 3 documents disagree in **both** directions
(credit +2/+2/+1, debit −2/−2/−1), and altana sets no `stated_total_credits` or
`stated_total_debits` at all — so no money check anywhere in the platform can
see these documents, and the count is the only instrument that exists for them.
Its printed counts are gated equal to *label-matched* rows
(`analysis/altana.py:187-190`), which is why both directions are incomparable
and why the disagreement is a semantics question, not a defect claim.

---

## 4. Would-be-flagged populations

Documents where at least one direction is `mismatch`, by the outcome class the
platform assigns **today**. Aggregate counts per parser; hashes are in the
JSON output (`--json`, key `would_be_flagged`), never statement content.

| current outcome | parser | documents |
|---|---|---|
| **validated** | **first_community** | **3** |
| withheld | td_canada_native | 10 |
| withheld | rbc | 6 |
| withheld | scotiabank | 4 |
| withheld | atb | 2 |
| withheld | southside_scanned | 1 |
| review | — | 0 |

**26 documents in total; 3 of them currently publish a number.** That is the
critical list, and it is three documents.

### 4.1 The three validated documents — `first_community`

All three are `validated`, all three have `recon.ok == True`,
`credit_coverage == 1.0`, `debit_coverage == 1.0` and `sum_delta == 0.0`, and
all three reproduce the printed **credit** count exactly. What disagrees is the
debit count, short by 1, 7 and 1 rows against `'N Debits This Period'` — a
whole-direction printed figure with no category structure to hide behind
(`analysis/first_community.py:123-125`).

**This is §3.2 of the proposal, alive:** the money reconciles to the cent and
the row count does not, so no amount-based check in `analysis/reconcile.py` can
see it and none did. It is the strongest available evidence that count
evidence is a real, independent axis.

It is **not** adjudicated here. Phase 1 takes no truth-set action, and whether
the seven rows are missing, merged, or counted differently by the bank is a
question only the PDF bytes can settle.

### 4.2 The 23 already-withheld documents

Every one is already `withheld` with `recon.ok == False`, so the check agrees
with the platform's existing refusal rather than contradicting it. Two shapes:

- **`td_canada_native` (10) — the RBC class, still live.** Nine of the ten are
  perfectly antisymmetric: the credit count is short by exactly the amount the
  debit count is long (e.g. 22/130 printed vs 18/134 captured, 18/150 vs
  14/154). Rows on the wrong side of the ledger. A ready-made parser card.
- **`rbc` (6), `scotiabank` (4), `atb` (2), `southside_scanned` (1) — gross
  detail loss.** Coverage ratios from 0.45 to 10.8 and large `sum_delta`s; the
  count restates what the money check already refused.

---

## 5. PNC — the disclosure, restated as the sign-off requires

**The PNC witness is a per-SECTION item count and is NOT expressible in this
check's schema. This check would not have caught it.**

`W3_TRACKA_LOG.md` §3.3/§3.7: PNC's section list is also its list of section
*boundaries*, so an unknown section is swallowed by the one above it and its
rows take that section's direction. For `Fee Refunds` — always printed inside
`Deposits and Other Additions` — **no amount changed sign and no direction
total changed**, so a per-direction count is blind to it by construction. It
would have caught the `Checks and Substitute Checks` case (13 documents), where
a whole section was unread and both the debit count and the debit money were
short — but the money check catches that one too.

PNC also does not populate `stated_credit_count` / `stated_debit_count` at all,
so all **45 PNC documents report `not_printed`** — which is true of the schema
and false of the document. That gap is recorded as data in
`telemetry/stated_counts.SECTION_LEVEL_ORACLES` alongside Wells' unread
per-account `Totals` line (221 documents), so the disclosure travels with the
tool instead of living only in a paragraph.

The strongest form of this check is per section. The schema has nowhere to put
it. Recorded, not proposed (proposal open question 5).

---

## 6. Direction, not sign — the proof

`analysis/metrics.py:186-191` counts `t.amount >= 0` as a deposit, so a
zero-amount row is counted as a deposit whatever column the bank printed it in.
The observer counts by `Transaction.direction` and computes the sign-keyed
count alongside as a counterfactual.

**The concrete example class: 216 zero-amount rows exist across 58 analysed
documents, and 214 of them are printed in the DEBIT column** — 171 across 51
`bank_of_america` documents, 42 across 5 `scotiabank` documents, 1 in
`wells_fargo`. Only 2 (one `td_us` document) are printed as credits. A
sign-keyed count moves all 214 debit-printed rows into the credit bucket; the
direction-keyed count moves none of them.

Re-running the identical comparison keyed on sign instead of direction:

| | comparisons |
|---|---|
| `sign_false_mismatch` — direction says `match`, sign would say `mismatch` | **51** |
| `sign_false_match` — direction says `mismatch`, sign would say `match` | **0** |

**49 documents, all currently `validated`, would be wrongly flagged by a
sign-keyed count. Zero real defects would be found by it that direction misses.**

A worked example (`bank_of_america`, `C7EEF01B…`, currently `validated`, 4
zero-amount rows, all printed as withdrawals):

```
credit: stated 16   captured (direction) 16   -> match
        captured (sign)      20   -> would be mismatch
```

Its printed credit count is 16, our credit rows are 16, and a sign-keyed check
would have counted 20 and called a correct document wrong. That is the RBC §5.5
row class in a bank that never had the RBC defect, and it is why the
recommendation in proposal §4.1(a) is load-bearing rather than stylistic.

Proposal open question 1 asked, per parser, how often direction and sign
disagree — if never, the check is weaker than §3.2 claims. Answer: they
disagree on **214 rows across 57 documents in four parsers**, and the
disagreement is one-sided in exactly the direction that matters. Two of those
four parsers (`wells_fargo`, `td_us`) print no count at all, so the whole
measurable effect lands on `bank_of_america` and `scotiabank`.

---

## 7. The pinned 109

`docs/adb-audit-results.csv` pins 109 corpus-relative paths; the observer
hashes those PDFs directly and joins on `content_sha256` (a path is not an
identity — the corpus root is shared with untracked discovery material).
**106 PASS / 3 WITHHELD is untouched by this card: phase 1 triggers NO
re-baseline and takes NO truth-set action, per D5.**

### 7.1 Pinned PASS documents with a vocabulary `mismatch`: ONE

| hash | parser | credit | debit |
|---|---|---|---|
| `08B2A61B860AF109…` | first_community | `match` 76 = 76 | **`mismatch` stated 202, captured 195** |

One of the three §4.1 documents is in the pinned corpus. It is a PASS document
whose ADB audit is green, whose money reconciles exactly, and whose captured
debit rows are seven short of the bank's own printed debit count.

**D5 material, adjudication-first, no action taken.** Per the sign-off: a
pinned-PASS disagreement is adjudicated against printed-bank evidence first,
and any phase-2 movement of a pinned expected result requires the formal
ceremony (`W3_TRACKA_LOG.md` §2.2). Note the audit CSVs carry `transactions`
(one total) and **no per-direction count column at all**, so there is no
audited value to adjudicate against: settling this needs a forensic pass from
the PDF bytes in the idiom of `docs/adb-withheld-second-pass.md`. Proposal
risk R2, realised, on exactly one document.

### 7.2 Pinned PASS documents where the counterfactual disagrees: 14

Reported separately and explicitly **not** as mismatches — the whole point of
the closed vocabulary is that "we decline to say" is a different statement from
"we say this is wrong".

| parser | pinned PASS docs | counterfactual |
|---|---|---|
| bank_of_america | 6 | 4 would-be mismatch raw; **all 6** would-be mismatch under the `+check_count` mapping |
| capital_one | 4 | all 4 would-be mismatch, delta exactly +1 (the service-charge line) |
| altana | 3 | all 3 would-be mismatch in both directions |
| texas_bank | 1 | would-be mismatch, delta +1 |

**Read this as the cost of getting the semantics wrong: a phase 2 that treated
these four banks as comparable would move 14 pinned PASS documents into the
flagged population, and the evidence in §3.1-§3.3 says at least 5 of those
would be the check misreading the document rather than the document being
wrong.** Phase 1 exists precisely so this is known before anything can move.

---

## 8. Zero-change proof

### 8.1 The production path is byte-identical

```
$ git rev-parse HEAD
2f394bf3407ff4ba0f34342f648f5ba2304933b8      (base, before this card's commits)

$ git diff --stat HEAD -- analysis ocr webapp discovery
(empty)                                        exit 0

$ git status --porcelain -- analysis ocr webapp discovery
(empty)
```

Enforced going forward by `tests/test_stated_counts.py::
test_the_observer_is_not_wired_into_any_production_module`, which asserts no
file under `analysis/`, `ocr/`, `webapp/` or `discovery/` — and no module on
the telemetry *record* path — so much as mentions `stated_counts`.

### 8.2 The observer cannot write to what it observes

- **No payload mutation.** `test_the_observer_never_mutates_the_payload`
  deep-copies a payload, runs `evaluate` under four parser ids, and asserts the
  mapping is equal and its canonical JSON byte-identical afterwards.
  `Observation` and `DirectionObservation` are frozen dataclasses.
- **No cache mutation.** The join reads the artifact index through
  `sqlite3.connect(..., "mode=ro")` rather than `webapp.storage.Storage`,
  because constructing a `Storage` runs `_ensure_schema`, which *writes* a
  forward-only migration to the store it opens. An observer that can write to
  the thing it observes is not an observer.
- **No re-analysis.** The join goes through the cache's stored payloads
  directly, never through the memoizing wrappers, so no `compute` callback can
  fire: zero OCR, zero model calls, `$0.00`.

### 8.3 Suites

| proof | result |
|---|---|
| `python -m pytest -q` (default suite) | **2391 passed, 18 deselected**, exit 0 |
| `python -m pytest tests/test_stated_counts.py -q` | **55 passed**, exit 0 |
| `set -o pipefail; python -m pytest -m corpus -q` | see §8.4 |
| `python corpus_gate.py` | see §8.4 |
| `import telemetry` still pulls in no `webapp` module (T12) | asserted in the new suite |

Baseline for comparison: the default suite at base was 2,336 tests; the new
module adds 55 and changes none. There is no behavioural delta to measure
because there is no behavioural change: the corpus gate is trivially
byte-identical, and §8.4 proves it anyway as the card requires.

### 8.4 Corpus proofs

Run in this worktree at `269071e` (the observer commit), clean tree,
`set -o pipefail`, exit codes as printed.

```
$ git status --short
(empty apart from this document)

$ git diff --stat HEAD -- analysis ocr webapp discovery
(empty)

$ python -m pytest -q
2391 passed, 18 deselected, 1 warning in 167.37s
EXIT=0

$ python -m pytest tests/test_stated_counts.py -q
55 passed in 1.15s
EXIT=0

$ set -o pipefail; python -m pytest -m corpus -q
14 passed, 2395 deselected, 1 warning in 1210.26s (0:20:10)
EXIT=0

$ set -o pipefail; python corpus_gate.py
Corpus gate

[PASS] inventory: 109 pinned corpus PDFs, all on disk and audited by both oracles
[PASS] foreign_files: no non-corpus PDFs under the corpus root
[PASS] source_integrity: 109/109 pinned source PDFs match their pinned SHA-256
[PASS] balance_audit: 109 statements reproduce every audited balance field across backend, API, dashboard, CSV, XLSX, and package surfaces
[PASS] adb_audit: 109 statements reproduce every audited ADB field across backend, API, and dashboard-package surfaces
[PASS] balance_outcomes: balance: 106 pass, 3 withheld, same three statements
[PASS] adb_outcomes: adb: 106 pass, 3 withheld, same three statements
[PASS] ocr_coverage: 103 native-text + 6 committed-OCR = 109 statements resolved offline; no live OCR, no model calls
[PASS] exclusions: 0 named exclusions
[PASS] oracle_independence: 4 audit modules import no production financial mathematics

Coverage: 109 pinned PDFs (103 native text, 6 committed OCR), 0 exclusions
Ignored:  0 non-corpus PDFs under the corpus root
Outcomes: 106 PASS / 3 WITHHELD
Runtime:  393.0s

RESULT: GREEN
EXIT=0
```

**106 PASS / 3 WITHHELD, byte-identical, and the three pinned withheld keep
their documented diagnoses.** Trivially so — no analysis path changed — but the
card asks for it to be proved rather than asserted, and §7.1's single
pinned-PASS finding makes the distinction between "the gate is green" and "the
count check has nothing to say about the gate" worth having on the record.


---

## 9. Vocabulary and evaluation order (observer-side documentation)

Per direction, exactly one of `match | mismatch | not_printed |
semantics_incomparable | check_unavailable`. Evaluated in this order, and the
order is the enforcement:

1. no payload / no `statement` → `check_unavailable`
2. the expected side is absent → `not_printed`
3. the semantics are not comparable → `semantics_incomparable`
4. the captured side cannot be computed (no rows, aggregate-backed
   `UNCAPTURED` row, a row with no `direction`, not a formal statement) →
   `check_unavailable`
5. exact equality, no tolerance → `match` / `mismatch`

Step 3 sits above step 5, so **no code path reaches `mismatch` from a direction
whose semantics say `comparable=False`** — the forced-mismatch prohibition is
structural, not a caller's responsibility.
`test_an_incomparable_direction_can_never_emit_mismatch` runs every parser in
the table against a payload built to disagree and asserts it.

Step 2 sits above step 3 because with no printed evidence there is nothing for
the semantics to be about; `not_printed` is a fact about the document and
`semantics_incomparable` is a fact about the comparison.

**Independence** (`EXPECTED_FIELDS` / `CAPTURED_FIELDS` /
`FORBIDDEN_EXPECTED_SOURCES`): the expected side comes only from
`statement.stated_credit_count` / `stated_debit_count`; the captured side is
recomputed inside the observer from `statement.transactions[].direction`.
`metrics.effective_num_deposits` and its siblings — where the bank's printed
count is *copied to* (`analysis/metrics.py:353-356`) — are never read on any
vocabulary path, pinned by a tripwire mapping that raises on access.
The single labelled exception is the BofA `+check_count` counterfactual in the
advisory block, and a test asserts removing `metrics` entirely moves no
vocabulary result.

Reversals are counted **gross** and the comparison has **no tolerance**: a
count is an integer the bank printed, and the ±2% band `reconcile.py:67-71`
uses for money exists because OCR makes money approximate, not integers.

---

## 10. Recommendation to Ocean, for Gustavo

**The phase-1 evidence supports phase 2, narrowed.** Four things it establishes:

1. **The false-positive risk R1 named is real, is concentrated, and is now
   named per bank.** Every one of the 846 `semantics_incomparable` directions
   belongs to one of six documented classes, not to a diffuse "twenty parsers
   might disagree".
2. **Where the semantics are clean the check is quiet: 96.6% of comparable
   directions match, and only 3 currently-validated documents would flag.**
   A flag-to-review phase 2 restricted to the comparable set has a blast radius
   of three documents plus whatever the withheld set already refuses.
3. **It found something no money check can see** — `first_community`, 3
   validated documents, money exact to the cent, debit rows short of the bank's
   printed debit count.
4. **The direction-not-sign rule is worth 51 avoided false flags on 49
   validated documents**, and zero missed defects.

Recommended shape for phase 2, if approved:

- ship the `ReconResult` fields (proposal §7.1) and the two integrity flags
  (§7.2/§7.3) **gated on the semantics table**, so an incomparable direction
  emits nothing;
- keep `capital_one`, `texas_bank`, `bank_of_america` and `altana` incomparable
  at the platform level and open **parser cards** instead: the BofA
  three-readers disagreement, the service-charge scope, the altana label scope;
- promote `chase`, `us_bank` and `wilson_muir` to comparable on the §3.3
  evidence (387/387, 80/80, 16/16), with the label-list caveat recorded;
- adjudicate the one pinned-PASS `first_community` document from the PDF bytes
  **before** phase 2 merges, under the §2.2 ceremony, because it is the only
  document in the archive where phase 2 would move a pinned expected result.

Open questions carried unchanged: proposal open question 2 (`stated_nsf_count`
is the same shape and chose note-not-flag — consistency argues they should
match), open question 3 (`effective_num_deposits` publishes the bank's count
over our rows on 1,146 documents), open question 4 (`DIAGNOSABLE_CLASSES` is
`withheld`-only, so `review`-class count flags would be invisible in the
rollup that exists — Ocean has already ruled this extends when phase 2 lands),
and open question 5 (per-section counts, §5).
