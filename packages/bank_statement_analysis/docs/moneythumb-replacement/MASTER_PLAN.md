# Master Plan — MoneyThumb Replacement

Phase 1 deliverable. Author: Ocean (Lead Architect). Date: 2026-08-06.
Companion documents: CURRENT_ARCHITECTURE.md · PARITY_MATRIX.md · RISK_REGISTER.md ·
PRODUCTION_GAPS.md · FIELD_MAPPING.md · TASK_BOARD.md · MERGE_PLAN.md.

---

## 1. Thesis

The audit confirms the platform is a **validated analysis engine with a prototype
shell**. The financial core (reconciliation, ADB, revenue conservation, evidence-linked
classification) already exceeds MoneyThumb in rigor, explainability, and fail-closed
behavior — and it costs ~$0 marginal vs ~$3/statement. That core is the asset. Nothing
in this plan modifies its mathematics.

What stands between today and "production-grade replacement" is not the math; it is:
1. **Generality** — coverage is corpus-shaped; unknown banks depend on a Gemini fallback
   the production path must not require.
2. **The platform shell** — persistence, auth, concurrency, caching, audit logging.
3. **Structure** — multi-account documents, packages as durable entities with coherence
   checks.
4. **Continuous proof** — corpus audits and MoneyThumb comparison must run automatically,
   not by memory.
5. **Integrity hygiene** — statement-specific hardcodes inside parsers must be
   eliminated; they contradict our own engineering principles and weaken the meaning of
   "validated."

Guiding rule for every workstream: **prefer changes that solve categories of problems**
(a parser platform, a caching layer, a benchmark harness) over statement-specific or
bank-specific fixes.

## 2. Architecture decisions (Step 5 rulings)

These are the platform-level introductions the audit justifies. Each solves an entire
category of problems; anything narrower was rejected.

| ID | Decision | Ruling & rationale |
|----|----------|--------------------|
| AD-1 | **Parser platform** (registry + shared utilities + conformance harness) | APPROVED. Replace the 43-way or-chain with a `Parser` protocol, a registry with detection scoring, and shared `analysis/money.py` / `analysis/dates` / table utilities. Eliminates 38 `_money` clones and the `td_can` dependency inversion; makes parser order testable. Parsers keep their exact extraction logic — this is packaging, not rewriting; the corpus audit must be byte-identical before/after. |
| AD-2 | **Canonical evidence model** (schema v2) | APPROVED. `Document → accounts[] → Statement` container; account type, holder identity, check number, page/source provenance per transaction; integer-cents or Decimal money; explicit `direction`-vs-sign validator. Single-account `Statement` remains as the inner unit so ALL existing math is untouched; v2 wraps, never replaces. |
| AD-3 | **Package as a first-class entity** | APPROVED. Durable package record (id, documents, caller reference), month-map semantics (gaps, overlaps, duplicates via content hash), account-coherence checks, package math moved out of the Flask route into `analysis/package.py`. Fixes R-15/R-26/R-30 and closes PARITY #13/#14/#26 groundwork. |
| AD-4 | **Document-hash extraction caching** | APPROVED. Content-addressed store: sha256(pdf) → OCR markdown → extraction → report artifacts. Kills repeated OCR/LLM cost (R-11 economics, G7), gives idempotent uploads, and powers duplicate detection. |
| AD-5 | **Provider-neutral OCR interface** | APPROVED, staged. An `OcrProvider` interface with model-specific postprocess plugins; tesseract becomes a first-class member of `ocr/pipeline.py` (single preflight ladder — deletes the drifted duplicate in `webapp/worker.py`). Full second-provider support is P2; the interface extraction is P1 because the worker/pipeline drift is already a correctness hazard. |
| AD-6 | **Benchmark & comparison automation** | APPROVED. (a) CI job running the forensic audit oracles on every change (R-7); (b) a MoneyThumb comparison harness over `moneythumbResults/` inputs producing per-field diffs with discrepancy classification (our defect / MT defect / definition difference / source contradiction / insufficient evidence). Prerequisite for Milestone 2 (500–1,000 statement parallel validation). |
| AD-7 | **Generic statement understanding** | APPROVED as P2 investigation, not P1 build. The honest unknown-bank story needs a layout-agnostic table/column model (candidate: geometry-based column detection over native text + OCR grids) that feeds the SAME reconciliation gate. Until it exists, unknown banks route to Gemini (flagged, telemetered) or manual review. Do not attempt to leapfrog MoneyThumb's thousands of layouts by hand-writing parser #44…#400. |
| AD-8 | **Performance & fallback telemetry** | APPROVED. Record per-statement: path taken (native/tesseract/visual), parser used or fallback reason, timings, model calls, cost. Without this we cannot measure deterministic coverage decay (R-17) or the cost claims in PROJECT_GOAL. |
| AD-9 | Rewrite the financial core / adopt MT field schema wholesale | REJECTED. The core is validated and superior; MT's schema exhibits defects we must not copy (see FIELD_MAPPING §7, RISK_REGISTER benchmark notes). |

