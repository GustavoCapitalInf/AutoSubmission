# Phase 2.2 — TRUTH INSTRUMENTS (umbrella implementation card; Ocean, 2026-09-03)

**Authority:** Gustavo's FULL PHASE 2 EXECUTION AUTHORIZATION and rulings R1–R14
(`docs/moneythumb-replacement/PHASE2_RULINGS.md` §"Phase 2 remainder", 2026-09-03 — binding, read all
of it); OQ1–OQ11, Ruling A, Ruling B and the Vast.ai authorization (same file); the approved plan
`docs/moneythumb-replacement/phase2_remainder/PHASE2_REMAINDER_PLAN.md` (§G.2.2 is this milestone's
design; §D, §E, §J its taxonomy, architecture and classifier); the standing rules (`BATCH9-RULES.md` +
`PHASE2-RULES.md`, carried forward in full; the Phase-2.2 delta is §"Rules delta" below);
`ORCHESTRATION-MODEL-POLICY.md`. Every Phase 2.0/2.1 invariant is binding. **Validator success may STOP
escalation; validator failure may NEVER START escalation. The validator is a verifier, never an
optimizer.**

## Objective (exact)
Make the rest of Phase 2 measurable and honest before any customer page leaves the machine and before
any new coverage claim: (1) a deterministic **document classifier** with named evidence, whose primary
classification is DISJOINT and SUMS TO 755 over the unresolved set; (2) the layered **unresolved-reason
taxonomy** (L0 file → L1 kind → L2 extraction → L3 structure → L4 financial → L5 doctrine → L6 unknown)
with per-document reasons and the **two denominators** (raw; confirmed-complete-legible); (3) the
**sealed truth store**, the **adjudication CLI** and the **unseen holdout cage** (R3, R4) with a leakage
firewall; (4) the **identity fixes downstream milestones need**: a geometry-aware analysis key, native
evidence persisted with its sha, native word boxes in the display frame, the evidence-package boundary
amended for the one native reader; (5) the **research run mode** (`operator_forced_paddle`, research
partitions excluded from the run of record) that 2.3 will execute; (6) **R9**: the auto-mode hosted
extraction selection by reconciliation removed and the hosted edge fenced behind an explicit opt-in;
(7) funnel and technical-telemetry columns. Expected coverage movement **+0**; OCR-fed validated **0**;
**no customer page leaves the machine in 2.2** (the research mode is proven on synthetic fixtures only).
The 2,625 floor is untouched and payload-identical.

## Baseline (verified 2026-09-03 before anything moved)
| fact | value |
|---|---|
| `origin/main` = `HEAD` of `train12` | `a7ac9b0` (docs tip: the planning package `8c5d61f` + the rulings `a7ac9b0` on top of `21e3163`; code tree unchanged = **`4f7d798`**) |
| `phase2.1-final` | `d5d82e8` (annotated; on origin); CI 33712610441 SUCCESS on main |
| train branch | **`train12`** (opened from `origin/main` `a7ac9b0`) |
| floor | 2,625 / 3,380 (77.66 %); run of record **`discovery_reports/TRAIN11-4f7d798/2026-09-03T022827.644186-0000-331d9136`** (2,625 → 2,625 vs Phase 2.0; 3,380 unchanged; peak 1,239 MB; ≈ 74 min); its cold cache **`.claude/recovery/webapp_data_train11_cold`** (READ-ONLY; offline OCR key `B3F8D008…` at OCR_STAGE_VERSION 5 / EXTRACTION_SCHEMA_VERSION 2, 3,364 entries; analysis key `7799FEE4…` at ANALYSIS_STAGE_VERSION 17, 2,656 entries) |
| versions | OCR_STAGE_VERSION 5 · EXTRACTION_SCHEMA_VERSION 2 · EVIDENCE_SCHEMA_VERSION 1 · RASTER_VERSION 1 · ANALYSIS_STAGE_VERSION 17 · registry 84 · DIAGNOSTICS_VERSION (W3-2 v4) |
| suite at `4f7d798` | 8,756 passed / 45 skipped / 39 deselected; guards 275 (5 files); conformance 1,282 (7 files); gate GREEN 105/3/1; corpus slice 34 |
| the 755 (distinct shas, run of record) | failed 672 (no_parser_matched 537 · parser_declined 119 · invalid_pdf 16) · withheld 49 · review 21 · deferred 13; digital 583 · scanned 131 · mixed 12 · no-text 13 · invalid 16; failure_class B 656 / C 70 / "" 29; pages 5,110; census clusters FAM 322 · DECL 119 · NOT-STATEMENT 117 · SCAN-UNCLAIMED 89 · WH 52 · RV 18 · PF-INVALID-PDF 16 · OCR-NEGATIVE 13 · TEXT-LAYER-DEFECT 8 · NO-TEXT 1 (`phase2_remainder/research/REPO_CORPUS_MEMO.md` §3) |
| triggers | R 13 · U 123 · U-extract 0 · U-structure 123 · density-surfaced 23 · legal escalation population 13 · validated∩class-A 0 · Paddle attempted 0 (no real document has ever been read by Paddle) |
| local toolchain | Python 3.14.5 (CI pins 3.12 — write for both); PyMuPDF 1.27.2.3; Pillow 12.2.0; tesseract 5.5.0; poppler 24.08.0; no `paddleocr` locally |
| Vast host | configured from the `PADDLE_VAST_*` environment only; NOT used in 2.2 |
| privacy scan of the planning package | 87 residue sites adjudicated external provenance (`discovery_reports/train12-logs/privacy-scan-plan-package-ADJUDICATION.md`); the four repository audits 0 |

