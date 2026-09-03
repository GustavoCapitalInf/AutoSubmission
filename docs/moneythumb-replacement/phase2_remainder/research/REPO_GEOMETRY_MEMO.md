<!-- Companion to PHASE2_REMAINDER_PLAN.md — research/audit memo produced 2026-09-03 by an independent Fable 5.1 agent under Ocean's direction; read-only investigation; verbatim except for privacy scrubbing of archive filename fragments. -->

# Repository memo — Phase 2.0/2.1 evidence, geometry, Paddle, routing, artifact, provenance, cache and privacy architecture AS BUILT

Read-only investigation of `train11` at the Phase 2.1 closure tree (`4f7d798` code; docs tip `21e3163`). Every claim below cites `file:line` on that tree. Nothing was modified.

---

## 0. One-paragraph orientation

Two independent halves exist and are NOT yet joined in any production or discovery caller:

* **Intake** (`ocr/`) produces a `StatementMarkdown` (`ocr/document.py:11-41`) whose `pages` are flat page strings; since Phase 2.1 a Paddle read also attaches `evidence: ExtractionEvidence` (immutable canonical words + boxes) and a per-page `page_extractor` token list. The native ladder attaches NO evidence (`ocr/pipeline.py:92-112` sets only `page_integrity` and `page_extractor`).
* **Analysis** (`analysis/`) reads the flat markdown string through the parser registry and — only on the *unclaimed* branch, only with `GENERIC_STRUCTURER_ENABLED=1` (off everywhere, pinned) — the generic structurer, which can optionally take a `DocumentGeometry` (`analysis/pipeline.py:701-704, 730-733, 823-827, 1149-1153`).

Nobody wires the two together: `discovery/runner.py::_analyse` (`discovery/runner.py:965-991`) calls `analyze_document(markdown, parse_mode="deterministic", on_dispatch=..., sheets=...)` with **no `document_geometry`**, and nothing under `discovery/`, `webapp/` or `analysis/pipeline.py` calls `geometry_from_evidence(document.evidence)` or `geometry_from_pdf(...)`. The only caller of `geometry_from_pdf` outside its own package is the measurement tool `tools/measure_structurer.py:40,117`. So `DocumentGeometry` is proven, tested, byte-pinned infrastructure that no document in production or discovery has ever flowed through. That is the single most important fact for Phase 2.2 planning.

---

## 1. `evidence/canonical.py` — the canonical evidence model

**Package contract**: stdlib-only, owned by neither `ocr` nor `analysis` (`evidence/canonical.py:5-16`; pinned by `tests/test_evidence_boundary.py`). It "never decides what any word MEANS" (`:13-14`).

**Coordinate conventions** (`:18-39`): two closed spaces `"pdf_point"` and `"pixel"` (`:87-89`); origin top-left, y down in both (`:24-26`); box `(x0, y0, x1, y1)` with strict `x0 < x1 and y0 < y1`, refused (never clamped/swapped) otherwise (`:27-29, 306-310`); `page_index` 0-based everywhere in this package, `PageGeometry.page` is 1-based and derived as `page_index + 1` in exactly one place (`:35-39`).

**`EVIDENCE_SCHEMA_VERSION = 1`** (`:85`) — the serialized *evidence* shape's version. (This is distinct from `EXTRACTION_SCHEMA_VERSION = 2` in `webapp/artifact_cache.py:531`, which versions the OCR *artifact record* shape: `model/pages/page_integrity` + since v2 `page_extractor` + `evidence`.)

Key types, verbatim:

```python
@dataclass(frozen=True)
class PageFrame:                      # evidence/canonical.py:160-178
    page_index: int
    space: str
    width: float
    height: float
    pdf_width_pt: float | None = None
    pdf_height_pt: float | None = None
    raster_width_px: int | None = None
    raster_height_px: int | None = None
    dpi: float | None = None
    raster_sha256: str | None = None
    rotation_deg: int = 0
    scale_x: float = 1.0
    scale_y: float = 1.0
```
Validation (`:180-228`): a `pdf_point` frame has scale exactly 1.0 and no raster fields; a `pixel` frame requires raster dims, dpi, PDF dims in points, and per-axis scales within `SCALE_TOLERANCE = 0.01` of `dpi/72` AND of `raster_px/pdf_pt` (`:213-226`). `rotation_deg ∈ {0,90,180,270}` (`:100, 187-188`). Constructors `PageFrame.pixel(...)` (`:230-244`) and `PageFrame.pdf_points(...)` (`:246-250`). Converters `to_pdf_points` (`:253-257`, division by per-axis scale) and `to_pixels` (`:260-265`, refuses on a `pdf_point` frame).

```python
@dataclass(frozen=True)
class WordBox:                        # evidence/canonical.py:278-296
    word_id: str                      # "p{page}.l{line}.w{index}" (`:272-275`; "l-" when no line)
    page_index: int
    text: str
    x0: float; y0: float; x1: float; y1: float
    confidence: float | None = None   # ANNOTATION only; per-LINE score for Paddle 3.7; None for native (`:282-286`)
    line_ref: int | None = None       # extractor's own line index; None for native
```

