"""Stage A worker: a loopback-only HTTP service around the PaddleOCR-VL pipeline (layout + VL via vLLM).

Deployed to the rented host; run inside the Paddle virtualenv when the parser is needed, or any Python
with numpy and Pillow for the identity echo alone (the pipeline is built lazily). Mirrors `ocr/paddle_worker.py`:
127.0.0.1 bind only, bearer token, bounded JSON body, bounded image decode, closed error tokens,
retention none (the page exists only in memory). `paddleocr` is imported inside `main()` only.
"""
from __future__ import annotations

import argparse
import base64
import hmac
import io
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from PIL import Image

CONTRACT = 1
LOOPBACK_BIND = "127.0.0.1"
DEFAULT_PORT = 18003
MAX_BODY_BYTES = 32 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
MAX_IMAGE_SIDE_PX = 6_000
PIPELINE_VERSION = "v1.6"
SERVED_MODEL_NAME = "PaddleOCR-VL-1.6-0.9B"
RETENTION_POLICY = "none"
PREDICT_KWARGS = dict(use_doc_orientation_classify=False, use_doc_unwarping=False, use_layout_detection=True,
                      use_chart_recognition=False, use_seal_recognition=False, use_ocr_for_image_block=False,
                      format_block_content=False, merge_layout_blocks=True)


