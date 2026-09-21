# PHASE 3.1 — THE VISUAL FALLBACK: TWO MODELS THAT CHECK EACH OTHER

Handoff written 2026-09-21 by the extraction-shootout session, for the next agent.
Authority for every instruction in this document: Gustavo, 2026-09-21, after reading the shootout
leaderboard. Where this document and an older plan disagree, this document wins for Phase 3.1 only.

- Private copy (includes the connection section): `C:\Users\GustavoPrietodePaula\extraction-shootout\private\PHASE3-VISUAL-FALLBACK-HANDOFF.md`
- Repository copy for the project record: `docs/agent-handoffs/PHASE3-VISUAL-FALLBACK.md` (this file — identical to the private copy, with section 2 replaced by a pointer, because connection details never enter Git)
- Connection annex: `C:\Users\GustavoPrietodePaula\extraction-shootout\private\PHASE3-FALLBACK-CONNECTION.md`

---

## 0. What you are building, in one paragraph

A second extraction path for the web app. A user uploads a PDF. The deterministic parser runs first,
exactly as it does today. If its result does not validate, or if the operator ticks **Force visual
OCR**, the document is read instead by two vision models that check each other: **dots.mocr** reads
every page and proposes every row; **Qwen3.8-27B-NVFP4** reads the same page image together with
those proposed rows and returns a verdict on each one — confirm, correct, reject — and adds any row
it can see that dots.mocr missed. The merged rows are converted into the same `Statement` shape the
deterministic path produces, the existing analysis layer computes every metric unchanged, and a
confidence score built from model agreement plus the existing gate is returned with the analysis.
**Neither model performs arithmetic and neither model classifies anything.**

### 0.1 Read these first, in this order

1. This document, end to end, before touching code.
2. `docs/moneythumb-replacement/phase3/PHASE3-VLM-PROGRAM-PLAN-v1.md`, sections 3 and 4. The
   architecture and the twelve non-negotiable invariants stand unchanged. Only the Stage A and
   Stage B *model choices* in its section 5 are superseded, by the measured evidence in section 1
   below.
3. `vlm/schema.py`, `vlm/prompts.py`, `vlm/assemble.py`, `vlm/metadata.py`, `vlm/gate.py`. **The
   page-proposal contract, the no-arithmetic prompt, the row assembler and the deterministic gate
   already exist in the tree.** You are extending them, not inventing them. `vlm/schema.py` is at
   `SCHEMA_VERSION = 3`, `vlm/prompts.py` at `PROMPT_VERSION = 3`, `vlm/gate.py` at `GATE_VERSION = 6`.
4. `analysis/schema.py` (the `Statement` and `Transaction` contract), `analysis/metrics.py`,
   `analysis/adb.py`. These decide what the extractor must supply. Section 4 below distils them.
5. The connection annex, for the GPU host.
6. `reports/LEADERBOARD.md` inside `CHATGPT_COMPARISON_PACKAGE.zip`, for the evidence behind the
   model picks.

### 0.2 Standing rules inherited from the shootout, still binding

- Self-hosted inference only, on the rented instance named in the annex. Customer pages, extracted
  content and detailed diffs are never sent to a third-party inference provider.
- Connection details, customer page content and detailed diffs stay in the private tree. Reports and
  the repository carry metadata, counts and status only.
- Never request or copy a private key to the instance. Never disable host-key verification.
- Temperature 0, fixed seeds, pinned revisions, pinned prompt hashes. Identical inputs must produce
  identical proposals, and any nondeterminism is measured and recorded rather than assumed away.

---

## 1. Why these two models, and what the evidence actually says

Nine candidates were scored on 16 statements and 151 pages on 2026-09-20 and 2026-09-21, image-only
at 300 DPI, one frozen run each, against ChatGPT reference answers.

