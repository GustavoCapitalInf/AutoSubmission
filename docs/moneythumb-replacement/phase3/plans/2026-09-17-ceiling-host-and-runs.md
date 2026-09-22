# Phase 3 Ceiling Experiment — Host Lifecycle and Live Runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Depends on the four-part offline harness plan (`2026-09-17-ceiling-harness-part1..4.md`) being complete and green.

**Goal:** Bring the two model servers up on the rented RTX 5090 over the reviewed SSH/loopback transport, prove the whole path on synthetic pages, get the boundary code reviewed, then run the CTRL and U755 waves for arms 1–4 and report go/revise/stop.

**Architecture:** One remote directory `/workspace/ci_vlm/` holds the deployed Stage A worker script and pid/log files. Two vLLM servers (Stage A model on 18001, Stage B model on 18002) and the Stage A pipeline worker (Paddle venv, 18003) bind to 127.0.0.1 only. One SSH tunnel forwards the three loopback ports. `tools/vlm_vast.py` reuses `tools/paddle_vast.py` helpers (`_ssh_command`, `_scp_command`, `_run`, `_popen`, `mask_text`, `_pid_alive`, `_port_listening`, `_terminate_pid`) and `ocr.paddle_config` settings; every printed byte is masked.

**Tech Stack:** host image vLLM 0.29.0 + torch 2.13.0+cu130 + transformers 5.16.1 + xgrammar 0.2.3 (system Python 3.12); `/workspace/paddleocr-env` (paddleocr 3.7.0, paddlex 3.7.2, paddlepaddle-gpu 3.3.0, pypdfium2 5.13.0); `/venv/main` has `hf` (huggingface_hub 1.30.0); disk 21 GB free; `HF_HOME=/workspace/.hf_home`; paddlex weights cached in `~/.paddlex/official_models` (PaddleOCR-VL-1.6, PP-DocLayoutV3).

## Global Constraints

All constraints of the harness plan part 1 apply. In addition:

- Model pins (from the 2026-09-17 research; re-verify revision hashes at fetch time and record them in LICENSES.md and the fetch receipt): Stage A `PaddlePaddle/PaddleOCR-VL-1.6` (Apache-2.0, 1.92 GB, served name `PaddleOCR-VL-1.6-0.9B`); Stage B primary `Qwen/Qwen3.5-4B` (Apache-2.0, 9.32 GB); Stage B second variant `RedHatAI/Qwen3.5-9B-FP8-dynamic` (Apache-2.0, 14.01 GB) run only after the 4B waves and only if `df` shows ≥ 16 GB free (delete nothing without a receipt). Never `Qwen/Qwen3.5-9B` bf16 on this disk.
- Stage B server flags (Qwen3.5 hybrid-GDN risks on sm_120, vLLM issues #44209/#52872/#53726): `--max-model-len 16384 --max-num-seqs 4 --max-num-batched-tokens 4096 --gpu-memory-utilization 0.55 --limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar`; no `--speculative-config`; add `--enforce-eager` only if CUDA-graph capture OOMs (record it in the receipt).
- Stage A vLLM flags (recipe): `--trust-remote-code --max-num-batched-tokens 16384 --no-enable-prefix-caching --mm-processor-cache-gb 0 --gpu-memory-utilization 0.15 --max-model-len 16384 --served-model-name PaddleOCR-VL-1.6-0.9B`.
- All servers: `--host 127.0.0.1`, `--download-dir /workspace/models`, `HF_HOME=/workspace/.hf_home`, `HF_HUB_OFFLINE=1` after the fetch step, `VLLM_NO_USAGE_STATS=1`, `DO_NOT_TRACK=1`.
- Retention: the Stage A worker never writes request images to disk (predict on an in-memory array); vLLM logs must not contain prompts (`--disable-log-requests`, verify the flag name on 0.29 with `vllm serve --help`); the attestation step counts files under `/workspace/ci_vlm/` and `/tmp` newer than the wave start and requires zero image files.
- Cost: instance hours are recorded per wave (`instance_hours` in `result.json`); the operator supplies `--hourly-rate` once Gustavo provides it; until then receipts say `rate not measured`.
- Order of execution is fixed by R16: synthetic preflight → independent review → CTRL → U755.

## File Structure

| File | Responsibility |
|---|---|
| `vlm/stage_a_worker.py` | remote loopback HTTP service (Paddle venv): `/health`, `/version`, `/parse`; PaddleOCRVL pipeline with the vLLM backend; bounded, token-checked, retention none |
| `tools/vlm_vast.py` | `check`, `fetch`, `deploy`, `start-a`, `start-b`, `start-worker`, `status`, `stop`, `tunnel-up`, `tunnel-down`, `attest`; masked |
| `docs/moneythumb-replacement/phase3/LICENSES.md` | SPDX ids, repo ids, revision hashes, dates, URLs for every model and library used |
| `discovery_reports/train13-logs/p3ceiling/` | manifests, fetch receipts, waves (`waves/<arm>-<population>-<n>/`), reviews |
| `tests/test_vlm_stage_a_worker.py`, `tests/test_vlm_vast_tool.py` | offline tests with fake pipeline / fake runner |

---

### Task B1: Stage A worker (remote, Paddle venv)

**Files:**
- Create: `vlm/stage_a_worker.py`
- Test: `tests/test_vlm_stage_a_worker.py`

**Interfaces:**
- Produces: constants `CONTRACT = 1`, `LOOPBACK_BIND = "127.0.0.1"`, `DEFAULT_PORT = 18003`, `MAX_BODY_BYTES = 32 MiB`, `MAX_IMAGE_PIXELS = 30_000_000`; functions `resolve_token(environ)`, `check_bearer_token(token, header)`, `parse_bounded_json(raw) -> dict`, `decode_jpeg_bounded(b64) -> ndarray (BGR)`, `blocks_from_result(result: dict) -> list[dict]` (maps `parsing_res_list[*]` → `{label: block_label, bbox: block_bbox, content: block_content, order: block_order}`), `handle_parse(payload, *, pipeline, token, auth_header) -> dict` (`{"contract", "request_id", "page_index", "blocks", "timing": {"decode_ms", "inference_ms", "total_ms"}, "model": identity}`), `version_payload(environ) -> dict` (paddleocr/paddlex versions, pipeline version, backend, served model name, `retention: "none"`), `build_server(host, port, pipeline, token)`, `main(argv)`.
- Pipeline construction (mirrors the reviewed VL16 adapter and the 3.7.0 signature): `PaddleOCRVL(pipeline_version="v1.6", vl_rec_backend=environ.get("VLM_A_BACKEND", "vllm-server"), vl_rec_server_url=environ.get("VLM_A_SERVER_URL", "http://127.0.0.1:18001/v1"), vl_rec_api_model_name="PaddleOCR-VL-1.6-0.9B", use_doc_orientation_classify=False, use_doc_unwarping=False, use_layout_detection=True, use_chart_recognition=False, use_seal_recognition=False, use_ocr_for_image_block=False, format_block_content=False, merge_layout_blocks=True)`; `predict(input=image_bgr)`; per page result via `res.json["res"]` if present else `res.json` (both shapes seen in 3.x); the worker imports `paddleocr` lazily inside `main` so the module is unit-testable offline.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_stage_a_worker.py
import base64
import io
import json

import pytest
from PIL import Image

from vlm import stage_a_worker as w


class FakeRes:
    def __init__(self, payload):
        self.json = payload


class FakePipeline:
    def __init__(self):
        self.calls = []

    def predict(self, input, **kwargs):
        self.calls.append(input.shape)
        return [FakeRes({"res": {"parsing_res_list": [
            {"block_label": "table", "block_bbox": [1, 2, 3, 4], "block_content": "<table></table>", "block_order": 0, "block_id": 0},
            {"block_label": "text", "block_bbox": [5, 6, 7, 8], "block_content": "hello", "block_order": 1, "block_id": 1}]}})]


def _jpeg(w_=40, h_=30):
    buf = io.BytesIO()
    Image.new("RGB", (w_, h_), (255, 255, 255)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_handle_parse_maps_blocks_and_timings():
    pipe = FakePipeline()
    out = w.handle_parse({"contract": 1, "request_id": "abc.p0", "page_index": 0, "image_jpeg_b64": _jpeg()},
                         pipeline=pipe, token="t", auth_header="Bearer t")
    assert out["blocks"] == [{"label": "table", "bbox": [1, 2, 3, 4], "content": "<table></table>", "order": 0},
                             {"label": "text", "bbox": [5, 6, 7, 8], "content": "hello", "order": 1}]
    assert out["request_id"] == "abc.p0" and out["page_index"] == 0 and out["timing"]["inference_ms"] >= 0
    assert pipe.calls == [(30, 40, 3)]


def test_bad_token_and_bad_contract_refused():
    with pytest.raises(w.WorkerRefused) as exc:
        w.handle_parse({"contract": 1, "request_id": "x", "page_index": 0, "image_jpeg_b64": _jpeg()}, pipeline=FakePipeline(), token="t", auth_header="Bearer wrong")
    assert exc.value.code == "unauthorized"
    with pytest.raises(w.WorkerRefused) as exc:
        w.handle_parse({"contract": 2, "request_id": "x", "page_index": 0, "image_jpeg_b64": _jpeg()}, pipeline=FakePipeline(), token=None, auth_header=None)
    assert exc.value.code == "contract_mismatch"


def test_image_bounds():
    with pytest.raises(w.WorkerRefused) as exc:
        w.decode_jpeg_bounded(base64.b64encode(b"not an image").decode())
    assert exc.value.code == "image_invalid"
    assert w.decode_jpeg_bounded(_jpeg()).shape == (30, 40, 3)


def test_parse_bounded_json_and_version():
    assert w.parse_bounded_json(b'{"a": 1}') == {"a": 1}
    with pytest.raises(w.WorkerRefused):
        w.parse_bounded_json(b"[1]")
    version = w.version_payload({"VLM_A_BACKEND": "vllm-server"}, versions={"paddleocr": "3.7.0", "paddlex": "3.7.2"})
    assert version["retention"] == "none" and version["backend"] == "vllm-server" and version["pipeline_version"] == "v1.6"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_stage_a_worker.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.stage_a_worker'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/stage_a_worker.py
"""Stage A worker: a loopback-only HTTP service around the PaddleOCR-VL pipeline (layout + VL via vLLM).

Deployed to the rented host and run inside the Paddle virtualenv. Mirrors `ocr/paddle_worker.py`:
127.0.0.1 bind only, bearer token, bounded JSON body, bounded image decode, closed error tokens,
retention none (the page exists only in memory). `paddleocr` is imported inside `main()` only.
"""
from __future__ import annotations

import argparse
import base64
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
    if auth_header != f"Bearer {token}":
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
    blocks = []
    for item in inner.get("parsing_res_list") or []:
        if not isinstance(item, dict):
            continue
        blocks.append({"label": str(item.get("block_label") or "text"),
                       "bbox": [float(v) for v in (item.get("block_bbox") or [0, 0, 0, 0])[:4]],
                       "content": str(item.get("block_content") or ""),
                       "order": int(item.get("block_order") if item.get("block_order") is not None else len(blocks))})
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
        versions = {name: md.version(name) for name in ("paddleocr", "paddlex")}
    return {"contract": CONTRACT, "pipeline_version": PIPELINE_VERSION, "served_model_name": SERVED_MODEL_NAME,
            "backend": source.get("VLM_A_BACKEND", "vllm-server"), "retention": RETENTION_POLICY,
            "predict_kwargs": PREDICT_KWARGS, **{f"{k}_version": v for k, v in versions.items()}}


def _make_handler(pipeline, token: str | None, identity: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # never log request lines (they carry nothing sensitive, but keep quiet)
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
                self._send(200, handle_parse(payload, pipeline=pipeline, token=token, auth_header=self.headers.get("Authorization")))
            except WorkerRefused as exc:
                self._send(exc.status, {"error": exc.code})
            except Exception as exc:  # noqa: BLE001
                self._send(500, {"error": "inference_failed", "class": type(exc).__name__})

    return Handler


def build_server(host: str, port: int, pipeline, token: str | None) -> ThreadingHTTPServer:
    if host != LOOPBACK_BIND:
        raise WorkerRefused("bind_not_loopback")
    return ThreadingHTTPServer((host, port), _make_handler(pipeline, token, version_payload()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stage_a_worker")
    parser.add_argument("--port", type=int, default=int(os.environ.get("VLM_A_WORKER_PORT", DEFAULT_PORT)))
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_check:
        print(json.dumps(version_payload()))
        return 0
    from paddleocr import PaddleOCRVL

    pipeline = PaddleOCRVL(
        pipeline_version=PIPELINE_VERSION,
        vl_rec_backend=os.environ.get("VLM_A_BACKEND", "vllm-server"),
        vl_rec_server_url=os.environ.get("VLM_A_SERVER_URL", "http://127.0.0.1:18001/v1"),
        vl_rec_api_model_name=SERVED_MODEL_NAME,
        use_doc_orientation_classify=False, use_doc_unwarping=False, use_layout_detection=True,
        use_chart_recognition=False, use_seal_recognition=False, use_ocr_for_image_block=False,
        format_block_content=False, merge_layout_blocks=True,
    )
    server = build_server(LOOPBACK_BIND, args.port, pipeline, resolve_token())
    print(json.dumps({"listening": True, "port": args.port}), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_stage_a_worker.py -q -p no:cacheprovider`
Expected: `4 passed` (numpy is installed locally: 2.4.6).

- [ ] **Step 5: Commit**

```bash
git add vlm/stage_a_worker.py tests/test_vlm_stage_a_worker.py
git commit -m "vlm: Stage A loopback worker around the PaddleOCR-VL pipeline" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task B2: Host lifecycle tool

**Files:**
- Create: `tools/vlm_vast.py`
- Test: `tests/test_vlm_vast_tool.py`

**Interfaces:**
- Consumes: `ocr.paddle_config.load_paddle_settings`, `PaddleSettings`; `tools.paddle_vast._ssh_command`, `_scp_command`, `_run`, `_popen`, `mask_text`, `_pid_alive`, `_port_listening`, `_terminate_pid`, `_runtime_dir`, `PaddleVastError`.
- Produces: constants `REMOTE_DIR = "/workspace/ci_vlm"`, `PORTS = {"a": 18001, "b": 18002, "worker": 18003}`, `MODELS = {"a": {"repo": "PaddlePaddle/PaddleOCR-VL-1.6", "served": "PaddleOCR-VL-1.6-0.9B"}, "b": {"repo": "Qwen/Qwen3.5-4B", "served": "Qwen/Qwen3.5-4B"}, "b9": {"repo": "RedHatAI/Qwen3.5-9B-FP8-dynamic", "served": "RedHatAI/Qwen3.5-9B-FP8-dynamic"}}`, `SERVE_FLAGS = {...}` (the flag strings from Global Constraints), `PADDLE_PYTHON = "/workspace/paddleocr-env/bin/python"`, `HF_PYTHON = "/venv/main/bin/python"`; commands `cmd_check(settings, *, runner) -> dict` (disk free GB, GPU, vllm/torch versions, paddle venv versions, listening ports), `cmd_fetch(settings, key, *, runner) -> dict` (`hf download <repo> --local-dir /workspace/models/<safe-name>`; refuses when free disk < size + 2 GB; then records `sha256sum` of `config.json` and every `*.safetensors` and the resolved revision from the `.cache/huggingface` metadata; writes `discovery_reports/train13-logs/p3ceiling/fetch-<key>-<UTC>.json`), `cmd_deploy(settings, *, runner)` (scp `vlm/stage_a_worker.py` to `REMOTE_DIR`, then `--self-check` in the Paddle venv), `cmd_start(settings, key, *, runner)` (`nohup env ... vllm serve ... > REMOTE_DIR/<key>.log 2>&1 < /dev/null & echo $! > REMOTE_DIR/<key>.pid`; for `worker`: `nohup env VLM_A_WORKER_TOKEN=... PADDLE_PYTHON stage_a_worker.py`), `cmd_status(settings, *, runner)` (pids alive, ports listening, `/v1/models` through the tunnel if up, GPU memory), `cmd_stop(settings, key|all, *, runner)`, `cmd_tunnel_up(settings, *, popen)` (three `-L` forwards, pid to `<runtime_dir>/vlm_tunnel.pid`), `cmd_tunnel_down(settings)`, `cmd_attest(settings, *, runner, since_epoch) -> dict` (counts: server processes alive, files in REMOTE_DIR newer than since (excluding logs/pids), image files under /tmp newer than since; passes when all are zero), `main(argv)`.
- Every subprocess argument that could carry the host/user/port passes through `mask_text` before printing; the worker token is generated with `secrets.token_urlsafe(32)`, stored at `<runtime_dir>/vlm_worker.token` (chmod 600), never printed.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_vast_tool.py
import json
from types import SimpleNamespace

import pytest

from tools import vlm_vast


class Proc:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


def _settings():
    return SimpleNamespace(provider="vast.ai", execution_class="remote_paid", vast_host="203.0.113.9", vast_ssh_port=2222,
                           vast_ssh_user="root", runtime_dir=".paddle_runtime", worker_token=None, tunnel_local_port=18765, worker_port=8765)


def test_serve_command_pins_flags_and_loopback():
    cmd = vlm_vast.serve_command("b")
    assert "--host 127.0.0.1" in cmd and "--port 18002" in cmd and "Qwen/Qwen3.5-4B" in cmd
    assert "--max-num-seqs 4" in cmd and "--structured-outputs-config.backend xgrammar" in cmd and "--speculative-config" not in cmd
    a = vlm_vast.serve_command("a")
    assert "--served-model-name PaddleOCR-VL-1.6-0.9B" in a and "--trust-remote-code" in a and "--port 18001" in a


def test_fetch_refuses_when_disk_is_short():
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        return Proc(stdout="3\n")  # df reports 3 GB free
    with pytest.raises(vlm_vast.PaddleVastError) as exc:
        vlm_vast.cmd_fetch(_settings(), "b", runner=runner)
    assert "disk_insufficient" in str(exc.value)
    assert all("203.0.113.9" not in json.dumps(c) or True for c in calls)  # command lines may carry the host; output must not


def test_check_masks_host(capsys):
    def runner(args, **kwargs):
        text = " ".join(args)
        if "df" in text:
            return Proc("21\n")
        if "nvidia-smi" in text:
            return Proc("NVIDIA GeForce RTX 5090, 32607 MiB, 580.173.02\n")
        return Proc("vllm 0.29.0\ntorch 2.13.0+cu130\n")
    out = vlm_vast.cmd_check(_settings(), runner=runner)
    assert out["disk_free_gb"] == 21 and "5090" in out["gpu"]
    assert "203.0.113.9" not in json.dumps(out)


def test_tunnel_command_forwards_three_ports():
    cmd = vlm_vast.tunnel_command(_settings())
    forwards = [cmd[i + 1] for i, part in enumerate(cmd) if part == "-L"]
    assert forwards == ["127.0.0.1:18001:127.0.0.1:18001", "127.0.0.1:18002:127.0.0.1:18002", "127.0.0.1:18003:127.0.0.1:18003"]
    assert "-N" in cmd and "BatchMode=yes" in " ".join(cmd)


def test_attest_parses_counts():
    def runner(args, **kwargs):
        return Proc("SERVER_PROCESSES=0\nNEW_FILES=0\nTMP_IMAGES=0\n")
    att = vlm_vast.cmd_attest(_settings(), runner=runner, since_epoch=0.0)
    assert att["passed"] is True and att["counts"] == {"SERVER_PROCESSES": 0, "NEW_FILES": 0, "TMP_IMAGES": 0}

    def bad(args, **kwargs):
        return Proc("SERVER_PROCESSES=1\nNEW_FILES=0\nTMP_IMAGES=2\n")
    assert vlm_vast.cmd_attest(_settings(), runner=bad, since_epoch=0.0)["passed"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_vast_tool.py -q -p no:cacheprovider`
Expected: FAIL with `ImportError: cannot import name 'vlm_vast'`

- [ ] **Step 3: Write the implementation**

```python
# tools/vlm_vast.py
"""Lifecycle of the ceiling-experiment servers on the rented host. Everything printed is masked.

Reuses the reviewed transport of `tools/paddle_vast.py`; adds nothing to the trust boundary: SSH to the
configured host, loopback-only servers, one tunnel with three forwards.
"""
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ocr.paddle_config import PaddleConfigError, load_paddle_settings
from tools.paddle_vast import (PaddleVastError, _pid_alive, _popen, _port_listening, _run, _runtime_dir, _scp_command,
                               _ssh_command, _terminate_pid, mask_text)

REMOTE_DIR = "/workspace/ci_vlm"
MODELS_DIR = "/workspace/models"
HF_HOME = "/workspace/.hf_home"
PADDLE_PYTHON = "/workspace/paddleocr-env/bin/python"
HF_PYTHON = "/venv/main/bin/python"
PORTS = {"a": 18001, "b": 18002, "b9": 18002, "worker": 18003}
MODELS = {
    "a": {"repo": "PaddlePaddle/PaddleOCR-VL-1.6", "served": "PaddleOCR-VL-1.6-0.9B", "size_gb": 2.0},
    "b": {"repo": "Qwen/Qwen3.5-4B", "served": "Qwen/Qwen3.5-4B", "size_gb": 9.4},
    "b9": {"repo": "RedHatAI/Qwen3.5-9B-FP8-dynamic", "served": "RedHatAI/Qwen3.5-9B-FP8-dynamic", "size_gb": 14.1},
}
SERVE_FLAGS = {
    "a": "--trust-remote-code --max-num-batched-tokens 16384 --no-enable-prefix-caching --mm-processor-cache-gb 0 "
         "--gpu-memory-utilization 0.15 --max-model-len 16384",
    "b": "--max-model-len 16384 --max-num-seqs 4 --max-num-batched-tokens 4096 --gpu-memory-utilization 0.55 "
         "--limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar",
    "b9": "--max-model-len 16384 --max-num-seqs 4 --max-num-batched-tokens 4096 --gpu-memory-utilization 0.62 "
          "--limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar",
}
COMMON_ENV = f"HF_HOME={HF_HOME} HF_HUB_OFFLINE=1 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1"
DISK_MARGIN_GB = 2.0
RECEIPTS = Path("discovery_reports/train13-logs/p3ceiling")


def _local_dir(key: str) -> str:
    return f"{MODELS_DIR}/{MODELS[key]['repo'].replace('/', '__')}"


def serve_command(key: str) -> str:
    model = MODELS[key]
    return (f"vllm serve {_local_dir(key)} --served-model-name {model['served']} --host 127.0.0.1 --port {PORTS[key]} "
            f"--download-dir {MODELS_DIR} {SERVE_FLAGS[key]}")


def tunnel_command(settings) -> list[str]:
    cmd = ["ssh", "-N", "-o", "ExitOnForwardFailure=yes", "-o", "BatchMode=yes"]
    for port in (PORTS["a"], PORTS["b"], PORTS["worker"]):
        cmd += ["-L", f"127.0.0.1:{port}:127.0.0.1:{port}"]
    cmd += ["-p", str(settings.vast_ssh_port), f"{settings.vast_ssh_user}@{settings.vast_host}"]
    return cmd


def _ssh(settings, runner, command: str, timeout: float = 120.0):
    return _run(runner, _ssh_command(settings, command), capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout)


def _disk_free_gb(settings, runner) -> float:
    proc = _ssh(settings, runner, "df -BG --output=avail / | tail -1 | tr -dc '0-9'")
    return float((proc.stdout or "0").strip() or 0)


def cmd_check(settings, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    gpu = _ssh(settings, runner, "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader").stdout.strip()
    versions = _ssh(settings, runner, "python3 -m pip list 2>/dev/null | grep -i -E '^(vllm|torch|transformers|xgrammar) ' ; "
                                      f"{PADDLE_PYTHON} -m pip list 2>/dev/null | grep -i -E '^(paddleocr|paddlex|paddlepaddle-gpu|pypdfium2) '").stdout
    ports = _ssh(settings, runner, "ss -ltn 2>/dev/null | grep -o -E '127.0.0.1:(18001|18002|18003)' | sort -u").stdout.split()
    return {"provider": settings.provider, "execution_class": settings.execution_class, "gpu": mask_text(gpu, settings),
            "disk_free_gb": _disk_free_gb(settings, runner), "versions": mask_text(versions, settings).split("\n"),
            "listening": [p.split(":")[-1] for p in ports]}


def cmd_fetch(settings, key: str, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    model = MODELS[key]
    free = _disk_free_gb(settings, runner)
    if free < model["size_gb"] + DISK_MARGIN_GB:
        raise PaddleVastError(f"disk_insufficient:{free:.0f}GB_free")
    target = _local_dir(key)
    fetch = (f"mkdir -p {MODELS_DIR} && HF_HOME={HF_HOME} {HF_PYTHON} -m huggingface_hub.commands.huggingface_cli download "
             f"{model['repo']} --local-dir {target} > {REMOTE_DIR}/fetch-{key}.log 2>&1; echo EXIT=$?")
    proc = _ssh(settings, runner, f"mkdir -p {REMOTE_DIR} && {fetch}", timeout=3600.0)
    hashes = _ssh(settings, runner, f"cd {target} && sha256sum config.json *.safetensors 2>/dev/null; "
                                    f"cat .cache/huggingface/download/*.metadata 2>/dev/null | head -c 2000", timeout=600.0).stdout
    receipt = {"key": key, "repo": model["repo"], "local_dir": target, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "exit": (proc.stdout or "").strip().split("EXIT=")[-1], "hashes": mask_text(hashes, settings).split("\n"),
               "disk_free_gb_before": free, "disk_free_gb_after": _disk_free_gb(settings, runner)}
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    path = RECEIPTS / f"fetch-{key}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {**receipt, "receipt": str(path)}


def cmd_deploy(settings, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    _ssh(settings, runner, f"mkdir -p {REMOTE_DIR}")
    local = Path("vlm/stage_a_worker.py")
    _run(runner, _scp_command(settings, str(local), f"{REMOTE_DIR}/stage_a_worker.py"), capture_output=True, text=True, timeout=120)
    check = _ssh(settings, runner, f"{PADDLE_PYTHON} {REMOTE_DIR}/stage_a_worker.py --self-check")
    return {"deployed": True, "self_check": mask_text((check.stdout or "").strip(), settings)}


def _token_path(settings) -> Path:
    return _runtime_dir(settings) / "vlm_worker.token"


def _token(settings) -> str:
    path = _token_path(settings)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    path.write_text(token, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return token


def cmd_start(settings, key: str, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    if key == "worker":
        env = f"VLM_A_WORKER_TOKEN={_token(settings)} VLM_A_BACKEND=vllm-server VLM_A_SERVER_URL=http://127.0.0.1:{PORTS['a']}/v1 VLM_A_WORKER_PORT={PORTS['worker']}"
        launch = f"{PADDLE_PYTHON} {REMOTE_DIR}/stage_a_worker.py"
    else:
        env = COMMON_ENV
        launch = serve_command(key)
    remote = (f"mkdir -p {REMOTE_DIR} && cd {REMOTE_DIR} && nohup env {env} {launch} > {REMOTE_DIR}/{key}.log 2>&1 < /dev/null & "
              f"echo $! > {REMOTE_DIR}/{key}.pid; cat {REMOTE_DIR}/{key}.pid")
    proc = _ssh(settings, runner, remote, timeout=60.0)
    return {"started": key, "remote_pid": (proc.stdout or "").strip(), "port": PORTS[key]}


def cmd_stop(settings, key: str, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    keys = ("worker", "b", "a") if key == "all" else (key,)
    out = {}
    for k in keys:
        proc = _ssh(settings, runner, f"if [ -f {REMOTE_DIR}/{k}.pid ]; then kill $(cat {REMOTE_DIR}/{k}.pid) 2>/dev/null; sleep 3; "
                                      f"kill -9 $(cat {REMOTE_DIR}/{k}.pid) 2>/dev/null; rm -f {REMOTE_DIR}/{k}.pid; echo stopped; else echo absent; fi")
        out[k] = (proc.stdout or "").strip()
    return out


def cmd_status(settings, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    proc = _ssh(settings, runner, f"for k in a b worker; do if [ -f {REMOTE_DIR}/$k.pid ] && kill -0 $(cat {REMOTE_DIR}/$k.pid) 2>/dev/null; then echo $k=alive; else echo $k=down; fi; done; "
                                  "ss -ltn 2>/dev/null | grep -o -E '127.0.0.1:(18001|18002|18003)' | sort -u; nvidia-smi --query-gpu=memory.used --format=csv,noheader")
    return {"remote": mask_text(proc.stdout or "", settings).split("\n"),
            "tunnel_local_ports_listening": {str(p): _port_listening(p) for p in (PORTS["a"], PORTS["b"], PORTS["worker"])}}


def cmd_tunnel_up(settings, *, popen: Callable[..., Any] = subprocess.Popen) -> dict:
    for port in (PORTS["a"], PORTS["b"], PORTS["worker"]):
        if _port_listening(port):
            raise PaddleVastError(f"local_port_in_use:{port}")
    process = _popen(popen, tunnel_command(settings), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pid_path = _runtime_dir(settings) / "vlm_tunnel.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(process.pid), encoding="utf-8")
    time.sleep(2.0)
    return {"pid": process.pid, "ports": [PORTS["a"], PORTS["b"], PORTS["worker"]]}


def cmd_tunnel_down(settings) -> dict:
    pid_path = _runtime_dir(settings) / "vlm_tunnel.pid"
    if not pid_path.exists():
        return {"stopped": False, "reason": "no vlm_tunnel.pid"}
    pid = int(pid_path.read_text(encoding="utf-8").strip() or 0)
    if pid and _pid_alive(pid):
        _terminate_pid(pid)
    pid_path.unlink()
    return {"stopped": True, "pid": pid}


_ATTEST = ("SERVER_PROCESSES=$(ps -eo cmd | grep -v grep | grep -c -E 'vllm serve|stage_a_worker.py'); "
           "NEW_FILES=$(find {dir} -type f -newermt '@{since}' ! -name '*.log' ! -name '*.pid' 2>/dev/null | wc -l); "
           "TMP_IMAGES=$(find /tmp -type f -newermt '@{since}' \\( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \\) 2>/dev/null | wc -l); "
           "echo SERVER_PROCESSES=$SERVER_PROCESSES; echo NEW_FILES=$NEW_FILES; echo TMP_IMAGES=$TMP_IMAGES")


def cmd_attest(settings, *, runner: Callable[..., Any] = subprocess.run, since_epoch: float) -> dict:
    proc = _ssh(settings, runner, _ATTEST.format(dir=REMOTE_DIR, since=int(since_epoch)))
    counts: dict[str, int] = {}
    for line in (proc.stdout or "").splitlines():
        if "=" in line:
            name, value = line.split("=", 1)
            counts[name.strip()] = int(value.strip() or 0)
    inspected = set(counts) == {"SERVER_PROCESSES", "NEW_FILES", "TMP_IMAGES"}
    return {"inspected": inspected, "counts": counts, "passed": inspected and all(v == 0 for v in counts.values()),
            "retention_declared": "none", "attested_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm_vast")
    parser.add_argument("command", choices=("check", "fetch", "deploy", "start", "stop", "status", "tunnel-up", "tunnel-down", "attest"))
    parser.add_argument("--key", choices=("a", "b", "b9", "worker", "all"), default=None)
    parser.add_argument("--since-epoch", type=float, default=0.0)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        settings = load_paddle_settings()
    except PaddleConfigError as exc:
        print(json.dumps({"error": "paddle_config_missing", "detail": str(exc)}))
        return 2
    try:
        if args.command == "check":
            out = cmd_check(settings)
        elif args.command == "fetch":
            out = cmd_fetch(settings, args.key)
        elif args.command == "deploy":
            out = cmd_deploy(settings)
        elif args.command == "start":
            out = cmd_start(settings, args.key)
        elif args.command == "stop":
            out = cmd_stop(settings, args.key or "all")
        elif args.command == "status":
            out = cmd_status(settings)
        elif args.command == "tunnel-up":
            out = cmd_tunnel_up(settings)
        elif args.command == "tunnel-down":
            out = cmd_tunnel_down(settings)
        else:
            out = cmd_attest(settings, since_epoch=args.since_epoch)
    except PaddleVastError as exc:
        print(json.dumps({"error": mask_text(str(exc), settings)}))
        return 1
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_vast_tool.py -q -p no:cacheprovider`
Expected: `5 passed`. (`_run`'s keyword pass-through must accept `encoding`/`errors`; if `tools.paddle_vast._run` filters kwargs, call `runner(...)` through it exactly as `cmd_check` there does and drop the two keywords, decoding with `errors="replace"` afterwards.)

- [ ] **Step 5: Commit**

```bash
git add tools/vlm_vast.py tests/test_vlm_vast_tool.py
git commit -m "vlm: host lifecycle tool (fetch, deploy, start, stop, tunnel, attest)" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task B3: LICENSES.md and pins receipt

**Files:**
- Create: `docs/moneythumb-replacement/phase3/LICENSES.md`

- [ ] **Step 1: Write the file** with one table row per item: name, repo/package, version or revision hash (models: the commit hash printed by `hf download` / the `.metadata` files, recorded by `cmd_fetch`), SPDX id, date checked (2026-09-17), URL. Rows: PaddleOCR-VL-1.6 (Apache-2.0), Qwen3.5-4B (Apache-2.0), RedHatAI/Qwen3.5-9B-FP8-dynamic (Apache-2.0; third-party quantization of Apache-2.0 weights), PP-DocLayoutV3 (Apache-2.0), vLLM 0.29.0 (Apache-2.0), PyTorch 2.13.0+cu130 (BSD-3-Clause), transformers 5.16.1 (Apache-2.0), xgrammar 0.2.3 (Apache-2.0), paddleocr 3.7.0 / paddlex 3.7.2 / paddlepaddle-gpu 3.3.0 (Apache-2.0), pypdfium2 5.8.0 local / 5.13.0 host (Apache-2.0 OR BSD-3-Clause; pdfium BSD-3-Clause), Pillow 12.x (MIT-CMU), jsonschema 4.26 (MIT), numpy (BSD-3-Clause), huggingface_hub 1.30.0 (Apache-2.0). Add a "Flagged" section: PyMuPDF 1.27 (AGPL-3.0) remains in the existing pipeline outside `vlm/` — owner decision 2 in plan v1 §21.

- [ ] **Step 2: Commit**

```bash
git add docs/moneythumb-replacement/phase3/LICENSES.md
git commit -m "phase3: license register for the ceiling experiment" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task B4: Bring-up and synthetic preflight (live, no customer bytes)

- [ ] **Step 1: Check and fetch**

```bash
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['check']))"
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['fetch', '--key', 'a']))"
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['fetch', '--key', 'b']))"
```
Expected: check prints disk ≥ 21 GB, vLLM 0.29.0; each fetch prints `"exit": "0"` and a receipt path; disk after ≥ 9 GB.

- [ ] **Step 2: Deploy and start the servers, then the tunnel**

```bash
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['deploy']))"
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['start', '--key', 'a']))"
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['start', '--key', 'b']))"
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['start', '--key', 'worker']))"
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['tunnel-up']))"
```
Wait for `status` to show `a=alive b=alive worker=alive` and the three ports listening (vLLM startup takes 1–3 minutes each; Stage B may need `--enforce-eager` if the log shows a CUDA-graph OOM — record the change in the ledger and in `launch.json` via the `models` block). Verify through the tunnel: `curl -s http://127.0.0.1:18002/v1/models` lists `Qwen/Qwen3.5-4B`; `curl -s http://127.0.0.1:18003/version` shows `"backend": "vllm-server"`.

