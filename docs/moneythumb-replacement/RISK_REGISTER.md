# Risk Register

Phase 1 audit — MoneyThumb Replacement Initiative. Author: Ocean. Date: 2026-08-06.
Severity: **Critical** (blocks the replacement claim or threatens financial integrity),
**High** (will bite in production), **Medium** (debt/friction), **Low** (hygiene).
Nothing here is fixed in Phase 1 — identification only.

## Financial-integrity risks

| ID | Severity | Risk | Evidence |
|----|----------|------|----------|
| R-1 | Critical | **Statement-specific hardcodes inside parsers/repairs** — literal dates, check numbers, exact dollar deltas, and customer names. These violate the project's own engineering principles ("never introduce statement-specific hacks", "never hardcode expected values") and will silently do nothing — or the wrong thing — on the next customer's file. | `scanned_small_bank.py:300-321` (repair keyed to `date=="2026-06-18" and description=="Check 1944" and amount==-4500.00`); `bank_repairs.py:115-134` (Chase repair fires only on exactly −1000.00 delta); `community_section.py:29,226` (literal "GREEN CONVERGENCE"/"FIELD TRUCKING LLC", account `35127380`); `scanned_small_bank.py:214-216,338` ("THE GRANITE GIRLS, LLC", "KLR ENTERPRISES"); `wells.py:20-22` (default year 2026); `rbc.py:288-291` (hardcoded period start, Dec/Jan only); mojibake regexes `rbc.py:246`, `scanned_small_bank.py:146,211` |
| R-2 | Critical | **Deterministic-path escalation blind spot** — a deterministic parser that matches but mis-signs or drops rows produces a confidently wrong report; escalation/cross-check applies only when `deterministic_stmt is None`. Reconciliation catches most cases, but summary-only statements (where `summary_ok` carries the day at ±$1.00) have the weakest net. | `analysis/pipeline.py:424-444` (condition at :432) |
| R-3 | High | **Keyword-list sign inference** for Canadian banks — credit/debit decided by merchant-name lists; a new merchant flips a sign silently. Mitigated only where printed balances exist (`_solve_segment`, itself a 2^16 brute force). | `rbc.py:29-64,181-182,251-274`; `td_can.py:153-174` |
| R-4 | High | **`trust_stated_summary=None` path** adopts bank-stated totals labeled `bank_stated_unverified` as effective deposits, feeding eligible deposits and the withholding denominator without reconciliation — distinguished only by a source label downstream consumers may ignore. | `analysis/metrics.py:361-371` |
| R-5 | High | **Unjustified magic thresholds** — ±$1.00 summary tolerance vs ±$0.01 sum check; 0.98–1.02 coverage band; cadence constants (1.6/1.5/5–9/2.5 days); 14-day reversal window; ≥3 breaks ⇒ possible fraud; recurrence ≥3/≥2. No calibration record; hand-assigned "confidence" constants (0.99…0.35) look probabilistic but are ordinal. | `reconcile.py:15,60-61,71,146,212,221`; `transaction_classifier.py:1186-1189,1286,1376`; `pipeline.py:266,286,334` |
| R-6 | High | **Counterparty-specific entries in "global" registries** — a single merchant as an operating-revenue source; bare numeric/phone-string lender aliases risk cross-statement false positives. | `classification_registry.py:143` ("11-101 Signal R"), `:42` ("3329001101"), `:33-34` ("MC 844 662 3467") |
| R-7 | Critical | **Corpus-wide validation is not continuously enforced** — the 106/109 guarantee rests on manually-run audit scripts; pytest pins only recorded CSVs + PDF hashes. A parser regression on ~98 of 109 corpus PDFs passes the default test run. | `adb_forensic_audit.py`, `balance_forensic_audit.py` (manual); `tests/test_balance_metrics_audit.py` (snapshot-only) |
| R-8 | Medium | **Float money everywhere except ADB** — metrics sums floats and rounds at the end; delta-equality checks (`revenue_reconciliation_delta == 0.0`) could flap on large statements. Schema money is `float`. | `analysis/metrics.py:256-299`; `analysis/schema.py` |
| R-9 | Medium | **`normalize_statement` heuristic** deletes any row whose description starts with balance-marker words when its amount equals a statement balance — a legitimate coincident transaction would be dropped. | `analysis/pipeline.py:78-94` |
| R-10 | Medium | **Escalation acceptance heuristic** ("fewer issues" wins) can adopt a differently-wrong extraction; no third arbiter. | `analysis/pipeline.py:438` |
| R-11 | Medium | **OCR truncation without flag** — 4096 max tokens/page with no finish_reason check; a very dense page truncates silently (local server allows 32768). | `ocr/ocr_client.py:10`; `local_ocr_server.py:123` |

## Coverage / generality risks

