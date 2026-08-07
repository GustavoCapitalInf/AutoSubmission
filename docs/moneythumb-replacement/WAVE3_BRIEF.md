# Wave 3 Execution Brief — Generic Capability

Author: Ocean. Date: 2026-08-07.
Status: **proposed — awaiting Gustavo's approval; nothing implemented.**
Baseline: `main` post-Wave-2 + discovery (see DISCOVERY_COMBINED_REPORT.md).
Ordering directive (Gustavo): generic capabilities over individual statement
fixes; the exception boundary is task 1.

## 0. Thesis

Discovery proved the platform's *correctness* end-to-end at production scale
and located the gap precisely: **capability, not discipline**. 49.7% of the
market-shaped stream is unclaimed and 17.5% is claimed-but-withheld — both
are layout-knowledge problems, in three sizes: variants of known banks
(~660 + most of the 614 withheld), the Unidentified mix (725), and low-volume
unknown banks (~180). Hand-writing parser #47…#400 is explicitly rejected
(AD-7). Wave 3 builds the generic machinery and lets evidence route each
cluster to the cheapest adequate mechanism.

## 1. Task cards (priority order)

### W3-1 — Exception boundary at the dispatch/parse seam  [FIRST; required by Gustavo]
A parser crash becomes an explicit fail-closed outcome, never an escaped
exception. Registry-level `try` around each `parse` attempt (and detect,
defensively): outcome `failed / parser_exception`, telemetry carries parser
id + exception class name (never messages — sensitivity), document routed to
review, processing continues. The 53 discovery crashes become the regression
fixtures (US Bank AttributeError ×36, BofA ValueError ×16, TD ×1 — synthetic
reproductions, not archive files). Acceptance: no code path from `resolve()`
through parse can raise out of the seam; corpus gate byte-identical; the
53 re-run as `parser_exception` outcomes. Owner: REEF. Size: small.
**Underlying defects are then fixed as ordinary bugs with fixtures (the
boundary is the platform fix; the two crash clusters are the first two bug
tickets).**

### W3-2 — Withheld-diagnostics platform (turns the 614 into ranked evidence)
Generic, bank-agnostic diagnosis of WHY a claimed document fails validation:
per-check failure taxonomy (which reconciliation identity, which ADB check,
missing summary field, count mismatch, page-coverage gap…) emitted into
telemetry + a rollup view. No parser changes in this task — it produces the
evidence that ranks variant work by check-class and volume, so remediation
becomes "fix the top failing check-class for chase variants" instead of
statement-by-statement archaeology. Owner: HARBOR (consumes analysis
outputs; zero protected-module change — diagnostics read existing
reconciliation/ADB issue lists). Size: small-medium.

### W3-3 — P2-1: generic statement understanding (the wave centerpiece)
AD-7 executed with its requirements corpus now in hand (1,741 unclaimed +
cluster ranking + 159 OCR-text failures).
- **3a Investigation spike (time-boxed):** candidate approaches measured on a
  stratified sample drawn from the clusters (BMO/Chase variants, Unidentified,
  low-volume unknowns): layout-agnostic table/column structurer over native
  text + OCR grids feeding the SAME `Statement` schema and the SAME
  reconciliation gate. Inputs to reuse (adapted, cited, never wholesale —
  PROTOTYPE_REVIEW items 1–3): the source-grounding validator concept
  (`grounding.py`), the replay eval harness + recorded-fixture design
  (`eval_unknown_banks.py`), bounded-retry/kill-switch patterns.
- **3b Ocean design review** — go/no-go + architecture ruling.
- **3c Build behind the gate:** structurer → Statement → reconciliation →
  fail-closed; source-grounding as the second validation axis; measured
  coverage/validation uplift reported against the discovery corpus via the
  existing runner (which needs no changes to measure it).
  Success metric (proposal): +15–25 points of validated coverage on the
  discovery set at $0 vendor cost, zero corpus-gate drift, zero false
  validations (grounding + reconciliation both required).
Owner: REEF (new sub-system), Ocean-gated at 3b. Size: LARGE — the wave's
token center.

### W3-4 — Cluster adjudication & routing (after 3a informs build-vs-parser)
Tooling + workflow to disposition each cluster: known-bank variant (→ W3-2
evidence), generic-understanding candidate (→ W3-3), new-parser candidate
(only where volume AND layout stability justify — Huntington 54 is the first
test case), junk/unusable. Includes the misfiled-document queue (21) and
Unidentified sampling. Owner: HARBOR tooling + Ocean/Gustavo adjudication.

### W3-5 — Visual-OCR rung integration (recovers the 13 + upgrades class 5)
The local visual-OCR provider joins the discovery ladder behind cache +
truncation flags + telemetry cost accounting; the 13 deferred and the 159
tesseract-insufficient documents get a measured second read. Depends on the
local OCR server being available; stays $0-vendor. Owner: SONAR.

### W3-6 — Carried backlog (scheduled, small)
R-1 residual sweep (altana digit run; farmers_merchants weakest-evidence
registration); near-miss marker quality (regions/navigant corroborating
markers); cache eviction policy (now with real size data: ~1.5 GB analysis
artifacts); telemetry extraction-token capture (protected-file diff);
truncation-flag review policy (adjudication outcome); D-2b auth trio when
serving-layer work resumes.

## 2. Explicitly out of scope
Statement-by-statement fixes; new parsers ahead of W3-4 adjudication; Gemini
or any paid fallback in the production path; L-* (schema v2/packages) —
sequenced after the coverage story per MASTER_PLAN; protected financial
modules (unchanged mandate).

## 3. Proposed execution structure
Agents (Opus 5, subject to Gustavo's approval): REEF (W3-1 → W3-3a spike),
HARBOR (W3-2 → W3-4 tooling), SONAR (W3-5) — three to start; W3-3c staffing
decided at the 3b review. Merge order: W3-1 → W3-2 → (3a report) → 3b gate →
3c/W3-4/W3-5 as ruled. Standing criteria unchanged: suite green, corpus gate
GREEN (byte-identical unless Ocean-approved re-baseline), no new
statement-specific constants, protected modules untouched, CI green per
merge, discovery re-runs measured via the existing runner.

## 4. Gates for Gustavo
1. This brief (scope + agent count).
2. W3-3b design review outcome before any 3c build.
3. Any new-parser decision out of W3-4.
4. Prototype-branch deletion recommendation lands with 3a (it consumes them).
