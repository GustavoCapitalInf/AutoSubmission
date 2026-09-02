# Agent Handoff — P21-ROUTING (Phase 2.1 cell R: the Paddle rung wired into the ONE ladder and the ONE router — admitted Class-A triggers only; per-page provenance; the artifact record; the settings key; the discovery mode; the vocabularies; the forbidden edges proved absent)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `docs/agent-handoffs/PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (all of it — Ruling A, Ruling B, the Vast
authorization and the privacy boundary bind you), then the umbrella `docs/agent-handoffs/PHASE2-1-PADDLE.md`
(every section; D4, D6, D8; cases 1, 2, 3, 4, 9, 10, 12, 14, 15, 19, 20), then `ocr/escalation.py`,
`ocr/pipeline.py`, `ocr/document.py`, `discovery/runner.py` (all of the recovery/upgrade block),
`webapp/artifact_cache.py` (`ocr_settings_key`, `_ocr_extractor`, `put_ocr`, `cached_ocr`,
`EXTRACTION_SCHEMA_VERSION`), `telemetry/record.py`, `telemetry/run_of_record.py`,
`tools/train/provenance.py`, `ocr/paddle_config.py` + `ocr/paddle_rung.py` + `tests/paddle_fake_worker.py`
(cell P's, composed on your base — the rung is the ONLY Paddle entry you call), `evidence/canonical.py`,
and the Phase 2.0 tripwires `tests/test_escalation_tripwires.py` / `tests/test_escalation_router.py`.
Ocean reviews and composes; you never merge or push. **Hygiene card in coverage clothing:
`newly validated = 0` in every replay you run (the Paddle path never receives a customer document in
this phase — D8); every previously validated document preserved with payload identical; the offline
ladder's page strings byte-identical under the new schema version.**

# Why
Phase 2.0 left a SLOT: `EXTRACTOR_ORDER = ("local_tesseract", "visual")` with a comment naming
PaddleOCR's place; `_ocr_extractor` with a legibility slot; `source_path_for` with a closed
fallthrough; `run_of_record` with `visual_ocr_key` only. Filling those slots is where every forbidden
edge could quietly appear: a runner that escalates an unclaimed Tesseract read "because Paddle is
there", a webapp auto mode that discovers a new hosted hop, a cache that serves a Paddle read for an
offline key, a replay that picks the wrong partition. This cell fills the slots and proves, by
structure and by mutation, that none of those edges exists.

# Design (ruled — do not re-decide)
1. **Router (D4).** `ocr/escalation.py`: `EXTRACTOR_ORDER = ("local_tesseract", "paddle",
   "visual")`; `RouterInputs` gains `enabled: frozenset[str]` (the extractors THIS RUN may use — a
   mode constant known before any document is read); `router_inputs(...)` gains the keyword-only
   `enabled`; `decide` picks the first extractor in `EXTRACTOR_ORDER` that is in `enabled` and not in
   `attempted` (else `no_allowed_extractor_remains`). `ADMITTED_TRIGGERS` UNCHANGED (T refused; the
   density signal never a trigger — Ruling B). Update the tripwires: the field pin becomes the six
   names; the constructor parameter pin gains `enabled`; ADD a repo-wide AST tripwire that at every
   `decide(` call site the `enabled=` argument is an attribute reference on `self` or a module-level
   constant (`self.enabled_extractors`, `ENABLED_…`), never a call, comprehension, subscript or
   conditional — a per-document fact cannot be smuggled in through a mode field. `RouterInputs.
   __subclasses__() == []` stays. `webapp/worker.py::_force_ocr_decision` passes
   `enabled=WORKER_ENABLED_EXTRACTORS` = `frozenset({"visual"})` (a module constant; the webapp is NOT
   wired to Paddle — Ruling A; its behaviour is byte-identical). `discovery/runner.py` sets
   `self.enabled_extractors` from the mode: `MODE_SCANNED_VISUAL → {"visual"}`, the new
   `MODE_SCANNED_PADDLE → {"paddle"}`, every other mode → `frozenset()`.
2. **Ladder (`ocr/pipeline.py`).** `parse_statement(..., allow_paddle_ocr: bool = False,
   paddle_data_scope: str | None = None)`. The Paddle rung runs ONLY on the forced path:
   `force_ocr and allow_paddle_ocr` — and `allow_paddle_ocr and allow_visual_ocr` together is a
   `ValueError("one OCR extractor per call; the router chooses")`. The NON-forced ladder is UNCHANGED
   (native → Tesseract → return / `None`); `allow_paddle_ocr` is INERT there (CASE 12: the auto-mode
   fallthrough to the visual rung is pre-existing and stays exactly as it is; it does NOT gain a Paddle
   arm — Ruling A). The rung: `from .paddle_rung import read_document` LAZILY inside the branch (add the
   `sys.modules` absence assertion for `ocr.paddle_rung` / `ocr.paddle_client` after an offline run,
   beside the existing `ocr.ocr_client` one); `read = read_document(pdf_bytes, document_sha256=<from
   profile.content_sha256, else ocr.inspect.content_sha256>, data_scope=paddle_data_scope, dpi=dpi)`
   (`paddle_data_scope` REQUIRED — `None` with `allow_paddle_ocr` is a `ValueError`); the result becomes
   `StatementMarkdown(source_file, model=PADDLE_MODEL_TOKEN, pages=read.pages,
   page_integrity=assess_pages(read.pages), page_extractor=read.page_extractor,
   evidence=read.evidence)`. `PaddleRefused` / `PaddleTransportError` PROPAGATE (the caller records
   them — never caught here, never a hop). `on_stage("paddle_ocr")`. No postprocess: the Paddle page
   strings never pass through `ocr_client.postprocess` / `apply_admitted` (CASE 10 — prove by AST that
   `ocr/pipeline.py`'s Paddle branch references neither, and by a runtime spy).
3. **Seam object (`ocr/document.py`).** `StatementMarkdown` gains `page_extractor: list[str] =
   field(default_factory=list)` and `evidence: object | None = None` (typed as `object` to keep this
   module free of any `evidence` import? — NO: import `evidence.canonical.ExtractionEvidence` for the
   type; `evidence/` is neutral and stdlib-only, so this import widens no pinned boundary; add the
   assertion that `ocr/document.py` imports nothing but `evidence`, `.config`, `.truncation`).
   `to_markdown()` BYTE-IDENTICAL (the committed corpus artifacts pin it — run
   `tests/test_filename_boundary.py` and the corpus artifacts' hash checks). The ladder sets
   `page_extractor` for EVERY rung: native → the native model token per page, Tesseract →
   `"local-tesseract-ocr"` per page, visual → `settings.model` per page, Paddle → the read's list.
   `__post_init__`: `page_extractor`, when non-empty, must have `len(pages)` entries, each passing
   `validate_model_token(..., allow_reserved=True)`; `evidence`, when present, must be an
   `ExtractionEvidence` whose page count equals `len(pages)` and whose `page_texts()` EQUAL `pages`
   (the derived strings and the evidence are one object; a drift is refused).
4. **Token vocabulary.** `ocr/config.py::RESERVED_MODEL_PREFIXES` gains `PADDLE_MODEL_TOKEN` (an env
   `OCR_MODEL` cannot impersonate the rung; `tests/test_ocr_provenance_injection.py` extended).
   `telemetry/record.py`: `SOURCE_PATHS = ("native", "local_tesseract", "paddle", "visual", "none")`;
   `PADDLE_MODEL_TOKENS = frozenset({PADDLE_MODEL_TOKEN})` beside `VISUAL_MODEL_TOKENS` (imported from
   `ocr.paddle_config`? — `telemetry` may import `ocr` (it already imports nothing from it; check
   `telemetry/record.py`'s existing imports and the tripwires: `ocr/escalation.py` must not import
   `telemetry`, the reverse is not forbidden — but keep the discipline the visual token uses: a
   LITERAL mirrored here and held equal to `ocr.paddle_config.PADDLE_MODEL_TOKEN` by a test);
   `source_path_for` maps exactly that token → `"paddle"`; any other `paddle…` string stays `"none"` +
   `source_path_unrecognized_model` (update the P20-SEAM fallthrough test that asserts `paddle+x` →
   `none` to say so explicitly); `source_section` gains `evidence_sha256`, `provider`,
   `execution_class` (from `doc.evidence.runtime` when present, else `None`); `model_calls_for`
   reports one call per Paddle page, `purpose: "paddle_ocr"`, the unpriced model named (NOT added to
   `FREE_MODELS`). `FAILURE_CLASSES` / `EXTRACTION_TRIGGERS` unchanged.
5. **Artifact record + key (D6).** `webapp/artifact_cache.py`: `EXTRACTION_SCHEMA_VERSION` 1 → 2
   with its pin (`tests/test_artifact_cache.py`) in the SAME commit; `put_ocr` stores
   `page_extractor` and `evidence` (`evidence.to_json`) beside `model/pages/page_integrity`;
   `cached_ocr` restores both (`evidence.from_json` — a drifted cached copy raises, and THAT is
   surfaced as a cache miss-with-finding, never served); `_ocr_extractor(force_ocr, allow_local_ocr,
   allow_visual_ocr, allow_paddle_ocr)` returns `"paddle"` for `force_ocr and allow_paddle_ocr`
   (truth table pinned; `"visual"` and `"offline"` unchanged); `ocr_settings_key` gains
   `allow_paddle_ocr` (boolean partition field, v5+ material — NOTE: adding it changes the offline key
   too; that is accepted and the reason the train's cold run is required) and, when the extractor is
   `"paddle"`, the block `paddle_settings_key_material(load_paddle_settings())` — and when Paddle
   settings CANNOT be loaded (no env) the paddle-labelled key must REFUSE (raise
   `PaddleConfigError`), never fall back to a default block; the offline/visual keys never touch
   Paddle settings (assert no `ocr.paddle_config` import on the offline path — lazy import inside the
   paddle branch). `cached_ocr` gains `allow_paddle_ocr`. `OCR_STAGE_VERSION` stays 5.
6. **Discovery.** `MODE_SCANNED_PADDLE = "scanned-paddle"` (`--scanned-paddle`; in `LOCAL_OCR_MODES`
   like scanned-visual; mutually exclusive with the other modes); `_read_paddle(raw, name, profile)`
   mirrors `_read_visual` with `parse_statement(force_ocr=True, allow_local_ocr=False,
   allow_visual_ocr=False, allow_paddle_ocr=True, paddle_data_scope="customer")` — the LITERAL
   `"customer"` (the runner reads the archive; a test asserts by AST that `_read_paddle` passes exactly
   that literal); `PaddleRefused` and `PaddleTransportError` are caught THERE (like `_read_visual`
   catches `Exception`) and returned as the error type; the recovery and upgrade branches dispatch on
   `decision.extractor` (`"paddle"` → `_read_paddle`; `"visual"` → `_read_visual`; anything else →
   the existing `escalation_refused` terminal row); CLI preflight: `--scanned-paddle` calls
   `ocr.paddle_client.probe()` and refuses to start when unavailable (mirror the visual probe; print
   the reason token, never a host); the escalation budget applies unchanged. Rows (`discovery/report.py`,
   APPENDED at the end of `ROW_FIELDS`): `paddle_rung` (vocabulary = `visual_rung`'s plus
   `refused_customer_data`), `cache_paddle`, `escalation_extractor` (`""|paddle|visual`),
   `evidence_sha256`, `paddle_provider`, `paddle_execution_class`; `summarize` counts `paddle_rung`
   and `escalation_extractor` like `visual_rung`. A refusal from the rung's authorization gate
   (`PaddleRefused.reason == "remote_customer_data_refused"`) is recorded `paddle_rung =
   refused_customer_data`, `outcome_class/outcome_reason = failed / paddle_refused`, `error_type =
   PaddleRefused` — a named, counted finding (D8), never silent, never a hop.
   `GATE_ASSESSED_SOURCES` gains `"paddle"`. `tools/phase2_trigger_split.py` — no change (report
   only).
7. **Run of record.** `telemetry/run_of_record.py`: `partitions.paddle_ocr_key` optional like
   `visual_ocr_key`; `ocr_keys_by_source["paddle"]`; a row with `paddle_rung ∈ {recovered, upgraded}`
   → the paddle key (and never the visual key, and vice versa — test both); reconstruction for older
   runs unchanged (they have no paddle key; a paddle row on such a run resolves to `None`).
   `tools/train/provenance.py` records `paddle_ocr_key` when Paddle settings load (else omits it with
   a note — never a placeholder key). `tools/cohort_replay.py`: no change unless a reader you touched
   requires it; if so, the smallest change and a test.
8. **CASE 9 (disagreement).** When the UPGRADE path adopts a Paddle read (the SAME validator produced
   a payload), the row keeps BOTH source paths recorded (`source_path` = the adopted read;
   `escalation_extractor` = paddle; the offline read's model in a new row field `offline_source_model`)
   and the OCR cache holds both partitions — no fusion, no merge of page strings, no choice by which
   one reconciles (a mutant that adopts the Paddle read when the offline one had a payload is killed
   by the `stop`/`_upgrade_eligible` tests: a claimed offline read is never escalated). Two-engine
   escalation (paddle AND visual on one document) is NOT possible in this phase — `enabled` holds one
   extractor per mode; pin it.
9. **CASE 19.** The offline partition's page strings and `to_markdown()` are byte-identical under
   `EXTRACTION_SCHEMA_VERSION` 2: cohort replay `--expect-identical` at base and at closure over the
   full archive (`--allow-unresolved` / `--expect-unresolved 29` as Phase 2.0 did; `discovery_reports/
   TRAIN10-941918f/2026-09-02T063646.710847-0000-ef34ee30`, data dir `.claude/recovery/webapp_data_train10_cold`
   READ-ONLY) — and note that the replay reads the OLD cache (schema 1 records): it must still load
   them (`page_extractor` absent → `[]`, `evidence` absent → `None`), which is itself a test.

# Files you own (exact; nothing else)
`ocr/escalation.py` · `ocr/pipeline.py` · `ocr/document.py` · `ocr/config.py` (`RESERVED_MODEL_PREFIXES`
only) · `webapp/artifact_cache.py` · `webapp/worker.py` (the `enabled=` argument + the constant only)
· `discovery/runner.py` · `discovery/cli.py` · `discovery/report.py` · `telemetry/record.py` ·
`telemetry/run_of_record.py` · `tools/train/provenance.py` · `tools/cohort_replay.py` (only if
required) · tests: `tests/test_escalation_router.py`, `tests/test_escalation_tripwires.py`,
`tests/test_visual_rung.py`, `tests/test_artifact_cache.py`, `tests/test_run_of_record.py`,
`tests/test_cohort_replay_selection.py`, `tests/test_telemetry.py`, `tests/test_q3_native_only.py`
(CASE 14 addition only), `tests/test_ocr_provenance_injection.py`, `tests/test_discovery.py`,
`tests/test_pipeline.py`, `tests/test_no_statement_hardcodes.py` (extend the OQ2 scans to `evidence/`
and `tools/paddle_vast.py` — CASE 15), and the new `tests/test_paddle_routing.py` (cases 1, 2, 3, 4, 9,
10, 12, 14, 18-runner-half, 19, 20 through the REAL `DiscoveryRunner` with `tests/paddle_fake_worker.py`
and `ocr.pipeline`-level seams) · your W3 section. Not yours: `ocr/paddle_*.py` except
`paddle_config.py`'s reserved-token consumer, `evidence/`, `analysis/`, `tools/paddle_vast.py`.

# Cases you must prove (each through the real runner unless a unit test is stated)
1 — a `--scanned-paddle` run on an image-only PDF whose Tesseract rung returns `None` (R) → the
router names `paddle` (`escalation_trigger = offline_rungs_produced_no_text`), `_read_paddle` runs
(fake worker sees exactly the page count), the read analyses through the SAME `_analyse`, and — with
the runner's `"customer"` scope against a `remote_paid` fake — the rung REFUSES (`paddle_rung =
refused_customer_data`) while the same run with a `local_free` fake proceeds to `recovered`; the
U-extract shape (a gate-unusable Tesseract read: 40 characters) likewise names `paddle` · 2 — the
usable-but-unclaimable Tesseract read (`USABLE_UNCLAIMABLE`) → `no_admitted_trigger`, the fake worker
sees ZERO requests, `paddle_rung = not_attempted`, `failure_class = B` · 3 — a claimed read that
fails financial validation (Class C; use an existing pinned-refusal corpus artifact as the Tesseract
text, as `test_escalation_router.py` already does) → zero requests, `failure_class = C` · 4 —
`PADDED_TABULAR` (density-surfaced, usable) → zero requests · 9 — as §8 · 10 — AST + spy · 12 —
`parse_statement(allow_paddle_ocr=True)` without `force_ocr` never imports `ocr.paddle_rung`; the
worker (`webapp/worker.py`) has no `allow_paddle_ocr` call site (AST) and `WORKER_ENABLED_EXTRACTORS ==
{"visual"}`; auto mode's behaviour on the Class-B fixture is byte-identical to Phase 2.0 (pin the
existing test) · 14 — a Paddle-fed `StatementMarkdown` through `analysis.provenance.extractor_model`
→ `paddle-ocr+ppocrv5`, and the Q3 gate refuses (`q3_provenance_refused`) · 15 — the OQ2 scans over
`evidence/` and the Paddle tool · 18 — `_read_paddle` on a fake worker that refuses connections / 500s
/ times out → `paddle_rung = failed`, `outcome_reason = ocr_failed`, `error_type` = the class name,
and `_read_visual` was NEVER called (spy) · 19 — as §9 · 20 — as case 1's refusal leg plus the AST
literal pin.

# Mutation table (every mutant, every killer named)
M1 upgrade triggers gain `dispatch.outcome != "claimed"` → case 2 · M2 `enabled` ignored (router
picks paddle in scanned-visual) → the visual-rung suite (32 tests) · M3 `enabled` computed from
`evidence.usable` at a call site → the AST tripwire · M4 `_read_paddle` passes `"synthetic"` → the
literal pin + case 1's refusal leg · M5 `parse_statement` runs the Paddle rung on the non-forced
path → case 12 · M6 the Paddle branch calls `apply_admitted` → case 10 · M7 `page_extractor` unchecked
length → the seam validation test · M8 `evidence.page_texts() != pages` accepted → the drift test ·
M9 `_ocr_extractor` returns `"visual"` for paddle → the truth table · M10 `EXTRACTION_SCHEMA_VERSION`
left at 1 → the pin · M11 `ocr_partition_for_row` returns the visual key for a paddle row → the
run-of-record test · M12 `source_path_for("paddle-ocr+ppocrv5")` → `"visual"` → the vocabulary test
· M13 `PADDLE_MODEL_TOKEN` added to `FREE_MODELS` → the prices test · M14 `_read_paddle` catches
`PaddleTransportError` and calls `_read_visual` → case 18 · M15 `RESERVED_MODEL_PREFIXES` without the
token → the injection test · M16 the worker's constant becomes `{"visual", "paddle"}` → case 12.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python
corpus_gate.py` GREEN; `pytest -m corpus`; cohort replay per §9 (base `--expect-identical`, closure
`--expect-identical`); the archive sweep is NOT required (no analysis reader changed — say so);
privacy scan 0; message scan 0; the secrets scan (no `PADDLE_VAST_*` VALUE in any added line);
`tests/test_visual_rung.py` 32/32 unchanged in meaning. Two harnesses never run concurrently on this
host (`tasklist | findstr python` first).

# Report contract (final message to Ocean AND your W3 section `# §P21ROUTING — …`)
population (the fixtures; the replay population) · root cause · solution · newly validated (0) ·
other ladder movement (0) · previously validated preserved (all, identical; the replay numbers) ·
regressions (0) · failure-class evidence (which of A/B/C each case touches and the test proving the
forbidden edge absent) · escalation evidence (legal population unchanged at 13; the refusal
counters) · remote evidence (every Paddle request in the suite went to the in-process fake on
loopback; zero real requests) · commits · proof-floor exits · privacy + secrets counts · risks last.

# Exclusions
No webapp Paddle wiring (Ruling A). No page-level routing. No Trigger T / density admission. No
two-engine escalation. No `evidence_refs[]`. No Unlimited enablement. No change to `ADMITTED_TRIGGERS`,
`classify_failure`, `ExtractionQualityGate`, `CHAR_FLOOR`, `ALNUM_DENSITY_FLOOR`. No customer data
to any worker (the runner's `"customer"` literal + the absent second opt-in guarantee it; you never
set `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN`, in tests or otherwise — a test asserts the literal is absent
from the environment the suite runs in). No real network in the default suite.
