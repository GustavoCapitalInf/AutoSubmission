# W3-2 — the withheld-diagnostics taxonomy and its mapping

Agent B (HARBOR), 2026-08-07. Branch `wave3-diagnostics`.
Card: `WAVE3_BRIEF.md` §W3-2. Data contract: `H3_SCHEMA.md` (this extends the
record per its own conventions; every invariant there still holds).

---

## 1. The question this answers

Discovery withheld **614 claimed documents** — 17.5% of the archive, and the
highest value-per-fix class in `DISCOVERY_COMBINED_REPORT.md` §2, because
detection and the claim were already correct. What discovery could say about
each was `outcome.class = withheld`, `outcome.reason = withheld_adb`. That is
the *decision*, not the *diagnosis*: it does not say which check refused.

W3-2 makes the diagnosis a query. After it, "fix the top failing check-class
for chase variants" is a `GROUP BY`, and 614 statement-by-statement autopsies
are not needed to find out where the 317 chase withholds actually break.

Three properties are non-negotiable and everything below is shaped by them:

1. **Read-only.** Diagnostics are a projection of the analysis payload the
   telemetry collector already receives. No `analysis/` module is imported,
   nothing is recomputed, no object is mutated. Proven by test on real
   documents, not asserted in prose.
2. **Sensitivity (H3_SCHEMA I1).** Check names, field names, taxonomy codes
   and counts. Never a value, amount, date, description or filename. The two
   richest diagnostic sources — reconciliation issues and ADB warnings — are
   free text that quotes all of those, so they are *matched and discarded*,
   never stored.
3. **Nothing silently dropped.** Every vocabulary is closed and every one has
   an explicit `unmapped` bucket, so a check that `analysis/` grows later
   surfaces as `unmapped` in the rollup instead of vanishing. Drift guards in
   `tests/test_diagnostics.py` fail the build the moment it happens.

## 2. Where the vocabulary comes from (survey first)

The brief requires the vocabulary to derive from the checks `analysis/`
**actually performs**, not from what a diagnosis "ought" to include. The survey
found exactly four sources in the serialized payload, and one gap.

| # | Source | Payload path | Shape | Sensitivity |
|---|---|---|---|---|
| 1 | ADB validation suite (`analysis/adb.py::_validate`) | `metrics.adb.validations` | `{check_name: bool}` — **14** names, our constants | safe as-is |
| 2 | Document integrity flags (`analysis/pipeline.py::assess_document_integrity`) | `integrity.flags` | list of **10** enum codes, our constants | safe as-is |
| 3 | Reconciliation issues (`analysis/reconcile.py` ×6 + `analysis/pipeline.py` ×1) | `reconciliation.issues` | **7** f-string shapes | **quotes amounts, dates, descriptions** |
| 4 | ADB warnings (`analysis/adb.py`) | `metrics.adb.warnings` | **19** f-string shapes | quotes amounts and dates |

Sources 1 and 2 need no interpretation: the failing *names* are the taxonomy.
Sources 3 and 4 are prose and must be classified into codes.

**The gap, recorded rather than invented.** The brief lists "count mismatch" as
an example failure. There is **no platform-level check comparing
`stated_credit_count` / `stated_debit_count` against the captured row counts**.
The only count comparison in the tree is parser-local
(`analysis/community_section.py:208`) and never reaches the payload as an
issue. A `count_mismatch` code is therefore *not* in this vocabulary: inventing
one would mean W3-2 performing analysis rather than reporting it, and the
standing rules put analysis changes out of scope for this card. What the
record *does* carry is the raw material for it — `counts.transactions` and the
presence/absence of `stated_credit_count` / `stated_debit_count` in
`summary_fields_absent` — so if Ocean wants the check, it is a small
`analysis/` ticket and one new row in §3.1 here.

Two smaller findings from the same survey, logged for the backlog:

- `analysis/pipeline.py` tests for a quality level `summary_trusted` in two
  places (lines 218, 268) that `assess_quality` never assigns. Dead vocabulary
  — harmless, but it means one integrity branch is unreachable.
