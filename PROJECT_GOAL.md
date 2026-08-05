# Project Goal: Universal Bank Statement Intelligence

## Mission

Build an in-house replacement for MoneyThumb that can process defensible
underwriting data from bank statements issued by virtually any financial
institution. The system must support major banks, regional credit unions,
community banks, unfamiliar institutions, digital PDFs, scans, and degraded
photocopies without requiring a new parser for every bank name.

The priority order is:

1. Accuracy.
2. Evidence-based validation.
3. Fail-closed behavior.
4. Broad bank compatibility.
5. Low processing cost.
6. Maintainability.
7. Performance.

An unfamiliar layout is not an automatic failure, and a plausible result is not
an automatic success. The system may approve a result only when the source
evidence and reconstructed ledger prove it.

## Target Architecture

```text
PDF intake
-> document inspection
-> native text and layout extraction
-> local OCR preflight when native text is insufficient
-> known deterministic parser attempt
-> layout-aware visual OCR only when needed
-> generic statement extraction for unknown layouts
-> normalized single-account financial model
-> source grounding and mathematical reconciliation
-> integrity and confidence decision
-> deterministic underwriting metrics
-> API, dashboard, batch, and exports
```

Dedicated parsers remain useful for certified, high-volume layouts. They are an
optimization layer, not the boundary of bank support. Unknown layouts use the
generic extraction path and must satisfy the same financial contracts before
their values become authoritative.

## Approval Contract

For an authoritative result, the platform must:

- Identify one unambiguous source account and statement period.
- Extract every posted transaction with direction, amount, date, description,
  and page provenance; preserve a printed running balance when available.
- Locate generic-model transactions and statement-level amounts in source text.
- Reconcile beginning balance plus credits minus debits to ending balance.
- Reconcile printed summaries and running balances when those controls exist.
- Reconstruct every calendar day's ending balance for balance metrics.
- Calculate all financial values in deterministic code, not in the model.
- Classify each credit exactly once as verified revenue, unverified deposit, or
  non-revenue.
- Preserve lender, insurance, NSF, return, ACH, POS, ATM, and check evidence.
- Return an explicit unavailable/manual-review state when any required proof is
  missing or contradictory.

Failed source grounding, ambiguous account selection, incomplete ledgers, and
source contradictions must never produce zero-valued or stale financial output.

## Cost Policy

Use the least expensive reliable route per document:

1. Native PDF text and deterministic parser: no model call.
2. Local Tesseract preflight for scanned text: no model call.
3. Unlimited OCR for one layout-aware visual read when local evidence is weak.
4. One paid Gemini document transcription only when Unlimited OCR is unavailable.
5. Gemini 3.5 Flash-Lite for generic normalization of an unknown layout.
6. One stronger extraction only when budget remains and validation fails.
7. Manual review after the document-wide external-attempt budget is exhausted.

The default Gemini budget is two calls per document across document transcription
and structured extraction. A visual fallback therefore leaves one normalization
call and cannot escalate again. Every successful call records model, latency,
token use, estimated cost, and pricing version. Provider errors record only the
exception type, not statement data.

Production bank statements must use a paid Gemini project. Google's paid-service
terms do not use prompts or responses to improve its products; the unpaid tier
must not receive confidential statements.

## Current Baseline

Measured on August 4, 2026:

- The ordered deterministic registry contains 43 parser variants.
- The existing repository corpus remains regression-tested.
- Unknown layouts have a bounded generic route with page-level source grounding.
- Multi-account ambiguity and ungrounded generic extraction fail closed.
- Web and batch PDF processing share one authoritative routing function.
- API, dashboard, package, and export payloads receive withheld values as null,
  not fabricated zeroes.
- 564 offline automated tests pass; three live tests remain opt-in.
- A paid live Gemini smoke test reconstructed and approved a synthetic unseen
  community-bank statement in one external attempt.

This baseline proves the architecture and known regression corpus. It does not
prove universal accuracy on every institution or document condition.

## Known Source Exceptions

- Farmers & Merchants: the supplied PDF omits transaction detail needed to
  reconstruct a unique ledger.
- BMO: the supplied statement contains conflicting printed totals and many
  running-balance breaks.
- Chase transaction export: the file is not a complete formal statement and
  remains a manual-review document.

These sources must remain review cases instead of receiving plausible estimates.

## Replacement Milestones

1. Architecture foundation: generic unknown-layout route, independent source
   grounding, hard cost limits, fail-closed serialization, and unified routing.
2. Shadow validation: compare 500 to 1,000 varied real statements against
   independently reconstructed ledgers and the current MoneyThumb output.
3. Measured rollout: route certified layouts and high-confidence generic results
   in-house while tracking field accuracy and manual-review rate by layout.
4. Production hardening: durable jobs, object storage, authentication,
   authorization, tenant isolation, audit logs, encryption, retention controls,
   rate limiting, malware screening, monitoring, and disaster recovery.
5. Primary platform: remove routine MoneyThumb dependence once accuracy,
   reliability, security, licensing, and review operations meet company policy.

## Production Release Gates

Before this becomes the company's primary processor:

- Run a representative blinded benchmark, including unfamiliar community banks,
  Canadian institutions, multi-account documents, scans, and damaged PDFs.
- Define and meet field-level accuracy, false-approval, and manual-review service
  level thresholds.
- Enable paid Gemini billing and execute the applicable data-processing terms.
- Resolve all third-party license obligations documented in
  `docs/production-dependency-licenses.md`.
- Replace the in-memory job store and single-process worker with durable,
  observable infrastructure.
- Complete security, privacy, retention, and incident-response review.

The operating standard is a near-zero false-approval rate. Unknown formats are
expected; unsupported evidence is not an excuse to invent an answer.