| ID | Severity | Risk | Evidence |
|----|----------|------|----------|
| R-12 | Critical | **Unknown-bank support depends on Gemini**, which PROJECT_GOAL.md wants out of the zero-vendor-cost production path. Without it, an unrecognized layout has no path but manual review; with it, we have vendor dependence. There is no in-house generic layout-understanding layer. | `analysis/pipeline.py:405-422`; PROJECT_GOAL.md "Cost and Performance" |
| R-13 | Critical | **Parser scaling model** — every new bank/layout revision is hand-written code inserted into an ordered 43-way or-chain with no conformance harness. MoneyThumb-scale coverage (thousands of layouts) is unreachable this way. | `analysis/pipeline.py:357-402` |
| R-14 | High | **Single-account schema** — multi-account PDFs silently reduced to one account (savings dropped). MoneyThumb splits and reports both. Underwriters can miss accounts entirely. | `analysis/schema.py:29-65`; `truist.py:56-67`; `navy_federal.py:57-69` |
| R-15 | High | **Package semantics are naive** — months = `max(1, statement_count)`; no month-gap, overlap, duplicate, or same-account coherence checks; a package mixing different businesses' accounts sums silently; duplicate uploads double-count. | `webapp/app.py:778`, `app.py:238-915` |
| R-16 | Medium | **Fragile native-text extractors** — Wells Fargo parses by hardcoded pixel coordinates; stringly side channels (`NFCU_TX|`, `WF_TX|`, `SOURCE_POSTING_DATE|`) smuggled through markdown comments, unversioned. | `ocr/native_text.py:303-382,187-197,296-298` |
| R-17 | Medium | **Self-invalidating parsers silently fall through to Gemini** — "deterministic coverage" is corpus-shaped; any OCR noise on a supported bank costs an LLM call with no telemetry recording the fallback rate. | `bluevine.py:78-81`; `scanned_small_bank.py:418-419`; etc. |

## Operational / production risks (serving layer)

| ID | Severity | Risk | Evidence |
|----|----------|------|----------|
| R-18 | Critical | **No authentication/authorization on any route**; job UUIDs are the only access control; any client can read, mutate reviews, and download exports. No tenancy. | `webapp/app.py` (no auth code anywhere) |
| R-19 | Critical | **Flask dev server with `debug=True` is the deployment** — Werkzeug interactive debugger = RCE if bound beyond localhost; no WSGI server, TLS, proxy, or health endpoint. | `webapp/app.py:1156-1157`; `run.ps1:43` |
| R-20 | Critical | **Zero persistence** — jobs, results, queue, and analyst revenue-review decisions all vanish on restart; PDFs and results live in process RAM indefinitely (no TTL/eviction). | `webapp/jobs.py:8-50`; `webapp/app.py:26-50` |
| R-21 | High | **No audit logging at all** — analyst review mutations leave no actor/timestamp/prior-value trace; a compliance problem for underwriting decisions. | `webapp/app.py:1027-1050`; no `import logging` in `webapp/` |
| R-22 | High | **Serial single-worker processing, unbounded queue, no timeouts** — one hung OCR call blocks the platform; a 10-statement package processes sequentially. | `webapp/app.py:26-50`; `webapp/worker.py` |
| R-23 | High | **No server-side upload validation** — no size/MIME/page-count caps ("100MB" is display text); whole files buffered in RAM; no rate limiting; `/render` + `/page` re-rasterize per request (DoS-able). | `webapp/app.py:935,999-1005,1109`; `index.html:977` |
| R-24 | High | **Sensitive-data handling** — unmasked account numbers in JSON/CSV exports (only the UI masks); no encryption-at-rest/retention/deletion story; guessable OCR key derived from public pod id. | `analysis/serialization.py:131`; `app.js:234-239`; `run.ps1:18-19` |
| R-25 | Medium | **Injection surfaces** — Content-Disposition built from unsanitized client filename; CSV formula injection (`=`,`+`,`@` in descriptions); OCR-derived HTML served raw at `/result`. | `webapp/app.py:1148-1152,110-115,1115-1120` |
| R-26 | Medium | **No idempotency/dedup** — same PDF re-uploaded = new job, full re-OCR, double-counted in packages. | `webapp/jobs.py:43` |
| R-27 | Low | **Dead endpoints and dead UI** — 5 unused viewer routes still exposed; decorative search/notification controls; hardcoded profile card. | `webapp/app.py` routes 4-6,12,13; `index.html:917-936` |

## Maintainability risks

| ID | Severity | Risk | Evidence |
|----|----------|------|----------|
| R-28 | High | **Helper duplication at scale** — 38 `_money` implementations; 14 modules import `td_can._parse_money` (wrong dependency direction); 17 `_iso` clones; 12 check-section parsers; duplicated preflight ladders in `ocr/pipeline.py` vs `webapp/worker.py` (already drifted). | grep counts; `ocr/pipeline.py:38-47` vs `webapp/worker.py:22-29` |
| R-29 | Medium | **Orchestrator contamination** — BMO contradiction check, Chase-export sentinel, ordered repair list all live inside `analysis/pipeline.py`. | `pipeline.py:100-116,153-162,211-270` |
| R-30 | Medium | **~680-line package aggregation inside a Flask route module** — analysis logic in the serving layer, untestable in isolation from Flask. | `webapp/app.py:238-915` |
| R-31 | Low | **Stale documentation** — "323 tests"/"105 PDFs" in PROJECT_GOAL.md vs actual 523/109; backlog references `BankStatements/` paths that don't exist; conftest `samples_dir` typo (`BankStatements` vs `Bank Statements`). | `PROJECT_GOAL.md:37-44`; `docs/backlog.md`; `conftest.py` |
| R-32 | Low | **Dead/latent code** — unused `interest` in implied-beginning derivation; empty `BANK_SPECIFIC_LENDER_ALIASES`; unreachable `summary_trusted` quality branch; vestigial `base` parser parameter; dead `wells._is_credit`. | `reconcile.py:83-87`; `classification_registry.py:294`; `pipeline.py:298,337`; `wells.py:34-42,85-86` |

## Benchmark-derived observations (MoneyThumb defects — do NOT copy)

For the avoidance of doubt, these MT behaviors were observed in the benchmark and must
NOT be replicated: headline ending balance that ignores its own failed reconciliation
(bmo_jan); "Total Revenue" statistic that actually equals net cash flow; string-typed
numerics and label-keyed loose tables; deprecated ledger export with no replacement;
activity-day-only daily balances that make ADB unverifiable.
