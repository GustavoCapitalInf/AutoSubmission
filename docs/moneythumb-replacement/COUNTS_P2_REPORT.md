# COUNTS-P2 — the stated-count integrity check, PHASE 2 (flag, never withhold)

Card: `docs/agent-handoffs/COUNTS-P2.md`. Binding law: Gustavo's 2026-08-10
**STATED-COUNT CHECK** sign-off and the same day's **D5 FORENSIC
ADJUDICATION**; `PROPOSAL_STATED_COUNTS.md` §7 (pinned diff shape);
`COUNTS_P1_MEASUREMENT.md` §9/§10 (vocabulary, evidence, recommendation).
Phase 2 approved by Gustavo 2026-08-13 under the narrowed design.

- Base: `42ec03d7ad8124a7cf7d462b5834b6462308bab0` · branch `wave3-counts-p2`
- Ships: `analysis/count_semantics.py` (new), `analysis/reconcile.py` §7.1
  pinned, `analysis/pipeline.py` §7.2 amended, `telemetry/diagnostics.py` §7.3,
  `telemetry/stated_counts.py` (consumes the shared table), tests, this
  document, `W3_2_TAXONOMY.md` §3.2/§5/§10/§11/§12.
- **`ANALYSIS_STAGE_VERSION` is NOT bumped here — Ocean's at merge** (D-3:
  `integrity.flags` changes for unchanged settings).

**Headline: zero outcome movement.** The pinned 109 reproduce 100 validated /
6 review / 3 withheld before and after, the gate stays 106 PASS / 3 WITHHELD,
and the check's entire footprint on the corpus is one code on a document the
platform already refuses.

---

## 1. The pre-measurement gate (run BEFORE any production edit)

The phase-1 observer, joined to discovery run
`ca2ba0eb` (`2026-08-10T180653.021975-0000-ca2ba0eb`, 3,506 rows → **3,380
distinct documents**) against the D-3 cache at `ANALYSIS_STAGE_VERSION = 7`,
run twice: once with the phase-1 table and once with the amended table (the
three promotions applied in-process, no file edited). Read-only: no OCR, no
model call, `$0.00`.

### 1.1 The three gate conditions

| # | Condition (handoff req. 1) | Required | Measured | Verdict |
|---|---|---|---|---|
| a | pinned-PASS documents with a vocabulary `mismatch` | 0 | **0** (both tables) | PASS |
| b | fresh v7 counterfactual for every promotion | 0 would-be mismatches each | chase:debit **387 match / 0**; us_bank:credit **40 / 0**; us_bank:debit **40 / 0**; wilson_muir:credit **8 / 0**; wilson_muir:debit **8 / 0** | PASS — all three promotions ship |
| c | would-be `validated → review` movers | 0 | **0** | PASS |

The sole phase-1 pinned-PASS mismatch (`08B2A61B…`, first_community, D5
`semantics_difference`) now reads **`match` in both directions** — 3 of 3
first_community documents do. FIXUPS-1 `acd0b07` did what D5 recommendation
(a) said it would.

### 1.2 The whole archive, phase-1 table vs amended table, both at v7

| Direction results (2 per document, 6,760) | phase-1 table | amended table |
|---|---|---|
| `match` | 1,399 | **1,882** |
| `mismatch` | **46** | **46** |
| `not_printed` | 1,089 | 1,089 |
| `semantics_incomparable` | 1,154 | 671 |
| `check_unavailable` | 3,072 | 3,072 |

| Documents | phase-1 table | amended table |
|---|---|---|
| at least one direction comparable | 1,095 | 1,143 |
| **at least one direction `mismatch`** | **23** | **23** |
| an incomparable direction | 949 | 514 |
| no printed count either direction | 544 | 544 |
| no payload at all | 1,536 | 1,536 |

**The promotions move 483 directions from "we decline to say" to "we say they
agree" and produce not one new disagreement.** That is the whole case for
them, and it is measured rather than argued.

### 1.3 Drift against the phase-1 (v5) measurement, explained

