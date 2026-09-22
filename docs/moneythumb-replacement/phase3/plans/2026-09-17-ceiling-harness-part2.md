# Phase 3 Ceiling Experiment — Offline Harness Implementation Plan (part 2 of 3)

> Continues part 1 (header, Global Constraints, File Structure apply verbatim). Tasks 4–9: schema, HTTP clients, text parsing, HTML tables, row assembly, metadata rules.

---

### Task 4: Page-proposal JSON schema

**Files:**
- Create: `vlm/schema.py`
- Test: `tests/test_vlm_schema.py`

**Interfaces:**
- Produces: `SCHEMA_VERSION = 1`, `PAGE_ROLES`, `DIRECTIONS`, `SECTION_KINDS`, `PAGE_PROPOSAL_SCHEMA: dict`, `schema_sha256() -> str`, `validate_page_proposal(obj) -> list[str]` (empty list = valid), `empty_proposal(page_role="blank_or_other") -> dict`.

Design notes: the schema is what vLLM's xgrammar backend receives, so it uses only `type`, `properties`, `required`, `additionalProperties: false`, `enum`, `items`, and nullable unions as `["string", "null"]`. No `pattern`, `format`, `minimum` (date format is checked in Python by the gate). `amount` is a positive magnitude; `direction` carries the sign.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_schema.py
import copy

from vlm import schema


def _row(**overrides):
    row = {"date": "2031-01-02", "date_text": "01/02", "description": "SYNTHETIC ROW 02", "amount": 20.0,
           "direction": "credit", "balance": 530.0, "section_index": 0, "continues_previous": False,
           "box": [0.1, 0.2, 0.9, 0.22]}
    row.update(overrides)
    return row


def _proposal():
    return {
        "page_role": "statement_page",
        "account": {"bank": "SYNTHETIC BANK", "account_name": None, "account_number_last4": "0001",
                    "currency": "USD", "period_start": "2031-01-01", "period_end": "2031-01-31",
                    "beginning_balance": 500.0, "ending_balance": 860.0},
        "sections": [{"name": "TRANSACTIONS", "kind": "mixed"}],
        "rows": [_row()],
        "daily_balances": [],
        "notes": "",
    }


def test_valid_proposal_has_no_errors():
    assert schema.validate_page_proposal(_proposal()) == []


def test_additional_property_is_rejected():
    bad = _proposal()
    bad["extra"] = 1
    assert schema.validate_page_proposal(bad)


def test_bad_direction_and_missing_field_are_rejected():
    bad = _proposal()
    bad["rows"][0]["direction"] = "in"
    assert schema.validate_page_proposal(bad)
    bad2 = _proposal()
    del bad2["rows"][0]["amount"]
    assert schema.validate_page_proposal(bad2)


def test_nullables_allowed():
    ok = _proposal()
    ok["rows"][0].update({"date": None, "balance": None, "section_index": None, "box": None})
    ok["account"] = {k: None for k in ok["account"]}
    assert schema.validate_page_proposal(ok) == []


def test_schema_uses_only_grammar_safe_keywords():
    def keys(node):
        if isinstance(node, dict):
            for k, v in node.items():
                yield k
                yield from keys(v)
        elif isinstance(node, list):
            for v in node:
                yield from keys(v)
    forbidden = {"pattern", "format", "minimum", "maximum", "minLength", "maxLength", "oneOf", "allOf", "$ref"}
    assert not (set(keys(schema.PAGE_PROPOSAL_SCHEMA)) & forbidden)


def test_schema_hash_is_stable_and_empty_proposal_valid():
    assert schema.schema_sha256() == schema.schema_sha256() and len(schema.schema_sha256()) == 64
    assert schema.validate_page_proposal(schema.empty_proposal()) == []
    assert schema.empty_proposal()["page_role"] == "blank_or_other"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_schema.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.schema'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/schema.py
"""The page-proposal schema: what Stage B must emit, and what the harness validates locally.

Grammar-safe subset only (vLLM structured outputs, xgrammar backend): type, properties, required,
additionalProperties=false, enum, items, nullable unions. Source-level fields only; never a metric.
"""
from __future__ import annotations

import jsonschema

from vlm.receipts import canonical_json, sha256_bytes

SCHEMA_VERSION = 1
PAGE_ROLES = ("statement_page", "summary_page", "cheque_images", "cover_or_notice", "blank_or_other")
DIRECTIONS = ("credit", "debit", "unknown")
SECTION_KINDS = ("deposits", "withdrawals", "checks", "fees", "mixed", "daily_balances", "other")


def _nullable(kind: str) -> dict:
    return {"type": [kind, "null"]}


_ROW = {
    "type": "object",
    "additionalProperties": False,
    "required": ["date", "date_text", "description", "amount", "direction", "balance",
                 "section_index", "continues_previous", "box"],
    "properties": {
        "date": _nullable("string"),
        "date_text": {"type": "string"},
        "description": {"type": "string"},
        "amount": {"type": "number"},
        "direction": {"type": "string", "enum": list(DIRECTIONS)},
        "balance": _nullable("number"),
        "section_index": _nullable("integer"),
        "continues_previous": {"type": "boolean"},
        "box": {"type": ["array", "null"], "items": {"type": "number"}},
    },
}

_ACCOUNT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["bank", "account_name", "account_number_last4", "currency", "period_start",
                 "period_end", "beginning_balance", "ending_balance"],
    "properties": {
        "bank": _nullable("string"),
        "account_name": _nullable("string"),
        "account_number_last4": _nullable("string"),
        "currency": _nullable("string"),
        "period_start": _nullable("string"),
        "period_end": _nullable("string"),
        "beginning_balance": _nullable("number"),
        "ending_balance": _nullable("number"),
    },
}

PAGE_PROPOSAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page_role", "account", "sections", "rows", "daily_balances", "notes"],
    "properties": {
        "page_role": {"type": "string", "enum": list(PAGE_ROLES)},
        "account": _ACCOUNT,
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "kind"],
                "properties": {"name": {"type": "string"}, "kind": {"type": "string", "enum": list(SECTION_KINDS)}},
            },
        },
        "rows": {"type": "array", "items": _ROW},
        "daily_balances": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["date", "balance"],
                "properties": {"date": _nullable("string"), "balance": {"type": "number"}},
            },
        },
        "notes": {"type": "string"},
    },
}

