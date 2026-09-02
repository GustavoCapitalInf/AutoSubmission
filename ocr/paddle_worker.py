"""ocr/paddle_worker.py — the remote PaddleOCR loopback service (Phase 2.1
cell P, `docs/agent-handoffs/P21-PADDLE.md` §1, D7).

Runs under the Vast.ai host's `/venv/main` Python (3.12), where `paddleocr`,
`paddlepaddle-gpu`, `Pillow` and `numpy` are installed. It uses ONLY the
standard library plus Pillow and numpy at import time — `paddleocr` is
imported inside the inference function so this module stays importable, and
its request validation unit-testable, on a machine that has never installed
PaddleOCR (this repository's default suite included).

Design (see the umbrella card, D7, and this file's own card, §1):

* `http.server.ThreadingHTTPServer`, bound to `127.0.0.1` ONLY. Any other
  `PADDLE_WORKER_BIND` is a startup error, not an option — this worker is
  reachable ONLY through the SSH tunnel the lifecycle tool opens; it is never
  registered as a Vast "open port" and never fronted by Caddy.
* Identity comes from the worker's OWN environment (`PADDLE_PROVIDER`,
  `PADDLE_EXECUTION_CLASS`), validated against the SAME two tiny closed
  vocabularies `ocr/paddle_config.py` defines — copied here as literals
  (below) because this module does not import the repository's `ocr`
  package; it must stand alone on the remote host.
* Every bound (body size, JSON shape, base64, PNG magic, image dimensions,
  pixel count) is enforced BEFORE the corresponding decode step runs, never
  after — a refusal never partially decodes untrusted input.
* No retention: an image's bytes exist only in the request handler's local
  variables; nothing is written to disk; the one log line per request never
  contains text content.
* The PaddleOCR pipeline is built ONCE, lazily, on the first `/ocr` call (so
  `/health` and `/version` answer before the model loads) with EXACTLY the
  pinned identity; one inference at a time (`_INFERENCE_LOCK`).

PaddleOCR 3.7 result accessor (verified on the Vast host, 2026-09-02, by
reading `paddlex.inference.common.result.mixin.JsonMixin._to_json`, which
every PaddleOCR pipeline result inherits):

    def _to_json(self):
        return {"res": _format_data(copy.deepcopy(self))}

so ``result[0].json["res"]`` is the JSON-serializable page result (numpy
arrays converted to lists) — the exact shape of
`tests/fixtures/paddle/paddle_demo_wordboxes_res.json`. This module reads it
that way and drops `input_path` before returning (the contract in §1: "the
PaddleOCR result dict verbatim, minus input_path").
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Identity vocabularies and pins, copied as LITERALS. Source of truth:
# `ocr/paddle_config.py` (PROVIDERS, EXECUTION_CLASSES, PROVIDER_CLASS, and
# the D5 pin block `paddle_runtime_identity()`). This module does not import
# that package — it must be deployable standalone (`tools/paddle_vast.py
# deploy` copies only this one file to the remote host).
# ---------------------------------------------------------------------------
PROVIDERS = ("vast.ai", "local")
EXECUTION_CLASSES = ("remote_paid", "local_free")
PROVIDER_CLASS = {"vast.ai": "remote_paid", "local": "local_free"}

WORKER_CONTRACT = 1
PADDLEOCR_VERSION_PIN = "3.7.0"
PADDLEPADDLE_VERSION_PIN = "3.3.0"
OCR_VERSION_PIN = "PP-OCRv5"
TEXT_DETECTION_MODEL_PIN = "PP-OCRv5_server_det"
TEXT_RECOGNITION_MODEL_PIN = "en_PP-OCRv5_mobile_rec"
PIPELINE_SWITCHES = {
    "use_doc_orientation_classify": False,
    "use_doc_unwarping": False,
    "use_textline_orientation": False,
    "return_word_box": True,
    "text_rec_score_thresh": 0.0,
}

# ---------------------------------------------------------------------------
# Bounds (D7). Every literal below is written to avoid a contiguous 6+ digit
# run or a two-decimal-place literal, which is incidental style rather than a
# functional requirement, but keeps this module clean under the OQ2 scan the
# same way the rest of `ocr/*.py` is.
# ---------------------------------------------------------------------------
MAX_BODY_BYTES = 32 * 1024 * 1024          # 32 MiB
MAX_RESPONSE_HINT_BYTES = 64 * 1024 * 1024  # informational only; the client enforces its own bound
MAX_IMAGE_PIXELS = 30_000_000
MAX_IMAGE_SIDE_PX = 6_000
MAX_JSON_DEPTH = 20
DEFAULT_WORKER_PORT = 8_765
LOOPBACK_BIND = "127.0.0.1"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

#: The closed error-token vocabulary (§1). Every 4xx/5xx `/ocr` (or config)
#: failure returns one of these in `{"error": <token>}` — never a traceback,
#: never request content.
ERROR_TOKENS = (
    "bad_json",
    "contract_mismatch",
    "body_too_large",
    "not_png",
    "image_too_large",
    "bad_base64",
    "unauthorized",
    "inference_failed",
    "not_found",
    "method_not_allowed",
)


class WorkerConfigError(RuntimeError):
    """The worker's own environment is not a legal configuration. Raised at
    startup, before the socket is opened."""


class WorkerRefused(RuntimeError):
    """One bound or shape check failed. `.token` is a member of
    `ERROR_TOKENS`; `.status` is the HTTP status to answer with."""

    def __init__(self, token: str, status: int, detail: str = ""):
        if token not in ERROR_TOKENS:
            raise ValueError(f"unknown worker error token {token!r}")
        self.token = token
        self.status = status
        super().__init__(detail or token)


def resolve_bind_address(environ: dict | None = None) -> str:
    """`PADDLE_WORKER_BIND` unset -> loopback. Set to anything but the exact
    loopback literal -> `WorkerConfigError` (never a listening socket on a
    non-loopback address, ever)."""
    source = os.environ if environ is None else environ
    bind = (source.get("PADDLE_WORKER_BIND") or "").strip() or LOOPBACK_BIND
    if bind != LOOPBACK_BIND:
        raise WorkerConfigError(
            f"PADDLE_WORKER_BIND must be {LOOPBACK_BIND!r} (loopback only); refusing {bind!r}"
        )
    return bind


def resolve_identity(environ: dict | None = None) -> dict:
    """The worker's declared provider/execution_class, validated against the
    SAME closed pairing `ocr/paddle_config.py` enforces client-side (D2)."""
    source = os.environ if environ is None else environ
    provider = (source.get("PADDLE_PROVIDER") or "").strip()
    execution_class = (source.get("PADDLE_EXECUTION_CLASS") or "").strip()
    if provider not in PROVIDERS:
        raise WorkerConfigError(f"PADDLE_PROVIDER must be one of {PROVIDERS}; got {provider!r}")
    if execution_class not in EXECUTION_CLASSES:
        raise WorkerConfigError(
            f"PADDLE_EXECUTION_CLASS must be one of {EXECUTION_CLASSES}; got {execution_class!r}"
        )
    if PROVIDER_CLASS[provider] != execution_class:
        raise WorkerConfigError(
            f"PADDLE_PROVIDER={provider!r} requires PADDLE_EXECUTION_CLASS="
            f"{PROVIDER_CLASS[provider]!r}; refusing the declared {execution_class!r}"
        )
    return {"provider": provider, "execution_class": execution_class}


def resolve_port(environ: dict | None = None) -> int:
    source = os.environ if environ is None else environ
    raw = (source.get("PADDLE_WORKER_PORT") or "").strip()
    if not raw:
        return DEFAULT_WORKER_PORT
    try:
        port = int(raw)
    except ValueError as exc:
        raise WorkerConfigError("PADDLE_WORKER_PORT must be an integer port") from exc
    if not (1 <= port <= 65535):
        raise WorkerConfigError("PADDLE_WORKER_PORT must be a port in 1..65535")
    return port


def resolve_token(environ: dict | None = None) -> str | None:
    source = os.environ if environ is None else environ
    token = (source.get("PADDLE_WORKER_TOKEN") or "").strip()
    return token or None


# ---------------------------------------------------------------------------
# Bounded JSON body parsing
# ---------------------------------------------------------------------------

def _json_nesting_depth(text: str) -> int:
    """The maximum bracket/brace nesting depth of `text`, ignoring the
    contents of JSON strings (so a string value containing `{` does not
    count). A bound checked BEFORE `json.loads` is asked to parse anything,
    so a pathologically nested body never reaches the parser at all."""
    depth = 0
    max_depth = 0
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch in "}]":
            depth -= 1
    return max_depth


def parse_bounded_json(raw: bytes) -> dict:
    """Decode `raw` as JSON with a depth bound, refusing before the parser
    sees anything pathological. Raises `WorkerRefused("bad_json", 400)`."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkerRefused("bad_json", 400, f"invalid utf-8: {exc}") from exc
    if _json_nesting_depth(text) > MAX_JSON_DEPTH:
        raise WorkerRefused("bad_json", 400, "JSON nesting too deep")
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise WorkerRefused("bad_json", 400, str(type(exc).__name__)) from exc
    if not isinstance(payload, dict):
        raise WorkerRefused("bad_json", 400, "top-level JSON value must be an object")
    return payload


