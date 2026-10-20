# PROPOSAL — the platform-level stated-count integrity check

PLATFORM-PROPOSALS, 2026-08-10. Branch `wave3-platform-proposals`.
Card: `docs/agent-handoffs/PLATFORM-PROPOSALS.md`, deliverable A.
**Status: PROPOSAL. No code was written. `analysis/` was opened read-only.**
Ocean reviews; **Gustavo signs off before any implementation exists anywhere.**

Every claim below is sourced to a log section or a `file:line`. Where a number
could not be measured inside this card's read-only mandate, it is labelled
`ESTIMATE` and the exact measurement that would settle it is given.

---

## 1. The proposal in one paragraph

The platform extracts `stated_credit_count` and `stated_debit_count` from
twenty parser modules, **publishes them as its own deposit and withdrawal
counts** (`analysis/metrics.py:353-356`, `:368-371`), and never once compares
them against the rows it also publishes. This proposal adds that comparison. It
recommends a **per-direction count check computed in `analysis/reconcile.py`
and surfaced as an integrity flag in `analysis/pipeline.py`** — which lands the
document in `review` with its value still published — and it recommends
explicitly **against** the fail-closed placement that would withhold, until the
false-positive rate has been measured. It also recommends a **two-phase
rollout**: an observe-only phase that measures the check over the frozen
baseline at zero vendor cost, and a flag-emitting phase that is only entered if
the measured evidence supports it.

---

## 2. The gap, as recorded

W3-2 §2 found it while surveying what checks `analysis/` actually performs:

> There is **no platform-level check comparing `stated_credit_count` /
> `stated_debit_count` against the captured row counts**. The only count
> comparison in the tree is parser-local (`analysis/community_section.py:208`)
> and never reaches the payload as an issue.

W3-2 declined to invent one, correctly: a diagnostics card that added an
analysis check would be performing analysis rather than reporting it
(`W3_2_TAXONOMY.md` §2, §10 open question 1). The gap has been re-raised by
every Track A cell since — `W3_TRACKA_LOG.md` §5.7 item 4 (RBC), §B7.3 (BofA),
§3.7 item 3 (PNC), §1.8 item 4 (us_bank) — always with the same disposition:
protected-module change, out of this cell's scope.

This document is the card those four findings were queued against.

---

## 3. Why it is worth doing — four witnesses and one mechanism

### 3.1 The mechanism: the platform already publishes an unverified count

This is the argument that was not in any of the four carried findings, and it
is the strongest one.

`analysis/metrics.py:346-371` sets the *published* counts:

```
if trust_stated_summary is True:            # metrics.py:346
    ...
    if stmt.stated_credit_count is not None:
        m.effective_num_deposits = stmt.stated_credit_count      # :353-354
    if stmt.stated_debit_count is not None:
        m.effective_num_withdrawals = stmt.stated_debit_count    # :355-356
elif trust_stated_summary is None:          # :361  (identical block at :368-371)
```

`effective_num_deposits` starts as the row-derived count (`metrics.py:304-305`)
and is then **silently overwritten by the bank's printed figure** whenever the
bank printed one and the summary reconciled — or was merely unverifiable. Both
values are serialized (`analysis/serialization.py:102-104`, `asdict(metrics)`),
so the payload carries the row count and the bank count side by side and
asserts nothing about their relationship.

The consequence, stated plainly: **on a document where the two disagree, the
platform publishes the bank's count next to our transaction list, and nothing
anywhere says they describe different ledgers.** The proposed check does not
introduce a new claim. It checks a claim the platform already makes.

### 3.2 A count is the only check that is not a function of the amounts

Every existing completeness check in `analysis/reconcile.py` is arithmetic over
amounts: the sum check (`:93-98`), the running-balance chain (`:108-122`), the
summary identity (`:131-153`), credit and debit coverage (`:209-226`). All of
them are blind, by construction, to any rearrangement of rows that preserves
sums.

RBC is the witness. `W3_TRACKA_LOG.md` §5.5:

> **8 of them improved**: six had a credit/debit COUNT that disagreed with the
> bank's own summary (zero-amount and equal-amount rows on the wrong side) and
> two had a credit TOTAL that was wrong by tens of thousands while still
> passing ADB.

Six documents, **already validated**, passing the full ADB suite and every
reconciliation check, with a per-direction count that contradicted the bank's
own printed summary. The class that produced them — a zero-amount row on the
wrong side of the ledger, and an equal amount on each side — moves no money at
all. No amount-based check can see it. A count sees it immediately.

