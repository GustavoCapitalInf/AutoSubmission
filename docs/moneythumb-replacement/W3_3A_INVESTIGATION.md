# W3-3a — P2-1 investigation spike: layout-agnostic statement understanding

Author: Agent A (REEF). Date: 2026-08-07.
Status: **investigation complete; no production code proposed for merge.**
Task: WAVE3_BRIEF W3-3a · MASTER_PLAN AD-7 / P2-1 · gates at W3-3b (Ocean + Gustavo).
Spike code: `experiments/w3_3a/` (committed, guarded by
`tests/test_experiments_are_not_wired.py`; nothing on the dispatch or pipeline
path changed for this task).

---

## 0. Abstract

A ~400-line structurer that knows **no bank** was written and measured against
the platform's own gate on 184 real documents (109 pinned corpus + 75 archive
documents sampled across three unclaimed clusters). Headline numbers:

| Measure | Result |
|---|---|
| Pinned corpus: reached a publishable value | **5 / 109 (4.6%)** |
| Pinned corpus: of those, agreed with the claiming parser field-for-field | **5 / 5 — zero false validations** |
| Pinned corpus: produced a `Statement` at all | 81 / 109 (74%), 88 / 109 (81%) with row-detection variant B |
| Pinned corpus: agreed on beginning / ending balance where structured | 83% / 74% |
| Pinned corpus: agreed on transaction count and signed sum | 8.6% |
| Archive, currently-unclaimed documents: reached a publishable value | **6 / 75 (8%)** where the platform's coverage today is 0 |
| Vendor cost | **$0.00** — no model call in any measurement |
| Structuring cost | **5.6 ms/document** (the gate that judges it costs ~0.9 s, unchanged) |

Three findings decide the architecture:

1. **The gate is sufficient.** A deliberately naive structurer produced wrong
   transaction sets on 91% of the documents it read, and *not one* wrong value
   reached a publishable outcome. Reconciliation + ADB caught every one. This
   is the AD-7 premise measured rather than asserted: trust can come from the
   gate, so an approximate structurer is safe to build.
2. **The binding constraint is completeness, not recognition.** Getting into the
   gate is easy (74% → 81% by loosening one row-detection rule) and passing it
   did not move at all (5 → 5). Balances are found; the *transaction set* is
   not. Every improvement that matters is about capturing all rows with correct
   signs, not about recognising more documents.
3. **Flat text is the wrong input.** Where the structurer refused, the dominant
   cause was that the flattened line does not begin with a date — a
   multi-column page whose reading order was destroyed before the structurer
   saw it. This argues for reading **word geometry** (positions), not lines,
   and it is the single biggest lever available.

**Recommendation to the 3b review: build, but scope the claim honestly.** The
brief's proposed success metric (+15–25 points of validated coverage) is **not
supported** by this evidence for the unclaimed bucket alone; the measured basis
supports **+4 points today and +8 to +14 points with the geometry input**, and
the rest of the brief's target has to come from W3-2 (the 614 withheld) and
W3-5 (the 159 OCR-text failures), which are different mechanisms.

---

## 1. What was built, and what it knows

`experiments/w3_3a/structurer.py`, ~400 lines, deterministic, offline, no model.

A bank statement is not 47 layouts; it is one structure — a period, an opening
balance, a sequence of dated signed amounts, a closing balance — printed 47
ways. The spike encodes the structure and infers the printing:

| Stage | Rule | Bank knowledge used |
|---|---|---|
| Rows | a line whose head carries a date token (5 shapes) and which contains money | none |
| Column roles | **hypothesis test**: is the last money token a running balance? accepted iff `balance[i] − balance[i−1] == amount[i]` for ≥80% of rows | none |
| Signs | from the balance chain where it exists; else from the direction word in the nearest heading (`DEPOSIT`/`CREDIT` vs `WITHDRAWAL`/`DEBIT`/`FEE`); else **refuse** | English banking furniture only |
| Summary | first money token after a label (`BEGINNING BALANCE`, `CLOSING BALANCE`, `TOTAL DEPOSITS`…) | label vocabulary adapted from the prototype `grounding.py` |
| Period | an explicit `A to B` span of 20–100 days, else min/max row date | none |
| Year for `MM/DD` rows | majority year among the dates that *do* print one | none |

No institution, product, filename or document is named anywhere in it, and no
constant is fitted to a specific statement — the R-1 discipline applies to a
structurer exactly as it does to a parser.

The output is a `Statement` — the same schema the 46 parsers and the LLM path
fill — handed to the same `reconcile` → `classify` → `compute_metrics` chain the
pipeline runs. The harness measures **the gate**, not the structurer, which is
the design the prototype `eval_unknown_banks.py` got right.

