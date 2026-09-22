# Phase 3.1 visual fallback implementation and evaluation

Implementation, the bounded model evaluation and the deterministic date fix are
complete. **Reading-quality acceptance remains unpassed.** The final v9 evidence
resolves 215 missing dates from reviewed text and periods, but both statements remain
held for five other gate reasons and no analysis is published. The local app is ready
for restricted testing with the same two authorized PDFs and their saved evidence.
This is not a production rollout or authorization for other customer uploads.

The governing instructions are [PHASE3-VISUAL-FALLBACK.md](PHASE3-VISUAL-FALLBACK.md).
This record contains implementation details, counts and status only. Artifact files
holding customer pages, extracted content, detailed comparisons and document hashes
remain in private storage. The tool-context exposure is disclosed below. Connection
details are excluded, and the historical independent-transcription leaderboard is unchanged.

## Diagnostic privacy incident

A delegated diagnostic search accidentally included saved customer request content,
including inline page-image data, in tool output, exposing it to the assistant's tool context contrary to the approved
boundary. The search stopped; subsequent checks use explicit code filenames or local
scripts that emit closed metadata only. The already emitted output cannot be retracted.
This incident was disclosed to the owner.
A private, ignored `AGENTS.md` now records the boundary: no broad private-evidence
searches or source-content tool output; use explicit code paths and scripts that emit
closed metadata only. This safeguard does not retract the earlier exposure.

## Implemented pipeline

- The pinned dots.mocr proposer reads every full page with its frozen prompt. The
  deterministic assembler preserves transaction descriptions, reference cells, printed
  monetary columns, boxes and locators. Headerless tables and complete bare HTML are
  supported conservatively; malformed layouts remain explicit failures.
- The pinned Qwen reviewer sees the full page image and every proposed row. It is
  **instructed to transcribe the description from the image** before its verdict.
  The request preserves declared schema property order. A confirmation with a different
  observed description is invalid. This contract detects contradictions; it does not
  prove that the reviewer read independently or correctly.
- Pages with more than fifteen proposals use review batches of fifteen stable IDs.
  Every batch receives the same full page image and all candidates as context. One
  subsequent page pass owns missing-row additions and metadata. Incomplete coverage,
  a malformed response or any truncated batch holds the whole page. Discovery overflow
  also remains held; batching is not a claim that every possible dense page will fit.
- A malformed or truncated proposer response can receive one bounded recovery
  generation: two fixed overlapping horizontal crops. Every original and crop proposal
  remains available for explicit review against the full image. No value-based
  deduplication occurs. A crop that is exactly RGB white in the decoded source image
  can be certified empty by deterministic pixel equality; near-white and threshold
  heuristics are not accepted. The initial full-page call and any initial failure are
  always retained. Both crop regions must be accounted for before recovery succeeds.
- Corrections repeat the exact original field value. The merge retains full original
  and corrected rows and raw patches. Redundant unchanged patches are allowed only
  beside a genuine, valid correction; an unchanged-only correction still fails.
  Reviewer additions remain single-reader evidence. Rejected and unresolved rows are
  retained for inspection and cannot enter the admitted ledger.
- After all model reviews and a consistent merge of reviewed period fields,
  `vlm/dates.py` resolves an originally null ISO date only when the reviewed
  `date_text` and period admit exactly one calendar interpretation. Numeric month/day
  and day/month alternatives are considered without a locale preference; ambiguous,
  impossible or out-of-period readings stay unresolved. The resolver never guesses a
  current year, consults a native baseline or overwrites an explicit model date.
  Original records, printed date text and raw reviewer states remain unchanged.
  Separate audit evidence records the reviewed period, source text, candidate dates
  and resolution used by the gate.
- The existing gate and reconciliation perform arithmetic. The models neither compute
  metrics nor classify transactions. Printed period, balance anchors, totals, counts,
  fees, interest, daily balances and signed reversal columns reach the source boundary.
- Phase 3.1a offers reviewed `StatementMarkdown` to an existing deterministic reader,
  accepting its report only when every source field and ordered row matches. Phase
  3.1b builds the same report through `analysis.pipeline.analyze_statement` for unmatched
  layouts. Both use the existing metric, ADB, classification and serialization code.
  Multiple accounts remain held pending separate support.
- Explicit reviewer currency is labeled `model_extracted`. Missing currency can use
  an existing `institution_default` only after a deterministic parser reproduces every
  other reviewed source field. A parser's printed, product or jurisdiction currency
  obtained only from unreviewed Stage A text cannot fill the gap; schema defaults are
  also refused. Missing or conflicting denomination evidence otherwise holds the result.

Every model request, response, prompt and rendered image is content-addressed. Manifests pin
model revisions, schema semantics and order, templates, rendering, recovery/batching
rules, source files and currency-reader implementations. Date resolution is pinned by
version 1, policy `unique_reviewed_period_date_v1` and its source hash. Failed calls are receipted;
transport retries are disabled. Partial runs resume from recorded evidence instead of
silently obtaining another reading. HTTP clients ignore environment proxies and refuse
redirects. Historical receipts keep the source hashes that actually produced them.