| candidate | licence | money recall | truncated pages | repeated lines | pages/min |
|---|---|---|---|---|---|
| bonsai2-27b-pq2 | research build | 99.5% | 3 | 13,909 | 4.9 |
| qwen3.8-27b-nvfp4 | Apache-2.0 | 99.3% | 0 | 2,737 | 3.1 |
| dots.mocr | custom, see 8.1 | 98.5% | 5 | 1,796 | 5.3 |
| ovisocr2 | Apache-2.0 | 97.8% | 6 | 6,340 | 14.1 |
| qwen3.5-9b | Apache-2.0 | 97.4% | 5 | 8,488 | 3.5 |
| glm-ocr | MIT | 94.7% | 0 | 369 | 24.6 |
| internvl3.5-8b | Apache-2.0 | 93.8% | 5 | 2,271 | 3.7 |
| teleocr-official | — | 92.4% | 0 | 78 | 7.4 |
| deepseek-ocr-2 | — | 75.9% | 2 | 1,363 | 25.6 |

**Qwen3.8-27B-NVFP4 is the reviewer** because it matched the best amount recall in the field while
being the only top finisher with no truncated pages, it runs on stock vLLM, and it is already
licence-cleared in `docs/moneythumb-replacement/phase3/LICENSES.md` at the same pinned revision.
Bonsai 2 scored fractionally higher but needs a research fork of llama.cpp pinned to one commit and
produced by far the most repetition; it is not a foundation to build on.

**dots.mocr is the proposer** because it is a different architecture with a different failure mode,
it emits layout JSON with bounding boxes that give every row page and box provenance, and it covers
the reviewer's weakest document (US Bank: Qwen 82%, dots.mocr 100%).

### 1.1 The number that justifies the whole design

Their errors barely overlap, so agreement is a usable confidence signal. Measured on the 151 pages:

```
Pages where both models produce an identical set of amounts:  137 of 151  (91%)
Of those, sets that match the reference exactly:              136 of 137  (99%)
Amounts missed by both models:                                  8 of 3,357
Pages left over for review:                                    14 of 151   (9%)
```

### 1.2 Three caveats you must carry forward, not bury

1. **Reference agreement is not correctness.** The references are ChatGPT output. In the bounded
   evidence review, 90 of 400 examined disagreements went **against the reference**, not against the
   model. Differences below about one point are not real differences.
2. **The reviewer configuration is new.** Every number above comes from the two models transcribing
   pages *independently*. In this design Stage B instead sees Stage A's rows. That changes its
   behaviour, and it can make things worse by anchoring the reviewer on the proposer's mistakes. The
   agreement rate and the correction quality **must be re-measured** in review mode before any
   confidence band is trusted. Section 6 is that measurement.
3. **Neither dots.mocr nor Qwen in review mode has been through the disagreement review.** Only the
   independent runs were.

### 1.3 If dots.mocr cannot be used (see the licence item in 8.1)

Measured substitutes for the Stage A slot, same reviewer, same corpus:

| Stage A | licence | union recall | pages agreeing | pages left for review |
|---|---|---|---|---|
| dots.mocr | custom | 99.76% | 137 of 151 (91%) | 14 |
| qwen3.5-9b | Apache-2.0 | 99.88% | 134 of 151 (89%) | 17 |
| ovisocr2 | Apache-2.0 | 99.55% | 128 of 151 (85%) | 23 |
| glm-ocr | MIT | 99.64% | 110 of 151 (73%) | 41 |

The pipeline does not depend on dots.mocr. Swapping it costs between two and twenty-seven extra
review pages out of 151. Note that `qwen3.5-9b` scores best on paper but shares an architecture
family with the reviewer, so its agreement is weaker evidence of correctness than agreement across
families; prefer `ovisocr2` if the choice is forced and independence matters more than the headline.
`PaddleOCR-VL-1.6` is a further Apache-2.0 option already implemented in the tree, but it was not in
this shootout and would have to be measured first.

---

## 2. The GPU host, and what is already installed

The instance address, port, host-key fingerprint and SSH alias are deliberately **not** in this
repository. They are in the private connection annex named at the top of this document, together
with the tunnel commands. Ask Gustavo for it if you do not have it.

What matters here, and is safe to record:

- One rented NVIDIA RTX 6000D with 85,651 MiB, 384 vCPU, 755 GB RAM, ~320 GB free on `/workspace`.
- Remote root `/workspace/bank-statement-shootout`.
- Installed and verified on 2026-09-21: `envs/vllm` with vLLM 0.29.0, torch 2.13.0+cu130,
  transformers 5.17.0; CUDA 13.0 toolkit alongside the image's 12.8 (the FlashInfer JIT needs
  at least 12.9 on Blackwell).
- Stage A weights `rednote-hilab/dots.mocr` at revision `e539fbb52280393adc081b289ec597430a0f9031`.
- Stage B weights `nvidia/Qwen3.8-27B-NVFP4` at revision `482ca0f3832238542f8f5295dde86b5f22711d80`.
  Both are the exact revisions that produced the leaderboard numbers. Do not float them.
- The 16 reference PDFs and the frozen 300 DPI renders under `corpus/` and `pages/`.
- `artifacts/serve_pair.sh start|stop|status` starts Stage A on port 18013 at
  `gpu_memory_utilization 0.20` and Stage B on port 18022 at `0.55`, so **both models stay resident
  at once** on this card. That was impossible on the 32 GB machine the shootout ran on, where
  candidates were served one at a time. Other serving flags are identical to the benchmark
  (`--max-model-len 32768 --max-num-seqs 2 --limit-mm-per-prompt.image 1
  --no-enable-prefix-caching`, `--trust-remote-code` for Stage A only,
  `VLLM_USE_FLASHINFER_SAMPLER=0`). Raising `--max-num-seqs` for throughput is a later, separate
  change that must be re-validated, because batching can perturb numerics even at temperature 0.
- Model servers bind loopback only and are reached over an SSH tunnel. Port 8080 on the instance is
  the template's own Jupyter; leave it alone.

---

## 3. The pipeline

```
PDF ─► Stage 0  render pages, 300 DPI, pypdfium2, page hash recorded
    ─► Stage A  dots.mocr per page  ──► layout elements with boxes ──► candidate rows
    ─► Stage B  Qwen3.8-27B per page: page image + Stage A's candidate rows
                 ──► per-row verdict: confirm | correct | reject,  plus rows Stage A missed
    ─► Stage C  merge (our code, deterministic): row states, field provenance, confidence
    ─► Stage D  the existing gate: vlm/gate.py then analysis/reconcile.py
    ─► Stage E  adapt to the shape the analysis layer already consumes
    ─► the existing analysis layer computes every metric, unchanged
```

### Stage 0 — render

Reuse `vlm/render.py::render_pages`. It already returns `jpeg`, `jpeg_sha256`, `pixel_sha256`,
`pdf_width_pt`, `pdf_height_pt`, `rotation_deg` and a `render_settings()` block for provenance.
Note it scales to a 1540 px long edge rather than a DPI, whereas the shootout rendered 300 DPI PNG.
**Measure both before choosing.** If the 1540 px render loses amounts on dense pages, raise the long
edge or switch that path to 300 DPI; the benchmark numbers in section 1 are only valid for input of
the quality they were measured on. This is the first thing to check in section 6, because everything
downstream inherits it.

Feed the models the page image only. Do not feed them the PDF text layer: by the time this path
runs, the text layer has already failed, and mixing it in makes the two readings non-independent.

### Stage A — dots.mocr, the proposer

- Server: port 18013, the frozen benchmark prompt, `temperature 0`, `seed 0`, `max_tokens 12000`.
- Output: layout elements, each with `bbox`, a category from the model's fixed list, and text.
- Then **our** deterministic row assembler turns table and text elements into candidate rows. Extend
  `vlm/assemble.py`; `CandidateRow` already carries `date`, `date_text`, `description`, `amount`,
  `direction`, `balance`, `page`, `source`, `locator` and `direction_source`.
- Keep the boxes. They are what lets the reviewer be pointed at a region and what lets a human
  auditor find the row on the page later.
- Known Stage A failure mode from the benchmark: 5 truncated pages and 1,796 repeated lines. A
  truncated page must keep its slot and be marked, never silently shortened.

### Stage B — Qwen3.8-27B-NVFP4, the reviewer

