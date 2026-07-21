# PaddleOCR Bank Statement Parser — Design

**Date:** 2026-07-21
**Status:** Approved (pending written-spec review)

## Purpose

A fresh, standalone CLI tool that extracts the **entire** contents of a bank
statement PDF into structured JSON. The JSON is handed to a downstream AI step
that performs calculations (e.g. daily average balance). The parser itself does
no math — it extracts and structures data only.

## Scope & Constraints

- **Input:** PDF files. Mostly digitally-generated (selectable text) but may be
  scanned. The parser treats every PDF the same way: rasterize → OCR.
- **OCR engine:** **PaddleOCR only.** No pdfplumber/EasyOCR/Tesseract fallback
  chain for now.
- **Extraction approach:** Option A — plain PP-OCR (text + bounding boxes) with
  custom bbox-based row/column reconstruction. No PP-Structure.
- **Bank handling:** Option 2 — detect the bank, apply a per-bank profile;
  generic fallback for unknown banks.
- **Interface:** CLI — `python parse.py <statement.pdf>`.
- **Output:** Structured JSON to stdout (or `--out file.json`), including a
  `raw_text` fallback field per page.

Known banks (from `BankStatements/`): Bank of America, Chase, RBC, TD,
Wells Fargo, plus assorted others (`RANDOM_BANK`) handled by the generic profile.

## Architecture & Flow

```
parse.py <statement.pdf>
  1. Rasterize      pdf2image (poppler) → one PIL image per page @ 300 DPI
  2. OCR engine     PaddleOCR (PP-OCR) → (text, bbox, confidence) per page;
                    singleton reader loaded once
  3. Line/row       group words into lines by y-overlap; sort top→bottom
     grouping       (shared, bank-agnostic)
  4. Bank detect    scan text for header keywords → pick profile
                    (chase / bofa / rbc / td / wells_fargo / generic)
  5. Bank profile   profile declares column x-ranges, date format,
     parser         transaction-section markers, account-info regexes;
                    emits structured transactions + account info
  6. JSON output    stdout, or --out file.json
```

Core principle: **one shared engine** (steps 1–3 + geometry helpers) plus
**small per-bank profiles** (step 5). Each unit has one clear purpose and is
independently testable.

## Module Layout

```
hasToworkOCR/
├── parse.py                  # CLI entry point: args, orchestration, JSON output
├── requirements.txt
├── BankStatements/           # sample PDFs (already present)
├── output/                   # generated JSON (gitignored)
└── ocr/
    ├── __init__.py
    ├── rasterize.py          # PDF bytes → list[PIL.Image] (pdf2image/poppler)
    ├── engine.py             # PaddleOCR singleton; page image → list[OCRWord]
    ├── models.py             # dataclasses (below)
    ├── grouping.py           # bbox geometry: words→lines, lines→rows, column split
    ├── detect.py             # bank detection from page text → profile name
    ├── profiles/
    │   ├── __init__.py       # registry: name → profile; get_profile()
    │   ├── base.py           # BankProfile interface + GenericProfile fallback
    │   ├── chase.py
    │   ├── bofa.py
    │   ├── rbc.py
    │   ├── td.py
    │   └── wells_fargo.py
    └── serialize.py          # StatementResult → dict/JSON
```

### Profile interface (`base.py`)

```python
class BankProfile:
    name: str
    def matches(self, page_text: str) -> bool: ...          # used by detect.py
    def parse_account_info(self, lines) -> AccountInfo: ...
    def parse_transactions(self, lines) -> list[Transaction]: ...
```

`GenericProfile` in `base.py` provides default implementations and is the
fallback when no bank matches. Each bank subclass overrides only what differs.

## Data Models (`models.py`)

```python
@dataclass
class BBox:      x0: float; y0: float; x1: float; y1: float
@dataclass
class OCRWord:   text: str; bbox: BBox; confidence: float
@dataclass
class OCRLine:   text: str; words: list[OCRWord]; bbox: BBox; y_center: float

@dataclass
class Transaction:
    date: str | None          # ISO "YYYY-MM-DD" (normalized)
    description: str
    debit: float | None       # money out (positive, or None)
    credit: float | None      # money in  (positive, or None)
    balance: float | None     # running balance if printed
    raw_line: str             # original OCR text for the row (audit trail)

@dataclass
class AccountInfo:
    bank: str
    account_holder: str | None
    account_number: str | None      # masked as printed, e.g. "****1234"
    statement_period: str | None    # e.g. "2025-10-01 to 2025-10-31"
    beginning_balance: float | None
    ending_balance: float | None

@dataclass
class StatementResult:
    account_info: AccountInfo
    transactions: list[Transaction]
    raw_text: list[str]       # full OCR text per page
    meta: dict                # page_count, engine, mean_confidence, source_file, ...
```

### Design decisions

1. **Separate nullable `debit`/`credit` fields** rather than a single signed
   `amount` — cleaner for downstream math, matches how most statements print.
2. **Dates normalized to ISO `YYYY-MM-DD`.** Statements that print only `MM/DD`
   have the year inferred from the statement period.

## JSON Output Schema

```json
{
  "account_info": {
    "bank": "chase",
    "account_holder": "SALOMON ...",
    "account_number": "****1234",
    "statement_period": "2026-02-01 to 2026-02-27",
    "beginning_balance": 1234.56,
    "ending_balance": 2345.67
  },
  "transactions": [
    {"date": "2026-02-03", "description": "ZELLE PAYMENT ...",
     "debit": 250.00, "credit": null, "balance": 984.56,
     "raw_line": "02/03 ZELLE PAYMENT ... 250.00 984.56"}
  ],
  "raw_text": ["...page 1 text...", "...page 2 text..."],
  "meta": {"source_file": "Chase Salomon January.pdf",
           "page_count": 4, "engine": "paddleocr", "mean_confidence": 0.97,
           "skipped_lines": 0}
}
```

## Error Handling

- **Bad/unreadable PDF** → exit non-zero, clear stderr message; never emit
  half-valid JSON.
- **No bank matched** → `GenericProfile`, `"bank": "generic"`, still emit JSON;
  warning to stderr.
- **Low OCR confidence** → keep rows; record `mean_confidence` in `meta`.
- **Unparseable transaction row** → keep it in `raw_text`, skip as a structured
  `Transaction` (don't crash); count in `meta.skipped_lines`.
- **Balance sanity check** (optional, per profile): if running balances are
  printed, verify `prev_balance ± amount == balance`; mismatches flagged in
  `meta`, not fatal.

## Testing (TDD)

- **`grouping.py` geometry** — unit tests with synthetic `OCRWord` lists (no OCR):
  words→lines, lines→rows, column splitting. Fast, deterministic.
- **`detect.py`** — known header snippets → assert correct profile.
- **Per-profile `parse_transactions`** — hand-built line fixtures per bank layout.
- **Golden tests** — real sample PDFs end-to-end; snapshot JSON, assert against a
  reviewed per-bank baseline. Catches regressions when tuning a profile.
- PaddleOCR is mocked in unit tests (slow/non-deterministic); only golden tests
  invoke Paddle, run on demand rather than every save.

## Out of Scope

- Any math/calculations (downstream AI's job).
- Fallback OCR engines (pdfplumber/EasyOCR/Tesseract).
- PP-Structure table recognition.
- Non-PDF inputs.
- API server / UI (CLI only).

## Notes

- Working directory `hasToworkOCR` is not a git repository. Recommend
  `git init` before implementation so the spec and golden baselines are tracked.
