from __future__ import annotations
import base64
import io
import time
from PIL import Image
from .config import Settings, load_settings

_PROMPT = (
    "Extract the text from the above document as if you were reading it "
    "naturally. Return tables in HTML format. Return equations in LaTeX. "
    "Wrap watermarks in <watermark></watermark> and page numbers in "
    "<page_number></page_number>. Prefer ☐ and ☑ for checkboxes. "
    "Output only the document content as clean Markdown — no commentary, "
    "no code fences around the whole answer."
)


def build_prompt() -> str:
    return _PROMPT


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
                model=settings.model, messages=messages, temperature=0.0,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:  # transient network / server errors
            last_exc = e
            time.sleep(min(2 ** attempt, 8) * 0.1)
    raise last_exc