- Server: port 18022, `chat_template_kwargs {"enable_thinking": false}`, `temperature 0`, `seed 0`.
- Input per page: the page image, plus Stage A's candidate rows as a compact numbered list.
- Output: constrained JSON, one entry per candidate row plus an `added` list. Use vLLM guided
  decoding against a schema derived from `vlm/schema.py`, bump `SCHEMA_VERSION`, and pin the schema
  by hash in the receipt. Keep `vlm/prompts.py`'s existing rule verbatim: copy every value exactly
  as printed, never compute, infer or invent a value.
- **Every Stage A row gets an explicit verdict.** This is Gustavo's requirement that anything
  dots.mocr caught be double-checked rather than trusted, and it is satisfied by construction: no
  row reaches the merge without the reviewer having looked at it.
- A `correct` verdict must carry both the original and the corrected value. Never overwrite in place.
- Rows the reviewer adds are marked as reviewer-only and carry lower confidence, because nothing
  independent has confirmed them.

### Stage C — merge and confidence (our code, deterministic)

Row states, and the whole basis of the confidence score:

| state | meaning | evidence strength |
|---|---|---|
| `agreed` | reviewer confirmed the proposer's row unchanged | highest; the 99% band in 1.1 |
| `corrected` | reviewer changed at least one field | medium, both values retained |
| `added` | reviewer saw a row the proposer missed | medium, one model only |
| `rejected` | reviewer says it is not a transaction row | excluded, retained as evidence |
| `unresolved` | reviewer could not read it, or the page truncated | low, must surface for review |

Page confidence and document confidence roll up from these states **combined with** the Stage D gate
result. Do not invent a score from model self-reported probabilities; the evidence base here is
inter-model agreement and deterministic reconciliation, nothing else. Until section 6 has been run,
treat every band as provisional and record the raw state counts alongside any score, so the bands
can be re-cut later without re-extracting.

### Stage D — the gate

`vlm/gate.py` already exists at `GATE_VERSION = 6` with a closed refusal vocabulary (`no_rows`,
`sum_mismatch`, `continuity_break`, `duplicate_row`, `currency_conflict`, `period_mismatch` and the
rest). Use it. It never admits partially. Then `analysis/reconcile.py::reconcile` decides. The model
proposes; deterministic arithmetic disposes. This is invariant 1 of the program plan and it is not
negotiable.

### Stage E — hand off to the analysis layer

Two altitudes are possible and the choice matters. **Prefer the first.**

1. **Return a `StatementMarkdown`** (`ocr/document.py`), exactly as `ocr/paddle_rung.py` already
   adapts `PaddleRead` at `ocr/pipeline.py:169-182`. Required fields: `source_file`, a `model` token
   that passes `ocr/config.py::validate_model_token`, `pages: list[str]`, `page_integrity` from
   `ocr.truncation.assess_pages`, `page_extractor` with one token per page, and optionally
   `evidence` and `extraction_telemetry`. Then `analyze(doc)` in `webapp/worker.py:457-463` produces
   everything else for free, and every metric, classification and webapp field follows without a
   single change to the analysis layer.
2. Returning a finished payload dict (`analysis/serialization.py::document_report_to_dict`) bypasses
   the analysis layer and forces you to reproduce dozens of keys that the exporters, the ADB rows
   and `telemetry/record.py::classify_outcome` all read. Only take this route for the case in 5.3,
   and only after reading section 4.

---

## 4. The output contract: what the models supply, what the app computes

Gustavo's rule, verbatim: *the model should not perform any calculations; our app makes all the
calculations based on the definitions already established.* The codebase already enforces this.
`vlm/schema.py` line 4 says "source-level fields only; never a metric".

### 4.1 What the extractor must supply

**Per account** — these are the fields of `analysis/schema.py::Statement`:

`bank`, `account_name`, `account_number`, `period_start`, `period_end`, `beginning_balance`,
`ending_balance`, `currency` (let the platform set `currency_source`), `days_in_period`,
`stated_total_credits`, `stated_total_debits` (positive magnitude), `stated_credit_count`,
`stated_debit_count`, `stated_service_charge` (positive), `stated_interest_paid` (positive),
`stated_nsf_count` (this period, not year to date), `bank_reported_average_balance` with its
verbatim `bank_reported_average_label`, and `stated_daily_balances` as `{date, balance}` pairs.

