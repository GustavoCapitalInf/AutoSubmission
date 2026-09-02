from __future__ import annotations
import html
import re
import markdown

# A standalone section title: all uppercase letters (spaces/&/./-/' allowed, but
# NOT commas — those usually mark a company/person name), 3-50 chars, <=6 words,
# no digit, no HTML tag, at least 3 letters.
_HEADER_LINE_RE = re.compile(r"^[A-Z][A-Z &.'/\-]{2,49}$")

# Whole-word tokens that mark an entity/person name rather than a section title.
_NAME_TOKENS = {
    "INC", "INC.", "LLC", "L.L.C.", "LTD", "LTD.", "CORP", "CORP.", "CO", "CO.",
    "DBA", "GROUP", "N.A.", "N.A", "ASSOCIATION", "COMPANY", "TRUST", "ESTATE",
}

# Known statement section titles (lowercased), matched case-insensitively so
# Title-Case banks (BofA: "Account summary", "Deposits and other credits") get
# promoted too, not just ALL-CAPS ones (Chase). A trailing "- continued" /
# "(continued)" is tolerated.
_KNOWN_TITLES = {
    "account summary", "account activity", "deposits and other credits",
    "withdrawals and other debits", "total deposits and other credits",
    "total withdrawals and other debits", "your checking account",
    "your savings account", "checks", "service fees", "daily ledger balances",
    "daily balance summary", "deposits and additions", "electronic withdrawals",
    "checking summary", "savings summary", "checks paid", "transaction detail",
    "customer service information", "consolidated balance summary",
    "atm & debit card withdrawals", "atm & debit card summary",
    "service charge summary", "service charge detail", "overdraft protection",
    "interest summary", "fees", "assets", "total assets",
}
_CONTINUED_RE = re.compile(r"\s*[-(]\s*continued\s*\)?$", re.IGNORECASE)


def _is_known_title(s: str) -> bool:
    base = _CONTINUED_RE.sub("", s.strip()).strip().lower()
    return base in _KNOWN_TITLES


def _is_section_title(line: str) -> bool:
    s = line.strip()
    if _is_known_title(s):
        return True
    if not (3 <= len(s) <= 50):
        return False
    if "<" in s or ">" in s or "," in s:
        return False
    if any(ch.isdigit() for ch in s):
        return False
    words = s.split()
    if len(words) > 6:
        return False
    if any(w in _NAME_TOKENS for w in words):
        return False
    if sum(ch.isalpha() for ch in s) < 3:
        return False
    return bool(_HEADER_LINE_RE.match(s))


def promote_headers(markdown_text: str) -> str:
    """Promote standalone ALL-CAPS statement section titles (e.g.
    'DEPOSITS AND ADDITIONS', 'CHECKING SUMMARY') to '##' markdown headings so
    they render as styled headers. Conservative: skips lines with digits, HTML,
    mixed case, or that are already headings/table markup."""
    out = []
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("<!--"):
            out.append(line)
        elif _is_section_title(line):
            out.append(f"## {stripped}")
        else:
            out.append(line)
    return "\n".join(out)


_STYLE = """
:root { --fg:#1f2328; --muted:#57606a; --line:#d0d7de; --accent:#5F4CFE;
        --zebra:#f6f8fa; --head:#eef1f5; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
       color: var(--fg); line-height: 1.55; margin: 0; padding: 2rem 2.2rem;
       max-width: 980px; }
h1, h2, h3, h4 { line-height: 1.25; margin: 1.6em 0 .5em; font-weight: 650; }
h1 { font-size: 1.7rem; }
h2 { font-size: 1.25rem; color: var(--accent); border-bottom: 2px solid var(--line);
     padding-bottom: .25em; letter-spacing: .01em; }
h3 { font-size: 1.05rem; color: var(--muted); }
p { margin: .5em 0; }
hr { border: 0; border-top: 1px solid var(--line); margin: 1.5em 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92rem;
        box-shadow: 0 1px 2px rgba(0,0,0,.04); }
th, td { border: 1px solid var(--line); padding: .5rem .7rem; text-align: left;
         vertical-align: top; }
thead th, tr:first-child td { background: var(--head); font-weight: 650;
         position: sticky; top: 0; }
tbody tr:nth-child(even), tr:nth-child(even) { background: var(--zebra); }
/* Right-align cells that are purely monetary/numeric. */
td:last-child { font-variant-numeric: tabular-nums; }
code, pre { font-family: "SF Mono", "Cascadia Code", Consolas, monospace;
            font-size: .88rem; }
pre { background: var(--zebra); padding: 1rem; border-radius: 6px; overflow-x: auto; }
img.doc-image { max-width: 100%; height: auto; display: block; margin: .8em 0;
                border: 1px solid var(--line); border-radius: 4px; }
/* Region boxes (mirror the demo's rendered-with-boxes view). */
.page-sep { margin: 1.4rem 0 .6rem; font-size: .72rem; letter-spacing: .12em;
            text-transform: uppercase; color: var(--muted); }
.region { position: relative; border: 1.5px solid transparent; border-radius: 5px;
          padding: .45rem .6rem; margin: .85rem 0 .35rem; }
.region > :first-child { margin-top: 0; }
.region > :last-child { margin-bottom: 0; }
.region-tag { position: absolute; top: -.62rem; left: .5rem; font-size: .58rem;
              line-height: 1.05rem; text-transform: uppercase; letter-spacing: .06em;
              color: #fff; padding: 0 .35rem; border-radius: 3px; font-weight: 600; }
/* Toggled off: read the rendered text cleanly with no boxes. */
body.hide-regions .region { border-color: transparent !important; padding: 0; margin: .4rem 0; }
body.hide-regions .region-tag { display: none; }
"""

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{style}</style>
</head>
<body>
{body}
</body>
</html>
"""


def render_fragment(markdown_text: str) -> str:
    """Render markdown to just the HTML body fragment (no page wrapper/styles).
    Used for live incremental rendering into an already-styled container."""
    promoted = promote_headers(markdown_text)
    return markdown.markdown(promoted, extensions=["tables"])


def markdown_to_html(markdown_text: str, title: str = "") -> str:
    return _PAGE_TEMPLATE.format(title=html.escape(title), style=_STYLE,
                                 body=render_fragment(markdown_text))


def rendered_skeleton() -> str:
    """A full styled page with an empty '#live-root' container, loaded once into
    the viewer's iframe so live fragments can be injected without reloading."""
    return _PAGE_TEMPLATE.format(title="", style=_STYLE, body='<div id="live-root"></div>')