## Scope — five bounded cells, disjoint FILE ownership; Ocean composes
| cell | card | delivers | cases |
|---|---|---|---|
| **K — IDENTITY & FRAMES** | `P22-IDENTITY.md` | `evidence/native.py` (the one native PyMuPDF reader, display-frame boxes, lazy `fitz`); the amended evidence-boundary tripwire; `analysis/structurer/geometry.py::native_evidence_from_pdf` re-exported (byte-identical on unrotated pages, pinned; rotated pages in the display frame, pinned); the `pdf_point` bounds check; native evidence attached by the OCR ladder and persisted in the OCR record (`EXTRACTION_SCHEMA_VERSION` 2 → 3, pinned); the geometry-aware analysis key (`analysis_input_sha` + `Settings.reconstruction_mode`; `ANALYSIS_STAGE_VERSION` 17 → 18, pinned); the research-partition id in the OCR settings key and `run_of_record`'s refusal of research partitions; `tools/train/provenance.py` partitions; the `/Rotate` census | 12–17 |
| **C — CLASSIFIER** | `P22-CLASSIFY.md` | the neutral `layout/` package: `layout/signals.py` (closed EN/FR/ES lexicons, shape regexes), `layout/document_class.py` (`classify_document(...) -> DocumentClass`), `layout/refusals.py` (the L0/L1 vocabulary); the boundary tripwire (stdlib + `evidence` only); the OQ2 scans extended to `layout/`; synthetic fixtures for every kind | 1–5, 24 |
| **H — SEALED TRUTH & HOLDOUT** | `P22-HOLDOUT.md` | `tools/holdout/` (the sealed store: append-only, hash-chained JSONL keyed by content sha, outside the repository at `SEALED_TRUTH_DIR`; the holdout manifest with strata and status rules; the manifest digest export), `tools/adjudicate.py` (local page rendering, verdict capture, evidence packets, queues); the leakage-firewall tripwire | 18–21, 24 |
| **F — FENCE (R9)** | `P22-FENCE.md` | `analysis/pipeline.py`: the reconciliation-based selection between two hosted extractions REMOVED; the auto-mode Class-B → hosted extraction edge fenced behind an explicit opt-in literal (Ruling A in code); characterisation tests at base; AST tripwires; cohort replay proving deterministic mode byte-identical | 22 |
| **T — TRUTH TABLE, TELEMETRY, RESEARCH MODE** | `P22-TRUTHTABLE.md` (launched from the integration base after K and C compose) | `telemetry/unresolved_taxonomy.py` (L0–L6 with drift guards and precedence), the `refused` outcome vocabulary across `telemetry/record.py`, `discovery/compare.py`, `tools/train8_compare.py`, `discovery/report.py` (both denominators; the disjoint primary classification summing to 755; diagnostic labels reported separately); the classifier wired into rows as a recorded fact; funnel + technical-telemetry columns; `discovery --research-paddle` (`operator_forced_paddle` admitted only in that mode; both literals; research partition; never auto mode); geometry passed to `analyze_document` behind `reconstruction_mode` (seam wiring only — the structurer stays off) | 6–11, 23, 25 |

Composition order at the train: **K → C → H → F → T** (T is launched from `train12` + K + C composed;
H and F compose whenever green). Ownership is disjoint by construction (each card lists exact files);
any overlap discovered is reported to Ocean, never resolved by a cell.

## Material design decisions (Ocean; each preserves every binding invariant; format: expected → changed → why → risks → tests)

**D1 — the classifier lives in a neutral `layout/` package, not in `ocr/` or `analysis/`.** *Expected:*
`ocr/document_class.py`. *Changed:* top-level `layout/` importing only the standard library and
`evidence`. *Why:* the classifier reads evidence from any extractor and its verdict is consumed by the
intake ladder (a refusal before a paid rung, 2.5) and by analysis (formal-statement semantics); the
analysis→ocr allowlist is pinned EMPTY and ocr→analysis is forbidden, so neither side may own it; the
same package will hold the LayoutModel in 2.4. *Risks:* a third home for lexicons — mitigated by ONE
`layout/signals.py`. *Tests:* `tests/test_layout_boundary.py` (AST at any depth, like
`test_evidence_boundary.py`).

**D2 — classification never edits the raw denominator and never routes in 2.2.** *Expected:* a
not-statement list removes documents from coverage. *Changed:* `document_class` is a recorded fact on
the row; the primary classification is DISJOINT and sums to 755 on the unresolved set (and to 3,380 on
the archive); the CCL denominator is reported in two forms — *adjudicated* (from the sealed store) and
*classifier-proposed* — and the raw denominator is always printed beside it. *Why:* R11/R12; honesty.
*Tests:* the compare tool refuses a base/candidate pair whose raw denominators differ; the report
asserts the sum; a validated document classified other than `STATEMENT_COMPLETE` is a named finding.