Current versions are schema 6, prompt 8, review merge 4, gate 7, review batching 1,
proposal recovery 2, currency resolver 2, date resolver 1, adapter 3 and pair contract 1.
The date fix did not change schema 6, prompt 8 or gate 7. Global OCR stage 5 and
extraction schema 3 were not bumped.

## Web application and held results

Force visual OCR bypasses native-text inspection at both upload intake and the worker,
as well as native parsing and the legacy OCR ladder. Structural PDF validation still
checks encryption, size and page limits and stores an honest, unclassified profile.
The old visual reader remains behind an explicit comparison flag. Automatic fallback
is configurable and starts with the narrow parser-failure trigger.

The existing background queue reports page, crop, review-batch and discovery progress.
One worker slot deliberately serializes GPU work; concurrency was not increased without
serving-capacity evidence. Pair caches are separate from native extraction and retain
review evidence. Exact-PDF authorization is checked before cache access, and publication
policy is evaluated on every analysis.

A held result has no published metrics. **Review extraction** shows final reviewed text
and a separate, escaped view of retained originals, corrections, effective rows and
specific page/gate reasons. Rejected and unresolved evidence is marked as not admitted;
showing it does not turn it into a ledger. Source viewing and text export remain usable,
while metric actions stay disabled and JSON/CSV/XLSX downloads refuse the request.
Previous job metrics are cleared when a held result is loaded.
Dates resolved by the platform are displayed separately from the retained reviewer
output, so deterministic date completion is not presented as a model correction.

The default remote customer fence is closed and the default policy is `always_review`.
The evaluation server is authorized only for the exact two selected PDFs, uses the
narrow trigger and retains `always_review`. General publication policy, a broad
fallback trigger and production hosting remain owner decisions.

## Synthetic verification

The three supplied fixtures were used for live wiring, without a corpus replay. They
lack the complete printed source anchors needed for publication; the dense fixture
also contains impossible dates. Their gate refusals are expected. Successful metric
production is verified separately with fabricated complete source evidence and mocked
transport, rather than claimed from incomplete live fixtures.

The dense page exposed an anchoring problem: early prompts produced incorrect
confirmations, then correct observations paired with contradictory confirmations.
Those contradictions were held. After correcting wire schema order, the bounded dense
check returned sixty corrections restoring the complete synthetic descriptions, with
no review errors or truncation. This is a fixture result, not proof of customer quality.

A separate short-fixture recovery check injected a failed original proposal and then
made actual crop/reviewer calls. The exact-white lower region was certified empty;
the remaining crop proposed six rows and the full-page reviewer confirmed all six
complete descriptions. There were no review errors. Because the initial failure was
injected, this check proves the recovery wiring, not a fresh end-to-end initial read.

Reviewer repeatability was measured on that actual six-row synthetic request. The
original request body was sent **twice more through fresh HTTP calls**, without an
extraction-cache substitute. All three responses finished normally, confirmed six rows,
and used 587 completion tokens. Their exact model-content bytes and parsed JSON were
identical. The finding applies to this request only and does not establish general
determinism or accuracy.

The 1540-pixel renderer was selected on the dense fixture: it returned complete layout
JSON, while the bounded 300-DPI comparison produced repetitive SVG and exhausted the
12,000-token budget. Rendering, model revisions and generation settings are pinned.

## Final two-statement evidence: v8 model run and v9 date replay

The v8 model run supplied the frozen requests and responses. The v9 check replayed all
52 logical calls from those exact saved bytes, with zero unmatched requests and zero
chat POSTs. Each derived cached receipt links its original v8 receipt; all 265 parent
content-addressed blobs and original document bytes were verified. Four read-only
model-pin GETs were made. No new model reading was obtained.

The final run used the same authorized US Bank and Regions documents, twelve pages in
total. No additional customer statement or alternative model was introduced. It made
52 actual model calls: 18 proposer and 34 reviewer calls. Four proposer responses were
non-stop/truncated; no reviewer response was truncated. Every one of the 275 assembled
Stage A candidates received exactly one explicit reviewer verdict, with its original
values retained.

| Document | Pages | Stage A candidates | Agreed | Corrected | Unresolved evidence | Result |
|---|---:|---:|---:|---:|---:|---|
| US Bank | 4 | 33 | 10 | 23 | 5 | Held; no analysis |
| Regions | 8 | 242 | 197 | 45 | 0 | Held; no analysis |
| Total | 12 | 275 | 207 | 68 | 5 | No metrics published |

The five unresolved US Bank records are reviewer-only additions on a held page; they
are not omitted Stage A verdicts. US Bank has two pages with errors and one effectively
truncated page. Regions has one page with errors/truncation and twenty extracted
daily-balance snapshots. No usable, admitted daily ledger was produced for either
document. A snapshot count is not proof of ledger completeness.