```python
@dataclass(frozen=True)
class LineBox:                        # evidence/canonical.py:329-339
    line_id: str; page_index: int; y_top: float; y_bottom: float
    word_ids: tuple[str, ...]; text: str
```
`LineBox` is DERIVED by `group_lines` (`:353-389`), "never taken from an extractor's own line breaks" (`:331-332`). The ONE grouping rule: sort by `(round(mid_y, 1), x0)`, start a new line when a word's mid-y differs from the previous word's by more than `max(1.0, 0.6 × median word height)` (`:342-350, 362-376`), then sort each line by `x0`; `text` = words joined by single spaces. One page per call (`:365-367`).

```python
@dataclass(frozen=True)
class PageEvidence:                   # evidence/canonical.py:396-406
    frame: PageFrame
    words: tuple[WordBox, ...]        # extractor order
    lines: tuple[LineBox, ...] = ()   # derived via group_lines if empty (`:430`)
    raw: Mapping[str, Any] | None = None   # extractor's verbatim per-page result, deep-frozen (`:439-448`)
    raw_sha256: str | None = None
    notes: tuple[str, ...] = ()
```
Pixel-frame words must lie inside the raster (`:422-429`); a `pdf_point` frame has **no bounds check** (the review measured a rotated footer word accepted 151 pt below the declared height — `reviews/PHASE2_P21GEOMETRY_REVIEW.md:50`).

```python
@dataclass(frozen=True)
class ExtractionEvidence:             # evidence/canonical.py:472-487
    document_sha256: str
    extractor_id: str
    model_token: str
    pages: tuple[PageEvidence, ...]   # contiguous from 0 (`:503-505`)
    runtime: Mapping[str, Any] = field(default_factory=dict)  # provenance facts, deep-frozen
    schema_version: int = EVIDENCE_SCHEMA_VERSION
    evidence_sha256: str = ""         # sha over canonical JSON of everything else (`:508-512`)
```
`page_text(page)` (`:464-469`) = derived lines joined by `\n` — D9's page string the validator reads for a Paddle page. `to_json`/`from_json` (`:565-600`) are deterministic; `from_json` re-derives and refuses a drifted `evidence_sha256`/`raw_sha256` (`:570-573`).

**How the two sources map in**:
* Native: `analysis/structurer/geometry.py::native_evidence_from_pdf` (`:236-340`) — PyMuPDF `page.get_text("words")` → one `WordBox` per non-blank word, `word_id(page_index, None, k)`, `line_ref=None`, `confidence=None`, frame = `PageFrame.pdf_points(width=page.rect.width, height=page.rect.height, rotation_deg=page.rotation)` (`:297-305`), `raw=None`, `runtime={"pymupdf_version": ...}` (`:278-280`), `extractor_id = model_token = "native-pdf-words"` (`:73`). Two page-level failure notes: `native_page_unreadable` (placeholder 1×1 frame, `:92, 307-308`), `native_page_word_refused` (real frame, zero words — one bad box refuses the WHOLE page, `:106, 319-321`), plus `native_words_unrotated_space` on any rotated page (`:115, 317`).
* Paddle: `ocr/paddle_adapter.py::page_evidence_from_result` (`:63-138`) reads exactly `text_word[i][j]`, `text_word_boxes[i][j]`, `rec_texts`, `rec_scores` from the 3.7 `return_word_box=True` result; `word_id(page, i, j)`, `line_ref=i`, `confidence=rec_scores[i]` (line score copied to each word, `:14-17, 96-128`); blank words dropped and counted in `notes` (`:107-109, 135`); any length mismatch / non-string / bad box → `PaddleAdapterError` for the WHOLE page → the rung fails the WHOLE document (`:37-44`; `ocr/paddle_rung.py:217-220`). `raw` = the whole Paddle result dict minus `input_path` (`ocr/paddle_worker.py:300-302`), so `dt_polys`, `rec_polys`, `rec_boxes`, `textline_orientation_angles` are all retained verbatim inside the immutable evidence.

**What is kept vs lost**: kept — word text, word box, per-line confidence, extractor line index (Paddle only), page frame with dpi/rotation/raster sha, the verbatim raw result (Paddle only), derived lines. Lost/never captured — font name/size/style, glyph-level boxes, colour, ruling lines / graphics, PyMuPDF's own block/line structure (`get_text("words")` returns block/line/word numbers in items 5-7 of each tuple, which the reader discards at `:311-315`), text direction, reading-order hints, image regions. Rotation is *recorded*, not applied (see §5).

---

## 2. `DocumentGeometry`, its consumers, and the structurer as built

`ocr/document.py` is NOT geometry — it is `StatementMarkdown`, the intake seam object (`:11-41`): `source_file`, `model`, `pages: list[str]`, `page_integrity`, `page_extractor: list[str]`, `evidence: ExtractionEvidence | None`. `__post_init__` (`:43-124`) validates tokens, refuses line breaks / `-->` in `source_file`, requires `page_extractor` length == pages, and requires `evidence.page_texts() == pages` exactly (`:110-124`) — the derived page strings and the evidence are one object. `to_markdown()` (`:135-151`) is byte-pinned by the committed corpus artifacts and carries NO geometry.

`DocumentGeometry` lives in `analysis/structurer/geometry.py`:

```python
@dataclass(frozen=True)
class Word:      text; x0; y0; x1; y1                     # PDF points, origin top-left (`:120-136`)
@dataclass(frozen=True)
class GeoLine:   page: int; words: tuple[Word,...]; text: str; spans: tuple[tuple[int,int],...]  # (`:139-162`)
                 # x_at(offset) -> the x0 of the word containing that text offset (`:157-162`)
@dataclass(frozen=True)
class PageGeometry: page: int (1-based); width; height; lines; frame: PageFrame|None = None; source: str = "native"  # (`:165-179`)
@dataclass(frozen=True)
class DocumentGeometry: pages: tuple[PageGeometry, ...]   # .lines, .word_count (`:182-194`)
```
Representation: **lines of words in PDF points**, per page, plus (since 2.1) the frame and source. That is the whole vocabulary: there is no row object, no column object, no block, no table, no region, no page-header/footer notion, no cross-page link. `geometry_from_evidence` (`:343-405`) converts every word to points through its own page frame, rebuilds lines from `page.lines` (never regroups), keeps empty pages, returns `None` on zero words or any hostile shape. `geometry_from_pdf = geometry_from_evidence(native_evidence_from_pdf(...))` (`:408-420`), pinned byte-identical to Phase 2.0 on 109 PDFs / 830 pages.

**Consumers that exist**:
1. `analysis/structurer/rows.py::source_lines_from_geometry` (`:157-162`) — flattens `geometry.lines` to `SourceLine(page, text, index, geo)`; the only production consumer.
2. `tools/measure_structurer.py:117` — the W3-3c measurement harness.
3. `ocr/column_grid.py` — **does NOT consume `DocumentGeometry`**. It defines its own `GridWord` (`:65-87`, "deliberately local" because `ocr/` may not import `analysis/`), reads PyMuPDF words directly (`page_words`, `:134-144`), and is used by the native-text rung's bank-specific readers (Woodforest per `ocr/native_text.py:500`; `GEOM-1`). It already contains real geometric mechanisms worth graduating: header-named column bands (`find_columns`, `:163-186`), right-edge cell snapping for right-aligned money (`read_rows`, `:295-298, 341-359`), row = anchor cell + everything until the next anchor (not "a visual line", `:247-260`), last-row floor by line pitch (`_last_row_floor`, `:189-223`), split-cell refusal (`:361-375`), collision/ambiguity refusals (`GridRefusal`, `:125-131`). It is bank-agnostic in mechanism but each caller supplies the header label vocabulary.
4. `analysis/tables.py` — HTML-table and flattened-text utilities for parsers (`:1-33`); no geometry; `group_rows`/`read_grid_rows` operate on text lines.
5. `ocr/native_text.py::parse_native_printed_rows` (`:1453-1515`) and `_printed_lines`/`_row_bands` (`:1190-1280`) — another geometry reader (PyMuPDF `get_text("dict")` line boxes) inside the native rung that rewrites flattened text into printed rows for the core-processor family. Again local, not `DocumentGeometry`.

So there are today **three separate geometric readers** (structurer geometry, `column_grid`, `native_text` printed-rows), only one of which is the canonical `DocumentGeometry` path. Phase 2.2 must decide whether the other two graduate into (or are re-expressed on top of) the canonical geometry; the import boundary (`analysis → ocr` allowlist pinned EMPTY, `tests/test_escalation_tripwires.py:52`; `ocr → analysis` forbidden) means graduation must go through the neutral `evidence/` package or a new neutral layout package.

**The structurer (W3-3c) as built** — `analysis/structurer/{core,rows,tokens,summary,grounding}.py`:

