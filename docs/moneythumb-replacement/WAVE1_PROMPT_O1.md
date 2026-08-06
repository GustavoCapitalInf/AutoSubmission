# Wave 1 — Agent B Implementation Prompt: O-1 Unified Document Preflight

Issued by Ocean (Lead Architect), 2026-08-06. D-1 is completed, reviewed, and
APPROVED (commits 0f335c2..58a65a6 on `wave1-serving`). O-1 is now authorized.
You remain Agent B, serving track.

## Where you work

- Same worktree (`mt-universal-extraction`), same branch `wave1-serving`, building
  ON TOP of your D-1 commits. Commit prefix changes to `O-1:` so Ocean can merge the
  D-1 boundary (through 58a65a6) separately — the wave merge order H-2 → D-1 → R-1 →
  O-1 is preserved at merge time even though you develop linearly.
- Python: `C:/Python314/python.exe`.
- Required reading: WAVE1_BRIEF.md O-1 card (mt-lead worktree docs path you already
  know), `ocr/pipeline.py:15-90`, `ocr/native_text.py` (entry points only),
  `webapp/worker.py`, `webapp/storage.py` (your own hash helper), and
  `docs/balance-metrics-audit-results.csv` (the `source_type` column — your parity
  oracle).

## Objective

One reusable pre-parser inspection layer producing a `DocumentProfile` for every
document, consumed by a SINGLE intake ladder — replacing the drifted duplicate
preflights in `ocr/pipeline.py` and `webapp/worker.py`. This is INSPECTION ONLY:
you do not rewrite, tune, or "improve" any parser or extractor logic. Existing
native-text extractors are CALLED, never modified.

## Scope

1. **New `ocr/inspect.py`** — `DocumentProfile` dataclass + `inspect_pdf(pdf_bytes)`:
   - `valid_pdf` (header + parseable structure), `encrypted` flag
   - `page_count`
   - `content_sha256` — REUSE `webapp.storage.content_sha256` semantics; do not
     define a second hash. If importing webapp from ocr is an unwanted dependency
     direction, put the one-line helper in `ocr/inspect.py` and have
     `webapp/storage.py` import it from there (allowed), keeping ONE definition.
   - per-page native-text availability (reuse the existing char-count logic from
     `parse_native_pdf_text`'s gate — factor the THRESHOLD CONSTANTS out, not the
     extractors)
   - `classification`: digital | scanned | mixed
   - `likely_ocr_required` bool
   - `malformed_pages: list[int]`
   - `likely_account_count: int` — marker heuristics only ("Account Number/Type"
     block counting). ADVISORY: consumed by nothing.
   - `layout_signals` — table markers, statement-period markers, "Page N of M"
     presence, reusing existing regex patterns by reference. ADVISORY: consumed by
     nothing.
2. **Single ladder:** `ocr/pipeline.py` becomes the one place that decides
   native → tesseract → visual OCR, driven by the profile. `webapp/worker.py`
   deletes its private ladder and calls the unified one. `parse.py` adopts it.
   The ladder's ROUTING BEHAVIOR must be preserved exactly (see parity below);
   note that tesseract is currently webapp-only — preserve that: the unified ladder
   takes a capability flag (e.g. `allow_local_ocr`) so `parse.py`'s behavior does
   not silently gain a tesseract stage it never had.
3. **Webapp surfacing (minimal):** `/upload` response and `/status` gain
   `content_sha256` and a `duplicate_of` indication when the same hash was uploaded
   before (query your own `documents` table); encrypted or invalid PDFs are rejected
   at upload with the same JSON error shape D-2a established. No UI work.
4. **Persistence:** store the profile (or its scalar fields) with the document row —
   additive column(s) via your `_MIGRATIONS` hook (schema v2), demonstrating the
   forward-only migration path you built.

## File allowlist (exhaustive — nothing else)