### 3.3 BofA: a second free population

`W3_TRACKA_LOG.md` §B7.3: BofA prints `# of deposits/credits` and
`# of withdrawals/debits` on every business statement, and the parser already
reads both (`analysis/bofa.py:390-393`, `:513-516`, `:587-589`). The check costs
nothing extra there.

### 3.4 PNC: the decisive witness, and an honest limit on what it proves

`W3_TRACKA_LOG.md` §3.7 item 3:

> the count is what caught the swallowed-section defect here, ahead of any
> money check, because a swallowed section keeps the money in the right
> direction while moving the rows.

The mechanism is §3.3 of that same section: PNC's section list is also its list
of section *boundaries*, so an unknown section is swallowed by the one above
it, and its rows take that section's direction. For `Fee Refunds` — always
printed inside `Deposits and Other Additions` in this archive — **no observed
amount changed sign**, so the credit total and the debit total both remained
correct. The defect existed only in the row-to-section attribution.

**This must be stated precisely, because the obvious reading overstates it.**
What caught PNC's defect was the bank's **per-section** item count, which
`analysis/pnc.py` reads as section structure but the `Statement` schema has no
field for. A *per-direction* count of the kind this proposal adds would not
have caught the `Fee Refunds` case (5 documents), because the direction totals
were right. It **would** have caught the `Checks and Substitute Checks` case
(13 documents), where a whole section was unread and both the debit count and
the debit money were short.

So PNC argues two things, and only the first is in scope here:

1. count evidence is a real and independent axis — **in scope**;
2. the per-direction pair is the *coarsest* form of that evidence, and a bank
   that prints per-section counts is offering a strictly stronger oracle that
   the schema cannot hold — **out of scope, and recorded as open question 5**.

PNC also does **not** populate `stated_credit_count` / `stated_debit_count`
today (no assignment exists in `analysis/pnc.py`), so PNC's 45 archive
documents would report the check as *not applicable* until a parser change
reads the subtotal table into those fields. The same is true of Wells Fargo:
`analysis/wells.py` contains no assignment to either field, and its printed
per-account `Totals` line is an unread oracle (`W3_TRACKA_LOG.md` §W7.4).

---

## 4. The check semantics, exactly

### 4.1 The comparison

For each direction independently:

```
stated  = stmt.stated_credit_count            (or stated_debit_count)
captured = number of rows in stmt.transactions whose `direction` is "credit"
                                                            (or "debit")
match   = (stated == captured)
```

Three properties, each with its reason:

**(a) Count by `Transaction.direction`, never by the sign of the amount.**
`analysis/schema.py:18` makes `direction` a required field: `'Either "debit" or
"credit"'`. It records the column the bank printed the row in. The sign records
the money. For a count the column is the correct key, and the difference is not
academic: `analysis/metrics.py:186-191` counts `t.amount >= 0` as a deposit, so
a **zero-amount row is currently counted as a deposit regardless of the column
it was printed in**. That is exactly the row class RBC §5.5 names. A count
check keyed on sign would inherit the defect it exists to catch.

**(b) Exact equality, no tolerance.** A count is an integer the bank printed.
`analysis/reconcile.py:67-71` uses a ±2% band for money because OCR and rounding
make money approximate; neither applies to an integer. `_TOL` is not used here.

**(c) No reversal adjustment.** `analysis/reconcile.py:165-207` nets settlement
reversals out of the *money* coverage because banks net them in their printed
totals. A reversal is nonetheless a printed row that the bank counted, so
netting it out of a count would create the mismatch it was meant to remove.
The counts are compared gross.

### 4.2 When the check does not run

The check is **not applicable** — not passed, not failed, and never fabricated
— in any of these cases. Each is a real population, not a hypothetical.

| Guard | Source | Reason |
|---|---|---|
| `stated_credit_count is None` (per direction, independently) | `analysis/schema.py:45-46` default `None` | The bank printed no count, or the parser does not read it. W3-2 §3.5 already surfaces this as `summary_fields_absent`. Absence is a fact about the document, not a failure. |
| the statement carries aggregate rows | `analysis/pipeline.py:140` — `"UNCAPTURED" in t.description.upper()` | One aggregate row stands for many postings by design. The count check is structurally guaranteed to fail and would say nothing. `assess_quality` already routes these to `summary_aggregate`. |
| the registration is not a formal statement | `analysis/pipeline.py:143`, `registration.formal_statement` | Already routed to `needs_review` with its own note; a count on a non-statement is not a finding. |
| no transactions at all | — | Zero rows against a printed count is `detail_coverage` by every existing check; adding a count code says nothing new and would double-rank the document. |

