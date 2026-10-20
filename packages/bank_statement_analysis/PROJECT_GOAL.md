# Project Goal: In-House Bank Statement Analysis

## Objective

Replace the current MoneyThumb workflow, which costs approximately $3 per
uploaded statement, with an in-house bank-statement analysis platform that runs
on company-controlled infrastructure at negligible marginal cost.

The replacement must extract complete transaction data, calculate underwriting
metrics accurately, reject or escalate statements it cannot prove correct, and
provide evidence an underwriter can audit.

## Target Capability

For every supported statement format, the platform should:

- Read native-text, scanned, and image-based PDF statements.
- Extract every posted transaction with its date, original description, amount,
  direction, and running balance when printed.
- Extract account type, statement period, bank name, routing number, and masked
  account number.
- Calculate beginning, ending, lowest, and average daily balances.
- Calculate credits, debits, withholding rate, negative days, POS purchases,
  NSF events, and ATM cash withdrawals.
- Detect known MCA lenders and recurring debit obligations with transaction
  evidence.
- Reconcile line items against printed balances and statement summaries.
- Detect missing posting dates, incomplete transaction detail, arithmetic
  contradictions, and running-balance discontinuities.
- Approve a result automatically only when the source data and reconstructed
  ledger pass the required validations.
- Export standardized transaction and underwriting data through the UI and API.
- Preserve the original statement and classification evidence for audit.

## Current Baseline

Measured against the repository corpus as of August 6, 2026:

- 109 of 109 statement PDFs parse (103 digital/native, 6 local-OCR scans).
- 106 of 109 statements pass the independent Average Daily Balance audit; the
  other 3 are withheld source contradictions, which is the intended fail-closed
  result rather than a defect. See `docs/adb-forensic-audit.md`.
- 106 of 109 statements pass the independent opening/ending/highest/lowest
  balance audit across backend, API, dashboard, CSV, XLSX, and package
  surfaces, with the same 3 withheld. See
  `docs/balance-metrics-production-audit.md`.
- 44 bank labels and 44 parser variants are represented in the audited corpus;
  41 of the 44 banks have at least one fully validated statement. The 3 without
  one (BMO, Farmers & Merchants, IBC) are represented by a single statement
  each, and all three of those are the withheld source contradictions.
- 533 automated tests pass in the default suite (about 50 seconds). The corpus
  gate runs separately (`python corpus_gate.py`, or `pytest -m corpus`, about 5
  minutes) and re-verifies all 109 statements against the committed audits,
  offline and with no model calls.
- Local visual OCR runs on the RX 7800 XT without a per-document vendor charge.
- Recognized formats use deterministic parsers without a Gemini extraction call.

This baseline demonstrates strong support for the tested statement layouts. It
does not establish universal support for every layout, account type, or revision
issued by those banks.

## Known Exceptions

The three withheld source contradictions counted in the baseline above are:

- Farmers & Merchants (`Ace_Auto_Final_Cut.pdf`): the source PDF omits
  transaction detail required to independently reconstruct the ledger.
- BMO (`BMO_Statement_January_2026 Final-1-2 (1).pdf`): the source statement
  contains conflicting printed totals and numerous running-balance breaks.
- IBC (`IBC April (1).pdf`): the printed recap and the complete detail/daily
  table disagree by $10,000.00 on the closing balance, so no unique daily
  ledger exists.

Separately, and not counted among the three:

- Chase transaction export (`Chase Business.pdf`): its balance metrics
  reconcile and it passes both audits, but it is not a complete formal
  statement — it carries no summary block or statement period — so the pipeline
  still classifies it `manual_review_required`.

These documents must remain review cases instead of receiving plausible but
unproven automatic approval.

## Remaining Work

### Format Certification

- Build a deeper regression corpus for the highest-volume US banks.
- Cover multiple months, business and personal accounts, revised layouts,
  multi-page statements, scans, and degraded PDFs.
- Compare production output against independently reconstructed ledgers and the
  existing MoneyThumb result set.
- Track accuracy by bank, layout fingerprint, field, and transaction category.

### Underwriting Coverage

- Expand true-revenue and non-revenue transaction categorization.
- Add broader transfer, payroll, loan, tax, refund, fee, and cash-flow classes.
- Define configurable underwriting scorecards and approval rules.
- Add multi-statement and multi-account applicant summaries.

### Document Integrity

- Add PDF metadata and structural inspection.
- Detect altered objects, replaced images, inconsistent fonts and coordinates,
  regenerated OCR layers, and suspicious producer history.
- Build known-good layout fingerprints without treating an unfamiliar layout as
  proof of fraud.
- Produce explainable risk flags; do not claim fraud from arithmetic anomalies
  alone.

### Production Platform

- Add authentication, authorization, tenant separation, and audit logging.
- Replace the in-memory job store and single-process queue with durable storage
  and resilient workers.
- Encrypt documents in transit and at rest and implement retention/deletion
  policies.
- Add rate limits, upload validation, monitoring, failure alerts, backups, and
  operational dashboards.
- Publish a versioned API with stable schemas and idempotent job submission.

### Cost and Performance

Note (2026-10-15): the owner's ruling of 2026-10-13 removed every model path this document names (the local
visual OCR on the RX 7800 XT and the Gemini extraction in the baseline above, the visual OCR below). Scanned
pages are read by local Tesseract on the machine and nothing is sent out; git history holds the removed code.

- Keep native extraction, deterministic parsing, and visual OCR local by
  default.
- Remove the Gemini fallback from the zero-vendor-cost production path; route an
  unsupported format to review or parser development instead.
- Measure electricity, hardware utilization, queue time, and maintenance cost
  per statement.
- Improve scanned-document throughput beyond the current approximately
  23 seconds per visually OCR'd page.

## Replacement Milestones

1. Controlled use: process validated layouts in-house and retain MoneyThumb only
   as fallback.
2. Parallel validation: compare at least 500 to 1,000 real statements against
   MoneyThumb and independent ledger checks.
3. Limited replacement: stop sending certified layouts to MoneyThumb after they
   meet the accuracy and review-rate thresholds.
4. Primary platform: route all uploads in-house and use manual review for unknown
   or failed layouts.
5. Full replacement: remove the MoneyThumb dependency after production security,
   reliability, format coverage, and fraud controls meet business requirements.

## Release Standard

A bank or layout is corporate-certified only when:

- Complete transaction detail is captured.
- Beginning balance plus all posted activity reproduces the ending balance.
- Printed running balances are continuous when present.
- Parsed posting dates cover the transaction dates printed by the source.
- Credits and debits agree with the bank summary when the summary is present.
- Average Daily Balance can be independently reconstructed.
- POS, NSF, ATM, lender, and revenue classifications pass fixture evidence
  review.
- At least several independent statements for the layout pass, including edge
  cases.
- Failures produce an explicit manual-review result rather than an approved
  estimate.

The operating priority is a near-zero false-approval rate. Unsupported or
internally contradictory documents should fail closed.
