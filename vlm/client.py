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
    content_sha256: str = ""


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
            content_sha256=sha256_bytes(text.encode("utf-8")),
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