**Absence is never a failure, and a missing count is never inferred from the
other one.** A bank that prints `# of deposits` and not `# of withdrawals` gets
one check, not two.

### 4.3 What the check deliberately does not do

- It does not compare `stated_credit_count + stated_debit_count` against
  `len(stmt.transactions)`. That combined form is what
  `analysis/scanned_small_bank.py:525-527` uses as a parser-level completeness
  floor, and it is weaker: it cannot see a row that moved from one direction to
  the other, which is the RBC class.
- It does not touch `metrics.effective_num_deposits`. Changing which count the
  platform publishes is a separate decision with its own blast radius
  (open question 3).
- It does not check per-section counts (§3.4, open question 5).

---

## 5. Placement — and the finding that placement *is* the consequence

The card asks for an argued placement between `analysis/reconcile.py` and
`analysis/pipeline.py::assess_document_integrity`. Reading both control flows
shows the question is not a matter of taste: **in this codebase the two
placements produce two different outcome classes, automatically, with no extra
machinery on either path.**

### 5.1 The reconcile path forces `withheld`

`analysis/reconcile.py:228` — `ok = not issues`. Any `issues.append(...)`
makes `ReconResult.ok` false. Then:

| Step | Site | Effect |
|---|---|---|
| `trust_running_balances=recon.ok and …` | `analysis/pipeline.py:399` | becomes `False` |
| `m.adb_ok = trust_running_balances and adb.ok` | `analysis/metrics.py:313-316` | becomes `False` |
| `balances = {…} if m.adb_ok else {}` | `analysis/metrics.py:322-326` | empty |
| `m.average_daily_balance` never assigned | `analysis/metrics.py:331` is inside `if balances:` | stays `None` |
| `if metrics.average_daily_balance is None: return "withheld", "withheld_adb"` | `telemetry/record.py:296-297` | **withheld** |

An `issues.append` is therefore a decision to withhold the document's ADB.
There is no lighter-touch version of it.

### 5.2 The integrity path produces `review`

`assess_document_integrity` appends flags and never touches `recon.ok`. Then
`telemetry/record.py:309-310`: `if flags: return "review", "integrity_flags"`.
The value is published; approval is blocked; a human sees it.

Note one asymmetry that must be decided rather than inherited: a flag alone
sets `integrity.risk_level = "review"` (`analysis/pipeline.py:297-298`) but does
**not** set `possible_document_issue` (`:285-294`), so
`quality.corporate_use` stays `"approved"` (`:419`). Telemetry would call the
document `review` while the payload's `corporate_use` still says `approved`.
That is coherent for a phase-1 signal and probably not coherent for a
permanent one — see decision D3.

### 5.3 The recommendation

**Compute in `analysis/reconcile.py`. Consequence in
`analysis/pipeline.py::assess_document_integrity`. No `issues.append`.**

Computation belongs in `reconcile` because that is where the inputs already
are: `reconcile()` is the one function that holds the `Statement` and derives
"what the captured detail says" against "what the bank stated" — the credit and
debit coverage ratios at `:209-226` are the exact siblings of this check. Adding
a third comparison there keeps one module answering one question.

Consequence belongs in `pipeline` because `assess_document_integrity` is where
`ReconResult` fields already become flags without becoming refusals — the
existing precedent is `recon.continuity_breaks`, computed in reconcile
(`:105-122`) and turned into `running_balance_breaks` in pipeline (`:218-220`).

The proposal **breaks with the existing reconcile pattern in one respect and
says so**: every current check in `reconcile()` appends an issue *and* is
flagged. This one appends no issue. The reason is not fastidiousness about
layering:

> Every existing reconcile issue is a statement about **arithmetic the document
> can settle from its own numbers**. A count mismatch is a statement about a
> **semantic mapping** — "what this bank calls a deposit" versus "what our
> parser records as `direction == 'credit'`" — held independently by twenty
> parser modules, and its false-positive rate has never been measured on a
> single document. Withholding a published value on an unmeasured semantic
> mapping is the one thing the fail-closed discipline is *not* for.