* Entry: `structure_unclaimed(markdown, *, geometry=None) -> Statement | None` (`core.py:216-233`), never raises, off unless `GENERIC_STRUCTURER_ENABLED` (`core.py:45, 63-64`). Diagnostic entry `structure_document(markdown, geometry=None, require_grounding=True) -> StructureOutcome` (`core.py:94-206`) returning `reason ∈ {no_text, no_dated_rows, no_signable_rows, no_printed_period, posting_before_inferred_period_start, period_excludes_rows, ledger_incomplete, ungrounded, structured}`.
* Pipeline placement: unclaimed branch only, after the parser registry sweep, never for `ambiguous`/`parser_exception` (`analysis/pipeline.py:816-827`); adopted as `model_used = "generic-structurer-deterministic"` (`:906-913`); then the SAME `reconcile`, metrics and integrity gates as any parser (`:917+`).
* Input: lines (from geometry if given, else flattened markdown with `<tr>` flattening, `rows.py:127-162`). **Rows are lines**: one `SourceLine` → at most one `_RawRow` (`rows.py:286-331`). A row is a line whose first readable date sits in the date x-band (geometry) or at offset ≤ 2 (text) and which carries ≥1 money token; a non-row, non-heading line with no money and < 120 chars is appended to the previous row's description (`:301-310`) — the only continuation handling.
* Column inference: date band = the largest 1-D cluster (gap tolerance 6 pt) of first-date x positions, ≥5 members and ≥50% of dated lines (`_date_column`, `:197-221`); money bands = 1-D clusters (tolerance 12 pt) of money-token x0 positions with ≥5 members (`_money_columns`, `:224-236`). Positions are the word x0 at the token's text offset (`GeoLine.x_at`).
* Role/sign inference — deliberately a single hypothesis tested against the document's arithmetic: H1 "last money token is the running balance, second-last is the amount", accepted iff `balance[i] − balance[i−1] == amount[i]` for ≥ 90 % of ≥ 5 checked rows (`MIN_CHAIN_AGREEMENT`, `MIN_CHAIN_ROWS`, `:41-50, 334-352, 373-375`); with ≥3 money bands, debit/credit band identity is voted by balance movement (`columns_debit_credit`, `:448-485`); fallback sign from the nearest direction heading word (`_section_sign`, `:253-267`) only when NOT chained (`:411-420`); otherwise the row is not published (`:422-423`). Summary furniture excluded by a prefix regex (`_ROW_EXCLUSION_RE`, `:71-78`).
* Summary/period: label vocabulary (`summary.py:45-72`), first-label-wins (`:86-113`), period from a printed range or from the two balance anchor dates (`:195-234`) with a `+1 day` inference for prior-close labels (`:185-192, 227-229`), bounded 5–100 days (`:157-158`).
* Publication requires: rows inside the period; `beginning + Σamounts == ending` within 0.02 (`core.py:191-194`, `ledger_incomplete` otherwise); and grounding — every row's amount located in the raw page text within 240 chars of one of ~30 renderings of its date and a distinctive description word, span-unique; both balances beside a label; 100 % transaction coverage (`grounding.py:224-294`).
* Generality: bank-agnostic by construction (no issuer names; English + Canadian-French month words, `tokens.py:41-51`), but structurally narrow: single-hypothesis balance chain; line = row; no header detection/semantics (direction words only); no wrapped-row assembly beyond text-only trailing lines; no multi-line date-above-description layouts; no repeated-header suppression beyond the summary regex; no multi-account partition (§7 limit 5 of `W3_3C_STRUCTURER.md`); no cross-page continuity model; no currency evidence; no candidate/ambiguity representation — one reading or refusal.
* Measured (`W3_3C_STRUCTURER.md` §4, §4b): on the 109 pinned corpus, 6 published / 5 validated / **0 wrong**; refusals dominated by `ledger_incomplete` 53 (rows missing), `no_printed_period` 19, `ungrounded` 12, `no_dated_rows` 11. On 75 unclaimed archive documents: 4 validated (5.3 %). Sign provenance: 58–78 % heading, 21–42 % chain, < 1 % geometry columns. Conclusion recorded there: "the binding constraint is completeness".
* Tests: `tests/test_structurer.py`, `tests/test_structurer_safety.py` (property/mutation pins — a wrong column is rejected, one printed amount cannot ground two rows, no mutation publishes a statement failing its own arithmetic, rung off by default, never raises: `:116, 196, 263, 283, 295`), `tests/test_structurer_pipeline.py`, `tests/test_geometry_frames.py`.

**Validator-as-optimizer note**: the chain test is a hypothesis check against corroborating printed evidence (the running-balance column), not a search over candidates for one that balances — it tests ONE fixed reading and refuses otherwise. That is the pattern Phase 2.2 must keep; any "generate N column readings, keep the one whose chain agrees" generalisation must instead require the header/geometry evidence to nominate the reading first and the chain only to corroborate. Separately, a pre-existing edge in the LLM auto branch — `analysis/pipeline.py:918-960` chooses between the cheap and the escalation model's extraction by which reconciles better (`better_summary`/`fewer_issues`) — IS validator-driven selection; it is unreachable in `parse_mode="deterministic"` (the discovery runner and the corpus gate) but live in the webapp's `auto` mode. Phase 2 planning should name it (it predates Phase 2 and Ruling A did not touch it).

---

## 3. The Paddle path

**Worker** (`ocr/paddle_worker.py`, deployed alone to the Vast host): stdlib `ThreadingHTTPServer` bound to `127.0.0.1` only (`:137-147, 622-625`); identity from its own env, validated against the closed pairing (`:69-71, 150-167`); pins as literals (`:73-85`): PaddleOCR 3.7.0, PaddlePaddle 3.3.0, `PP-OCRv5`, det `PP-OCRv5_server_det`, rec `en_PP-OCRv5_mobile_rec`, switches `use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, return_word_box=True, text_rec_score_thresh=0.0`. Pipeline = plain `PaddleOCR(...)` det+rec (`:256-269`) — **no PP-StructureV3, no layout detection, no table recognition, no orientation classifier, no unwarping**; `predict(input=array, return_word_box=True)` (`:289`), one inference at a time (`:279`). Bounds enforced before decode (`:93-99, 392-445`): body ≤ 32 MiB, PNG only (magic + IHDR), ≤ 6,000 px side, ≤ 30 MP, JSON depth ≤ 20; closed error tokens (`:106-117`); optional bearer token on every route (`:448-463`); no disk, one content-free log line per request (`:26-28, 545-546, 616`). Response: `raw` (result minus `input_path`), image dims + sha, timing (`decode_ms`, `inference_ms`, `total_ms`, `cold_load`), `gpu.memory_used_mib`, the identity block, `request_id`, `page_index` (`:517-531`).

**Client** (`ocr/paddle_client.py`): stdlib `urllib` only; loopback URL required at construction (`:150-154`); a `remote_paid` client cannot be constructed without the remote opt-in literal re-derived from the environment (`:155-164`), nor with `customer_data_opt_in` unless the customer literal is in the environment (`:165-173`); `MAX_RESPONSE_BYTES = 64 MiB`, `DEFAULT_TIMEOUT = 120 s`, `MAX_TRANSPORT_RETRIES = 2` same-URL transient-only (`:62-66, 186-207`); redirects refused (`:108-113`); `verify_identity` compares nine fields exactly plus shape bounds on `gpu`/`python_version`/`cuda_compiled` (`:70-80, 281-311`). `probe()` never raises (`:314-341`).

