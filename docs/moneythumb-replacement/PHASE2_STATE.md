---
name: phase2-state
description: "PHASE 2.1 COMPLETE (2026-09-03, gate met, STOPPED pending Gustavo's approval of the closure report; composed code tree 4f7d798 on train11; cold run 2,625 -> 2,625; Paddle-eligible 13 / attempted 0 by the privacy boundary; two rulings requested: the 13-document remote-data run and the Vast hourly rate). Opening record: (opened 2026-09-02 on train11 from 9a54952; Ruling A / Ruling B / the Vast.ai remote_paid authorization recorded; cells G and P launched, R after P; privacy boundary: no customer documents to Vast). PHASE 2.0 COMPLETE (2026-09-02, gate met, approved by Gustavo): composed train10 941918f (docs tip on train); OQ1-OQ11 RULED (PHASE2_RULINGS.md); five cells + P20-REPLAY-SHAPE reviewed/closed/re-reviewed; floor 2,625 preserved by full-archive replay AND cold run (2,625 -> 2,625, 3,380 unchanged); OCR_STAGE_VERSION 5; OCR-fed validated 0; legal escalation population 13; Phase 2.1 (PaddleOCR) NOT authorized until Gustavo approves"
metadata:
  node_type: memory
  type: project
  originSessionId: 71746312-b66b-440b-a510-c04ff00bcdd2
  modified: 2026-09-02T00:00:00.000Z
---

**Baseline (unchanged)**: batch 9 FROZEN at `batch9-final` = `819d97d` (2,625 / 3,380 = 77.66%).
Phase 2.0 base `train10` opened from `origin/main` `746e1e9` (the freeze tree + the read-only census
tool + docs). Gustavo's OQ1–OQ11 rulings: `docs/moneythumb-replacement/PHASE2_RULINGS.md` (binding).

