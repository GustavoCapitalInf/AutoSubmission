"""Smoke test: send one identical page image to both servers and report status only.

    envs/vllm/bin/python artifacts/smoke_pair.py --page synthetic/pages/example.png

Prints metadata only (HTTP status, finish reason, character counts, elapsed seconds). Page content is
never printed, so this is safe to run from the hosted coding session.
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import time
import urllib.request

ROOT = pathlib.Path("/workspace/bank-statement-shootout")

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


def synthetic_page(page: pathlib.Path, root: pathlib.Path) -> bytes:
    """No customer-page default; even a symlink must stay in the fixture tree."""
    source = page.resolve(strict=True)
    if not source.is_relative_to(root.resolve(strict=True)) or source.suffix.lower() != ".png":
        raise ValueError("synthetic_png_required")
    raw = source.read_bytes()
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("synthetic_png_required")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", type=pathlib.Path, required=True)
    parser.add_argument("--synthetic-root", type=pathlib.Path, default=ROOT / "synthetic")
    args = parser.parse_args(argv)
    try:
        raw = synthetic_page(args.page, args.synthetic_root)
        b64 = base64.b64encode(raw).decode()
        print(json.dumps({"scope": "synthetic", "bytes": len(raw)}), flush=True)
        print(json.dumps(ask(18013, "dotsmocr", STAGE_A_PROMPT, b64)), flush=True)
        print(json.dumps(ask(18022, "qwen3.8-27b-nvfp4", STAGE_B_PROMPT, b64,
                             {"chat_template_kwargs": {"enable_thinking": False}})), flush=True)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
