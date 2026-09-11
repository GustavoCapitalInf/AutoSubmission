# Agent Handoff — P23-WAVE (Phase 2.3 cell W: the resumable wave runner over CTRL → U755 → SLICE on the approved Vast instance, the technical-telemetry field, the retention attestation, the population files)

**Launch base:** `train13` at its opening commit (= `main` = `phase2.2-final` `d84af95`). Worktree
`.claude/worktrees/mt23-wave`, branch `wave23-wave`.

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (ALL of it — the 2026-09-03 section: the Paddle
customer-data authorization and its retention rule, R1, R2 WITHDRAWN (cost is never yours), the
anti-optimizer rule, the STOP conditions), then the umbrella `docs/agent-handoffs/PHASE2-3-WAVE.md` (D1–D11,
the contracts, cases 1–5, 8, 12–14, the rules delta), then `docs/moneythumb-replacement/PADDLE_VAST_RUNBOOK.md`
(the lifecycle, the privacy boundary, the Secure Cloud machine section) and `PADDLE_MEASUREMENTS.md`, then
the Phase 2.2 research mode as composed: `discovery/cli.py` (`--research-paddle --population
--research-partition --data-dir --holdout-digest --root --out`), `discovery/runner.py` (`MODE_RESEARCH_PADDLE`,
`RESEARCH_TRIGGERS`, `refuse_production_data_dir`, `_read_paddle`, `_project_funnel`, `ROW_FIELDS` — the
columns `stage_*`, `bytes_up`, `bytes_down`, `inference_ms`, `vram_mb`, `peak_rss_mb`, `research_partition`,
`paddle_rung`, `cache_paddle`, `paddle_refusal_reason`), `ocr/paddle_rung.py` (`PaddleRead.telemetry`: per-page
`inference_ms` / bytes and the totals), `ocr/pipeline.py` (where a `PaddleRead` becomes a `StatementMarkdown`),
`ocr/document.py` (`StatementMarkdown`), `ocr/paddle_client.py` (the closed `RUNTIME_FIELDS` whitelist and the
identity check), `ocr/paddle_worker.py` (`/version`, `/health`, the no-retention design), `tools/paddle_vast.py`
(check / deploy / start / stop / tunnel-up / tunnel-down / status / measure), `webapp/artifact_cache.py`
(`cached_ocr(..., research_partition=)`), `telemetry/run_of_record.py` (the research-partition refusal),
`tests/paddle_fake_worker.py`, `tests/paddle_synthetic.py`, `tests/test_research_mode.py` (T's synthetic
end-to-end proof — your runner drives the same door). Ocean reviews and composes; you never merge or push.
**Hygiene card: `newly validated = 0` official; every previously validated document preserved (the production
partitions are never written); research-validated shas are NAMED, never counted; no cost, rate, price or
billing anywhere; the two opt-in literals only in the environment of an authorized run.**

# Why
Phase 2.2 built the door (research mode through the router, research partitions the run of record can never
select, the funnel columns) and proved it on synthetic fixtures only. Phase 2.3's evidence — E-gate v2,
agreement, the truth table v2, the fallout — needs real Paddle evidence on the control sample and the
unresolved corpus, produced ONCE, immutably, resumably, with every page attempted or refused with a reason,
and with the instance left holding nothing. This cell is the runner and the record; it admits nothing.

# What you deliver (ruled — do not re-decide)
1. **`tools/paddle_wave.py`** — a thin, RESUMABLE orchestrator around the Phase 2.2 research mode; it never
   reads a page itself and never imports `ocr.paddle_rung` (an AST test pins it). Subcommands:
   `populations` (item 5) · `preflight` (item 2) · `run --population <CTRL|U755|SLICE file>
   --research-partition <id> --config <paddle-v5-prod>` — lifecycle `check → deploy (if needed) → start →
   tunnel-up → status` through `tools.paddle_vast`, identity verified against the pins, then
   `python -m discovery --research-paddle --population … --research-partition … --data-dir <research dir>
   --out <run dir> --root "Bank Statements"` in CHUNKS of the population (resumable: a chunk already read is
   a cache hit under the same key — `cache_paddle` on the row; the runner records progress by sha in a
   private state file under the research data dir and continues from it after any interruption), then
   `stop → tunnel-down` and the attestation (item 4) · `report` (item 6). D3 by construction: `run` refuses
   to start U755 while CTRL has an unattempted page under the same configuration; SLICE only after both.
