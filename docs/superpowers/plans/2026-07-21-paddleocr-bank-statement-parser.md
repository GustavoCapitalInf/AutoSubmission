# PaddleOCR Bank Statement Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone CLI that extracts an entire bank-statement PDF into structured JSON using PaddleOCR, ready for a downstream AI to do math on.

**Architecture:** Rasterize PDF pages → PaddleOCR (PP-OCR) words+bboxes → group words into lines/rows → detect the bank → apply a per-bank profile (with a generic fallback) to emit structured account info + transactions → serialize to JSON. One shared engine plus small per-bank profile classes.

**Tech Stack:** Python 3.12, PaddleOCR 3.x (`paddlepaddle` 3.x), pdf2image + Poppler, Pillow, pytest.

## Global Constraints

- **Interpreter:** Python **3.12** only (PaddlePaddle has no 3.14 wheels). All commands use the project venv `.venv` created from `py -3.12`.
- **OCR engine:** PaddleOCR **only**. No pdfplumber/EasyOCR/Tesseract fallback.
- **Poppler path:** `C:\poppler-24.08.0\Library\bin` (already on machine). Pass via `poppler_path` on Windows; on non-Windows pass `None`.
- **Extraction approach:** plain PP-OCR text+bboxes with custom row/column reconstruction. No PP-Structure.
- **Output:** structured JSON to stdout, or to a file via `--out`. Includes per-page `raw_text`.
- **Dates:** normalized to ISO `YYYY-MM-DD`; year inferred from statement period when only `MM/DD` printed.
- **Money:** `debit`/`credit` are separate positive-or-`None` floats (not one signed amount).
- **No math:** the parser never computes balances/averages — that is the downstream AI's job.
- **Testing:** PaddleOCR is mocked in unit tests; only golden tests invoke real Paddle and are run on demand.

---

### Task 1: Project scaffold, venv, dependencies, git

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `ocr/__init__.py` (empty)
- Create: `ocr/profiles/__init__.py` (empty for now)
- Create: `tests/__init__.py` (empty)
- Create: `conftest.py`

**Interfaces:**
- Produces: a working `.venv` with PaddleOCR importable; `SAMPLES_DIR` pytest fixture returning the `BankStatements/` path.

- [ ] **Step 1: Initialize git**

```bash
cd "C:/Users/GustavoPrietodePaula/OneDrive - Capital Infusion/Desktop/Capital Infusion Projects/hasToworkOCR"
git init
```

- [ ] **Step 2: Create the venv from Python 3.12**

```bash
py -3.12 -m venv .venv
```

- [ ] **Step 3: Write `requirements.txt`**

```
paddleocr==3.7.0
paddlepaddle==3.3.1
pdf2image==1.17.0
pillow
pytest
```

- [ ] **Step 4: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
output/
.pytest_cache/
# Do NOT ignore BankStatements/ — samples are needed for golden tests
```

- [ ] **Step 5: Install dependencies (slow — downloads Paddle)**

Run:
```bash
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements.txt
```
Expected: ends with `Successfully installed ... paddleocr-3.7.0 paddlepaddle-3.3.1 ...`

- [ ] **Step 6: Write `conftest.py` (shared fixtures)**

```python
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent

@pytest.fixture
def samples_dir() -> Path:
    return PROJECT_ROOT / "BankStatements"

@pytest.fixture
def sample_pdf(samples_dir) -> Path:
    # A known, small digital PDF used across engine/rasterize tests.
    p = samples_dir / "CHASE_BANK" / "Chase Salomon January.pdf"
    assert p.exists(), f"missing sample: {p}"
    return p
```

- [ ] **Step 7: Create empty package files**

Create `ocr/__init__.py`, `ocr/profiles/__init__.py`, `tests/__init__.py` as empty files.

- [ ] **Step 8: Smoke-test the environment**

Run:
```bash
.venv/Scripts/python.exe -c "from paddleocr import PaddleOCR; print('paddleocr import ok')"
```
Expected: prints `paddleocr import ok` (may also print model-download logs on first run).

- [ ] **Step 9: Commit**

```bash
git add requirements.txt .gitignore conftest.py ocr/__init__.py ocr/profiles/__init__.py tests/__init__.py docs/
git commit -m "chore: scaffold PaddleOCR bank statement parser (venv, deps, git)"
```

---

### Task 2: Data models

**Files:**
- Create: `ocr/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `BBox(x0: float, y0: float, x1: float, y1: float)` with props `width`, `height`, `y_center`.
  - `OCRWord(text: str, bbox: BBox, confidence: float = 1.0)`.
  - `OCRLine(text: str, words: list[OCRWord], bbox: BBox, y_center: float)`.
  - `Transaction(date: str | None, description: str, debit: float | None, credit: float | None, balance: float | None, raw_line: str)`.
  - `AccountInfo(bank: str, account_holder: str | None = None, account_number: str | None = None, statement_period: str | None = None, beginning_balance: float | None = None, ending_balance: float | None = None)`.
  - `StatementResult(account_info: AccountInfo, transactions: list[Transaction], raw_text: list[str], meta: dict)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from ocr.models import BBox, OCRWord, OCRLine, Transaction, AccountInfo, StatementResult

def test_bbox_geometry():
    b = BBox(10, 20, 30, 60)
    assert b.width == 20
    assert b.height == 40
    assert b.y_center == 40

def test_transaction_defaults():
    t = Transaction(date="2026-01-03", description="ACME", debit=10.0,
                    credit=None, balance=90.0, raw_line="01/03 ACME 10.00 90.00")
    assert t.credit is None
    assert t.debit == 10.0

def test_statement_result_holds_parts():
    r = StatementResult(
        account_info=AccountInfo(bank="chase"),
        transactions=[],
        raw_text=["page one"],
        meta={"page_count": 1},
    )
    assert r.account_info.bank == "chase"
    assert r.raw_text == ["page one"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ocr.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# ocr/models.py
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2.0

@dataclass
class OCRWord:
    text: str
    bbox: BBox
    confidence: float = 1.0

@dataclass
class OCRLine:
    text: str
    words: list[OCRWord] = field(default_factory=list)
    bbox: BBox | None = None
    y_center: float = 0.0

@dataclass
class Transaction:
    date: str | None
    description: str
    debit: float | None
    credit: float | None
    balance: float | None
    raw_line: str

@dataclass
class AccountInfo:
    bank: str
    account_holder: str | None = None
    account_number: str | None = None
    statement_period: str | None = None
    beginning_balance: float | None = None
    ending_balance: float | None = None

@dataclass
class StatementResult:
    account_info: AccountInfo
    transactions: list[Transaction] = field(default_factory=list)
    raw_text: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add ocr/models.py tests/test_models.py
git commit -m "feat: add OCR and statement data models"
```