class WorkerRefused(Exception):
    def __init__(self, code: str, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def resolve_token(environ: dict | None = None) -> str | None:
    source = os.environ if environ is None else environ
    token = source.get("VLM_A_WORKER_TOKEN", "").strip()
    return token or None


def check_bearer_token(token: str | None, auth_header: str | None) -> None:
    if token is None:
        return
    expected = f"Bearer {token}"
    if not isinstance(auth_header, str) or not hmac.compare_digest(auth_header.encode("utf-8"), expected.encode("utf-8")):
        raise WorkerRefused("unauthorized", 401)


def parse_bounded_json(raw: bytes) -> dict:
    if len(raw) > MAX_BODY_BYTES:
        raise WorkerRefused("body_too_large", 413)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise WorkerRefused("json_invalid") from None
    if not isinstance(value, dict):
        raise WorkerRefused("json_not_object")
    return value


def decode_jpeg_bounded(image_b64: str) -> np.ndarray:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except (ValueError, TypeError):
        raise WorkerRefused("image_b64_invalid") from None
    try:
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            if width > MAX_IMAGE_SIDE_PX or height > MAX_IMAGE_SIDE_PX or width * height > MAX_IMAGE_PIXELS:
                raise WorkerRefused("image_too_large", 413)
            rgb = np.asarray(image.convert("RGB"))
    except WorkerRefused:
        raise
    except Exception:  # noqa: BLE001 — any decoder failure is one token
        raise WorkerRefused("image_invalid") from None
    return np.ascontiguousarray(rgb[:, :, ::-1])  # BGR, as the pipeline expects


def blocks_from_result(result: dict) -> list[dict]:
    inner = result.get("res") if isinstance(result.get("res"), dict) else result
    blocks: list[dict] = []
    for item in inner.get("parsing_res_list") or []:
        if not isinstance(item, dict):
            continue
        order = item.get("block_order")
        blocks.append({"label": str(item.get("block_label") or "text"),
                       "bbox": [float(v) for v in (item.get("block_bbox") or [0, 0, 0, 0])[:4]],
                       "content": str(item.get("block_content") or ""),
                       "order": int(order) if order is not None else len(blocks)})
    return blocks


def handle_parse(payload: dict, *, pipeline, token: str | None, auth_header: str | None) -> dict:
    check_bearer_token(token, auth_header)
    if payload.get("contract") != CONTRACT:
        raise WorkerRefused("contract_mismatch")
    request_id = payload.get("request_id")
    page_index = payload.get("page_index")
    if not isinstance(request_id, str) or not isinstance(page_index, int):
        raise WorkerRefused("request_shape")
    started = time.perf_counter()
    image = decode_jpeg_bounded(str(payload.get("image_jpeg_b64") or ""))
    decoded = time.perf_counter()
    results = list(pipeline.predict(input=image, **PREDICT_KWARGS))
    finished = time.perf_counter()
    blocks = blocks_from_result(results[0].json if results else {})
    return {"contract": CONTRACT, "request_id": request_id, "page_index": page_index, "blocks": blocks,
            "timing": {"decode_ms": (decoded - started) * 1000.0, "inference_ms": (finished - decoded) * 1000.0,
                       "total_ms": (finished - started) * 1000.0}}


def version_payload(environ: dict | None = None, *, versions: dict | None = None) -> dict:
    source = os.environ if environ is None else environ
    if versions is None:
        import importlib.metadata as md

        versions = {}
        for name in ("paddleocr", "paddlex"):
            try:
                versions[name] = md.version(name)
            except md.PackageNotFoundError:
                versions[name] = "absent"
    # BLOCK-2: echo the declaration this worker was started under, so the caller can refuse a mismatch
    # before any page byte moves (the same contract as `ocr/paddle_worker.py`'s /version).
    return {"contract": CONTRACT, "pipeline_version": PIPELINE_VERSION, "served_model_name": SERVED_MODEL_NAME,
            "backend": source.get("VLM_A_BACKEND", "vllm-server"), "retention": RETENTION_POLICY,
            "provider": source.get("PADDLE_PROVIDER", ""), "execution_class": source.get("PADDLE_EXECUTION_CLASS", ""),
            "predict_kwargs": PREDICT_KWARGS, **{f"{k}_version": v for k, v in versions.items()}}


def _make_handler(pipeline, token: str | None, identity: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the log free of request lines
            pass

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path == "/health":
                self._send(200, {"status": "ok"})
            elif self.path == "/version":
                self._send(200, identity)
            else:
                self._send(404, {"error": "not_found"})

        def do_POST(self):  # noqa: N802
            if self.path != "/parse":
                self._send(404, {"error": "not_found"})
                return
            if self.headers.get("Transfer-Encoding"):
                self._send(400, {"error": "chunked_refused"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY_BYTES:
                    raise WorkerRefused("body_too_large", 413)
                payload = parse_bounded_json(self.rfile.read(length))
                self._send(200, handle_parse(payload, pipeline=pipeline, token=token,
                                             auth_header=self.headers.get("Authorization")))
            except WorkerRefused as exc:
                self._send(exc.status, {"error": exc.code})
            except Exception as exc:  # noqa: BLE001
                self._send(500, {"error": "inference_failed", "class": type(exc).__name__})

    return Handler


def build_server(host: str, port: int, pipeline, token: str | None) -> ThreadingHTTPServer:
    if host != LOOPBACK_BIND:
        raise WorkerRefused("bind_not_loopback")
    return ThreadingHTTPServer((host, port), _make_handler(pipeline, token, version_payload()))


def _build_pipeline():
    from paddleocr import PaddleOCRVL

    return PaddleOCRVL(
        pipeline_version=PIPELINE_VERSION,
        vl_rec_backend=os.environ.get("VLM_A_BACKEND", "vllm-server"),
        vl_rec_server_url=os.environ.get("VLM_A_SERVER_URL", "http://127.0.0.1:18001/v1"),
        vl_rec_api_model_name=SERVED_MODEL_NAME,
        use_doc_orientation_classify=False, use_doc_unwarping=False, use_layout_detection=True,
        use_chart_recognition=False, use_seal_recognition=False, use_ocr_for_image_block=False,
        format_block_content=False, merge_layout_blocks=True,
    )


class LazyPipeline:
    """The pipeline is built on the first /parse, so /health and /version (the identity echo the runner
    verifies before any page moves) work on a host without the Paddle environment (2026-09-18: the
    restarted instance kept the scripts but not the environment, and the 27B arm never parses). A /parse
    there refuses `stage_a_unavailable` (503) instead of the worker failing to start."""

    def __init__(self, factory=_build_pipeline) -> None:
        self._factory = factory
        self._pipeline = None
        self._unavailable = False

    def predict(self, input, **kwargs):
        if self._pipeline is None:
            if self._unavailable:
                raise WorkerRefused("stage_a_unavailable", 503)
            try:
                self._pipeline = self._factory()
            except Exception:  # noqa: BLE001 - the whole environment may be absent
                self._unavailable = True
                raise WorkerRefused("stage_a_unavailable", 503) from None
        return self._pipeline.predict(input=input, **kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stage_a_worker")
    parser.add_argument("--port", type=int, default=int(os.environ.get("VLM_A_WORKER_PORT", DEFAULT_PORT)))
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--allow-no-token", action="store_true", help="loopback-only diagnostics; never for a wave")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_check:
        print(json.dumps(version_payload()))
        return 0
    token = resolve_token()
    if token is None and not args.allow_no_token:
        print(json.dumps({"error": "token_required"}), flush=True)
        return 2
    server = build_server(LOOPBACK_BIND, args.port, LazyPipeline(), token)
    print(json.dumps({"listening": True, "port": args.port}), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