- `report_to_dict` nulls `statement.ending_balance` when neither the ledger nor
  the bank's own summary supports it. So `summary_fields_absent` means "absent
  from what the platform published", which is deliberately what a diagnostic
  should say: it is exactly the field the next stage did not get. Called out
  because reading it as "the bank printed no closing balance" would be wrong.

## 3. The mapping

Codes are namespaced `source:name`. The namespace says where the evidence came
from, which matters when reading a rollup: an `adb:` code is a check the ADB
engine ran, an `adb_state:` code is a condition it reported in prose, and a
`recon:`/`integrity:` code comes from the other two sources.

### 3.1 Source 1 — ADB validation checks → `adb:<check_name>`

Emitted when the check is `false`. Verbatim names, no translation, so the code
is greppable straight into `analysis/adb.py`.

| Check | Class |
|---|---|
| `statement_period_dates_valid` | period_integrity |
| `all_transactions_dated` | period_integrity |
| `transactions_within_period` | period_integrity |
| `bank_daily_balance_dates_valid` | daily_ledger_structure |
| `daily_balance_count_equals_calendar_days` | daily_ledger_structure |
| `daily_balances_contiguous` | daily_ledger_structure |
| `covers_opening_day` | daily_ledger_structure |
| `covers_closing_day` | daily_ledger_structure |
| `final_balance_matches_statement_closing` | ledger_identity |
| `ledger_reconciles_to_closing` | ledger_identity |
| `opening_balance_matches_statement` | summary_field_missing |
| `running_balances_support_daily_ledger` | balance_continuity |
| `posting_dates_cover_source` | posting_date_coverage |
| `agrees_with_bank_stated_average` | *advisory* |
| anything else | `adb:unmapped` → **unmapped** |

`agrees_with_bank_stated_average` is advisory because it only ever runs when
`result.ok` is already true — it can never be the reason a document was
withheld, and letting it choose a class would misdirect remediation.

### 3.2 Source 2 — integrity flags → `integrity:<flag>`

| Flag | Class |
|---|---|
| `summary_math_inconsistent` | summary_identity |
| `ledger_sum_mismatch` | ledger_identity |
| `running_balance_breaks` | balance_continuity |
| `credit_detail_coverage_mismatch` | detail_coverage |
| `debit_detail_coverage_mismatch` | detail_coverage |
| `credit_count_mismatch` | detail_coverage (COUNTS-P2) |
| `debit_count_mismatch` | detail_coverage (COUNTS-P2) |
| `conflicting_statement_summaries` | source_contradiction |
| `missing_declared_statement_page` | page_coverage |
| `transaction_detail_not_corporate_reliable` | *advisory* (a consequence) |
| `not_a_formal_statement` | *advisory* (a document class, not a failure) |
| `parser_ambiguous` | *advisory* (a dispatch fact; `dispatch.outcome` carries it) |
| `parser_exception` | *advisory* (W3-1: a parser raised; `dispatch.exceptions` carries who and what) |
| `integrity_check_exception` | **`check_unavailable`** (W3-2b) |
| `repair_exception` | **`extraction_failure`** (REPAIR-GUARD/PIPE5: a statement-repair stage raised and was discarded whole, so the published statement is the unrepaired one — a production stage that did not complete, upstream of every financial class. The stage is twelve steps, only one of which is a bank-summary repair; see the v4 changelog for what the discard costs) |
| anything else | `integrity:unmapped` → **unmapped** |

**The two W3-1 crash flags are treated differently, and the difference is the
point** (W3-2b, Ocean ruling).

`parser_exception` stays advisory for the same reason `parser_ambiguous` is: it
describes **our** code, not the statement's arithmetic, and — critically — it
leaves no diagnosis incomplete. A parser that crashed produced no claim, so the
document never reached the checks at all; it lands in `failed`, which is not
diagnosable (§5). Where the flag appears on a document that *did* reach the
checks, that document was withheld by a check in the classed vocabulary, and
letting a crash outrank it would put "a parser broke" at the top of a ranking
that exists to say *which financial check* failed. It stays in `codes`, and
`dispatch.exceptions` plus W3-1's crash-cluster ranking are where it is acted on.