1. `ocr/inspect.py` — new
2. `ocr/pipeline.py`
3. `webapp/worker.py`
4. `webapp/app.py` — minimal surfacing only
5. `webapp/storage.py` — hash-helper relocation (if chosen) + additive migration
6. `parse.py`
7. `tests/test_inspect.py` — new
8. `tests/test_pipeline.py`, `tests/test_webapp_worker.py`, `tests/test_webapp_app.py`,
   `tests/test_webapp_storage.py` — behavior-parity / additive updates, documented
9. `conftest.py` — GRANTED EXCEPTION (your D-1 request, approved): ONE session-scoped
   fixture routing `WEBAPP_DATA_DIR` to a pytest tmp dir so suites never write the
   repo-root `webapp_data/`. Nothing else in this file.

## Protected (do not touch; stop and ask Ocean if you believe you must)

Everything else. Explicitly: ALL of `analysis/`; `ocr/native_text.py`,
`ocr/ocr_client.py`, `ocr/local_tesseract.py`, `ocr/rasterize.py`, `ocr/render.py`,
`ocr/document.py`, `ocr/config.py` (all CALLED, never modified — if a threshold
constant must move, it moves by import from its current home or is duplicated-by-
reference with a comment, not edited in place); `webapp/jobs.py`;
`tests/test_webapp_security.py` (still must pass UNCHANGED); corpus assets, audit
CSVs, `corpus_gate.py`, audit scripts, `tests/corpus_cache/`, `pytest.ini`,
`requirements.txt`, `.github/`, templates/static.

## Acceptance criteria

1. Exactly ONE preflight ladder in the codebase (`webapp/worker.py` contains no
   routing decisions of its own).
2. **Corpus parity:** a test (marked `corpus`? NO — it must run in the default
   suite, so make it fast: native-text detection only, no OCR) proving that for all
   109 corpus PDFs, the profile's digital/scanned classification matches the
   `source_type` column of `docs/balance-metrics-audit-results.csv`
   (digital/native ↔ digital, scanned/local_ocr ↔ scanned). Any mismatch is a
   failure — the profile must describe reality, not redefine it.
3. Corpus gate GREEN and byte-identical (pure-refactor standard: same 106/3, same
   every field). Run once before handoff, attach tail.
4. Duplicate upload of identical bytes → flagged in the upload response; distinct
   bytes → not flagged.
5. Encrypted PDF and non-PDF → JSON 400 at upload (test with a synthetic encrypted
   fixture generated in-test via pypdf if available, else PyMuPDF; if neither can
   produce one, an encrypted-flag unit test on a hand-built minimal PDF is
   acceptable — document the choice).
6. `likely_account_count` and `layout_signals` are consumed by NOTHING (grep-proof:
   no production code reads them; only tests and the stored profile).
7. `tests/test_webapp_security.py`: 70 passed, file untouched. Full suite green.
   Schema migration v1→v2 covered by a test (open a v1 store, migrate, verify).

## Required tests

`tests/test_inspect.py`: profile unit tests per signal (valid/invalid/encrypted/
mixed synthetic PDFs); hash equivalence to the D-1 definition; account-count and
layout signals on synthetic markdown-bearing PDFs; the 109-document parity test
(fast, native-detection only). Updates: ladder parity in `test_pipeline.py` /
`test_webapp_worker.py`; duplicate-flag + rejection tests in `test_webapp_app.py`;
migration test in `test_webapp_storage.py`.

## Commit / handoff / conduct

Same rules as D-1: commits only on `wave1-serving`, prefix `O-1:`, Co-Authored-By
trailer, NEVER merge or push, stop-and-ask (in the final report) for any
non-allowlisted file. Handoff report: commits, file list, ladder description
(before/after), parity-test evidence, migration demonstration, test tails
(inspect, security-unchanged, full suite, corpus-gate tail), deviations/questions.
Do not start any other task. This completes your Wave 1 track.