**Rung** (`ocr/paddle_rung.py::read_document`, `:139-246`): order = settings → `check_remote_authorization(settings, data_scope)` → `verify_identity` → `rasterize_pdf(pdf_bytes, dpi=300)` (pdf2image/Poppler, `ocr/rasterize.py:23-25`, display-oriented) → page-count agreement with PyMuPDF or `paddle_frame_mismatch` (`:165-178`) → per page `PageFrame.pixel(raster dims, dpi, pdf_width_pt=page.rect.width, pdf_height_pt=page.rect.height, raster_sha256, rotation_deg=page.rotation)` (`:189-203`; note `page.rect` is the ROTATED display rect, consistent with the raster) → PNG in memory → `client.ocr_page` → envelope check → adapter (`:205-221`). Whole-document failure on any page's frame or adapter refusal; transport errors propagate. Output `PaddleRead(pages=evidence.page_texts(), evidence, page_extractor=[token]*n, telemetry)` (`:90-101, 242-246`). `runtime` is built from a closed whitelist (`RUNTIME_FIELDS`, `:73-78, 101-124`): versions, models, switches, gpu, cuda, python, `provider`, `execution_class`, `worker_contract`, `dpi`, `data_scope` — never URL/host/port/token. **Batching**: none — one page per request, sequential; no concurrency. **Timeouts**: 120 s per request. **DPI**: 300 fixed (`ocr/paddle_config.py:113`; a letter page = 2550×3300 px, under PP-OCRv5's 4000 px limit).

**Telemetry/cost**: per-page `inference_ms`, `total_ms`, `bytes_sent/received`, dims, `cold_load`, `gpu_memory_used_mib`, plus totals (`paddle_rung.py:127-139, 223-231`). GPU-seconds are NOT computed from these; "total GPU-attributable seconds" is the worker wall time between `start` and `stop` measured by the lifecycle tool (`P21-PADDLE.md` §6). `telemetry/record.py:490-508` reports one model call per Paddle page with `purpose: "paddle_ocr"`, unpriced (not in `FREE_MODELS`), so `estimate()` reports `unpriced` and cost is "rate not measured" (`PADDLE_MEASUREMENTS.md`). Measured on the synthetic 8-row page: cold e2e 5,208 ms, warm median 1,872 ms / p95 2,152 ms, ~331 KiB wire per page, ~12 KiB back, 7.7 GiB VRAM resident.

**Lifecycle** (`tools/paddle_vast.py`): `check / deploy / start / tunnel-up / status / measure / stop / tunnel-down`; SSH `-L 127.0.0.1:18765:127.0.0.1:8765` (`:143-148`); per-session token file (`:292-296`); every printed value masked (`:111-120`); `measure` refuses any fixture path containing `"Bank Statements"`, `"tests/corpus_cache"`, `"discovery_reports"` (`FORBIDDEN_FIXTURE_SUBSTRINGS`, `:74-78`).

**Provenance classification**: `remote_paid` by declaration (`PADDLE_PROVIDER=vast.ai` ⇒ `remote_paid` only, `ocr/paddle_config.py:129-142, 279-283`) corroborated by the worker's echo (`paddle_client.py:296-310`); `ocr.endpoint_policy.classify_endpoint` is used only to REQUIRE loopback, never to classify the execution (`paddle_config.py:11-16, 300-304`).

---

## 4. Routing and the privacy boundary

**Router** (`ocr/escalation.py`): closed failure classes A/B/C/"" (`:71-91`); closed triggers with `TRUNCATION_FLAGGED` defined-but-refused (`:104-178`); `EXTRACTOR_ORDER = ("local_tesseract", "paddle", "visual")` (`:205`) with a comment naming a future `"unlimited_ocr"` slot (`:201-202`); `RouterInputs(profile, evidence, triggers, attempted, stop, enabled)` (`:367-401`) — six fields pinned, no subclassing, one constructor `router_inputs(...)` (`:404-425`); `decide` = `stop` → refuse; no admitted trigger → refuse; first extractor in order ∈ `enabled` ∖ `attempted` (`:449-480`). `ExtractionQualityGate.assess` (`:325-360`): `usable` decided only by `no_text_produced` / `below_char_floor` (200) / `all_pages_empty`; the alnum-density floor 0.70 is SURFACE-ONLY (`:218-271`, Ruling B). Class-A is assessed only for extractor-produced reads (`discovery/runner.py:373-391`, `GATE_ASSESSED_SOURCES = {"local_tesseract","visual","paddle"}`); a native read is never Class A (`:377-384`).

**Ladder** (`ocr/pipeline.py::parse_statement`, `:22-222`): non-forced path = native rung (skipped when the profile says zero native chars, `:78-88`) → Tesseract if `allow_local_ocr` (`:89-91`) → return; the Paddle rung runs ONLY on `force_ocr and allow_paddle_ocr and not allow_visual_ocr` with a REQUIRED `paddle_data_scope` (`:118-152`); lazy import of `ocr.paddle_rung` (`:131-132`); otherwise the visual (Unlimited-OCR-style OpenAI-dialect) rung (`:154-222`).