`integrity_check_exception` is different in kind. A registered integrity check
**raised**, so its finding is **unknown, not clean** — and the check that
crashed is typically the one that would have produced
`source_contradiction`. Its absence therefore proves nothing, and reporting the
next class down would present an incomplete diagnosis as a confident one. It is
classed `check_unavailable` and ranked above every financial class.

### 3.3 Source 3 — reconciliation issues → `recon:<code>`

Matched on the **literal prefix** of the format string `analysis/` writes, plus
a tail fragment where the prefix alone is not decisive. First match wins. The
issue string is then discarded.

| Prefix (and tail) | Code | Class |
|---|---|---|
| `cannot run sum check` | `sum_check_inputs_missing` | summary_field_missing |
| `sum check off by` | `sum_check_failed` | ledger_identity |
| `bank-stated summary does not reconcile` | `summary_identity_failed` | summary_identity |
| `captured $` … ` in credits (` | `credit_coverage_short` | detail_coverage |
| `captured $` … ` in debits (` | `debit_coverage_short` | detail_coverage |
| `escalation extraction failed` | `escalation_extraction_failed` | extraction_failure |
| `row ` … `balance jumped to` | `running_balance_break` | balance_continuity |
| no match | `unmapped_issue` | **unmapped** |

**Why prefix-anchored, not substring.** The continuity issue interpolates a
transaction description:
`row 7 (2026-01-02 'ACH DEBIT …'): balance jumped to …`. A bare substring match
would let a document whose description contains another rule's wording choose
its own bucket. Anchoring on the prefix puts the decision in text `analysis/`
wrote. `tests/test_diagnostics.py::test_a_reconciliation_issue_is_anchored_on_our_prefix_not_the_description`
feeds exactly that hostile description and asserts one code comes back.

### 3.4 Source 4 — ADB warnings → `adb_state:<code>`

Substring anchors are sufficient here: every ADB warning interpolates only
dates, counts and amounts — never a transaction description — so no statement
text can reach these strings.

| Anchor | Code | Class |
|---|---|---|
| `have no parseable date` | `undated_transactions` | period_integrity |
| `statement period start missing` | `period_start_missing` | period_integrity |
| `statement period end missing` | `period_end_missing` | period_integrity |
| `statement period is inverted` | `period_inverted` | period_integrity |
| `does not provide a valid, ordered start and end date` | `period_dates_invalid` | period_integrity |
| `fall outside the statement period` | `out_of_period_transactions` | period_integrity |
| `cannot determine a statement period` | `period_unresolvable` | **adb_not_computable** |
| `no opening balance and none derivable` | `opening_balance_underivable` | **adb_not_computable** |
| `statement prints no beginning balance` | `beginning_balance_absent` | summary_field_missing |
| `statement prints no closing balance` | `closing_balance_absent` | summary_field_missing |
| `bank daily balance has invalid or out-of-period date` | `daily_balance_date_invalid` | daily_ledger_structure |
| `bank daily balance history contains duplicate date` | `daily_balance_date_duplicate` | daily_ledger_structure |
| `daily balances for a` | `daily_balance_count_mismatch` | daily_ledger_structure |
| `daily balance series has a gap` | `daily_balance_series_gap` | daily_ledger_structure |
| `final reconstructed balance` | `final_balance_drift` | ledger_identity |
| `ledger does not reconcile` | `ledger_reconcile_failed` | ledger_identity |
| `running balances do not support` | `running_balances_unsupported` | balance_continuity |
| `posting date(s) but the statement` | `posting_dates_incomplete` | posting_date_coverage |
| `differs from the bank-printed` | `stated_average_disagrees` | *advisory* |
| no match | `unmapped_warning` | **unmapped** |

**The overlap with §3.1 is deliberate.** Most warnings are the prose form of a
validation check, so mapping them costs a redundant code per document. It earns
its keep on the two paths where `compute_average_daily_balance` returns
**before** `_validate` runs — no resolvable period, or no derivable opening
balance. On those, `validations` is `{}` and the warning is the only evidence
that exists. Those two are the `adb_not_computable` class, and they would be
invisible without this source.

