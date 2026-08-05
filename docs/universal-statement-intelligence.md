# Universal Statement Intelligence

## Purpose

This document defines the production routing and trust boundary for statements
whose institution or layout may never have appeared in the parser corpus. The
system generalizes through a validated extraction contract, not through a bank
name allowlist.

## Authoritative Route

All PDF callers use `webapp.worker.analyze_pdf`. The web worker and `batch.py`
therefore cannot silently choose different extraction paths.

### 1. Native document inspection

The router first extracts selectable PDF text and geometry. Institution-specific
native readers are tried before the general native reader because they preserve
known row ownership and columns. If native text is too sparse, the router tries
local Tesseract as a zero-provider-cost preflight.

### 2. Deterministic parser registry

`analysis/parser_registry.py` owns the ordered parser registry. A parser either
returns one isolated `Statement` or returns `None`. Parser order is explicit and
tested because several formats share broad table vocabulary.

Known layouts continue to receive deterministic extraction without Gemini. The
generic path is not allowed to override a valid deterministic result merely
because a model produces something plausible.

### 3. Visual OCR retry

Tesseract is a cheap routing signal, not sufficient evidence for an unknown
layout. Weak Tesseract output receives one layout-aware visual OCR pass through
Unlimited OCR. Native text receives a visual retry only when validation suggests
an extraction problem that a new visual read could repair.

If Unlimited OCR is unavailable and a Gemini call remains, the router sends the
whole PDF to Flash-Lite for transcription. That call consumes one slot from the
same document-wide budget. With the default limit of two, only one structured
ledger extraction remains and no stronger retry is possible. If no slot remains,
the visual provider error is returned without an unbounded fallback chain.

The router does not spend visual OCR on a native source already proven to be an
incomplete export, a missing page, or an internally contradictory statement.

### 4. Generic statement extraction

When no deterministic parser matches, Gemini converts OCR markdown to the shared
`Statement` schema. The model is restricted to extraction and normalization. It
does not calculate balances, revenue, withholding, or other underwriting values.

The generic schema requires:

- one-based source-page provenance for every transaction;
- distinct account count and account-selection status;
- isolation of exactly one account ledger;
- printed summary values without invented arithmetic;
- null values when evidence is absent.

`gemini-3.5-flash-lite` is the default low-cost model. A stronger extraction is
permitted only when the first result fails reconciliation or source grounding.
The default document-wide cap is two external extraction attempts.

## Independent Validation

Model output is not trusted because it is internally consistent. Two independent
controls must pass.

### Source grounding

`analysis/grounding.py` verifies generic extraction directly against OCR text:

- every transaction amount and posting date must appear on its claimed page;
- distinctive description terms must appear near that amount;
- a claimed printed running balance must appear near the same source row;
- one source amount span cannot support two duplicate model transactions;
- the statement period must be valid, source-supported, and contain every posting;
- the institution name and any selected account suffix must exist in the source;
- opening, ending, summary, and printed-average values must appear beside an
  appropriate source label;
- every extracted bank-printed daily balance must match a dated row in a labeled
  daily-balance table on its claimed page;
- transactions without valid page provenance fail validation.

This catches self-reconciling hallucinations that ordinary ledger math cannot.
For scanned PDFs, grounding proves consistency with the selected OCR
transcription, not pixel-perfect agreement with the original image. Printed
summaries, running balances, closing reconciliation, corpus benchmarks, and
manual review remain the controls against a self-consistent OCR error.

### Financial reconciliation

Deterministic Python independently verifies:

```text
opening balance + posted credits - posted debits = ending balance
```

It also checks printed summary totals, transaction counts, posting-date coverage,
running-balance continuity, and daily-balance reconstruction where evidence is
available. All underwriting metrics are derived after these controls.

## Fail-Closed Contract

Generic output is withheld when source grounding fails or account selection is
ambiguous. Serialization preserves diagnostic evidence but removes unproven
transactions and financial values before they reach a consumer.

The API contract for withheld generic values is:

- `metrics.authoritative = false`;
- `metrics.unavailable_reason` explains the machine-readable reason;
- financial metrics are `null`, never `0` as a fallback;
- transaction classifications and detection evidence are empty;
- quality is `manual_review_required`;
- package totals are `null` when no document in the package is authoritative.

The existing dashboard consumes these backend values. It does not calculate a
second answer or fabricate a display fallback.

## Cost Controls

The following environment variables define the external extraction boundary:

| Variable | Default | Meaning |
| --- | ---: | --- |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Primary generic model |
| `GEMINI_ESCALATION_MODEL` | `gemini-3.5-flash` | Stronger bounded retry |
| `GEMINI_MAX_EXTRACTION_ATTEMPTS` | `2` | Maximum Gemini calls per document, including paid visual fallback |
| `GEMINI_TIMEOUT_MS` | `90000` | Request timeout |
| `GEMINI_HTTP_ATTEMPTS` | `1` | SDK HTTP attempts per call |

Set `GEMINI_MAX_EXTRACTION_ATTEMPTS=0` to disable external generic extraction
globally while retaining deterministic parsers.

Each completed call records prompt, response, and thinking tokens when supplied
by the provider, plus latency and a versioned cost estimate. Unknown model IDs
retain token telemetry but do not receive an invented price.

Pricing tables are estimates for operational monitoring, not billing records.
Provider invoices remain authoritative. Visual OCR infrastructure cost is not
currently included in Gemini token telemetry and must be measured separately.

## Verification

Run the deterministic regression suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run the opt-in generic live smoke test against the paid Gemini project:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m live tests\test_live_smoke.py -k generic
```

The live fixture is synthetic and contains no customer information. A passing
smoke test proves connectivity and contract behavior, not accuracy across unseen
real-world layouts.

## Remaining Production Work

This architecture removes named-bank parsing as the product boundary, but it is
not by itself universal certification. Required next steps are:

- blinded benchmarking on hundreds of varied real statements;
- field-level accuracy and false-approval reporting by layout fingerprint;
- durable queues, object storage, retries, idempotency, and provider circuit
  breakers;
- authentication, tenant isolation, encryption, retention, and audit controls;
- manual-review operations and feedback capture;
- dependency license resolution and software-composition scanning;
- provider cost, latency, and availability monitoring.
