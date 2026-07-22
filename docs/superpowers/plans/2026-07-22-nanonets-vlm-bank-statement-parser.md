# Nanonets-OCR2 Bank Statement → Markdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI that converts a bank-statement PDF into one combined Markdown file by sending each rasterized page to a `nanonets/Nanonets-OCR2-1.5B-exp` model on an OpenAI-compatible endpoint (RunPod now, RX 7800 XT later).

**Architecture:** Rasterize PDF pages → for each page POST a base64 image + the Nanonets OCR prompt to an OpenAI-compatible `/v1/chat/completions` endpoint → collect each page's markdown → concatenate into one `.md` with page separators and a provenance comment. The laptop is only the client; the model runs on a remote/rented GPU. No JSON extraction, no math, no per-bank logic.

**Tech Stack:** Python 3.12, `openai` client library, pdf2image + Poppler, Pillow, pytest.

## Global Constraints

- **Interpreter:** Python **3.12** via the existing project venv `.venv`. Run everything as `.venv/Scripts/python.exe ...`. The system `python` is 3.14 and must not be used.
- **Poppler path:** `C:\poppler-24.08.0\Library\bin` (used by `rasterize.py`).
- **Model:** default `nanonets/Nanonets-OCR2-1.5B-exp`; configurable via `NANONETS_MODEL` env and `--model` flag.
- **Endpoint:** OpenAI-compatible, host-agnostic. Base URL / key / model from env (`NANONETS_BASE_URL`, `NANONETS_API_KEY`, `NANONETS_MODEL`). This machine never runs the model.
- **Client library:** the `openai` Python package pointed at our endpoint. No OpenAI account or cost.
- **Output:** one combined Markdown file per PDF; pages joined by `--- Page N ---`; a single non-rendering provenance comment at the top. To `--out FILE` or stdout.
- **Processing:** page by page (one image per API call).
- **No math, no JSON transaction extraction, no per-bank detection/profiles.**
- **Testing:** the network/model is never called in the default test run — the OpenAI client is mocked and `page_ocr_fn` is injected. A `live` pytest marker gates the one real-endpoint smoke test.

---

### Task 1: Configuration

**Files:** Create `ocr/config.py`; Test `tests/test_config.py`.

**Interfaces:**
- `@dataclass Settings` fields: `base_url: str`, `model: str`, `api_key: str`, `timeout: float`, `retries: int`.
- `load_settings(model_override: str | None = None) -> Settings` — env with defaults; `model_override` (from `--model`) wins over `NANONETS_MODEL`.
- Defaults: base_url `http://localhost:8000/v1`; model `nanonets/Nanonets-OCR2-1.5B-exp`; api_key `EMPTY`; timeout `120`; retries `3`.

- [ ] **Step 1: Failing test** — `tests/test_config.py`

```python
from ocr.config import load_settings, Settings

def test_defaults(monkeypatch):
    for k in ("NANONETS_BASE_URL", "NANONETS_MODEL", "NANONETS_API_KEY",
              "NANONETS_TIMEOUT", "NANONETS_RETRIES"):
        monkeypatch.delenv(k, raising=False)
    s = load_settings()
    assert isinstance(s, Settings)
    assert s.base_url == "http://localhost:8000/v1"
    assert s.model == "nanonets/Nanonets-OCR2-1.5B-exp"
    assert s.api_key == "EMPTY"
    assert s.timeout == 120.0
    assert s.retries == 3

def test_env_and_override(monkeypatch):
    monkeypatch.setenv("NANONETS_BASE_URL", "https://pod-8000.proxy.runpod.net/v1")
    monkeypatch.setenv("NANONETS_API_KEY", "tok")
    monkeypatch.setenv("NANONETS_TIMEOUT", "45")
    monkeypatch.setenv("NANONETS_RETRIES", "5")
    s = load_settings(model_override="some/other-model")
    assert s.base_url == "https://pod-8000.proxy.runpod.net/v1"
    assert s.api_key == "tok"
    assert s.timeout == 45.0
    assert s.retries == 5
    assert s.model == "some/other-model"
```

- [ ] **Step 2: Run → fail** `.venv/Scripts/python.exe -m pytest tests/test_config.py -v` (ModuleNotFoundError)
- [ ] **Step 3: Implement** — `ocr/config.py`

```python
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass
class Settings:
    base_url: str
    model: str
    api_key: str
    timeout: float
    retries: int

def load_settings(model_override: str | None = None) -> Settings:
    return Settings(
        base_url=os.environ.get("NANONETS_BASE_URL", "http://localhost:8000/v1"),
        model=model_override or os.environ.get("NANONETS_MODEL", "nanonets/Nanonets-OCR2-1.5B-exp"),
        api_key=os.environ.get("NANONETS_API_KEY", "EMPTY"),
        timeout=float(os.environ.get("NANONETS_TIMEOUT", "120")),
        retries=int(os.environ.get("NANONETS_RETRIES", "3")),
    )
```

