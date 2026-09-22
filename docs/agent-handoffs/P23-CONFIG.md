# Agent Handoff — P23-CONFIG (Phase 2.3 cell V: the two ruled configuration A/Bs — R6 orientation classifiers, R5 PP-OCRv6 — as separately pinned blocks and partitions; the production pin untouched)

**Launch base:** the `train13` tip Ocean names at launch, AFTER cell W (P23-WAVE) has composed — your runs go
through W's runner (`tools/paddle_wave.py run --config <block>`) and its lifecycle; you add the blocks it
selects. Worktree `.claude/worktrees/mt23-config`, branch `wave23-config`.

Read `docs/agent-handoffs/BATCH9-RULES.md`, `PHASE2-RULES.md`, `docs/moneythumb-replacement/PHASE2_RULINGS.md`
(R5 and R6 verbatim; the Paddle customer-data authorization — SLICE and the wave are in scope; R2 WITHDRAWN;
"do not silently switch to PP-OCRv6"; the Phase 2.1 Vast authorization: a pin change is its own reviewed
edit and partition), the umbrella `docs/agent-handoffs/PHASE2-3-WAVE.md` (D10, case 11, the exclusions), the
plan §G.2.3 cell V and §H.2, `docs/moneythumb-replacement/PADDLE_VAST_RUNBOOK.md`, `PADDLE_MEASUREMENTS.md`,
then the code: `ocr/paddle_config.py` (the pins `PADDLE_OCR_VERSION`, `PADDLE_TEXT_DETECTION_MODEL`,
`PADDLE_TEXT_RECOGNITION_MODEL`, the five switches including `use_doc_orientation_classify` /
`use_textline_orientation` OFF, `PADDLE_MODEL_TOKEN`, `PADDLE_WORKER_CONTRACT`, the settings-key material),
`ocr/paddle_worker.py` (how the worker loads its models and answers `/version`), `ocr/paddle_client.py` (the
identity verification against the pins — nine fields), `ocr/paddle_rung.py`, `tools/paddle_vast.py`
(`deploy`, `start`, `measure`), `webapp/artifact_cache.py::ocr_settings_key` (what partitions the key: the
model token, the pins, `research_partition`), `tools/paddle_wave.py` (cell W's `--config`), the W3 sections
`# §P21PADDLE*` and `# §P23WAVE`. Ocean reviews and composes; you never merge or push. **Hygiene card:
`newly validated = 0`; the PRODUCTION configuration block byte-identical to Phase 2.1 (a test pins every pin);
production code never reads an A/B block; every A/B page lands in its OWN research partition; no cost
field; the two literals only in the run's environment.**

# Why
R5 (PP-OCRv6 — Baidu's claimed detection/recognition gains, unproven on statements) and R6 (the orientation
classifiers, the layout memo's first recommendation for scanned/mixed pages) are ruled YES as MEASURED
alternatives: separately pinned, separately partitioned, compared on named criteria, never switched into
production by this milestone. The comparison is what 2.5 will read.

# What you deliver (ruled — do not re-decide)
1. **Configuration blocks in `ocr/paddle_config.py`:** a closed registry `PADDLE_CONFIGURATIONS` of exactly
   three frozen blocks — `paddle-v5-prod` (the Phase 2.1 pins, byte-for-byte; the ONLY block production code
   resolves — `load_paddle_settings()` without a configuration argument yields it, and a test pins every field
   against the module's Phase 2.1 constants), `paddle-v5-orient` (the same models with
   `use_doc_orientation_classify=True` and `use_textline_orientation=True`; model token
   `paddle-ocr+ppocrv5+orient`), `paddle-v6` (`PP-OCRv6` detection and recognition models named exactly as
   Baidu publishes them at the pinned PaddleOCR 3.7 — record the names and their versions; token
   `paddle-ocr+ppocrv6`). Each block is settings-key material through its own token (a page read under two
   blocks is two OCR artifacts); each block's identity is verified by the client against ITS pins (the worker
   reports the loaded configuration); a block never inherits a field silently (frozen dataclass, explicit).
2. **The worker loads a configuration:** `paddle_worker.py` takes the configuration id at `start` (through
   `tools/paddle_vast.py start --config`), loads exactly that block's models and switches, and reports the
   id and the pins in `/version`; the client refuses a worker whose reported configuration differs from the
   requested one (a mismatch is a `PaddleRefused` before any `/ocr`). Model weights for v6 are downloaded on
   the instance by `deploy --config paddle-v6` (weights are not customer data); the download is recorded by
   name and size in the log, never by URL with a token.
3. **The runs (through W's runner, each its own partition, the two literals in the run's environment):**
   `research/paddle-v5-orient` over the scanned and mixed pages of CTRL and U755 (from the rows'
   `classification`; ≈ 600 pages); `research/paddle-v6` over SLICE + a 200-page stratified sample of U755
   (by census family and modality; the sample file and its digest in your W3). CTRL's orientation pages first.
4. **`tools/paddle_config_ab.py`** — READ-ONLY over the partitions: for every page read under two blocks,
   R5's comparison list — numeric and character fidelity (through cell X's agreement functions against the
   native words where they exist; between the two Paddle readings otherwise), missing / extra tokens,
   geometry (box count and regularity from cell E's metrics), completeness (word count per page), scanned
   pages separately, false evidence (words with no ink under them — E's ink metric), stability (two reads
   of the same page under one block — sha equality), latency and VRAM (from the technical telemetry).
   Downstream reconstruction is cell B's (its fallout funnel per configuration reads your partitions).
   Output: counts and percentiles per configuration and per modality; never a page's text; never a sha beside
   a verdict.
5. **Never a silent switch:** `ocr/escalation.py`, `discovery/runner.py`'s production modes and the webapp
   read `paddle-v5-prod` only (AST pins: the only configuration literal outside the registry and the wave
   runner is `paddle-v5-prod`); the cold run's OCR key at the train is unchanged (the production block's
   token unchanged).
