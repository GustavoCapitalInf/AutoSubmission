"""Smoke test: send one identical page image to both servers and report status only.

    envs/vllm/bin/python artifacts/smoke_pair.py

Prints metadata only (HTTP status, finish reason, character counts, elapsed seconds). Page content is
never printed, so this is safe to run from the hosted coding session.
"""
from __future__ import annotations

import base64
import json
import pathlib
import time
import urllib.request

ROOT = pathlib.Path("/workspace/bank-statement-shootout")
PAGE = ROOT / "pages" / "Regions" / sorted(p.name for p in (ROOT / "pages" / "Regions").iterdir())[0] / "page-0004.png"

STAGE_A_PROMPT = (
    "Please output the layout information from the PDF image, including each layout element's bbox, "
    "its category, and the corresponding text content within the bbox."
)
STAGE_B_PROMPT = (
    "Transcribe ALL readable text in this page image. Do not summarize, interpret, calculate, "
    "classify financial transactions, or correct the source."
)


def ask(port: int, model: str, prompt: str, b64: str, extra: dict | None = None) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": prompt},
        ]}],
        "max_tokens": 2048,
        "temperature": 0,
        "seed": 0,
    }
    if extra:
        body.update(extra)
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as resp:
        payload = json.load(resp)
        status = resp.status
    choice = payload["choices"][0]
    text = choice["message"]["content"] or ""
    return {
        "port": port,
        "http": status,
        "finish_reason": choice.get("finish_reason"),
        "chars": len(text),
        "completion_tokens": payload.get("usage", {}).get("completion_tokens"),
        "seconds": round(time.time() - t0, 1),
    }


def main() -> int:
    b64 = base64.b64encode(PAGE.read_bytes()).decode()
    print(json.dumps({"page": PAGE.name, "bytes": PAGE.stat().st_size}), flush=True)
    print(json.dumps(ask(18013, "dotsmocr", STAGE_A_PROMPT, b64)), flush=True)
    print(json.dumps(ask(18022, "qwen3.8-27b-nvfp4", STAGE_B_PROMPT, b64,
                         {"chat_template_kwargs": {"enable_thinking": False}})), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