## 2. Method

- **Stratum A — the pinned 109.** Every one is claimed by a parser and audited
  field-by-field, so this stratum measures *accuracy*: the structurer's output
  is compared against the claiming parser's `Statement` on beginning balance,
  ending balance, transaction count and signed transaction sum.
- **Stratum B — 75 archive documents**, drawn deterministically (sorted by path,
  every k-th) from the discovery rows in three clusters: known-bank variants
  (BMO/Chase/TD/CIBC/BofA/RBC folders), the Unidentified mix, and low-volume
  unknown banks (Huntington/Mercury/Fifth Third/Citibank/Lead/Zions/Brex). Only
  documents **no parser claimed** are sampled, so the platform's coverage on
  this stratum is 0 by construction.
- Documents are read through the **production ladder** (`ocr.pipeline.parse_statement`,
  offline rungs only) — the DSC-1 binding, for the same reason: measuring
  through a different reader than production uses makes every number a fiction.
- Archive documents were read **in place, read-only**. No archive file was
  copied, modified or committed; the harness prints aggregate counts only, and
  no statement content, filename or amount appears in this document or in any
  committed fixture.

Reproduce with:

```
python -m experiments.w3_3a.evaluate --corpus
python -m experiments.w3_3a.evaluate --archive --per-cluster 25 \
    --reports <main-checkout>/discovery_reports --archive-root "<main-checkout>/Bank Statements"
```

## 3. Measured results

### 3.1 Stratum A — accuracy against audited truth (109 documents, 127 s)

| Disposition | Variant A (date leads the line) | Variant B (date anywhere in the line head) |
|---|---|---|
| validated (would publish a value) | 5 (4.6%) | 5 (4.6%) |
| withheld — ADB refused | 76 (69.7%) | 83 (76.1%) |
| refused — no dated rows found | 25 (22.9%) | 19 (17.4%) |
| refused — rows found, no sign available | 3 (2.8%) | 2 (1.8%) |

Field agreement, over the documents that produced a `Statement`:

| Field | Variant A (n=81) | Variant B (n=88) |
|---|---|---|
| beginning balance | 82.7% | 79.5% |
| ending balance | 74.1% | 71.6% |
| transaction count | 8.6% | 9.1% |
| signed transaction sum | 8.6% | 6.8% |
| **validated *and* correct** | **5 of 5** | **5 of 5** |
| **validated and WRONG** | **0** | **0** |

### 3.2 Stratum B — reach on unclaimed documents (75 documents)

| Cluster | n | validated | withheld (ADB) | refused | balance-chain accepted |
|---|---|---|---|---|---|
| known-bank variants | 25 | **3 (12%)** | 14 | 8 | 5 |
| Unidentified mix | 25 | **0** | 18 | 7 | 3 |
| low-volume unknown banks | 25 | **3 (12%)** | 20 | 2 | 6 |

(Variant B figures; variant A validated the same 6 documents and structured 13
fewer.) Every one of these 75 documents is `unclaimed` today, i.e. contributes
0 to coverage.

### 3.3 Where it stops, ranked (22 refusals characterised structurally)

| Cause | Documents | Reading |
|---|---|---|
| fewer than 5 lines carry both a date and money | 12 | the text itself is sparse — an image-only or non-statement document. **Not a structurer problem**: this is W3-5's visual rung. |
| ≥5 date+money lines, but the date is not at the head of the line | 7 | reading order lost in flattening — the geometry finding (§5) |
| ≥5 date-leading lines, still refused | 3 | no year available (2), row-date token unreadable (1) |

## 4. Candidate approaches, assessed against this evidence