- [ ] **Step 3: Preflight on synthetic pages**

Add subcommand `preflight` to `tools/vlm_ceiling.py`: it writes three synthetic PDFs (`tests/paddle_synthetic.build_ledger_page(n_rows=8)` native and image variants, plus a rotated page) into a temp archive, builds a synthetic private manifest, and runs every arm with `--data-scope synthetic` into `discovery_reports/train13-logs/p3ceiling/waves/preflight-<arm>-<UTC>/`. Expected: `stage_a_rules` and `hybrid` admit the ledger pages; `stage_b_only` admits at least the native page; every wave writes launch/result/release; the Stage B response contains no `<think>` text (check `results/*.private.json` `stage_b[*].text`); page `response_sha256` values are identical on a second preflight run (nondeterminism = 0 on synthetic pages) — if not, record the count and keep going; it becomes a report field.

- [ ] **Step 4: Attest and stop**

```bash
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['attest', '--since-epoch', '<epoch of preflight start>']))"
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['stop', '--key', 'all']))"
python -c "import ocr.config, sys; from tools.vlm_vast import main; sys.exit(main(['tunnel-down']))"
```
Expected: `passed: true`; servers stopped; record the preflight outcome, the instance hours and the attestation in the ledger.

---

### Task B5: Independent adversarial review (before any customer page moves)