**D3 — the one native reader lives in `evidence/native.py` with a LAZY PyMuPDF import; the boundary
tripwire is amended precisely.** *Expected:* keep `native_evidence_from_pdf` on the analysis side.
*Changed:* the OCR ladder must attach native evidence to the artifact (it cannot import `analysis`),
and the structurer must consume the same reader (it cannot import `ocr`); the only shared home is
`evidence/`, whose tripwire says "stdlib only". The tripwire becomes: `evidence/` imports nothing from
any repository package; third-party imports are forbidden EXCEPT `fitz`, imported lazily inside
`evidence/native.py::native_evidence_from_pdf` and nowhere else (AST-pinned by name and site).
`analysis/structurer/geometry.py::native_evidence_from_pdf` becomes a re-export; `geometry_from_pdf`
stays byte-identical on every unrotated page (the 109-document / 830-page pin stands). *Why:* one
reader, one geometry, one sha; PyMuPDF is already a hard dependency of both sides. *Risks:* the
evidence package is no longer importable without PyMuPDF installed — false: the import is lazy, and a
test proves `import evidence` succeeds with `fitz` absent from `sys.modules`. *Tests:* the amended
boundary test; the re-export equality pin.

**D4 — native word boxes move into the DISPLAY frame; rotation is applied, recorded, and pinned.**
*Expected:* keep PyMuPDF's unrotated word space (the Phase 2.1 note). *Changed:* `native_evidence_from_pdf`
transforms each word box by the page's rotation matrix into the display frame (the frame `page.rect`
already describes); `PageFrame.rotation_deg` records what was applied; the `native_words_unrotated_space`
note is retired; a `pdf_point` frame gains the bounds check pixel frames already have. *Why:* the Paddle
raster is display-oriented; 2.3's native↔Paddle agreement and 2.4's LayoutModel need one frame. *Risks:*
a rotated native page's geometry CHANGES by design — no production consumer of geometry exists today, so
zero movement by construction; the change is pinned with 0/90/180/270 synthetics and the /Rotate census
over all 3,380 is reported. *Tests:* case 14, 15.

**D5 — native evidence is persisted in the OCR record; `EXTRACTION_SCHEMA_VERSION` 2 → 3.** *Expected:*
recompute geometry from the PDF on demand. *Changed:* the native rung builds evidence once, attaches it
to `StatementMarkdown.evidence` (the D9 invariant `evidence.page_texts() == pages` does NOT hold for the
native rung, whose page strings come from `_native_pages`/blocks, not from word grouping — so the record
carries native evidence in a sibling field `native_evidence` with its sha, and `StatementMarkdown` gains
`native_evidence: ExtractionEvidence | None` with its own consistency check: page count equal; no text
equality required), `evidence_sha256` populated on native rows; the schema bump is key material for every
extractor, so the whole OCR cache is rebuilt at the train's cold run (≈ 74 min; required anyway). *Why:*
raw next to derived; replay without re-opening PDFs; the sha is the lineage 2.4 will reference. *Risks:*
artifact size (words for ≈ 25,000 native pages — measured and reported; expected tens of MB); the
`to_markdown()` byte-identity pin stands. *Tests:* case 13.

**D6 — the analysis key sees geometry and the reconstruction mode; `ANALYSIS_STAGE_VERSION` 17 → 18.**
*Expected:* a boolean "geometry supplied". *Changed:* `analysis_input_sha` includes the evidence sha
that fed geometry (or the literal `no-geometry`); `analysis_settings_key` includes
`Settings.reconstruction_mode ∈ {"off", "research", "production"}` (default `off`); the
`GENERIC_STRUCTURER_ENABLED` environment contract is RETIRED — `structurer_enabled()` reads the setting;
`run_of_record` learns the new stage. *Why:* the geometry-blind key was the named stale-cache hazard;
the mode is what 2.3 (research) and 2.4 (production) will flip. *Risks:* the analysis cache goes cold at
the train's cold run (required anyway). *Tests:* case 12.

**D7 — research partitions are excluded from the run of record by construction.** *Expected:* a flag on
the row. *Changed:* the OCR settings key gains `research_partition: str` (empty for production); a
non-empty value makes `run_of_record` REFUSE to select the artifact (a research artifact can never become
historical truth); the research mode writes to a separate `--data-dir`. *Why:* research admission and
production admission stay different concepts (R1, the plan §F.2). *Tests:* case 17, 23.

**D8 — the research mode starts Paddle through the router, never around it.** *Expected:* the runner
calls the rung directly. *Changed:* a new admitted trigger `operator_forced_paddle` (pre-financial by
construction: a run-mode fact, like `operator_forced_visual`), admitted ONLY when the runner is in
`--research-paddle` mode, with `enabled = {"paddle"}` as a MODE constant (the D4 tripwire stands), both
literals present in the process environment, a population file of content shas, and a research
partition id; in that mode every document in the population is read by Paddle regardless of profile,
which is the research admission Gustavo authorized; auto mode has no path to it. *Why:* the router stays
the only starter; `RouterInputs` stays verdict-blind. *Risks:* none new. *Tests:* case 23; 2.2 proves it
end to end on synthetic fixtures only (no customer page leaves the machine in 2.2).

