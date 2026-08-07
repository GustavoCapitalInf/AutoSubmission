# Discovery Tranche 1 — Report

Ocean. Run `2026-08-07T02:34:05…-ec400125`, mode `--digital`, commit `b57ff52`.
Wall clock **50.4 min** (~0.9 s/document). Vendor cost **$0.00** — zero model
calls; the no-model-client property held structurally for the entire run.
Frozen baseline verified at start and unchanged at end (3,768 files /
3,615 PDFs / 996,080,803 bytes). No stop condition triggered. No source file
modified. Full artifacts (gitignored): `discovery_reports/…-ec400125/`
(report.txt, summary.json, rows.csv, hash_map.csv, telemetry.jsonl).

## 1. Accounting (every document explicitly disposed)

| Disposition | Count | Notes |
|---|---|---|
| Enumerated | 3,506 | discovery set (pinned 109 excluded by manifest partition) |
| Processed | 3,314 | |
| Deferred to tranche 2 | 192 | scanned 176 + mixed 16 (`deferred_scanned`) |
| Rejected invalid/encrypted | 17 | `invalid_pdf` — honest-rejection bucket |
| Dispatched live | 3,245 | |
| Served from cache | 69 | duplicate content (incl. pinned-corpus copies) — no re-dispatch |
| Duplicates identified | 124 within-archive + 82 pinned-corpus copies | flagged by content hash |

## 2. Dispatch & outcomes

| | Count | % of 3,245 dispatched |
|---|---|---|
| **Claimed (deterministic)** | **1,662** | **51.2%** |
| Unclaimed | 1,583 | 48.8% |
| **Ambiguous** | **0** | **0.0%** |

Outcomes over processed: **validated 1,049** (31.7%) · review 5 · **withheld
608** (18.3%, `withheld_adb` — fail-closed exactly as designed) · failed 1,652
(1,583 no-parser + **52 exceptions** + 17 invalid) · deferred 192.

## 3. Per-parser validation rate (claims ≥ 20)

| Parser | Claims | Validated | Rate |
|---|---|---|---|
| navy_federal / bluevine / td_us / mission_valley | 48 / 29 / 28 / 18 | all | **100%** |
| relay | 22 | 21 | 95.5% |
| scotiabank | 80 | 75 | 93.8% |
| regions | 21 | 18 | 85.7% |
| bank_of_america | 344 | 291 | 84.6% |
| wells_fargo | 233 | 192 | 82.4% |
| pnc | 44 | 28 | 63.6% |
| truist | 48 | 28 | 58.3% |
| rbc | 156 | 90 | 57.7% |
| **chase** | **411** | **94** | **22.9%** |
| **td_canada_native** | **73** | **7** | **9.6%** |

## 4. Folder-label detection accuracy

Of 1,662 claims: **agree 1,416** · unlabelled folder 225 · label-unmatched 21.
The 21: Chase→mission_valley (16), Chase→relay (4), TD Bank→td_canada_native
(1). **All 21 validated end-to-end (full reconciliation)** — the evidence says
these are misfiled documents in the archive's folders, not wrong parser
claims. Queued for human adjudication, not remediation. Bonus: the
`Unidentified/` folder yielded **148 fully validated** statements
(scotiabank 54, navy_federal 48, wilson_muir 10, …) — documents the human
sorter couldn't place that the registry identified and reconciled.

## 5. Ranked unknown-layout clusters (unclaimed 1,583)

Unidentified 649 · **BMO 178** (parser covers ~1 of its layouts; folder holds
184) · **Chase 171** · Huntington 54 (no parser exists) · CIBC 41 (only the
French parser exists) · RBC 39 · Bank of America 37 · Mercury 31 ·
Bluevine 28 · TD Bank 26 · Capital One 24 · Citizens 22 · PNC/US Bank 17 ·
Fifth Third 16 · Citibank/Lead Bank 15 · Zions 13 · Truist 12 · Brex 10 · …

## 6. Cache & integrity

OCR cache: 3,364 entries, 125 hits (duplicates). Analysis cache: 1,662
entries written (re-runs now free). Truncation flag fired on **1** page of 1
native document (first real fire; document failed anyway — no masking
effect). Telemetry: one JSONL record per document, sensitivity invariant
intact (spot-checked; hashes/ids/counts only).

## 7. Systemic findings

- **S1 — The bottleneck for known banks is extraction completeness, not
  detection.** 608 claimed documents withheld on ADB validation; chase
  validates only 22.9% of its claims, td_canada_native 9.6%. The fail-closed
  machinery worked at scale — nothing invalid leaked — but layout variants of
  known banks are the top volume opportunity.
- **S2 — Two crash clusters (52 exceptions, 1.6%):** AttributeError ×36
  (US Bank folder — 36 of that folder's 59 docs), ValueError ×16 (Bank of
  America folder). Crashes escape as exceptions instead of failing closed.
  Platform fix needed: an exception boundary at the dispatch/parse seam that
  converts a parser crash into a fail-closed `failed/parser_exception`
  outcome with telemetry attribution. **No remediation performed** (per
  instruction); documents are correctly counted as failed.
- **S3 — Detection integrity held at production scale: ambiguous 0** across
  3,245 dispatches, zero observed cross-claims. The R-3.4/R-4b marker work
  did its job.
- **S4 — Near-miss telemetry works** (regions/navigant corroborating markers
  fire sub-threshold on 20–30% of unclaimed docs) and gives P2-1 a ranking
  signal, though those two parsers' corroborating markers are generic enough
  to be noisy.

## 8. Proposed Wave 3 requirements (draft, for Gustavo's review)

1. **Exception boundary** at the dispatch/parse seam (S2) — small, platform-
   level, first.
2. **Layout-variant completeness program** for claimed-but-withheld leaders
   (chase 317, rbc 66, td_canada 66, bofa 53, wells 41) — evidence-driven
   parser work with per-variant fixtures, targeting the 608 withheld.
3. **P2-1 generic-understanding investigation**, now with its requirements
   corpus: the 1,583 unclaimed + §5 ranking (BMO and Chase variants first);
   prototype `grounding.py` + eval harness as catalogued inputs.
4. **Registry candidates by volume** (Huntington 54, Mercury 31, CIBC-EN 41,
   Fifth Third 16, Citibank 15, Lead 15, Zions 13, Brex 10) — decided after
   cluster adjudication, not before.
5. **Folder-label adjudication workflow** (21 misfiled + 225 unlabelled).
6. Near-miss marker-quality pass for regions/navigant corroborating markers.

## 9. Tranche 2 recommendation

**Safe to begin.** Scope is small (176 scanned + 16 mixed), O-3 truncation
flags are live, telemetry and cache are proven, and the S2 exception risk is
accounted (crashes are counted, not hidden). The S2 boundary fix would make
tranche-2 statistics marginally cleaner but is not a safety blocker. Estimated
serial runtime: hours (local OCR ~23 s/page); no vendor cost. Awaiting
Gustavo's go.
