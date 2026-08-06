# Current Architecture

Phase 1 audit — MoneyThumb Replacement Initiative.
Author: Ocean (Lead Architect). Date: 2026-08-06.
Sources: full-repository audit (five subsystem audits, file:line evidence throughout).

---

## 1. System overview

The platform converts a bank-statement PDF into an audited underwriting report. The
macro-architecture is deliberately split so that **no LLM ever computes a number**:
LLMs and OCR models only transcribe; every financial figure is derived by
deterministic Python and gated by reconciliation before it is trusted.

```
PDF bytes
  ↓  ocr/pipeline.py  (native-text preflight → tesseract [webapp only] → visual OCR)
Markdown (StatementMarkdown, pages joined by "--- Page N ---")
  ↓  analysis/pipeline.py :: analyze_markdown
Extraction
  ├─ deterministic: 43-parser or-chain (analysis/<bank>.py), self-detecting, first match wins
  └─ fallback: Gemini structured output (analysis/extract.py, gemini-3.5-flash-lite)
Statement (analysis/schema.py — single-account normalized ledger)
  ↓  normalize_statement + apply_statement_repairs (year boundaries, 8 bank repairs)
Reconciliation (analysis/reconcile.py — sum check, continuity, summary identity, coverage)
  ↓  (failure on the Gemini path → escalate to gemini-3.5-flash; deterministic path never escalates)
Classification (analysis/transaction_classifier.py — 16 states + 3-way revenue state per row)
  ↓
Financial calculations (analysis/metrics.py + analysis/adb.py — Decimal ADB, fail-closed)
  ↓
Quality & integrity gates (assess_quality, assess_document_integrity in analysis/pipeline.py)
  ↓
Detection (analysis/detect.py — funders, potential lenders, insurance, recurring debits)
  ↓
Report → serialization (analysis/serialization.py — the single JSON contract)
  ↓
API / Dashboard (webapp/app.py + static/app.js)  and  CLI (analyze.py, batch.py)
  ↓
Exports (md / html / json / csv / xlsx per statement; json / csv / xlsx per package)
```

---

## 2. Pipeline detail

### 2.1 OCR pipeline (`ocr/`)

Entry: `ocr/pipeline.py:15 parse_statement(pdf_bytes, ...)`.

1. **Native-text preflight** (unless `force_ocr`), fixed priority order in
   `ocr/pipeline.py:38-52`:
   - `parse_native_navy_federal` — PyMuPDF geometry row reconstruction; emits structured
     rows as HTML-comment side channels (`NFCU_TX|...`, `SOURCE_POSTING_DATE|...`).
   - `parse_native_td_canada`, `parse_native_wells_fargo` (hardcoded pixel columns,
     `ocr/native_text.py:303-382`), `parse_native_desjardins`.
   - `parse_native_pdf_text` — generic gate: ≥500 chars total AND ≥half the pages ≥200 chars.
2. **Local Tesseract** — `ocr/local_tesseract.py` (200 DPI, `--psm 6`, ≥200-char gate).
   Only invoked by `webapp/worker.py:33`; NOT part of `ocr/pipeline.py` or `parse.py`.
3. **Visual OCR** — rasterize at 300 DPI (`ocr/rasterize.py`), page-by-page requests to
   `baidu/Unlimited-OCR` over an OpenAI-compatible endpoint (`ocr/ocr_client.py:399-450`,
   prompt `"Free OCR."`, 4096 max tokens/page, default 1 worker, ~23 s/page locally).
   Adaptive re-OCR: orphan amount-table signature → 250 DPI retry; TD QR refusal →
   masked-corner render variants.
4. **Post-processing** (`ocr_client.py:389-396`): strip `<|det|>` tags/refusals, collapse
   repetition degeneration, split fused headers, repair fused amount tables (Chase),
   fix amount-column bleed (BofA), inline cropped check images as base64.

**Provider abstraction: none.** The wire format is OpenAI-compatible, but the content
contract (det-tag grammar, refusal regexes, failure-mode repairs, prompt) is specific to
Unlimited-OCR. Swapping models means rewriting the postprocess layer.

**Caching: none.** No document-hash cache; identical bytes re-pay full OCR + LLM cost on
every run. SHA-256 hashing exists only in audit scripts and tests.

