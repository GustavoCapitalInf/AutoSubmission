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
_REFUSAL_RE = re.compile(
    r"The image (?:provided )?is a[^.]*\.\s*"
    r"It does not contain[^.]*\.\s*"
    r"Therefore,?\s*no textual content can be extracted from (?:this|the) image\.?",
    re.IGNORECASE,
)


def build_prompt() -> str:
    return f"<image>{_TASK}"


def strip_det_tags(text: str) -> str:
    """Remove Unlimited-OCR's <|det|>label [x0,y0,x1,y1]<|/det|> region annotations,
    keeping the transcribed content that follows each tag."""
    return _DET_TAG_RE.sub("", text)


def strip_refusal_commentary(text: str) -> str:
    """Remove Unlimited-OCR's occasional inline refusal commentary on graphics it
    can't parse (e.g. QR codes), which otherwise leaks into the markdown output."""
    return _REFUSAL_RE.sub("", text)


# Transaction-table column headers the model fuses into the first data row
# (e.g. "DATE01/02", "AMOUNT$1,000.00"). Matched longest-first so multi-word
# headers ("DATE PAID") win over their prefixes ("DATE").
_FUSED_HEADERS = sorted(
    ["DATE PAID", "DATE", "DESCRIPTION", "AMOUNT", "BALANCE",
     "CHECK NUMBER", "CHECK NO.", "CHECK NO"],
    key=len, reverse=True,
)
_TABLE_RE = re.compile(r"<table>.*?</table>", re.DOTALL)
_FIRST_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_CELL_RE = re.compile(r"<td>(.*?)</td>", re.DOTALL)


def _split_fused_cell(cell_text: str) -> tuple[str, str] | None:
    """If a cell is a header glued to a value with no separating space
    (the fusion signature), return (header, value); else None."""
    for header in _FUSED_HEADERS:
        if (
            cell_text.startswith(header)
            and len(cell_text) > len(header)
            and not cell_text[len(header)].isspace()
        ):
            return header, cell_text[len(header):]
    return None


def split_fused_header_row(text: str) -> str:
    """Repair Unlimited-OCR's transaction tables where the column-header row is
    merged into the first data row (every first-row cell is "<HEADER><value>").
    Splits that row back into a proper header row + a clean first data row.
    Only acts when EVERY first-row cell is fused, so already-correct headers and
    label/value summary rows are left untouched."""
    def fix_table(match: re.Match) -> str:
        table = match.group(0)
        row_match = _FIRST_ROW_RE.search(table)
        if row_match is None:
            return table
        cells = _CELL_RE.findall(row_match.group(1))
        if len(cells) < 2:
            return table
        splits = [_split_fused_cell(c) for c in cells]
        if not all(splits):  # require every cell to be fused
            return table
        header_row = "<tr>" + "".join(f"<td>{h}</td>" for h, _ in splits) + "</tr>"
        data_row = "<tr>" + "".join(f"<td>{v}</td>" for _, v in splits) + "</tr>"
        return table[:row_match.start()] + header_row + data_row + table[row_match.end():]

    return _TABLE_RE.sub(fix_table, text)


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
            return split_fused_header_row(
                strip_refusal_commentary(strip_det_tags(text))
            )
        except Exception as e:  # transient network / server errors
            last_exc = e
            time.sleep(min(2 ** attempt, 8) * 0.1)
    raise last_exc
