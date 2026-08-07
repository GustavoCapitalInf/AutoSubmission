# H-3 — Telemetry record schema and emission architecture

Agent C (HARBOR), 2026-08-06. Branch `wave2-proof`.
**Status: BUILT.** Phase 1 (design) reviewed and approved; phase 2 shipped as
`1eeaeff`; the `deferred` outcome class added in DSC-1b. §12 records the
rulings; this document remains the contract.

This document is DSC-2's data contract (WAVE2_BRIEF §6 checkpoint 2). It defines
one record shape, where every field comes from, the one pipeline seam it needs,
how it is stored on both paths, and the tests that keep it honest.

---

## 1. What H-3 is, and what it must never become

H-3 answers one question per statement — *what happened to this document, and
what did it cost* — so that the deterministic-coverage rate and its failure
taxonomy are a query rather than an afternoon of log archaeology.

It is **write-only side-band**. Nothing in a telemetry record is ever read back
by analysis, and no analysis output changes because telemetry is on. That is not
a style preference: the corpus gate is byte-identical merge authority, so any
observable change to a report is a stop-the-line failure. §10 makes it a test.

---

## 2. Schema invariants

These are properties of the record, each with a planned test (§10).

**I1 — Non-sensitive by construction.** A record carries hashes, registry ids,
enum codes, counts, and timings. It never carries: customer or business names,
account numbers or fragments, monetary amounts, dates from the statement,
transaction descriptions, statement text, or **filenames**.

Two consequences that are easy to get wrong and are therefore called out:

- **No filename.** `Bank Statements/.../SALON BARK LLC March.pdf` is customer
  data in the path. Documents are identified by `content_sha256` only. A run
  that needs to map hash → file keeps that mapping in its own gitignored
  artifact (DSC-1's concern, not the record's).
- **No extracted bank label.** `parser_id` (e.g. `chase_export`) is a constant
  from our registry and is safe. `Statement.bank` is *read out of the document*
  — on the LLM path for an unknown institution that string can be a business
  name. The record carries `parser_id`, never `statement.bank`.
- **No exception messages.** Only the exception **class name**. A traceback
  message routinely contains a fragment of the document.

**I2 — One shape, two backends.** The identical JSON object is what SQLite
stores and what JSONL writes. SQLite adds indexed columns *projected from* the
record; it never holds a field the JSON lacks. A round-trip test asserts
equality both ways.

**I3 — Append-only.** Telemetry is evidence. The table carries the same
UPDATE/DELETE triggers as `audit_log`; JSONL is opened `"a"`.

**I4 — Emission cannot fail a job.** Every emit path is wrapped so that a
telemetry defect degrades to a missing record, never a failed analysis. A
record that could not be written is a lost measurement, not a lost result.

**I5 — Honest absence.** Every field distinguishes *unknown* from *zero*.
`truncation.assessed = false` is not "0 truncated pages"; `cost.amount = null`
is not "$0.00"; `dispatch.source = "cached"` is not "unclaimed". This is the
same fail-closed discipline the financial core already uses.

---

## 3. The record

`telemetry_version: 1`. JSON, UTF-8, one object per statement per run.