### 3.5 Summary-field presence

`summary_fields_absent` lists, by name only, which of the 13 `Statement`
summary fields the payload does not carry (`period_start`, `period_end`,
`beginning_balance`, `ending_balance`, `days_in_period`,
`stated_total_credits`, `stated_total_debits`, `stated_credit_count`,
`stated_debit_count`, `stated_service_charge`, `stated_interest_paid`,
`stated_average_balance`, `stated_daily_balances`). Field names only — the
brief's "missing/malformed summary field" question. Absence does **not** decide
a class on its own: `analysis/` already turns the absences that matter into
checks (§3.1, §3.4), and inventing a rule here would be W3-2 doing analysis.

## 4. The failure classes and their precedence

The fine-grained codes are the evidence; the **primary class** is the one
ranked bucket a document lands in, and it is what the rollup groups by.

Ranked most-upstream first — the primary class is the highest-ranked class
present:

| # | Class | Means |
|---|---|---|
| 1 | `no_analysis_payload` | reserved: nothing to diagnose (see §5 on scope) |
| 2 | `adb_not_computable` | the ADB engine returned before it could validate |
| 3 | `extraction_failure` | a stage that PRODUCES the statement did not complete: the escalation extraction failed, or a statement-repair stage raised and was discarded whole |
| 4 | `check_unavailable` | a registered integrity check raised: this diagnosis is INCOMPLETE, and must not present as a confident lower class |
| 5 | `source_contradiction` | a registration integrity check proved the document contradicts itself |
| 6 | `period_integrity` | the period the whole average is divided by is wrong |
| 7 | `summary_field_missing` | an input the checks need was never published |
| 8 | `summary_identity` | the bank's own summary block fails its own identity |
| 9 | `detail_coverage` | line items do not add up to the bank's stated totals |
| 10 | `posting_date_coverage` | posting dates folded together; days carry the wrong balances |
| 11 | `balance_continuity` | printed running balances contradict the reconstructed ledger |
| 12 | `ledger_identity` | beginning + activity != ending |
| 13 | `daily_ledger_structure` | the reconstructed day series itself is malformed |
| 14 | `page_coverage` | pages the statement declares are not in the supplied PDF |
| 15 | `unmapped` | a check this taxonomy has never seen |
| 16 | `advisory_only` | evidence exists, but all of it is consequence or comparison |
| 17 | `undiagnosed` | withheld, and the taxonomy saw nothing — itself a finding |

**Why this order.** Ranking is by *cause over symptom*, because the class is
what ranks remediation work. The clearest case is
`detail_coverage` above `ledger_identity`: `Ace_Auto_Final_Cut.pdf` fails its
ledger identity *because* only 11 of the bank's 26 stated checks/debits are in
the document at all. Reporting it as `ledger_identity` would aim remediation at
the arithmetic that noticed the problem instead of the missing detail. The same
logic puts `source_contradiction` near the top — when the document disagrees
with itself, every downstream check failing is expected, not informative.

`advisory_only` and `undiagnosed` are separate names on purpose. `undiagnosed`
means the platform withheld and this taxonomy explained nothing: that is a
defect in the taxonomy or a check running somewhere it does not read, and it
must be visible in the rollup rather than nulled.

## 5. Scope: which documents get diagnosed

`DIAGNOSABLE_CLASSES = ("withheld", "review")` (COUNTS-P2; `("withheld",)`
through v2). Every other outcome class gets `empty_diagnostics()`.

- `validated` published a number nothing questioned, and diagnosing 100
  healthy corpus documents would bury the ones that matter. This is the
  acceptance property, restated at v3: **"the 100 validated produce empty
  diagnostics"** — it was "the 106" while `review` was out of scope.
