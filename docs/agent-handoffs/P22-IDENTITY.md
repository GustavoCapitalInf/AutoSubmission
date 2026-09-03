# Agent Handoff — P22-IDENTITY (Phase 2.2 cell K: one native reader in `evidence/`, display-frame word boxes, native evidence persisted with its sha, the geometry-aware analysis key, research partitions excluded from the run of record)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `docs/agent-handoffs/PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (ALL of it — the 2026-09-03 section at the end is
binding: the full authorization, R1–R14, cost OUT OF SCOPE), then the umbrella
`docs/agent-handoffs/PHASE2-2-TRUTH.md` (D3–D7, cases 12–17, the rules delta), then
`docs/moneythumb-replacement/phase2_remainder/research/REPO_GEOMETRY_MEMO.md` (§2, §4, §5 — the
audit that found what you fix), then `evidence/canonical.py`, `analysis/structurer/geometry.py`,
`tests/test_geometry_frames.py`, `tests/test_evidence_boundary.py`, `tests/test_evidence_canonical.py`,
`ocr/pipeline.py`, `ocr/document.py`, `webapp/artifact_cache.py` (the OCR record, `analysis_input_sha`,
`analysis_settings_key`, the OCR settings key, the version pins and their tests), `telemetry/run_of_record.py`,
`tools/train/provenance.py`, `analysis/config.py`, `analysis/structurer/core.py` (`structurer_enabled`).
Ocean reviews and composes; you never merge or push. **Hygiene card: `newly validated = 0`; every
previously validated document preserved with payload identical; no network call; no customer data
leaves the machine; nothing under `discovery/`, `layout/`, `tools/holdout/`, `ocr/escalation.py`,
`analysis/pipeline.py` is touched.**

# Why
Phase 2.1 left five documented prerequisites. Three of them are identity defects that would make every
later measurement unsafe: the analysis cache key cannot tell a geometry-fed analysis from a text-only
one (a stale answer would be served silently the day 2.3 turns the structurer on in research mode); the
native geometry path discards the evidence sha it computes and recomputes it (~2.7×), so no native
document has lineage to its words; native word boxes live in PyMuPDF's unrotated space while the Paddle
raster is display-oriented, so a rotated page's two geometries cannot be compared. A fourth need is new:
2.3 writes research partitions that must NEVER become historical truth. This cell fixes exactly those
and nothing else.

# What you deliver (ruled — do not re-decide)
1. **`evidence/native.py`** — `native_evidence_from_pdf(pdf_bytes) -> ExtractionEvidence | None`, the
   ONE native reader. PyMuPDF is imported LAZILY inside the function (`import fitz` at the first line of
   the function body, nowhere else in `evidence/`). Per page: the frame is
   `PageFrame.pdf_points(page_index=i, width_pt=page.rect.width, height_pt=page.rect.height,
   rotation_deg=page.rotation)` (display orientation, as today); every word from `page.get_text("words")`
   with non-blank text is transformed by `page.rotation_matrix` into the DISPLAY frame before it becomes
   a `WordBox` (normalise so `x0<x1, y0<y1` after the transform — a transform, not a swap; assert the
   transformed box lies inside the frame or refuse the page with a note `native_word_outside_frame`);
   `extractor_id="native-pdf-words"`, `model_token="native-pdf-words"`, `runtime={"pymupdf_version":
   …, "frame": "display"}`, `raw=None`, `confidence=None`, `line_ref=None`; `document_sha256` computed
   locally (upper-case hex). Returns `None` exactly when the Phase 2.1 function returned `None`; never
   raises. The `native_words_unrotated_space` note is retired (a rotated page now carries
   `rotation_applied` in `notes`).
2. **`analysis/structurer/geometry.py::native_evidence_from_pdf`** becomes a re-export of (1) (an
   `from evidence.native import native_evidence_from_pdf` — the ONLY new import). `geometry_from_pdf`
   stays `geometry_from_evidence(native_evidence_from_pdf(...))`. Pins: on every UNROTATED page the
   output is byte-identical to the Phase 2.1 implementation — keep the existing legacy copy in
   `tests/test_geometry_frames.py` and re-assert equality on the structurer fixtures and the same ≥ 12
   pinned corpus PDFs (read-only; sha16s only in your W3); on ROTATED pages the output DIFFERS by design
   — add a second pin: a synthetic one-page PDF rendered four times with `/Rotate` 0/90/180/270 (PyMuPDF
   `page.set_rotation`) yields the same line texts and word boxes at the expected display positions
   (state the tolerance you measured in the docstring). Delete nothing else from `geometry.py`.