# Per-region colors, matching the document-panel overlay (app.js BOX_COLORS).
REGION_COLORS = {
    "title": "#ff5c5c", "header": "#ffb020", "text": "#5c8cff", "table": "#23c4a8",
    "footer": "#8b8b95", "figure": "#c77dff", "image": "#c77dff", "list": "#9d7bff",
    "page_number": "#8b8b95", "caption": "#23c4a8",
}
_PICTURE_LABELS = {"image", "figure", "picture", "photo", "chart", "diagram",
                   "logo", "signature"}
# A region tag with its label and 0-1000 normalized box: <|det|>label [x0,y0,x1,y1]<|/det|>
_REGION_SPLIT_RE = re.compile(
    r"<\|det\|>\s*(\w+)\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\](?:<\|/det\|>)?"
)


def _image_region_html(coords, page_image) -> str:
    from .ocr_client import _crop_data_uri
    w, h = page_image.size
    x0 = max(0, round(coords[0] / 1000 * w)); y0 = max(0, round(coords[1] / 1000 * h))
    x1 = min(w, round(coords[2] / 1000 * w)); y1 = min(h, round(coords[3] / 1000 * h))
    if x1 <= x0 or y1 <= y0:
        return ""
    return f'<img class="doc-image" src="{_crop_data_uri(page_image, (x0, y0, x1, y1))}" alt="image" />'


def _region_html(label: str, coords, content: str, page_image) -> str:
    # OQ1 = C: the display path never calls `postprocess` (or `apply_admitted`
    # — the quarantine covers analysis AND display alike). `content` is the
    # model's raw region text, rendered as-is.
    label = label.lower()
    color = REGION_COLORS.get(label, "#5c8cff")
    if page_image is not None and label in _PICTURE_LABELS:
        inner = _image_region_html(coords, page_image)
    else:
        inner = render_fragment(content)
    return (f'<div class="region" style="border-color:{color}">'
            f'<span class="region-tag" style="background:{color}">{html.escape(label)}</span>'
            f'{inner}</div>')


def _render_boxed_page(raw: str, page_image) -> str:
    # OQ1 = C: raw content only — no `postprocess` on the display path.
    parts = _REGION_SPLIT_RE.split(raw)
    regions = []
    for j in range(1, len(parts), 6):
        label, x0, y0, x1, y1, content = parts[j:j + 6]
        regions.append(_region_html(label, (int(x0), int(y0), int(x1), int(y1)),
                                     content, page_image))
    if not regions:
        # No complete region tags yet (very start of a page's stream): plain text.
        return render_fragment(raw)
    return "".join(regions)


def render_boxed(pages: list[str], page_images=None) -> str:
    """Render per-page raw OCR output into an HTML body fragment where each
    detected region is wrapped in a colored, labeled box (mirroring the demo's
    rendered-with-boxes view). `page_images`, when given (final render), lets
    picture regions embed the cropped image instead of a placeholder box."""
    out = []
    for i, raw in enumerate(pages):
        img = page_images[i] if page_images and i < len(page_images) else None
        out.append(f'<div class="page-sep">Page {i + 1}</div>')
        out.append(_render_boxed_page(raw, img))
    return "\n".join(out)