- [ ] **Step 4: Run → pass**
- [ ] **Step 5: Commit** `feat: add env-driven Nanonets endpoint settings`

---

### Task 2: OCR client (image → page markdown)

**Files:** Create `ocr/ocr_client.py`; Test `tests/test_ocr_client.py`.

**Interfaces:**
- `build_prompt() -> str` — Nanonets OCR instruction (mentions HTML tables).
- `image_to_data_uri(image) -> str` — `data:image/png;base64,...`.
- `ocr_page(image, *, settings=None, client=None) -> str` — one page → markdown (`resp.choices[0].message.content`). `client` injectable; default built from `settings` via `OpenAI(base_url, api_key, timeout)`. Retries transient exceptions up to `settings.retries`.

- [ ] **Step 1: Failing tests** — `tests/test_ocr_client.py`

```python
from PIL import Image
from ocr.config import Settings
from ocr.ocr_client import build_prompt, image_to_data_uri, ocr_page

def _img(): return Image.new("RGB", (12, 8), (255, 255, 255))
def _settings(): return Settings(base_url="http://x/v1", model="m", api_key="EMPTY", timeout=5, retries=3)

def test_image_to_data_uri():
    uri = image_to_data_uri(_img())
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > len("data:image/png;base64,")

def test_build_prompt_mentions_html_tables():
    p = build_prompt().lower()
    assert "html" in p and "table" in p

class _M:  # generic attribute holder
    pass

class _FakeCompletions:
    def __init__(self, text, fail_times=0):
        self.text = text; self.fail_times = fail_times; self.calls = []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("transient")
        m = _M(); m.message = _M(); m.message.content = self.text
        r = _M(); r.choices = [m]
        return r

class _FakeChat:
    def __init__(self, completions): self.completions = completions

class _FakeClient:
    def __init__(self, text, fail_times=0):
        self.chat = _FakeChat(_FakeCompletions(text, fail_times))

def test_ocr_page_sends_image_and_prompt_and_returns_text():
    client = _FakeClient("# Page markdown\n<table></table>")
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == "# Page markdown\n<table></table>"
    sent = client.chat.completions.calls[0]
    assert sent["model"] == "m"
    content = sent["messages"][-1]["content"]
    kinds = {part["type"] for part in content}
    assert "image_url" in kinds and "text" in kinds
    img_part = next(p for p in content if p["type"] == "image_url")
    assert img_part["image_url"]["url"].startswith("data:image/png;base64,")

def test_ocr_page_retries_then_succeeds():
    client = _FakeClient("ok", fail_times=2)
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == "ok"
    assert len(client.chat.completions.calls) == 3
```

- [ ] **Step 2: Run → fail**
- [ ] **Step 3: Implement** — `ocr/ocr_client.py`

```python
from __future__ import annotations
import base64
import io
import time
from PIL import Image
from .config import Settings, load_settings

_PROMPT = (
    "Extract the text from the above document as if you were reading it "
    "naturally. Return tables in HTML format. Return equations in LaTeX. "
    "Wrap watermarks in <watermark></watermark> and page numbers in "
    "<page_number></page_number>. Prefer ☐ and ☑ for checkboxes. "
    "Output only the document content as clean Markdown — no commentary, "
    "no code fences around the whole answer."
)

def build_prompt() -> str:
    return _PROMPT

def image_to_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"

def _build_client(settings: Settings):
    from openai import OpenAI
    return OpenAI(base_url=settings.base_url, api_key=settings.api_key, timeout=settings.timeout)

def ocr_page(image: Image.Image, *, settings: Settings | None = None, client=None) -> str:
    settings = settings or load_settings()
    if client is None:
        client = _build_client(settings)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": build_prompt()},
            {"type": "image_url", "image_url": {"url": image_to_data_uri(image)}},
        ],
    }]
    last_exc = None
    for attempt in range(max(1, settings.retries)):
        try:
            resp = client.chat.completions.create(
                model=settings.model, messages=messages, temperature=0.0,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            last_exc = e
            time.sleep(min(2 ** attempt, 8) * 0.1)
    raise last_exc
```

- [ ] **Step 4: Run → pass**
- [ ] **Step 5: Commit** `feat: add OpenAI-compatible Nanonets OCR client`

---

### Task 3: Document holder and markdown assembly

**Files:** Create `ocr/document.py`; Test `tests/test_document.py`.

**Interfaces:** `@dataclass StatementMarkdown(source_file, model, pages: list[str])` + `.to_markdown()` → provenance comment `<!-- source: X | pages: N | model: Y | empty: E -->`, blank line, pages joined by `\n\n--- Page i ---\n\n`; empty pages render `--- Page i (empty) ---`.

