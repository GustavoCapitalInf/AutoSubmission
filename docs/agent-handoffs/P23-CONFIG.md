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