_VALIDATOR = jsonschema.Draft202012Validator(PAGE_PROPOSAL_SCHEMA)


def schema_sha256() -> str:
    return sha256_bytes(canonical_json(PAGE_PROPOSAL_SCHEMA).encode("utf-8"))


def validate_page_proposal(obj: object) -> list[str]:
    return sorted(f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in _VALIDATOR.iter_errors(obj))


def empty_proposal(page_role: str = "blank_or_other") -> dict:
    return {
        "page_role": page_role,
        "account": {k: None for k in _ACCOUNT["required"]},
        "sections": [],
        "rows": [],
        "daily_balances": [],
        "notes": "",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_schema.py -q -p no:cacheprovider`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/schema.py tests/test_vlm_schema.py
git commit -m "vlm: page-proposal schema (grammar-safe subset)" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Bounded loopback HTTP clients (vLLM chat, Stage A worker)

**Files:**
- Create: `vlm/client.py`
- Test: `tests/test_vlm_client.py`

**Interfaces:**
- Consumes: `ocr.endpoint_policy.classify_endpoint(base_url) -> str`.
- Produces: `TransportError(RuntimeError)`, `HttpJson(base_url, *, timeout=240.0, token=None, opener=None)` with `get_json(path) -> dict`, `post_json(path, body) -> dict`; `ChatResult` dataclass; `VlmClient(HttpJson)` with `models() -> list[str]` and `chat(model, prompt, *, image_jpeg=None, schema=None, schema_name="page_proposal", max_tokens=4096, seed=0, disable_thinking=True) -> ChatResult`; `StageAWorkerClient(HttpJson)` with `health() -> dict`, `version() -> dict`, `parse_page(jpeg, *, request_id, page_index) -> dict`; `image_data_uri(jpeg) -> str`.

Design notes: `urllib` only; refuses any non-loopback base URL at construction; no redirects (`HTTPRedirectHandler.redirect_request` returns None → `HTTPError`, wrapped as `redirect_refused`); response read bounded at 16 MiB; retries (max 2) only on connection-level `URLError`, never on HTTP status; every result carries `request_sha256` (canonical body) and `response_sha256` (raw bytes) so receipts can bind them without storing customer text in public files.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_client.py
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from vlm import client as vclient


class _Fake(BaseHTTPRequestHandler):
    calls: list[dict] = []
    mode = "ok"

    def log_message(self, *args):  # silence
        pass

    def do_GET(self):
        if self.path == "/v1/models":
            body = json.dumps({"data": [{"id": "fake-model"}]}).encode()
        elif self.path == "/health":
            body = b'{"status":"ok"}'
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        _Fake.calls.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": json.loads(raw)})
        if _Fake.mode == "redirect":
            self.send_response(302); self.send_header("Location", "http://127.0.0.1:9/elsewhere"); self.end_headers(); return
        if self.path == "/v1/chat/completions":
            content = json.dumps({"page_role": "blank_or_other"}) if _Fake.mode == "ok" else "not json"
            body = json.dumps({"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                               "usage": {"prompt_tokens": 12, "completion_tokens": 3}}).encode()
        else:
            body = json.dumps({"blocks": [], "timing": {"total_ms": 1.0}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


@pytest.fixture
def server():
    _Fake.calls = []
    _Fake.mode = "ok"
    httpd = HTTPServer(("127.0.0.1", 0), _Fake)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_non_loopback_refused():
    with pytest.raises(vclient.TransportError) as exc:
        vclient.VlmClient("http://10.0.0.5:8000")
    assert "not_loopback" in str(exc.value)


def test_models_and_chat_structured(server):
    c = vclient.VlmClient(server, token="tok")
    assert c.models() == ["fake-model"]
    result = c.chat("fake-model", "Extract", image_jpeg=b"\xff\xd8\xffJPEG", schema={"type": "object"}, seed=7)
    assert result.parsed == {"page_role": "blank_or_other"} and result.finish_reason == "stop"
    assert result.prompt_tokens == 12 and result.completion_tokens == 3 and result.total_ms >= 0
    call = _Fake.calls[-1]
    assert call["auth"] == "Bearer tok"
    body = call["body"]
    assert body["temperature"] == 0 and body["seed"] == 7 and body["max_tokens"] == 4096
    assert body["response_format"] == {"type": "json_schema", "json_schema": {"name": "page_proposal", "schema": {"type": "object"}}}
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    parts = body["messages"][0]["content"]
    assert parts[0]["type"] == "image_url" and parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert parts[1] == {"type": "text", "text": "Extract"}
    assert len(result.request_sha256) == 64 and len(result.response_sha256) == 64


def test_chat_text_without_schema_or_image(server):
    c = vclient.VlmClient(server)
    result = c.chat("fake-model", "Table Recognition:", disable_thinking=False)
    assert result.parsed is None and result.text == '{"page_role": "blank_or_other"}'
    body = _Fake.calls[-1]["body"]
    assert "response_format" not in body and "chat_template_kwargs" not in body
    assert body["messages"][0]["content"] == [{"type": "text", "text": "Table Recognition:"}]


def test_unparseable_json_is_reported_not_raised(server):
    _Fake.mode = "badjson"
    result = vclient.VlmClient(server).chat("fake-model", "x", schema={"type": "object"})
    assert result.parsed is None and result.parse_error == "json_invalid"


def test_redirect_refused(server):
    _Fake.mode = "redirect"
    with pytest.raises(vclient.TransportError) as exc:
        vclient.VlmClient(server).chat("fake-model", "x")
    assert "redirect_refused" in str(exc.value) or "http_302" in str(exc.value)


def test_stage_a_worker_client(server):
    w = vclient.StageAWorkerClient(server, token="t")
    assert w.health() == {"status": "ok"}
    out = w.parse_page(b"\xff\xd8\xff", request_id="abc.p0", page_index=0)
    assert out["blocks"] == [] and _Fake.calls[-1]["body"]["contract"] == 1
    assert _Fake.calls[-1]["body"]["image_jpeg_b64"] and _Fake.calls[-1]["body"]["page_index"] == 0


def test_connection_refused_becomes_transport_error():
    c = vclient.VlmClient("http://127.0.0.1:9", timeout=1.0)
    with pytest.raises(vclient.TransportError):
        c.models()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_client.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.client'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/client.py
"""Bounded loopback HTTP clients: the vLLM OpenAI-compatible chat endpoint and the Stage A worker.

Mirrors `ocr/paddle_client.py`: loopback only, no redirects, bounded reads, retries only on
connection-level errors and only to the same URL. Results carry hashes of the request body and the
raw response so receipts can bind them without storing customer text in public files.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from ocr.endpoint_policy import classify_endpoint
from vlm.receipts import canonical_json, sha256_bytes

MAX_RESPONSE_BYTES = 16 * 1024 * 1024
DEFAULT_TIMEOUT = 240.0
MAX_TRANSPORT_RETRIES = 2
CONTRACT = 1


class TransportError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def _default_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect)


def image_data_uri(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")


class HttpJson:
    def __init__(self, base_url: str, *, timeout: float = DEFAULT_TIMEOUT, token: str | None = None,
                 opener: Callable[[], urllib.request.OpenerDirector] | None = None) -> None:
        if classify_endpoint(base_url) != "loopback":
            raise TransportError("endpoint_not_loopback")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token
        self._opener = (opener or _default_opener)()

    def _request(self, method: str, path: str, body: bytes | None) -> tuple[bytes, float]:
        url = self.base_url + path
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        attempt = 0
        while True:
            request = urllib.request.Request(url, data=body, headers=headers, method=method)
            started = time.perf_counter()
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise TransportError("response_too_large")
                    return raw, (time.perf_counter() - started) * 1000.0
            except urllib.error.HTTPError as exc:
                if 300 <= exc.code < 400:
                    raise TransportError("redirect_refused") from None
                raise TransportError(f"http_{exc.code}") from None
            except urllib.error.URLError as exc:
                attempt += 1
                if attempt > MAX_TRANSPORT_RETRIES:
                    raise TransportError(f"connection_failed:{type(exc.reason).__name__}") from None
            except (TimeoutError, OSError) as exc:
                attempt += 1
                if attempt > MAX_TRANSPORT_RETRIES:
                    raise TransportError(f"connection_failed:{type(exc).__name__}") from None

    def get_json(self, path: str) -> dict:
        raw, _ = self._request("GET", path, None)
        return _decode(raw)

    def post_json(self, path: str, body: dict) -> dict:
        raw, _ = self._request("POST", path, canonical_json(body).encode("utf-8"))
        return _decode(raw)


def _decode(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise TransportError("response_not_json") from None
    if not isinstance(value, dict):
        raise TransportError("response_not_object")
    return value


@dataclass(frozen=True)
class ChatResult:
    text: str
    parsed: dict | None
    parse_error: str | None
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    total_ms: float
    request_sha256: str
    response_sha256: str


class VlmClient(HttpJson):
    def models(self) -> list[str]:
        data = self.get_json("/v1/models").get("data") or []
        return [str(item.get("id")) for item in data if isinstance(item, dict)]

    def chat(self, model: str, prompt: str, *, image_jpeg: bytes | None = None, schema: dict | None = None,
             schema_name: str = "page_proposal", max_tokens: int = 4096, seed: int = 0,
             disable_thinking: bool = True) -> ChatResult:
        content: list[dict[str, Any]] = []
        if image_jpeg is not None:
            content.append({"type": "image_url", "image_url": {"url": image_data_uri(image_jpeg)}})
        content.append({"type": "text", "text": prompt})
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
            "seed": seed,
            "max_tokens": max_tokens,
        }
        if schema is not None:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": schema_name, "schema": schema}}
        if disable_thinking:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        encoded = canonical_json(body).encode("utf-8")
        raw, total_ms = self._request("POST", "/v1/chat/completions", encoded)
        payload = _decode(raw)
        try:
            choice = payload["choices"][0]
            text = str(choice["message"].get("content") or "")
            finish = str(choice.get("finish_reason") or "")
        except (KeyError, IndexError, TypeError):
            raise TransportError("chat_response_shape") from None
        usage = payload.get("usage") or {}
        parsed: dict | None = None
        parse_error: str | None = None
        if schema is not None:
            try:
                candidate = json.loads(text)
                if isinstance(candidate, dict):
                    parsed = candidate
                else:
                    parse_error = "json_not_object"
            except ValueError:
                parse_error = "json_invalid"
        return ChatResult(
            text=text, parsed=parsed, parse_error=parse_error, finish_reason=finish,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0), total_ms=total_ms,
            request_sha256=sha256_bytes(encoded), response_sha256=sha256_bytes(raw),
        )


class StageAWorkerClient(HttpJson):
    def health(self) -> dict:
        return self.get_json("/health")

    def version(self) -> dict:
        return self.get_json("/version")

    def parse_page(self, jpeg: bytes, *, request_id: str, page_index: int) -> dict:
        body = {"contract": CONTRACT, "request_id": request_id, "page_index": page_index,
                "image_jpeg_b64": base64.b64encode(jpeg).decode("ascii")}
        return self.post_json("/parse", body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_client.py -q -p no:cacheprovider`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/client.py tests/test_vlm_client.py
git commit -m "vlm: bounded loopback clients for vLLM chat and the Stage A worker" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Money, date and description parsing

**Files:**
- Create: `vlm/textparse.py`
- Test: `tests/test_vlm_textparse.py`

**Interfaces:**
- Produces: `parse_money(text) -> Decimal | None` (signed; parentheses, trailing `-`, `CR`/`DR`, `−`, currency symbols, thousands separators), `is_money_like(text) -> bool`, `parse_date(text, *, year_hint=None, day_first=False) -> str | None` (ISO), `is_date_like(text) -> bool`, `normalise_description(text) -> str`, `to_decimal(value) -> Decimal` (float/int/str → 2-place Decimal), `money_str(value) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_textparse.py
from decimal import Decimal

from vlm import textparse as tp


def test_parse_money_shapes():
    assert tp.parse_money("1,234.56") == Decimal("1234.56")
    assert tp.parse_money("$1,234.56") == Decimal("1234.56")
    assert tp.parse_money("(1,234.56)") == Decimal("-1234.56")
    assert tp.parse_money("1,234.56-") == Decimal("-1234.56")
    assert tp.parse_money("-12.00") == Decimal("-12.00")
    assert tp.parse_money("−12.00") == Decimal("-12.00")
    assert tp.parse_money("12.00 CR") == Decimal("12.00")
    assert tp.parse_money("12.00 DR") == Decimal("-12.00")
    assert tp.parse_money("CAD 5.00") == Decimal("5.00")
    assert tp.parse_money("500") == Decimal("500.00")
    assert tp.parse_money("") is None and tp.parse_money("abc") is None and tp.parse_money("01/02") is None
    assert tp.parse_money("1.2.3") is None


def test_is_money_like_and_date_like():
    assert tp.is_money_like("1,234.56") and tp.is_money_like("(3.00)") and not tp.is_money_like("Jan 3")
    assert tp.is_date_like("01/02/2031") and tp.is_date_like("Jan 3") and tp.is_date_like("2031-01-02")
    assert not tp.is_date_like("1,234.56") and not tp.is_date_like("SYNTHETIC")


def test_parse_date_formats():
    assert tp.parse_date("2031-01-02") == "2031-01-02"
    assert tp.parse_date("01/02/2031") == "2031-01-02"
    assert tp.parse_date("1/2/31") == "2031-01-02"
    assert tp.parse_date("01/02", year_hint=2031) == "2031-01-02"
    assert tp.parse_date("01/02") is None
    assert tp.parse_date("Jan 2, 2031") == "2031-01-02"
    assert tp.parse_date("2 Jan 2031") == "2031-01-02"
    assert tp.parse_date("Jan 2", year_hint=2031) == "2031-01-02"
    assert tp.parse_date("02/01/2031", day_first=True) == "2031-01-02"
    assert tp.parse_date("13/01/2031") == "2031-01-13"     # month 13 impossible → day-first fallback
    assert tp.parse_date("2031-02-30") is None and tp.parse_date("garbage") is None


def test_normalise_description_and_decimals():
    assert tp.normalise_description("  POS  Purchase\tSTORE #12 ") == "pos purchase store 12"
    assert tp.to_decimal(530.0) == Decimal("530.00") and tp.to_decimal("1,000") == Decimal("1000.00")
    assert tp.money_str(Decimal("-5")) == "-5.00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_textparse.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.textparse'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/textparse.py
"""Deterministic parsing of printed money, dates and descriptions. `decimal` throughout."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

_CURRENCY = re.compile(r"^(?:[A-Z]{3}\s*)?[$€£¥]?\s*")
_MONEY_CORE = re.compile(r"^\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?$|^\d+(?:\.\d{1,2})?$")
_DATE_LIKE = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?|"
    r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?(?:\s+\d{4})?)$",
    re.IGNORECASE,
)
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")


def parse_money(text: str | None) -> Decimal | None:
    if text is None:
        return None
    raw = text.strip().replace("−", "-").replace("–", "-")
    if not raw:
        return None
    negative = False
    if raw.startswith("(") and raw.endswith(")"):
        negative, raw = True, raw[1:-1].strip()
    upper = raw.upper()
    if upper.endswith(" CR") or upper.endswith("CR"):
        raw = raw[:-2].strip()
    elif upper.endswith(" DR") or upper.endswith("DR"):
        negative, raw = True, raw[:-2].strip()
    if raw.endswith("-"):
        negative, raw = True, raw[:-1].strip()
    if raw.startswith("-"):
        negative, raw = True, raw[1:].strip()
    raw = _CURRENCY.sub("", raw).strip()
    if not _MONEY_CORE.match(raw):
        return None
    try:
        value = Decimal(raw.replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return -value if negative else value


def is_money_like(text: str | None) -> bool:
    return parse_money(text) is not None


def is_date_like(text: str | None) -> bool:
    return bool(text) and _DATE_LIKE.match(text.strip()) is not None


def _iso(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _year(value: str) -> int:
    number = int(value)
    return number + 2000 if number < 100 else number


def parse_date(text: str | None, *, year_hint: int | None = None, day_first: bool = False) -> str | None:
    if not text:
        return None
    raw = text.strip().rstrip(".").replace(".", " ")
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if match:
        return _iso(int(match[1]), int(match[2]), int(match[3]))
    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", raw)
    if match:
        first, second = int(match[1]), int(match[2])
        year = _year(match[3]) if match[3] else year_hint
        if year is None:
            return None
        month, day = (second, first) if day_first else (first, second)
        result = _iso(year, month, day)
        if result is None and not day_first and first > 12:
            result = _iso(year, second, first)
        return result
    match = re.fullmatch(r"([A-Za-z]{3,9})\s+(\d{1,2}),?(?:\s+(\d{4}))?", raw)
    if match:
        month = _MONTHS.get(match[1][:3].lower())
        year = int(match[3]) if match[3] else year_hint
        return _iso(year, month, int(match[2])) if month and year else None
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})(?:,?\s+(\d{4}))?", raw)
    if match:
        month = _MONTHS.get(match[2][:3].lower())
        year = int(match[3]) if match[3] else year_hint
        return _iso(year, month, int(match[1])) if month and year else None
    return None


def normalise_description(text: str | None) -> str:
    cleaned = _PUNCT.sub(" ", (text or "").lower())
    return _WS.sub(" ", cleaned).strip()


def to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    parsed = parse_money(str(value))
    if parsed is None:
        raise ValueError("not_money")
    return parsed


def money_str(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_textparse.py -q -p no:cacheprovider`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/textparse.py tests/test_vlm_textparse.py
git commit -m "vlm: deterministic money, date and description parsing" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: HTML tables → cell grids and column roles

**Files:**
- Create: `vlm/tables.py`
- Test: `tests/test_vlm_tables.py`

**Interfaces:**
- Consumes: `vlm.textparse.is_money_like`, `is_date_like`.
- Produces: `parse_html_tables(html) -> list[list[list[str]]]` (tables → rows → cells, text only, `<br>` → space, `colspan` expands by repeating the cell), `ColumnMap` dataclass (`date, description, debit, credit, amount, balance: int | None`, `header_row: int | None`), `classify_columns(grid) -> ColumnMap`.

Column rules: (1) a header row is the first row where at least two cells match header keywords; (2) header keywords: date→{date, posted, post date, trans date, transaction date, effective}; description→{description, details, transaction, particulars, memo, activity, narrative, payee}; debit→{debit, debits, withdrawal, withdrawals, payments, money out, paid out, charges, checks/debits}; credit→{credit, credits, deposit, deposits, money in, paid in, additions, deposits/credits}; amount→{amount, transaction amount}; balance→{balance, running balance, ledger balance, ending balance, balance forward}; (3) without a header, infer: date = column with most date-like cells (≥ 50 percent of non-empty), balance = rightmost column with most money-like cells, amount = the other money-like column (one) or debit/credit (two, left→debit, right→credit when both have money cells; ties broken by position), description = the non-money non-date column with the longest average text.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_tables.py
from vlm import tables

HTML = """
<html><body><table>
<tr><th>Date</th><th>Description</th><th>Withdrawals</th><th>Deposits</th><th>Balance</th></tr>
<tr><td>01/02</td><td>SYNTHETIC<br>ROW 01</td><td></td><td>10.00</td><td>510.00</td></tr>
<tr><td>01/03</td><td>SYNTHETIC ROW 02</td><td>5.00</td><td></td><td>505.00</td></tr>
</table>
<table><tr><td colspan="2">Totals</td><td>5.00</td></tr></table>
</body></html>
"""


def test_parse_html_tables_grid():
    grids = tables.parse_html_tables(HTML)
    assert len(grids) == 2
    assert grids[0][0] == ["Date", "Description", "Withdrawals", "Deposits", "Balance"]
    assert grids[0][1] == ["01/02", "SYNTHETIC ROW 01", "", "10.00", "510.00"]
    assert grids[1][0] == ["Totals", "Totals", "5.00"]


def test_classify_columns_with_header():
    grid = tables.parse_html_tables(HTML)[0]
    cm = tables.classify_columns(grid)
    assert (cm.date, cm.description, cm.debit, cm.credit, cm.amount, cm.balance, cm.header_row) == (0, 1, 2, 3, None, 4, 0)


def test_classify_columns_without_header_single_amount():
    grid = [["2031-01-01", "SYNTHETIC ROW 01", "10.00", "510.00"],
            ["2031-01-02", "SYNTHETIC ROW 02", "20.00", "530.00"],
            ["2031-01-03", "SYNTHETIC ROW 03", "30.00", "560.00"]]
    cm = tables.classify_columns(grid)
    assert (cm.date, cm.description, cm.amount, cm.balance, cm.header_row) == (0, 1, 2, 3, None)
    assert cm.debit is None and cm.credit is None


def test_classify_columns_without_header_two_money_columns_and_balance():
    grid = [["01/02", "A", "", "10.00", "510.00"], ["01/03", "B", "5.00", "", "505.00"], ["01/04", "C", "1.00", "", "504.00"]]
    cm = tables.classify_columns(grid)
    assert (cm.date, cm.description, cm.debit, cm.credit, cm.balance) == (0, 1, 2, 3, 4)


def test_classify_columns_empty_grid():
    cm = tables.classify_columns([])
    assert cm.date is None and cm.balance is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_tables.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.tables'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/tables.py
"""HTML tables (as document parsers emit them) → text grids → column roles."""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser

from vlm.textparse import is_date_like, is_money_like

HEADER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "date": ("date", "posted", "post date", "trans date", "transaction date", "effective", "date posted"),
    "description": ("description", "details", "transaction", "particulars", "memo", "activity", "narrative", "payee", "transactions"),
    "debit": ("debit", "debits", "withdrawal", "withdrawals", "payments", "money out", "paid out", "charges", "checks/debits", "withdrawals/debits", "subtractions"),
    "credit": ("credit", "credits", "deposit", "deposits", "money in", "paid in", "additions", "deposits/credits", "deposits/additions"),
    "amount": ("amount", "transaction amount", "amt"),
    "balance": ("balance", "running balance", "ledger balance", "ending balance", "balance forward", "daily balance"),
}
ROLE_PRIORITY = ("balance", "debit", "credit", "amount", "date", "description")