- `review` published a number too, but approval is blocked and the reason is a
  flag this taxonomy already names. It joined the scope at v3 because phase 2
  of the stated-count check emits codes whose ONLY outcome class is `review`:
  a `withheld`-only scope would have made a whole vocabulary unreadable in the
  one rollup that reads it (§10 open question 2, ruled by Ocean 2026-08-10 —
  "extends to review WHEN phase 2 lands, not before"). The pinned corpus's six
  review documents are enumerated in `tests/test_telemetry_corpus.py`.
- `failed` has no payload at all — there is nothing to project. Its cause is
  `outcome.error_type`, which W3-1 is making authoritative. `no_analysis_payload`
  is kept in the precedence list as the reserved name for that class if a later
  card widens the scope.
- `deferred` is a statement about the run, not the document.

`counts` is `{}` when not evaluated, not a dict of zeros: H3_SCHEMA I5 — a
validated document has no failing-check count of zero, it has no measurement.

## 6. Where it hooks in — and why discovery needs no change

The diagnostics are computed inside `telemetry/record.py::build_record`, from
the `payload` argument that **all three emitters already pass**:

| Emitter | Call site | Change needed |
|---|---|---|
| discovery runner | `discovery/runner.py::_emit` | **none** |
| batch CLI | `batch.py` | **none** |
| webapp worker | `webapp/worker.py` | **none** |

A future discovery re-run therefore picks the diagnostics up with **zero
`discovery/` changes** — the requirement in the card, met. Storage needs no
migration either: SQLite stores the record as JSON in the `record` column and
projects only the typed columns it already has (H3_SCHEMA §8.1), so v4 carries
the new section unchanged and JSONL is unaffected.

Files touched: `telemetry/diagnostics.py` (new), `telemetry/record.py`
(one import, one `TOP_LEVEL_KEYS` entry, one record field),
`telemetry/report.py` (the rollup), `telemetry/__init__.py` (exports),
`tests/`, this document. Nothing else.

## 7. The rollup

```
python -m telemetry.report --jsonl <run>/telemetry.jsonl --diagnostics
python -m telemetry.report --sqlite webapp_data --run-id <id> --diagnostics
python -m telemetry.report --jsonl <run>/telemetry.jsonl --diagnostics --json
python -m telemetry.report --jsonl <run>/telemetry.jsonl --by diagnostic_class
```

Both backends carry the identical record (H3_SCHEMA I2), so both produce the
identical table. Output is ASCII-only, for the same reason the coverage report
is: a console in a legacy code page must not turn a measurement into a
`UnicodeEncodeError`.

The table is failure-class × parser × volume, plus class totals, the top codes,
and an unmapped line that is `0 | 0 | 0` when the vocabulary is complete and
loud when it is not. A record written before this section existed reports as
not-diagnosed rather than crashing the rollup.

## 8. Validation anchors

| Anchor | Test |
|---|---|
| The 3 pinned withheld reproduce their documented diagnosis | `tests/test_telemetry_corpus.py::test_withheld_diagnostics_reproduce_the_documented_diagnosis` (corpus-marked) |
| The 106 produce empty diagnostics | same test |
| Diagnostics mutate no analysis output | `tests/test_telemetry_corpus.py::test_diagnostics_change_no_analysis_output` (default run) and `tests/test_diagnostics.py::test_diagnosis_does_not_touch_the_payload` |
| No statement text reaches the section | `tests/test_diagnostics.py::test_no_statement_text_reaches_the_diagnostics_section` + the extended I1 test on real documents |
| The vocabulary matches `analysis/` | four drift guards in `tests/test_diagnostics.py` |

The expected diagnoses are taken from `docs/adb-withheld-second-pass.md`, which
established them forensically from the PDF bytes — not from a run of this code:

| Statement | Documented finding | Primary class |
|---|---|---|
| `Ace_Auto_Final_Cut.pdf` | "supplied PDF has incomplete transaction detail" (11 of 26 stated debits visible) | `detail_coverage` |
| `BMO_Statement_January_2026 Final-1-2 (1).pdf` | "mutually contradictory financial records" (page 1 vs page 2 vs row amounts) | `source_contradiction` |
| `IBC April (1).pdf` | the bank-stated summary fails its own identity | `summary_identity` |