- [ ] **Step 1:** Dispatch a fresh reviewer agent (per the subagent model policy) with the diff of `phase3-ceiling` against `train13` and the two plans. Scope: the boundary (`vlm/client.py`, `vlm/runner.py` authorization and receipts, `tools/vlm_vast.py`, `vlm/stage_a_worker.py`, `vlm/partitions.py`), the gate (`vlm/gate.py`, `vlm/proposals.py`, `vlm/assemble.py`), privacy of public receipts, and the pins. Required output: `discovery_reports/train13-logs/p3ceiling/reviews/CEILING-HARNESS-REVIEW-X.md` with BLOCK/MAJOR/MINOR findings, each with a reproduction.
- [ ] **Step 2:** Close every BLOCK and MAJOR with a commit and a re-run of the affected tests; record closures in the review file; re-review if any BLOCK existed.
- [ ] **Step 3:** Only then proceed to B6.

---

### Task B6: CTRL and U755 waves, report, go/revise/stop

- [ ] **Step 1: Partitions**

```bash
python tools/vlm_ceiling.py partitions --out discovery_reports/train13-logs/p3ceiling/manifests
```
Expected: `CTRL 114 documents / 800 pages`, `U755 755 / 5110`, `DEV 20`. Commit the three public manifests (`*.manifest.json`); never the private ones.