- [ ] **Step 1: Failing test** — `tests/test_document.py`

```python
from ocr.document import StatementMarkdown

def test_to_markdown_provenance_and_separators():
    doc = StatementMarkdown(source_file="x.pdf", model="m", pages=["# A", "# B"])
    md = doc.to_markdown()
    assert md.startswith("<!-- source: x.pdf | pages: 2 | model: m | empty: 0 -->")
    assert "--- Page 1 ---" in md and "--- Page 2 ---" in md
    assert "# A" in md and "# B" in md

def test_to_markdown_marks_empty_pages():
    doc = StatementMarkdown(source_file="x.pdf", model="m", pages=["# A", "   "])
    md = doc.to_markdown()
    assert "empty: 1" in md
    assert "--- Page 2 (empty) ---" in md
```

- [ ] **Step 2: Run → fail**
- [ ] **Step 3: Implement** — `ocr/document.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class StatementMarkdown:
    source_file: str
    model: str
    pages: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        empty = sum(1 for p in self.pages if not p.strip())
        header = (
            f"<!-- source: {self.source_file} | pages: {len(self.pages)} "
            f"| model: {self.model} | empty: {empty} -->"
        )
        blocks = [header, ""]
        for i, page in enumerate(self.pages, start=1):
            if page.strip():
                blocks.append(f"--- Page {i} ---")
                blocks.append(page.strip())
            else:
                blocks.append(f"--- Page {i} (empty) ---")
        return "\n\n".join(blocks) + "\n"
```

- [ ] **Step 4: Run → pass**
- [ ] **Step 5: Commit** `feat: add StatementMarkdown assembly with page separators`

---

### Task 4: Pipeline orchestration

**Files:** Create `ocr/pipeline.py`; Test `tests/test_pipeline.py`.

**Interfaces:** `parse_statement(pdf_bytes, source_file="", dpi=200, model=None, page_ocr_fn=None) -> StatementMarkdown` — rasterize, run `page_ocr_fn(image)` per page (default `ocr_page` bound to `load_settings(model)`), collect markdown, return `StatementMarkdown` whose `model` is the resolved model. `page_ocr_fn` injectable.

- [ ] **Step 1: Failing test** — `tests/test_pipeline.py`

```python
from ocr.pipeline import parse_statement

def test_parse_statement_uses_injected_ocr(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=200: ["p0", "p1", "p2"])
    calls = []
    def fake_ocr(image):
        calls.append(image); return f"# md for {image}"
    doc = parse_statement(b"%PDF-fake", source_file="s.pdf", dpi=150,
                          model="nanonets/Nanonets-OCR2-1.5B-exp", page_ocr_fn=fake_ocr)
    assert doc.source_file == "s.pdf"
    assert doc.model == "nanonets/Nanonets-OCR2-1.5B-exp"
    assert doc.pages == ["# md for p0", "# md for p1", "# md for p2"]
    assert len(calls) == 3
    assert "--- Page 3 ---" in doc.to_markdown()
```

- [ ] **Step 2: Run → fail**
- [ ] **Step 3: Implement** — `ocr/pipeline.py`

```python
from __future__ import annotations
from .rasterize import rasterize_pdf
from .document import StatementMarkdown
from .config import load_settings

def parse_statement(pdf_bytes: bytes, source_file: str = "", dpi: int = 200,
                    model: str | None = None, page_ocr_fn=None) -> StatementMarkdown:
    settings = load_settings(model_override=model)
    if page_ocr_fn is None:
        from .ocr_client import ocr_page
        page_ocr_fn = lambda image: ocr_page(image, settings=settings)
    pages = rasterize_pdf(pdf_bytes, dpi=dpi)
    markdown_pages = [page_ocr_fn(image) for image in pages]
    return StatementMarkdown(source_file=source_file, model=settings.model, pages=markdown_pages)
```

- [ ] **Step 4: Run → pass**
- [ ] **Step 5: Commit** `feat: add rasterize->per-page OCR->assemble pipeline`

---

### Task 5: CLI entry point

**Files:** Create `parse.py`; Test `tests/test_cli.py`.

**Interfaces:** `main(argv=None) -> int` — `python parse.py <pdf> [--out FILE] [--dpi N] [--model NAME]`. Unreadable PDF → stderr + 2; parse/network failure → stderr + 1; success → 0; write to `--out` (utf-8) or stdout.

- [ ] **Step 1: Failing test** — `tests/test_cli.py`