## 3. Roadmap

Ordering principle: P0 = release blockers for Milestone 1 (controlled in-house use with
MoneyThumb fallback); P1 = required before Milestone 3 (limited replacement); P2 =
required for Milestone 4–5 (primary platform / full replacement); P3 = enhancements.

### P0 — Release blockers

| # | Item | Closes | Notes |
|---|------|--------|-------|
| P0-1 | **CI enforcement of corpus audits** — forensic ADB + balance oracles run on every PR; hash-pinned corpus; red on any drift | R-7, G4 | Cheapest, highest-leverage integrity win. Do first; it protects every other workstream in this plan. |
| P0-2 | **Purge statement-specific hardcodes** — remove/generalize literal names, dates, check numbers, exact deltas, mojibake regexes; each removal must keep the corpus audit green or convert the statement to an honest review case | R-1, R-6, G3 | If a statement only passes because of a memorized constant, it was never validated — fail it closed instead. |
| P0-3 | **Persistence + job durability** — durable job/result store (SQLite/Postgres), queue survives restart, analyst review decisions recorded with actor/timestamp | R-20, R-21 (partial), G2 | Precondition for anyone trusting the tool with real deals. |
| P0-4 | **Serving-layer hardening minimum** — kill debug mode, real WSGI server, auth (even single-tenant API key), server-side upload limits, masked account numbers in exports, filename/CSV-injection fixes | R-18, R-19, R-23, R-24, R-25 | Scoped to "safe on a company network," not full multi-tenancy. |
| P0-5 | **Document-hash cache + duplicate detection** | AD-4, R-26, G7 (partial) | Also unblocks cheap re-analysis during all later development. |
| P0-6 | **MoneyThumb comparison harness v1** — run our pipeline on the 6 benchmark inputs, diff against `moneythumbResults/`, emit classified discrepancy report | AD-6, G9 | Uses the FIELD_MAPPING verdicts as the diff dictionary. |

### P1 — Critical improvements

| # | Item | Closes |
|---|------|--------|
| P1-1 | **Parser platform migration** — registry, shared money/date/table utils, conformance tests per parser, byte-identical corpus proof | AD-1, R-13, R-28 |
| P1-2 | **Schema v2 (canonical evidence model)** — multi-account container, account type, holder identity, check numbers, provenance; adapters keep existing math untouched | AD-2, R-14, G5 |
| P1-3 | **Package entity + coherence** — durable packages, month-map (gaps/overlaps/duplicates), account matching, package math extracted from the Flask route | AD-3, R-15, R-30, G5 |
| P1-4 | **Unified OCR preflight + provider interface extraction** — single ladder in `ocr/pipeline.py`, worker consumes it; truncation detection (finish_reason) flagged | AD-5, R-11, R-16 (partial), R-28 |
| P1-5 | **Concurrency + async jobs** — worker pool, per-job timeouts, bounded queue, completion webhooks/polling contract | R-22, G7 |
| P1-6 | **Underwriting derivations** — true-balance daily series, DTI/DSCR/withhold%, monthly MCA cadence rollup, monthly cash flows, large/recurring transaction views | G6, PARITY #11/#25, FIELD_MAPPING ADOPT/DERIVE list |
| P1-7 | **Telemetry** — path/parser/fallback/cost/timing per statement; deterministic-coverage dashboard | AD-8, R-17 |
| P1-8 | **Escalation cross-check for deterministic parses** — when a deterministic parse fails reconciliation, run the LLM extractor as a second opinion (comparison only, never silent adoption) | R-2, R-10 |
| P1-9 | **Export ergonomics** — flat typed transaction CSV/XLSX (statement + package), typed XLSX cells, review-decision export artifact | G8, PARITY #19 |

