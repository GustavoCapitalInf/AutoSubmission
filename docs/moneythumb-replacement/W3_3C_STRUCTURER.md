# W3-3c — the generic statement structurer

Author: Agent A (REEF). Date: 2026-08-07.
Status: **subsystem proof-complete; the pipeline rung is PROPOSED and pinned as
strict xfails, awaiting Ocean.** Default off.
Rulings implemented: W3-3b 1–6 (`WAVE2_EXECUTION_LOG.md`).
Evidence it was built from: `W3_3A_INVESTIGATION.md` (frozen).

---

## 1. What it is

`analysis/structurer/` fills the same `Statement` schema every parser fills,
for documents no parser claims. It knows the STRUCTURE of a bank statement —
a period, an opening balance, a sequence of dated signed amounts, a closing
balance — and infers each document's printing of it.

| Module | Job |
|---|---|
| `tokens.py` | every date and money shape, read without knowing which one this bank uses |
| `geometry.py` | PDF word boxes → visual lines (the 3a finding: flat text destroys reading order) |
| `rows.py` | which column is the date / amount / balance, and what sign each row carries |
| `summary.py` | the printed period and summary figures, with provenance |
| `grounding.py` | was each published value actually printed? (second validation axis) |
| `core.py` | the rung: source → `Statement`, or a refusal that names the step that failed |

The subsystem's entire public surface for the pipeline is one function:

```python
structure_unclaimed(markdown, *, geometry=None) -> Statement | None
```

`None` means "no opinion" and the caller proceeds exactly as it does today.

## 2. The rules that decide, and why each one is a rule

| Decision | Rule | Alternative rejected |
|---|---|---|
| Which column is the balance | the reading under which `balance[i] − balance[i−1] == amount[i]` holds for **≥90% of ≥5 rows** | trusting the rightmost money column: a running item COUNT sits in the same place and scores ~0 here |
| Which sign a row carries | balance-chain delta → debit/credit column (geometry) → direction word in the nearest heading → **refuse** | inferring from magnitude or position: a debit read as a credit reconciles nowhere and misleads everywhere |
| What year a `MM/DD` row is | the majority year the DOCUMENT prints | `date.today()`: silently re-dates an archived statement |
| What the period is | an explicit printed range, or the two dates printed beside the opening and closing balances | deriving it from the first and last transaction: shortens every period whose opening days were quiet, and the ADB engine divides by the length |
| Whether a dated money line is a transaction | not if it is summary furniture (`Total…`, `Balance forward on…`, `Closing balance…`) | taking every dated money line: invents transactions and drags the ledger into the previous period |
| Whether to publish at all | the ledger must reach the printed closing balance, every row and both balance anchors must be **grounded**, and every row must fall inside the period | letting reconciliation catch it downstream: true, but "some of the rows" is not a weaker statement than the truth, it is a false one |

## 3. Grounding (ruling 3)

Reconciliation proves arithmetic. It cannot prove a number was ever printed.
A structurer that mis-reads a column, re-uses one printed figure twice, or
supplies a year the document never printed can produce a set of numbers that
adds up perfectly and describes a statement that does not exist.

`grounding.py` re-locates every published value in the **raw page text**,
independently of the reasoning that produced it:

- each transaction amount, on the page it claims, within a window of its own
  date (in any of ~30 renderings) and a distinctive word of its description;
- **span uniqueness** — one printed figure justifies one row, never two;
- each published summary figure beside an appropriate label;
- a printed period;
- no provenance → not publishable.

Rebuilt from the concepts in the archived prototype's `analysis/grounding.py`
(`archive/universal-prototype-2026-08-05`, commit `54a9e8d`) against the
post-R-2 shared money/date utilities, reviewed heuristic by heuristic. The
prototype checked a model's output; the mechanism is extractor-agnostic, and
on a deterministic structurer it catches inference errors instead of
hallucinations. Its architecture was not merged (ruling 3).

## 4. Measured (109 pinned documents, read through the production ladder)

Reproduce: `python -m tools.measure_structurer --corpus [--flat]`.

| | flat text (3a baseline) | **word geometry** |
|---|---|---|
| published a statement | 7 | 6 |
| …of which validated by the platform's own gate | 5 | **5** |
| …of which **correct on every audited field** | 5 | **5** |
| **published and WRONG** | **0** | **0** |
| field agreement among published (begin/end/count/sum) | 100 / 100 / 86 / 100 % | **100 / 100 / 100 / 100 %** |
| refused: rows unreadable (`no_dated_rows`) | 25 | **11** |
| refused: rows outside the period | 21 | **7** |
| refused: no printed period | 14 | 19 |
| refused: ledger did not reach the closing balance | 29 | 53 |
| refused: ungrounded | 10 | 12 |

**Published implies correct** on this corpus: every field of every published
statement matches the audited truth. That is the acceptance criterion, and it
is met by refusing — 103 of 109 documents produce no opinion at all.

**What geometry bought**, precisely: it moved documents *deeper* into the
pipeline rather than further through it. Reading-order failures collapse
(`no_dated_rows` 25 → 11, `period_excludes_rows` 21 → 7) and the residue
concentrates in `ledger_incomplete` (29 → 53) — the structurer now reads the
document's shape correctly and is missing *rows*. The 3a finding stands
confirmed with a sharper edge: **the binding constraint is completeness, and
it is now visible and named instead of hidden inside a wrong answer.**

