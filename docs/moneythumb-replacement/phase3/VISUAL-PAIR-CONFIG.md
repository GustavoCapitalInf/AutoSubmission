# Phase 3.1 visual fallback runtime contract

Implementation and the bounded evaluation are complete, but reading-quality acceptance
remains unpassed. Exact-byte replay of saved model evidence resolved 215 dates without
new chat requests; both final statements remain held for other gate reasons. See the
[implementation and evaluation record](../../agent-handoffs/PHASE3.1-IMPLEMENTATION.md).
The local evaluation app supports reviewing the two specifically authorized PDFs;
it is not a general customer rollout.

Start with [the example configuration](../../../.env.visual-pair.example), which keeps
customer transmission closed and every extracted result held for human review.
Force visual OCR selects the pair even when automatic fallback is disabled. It skips
native text at upload intake and in the worker, native parsing and legacy OCR. Encryption,
file-size and page-count checks still run without reading the text layer.

| Variable | Default | Meaning |
|---|---|---|
| `OCR_ALLOW_VISUAL_PAIR` | `0` | Set `1` to enable automatic fallback in Auto and Deterministic modes. |
| `OCR_VISUAL_PAIR_FALLBACK_TRIGGER` | `narrow` | `narrow`: no deterministic analysis; `broad`: also any non-validated analysis. Broad is implemented but not selected. |
| `OCR_VISUAL_PAIR_LEGACY_VISUAL` | `0` | Set `1` only for explicit comparison with the former visual OCR rung and its original preflight. |
| `VISUAL_PAIR_PROPOSER_URL` | loopback port 18013 `/v1` | dots.mocr transport. |
| `VISUAL_PAIR_REVIEWER_URL` | loopback port 18022 `/v1` | Qwen reviewer transport. |
| `VISUAL_PAIR_EXECUTION_CLASS` | `remote_paid` | The only deployment supported in this phase; loopback can be a remote tunnel. |
| `VISUAL_PAIR_TIMEOUT` | `900` seconds | Per-request timeout, without automatic transport retries. |
| `VISUAL_PAIR_PRIVATE_ROOT` | Absolute home-directory path `.local/share/bank-statement-analysis/phase31-private` | Private evidence root outside the checkout. Relative paths and paths resolving inside the checkout are refused. |
| `VISUAL_PAIR_REVIEW_POLICY` | `always_review` | Hold all results; `admit_gated` requires an authorized publication policy or explicit synthetic checks. It never bypasses the gate. |
| `VISUAL_PAIR_CUSTOMER_DOCUMENT_SHA256_ALLOWLIST` | absent | Optional comma-separated lowercase SHA256s restricting an authorized evaluation to exact PDF bytes. Empty or malformed values fail closed. |

The remote customer fence requires both settings and the current environment to
contain `VISUAL_PAIR_REMOTE_CUSTOMER_DATA_OPT_IN` with the exact value
`I_AUTHORIZE_CUSTOMER_DOCUMENTS_TO_REMOTE_VISUAL_PAIR`. The example does not set it.
The upload worker always declares customer scope, including cache hits. Only explicit
fixture tooling can declare synthetic scope. A local-execution declaration cannot
bypass the fence: model servers do not attest whether loopback traverses a remote tunnel.
The HTTP client disables environment proxies and redirects.

The document allowlist narrows the remote opt-in; it never replaces it. Both loaded
settings and current environment must permit the actual PDF bytes before extraction
cache access. The worker converts its uppercase storage digest to the allowlist's
lowercase form without changing the existing document-storage convention. Document
hashes and opt-in configuration belong in private runtime files.

The local evaluation server uses the exact two-document allowlist, narrow fallback and
`always_review`. Both approved PDFs completed actual forced uploads from the v9 cache
with no additional model calls. Held evidence and platform date attribution are
available for review; no analysis or metric export was published. Other documents
remain outside this evaluation authorization.
A new pair request must pass authorization even when its extraction is cached.

## Reading and review boundaries

Both model revisions, generation parameters and the 1540-pixel long-edge renderer are
pinned. The dense synthetic comparison selected that renderer after 300 DPI exhausted
the proposal budget with repetitive malformed output. This is a wiring finding, not
customer-quality validation.

Pages with more than fifteen candidates use batches of fifteen stable candidate IDs,
then one pass owns missed rows and page metadata. Every review uses the full page image.
Any incomplete batch or discovery response holds the page. The schema's declared wire
order places source description observation before verdict/correction output, and
contradictory confirmations are refused.