### 2.2 Extraction pipeline (`analysis/pipeline.py`, `analysis/extract.py`)

- **Dispatch** — no registry. `_deterministic_statement` (`pipeline.py:357-402`) is a
  hand-ordered short-circuit `or`-chain of 43 parser calls; each parser self-detects via
  substring sniffing and returns `Statement | None`. Order is load-bearing and untested.
- **Self-invalidation** — many parsers return None when their line items fail to tie to
  the stated summary (bluevine, wilson_muir, truist, community_section,
  scanned_small_bank). Safe-by-default, but it means an unmatched same-bank statement
  silently costs a Gemini call.
- **Gemini fallback** — whole-markdown single prompt, Pydantic `response_schema=Statement`,
  temperature 0, `gemini-3.5-flash-lite`; escalation to `gemini-3.5-flash` only when
  reconciliation fails AND the summary identity does not hold (`pipeline.py:424-444`).
  `parse_mode="deterministic"` raises instead of falling back.
- **Repairs** — `normalize_statement` (drops balance rows misread as transactions) then
  `apply_statement_repairs`: 8 bank-specific repairs (`analysis/bank_repairs.py`) plus
  `assign_transaction_years` (year-boundary correction, `analysis/dates.py:277`).

### 2.3 Parser framework (`analysis/<bank>.py`, ~43 modules, ~8.5–9k LOC)

- No base class, no shared interface, no priority metadata. Adding a bank = new module +
  import + insertion at the right position in the or-chain.
- **Duplication (measured):** `_money` defined 38 times; 14 modules import the private
  `_parse_money` from `td_can.py` (a Canadian parser is the de-facto shared money
  utility); `_iso` date helpers in 17 modules; check-section parsing in 12; HTML-table
  helpers in 3; section-chunking regexes re-invented per parser.
- **Single-account schema** — multi-account statements are handled by picking one account
  (Truist: first checking block; Navy Federal: isolates Business Checking).
- **Sign inference by keyword lists** for Canadian banks (rbc, td_can) including named
  merchants; `rbc.py:251-274` brute-forces sign assignment (2^16) per balance segment.
- **Corpus overfitting** — statement-specific hardcodes exist (see RISK_REGISTER R-1):
  literal dates/check numbers/amount deltas (`scanned_small_bank.py:300-321`,
  `bank_repairs.py:115-134`), literal customer names (`community_section.py:29`,
  `scanned_small_bank.py:214-216, 338`), hardcoded years (`wells.py:20-22`,
  `rbc.py:288-291`), corpus mojibake baked into regexes (`rbc.py:246`).

### 2.4 Reconciliation pipeline (`analysis/reconcile.py`)

Run before any metric. Four checks:
1. Sum check: `beginning + Σ signed amounts == ending` (±$0.01).
2. Running-balance continuity with same-day grouping (counts breaks).
3. Bank-summary self-identity: `beginning + credits − debits (± service charge ± interest)
   == ending` (±$1.00; minimum-residual of 4 variants). The backbone check for
   summary-only/image statements.
4. Credit/debit line-item coverage vs stated totals (0.98–1.02 band) with
   settlement-reversal netting.

Never raises; emits `ReconResult` with full issue list. Downstream consumes
`trust_stated_summary` / `trust_running_balances`.

### 2.5 Ledger / financial calculations (`analysis/adb.py`, `analysis/metrics.py`)

- **ADB** — Decimal math, half-up cent rounding. Daily ledger reconstructed from an
  opening balance (source recorded: stated → derived_from_closing →
  first_printed_balance) + signed postings, carry-forward on quiet days, bank-printed
  daily snapshots override reconstruction. A 12+-check validation suite must fully pass
  (`ok=True`) or the ADB is withheld; the bank-printed average is comparison evidence
  only, never a fallback value. `posting_dates_cover_source` proves against the raw
  markdown that the parser did not collapse posting dates. Fully auditable via
  `debug_report()`.
