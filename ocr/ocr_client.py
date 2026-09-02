from __future__ import annotations
import base64
import io
import re
import time
from PIL import Image
from .config import Settings, load_settings
from .truncation import PageText

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


# ---------------------------------------------------------------------------
# OQ1 = C (docs/moneythumb-replacement/PHASE2_RULINGS.md): quarantine the
# entire nine-function postprocess chain on every path. The default is raw
# evidence. Re-admission is per function, on that function's own census
# (docs/moneythumb-replacement/OCR_POSTPROCESS_CENSUS.md) + synthetic
# fixtures (tests/fixtures/ocr_postprocess/), after independent review.
# Nothing is re-admitted in Phase 2.0: ADMITTED_POSTPROCESS is empty and
# apply_admitted() is a no-op. `postprocess` itself stays importable (the
# census and its tests exercise it directly) but is called by NOTHING on the
# analysis path (`ocr_page`, below) or the display path (`ocr/render.py`).
# ---------------------------------------------------------------------------
POSTPROCESS_STATE = "quarantined"
ADMITTED_POSTPROCESS: tuple[str, ...] = ()

#: Every member `apply_admitted` is allowed to apply, keyed by name so a
#: future re-admission names a member rather than re-wiring a call chain.
_POSTPROCESS_MEMBERS = {
    "strip_det_tags": strip_det_tags,
    "strip_refusal_commentary": strip_refusal_commentary,
    "strip_placeholder_markers": strip_placeholder_markers,
    "strip_oversized_embedded_images": strip_oversized_embedded_images,
    "collapse_repeated_amounts": collapse_repeated_amounts,
    "collapse_repeated_page_numbers": collapse_repeated_page_numbers,
    "split_fused_header_row": split_fused_header_row,
    "repair_fused_amount_table": repair_fused_amount_table,
    "fix_amount_column_bleed": fix_amount_column_bleed,
}


def apply_admitted(text: str) -> str:
    """Apply exactly the members named in `ADMITTED_POSTPROCESS`, in the order
    they appear there. This is what the analysis path calls instead of
    `postprocess` — in Phase 2.0 `ADMITTED_POSTPROCESS` is empty, so this is a
    no-op and `text` returns unchanged. A future re-admission adds a name to
    the tuple; it never revives the whole chain."""
    for name in ADMITTED_POSTPROCESS:
        text = _POSTPROCESS_MEMBERS[name](text)
    return text