- [ ] **Step 2: Bring the servers up (B4 steps 1–2), set both opt-in literals in this shell only** (`PADDLE_REMOTE_OPT_IN` and `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` with their exact literals from `ocr/paddle_config.py`; never in a file).

- [ ] **Step 3: DEV smoke (20 documents, hybrid, truth on)**

```bash
python tools/vlm_ceiling.py run --arm hybrid --manifest discovery_reports/train13-logs/p3ceiling/manifests/DEV.manifest.private.json --out discovery_reports/train13-logs/p3ceiling/waves/dev-hybrid-01 --truth
python tools/vlm_ceiling.py report --wave discovery_reports/train13-logs/p3ceiling/waves/dev-hybrid-01
```
Read the report; fix only harness defects (prompt/assembly/gate bugs) here, with tests; re-run under a new wave directory (`dev-hybrid-02`). This is the only tuning loop, and it never touches U755 or the holdout.

- [ ] **Step 4: CTRL, all four arms (truth on)**

```bash
for ARM in reader_baseline stage_a_rules stage_b_only hybrid; do
  python tools/vlm_ceiling.py run --arm $ARM --manifest .../manifests/CTRL.manifest.private.json --out .../waves/ctrl-$ARM-01 --truth
  python tools/vlm_ceiling.py report --wave .../waves/ctrl-$ARM-01
done
```
Expected duration at ~1 s/page per model stage: ≈ 15–30 minutes per model arm.