2. **Preflight and the literals.** `run` refuses, naming the missing one, unless BOTH `PADDLE_REMOTE_OPT_IN`
   and `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` carry their exact literals in ITS process environment (the
   existing checks in `ocr/paddle_config.py`; you add the up-front naming); the literals are set per command
   by the operator (you, for the authorized runs) and appear in no tracked file, no `.env`, no log. The
   runner's log records the population name, its digest, the partition id and the configuration — never a
   document's contents, sha with verdict, host, port, user or token. Refuses a `--data-dir` that is or is
   inside a production or historical cache (T's door — reuse it, do not re-implement).
3. **The technical-telemetry field (cell T's named STOP).** `StatementMarkdown` gains ONE optional field
   `extraction_telemetry: dict | None = None` (per-page `inference_ms`, `bytes_sent`, `bytes_received`, and the
   totals — exactly what `PaddleRead.telemetry` already carries; plus `vram_mb` ONLY if the worker's response
   already carries a VRAM sample — if it does not, `vram_mb` stays empty and you say so; you do not add a
   worker endpoint for it in this cell), set in `ocr/pipeline.py` where the `PaddleRead` becomes the document
   (one line), and projected by `discovery/runner.py::_project_funnel` into the four columns on a LIVE Paddle
   read. RULED: telemetry is TRANSIENT — never persisted into the OCR artifact (no schema bump; a cache hit
   carries none and the columns stay empty on `cache_paddle = hit`); `to_markdown()` byte-identical; the
   analysis input and every cache key untouched (a test proves payload and key identity with the field set
   and unset).
4. **Retention attestation (case 12).** After `stop`, the runner inspects the instance over the existing
   masked SSH runner: the worker's runtime directory holds no request artefacts and no page bytes, no worker
   process is alive, and `/version` (read BEFORE stop) reports `retention: none` — if `/version` does not
   carry that field today, add it to the worker and to the client's closed `RUNTIME_FIELDS` whitelist with
   its shape check (a string equal to `none`), the ONE worker/client change this cell may make. The
   attestation is written to the run's log as a closed record (fields and booleans, never paths from the
   instance), and proven on the real instance during the CTRL run.
5. **Populations.** `populations` derives, from the Phase 2.2 run of record
   `discovery_reports/TRAIN12-52bd8f2/2026-09-11T040247.502179-0000-fd6b4d7f/rows.csv`, three files under
   `discovery_reports/train13-logs/populations/` (gitignored): `CTRL.shas` (every `source_path =
   local_tesseract` row that is `validated` — 36 at the run of record — plus native-validated documents
   stratified by `folder_label` family and page-count bucket to ≈ 114, chosen deterministically from a
   recorded seed so the file reproduces), `U755.shas` (every non-validated distinct sha — 755), `SLICE.shas`
   (the 34-document corpus slice from `corpus_gate.py`'s manifest); content shas one per line with `#`
   comments; the sha256 digest of each file is printed and goes in your W3; a sha in the holdout digest is
   refused by T's door at run time (you also assert at derivation that none is in
   `docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt`'s list).
6. **Rasters (D2).** Under `--retain-rasters` (ON for the research runs), the PNG each page sent is kept
   sha-named under the research data dir (`<data-dir>/rasters/<content sha>/<page>.png`, gitignored, the
   archive's retention rule); production partitions keep only `raster_sha256` — a test proves the production
   path writes no raster file.
7. **`report`** prints, per population and configuration: pages attempted / evidence produced / refused by
   `paddle_refusal_reason` (every page attempted or refused — the count identity), cache hits on a re-run,
   latency percentiles (per page `inference_ms` p50 / p95, wall), bytes up / down totals, VRAM if present,
   local `peak_rss_mb`, the partition ids, the attestation summary. NO cost, rate, price, usd, billing key
   anywhere (T's grep test extends to your report keys).
8. **The runs (the authorized customer-data runs — the first ever):** CTRL, then U755, then SLICE, under
   `paddle-v5-prod` (the Phase 2.1 pins; the configuration blocks are cell V's — you run the production
   block only), each detached under the host lock with a durable log ending `EXIT=`, resumable after any
   interruption, the instance stopped and the tunnel closed at the end of every session, the attestation
   after each. BEFORE the first live run: rotate the worker session token by deleting the gitignored
   `.paddle_runtime/worker.token` (its value was printed into a local log during the 2.2 closure and
   redacted; `start` mints a fresh one; record the rotation). Never the previous (pre-2026-09-04) instance.
9. **No hardcodes; no routing:** nothing in `ocr/escalation.py`; the OQ2 scans cover `tools/paddle_wave.py`
   (append it to the scan roots as the 2.2 cells did).

# Files you own (exact; nothing else)
`tools/paddle_wave.py` (new) · `ocr/document.py` (the one field) · `ocr/pipeline.py` (the one line) ·
`discovery/runner.py` (`_project_funnel`'s projection of the four columns ONLY) · `ocr/paddle_worker.py` +
`ocr/paddle_client.py` (the `retention` field and its whitelist entry ONLY, if absent) ·
`tests/test_paddle_wave.py` (new) · `tests/test_paddle_rung.py` and `tests/test_research_mode.py` (APPEND
the telemetry / raster / attestation pins only) · `tests/test_no_statement_hardcodes.py` (the roots append) ·
`docs/moneythumb-replacement/PADDLE_VAST_RUNBOOK.md` (a "Phase 2.3 wave" section) · your W3 section.
`analysis/**`, `layout/**`, `telemetry/**`, `evidence/**`, `ocr/escalation.py`, `ocr/paddle_config.py`
(cell V's), `webapp/**` are NOT yours.

# Mutation table (run every mutant, name every killer)
M1 skip a page on a worker exception instead of recording E0 → the population-count identity test · M2 the
research partition dropped from the runner's `cached_ocr` call → K's `run_of_record` refusal test / the key
test · M3 the preflight accepting one literal → the preflight test (each literal alone refuses, naming the
other) · M4 the telemetry persisted into the OCR artifact → the cache round-trip byte-identity test · M5 a
raster written under a production partition → the production-path test · M6 a population sha read twice
under one configuration → the re-run cache-hit sha-equality test · M7 U755 started with CTRL incomplete →
the order test · M8 the attestation reporting `none` without inspecting → the attestation test (a fake SSH
runner that lists a leftover file must fail it) · M9 a cost key in the report → the grep test · M10 the
runner importing `ocr.paddle_rung` or calling `read_document` → the AST test · M11 `run` accepting a
`--data-dir` inside a cold cache → T's containment test through the runner · M12 the state file resuming
past a sha whose row was refused → the resume test.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus`; the synthetic end-to-end wave on the fake worker (populations of
rendered PDFs, dates ≥ 2031: one request per page, a second run all cache hits, resume after a killed
chunk, the attestation against a fake runner); `cohort_replay --expect-identical` over `--parser` chunks
touching the runner (the projection changed) at base and closure — the offline partition byte-identical;
then the LIVE runs CTRL → U755 → SLICE with every log and the attestations; privacy scan 0 over your added
lines against the run-of-record population AND the message scanner (`tools/huntington_msg_privacy_scan.py`
over a temp file, `--shas` = the population) over every wave log and report you wrote → 0; message scan 0
over your commits. Heavy proofs and wave sessions one at a time under the lock (mkdir-only; holder inside;
own-holder release; Git bash `rmdir` when Python's is refused; unbounded waits).

# Report contract (final message to Ocean AND your W3 section `# §P23WAVE — …`)
population (CTRL / U755 / SLICE: documents, pages, digests) · root cause · solution · attempted / evidence /
refused by reason per population (the count identity) · cache hits on re-run · technical telemetry
(latency percentiles, bytes, VRAM, peak RSS; no cost) · the retention attestations · newly validated 0
(research-validated shas NAMED in their own row, never counted) · previously validated preserved (the
production partitions untouched; the replay identical) · regressions 0 · escalation evidence (the trigger
only from `RESEARCH_TRIGGERS`; no B/C edge) · commits · proof exits · privacy count (added lines AND wave
outputs) · risks last (what the evidence cannot say until E, X and B read it).

# Exclusions
No E-metric (cell E) · no agreement (cell X) · no configuration block (cell V) · no structurer run (cell B) ·
no classifier change (cell P) · no production routing · no cost · no page to any endpoint but the approved
instance through the loopback tunnel · no HOLD sha in any population.