- **Metrics** — deposits/withdrawals (line-item and bank-stated "effective" variants with
  source labels), NSF (row-count wins over stated count), negative days, POS/ATM/ACH/
  check/loan channel counts (settled activity only), three-state revenue totals with a
  conservation identity (every posted credit in exactly one state or `ValueError`),
  lender/insurance rollups from contribution flags, cash flow, withholding rate with a
  configurable denominator (`WITHHOLDING_DENOMINATOR_MODE`: legacy eligible deposits
  [default] or verified revenue).

### 2.6 Revenue pipeline (`analysis/transaction_classifier.py`, `analysis/revenue.py`,
`analysis/classification_registry.py`)

- Every posted credit gets exactly one of `verified_revenue | unverified_deposit |
  non_revenue`, decided by an 11-step precedence ladder (reversals → insurance → lender
  funding → transfers/loan proceeds/owner contributions → operating-source alias with
  context → generic settlement descriptors → generic deposits → catch-all unverified).
- Statement-level second passes: duplicate detection (requires identical printed running
  balance as proof), reversal-pair matching (≤14-day window, exact amount, shared
  tokens), operating-source recurrence upgrades (≥3, or ≥2 on business accounts).
- Registry: 67 confirmed lenders, 3 potential lenders, 32 operating revenue sources,
  23 insurers, 8 lease providers; normalized token-boundary matching, longest alias wins;
  deliberate OCR-error alias variants. Contract documented in
  `docs/transaction-classification.md` (all counterparty knowledge in the registry; no
  description checks in parsers/metrics/API/frontend).
- Full explainability per row: match method, matched alias/rule, confidence, reason,
  context signals, source location, related transaction, review state.
- Analyst review loop: only initially-unverified rows are reviewable
  (confirm/reject/reset); serialized views rebuilt from the row records.

### 2.7 Lender pipeline (`analysis/detect.py`, `analysis/lenders.py`)

- Confirmed-lender debits at 0.99 confidence via registry; potential lenders at 0.82;
  explicit loan-repayment descriptors at 0.78 (review-required).
- Recurring-debit detection: groups unknown-entity debits by (canonical entity, exact
  amount), requires ≥3 occurrences AND daily/weekly cadence statistics; result is only
  ever `potential_lender` (recurrence alone is never lender evidence).
- Aggregated `FunderMatch` / `RecurringDebit` / `DetectionResult` with evidence
  transactions and per-funder withholding exposure.

### 2.8 Quality & integrity (`analysis/pipeline.py:150-354`)

- `assess_quality`: `transaction_level` (approved) / `summary_aggregate` (summary_only) /
  `needs_review` (manual review). Chase transaction exports are always review.
- `assess_document_integrity`: summary-math inconsistency, ledger-sum mismatch,
  continuity breaks, coverage mismatch, not-a-formal-statement, conflicting summaries
  (BMO-specific check embedded in the orchestrator), missing declared pages
  ("Page N of M" scan). `possible_document_issue` demotes quality to manual review.

### 2.9 API / Dashboard pipeline (`webapp/`)

- Single Flask app (`webapp/app.py`, 1157 lines), 14 routes, no blueprints, no auth,
  no versioning; 5 routes are dead remnants of the old 4-panel viewer.
- **Job model**: in-memory dict + lock (`webapp/jobs.py`), unbounded module-level deque,
  ONE daemon worker thread → strict serial processing; no persistence, no idempotency,
  no timeouts; everything (including PDF bytes) resident in RAM forever; all state lost
  on restart, including analyst revenue-review decisions.
- **Worker ladder** (`webapp/worker.py`): deterministic native parsers → local tesseract
  → remote visual OCR, with a visual-OCR retry when deterministic analysis fails. The
  preflight order is duplicated (and already drifted) from `ocr/pipeline.py`.
- **Dashboard** (`static/app.js`, 2038 lines): underwriting metric grid, evidence tables,
  filterable paginated ledger with inline revenue review, package view with per-statement
  drill-down. Weaknesses: no source-document viewer wired in, client-side regex fallback
  for routing/account numbers, hardcoded "confidence" heuristic, decorative dead UI.
- **Package analysis** (`_package_analysis`, `app.py:238-915`, ~680 lines in the route
  module): per-document rows, totals (~60 keys), merged funders, flattened ledger with
  source provenance, package decision, days-weighted Decimal package ADB over validated
  statements only. Packages are ephemeral (id list in the browser); months are counted
  as `max(1, completed_count)`; no account-coherence or duplicate-statement checks.

