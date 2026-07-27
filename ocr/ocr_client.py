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


# Mis-segmentation signature. On tables with wide intra-description whitespace
# (e.g. Truist "Other withdrawals"), Unlimited-OCR reads the gap as a column
# break and splits the amounts off into their own standalone single-column
# "AMOUNT($)" table, divorced from the descriptions. A lone amount-only table
# never occurs in a correctly-read statement, so it's a safe signal to re-OCR
# the page at a lower DPI (which does not trip the false column break).
_ORPHAN_AMOUNT_TABLE_RE = re.compile(
    r"<table>\s*<tr>\s*<td[^>]*>\s*AMOUNT\s*\(\$\)\s*</td>\s*</tr>"
    r"(?:\s*<tr>\s*<td[^>]*>\s*-?\$?[\d,]+\.\d{2}\s*</td>\s*</tr>){2,}",
    re.IGNORECASE,
)
def looks_missegmented(text: str) -> bool:
    """True if the output shows the column-split mis-segmentation (a standalone
    single-column amount table). Used to trigger a lower-DPI re-OCR of the page."""
    return bool(_ORPHAN_AMOUNT_TABLE_RE.search(text))


# TD statement markers. TD's first page carries a QR code ("Go paperless"); at the
# tuned 300 DPI the model emits a refusal on the QR region and then stops early,
# skipping the ACCOUNT SUMMARY and the entire daily-activity body. It reads the
# whole page at 200 DPI, so the pipeline re-OCRs a truncated TD page there.
_TD_MARKERS_RE = re.compile(r"most convenient bank|td business|\btd bank\b", re.IGNORECASE)


def is_td_statement(text: str) -> bool:
    return bool(_TD_MARKERS_RE.search(text))


def looks_truncated_td(text: str) -> bool:
    """True for a TD page-1 read that stopped after the header block — the TD
    'STATEMENT OF ACCOUNT' banner is present but the ACCOUNT SUMMARY that always
    follows it on page 1 is missing (generation was derailed by the QR code)."""
    low = text.lower()
    return (is_td_statement(text) and "statement of account" in low
            and "account summary" not in low)


def _mask_qr(image: Image.Image) -> Image.Image:
    """White out TD's top-right corner (the QR code + 'Go paperless' green box)
    so the model doesn't emit a QR refusal that derails generation."""
    from PIL import ImageDraw
    im = image.copy()
    w, h = im.size
    ImageDraw.Draw(im).rectangle([int(w * 0.60), 0, w, int(h * 0.12)], fill="white")
    return im


# TD's first page is unstable across renders: the QR-code refusal makes the model
# stop after the header, and which render avoids it varies per statement (some read
# at 150 DPI, some at 200, some only with the QR masked out). Try these variants in
# order and keep the first that recovers the ACCOUNT SUMMARY. (dpi, mask_qr):
_TD_RECOVERY_VARIANTS = [(300, True), (250, True), (200, True), (200, False), (150, False)]


def recover_truncated_td_page(pdf_bytes: bytes, page_index: int, *, settings, client) -> str | None:
    """Re-OCR a truncated TD page across render variants; return the first full
    read (ACCOUNT SUMMARY present), or None if every variant still truncates."""
    from .rasterize import rasterize_page
    for dpi, mask in _TD_RECOVERY_VARIANTS:
        img = rasterize_page(pdf_bytes, page_index, dpi=dpi)
        if mask:
            img = _mask_qr(img)
        out = ocr_page(img, settings=settings, client=client)
        if not looks_truncated_td(out) and "account summary" in out.lower():
            return out
    return None


# A first-row cell where a column header is glued onto its first data value, e.g.
# "DATE04/06", "AMOUNT260.00", "DESCRIPTIONOrig CO...". The lookahead requires a
# value-like continuation so legit headers ("AMOUNT($)", "DATE PAID") never match.
_FUSED_HEADER_CELL_RE = re.compile(r"^(DATE|AMOUNT|BALANCE|DESCRIPTION)(?=[0-9A-Z][0-9a-z])")
_MONEY_CELL_RE = re.compile(r"^-?\$?[\d,]+\.\d{2}$")