Fail-closed means "do not publish a number we cannot prove". It does not mean
"withhold on any disagreement". Compare `W3_TRACKA_LOG.md` §3.5 (PNC), where a
parser-level gate was deliberately *not* added because the transition it would
produce (withheld → unclaimed) was a decision only Ocean could take. The same
discipline applies here: validated → withheld is a bigger transition than
validated → review, and it should be earned by measurement.

---

## 6. The failure surface

### 6.1 New `ReconResult` fields (`analysis/reconcile.py`)

```
stated_credit_count_matches: bool | None = None
stated_debit_count_matches:  bool | None = None
captured_credit_count: int | None = None
captured_debit_count:  int | None = None
```

`None` means **not applicable** (§4.2), which is the H3_SCHEMA I5 discipline
W3-2 §5 already applies to `counts`: a document with no measurement has no
measurement, not a zero.

### 6.2 New integrity flags (`analysis/pipeline.py`)

```
credit_count_mismatch      — "captured credit rows do not match the bank-stated credit count"
debit_count_mismatch       — "captured debit rows do not match the bank-stated debit count"
```

Two flags rather than one, matching the existing
`credit_detail_coverage_mismatch` / `debit_detail_coverage_mismatch` pair
(`analysis/pipeline.py:221-226`), so a rollup can tell a lost credit section
from a lost debit section without re-reading a note.

**Note text carries no values.** The existing coverage notes are value-free
(`:223`, `:226`) and these must be too, because notes travel into durable job
records — the leak W3-1's review closed (`WAVE2_EXECUTION_LOG.md`, 2026-08-07:
"crash messages quoting statement fragments no longer reach durable job
records"). The counts themselves are integers rather than money, but they are
document content, and H3_SCHEMA I1 says names only.

### 6.3 W3-2 taxonomy: codes and class

New codes, in the existing `integrity:<flag>` namespace (`W3_2_TAXONOMY.md`
§3.2):

| Code | Class |
|---|---|
| `integrity:credit_count_mismatch` | `detail_coverage` |
| `integrity:debit_count_mismatch` | `detail_coverage` |

**Argument for `detail_coverage` (precedence rank 9) rather than a new class.**
`W3_2_TAXONOMY.md` §4 defines `detail_coverage` as "line items do not add up to
the bank's stated totals" and ranks it by cause-over-symptom. A count mismatch
has the same cause (the captured detail does not reproduce the bank's stated
detail), the same remediation (find the rows the reader lost or mis-sided), and
the same owner (the parser cell for that bank). Splitting it into its own class
would split one remediation queue in two and would make the W3-4 ranking
report a bank twice for one defect.

**Argument against ranking it higher.** The temptation is to rank a count above
money coverage because it is the more sensitive instrument. That inverts the
taxonomy's stated principle: precedence ranks *causes*, not *sensitivities*.
A document that fails both is failing one thing.

**A count-only failure is nonetheless a distinct and important case**, and it
is visible without a new class: the document's `codes` list carries
`integrity:credit_count_mismatch` and *not* `integrity:credit_coverage_short`.
The rollup's top-codes line (`W3_2_TAXONOMY.md` §7) surfaces it directly.

### 6.4 The sequencing constraint this creates

`W3_2_TAXONOMY.md` §9 pins a drift guard: a regex over `flags.append("…")` in
`analysis/pipeline.py` is asserted **equal** to `INTEGRITY_FLAGS` in
`telemetry/diagnostics.py`. Adding two flags to `analysis/` therefore **fails
the build** until `telemetry/` is updated in the same merge. This is the guard
working as designed, and it means:

- the `analysis/` change and the `telemetry/` change are **one merge**, not two;
- `DIAGNOSTICS_VERSION` goes **v2 → v3**, and `telemetry.report --diagnostics`
  will print `WARNING mixed taxonomy versions` across the boundary
  (`W3_2_TAXONOMY.md` §11) — correct behaviour, but it means the baseline
  rollup and the post-merge rollup are not directly comparable and the
  changelog entry must say so.

---

## 7. The protected-module diff SHAPE — pinned, **not applied**