### 2.10 Export pipeline

- Per statement: `md`, `html`, `json` (full `report_to_dict`), `csv` (long
  `section,field,value` format; ADB exploded per day), `xlsx` (hand-rolled OOXML, all
  inline strings).
- Per package: `json` (full payload), `csv`/`xlsx` (long format, OMITS the transaction
  ledger and monthly rows).
- CLI: `analyze.py` (human report + `--json`), `batch.py` (47-column triage CSV),
  `parse.py` (markdown/html).
- Fail-closed serialization: rejected ADB values and unreconciled ending balances are
  nulled at the export boundary (`analysis/serialization.py:102-141`).

---

## 3. Test & validation infrastructure

- **523 tests** (the "323" figure in PROJECT_GOAL.md is stale), 4.2 s collection; corpus
  is **109 PDFs** across 44 banks/parsers (105 is stale). 106 PASS / 3 WITHHELD
  (Ace/Farmers & Merchants, BMO, IBC — proven source-document defects, correctly
  fail-closed).
- Strong suites: ADB property/spec tests (45), per-bank inline-snippet regressions (97),
  hash-pinned full-pipeline fixtures for the 4 newest statements, snapshot-locked audit
  CSVs, export-leak prevention tests, frontend-binding string assertions.
- **The corpus-wide guarantee is manual**: `adb_forensic_audit.py` and
  `balance_forensic_audit.py` (independent Decimal oracles that never import production
  math) must be run by hand; pytest only pins their recorded CSVs and the PDF hashes. A
  regression on ~98 of 109 corpus PDFs would not fail the default test run.
- No automated MoneyThumb comparison exists. No performance/cost regression gate.
- Latent fixture bug: `conftest.py` `samples_dir` points to `BankStatements` (no space);
  the real folder is `Bank Statements`. Only the deselected live test uses it.

---

## 4. Architectural strengths

1. **LLM-transcribes / Python-computes separation** — the foundation of auditability.
2. **Reconciliation before trust** — metrics consume explicit trust flags; escalation is
   reconciliation-gated (an elegant cost lever).
3. **Fail-closed discipline end-to-end** — ADB withheld unless 12+ checks pass; rejected
   values nulled at serialization; conservation identities raise on violation; withheld
   statements proven (by independent re-derivation) to be source defects.
4. **Single classification record per row** consumed by metrics, detection,
   serialization, and review — no double counting, full explainability.
5. **Self-invalidating deterministic parsers** — tie out or step aside.
6. **Sophisticated correctness machinery** — year-boundary correction, source
   posting-date proof, duplicate detection requiring balance evidence.
7. **Independent audit oracles** with machine-readable, hash-pinned results.

## 5. Architectural weaknesses

1. **No parser platform** — 43-way ordered or-chain, no registry/base class, ~9k LOC with
   massive helper duplication anchored on `td_can._parse_money`.
2. **Corpus overfitting** — literal customer names, dates, check numbers, exact deltas,
   and mojibake in parsers; these violate the project's own engineering principles.
3. **Single-account schema** — multi-account documents are silently reduced to one
   account; packages exist only in the webapp layer with no persistence or coherence
   checks.
4. **No caching/idempotency** — full OCR+LLM cost re-paid for identical bytes.
5. **Escalation blind spot** — deterministic parses are never cross-checked by a second
   extractor even when reconciliation fails.
6. **Provider-coupled OCR** — postprocess layer welded to Unlimited-OCR failure modes;
   tesseract a webapp-only bolt-on; preflight logic duplicated in two places.
7. **Serving layer is a prototype** — unauthenticated, in-memory, single-threaded Flask
   dev server in debug mode; no logging, limits, retention, or persistence.
8. **Float money + inconsistent tolerances** (±$0.01 vs ±$1.00 vs 98–102%) without a
   documented calibration rationale.
9. **Orchestrator contamination** — bank-specific logic (BMO contradiction check, Chase
   export sentinel, ordered repair list) inside `analysis/pipeline.py`.
10. **Stringly-typed side channels** (`NFCU_TX|`, `WF_TX|`, `SOURCE_POSTING_DATE|`)
    smuggled through markdown comments with no schema or versioning.
