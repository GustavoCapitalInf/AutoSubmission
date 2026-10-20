# Production Gaps

Phase 1 audit — MoneyThumb Replacement Initiative. Author: Ocean. Date: 2026-08-06.

This document answers one question: **what prevents us from honestly saying "this
application is a production-grade MoneyThumb replacement"?** Each gap references the
RISK_REGISTER (R-nn) and PARITY_MATRIX (#nn) entries that substantiate it.

## What we CAN honestly say today

- The financial calculation core (ADB, balance metrics, reconciliation, revenue
  conservation) is more defensible, more explainable, and more fail-closed than
  MoneyThumb's observable behavior (PARITY #1, #8, #9, #15).
- 106 of 109 corpus statements produce fully validated results on every surface
  (backend, API, CSV/XLSX, package, dashboard); the 3 withheld are proven source
  defects that correctly fail closed.
- The marginal cost per statement on the deterministic + local-OCR path is ~$0 vs
  MoneyThumb's ~$3 (PARITY #21).

## Gap classes blocking the replacement claim

### G1. Coverage is corpus-shaped, not market-shaped (R-12, R-13, R-17; PARITY #3)
The 44 supported banks are the banks we have statements for. A production statement
stream will immediately contain: unseen banks, revised layouts from supported banks,
degraded scans, and multi-account documents. Today those either fall to Gemini (vendor
cost the goal forbids in production) or fail. MoneyThumb handled an unknown bank in the
benchmark gracefully; we cannot claim that yet. **This is the largest gap.**

### G2. The serving layer is a prototype (R-18…R-26; PARITY #18, #23)
No auth, no tenancy, no persistence, no audit log, no limits, debug-mode dev server,
serial single-worker queue, results lost on restart, analyst decisions unrecorded.
Every operational property in PROJECT_GOAL.md's "Production Platform" section is
currently absent. Nothing built on this can be offered to underwriters as a system of
record.

### G3. Integrity principles are violated inside the codebase (R-1, R-6)
Parsers and repairs contain literal customer names, dates, check numbers, and exact
dollar deltas. Beyond the maintenance hazard, these undermine the honesty of the
"validated" claim: a validation corpus partially matched by memorized constants is
weaker evidence than it appears. These must be removed or converted into generic,
evidence-gated rules before certification claims are made.

### G4. Validation is not continuously enforced (R-7; PARITY #24 caveat)
The corpus-wide guarantee requires a human to remember to run two audit scripts. Until
the forensic audits (or an equivalent) run in CI on every change, "106/109 validated"
describes a past event, not a present property.

### G5. Multi-account and package semantics are below MoneyThumb (R-14, R-15; PARITY #7, #13, #14, #26)
Real MCA submissions are 3–6 statements, frequently multi-account. We silently drop
secondary accounts, treat packages as browser-session state, count months naively, and
never detect duplicates, gaps, overlaps, or mixed accounts. MoneyThumb does all of this
visibly. An underwriter comparing outputs will notice immediately.

### G6. Missing underwriting intelligence (PARITY #11, #16, #25)
- True-balance duality (balances/cash-flow/negative-days excluding non-revenue funds)
- DTI %, DSCR, MCA withhold %, average-monthly revenue trios, months-since-negative
- PDF-forensics fraud signals (producer, fonts, object history) alongside our
  arithmetic integrity flags
- FDIC bank enrichment, duplicate-document detection
These are what MoneyThumb's consumers actually read; most are cheap derivations over
data we already produce.

### G7. Scanned-document throughput (PARITY #2, #20)
~23 s/page, one worker, synchronous jobs, no caching, no async contract. A 25-page
scanned package takes ~10 minutes of blocking pipeline time. MoneyThumb is async at
scale. Production requires caching (never re-OCR identical bytes), concurrency, and a
job API that survives restarts.

### G8. Export ergonomics (PARITY #19)
No flat transaction table (date/description/amount/category) at statement or package
level; long-format CSV with JSON-in-a-cell; untyped XLSX; package CSV/XLSX omit the
ledger; no PDF report; review decisions not exported as a labeled artifact.

### G9. No comparison/benchmark tooling (PARITY #24; PROJECT_GOAL "Remaining Work")
The MoneyThumb benchmark exists as files, but there is no harness that runs our
pipeline over the same inputs and diffs the results, no per-bank accuracy tracking, no
discrepancy classification workflow. Milestone 2 (parallel validation of 500–1,000
statements) is impossible without this.

## Honest status statement

> The platform is a **validated analysis engine with a prototype shell**. Its financial
> core already exceeds MoneyThumb in rigor, explainability, and cost. It is not yet a
> production-grade replacement because coverage is corpus-bound, the serving layer lacks
> every production property, multi-account/package handling is below the benchmark,
> validation is manually triggered, and several parsers contain memorized
> statement-specific constants that must be eliminated before certification claims can
> be made.