**Per row** — `analysis/schema.py::Transaction`:

`date` (ISO), `description` (exactly as printed), `amount` (signed at the `Statement` boundary,
negative for money out; magnitude plus `direction` at the page-proposal boundary), `direction` (the
printed **column**, which is not always the sign), `running_balance` when one is printed.

### 4.2 What the extractor must never produce

Average daily balance, NSF count, POS count, total credits or debits, withholding rate, cash flow,
any revenue figure, any lender identification, any classification. All of it is computed by
`analysis/metrics.py` and `analysis/adb.py` from the fields in 4.1.

### 4.3 How the webapp fields Gustavo named actually get filled

| webapp field | how it is produced | what the extractor must get right |
|---|---|---|
| Total Credits / Total Debits | `effective_total_deposits` / `effective_total_withdrawals` prefer the bank's stated totals when they reconcile, else sum the rows | `stated_total_credits`, `stated_total_debits` as printed, and complete rows |
| Transactions | the row list, counted after classification | every row, once, with no duplicates |
| NSFs | `effective_nsf_count = negative_days` — **negative-ending calendar days, not descriptions** | `running_balance` per row and/or `stated_daily_balances`, plus period dates |
| POS count | `pos_count` from description patterns, requires `amount < 0` | verbatim descriptions and correct signs |
| Average daily balance | `analysis/adb.py`, calendar-day printed period | `period_start`, `period_end`, `beginning_balance`, daily balance coverage |
| Withholding rate | lender debits ÷ eligible deposits | verbatim descriptions, correct signs |
| Lenders, insurance, revenue split | alias registries matched on the normalised description | **verbatim descriptions** |
| Ending balance | published only when reconciliation passes | `ending_balance` as printed |

### 4.4 The four fields that decide whether anything is publishable at all

This is the checklist to test against, because each one silently nulls a headline number:

1. **`period_start` and `period_end`** — without them the ADB computation refuses outright.
2. **`beginning_balance`** — a missing printed opening balance makes `opening_balance_matches_statement`
   false, which makes `adb.ok` false, which nulls `average_daily_balance` in the payload.
3. **`ending_balance`** — drives the reconciliation sum check; when reconciliation fails the payload
   nulls `statement.ending_balance`.
4. **`running_balance` per row, or `stated_daily_balances`** — without a daily ledger there are no
   negative days, and without negative days there is **no NSF count**.

A run that captures every transaction but loses the printed opening balance produces a statement
with no ADB and no NSF count. Weight your extraction effort accordingly.

### 4.5 Verbatim descriptions are load-bearing

Lender detection, insurance detection, POS, ATM, cheque and revenue classification are all string
matches over the description, with an OCR-repair normalisation step in front
(`analysis/transaction_classifier.py`, `analysis/classification_registry.py`). A model that tidies,
truncates, translates or re-words a description silently breaks classification. The prompt must
forbid it and section 6 must test for it.

### 4.6 Known gaps worth recording, not silently fixing

- `Transaction` has no page or line provenance. `vlm/assemble.py::CandidateRow` carries `page` and
  `locator`, and both are dropped at the `Statement` boundary. `TransactionClassification.source_page`
  exists but is never populated in production. Carrying provenance through is valuable for audit and
  for the review queue; it is a schema change, so raise it rather than improvising one.
- The multi-account payload branch exists (`analysis/payload_shape.py`, `analysis/serialization.py`)
  but is unreachable today because `analyze_document` publishes one account per document. If the
  visual path can see several accounts in one PDF, that branch becomes reachable and needs its own
  test pass.
- There is no document-level confidence score in the product today. The score this phase introduces
  is new surface; name it explicitly rather than overloading `quality`, `integrity` or the pinned
  `escalated` field.

---

## 5. Web app integration

### 5.1 Force visual OCR already exists — repoint it, do not rebuild it

The button is built end to end already:

| layer | identifier | location |
|---|---|---|
| checkbox | `forceOcrToggle`, label "Force visual OCR" | `webapp/templates/index.html:985-987` |
| form field | `form.append("force_ocr", "1")` | `webapp/static/app.js:1298` |
| server read | `request.form.get("force_ocr") == "1"` | `webapp/app.py:1917` |
| persisted | `Job.force_ocr` | `webapp/jobs.py:43` |
| consumed | `run_job(..., force_ocr, ...)` | `webapp/worker.py:404` |

Today it routes to the old visual OCR rung and still reads the text layer first.
**Gustavo's instruction: when it is ticked, skip the established deterministic approach entirely and
run the two-model path.** So `force_ocr=True` must bypass the native read and go straight to the new
extractor. Keep the old visual rung reachable behind a config flag for comparison runs; do not
delete it while it is the only thing that has ever run in production.

Two things must move with it:
- Add the new extractor to `EXTRACTOR_ORDER` (`ocr/escalation.py:223`) and to
  `WORKER_ENABLED_EXTRACTORS` (`webapp/worker.py:115`, today `frozenset({"visual"})` and the single
  hard stop that keeps Paddle dark), with a trigger constant beside `OPERATOR_FORCED_VISUAL`
  (`ocr/escalation.py:149`) registered in `ADMITTED_TRIGGERS`.
- Add the new capability flag to `webapp/artifact_cache.py::ocr_settings_key`, in the same material
  block as `allow_paddle_ocr`. **If you skip this, a cached deterministic read is served for a
  vision-forced request** and you will chase a ghost for a day.

### 5.2 The automatic fallback

The seam for the deterministic mode already exists: `webapp/worker.py:471-479`, where
`analysis is not None` is exactly the "deterministic parsing validated" predicate, and the code
already falls through to another extractor when it is false.

**Auto mode has no such branch.** `webapp/worker.py:532-539` is a straight line from read to analyse
to result, with no test on failure. Gustavo's flow — parse, and if it cannot be validated run the new
approach — requires adding that branch. That is new work, not a fill-in.

Decide the trigger deliberately and make it configurable:

- The narrow trigger is `analysis is None`, which fires only on an outright parser failure.
- The broad trigger adds `telemetry/record.py::classify_outcome(...) != "validated"`, which also
  catches results that came back but are withheld, most commonly `withheld_adb`. This is closer to
  what "cannot be validated" means to a reader, and it is the one that will actually improve
  outcomes, but it fires far more often and every firing costs GPU minutes.

Start narrow, measure how often the broad trigger would have fired on the existing cold-run cache,
and bring the number to Gustavo rather than picking for him.

### 5.3 When better pixels are not the problem

Two different things make a statement fail, and only one of them is an OCR problem.

1. **The text layer failed** (a scanned PDF, no selectable text). Better page reading fixes it, the
   existing bank-specific parsers then work, and Stage E option 1 gives you every metric for free.
2. **No deterministic parser matched the layout** (`"no deterministic parser matched this
   statement"`). Better text does not help, because the failure is in the parser dispatch, not the
   reading. Handling this case means the visual path must produce structured rows *directly* and a
   generic adapter must build the report without a bank-specific parser.

Case 1 is the shorter path and it already fills every webapp field. Case 2 is genuinely more work
and touches the analysis layer. **Both are in scope** — Gustavo asked for the fallback to handle
statements the current parser cannot validate, and that set includes unmatched layouts. Sequence
them as 3.1a and 3.1b, deliver 3.1a first because it is testable end to end on its own, and do not
quietly drop 3.1b.

### 5.4 Latency: this cannot be a synchronous request

Measured one page at a time on a 32 GB card, Stage A ran at 5.3 pages per minute and Stage B at 3.1.
Both models now sit on one 85 GB card and can be batched, so this will improve, but a ten-page
statement is still minutes, not seconds. The job queue already exists (`webapp/app.py:137-157`, a
single worker thread with one slot) and the front end already polls `/status/<job_id>`. Use them.
Report progress per stage through `store.set_stage`. Do not block an HTTP request on the GPU, and
check whether one queue slot is still the right choice when a job can hold the GPU for minutes.

---

## 6. Validate before this goes anywhere near production

