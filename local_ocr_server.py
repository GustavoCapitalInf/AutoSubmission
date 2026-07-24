"""Local OpenAI-compatible OCR server for baidu/Unlimited-OCR on AMD/ROCm.

This replaces the RunPod/vLLM endpoint with the model running on your own GPU
(RX 7800 XT, gfx1101). It speaks just enough of the OpenAI Chat Completions API
for this repo's client (`ocr/ocr_client.py`) — `GET /v1/models` and
`POST /v1/chat/completions` (streaming and non-streaming) — so the CLI and webapp
work unchanged. Point them at it with:

    OCR_BASE_URL=http://localhost:8000/v1
    OCR_API_KEY=EMPTY

vLLM-only request fields (`skip_special_tokens`, `vllm_xargs`) are accepted and
mapped where meaningful (ngram_size -> no_repeat_ngram_size, window_size ->
ngram_window) or ignored. The model runs via its own `trust_remote_code`
`model.infer(...)`, so there is no vLLM dependency.

Run:  HSA_OVERRIDE_GFX_VERSION=11.0.0 .venv/bin/python local_ocr_server.py
Env:  OCR_LOCAL_MODEL (default baidu/Unlimited-OCR), OCR_LOCAL_PORT (default 8000).
"""
from __future__ import annotations
import base64
import contextlib
import json
import os
import queue
import re
import shutil
import tempfile
import threading
import time
import uuid

from flask import Flask, Response, jsonify, request

MODEL_ID = os.environ.get("OCR_LOCAL_MODEL", "baidu/Unlimited-OCR")
PORT = int(os.environ.get("OCR_LOCAL_PORT", "8000"))

_model = None
_tokenizer = None
_load_lock = threading.Lock()
# model.infer is stateful/not thread-safe; serialize inference across requests.
_infer_lock = threading.Lock()


def _load_model():
    global _model, _tokenizer
    with _load_lock:
        if _model is not None:
            return
        import torch
        from transformers import AutoModel, AutoTokenizer

        print(f"[local-ocr] loading {MODEL_ID} ...", flush=True)
        t0 = time.time()
        tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        model = AutoModel.from_pretrained(
            MODEL_ID, trust_remote_code=True, use_safetensors=True,
            torch_dtype=torch.bfloat16, attn_implementation="eager",
        )
        _model = model.eval().cuda()
        _tokenizer = tok
        print(f"[local-ocr] loaded in {time.time()-t0:.0f}s", flush=True)


_DATA_URI_RE = re.compile(r"^data:image/\w+;base64,(.*)$", re.DOTALL)


def _extract_prompt_and_image(messages):
    """Pull the text prompt and the (base64) image out of the last user message,
    matching what ocr/ocr_client.py sends: a text block then an image_url block."""
    prompt, img_b64 = "<image>Free OCR.", None
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            btype = block.get("type")
            if btype == "text" and block.get("text"):
                prompt = block["text"]
            elif btype == "image_url":
                url = (block.get("image_url") or {}).get("url", "")
                m = _DATA_URI_RE.match(url)
                if m:
                    img_b64 = m.group(1)
    return prompt, img_b64


def _write_temp_image(img_b64: str):
    """Decode the base64 page image to a temp PNG. infer() takes a file path and
    calls os.makedirs(output_path) unconditionally, so we hand it a temp dir too."""
    tmp = tempfile.mkdtemp(prefix="local_ocr_")
    img_path = os.path.join(tmp, "page.png")
    with open(img_path, "wb") as f:
        f.write(base64.b64decode(img_b64))
    return tmp, img_path


def _run_ocr(prompt: str, img_b64: str, ngram_size: int, window_size: int) -> str:
    """Non-streaming (CLI) path. eval_mode=True returns the RAW decoded text with
    the model's own <|det|>label [x0,y0,x1,y1]<|/det|> region tags intact — the
    same shape the vLLM endpoint returned, which the client's embed_image_regions
    and the webapp's box overlays parse. (save_results mode instead strips those
    tags into a clean result.md, which kills the boxes.)"""
    _load_model()
    tmp, img_path = _write_temp_image(img_b64)
    try:
        with _infer_lock:
            result = _model.infer(
                _tokenizer,
                prompt=prompt,
                image_file=img_path,
                output_path=tmp,
                base_size=1024, image_size=640, crop_mode=True,
                max_length=32768,
                no_repeat_ngram_size=ngram_size, ngram_window=window_size,
                eval_mode=True,
            )
        return result if isinstance(result, str) else ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class _QueueWriter:
    """A file-like that turns writes into queue items — used to capture the
    model's TextStreamer, which prints generated text to stdout as tokens land."""
    def __init__(self, q: "queue.Queue") -> None:
        self._q = q

    def write(self, s: str) -> int:
        if s:
            self._q.put(s)
        return len(s)

    def flush(self) -> None:
        pass