# ---------------------------------------------------------------------------
# OQ2 = YES: the no-statement-hardcodes / value-meaning-hardcodes protection
# extends into `ocr/`. Everything below chooses WHICH PIXELS ARE READ (page
# selection / render variant), never what a value means, and is declared here
# rather than discovered. `tests/test_no_statement_hardcodes.py`'s OCR_DIR
# scan asserts every issuer-named regex in `ocr/ocr_client.py`, `ocr/pipeline.py`
# and `ocr/render.py` is registered here; `tests/test_ocr_intake_furniture.py`
# pins each declared behavior to what it actually does.
# ---------------------------------------------------------------------------
INTAKE_FURNITURE = {
    "_TD_MARKERS_RE": {
        "issuer": "TD",
        "behavior": "detects the issuer's own printed page-1 banner text",
        "justification": (
            "a QR-code region on TD's page 1 derails generation; recognizing "
            "the issuer's own printed banner is what lets the pipeline choose "
            "a page-1 render variant that avoids the derailment"
        ),
        "scope": "detection only (feeds page-1 render-variant selection); "
                 "never reads or writes a money token",
        "pinned_by": "tests/test_ocr_intake_furniture.py",
    },
    "is_td_statement": {
        "issuer": "TD",
        "behavior": "the printed-banner test itself: True iff `_TD_MARKERS_RE` "
                     "matches the page text",
        "justification": (
            "a thin, named wrapper around the same detection `_TD_MARKERS_RE` "
            "performs; declared separately (review MAJOR-4) because it is the "
            "function other intake code actually calls"
        ),
        "scope": "detection only; never reads or writes a money token",
        "pinned_by": "tests/test_ocr_intake_furniture.py, tests/test_ocr_client.py",
    },
    "looks_truncated_td": {
        "issuer": "TD",
        "behavior": "True iff the page is a TD page-1 whose 'STATEMENT OF "
                     "ACCOUNT' banner printed but whose 'ACCOUNT SUMMARY' "
                     "caption did not — the QR-derailment signature",
        "justification": (
            "detects a printed STRUCTURAL SECTION CAPTION's absence, never a "
            "figure; the two substrings it tests for are never removed by "
            "any postprocess member, so this reads exactly the same "
            "on raw text as it would on cleaned text"
        ),
        "scope": "detection only (feeds recover_truncated_td_page's "
                 "candidate-read selection, below); never reads or writes a "
                 "money token",
        "pinned_by": "tests/test_ocr_intake_furniture.py, tests/test_ocr_client.py",
    },
    "_TD_RECOVERY_VARIANTS": {
        "issuer": "TD",
        "behavior": "a fixed, declared list of (dpi, mask_qr) render variants "
                     "tried in order until one recovers the page",
        "justification": (
            "which render variant avoids the QR derailment varies per "
            "statement; trying a fixed, declared list is page-selection, not "
            "value invention — no variant is chosen from the page's content"
        ),
        "scope": "render variant (dpi, mask flag) selection only, AND (review "
                 "MAJOR-4) selects which of up to five candidate re-OCR reads "
                 "is kept via `recover_truncated_td_page` (below), keyed on a "
                 "printed structural section caption ('ACCOUNT SUMMARY'), "
                 "never on a printed figure",
        "pinned_by": "tests/test_ocr_intake_furniture.py",
    },
    "recover_truncated_td_page": {
        "issuer": "TD",
        "behavior": "re-OCRs a truncated TD page-1 across `_TD_RECOVERY_"
                     "VARIANTS` in order and keeps the first read whose "
                     "'ACCOUNT SUMMARY' caption is present and no longer "
                     "flagged truncated",
        "justification": (
            "chooses among candidate reads on a printed structural section "
            "caption alone; no arithmetic, no value comparison, no candidate "
            "selected because it 'balances' anything — the same fail-closed "
            "shape as `_mask_qr` and `_TD_MARKERS_RE`, applied across reads "
            "instead of within one"
        ),
        "scope": "selects which of up to five candidate re-OCR reads is kept, "
                 "keyed on a printed structural section caption, never on a "
                 "printed figure",
        "pinned_by": "tests/test_ocr_intake_furniture.py, tests/test_ocr_client.py",
    },
    "_mask_qr": {
        "issuer": "TD",
        "behavior": "whites out a fixed rectangle of the page before re-render",
        "justification": (
            "the QR code + 'Go paperless' box occupies a fixed structural "
            "region (top-right corner) on every TD statement; masking pixels "
            "there never touches the body/table region where printed "
            "financial figures live"
        ),
        "scope": "pixel masking on a fixed fraction of the page "
                 "(60-100% width x 0-12% height); takes only an image, "
                 "never text, so it cannot depend on a printed figure",
        "pinned_by": "tests/test_ocr_intake_furniture.py",
    },
    "looks_missegmented": {
        "issuer": None,
        "behavior": "detects a standalone single-column amount table (a "
                    "column-split mis-segmentation signature) and triggers a "
                    "lower-DPI re-OCR of the page",
        "justification": (
            "a lone amount-only table never occurs in a correctly read "
            "statement; this is a structural OCR-layout artifact, not an "
            "issuer-specific rule — no issuer name or printed figure "
            "participates in the signature"
        ),
        "scope": "render DPI selection only, AND (review MAJOR-4) selects "
                 "which of two candidate re-OCR reads (`ocr/pipeline.py`'s "
                 "fallback-DPI branch) is kept, keyed on a table-shape "
                 "signature, never on a printed figure",
        "pinned_by": "tests/test_ocr_client.py",
    },
}