6. **No hardcodes:** the OQ2 scans cover the tool.

# Files you own (exact; nothing else)
`ocr/paddle_config.py` (the registry and the loader's configuration argument; the production block's values
UNCHANGED) · `ocr/paddle_worker.py` (loading by configuration; `/version`'s configuration fields) ·
`ocr/paddle_client.py` (the per-configuration identity check and the whitelist entries) · `ocr/paddle_rung.py`
(threading the configuration to the client) · `tools/paddle_vast.py` (`--config` on `deploy` / `start`) ·
`tools/paddle_config_ab.py` (new) · `tests/test_paddle_config.py`, `tests/test_paddle_worker*.py`,
`tests/test_paddle_client*.py`, `tests/test_paddle_rung.py` (APPEND) · `tests/test_paddle_config_ab.py` (new) ·
`tests/test_no_statement_hardcodes.py` (the roots append) · `docs/moneythumb-replacement/PADDLE_VAST_RUNBOOK.md`
(the configurations section) · `PADDLE_MEASUREMENTS.md` (the per-configuration figures) · your W3 section.
`tools/paddle_wave.py` (cell W's — report a needed change), `ocr/escalation.py`, `analysis/**`, `layout/**`,
`evidence/**`, `telemetry/**`, `webapp/**` are NOT yours.

# Mutation table (run every mutant, name every killer)
M1 the production block's `use_textline_orientation` flipped → the byte-for-byte pin · M2 a block inheriting
a field from another → the explicit-field test · M3 the client accepting a worker that reports another
configuration → the mismatch refusal test · M4 two blocks sharing a model token → the distinct-token /
distinct-key test · M5 production code resolving `paddle-v6` (planted in a scratch copy of the runner) → the
AST pin · M6 an A/B page written under the production partition → the partition test · M7 the comparison
tool printing a page's text → the output-shape test · M8 the v6 model names silently changed → the pin ·
M9 a cost key in the measurements → the grep test · M10 `deploy --config paddle-v6` sending anything but
the worker script and weight requests → the transport test on the fake runner.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus`; every Paddle test file; `cohort_replay --expect-identical` at base and
closure over the `--parser` chunks (the OCR key material changed for A/B blocks ONLY — the production key must
be byte-identical: prove it directly); the live A/B runs with their logs and attestations (through W's
runner, its lock sessions); the comparison over both partitions; privacy scan 0 over added lines; the
message scanner over your run logs; message scan 0 over commits. Heavy proofs and wave sessions one at a
time under `discovery_reports/train13-logs/HARNESS.lock` (mkdir-only; own-holder release; Git bash `rmdir`).

# Report contract (final message to Ocean AND your W3 section `# §P23CONFIG — …`)
population (the orientation pages; SLICE + the 200-page sample; digests) · root cause · solution · newly
validated 0 · ladder movement 0 · preserved all, identical (the production key unchanged) · regressions 0 ·
the R5 comparison table and the R6 comparison table (per modality; counts and percentiles) · identity
evidence (the production block pinned; the tokens distinct) · technical performance per configuration
(no cost) · commits · proof exits · privacy count · risks last (what the comparison cannot say until cell B's
fallout per configuration).

# Exclusions
No production pin change · no routing · no admission of either configuration · no fusion of readings · no
cost · no page outside the named populations · no Paddle call outside W's runner.

---

# Bounded configuration clarification — 2026-09-15

Status: root-adopted clarification after independent source/design review, 2026-09-15. This authorizes only the bounded implementation below, starting at the actual launch tip named by root after W composes. It is not a V launch, implemented change, passed proof, model deployment, or authority for a broader OCR integration. Existing R5/R6 customer-data, retention, opt-in, privacy, serialized-proof, production-identity and no-Phase-3 boundaries remain in force.

This clarification makes the existing V deliverables implementable through W's real call chain and documents the limited research geometry treatment that those deliverables require. It does not authorize production admission, alternate backends, general OCR replacement, additional customer populations, or a production pin/key/schema change.

## 1. Exact source basis and configuration identities

Use these preserved private memos together:

- `official-pins-and-geometry.md`: exact PaddleOCR v3.7.0 release source, commit `b03f46425e8ff4442b268ce449e3eef758146cd4`.
- `PADDLEX-3.7.2-ADDENDUM.md`: recorded PaddleX 3.7.2, exact source commit `ffb64904d23708863ff5b8da312a5cbd52a7f462`; ten inspected relevant files are byte-identical to PaddleX v3.7.0 `e0068ce0bfe75b2992e5b38d06a0393c70f887f7`. This is a bounded source comparison, not whole-package/runtime equivalence.
- `LINE-ORIENTATION-SEAM.md`: same exact 3.7.2 source, including the subsequently inspected cropper/export/box-converter; no model or geometry proof was executed by that memo.
- `CONFIGURATION-THREADING-SEAMS.md`: W executable `789751866ed47fd049711ba775d14a89c656ae45` plus root configuration/cache/discovery seam inspection. Refresh against V's actual composed launch tree.

The registry remains exactly three frozen, explicit blocks:

| Block / research partition | Detection / recognition | Orientation models and switches |
| --- | --- | --- |
| `paddle-v5-prod` | `PP-OCRv5_server_det` / `en_PP-OCRv5_mobile_rec` | Preserve all original production fields and five switches exactly. Token `paddle-ocr+ppocrv5`. |
| `paddle-v5-orient` | Same v5 pair | `PP-LCNet_x1_0_doc_ori` and `PP-LCNet_x1_0_textline_ori`; document and textline orientation true; unwarping false; word boxes true; score threshold 0.0. Token `paddle-ocr+ppocrv5+orient`. |
| `paddle-v6` | `PP-OCRv6_medium_det` / `PP-OCRv6_medium_rec`, family `PP-OCRv6` | Both orientation switches false; unwarping false; word boxes true; score threshold 0.0. Token `paddle-ocr+ppocrv6`. |

Keep PaddleOCR **3.7.0**, PaddlePaddle GPU **3.3.0**, recorded PaddleX **3.7.2**, and the reviewed static word-box-capable route. Verify the actual selected runtime before deployment; no package upgrade or backend substitution follows from this clarification. Transformers word-box support is explicitly absent in the inspected source. Explicit model names are material because upstream model-name arguments override family/lang selection. Published model sizes in the memo are not measured installed bytes; record actual names/sizes at the authorized deploy step.

Research static-backend enforcement must be concrete: the current `_Model._build` omits `engine`, and upstream `engine=None` is automatic selection, so a declared static label is insufficient. For a research alternative, either explicitly select `paddle_static` in the constructor or use a reviewed API to prove the actual loaded predictor is static; test constructor arguments, actual-engine verification and identity agreement. Bind that alternative's backend to its frozen block, research key material and verified identity, and refuse an unsupported or unproved route before customer inference. Keep production constructor arguments and production key/runtime bytes unchanged. When the production block is used as a research baseline, establish the required actual static-route fact through the reviewed verification record without adding a production constructor argument or canonical runtime/key field. This requirement identifies an unproved selection seam, not an observed backend failure.

Partition ids are the block ids above, **without `research/` or a newly invented prefix**. The umbrella's corrected ids supersede the older slash spelling in V's run paragraph. Each block uses a separate research data directory. Separate read-pass stores may use the same block partition id; the directory is not model/key identity.

## 2. Exact bounded ownership additions

Retain V's existing named ownership. For these additional files, permission is limited to the listed plumbing or proof append; it is not ownership of their broader subsystems. Root coordinates shared files against composed W/E/X and retains responsibility for composition. No `analysis/**`, router logic, general layout/evidence geometry, webapp production caller, or upstream PaddleX source edit is added.

| Additional implementation file | Allowed change only |
| --- | --- |
| `tools/paddle_wave.py` | Resolve the closed registry; carry selected settings through initial lifecycle and token-refresh reload; pass the selected configuration to research discovery; enforce the explicit V study plans below consistently in preflight/run/report. Preserve production ordering, lifecycle and retention. |
| `discovery/cli.py` | Research-only configuration argument, forwarding, and actual selected-key provenance from this child. Production mode selection remains unchanged. |
| `discovery/runner.py` | Validate selected block/partition/mode, pass the same resolved settings to the existing Paddle compute/cache call sites, and capture actual private artifact selection. Preserve all W/E/X projections and analysis behavior. |
| `ocr/pipeline.py` | Optional selected Paddle settings forwarded to the existing rung; stamp the corresponding document token. No ladder or admission change. |
| `webapp/artifact_cache.py` | Optional explicit Paddle settings in `cached_ocr`/`ocr_settings_key`, validated before a cache bypass; byte-identical default key material. No webapp route/worker may select an alternative. |
| `ocr/paddle_adapter.py` | Forward the verified selected model token into `evidence_from_pages`. No box association, coordinate repair, clamping, token reconstruction or canonical geometry change here. |
| `ocr/config.py` | Reserve every registered Paddle provenance token against environment/CLI model impersonation; keep ordinary model validation unchanged. |
| `telemetry/record.py` | Add the exact A/B model tokens to the closed Paddle source vocabulary and pin equality to the registry. No record-schema, cost, routing or customer-content additions. |

Existing test files additionally available for the matching bounded integration cases are:

```text
tests/test_paddle_wave.py
tests/test_paddle_vast_tool.py
tests/test_research_mode.py
tests/test_pipeline.py
tests/test_artifact_cache.py
tests/test_paddle_adapter.py
tests/test_paddle_routing.py
tests/test_telemetry.py
tests/test_extraction_quality_admission.py
tests/paddle_fake_worker.py
```

These names were inspected in root or the relevant composed-to-be cell. The existing card's worker/client globs currently correspond to `tests/test_paddle_worker.py` and `tests/test_paddle_client.py`; place their new configuration/geometry controls there, with existing `tests/test_paddle_config.py` and `tests/test_paddle_rung.py`. Keep the already authorized new comparison test `tests/test_paddle_config_ab.py` and source tool `tools/paddle_config_ab.py`. No new wildcard test/file ownership is granted.

The shared fixture `tests/paddle_fake_worker.py` is included only for the minimal explicit configuration identity in `DEFAULT_IDENTITY` and corresponding synthetic selected-block responses. Within the exact named test files, narrowly necessary fixture and call-shape updates may accommodate the new explicit arguments and identity fields while preserving every existing assertion's strength. In particular, the client's exact required-field-set assertion gains the configuration field; it must remain an exact closed-set assertion, never become a subset check. Production fixture responses may expose the new required verification field without changing production canonical runtime or key material. Preserve old negative controls and add selected-block/backend refusal controls.

Optional exact proof driver: `tools/p23config_mutation_table.py`, solely for V's named reversible mutants, named killers, green baseline check, source restoration and append-only private table logs. It performs no corpus/model work and must not become a new Paddle call site. If introduced, add that exact path beside `tools/paddle_config_ab.py` to V's hardcode-scan roots with presence/coverage tests; no blanket `tools/` allowance.

E's `tests/test_extraction_quality_admission.py::ALLOWED_NAMERS` may gain exactly **`tools/paddle_config_ab.py`** as a read-only research comparison consumer. Preserve the separate AST ban on router/analysis/webapp readers and the ban on metric readers in the other guarded layers. Retain the existence check. Do not exempt an entire directory or add the mutation driver merely because it exists; design that driver without direct `eq_*` spellings unless a specific additional proof-instrument entry is separately reviewed.

Conditional, only if the generic provenance tool remains in V's A/B workflow: `tools/train/provenance.py` and `tests/test_run_of_record.py` may carry the explicit selection or consume the child's recorded key. The preferred actual-key route below needs no new generic-provenance key computation. Leaving this tool untouched means its default-derived Paddle key cannot be presented as A/B provenance.

## 3. Selection must reach the actual read and key

Resolve one block explicitly at W's research entry point. Thread it through lifecycle initial settings, check/deploy/start/status, post-token-refresh settings, child argv, research CLI/runner, pipeline/rung/client, and canonical/document/page-extractor tokens. The worker engine and `/version` must use the same selected block. A requested id cannot simply be echoed while the engine loads production models.

Validate selected configuration against mode and exact partition **before any compute or cache bypass**. `DiscoveryRunner._read_paddle` computes directly when `self.cache is None`, and `cached_ocr` returns `compute()` before key derivation when `cache is None`; a guard located only in `ocr_settings_key` does not protect either path. Production callers resolve production only. Unknown selections, non-production selection without the correct nonempty research partition, or non-research mode carrying a research selection must refuse; never silently drop the argument or fall back to production.

The client verifies explicit worker configuration and all selected pins before any `/ocr`/raster work. Preserve authorization checks, token refresh, loopback transport, one-worker serialization, and ordinary lifecycle cleanup. `deploy --config` may copy only the standalone worker script and perform the selected model-weight preparation; self-check metadata alone is not a weight-loading proof. Keep existing interpreter/compression behavior.

### Data mirrors and production call-site bans

The card's selection ban remains a call-site/data-flow rule, not a ban that forces a standalone worker to lie about its supported table. Permit exact, equality-tested data mirrors only in:

- `ocr/paddle_config.py`: authoritative three-block registry.
- `ocr/paddle_worker.py`: standalone selected-block data required because deploy copies this one script; engine and reported identity use it.
- `telemetry/record.py`: closed recognized token vocabulary only.
- `ocr/config.py`: closed reserved token vocabulary, preferably derived from registry data.

The wave registry selector is the only research orchestration selector; lifecycle/CLI/runner/cache/pipeline forward or validate its explicit selection. Production webapp, production discovery, router and analysis cannot select an A/B block or read an ambient override. AST/inventory tests must distinguish these exact data definitions and research forwarding sites from production selection calls; preserve site multiplicity and alias/callback/indirection attacks. No whole-module exemptions, dynamic default-from-environment selector, or catch-all token prefix recognizing unknown models.

## 4. Production bytes are invariant

For an unchanged environment/toolchain and omitted configuration, and for an explicitly selected production block, require the pre-V **key material and resulting keys**, original production token, canonical production evidence/runtime payload, all five switches, versions/models and global worker contract to remain byte-identical. The new registry must not silently inherit fields, while its serialization still omits fields that never belonged to the old production material.

Do not insert configuration id, read-pass id, orientation-model metadata, normalization version or another new default field into production settings-key/runtime bytes. Do not bump global OCR, raster, extraction schema or production contract versions to distinguish A/B experiments. Research alternatives carry explicit additional model/normalization identity where needed, with their own tokens/pins/partitions. Verification may inspect an added `/version` field without copying that field into production canonical runtime. Any later semantic change to research coordinate normalization must receive a distinct reviewed research identity before cache writes; it cannot reuse artifacts under a stale meaning.

Default non-Paddle keys retain their lazy independence from Paddle settings. Reconstruct historical key versions exactly as before. Pin production equality directly against the committed pre-V implementation, not only against a newly rewritten table.

## 5. Actual selected-key provenance

Do not infer the A/B key from partition spelling or rerun a default settings-key calculation after the fact. In the research child, `CacheResult.cache_key` identifies the exact artifact read/written. The existing read-only `cache.storage.cache_lookup(stage, cache_key)` exposes its input SHA, settings key and path; verify those against the requested document, block and canonical evidence. Gather actual selected keys and evidence identities privately and record the run's selected block/partition/population digest and exact settings key. Multiple unexpected keys or conflicting bindings are findings, not a first/latest choice.

Use the established exact-tuple selection/ambiguity policy when the comparison tool reads artifacts, and validate envelope/canonical identity. A missing artifact or failed/unsupported read is a missing/refused measurement, never zero error or successful agreement. Preserve raw runtime distinctions rather than collapsing GPU/Python changes into one reading. No customer hash is printed beside a verdict; private manifests may contain the minimum necessary identity binding.

## 6. Explicit study plans and population units

These are research study plans, not a relaxation of the production configuration's default `CTRL → U755 → SLICE` order. Use one plan definition for W preflight, state binding, run and report; bind exact manifests, stage labels, configuration, parent population membership and digests. Unknown plan/stage names refuse rather than exploit W's current unknown-label bypass.

1. **Production main wave:** keep the existing full-population order and semantics unchanged. V does not restart it.
2. **Orientation main study:** separately derived `CTRL` scanned/mixed document subset first, then the `U755` scanned/mixed document subset. Each comes only from the existing approved population and recorded row classification. Their private manifests are distinct from full W manifests. W reads all pages of a selected document; do not pretend digital pages inside a mixed document were excluded.
3. **v6 main study:** the stratified U755 sample first, then existing SLICE. This study does not require a fresh full CTRL/U755 campaign under v6. The existing R5 ruling says **SLICE + ~200 pages** and allows Ocean to refine the starting sample. Prefer an exact 200-page whole-document selection when practical; otherwise root may freeze a justified nearby whole-document total, deterministically selected from U755 by family/modality strata **before outcomes**, recording exact documents/pages, selection rule and digest. No new user permission is implied by ordinary whole-document rounding within that ruling. Do not label an approximate sample exactly 200 or introduce page slicing through the OCR pipeline.
4. **Paired technical/stability studies:** root freezes bounded paired subsets, manifests/digests and read schedule **inside the above existing population sets** before any paired live run. Main campaigns are not duplicated merely to measure stability. Use existing matching fresh reads as the first observation when actual computation and runtime/raster identity are proved; obtain only the missing fresh read(s) on the frozen subset. Keep stage labels/order explicit. If a fresh subset store needs predecessor evidence, use a root-reviewed study definition that binds the completed parent study and its exact manifests read-only, or choose a self-contained nested subset prefix; do not synthesize completed predecessor state or enlarge the subset silently to satisfy the generic full-wave rule. Default production-main ordering remains unchanged.

Scope is documents/pages from the existing approved sets only, without sealed holdout or new truth labels. Root controls the concrete sample/paired manifests at launch. No population file, source artifact or live measurement was read for this clarification.

## 7. Two actual reads, not a cache replay

For stability, there must be two actual worker reads of identical transmitted page bytes under one frozen block/runtime. A normal rerun in the same W state skips completed evidence; a cache hit also performs no second inference. Neither is a stability observation.

Use independently empty dedicated research stores for the necessary fresh subset pass(es), retaining the same block partition id and immutable manifests; preserve both results without deleting, resetting or overwriting the first evidence store. Do not add a pass label to production/model key material. Avoid `--no-cache`, which removes the immutable artifact needed by W's evidence/retention path. Root may reuse an already-recorded first live reading only when it matches the declared paired conditions.

Prove an actual live miss/request for each selected member in each observation, with technical telemetry bound to its resulting artifact. Discovery may emit later cached alias visits, so group privately by selected SHA and keep alias observations separate rather than insisting every row is a miss or selecting only the last alias. Failed, unsupported or absent second readings stay explicit.

Report complete canonical evidence SHA equality as required, plus whether differences belong to page evidence or recorded runtime. A per-page digest must be a named deterministic digest over the existing complete serialized page payload; do not call raw-result hashes complete page hashes or strip metadata to manufacture stability. Match block/key, original raster bytes, page index and runtime before assigning change to the model. For speed/VRAM, match hardware, runtime, backend, transport and warm/cold condition on the same bounded paired subset; otherwise report historical measurements separately and say model-only effects were not isolated. No full extra baseline campaign is required by this clarification.

## 8. Research-orientation worker normalization: bounded allowance

V may implement and independently prove **research-orientation-only, pair-preserving coordinate normalization inside `ocr/paddle_worker.py`** at the owned result boundary, with explicit eligibility checks and closed refusals. The memo establishes a conditional seam, not a currently passed geometry proof. Nothing may use an unproved normalization path for customer reads.

### Page-level eligibility

- Unwarping is false in the frozen block, actual constructor arguments and returned settings. Verify supported document angle 0/90/180/270 and actual preprocessor output dimensions from internal result data before JSON discards them.
- Use the pinned OpenCV center/translation/output-size convention. Invert all four box corners, then form canonical AABBs in the **original transmitted page frame**. Preserve original raster hash, PDF geometry and scale; do not send/store a second image as if it were the original.
- Enabled-stage metadata must be finite, valid and consistent. Honor -1 only as the documented disabled-stage sentinel paired with disabled settings; do not reject unchanged production solely for that sentinel.

### Initial line-level eligibility

- Start with the explicitly proved integer, axis-aligned **horizontal** quad/general-text, static-CTC subset in which crop and helper axes agree, each word spans the full line height, and the decoder/group ordering preserves the word/box association. Exact source dimensions and integer rounding belong to the proof. Do not generalize from a centered/equal-width example.
- Enabled textline labels are exact class IDs 0/1, not degrees; disabled uses -1. Bind each accepted recognition occurrence to its own retained detection occurrence. Full positional correspondence may identify duplicate polygons; a filtered/ambiguous duplicate occurrence must refuse. No first-N zip, fuzzy polygon match or first-match dictionary choice.
- Class 1 inverse moves each word's own box while retaining its text, score and identity; for a proved rectangle `[L,R]`, horizontal bounds become `[L+R-x1, L+R-x0]`. Class 0 preserves coordinates. Never reverse words alone, reverse boxes alone, assign equal-width slots or independently resort transformed boxes.
- Cardinality equality alone is insufficient: require proved text/group ordering and finite score/coordinate bounds. Unsupported mixed/deferred/ambiguous grouping, uncertain vertex order, skewed or nonrectangular polygons, nonlinear preprocessing, and malformed metadata refuse as a whole document through existing failure semantics. No clamp, drop, partial page or fallback to another reading.
- **Initially unsupported:** vertical cases and the cropper/helper threshold seam. Cropper turns at height/width **>=1.5**; the helper calls a line vertical only at **>1.5**. The source memo's vertical inverse is a candidate, not a passed proof. Test these shapes as explicit refusals unless root separately accepts a proved, precisely bounded extension. This clarification does not approve a general vertical/skew/poly solution.
- Restore line/crop association within the preprocessed-page frame first, then invert document rotation into the original transmitted page frame. Prove this composition at the actual worker boundary. Keep explicit research normalization identity/provenance; changed coordinates must not be labeled verbatim upstream output. Production orientation-off results remain untouched.

The worker can emit the existing adapter arrays after normalization. Adapter geometry, canonical evidence geometry, structurer, router and validator changes are not included. The adapter's separate selected-model-token threading in section 2 is still required.

### Required synthetic boundary proofs before enabling the subset

In the exact owned worker test file, add independent expected-coordinate fixtures for nonsquare pages at all four right angles, fractional/boundary boxes and unchanged original frame/hash; unequal opposite-end horizontal words under class 0/1; disabled -1; combined page/line rotation; batch order and filtered detections; duplicate occurrence ambiguity; integer rounding and the 1.5 threshold; and unsupported geometry/grouping refusals. Exercise the actual adopted worker boundary and pinned crop/turn/helper conventions, not a stand-alone correction whose output creates its own expected answer.

Mutants must distinguish no inverse, wrong sign/order, w-1/h-1 substitution, unconditional reflection, label-only/box-only reversal, independent sorting, wrong occurrence association, clamp/drop, partial-page return, production normalization and identity omission. These extend the card's named mutation obligations; no pass count is asserted here.

### Limits and forbidden shortcuts

The final upstream JSON does not retain the crop transform or raw CTC column positions. General skewed/nonrectangular/polygon geometry and uncertain text/box ordering are not recoverable merely by reflecting final AABBs. CTC boxes remain approximate word extents even inside the supported normalization subset. This scope **does not authorize** a global PaddleX monkeypatch, upstream-file edit, copied pipeline, crop/decoder hook, custom OCR assembly, alternative model/backend, or a general inverse that the current result lacks data to support. A broader intervention requires its own concrete design/ownership review before implementation.

Unsupported is an **integration measurement limit**, not evidence that the OCR model is inaccurate or that the document is unreadable. Report requested/eligible/supported/refused/missing denominators, refusal categories, modality and configuration. Compare accuracy only on paired measured support and disclose coverage; never score an unsupported normalization as bad OCR, turn it into a production refusal, or hide it by excluding the denominator.

## 9. Proof/review boundary

Retain the original V M1–M10 requirements, production call-site tripwires, no-customer-text/no-cost output constraints, and all required floor/live/attestation/review gates. Add focused threading, bypass, actual-key, study-order, fresh-read and geometry mutants only for the implemented seams. Every mutant must run from a green baseline, reach its named killer and restore source. No existing production reader ban is weakened to make a comparison test pass.

Before any V customer run: root adopts the bounded clarification; W composes; V's exact launch base and study manifests are frozen; registry/worker/client/key/partition synthetic end-to-end proof passes; geometry support is independently approved within the declared subset; runtime/model identity and permitted downloads are verified. The existing two opt-in literals remain scoped to each W-run environment, with serialized lock sessions and complete retention attestation. No V launch or live work is performed by this clarification.

## Independent design review and adoption

X prepared the source-based clarification; P independently inspected the actual cache,
worker, pipeline, identity, population and geometry seams and reviewed the frozen
draft. Root incorporated the exact shared fake-worker fixture ownership and concrete
research static-backend enforcement, and read the complete amended text and review.
The reviewer confirmed both closures and the line/crop-before-document inverse order.
No implementation or model/geometry test was performed as part of this design review.
The private frozen drafts, source manifests and review are under
`discovery_reports/train13-logs/p23config-prep/`. Recheck the source seams at V's
actual composed launch commit; all original and clarified proof gates remain owed.