---

### Task 3: PDF rasterization

**Files:**
- Create: `ocr/rasterize.py`
- Test: `tests/test_rasterize.py`

**Interfaces:**
- Consumes: Poppler at the Global-Constraints path.
- Produces: `rasterize_pdf(pdf_bytes: bytes, dpi: int = 300) -> list[PIL.Image.Image]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rasterize.py
from PIL import Image
from ocr.rasterize import rasterize_pdf

def test_rasterize_returns_images(sample_pdf):
    pages = rasterize_pdf(sample_pdf.read_bytes(), dpi=150)
    assert len(pages) >= 1
    assert all(isinstance(p, Image.Image) for p in pages)
    assert pages[0].width > 0 and pages[0].height > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rasterize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ocr.rasterize'`

- [ ] **Step 3: Write minimal implementation**

```python
# ocr/rasterize.py
from __future__ import annotations
import os
import sys
from PIL import Image
from pdf2image import convert_from_bytes

POPPLER_PATH = (
    None if sys.platform != "win32"
    else os.environ.get("POPPLER_PATH", r"C:\poppler-24.08.0\Library\bin")
)

def rasterize_pdf(pdf_bytes: bytes, dpi: int = 300) -> list[Image.Image]:
    """Rasterize every page of a PDF to a PIL image at the given DPI."""
    return convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rasterize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ocr/rasterize.py tests/test_rasterize.py
git commit -m "feat: add PDF rasterization via pdf2image"
```

---

### Task 4: PaddleOCR engine wrapper

**Files:**
- Create: `ocr/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `BBox`, `OCRWord` from `ocr.models`; `PIL.Image`.
- Produces:
  - `get_reader() -> PaddleOCR` (module-level singleton, lang="en").
  - `words_from_paddle_result(result_dict: dict) -> list[OCRWord]` — pure adapter from one page's PaddleOCR 3.x result dict to `OCRWord`s. Reads keys `rec_texts` (list[str]), `rec_scores` (list[float]), `rec_polys` (list of 4-point polygons, each point `[x, y]`).
  - `ocr_image(image: PIL.Image.Image) -> list[OCRWord]` — runs Paddle on one page image.

**Note on the 3.x API:** `PaddleOCR().predict(numpy_or_path)` returns a list of result objects; `result[0].json["res"]` (or `result[0]` mapping) carries `rec_texts`, `rec_scores`, `rec_polys`. The pure adapter is unit-tested with a synthetic dict so the exact call site is the only thing that touches real Paddle.

- [ ] **Step 1: Write the failing test (pure adapter, no Paddle)**

```python
# tests/test_engine.py
from ocr.engine import words_from_paddle_result
from ocr.models import OCRWord

def test_words_from_paddle_result_maps_polys_to_bboxes():
    result = {
        "rec_texts": ["Hello", "World"],
        "rec_scores": [0.99, 0.88],
        "rec_polys": [
            [[10, 20], [50, 20], [50, 40], [10, 40]],   # x0,y0,x1,y1 = 10,20,50,40
            [[60, 22], [90, 22], [90, 38], [60, 38]],
        ],
    }
    words = words_from_paddle_result(result)
    assert [w.text for w in words] == ["Hello", "World"]
    assert isinstance(words[0], OCRWord)
    assert (words[0].bbox.x0, words[0].bbox.y0, words[0].bbox.x1, words[0].bbox.y1) == (10, 20, 50, 40)
    assert words[0].confidence == 0.99

