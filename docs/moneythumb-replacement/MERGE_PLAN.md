# Merge Plan & Agent Boundaries

Phase 1 deliverable. Author: Ocean. Date: 2026-08-06.

## 1. Agent ownership map

Five implementation agents, each owning a disjoint file set. Ocean owns architecture,
review, and the protected financial modules.

| Agent | Subsystem | Owned paths | Must NOT touch |
|-------|-----------|-------------|----------------|
| **HARBOR** | Validation & benchmark infra | `tests/` (suite-wide additions), CI config, `adb_forensic_audit.py`, `balance_forensic_audit.py`, comparison harness (new `benchmark/`), telemetry module (new), docs count fixes | `analysis/` production code, `webapp/` |
| **REEF** | Parser platform & extraction | `analysis/<bank>.py` (all 43), `analysis/pipeline.py` (dispatch/repair sections), `analysis/extract.py`, `analysis/bank_repairs.py`, new `analysis/money.py`/registry-of-parsers, per-parser tests | `analysis/adb.py`, `reconcile.py`, `metrics.py`, `transaction_classifier.py`, `serialization.py`, `webapp/`, `ocr/` |
| **LEDGER** | Schema, packages, financial surface | `analysis/schema.py` (v2 container), new `analysis/package.py`, `analysis/detect.py` views, `analysis/classification_registry.py` (additions, with Ocean review), new derivation modules (true-balance, ratios), `analysis/serialization.py` (additive fields only, Ocean-reviewed), export formatting | Protected module internals (MASTER_PLAN §4); `webapp/app.py` beyond deleting the extracted `_package_analysis`; `ocr/` |
| **DELTA** | Serving platform | `webapp/` (all), new storage/queue/cache modules, deployment config, API spec | `analysis/` (any), `ocr/` (any) — consumes interfaces only |
| **SONAR** | OCR & document intake | `ocr/` (all), `local_ocr_server.py`, `parse.py`, `sweep_ocr.py`, `triage_scan.py`, new forensics module | `analysis/` except the side-channel consumer touchpoints (`dates.py:228-242`, `wells.py:72`) which require a coordinated REEF handshake |

Shared-file protocol: `analysis/pipeline.py` is the one genuinely shared hot spot
(REEF owns dispatch/repairs; LEDGER's package work must not touch it; Ocean reviews
every diff to it). `analysis/serialization.py` changes are additive-only and
Ocean-reviewed, because its fail-closed nulling rules are protected.

## 2. Interface contracts (agreed before implementation starts)

1. **Parser protocol** (REEF → all): `detect(markdown) -> score`, `parse(markdown) ->
   Statement | None`; registry data drives order. RFC to Ocean before migration.
2. **Schema v2** (LEDGER → REEF, DELTA): `Document`/`Account` container wrapping the
   existing `Statement`; adapters guarantee protected modules see today's shapes.
   RFC to Ocean first — this is the highest-coordination change in the plan.
3. **OCR ladder** (SONAR → DELTA): `parse_statement(pdf_bytes, mode, force_ocr) ->
   StatementMarkdown` remains the single entry; worker stops owning any ladder logic.
4. **Cache/store** (DELTA → HARBOR): content-hash keys exposed so telemetry and the
   comparison harness reuse cached artifacts.
5. **Side channels** (SONAR ↔ REEF): versioned structured attachments replace
   `NFCU_TX|`-style comment strings; one coordinated PR pair.

## 3. Merge order

Ordering minimizes conflicts by sequencing the shared hot spots and letting
independent tracks run in parallel.

```
Wave 0  (immediately, parallel — no shared files):
  H-1 CI corpus gate            ← lands FIRST; every later PR is judged by it
  H-6 stale docs/fixture fixes
  D-2 hardening minimum (webapp only)

Wave 1  (parallel):
  R-1 hardcode purge            (parsers only; judged by H-1)
  D-1 persistence               (webapp only)
  O-1 unified preflight ladder  (ocr/ only; D-5 lands right after as a small DELTA PR)
  H-2 MoneyThumb harness v1     (new benchmark/ dir)

Wave 2  (sequenced through analysis/):
  R-2 shared utilities          → then R-3 registry/dispatch → then R-4 conformance
  D-3 cache + dedup             (parallel, webapp/storage side)
  O-3 truncation flags, O-4 side-channel schema (paired with REEF touchpoint PR)
  H-3 telemetry                 (hooks into pipeline seam AFTER R-3 lands)

Wave 3  (the big coordination point):
  L-1 schema v2 RFC → implementation with REEF (R-6) adapters
  D-4 concurrency/async         (parallel, independent)
  R-5 deterministic cross-check (after R-3)

Wave 4:
  L-2 package entity (consumes schema v2 + D-3 hashes; deletes app.py aggregation)
  L-3 underwriting derivations  (after L-1/L-2)
  L-6 typed exports             (after L-2)
  D-6 versioned API             (after L-2 shapes settle)

Wave 5 (P2 track):
  R-7 generic understanding · O-5 forensics · L-4 transfer matching ·
  L-5 registry expansion · D-7 full production posture · H-4/H-5 calibration & accuracy
```

Rules:
- **H-1 merges before anything else.** No analysis-layer PR merges without the corpus
  gate green.
- One wave-2+ PR in `analysis/pipeline.py` at a time; Ocean sequences.
- Schema v2 (Wave 3) is a merge freeze window for `analysis/`: REEF and LEDGER
  coordinate on a shared branch; DELTA/SONAR/HARBOR are unaffected.
- Protected modules: any diff → Ocean review + full forensic audit attached to the PR.
- Byte-identical corpus proof required for R-2/R-3/O-1/O-2 (pure refactors); documented
  intentional deltas required for R-1 (hardcode purge may legitimately convert
  statements to review cases).

## 4. Conflict analysis

| Potential conflict | Mitigation |
|---|---|
| REEF (dispatch) vs LEDGER (schema v2) both in `analysis/` | Sequenced: registry migration (Wave 2) completes before schema v2 (Wave 3); v2 is adapter-based so parser diffs stay mechanical |
| DELTA worker vs SONAR ladder | O-1 defines the interface; D-5 is a follow-up deletion PR, not parallel edit |
| LEDGER package extraction vs DELTA app.py work | `_package_analysis` extraction (L-2) lands as move-only PR; DELTA rebases route wiring on top |
| HARBOR telemetry vs REEF dispatch | Telemetry hooks the post-R-3 seam; H-3 blocked on R-3 |
| Registry edits (LEDGER L-5) vs classifier (protected) | Registry is data-only; classifier code changes remain Ocean-gated |

## 5. Review gates (Ocean)

Every PR: standing criteria from TASK_BOARD (tests green, corpus audit, no new
statement-specific constants). Additionally Ocean pre-approves: parser-protocol RFC,
schema-v2 RFC, money-representation decision (Decimal vs int cents), underwriting-ratio
definitions (L-3), OCR provider interface (O-2), tamper-score semantics (O-5), and
every discrepancy ruling from the comparison harness (H-2) before any code changes in
response to a MoneyThumb difference — differences are investigated against source
statements, never resolved by copying MoneyThumb.