```jsonc
{
  "telemetry_version": 1,
  "record_id": "b1f0…",             // uuid4, idempotency key
  "run_id": "2026-08-06T21:04:11Z-a1b2c3",   // groups one batch/discovery run
  "emitted_at": "2026-08-06T22:41:07.881Z",  // utc_now_iso()
  "emitter": "batch",                        // batch | webapp
  "job_id": null,                            // webapp only

  "document": {
    "content_sha256": "0CBD2AD8…",           // UPPER hex, ocr.inspect.content_sha256
    "byte_size": 481223,
    "page_count": 4,
    "classification": "scanned",             // digital|scanned|mixed|unknown
    "valid_pdf": true,
    "encrypted": false,
    "malformed_page_count": 0,
    "likely_account_count": 1,               // ADVISORY (O-1)
    "duplicate_of_prior_record": false       // same content_sha256 earlier in this run
  },

  "source": {
    "path": "local_tesseract",               // native|local_tesseract|visual|none
    "model": "local-tesseract-ocr",          // StatementMarkdown.model verbatim
    "page_count": 4,
    "truncation": {
      "assessed": true,                      // page_integrity non-empty
      "truncated_page_count": 0,
      "truncated_page_indices": [],          // 0-based
      "signals": []                          // O-3 signal codes, deduped
    }
  },

  "dispatch": {
    "source": "live",                        // live|cached|unavailable
    "outcome": "claimed",                    // claimed|ambiguous|unclaimed|parser_exception|null
    "parser_id": "columbia",
    "score": 0.75,
    "candidates": [["columbia", 0.75]],      // post-supersedes claimants
    "attempted": [],                         // detected, then parse() -> None
    "exceptions": [],                        // W3-1: [id, "detect"|"parse", "ValueError"]
    "scores": [["columbia",0.75],["regions",0.125]],  // §4
    "scores_floor": 0.0,
    "scores_capped": false,
    "registration_count": 46
  },

  "stages": {
    "preflight": {"ms": 41.2,   "cache": "bypass"},
    "ocr":       {"ms": 18734.0,"cache": "miss"},
    "analysis":  {"ms": 612.9,  "cache": "miss"},
    "report":    {"ms": 22.4,   "cache": "hit"}
  },

  "models": {
    "calls": [
      {"stage":"ocr","model":"<ocr model id>","purpose":"visual_ocr",
       "calls":4,"prompt_tokens":null,"completion_tokens":3871}
    ],
    "cost": {
      "currency":"USD",
      "amount": null,
      "complete": false,
      "price_table_version":"2026-08-06.1",
      "unpriced_models":["<ocr model id>"]
    }
  },

  "outcome": {
    "class": "validated",                    // validated|review|withheld|failed|deferred
    "reason": "approved",                    // short enum code, §6
    "escalated": false,
    "error_type": null,                      // exception class name only
    "fallback_reason": null                  // §5.3
  }
}
```

### 3.1 Field provenance

Every field is read from something that already exists. Nothing is recomputed by
telemetry except the near-miss vector (§4) and the timings.

| Field | Source | Notes |
|---|---|---|
| `document.*` | `ocr.inspect.DocumentProfile` (O-1) | `inspect_pdf` never raises; batch must start calling it |
| `source.model`, `source.page_count` | `StatementMarkdown.model` / `len(pages)` | |
| `source.path` | derived from `model` | `native-pdf-text*` → native; `local-tesseract-ocr` → local_tesseract; else visual. The webapp's `on_stage` rung is the same fact but is unavailable on the CLI, so `model` is the single authority both paths share |
| `source.truncation.*` | `doc.truncated_pages`, `doc.page_integrity` (O-3) | Correct on cache hit and miss — D-3b round-trips `page_integrity` |
| `dispatch.outcome/parser_id/score/candidates/attempted` | `analysis.parser_registry.Dispatch` (R-3 §4.1) | via the §5 seam |
| `dispatch.exceptions` | `Dispatch.exceptions` (W3-1) | `[parser_id, stage, ExceptionClass]`; class names only, per I1 |
| `dispatch.scores` | `detection_report(markdown)` | §4 |
| `stages.*.ms` | `perf_counter()` in the emitters | |
| `stages.*.cache` | `CacheResult.cached` | §7 |
| `models.calls[].completion_tokens` | `PageText.completion_tokens` (visual rung, live reads only) | `null` otherwise — never estimated |
| `outcome.class` | serialized analysis payload | §6 |
| `outcome.escalated` | `Report.escalated` | |

---

## 4. Near-miss scores: the full non-zero vector, capped at 12

**Decision: record every registration whose score is `> 0.0`, best first, capped
at 12 entries with `scores_capped` marking the cap. Do not record zeros.**

The brief framed this as "full vector vs top-N above a floor", with cost as the
argument against the full vector: 46 registrations × 3,506 documents = 161,276
pairs. **Measured, that cost does not exist**, because scores are sparse. On four
corpus documents spanning the layout range:

| Document | chars | non-zero scores of 46 | near-misses in (0, 0.5) | `detection_report` |
|---|---|---|---|---|
| `Chase/Chase Mar.pdf` | 23,312 | 4 | bmo 0.167, regions 0.125, navigant 0.1 | 5.2 ms |
| `Others/Altana/Altana april 26.pdf` | 61,109 | 7 | midflorida 0.167, secu 0.167, bank_of_america 0.125, pnc 0.125, regions 0.125, relay 0.1 | 11.7 ms |
| `Misc/Columbia May 26 complete.pdf` | 10,622 | 2 | regions 0.125 | 2.5 ms |
| `Regions/Regions.pdf` | 7,455 | 2 | navigant 0.1 | 1.8 ms |