Gustavo's instruction: **do not use a larger corpus.** Use the existing 16 statements and 151 pages,
which are already on the instance under `corpus/` and `pages/` with frozen hashes.

Run these in order and record every number in the ledger:

1. **Reproduce Stage A alone.** Re-run dots.mocr over the frozen renders and confirm 98.5% money
   recall against the stored report. If it differs, stop: something in the environment moved, and
   nothing below this line means anything until it is explained.
2. **Check the renderer.** Run Stage A on `vlm/render.py` output at 1540 px long edge and compare
   against the 300 DPI PNG result. Pick the render settings on that evidence and pin them.
3. **Run the pair in review mode** over the same pages and report: money recall, extra amounts, the
   distribution of row states, and how many pages come back all-`agreed`.
4. **Score the reviewer's corrections.** For every `corrected` row, did the change move toward the
   reference or away from it? This is the measurement that decides whether review mode helps at all,
   and it is the one that can fail. Anchoring is a real risk: a reviewer shown a wrong row may
   confirm it.
5. **Test the four publishable fields** from 4.4 per document: did the pipeline capture period dates,
   opening balance, closing balance and a usable daily ledger?
6. **Test description fidelity** from 4.5: compare extracted descriptions against references
   character for character, and count how often classification would change.
7. **Calibrate the confidence bands** from the row states, and only then write the thresholds down.

Success criteria to beat, all on the frozen corpus: pair money recall at least as good as Stage A
alone; extra amounts no worse than the reviewer alone (21); no page silently shortened; and the
`agreed` band measurably more accurate than the other bands. If the reviewer does not beat the
proposer alone, say so plainly and stop rather than shipping a slower pipeline that is not better.

Sample disagreements against the actual page images using the source-check viewer added in commit
`7203b2c`; customer content stays in the private tree.

---

## 7. Rulings in force. Do not re-decide these.

1. The model proposes, deterministic arithmetic decides. The VLM is never the admission authority.
2. The deterministic reader stays primary wherever it validates. The visual path is residue only,
   plus the explicit operator override.
3. Metrics stay in `analysis/metrics.py` and `analysis/adb.py` under the existing ADB doctrine
   (calendar-day printed period) and currency doctrine (native currency canonical, no FX in the
   analysis layer).
4. Fail closed. Missing, contradictory or unreconciled evidence is quarantined with reasons, never
   partially admitted.
5. Every model input and output is content-addressed and receipted; weights, prompts, schemas and
   gate versions pinned by hash in every receipt.
6. Cache keys depend only on pinned configuration and tree constants. No silent second reading.
7. Model outputs are never overwritten; a correction is a new record beside the original.
8. Pinned revisions only, for both models. Never float to `main`.

---

## 8. Open items for Gustavo. Do not decide these yourself.

### 8.1 The dots.mocr licence — raise this before building on it

The Hugging Face metadata tag says MIT. **The shipped licence file is not MIT.** The snapshot
contains `dots.mocr LICENSE AGREEMENT`, a custom agreement from Xingyin Information Technology
(Shanghai) Co., Ltd. Its grant is broad and explicitly permits commercial use, SaaS and proprietary
incorporation. But it carries an acceptable-use policy, and one clause bears directly on this
product: it prohibits using the model to process or extract sensitive personal data protected under
laws such as GDPR or HIPAA, *"particularly when dealing with documents containing personally
identifiable information (such as ID numbers, health data, financial information, etc.)"*, unless
the licensee has obtained all necessary consents or another lawful basis and has implemented
adequate anonymisation, pseudonymisation or other privacy-enhancing technologies.

Bank statements are exactly that class of document. The clause is conditional rather than an
outright prohibition, and an underwriting applicant submitting their own statements is plausibly a
lawful basis, but that is a legal determination and not mine to make. It also conflicts with the
project's own rule in `LICENSES.md`: *only Apache-2.0, MIT, BSD or equivalent*, under which
MinerU2.5 was already excluded for having additional commercial terms.

