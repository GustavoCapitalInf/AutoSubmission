# Agent Handoff — P21-GEOMETRY (Phase 2.1 cell G: one `DocumentGeometry` from canonical evidence — native PyMuPDF words and Paddle word boxes through the SAME path; explicit, tested coordinate frames)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `docs/agent-handoffs/PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (all of it — the Phase 2.1 section at the end is
binding), then the umbrella `docs/agent-handoffs/PHASE2-1-PADDLE.md` (§"Evidence contract", D1, D9,
cases 5/6/8), then `evidence/canonical.py` (the contract you consume — read every docstring), then
`analysis/structurer/geometry.py`, `analysis/structurer/rows.py::source_lines_from_geometry`, and
`tests/test_structurer.py`. Ocean reviews and composes; you never merge or push. **Hygiene card:
`newly validated = 0`; every previously validated document preserved with payload identical; no
network call of any kind; nothing under `ocr/`, `discovery/`, `webapp/`, `telemetry/` is touched.**

# Why
`analysis/structurer/geometry.py` is the pre-built, unwired socket for word geometry: it reads native
PDF words with PyMuPDF, groups them into visual lines, and hands `rows.py` positions it cannot get
from flat text. It knows one source (PyMuPDF) and one coordinate space (PDF points, implicitly).
Phase 2.1 adds a second source (PaddleOCR word boxes, in raster pixels) and Phase 2.2 will consume
the result for both. If the two sources take two paths, "one geometry regardless of extraction
source" is a slogan; if PDF points and pixels can be confused, every later column decision is wrong
by a factor of dpi/72. This cell makes the path ONE and the conventions EXPLICIT.

# What you deliver (ruled — do not re-decide)
1. **`native_evidence_from_pdf(pdf_bytes) -> ExtractionEvidence | None`** in
   `analysis/structurer/geometry.py` (PyMuPDF is already this module's lazy dependency; the neutral
   `evidence/` package must stay standard-library-only, so the native reader lives on the consumer
   side, not in `evidence/`). Per page: `PageFrame.pdf_points(page_index=i (0-based),
   width_pt=page.rect.width, height_pt=page.rect.height, rotation_deg=page.rotation)`; one `WordBox`
   per PyMuPDF word (`page.get_text("words")` items with non-blank text), `word_id = word_id(i, None,
   k)`, `line_ref=None`, `confidence=None`; `extractor_id="native-pdf-words"`,
   `model_token="native-pdf-words"`; `runtime={"pymupdf_version": <fitz version string>}`; `raw=None`.
   `document_sha256` = `hashlib.sha256(pdf_bytes).hexdigest().upper()` (the platform convention —
   compute it locally; do not import `ocr.inspect`). Returns `None` exactly when the Phase-2.0
   function returned `None` (unparseable bytes, no words at all); never raises.
2. **`geometry_from_evidence(evidence: ExtractionEvidence) -> DocumentGeometry | None`** — the ONE
   consumer path. For every page: `PageGeometry(page=page_index + 1, width=pdf_width_pt,
   height=pdf_height_pt, lines=…, frame=page.frame, source=evidence.extractor_id)`; words converted
   to PDF points through `evidence.to_pdf_points(frame, …)` (a `pdf_point` frame is the identity; a
   `pixel` frame divides by the per-axis scale); lines taken from `page.lines` (ALREADY derived by
   `evidence.group_lines`, the one rule) and rebuilt as `GeoLine(page, words, text, spans)` with the
   span arithmetic `_group_lines` uses today. `None` when `evidence.word_count == 0`. Never raises
   on its own defect — a structurer input that throws is the W3-1 crash class; wrap and return `None`,
   and add a test that a hostile evidence object (a `words` tuple containing a non-`WordBox`) yields
   `None`, not an exception.