So the "full vector" is ~2–7 pairs per document, not 46: roughly **14,000 pairs
across the whole discovery archive**, a few hundred KB. Dropping zeros loses
nothing — a zero means "no evidence", it is identical for every registration
that has it, and the set is exactly `registration_count` minus what is listed.

Why not a 0.1-style floor: R-3's scorer produces near-misses by a computed
formula (`0.5 × corroborating_hits / n`), so the interesting DSC-2 signal — "this
document almost matched `bmo`" — lives precisely in the small values a floor
would discard. The measured minimum here is 0.1 and it is meaningful (one
corroborating marker of ten). The cap at 12 is a safety valve for a pathological
document, not a policy; if `scores_capped` is ever true on real data that is
itself a finding.

**This is what makes "almost matched" rankable for DSC-2**, which is the property
`R3_DETECTION_FINDING.md §6` says the weak-but-nonzero score exists to provide:
telling "a statement from a registered bank whose layout drifted" apart from
"never heard of this institution".

---

## 5. The pipeline seam

### 5.1 The problem, stated precisely

`Dispatch` is created at `analysis/pipeline.py:294` (`dispatch = resolve(markdown)`)
and is **purely internal** — not on `Report`, not serialized, not returned. R3_RFC
§4.1 designates it as H-3's data source, so H-3 needs exactly one way to observe
it.

A second fact, which the brief's design inputs do not anticipate and which I want
on the record: **`Dispatch` does not carry near-miss scores.**
`_surviving_claimants` keeps only detections with `score >= 0.5`, so `candidates`
is claimants-only. The near-miss vector is not reconstructible from `Dispatch`
and must come from `detection_report(markdown)` (§4) — which costs a second
detect sweep of 1.8–11.7 ms and **needs no pipeline change at all**, since
telemetry can call it directly.

### 5.2 Proposed diff — one keyword-only callback, 4 lines

```diff
--- a/analysis/pipeline.py
+++ b/analysis/pipeline.py
@@
-def analyze_markdown(markdown: str, *, settings: Settings | None = None,
-                     parse_mode: str = "auto") -> Report:
+def analyze_markdown(markdown: str, *, settings: Settings | None = None,
+                     parse_mode: str = "auto",
+                     on_dispatch: Callable[[Dispatch], None] | None = None) -> Report:
@@
     model_used = settings.model
     dispatch = resolve(markdown)
+    if on_dispatch is not None:
+        # Write-only side-band (H-3). Contract: the callback must not raise and
+        # must not mutate; nothing here reads it back.
+        on_dispatch(dispatch)
     deterministic_stmt = dispatch.statement
```

Plus `from typing import Callable` if absent. **That is the entire pipeline diff:
one keyword-only parameter defaulting to `None`, two statements, one import.**
`Report` is untouched, no existing call site changes, and with no callback passed
the function is byte-identical in behaviour.

The "must not raise" contract is discharged on the telemetry side, not by a
`try/except` in `pipeline.py` — swallowing exceptions inside analysis would be new
control flow in a protected file. The collector wraps its own body (I4) and §10
tests that it cannot raise.

### 5.3 Alternatives considered and rejected