## 4b. Measured on documents no parser claims (75 archive documents)

Deterministic stratified sample across the three ranked clusters, read in
place, read-only, aggregates only. These documents contribute **zero** coverage
today by construction.

| Cluster | n | validated (geometry) | validated (flat) | dominant refusal |
|---|---|---|---|---|
| known-bank variants | 25 | 0 | 0 | no printed period (10), ledger incomplete (8) |
| Unidentified mix | 25 | **1** | 0 | ungrounded (6), no printed period (6) |
| low-volume unknown banks | 25 | **3** | 3 | rows outside the period (10), ungrounded (9) |
| **total** | **75** | **4 (5.3%)** | **3 (4.0%)** | — |

Sign provenance across ~5,700 accepted rows: 58–78% from a direction heading,
21–42% from the balance chain, <1% from geometry-separated debit/credit
columns.

### What this does to the targets (ruling 6: no predetermined number)

3a measured **8%** of this same population reaching a publishable value. This
build measures **5.3%** — and the difference is not a regression, it is the
ledger-identity requirement added here (§2, last row): a statement whose rows
do not reach its own printed closing balance is now refused rather than
published for reconciliation to withhold later. Some of 3a's archive
"validations" were incomplete ledgers that no audited truth existed to catch.

Extrapolated honestly against the frozen 3,506-document baseline:

| | measured basis | coverage delta |
|---|---|---|
| this build, as it stands | 5.3% of 1,741 unclaimed ≈ 92 documents | **≈ +2.6 points** |
| 3a's flat-input estimate | 8% of 1,741, without the ledger check | +4 points |
| the +10–17 geometry hypothesis | — | **NOT validated by this build** |

Geometry did what the 3a evidence predicted — it removed reading-order failure
as the binding constraint — but that moved documents from one refusal to
another rather than through the gate. The hypothesis is not disproven either:
the refusals it exposed are concrete and named (`no_printed_period` 24%,
`ungrounded` 20%, `ledger_incomplete` 17%, `period_excludes_rows` 16%), and
each is a tractable piece of work rather than a mystery. **What this build
establishes is the safety floor, not the coverage ceiling.**

## 5. Placement (ruling 2) — proposed, not written

A fallback on the **unclaimed branch** of `analyze_markdown`, never a
registration. A parser that claimed a document on proven issuer evidence keeps
it; `ambiguous` and `parser_exception` keep their own fail-closed outcomes and
are never rescued by structuring. The full proposed diff (six added lines, one
import, one optional keyword, no re-indentation) is in the module docstring of
`tests/test_structurer_pipeline.py` and pinned there by two strict xfails.

`model_used = "generic-structurer-deterministic"` is the measurement hook: the
`-deterministic` suffix is what `telemetry.record.model_calls_for` reads as "no
model call" (there is none), and the prefix keeps the rung distinguishable from
every parser, so coverage statistics never conflate "a parser claimed this"
with "the generic rung structured this". **No telemetry change is required.**

Discovery-side reporting (a `structured` column and a rollup line) is a
`discovery/` change and therefore HARBOR's file — design only, per dispatch:
the runner reads `payload["model_used"]`, which it already receives, and needs
no new plumbing from this subsystem.

## 6. Opt-in (ruling 6)

`GENERIC_STRUCTURER_ENABLED=1`. Absent, empty, `0`, `false` or `no` → the rung
does not run and `analyze_markdown` behaves exactly as it does today, which a
test asserts at the pipeline level. Chosen as an environment contract rather
than a `Settings` field to keep the change inside this subsystem's file
domain; if Ocean prefers it in `analysis/config.py`, that is a two-line
follow-up.

## 7. Known limits, honestly

1. **Completeness is the gap.** 53 of 109 pinned documents read most of their
   rows and not all. Every one of them refuses. Closing this is the next
   tranche of work and is where the remaining coverage lives.
2. **Small statements refuse.** The chain test needs 5 rows; a 3-transaction
   statement with no direction headings cannot establish its signs.
3. **`balance forward + 1 day`** is a convention, not a proof. It is applied
   only for labels that state a prior-period close, and it is called out here
   because it is the one place the subsystem infers a date the document does
   not print. An open question for review (§8.2).
4. **Scanned documents get nothing extra.** `geometry_from_pdf` returns None
   without native text; OCR-grid geometry is a W3-5 interface question.
5. **Multi-account documents** are read as one ledger, and will usually fail
   the ledger-identity check and refuse. Correct, but crude — L-1 territory.

## 8. Open questions for the review

1. **Publish-vs-refuse on `ledger_incomplete`.** The subsystem refuses when its
   ledger does not reach the printed closing balance, on the argument that a
   partial ledger is a false statement rather than a weak one. Reconciliation
   would have withheld those documents anyway, so no validated coverage is
   lost — but it does mean the rung produces no artifact for an analyst to look
   at. Confirm the refusal, or prefer publish-and-withhold?
2. **The `+1 day` period convention** (§7.3). Keep, or refuse unless the period
   is printed as an explicit range?
3. **Geometry wiring.** The proposed `document_geometry` keyword is inert until
   a caller passes it, and the callers that hold the PDF bytes are the webapp
   worker and the discovery runner (HARBOR's file). Who wires it, and when?
4. **Grounding strictness.** Transaction coverage is required at **1.0**. The
   harness can report the distribution at lower thresholds if Ocean wants the
   evidence for a different bar; production should not move without it.