The v9 deterministic step resolved all **18 US Bank and 197 Regions null dates**:
**215 resolved, zero unresolved**. Each had one valid interpretation of its reviewed
printed date within the consistently reviewed period. `date_unparsed` was removed
from both gate results. Canonical bytes of raw `row_evidence` and `field_evidence`
remain identical to v8; date attribution is separate. These are platform resolutions,
not new reviewer corrections, and they do not remove the other admission failures.

Local deterministic corroboration found all four US Bank period/balance anchors
matching its native baseline. Three Regions anchors matched; the ending balance
differed. These are comparisons between readers, not judgments against source pixels.
No source value or missing date was repaired from a baseline, and no baseline result
was used to override a visual gate refusal.

The final v9 gate reasons are:

- US Bank: `anchor_disagreement`, `proposal_invalid`, `currency_conflict`,
  `sum_mismatch`, `summary_mismatch`.
- Regions: `anchor_disagreement`, `currency_conflict`, `proposal_invalid`,
  `direction_unknown`, `duplicate_row`.

Repeated reviewer metadata disagreed on the bank field in both documents and on
`stated_total_credits` in US Bank. The Regions ending-balance difference is against
the native baseline, not a disagreement between its reviewed metadata pages.

The three judgment questions in handoff section 6 remain unpassed:

1. **Correction benefit:** source-page review has not established that the final
   corrections are clearly net positive. Counts and native-text agreement cannot
   establish that result.
2. **Publishable fields:** extraction retained period and balance evidence, but both
   documents failed admission and neither yielded a usable admitted daily ledger.
3. **Verbatim descriptions:** synthetic checks and local native corroboration provide
   evidence, but no completed pixel-grounded customer-description judgment is claimed.

No hosted-model visual judgment was performed. The diagnostic tool-context exposure
is disclosed above and does not constitute a source-page quality review. The private
source viewer supports row/page inspection and verdict export
without another model call, but its existence is not a completed human review. No
confidence band is calibrated or promoted, and no production readiness is claimed.

Earlier trial receipts remain immutable. That trial used schema 5/prompt 6 and held both
documents with 33 corrected, 118 added and 58 unresolved records. Subsequent assembly,
schema-order, batching and recovery fixes are recorded as new evidence; the final run
does not retroactively change the earlier result or its limitations.

## Validation and operation record

The affected-module regression run passed 700 tests before the final app fixes. A
subsequent focused run passed 98 checks after those fixes, with one corpus test
deselected. These overlapping counts are not additive. Coverage includes source-field
preservation, gate refusals, signed reversals, ADB/classification through the existing
analysis layer, per-candidate coverage, immutable corrections, recovery lineage,
truncation slots, cache corruption, authorization, forced-upload native bypass and
held-result export restrictions.

The date-resolution change passed 102 focused date, gate, pipeline, adapter and UI
checks, followed by 121 static and application-boundary checks. These runs overlap the
earlier suites and must not be summed. Tests cover null-only completion, calendar and
period boundaries, month/day ambiguity, preserved explicit dates, immutable reviewer
evidence and separate UI attribution. The actual saved-response replay resolved the
dates without changing model evidence; both documents still failed admission.

After the v9 evidence was imported, the restarted local app answered HTTP 200. Both
authorized PDFs were submitted through actual forced-upload HTTP requests and
completed from the v9 pair cache with **zero additional model calls**. Both remained
held, retained review evidence and separate date attribution were present, analysis
was absent, and all three metric-download formats returned 404. Parent evidence lineage
was preserved during import.
Final operational checks returned HTTP 200 from the local app and both model endpoints.
Browser inspection used fabricated held data only and checked the review heading,
refusal reasons and collapsible evidence; it did not expose customer content.

GPU cleanup and restart verification completed after the final calls. All six tracked
old process identities were gone, with no zombies remaining. Both model services were
restarted with the original revisions and serving arguments and answered healthy,
idle status with zero running or waiting requests. Request/output logging and prefix
caching remained disabled. The Jupyter process identity and port were unchanged.
Customer PDFs were not copied to remote storage; only in-memory page requests were
sent. No further inference is planned for this evaluation.
The later v9 replay made only the read-only model-pin GETs described above, so this
cleanup remains valid; a second model restart was unnecessary.

No 16-statement corpus replay occurred. The requested cold cache
`.claude/recovery/webapp_data_train12_cold` is unavailable in this checkout and was not
recreated or written. Narrow/broad trigger frequency therefore remains unavailable,
not zero. Broad fallback was not silently selected.

Full evidence and appended run ledgers remain in the ignored local
`.claude/phase31-private/` tree. The original final model run is under
`real-judgment-20260921/check-v8/7ecdcca25a0e485f97bcd5dc4b92b2bf`; its saved-response
replay evidence and `webapp-evaluation-v9.private.json` record the subsequent checks.
Original and derived evidence remain separate. The Windows ledger named in the
handoff is not mounted in this workspace.
The accepted dots.mocr licence is recorded as the requested clerical row in
[LICENSES.md](../moneythumb-replacement/phase3/LICENSES.md); model and licence choices
were not reopened.