| # | Approach | Evidence | Verdict |
|---|---|---|---|
| A | **Text-line structurer** (what was measured) | 4.6% corpus / 8% archive validated, 0 false validations, 5.6 ms/doc, $0 | Viable floor. Cheap, safe, insufficient alone. |
| B | **Word-geometry structurer** — read PDF word boxes (already available via the native-text layer's engine), cluster x-positions into columns, type each column (date / description / debit / credit / balance) by content statistics, then apply A's chain test | 7 of 22 refusals are pure reading-order failures; and the transaction-completeness failures in §3.1 are dominated by multi-line descriptions and multi-column amounts, which geometry resolves and flat text cannot | **The recommended core.** Largest measured lever, still deterministic and $0. |
| C | **Table-grid structurer** (consume the OCR reader's HTML tables when present) | the corpus's table-shaped documents already structure well under A; the archive's unclaimed half is mostly native text with no table markup | Fold into B as an input adapter, not a separate path. |
| D | **Model structurer behind the same gate** (the prototype's `StatementStructurer` + bounded retry) | not measured here; PROJECT_GOAL excludes paid vendors from the production path | Keep the protocol shape so a local model can be dropped in later; no vendor call in production. |
| E | **More parsers** | AD-7 already rejected #47…#400; discovery ranks the largest single unknown bank at 54 documents | Rejected, unchanged. Reserved for W3-4 adjudication of specific high-volume, layout-stable banks. |

## 5. Proposed architecture (for the 3b ruling)

```
markdown / word-geometry
        |
        v
   Structurer  (protocol: structure(document) -> Statement | Refusal)
        |            deterministic first; model-backed later, same protocol
        v
    Statement   <-- the SAME schema parsers and the LLM path fill
        |
        +--> reconcile  (arithmetic truth)          } BOTH must pass
        +--> grounding  (source truth, §6)          } before anything publishes
        |
        v
   fail closed: withheld / review, never a guessed value
```

Placement — **the dispatch seam does not change**. The structurer is a rung
*after* `resolve()` returns `unclaimed`, inside the pipeline's existing
"nothing claimed this" branch, behind a setting that defaults **off** until 3c
has its own measurements:

- `Dispatch` is untouched; the registry keeps its meaning ("which parser
  claimed this"), and a structured document reports `parser_id = null` with a
  new telemetry outcome value, so coverage statistics never conflate a parser
  claim with a structurer hypothesis;
- the corpus gate is unaffected by construction: all 109 are claimed, so the
  unclaimed branch is never reached for them — the byte-identity proof holds
  without a re-baseline;
- `parse_mode="deterministic"` gains a third state (structured), which the
  discovery runner can measure with the runner it already has.

Success metric, estimated from measurement rather than proposed from hope:

| Scenario | Basis | Validated coverage delta over the 3,506-document discovery set |
|---|---|---|
| Ship approach A as-is | 8% of 1,741 unclaimed | **+4.0 points** |
| A + geometry input (B) closing the reading-order and completeness gaps | 20–35% of unclaimed, the range the §3.3 causes support | **+10 to +17 points** |
| Brief's proposed target (+15–25) | — | reachable **only** with W3-2's withheld-614 work and W3-5's OCR rung included; not from the unclaimed bucket alone |

Non-negotiable acceptance for 3c: **zero false validations**, measured on the
pinned 109 exactly as in §3.1 (this spike: 5 of 5 correct, 0 wrong), plus corpus
gate byte-identical and the structurer's outputs never entering an audited path
without both reconciliation and grounding.

### Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | A self-consistent wrong reading passes reconciliation (e.g. a column read as amounts that happens to chain) | **High — the only one that matters** | grounding as a second, independent axis (§6); zero-false-validation acceptance measured per release; the chain test requires ≥80% agreement over ≥3 rows, which is hard to reach by accident |
| 2 | Coverage claims drift from parser claims in the statistics | Medium | separate outcome value in telemetry; `parser_id` stays null; discovery reports the two separately |
| 3 | Scope creep into the protected financial core | Medium | the structurer produces `Statement` and nothing else; reconciliation, ADB, classification, serialization untouched (MASTER_PLAN §4) |
| 4 | The structurer becomes a bag of bank-specific special cases | Medium | the R-1 guard test already forbids statement-specific constants; extend its file list to the structurer in 3c |
| 5 | Geometry input ties us to one PDF engine | Low | the engine is already a production dependency for native text; the structurer takes an interface, not a library |
| 6 | Cost/latency on a 3,500-document run | Low | measured 5.6 ms/document; the gate around it is unchanged |

## 6. Adapted-input assessment (PROTOTYPE_REVIEW items 1–3)

- **`analysis/grounding.py` (54a9e8d, 517 lines) — consulted, partially adapted,
  worth rebuilding.** Its label vocabulary and label-window technique were
  adapted directly into the spike's summary extraction (cited in the source),
  with the direction reversed: the prototype checked that a claimed value sat
  beside an appropriate label, the spike uses the same relation to *find* the
  value. Its full contribution — amount-and-date-on-the-claimed-page, span
  uniqueness (one source span cannot justify two extracted rows), period and
  identity scoping — is exactly the second validation axis this architecture
  needs, and this spike's §3.1 result is precisely why: reconciliation caught
  every wrong value here, but reconciliation alone cannot distinguish a
  transaction the document contains from a plausible one it does not. **Rebuild
  it against the post-R-2 `analysis/money.py` and `analysis/date_tokens.py`,
  heuristic by heuristic, in 3c — do not import it.** Its `_date_variants` set
  (23 renderings of one date) is reusable almost as-is and is the kind of thing
  it would be wasteful to re-derive.
- **`eval_unknown_banks.py` (f14282e, 392 lines) — design adopted, code not.**
  "One question per statement: did the unknown path reach automatic approval or
  fail closed, and why" is the right frame and shaped this spike's harness. Its
  **recorded-fixture replay** design is the piece to build for real in 3c: the
  live harness used here needs the archive to run, which makes it unusable in
  CI, while a recorded corpus of `(document markdown, structurer output)` pairs
  measures the trust layer offline and deterministically. Its `--check`
  regression mode is the mechanism that would keep a structurer from silently
  regressing between waves.
- **Bounded-retry / kill-switch (`analysis/universal.py`, f14282e) — deferred,
  not needed yet.** The deterministic structurer has nothing to retry: it is
  pure and total, and a second attempt returns the same answer. The pattern
  becomes relevant only at approach D (a model-backed structurer), where its
  attempt budget, `=0` kill switch and per-attempt telemetry are the right
  shape and should be adopted then rather than anticipated now.
- **Rejected material** (Gemini-centred production routing, protected-module
  edits, prototype `webapp/`): unchanged from PROTOTYPE_REVIEW's assessment;
  nothing in this investigation found a reason to revisit any of it.

### Prototype-branch deletion recommendation

**Delete both branch refs after tagging.** The P2-1 investigation was the last
outstanding consumer (PROTOTYPE_REVIEW "Incorporation status"), and it has now
extracted what it needs:

- item 1 (grounding) — technique understood, vocabulary adapted, rebuild
  specified above; the file is quoted in this document by design and location,
  and the 3c rebuild is a review of heuristics, not a port;
- item 2 (eval harness) — design adopted, replay-fixture pattern specified;
- item 3 (bounded retry) — deferred to approach D, with its contract recorded
  in PROTOTYPE_REVIEW §3 and here;
- item 4 (contract docs) — a docs-pass item, needing no branch.

Recommendation, in order: tag `archive/universal-prototype-2026-08-04`
(`f14282e`) and `archive/universal-prototype-2026-08-05` (`54a9e8d`) so both
objects stay permanently reachable, push the tags, verify they resolve, then
delete `origin/cursor/cloud-agent-1785900428099-wlfy6` and
`origin/feature/universal-statement-intelligence`. Nothing is lost: a tag is as
reachable as a branch and cannot be mistaken for a line of development. This is
Gustavo's call (WAVE3_BRIEF §4.4); the agent has not touched either ref.

## 7. What 3c would build, if approved

1. **Geometry reader** — word boxes → column clusters → typed columns, as an
   input adapter behind the same structurer interface (largest measured lever).
2. **Structurer**, promoted into the production tree with the spike's rules,
   the completeness work §3.3 identifies (multi-line descriptions, section
   totals as a cross-check, wider summary-label coverage), and R-1 guard-test
   coverage.
3. **Grounding**, rebuilt from the prototype's design against shared utilities,
   as the second validation axis. Both axes required before publication.
4. **Replay harness + recorded fixtures**, offline and CI-runnable, with a
   `--check` regression mode; synthetic layouts plus recorded (masked) archive
   structures.
5. **Wiring**: one rung in the unclaimed branch, default off, telemetry outcome
   distinct from a parser claim; discovery re-run measures the delta with the
   runner it already has.

## 8. Open questions for the 3b review

1. **Placement.** Rung inside the pipeline's unclaimed branch (proposed) versus
   a registry registration with a band-900 "last resort" registration. The
   proposal deliberately keeps it out of the registry so that "claimed" keeps
   meaning "a parser recognised this document" — is that the ruling?
2. **Success metric.** Does Ocean accept re-scoping the brief's +15–25 points to
   +10 to +17 from this bucket, with the remainder assigned to W3-2 and W3-5?
3. **Grounding scope for 3c.** Full rebuild (all six heuristic families) before
   any structurer output publishes, or amount/date/page grounding first with
   span-uniqueness and identity scoping following?
4. **Withheld-614 reuse.** A structurer opinion on a document a parser already
   claimed is a completeness cross-check (W3-2's ranked failures suggest
   missing transactions are the common cause). Attractive, but it puts two
   extractors on one document — in scope for 3c, or a separate ticket?
5. **Geometry dependency.** The word-box reader means the structurer's input is
   produced by the PDF engine rather than by the markdown ladder. Acceptable,
   or must every structurer input remain the same markdown every other path
   sees?
