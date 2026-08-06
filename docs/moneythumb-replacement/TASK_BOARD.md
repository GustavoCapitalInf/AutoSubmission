# Task Board

Phase 1 deliverable. Author: Ocean. Date: 2026-08-06.
Work is grouped by **owning subsystem agent** (see MERGE_PLAN.md for boundaries and
ordering). Every task lists its MASTER_PLAN item, priority, and acceptance criteria.
Status values: TODO / IN-PROGRESS / REVIEW (Ocean) / DONE.

Standing acceptance criteria for EVERY task:
- Full pytest suite green (currently 523 tests).
- Forensic corpus audits byte-identical (or intentional deltas documented + approved).
- No new statement-specific constants; counterparty knowledge only via the registry.
- No changes to protected financial modules (MASTER_PLAN §4) without Ocean approval.

---

## Agent HARBOR — Validation & Benchmark Infrastructure

| ID | P | Task | Acceptance criteria | Status |
|----|---|------|---------------------|--------|
| H-1 | P0-1 | Wire `adb_forensic_audit.py` + `balance_forensic_audit.py` into CI (or a `pytest -m corpus` gate) over the 109-PDF corpus | Any parser regression on any corpus PDF turns the build red; runtime documented; run instructions in README | TODO |
| H-2 | P0-6 | MoneyThumb comparison harness v1: run pipeline on the 6 benchmark inputs, diff vs `moneythumbResults/` using FIELD_MAPPING verdicts; emit per-field discrepancy report with classification (our defect / MT defect / definition / source contradiction / insufficient evidence) | Committed report for all 6 sets; harness re-runnable with one command; klr_may documented as MT-failure case | TODO |
| H-3 | P1-7 | Telemetry: per-statement record of path (native/tesseract/visual), parser or fallback reason, timings, model calls, estimated cost | Batch + webapp both emit records; deterministic-coverage rate computable from logs | TODO |
| H-4 | P2-9 | Threshold calibration record: document and config-ify every tolerance/cadence constant (R-5) with corpus-derived justification | Constants in one config module with provenance comments; behavior unchanged by default | TODO |
| H-5 | P2-7 | Per-bank accuracy tracking + layout fingerprints over the expanding corpus | Accuracy by bank/field/layout queryable; report generated in CI | TODO |
| H-6 | P0 hygiene | Fix stale docs/fixtures: PROJECT_GOAL counts (523/109), `conftest.py` `BankStatements` path typo, backlog path references | Docs match reality; live-test fixture resolves | TODO |

## Agent REEF — Parser Platform & Extraction

| ID | P | Task | Acceptance criteria | Status |
|----|---|------|---------------------|--------|
| R-1 | P0-2 | Purge statement-specific hardcodes (RISK R-1 list: scanned_small_bank literal date/check repairs, community_section literal names/accounts, bank_repairs exact-delta rules, rbc/wells hardcoded years, mojibake regexes; registry counterparty entries per R-6 reviewed with Ocean) | Each removal either generalized (evidence-gated rule) or the affected statement fails closed to review; corpus audit rerun documents every status change; zero literal customer names/dates/amounts remain in parsers | TODO |
| R-2 | P1-1a | Shared utilities: `analysis/money.py` (all `_money`/`_parse_money` variants consolidated, incl. French formats), shared date helpers, shared HTML-table + section-chunking utils | 38 `_money` clones → 1 module; `td_can` import inversion gone; corpus audit byte-identical | TODO |
| R-3 | P1-1b | `Parser` protocol + registry with detection scoring; or-chain replaced; order becomes explicit tested metadata | Dispatch covered by tests (incl. ambiguity cases); adding a parser touches no orchestrator code; corpus audit byte-identical | TODO |
| R-4 | P1-1c | Per-parser conformance harness: every parser gets detection-positive, detection-negative, and self-invalidation tests | All 43 parsers covered incl. wells/scotia/columbia/navigant/relay/first_farmers (currently untested directly) | TODO |
| R-5 | P1-8 | Deterministic-parse cross-check: reconciliation failure on a deterministic parse triggers LLM second-opinion comparison (flag only, never silent adoption) | Divergences surfaced in report + telemetry; no output value silently replaced | TODO |
| R-6 | P1-2 (with LEDGER) | Migrate parsers to schema v2 outputs (account type, check number, multi-account emission where the source has them) | Coordinated with L-1; corpus audit green | TODO |
| R-7 | P2-1 | Generic statement understanding: investigation spike → design review with Ocean → build behind the reconciliation gate | Prototype measured on held-out statements; promotion decision documented | TODO |
| R-8 | P0-2 adjunct | Move BMO contradiction check, Chase-export sentinel, and repair-list ordering out of `analysis/pipeline.py` into the parser/repair layer | Orchestrator contains zero bank names; behavior identical | TODO |

## Agent LEDGER — Schema, Packages & Financial Surface