3. **`evidence/canonical.py`:** a `pdf_point` frame gains the bounds check `pixel` frames already have (a
   box outside `[0,width]×[0,height]` refuses at construction; no clamp, no swap). Nothing else in the
   contract changes; `EVIDENCE_SCHEMA_VERSION` stays 1 (the representation is unchanged; only a
   validation tightened — say so in your W3, and prove every existing evidence fixture still constructs).
4. **`tests/test_evidence_boundary.py`** amended precisely: `evidence/` imports nothing from any
   repository package (`analysis`, `ocr`, `discovery`, `webapp`, `telemetry`, `layout`, `tools`); NO
   third-party import anywhere in `evidence/` EXCEPT `fitz`, and that one ONLY as a lazy import inside
   `evidence/native.py::native_evidence_from_pdf` (AST: the import node's enclosing function name and
   module are asserted); `import evidence` succeeds in a subprocess where `fitz` is made unimportable
   (`sys.modules["fitz"] = None`); a module-level `import fitz` anywhere in `evidence/` fails the test.
5. **Native evidence persisted (D5).** `ocr/document.py::StatementMarkdown` gains
   `native_evidence: ExtractionEvidence | None = None` with its own `__post_init__` check (page count
   equal to `len(pages)`; NO text-equality requirement — the native page strings come from
   `_native_pages`, not from word grouping; document that asymmetry in the docstring). The native rung in
   `ocr/pipeline.py` attaches `native_evidence_from_pdf(pdf_bytes)` to the `StatementMarkdown` it
   returns (once per document; `None` when the reader returns `None`). `webapp/artifact_cache.py`: the
   OCR record persists `native_evidence` (JSON via `evidence.to_json`) and its `native_evidence_sha256`;
   `cached_ocr` restores it (a cache hit reproduces the sha byte-for-byte); **`EXTRACTION_SCHEMA_VERSION`
   2 → 3** in the same commit as its pin in `tests/test_artifact_cache.py`; a schema-2 record restored
   from an old cache (no `native_evidence` key) still restores with `native_evidence=None` and analyses
   (no crash). `to_markdown()` is byte-identical (the committed corpus artifacts and
   `tests/corpus_cache/` pin it). The row's `evidence_sha256` column is populated for native reads by
   the runner — NOT your file: expose the sha on the `StatementMarkdown` (`native_evidence_sha256`
   property) and name the one-line runner change in your W3 for cell T.
6. **The analysis key (D6).** `webapp/artifact_cache.py::analysis_input_sha(markdown, sheets, *,
   evidence_sha256: str | None = None)` — the hash includes `evidence_sha256` or the literal
   `"no-geometry"`; `analysis_settings_key` includes `reconstruction_mode`; **`ANALYSIS_STAGE_VERSION`
   17 → 18** in the same commit as its pin. `analysis/config.py::Settings` gains
   `reconstruction_mode: str = "off"` (closed vocabulary `off | research | production`; anything else
   refuses at load); `analysis/structurer/core.py::structurer_enabled()` reads the setting
   (`!= "off"`) and the `GENERIC_STRUCTURER_ENABLED` environment contract is RETIRED (the variable is
   inert; a test sets it and proves nothing changes; every existing test that set it is updated to the
   setting). The pipeline's `analyze_document(..., document_geometry=...)` signature is unchanged; who
   passes geometry is cell T's seam, not yours — but `cached_analysis(...)` must accept and key on the
   evidence sha (a keyword `evidence_sha256=None` threaded to `analysis_input_sha`).
7. **Research partitions (D7).** The OCR settings key gains `research_partition: str = ""`; a non-empty
   value is key material (its own partition); `telemetry/run_of_record.py` REFUSES to select an artifact
   whose settings key carries a non-empty `research_partition` (raise a named error naming the
   partition; the production selection is unchanged when the field is empty); `tools/train/provenance.py`
   records the field; `tools/cohort_replay.py` needs no change beyond honouring the refusal (verify;
   if it needs one line, it is in your ownership for that line only — say so).
8. **The /Rotate census:** a read-only count over all 3,380 (`Bank Statements/` via the run of record's
   rows) of pages with `page.rotation != 0` — a committed instrument under `tools/` is NOT required for a
   count; run it as a script in your worktree, report `documents with ≥1 rotated page`, `rotated pages`,
   and the rotation-value histogram in your W3 (counts only; no names, no shas).