| | P1 at v5 | P2 at v7 | why |
|---|---|---|---|
| `mismatch` directions | 49 | 46 | first_community's 3 debit mismatches resolved by `acd0b07` |
| mismatch documents | 26 | 23 | the same 3 documents |
| documents with no payload | 1,690 | 1,536 | BMO cell + FIXUPS-1 claimed 154 more |
| `semantics_incomparable` | 846 | 1,154 | those 154 new BMO documents print counts and their parsers are **UNSURVEYED** |

The last row is the unsurveyed default working in the field: 154 documents
from a parser family that landed *after* the semantics table was written are
silently incomparable, and no code had to be told about them.

### 1.4 The counterfactuals for the banks that stay incomparable (v7)

Every phase-1 number reproduces exactly, so nothing in §3.1-§3.2 of the
measurement was an artefact of v5:

| parser | direction | measured at v7 |
|---|---|---|
| bank_of_america | debit | raw form: 237 would-match / **107 would-mismatch**; `+check_count` form: 153 / **191** |
| capital_one | debit | 12 of 12 disagree by exactly **+1**, every one with a printed service charge |
| texas_bank | debit | 1 of 1 disagrees by **+1** |
| altana | credit + debit | 3 of 3 disagree in both directions (+1/+2 credit, −1/−2 debit) |

Pinned-PASS documents whose *counterfactual* disagrees: **14**, unchanged
(bofa 6, capital_one 4, altana 3, texas_bank 1). Not one of them is a
`mismatch`, and not one of them flags. That is the closed vocabulary doing its
job: "we decline to say" is a different statement from "we say this is wrong".

Direction-vs-sign, re-measured at v7: `sign_false_mismatch` **51**,
`sign_false_match` **0** — a sign-keyed count would still wrongly flag 51
comparisons on validated documents and would still find nothing direction
misses.

### 1.5 The one honest limit of this instrument

**Only 80 of the 109 pinned documents (78 PASS, 2 WITHHELD) appear in run
`ca2ba0eb` at all.** The archive scan and the pinned corpus are different
populations, so the cache join can speak for 78 of the 106 PASS documents and
no more. That is why the corpus proof below is not a formality: it runs the
real pipeline over all 109 and is the authoritative statement about the truth
set. It found one count flag the cache join could not see (§5.2) — on a
document that was already withheld.

---

## 2. What shipped, per file, verbatim

### 2.1 `analysis/count_semantics.py` — NEW (448 lines)

The authoritative parser-id × direction table, with the phase-1 argument and
`file:line` provenance on every entry, `UNSURVEYED = not comparable` as the
default, `SECTION_LEVEL_ORACLES` for PNC/Wells, and two functions:
`semantics_for()` and `counts_comparable()`. Comparable/incomparable split as
approved:

- **comparable** — atb, capital_one:credit, **chase (both, debit PROMOTED)**,
  chase_export:credit, farmers_merchants, first_community, first_farmers, ibc,
  linkbank, midflorida, rbc, rbc_french, scotiabank, td_canada,
  td_canada_native, texas_bank:credit, demo_national, mission_valley,
  dakota_west, apex_scanned, southside_scanned, bank_of_america:credit,
  **us_bank (both, PROMOTED)**, **wilson_muir (both, PROMOTED)**;
- **incomparable** — capital_one:debit, texas_bank:debit,
  bank_of_america:debit, altana:credit, altana:debit, chase_export:debit;
- **absent by design** — pnc, wells_fargo (section-level oracles);
- **everything else** — UNSURVEYED, and therefore silent.

The chase entry carries the label-list caveat the card required, in the entry
itself:

> CAVEAT, recorded because it is the failure mode this entry buys: a
> label-list sum is only as complete as its label list, so a NEW Chase layout
> printing a debit category the list does not name under-counts the EXPECTED
> side quietly rather than failing loudly, and would surface here as a count
> mismatch on correct rows. That is a flag, never a withholding, and the
> remediation is the Chase parser card.

### 2.2 `analysis/reconcile.py` — §7.1, PINNED (+35 / −0, PROTECTED MODULE)

Three hunks, semantically identical to the pinned text; the only difference
from the proposal's `+~24` is the four constructor arguments the proposal
described in prose and the blank lines around them. **No existing line
changed. `ok` is untouched. No `issues.append`.**

Fields, at `analysis/reconcile.py:41-50`, after `settled_debit_detail`:

```python
    # Count coverage: did the captured rows reproduce the bank's own printed
    # per-direction COUNTS? Keyed on Transaction.direction (the column the bank
    # printed the row in), NOT on the sign of the amount: a zero-amount row has
    # a column and no money, and that is exactly the class no amount-based
    # check can see. None = the bank printed no count, or this statement is
    # aggregate-backed — not applicable, never a zero.
    stated_credit_count_matches: bool | None = None
    stated_debit_count_matches: bool | None = None
    captured_credit_count: int | None = None
    captured_debit_count: int | None = None
```

Computation, at `analysis/reconcile.py:238-258`, immediately before
`ok = not issues` (:260):

```python
    # Deliberately appends NO issue: `ok` gates the ADB (pipeline.py:399 ->
    # metrics.py:313), so an issue here would withhold the document. The
    # consequence of a count mismatch is decided in
    # pipeline.assess_document_integrity, one layer up, where it can be a flag.
    credit_count_matches = debit_count_matches = None
    captured_credit_count = captured_debit_count = None
    aggregate_backed = any(
        "UNCAPTURED" in t.description.upper() for t in stmt.transactions
    )
    if stmt.transactions and not aggregate_backed:
        if stmt.stated_credit_count is not None:
            captured_credit_count = sum(
                1 for t in stmt.transactions if t.direction == "credit"
            )
            credit_count_matches = captured_credit_count == stmt.stated_credit_count
        if stmt.stated_debit_count is not None:
            captured_debit_count = sum(
                1 for t in stmt.transactions if t.direction == "debit"
            )
            debit_count_matches = captured_debit_count == stmt.stated_debit_count
```

Constructor, at `analysis/reconcile.py:277-280`:

```python
        stated_credit_count_matches=credit_count_matches,
        stated_debit_count_matches=debit_count_matches,
        captured_credit_count=captured_credit_count,
        captured_debit_count=captured_debit_count,
```

### 2.3 `analysis/pipeline.py` — §7.2, AMENDED (+31 / −0, PROTECTED MODULE)

One import at `:9` (`from .count_semantics import counts_comparable`) and one
block at `:237-266`, inserted immediately after the `not_a_formal_statement`
block exactly as pinned. The amendment is the `counts_comparable(...)`
conjunct in each condition, plus the resolution of the parser id:

```python
    formal = registration is None or registration.formal_statement
    claiming = dispatch.parser_id if dispatch is not None and dispatch.outcome == "claimed" else None
    if formal and counts_comparable(claiming, "credit") and recon.stated_credit_count_matches is False:
        flags.append("credit_count_mismatch")
        notes.append("captured credit rows do not match the bank-stated credit count")
    if formal and counts_comparable(claiming, "debit") and recon.stated_debit_count_matches is False:
        flags.append("debit_count_mismatch")
        notes.append("captured debit rows do not match the bank-stated debit count")
```

(The 20 comment lines above it, at `:237-258`, argue the three gates; they are
in the committed diff and quoted in full in the commit `524a4d9`.)

**One deliberate narrowing beyond the pinned text, flagged for Ocean.** The
pinned diff had only `formal` and `is False`; the semantics gate needs a
parser id, and `_registration_for` (which the pinned `formal` uses) resolves
by **bank label** when nothing claimed — the LLM path. A semantics entry is
evidence about *what one parser's reader produced*, not about the bank's
paper, so the gate uses `dispatch.parser_id` **only when the dispatch
claimed**. This is strictly quieter than the alternative and it makes the
production gate key identical to the measurement instrument's key
(`rows.csv:parser_id`), which is what lets §1 predict §5. `possible_document_issue`
is NOT extended (decision D3), `ok` is not read, and no issue is appended.