def repair_fused_amount_table(text: str) -> str:
    """Repair a DATE|DESCRIPTION|AMOUNT transaction table where the model fused the
    header row into the first data row AND split a wrapped description into an
    extra column (Chase-style). split_fused_header_row only handles the case where
    every cell is fused; this handles the partial fusion + description spill.

    Normalizes every row to three columns: first cell = date, last cell = amount,
    everything between merged as the description. Only fires when the first row's
    leading cell is a fused DATE and its trailing cell is a fused AMOUNT (never a
    debit/credit/balance table), so other tables are left untouched."""
    def fix(match: re.Match) -> str:
        table = match.group(0)
        rows = re.findall(r"<tr>(.*?)</tr>", table, re.DOTALL)
        if len(rows) < 2:
            return table
        fc = _CELL_RE.findall(rows[0])
        if len(fc) < 3:
            return table
        h0 = _FUSED_HEADER_CELL_RE.match(fc[0].strip())
        hL = _FUSED_HEADER_CELL_RE.match(fc[-1].strip())
        if not (h0 and h0.group(1) == "DATE" and hL and hL.group(1) == "AMOUNT"):
            return table

        def unfuse(cell: str) -> str:
            m = _FUSED_HEADER_CELL_RE.match(cell.strip())
            return cell.strip()[len(m.group(1)):] if m else cell.strip()

        # Reconstruct the first data row hidden inside the fused header row.
        date0 = fc[0].strip()[len("DATE"):]
        amt0 = fc[-1].strip()[len("AMOUNT"):]
        desc0 = " ".join(x for x in (unfuse(c) for c in fc[1:-1]) if x)
        out = ["<tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr>",
               f"<tr><td>{date0.strip()}</td><td>{desc0}</td><td>{amt0.strip()}</td></tr>"]
        for row in rows[1:]:
            cells = [c.strip() for c in _CELL_RE.findall(row)]
            # Only collapse genuine transaction rows (last cell is money); leave
            # totals / "continued" / colspan rows as they are.
            if len(cells) >= 3 and _MONEY_CELL_RE.match(cells[-1]):
                desc = " ".join(c for c in cells[1:-1] if c)
                out.append(f"<tr><td>{cells[0]}</td><td>{desc}</td><td>{cells[-1]}</td></tr>")
            else:
                out.append("<tr>" + row + "</tr>")
        return "<table>" + "".join(out) + "</table>"

    return _TABLE_RE.sub(fix, text)


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
_DATA_IMG_RE = re.compile(r'<img\b[^>]*src="data:image/[^"]+"[^>]*>', re.IGNORECASE)


def _crop_data_uri(image: Image.Image, box_px) -> str:
    crop = image.convert("RGB").crop(box_px)
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def embed_image_regions(raw: str, page_image: Image.Image) -> str:
    """Replace picture regions (image/figure/check/logo/signature) in the raw
    output with the actual pixels cropped from the page, embedded as <img> — so
    e.g. TD check-image scans render inline instead of being dropped as text.
    Coordinates are 0-1000 per-axis normalized. Degenerate and oversized boxes
    are dropped: the model sometimes tags an entire disclosure page as an image,
    which creates huge base64 blobs with no underwriting value."""
    W, H = page_image.size
    page_area = W * H

    def repl(match: re.Match) -> str:
        label = match.group(1).lower()
        x0 = max(0, round(int(match.group(2)) / 1000 * W))
        y0 = max(0, round(int(match.group(3)) / 1000 * H))
        x1 = min(W, round(int(match.group(4)) / 1000 * W))
        y1 = min(H, round(int(match.group(5)) / 1000 * H))
        if x1 <= x0 or y1 <= y0:
            return ""
        crop_width = x1 - x0
        crop_height = y1 - y0
        crop_area = crop_width * crop_height
        width_frac = crop_width / W
        height_frac = crop_height / H
        if crop_area / page_area > 0.35 or (height_frac > 0.45 and width_frac > 0.15):
            return ""
        uri = _crop_data_uri(page_image, (x0, y0, x1, y1))
        if len(uri) > 25_000:
            return ""
        return f'\n\n<img class="doc-image" src="{uri}" alt="{label}" />\n\n'

    return _IMAGE_DET_RE.sub(repl, raw)


def strip_oversized_embedded_images(text: str, *, max_len: int = 25_000) -> str:
    """Drop very large embedded data-URI images from OCR markdown."""
    def repl(match: re.Match) -> str:
        return "" if len(match.group(0)) > max_len else match.group(0)

    return _DATA_IMG_RE.sub(repl, text)


def _build_client(settings: Settings):
    from openai import OpenAI
    return OpenAI(base_url=settings.base_url, api_key=settings.api_key, timeout=settings.timeout)


def postprocess(raw: str) -> str:
    """Full cleanup chain applied to the model's raw output."""
    cleaned = strip_placeholder_markers(strip_refusal_commentary(strip_det_tags(raw)))
    cleaned = strip_oversized_embedded_images(cleaned)
    cleaned = collapse_repeated_amounts(cleaned)
    cleaned = collapse_repeated_page_numbers(cleaned)
    cleaned = repair_fused_amount_table(split_fused_header_row(cleaned))
    return fix_amount_column_bleed(cleaned)


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
