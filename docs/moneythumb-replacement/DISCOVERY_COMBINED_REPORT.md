# Discovery — Combined Tranche 1 + 2 Report

Ocean. 2026-08-07. Runs: `…-ec400125` (digital, 50.4 min) and `…-0fd1bc0b`
(scanned, 39.2 min, cumulative over the whole set). Total wall ~90 min,
**vendor cost $0.00** (zero model calls across both tranches; local tesseract
only on the scanned rung). Frozen baseline verified at start of both runs and
unchanged. Ambiguous dispatches: **0 across every live dispatch in both
tranches.** No source file modified; no remediation performed. All artifacts
preserved (gitignored) for Wave 3 analysis.

## 1. Final accounting — 3,506 discovery documents, every one disposed

| Disposition | Count | % |
|---|---|---|
| **Validated** (full fail-closed pipeline pass) | **1,058** | 30.2% |
| Review (validated values, integrity flags) | 10 | 0.3% |
| **Withheld** (claimed; ADB validation failed; fail-closed) | **614** | 17.5% |
| Unclaimed (no parser matched) | 1,741 | 49.7% |
| Parser crashes (exceptions) | 53 | 1.5% |
| Malformed / encrypted | 17 | 0.5% |
| Deferred (needs visual-OCR rung, disabled this wave) | 13 | 0.4% |

Claims total **1,682** (1,662 native + 20 tesseract). Duplicates handled by
content hash: 124 within-archive + 82 pinned-corpus copies. Deterministic
coverage over all dispatched documents: **~49%**; among *claimed* documents
the full-validation rate is **63%** (1,058+10 of 1,682).

Scanned tranche specifics: 179 documents read via tesseract → 20 claimed
(9 validated — first_farmers 6, apex_scanned 2, regions 1 — proving the
scanned path end-to-end at $0), 159 unclaimed; 13 deferred to the visual
rung; truncation flags fired on 4 documents total (3 tesseract, 1 native;
one flagged document still validated — the flag is advisory and
reconciliation independently passed).

## 2. Failure classes, ranked by volume × system-wide impact

| # | Class | Volume | Impact assessment |
|---|---|---|---|
| 1 | **Unclaimed — known banks, unseen layouts** (BMO 179, Chase 176, TD 45, CIBC 43, BofA 41, RBC 41, Citizens 30, Bluevine 28, CapOne 25, US Bank 19, PNC 17, Truist 15 + tail) | **~660** | Largest addressable block; each is a bank we already validate on other layouts. G1 quantified. |
| 2 | **Unidentified mix** (unclaimed docs from the human-unsortable folder) | **725** | Composition unknown until adjudicated; 148 of the folder's docs DID validate, so it is a mix of known-variant, unknown-bank, and junk. The purest generic-understanding test set. |
| 3 | **Claimed-but-withheld** | **614** | Highest value-per-fix: detection and claim already correct; extraction completeness fails ADB. Concentrated: chase 317, rbc 66, td_canada 66, bofa 53, wells 41. |
| 4 | **Unclaimed — banks with no parser** (Huntington 54, Mercury 31, Fifth Third 16, Citibank 15, Lead 15, Zions 14, Brex 10 + tail) | **~180** | Classic registry-expansion candidates; per-bank volume is modest — argues for generic capability over parser #47…#60. |
| 5 | **OCR extraction failures** (scanned docs where tesseract text yielded no claim) | **159** | Distinct mechanism from #1: text quality, not layout knowledge. Needs the visual rung or better OCR before parser work matters. |
| 6 | **Parser crashes** | **53** | Small volume, HIGHEST systemic severity: exceptions escape the fail-closed contract. Two clusters: `AttributeError` ×36 (US Bank folder), `ValueError` ×16+1 (BofA, TD). Wave 3 task 1. |
| 7 | Malformed/encrypted (17) · deferred-visual (13) · truncation flags (4) | 34 | Honest-rejection and integrity buckets working as designed; visual rung integration recovers the 13. |

## 3. What held under production load (the platform verdict)

- **Detection integrity: perfect.** 0 ambiguous, 0 observed cross-claims over
  ~5,000 live dispatches across both tranches; the 21 label mismatches all
  validated end-to-end (misfiled documents, queued for adjudication).
- **Fail-closed financial discipline: perfect.** Nothing unvalidated leaked
  to a validated outcome; 614 withheld rather than guessed.
- **Cost model: proven.** $0.00 vendor spend for 3,506 real documents.
- **Cache: proven.** Tranche 2 replayed tranche 1 free (1,732 cached rows).
- **Telemetry sensitivity invariant: held** (spot-checked both runs).
- **The gap is capability, not correctness**: half the market-shaped stream
  needs layout knowledge (classes 1, 2, 4) or better OCR text (class 5) that
  the platform does not yet have — exactly what AD-7/P2-1 anticipated.

## 4. Adjudication queue (human, no code)

21 misfiled documents; 225 claims in unlabelled folders; Unidentified-cluster
composition sampling; the 4 truncation-flagged documents; the flagged-but-
validated scanned document (review policy question: should a truncation flag
force review even when reconciliation passes?).

Wave 3 proposals: see `WAVE3_BRIEF.md`. No implementation has begun.
