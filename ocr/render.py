from __future__ import annotations
import html
import markdown

_STYLE = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 900px;
       margin: 2rem auto; padding: 0 1rem; line-height: 1.5; color: #1a1a1a; }
h1, h2, h3 { border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }
tr:nth-child(even) { background: #f7f7f7; }
"""

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{style}</style>
</head>
<body>
{body}
</body>
</html>
"""


def markdown_to_html(markdown_text: str, title: str = "") -> str:
    body = markdown.markdown(markdown_text, extensions=["tables"])
    return _PAGE_TEMPLATE.format(title=html.escape(title), style=_STYLE, body=body)