**D9 — the sealed truth store is outside the repository and invisible to production code.** *Expected:*
a labels CSV under `docs/`. *Changed:* `SEALED_TRUTH_DIR` (environment) names a directory outside the
checkout; records are append-only JSONL keyed by content sha (fields: sha, kind, sub_kind, completeness
findings, the five oracle figures, three sampled rows, adjudicator, timestamp, evidence-packet digest,
previous-record hash → a hash chain); the repository carries only
`docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt` (store version, record count, chain head);
the firewall tripwire proves no module under `analysis/ layout/ ocr/ evidence/ discovery/ webapp/
telemetry/` references the variable or imports `tools.holdout`. *Why:* R3, R4, label leakage (plan §M6).
*Tests:* cases 18–21.

**D10 — adjudication never blocks a milestone gate.** *Expected:* the gate waits for Gustavo's slice.
*Changed:* the classifier's verdicts produce truth table **v0** (classifier-proposed); the adjudication
queue and evidence packets for slice 1 (≈ 227: the 117 census not-statements, the 51 thin scans, the 13
exports, the 16 invalid files, 30 random FAM) are PREPARED and handed to Gustavo; **v1** (adjudicated)
lands whenever the adjudication session happens; every report prints adjudicated and classifier-proposed
counts separately. *Why:* "do not wait for routine approval" without letting a proposal masquerade as
truth. *Tests:* case 11.

**D11 — R9 in code, not in comments.** *Expected:* a tripwire that the selection is unreachable in
deterministic mode. *Changed:* the selection is REMOVED (the escalation extraction call existed only to
be preferred by reconciliation); auto mode's `dispatch unclaimed / parser_exception → extract_statement`
edge (the Class-B → hosted hop Ruling A refused) requires `HOSTED_EXTRACTION_OPT_IN=I_ACCEPT_HOSTED_MODEL_EXTRACTION`
in the environment, default absent → auto mode behaves as deterministic mode for those documents
(`failed / no_parser_matched`), which is the ruled doctrine; the base behaviour is characterised by a
test that reproduces the old selection on a fake extractor BEFORE the change and is then inverted.
*Why:* R9 verbatim: "do not leave reachable logic whose effective behavior is: multiple extractions →
compare financial reconciliation → prefer whichever extraction reconciles". *Risks:* a webapp user in
auto mode without the literal gets `failed` where they used to get a hosted extraction — surfaced in the
closure; deterministic mode (every run of record, the gate, discovery) is byte-identical (cohort replay,
cold run). *Tests:* case 22.

## Contracts

**Classifier (`layout/document_class.py`, cell C; consumed by T):**
```
classify_document(*, evidence: ExtractionEvidence | None, page_texts: tuple[str, ...] | None,
                  profile: DocumentProfileFacts) -> DocumentClass
DocumentProfileFacts(frozen): valid_pdf, encrypted, page_count, classification ("digital"|"scanned"|"mixed"|"unknown"),
                  page_text_chars: tuple[int, ...], magic: str | None   (facts only; no analysis objects)
DocumentClass(frozen): kind ∈ KINDS, sub_kind: str | None, modality ∈ {"digital","scanned","mixed","image_backed_text","unknown"},
                  language ∈ {"en","fr","es","unknown"}, account_kind ∈ {"deposit","card","loan","brokerage","unknown"},
                  completeness: tuple[Finding, ...], evidence: tuple[EvidenceRef, ...], tier ∈ {"structural","lexical","uncertain"},
                  version: int (CLASSIFIER_VERSION)
KINDS = ("STATEMENT_COMPLETE", "STATEMENT_PARTIAL", "STATEMENT_ILLEGIBLE", "ACTIVITY_EXPORT",
         "NOT_A_STATEMENT", "FILE_INVALID", "KIND_UNCERTAIN")            # closed; disjoint; exactly one per document
Finding(frozen): code (closed: missing_pages | missing_opening | missing_closing | missing_period | missing_first_page |
                  table_truncated | page_gap | balance_discontinuity_at_page_break), page: int | None, detail: str (no document text)
EvidenceRef(frozen): page: int, word_ids: tuple[str, ...] | None, span: tuple[int, int] | None, signal: str (closed signal name)
```
Deterministic; pure; no randomness; no document text in `detail`/`signal`; `KIND_UNCERTAIN` is a
first-class outcome; every verdict lists its signals.

**Taxonomy (`telemetry/unresolved_taxonomy.py`, cell T):** one code per layer L0–L6 per document
(`reason_l0 … reason_l6` columns, empty when the layer does not apply); the PRIMARY reason = the
highest non-empty layer; closed vocabularies per layer with drift guards in the W3-2 idiom (a code
`analysis/`, `ocr/` or `layout/` grows that the vocabulary does not know lands in `unmapped` and fails a
guard); L4 = the existing W3-2 classes unchanged; L3 and L2 codes exist in the vocabulary now (B1–B8,
E0–E5) and are populated by 2.3/2.4 (empty in 2.2 except where the existing structurer measurement
already names one).