def test_words_from_paddle_result_handles_empty():
    assert words_from_paddle_result({"rec_texts": [], "rec_scores": [], "rec_polys": []}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ocr.engine'`

- [ ] **Step 3: Write minimal implementation**

```python
# ocr/engine.py
from __future__ import annotations
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
from .models import BBox, OCRWord

_reader: PaddleOCR | None = None

def get_reader() -> PaddleOCR:
    global _reader
    if _reader is None:
        _reader = PaddleOCR(use_textline_orientation=True, lang="en")
    return _reader

def words_from_paddle_result(result_dict: dict) -> list[OCRWord]:
    """Adapt one page's PaddleOCR 3.x result dict into OCRWords."""
    texts = result_dict.get("rec_texts", []) or []
    scores = result_dict.get("rec_scores", []) or []
    polys = result_dict.get("rec_polys", []) or []
    words: list[OCRWord] = []
    for i, text in enumerate(texts):
        poly = polys[i]
        xs = [pt[0] for pt in poly]
        ys = [pt[1] for pt in poly]
        bbox = BBox(min(xs), min(ys), max(xs), max(ys))
        conf = float(scores[i]) if i < len(scores) else 1.0
        words.append(OCRWord(text=str(text), bbox=bbox, confidence=conf))
    return words

def _extract_res(predict_output) -> dict:
    """Normalize PaddleOCR.predict() output for one page into a plain dict."""
    item = predict_output[0]
    data = getattr(item, "json", None)
    if isinstance(data, dict):
        return data.get("res", data)
    # Mapping-style result object
    return item["res"] if "res" in item else dict(item)

def ocr_image(image: Image.Image) -> list[OCRWord]:
    reader = get_reader()
    arr = np.array(image.convert("RGB"))
    output = reader.predict(arr)
    return words_from_paddle_result(_extract_res(output))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_engine.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Verify the real API shape with a spike (manual, one-off)**

Run:
```bash
.venv/Scripts/python.exe -c "from ocr.rasterize import rasterize_pdf; from ocr.engine import ocr_image; from pathlib import Path; pages = rasterize_pdf(Path('BankStatements/CHASE_BANK/Chase Salomon January.pdf').read_bytes(), dpi=200); w = ocr_image(pages[0]); print(len(w), 'words'); [print(x.text, x.bbox.__dict__) for x in w[:8]]"
```
Expected: prints a nonzero word count and several `(text, bbox)` rows. If `_extract_res` raises a `KeyError`/`AttributeError`, print `output[0]` structure and adjust `_extract_res` to match the installed 3.x result shape, then re-run Step 4 tests.

- [ ] **Step 6: Commit**

```bash
git add ocr/engine.py tests/test_engine.py
git commit -m "feat: add PaddleOCR engine wrapper and result adapter"
```

---

### Task 5: Word/line/row grouping geometry

**Files:**
- Create: `ocr/grouping.py`
- Test: `tests/test_grouping.py`

**Interfaces:**
- Consumes: `OCRWord`, `OCRLine`, `BBox`.
- Produces:
  - `group_words_into_lines(words: list[OCRWord], y_tol: float = 6.0) -> list[OCRLine]` — words whose vertical centers are within `y_tol` join one line; each line's words sorted left→right; lines sorted top→bottom; `OCRLine.text` is words joined by single spaces; `OCRLine.bbox` spans all words; `y_center` is the mean word center.
  - `words_in_x_range(line: OCRLine, x0: float, x1: float) -> list[OCRWord]` — words whose bbox center-x falls in `[x0, x1)`.
  - `text_in_x_range(line: OCRLine, x0: float, x1: float) -> str` — those words' text joined by spaces.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_grouping.py
from ocr.models import OCRWord, BBox
from ocr.grouping import group_words_into_lines, words_in_x_range, text_in_x_range

def _w(text, x0, y0, x1, y1):
    return OCRWord(text=text, bbox=BBox(x0, y0, x1, y1), confidence=1.0)

def test_group_words_into_lines_orders_and_joins():
    words = [
        _w("World", 60, 21, 90, 39),
        _w("Hello", 10, 20, 50, 40),      # same row as World
        _w("Next", 10, 80, 50, 100),      # lower row
    ]
    lines = group_words_into_lines(words, y_tol=6)
    assert len(lines) == 2
    assert lines[0].text == "Hello World"   # sorted left→right, top row first
    assert lines[1].text == "Next"

def test_words_in_x_range_uses_center():
    line = group_words_into_lines([
        _w("DATE", 0, 0, 40, 10),
        _w("DESC", 100, 0, 200, 10),
        _w("9.99", 300, 0, 340, 10),
    ])[0]
    assert text_in_x_range(line, 90, 250) == "DESC"
    assert text_in_x_range(line, 280, 400) == "9.99"
    assert [w.text for w in words_in_x_range(line, 0, 90)] == ["DATE"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_grouping.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ocr.grouping'`

- [ ] **Step 3: Write minimal implementation**

```python
# ocr/grouping.py
from __future__ import annotations
from .models import OCRWord, OCRLine, BBox

def group_words_into_lines(words: list[OCRWord], y_tol: float = 6.0) -> list[OCRLine]:
    remaining = sorted(words, key=lambda w: w.bbox.y_center)
    lines: list[OCRLine] = []
    for w in remaining:
        placed = False
        for ln in lines:
            if abs(w.bbox.y_center - ln.y_center) <= y_tol:
                ln.words.append(w)
                ln.y_center = sum(x.bbox.y_center for x in ln.words) / len(ln.words)
                placed = True
                break
        if not placed:
            lines.append(OCRLine(text="", words=[w], bbox=None, y_center=w.bbox.y_center))
    for ln in lines:
        ln.words.sort(key=lambda w: w.bbox.x0)
        ln.text = " ".join(w.text for w in ln.words)
        ln.bbox = BBox(
            min(w.bbox.x0 for w in ln.words),
            min(w.bbox.y0 for w in ln.words),
            max(w.bbox.x1 for w in ln.words),
            max(w.bbox.y1 for w in ln.words),
        )
    lines.sort(key=lambda l: l.y_center)
    return lines

def words_in_x_range(line: OCRLine, x0: float, x1: float) -> list[OCRWord]:
    out = []
    for w in line.words:
        cx = (w.bbox.x0 + w.bbox.x1) / 2.0
        if x0 <= cx < x1:
            out.append(w)
    return out

def text_in_x_range(line: OCRLine, x0: float, x1: float) -> str:
    return " ".join(w.text for w in words_in_x_range(line, x0, x1))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_grouping.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add ocr/grouping.py tests/test_grouping.py
git commit -m "feat: add word/line/row grouping geometry"
```

---

### Task 6: Shared parsing helpers + BankProfile base + GenericProfile

**Files:**
- Create: `ocr/parse_helpers.py`
- Create: `ocr/profiles/base.py`
- Test: `tests/test_parse_helpers.py`
- Test: `tests/test_generic_profile.py`

**Interfaces:**
- Produces in `ocr/parse_helpers.py`:
  - `parse_money(token: str) -> float | None` — `"$1,234.56"`→`1234.56`, `"(45.00)"`→`45.0`, `"1,000.00-"`→`1000.0`, junk→`None`. Always returns a positive magnitude (sign handling is the caller's job).
  - `find_amounts(text: str) -> list[str]` — regex `find` of money-like tokens in reading order.
  - `normalize_date(raw: str, year_hint: int | None) -> str | None` — accepts `MM/DD`, `MM/DD/YY`, `MM/DD/YYYY`, `Mon DD`, `DD Mon YYYY`; returns ISO `YYYY-MM-DD`; uses `year_hint` when the year is absent; junk→`None`.
- Produces in `ocr/profiles/base.py`:
  - `class BankProfile` with attributes/methods:
    - `name: str = "generic"`
    - `header_keywords: list[str] = []`
    - `matches(self, page_text: str) -> bool` (default: any keyword case-insensitively present)
    - `parse_account_info(self, lines: list[OCRLine]) -> AccountInfo`
    - `parse_transactions(self, lines: list[OCRLine], year_hint: int | None) -> list[Transaction]`
  - `class GenericProfile(BankProfile)` — concrete fallback. `parse_transactions` keeps any line that starts with a date token and contains ≥1 money token: the trailing money token becomes `balance` if ≥2 amounts are present, the preceding amount becomes `debit` or `credit` based on `is_credit_line`/`is_debit_line` keyword tests (reuse keyword lists inline), else defaults to `debit`. Description is the text between the date and the first amount.

- [ ] **Step 1: Write failing tests for helpers**

```python
# tests/test_parse_helpers.py
from ocr.parse_helpers import parse_money, find_amounts, normalize_date

def test_parse_money_variants():
    assert parse_money("$1,234.56") == 1234.56
    assert parse_money("(45.00)") == 45.0
    assert parse_money("1,000.00-") == 1000.0
    assert parse_money("hello") is None

def test_find_amounts_reading_order():
    assert find_amounts("02/03 ACME 250.00 984.56") == ["250.00", "984.56"]

def test_normalize_date_infers_year():
    assert normalize_date("02/03", 2026) == "2026-02-03"
    assert normalize_date("02/03/2025", None) == "2025-02-03"
    assert normalize_date("garbage", 2026) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_parse_helpers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ocr.parse_helpers'`

- [ ] **Step 3: Implement `ocr/parse_helpers.py`**

```python
# ocr/parse_helpers.py
from __future__ import annotations
import re
from datetime import datetime

_MONEY_RE = re.compile(r"\(?\$?\s?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?-?\)?")
_MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], start=1)}

def parse_money(token: str) -> float | None:
    if token is None:
        return None
    t = token.strip()
    if not re.search(r"\d", t):
        return None
    cleaned = t.replace("$", "").replace(",", "").replace(" ", "")
    cleaned = cleaned.replace("(", "").replace(")", "").rstrip("-").lstrip("-")
    if not cleaned:
        return None
    try:
        return abs(float(cleaned))
    except ValueError:
        return None

def find_amounts(text: str) -> list[str]:
    out = []
    for m in _MONEY_RE.finditer(text or ""):
        tok = m.group().strip()
        if re.search(r"\d\.\d{2}", tok) or re.search(r"\d,\d{3}", tok):
            out.append(tok)
    return out

def normalize_date(raw: str, year_hint: int | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    # Numeric MM/DD[/YY[YY]]
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?$", s)
    if m:
        mo, da, yr = int(m.group(1)), int(m.group(2)), m.group(3)
        if yr is None:
            if year_hint is None:
                return None
            year = year_hint
        else:
            year = int(yr)
            if year < 100:
                year += 2000
        try:
            return datetime(year, mo, da).strftime("%Y-%m-%d")
        except ValueError:
            return None
    # "Mon DD" or "DD Mon YYYY"
    m = re.match(r"^([A-Za-z]{3,})\.?\s+(\d{1,2})(?:,?\s+(\d{4}))?$", s)
    if m and m.group(1)[:3].lower() in _MONTHS:
        mo = _MONTHS[m.group(1)[:3].lower()]
        da = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else year_hint
        if year is None:
            return None
        try:
            return datetime(year, mo, da).strftime("%Y-%m-%d")
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]{3,})\.?\s+(\d{4})$", s)
    if m and m.group(2)[:3].lower() in _MONTHS:
        try:
            return datetime(int(m.group(3)), _MONTHS[m.group(2)[:3].lower()], int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None
```

- [ ] **Step 4: Run to verify helpers pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_parse_helpers.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Write failing test for GenericProfile**

```python
# tests/test_generic_profile.py
from ocr.models import OCRWord, BBox
from ocr.grouping import group_words_into_lines
from ocr.profiles.base import GenericProfile

def _line(text, y):
    # Build a line whose words carry increasing x so ordering is stable.
    words = []
    x = 0
    for tok in text.split():
        words.append(OCRWord(tok, BBox(x, y, x + 10 * len(tok), y + 10), 1.0))
        x += 10 * len(tok) + 10
    return words

def test_generic_parses_dated_money_line():
    words = _line("02/03 ZELLE PAYMENT DEPOSIT 250.00 984.56", 10)
    lines = group_words_into_lines(words)
    txns = GenericProfile().parse_transactions(lines, year_hint=2026)
    assert len(txns) == 1
    t = txns[0]
    assert t.date == "2026-02-03"
    assert t.balance == 984.56
    assert t.credit == 250.00        # "deposit" → credit
    assert t.debit is None

def test_generic_skips_non_transaction_line():
    words = _line("Beginning balance on statement", 10)
    lines = group_words_into_lines(words)
    assert GenericProfile().parse_transactions(lines, year_hint=2026) == []
```

- [ ] **Step 6: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_generic_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ocr.profiles.base'`

- [ ] **Step 7: Implement `ocr/profiles/base.py`**

```python
# ocr/profiles/base.py
from __future__ import annotations
import re
from ..models import OCRLine, Transaction, AccountInfo
from ..parse_helpers import parse_money, find_amounts, normalize_date

_CREDIT_WORDS = ("deposit", "credit", "ach credit", "transfer in", "stripe",
                 "interest", "refund", "zelle deposit")
_DEBIT_WORDS = ("debit", "withdrawal", "purchase", "pos", "atm", "check",
                "payment", "fee", "charge", "transfer out", "ach debit")

_DATE_TOKEN_RE = re.compile(r"^(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|[A-Za-z]{3,}\.?\s+\d{1,2})")

def is_credit_line(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in _CREDIT_WORDS)

def is_debit_line(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in _DEBIT_WORDS)

class BankProfile:
    name: str = "generic"
    header_keywords: list[str] = []

    def matches(self, page_text: str) -> bool:
        t = page_text.lower()
        return any(k.lower() in t for k in self.header_keywords)

    def parse_account_info(self, lines: list[OCRLine]) -> AccountInfo:
        return AccountInfo(bank=self.name)

    def parse_transactions(self, lines: list[OCRLine], year_hint: int | None) -> list[Transaction]:
        raise NotImplementedError

class GenericProfile(BankProfile):
    name = "generic"

    def parse_transactions(self, lines, year_hint):
        txns: list[Transaction] = []
        for ln in lines:
            text = ln.text.strip()
            m = _DATE_TOKEN_RE.match(text)
            if not m:
                continue
            date = normalize_date(m.group(0), year_hint)
            if date is None:
                continue
            amounts = find_amounts(text[m.end():])
            if not amounts:
                continue
            balance = parse_money(amounts[-1]) if len(amounts) >= 2 else None
            amount_tok = amounts[-2] if len(amounts) >= 2 else amounts[-1]
            amount = parse_money(amount_tok)
            first_amt_pos = text.find(amounts[0], m.end())
            description = text[m.end():first_amt_pos].strip() if first_amt_pos > 0 else ""
            debit = credit = None
            if is_credit_line(text) and not is_debit_line(text):
                credit = amount
            else:
                debit = amount
            txns.append(Transaction(date=date, description=description,
                                    debit=debit, credit=credit, balance=balance,
                                    raw_line=text))
        return txns
```

- [ ] **Step 8: Run to verify GenericProfile passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_generic_profile.py -v`
Expected: PASS (2 passed)

- [ ] **Step 9: Commit**

```bash
git add ocr/parse_helpers.py ocr/profiles/base.py tests/test_parse_helpers.py tests/test_generic_profile.py
git commit -m "feat: add parsing helpers, BankProfile base, and generic fallback profile"
```

---

### Task 7: Bank detection + profile registry

**Files:**
- Modify: `ocr/profiles/__init__.py`
- Create: `ocr/detect.py`
- Test: `tests/test_detect.py`

**Interfaces:**
- Consumes: `GenericProfile` and (later) each bank profile class.
- Produces:
  - `ocr/profiles/__init__.py`: `ALL_PROFILES: list[BankProfile]` (bank profiles first, generic last) and `get_profile(name: str) -> BankProfile`.
  - `ocr/detect.py`: `detect_profile(full_text: str) -> BankProfile` — first profile whose `matches()` is true, else `GenericProfile()`.

**Note:** At this task only `GenericProfile` exists; the registry starts with just generic. Per-bank tasks (9–13) append their class to `ALL_PROFILES`. The detection test here uses a temporary dummy profile so it does not depend on later tasks.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_detect.py
from ocr.detect import detect_profile
from ocr.profiles.base import BankProfile, GenericProfile

def test_detect_falls_back_to_generic():
    prof = detect_profile("some unrecognizable statement text")
    assert isinstance(prof, GenericProfile)

def test_detect_matches_keyword(monkeypatch):
    class DummyBank(BankProfile):
        name = "dummy"
        header_keywords = ["dummybank n.a."]
        def parse_transactions(self, lines, year_hint):
            return []
    import ocr.detect as detect_mod
    monkeypatch.setattr(detect_mod, "ALL_PROFILES", [DummyBank(), GenericProfile()])
    prof = detect_profile("Welcome to DummyBank N.A. your statement")
    assert prof.name == "dummy"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_detect.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ocr.detect'`

- [ ] **Step 3: Implement the registry**

```python
# ocr/profiles/__init__.py
from .base import BankProfile, GenericProfile

# Bank profiles are appended here as they are implemented (Tasks 9–13).
ALL_PROFILES: list[BankProfile] = [
    GenericProfile(),
]

def get_profile(name: str) -> BankProfile:
    for p in ALL_PROFILES:
        if p.name == name:
            return p
    return GenericProfile()
```

- [ ] **Step 4: Implement `ocr/detect.py`**

```python
# ocr/detect.py
from __future__ import annotations
from .profiles import ALL_PROFILES
from .profiles.base import BankProfile, GenericProfile

def detect_profile(full_text: str) -> BankProfile:
    for profile in ALL_PROFILES:
        if isinstance(profile, GenericProfile):
            continue
        if profile.matches(full_text):
            return profile
    return GenericProfile()
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_detect.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add ocr/detect.py ocr/profiles/__init__.py tests/test_detect.py
git commit -m "feat: add bank detection and profile registry"
```

---

### Task 8: Serialization + CLI orchestration

**Files:**
- Create: `ocr/serialize.py`
- Create: `ocr/pipeline.py`
- Create: `parse.py`
- Test: `tests/test_serialize.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `ocr/serialize.py`: `result_to_dict(result: StatementResult) -> dict`; `result_to_json(result: StatementResult, indent: int = 2) -> str`.
  - `ocr/pipeline.py`: `parse_statement(pdf_bytes: bytes, source_file: str = "", dpi: int = 300, page_words_fn=None) -> StatementResult`. `page_words_fn(image) -> list[OCRWord]` defaults to `ocr.engine.ocr_image` and is injectable so tests avoid real Paddle. Also `infer_year_hint(full_text: str) -> int | None` extracting a 4-digit year (2019–2035) from statement text.
  - `parse.py`: CLI — `python parse.py <pdf> [--out FILE] [--dpi N]`; prints JSON to stdout or writes `--out`; exits non-zero with a stderr message on unreadable PDF.

- [ ] **Step 1: Write failing serialize test**

```python
# tests/test_serialize.py
import json
from ocr.models import StatementResult, AccountInfo, Transaction
from ocr.serialize import result_to_dict, result_to_json

def _result():
    return StatementResult(
        account_info=AccountInfo(bank="chase", ending_balance=100.0),
        transactions=[Transaction("2026-02-03", "ACME", 10.0, None, 90.0, "02/03 ACME 10.00 90.00")],
        raw_text=["page 1"],
        meta={"page_count": 1},
    )

def test_result_to_dict_shape():
    d = result_to_dict(_result())
    assert d["account_info"]["bank"] == "chase"
    assert d["transactions"][0]["debit"] == 10.0
    assert d["transactions"][0]["credit"] is None
    assert d["raw_text"] == ["page 1"]
    assert d["meta"]["page_count"] == 1

def test_result_to_json_roundtrips():
    parsed = json.loads(result_to_json(_result()))
    assert parsed["transactions"][0]["date"] == "2026-02-03"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_serialize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ocr.serialize'`

- [ ] **Step 3: Implement `ocr/serialize.py`**

```python
# ocr/serialize.py
from __future__ import annotations
import json
from dataclasses import asdict
from .models import StatementResult

def result_to_dict(result: StatementResult) -> dict:
    return {
        "account_info": asdict(result.account_info),
        "transactions": [asdict(t) for t in result.transactions],
        "raw_text": list(result.raw_text),
        "meta": dict(result.meta),
    }

def result_to_json(result: StatementResult, indent: int = 2) -> str:
    return json.dumps(result_to_dict(result), indent=indent, ensure_ascii=False)
```

- [ ] **Step 4: Run to verify serialize passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_serialize.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Write failing pipeline test (Paddle injected, no real OCR)**

```python
# tests/test_pipeline.py
from ocr.models import OCRWord, BBox
from ocr.pipeline import parse_statement, infer_year_hint

def test_infer_year_hint():
    assert infer_year_hint("Statement period 02/01/2026 - 02/27/2026") == 2026
    assert infer_year_hint("no year here") is None

def test_parse_statement_uses_injected_ocr(monkeypatch):
    # Fake OCR: one page with a single dated deposit line.
    def fake_words(image):
        x = 0
        words = []
        for tok in "02/03 ACH CREDIT DEPOSIT 250.00 984.56".split():
            words.append(OCRWord(tok, BBox(x, 10, x + 10, 20), 1.0))
            x += 20
        return words
    # Rasterize returns one dummy "page" object; fake_words ignores it.
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: [object()])
    result = parse_statement(b"%PDF-fake", source_file="x.pdf", page_words_fn=fake_words)
    assert result.meta["page_count"] == 1
    assert len(result.transactions) == 1
    assert result.transactions[0].credit == 250.00
    assert result.transactions[0].balance == 984.56
```

- [ ] **Step 6: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ocr.pipeline'`

- [ ] **Step 7: Implement `ocr/pipeline.py`**

```python
# ocr/pipeline.py
from __future__ import annotations
import re
from statistics import mean
from .models import StatementResult
from .rasterize import rasterize_pdf
from .grouping import group_words_into_lines
from .detect import detect_profile

def infer_year_hint(full_text: str) -> int | None:
    years = [int(y) for y in re.findall(r"\b(20[1-3]\d)\b", full_text or "")]
    years = [y for y in years if 2019 <= y <= 2035]
    return max(set(years), key=years.count) if years else None

def parse_statement(pdf_bytes: bytes, source_file: str = "", dpi: int = 300,
                    page_words_fn=None) -> StatementResult:
    if page_words_fn is None:
        from .engine import ocr_image as page_words_fn  # lazy: avoids importing Paddle in tests
    pages = rasterize_pdf(pdf_bytes, dpi=dpi)
    raw_text: list[str] = []
    all_lines = []
    confidences: list[float] = []
    for image in pages:
        words = page_words_fn(image)
        confidences.extend(w.confidence for w in words)
        lines = group_words_into_lines(words)
        all_lines.append(lines)
        raw_text.append("\n".join(ln.text for ln in lines))

    full_text = "\n".join(raw_text)
    profile = detect_profile(full_text)
    year_hint = infer_year_hint(full_text)

    account_info = profile.parse_account_info([ln for pg in all_lines for ln in pg])
    account_info.bank = profile.name
    transactions = []
    for lines in all_lines:
        transactions.extend(profile.parse_transactions(lines, year_hint))

    meta = {
        "source_file": source_file,
        "page_count": len(pages),
        "engine": "paddleocr",
        "mean_confidence": round(mean(confidences), 4) if confidences else 0.0,
        "profile": profile.name,
        "skipped_lines": 0,
    }
    return StatementResult(account_info=account_info, transactions=transactions,
                           raw_text=raw_text, meta=meta)
```

- [ ] **Step 8: Run to verify pipeline passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: PASS (2 passed)

- [ ] **Step 9: Implement `parse.py` CLI**

```python
# parse.py
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from ocr.pipeline import parse_statement
from ocr.serialize import result_to_json

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Extract a bank statement PDF to JSON.")
    ap.add_argument("pdf", help="Path to the statement PDF")
    ap.add_argument("--out", help="Write JSON here instead of stdout")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args(argv)

    path = Path(args.pdf)
    try:
        pdf_bytes = path.read_bytes()
    except OSError as e:
        print(f"error: cannot read PDF: {e}", file=sys.stderr)
        return 2
    try:
        result = parse_statement(pdf_bytes, source_file=path.name, dpi=args.dpi)
    except Exception as e:  # unreadable/corrupt PDF or OCR failure
        print(f"error: failed to parse statement: {e}", file=sys.stderr)
        return 1

    text = result_to_json(result)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 10: Manual end-to-end smoke on a real PDF**

Run:
```bash
.venv/Scripts/python.exe parse.py "BankStatements/CHASE_BANK/Chase Salomon January.pdf" --out output/chase_jan.json --dpi 200
```
Expected: exit 0; `output/chase_jan.json` contains `account_info`, a non-empty `transactions` array, `raw_text`, and `meta`. Inspect it; some transactions may be imperfect — bank-specific accuracy is Tasks 9–13.

- [ ] **Step 11: Commit**

```bash
git add ocr/serialize.py ocr/pipeline.py parse.py tests/test_serialize.py tests/test_pipeline.py
git commit -m "feat: add serialization, pipeline orchestration, and CLI"
```

---

### Tasks 9–13: Per-bank profiles (Chase, BofA, RBC, TD, Wells Fargo)

Each bank profile is one task following the **same recipe**. They are independent of one another; only their sample folder and class name differ. Do them one at a time, each ending in a committed, golden-tested profile.

| Task | name | class file | sample folder | one sample for golden |
|------|------|-----------|---------------|-----------------------|
| 9  | `chase`       | `ocr/profiles/chase.py`       | `CHASE_BANK`         | `Chase Salomon January.pdf` |
| 10 | `bofa`        | `ocr/profiles/bofa.py`        | `BANK__OF_AMERICA_BANK` | `BofA Statement.pdf` |
| 11 | `rbc`         | `ocr/profiles/rbc.py`         | `RBC_BANK`           | `Chequing Statement-JAN+.pdf` |
| 12 | `td`          | `ocr/profiles/td.py`          | `TD_BANK`            | `TD BANK NARROW JAN.pdf` |
| 13 | `wells_fargo` | `ocr/profiles/wells_fargo.py` | `WELLS_FARGO_BANK`   | `113025 WellsFargo.pdf` |

**Recipe (repeat per task, substituting the row above):**

- [ ] **Step 1: Capture the real OCR layout (spike).** Run the pipeline on the golden sample and dump grouped lines with x-coordinates so you can read the column geometry:

```bash
.venv/Scripts/python.exe -c "import json; from pathlib import Path; from ocr.rasterize import rasterize_pdf; from ocr.engine import ocr_image; from ocr.grouping import group_words_into_lines; pages=rasterize_pdf(Path('BankStatements/<FOLDER>/<SAMPLE>').read_bytes(), dpi=200); [print(f'--- p{i} ---') or [print(round(ln.bbox.x0),round(ln.y_center),repr(ln.text)) for ln in group_words_into_lines(ocr_image(pg))] for i,pg in enumerate(pages)]" > /tmp/<name>_layout.txt
```
Read `/tmp/<name>_layout.txt`. Note: (a) header keyword(s) unique to this bank for `matches()`; (b) the x-position where the amount/balance columns begin; (c) the date format; (d) the line(s) that mark the start and end of the transaction table; (e) how debits vs credits are distinguished (separate columns vs. a deposits/withdrawals section vs. sign).

- [ ] **Step 2: Write a golden test from a hand-checked expectation.** Open the sample PDF yourself, pick **3 real transactions** (ideally one debit, one credit, and one with a balance) plus the ending balance, and assert them:

```python
# tests/test_<name>_golden.py  (example shape — fill with THIS bank's real values)
import pytest
from pathlib import Path
from ocr.pipeline import parse_statement

pytestmark = pytest.mark.golden  # deselected by default; runs real Paddle

def _parse():
    p = Path("BankStatements/<FOLDER>/<SAMPLE>")
    return parse_statement(p.read_bytes(), source_file=p.name, dpi=200)

def test_<name>_detects_bank():
    assert _parse().account_info.bank == "<name>"

def test_<name>_known_transactions():
    txns = _parse().transactions
    # Replace with real values read from the PDF:
    dates = {t.date for t in txns}
    assert "2026-01-05" in dates
    # find a specific credit / debit / balance and assert exact amounts
    ...
```

Register the `golden` marker in `conftest.py` (add once, first bank task):

```python
# add to conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "golden: end-to-end tests that run real PaddleOCR")
```

- [ ] **Step 3: Run the golden test to verify it fails** (profile not written yet, so bank detects as `generic` and/or values are wrong):

Run: `.venv/Scripts/python.exe -m pytest tests/test_<name>_golden.py -v -m golden`
Expected: FAIL.

- [ ] **Step 4: Write the profile class.** Subclass `BankProfile`; set `header_keywords` from Step 1; implement `parse_transactions` using `text_in_x_range` (for separate debit/credit columns) or the generic dated-line logic (for single-column layouts), and `parse_account_info` with regexes for holder / account number (masked) / period / beginning+ending balance. Example skeleton:

```python
# ocr/profiles/<name>.py
from __future__ import annotations
import re
from ..models import Transaction, AccountInfo, OCRLine
from ..parse_helpers import parse_money, normalize_date, find_amounts
from ..grouping import text_in_x_range
from .base import BankProfile

class <Name>Profile(BankProfile):
    name = "<name>"
    header_keywords = [ ... ]           # from Step 1(a)

    # Column x-boundaries observed in Step 1(b); tune to the real dump.
    DESC_X = (..., ...)
    DEBIT_X = (..., ...)
    CREDIT_X = (..., ...)
    BALANCE_X = (..., ...)

    def parse_account_info(self, lines: list[OCRLine]) -> AccountInfo:
        text = "\n".join(ln.text for ln in lines)
        info = AccountInfo(bank=self.name)
        m = re.search(r"...", text)     # account number → mask
        # ...period, beginning/ending balance...
        return info

    def parse_transactions(self, lines, year_hint):
        txns = []
        in_table = False
        for ln in lines:
            # toggle in_table on the start/end markers from Step 1(d)
            # if in_table and line starts with a date:
            #   date = normalize_date(<date col text>, year_hint)
            #   debit = parse_money(text_in_x_range(ln, *self.DEBIT_X))
            #   credit = parse_money(text_in_x_range(ln, *self.CREDIT_X))
            #   balance = parse_money(text_in_x_range(ln, *self.BALANCE_X))
            #   description = text_in_x_range(ln, *self.DESC_X)
            #   append Transaction(...)
            ...
        return txns
```

- [ ] **Step 5: Register the profile.** Add to `ocr/profiles/__init__.py`, **before** `GenericProfile()`:

```python
from .<name> import <Name>Profile
ALL_PROFILES: list[BankProfile] = [
    <Name>Profile(),   # ...and any previously added banks
    GenericProfile(),
]
```

- [ ] **Step 6: Run the golden test to verify it passes.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_<name>_golden.py -v -m golden`
Expected: PASS. Iterate on the x-ranges/regexes until the 3 hand-checked transactions and detection pass.

- [ ] **Step 7: Run the full non-golden suite** to confirm no regressions in shared code:

Run: `.venv/Scripts/python.exe -m pytest -m "not golden" -v`
Expected: all PASS.

- [ ] **Step 8: Commit.**

```bash
git add ocr/profiles/<name>.py ocr/profiles/__init__.py tests/test_<name>_golden.py conftest.py
git commit -m "feat: add <Name> bank statement profile"
```

---

### Task 14: Default pytest config + README

**Files:**
- Create: `pytest.ini`
- Create: `README.md`

**Interfaces:** none (docs/config only).

- [ ] **Step 1: Write `pytest.ini` so golden tests are opt-in**

```ini
[pytest]
addopts = -m "not golden"
markers =
    golden: end-to-end tests that run real PaddleOCR (run with: pytest -m golden)
```

- [ ] **Step 2: Verify default run skips golden and passes**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: unit tests run and PASS; golden tests deselected.

- [ ] **Step 3: Write `README.md`**

````markdown
# Bank Statement Parser (PaddleOCR)

Extracts a bank-statement PDF into structured JSON for downstream AI math.

## Setup (Python 3.12 required — PaddlePaddle has no 3.14 wheels)

```bash
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Poppler must be installed (Windows: `C:\poppler-24.08.0\Library\bin`).

## Usage

```bash
.venv/Scripts/python.exe parse.py path/to/statement.pdf --out output/result.json
```

Output JSON: `account_info`, `transactions[]` (date, description, debit, credit,
balance, raw_line), per-page `raw_text`, and `meta`.

## Tests

```bash
.venv/Scripts/python.exe -m pytest            # fast unit tests
.venv/Scripts/python.exe -m pytest -m golden  # real-OCR golden tests (slow)
```

## Supported banks

Chase, Bank of America, RBC, TD, Wells Fargo. Unknown banks fall back to a
generic profile.
````

- [ ] **Step 4: Commit**

```bash
git add pytest.ini README.md
git commit -m "docs: add README and pytest config"
```

---

## Self-Review Notes

- **Spec coverage:** rasterize (T3), PaddleOCR-only engine (T4), row/column grouping (T5), bank detection + per-bank profiles + generic fallback (T6–T13), JSON schema incl. raw_text/meta (T2/T8), CLI (T8), error handling — unreadable PDF non-zero exit (T8 parse.py), generic fallback (T6/T7), mean_confidence + skipped_lines in meta (T8), testing incl. mocked Paddle unit tests and on-demand golden tests (throughout). ✅
- **Balance sanity check** from the spec is marked optional; not a dedicated task. If desired later, it slots into each profile's `parse_transactions` and writes flags into `meta` — noted here so it is not forgotten.
- **Type consistency:** `parse_transactions(lines, year_hint)` signature is uniform across base/generic/bank profiles and matches the pipeline call site; `page_words_fn(image) -> list[OCRWord]` matches `ocr_image`.