**Discovery** (`discovery/runner.py`): `MODE_SCANNED_PADDLE` (`:113`); `enabled_extractors` = `{"paddle"}` for that mode, `{"visual"}` for `--scanned-visual`, else empty (`:667-676`); `_read_paddle` (`:844-918`) calls `parse_statement(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False, allow_paddle_ocr=True, paddle_data_scope="customer")` — the LITERAL `"customer"` pinned by AST (`:848-851, 876-877`) — through `cached_ocr(... allow_paddle_ocr=True)` (`:887-899`); a `PaddleRefused("remote_customer_data_refused")` becomes row token `refused_customer_data` (`:904-913, 1204-1206, 1325-1326`). Recovery path (offline ladder produced nothing) and upgrade path (gate-unusable Tesseract read) both dispatch on `decision.extractor` (`:1140-1218, 1257-1353`). The upgrade path adopts a Paddle read only when `_analyse` produced a payload, keeping both source paths on the row (`:1329-1346`; CASE 9). Rows carry `paddle_rung`, `cache_paddle`, `escalation_extractor`, `evidence_sha256`, `paddle_provider`, `paddle_execution_class`, `paddle_refusal_reason` (`:253-287`).

**What BLOCKS customer-scope documents from Vast today** — three independent gates, all keyed on ONE literal:
1. `ocr/paddle_config.py::check_remote_authorization` (`:356-404`): `data_scope == "customer"` on a `remote_paid` worker → `PaddleRefused("remote_customer_data_refused")` unless `settings.customer_data_opt_in` AND `os.environ["PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN"] == "I_AUTHORIZE_CUSTOMER_DOCUMENTS_TO_REMOTE_PADDLE_OCR"` (`:148-151, 395-404`). Called first thing in `read_document` (`paddle_rung.py:158`).
2. `ocr/paddle_client.py::PaddleClient.__init__` (`:165-173`): a settings object claiming `customer_data_opt_in` without the environment literal cannot construct a client.
3. `tools/paddle_vast.py::cmd_measure` refuses real-data fixture paths (`:74-78`) — this is the lifecycle tool's synthetic-only measurement, unrelated to the runner.
Plus the standing rules: the test suite asserts the customer literal is ABSENT from its environment (`P21-ROUTING.md` Exclusions); `PADDLE_VAST_RUNBOOK.md` forbids setting it without the ruling; `PHASE2_RULINGS.md` §"Data privacy boundary".

