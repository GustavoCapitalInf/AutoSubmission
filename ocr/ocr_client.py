from __future__ import annotations
import base64
import io
import re
import time
from PIL import Image
from .config import Settings, load_settings

_TASK = "Free OCR."
_MAX_TOKENS = 4096
_DET_TAG_RE = re.compile(r"<\|det\|>.*?<\|/det\|>")


def build_prompt() -> str:
    return f"<image>{_TASK}"


def strip_det_tags(text: str) -> str:
    """Remove Unlimited-OCR's <|det|>label [x0,y0,x1,y1]<|/det|> region annotations,
    keeping the transcribed content that follows each tag."""
    return _DET_TAG_RE.sub("", text)


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
                model=settings.model,
                messages=messages,
                temperature=0.0,
                max_tokens=_MAX_TOKENS,
                extra_body={
                    "skip_special_tokens": False,
                    "vllm_xargs": {
                        "ngram_size": settings.ngram_size,
                        "window_size": settings.window_size,
                    },
                },
            )
            text = resp.choices[0].message.content or ""
            return strip_det_tags(text)
        except Exception as e:  # transient network / server errors
            last_exc = e
            time.sleep(min(2 ** attempt, 8) * 0.1)
    raise last_exc