def _build_client(settings: Settings):
    """Build the OpenAI-compatible client for the visual rung — OQ3's gate.

    `check_endpoint` runs BEFORE the `openai` import and BEFORE any client is
    constructed: a refused endpoint raises `EndpointRefused` and nothing is
    built, nothing is sent. BOTH the endpoint class AND the opt-in are
    re-derived fresh here rather than trusted from `settings.endpoint_class`
    / `settings.remote_opt_in` (descriptive fields) — MINOR-2
    (PHASE2_P20SEAM_REVIEW.md): a hand-built `Settings(..., remote_opt_in=
    True)` used to reach a remote endpoint with the env literal never set,
    because only `endpoint_class` was re-derived. Re-deriving `remote_opt_in`
    too closes that: the ONLY way to a remote endpoint is the real
    `OCR_REMOTE_OPT_IN` env var, regardless of how `Settings` was built.
    There is exactly one endpoint per process: this function builds one
    client for one `base_url` and has no fallback list or second host to
    hop to — a refusal or a failure here ends the rung.
    """
    from .endpoint_policy import EndpointRefused, check_endpoint, remote_opt_in_from_env

    decision = check_endpoint(settings.base_url, opt_in=remote_opt_in_from_env())
    if not decision.allowed:
        raise EndpointRefused(decision, settings.base_url)

    from openai import OpenAI
    return OpenAI(base_url=settings.base_url, api_key=settings.api_key, timeout=settings.timeout)


# O-3: the only truncation evidence the endpoint itself offers. Both readers are
# deliberately defensive — a server (or a test double) that reports neither field
# must yield "no signal", never a false one. See ocr/truncation.py.
def _finish_reason(choice) -> str | None:
    """``choices[0].finish_reason``: 'stop' when the model finished, 'length'
    when it hit max_tokens mid-page. Absent on every chunk of a stream except
    the last."""
    value = getattr(choice, "finish_reason", None)
    return value if isinstance(value, str) and value else None


def _completion_tokens(response, current: int | None = None) -> int | None:
    """``usage.completion_tokens`` when the endpoint reports it (vLLM does on
    non-streamed responses; the bundled local_ocr_server.py never does)."""
    usage = getattr(response, "usage", None)
    value = getattr(usage, "completion_tokens", None) if usage is not None else None
    return value if isinstance(value, int) else current


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
    """Run OCR on one page image and return the model's raw markdown.

    OQ1 = C (Phase 2.0): the nine-function `postprocess` cleanup chain is
    quarantined on every path. This returns the model's completion string as
    received — det tags, refusal prose, placeholders, degenerate repeated
    amounts and fused table cells all included — passed only through
    `apply_admitted`, which is a no-op while `ADMITTED_POSTPROCESS` is empty.
    `embed_image_regions` is likewise not applied here: document pixels never
    enter the text the validator reads (F-2); the function stays importable,
    unwired, for a possible future display-only use.

    If `on_delta` is given, the request is streamed and each raw text chunk is
    passed to `on_delta(chunk)` as it arrives (for live display). The returned
    value is always the same raw text regardless of streaming.

    O-3: the return value is a `PageText` — a `str` carrying the model's
    completion signals (`finish_reason`, `usage.completion_tokens`, and the
    `max_tokens` ceiling that was requested) so `ocr/pipeline.py` can tell a
    complete page from one the model stopped writing. It is a `str` subclass
    precisely so nothing downstream has to change: every existing consumer, and
    every test double that returns a plain `str`, behaves exactly as before."""
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
            finish_reason = None
            completion_tokens = None
            if on_delta is None:
                resp = client.chat.completions.create(**kwargs)
                raw = resp.choices[0].message.content or ""
                finish_reason = _finish_reason(resp.choices[0])
                completion_tokens = _completion_tokens(resp)
            else:
                raw = ""
                for chunk in client.chat.completions.create(stream=True, **kwargs):
                    # Usage rides on a trailing choice-less chunk; read it first.
                    completion_tokens = _completion_tokens(chunk, completion_tokens)
                    if not chunk.choices:
                        continue
                    finish_reason = _finish_reason(chunk.choices[0]) or finish_reason
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        raw += delta
                        on_delta(delta)
            # OQ1 = C: no cleanup chain and no pixel embedding on the analysis
            # path. `apply_admitted` is a no-op in Phase 2.0 (ADMITTED_POSTPROCESS
            # is empty), so this is the model's raw completion string.
            return PageText(apply_admitted(raw), finish_reason=finish_reason,
                            completion_tokens=completion_tokens, max_tokens=_MAX_TOKENS)
        except Exception as e:  # transient network / server errors
            last_exc = e
            time.sleep(min(2 ** attempt, 8) * 0.1)
    raise last_exc