**Insertion position and payload order.** The block sits where the pinned diff
put it, which is *above* the ambiguity/crash/contradiction flags. A document
that gets no count flag therefore has a byte-identical `integrity.flags` list;
a document that gets one and also carries a later flag sees the new flag
inserted before it. The pinned design already ruled on this — "flag insertion
order is cosmetic: `:283` de-duplicates while preserving order,
`classify_outcome` tests membership, and the taxonomy ranks by
`CLASS_PRECEDENCE`, not by position" — and no pinned-corpus document is in
that position (Ace_Auto's flag appends at the end).

### 2.4 `telemetry/diagnostics.py` — §7.3 (+39 / −8)

- `DIAGNOSTICS_VERSION` **2 → 3** (`:51`), with the v3 note in the constant's
  own docstring;
- `DIAGNOSABLE_CLASSES = ("withheld", "review")` (`:74`), per the standing
  Ocean ruling, coupled to this merge;
- `INTEGRITY_FLAGS` gains `credit_count_mismatch` / `debit_count_mismatch`
  (`:131-132`) — which is what satisfies the §9 drift guard;
- `CLASS_OF` maps both to `detail_coverage` (`:300-301`), rank 9. Neither is in
  `ADVISORY_CODES`: they are financial findings, not consequences.

### 2.5 `telemetry/stated_counts.py` (+~30 / −~330)

The observer's forked copy of the table is **deleted** and imported from
`analysis.count_semantics` instead, so the instrument that predicts the flag
population and the code that emits it cannot disagree. `OBSERVER_VERSION`
**1 → 2** (the constant's contract is "bumped when the vocabulary, the
evaluation order or the semantics table changes" — the table changed). The
vocabulary, the evaluation order, every guard and the CLI are untouched, and
`analysis/` still does not mention this module: the dependency runs
telemetry → analysis and the phase-1 not-wired test still proves it.

### 2.6 `W3_2_TAXONOMY.md`

§3.2 gains both codes; §5 restates the acceptance property ("the 100 validated
produce empty diagnostics"); §10 open questions 1 and 2 are marked RESOLVED;
§11 gains the v3 entry with the blast radius; §12 is updated from "when phase 2
lands" to what landed — the document itself said this section would be
replaced at this merge.

---

## 3. Test inventory

`tests/test_count_semantics.py` — **37 new tests**:

| Group | Tests |
|---|---|
| the table | both directions per entry with an argument >40 chars; every id exists in the registry; **the comparable/incomparable split is pinned exactly** so a promotion can never be incidental; every promoted entry carries its counterfactual; unknown direction raises |
| the default | unsurveyed → UNSURVEYED and `comparable is False` for `None`, `""`, a fabricated id and a **real unsurveyed registration**; the witness is asserted to be a real registration absent from the table; section-level oracles never comparable |
| one table | the observer's `SEMANTICS`, `UNSURVEYED`, `semantics_for`, `SECTION_LEVEL_ORACLES` are the *same objects* as production's |
| reconcile (§7.1) | match records True + captured totals; a row on the wrong side is caught in both directions **while the money check sees nothing**; the zero-amount witness (direction, not sign) with the sign-keyed counterfactual computed in the test; absent count → None, never 0; one direction never inferred from the other; aggregate-backed → None; no rows → None; reversals gross; **the issue list is byte-identical to the same statement with the counts removed** |
| independence | `metrics.effective_num_deposits` is proven to carry the bank's figure while the check still reports our rows and still disagrees; plus a source guard that `reconcile.py` contains no `effective_num` / `num_deposits` |
| pipeline (§7.2) | comparable mismatch → both flags, `review`, `recon.ok` True, `possible_document_issue` False; notes carry no digits; matching → no flag; **incomparable-never-flags, parametrized over every incomparable entry in the table**, asserting the measurement still says `False` and the flag is still absent; **unsurveyed-never-flags**; `None` never flags on both populations that produce it; non-formal never flags; unclaimed/bank-label never flags; ambiguous never flags; only the disagreeing direction flags |
| end to end | a count flag alone classifies `("review", "integrity_flags")` and never `withheld`; both codes registered and classed `detail_coverage`; a grep-level guard that the count block contains no `issues.append` and neither flag reaches `possible_document_issue` |

**Mutation-checked** (each mutation applied, suite run, mutation reverted):

| Mutation | Tests that fail |
|---|---|
| remove the semantics gate from both conditions | **8** |
| `recon.stated_*_count_matches is False` → `not recon.stated_*_count_matches` | **1** |
| count by `amount >= 0` / `< 0` instead of by `direction` | **7** |

Changed elsewhere: `tests/test_stated_counts.py` (the both-directions
incomparable fixture moved `us_bank` → `altana`, since us_bank was promoted;
55 tests still pass unchanged otherwise), `tests/test_diagnostics.py` (the
scope test restated + a new one proving a review document is diagnosed from
its count flag; the mixed-version test pins v3), `tests/test_telemetry_corpus.py`
(the anchor re-pinned, §5.2).

---

## 4. Proof transcript

Run in the worktree, clean tree, exit codes as printed.

```
$ git rev-parse HEAD                       (base)
42ec03d7ad8124a7cf7d462b5834b6462308bab0

$ python -m pytest -q
2513 passed, 18 deselected, 1 warning in 187.54s
EXIT=0

$ python -m pytest tests/test_count_semantics.py -q
37 passed in 1.57s
EXIT=0

$ python -m pytest tests/test_stated_counts.py -q
55 passed in 0.27s
EXIT=0

$ set -o pipefail; python -m pytest -m corpus -q
14 passed, 2517 deselected, 1 warning in 1130.78s (0:18:50)
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
Runtime:  384.4s

RESULT: GREEN
EXIT=0
```

**Byte-identical on outcome classes.** Every audited field reproduces across
backend, API, dashboard, CSV, XLSX and package surfaces; the two oracles agree
on the same three withheld statements; the payload's four new
`reconciliation` keys are additive (`asdict(ReconResult)`, and no consumer
enumerates that section's keys — `webapp/app.py:188` copies it whole), so
nothing an audit reads moved.

Baseline for comparison: the default suite at base was 2,475 tests; this card
adds 38 and changes none of the others' outcomes.

---

## 5. The predicted flag population

### 5.1 By parser × current outcome class (archive, 3,380 documents, v7)

| current outcome | parser | documents | directions flagged |
|---|---|---|---|
| **withheld** | td_canada_native | 10 | credit + debit |
| **withheld** | rbc | 6 | credit + debit |
| **withheld** | scotiabank | 4 | credit + debit |
| **withheld** | atb | 2 | credit + debit |
| **withheld** | southside_scanned | 1 | credit + debit |
| **validated** | — | **0** | — |
| **review** | — | **0** | — |

**23 documents, every one already `withheld` with `recon.ok is False`.** The
check agrees with a refusal the platform already makes; it contradicts nothing
it publishes. Ten of the 23 are the RBC row-on-the-wrong-side class in
td_canada_native (nine perfectly antisymmetric), which is a ready-made parser
card; the other 13 are gross detail loss the money check already refuses.

Zero of the 3,380 change outcome class, because a flag on a `withheld`
document changes nothing (`telemetry/record.py:296` returns before the flag
check) and no `validated` or `review` document carries one.

### 5.2 On the pinned 109 (the real pipeline, not the cache join)

100 validated / 6 review / 3 withheld — **the canonical split, unchanged**.
Gate: 106 PASS / 3 WITHHELD, unchanged.

The check's entire footprint is **one code**:
`integrity:debit_count_mismatch` on `Ace_Auto_Final_Cut.pdf`
(farmers_merchants), one of the three pinned withheld. Its documented
diagnosis is `detail_coverage` — "the supplied PDF has incomplete transaction
detail, 11 of 26 checks/debits visible" — and the count says exactly that:
the debit COUNT is short in the same way the debit MONEY is. **Primary class
unchanged, outcome unchanged, one code added to a document that already had
ten.**

This document is not in run `ca2ba0eb` (§1.5), which is why the archive
instrument did not predict it. It is a true positive, on an already-refused
document, in the class the check was built for — and it is the reason the
corpus proof is a proof and not a formality.

The six review documents are unaffected and are now enumerated in the corpus
test: `Chase Business.pdf` (advisory_only — a transaction export) and five
`page_coverage` documents. **None carries a count code.**

---

## 6. Promotions: shipped and dropped

| candidate | evidence at v7 | decision |
|---|---|---|
| `chase:debit` | 387 match / 0 mismatch of 389 documents (2 print no debit count) | **SHIPPED**, with the label-list caveat in the entry |
| `us_bank:credit` | 40 / 0 | **SHIPPED** |
| `us_bank:debit` | 40 / 0 | **SHIPPED** |
| `wilson_muir:credit` | 8 / 0 | **SHIPPED** |
| `wilson_muir:debit` | 8 / 0 | **SHIPPED** |
| `chase_export:debit` | **no evidence exists** — 4 of 4 documents print no debit count, so the counterfactual is empty | **DROPPED.** Same reader as chase; promoted on chase's evidence it would be an unproven mapping shipped on a sibling's numbers. Recorded in the entry. |
| `capital_one:debit`, `texas_bank:debit` | 12/12 and 1/1 disagree by exactly +1 (the service-charge line) | not promoted — parser card |
| `bank_of_america:debit` | raw 107 wrong / mapped 191 wrong of 344 | not promoted — parser card (make the three readers agree) |
| `altana` both | 3/3 disagree both directions; printed counts gated to label-matched rows | not promoted — parser card |

Nothing was promoted whose fresh v7 counterfactual was non-zero, and one
candidate that was never in the card's list (`chase_export:debit`) was
considered and refused for lack of evidence.

---

## 7. Risks

| # | Risk | Severity | Position |
|---|---|---|---|
| R1 | **A new Chase layout under-counts the expected side** (label-list sum) and flags correct rows. | Medium | Named in the table entry itself. It is a flag, never a withholding; REEF-CHASE-LAYOUTS' new registrations are UNSURVEYED and cannot flag at all, so this can only arrive through a change to the *existing* chase reader. |
| R2 | **A parser card that changes a printed-count scope** (capital_one, texas_bank, bofa, altana) must also flip its table entry, or the check stays silent after the reason for silence is gone. | Medium | The entries say what would have to change. The comparable/incomparable split is pinned by a test, so flipping one is a deliberate, reviewed edit. |
| R3 | **`DIAGNOSABLE_CLASSES` widening changes the rollup denominator**, not just its vocabulary: 3 → 9 diagnosed on the pinned 109. | Low, certain | `DIAGNOSTICS_VERSION` 3 makes it visible; the v3 changelog says both halves are non-comparable across the boundary. |
| R4 | **The archive instrument and the pinned corpus are different populations** (§1.5), so a cache-join prediction can miss a corpus document. | Medium | Proven concretely by Ace_Auto. Mitigation is the one used here: predict from the cache, *verify* on the corpus. |
| R5 | Two zero-count directions could both be "right" for the wrong reason on a bank whose parser gates on counts already (`community_section`, `scanned_small_bank`). | Low | Their entries say so; a claimed document has matching counts under the gate's own SIGN-keyed test, which is a weaker key than ours, so the check still has something to say. |
| R6 | `stated_nsf_count` remains note-not-flag while the per-direction counts are now flags. | Low | Proposal open question 2, unchanged and not in this card's scope. |

---

## 8. Unresolved questions

1. **`possible_document_issue` (D3).** A count mismatch sets telemetry
   `review` while the payload's `quality.corporate_use` still says `approved`.
   Deliberately unchanged here (D3: "not in phase 2"), and the inconsistency
   is real either way. W3-4 adjudication question.
2. **`effective_num_deposits` (open question 3).** The platform still
   publishes the bank's printed count over its own rows on ~1,146 documents,
   including the 23 where we now say the two disagree. Flagging the
   disagreement while continuing to publish the bank's side is coherent for
   `review` and worth a ruling.
3. **`stated_nsf_count` (open question 2).** Same shape, chose note-not-flag.
   Consistency argues the two should match; neither was changed.
4. **Per-section counts (open question 5).** PNC's stronger oracle still has
   nowhere to live in the schema. Recorded, not proposed.
5. **The four parser cards this measurement has fully specified** — BofA's
   three disagreeing readers, the capital_one/texas_bank service-charge scope,
   the altana label scope, and td_canada_native's ten wrong-side documents.
   Each has its evidence in §1.4/§5.1 and each would move documents out of
   `semantics_incomparable` or out of `withheld`. Sequencing is Ocean's.
6. **Chase parser-id coupling with the parallel cell.** REEF-CHASE-LAYOUTS may
   register new Chase layouts under new ids; those ids are UNSURVEYED and
   silent by construction, which is correct and deliberate. If that cell
   intends its new layouts to be covered by the count check, that is a
   follow-up edit to this table with its own counterfactual.