```python
import types
import parse as cli

def test_main_writes_markdown(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"; pdf.write_bytes(b"%PDF-fake")
    out = tmp_path / "s.md"
    fake_doc = types.SimpleNamespace(to_markdown=lambda: "<!-- x -->\n\n--- Page 1 ---\n\n# hi\n")
    monkeypatch.setattr(cli, "parse_statement",
                        lambda pdf_bytes, source_file="", dpi=200, model=None: fake_doc)
    rc = cli.main([str(pdf), "--out", str(out), "--dpi", "150"])
    assert rc == 0
    assert out.read_text(encoding="utf-8").startswith("<!-- x -->")

def test_main_missing_pdf_returns_2(capsys):
    rc = cli.main(["does_not_exist.pdf"])
    assert rc == 2
    assert "cannot read PDF" in capsys.readouterr().err

def test_main_failure_returns_1(monkeypatch, tmp_path, capsys):
    pdf = tmp_path / "s.pdf"; pdf.write_bytes(b"%PDF-fake")
    def boom(pdf_bytes, source_file="", dpi=200, model=None):
        raise RuntimeError("endpoint down")
    monkeypatch.setattr(cli, "parse_statement", boom)
    rc = cli.main([str(pdf)])
    assert rc == 1
    assert "failed to parse statement" in capsys.readouterr().err
```

- [ ] **Step 2: Run → fail**
- [ ] **Step 3: Implement** — `parse.py`

```python
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from ocr.pipeline import parse_statement

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bank statement PDF -> Markdown via Nanonets-OCR2.")
    ap.add_argument("pdf", help="Path to the statement PDF")
    ap.add_argument("--out", help="Write Markdown here instead of stdout")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--model", default=None, help="Override the model name")
    args = ap.parse_args(argv)

    path = Path(args.pdf)
    try:
        pdf_bytes = path.read_bytes()
    except OSError as e:
        print(f"error: cannot read PDF: {e}", file=sys.stderr)
        return 2
    try:
        doc = parse_statement(pdf_bytes, source_file=path.name, dpi=args.dpi, model=args.model)
    except Exception as e:
        print(f"error: failed to parse statement: {e}", file=sys.stderr)
        return 1

    text = doc.to_markdown()
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run → pass**; then full suite `.venv/Scripts/python.exe -m pytest -q`
- [ ] **Step 5: Commit** `feat: add CLI that writes combined statement markdown`

---

### Task 6: Live smoke test, pytest config, README

**Files:** Create `tests/test_live_smoke.py`, `pytest.ini`, `README.md`; Modify `conftest.py` (register `live` marker + `first_page_image` fixture).

- [ ] **Step 1: conftest.py additions**

```python
def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits the real Nanonets endpoint (run with -m live)")

@pytest.fixture
def first_page_image(sample_pdf):
    from ocr.rasterize import rasterize_pdf
    return rasterize_pdf(sample_pdf.read_bytes(), dpi=150)[0]
```

- [ ] **Step 2: `tests/test_live_smoke.py`**

```python
import os
import pytest

pytestmark = pytest.mark.live

@pytest.mark.skipif(not os.environ.get("NANONETS_BASE_URL"),
                    reason="set NANONETS_BASE_URL to run the live smoke test")
def test_live_single_page_returns_markdown(first_page_image):
    from ocr.ocr_client import ocr_page
    md = ocr_page(first_page_image)
    assert isinstance(md, str) and md.strip()
```

- [ ] **Step 3: `pytest.ini`**

```ini
[pytest]
addopts = -m "not live"
markers =
    live: hits the real Nanonets endpoint (run with: pytest -m live)
```

- [ ] **Step 4: Run default suite → live deselected, rest pass**
- [ ] **Step 5: `README.md`** — setup (py 3.12 venv), env vars (`NANONETS_BASE_URL/_MODEL/_API_KEY`, default model `nanonets/Nanonets-OCR2-1.5B-exp`), usage (`parse.py ... --out ...`), tests (default vs `-m live`). Note the laptop is only the client; no OpenAI account/cost.
- [ ] **Step 6: Commit** `docs: add live smoke test, pytest config, and README`

---

## Self-Review Notes

- **Spec coverage:** config/env (T1), OCR client with base64 image + prompt + retries (T2), markdown assembly with provenance/separators/empty-page (T3), page-by-page pipeline with injectable OCR (T4), CLI with exits 0/1/2 (T5), live-only smoke + pytest config + README (T6). `rasterize.py` reused. ✅
- **Default model** `nanonets/Nanonets-OCR2-1.5B-exp` everywhere (config default, pipeline test, README). ✅
- **Type consistency:** `ocr_page(image, *, settings, client) -> str` (T2) == `page_ocr_fn(image) -> str` (T4); `parse_statement(...) -> StatementMarkdown` (T4) == CLI usage + `.to_markdown()` (T3, T5); `load_settings(model_override=...)` (T1) == pipeline usage (T4). ✅
