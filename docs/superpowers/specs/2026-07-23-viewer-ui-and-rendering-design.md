# Document Viewer UI + Better Markdown Rendering — Design

**Date:** 2026-07-23
**Status:** Approved by delegation ("do whatever you think is best, don't ask")

## Purpose

Two related improvements to the local web app:
1. **Rendering quality** — the rendered markdown should identify more headings and
   render tables/typography much more cleanly.
2. **UI overhaul** — replace the batch job-list UI with a dark, 3-panel document
   viewer modeled on the official Unlimited-OCR demo: original page images |
   markdown source | rendered markdown, with a polished toolbar.

## Decisions (made autonomously)

- **Keep batch.** Multiple PDFs can be uploaded; a document selector in the toolbar
  switches which one is shown in the 3-panel viewer. (Reconciles the demo's
  single-doc look with the earlier batch requirement.)
- **Middle panel = markdown source** (post-cleanup, monospace), not the literal
  `<|det|>` raw — the det tags are noise for a bank-statement tool, and the panel
  still gives the demo's "source view" look. Right panel = the rendered markdown.
- **Toolbar** approximates the demo aesthetic with only real controls: title,
  Upload, document selector, a DPI (detail) selector, and a status pill. No
  fake/cosmetic buttons.

## Rendering improvements (`ocr/render.py`)

- `promote_headers(markdown_text) -> str` — promote standalone ALL-CAPS section
  titles (e.g. `DEPOSITS AND ADDITIONS`, `CHECKING SUMMARY`,
  `CUSTOMER SERVICE INFORMATION`) to `##` markdown headings. Conservative: only a
  line that is all uppercase letters (spaces/`&`/`.`/`-` allowed), 3–50 chars,
  ≤6 words, contains no digit and no HTML tag, and is not already a heading.
  This avoids promoting transaction/data lines (which contain digits or mixed case).
- Richer `_STYLE`: real typographic scale for headings, tables with borders +
  zebra striping + shaded header row + right-aligned numeric-looking cells, code
  blocks, and comfortable spacing. Applied by `markdown_to_html`, which now runs
  `promote_headers` before conversion.
- `markdown_to_html` keeps its existing signature (`markdown_text, title=""`) so
  the CLI `--html` and the `/result` route keep working unchanged.

## UI overhaul (`webapp/`)

### Backend (`webapp/`)

- `Job` gains `pdf_bytes: bytes | None`, `page_count: int`, and keeps `markdown`
  and `html` (already present). `JobStore.set_result` extended to also record the
  markdown (already does) — add `page_count`/`pdf_bytes` recorded at upload time.
- `worker.run_job` unchanged in behavior; it already produces markdown + html.
  `page_count` is derived at upload (rasterize count) or from the result document.
- New routes in `app.py`:
  - `GET /page/<job_id>/<int:n>` — rasterize page `n` (0-indexed) of the job's PDF
    at a display DPI (100) and return it as `image/png`. 404 if job/page unknown.
  - `GET /markdown/<job_id>` — the raw markdown source (`text/plain`). 404 if not done.
  - Existing `/`, `/upload`, `/status/<id>`, `/result/<id>`, `/download/<id>/<fmt>`
    stay. `/upload` response additionally includes `page_count` per job.
- `run_job` / upload store the uploaded `pdf_bytes` and `page_count` on the Job so
  `/page` can rasterize on demand (avoids holding many large page images in memory).

### Frontend (`webapp/templates/index.html` + `webapp/static/app.js`)

- Dark theme. Top toolbar: `Unlimited-OCR` wordmark, Upload button (multi-file),
  a `<select>` document switcher populated as uploads complete, a DPI `<select>`,
  and a status pill reflecting the selected doc's job status.
- Body: three flex columns, each independently scrollable —
  - **Left "Document":** stacked `<img>` page images from `/page/<job>/<n>` for
    n in 0..page_count-1.
  - **Middle "Markdown":** `<pre>` of `/markdown/<job>` (monospace).
  - **Right "Rendered":** an `<iframe>` of `/result/<job>` (the styled HTML).
- Uploading kicks off processing (existing `/upload` + `/status` polling). When a
  job reaches `done`, its option in the switcher is enabled and, if selected, the
  three panels load. `error` shows the message in the panels area.
- Vanilla JS only (no framework), consistent with the existing app.

## Testing

- `ocr/render.py`: unit tests for `promote_headers` (promotes ALL-CAPS section
  titles; leaves data lines, mixed-case text, and existing headings alone) and
  that `markdown_to_html` output contains the promoted `<h2>` and the richer style.
- `webapp/app.py`: Flask test-client tests for the new routes with `parse_statement`
  mocked and `threading.Thread` replaced by a synchronous fake (existing pattern):
  `/markdown/<job>` returns the source once done and 404 before; `/page/<job>/<n>`
  returns PNG bytes for a valid page and 404 for an out-of-range page (rasterize
  monkeypatched to avoid real poppler in the unit test).
- Manual smoke: run the app against the live pod, upload a real statement, confirm
  all three panels render and the switcher works.

## Out of scope

- No change to the OCR engine/prompt or `ocr.pipeline`.
- No literal `<|det|>` raw view (middle panel shows cleaned markdown source).
- No auth/deployment (still local single-user).