@dataclass(frozen=True)
class ColumnMap:
    date: int | None
    description: int | None
    debit: int | None
    credit: int | None
    amount: int | None
    balance: int | None
    header_row: int | None


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._span = 1

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._span = 1
            for name, value in attrs:
                if name == "colspan" and value and value.isdigit():
                    self._span = max(1, int(value))
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            text = " ".join("".join(self._cell).split())
            self._row.extend([text] * self._span)
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_html_tables(html: str) -> list[list[list[str]]]:
    parser = _TableParser()
    parser.feed(html or "")
    parser.close()
    return [table for table in parser.tables if table]


def _header_role(cell: str) -> str | None:
    text = " ".join(cell.lower().replace("_", " ").split())
    if not text:
        return None
    for role in ROLE_PRIORITY:
        for keyword in HEADER_KEYWORDS[role]:
            if text == keyword or text.startswith(keyword + " ") or text.endswith(" " + keyword) or text == keyword + "s":
                return role
    return None


def _column(grid: list[list[str]], index: int) -> list[str]:
    return [row[index] for row in grid if index < len(row)]


def classify_columns(grid: list[list[str]]) -> ColumnMap:
    empty = ColumnMap(None, None, None, None, None, None, None)
    if not grid:
        return empty
    width = max(len(row) for row in grid)
    for row_index, row in enumerate(grid[:3]):
        roles = [_header_role(cell) for cell in row]
        if sum(1 for r in roles if r) >= 2:
            assigned: dict[str, int] = {}
            for col, role in enumerate(roles):
                if role and role not in assigned:
                    assigned[role] = col
            return ColumnMap(assigned.get("date"), assigned.get("description"), assigned.get("debit"),
                             assigned.get("credit"), assigned.get("amount"), assigned.get("balance"), row_index)
    stats = []
    for col in range(width):
        cells = [c for c in _column(grid, col) if c.strip()]
        dates = sum(1 for c in cells if is_date_like(c))
        money = sum(1 for c in cells if is_money_like(c) and not is_date_like(c))
        avg_len = (sum(len(c) for c in cells) / len(cells)) if cells else 0.0
        stats.append((col, len(cells), dates, money, avg_len))
    date_col = max((s for s in stats if s[1] and s[2] * 2 >= s[1]), key=lambda s: (s[2], -s[0]), default=None)
    money_cols = [s[0] for s in stats if s[1] and s[3] * 2 >= s[1] and (date_col is None or s[0] != date_col[0])]
    balance = money_cols[-1] if money_cols else None
    others = [c for c in money_cols if c != balance]
    amount = debit = credit = None
    if len(others) == 1:
        amount = others[0]
    elif len(others) >= 2:
        debit, credit = others[-2], others[-1]
    used = {c for c in (balance, amount, debit, credit, date_col[0] if date_col else None) if c is not None}
    text_cols = [s for s in stats if s[0] not in used and s[1]]
    description = max(text_cols, key=lambda s: (s[4], -s[0]))[0] if text_cols else None
    return ColumnMap(date_col[0] if date_col else None, description, debit, credit, amount, balance, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_tables.py -q -p no:cacheprovider`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/tables.py tests/test_vlm_tables.py
git commit -m "vlm: HTML table grids and column-role classification" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Row assembly from Stage A blocks

**Files:**
- Create: `vlm/assemble.py`
- Test: `tests/test_vlm_assemble.py`

**Interfaces:**
- Consumes: `vlm.tables.parse_html_tables`, `classify_columns`; `vlm.textparse`.
- Produces: `CandidateRow` (see part 1), `Block` dataclass (`label: str, bbox: tuple[float, float, float, float], content: str, order: int, page: int`), `blocks_from_worker(raw: dict, *, page: int, width: int, height: int) -> list[Block]` (normalises pixel boxes to 0..1, tolerates missing fields), `rows_from_grid(grid, colmap, *, page, table_index, year_hint=None, day_first=False) -> list[CandidateRow]`, `rows_from_blocks(blocks, *, year_hint=None, day_first=False) -> list[CandidateRow]`, `text_lines_from_blocks(blocks) -> list[str]`.

Row rules: skip the header row; a row with no money in amount/debit/credit/balance columns is a continuation → appended to the previous row's description (if any); a blank date inherits the previous row's date (date_text records the printed text, possibly empty); debit column money → direction `debit`, credit column → `credit` (`direction_source="column"`); a single `amount` column: negative or parenthesised → debit, else `unknown` (`direction_source="printed"` when a sign was printed, else the gate may resolve by chain); rows whose description matches `^(total|totals|subtotal|ending balance|beginning balance|balance forward)` are skipped.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_assemble.py
from decimal import Decimal

from vlm import assemble
from vlm.tables import classify_columns

WORKER_RAW = {
    "blocks": [
        {"label": "text", "bbox": [10, 10, 500, 40], "content": "SYNTHETIC BANK  Statement Period 01/01/2031 - 01/31/2031", "order": 0},
        {"label": "table", "bbox": [10, 50, 700, 300], "order": 1, "content": (
            "<table><tr><th>Date</th><th>Description</th><th>Amount</th><th>Balance</th></tr>"
            "<tr><td>01/01</td><td>SYNTHETIC ROW 01</td><td>10.00</td><td>510.00</td></tr>"
            "<tr><td></td><td>continued text</td><td></td><td></td></tr>"
            "<tr><td>01/02</td><td>SYNTHETIC ROW 02</td><td>-5.00</td><td>505.00</td></tr>"
            "<tr><td>01/03</td><td>Total</td><td>5.00</td><td></td></tr></table>")},
    ],
}


def test_blocks_from_worker_normalises_boxes():
    blocks = assemble.blocks_from_worker(WORKER_RAW, page=0, width=1000, height=2000)
    assert [b.label for b in blocks] == ["text", "table"]
    assert blocks[0].bbox == (0.01, 0.005, 0.5, 0.02) and blocks[0].page == 0


def test_rows_from_blocks_with_continuation_and_totals():
    blocks = assemble.blocks_from_worker(WORKER_RAW, page=0, width=1000, height=2000)
    rows = assemble.rows_from_blocks(blocks, year_hint=2031)
    assert len(rows) == 2
    first, second = rows
    assert first.date == "2031-01-01" and first.description == "SYNTHETIC ROW 01 continued text"
    assert first.amount == Decimal("10.00") and first.direction == "unknown" and first.balance == Decimal("510.00")
    assert second.amount == Decimal("5.00") and second.direction == "debit" and second.direction_source == "printed"
    assert first.locator == "t0r1" and first.source == "stage_a" and first.page == 0


def test_rows_from_grid_debit_credit_columns_and_date_carry():
    grid = [["Date", "Description", "Debits", "Credits", "Balance"],
            ["01/02", "A", "", "10.00", "510.00"],
            ["", "B", "5.00", "", "505.00"]]
    rows = assemble.rows_from_grid(grid, classify_columns(grid), page=1, table_index=3, year_hint=2031)
    assert [(r.date, r.direction, r.direction_source, r.amount) for r in rows] == [
        ("2031-01-02", "credit", "column", Decimal("10.00")), ("2031-01-02", "debit", "column", Decimal("5.00"))]
    assert rows[1].date_text == "" and rows[1].locator == "t3r2"


def test_text_lines_from_blocks():
    blocks = assemble.blocks_from_worker(WORKER_RAW, page=0, width=1000, height=2000)
    lines = assemble.text_lines_from_blocks(blocks)
    assert lines and lines[0].startswith("SYNTHETIC BANK")


def test_unmappable_table_yields_no_rows():
    blocks = [assemble.Block("table", (0, 0, 1, 1), "<table><tr><td>a</td><td>b</td></tr></table>", 0, 0)]
    assert assemble.rows_from_blocks(blocks) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_assemble.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.assemble'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/assemble.py
"""Stage A parser output → candidate transaction rows (deterministic, provenance kept)."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal

from vlm.tables import ColumnMap, classify_columns, parse_html_tables
from vlm.textparse import parse_date, parse_money

SKIP_DESCRIPTION = re.compile(r"^(total|totals|subtotal|sub-total|ending balance|beginning balance|balance forward|closing balance|opening balance)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CandidateRow:
    date: str | None
    date_text: str
    description: str
    amount: Decimal
    direction: str
    balance: Decimal | None
    page: int
    source: str
    locator: str
    direction_source: str = "printed"


@dataclass(frozen=True)
class Block:
    label: str
    bbox: tuple[float, float, float, float]
    content: str
    order: int
    page: int


def blocks_from_worker(raw: dict, *, page: int, width: int, height: int) -> list[Block]:
    blocks: list[Block] = []
    for order, item in enumerate(raw.get("blocks") or []):
        if not isinstance(item, dict):
            continue
        box = item.get("bbox") or [0, 0, 0, 0]
        try:
            x0, y0, x1, y1 = (float(v) for v in box[:4])
        except (TypeError, ValueError):
            x0 = y0 = x1 = y1 = 0.0
        norm = (round(x0 / width, 6), round(y0 / height, 6), round(x1 / width, 6), round(y1 / height, 6)) if width and height else (0.0, 0.0, 0.0, 0.0)
        blocks.append(Block(label=str(item.get("label") or "text"), bbox=norm, content=str(item.get("content") or ""),
                            order=int(item.get("order", order)), page=page))
    return sorted(blocks, key=lambda b: b.order)


def _cell(row: list[str], index: int | None) -> str:
    return row[index].strip() if index is not None and index < len(row) else ""


def rows_from_grid(grid: list[list[str]], colmap: ColumnMap, *, page: int, table_index: int,
                   year_hint: int | None = None, day_first: bool = False) -> list[CandidateRow]:
    if colmap.balance is None and colmap.amount is None and colmap.debit is None and colmap.credit is None:
        return []
    rows: list[CandidateRow] = []
    last_date: str | None = None
    for row_index, row in enumerate(grid):
        if colmap.header_row is not None and row_index == colmap.header_row:
            continue
        description = _cell(row, colmap.description)
        debit = parse_money(_cell(row, colmap.debit))
        credit = parse_money(_cell(row, colmap.credit))
        amount = parse_money(_cell(row, colmap.amount))
        balance = parse_money(_cell(row, colmap.balance))
        if debit is None and credit is None and amount is None:
            if rows and description and balance is None:
                rows[-1] = replace(rows[-1], description=(rows[-1].description + " " + description).strip())
            continue
        if SKIP_DESCRIPTION.match(description):
            continue
        date_text = _cell(row, colmap.date)
        date = parse_date(date_text, year_hint=year_hint, day_first=day_first) if date_text else None
        if date is None and not date_text:
            date = last_date
        else:
            last_date = date or last_date
        if debit is not None:
            magnitude, direction, source = abs(debit), "debit", "column"
        elif credit is not None:
            magnitude, direction, source = abs(credit), "credit", "column"
        else:
            magnitude = abs(amount)
            direction = "debit" if amount < 0 else "unknown"
            source = "printed"
        rows.append(CandidateRow(date=date, date_text=date_text, description=description, amount=magnitude,
                                 direction=direction, balance=balance, page=page, source="stage_a",
                                 locator=f"t{table_index}r{row_index}", direction_source=source))
    return rows


def rows_from_blocks(blocks: list[Block], *, year_hint: int | None = None, day_first: bool = False) -> list[CandidateRow]:
    rows: list[CandidateRow] = []
    table_index = 0
    for block in blocks:
        if block.label != "table":
            continue
        for grid in parse_html_tables(block.content):
            rows.extend(rows_from_grid(grid, classify_columns(grid), page=block.page, table_index=table_index,
                                       year_hint=year_hint, day_first=day_first))
            table_index += 1
    return rows


def text_lines_from_blocks(blocks: list[Block]) -> list[str]:
    lines: list[str] = []
    for block in blocks:
        if block.label == "table":
            for grid in parse_html_tables(block.content):
                lines.extend(" ".join(c for c in row if c) for row in grid)
        else:
            lines.extend(line.strip() for line in block.content.splitlines() if line.strip())
    return lines
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_assemble.py -q -p no:cacheprovider`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/assemble.py tests/test_vlm_assemble.py
git commit -m "vlm: candidate rows from parser tables" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Rule-based account metadata

**Files:**
- Create: `vlm/metadata.py`
- Test: `tests/test_vlm_metadata.py`

**Interfaces:**
- Consumes: `vlm.textparse.parse_money`, `parse_date`.
- Produces: `AccountMeta` (see part 1), `extract_meta(lines: list[str], *, year_hint=None) -> AccountMeta`, `merge_meta(first: AccountMeta, second: AccountMeta) -> AccountMeta` (first non-null wins), `year_from_meta(meta) -> int | None`.

Rules: beginning balance keys `beginning balance|opening balance|previous balance|balance forward|starting balance|balance brought forward|previous statement balance`; ending keys `ending balance|closing balance|new balance|balance at end|current balance|statement balance|ending ledger balance|closing ledger balance`; the value is the LAST money token on the same line (or the next line if the line has none); period from `(statement period|period|from)?\s*<date>\s*(to|-|–|through)\s*<date>` where dates match the parse_date formats; currency from tokens `USD|CAD|EUR|GBP` or symbols `$`→null (ambiguous), `€`→EUR, `£`→GBP; account last4 from `(account|acct)\.?\s*(number|no\.?|#)?\s*[:#]?\s*[\dXx*\-\s]*(\d{4})`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_metadata.py
from decimal import Decimal

from vlm import metadata as md

LINES = [
    "SYNTHETIC BANK",
    "Account Number: XXXX-XXXX-0001",
    "Statement Period 01/01/2031 - 01/31/2031",
    "Beginning Balance 500.00",
    "Deposits and Credits 360.00",
    "Ending Balance",
    "860.00",
    "All amounts in CAD",
]


def test_extract_meta_rules():
    meta = md.extract_meta(LINES)
    assert meta.beginning_balance == Decimal("500.00") and meta.ending_balance == Decimal("860.00")
    assert (meta.period_start, meta.period_end) == ("2031-01-01", "2031-01-31")
    assert meta.currency == "CAD" and meta.account_last4 == "0001"
    assert "beginning:rule" in meta.sources and "ending:rule" in meta.sources and "period:rule" in meta.sources


def test_extract_meta_missing_fields_are_none():
    meta = md.extract_meta(["nothing here"])
    assert meta.beginning_balance is None and meta.period_start is None and meta.currency is None
    assert meta.sources == ()


def test_merge_meta_first_non_null_wins():
    a = md.extract_meta(["Ending Balance 10.00"])
    b = md.extract_meta(["Beginning Balance 5.00", "Ending Balance 99.00"])
    merged = md.merge_meta(a, b)
    assert merged.ending_balance == Decimal("10.00") and merged.beginning_balance == Decimal("5.00")


def test_year_from_meta():
    assert md.year_from_meta(md.extract_meta(LINES)) == 2031
    assert md.year_from_meta(md.extract_meta([])) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_metadata.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.metadata'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/metadata.py
"""Rule-based statement metadata from printed text lines (Stage A arm); merged with Stage B."""
from __future__ import annotations

import re
from dataclasses import dataclass, fields
from decimal import Decimal

from vlm.textparse import parse_date, parse_money

BEGIN_RE = re.compile(r"\b(beginning balance|opening balance|previous balance|balance forward|starting balance|balance brought forward|previous statement balance)\b", re.I)
END_RE = re.compile(r"\b(ending balance|closing balance|new balance|balance at end|current balance|statement balance|ending ledger balance|closing ledger balance)\b", re.I)
MONEY_TOKEN = re.compile(r"\(?-?[$€£]?\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})\)?-?|\(?-?[$€£]?\s?\d+\.\d{2}\)?-?")
DATE_TOKEN = r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|[A-Za-z]{3,9}\.? \d{1,2},? \d{4}|\d{1,2} [A-Za-z]{3,9},? \d{4})"
PERIOD_RE = re.compile(rf"({DATE_TOKEN})\s*(?:to|-|–|—|through|thru)\s*({DATE_TOKEN})", re.I)
CURRENCY_RE = re.compile(r"\b(USD|CAD|EUR|GBP|AUD|NZD|MXN)\b")
LAST4_RE = re.compile(r"\b(?:account|acct)\.?\s*(?:number|no\.?|#)?\s*[:#]?\s*[\dXx*\-\s]*?(\d{4})\b", re.I)