### P2 — Important improvements

| # | Item | Closes |
|---|------|--------|
| P2-1 | **Generic statement understanding investigation → build** — layout-agnostic column/table model behind the reconciliation gate; target: unknown-bank statements pass or fail closed without Gemini | AD-7, R-12, G1 |
| P2-2 | **Document forensics + composite tamper score** — PDF producer/metadata/font/object inspection joined with existing arithmetic flags; human-readable contributing factors | G6, PARITY #16, FIELD_MAPPING §3 |
| P2-3 | **Cross-account transfer matching** within packages | PARITY #14 |
| P2-4 | **Multi-tenancy, audit logging (full), retention/deletion, encryption at rest** | G2 remainder, R-21, R-24 |
| P2-5 | **Registry expansion program** — MCA funders, processors, factoring/healthcare/debt-collector categories; alias contribution workflow with fixture requirements | R-6 hygiene, FIELD_MAPPING §6 |
| P2-6 | **FDIC enrichment**; account-holder identity extraction hardening | FIELD_MAPPING §3 |
| P2-7 | **Corpus expansion + per-bank accuracy tracking** — top-US-bank regression corpus, layout fingerprints, accuracy by bank/field | PROJECT_GOAL "Format Certification", G1 |
| P2-8 | **Versioned public API** — stable schemas, idempotent submission, error taxonomy | G2, PARITY #18 |
| P2-9 | **Threshold calibration record** — document/justify every tolerance and cadence constant against the corpus; make them config with provenance | R-5 |

### P3 — Future enhancements

Scanned-throughput optimization (batching, better GPU utilization, alternate OCR
models via AD-5); configurable underwriting scorecards and approval rules; multi-
applicant summaries; PDF report export; dashboard source-document viewer using the
existing (currently dead) page-image endpoints; browser-level frontend tests replacing
string assertions; OD-balance variant; web-presence enrichment (only if business asks).

## 4. What is explicitly protected (do-not-touch list)

Per the preservation mandate, the following are frozen absent a mathematically proven
defect, and any PR touching them requires Ocean review plus a green forensic audit:

- `analysis/adb.py` — algorithm and validation suite semantics
- `analysis/reconcile.py` — check definitions and fail-closed behavior
- `analysis/metrics.py` — metric definitions and conservation identities
- `analysis/transaction_classifier.py` precedence order and evidence contract
- `analysis/serialization.py` fail-closed nulling rules
- The 3 withheld statements stay withheld (proven source defects; see
  `docs/adb-withheld-second-pass.md`)
- The withholding-denominator configuration contract

## 5. Milestone gates

| Milestone (PROJECT_GOAL) | Gate — all must be true |
|---|---|
| M1 Controlled use | P0 complete; corpus audit green in CI; comparison harness reporting on the 6 benchmark sets |
| M2 Parallel validation | P1-1…P1-5, P1-7 complete; 500–1,000 real statements through the comparison harness; discrepancies classified |
| M3 Limited replacement | P1 complete; per-bank accuracy thresholds met on certified layouts; review-rate within budget |
| M4 Primary platform | P2-1 (unknown-bank story), P2-4, P2-7, P2-8 complete |
| M5 Full replacement | P2 complete; fraud controls (P2-2) operational; MoneyThumb dependency removed |

## 6. Success definition

We do not ship "a copy of MoneyThumb." We ship a platform that: extracts complete
evidence-linked ledgers (which MT no longer even exports), reconciles and fails closed
where MT demonstrably does not, explains every number, handles packages and
multi-account documents at least as well as MT, costs ~$0 marginal, and proves its own
accuracy continuously against both an audited corpus and MT itself — until the day the
comparison is no longer worth running.
