# Agent Handoff — P20-ROUTER (Phase 2.0 cell A: failure classes, the independent EscalationRouter, the ExtractionQualityGate, the Trigger-U split)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `docs/agent-handoffs/PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md`, then `PHASE2_ARCHITECTURE_PLAN.md` §1–§4 and §17
"Phase 2.0", then the umbrella `docs/agent-handoffs/PHASE2-0-SAFETY.md`. Ocean reviews and composes;
you never merge or push. **Hygiene card: `newly validated = 0`; every previously validated document
preserved with payload identical.** Nothing makes a network call. The visual rung stays disabled for
production.

# Why
`discovery/runner.py::_needs_visual_upgrade` (`:521-541`) escalates a Tesseract read to the visual rung
on `dispatch.outcome != "claimed"` — a STRUCTURAL failure (Class B) wearing an extraction failure's
clothes (Class A). It has never fired (0/3,506) but it is the shape that becomes "try OCR until it
balances" the day the rung is enabled. The validator has no architectural boundary that stops a
future edit from consulting its verdict before escalating. Phase 2.0 must make that edge impossible,
not merely absent.

# The invariant you are implementing
**Validator success may STOP escalation. Validator failure may NEVER START escalation.** Only
pre-financial evidence may start an extractor. There is no B → OCR edge and no C → OCR edge.

