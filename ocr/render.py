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