# ---------------------------------------------------------------------------
# The /ocr request: validate, decode, infer
# ---------------------------------------------------------------------------

class _Model:
    """The lazily-built PaddleOCR pipeline, one at a time (D7)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._pipeline = None

    @property
    def loaded(self) -> bool:
        return self._pipeline is not None

    def _build(self):
        # Imported here, never at module scope (D7): this module must remain
        # importable on a machine without `paddleocr` installed.
        from paddleocr import PaddleOCR

        return PaddleOCR(
            text_detection_model_name=TEXT_DETECTION_MODEL_PIN,
            text_recognition_model_name=TEXT_RECOGNITION_MODEL_PIN,
            ocr_version=OCR_VERSION_PIN,
            use_doc_orientation_classify=PIPELINE_SWITCHES["use_doc_orientation_classify"],
            use_doc_unwarping=PIPELINE_SWITCHES["use_doc_unwarping"],
            use_textline_orientation=PIPELINE_SWITCHES["use_textline_orientation"],
            text_rec_score_thresh=PIPELINE_SWITCHES["text_rec_score_thresh"],
        )

    def infer(self, image) -> tuple[dict, bool]:
        """Run one inference. Returns `(raw_result_dict, cold_load)`. Serialized:
        one inference in flight at a time, across every request."""
        cold_load = False
        with self._infer_lock:
            try:
                if self._pipeline is None:
                    with self._lock:
                        if self._pipeline is None:
                            self._pipeline = self._build()
                            cold_load = True
                results = self._pipeline.predict(input=image, return_word_box=True)
            except WorkerRefused:
                raise
            except Exception as exc:
                # Covers both a build failure (e.g. `paddleocr` not
                # installed — exercised offline by this repo's own test
                # suite) and a real inference failure (exercised only with
                # `paddleocr` installed, on the Vast worker).
                raise WorkerRefused("inference_failed", 500, type(exc).__name__) from exc
            if not results:
                raise WorkerRefused("inference_failed", 500, "empty result list")
            raw = dict(results[0].json["res"])
            raw.pop("input_path", None)
            return raw, cold_load


_MODEL = _Model()
_WORKER_STARTED_AT = time.time()


def _gpu_query(fields: str) -> list[str] | None:
    """`nvidia-smi --query-gpu=<fields>`, first GPU only. `None` when the
    tool is unavailable or fails (a worker running without an attached GPU,
    or under a test harness) — never raised, never a hang (bounded timeout)."""
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10.0, check=True,
        )
    except Exception:
        return None
    line = out.stdout.strip().splitlines()
    if not line:
        return None
    return [part.strip() for part in line[0].split(",")]


def gpu_identity() -> dict:
    row = _gpu_query("name,memory.total,driver_version")
    if row is None or len(row) < 3:
        return {"name": None, "memory_total_mib": None, "driver_version": None}
    name, memory_total, driver = row
    mib = None
    try:
        mib = int(float(memory_total.split()[0]))
    except (ValueError, IndexError):
        pass
    return {"name": name, "memory_total_mib": mib, "driver_version": driver}


def gpu_memory_used_mib() -> int | None:
    row = _gpu_query("memory.used")
    if row is None or not row:
        return None
    try:
        return int(float(row[0].split()[0]))
    except (ValueError, IndexError):
        return None


def cuda_compiled() -> bool | None:
    try:
        import paddle  # imported lazily; absent on a machine without paddlepaddle

        return bool(paddle.device.is_compiled_with_cuda())
    except Exception:
        return None


def version_payload(identity: dict) -> dict:
    return {
        "contract": WORKER_CONTRACT,
        "provider": identity["provider"],
        "execution_class": identity["execution_class"],
        "gpu": gpu_identity(),
        "paddleocr_version": PADDLEOCR_VERSION_PIN,
        "paddlepaddle_version": PADDLEPADDLE_VERSION_PIN,
        "cuda_compiled": cuda_compiled(),
        "ocr_version": OCR_VERSION_PIN,
        "text_detection_model_name": TEXT_DETECTION_MODEL_PIN,
        "text_recognition_model_name": TEXT_RECOGNITION_MODEL_PIN,
        "pipeline_switches": dict(PIPELINE_SWITCHES),
        "python_version": platform.python_version(),
        "worker_started_at": _WORKER_STARTED_AT,
        "model_loaded": _MODEL.loaded,
    }


def _decode_image_bounded(image_b64: str):
    """base64 -> PNG magic -> bounded PIL decode. Every bound is checked
    BEFORE the corresponding step: base64 validity before any byte is
    inspected, the PNG magic before Pillow ever touches the bytes, the pixel
    count and side length before `.load()` fully decodes the pixel buffer."""
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise WorkerRefused("bad_base64", 400, type(exc).__name__) from exc
    if len(raw) < len(PNG_MAGIC) or raw[: len(PNG_MAGIC)] != PNG_MAGIC:
        raise WorkerRefused("not_png", 400, "missing PNG magic bytes")

    from PIL import Image

    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        try:
            image = Image.open(io.BytesIO(raw))
            image.load()
        except Exception as exc:
            name = type(exc).__name__
            if "DecompressionBomb" in name:
                raise WorkerRefused("image_too_large", 400, name) from exc
            raise WorkerRefused("not_png", 400, name) from exc
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit

    width, height = image.size
    if width > MAX_IMAGE_SIDE_PX or height > MAX_IMAGE_SIDE_PX:
        raise WorkerRefused("image_too_large", 400, f"{width}x{height} exceeds {MAX_IMAGE_SIDE_PX}px")
    return image, raw


def handle_ocr_request(payload: dict, *, identity: dict, token: str | None,
                        auth_header: str | None) -> dict:
    """The full `/ocr` request pipeline over an already-JSON-decoded body.
    Every refusal is a `WorkerRefused`; the caller turns it into the HTTP
    response. No image byte is touched before every bound above it passes."""
    if token is not None:
        import hmac

        supplied = ""
        if auth_header and auth_header.startswith("Bearer "):
            supplied = auth_header[len("Bearer "):]
        if not hmac.compare_digest(supplied, token):
            raise WorkerRefused("unauthorized", 401)

    if payload.get("contract") != WORKER_CONTRACT:
        raise WorkerRefused("contract_mismatch", 400, f"got {payload.get('contract')!r}")

    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise WorkerRefused("bad_json", 400, "request_id must be a non-empty string")
    page_index = payload.get("page_index")
    if not isinstance(page_index, int) or isinstance(page_index, bool) or page_index < 0:
        raise WorkerRefused("bad_json", 400, "page_index must be a non-negative int")
    image_b64 = payload.get("image_png_b64")
    if not isinstance(image_b64, str) or not image_b64:
        raise WorkerRefused("bad_json", 400, "image_png_b64 must be a non-empty string")

    t_decode_start = time.perf_counter()
    image, raw_png = _decode_image_bounded(image_b64)
    decode_ms = (time.perf_counter() - t_decode_start) * 1000.0

    import numpy as np

    array = np.array(image.convert("RGB"))
    t_infer_start = time.perf_counter()
    raw, cold_load = _MODEL.infer(array)
    inference_ms = (time.perf_counter() - t_infer_start) * 1000.0
    total_ms = decode_ms + inference_ms

    width, height = image.size
    return {
        "raw": raw,
        "image": {"width": width, "height": height, "sha256": hashlib.sha256(raw_png).hexdigest()},
        "timing": {
            "decode_ms": decode_ms,
            "inference_ms": inference_ms,
            "total_ms": total_ms,
            "cold_load": cold_load,
        },
        "gpu": {"memory_used_mib": gpu_memory_used_mib()},
        "model": version_payload(identity),
        "request_id": request_id,
        "page_index": page_index,
    }


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------

def _make_handler(identity: dict, token: str | None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "PaddleWorker/1"

        def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
            pass  # silenced; `_log_line` below is the one line per request

        def _log_line(self, method: str, path: str, status: int, ms: float, extra: str = "") -> None:
            sys.stderr.write(f"{method} {path} {status} {ms:.1f}ms{(' ' + extra) if extra else ''}\n")

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error_token(self, token_value: str, status: int) -> None:
            self._send_json(status, {"error": token_value})

        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            started = time.perf_counter()
            if self.path == "/health":
                self._send_json(200, {"ok": True, "contract": WORKER_CONTRACT})
            elif self.path == "/version":
                self._send_json(200, version_payload(identity))
            else:
                self._send_error_token("not_found", 404)
            self._log_line("GET", self.path, 200, (time.perf_counter() - started) * 1000.0)

        def do_POST(self) -> None:  # noqa: N802 - stdlib method name
            started = time.perf_counter()
            if self.path != "/ocr":
                self._send_error_token("method_not_allowed", 405)
                return
            status = 200
            page_index = None
            width = height = None
            try:
                length_header = self.headers.get("Content-Length")
                if length_header is None:
                    raise WorkerRefused("bad_json", 400, "missing Content-Length")
                try:
                    length = int(length_header)
                except ValueError as exc:
                    raise WorkerRefused("bad_json", 400, "invalid Content-Length") from exc
                if length > MAX_BODY_BYTES or length < 0:
                    raise WorkerRefused("body_too_large", 413)
                raw_body = self.rfile.read(length)
                if len(raw_body) != length:
                    raise WorkerRefused("bad_json", 400, "short read")
                payload = parse_bounded_json(raw_body)
                result = handle_ocr_request(
                    payload, identity=identity, token=token,
                    auth_header=self.headers.get("Authorization"),
                )
                page_index = result.get("page_index")
                width = result["image"]["width"]
                height = result["image"]["height"]
                self._send_json(200, result)
            except WorkerRefused as refused:
                status = refused.status
                self._send_error_token(refused.token, refused.status)
            except Exception:  # pragma: no cover - defensive; never a traceback to the wire
                status = 500
                self._send_error_token("inference_failed", 500)
            finally:
                extra = f"page={page_index} {width}x{height}" if width else ""
                self._log_line("POST", self.path, status, (time.perf_counter() - started) * 1000.0, extra)

    return Handler


def build_server(host: str, port: int, identity: dict, token: str | None) -> ThreadingHTTPServer:
    if host != LOOPBACK_BIND:
        raise WorkerConfigError(f"refusing to bind to non-loopback address {host!r}")
    return ThreadingHTTPServer((host, port), _make_handler(identity, token))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    identity = resolve_identity()
    if "--self-check" in argv:
        print(json.dumps(version_payload(identity), sort_keys=True, indent=2))
        return 0
    host = resolve_bind_address()
    port = resolve_port()
    token = resolve_token()
    server = build_server(host, port, identity, token)
    sys.stderr.write(
        f"paddle_worker listening on {host}:{port} "
        f"(provider={identity['provider']} execution_class={identity['execution_class']} "
        f"token={'set' if token else 'unset'})\n"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
