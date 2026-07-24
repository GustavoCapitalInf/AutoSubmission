from __future__ import annotations
import base64
import io
import re
import time
from PIL import Image
from .config import Settings, load_settings

_TASK = "Free OCR."
_MAX_TOKENS = 4096
# Well-formed region tag: <|det|>label [x0,y0,x1,y1]<|/det|>
_DET_PAIR_RE = re.compile(r"<\|det\|>.*?<\|/det\|>")
# Orphan tag (no closing), e.g. "<|det|>footer [819, 811, 942, 825]" or "...]]"
_DET_ORPHAN_RE = re.compile(r"<\|det\|>\s*\w+\s*\[[^\]\n]*\]+")
# Any bare leftover tag.
_DET_BARE_RE = re.compile(r"<\|/?det\|>")
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
    keeping the transcribed content that follows each tag. Handles both well-formed
    pairs and orphan/unclosed tags (which the model emits around footers)."""
    text = _DET_PAIR_RE.sub("", text)
    text = _DET_ORPHAN_RE.sub("", text)
    text = _DET_BARE_RE.sub("", text)
    return text


def strip_refusal_commentary(text: str) -> str:
    """Remove Unlimited-OCR's occasional inline refusal commentary on graphics it
    can't parse (e.g. QR codes), which otherwise leaks into the markdown output."""
    return _REFUSAL_RE.sub("", text)


# The model's placeholder for a detected region it read as having no text (a logo,
# stamp, graphic). Casing/spacing varies: "[Non-Text]", "[NO TEXT]", "[No text]".
_PLACEHOLDER_RE = re.compile(r"\[\s*non?[-\s]?text\s*\]", re.IGNORECASE)


def strip_placeholder_markers(text: str) -> str:
    """Remove the model's '[Non-Text]' / '[No text]' region placeholders. Lines
    that are only a placeholder are dropped entirely; inline ones are removed in
    place. Real content is untouched."""
    out = []
    for line in text.splitlines():
        if _PLACEHOLDER_RE.fullmatch(line.strip()):
            continue  # a line that is just the placeholder -> drop it
        out.append(_PLACEHOLDER_RE.sub("", line))
    return "\n".join(out)


# A monetary token, and a run of 3+ such tokens separated only by whitespace.
_MONEY_TOKEN = r"-?\$?[\d,]+\.\d{2}"
_MONEY_RUN_RE = re.compile(rf"{_MONEY_TOKEN}(?:\s+{_MONEY_TOKEN}){{2,}}")


def collapse_repeated_amounts(text: str) -> str:
    """Collapse model repetition-degeneration: a run of 3+ bare, whitespace-only-
    separated money tokens where one value repeats >=3 times is replaced by that
    single dominant value. Legitimate amounts live in table cells (separated by
    </td><td>, never bare whitespace) or on lines with dates/descriptions, so this
    only fires on degenerate footer bursts, and a run of distinct amounts (no value
    repeated 3+ times) is left untouched."""
    from collections import Counter

    def repl(match: re.Match) -> str:
        tokens = re.findall(_MONEY_TOKEN, match.group(0))
        value, count = Counter(tokens).most_common(1)[0]
        return value if count >= 3 else match.group(0)

    return _MONEY_RUN_RE.sub(repl, text)


# A "Page N of M" (or "Page: N of M", "Page N/M") footer repeated consecutively.
_PAGE_DUP_RE = re.compile(
    r"(Page:?\s*\d+\s*(?:of|/)\s*\d+)(?:\s+\1)+", re.IGNORECASE
)


def collapse_repeated_page_numbers(text: str) -> str:
    """Collapse a page-number footer that the model duplicated consecutively
    (e.g. 'Page 4 of 10 Page 4 of 10') down to a single occurrence. Only exact
    consecutive repeats collapse (backreference), so distinct pages are untouched."""
    return _PAGE_DUP_RE.sub(r"\1", text)


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


# A monetary value at the very end of a cell, optionally preceded by other text.
# e.g. "ID:9531796 INDN:HEARTLAND SE CO -74.88" -> prefix + "-74.88".
_AMOUNT_BLEED_RE = re.compile(r"^(.+?)\s+(-?\$?[\d,]+\.\d{2})$", re.DOTALL)


