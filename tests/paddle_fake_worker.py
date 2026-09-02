"""`FakeWorker` — the default suite's ONLY Paddle worker (Phase 2.1 cell P,
`docs/agent-handoffs/P21-PADDLE.md` §7).

An in-process `http.server.ThreadingHTTPServer` bound to `127.0.0.1` port 0
(the OS picks a free ephemeral port; nothing is ever exposed beyond
loopback), implementing the SAME `/health` / `/version` / `/ocr` contract as
`ocr/paddle_worker.py` — but answering from a canned result (the demo
fixture, or a caller-supplied generator) instead of running PaddleOCR. No
`paddleocr` import anywhere in this module: it is the offline stand-in used
by every non-`live` Paddle test.

Usage::

    with FakeWorker() as fake:
        client = PaddleClient(settings_pointed_at(fake.url))
        ...
        assert fake.requests[0]["page_index"] == 0

`identity` overrides let CASE 16 (a worker that echoes a mismatching
provider/execution_class) and D5's per-field mismatch tests exist without a
second server implementation. `fail_mode` lets CASE 18 exercise every
transport failure class from one object.
"""
from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from ocr.paddle_client import MAX_RESPONSE_BYTES
from ocr.paddle_worker import (
    ERROR_TOKENS,
    PADDLEOCR_VERSION_PIN,
    PADDLEPADDLE_VERSION_PIN,
    OCR_VERSION_PIN,
    PIPELINE_SWITCHES,
    TEXT_DETECTION_MODEL_PIN,
    TEXT_RECOGNITION_MODEL_PIN,
    WORKER_CONTRACT,
    PNG_MAGIC,
)

#: The default identity a `FakeWorker` echoes — exactly the pins. Tests that
#: want a mismatch pass `identity_overrides`.
DEFAULT_IDENTITY = {
    "contract": WORKER_CONTRACT,
    "provider": "vast.ai",
    "execution_class": "remote_paid",
    "gpu": {"name": "FAKE-GPU", "memory_total_mib": 32_607, "driver_version": "000.00.0"},
    "paddleocr_version": PADDLEOCR_VERSION_PIN,
    "paddlepaddle_version": PADDLEPADDLE_VERSION_PIN,
    "cuda_compiled": True,
    "ocr_version": OCR_VERSION_PIN,
    "text_detection_model_name": TEXT_DETECTION_MODEL_PIN,
    "text_recognition_model_name": TEXT_RECOGNITION_MODEL_PIN,
    "pipeline_switches": dict(PIPELINE_SWITCHES),
    "python_version": "3.12.0",
    "worker_started_at": 0.0,
    "model_loaded": True,
}

#: Fail-injection modes CASE 18 exercises. `"none"` behaves normally.
FAIL_MODES = (
    "none", "http_500", "malformed_json", "oversized_body", "hang",
    "connection_refused", "redirect",
)

#: A minimal 1x1 PNG (transparent), used when a caller does not supply a
#: `result_for` callback: enough bytes to pass the PNG-magic and PIL-decode
#: checks without any real image content.
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
TINY_PNG_BYTES = base64.b64decode(_TINY_PNG_B64)