@dataclass(frozen=True)
class AccountMeta:
    beginning_balance: Decimal | None
    ending_balance: Decimal | None
    period_start: str | None
    period_end: str | None
    currency: str | None
    account_last4: str | None
    bank: str | None
    sources: tuple[str, ...]


EMPTY_META = AccountMeta(None, None, None, None, None, None, None, ())


def _money_after(lines: list[str], index: int) -> Decimal | None:
    for candidate in (lines[index], lines[index + 1] if index + 1 < len(lines) else ""):
        tokens = MONEY_TOKEN.findall(candidate)
        for token in reversed(tokens):
            value = parse_money(token.strip())
            if value is not None:
                return value
    return None


def extract_meta(lines: list[str], *, year_hint: int | None = None) -> AccountMeta:
    beginning = ending = None
    start = end = currency = last4 = None
    sources: list[str] = []
    for index, line in enumerate(lines):
        if beginning is None and BEGIN_RE.search(line):
            beginning = _money_after(lines, index)
            if beginning is not None:
                sources.append("beginning:rule")
        if ending is None and END_RE.search(line):
            ending = _money_after(lines, index)
            if ending is not None:
                sources.append("ending:rule")
        if start is None:
            match = PERIOD_RE.search(line)
            if match:
                first, second = parse_date(match[1], year_hint=year_hint), parse_date(match[2], year_hint=year_hint)
                if first and second:
                    start, end = first, second
                    sources.append("period:rule")
        if currency is None:
            match = CURRENCY_RE.search(line)
            if match:
                currency = match[1].upper()
                sources.append("currency:rule")
            elif "€" in line:
                currency, _ = "EUR", sources.append("currency:symbol")
            elif "£" in line:
                currency, _ = "GBP", sources.append("currency:symbol")
        if last4 is None:
            match = LAST4_RE.search(line)
            if match:
                last4 = match[1]
                sources.append("last4:rule")
    return AccountMeta(beginning, ending, start, end, currency, last4, None, tuple(sources))


def merge_meta(first: AccountMeta, second: AccountMeta) -> AccountMeta:
    values = {}
    for field in fields(AccountMeta):
        if field.name == "sources":
            continue
        a, b = getattr(first, field.name), getattr(second, field.name)
        values[field.name] = a if a is not None else b
    return AccountMeta(sources=tuple(dict.fromkeys(first.sources + second.sources)), **values)


def year_from_meta(meta: AccountMeta) -> int | None:
    for value in (meta.period_end, meta.period_start):
        if value:
            return int(value[:4])
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_metadata.py -q -p no:cacheprovider`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/metadata.py tests/test_vlm_metadata.py
git commit -m "vlm: rule-based account metadata" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

Continue with part 3 (`2026-09-17-ceiling-harness-part3.md`): gate, reader truth and matching, prompts and proposals, runner, report, CLI.