## 9. Drift guards

`analysis/` is protected, so this module cannot be kept in sync by convention.
Four tests read its **source text** (read-only) and fail loudly on drift:

| Guard | Method |
|---|---|
| ADB check names | regex `checks["…"] =` in `analysis/adb.py` == `ADB_CHECKS` |
| Integrity flags | regex `flags.append("…")` in `analysis/pipeline.py` == `INTEGRITY_FLAGS` |
| Reconciliation issues | count of `issues.append(` in `reconcile.py` + `pipeline.py` == 7 anchors |
| ADB warnings | count of `warnings.append(` in `adb.py` == 19 anchors |

Names are asserted by identity where the source is enum-shaped; the two
f-string sources are asserted by **call-site count**, because their text is not
statically extractable. Either way, adding a check to `analysis/` fails the
build with a message naming this file — and even if someone bypasses the guard,
the new shape lands in `unmapped` at runtime and shows in the rollup.

## 10. Open questions for Ocean

1. **The `count_mismatch` gap (§2). RESOLVED** — `PROPOSAL_STATED_COUNTS.md`,
   Gustavo's 2026-08-10 sign-off, COUNTS-P1's measurement and COUNTS-P2's
   merge. `analysis/` grew the check, computed in `reconcile.py` and flagged
   in `pipeline.py`, gated on `analysis/count_semantics.py`. See §11 v3.
2. **Scope (§5). RESOLVED** — extended to `review` with the COUNTS-P2 merge,
   per Ocean's 2026-08-10 ruling. The acceptance property was restated, not
   dropped: "the 100 validated produce empty diagnostics". `failed` remains
   out of scope — it has no payload to project.
3. **Precedence (§4).** Cause-over-symptom is a judgement call, and it is what
   the ranking in W3-4's remediation queue will inherit. The three corpus
   anchors agree with it; 614 documents may argue otherwise, and re-ranking is
   cheap (one tuple) but re-baselines the rollup.
4. **Pre-existing sensitivity-test brittleness (disclosed).** The I1 test
   compared statement values against the *whole* serialized record, including
   `emitted_at`. A wall-clock reading of `…:58:51.752210` reads as the amount
   `51.75`, which is how it failed on a rerun during this card. Fixed by
   excluding four machine-generated identifier fields
   (`record_id`, `emitted_at`, `run_id`, `document.content_sha256`) from the
   substring scan and pinning each of them by shape in a new test, so the scan
   narrows without the invariant narrowing. Test-only change.

---

## 11. Changelog — the taxonomy vocabulary

`DIAGNOSTICS_VERSION` travels in every record precisely so a rollup spanning a
vocabulary change can say so. `telemetry.report --diagnostics` prints a
`WARNING mixed taxonomy versions` line whenever it sees more than one, because
class counts either side of a re-classing are not comparing like with like.

### v1 — W3-2, as shipped

The four-source vocabulary and the 16-class ranking.

### v2 — W3-2b (Ocean ruling, 2026-08-07): `check_unavailable`

`integrity:integrity_check_exception` moved from `ADVISORY_CODES` to the new
class **`check_unavailable`**, ranked 4th — above every financial class.

**Why.** W3-1 added two crash flags and both were classed advisory on the
argument that they describe our code rather than the statement's arithmetic.
That argument holds for `parser_exception` and fails for
`integrity_check_exception`: a crashed integrity check happens *inside* a
diagnosis and makes it **partial**, and the check that crashed is typically the
one that would have produced `source_contradiction`. Its absence proves
nothing, so ranking the document by the next class down presents an incomplete
diagnosis as a confident one.

`parser_exception` stays advisory, and the distinction is asserted
(`test_a_parser_crash_leaves_no_diagnosis_to_be_incomplete`): a parser that
crashed produced no claim, so the document never reached the checks and has no
diagnosis to be incomplete — it lands in `failed`, which is not diagnosable.

**Blast radius.** Re-baselines the rollup: any document carrying
`integrity_check_exception` ranks one class higher than it did at v1. The
pinned three corpus withheld are **unaffected** — none had an integrity check
crash — and the corpus anchor now asserts that explicitly rather than leaving
it to be inferred.