class FakeWorker:
    """Context manager: `with FakeWorker(...) as fake: fake.url`.

    `result_for(page_index, image_bytes) -> dict` returns the raw PaddleOCR
    result dict (the worker's own `raw` field) for one request; the default
    returns an empty-but-valid result (no text_word entries) so the default
    suite never depends on OCR content. `identity_overrides` merges onto
    `DEFAULT_IDENTITY`. `token` mirrors `PADDLE_WORKER_TOKEN`. `fail_mode`
    is one of `FAIL_MODES` and applies to every `/ocr` request; `connection_refused`
    means the server never starts listening at all (`url` still resolves, so a
    client sees a real connection failure).
    """

    def __init__(self, *, result_for: Callable[[int, bytes], dict] | None = None,
                 identity_overrides: dict | None = None, token: str | None = None,
                 fail_mode: str = "none") -> None:
        if fail_mode not in FAIL_MODES:
            raise ValueError(f"unknown fail_mode {fail_mode!r}")
        self._result_for = result_for or (lambda page_index, image_bytes: _empty_result(page_index))
        self._identity = dict(DEFAULT_IDENTITY)
        if identity_overrides:
            self._identity.update(identity_overrides)
        self._token = token
        self._fail_mode = fail_mode
        self.requests: list[dict[str, Any]] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.url = ""

    def __enter__(self) -> "FakeWorker":
        if self._fail_mode == "connection_refused":
            # Bind and immediately close: the port is free again, so a
            # client's connection attempt fails the same way an unreachable
            # host would, without this object holding a listening socket.
            probe = ThreadingHTTPServer(("127.0.0.1", 0), _NullHandler)
            port = probe.server_address[1]
            probe.server_close()
            self.url = f"http://127.0.0.1:{port}"
            return self
        fake = self
        identity = self._identity
        token = self._token
        fail_mode = self._fail_mode
        result_for = self._result_for
        requests_log = self.requests

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # noqa: A003
                pass

            def _send(self, status: int, payload: dict) -> None:
                body = json.dumps(payload).encode("utf-8")
                if fail_mode == "malformed_json":
                    body = b"{not json"
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                if fail_mode == "oversized_body":
                    body = body + b" " * (MAX_RESPONSE_BYTES + 1024)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_redirect(self) -> None:
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/elsewhere")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    self._send(200, {"ok": True, "contract": WORKER_CONTRACT})
                elif self.path == "/version":
                    self._send(200, dict(identity))
                else:
                    self._send(404, {"error": "not_found"})

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/ocr":
                    self._send(405, {"error": "method_not_allowed"})
                    return
                if fail_mode == "hang":
                    time.sleep(3600)
                    return
                if fail_mode == "http_500":
                    self._send(500, {"error": "inference_failed"})
                    return
                if fail_mode == "redirect":
                    self._send_redirect()
                    return
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                payload = json.loads(body)
                if token is not None:
                    auth = self.headers.get("Authorization") or ""
                    if auth != f"Bearer {token}":
                        self._send(401, {"error": "unauthorized"})
                        return
                image_bytes = base64.b64decode(payload["image_png_b64"])
                requests_log.append({
                    "page_index": payload.get("page_index"),
                    "request_id": payload.get("request_id"),
                    "bytes": len(image_bytes),
                })
                raw = result_for(payload.get("page_index"), image_bytes)
                self._send(200, {
                    "raw": raw,
                    "image": {"width": 1, "height": 1, "sha256": hashlib.sha256(image_bytes).hexdigest()},
                    "timing": {"decode_ms": 1.0, "inference_ms": 2.0, "total_ms": 3.0, "cold_load": len(requests_log) == 1},
                    "gpu": {"memory_used_mib": 512},
                    "model": dict(identity),
                    "request_id": payload.get("request_id"),
                    "page_index": payload.get("page_index"),
                })

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = self._server.server_address[1]
        self.url = f"http://127.0.0.1:{port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return fake

    def __exit__(self, *exc_info) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)


class _NullHandler(BaseHTTPRequestHandler):
    """Used only to reserve then release a port for `fail_mode="connection_refused"`."""

    def log_message(self, fmt, *args):  # noqa: A003
        pass


def _empty_result(page_index: int) -> dict:
    return {
        "input_path": "fake.png",
        "page_index": page_index,
        "model_settings": dict(PIPELINE_SWITCHES),
        "text_type": "general",
        "return_word_box": True,
        "text_rec_score_thresh": 0.0,
        "dt_polys": [],
        "rec_polys": [],
        "rec_boxes": [],
        "rec_texts": [],
        "rec_scores": [],
        "text_word": [],
        "text_word_boxes": [],
        "textline_orientation_angles": [],
        "text_det_params": {"box_thresh": 0.6, "limit_side_len": 64, "limit_type": "min",
                             "max_side_limit": 4_000, "thresh": 0.3, "unclip_ratio": 1.5},
    }