def fix_amount_column_bleed(text: str) -> str:
    """Repair tables (BofA-style) where a wrapped transaction description bleeds
    into the Amount column, so the amount cell reads '<description tail> <money>'.
    In any table with an 'Amount' header, split such cells: keep only the trailing
    money in the amount cell and append the leading text to that row's description
    (the column immediately left of Amount). Cells that are money-only are untouched."""
    def fix_table(match: re.Match) -> str:
        table = match.group(0)
        rows = re.findall(r"<tr>.*?</tr>", table, re.DOTALL)
        if len(rows) < 2:
            return table
        header_cells = _CELL_RE.findall(rows[0])
        amount_idx = next(
            (i for i, c in enumerate(header_cells) if c.strip().lower() == "amount"),
            None,
        )
        if amount_idx is None or amount_idx < 1:
            return table
        desc_idx = amount_idx - 1

        changed = False
        new_rows = [rows[0]]
        for row in rows[1:]:
            cells = _CELL_RE.findall(row)
            if len(cells) <= amount_idx:
                new_rows.append(row)
                continue
            m = _AMOUNT_BLEED_RE.match(cells[amount_idx].strip())
            if m is None:
                new_rows.append(row)
                continue
            prefix, money = m.group(1).strip(), m.group(2)
            cells[amount_idx] = money
            existing_desc = cells[desc_idx].strip()
            cells[desc_idx] = f"{existing_desc} {prefix}".strip()
            new_rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            changed = True

        if not changed:
            return table
        return "<table>" + "".join(new_rows) + "</table>"

    return _TABLE_RE.sub(fix_table, text)


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


# Region types that are pictures (check scans, logos, figures, signatures) rather
# than text. The model tags them with 0-1000-normalized bounding boxes.
_IMAGE_DET_RE = re.compile(
    r"<\|det\|>(image|figure|picture|photo|chart|diagram|logo|signature)\s*"
    r"\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\](?:<\|/det\|>)?",
    re.IGNORECASE,
)


def _crop_data_uri(image: Image.Image, box_px) -> str:
    crop = image.convert("RGB").crop(box_px)
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def embed_image_regions(raw: str, page_image: Image.Image) -> str:
    """Replace picture regions (image/figure/check/logo/signature) in the raw
    output with the actual pixels cropped from the page, embedded as <img> — so
    e.g. TD check-image scans render inline instead of being dropped as text.
    Coordinates are 0-1000 per-axis normalized. Degenerate boxes are dropped."""
    W, H = page_image.size

    def repl(match: re.Match) -> str:
        label = match.group(1).lower()
        x0 = max(0, round(int(match.group(2)) / 1000 * W))
        y0 = max(0, round(int(match.group(3)) / 1000 * H))
        x1 = min(W, round(int(match.group(4)) / 1000 * W))
        y1 = min(H, round(int(match.group(5)) / 1000 * H))
        if x1 <= x0 or y1 <= y0:
            return ""
        uri = _crop_data_uri(page_image, (x0, y0, x1, y1))
        return f'\n\n<img class="doc-image" src="{uri}" alt="{label}" />\n\n'

    return _IMAGE_DET_RE.sub(repl, raw)


def _build_client(settings: Settings):
    from openai import OpenAI
    return OpenAI(base_url=settings.base_url, api_key=settings.api_key, timeout=settings.timeout)


def postprocess(raw: str) -> str:
    """Full cleanup chain applied to the model's raw output."""
    cleaned = strip_placeholder_markers(strip_refusal_commentary(strip_det_tags(raw)))
    cleaned = collapse_repeated_amounts(cleaned)
    cleaned = collapse_repeated_page_numbers(cleaned)
    return fix_amount_column_bleed(split_fused_header_row(cleaned))


def ocr_page(image: Image.Image, *, settings: Settings | None = None, client=None,
             on_delta=None) -> str:
    """Run OCR on one page image and return the cleaned markdown.

    If `on_delta` is given, the request is streamed and each raw text chunk is
    passed to `on_delta(chunk)` as it arrives (for live display). The returned
    value is always the fully-cleaned markdown regardless of streaming."""
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
    kwargs = dict(
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
    last_exc = None
    for attempt in range(max(1, settings.retries)):
        try:
            if on_delta is None:
                resp = client.chat.completions.create(**kwargs)
                raw = resp.choices[0].message.content or ""
            else:
                raw = ""
                for chunk in client.chat.completions.create(stream=True, **kwargs):
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        raw += delta
                        on_delta(delta)
            # Embed picture regions (crop from the page) before text det tags are stripped.
            raw = embed_image_regions(raw, image)
            return postprocess(raw)
        except Exception as e:  # transient network / server errors
            last_exc = e
            time.sleep(min(2 ** attempt, 8) * 0.1)
    raise last_exc
