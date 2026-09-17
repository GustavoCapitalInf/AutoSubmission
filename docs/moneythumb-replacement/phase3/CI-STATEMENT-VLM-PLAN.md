# A Capital Infusion bank-statement model: forking a vision-language model under a deterministic gate

Status: PROPOSAL (root, 2026-09-17). Phase 3 and Qwen are excluded by the current rulings; nothing
here runs until Gustavo unlocks it (section 8). Working name below is a placeholder.

## 1. What we are building

A self-hosted vision-language model (VLM), fine-tuned on bank statements, whose only job is to turn
statement pages into structured proposals: transactions (date, description, amount, direction,
running balance, section), account and period metadata, currency, and page roles. It never computes
a financial metric and it never admits its own output. A deterministic gate (running-balance
reconciliation, date monotonicity, period totals, duplicate detection, the ADB and currency
doctrines) decides what enters the ledger. The existing deterministic reader stays the primary path
wherever it validates; the model handles the residue and serves as a second opinion.

Why this shape: bank statements carry their own truth test (the balances must reconcile), which is
exactly what makes a hallucination-prone model safe to use. Few document domains offer that.

## 2. Assets we already have (this is why it is feasible)

* 3,380 documents; 2,625 validated by the deterministic reader with balance-reconciled rows: silver
  labels for free.
* 91 known layout families and a failure taxonomy of the 755 unresolved documents (most are layout
  problems on native text; about a fifth are scans).
* The evaluation harness that any ML program needs and rarely has: sealed holdout, adjudication
  store, truth table, false-accept discipline, privacy boundary, retention attestation.
* An approved rented GPU (RTX 5090, 32 GB) and a pinned self-hosting path (vLLM already on the
  instance image); a separate machine designated for the Unlimited OCR work.
* Canonical geometry and word boxes from PyMuPDF for native pages (exact and free), usable as extra
  input to the model and as a cross-check.

## 3. Plan

### Phase 3.0 — Decision and boundary (1 week)
* Rulings: unlock Phase 3; define the training-data boundary (customer pages may be used for
  training only on infrastructure we control or rent under the existing remote_paid rules; no
  third-party API; encrypted transfer; retention attestation per job); pick the license-clean base
  model per size (Qwen2.5-VL 7B is Apache-2.0; check larger sizes and PaddleOCR-VL).
* Success criteria, fixed now: coverage on the residue at zero false accepts on the sealed holdout;
  agreement with the validated reader on the 2,625; cost and latency per statement.
* Close Phase 2.3 cheaply: record the stage-6 closure, write the v6 comparison report from the six
  closed steps with the double-read caveat, and either drop the orientation family or run it later
  with the lighter process. Do not build more provenance apparatus.

### Phase 3.1 — Ceiling measurement with an off-the-shelf model (2 weeks)
* Serve Qwen2.5-VL-7B (and PaddleOCR-VL as a comparison) with vLLM on the rented GPU.
* Prompted extraction to a strict JSON schema; page-by-page; multi-page stitching by rules.
* The gate: reconcile running balances, dates, totals; reject or quarantine on any failure.
* Run on the 755 residue and the control sample; measure gate-pass rate, false accepts on the
  holdout, per-layout-family behaviour, latency and cost. This tells us the ceiling before any
  training money is spent and produces the first hard-case list.

### Phase 3.2 — Data engine (2 to 3 weeks, in parallel)
* Silver labels: export reconciled rows from the 2,625 as page-aligned targets.
* Synthetic statements: a ledger simulator plus renderers for the layout families and their
  variants (fonts, column orders, multi-account, continuation lines, foreign currency, scans with
  rotation, skew, noise, JPEG artefacts). Perfect labels, unlimited volume, no privacy exposure.
* Hard cases: residue pages adjudicated into the sealed store; the holdout stays untouched.

### Phase 3.3 — Fine-tune (2 weeks)
* LoRA/QLoRA on the 7B model on the 5090 (hours per run); curriculum synthetic → silver real → hard
  cases; strict JSON outputs; a page-role/classification output (statement page, summary page,
  cheque image, not a statement).
* No metric computation in the model. No full fine-tune; no model above what one rented GPU serves.

### Phase 3.4 — Evaluation and admission rules (1 to 2 weeks)
* Same harness as today: sealed holdout, adjudication, zero false accepts as the bar.
* Admission rule: deterministic reader first where it validates; model proposals only through the
  gate; agreement thresholds per layout family; everything else to review.
* Report per family and per source, with the same honesty about unqualified and refused documents.

### Phase 3.5 — Productionize (2 weeks)
* Inference service on the rented GPU, page-level caching, batch mode, per-statement cost and
  latency budget, drift and gate-failure monitoring, monthly retraining with a synthetic refresh.

## 4. Efficiency (the concern is fair)

The inefficiency of the last week came from bespoke provenance instruments, not from the science.
This program keeps the discipline where it protects the business (privacy boundary, sealed holdout,
the gate, hostile review of anything that admits data into the ledger) and drops the rest: one
generic experiment runner with data-driven receipts, direct test runs for helpers, reviews batched
per phase, and a half-day time box per interruption. Prompt-first before any training keeps the
first two weeks cheap and reversible.

## 5. Risks and mitigations

* Confident wrong digits: the gate; never admit an unreconciled row; show the page crop on review.
* Multi-page continuity and balance carry-over: page-level proposals stitched by rules.
* Overfitting to our families: synthetic diversity, the holdout, per-family reporting.
* Licensing: Apache-2.0 sizes only unless ruled otherwise.
* Data boundary during training: more pages leave the machine than in the Paddle wave; same rules,
  explicit attestation per training job, or train on the separate machine.
* Drift as banks change layouts: monthly retrain; synthetic generator updated from new families.

## 6. Timeline and cost

Ceiling measurement in about two weeks; a gated production candidate in eight to ten weeks. GPU
cost is one rented card for a few hours per training run plus inference at roughly a second or two
per page. Engineering cost is dominated by the data engine and the gate, both of which outlive any
model.

## 7. What stays exactly as it is

The ADB and currency doctrines, the holdout cage, the privacy boundary, the deterministic reader as
primary, the truth table and adjudication store, and the rule that nothing is admitted without a
reconciled deterministic check.

## 8. Rulings needed from Gustavo

1. Unlock Phase 3 with this plan (or an amended one).
2. Training-data boundary: which infrastructure, what retention, what attestation.
3. Base model and license policy.
4. What to do with the rest of Phase 2.3: close with the v6 report and defer the orientation family,
   or finish it under the lighter process.