3. **`geometry_from_pdf(pdf_bytes)` becomes `geometry_from_evidence(native_evidence_from_pdf(…))`**
   with BYTE-IDENTICAL output. Pin it: copy the Phase-2.0 implementation VERBATIM into
   `tests/test_geometry_frames.py` as `_legacy_geometry_from_pdf` (with the legacy `_group_lines`) and
   assert equality of `DocumentGeometry` — every page's `page`/`width`/`height`, every line's
   `text`/`spans`, every word's box — on: the structurer fixtures already in `tests/test_structurer.py`,
   the two structurer-safety fixtures, and at least 12 pinned corpus PDFs under `Bank Statements/`
   (choose by name from `corpus_gate.py`'s manifest, read-only; report their sha16s in your W3, not
   their names' contents). The legacy copy exists only to prove the equivalence; it is never called
   by production code.
4. **`PageGeometry` gains `frame: PageFrame | None = None` and `source: str = "native"`** — defaults
   keep every existing constructor call valid (`tests/test_structurer.py` builds them positionally).
   `DocumentGeometry` unchanged. `_group_lines(page_number, words)` stays as a thin wrapper that
   delegates to `evidence.group_lines` (build `WordBox`es from `Word`s, group, rebuild) so the
   grouping rule has ONE implementation — pinned by `tests/test_evidence_canonical.py::
   test_the_grouping_rule_matches_the_structurer_native_grouping_exactly` (already committed) and by
   an AST test of yours that `geometry.py` contains no second median/tolerance computation.
5. **Coordinate conventions, explicit and tested (CASE 5 geometry half, CASE 6, CASE 8):**
   * A synthetic PIXEL evidence (a letter page at 300 dpi; a header row and three ledger rows of
     `WordBox`es with `line_ref` and `confidence`) → `geometry_from_evidence` → every `Word` box in
     points; `to_pixels(frame, x, y)` on each corner reproduces the original pixel box within
     1e-6; `PageGeometry.frame.space == "pixel"`, `.source == "paddle-ocr"`; line texts equal the
     evidence's `page_text` lines; `GeoLine.x_at(offset)` returns the word's x0 in POINTS.
   * The SAME rows as a PDF_POINT evidence (rendered with PyMuPDF into a real one-page PDF via
     `fitz.open()` + `page.insert_text` at known positions — synthetic strings only) →
     `native_evidence_from_pdf` → `geometry_from_evidence` → the same line texts; the two geometries'
     word boxes agree within 1.5 pt (font metrics, not a conversion error — state the measured
     maximum delta in the test's docstring); `.frame.space == "pdf_point"`, `.source ==
     "native-pdf-words"`.
   * Mixed spaces on one document (page 0 pixel, page 1 pdf_point) is LEGAL (a mixed document is
     the Phase 2.4 case) and each page converts by its own frame — test it.
   * Malformed: a frame whose scale disagrees with dpi, an inverted box, a box outside its raster, a
     missing dpi — all refused at `evidence/` construction (already pinned there); YOUR test proves
     `geometry_from_evidence` never sees them because they cannot exist, AND that a hand-built
     `PageEvidence` whose `lines` reference a word id the page lacks cannot be built either. No
     clamping, no swapping, no "best effort" anywhere in `geometry.py`.
   * Rotation: `rotation_deg` is RECORDED from `page.rotation`. Measure over the 109 pinned corpus
     PDFs how many pages carry `rotation != 0` (read-only; count only) and record it in your W3.
     PyMuPDF's `get_text("words")` boxes are in the UNROTATED page space while `page.rect` is the
     rotated (display) rectangle — the Phase-2.0 function already mixed the two on a rotated page,
     and this cell PRESERVES that behaviour (byte-identical, item 3) rather than fixing it silently:
     a rotated native page's `PageEvidence` carries `notes=("native_words_unrotated_space",)` and
     the mismatch is DOCUMENTED in your W3 as a Phase-2.2 prerequisite (the Paddle raster IS
     display-oriented, so a rotated page's native and Paddle geometries would not align until it is
     resolved). Do not apply `page.rotation_matrix` in this cell.
6. **`PageGeometry.page` is 1-based; `PageFrame.page_index` is 0-based** — the one place the two
   conventions meet is `geometry_from_evidence`, and a test pins `page == frame.page_index + 1` on
   every page of a three-page document with an empty middle page (empty pages are KEPT so page
   numbers stay true — the existing `DocumentGeometry` docstring's rule).
7. **No hardcodes:** nothing statement-specific, nothing bank-specific, no literal amounts/dates
   beyond obviously synthetic test strings (`tests/test_no_statement_hardcodes.py` already scans
   `analysis/`).

# Files you own (exact; nothing else)
`analysis/structurer/geometry.py` · `tests/test_geometry_frames.py` (new) · `tests/test_structurer.py`
(APPEND tests only; never edit an existing test) · your W3 section. If you find you need a change in
`evidence/canonical.py` (Ocean's), STOP and report the exact change with its reason — do not edit it.

# Mutation table (run every mutant, name every killer)
M1 `to_pdf_points` returns pixels unchanged for a pixel frame → the round-trip / point-agreement
tests · M2 `page = page_index` (0-based leak) → the page-number pin · M3 `geometry_from_pdf` skips
empty pages → the legacy-equivalence pin · M4 a second grouping implementation with tolerance 0.5 ×
median → the grouping-equality pin + your AST test · M5 `source` hardcoded `"native"` for pixel
evidence → the source assertion · M6 `geometry_from_evidence` raises on a hostile page → the
never-raises test · M7 words re-sorted by text instead of x → line-text pins · M8 `frame` dropped from
`PageGeometry` → the frame assertions · M9 scale applied on one axis only → the round-trip on a
non-square page.

# Proof floor (BATCH9-RULES + PHASE2-RULES, unchanged)
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python
corpus_gate.py` GREEN 105/3/1; `pytest -m corpus` from the repo tree or a worktree under
`.claude/worktrees/`; `cohort_replay --expect-identical` at base and at closure over
`--parser` for every registration whose module imports `analysis.structurer` (measure: `grep -rl
"analysis.structurer" analysis/` — if none, replay the `guardian_cu` + `first_citizens` cohorts as
representative and say so); privacy scan 0 over your added lines against the Phase 2.0 run of record
(`discovery_reports/TRAIN10-941918f/2026-09-02T063646.710847-0000-ef34ee30/rows.csv`, cold cache
`.claude/recovery/webapp_data_train10_cold`, READ-ONLY); message scan 0. `GENERIC_STRUCTURER_ENABLED`
stays unset in every test you write (pin: `structurer_enabled()` is False under the default
environment — add the assertion to your test file).

# Report contract (final message to Ocean AND your W3 section `# §P21GEOMETRY — …`)
population (the fixtures and corpus PDFs you pinned, by sha16) · root cause · solution · newly
validated (0) · other ladder movement (0) · previously validated preserved (all, identical) ·
regressions (0) · correctness evidence (the equivalence pin, the round-trip deltas, the rotation
count) · generalization evidence (the mixed-space document) · commits · proof-floor exits · privacy
count · risks last (the rotation prerequisite named).

# Exclusions
No Paddle code, no HTTP, no `ocr/` imports (the analysis→ocr allowlist is pinned EMPTY — your
imports of `evidence` are the ONLY new import), no structurer enablement, no change to `rows.py` /
`core.py` / `grounding.py`, no `evidence_refs[]`, no rotation fix, no page-level routing.