Per the W3-1b idiom (`WAVE2_EXECUTION_LOG.md`, 2026-08-07: "Pipeline diff
verified verbatim-as-approved"), the diff is written here for approval and
implemented only after sign-off. Line anchors are against the tree at
`bb7d644`.

### 7.1 `analysis/reconcile.py`

Four dataclass fields, after `settled_debit_detail` (`:40`):

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

One computation block, immediately before `ok = not issues` (`:228`):

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

The `formal_statement` guard from §4.2 is deliberately **not** in this block:
`reconcile(stmt)` takes only the `Statement` and has no `dispatch`, so it cannot
see the registration. It belongs one layer up, in `assess_document_integrity`,
which already resolves it at `analysis/pipeline.py:232` — carried into §7.2.

plus the four names carried into the `ReconResult(...)` constructor at
`:229-246`. **Net: +~24 lines, −0. `ok` is untouched. No existing line changes
behaviour.**

### 7.2 `analysis/pipeline.py` — PHASE 2 ONLY (see §8)

Inserted in `assess_document_integrity` immediately after the
`not_a_formal_statement` block (`:232-235`) — **not** next to its precedence
sibling at `:221-226`, because `registration` is not yet resolved there and the
formal-statement guard from §4.2 needs it:

```python
    formal = registration is None or registration.formal_statement
    if formal and recon.stated_credit_count_matches is False:
        flags.append("credit_count_mismatch")
        notes.append("captured credit rows do not match the bank-stated credit count")
    if formal and recon.stated_debit_count_matches is False:
        flags.append("debit_count_mismatch")
        notes.append("captured debit rows do not match the bank-stated debit count")
```

**Net: +7 lines, −0.** `is False` rather than `not …` is load-bearing: `None`
is not-applicable and must not flag. Flag insertion order is cosmetic —
`:283` de-duplicates while preserving order, `classify_outcome` tests
membership (`telemetry/record.py:309`), and the taxonomy ranks by
`CLASS_PRECEDENCE`, not by position.

`possible_document_issue` (`:285-294`) is **not** extended — see decision D3.

### 7.3 `telemetry/diagnostics.py` (same merge, per §6.4)

Two entries in `INTEGRITY_FLAGS` (`telemetry/diagnostics.py:92`), each mapped to
`detail_coverage` in `CLASS_OF` and therefore reaching `CLASS_PRECEDENCE`
(`:213`) at rank 9; `DIAGNOSTICS_VERSION` (`:46`) 2 → 3; a changelog entry in
`W3_2_TAXONOMY.md` §11. Neither belongs in `ADVISORY_CODES` (`:310`) — they are
financial findings, not consequences.

### 7.4 `ANALYSIS_STAGE_VERSION`

**Phase 1: no bump required** — `ReconResult` gains fields, so the serialized
payload gains four keys, but no existing value changes. Precedent:
`WAVE2_EXECUTION_LOG.md`, 2026-08-07, "**NO ANALYSIS_STAGE_VERSION bump**
(reasoning recorded)" for the W3-1 pipeline diff, which likewise only added.

**Phase 2: bump required** — `integrity.flags` changes for unchanged settings,
which is the D-3 rule verbatim (`webapp/artifact_cache.py:99-100`). `webapp/`
is protected; the bump is Ocean's at merge, exactly as every Track A cell
recorded (§5.7 item 5, §B7.5, §3.7 item 5, §W7.5).

---

## 8. Rollout: two phases, and why

**Phase 1 — observe.** Ship §7.1 only. The four `ReconResult` fields land in the
payload; nothing flags, nothing withholds, no outcome class moves, no cache
version changes. Then measure (§9). Cost: one merge, zero behavioural change,
zero vendor spend.

**Phase 2 — flag.** Ship §7.2 + §7.3 + the `ANALYSIS_STAGE_VERSION` bump, **only
if** Phase 1's measurement shows the mismatch population is dominated by real
defects rather than by semantic disagreement between banks and parsers.

**Phase 3 — withhold. Not proposed. Named so it is not assumed.** Promoting the
flag to a `reconcile` issue would make count mismatch fail-closed. It should be
considered only after Phase 2 has run over the archive and the population is
understood. It is a `validated → withheld` transition on documents that today
publish a number, and it is the same class of decision Ocean deferred on PNC
(`W3_TRACKA_LOG.md` §3.5).

This mirrors the structurer's own rollout — landed, opt-in, default off,
"until Ocean flips it after measured validation" (`W3_3C_STRUCTURER.md` §6) —
which is this codebase's established idiom for a change whose blast radius is
known in shape and unknown in size.

---

## 9. Blast radius

### 9.1 What is measurable inside this card, and what is not

`ESTIMATE` throughout this section. This worktree contains **no telemetry run
artifacts** — no `telemetry.jsonl`, no `rows.csv`, no `webapp_data` — so the
frozen baseline could not be joined. The measurement that settles it is in
§9.5 and costs no vendor spend and no re-analysis.

### 9.2 The applicability population is bounded by which parsers read the counts

Twenty modules assign `stated_credit_count` / `stated_debit_count`:
`altana.py:205-206`, `atb.py:121-122`, `bofa.py:390-393/513-516/587-589`,
`capital_one.py:37-39/189-193`, `chase.py:404-418/531-543`,
`community_section.py:192-193`, `demo_national.py:50-51`,
`farmers_merchants.py:56-57`, `first_community.py:150-151`,
`first_farmers.py:152-153`, `ibc.py:241-242`, `linkbank.py:70-71`,
`midflorida.py:119-120`, `rbc.py:401-405`,
`scanned_small_bank.py:287-288/466-467`, `scotia.py:80-82`,
`td_can.py:451-456/586-598`, `texas_bank.py:129-130`, `us_bank.py:293-294`,
`wilson_muir.py:162-163`. The LLM extraction path can also fill them, since
they are schema fields (`analysis/schema.py:45-46`).

**Every other parser reports the check as not applicable.** Notably PNC and
Wells Fargo — the two banks with the strongest printed count oracles — are in
that group today (§3.4).

### 9.3 Two populations are structurally immune

`analysis/community_section.py:205-210` and
`analysis/scanned_small_bank.py:206-207`, `:368-369`, `:525-527` already run a
count comparison **as a claim gate**: on mismatch the parser returns `None` and
the document goes unclaimed. A document those parsers claimed has, by
construction, matching counts. They cannot contribute a mismatch.

This is also the precedent for the semantics in §4: both existing count checks
compare per-direction row counts against the stated pair, and both use exact
equality.

### 9.4 Corpus (109 pinned documents / 106 PASS)

`ESTIMATE`, from the parser attribution in `docs/adb-audit-results.csv`
(109 rows): documents claimed by a count-reading module total roughly **50–55**
of 109 — chase 10, bank-of-america 8, td-canada-trust 6, atb-financial 5,
capital-one 4, royal-bank-of-canada 4 + banque-royale-du-canada 1, altana 3,
u.s.-bank 2, and one each for first-community, farmers-&-merchants,
first-farmers, linkbank, midflorida, texas-bank-and-trust, wilson-&-muir, ibc,
scotiabank, plus the `community_section` / `scanned_small_bank` documents that
§9.3 makes immune. How many of those *print* a count is a subset of that, and
was not measured.

**Could any of the 106 PASS documents fail the new check? This must be answered
before Phase 2, and the honest answer today is: unknown, and it is not
unlikely.** RBC is the direct precedent — six *already-validated* archive
documents carried a wrong per-direction count (§3.2) — and the corpus contains
five RBC documents. The RBC cell has since fixed that class
(`W3_TRACKA_LOG.md` §5.5: all eight now reproduce the printed counts and
totals exactly), but the corpus was not audited for counts, which is the next
point.

**The audit CSVs do not audit counts.** `docs/adb-audit-results.csv` and
`docs/balance-metrics-audit-results.csv` (headers read directly) carry
`transactions` — a single total row count — and no per-direction count column
at all. So a corpus document that failed the new check **could not be
adjudicated against the truth set**: there is no audited value to compare it
to. Resolving one would need a forensic pass from the PDF bytes, in the idiom
of `docs/adb-withheld-second-pass.md`.

**Ceremony territory, stated as the card requires.** If Phase 1's measurement
shows any corpus document failing the check, Phase 2 is a truth-set event, not
a merge: the 106/3 baseline moves, and the re-baseline ceremony
(`W3_TRACKA_LOG.md` §2.2, "APPROVED AND EXECUTED") applies — approval before
execution, forensic finding per document, no silent movement. Phase 1 exists
precisely so that this is known before anything can move.

### 9.5 The measurement that settles all of §9 — read-only, zero cost

The frozen baseline's **D-3 analysis artifact cache** already contains every
payload needed. Per `webapp/artifact_cache.py:117-119`, payloads are JSON files
at `<data_dir>/artifacts/analysis/<first2 of key>/<key>.json`, and
`report_to_dict` puts everything required in each one:

- `statement.stated_credit_count`, `statement.stated_debit_count`
  (`analysis/serialization.py:131`, `model_dump()`);
- `statement.transactions[].direction` (`analysis/schema.py:18`);
- `metrics.num_deposits` / `num_withdrawals` and
  `metrics.effective_num_deposits` / `effective_num_withdrawals`
  (`analysis/serialization.py:104`, `asdict(metrics)`).

So the entire blast radius — how many of 3,506 documents carry stated counts,
how many mismatch, how they split by parser, and how many are currently
`validated` — is a **read-only scan of cached JSON**. No re-analysis, no OCR, no
model calls, no `analysis/` change. This is the Phase 1 deliverable and it
should be produced *before* the Phase 1 merge, not after.

Note the telemetry record is **not** sufficient on its own: `telemetry/
diagnostics.py:480-495` stores `counts.transactions` (a total) and
`summary_fields_absent` (which tells you whether a stated count was present),
but no per-direction row count — correctly, under H3_SCHEMA I1. Telemetry can
measure *applicability*; only the artifact cache can measure *mismatch*.

---

## 10. Test plan

Written against the acceptance idiom the platform already uses: a rule is
pinned by a fixture in **both** directions, and no fixture asserts a value that
is not printed on a document.

**Unit — `tests/test_analysis.py` (or a new `tests/test_count_check.py`)**

| # | Assertion |
|---|---|
| 1 | matching counts → `stated_credit_count_matches is True`, no flag |
| 2 | one row moved to the wrong direction → `False` for both directions, both flags |
| 3 | **a zero-amount row printed as a credit**: counted as a credit; the check passes where a sign-keyed check would fail. The RBC §5.5 class, pinned directly |
| 4 | `stated_credit_count is None` → `matches is None`, **no flag** (the not-applicable control) |
| 5 | an aggregate-backed statement (`UNCAPTURED` row) → `None`, no flag, whatever the counts say |
| 6 | a settlement-reversal pair → counted gross; the money coverage adjustment at `reconcile.py:165-207` does not reach the counts |
| 7 | `recon.ok` is unchanged by any of the above (**the Phase-1 invariant, asserted directly**) |
| 8 | a count mismatch alone yields `outcome == ("review", "integrity_flags")` via `telemetry.record.classify_outcome`, and **never** `withheld` |

**Drift — `tests/test_diagnostics.py`**

| # | Assertion |
|---|---|
| 9 | the existing `flags.append("…")` guard (`W3_2_TAXONOMY.md` §9) passes with the two new flags present in `INTEGRITY_FLAGS` — i.e. the guard is *satisfied*, not weakened |
| 10 | both new codes map to `detail_coverage`, and the §4 precedence table still equals `CLASS_PRECEDENCE` (`test_the_precedence_table_in_the_taxonomy_doc_matches_the_code`) |

**Corpus — `tests/test_telemetry_corpus.py`, corpus-marked**

| # | Assertion |
|---|---|
| 11 | `python corpus_gate.py` stays **106 PASS / 3 WITHHELD**, byte-identical |
| 12 | the 3 pinned withheld reproduce their documented diagnosis unchanged (`Ace_Auto` → `detail_coverage`, `BMO` → `source_contradiction`, `IBC` → `summary_identity`) |
| 13 | **Phase 1 only:** no corpus document's serialized payload differs except by the four new keys |
| 14 | **Phase 2 only:** the set of corpus documents carrying either new flag is pinned explicitly — empty if Phase 1 measured it empty, enumerated with a forensic finding per document if not |

**Merge proof** — the standing criterion from `WAVE2_EXECUTION_LOG.md`
(2026-08-07): the default suite **and** `pytest -m corpus`, not the default
suite alone.

---

## 11. Decisions required

| # | Decision | Recommendation |
|---|---|---|
| **D1** | Is the count check worth a protected-module change at all? | **Yes.** §3.1: the platform already publishes the bank's count as its own and has never checked it against its own rows. |
| **D2** | Fail-closed (withhold) or flag-to-review? | **Flag-to-review (Phase 2), never withhold until measured.** §5.3. Withholding on an unmeasured cross-parser semantic mapping is not what fail-closed is for. |
| **D3** | Should the flag also block corporate approval (extend `possible_document_issue`, `analysis/pipeline.py:285-294`)? | **Not in Phase 2.** Leaving it out keeps the phase reversible. Revisit with the Phase 2 measurement — but note the inconsistency in §5.2 (telemetry `review` vs payload `corporate_use: approved`) is real either way and is a W3-4 adjudication question. |
| **D4** | Two phases, or one? | **Two.** Phase 1 costs one additive merge, no version bump, no outcome movement, and it is what makes D2 and D5 answerable with evidence instead of judgement. |
| **D5** | If Phase 1 finds corpus documents that would fail, does Phase 2 proceed? | **Gustavo's, not Ocean's.** It is a truth-set re-baseline (§9.4) and the ceremony at `W3_TRACKA_LOG.md` §2.2 applies. |
| **D6** | Should PNC and Wells parsers be changed to read the counts they print? | **Yes, but as separate parser cards**, sequenced after Phase 1. They are the same cards as `W3_TRACKA_LOG.md` §B7.2 / §W7.4 / §3.7 item 2 (the unread printed oracles), and folding them in here would make this proposal a parser change. |

---

## 12. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | **Semantic disagreement across 20 parsers.** "# of deposits" may exclude interest credits; "# of withdrawals" may or may not include cheques (`bofa.py:589` explicitly adds `check_count`; `us_bank.py:293-294` sums category counts; `wilson_muir.py:162-163` sums three). An exact-equality check across all of them is a bet that every parser normalized to "all rows in this direction". | **High — the dominant risk** | Phase 1 measures it before anything flags. If the mismatch population is dominated by one or two parsers, those are parser cards, not a platform check. |
| R2 | A corpus PASS document fails the check → truth-set movement with **no audited count to adjudicate against** (§9.4). | High | Phase 1; then the §2.2 ceremony, with a forensic per-document finding from the PDF bytes. |
| R3 | `direction` may not be uniformly populated to mean "the printed column" across 40+ parsers; some may derive it from the sign, which would make the check a restatement of the money check on those banks. | Medium | Phase 1's scan measures `direction` against `sign` per parser at the same time and at no extra cost. Any parser where they never disagree is a parser where the check adds nothing — worth knowing. |
| R4 | Drift guard makes `analysis/` and `telemetry/` a single merge (§6.4); a partial merge red-lines the build. | Low, certain | Sequence it as one merge; it is the guard working. |
| R5 | `DIAGNOSTICS_VERSION` v2→v3 makes the baseline rollup and the post-merge rollup non-comparable (`W3_2_TAXONOMY.md` §11). | Low | Expected and already handled by the mixed-version warning; record it in the §11 changelog. |
| R6 | Phase 1 ships four payload keys that nothing reads. | Low | That is the point of an observe phase, and it is additive: no bump, no movement (§7.4). |
| R7 | Scope creep to per-section counts (§3.4). | Low | Explicitly out of scope; open question 5. |

---

## 13. Open questions

1. **`direction` vs sign as the count key (§4.1).** Recommended: `direction`.
   Phase 1 should report, per parser, how often the two disagree. If they never
   disagree anywhere, the recommendation is still right but the check is weaker
   than §3.2 claims, and that changes D1's weight.
2. **`stated_nsf_count` is the same shape and the same gap.**
   `analysis/schema.py:55-56` carries it; `analysis/metrics.py:373-377` already
   *compares* it against the classified row count and emits a **note** — never a
   flag, never a code — and then keeps the row count. It is the closest thing in
   the tree to the check proposed here, and it chose note-not-flag. Should the
   count check follow it, or should `stated_nsf_count` follow the count check?
   Consistency argues they should match.
3. **Should `effective_num_deposits` change?** If the counts disagree and the
   detail is what we publish, publishing the bank's count is arguably the
   wrong choice (`analysis/metrics.py:353-356`). Out of scope here; it changes
   published values and needs its own blast radius.
4. **W3-2 §5 scope.** Diagnostics are `withheld`-only
   (`DIAGNOSABLE_CLASSES = ("withheld",)`). A count mismatch produces `review`,
   which is **not diagnosable today** — so the new codes would be invisible in
   the rollup that exists. Either `DIAGNOSABLE_CLASSES` widens to include
   `review` (a one-line change that breaks the acceptance property "the 106
   produce empty diagnostics", and which W3-2 §10 question 2 already says needs
   a ruling), or the count flags are measured through a different surface.
   **This is a real dependency between deliverable A and W3-2's open question 2
   and must be ruled on together.**
5. **Per-section counts (§3.4).** PNC prints an item count per section and the
   schema has nowhere to put it. The strongest form of this check is per
   section, not per direction. L-class schema question; recorded, not proposed.
6. **Where does the ADB suite fit?** `analysis/adb.py:467-484` has a `required`
   list that decides `result.ok`. The count check was deliberately **not** put
   there: `_validate` is about the daily ledger and the period, and a count is
   about detail coverage. Recorded so the choice is visible rather than
   assumed.