9. **No hardcodes** (the OQ2 scans already cover `evidence/`, `analysis/`, `ocr/`).

# Files you own (exact; nothing else)
`evidence/native.py` (new) · `evidence/canonical.py` (the bounds check only) · `evidence/__init__.py`
(export) · `analysis/structurer/geometry.py` (the re-export; nothing else) · `analysis/structurer/core.py`
(`structurer_enabled` only) · `analysis/config.py` (the new setting only) · `ocr/document.py` (the new
field only) · `ocr/pipeline.py` (attaching native evidence on the native rung only) ·
`webapp/artifact_cache.py` · `webapp/worker.py` (only if `cached_analysis`'s call site must thread the
sha — say so) · `telemetry/run_of_record.py` · `tools/train/provenance.py` · `tools/cohort_replay.py`
(one line, only if needed) · `requirements*.txt` (no change expected) · tests: `tests/test_evidence_boundary.py`,
`tests/test_evidence_canonical.py` (APPEND), `tests/test_geometry_frames.py` (APPEND), `tests/test_artifact_cache.py`
(APPEND + the two pins), `tests/test_run_of_record.py` (APPEND or new), `tests/test_native_evidence.py` (new),
`tests/test_structurer*.py` (only the env→setting updates) · your W3 section. Anything else → STOP and
report the exact change with its reason.

# Mutation table (run every mutant, name every killer)
M1 rotation matrix not applied (boxes left in unrotated space) → the four-angle pin · M2 `import fitz` at
module level in `evidence/native.py` → the boundary test · M3 a second `import fitz` in `canonical.py` →
the boundary test · M4 the bounds check dropped for `pdf_point` → case 15 · M5 `EXTRACTION_SCHEMA_VERSION`
left at 2 with `native_evidence` persisted → the pin test (and the cache-key test that a schema bump
changes the OCR key) · M6 `native_evidence` restored without re-verifying its sha → the sha round-trip
test · M7 `analysis_input_sha` ignores `evidence_sha256` → case 12 · M8 `reconstruction_mode` absent from
the settings key → case 12 · M9 `ANALYSIS_STAGE_VERSION` left at 17 → the pin · M10
`GENERIC_STRUCTURER_ENABLED` still honoured → the inert-variable test · M11 `run_of_record` selects a
research partition → case 17 · M12 `research_partition` omitted from the OCR key → the partition test ·
M13 the re-export replaced by a local copy of the reader → an AST test that `geometry.py` defines no
function named `native_evidence_from_pdf` (only imports it) · M14 `to_markdown()` emits an extra byte →
the corpus-artifact pin.

# Proof floor (BATCH9-RULES + PHASE2-RULES + the umbrella's rules delta)
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus` from the repo tree or a worktree under `.claude/worktrees/`;
`cohort_replay --expect-identical` at base AND at closure over the UNION of every registration
(`--parser` per id; this cell touches the intake ladder and both cache keys, so the whole offline
partition must replay byte-identical — note the OCR key changes, so replay reads the run of record's
partition through `run_of_record` as it stands; state exactly how you proved identity); privacy scan 0
over your added lines against the run-of-record population (`discovery_reports/TRAIN11-4f7d798/…-331d9136/rows.csv`,
cold cache `.claude/recovery/webapp_data_train11_cold`, READ-ONLY); message scan 0. Heavy proofs one at a
time on this host (`tasklist | findstr python` first).

# Report contract (final message to Ocean AND your W3 section `# §P22IDENTITY — …`)
population (fixtures, the ≥ 12 pinned PDFs by sha16, the rotation census counts) · root cause · solution
· newly validated (0) · other ladder movement (0) · previously validated preserved (all, identical, how
proven under the key change) · regressions (0) · correctness evidence (the two equality pins, the
four-angle pin, the sha round-trip, the two version pins, the partition refusal) · generalization evidence
(a mixed-frame document; a rotated document) · identity evidence (the two key changes) · commits ·
proof-floor exits · privacy count · the one-line runner change for cell T · native-evidence size measured
on the fixtures (extrapolate nothing) · risks last.

# Exclusions
No `discovery/` change · no `layout/` · no structurer enablement or reconstruction change · no Paddle
change · no `ocr/escalation.py` · no `analysis/pipeline.py` · no routing · no cost or billing field ·
no Tesseract boxes · no `local_free` · nothing leaves the machine.