| ID | P | Task | Acceptance criteria | Status |
|----|---|------|---------------------|--------|
| L-1 | P1-2 | Schema v2: `Document → accounts[] → Statement` container, account type, holder identity, page/source provenance, check number; Decimal/int-cents money decision RFC to Ocean; adapters so ALL existing math consumes the inner `Statement` unchanged | Zero changes inside protected modules; serialization versioned; corpus audit byte-identical through adapters | TODO |
| L-2 | P1-3 | Package entity: durable record, month-map semantics (gaps/overlaps/duplicates by content hash), account-coherence checks, `analysis/package.py` extracted from `webapp/app.py:238-915` | Package math unit-testable without Flask; existing package export values unchanged (regression-pinned); naive `max(1, count)` month divisor replaced with month-map with documented semantics | TODO |
| L-3 | P1-6 | Underwriting derivations: true-balance daily series, DTI/DSCR/withhold%, monthly MCA cadence rollup, monthly cash flows/negative-day variants, large-transaction + generalized recurring views | Each metric has a documented definition + fixture tests; definitions reviewed by Ocean; all fail-closed when inputs unvalidated | TODO |
| L-4 | P2-3 | Cross-account transfer matching within packages (amount/date/account-label evidence, MT `Matches` equivalent) | Matches carry evidence links; no false-match on ambiguous pairs (fail to unmatched) | TODO |
| L-5 | P2-5 | Registry expansion: MCA funders, processors, factoring/healthcare/debt-collector/OD/stop-payment categories; contribution workflow requiring fixtures | Every new alias lands with a fixture test; R-6 style entries barred by review checklist | TODO |
| L-6 | P1-9 | Flat typed transaction export (statement + package CSV/XLSX with real types), package export includes ledger + monthly tables, review-decision export artifact | An analyst can pivot a package ledger in Excel without parsing JSON-in-a-cell | TODO |

## Agent DELTA — Serving Platform (API, Jobs, Storage, Security)

| ID | P | Task | Acceptance criteria | Status |
|----|---|------|---------------------|--------|
| D-1 | P0-3 | Durable job/result store + queue that survives restart; analyst review decisions persisted with actor/timestamp/prior value | Kill -9 the server mid-queue → jobs resume; reviews replayable | TODO |
| D-2 | P0-4 | Hardening minimum: debug off, production WSGI server, API-key auth, server-side upload limits (size/MIME/pages/count), masked account numbers in exports, Content-Disposition sanitization, CSV formula-injection guard | Verified by tests; documented deployment procedure replaces `python -m webapp.app` | TODO |
| D-3 | P0-5 | Content-hash artifact cache (sha256 → OCR markdown → extraction → report) + duplicate-upload detection surfaced to packages | Re-upload of identical bytes performs zero OCR/LLM calls; package flags duplicates | TODO |
| D-4 | P1-5 | Worker pool + per-job timeouts + bounded queue + async completion contract (poll + webhook) | 10-statement package processes concurrently; hung OCR call cannot block other jobs; scanned docs don't require a live connection | TODO |
| D-5 | P1-4 | Consume unified OCR preflight from `ocr/pipeline.py` (after O-1); delete `webapp/worker.py` duplicate ladder | One ladder, one owner; behavior parity tests | TODO |
| D-6 | P2-8 | Versioned API: stable schemas, idempotent submission (via D-3 hashes), error taxonomy replacing raw exception strings; remove dead endpoints or wire them to the source-document viewer | OpenAPI spec committed; contract tests | TODO |
| D-7 | P2-4 | Full production posture: multi-tenancy, structured audit logging, retention/deletion, encryption at rest, rate limits, monitoring/health | Security review sign-off | TODO |

## Agent SONAR — OCR & Document Intake

| ID | P | Task | Acceptance criteria | Status |
|----|---|------|---------------------|--------|
| O-1 | P1-4a | Unify the native→tesseract→visual preflight ladder inside `ocr/pipeline.py` (single implementation; tesseract becomes a pipeline member, not a webapp bolt-on) | `webapp/worker.py` and `parse.py` consume the same ladder; parity tests on corpus paths | TODO |
| O-2 | P1-4b | `OcrProvider` interface + postprocess-plugin split (Unlimited-OCR repairs become that provider's plugin) | Adding a provider touches no pipeline code; existing outputs byte-identical | TODO |
| O-3 | P1-4c | Truncation detection: check finish_reason / token ceilings; flag suspect pages for re-OCR or review instead of silent truncation | Dense-page fixture demonstrates flag; no silent truncation path remains | TODO |
| O-4 | P1 | Schema the stringly side channels (`NFCU_TX|`, `WF_TX|`, `SOURCE_POSTING_DATE|`) into versioned structured attachments on `StatementMarkdown` | Markdown normalization can no longer silently break extraction; consumers updated | TODO |
| O-5 | P2-2 | Document forensics: PDF producer/metadata/font/object inspection (PyMuPDF), joined with existing arithmetic integrity flags into a composite tamper signal with human-readable contributing factors | BMO benchmark statement flagged with reasons; clean corpus statements not flagged; false-positive review with Ocean | TODO |
| O-6 | P3 | Scanned-throughput: page batching/concurrency tuning beyond workers=1, DPI policy consolidation, alternate-model evaluation via O-2 | Measured pages/min improvement without corpus-audit drift | TODO |

## Ocean (Lead Architect) — reserved work

Architecture reviews (R-3, R-7, L-1 RFC, L-3 definitions, O-2 interface), merge-order
enforcement (MERGE_PLAN.md), protected-module change approval, discrepancy rulings from
H-2 (our defect vs MT defect vs definition difference), registry-entry review (R-6
class), and roadmap re-prioritization at each milestone gate. Ocean does not take
implementation tasks except unblocking spikes.