def _run_ocr_stream(prompt: str, img_b64: str, ngram_size: int, window_size: int):
    """Streaming (webapp) path — yields raw det-tagged text chunks as the model
    generates them, for a live token-by-token fill. Runs infer() (NOT eval_mode,
    NOT save_results, tps_interval=0) in a worker thread with stdout redirected
    into a queue: in that mode infer's only output is its internal TextStreamer,
    which prints the raw text (EOS mapped to newline, no [TPS] noise) incrementally
    and writes no files. Generated tokens are identical to the eval_mode path, so
    streamed output matches the CLI byte-for-byte modulo trailing whitespace."""
    _load_model()
    tmp, img_path = _write_temp_image(img_b64)
    q: "queue.Queue" = queue.Queue()
    DONE = object()

    def worker():
        try:
            with _infer_lock:
                # redirect_stdout is process-global, but _infer_lock guarantees a
                # single in-flight infer, and nothing else writes stdout per-request.
                with contextlib.redirect_stdout(_QueueWriter(q)):
                    _model.infer(
                        _tokenizer,
                        prompt=prompt,
                        image_file=img_path,
                        output_path=tmp,
                        base_size=1024, image_size=640, crop_mode=True,
                        max_length=32768,
                        no_repeat_ngram_size=ngram_size, ngram_window=window_size,
                        tps_interval=0,
                    )
        except Exception as e:  # surface to the consumer
            q.put(e)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            q.put(DONE)

    threading.Thread(target=worker, daemon=True).start()
    while True:
        item = q.get()
        if item is DONE:
            return
        if isinstance(item, Exception):
            raise item
        yield item


def _extra_int(body, key, default):
    xargs = body.get("vllm_xargs") or {}
    try:
        return int(xargs.get(key, default))
    except (TypeError, ValueError):
        return default


app = Flask(__name__)


@app.get("/v1/models")
def list_models():
    return jsonify({
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local"}],
    })


@app.post("/v1/chat/completions")
def chat_completions():
    body = request.get_json(force=True)
    prompt, img_b64 = _extract_prompt_and_image(body.get("messages", []))
    if img_b64 is None:
        return jsonify({"error": {"message": "no image_url in request"}}), 400
    ngram_size = _extra_int(body, "ngram_size", 35)
    window_size = _extra_int(body, "window_size", 128)
    stream = bool(body.get("stream"))
    cid = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    if not stream:
        text = _run_ocr(prompt, img_b64, ngram_size, window_size)
        return jsonify({
            "id": cid, "object": "chat.completion", "created": created,
            "model": MODEL_ID,
            "choices": [{
                "index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": text},
            }],
        })

    # Stream raw det-tagged text chunk-by-chunk as the model generates, so the
    # webapp fills the page (and its region boxes) live as it reads.
    def _chunk(delta):
        return "data: " + json.dumps({
            "id": cid, "object": "chat.completion.chunk", "created": created,
            "model": MODEL_ID, "choices": [{"index": 0, "delta": delta}],
        }) + "\n\n"

    def sse():
        yield _chunk({"role": "assistant"})
        for piece in _run_ocr_stream(prompt, img_b64, ngram_size, window_size):
            yield _chunk({"content": piece})
        yield "data: " + json.dumps({
            "id": cid, "object": "chat.completion.chunk", "created": created,
            "model": MODEL_ID,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }) + "\n\n"
        yield "data: [DONE]\n\n"

    return Response(sse(), mimetype="text/event-stream")


if __name__ == "__main__":
    _load_model()  # fail fast + pay the load cost before serving
    print(f"[local-ocr] serving on http://localhost:{PORT}/v1", flush=True)
    app.run(host="0.0.0.0", port=PORT, threaded=True)