A malformed or truncated proposer response receives at most one recovery generation:
two fixed overlapping horizontal crops. Original failures, every candidate and crop
geometry remain in the receipt; no duplicate is silently removed. Both regions require
complete evidence. A crop whose decoded source pixels are all exactly RGB 255/255/255
may instead carry a deterministic empty-region proof. Near-white pixels, darkness
thresholds and variance heuristics cannot grant that proof. The full page always goes
to Stage A first, and Stage B always reviews the full page image.

Missing currency uses `currency_missing`; differing reviewed denominations use
`currency_conflict`. Currency resolution runs even when another check has failed,
and a successful resolution clears only `currency_missing`.
Missing currency remains held unless an existing deterministic institution rule exactly
reproduces the other reviewed Statement fields. Only `institution_default` is reusable
for this purpose. Printed, product and jurisdiction currency derived solely from raw
Stage A text requires reviewed denomination evidence; `schema_default` cannot supply it.
An explicit reviewer currency remains `model_extracted`.

Page truncation or review failure produces `page_unresolved` on that page. Reviewed
rows on other pages retain their original states. Incomplete documents retain row
validation but defer statement-wide sums, summaries, anchor derivation and direction
inference across gaps. Metrics remain withheld until the complete document passes.

Repeated bank/name headers compare formatting-insensitively, and account identifiers
compare all visible characters, including compatible masked/full restatements. The
earliest opening and latest closing are the statement anchors. A different continuation
balance requires a matching reviewed running balance or adjacent page endpoint;
unsupported differences remain `anchor_disagreement`. Periods, totals, counts, fees
and printed averages must agree across restatements. Raw field evidence is retained.

After all model reviews and a consistent reviewed statement-period merge, the platform
may complete a null row date from reviewed `date_text` only when exactly one valid
calendar interpretation lies in that period. It considers numeric month/day and
day/month forms without choosing a locale, and it does not guess the current year.
Ambiguous interpretations stay unresolved; explicit model dates are never overwritten.
Native PDF text and baseline results are not inputs. Original row records and raw
reviewer states stay intact; separate `date_resolution` evidence records the period,
printed text, candidate dates and selected result before the gate runs.

## Caching, review and publication

Pair extraction has its own cache partition containing revisions and hashes of prompts,
ordered/semantic schemas, renderer, assembler, gate, integrity rules, recovery, batching
and adapter. Currency-reader source changes also rotate the partition. Date resolution
pins version 1, policy `unique_reviewed_period_date_v1` and the resolver source hash.
Existing disabled
partitions are unchanged; global OCR and extraction-schema versions were not bumped.
Evidence survives cache restoration with checked digests. Admission policy is applied
again on every analysis; pair results do not reuse the text-only analysis cache.

**Review extraction** remains available for held results. It shows reviewed text plus
escaped originals, corrections, effective rows and named refusal reasons. Unresolved
and rejected records are labeled as not admitted. This presentation never inserts held
rows into analysis. Text/source actions stay available; metric actions and server-side
JSON/CSV/XLSX downloads remain unavailable when there is no admitted analysis. A review
viewer verdict does not authorize publication or change a saved model result.
Platform-resolved dates are attributed separately from reviewer output. Their presence
does not relabel an unchanged model row as corrected or authorize its admission.

`gate.reasons` remains the compatibility list of distinct codes. Occurrences are
recorded before deduplication in `gate.reason_occurrences` with code, source, field
when applicable, and page. `gate.reason_counts` reports each code's total, counts by
page, and document-level count. Row/field failures count separately; duplicate-row
counts identify each later offending row once. Aggregate checks use a null page
instead of guessing a location. The review UI and CLI expose these counts; older
audits without occurrence records show counts as unavailable.

The agreement score and raw row counts are provisional. They are not calibrated
probabilities, and the bounded evaluation did not establish net-positive customer
corrections. `always_review` remains the default even when every deterministic check
passes. Publishing metrics, choosing broad fallback and selecting production hosting
remain separate owner decisions.

Requests use the existing background queue and page/stage progress. One worker slot
serializes GPU jobs; increasing concurrency requires separate capacity and repeatability
measurements. Pair evidence stays under the external absolute private root;
HTTP upload handlers do not wait for GPU completion. Private judgment outputs
use the same external root by default. Repository-local output paths are refused.
Webapp uploads, cached extractions and audit state default to its `webapp_data`
child. `WEBAPP_DATA_DIR` and explicit storage overrides must also be absolute and
outside the checkout. Existing storage is not opened or migrated automatically.
