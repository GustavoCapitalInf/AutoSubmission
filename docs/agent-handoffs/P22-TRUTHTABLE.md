# Agent Handoff — P22-TRUTHTABLE (Phase 2.2 cell T: the layered unresolved taxonomy, the `refused` outcome and the exact transition matrix, the two denominators, the classifier wired into rows, funnel and technical-telemetry columns, the research run mode through the router, and the geometry seam behind `reconstruction_mode`)

**Launch base:** the integration base Ocean names at launch = `train12` + cell K (P22-IDENTITY) + cell C
(P22-CLASSIFY) composed. Do not start from bare `train12`.

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `docs/agent-handoffs/PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (ALL of it — the 2026-09-03 section: the authorization,
R1 (the Paddle customer-data scope you wire but NEVER exercise on customer data in 2.2), R11, R12, cost
OUT OF SCOPE), then the umbrella `docs/agent-handoffs/PHASE2-2-TRUTH.md` (D2, D7, D8, D10, the
contracts §"Taxonomy", §"refused", §"Research mode", §"Technical telemetry", cases 6–11, 23, 25), then
`docs/moneythumb-replacement/phase2_remainder/PHASE2_REMAINDER_PLAN.md` §D.4 (the L0–L6 vocabulary) and
§H.7, then `docs/moneythumb-replacement/W3_2_TAXONOMY.md` (the idiom: drift guards, precedence table
asserted equal to the code, `unmapped` never nulled), then `telemetry/diagnostics.py`,
`telemetry/record.py` (`classify_outcome`, `classify_document`, `DOCUMENT_LADDER`), `telemetry/report.py`,
`discovery/runner.py` (modes, `enabled_extractors`, `_read_paddle`, `ROW_FIELDS`, `classify_failure`,
`_failure_reason`, `_analyse`), `discovery/report.py`, `discovery/compare.py` (`LADDER`),
`tools/train8_compare.py`, `ocr/escalation.py` (`ADMITTED_TRIGGERS`, `EXTRACTOR_ORDER`, `RouterInputs`,
`decide`), the K and C W3 sections and diffs on your base (`layout/document_class.py`'s contract;
`StatementMarkdown.native_evidence`; `analysis_input_sha(..., evidence_sha256=)`;
`Settings.reconstruction_mode`; the `research_partition` key field; `run_of_record`'s refusal), and cell
F's W3 note on the diagnostics guard count. Ocean reviews and composes; you never merge or push.
**Hygiene card: `newly validated = 0`; every previously validated document preserved payload-identical;
no network (the fake worker is in-process); no customer page leaves the machine — the research mode is
proven on SYNTHETIC fixtures only; `reconstruction_mode` stays `off` in every run of record.**

# Why
"755 unresolved" is one number. Gustavo requires that every unresolved document carry ONE disjoint
primary kind and ONE defensible primary reason, that overlapping diagnostic labels (R, U, density,
failure class) be reported beside it and never summed with it, that `refused` become a first-class
terminal outcome without weakening the protection of `validated`, and that both denominators be
printed every time. 2.3 additionally needs a research mode that starts Paddle THROUGH the router on a
named population into a partition the run of record can never select, and 2.3/2.4 need the pipeline to
receive geometry behind a mode that is `off` today. This cell is the reporting and routing plumbing;
it moves no document.

# What you deliver (ruled — do not re-decide)
1. **`telemetry/unresolved_taxonomy.py`** — the L0–L6 vocabulary exactly as PHASE2_REMAINDER_PLAN §D.4
   (L0 FILE, L1 KIND, L2 EXTRACTION E0–E5, L3 STRUCTURE B1–B8, L4 FINANCIAL = the W3-2 classes unchanged,
   L5 DOCTRINE, L6 UNKNOWN), closed per layer with `unmapped`; `diagnose_unresolved(row, diagnostics,
   document_class) -> UnresolvedDiagnosis(reason_l0 … reason_l6, primary_layer, primary_code)`; the
   PRIMARY reason = the highest non-empty layer; precedence table in the module docstring asserted equal
   to the code by a test (the W3-2 idiom); drift guards: the set of outcome reasons the runner can emit
   (`_failure_reason`'s vocabulary + the deferred reasons + `refused` reasons), the classifier's `KINDS`
   and `Finding` codes, and the W3-2 classes are each read from their source and asserted to be covered
   or explicitly `unmapped`. L2/L3 codes are populated ONLY from facts the row already carries (today:
   the E-triad from `evidence_quality`; the existing structurer refusal reasons where a research row
   carries one); never inferred. `DIAGNOSTICS_VERSION`-style versioning: `UNRESOLVED_TAXONOMY_VERSION = 1`
   travels in every record; the report warns on mixed versions.
2. **`refused` (R11).** `telemetry/record.py::classify_outcome` gains the terminal class `refused` with
   the closed reasons `not_a_statement | file_invalid | insufficient_evidence | contradictory |
   incomplete | unreadable` (RESERVED — nothing produces them in 2.2; a test asserts zero `refused`
   rows on the run of record's replay); `DOCUMENT_LADDER` unchanged; `discovery/compare.py`: `refused` is
   UNRANKED against failed/withheld/review (moving between them is `unranked`), ANY transition out of
   `validated` — to `refused` included — is `regressed` (exit 2 under `--fail-on-regression`); the
   comparison prints the EXACT transition matrix (from-class × to-class counts, every class including
   `deferred`, `unknown`, `refused`); a base/candidate pair whose raw denominators (distinct sha counts)
   differ is REFUSED with a named error (no silent re-baselining); `tools/train8_compare.py` prints the
   matrix and the two denominators. The `classify_failure` vocabulary is untouched.
3. **Two denominators (R11/R12) in `discovery/report.py` + `summary.json`:** `raw_coverage =
   validated / 3,380`; `ccl_adjudicated = validated_in_ccl / |CCL|` where CCL is read ONLY from the
   repository digest file `docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt`'s adjudicated sha16
   list joined to the store's verdicts — which the runner CANNOT read (firewall) — so the runner prints
   `ccl_adjudicated: not available in this process` and the join is done by a separate read-only tool
   `tools/truth_report.py` that DOES read the sealed store (under `SEALED_TRUTH_DIR`; it is a `tools/`
   instrument, allowed by the firewall) and prints both denominators plus the disjoint primary
   classification (adjudicated where present, classifier-proposed elsewhere, labelled per document
   which); `ccl_classifier_proposed = validated_in_proposed_ccl / |proposed CCL|` printed by the runner
   from its own classification column; the raw denominator is printed first and never replaced; card /
   loan / brokerage account kinds reported as separate rows (R12).
4. **The classifier wired as a recorded fact (D2, case 6).** In `discovery/runner.py`, after the read and
   BEFORE analysis, call `layout.document_class.classify_document(evidence=<the read's evidence or
   native_evidence>, page_texts=<the pages when no evidence>, profile=DocumentProfileFacts(...copied
   from the DocumentProfile...))`; record `document_class`, `class_sub_kind`, `class_modality`,
   `class_account_kind`, `class_tier`, `class_signals` (a `|`-joined closed list), `class_version`,
   `completeness_findings` on the row; NEVER pass it to `analyze_document`; a test proves the analysis
   payload is byte-identical with the classifier present and with it stubbed out. Also record
   `evidence_sha256` for native reads from cell K's `native_evidence_sha256` (the one-line change K's
   W3 names). The primary classification is asserted DISJOINT (one kind per row) and the report prints
   the kind × modality × tier table over the archive and over the unresolved set with the sum shown;
   R / U / density / failure-class counts in a SEPARATE table titled "diagnostic labels (overlapping;
   never summed)".
5. **Funnel + technical telemetry (case 25).** `ROW_FIELDS` APPENDED (never reordered):
   `stage_extract | stage_evidence | stage_geometry | stage_layout | stage_candidate | stage_verdict`
   (closed vocabularies; `not_attempted` default; populated from facts the runner already has: e.g.
   `stage_extract = native|tesseract|paddle|none`, `stage_evidence = present|absent`, `stage_geometry
   = not_attempted` until 2.3), `bytes_up`, `bytes_down`, `inference_ms`, `vram_mb` (from the Paddle
   client's per-request fields when a Paddle read happened; empty otherwise), `peak_rss_mb` (per document
   via `psutil` when importable — add it to `requirements-local.txt` and `requirements.txt` ONLY if CI
   needs it for a test; otherwise local only — and the literal `not measured` when absent), `research_partition`,
   `escalation_trigger` (existing), `reason_l0 … reason_l6`, `primary_reason_layer`, `primary_reason`,
   `document_class …` (item 4). The row-shape test updated in the same commit. NO cost, rate, price or
   billing field anywhere (a test greps `ROW_FIELDS` and `summary.json` keys for `cost|price|rate|usd|
   billing` and asserts none).
6. **Research mode (D7, D8, case 23).** `python -m discovery --research-paddle --population <shas.txt>
   --research-partition <id> --data-dir <dir> --out <run dir>`: `MODE_RESEARCH_PADDLE`;
   `enabled_extractors = frozenset({"paddle"})` as a MODE constant (the D4 AST tripwire in
   `tests/test_escalation_tripwires.py` must still pass — it pins every `enabled=` at a `decide(` site to
   a runner/mode attribute); the population file is REQUIRED (content shas, `#` comments), and a sha not
   in the population is SKIPPED with `research_skipped_not_in_population` on the row; a sha present in
   the holdout digest's list (`docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt`, cell H) is
   REFUSED (`research_refused_holdout`); `ocr/escalation.py`: a new admitted trigger
   `operator_forced_paddle` (pre-financial: a run-mode fact) that the runner supplies ONLY in this mode
   (`RouterInputs` unchanged — the trigger travels in the existing `triggers` field; a test proves no
   other mode can produce it and a mutant that admits it in `--scanned-paddle` is caught); the router
   names `paddle` for every population document regardless of profile (the research admission);
   `_read_paddle` runs as today with `paddle_data_scope="customer"` (the runner always reads the archive)
   — so the mode REFUSES at start unless BOTH `PADDLE_REMOTE_OPT_IN` and
   `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` are present in the process environment with their exact
   literals (the existing checks; you add the up-front preflight refusal naming which is missing); the
   `--data-dir` must not equal any of the production/cold cache directories (`webapp_data`,
   `.claude/recovery/webapp_data_train*_cold`) — refuse; the OCR settings key carries `research_partition
   = <id>` (cell K's field) so `run_of_record` can never select it; rows carry `research_partition`;
   the report's headline coverage excludes research rows by construction and prints a separate
   "research partition <id>" table (attempted / evidence / E-gate / geometry / stages). **In 2.2 this mode
   is proven end to end ONLY on synthetic fixtures with the fake worker** (a synthetic population of
   rendered PDFs in a temp root, `--root <temp>`): exactly one fake-worker request per page; rows carry
   the partition; `run_of_record` refuses the partition; auto mode and every other mode have no path to
   the trigger. **You never set `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` outside a test process's own
   environment, and never against `Bank Statements/`.**
7. **The geometry seam behind the mode (inert in 2.2).** `discovery/runner.py::_analyse` (and
   `webapp/worker.py`'s `_analyze_doc` — read K's W3 for whether `cached_analysis` threads the sha; if
   `webapp/worker.py` needs a call-site change it is YOURS for that line) passes
   `document_geometry=geometry_from_evidence(<the read's evidence or native_evidence>)` and
   `evidence_sha256=<its sha>` into the analysis call ONLY when `settings.reconstruction_mode != "off"`;
   when `off` (every run of record) the call is byte-identical to today (the union replay proves it).
   `discovery/` may import `analysis.structurer.geometry` (check the import tripwires — `discovery` is a
   caller of `analysis` already; if a tripwire forbids the specific module, STOP and report).
8. **Cell F's consequence:** update `telemetry/diagnostics.py`'s reconciliation-issue anchor count
   guard (`tests/test_diagnostics.py`) to the count F's removal leaves, keeping the
   `recon:escalation_extraction_failed` anchor in the vocabulary (a record written before the change
   must still classify); bump `DIAGNOSTICS_VERSION` per the W3-2 changelog rule with a v5 entry in
   `docs/moneythumb-replacement/W3_2_TAXONOMY.md` §11 (you own that append).
9. **Instrument, committed:** `tools/truth_report.py` (item 3) — read-only; aggregates only; refuses to
   print a sha with a verdict (sha16 + kind is the finest grain, and only in the private `--out`).
10. **No hardcodes** (the OQ2 scans cover `telemetry/`, `discovery/`? — verify; if `discovery/` is not
    scanned, append it to the roots ONLY if `train12` + C's roots append leaves room without conflict;
    otherwise report).

# Files you own (exact; nothing else)
`telemetry/unresolved_taxonomy.py` (new) · `telemetry/record.py` · `telemetry/report.py` ·
`telemetry/diagnostics.py` (item 8 only) · `telemetry/__init__.py` (exports) · `discovery/runner.py` ·
`discovery/report.py` · `discovery/compare.py` · `discovery/__main__.py` / `discovery/cli.py` (the mode
flags) · `tools/train8_compare.py` · `tools/truth_report.py` (new) · `ocr/escalation.py` (the one
trigger; `RouterInputs`, `EXTRACTOR_ORDER`, `decide`'s shape untouched) · `webapp/worker.py` (one call
site, only if K's W3 says so) · `requirements-local.txt` (`psutil`) · `docs/moneythumb-replacement/W3_2_TAXONOMY.md`
(§11 v5 append) · tests: `tests/test_unresolved_taxonomy.py`, `tests/test_refused_outcome.py`,
`tests/test_two_denominators.py`, `tests/test_research_mode.py`, `tests/test_row_fields.py` (or the
existing row-shape test), `tests/test_diagnostics.py` (the count), `tests/test_escalation_tripwires.py`
(APPEND the new-trigger pins only) · your W3 section. `layout/`, `evidence/`, `webapp/artifact_cache.py`,
`telemetry/run_of_record.py`, `analysis/**` are NOT yours.

# Mutation table (run every mutant, name every killer)
M1 primary reason = the LOWEST non-empty layer → the precedence test · M2 a new runner reason not in the
vocabulary silently mapped to a class → the drift guard (inject a reason in a scratch copy) · M3
`validated → refused` treated as unranked → the regression test (exit 2) · M4 the transition matrix
omits a class → the matrix-shape test · M5 differing raw denominators accepted → the refusal test · M6
the classifier passed into `analyze_document` → the payload-identity test · M7 two kinds recorded for one
row → the disjoint assertion · M8 the diagnostic-label table summed into the primary table → the
never-summed test · M9 a cost/price/rate key in rows or summary → the grep test · M10 `enabled` computed
per document in research mode → the D4 AST tripwire · M11 `operator_forced_paddle` admitted in
`--scanned-paddle` → the mode-only test · M12 the research mode starting without one of the two
literals → the preflight refusal test · M13 a production `--data-dir` accepted in research mode → the
refusal test · M14 a holdout sha read in research mode → the holdout refusal test · M15 geometry passed
while `reconstruction_mode == "off"` → the byte-identity test · M16 `research_partition` missing from
the row → the row test · M17 the CCL denominator replacing the raw one in the headline → the
two-denominator test.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus`; `cohort_replay --expect-identical` at base AND closure over the UNION
of every registration (you touch the runner's analysis call and the outcome classifier; the whole
offline partition must replay byte-identical); the research-mode synthetic end-to-end run recorded
(documents, pages, fake-worker requests, the partition, the `run_of_record` refusal); privacy scan 0
over your added lines against the run-of-record population (`discovery_reports/TRAIN11-4f7d798/…-331d9136/rows.csv`,
cold cache `.claude/recovery/webapp_data_train11_cold`, READ-ONLY); message scan 0. Heavy proofs one at
a time on this host.

# Report contract (final message to Ocean AND your W3 section `# §P22TRUTHTABLE — …`)
population (the union replay; the synthetic research run) · root cause · solution · newly validated (0)
· other ladder movement (0) · previously validated preserved (all, identical) · regressions (0) ·
correctness evidence (precedence, drift guards, matrix, denominators, disjoint sum on the run of record
= 755 / 3,380 with the validated exceptions named by sha16 and kind) · classification evidence (the kind
× modality × tier tables; the diagnostic-label table) · escalation evidence (the trigger admitted only in
research mode; no B/C edge; the D4 tripwire) · identity evidence (the seam inert when `off`) · commits ·
proof-floor exits · privacy count · risks last (what the truth table cannot say until adjudication and
until Paddle evidence exists for scans).

# Exclusions
No customer page to any worker · no `reconstruction_mode != off` in any run of record · no routing from
classification · no structurer enablement · no `layout/` change (report a needed contract change to
Ocean) · no `analysis/` change · no cost field · no adjudication.