**Doc/code guard.** The §4 precedence table is asserted equal to
`CLASS_PRECEDENCE`, order and numbering included
(`test_the_precedence_table_in_the_taxonomy_doc_matches_the_code`), so the two
cannot drift again — the renumbering this change required was done from the
code, not by hand.

### v3 — COUNTS-P2 (Gustavo-approved 2026-08-13): the stated-count codes, and `review` becomes diagnosable

Two things at once, in one merge, because each is useless without the other.

**Two new codes.** `integrity:credit_count_mismatch` and
`integrity:debit_count_mismatch`, both classed **`detail_coverage`** (rank 9,
§3.2, §4). Same cause as the money-coverage pair (the captured detail does not
reproduce the bank's stated detail), same remediation (find the rows the
reader lost or mis-sided), same owner (that bank's parser cell) — so they
share the class rather than splitting one remediation queue in two, and they
are **not** ranked higher for being the more sensitive instrument: precedence
ranks causes, not sensitivities. A count-only failure is still visible without
a new class, because the document carries `integrity:credit_count_mismatch`
and *not* `recon:credit_coverage_short`.

**`DIAGNOSABLE_CLASSES` extends to `review`** (§5), per Ocean's standing
ruling. A count mismatch is flag-never-withhold by design, so `review` is the
only class these codes can appear in; leaving the scope at `withheld` would
have shipped a vocabulary nothing could read.

**Blast radius.** Both halves make a v2 rollup and a v3 rollup
non-comparable, and in different ways: the code set grew, and the *denominator*
grew. On the pinned 109 the diagnosed population goes 3 → 9 (the 3 withheld
plus 6 review documents that were already in `review` before this merge, five
for `page_coverage` and one advisory-only transaction export). No outcome
class moved: 100 validated / 6 review / 3 withheld before and after, and the
gate's 106 PASS / 3 WITHHELD is untouched. Exactly one count code appears in
the whole pinned corpus — `integrity:debit_count_mismatch` on
`Ace_Auto_Final_Cut.pdf`, which was already withheld and already diagnosed
`detail_coverage` for the same missing detail, so the code adds evidence to an
existing diagnosis and changes no class.

**What keeps the new codes quiet.** They are gated on
`analysis/count_semantics.py`, the per-bank table of what a printed count
denotes, whose default for an unsurveyed parser is *not comparable*. A parser
that starts publishing a printed count without a table entry emits nothing.

---

### v4 — REPAIR-GUARD/PIPE5 (2026-08-15): `integrity:repair_exception`

**One new code.** `integrity:repair_exception`, classed **`extraction_failure`**
(rank 3, §3.2, §4). `analysis/pipeline.py::apply_statement_repairs` runs after
dispatch and was therefore outside the guarded seam every `detect` and `parse`
runs behind; a repair that raised left `analyze_markdown` as a bare exception
and `webapp/worker.py` stored `str(exc)` — an exception message that routinely
quotes the cell of the document that provoked it — as the durable job error.
The stage is now discarded WHOLE and the crash survives as a class name.

**Why `extraction_failure` and not the two neighbouring crash classes.** Not
`check_unavailable`: a repair produces no finding, so no diagnosis is left
partial. Not advisory like `parser_exception`: a parser that crashed produced
no claim and its document never reached the checks, whereas this document
reached every check with figures the platform knows are uncorrected. It shares
`extraction_failure` with `recon:escalation_extraction_failed` because both
mean *a stage that produces the statement did not complete* — and it ranks
above the financial classes on W3-2b's own argument, since a repair rewrites
published balances and stated totals and so a `summary_identity` or
`ledger_identity` finding taken on unrepaired figures may be the crash's
symptom rather than its cause.

**What the discard actually costs — stated, not implied.** The stage is
TWELVE steps and only ONE of them is a bank-summary repair: nine further
bank-specific repairs, `assign_transaction_years`, and a final
`normalize_statement`. Two consequences follow that the flag's first wording
hid, and both are why the note now says *statement-repair stage … discarded
whole* rather than *bank-summary repair*:

* A raise late in the stage discards the work of every step that had already
  SUCCEEDED, including a bank-summary repair that did its job.
* `assign_transaction_years` is inside the discarded stage. On a statement
  whose period crosses a year boundary (Dec→Jan), parsers stamp one year on
  every `MM/DD` row and this step re-derives it. Discarding it publishes
  **wrong transaction DATES**, not merely uncorrected summary figures — and
  dates feed the dated ledger, the daily-balance series and the ADB. This is
  a strictly larger blast radius than "the summary is uncorrected", and it is
  pinned by `test_the_discard_publishes_uncorrected_dates_on_a_year_boundary`.

**Why the trade is still right.** The alternative to discarding is either
publishing a half-repaired statement (an unknown mixture of corrected and
uncorrected figures, with no way to say which) or letting the exception escape
and take the document's text into the job store with it. The discard is the
only option that is both fail-closed and honest, and it is never silent: the
flag routes the document to `review`, so a human sees it before the numbers
are used. What the flag must therefore NOT claim is that only summaries are
affected — hence the wording, and hence this paragraph.

**Blast radius.** Zero documents. The code fires nowhere in the 3,380-document
archive (measured: PIPE5 §4), and no outcome, flag or field moves. That is
precisely the state in which `DIAGNOSTICS_VERSION` is the only way to tell a
v3 rollup from a v4 one, which is why the bump is not optional — and why the
v4 entry ships with the guard test that makes the contract self-enforcing
(`test_the_diagnostics_version_moves_when_the_vocabulary_does`, mirroring the
mechanism COUNTS-P3 built for `OBSERVER_VERSION` after the same omission).

---

## 12. Observer-side vocabulary: the stated-count check

The two `integrity:` codes are in §3.2 and §4 as of v3; this section is what
remains once they are, and it is about the OTHER vocabulary — the five-value
one the measuring instrument uses, which never enters this taxonomy and reuses
two words that already mean something here. Recording the distinction is
cheaper than discovering it in a rollup.

The stated-count observer (Gustavo's 2026-08-10 sign-off; measurement in
`COUNTS_P1_MEASUREMENT.md`) classifies each document **per direction** as
exactly one of `match`, `mismatch`, `not_printed`, `semantics_incomparable`,
`check_unavailable`. It is a measuring instrument over cached payloads: it
emits no flag, produces no code in the `integrity:` namespace, never reaches
`diagnose`, and is not imported by `analysis/`, `ocr/`, `webapp/` or
`discovery/` — the dependency runs the other way, since COUNTS-P2 moved the
semantics table into `analysis/count_semantics.py` and the observer now reads
the shipping one.

Two names, two layers:

- **`check_unavailable`** here (§4, rank 4) is a *diagnostic class*: a
  document's diagnosis is incomplete because an integrity check crashed inside
  it. **`check_unavailable`** in the observer is a *count-check outcome*: there
  was no cached payload, no rows, aggregate-backed rows, or a row with no
  `direction`, so the comparison could not run. They are never mixed — the
  observer's values never enter `CLASS_OF`, `CLASS_PRECEDENCE` or
  `DIAGNOSTICS_VERSION`.
- **`semantics_incomparable`** has no counterpart here at all, and that is the
  point: it is the sign-off's forced-mismatch prohibition made into a value.
  Where a bank's printed count denotes a different set of rows than
  `Transaction.direction` does (cheques folded into a printed debit figure,
  category subtotals, multi-category sums, label-scoped subsets), the check
  declines to compare rather than manufacturing a defect — so that population
  produces no `integrity:` code either, and its absence from this taxonomy is
  a decision rather than a gap. The per-bank table and its arguments are
  `analysis/count_semantics.SEMANTICS`.

**Phase 2 landed (COUNTS-P2, 2026-08-13):** see the v3 changelog entry in §11
for the two codes, the widened scope, and the blast radius on the pinned 109.
`DIAGNOSABLE_CLASSES` extending to `review` closed §10 open question 2.