| Shape | Why not |
|---|---|
| **`Report.dispatch` field** | `Dispatch.statement` holds the parsed `Statement` — every amount and description. Hanging it off `Report` means any generic walker (`asdict`, a future serializer, a debug dump) leaks the full financial record into whatever consumes it. It also widens a type shared by serialization, the benchmark harness, and both gate oracles. A 4-line callback risks none of that. |
| **Telemetry calls `resolve()` again** | Re-runs the winning parser (18–28 ms measured, real parse work), and — worse — it is a *different* dispatch than the one the report came from. Telemetry must describe the run of record, not a re-enactment. |
| **`detection_report()` alone, no seam** | Recovers scores but not `attempted` (only observable inside `resolve`'s parse loop) and not post-`supersedes` `candidates` without duplicating registry logic in the telemetry module. Insufficient — but it is the right fallback for cache hits (§5.4) and the right source for §4. |
| **Extend `Dispatch` to carry all detections** | Cross-agent churn in R-3's just-merged core to save ≤12 ms. Not worth it. |

### 5.4 The cache-hit hole — declared, not papered over

D-3's analysis cache means that on a re-run **`analyze_markdown` is never called**,
so no `Dispatch` exists. The record then carries `dispatch.source = "cached"`,
`outcome`/`parser_id`/`attempted` null, and `scores` still populated (telemetry
can always call `detection_report` on the markdown it holds).

What survives on a cache hit: document facts, source/truncation facts, stage
timings, `stages.analysis.cache = "hit"`, and — critically — `outcome.class`,
because that is derived from the analysis payload, which the cache does return.
**The deterministic-coverage rate therefore stays computable on re-runs**; only
the parser diagnostics degrade. For DSC-2 tranche 0/1 this is a non-issue (a
first pass is all misses).

If Ocean wants complete parser telemetry on re-runs, the fix is to persist the
dispatch projection inside the cached analysis artifact — which changes the
cached payload shape and so requires an `ANALYSIS_STAGE_VERSION` bump and a D-3
module diff. I recommend **not** doing that in H-3: it couples telemetry to the
cache format for a benefit only re-runs see. Open question O-3 below.

---

## 6. Outcome classification

Four classes, evaluated in precedence order. Every input is already in the
serialized analysis payload, so the same mapping works identically on both paths
and on cache hits.

| Class | Condition | Meaning |
|---|---|---|
| `deferred` | the caller passes an explicit `deferred=<reason>` | work a tranche **chose not to do** — a scanned statement in an offline tranche. A statement about the run, not about the document (added DSC-1b) |
| `failed` | no analysis payload — exception, `analysis_error`, or `RuntimeError("no deterministic parser matched")` | **attempted, and errored** |
| `withheld` | payload exists and `metrics.average_daily_balance is null` | fail-closed: the platform refused to publish an authoritative value (this is exactly the corpus gate's WITHHELD) |
| `review` | `quality.corporate_use != "approved"` or `integrity.flags` non-empty | a number exists but needs a human |
| `validated` | everything else | `corporate_use == "approved"`, no integrity flags |

`deferred` exists so that **`failed` means one thing only: attempted and
errored.** Before it, a scanned document that tranche 1 deliberately skipped
landed in `failed` with a distinguishing reason, which made the headline
failure rate a function of which tranche you ran — and DSC-2 acts on "we did
not try" and "we tried and it broke" very differently.

It is reached **only** by an explicit declaration from the caller, never
inferred from an absent payload: inference would let a genuine failure hide as
a decision, which is the one thing this class must not permit. The reason
vocabulary is closed (`DEFERRED_REASONS`: `deferred_scanned`,
`deferred_visual_ocr`, `profile_only`) and an unknown reason raises, so a typo
cannot quietly become a new bucket. Deferred documents are excluded from the
deterministic-coverage denominator by class.

No storage change was needed: `telemetry.outcome_class` is plain `TEXT` with no
`CHECK` constraint, so the class vocabulary lives in the record, not the schema.

`outcome.reason` is a short enum code, never free text: `approved`,
`withheld_adb`, `integrity_flags`, `quality_needs_review`, `parser_ambiguous`,
`no_parser_matched`, `ocr_failed`, `invalid_pdf`, `encrypted`, `exception`,
plus the closed deferral vocabulary `deferred_scanned`, `deferred_visual_ocr`,
`profile_only`.

**Acceptance anchor** (`tests/test_telemetry_corpus.py`, corpus-marked). Run over
the pinned 109, the mapping reproduces the gate's split from a completely
independent code path — no oracle, no audit CSV, just the product's own
serialized payload:

| | Gate | Telemetry (measured) |
|---|---|---|
| WITHHELD | 3 | **3 `withheld`**, the same three statements |
| PASS | 106 | **100 `validated` + 6 `review`** |
| — | — | 0 `failed`, 109 `claimed` |

**Note the refinement, which the phase-1 draft got wrong.** `validated` is not
equal to the gate's PASS: the gate's PASS means "the audited values reproduce",
while `validated` additionally means "approved for corporate use". Six corpus
documents reproduce perfectly *and* carry an integrity flag (e.g. Columbia's
`missing_declared_statement_page`), so they are `review`. The classes are a
**finer partition** of PASS, and the test asserts exactly that: the withheld set
is the gate's three by name, nothing failed, and `validated + review == 106`.
Asserting a flat "106 validated" would have been asserting something untrue.

---

## 7. Cache freshness — consume `cache_hit`, do not duplicate it

Per Ocean's D-3 ruling 5. Findings:

- `JobStore.record_cache_hit` (`webapp/jobs.py:102`) writes
  `event_type='cache_hit'`, `job_id`, `detail={"stage","cache_key"}` — **webapp
  path only**. `artifact_cache.py` itself writes no audit rows, so a CLI run
  produces none.
- The audit row carries no `content_sha256`; document identity requires a join
  `jobs.document_id → documents.content_sha256`.

**Design:** the record's `stages.*.cache` is populated from `CacheResult.cached`,
which both emitters have in hand at zero cost and which works identically on both
paths. The `cache_hit` audit rows stay the webapp's authoritative event history
and are **not duplicated into telemetry**; the coverage tooling can join them by
`job_id` when someone wants the event timeline. This satisfies the ruling in the
direction it was aimed — no second writer of the same fact — while keeping the
CLI path from having a hole the webapp does not.

---

## 8. Storage

### 8.1 SQLite — schema v4 (webapp path)

`_MIGRATIONS[3] = _migrate_v3_to_v4`, `SCHEMA_VERSION = 3 → 4`, additive only,
matching D-3's v3 style.

```sql
CREATE TABLE IF NOT EXISTS telemetry (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id         TEXT NOT NULL UNIQUE,   -- idempotency
    run_id            TEXT NOT NULL,
    job_id            TEXT,                   -- FK-ish, nullable for CLI imports
    content_sha256    TEXT NOT NULL,
    emitted_at        TEXT NOT NULL,
    telemetry_version INTEGER NOT NULL,
    emitter           TEXT NOT NULL,
    outcome_class     TEXT NOT NULL,
    dispatch_outcome  TEXT,
    parser_id         TEXT,
    source_path       TEXT NOT NULL,
    record            TEXT NOT NULL           -- the canonical JSON of §3
);
CREATE INDEX IF NOT EXISTS idx_telemetry_run     ON telemetry(run_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_sha     ON telemetry(content_sha256);
CREATE INDEX IF NOT EXISTS idx_telemetry_outcome ON telemetry(outcome_class);
CREATE TRIGGER IF NOT EXISTS telemetry_no_update
BEFORE UPDATE ON telemetry BEGIN SELECT RAISE(ABORT,'telemetry is append-only'); END;
CREATE TRIGGER IF NOT EXISTS telemetry_no_delete
BEFORE DELETE ON telemetry BEGIN SELECT RAISE(ABORT,'telemetry is append-only'); END;
```

The typed columns are pure projections of `record` (I2) — indexed so the coverage
query never parses JSON for grouping, while `record` remains the single truth.

### 8.2 JSONL (CLI/batch path)

One record per line, `ensure_ascii=False`, `sort_keys=True`, appended. Default
`telemetry/<run_id>.jsonl` under a gitignored directory. **No SQLite import on
the batch path** — the writer is a plain file handle, so `batch.py` gains no
`webapp` dependency.

### 8.3 The module

New `telemetry/` package, HARBOR-owned per MERGE_PLAN:

```
telemetry/__init__.py     record dataclass + to_dict/from_dict, schema constant
telemetry/collect.py      DispatchCollector (the §5.2 callback), StageTimer
telemetry/emit.py         JsonlSink, SqliteSink, NullSink — one write(record) API
telemetry/prices.py       versioned price table (§9)
telemetry/report.py       the coverage command (§10)
```

Both sinks implement the same `write(record: dict) -> None`; emitters do not know
which they have. `NullSink` is the default, so telemetry is opt-in and a
misconfiguration degrades to silence.

---

## 9. Cost model — versioned estimates, never invented

Following PROTOTYPE_REVIEW item 3 (`analysis/universal.py`'s pattern: per-call
token telemetry with versioned price estimates and no invented prices).

Ground truth about what is countable today, from the survey:

- **There is no cost or token accounting anywhere in the repository.**
- The only token reader is `ocr/ocr_client.py::_completion_tokens`, used solely
  to feed O-3 truncation detection; the value is discarded after `PageText`
  construction and does not survive a cache round-trip.
- `analysis/extract.py` (the extraction LLM) captures no usage at all.

Therefore:

1. `models.calls[]` records **call counts**, which are always knowable: visual
   OCR = pages sent; extraction = 1, or 2 when `Report.escalated`.
2. `prompt_tokens`/`completion_tokens` are recorded **only where the platform
   actually reports them** (visual OCR, live reads) and are `null` otherwise.
   Never estimated from character counts.
3. `telemetry/prices.py` holds `PRICE_TABLE_VERSION` and per-model
   `(prompt_usd_per_1k, completion_usd_per_1k)` entries **only for models whose
   price we actually know**. A model absent from the table contributes nothing to
   `amount`, is listed in `unpriced_models`, and sets `complete = false`.
   `amount` is `null` when no call could be priced at all (I5).
4. The price table version travels in every record, so a later re-price is a
   recomputation over stored tokens rather than a lost measurement.

**Named limitation for Ocean:** true per-call cost for the extraction LLM needs
usage capture inside `analysis/extract.py` — a protected-file diff, out of H-3's
scope. Until then extraction cost is call-count-only. Recommended as a Wave-3
item rather than smuggled into this task.

---

## 10. Deterministic coverage in one command

```bash
python -m telemetry.report --jsonl telemetry/<run_id>.jsonl
python -m telemetry.report --sqlite webapp_data           # same output
python -m telemetry.report --jsonl … --by parser|bank_folder|source_path
```

Output (shape, numbers illustrative):

```
run 2026-08-06T21:04:11Z-a1b2c3 — 3,506 documents

deterministic coverage      2,412 / 3,506   68.8%     (dispatch.outcome=claimed)
  ambiguous                    41           1.2%
  unclaimed                 1,053          30.0%
outcome
  validated                 2,190          62.5%
  review                      388          11.1%
  withheld                     97           2.8%
  failed                      831          23.7%
source path   native 2,904 · local_tesseract 512 · visual 61 · none 29
truncation    assessed 573 · flagged 12 pages across 9 documents
cache         ocr hit 0 miss 3,506 · analysis hit 0 miss 3,506
cost          $— (unpriced: <ocr model id>)   calls: ocr 244, extraction 1,053
```

The SQLite path is one statement, no JSON parsing:

```sql
SELECT dispatch_outcome, outcome_class, COUNT(*)
FROM telemetry WHERE run_id = ? GROUP BY 1, 2;
```

Deterministic coverage = `claimed / total`, and the same script computes it from
either backend — the JSONL reader projects the same fields the SQLite columns
hold (I2), so the two must agree, and §11 tests that they do on identical input.

---

## 11. Test plan

| # | Test | Guards |
|---|---|---|
| T1 | Corpus document analyzed with and without `on_dispatch`: `report_to_dict` byte-identical | the whole side-band claim |
| T2 | Corpus gate GREEN with telemetry wired into both emitters | merge authority |
| T3 | Collector cannot raise — garbage/None/exploding sink still returns a Report | I4, the §5.2 contract |
| T4 | **Sensitivity**: emit for corpus documents, then assert the serialized record contains no filename, no `statement.bank`, no account number or fragment, no formatted amount from the statement, no transaction description; and that its key set is exactly the declared schema | I1 |
| T5 | Outcome mapping over the 109-document corpus = 106 validated / 3 withheld | §6 anchor |
| T6 | `scores` excludes zeros, is sorted desc, respects the cap, sets `scores_capped` | §4 |
| T7 | JSONL and SQLite produce identical coverage output from the same records; SQLite columns match their JSON projections | I2 |
| T8 | v3→v4 migration is additive; existing rows survive; append-only triggers fire | I3, D-3 compatibility |
| T9 | Cache-hit record: `dispatch.source = "cached"`, parser fields null, `outcome.class` still correct, `stages.analysis.cache = "hit"` | §5.4 |
| T10 | Unpriced model → `amount` null / `complete` false / model listed; priced model → exact arithmetic | §9 |
| T11 | Truncation fields correct on both a fresh read and a cache hit | O-3 × D-3b |
| T12 | `batch.py` emits without importing `webapp.*` (import-graph assertion) | §8.2 |

---

## 12. Rulings (Ocean, 2026-08-06) — phase 2 as built

All seven open questions were answered at the schema review; this section
records the answers and where each landed.

1. **Seam:** the 4-line callback APPROVED as proposed; the `Report.dispatch`
   rejection reasoning is now a comment in `analysis/pipeline.py` so nobody
   "simplifies" it back. Tests: no-callback byte-identity, and the collector
   contract lives with the collector.
2. **Near-miss vector:** APPROVED — every non-zero score, best-first, cap 12.
   Source is `detection_report`, admissible because `detect` is pure and total
   by the R-3 protocol contract, so the re-run provably reproduces the run of
   record (which is exactly what re-calling `resolve()` could not promise).
3. **Cache-hit hole:** ACCEPTED as a deliberate, documented degradation. No
   `ANALYSIS_STAGE_VERSION` churn for a re-run-only diagnostic.
4. **Sensitivity invariant:** APPROVED as specified. DSC-1 maintains its own
   gitignored hash→path map.
5. **Outcome anchor:** made a test (§6).
6. **Cost:** APPROVED. Extraction-LLM token capture is Wave-3 backlog
   (protected-file diff), logged rather than smuggled in.
7. **Storage:** APPROVED as specified.
8. **Default state: ON in both webapp and batch**, not null-sink-off — coverage
   measurement is the point, and the sensitivity invariant is what makes
   always-on safe. Kill switch: **`TELEMETRY_DISABLED=1`** (also
   `true`/`yes`/`on`), documented in the README telemetry section.
   **Retention:** append-only stands, no delete path this wave. The caveat
   Ocean asked to record: the append-only trigger will ABORT any run-scoped
   delete, so an expiry policy (D-7/Wave 3) has to arrive with a documented
   exception — either dropping and recreating the trigger inside the migration
   that introduces expiry, or moving expired rows by table swap. It is not a
   configuration change.

### Phase-2 implementation notes

- `source.path` for the six image-only corpus statements reads `none` in the
  offline anchor harness, because a document served from a committed OCR
  artifact has no `StatementMarkdown`. On the real emitters (`batch.py`, the
  worker) the ladder returns a document and the path is `local_tesseract` or
  `visual`. That is a property of the offline harness, not of the product.
- The coverage report is deliberately **ASCII-only**: it is printed by a CLI,
  and a console in a legacy code page must not be able to turn a measurement
  into a `UnicodeEncodeError` (the same trap H-0 hit in the gate).

## 13. Superseded: open questions as filed at the schema review

1. **Pipeline seam shape.** Approve the §5.2 callback (4 lines, `Report`
   untouched)? The alternative I rejected — a `Report.dispatch` field — would
   hang a full `Statement` (amounts, descriptions) off a widely-walked object;
   I consider that a sensitivity regression, but it is your call.
2. **Near-miss vector.** Approve "all non-zero scores, cap 12"? The measured
   sparsity (2–7 of 46) is what changed my recommendation from top-N to full.
3. **Cache-hit parser telemetry.** Accept the declared hole (§5.4), or do you
   want dispatch facts persisted into D-3's cached analysis artifact — which
   costs an `ANALYSIS_STAGE_VERSION` bump and a cross-agent diff for a re-run-only
   benefit?
4. **Filename exclusion.** I1 forbids filenames outright. DSC-1 will therefore
   need its own gitignored hash→path map to act on findings. Confirm that is the
   division you want.
5. **Extraction-LLM token capture** is out of scope (protected file), so
   extraction cost stays call-count-only this wave. Confirm as a Wave-3 item.
6. **Default-on or default-off in the webapp.** I propose `NullSink` by default
   with telemetry enabled explicitly (env var), so a webapp user never pays for a
   discovery feature. DSC-1 turns it on. Confirm.
7. **Retention.** Records are non-sensitive by I1, so I propose no expiry and no
   masking beyond the invariant. If discovery runs should self-expire, say so and
   it becomes a `run_id`-scoped delete — which conflicts with the append-only
   trigger, so I would need a documented exception.