**`refused` (cell T):** `classify_outcome` gains the terminal class `refused` (reasons: `not_a_statement`,
`file_invalid`, `insufficient_evidence`, `contradictory`, `incomplete`, `unreadable` — reserved now,
produced by later milestones; in 2.2 zero documents move into it); `DOCUMENT_LADDER`/`LADDER` keep
`failed < withheld < review < validated`; `refused` is UNRANKED relative to failed/withheld/review;
ANY transition out of `validated` (to anything, including `refused`) is a regression (exit 2); the
transition matrix is printed exactly (from-class × to-class counts).

**Sealed store / holdout (cell H):** see D9 and the card.

**Research mode (cell T, over K's key and `ocr/escalation.py`):** `python -m discovery --research-paddle
--population <shas.txt> --research-partition <id> --data-dir <research dir> --out <run dir>`; refuses
without `PADDLE_REMOTE_OPT_IN` and `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` in the process environment (the
runner declares `customer` scope as today); refuses a `--data-dir` equal to any production cache; the
row records `research_partition`, `escalation_trigger = operator_forced_paddle`; the report's headline
coverage EXCLUDES research partitions by construction (they are never selected by `run_of_record`).

## Provenance / lineage
`evidence_sha256` on every native row (new) and Paddle row (existing); `native_evidence` in the OCR
record with its own sha; the analysis input hash names the evidence it consumed; `reconstruction_mode`
and `research_partition` in the settings keys; the classifier version on every row; the truth-store
manifest digest in the repository; the adjudication records carry the evidence-packet digest so a
verdict can be re-read against what the adjudicator saw.

## Artifact / cache / replay implications
`EXTRACTION_SCHEMA_VERSION` 2 → 3 and `ANALYSIS_STAGE_VERSION` 17 → 18 in the same reviewed commits as
their pins; both caches rebuild at the train's cold run (`coldrun.sh` → `webapp_data_train12_cold`);
`webapp_data_train8/9/10/11_cold` READ-ONLY; `cohort_replay` needs the `research_partition` refusal and
the new stage; `tools/train/provenance.py` records the new keys.

## Technical telemetry (cell T; cost/billing is OUT OF SCOPE by Gustavo's ruling)
Per document: `stage_extract`, `stage_evidence`, `stage_geometry`, `stage_layout`, `stage_candidate`,
`stage_verdict` (closed vocabularies, `not_attempted` default); `bytes_up`, `bytes_down`,
`inference_ms`, `vram_mb` (from the Paddle client's existing per-request timing/gpu fields; empty for
non-Paddle rows); `peak_rss_mb` per document (`psutil` added to `requirements-local.txt` — a tool-time
dependency; the runner degrades to the honest `not measured` string when absent); no cost, no rate, no
billing field anywhere.

## Required cases (mapped)
| case | property | cell |
|---|---|---|
| 1 | every synthetic kind (complete statement EN/FR/ES; partial: page removed / opening removed / closing removed / period removed; activity export; cheque image; voided cheque; deposit slip; letter; card statement; loan statement; screenshot-as-PDF; invalid file; rotated statement) classifies with named evidence | C |
| 2 | `KIND_UNCERTAIN` exists, is reachable, and is asserted on a conflicting fixture | C |
| 3 | a cheque-image PDF (MICR-shaped digit groups in the bottom band + aspect ratio in [2.0, 2.6]) → `NOT_A_STATEMENT{cheque_image}` at tier `structural`; the same without MICR → `KIND_UNCERTAIN` or lexical, never structural | C |
| 4 | a statement with a `Page X of Y` gap → `STATEMENT_PARTIAL{page_gap}`; without an opening anchor → `{missing_opening}`; a running-balance discontinuity at a page break → `{balance_discontinuity_at_page_break}` | C |
| 5 | `layout/` imports only stdlib + `evidence` (AST at any depth); `classify_document` is pure (two calls, same inputs → equal outputs; no clock, no randomness) | C |
| 6 | wiring the classifier into rows changes NO analysis output (payload identity with and without the classification column; the classifier is never passed to `analyze_document`) | T |
| 7 | on the run of record, every validated SHA classifies `STATEMENT_COMPLETE`, or the exception is NAMED by sha and kind in the closure (a classifier defect to fix or a finding) | T |
| 8 | the primary classification is DISJOINT and sums to 755 on the unresolved set and to 3,380 on the archive; R, U, density and failure-class labels are reported in their own table and never summed with it | T |
| 9 | taxonomy drift guards: a code grown by `analysis/`, `ocr/` or `layout/` that the vocabulary lacks fails a guard AND lands in `unmapped`; the precedence table in the doc equals the code | T |
| 10 | `refused` in every vocabulary; compare: `validated → refused` is a regression (exit 2); `failed ↔ refused` is unranked; the transition matrix is printed exactly; a base/candidate pair with different raw denominators is refused | T |
| 11 | both denominators in `summary.json` and the report; CCL printed as `adjudicated` and `classifier_proposed` separately; the raw denominator is never replaced | T |
| 12 | two analyses of identical markdown, one with evidence and one without, produce different analysis keys; `reconstruction_mode` partitions the key; `ANALYSIS_STAGE_VERSION == 18` pinned in the same commit; the retired env contract is inert (setting the old variable changes nothing) | K |
| 13 | a native read's OCR record carries `native_evidence` with its sha; a cache hit reproduces the sha byte-for-byte; `to_markdown()` byte-identical (the committed corpus artifacts pin it); `EXTRACTION_SCHEMA_VERSION == 3` pinned; a schema-2 record restored from cache still analyses (no evidence, no crash) | K |
| 14 | native word boxes are in the display frame: synthetics at 0/90/180/270 render the same words at the expected display positions; unrotated pages produce geometry byte-identical to the Phase 2.1 pin (the legacy copy in `tests/test_geometry_frames.py`); the /Rotate census over all 3,380 is reported (count only) | K |
| 15 | a `pdf_point` box outside its page refuses at construction (no clamp, no swap) | K |
| 16 | `evidence/` boundary: no repository-package import anywhere under `evidence/`; the ONLY third-party import is `fitz`, lazily, inside `evidence/native.py::native_evidence_from_pdf`; `import evidence` succeeds with PyMuPDF absent from `sys.modules` | K |
| 17 | a non-empty `research_partition` in an OCR settings key makes `run_of_record` refuse the artifact; `cohort_replay` and `tools/train/provenance.py` never select it; the production key is unchanged when the field is empty | K |
| 18 | the sealed store: append-only (a rewrite of an earlier record is detected by the chain), keyed by content sha, minimum fields, lives ONLY under `SEALED_TRUTH_DIR`, refuses a path inside the checkout, refuses without the variable | H |
| 19 | firewall: no module under `analysis/ layout/ ocr/ evidence/ discovery/ webapp/ telemetry/` references `SEALED_TRUTH_DIR` or imports `tools.holdout` / `tools.adjudicate` (AST at any depth); a mutant import is caught | H |
| 20 | `tools/adjudicate.py`: renders pages locally from a PDF path (PyMuPDF), presents the evidence packet (classifier verdict + signals + the prior census tag as EVIDENCE, labelled as such, never as a default), records the verdict; writes nothing into the checkout; the packet digest is in the record | H |
| 21 | holdout manifest: strata fields; status `unseen → evaluated`, `evaluated → burned` (when named in an implementation change), `evaluated → graduated` only after a freeze tag; illegal transitions refuse; a holdout item can never be added to any population file the runner accepts in research mode (the runner refuses a sha present in the holdout manifest digest list) | H |
| 22 | R9: the base behaviour is characterised (a fake hosted extractor whose alternate reconciles is PREFERRED at base — the test is written first, then inverted); after the change no code path compares two extractions by reconciliation (AST: no second `extract_statement` call in `analyze_markdown`; a mutant re-adding the selection is caught); the auto-mode hosted edge requires the literal; deterministic mode is byte-identical (cohort replay `--expect-identical` over the union of registrations at base and closure; the full-archive replay at the train) | F |
| 23 | research mode: refuses without both literals, without a population file, or with a production `--data-dir`; `enabled == {"paddle"}` is a MODE constant (the D4 AST tripwire passes); `operator_forced_paddle` is admitted ONLY in that mode (a mutant admitting it elsewhere is caught); the fake worker receives exactly one request per page of the population; rows carry `research_partition`; proven on synthetic fixtures ONLY in 2.2 | T |
| 24 | no statement-specific hardcodes in `layout/`, `tools/holdout/`, `tools/adjudicate.py`, the new telemetry module (the OQ2 scans extended to `layout/` and `tools/holdout/`) | C + H + T |
| 25 | funnel and technical-telemetry columns appended at the END of `ROW_FIELDS` with `not_attempted` / empty defaults; the row-shape test updated; `psutil`-absent degrades to `not measured` | T |
Plus: mutation tables for every gate, vocabulary, key field, boundary and refusal each cell adds; the
tripwires named per cell; the geometry-passing seam (T) proven inert while `reconstruction_mode == off`
(payload identity on the union replay).

## Corpus measurements at closure (all offline; no customer page leaves the machine)
The classifier over all 3,380 from cached evidence/text (v0 truth table: kind × modality × tier; the
755 disjoint; validated exceptions named) · agreement with the census NOT-STATEMENT (117) and
portal-export (13) lists reported as agreement, never adopted · the /Rotate census · the adjudication
queue for slice 1 prepared (count, packets digest) · the funnel columns populated for the existing ladder
(Paddle stages `not_attempted`) · native evidence size in the rebuilt OCR cache · the research mode's
synthetic end-to-end proof (documents, pages, fake-worker requests) · newly validated 0 · OCR-fed
validated 0 · R / U / density unchanged · tests added · targeted / full suite / guards / conformance /
gate / corpus slice / cohort replay / cold run / compare / CI results · stage-version changes · final SHAs.

## Regression gates
Per cell: `newly validated = 0`; `previously validated preserved = all, payload identical` (cohort replay
`--expect-identical` at base and at closure over the cell's named cohorts — for K and F the union of
every registration is required because both touch a protected seam); mutation tables complete; privacy
scan 0 over added lines against the run-of-record population (adjudicated residue is reported per hit
with provenance, never silently); message scan 0 (MONEY / DIGITS / DATES); no secret, host, port or
token in any added line. At the train: the union cohort replay; `floor.sh` green; the cold run at the
composed tree (`coldrun.sh` → `webapp_data_train12_cold`) vs the Phase 2.1 run of record with
`--fail-on-regression` (2,625 → 2,625; 3,380 unchanged; 0 movers); remote CI green (run id recorded).

## Adversarial review plan
Every cell branch gets an independent adversarial review in the current orchestration environment (a
fresh agent that wrote none of the code and reads only the rulings, this card, the cell card, the diff
and the tests), findings reproduced before acceptance, BLOCK/MAJOR closed pre-compose, re-review green.
Attack list: a classification label reaching a financial verdict · the sealed store reachable from a
production import · the research partition selectable by a production replay · the research trigger
startable outside research mode or by a verdict · the native evidence changing a markdown byte · the
rotation transform disagreeing with Poppler's display orientation · under-partitioning of either key ·
the retired env contract still live · a second grouping or a second native reader · a statement literal
in a lexicon · the `refused` class weakening the validated-protection rule · the R9 removal changing any
deterministic-mode payload · the hosted opt-in literal defaulting on · a holdout sha admitted into a
research population · adjudication records writable from anywhere but the CLI · `psutil` or `fitz`
imported at module level where forbidden.

## Rules delta for Phase 2.2 cells (over BATCH9-RULES + PHASE2-RULES)
* Train **`train12`**; worktree `.claude/worktrees/mt22-<card>`, branch `wave22-<card>`; base = `train12`
  at your card's commit (T: the integration base named in its card). Cold caches
  `webapp_data_train8/9/10/11_cold` READ-ONLY; run of record = `TRAIN11-4f7d798/…-331d9136`.
* **Network:** NONE. No cell in 2.2 contacts the Vast host or any endpoint; the fake worker is in-process.
* **Customer data:** no production customer document leaves the machine; no archive text, figure, date
  or name in any tracked file (synthetic fixtures rendered from literal strings; dates ≥ 2031); the
  sealed store is never inside the checkout.
* **Cost / billing:** never measured, estimated, recorded or gated — Gustavo's ruling. Technical
  telemetry only.
* **Heavy proofs one at a time on this host:** targeted tests freely; the full suite / guards /
  conformance / gate / corpus slice / replay ONLY at closure and only after `tasklist | findstr python`
  shows no other harness; wait if one runs. Detached long runs with an `EXIT=` line on a durable log.
* Python 3.14 locally / 3.12 in CI — write for both. Report contract as PHASE2-RULES (failure-class
  evidence; escalation evidence for T and F) plus **identity evidence** (K: the two key changes and the
  pins), **classification evidence** (C/T: the disjoint sum), **firewall evidence** (H).
* W3 sections: `# §P22<CARD> — …` appended to `docs/moneythumb-replacement/W3_TRACKA_LOG.md`.

## Explicit exclusions (Phase 2.2)
Any Paddle run on customer data (2.3) · any routing change from classification (2.5) · a learned
classifier tier · structurer enablement or any `rows.py`/`core.py` reconstruction change (2.4) ·
`layout/` beyond the classifier (the LayoutModel is 2.4) · Unlimited · PP-OCRv6 · orientation pins ·
new bank parsers · page-level routing · `evidence_refs[]` on published values · the R10 repairs ceremony
(scheduled in 2.3) · the R14 integrity flag (2.4) · the declined branch (2.4) · Tesseract word boxes ·
a `local_free` install · cost telemetry of any kind. Opportunities exposed are DOCUMENTED in the cell's
W3 section, not built.

## Completion criteria (Phase 2.2 is complete only when ALL hold — then CONTINUE to 2.3 without asking)
Classifier delivered with the disjoint sum proven on the run of record (755 / 3,380) and every validated
exception named · taxonomy L0–L6 with drift guards · `refused` + transition matrix + both denominators
in the report · sealed store + adjudication CLI + holdout manifest + firewall proven · slice-1 queue and
packets prepared for Gustavo (adjudication NOT a gate) · native evidence persisted (schema 3) with sha
· display-frame geometry pinned (unrotated byte-identical; rotated by design) · geometry-aware analysis
key (stage 18) · research partitions refused by `run_of_record` · research mode proven end to end on
synthetic fixtures with the fake worker · R9 removed and the hosted edge fenced, deterministic mode
byte-identical · funnel/telemetry columns · every case above green · mutation tables complete ·
2,625 preserved payload-identical · newly validated 0 · OCR-fed validated 0 · no customer page left the
machine · proof floor green · adversarial reviews complete, findings reproduced and closed, re-reviews
green · cold run / replay green · CI green · docs durable (`BATCH9_TRANSITION.md` §7, `PHASE2_STATE.md`,
`PROJECT_STATUS.md`, this card's §Closure, the reviews) · worktree clean → **Phase 2.3 opens
(`PHASE2-3-WAVE.md`) without a user approval.**

## Closure (Ocean, 2026-09-11) — PHASE 2.2 COMPLETE; the completion criteria checked line by line

Composed code tree on `train12`: **`52bd8f2`** (K `87b5474` → C `40f619f` → H `e32c1a4` → F `b49bbc2` → Ocean's items `0f83190` / `4a9ba53` → T `72269f4` → the hermetic Paddle-config test pin `52bd8f2`, the one composed-tree integration fix — the first floor run's single red test read the host's minted worker token through the loader's reviewed fallback); every cell reviewed → closed → re-reviewed in the Fable 5.1 environment (K: APPROVE WITH FINDINGS twice; C: APPROVE WITH FINDINGS twice; H: APPROVE WITH FINDINGS → APPROVE; F: APPROVE WITH FINDINGS three times, the last with two MINORs carried; T: APPROVE WITH FINDINGS twice, the last item closed by a comment). Reviews under `reviews/PHASE2_P22{IDENTITY,CLASSIFY,HOLDOUT,FENCE,TRUTHTABLE}_REVIEW.md`. Fifteen `§P22*` W3 sections.

| criterion | held by | evidence |
|---|---|---|
| classifier delivered; disjoint sum 755 / 3,380 proven on the run of record; every validated exception named | C + T | `tools/classify_census.py`, `tools/p22truthtable_measure.py`: 3,380 == 3,380, 755 == 755; 431 validated exceptions by sha16 and kind (signal defects → the 2.3 precision cycle) |
| taxonomy L0–L6 with drift guards | T | `telemetry/unresolved_taxonomy.py`; precedence doc/code pin; L6 `unknown` structurally never empty |
| `refused` + transition matrix + both denominators in the report | T | `discovery/compare.py`, `discovery/report.py`, `tools/train8_compare.py`, `tools/truth_report.py` |
| sealed store + adjudication CLI + holdout manifest + firewall | H | `tools/holdout/`, `tools/adjudicate.py`, the firewall test; `truth/MANIFEST_DIGEST.txt` |
| slice-1 queue prepared (adjudication NOT a gate) | H | 214 packets under the private on-machine directory; nothing adjudicated |
| native evidence persisted (schema 3) with sha | K | `EXTRACTION_SCHEMA_VERSION` 3; `evidence_sha256` on native rows (T) |
| display-frame geometry pinned | K | unrotated byte-identical on the 12 pinned PDFs; rotated by design; the CropBox raster (RASTER_VERSION 2) |
| geometry-aware analysis key (stage 18) | K (+ Ocean item 2) | `ANALYSIS_STAGE_VERSION` 18; `reconstruction_mode` and `hosted_extraction_opt_in` in the settings key |
| research partitions refused by `run_of_record` | K + T | `research_partition` in the OCR key; the refusal; the research `--data-dir` fenced |
| research mode proven end to end on synthetic fixtures with the fake worker | T | one fake-worker request per page; rows carry the partition; auto mode has no path to the trigger |
| R9 removed and the hosted edge fenced; deterministic mode byte-identical | F | the union of every registration identical at base and closure; 30/30 mutants at the closure-3 tip |
| funnel / telemetry columns | T | `ROW_FIELDS` appended; `stage_extract` native 3,172 / tesseract 179 / not_attempted 16 / none 13; the Paddle telemetry columns declared and empty (the one-field change named for 2.3) |
| every case green; mutation tables complete | all | per cell: K 22/22 · C 28/28 · H 23/23 · F 30/30 · T 23/23 |
| 2,625 preserved payload-identical; newly validated 0; OCR-fed validated 0 | train | the cold run `TRAIN12-52bd8f2/2026-09-11T040247.502179-0000-fd6b4d7f` vs the Phase 2.1 run of record: 2,625 → 2,625; 3,380 unchanged (shared 3,380 = comparable 3,172 + quarantined 208; every class on the matrix diagonal; movers none; refused 0); compare exit 0; peak 1,261 MB; 5,966 s |
| no customer page left the machine | all | Paddle attempted 0; the two literals set in no run; the fake worker in-process |
| proof floor green | train | floor.log: suite 9,827 passed / 48 skipped / 39 deselected / 0 failed; guards 276; conformance 1,282; gate GREEN 105/3/1; corpus slice 34 |
| adversarial reviews complete, findings reproduced and closed, re-reviews green | all | the five review files |
| cold run / replay green | train | above |
| CI green | train | run 34567212012 (workflow_dispatch on `origin/train12` at `52bd8f2`; the conclusion recorded in the transition log's ON MAIN entry) |
| docs durable | Ocean | `BATCH9_TRANSITION.md` §7 (2026-09-10/11 entries), `PHASE2_STATE.md`, `PROJECT_STATUS.md`, this section, the reviews, the handoff |
| worktree clean | Ocean | `git status --short` empty but for the untracked `docs/moneythumb-replacement/superpowers/` left for Gustavo |

Carried to 2.3 (recorded residue, none blocking): K re-review N-1 / N-2 (population 0); C re-review R-1..R-4 and the 431 validated-exception residue (the precision cycle); F re-review-3 Q1 / Q2; T's Paddle-telemetry field; Ocean's optional item 3 (a durable worker record of the hosted-extraction refusal attribute); the lock rule; the `psutil` column's declared scope.

→ **Phase 2.3 opens (`PHASE2-3-WAVE.md`) without a user approval.**