# Design (ruled — do not re-decide)
1. **New module `ocr/escalation.py`** (imports NOTHING from `analysis/`, `discovery/`, `webapp/`):
   * `FailureClass` — closed vocabulary `A_EXTRACTION`, `B_STRUCTURE`, `C_VALIDATION` (strings
     `"A"`, `"B"`, `"C"` on rows; `""` = no failure / not applicable).
   * `ExtractionTrigger` — the closed LEGAL start vocabulary:
     `image_only_document` (profile `classification == "scanned"` or `native_text_total_chars == 0`),
     `mixed_document_pages_without_native_text` (profile `classification == "mixed"`; recorded, and
     in 2.0 consumed only through the document-level triggers below),
     `offline_rungs_produced_no_text` (= R: the offline ladder returned `None`),
     `extractor_output_unusable` (= U-extract: the quality gate refused a produced read),
     `extractor_failed` (raster/endpoint/transport failure while the page remains unreadable),
     `operator_forced_visual` (an explicit operator instruction — the worker's `force_ocr` and the
     `--scanned-visual` mode's recovery/upgrade permission are recorded under this and the two above).
     `truncation_flagged` (= T) is DEFINED in the vocabulary and REFUSED by the router in 2.0
     (`ADMITTED_TRIGGERS` excludes it); its population is measured, never routed (OQ4).
   * The ILLEGAL start signals are not representable: `RouterInputs` is a frozen dataclass whose
     fields are exactly `profile` (a `DocumentProfile`), `evidence` (an `EvidenceQuality`),
     `triggers` (a frozenset of `ExtractionTrigger`), `attempted` (tuple of extractor ids already
     run), and `stop` (bool — "the current evidence is already `validated`"). There is NO field
     for a payload, report, dispatch, outcome, reason, parser id, reconciliation or ADB state, and a
     test asserts the field set by name (a new field fails the pin).
   * `ExtractionQualityGate.assess(document | None, profile) -> EvidenceQuality(usable: bool,
     reasons: tuple[str, ...], chars_total: int, pages_empty: int, pages_total: int)` — decides
     Class A BEFORE any parser or validator runs, from the produced text and the profile only. The
     usable-evidence definition is DETERMINISTIC and STRUCTURAL: (i) `document is None` → unusable
     (`no_text_produced`); (ii) total non-whitespace characters below the existing Tesseract floor
     (`ocr/local_tesseract.py:42`, 200) → unusable (`below_char_floor`); (iii) every page empty →
     unusable (`all_pages_empty`); (iv) at most ONE further structural criterion you can justify
     from the 179 Tesseract reads in the read-only cold cache
     (`.claude/recovery/webapp_data_train9_cold`, e.g. alphanumeric density below a floor you MEASURE
     and justify, not tune). Every criterion is named in `reasons`. The gate must classify all 36
     validated Tesseract reads as usable (pin: `validated ∩ U-extract = 0`, measured by the instrument
     below) — a definition that fails that pin is wrong, not "strict".
   * `EscalationRouter.decide(inputs: RouterInputs) -> Escalation(extractor: str | None, trigger:
     ExtractionTrigger | None, refused: tuple[str, ...])`. Rules, in order: `stop` → no extractor
     (`stopped_by_validated`); no trigger in `ADMITTED_TRIGGERS` → none; every candidate extractor
     already in `attempted` → none (`no_allowed_extractor_remains`); otherwise the FIRST allowed
     extractor of the fixed order `("local_tesseract", "visual")` not yet attempted, subject to the
     endpoint policy of `ocr/endpoint_policy.py` (cell B2; until it composes, import-guard the call
     so your branch runs without it and B2's module is consulted when present — Ocean composes B2
     first). The extractor order is a preference among ALLOWED extractors, never a retry loop.
   * A `FailureClass` assignment function `classify_failure(evidence: EvidenceQuality, claimed:
     bool | None, validated: bool | None) -> str` that lives in `discovery/runner.py` (NOT in
     `ocr/escalation.py`, which must never see `claimed`/`validated`): unusable evidence → `A`;
     usable and not claimed → `B`; claimed and not validated → `C`; validated → `""`.
2. **Runner rewiring (`discovery/runner.py`)** — the offline path is UNCHANGED (the offline read is
   still analysed exactly as today; that is the frozen baseline). What changes: (a) `_read` is
   followed by `ExtractionQualityGate.assess`; (b) the RECOVERY branch (`markdown is None`) and the
   UPGRADE branch both go through `EscalationRouter.decide` with `RouterInputs` built from profile +
   evidence + triggers only; (c) `_needs_visual_upgrade` is DELETED and replaced by the router
   decision computed BEFORE `_analyse` (it may be *applied* after, but its inputs are frozen before
   the analysis runs, and a test proves the decision is identical whether or not the analysis ran);
   (d) `stop=True` iff the offline analysis outcome is `validated` (the one legal verdict input, a
   STOP); (e) the row gains `failure_class`, `escalation_trigger`, `evidence_quality`
   (`usable|unusable|none`) and `escalation_refused` (the router's refusal reasons joined by `; `);
   (f) the runner keeps a per-run counter of escalations and REFUSES to escalate more documents than
   the run's own pre-computed Class-A trigger population (report it in `summary.json`).
   `discovery/report.py` writes the new columns (append at the END of the header so existing readers
   by name are unaffected; the compare tools read by name).
3. **Worker (`webapp/worker.py`)** — the deterministic-mode `force_ocr` path (`:418-424`) is routed
   through the router: the START is the operator's flag (trigger `operator_forced_visual`); the
   STOP is `stop = analysis is not None`, which is legal only because in deterministic mode a payload
   exists iff a parser claimed (`analysis/pipeline.py` raises on every other resolve outcome — cite
   the line in the docstring and pin it with a test). The worker has no `validated` classification
   at that point and must not invent one. Auto mode is unchanged (the ladder inside `parse_statement` is
   already profile-driven and A-only; you add the guard test in item 5 that keeps it so).
4. **Trigger-U split instrument `tools/phase2_trigger_split.py`** (read-only; registered in
   `corpus_gate.EXCLUDED_ANALYSIS_CALLERS` only if it calls the analysis — it should NOT; it reads
   `rows.csv` and the cold cache's OCR artifacts): over the batch-9 run of record it prints R, U,
   U-extract, U-structure, overlap, validated ∩ each, T's surface population, and the legal
   escalation population (R + U-extract), with the sha16 lists to a PRIVATE `--out` file. Its
   headline numbers go in your W3 section. Expected: R = 13, U = 123 (89 `no_parser_matched` + 34
   `parser_declined`), validated ∩ (R ∪ U) = 0; U-extract + U-structure = 123 exactly; the split
   itself is your measurement — do not assume it.
5. **Tripwires (tests that prove the ABSENCE of the forbidden edges):**
   * AST/import guard `tests/test_escalation_tripwires.py`: `ocr/escalation.py` and `ocr/pipeline.py`
     import nothing from `analysis`, `discovery`, `webapp`, `telemetry` (the ladder and the router
     cannot see a validator); no module under `analysis/` imports `ocr.escalation`, `ocr.pipeline`,
     `ocr.ocr_client`, `discovery` (the validator cannot reach an extractor) — measure the CURRENT
     `analysis/` → `ocr` imports first and pin the exact allowlist (types only, e.g. `ocr.document`,
     `ocr.truncation`); `RouterInputs.__dataclass_fields__` equals the pinned set; the name of every
     `decide(` call site in `discovery/` and `webapp/` passes a `RouterInputs` built by one constructor
     function whose parameters are pinned by name.
   * Behavioural (cases 1–4): CASE 1 usable Tesseract text no parser claims → row `failure_class=B`,
     `visual_rung=not_attempted`, `_forbid_visual` never trips, in `--scanned-visual` mode; CASE 2 a
     claimed parse whose reconciliation fails → `C`, no visual call; CASE 3 a read below the floor →
     `A`, the router names `visual` with trigger `extractor_output_unusable`, and on a second document
     where `attempted` already holds `visual` it names none; CASE 4 a validator that raises / returns
     a failing report cannot reach `decide` (the only path to `decide` is the runner's constructor;
     prove by mutation: a mutant runner that passes `dispatch.outcome != "claimed"` into a trigger
     must be killed by CASE 1; a mutant that adds a `payload` field to `RouterInputs` is killed by
     the field pin; a mutant that removes `stop` handling is killed by a validated-Tesseract fixture
     that must NOT escalate).
   * `validated ∩ class-A = 0` pinned as a test over the run of record's `rows.csv` + the gate (the
     instrument's number, asserted).
   * The existing `tests/test_visual_rung.py` "cached analysis does not trigger a spurious escalation"
     stays green with the new mechanism (a D-3 analysis hit has no observable dispatch; your
     decision must not depend on one).
6. **Vocabulary:** `telemetry/record.py` gains `FAILURE_CLASSES = ("A", "B", "C", "")` and
   `EXTRACTION_TRIGGERS` (the closed tuple, mirrored from `ocr/escalation.py` and held equal by a
   test) so a row/record token from outside the vocabulary is refused. Do NOT touch `SOURCE_PATHS` /
   `source_path_for` (cell B2 owns that function).

# Mutation table (minimum; name every killer)
| mutant | expected killer |
|---|---|
| router escalates on `dispatch.outcome != "claimed"` | CASE 1 |
| router escalates on a failing reconciliation / withheld ADB | CASE 2 |
| `stop` ignored (validated Tesseract read escalates) | CASE 4 stop test |
| `truncation_flagged` admitted | the T-refusal test (OQ4) |
| router returns a remote/paid extractor id | endpoint-policy guard test (with B2's module stubbed absent → none) |
| a second extractor runs after `attempted` already holds it | CASE 3b |
| runner escalates more documents than the trigger population | the counter refusal test |
| `RouterInputs` gains a `payload` field | the field pin |
| `analysis/pipeline.py` imports `ocr.escalation` | the import guard |

# Measurements to report (W3 §P20ROUTER + your final message)
R · U · U-extract · U-structure · overlap · validated ∩ each · T surface · legal escalation population
· the quality-gate criteria and the census that justified them (distribution of chars_total / empty
pages over the 179 Tesseract reads and the 36 validated among them) · cohort replay at base
(`--expect-identical`) and at closure over: the 179 Tesseract shas + the 13 R shas + every visual-rung
test fixture family (`cohort_replay --shas <private file>`; both exit 0; 0 newly validated; preserved
all identical) · mutation table · tripwire list · tests added · targeted suite · guards · privacy 0.

# Ownership
`ocr/escalation.py` (new), `discovery/runner.py`, `discovery/report.py`, `webapp/worker.py`,
`telemetry/record.py` (ONLY the two new vocabularies; nothing else), `tools/phase2_trigger_split.py`
(new), `tests/test_escalation_router.py`, `tests/test_escalation_tripwires.py`, updates to
`tests/test_visual_rung.py` / `tests/test_discovery.py` / `tests/test_telemetry.py` where the row
schema or vocabulary pins live, W3 `§P20ROUTER`. NOT yours: `ocr/config.py`, `ocr/document.py`,
`ocr/ocr_client.py`, `ocr/render.py`, `ocr/pipeline.py`, `webapp/artifact_cache.py`,
`tools/cohort_replay.py`, `telemetry/stated_counts.py`, `webapp/static/*`, `analysis/*`.

# Exclusions
No PaddleOCR id in the extractor order (add the SLOT comment, not the code). No page-level routing.
No Trigger T routing. No change to `parse_statement`'s ladder order. No change to what the offline
partition produces (cohort replay must be byte-identical). No new columns anywhere but the row.

# Git
Base `train10` at your handoff's commit. Branch `wave20-router`, worktree `.claude/worktrees/mt20-router`.