**PHASE 2.0 — SAFETY FOUNDATIONS — COMPLETE 2026-09-02 (completion gate met; STOPPED pending
Gustavo's approval of the closure report).** Composed code tree **`941918f`** on `train10` (merges
`d4bb48c` SEAM → `db63c25` POSTPROCESS → `88e33b8` ROUTER → `422c8c6` ARTIFACTS → `7424e43` SURFACES
→ Ocean's composition `51692c3` → `941918f` REPLAY-SHAPE); docs tip on the train after it. Every
cell: implementation (Sonnet 5 HIGH) → independent adversarial review (Opus; four BLOCK, two
APPROVE WITH FINDINGS) → closure with every finding reproduced first → re-review → APPROVE WITH
FINDINGS with every residual closed. Reviews under `docs/moneythumb-replacement/reviews/PHASE2_P20*`.

**What landed** (durable record: `BATCH9_TRANSITION.md` §7, 2026-09-01/02 entries):
* `ocr/escalation.py` — closed failure classes A/B/C; closed trigger vocabulary (T defined and
  refused, OQ4); `RouterInputs` with no verdict field and one constructor; `EscalationRouter` where
  only pre-financial triggers START and only `validated` STOPS; `ExtractionQualityGate` on
  extractor-produced evidence only with the parameter-free admitted triad; the density criterion
  SURFACE-ONLY (a candidate for Phase 2.1 with labelled evidence); endpoint policy enforced once at
  `ocr_client._build_client`; vocabularies enforced at the row projection; import / signature /
  subclass / repo-wide call-site tripwires; validated∩class-A = 0 pinned row-wide.
* **Trigger-U split measured** (batch-9 run and the new run of record agree): R 13 · U 123 ·
  **U-extract (admitted) 0 · U-structure 123 · density-surfaced candidate 23 · legal escalation
  population 13** · T surface 3 (1 in U) · validated∩(R∪U) 0 · row-level Class-A 0.
* Nine-function postprocess census (31 synthetic fixtures, mechanical numeric-token accounting; the
  audit's UNPROVEN debit/credit/balance fold settled as constructible); the whole chain quarantined
  on analysis AND display paths behind an EMPTY admission tuple; `embed_image_regions` unwired;
  `INTAKE_FURNITURE` register (7 entries); the no-hardcodes guard layer-wide in `ocr/` with an
  exact-match issuer-string ratchet (OQ1 = C, OQ2).
* OCR_MODEL / `source_file` injection closed (`\A…\Z` charset, money-shape and reserved-prefix
  refusal, line-break and `-->` refusal in `source_file`); `ocr/endpoint_policy.py` loopback /
  private / remote / invalid with the exact opt-in literal `I_ACCEPT_REMOTE_PAID_OCR`, IMDS and CGNAT
  forced remote, one endpoint per process, refusal before any client exists; endpoint class and
  opt-in recorded in telemetry; `source_path_for` fallthrough closed with the unrecognized-model
  diagnostic; four legacy OCR scripts retired after salvaging their checks; `parse.py`/`batch.py`
  offline by default; RunPod relabeled the paid escape hatch (OQ3, OQ6, OQ7).
* `telemetry/run_of_record.py` — the one artifact-selection policy (recorded or verified-
  reconstructed partitions with a 90 % correspondence check; row-driven; raise on a corrupt index)
  adopted by `cohort_replay`, `CachedArtifacts`, the three shared scanners and the two fixpriv
  instruments; runs record their partitions (`coldrun.sh --mode`); the OCR settings key gained
  extractor / postprocess state / raster + schema versions / endpoint class / toolchain versions;
  **OCR_STAGE_VERSION 4 → 5** with its pin (OQ8, OQ10).
* `cohort_replay` replays through the runner's exact document call (P20-REPLAY-SHAPE): full archive
  3,380 shas at the closure tip — replayed 3,351, newly validated 0, **preserved 2,625 of 2,625
  identical**, regressions 0, `--expect-unresolved 29`, exit 0.
* The fabricated "OCR confidence" replaced by validation verdict words (no number; literal guard);
  the Q3 class admitted only on `native-pdf-text*` provenance through `analysis/provenance.py`'s
  ambiguity-refuses reader (exactly one well-formed field run terminating line one), raising
  `Q3ProvenanceRefused` in EVERY parse_mode (`q3_provenance_refused` reason token); the two 2026-07
  specs SUPERSEDED (OQ9, OQ11).

**Proof at the composed tree** (`941918f`): full suite **8,342 passed / 45 skipped / 38 deselected**;
guards 267; conformance 1,282; `corpus_gate.py` GREEN 105/3/1; corpus slice 34; remote CI GREEN
run 33599700440 on `origin/train10`; **cold run** `discovery_reports/TRAIN10-941918f/2026-09-02T063646…-ef34ee30`
vs the batch-9 run of record with `--fail-on-regression`: **2,625 → 2,625, 3,380 unchanged, 0
regressed, compare exit 0**, peak 1,242 MB; the run's provenance records its partitions (the first
`origin = recorded` run); OCR-fed validated 0; ANALYSIS_STAGE_VERSION stays 17 (no payload changed).

**Discovered, NOT in scope, for Gustavo**: the pre-existing webapp auto-mode edge
`dispatch unclaimed / parser_exception → extract_statement` (`analysis/pipeline.py`, hosted model)
is a Class-B → hosted-model-call path in the product's default mode, pinned unchanged by Phase 2.0
and reported for a ruling under OQ3's spirit. Backlog carried: 33 historical `tools/*.py` still use
the old `ColdCache` signature; `tools/ocr_legacy_census.py` names the four retired scripts.

**Next**: Gustavo reviews the closure report. Phase 2.1 (PaddleOCR as the primary NEW visual
extractor, geometry into `document_geometry`, allowed only on R + U-extract, per-page provenance)
is NOT authorized until he approves.

Related: [[batch9-state]] [[moneythumb-phase1-roadmap]] [[batch8-operating-model]] [[subagent-model-policy]]

**PHASE 2.1 — PADDLEOCR + CANONICAL WORD BOXES + DOCUMENTGEOMETRY — IN PROGRESS (opened
2026-09-02).** Gustavo approved Phase 2.0 and authorized Phase 2.1 only. Train **`train11`** from
`origin/main` `9a54952`. Rulings A (automatic hosted extraction REFUSED) and B (density
SURFACE-ONLY) and the explicit Vast.ai `remote_paid` authorization (with the DATA PRIVACY BOUNDARY:
no production customer statements to Vast without a separate ruling) are recorded in
`PHASE2_RULINGS.md` §"Phase 2.1". Umbrella card `docs/agent-handoffs/PHASE2-1-PADDLE.md`; cells
`P21-GEOMETRY` (G), `P21-PADDLE` (P), `P21-ROUTING` (R — after P composes). Ocean's cell 0 landed the
`evidence/` package and `ocr/paddle_config.py` (`1282eb0`, `888fb1c`). Live record: `BATCH9_TRANSITION.md`
§7, 2026-09-02 "PHASE 2.1 OPENED" and later entries. Expected coverage movement in this phase: the
13-document legal population is customer data and is NOT sent to Vast (D8) — synthetic proof only;
Paddle-eligible 13 / attempted 0 / newly validated 0 reported honestly; the 2,625 floor untouched.

**PHASE 2.1 — COMPLETE 2026-09-03 (completion gate met; STOPPED pending Gustavo's approval of the
closure report).** Composed code tree **`4f7d798`** on `train11`: cell 0 (`evidence/` +
`ocr/paddle_config.py`, Ocean) → G `6380f67` (one `DocumentGeometry` from canonical evidence; native
byte-identical on all 109 corpus PDFs / 830 pages) → P `db2ad95` + live proof `c2c1d82` (the loopback
stdlib worker on the Vast RTX 5090, the bounded client with declaration + worker corroboration, the
3.7 adapter into immutable evidence, the fail-closed rung, the lifecycle tool, the synthetic
measurements) → R `d757f86` (`RouterInputs.enabled`; `EXTRACTOR_ORDER` = local_tesseract, paddle,
visual; the forced-path-only rung; `--scanned-paddle`; per-page provenance on every rung;
EXTRACTION_SCHEMA_VERSION 2; the customer-scope refusal at the runner) → three composed-tree integration
fixes (`bf8cd11`, `4f7d798`). Every cell: implementation → independent adversarial review → every
finding reproduced → closure → independent re-review → residuals closed (G: BLOCK → APPROVE WITH
FINDINGS; P: APPROVE WITH FINDINGS twice; R: APPROVE WITH FINDINGS twice, the re-review and closure-2
performed in the Fable 5.1 environment under `ORCHESTRATION-MODEL-POLICY.md`).

**Proof at the composed tree**: full suite **8,756 passed / 45 skipped / 39 deselected**; guards 275;
conformance 1,282; gate GREEN 105/3/1; corpus slice 34; remote CI GREEN run 33705014589; **cold run
`discovery_reports/TRAIN11-4f7d798/2026-09-03T022827.644186-0000-331d9136` vs the Phase 2.0 run of
record: 2,625 → 2,625, 3,380 unchanged, compare exit 0** (peak 1,239 MB; the offline OCR partition
rebuilt under schema 2); cohort replay 2,625 / 2,625 identical at every cell's base and closure.
Measured on the new run of record: R 13 · U 123 · U-extract 0 · U-structure 123 · density-surfaced
23 · legal escalation population 13 · row-level Class-A 0 · OCR-fed validated 0 · **Paddle-eligible 13
documents / 17 pages · attempted 0 · newly validated Paddle-fed SHAs NONE · false accepts 0** (the
Paddle path proven end to end on synthetic fixtures: real PP-OCRv5 inference over the tunnel, cold e2e
5,208 ms, warm median 1,872 ms, `evidence_sha256` stable, cost "rate not measured").

**Rulings requested from Gustavo (not assumed)**: (1) may the 13-document legal escalation population
(customer statements, 17 pages) be sent to the Vast worker — the remote-data / privacy / retention
ruling (D8); until then `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` stays unset and a `--scanned-paddle`
archive run refuses by construction; (2) the Vast hourly rate for the cost figure. **Documented, not
built (Phase 2.2 prerequisites)**: the rotation-frame mismatch (0/830 pages today); the native
geometry path's discarded evidence sha (~2.7×); `analysis_input_sha` is geometry-blind; Tesseract word
boxes; a `local_free` worker deployment. **Next**: Gustavo reviews the closure report. Phase 2.2 is
NOT started; Unlimited OCR is NOT enabled.