**Required before Stage A is built on dots.mocr:** a ruling from Gustavo, with counsel if he wants
one, and a row added to `docs/moneythumb-replacement/phase3/LICENSES.md` recording the real licence
rather than the Hugging Face tag. If the answer is no, section 1.3 has the measured substitutes and
the cost of switching is small. Qwen3.8-27B-NVFP4 is already cleared as Apache-2.0 at the pinned
revision, so the reviewer side is unaffected either way.

### 8.2 Customer documents on a rented GPU

The 16 reference statements are already on the instance. Running **live customer uploads** through a
rented third-party machine is a different question, and the project already has machinery that
treats it as one: the Paddle path is fenced behind
`PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN = "I_AUTHORIZE_CUSTOMER_DOCUMENTS_TO_REMOTE_PADDLE_OCR"`, checked
in `ocr/paddle_config.py::check_remote_authorization`. The visual pair needs the same kind of
explicit, fail-closed authorisation, and Gustavo has to grant it. Build the fence now and leave it
closed.

### 8.3 Three more decisions that are his, not yours

- **Auto-admit or always review.** May a fallback result below a confidence band be published, or
  must it be held for human review? Section 6 gives the evidence; the policy is his.
- **The fallback trigger.** Narrow or broad, per 5.2, once you have measured how often each fires.
- **Where this runs in production.** A rented Vast instance whose address changes is fine for
  evaluation and wrong for production. Dedicated hosting is a cost decision.

---

## 9. Verification commands

On the instance (see the annex for the alias):

```bash
# both servers up, memory split, and what is loaded
bash /workspace/bank-statement-shootout/artifacts/serve_pair.sh status

# start or stop them
bash /workspace/bank-statement-shootout/artifacts/serve_pair.sh start
bash /workspace/bank-statement-shootout/artifacts/serve_pair.sh stop

# confirm the pinned revisions on disk
ls /workspace/bank-statement-shootout/models/hf_home/hub/models--rednote-hilab--dots.mocr/snapshots/
ls /workspace/bank-statement-shootout/models/hf_home/hub/models--nvidia--Qwen3.8-27B-NVFP4/snapshots/

# the frozen corpus, unchanged since the benchmark
python3 -c "import json;m=json.load(open('/workspace/bank-statement-shootout/pages/render-manifest.json'));print(len(m['pages']),'pages',m['dpi'],'DPI',m['renderer'])"
```

From the repository root, before changing anything:

```bash
git log --oneline -1
git status --short
python -c "import vlm.schema as s; print('page proposal schema', s.SCHEMA_VERSION)"
python -c "import vlm.gate as g; print('gate', g.GATE_VERSION)"
python -c "import vlm.prompts as p; print('prompt', p.PROMPT_VERSION)"
python -c "import webapp.artifact_cache as c; print('ocr stage', c.OCR_STAGE_VERSION, 'extraction schema', c.EXTRACTION_SCHEMA_VERSION)"
```

Tunnels, from Gustavo's computer:

```bash
ssh vast-shootout3 -L 127.0.0.1:18013:127.0.0.1:18013   # Stage A
ssh vast-shootout3 -L 127.0.0.1:18022:127.0.0.1:18022   # Stage B
```

---

## 10. The shortest path forward

1. Put the dots.mocr licence question (8.1) in front of Gustavo **today**. Everything in Stage A
   depends on the answer and the substitutes are measured and ready.
2. Start both servers and reproduce Stage A on the frozen corpus. Do not write new code until the
   98.5% number comes back.
3. Settle the renderer question (6.2) and pin the settings.
4. Build Stage B review mode against `vlm/schema.py`, then run step 6.3 and 6.4. If review mode does
   not beat the proposer alone, report that and stop.
5. Build Stage C and wire Stage D to the existing gate.
6. Wire 3.1a into the web app: repoint Force visual OCR, add the auto-mode fallback branch behind
   the narrow trigger, partition the cache key, keep it a queued job.
7. Measure the broad trigger on the cold-run cache and bring the number to Gustavo.
8. Then, and only then, start 3.1b for layouts no deterministic parser claims.

Keep the ledger at `C:\Users\GustavoPrietodePaula\extraction-shootout\RUN_STATE.md` current: one
entry per run, with the numbers and what they mean. The next agent after you will need it as much as
you needed this.