**What must change to honour Gustavo's new authorization (brief §6) while preserving the listed protections** — and, importantly, what need NOT change:
* Code: NOTHING structural. The gate is already designed for this: set `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN=I_AUTHORIZE_CUSTOMER_DOCUMENTS_TO_REMOTE_PADDLE_OCR` in the environment of the specific `--scanned-paddle` run (never a tracked file), alongside `PADDLE_REMOTE_OPT_IN`. `load_paddle_settings` derives `customer_data_opt_in` from it (`paddle_config.py:345-347`), `check_remote_authorization` re-derives it (`:395-398`), the client re-derives it (`paddle_client.py:165-173`), `read_document` records `data_scope="customer"` in `evidence.runtime` (`paddle_rung.py:64-72, 122`), the row records `paddle_provider`/`paddle_execution_class` (`runner.py:1493-1494`). Provenance, loopback, bounds, no retention, no content in logs and `remote_paid` classification all hold unchanged.
* Docs/rulings: record the authorization in `PHASE2_RULINGS.md` (the runbook's step 1, `PADDLE_VAST_RUNBOOK.md` §"The 13-document remote-data ruling"); update the runbook's boundary paragraph; update `P21-ROUTING.md`'s "the customer literal asserted ABSENT from the suite's environment" — the SUITE must keep that assertion (the default suite must never be able to send anything), while the operator's run environment carries it.
* Tests: the existing suite pins the refusal both ways; a test that the literal is absent from the *test* environment must stay. No test needs weakening.
* Two things the authorization does NOT reach, by construction of the current code: (a) the broad evaluation the brief wants (Paddle over unresolved documents that HAVE native text) is not reachable through `--scanned-paddle`: the router names `paddle` only on an admitted Class-A trigger (`offline_rungs_produced_no_text`, `extractor_output_unusable`, `operator_forced_visual` on the forced-only sites) and the upgrade path is entered only for Tesseract-sourced reads (`runner.py:1245-1257`) — a native-text document never reaches `decide` with an admitted trigger. So a broad evaluation needs a NEW, explicitly research-scoped mode (a mode constant, not a per-document fact — the D4 tripwire at `tests/test_escalation_tripwires.py` forbids per-document `enabled=`), OR an offline instrument that calls `parse_statement(force_ocr=True, allow_paddle_ocr=True, paddle_data_scope="customer")` directly per sha and writes into a separate research cache partition — never through auto mode (Ruling A). (b) `webapp/` has no Paddle call site (AST-pinned; `WORKER_ENABLED_EXTRACTORS == {"visual"}`), and Ruling A keeps it so.

---

## 5. Artifacts, cache, provenance — and the five documented prerequisites

**Keying** (`webapp/artifact_cache.py:25-60, 627-647`): `cache_key = SHA256(cache_format, stage, input_sha, settings_key)`. OCR stage input = raw PDF sha; settings = the 10 base knobs + at v5 `extractor` (`offline|visual|paddle`, `_ocr_extractor` `:688-714`), `allow_paddle_ocr`, postprocess state, `raster_version`, `extraction_schema_version`, `endpoint_class`, tesseract/poppler/pymupdf versions, and for a paddle-labelled call the D5 pin block + provider/class/tokens (`paddle_settings_key_material`, `paddle_config.py:421-434`) — never host/port/token (`:816-901`). Analysis stage input = `analysis_input_sha(markdown, sheets)` = sha over `{text: sha(admissible_text(markdown)), sheets: sha(per-sheet shas)}` (`:617-633`); settings = `analysis_settings_key` (`:904-939`): stage version, parse_mode, model names, registry fingerprint, `generic_structurer` flag. The OCR record (`put_ocr`, `:1076-1102`) stores `model`, `pages`, `page_integrity`, `page_extractor`, `evidence` (`to_json`); `cached_ocr` (`:1162-1270`) restores and refuses a drifted evidence as a miss-with-finding (`CACHE_FINDING_EVIDENCE_DRIFT`).

**Confirmed: the analysis input hash is geometry-blind** — `analysis_input_sha` hashes admissible text + sheet partition only (`:627-633`). Consequence: two OCR artifacts with identical page strings but different word boxes (or an artifact with evidence vs one without) resolve to the SAME analysis key. Today that is harmless because no caller passes `document_geometry` (§0) and the structurer is off. The day Phase 2.2 hands geometry to `analyze_document`, a cached analysis computed text-only would be served for a geometry-fed call and vice versa. Also `analysis_settings_key` carries `generic_structurer` but not a "geometry-fed" flag. The fix is a reviewed key change (add `evidence_sha256`-or-`None` — or a geometry digest — to the input hash; add a settings flag for the reconstruction mode) with an `ANALYSIS_STAGE_VERSION` bump; the run-of-record reconstruction (`telemetry/run_of_record.py`) must be taught the new shape as P20-ARTIFACTS did for OCR v4→v5.

**The five prerequisites, assessed against brief §23**:

| # | Item | Where | Blocks broad Paddle / generalized reconstruction? | Correctness | Reproducibility / cache | Performance | Belongs in Phase 2? When? |
|---|---|---|---|---|---|---|---|
| 1 | Rotation-frame mismatch (native words unrotated vs display-oriented raster) | `geometry.py:108-116, 297-305, 317`; `paddle_rung.py:189-201` (Paddle frame = display rect, consistent); reviewer's synthetic proof at 90/180/270 (`PHASE2_P21GEOMETRY_REVIEW.md:50`) | Not for Paddle-alone reconstruction (Paddle frames are internally consistent). It DOES block (a) any native-vs-Paddle comparison/overlay on a rotated page, (b) native-geometry reconstruction on rotated pages (x/y bands would be computed in a space whose width/height are swapped — a `/Rotate 90` page's words sit outside the declared frame), (c) any Phase-3 page-image overlay. | Latent today: 0/830 corpus pages rotated; but the unresolved 755 have NOT been measured for rotation — they must be. A rotated native page would silently produce wrong bands. | Fixing changes native evidence bytes for rotated pages only (evidence sha, geometry); nothing cached today depends on it. | none | YES, early in Phase 2.2 — cheap (apply `page.rotation_matrix` to boxes, or record words in display space and set the frame from the rotated rect; pin with the reviewer's 90/180/270 synthetic), gated by a census of rotation over the unresolved population. Also add the missing bounds check for `pdf_point` frames (a word outside its page should refuse like the pixel case). |
| 2 | Discarded `evidence_sha256` on the native path (~2.7×: 2.57 s → 6.92 s over 109 PDFs; ~51 % is the canonical-JSON+sha of an evidence nobody stores) | `ExtractionEvidence.__post_init__` `evidence/canonical.py:508-512`; `PageEvidence` raw hashing `:439-448`; `geometry.py:334-337`; review F-7 | Does not block correctness. Blocks SCALE: ~0.06 s/doc today → per-document reconstruction over 3,380 docs adds minutes, not hours — acceptable for a research wave, wasteful in production. | none | If the native evidence is later STORED (recommended, so native and Paddle runs are symmetric and the analysis key can carry an evidence sha), the sha becomes load-bearing and must stay. | ~2.7× on the native geometry read | Phase 2.2, low priority: make `evidence_sha256` lazily computed or make the native reader store its evidence in the OCR artifact (then the cost is paid once at intake, cached). Do not optimise before deciding whether native evidence is persisted. |
| 3 | `analysis_input_sha` geometry-blind | `webapp/artifact_cache.py:617-633, 904-939` | YES — it is a hard prerequisite for ENABLING the structurer/reconstruction on geometry with a cache in the loop (the discovery runner always uses the cache; a text-only cached analysis would be served for a geometry-fed call). | High: stale-answer hazard on any warm cache. | Requires a reviewed key change + `ANALYSIS_STAGE_VERSION` bump + run-of-record reconstruction update. | none | YES, FIRST in the reconstruction milestone, before any measurement run with a cache. |
| 4 | Tesseract word boxes | `ocr/local_tesseract.py:12-44` — `--psm 6`, `.txt` output only; no TSV/hOCR; text passes through `StatementMarkdown` with no evidence | Not for Paddle. Relevant only if Tesseract reads are to feed geometry (the 179 Tesseract-sourced archive reads) or serve as an independent second geometry for OCR-disagreement checks. Tesseract boxes are word-level with confidences (TSV), so the adapter would be trivial; but Tesseract's text quality is the reason Paddle exists. | none | Would change the offline OCR artifact shape (evidence on Tesseract reads) → OCR stage bump; the committed corpus artifacts (`tests/corpus_cache`, `build_corpus_cache.py`) pin Tesseract MARKDOWN, not boxes — adding evidence beside them is additive but the manifest format changes. | Tesseract re-run cost | DEFER until the Paddle evaluation shows whether Tesseract-sourced documents are recovered by Paddle anyway; revisit only as an OCR-disagreement instrument (brief §17), not as a coverage path. |
| 5 | `local_free` worker deployment | `paddle_worker.py:69-71` (provider-agnostic), `paddle_config.py:129-142`; no local `paddleocr` install (umbrella baseline) | Not for the evaluation (Vast is authorized). Relevant for COST and for production routing (a `local_free` Paddle would make Paddle a $0 rung and change the endpoint/cost calculus of the final router). | none | A `local_free` read is a DIFFERENT cache partition by design (`provider`/`execution_class` are key material, `paddle_config.py:421-434`); evidence shas may legitimately differ between GPU/CPU builds (Paddle is not bit-identical by contract). | CPU inference latency unknown | DEFER past the evaluation; decide from measured per-page cost and the routing decision. Keep the worker contract unchanged so it is a deployment, not a code change. |

**Version pinning & drift** (§7 of the directive): the identity is pinned in `ocr/paddle_config.py:88-113` and duplicated as literals in the worker (`paddle_worker.py:73-85`); `verify_identity` refuses any field mismatch before an image is sent (`paddle_client.py:281-311`; the "silent PP-OCRv6 hazard", `paddle_config.py:81-85`); the same block is settings-key material (`:421-434`) so a pin change opens a new cache partition; evidence records the identity in `runtime` (`paddle_rung.py:73-78`); telemetry maps only the exact token `paddle-ocr+ppocrv5` to source path `paddle` (`telemetry/record.py:174, 185-201`); `RESERVED_MODEL_PREFIXES` stops an env `OCR_MODEL` impersonating it (`ocr/config.py:76-81`). Not pinned: the PaddleX model weight hashes on the host (the model NAMES are pinned, not the weights' checksums), Poppler's version on the local side IS in the key (`ocr_toolchain_versions`), the worker's Pillow/numpy versions are not. Paddle output is not contractually bit-stable run to run (`PADDLE_MEASUREMENTS.md`), so replay reproducibility rests on the cached artifact, not on re-inference.

---

## 6. Phase 3 readiness — the candidate seam

The candidate type into the validator is `analysis.schema.Statement` (pydantic; `analysis/schema.py:122-225`): `bank`, `account_name`, `account_number`, `period_start/end`, `beginning_balance`, `ending_balance`, `currency` + `currency_source` (closed provenance vocabulary, `:86-101`), the stated summary fields, `stated_daily_balances`, `initialization_transaction_count`, `transactions: list[Transaction(date, description, amount signed, direction, running_balance)]` (`:105-114`). Multi-account documents are `DocumentReport` (one `Statement` per account, `analysis/pipeline.py:290`), published through the account-collection seam (`:770-780`).

Validation applied to any candidate regardless of producer: `reconcile(stmt, parser_id)` (`analysis/reconcile.py:94-314`: sum identity, running-balance continuity, stated-summary identity, coverage, counts), `compute_metrics` (ADB, withholds), `assess_document_integrity` (page declaration etc.), the approval gate — all reached from `_analyse` after `stmt`/`model_used` are set (`pipeline.py:917+`). Grounding (`ground_statement`) is today INTERNAL to the structurer, not a shared validator axis.

Entry points a future evidence-grounded model could use: (1) the unclaimed-branch slot where `structure_unclaimed(markdown, geometry=...)` sits (`pipeline.py:823-827`) — a generalisation would be "a candidate producer that returns `Statement | None` plus a provenance token"; (2) `extract_statement` (`analysis/extract.py`), the existing hosted-LLM producer, reached only in `parse_mode="auto"`, whose output already goes through the same `reconcile` (but with the validator-driven escalation choice noted in §2 — the pattern Phase 3 must not inherit). The inputs a Phase 3 producer needs — page images (rasters; only their sha is kept, `PageFrame.raster_sha256`, the PNGs are not persisted), canonical evidence (persisted for Paddle only), `DocumentGeometry` (derivable), statement context (the runner's row), provenance (`evidence.runtime`, `page_extractor`) — are all present or derivable EXCEPT a persisted page image and a shared grounding layer. The clean seam exists conceptually (`Statement` + `model_used` + the same gates) but is not yet a named interface: there is no "candidate with evidence refs" type (`evidence_refs[]` explicitly excluded in 2.1), and `analysis_input_sha` cannot yet describe a geometry- or image-fed analysis (§5 item 3).

---

## 7. What I could NOT determine (read-only, no runs)

* The rotation distribution over the 755 unresolved documents (only the 109 pinned corpus was censused: 0/830).
* Whether `page.rotation` is ever non-zero on Paddle-eligible scans (irrelevant to Paddle frames, relevant to native/Paddle overlay).
* The actual per-page Paddle cost on real statement pages (dense, multi-column) versus the 8-row synthetic — only the synthetic was measured.
* Whether the Vast host retains anything (the worker writes nothing; the SSH/container level was not audited).
* The real size of the geometry-fed analysis cache hazard in practice (no geometry-fed run has ever been cached).
* How much of `column_grid.py` / `native_text.py` printed-rows logic is reusable on Paddle word boxes (both are written against PyMuPDF words/dict; the mechanisms are transferable, the code paths are not, because of the `ocr`/`analysis` import boundary).