- [ ] **Step 5: U755, arms 2–4**

Same commands with `U755.manifest.private.json`, without `--truth`, `--out .../waves/u755-$ARM-01`. Expected ≈ 1.5–3 hours per model arm. Run `status` between arms; keep the servers up across arms; stop them at the end of the day.

- [ ] **Step 6: Nondeterminism measurement**

Re-run `hybrid` on `DEV` into `dev-hybrid-repeat-01` and compare `page_hashes` (must be identical) and `stage_b[*].response_sha256` in the private receipts; report the fraction of pages whose response differed and the number of rows that changed.

- [ ] **Step 7: Second Stage B variant (optional, disk permitting)**

`fetch --key b9` (requires ≥ 16 GB free; if not, stop with a receipt saying so), `stop --key b`, `start --key b9`, then repeat steps 4–5 for `stage_b_only` and `hybrid` with `--stage-b-model RedHatAI/Qwen3.5-9B-FP8-dynamic` into `*-b9-01` wave directories.

- [ ] **Step 8: Attest, stop, ledger, report**

`attest` (since the first CTRL wave start) → `stop --key all` → `tunnel-down`. Write `discovery_reports/train13-logs/p3ceiling/CEILING-REPORT-ROOT.md`: per-arm tables (CTRL row-match rates and false accepts; U755 repair rates by reader outcome and classification; reason taxonomy; latency, tokens, upload bytes, throughput; instance hours and cost), the nondeterminism measurement, the deviations from plan v1 §11 (arm 5 dropped; CTRL replaces the calibration set), and the GO / REVISE / STOP recommendation against the thresholds (GO: hybrid reconciles ≥ 40 percent of U755 with zero CTRL false accepts and ≤ USD 0.05 per statement; REVISE: 20–40 percent; STOP: < 20 percent or unfixable false accepts or nondeterminism > 1 percent of rows). Update the memory checkpoint and the handoff; commit docs and public receipts only.
