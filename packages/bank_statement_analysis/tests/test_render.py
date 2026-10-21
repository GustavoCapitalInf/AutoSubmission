import pytest

from ocr.render import markdown_to_html, promote_headers, render_fragment


def test_render_fragment_has_no_page_wrapper():
    frag = render_fragment("# Hello\n\nSome text.")
    assert "<h1>Hello</h1>" in frag
    assert "<!DOCTYPE html>" not in frag
    assert "<html" not in frag.lower()


def test_markdown_to_html_wraps_in_page_with_title():
    html = markdown_to_html("# Hello\n\nSome text.", title="chase.pdf")
    assert "<html" in html.lower()
    assert "<title>chase.pdf</title>" in html
    assert "<h1>Hello</h1>" in html
    assert "<p>Some text.</p>" in html


def test_markdown_to_html_passes_through_raw_html_tables():
    md = "Some text\n\n<table><tr><td>Date</td><td>Amount</td></tr></table>"
    html = markdown_to_html(md, title="x")
    assert "<table><tr><td>Date</td><td>Amount</td></tr></table>" in html


def test_markdown_to_html_includes_basic_styling():
    html = markdown_to_html("text", title="x")
    assert "<style>" in html


def test_promote_headers_promotes_allcaps_section_titles():
    md = "DEPOSITS AND ADDITIONS\nCHECKING SUMMARY\nCUSTOMER SERVICE INFORMATION"
    out = promote_headers(md)
    assert "## DEPOSITS AND ADDITIONS" in out
    assert "## CHECKING SUMMARY" in out
    assert "## CUSTOMER SERVICE INFORMATION" in out


def test_promote_headers_leaves_data_and_mixed_case_alone():
    md = (
        "01/02 Orig CO Name:Paymentech 1,000.00\n"        # has digits
        "Online Banking transfer from CHK 6973\n"          # mixed case
        "<table><tr><td>DATE</td></tr></table>\n"          # HTML
        "SALOMON MANAGEMENT GROUP INC ACCOUNT 000012345"   # has digits
    )
    out = promote_headers(md)
    assert "## " not in out


def test_promote_headers_excludes_company_and_person_names():
    # ALL-CAPS account-holder / entity lines must NOT become headings.
    md = (
        "SALOMON MANAGEMENT GROUP, INC.\n"   # comma + INC + GROUP
        "DBA SALOMON INSURANCE GROUP\n"      # DBA + GROUP
        "JPMORGAN CHASE BANK N.A."           # N.A.
    )
    out = promote_headers(md)
    assert "## " not in out


def test_promote_headers_promotes_titlecase_known_sections():
    # BofA-style Title-Case section headers should be promoted too.
    md = (
        "Account summary\n"
        "Deposits and other credits\n"
        "Withdrawals and other debits\n"
        "Deposits and other credits - continued"
    )
    out = promote_headers(md)
    assert "## Account summary" in out
    assert "## Deposits and other credits" in out
    assert "## Withdrawals and other debits" in out
    assert "## Deposits and other credits - continued" in out


def test_promote_headers_rendered_as_h2():
    html = markdown_to_html("DEPOSITS AND ADDITIONS\n\nSome content", title="x")
    assert "<h2>DEPOSITS AND ADDITIONS</h2>" in html


# --- Audit 2026-10-13, EXP-1: statement text is shown, never obeyed -------------------------------------------------
# A PDF's text layer is untrusted. Markup it prints is shown as text; only the bare table markup the visual-OCR rung
# prints its tables in passes through (exact, lower-case, attribute-free tags; the final review's finding 2), and the
# document's own header comment stays a comment.
# A normal statement renders exactly as before. Fabricated text only.

_NATIVE_SAMPLE = (
    "<!-- source: sample.pdf | pages: 2 | model: native-pdf-text | empty: 0 -->\n\n\n\n"
    "--- Page 1 ---\n\n"
    "CONTOSO BAKERY LLC\n"
    "DEPOSITS AND ADDITIONS\n"
    "03/02 ACH CREDIT FABRIKAM PAYROLL 1,250.00\n"
    "03/05 TRANSFER FROM SAMPLE & SONS 300.00\n"
    "    indented memo line\n\n"
    "| Date | Description | Amount |\n|---|---|---|\n| 03/09 | NORTHWIND SUPPLY | 75.10 |\n\n"
    "--- Page 2 ---\n\n"
    "Total deposits *2* items 1,550.00 <500 limit\n"
    "Ending balance $2,000.00\n"
)


def _body(page: str) -> str:
    return page[page.index("<body>\n") + len("<body>\n"):page.index("\n</body>")]


def test_a_normal_statement_renders_exactly_as_before():
    """The body the renderer produced before EXP-1 for this fabricated native statement, byte for byte."""
    assert _body(markdown_to_html(_NATIVE_SAMPLE, title="sample.pdf")) == (
        "<!-- source: sample.pdf | pages: 2 | model: native-pdf-text | empty: 0 -->\n\n"
        "<p>--- Page 1 ---</p>\n<p>CONTOSO BAKERY LLC</p>\n<h2>DEPOSITS AND ADDITIONS</h2>\n"
        "<p>03/02 ACH CREDIT FABRIKAM PAYROLL 1,250.00\n03/05 TRANSFER FROM SAMPLE &amp; SONS 300.00\n"
        "    indented memo line</p>\n"
        "<table>\n<thead>\n<tr>\n<th>Date</th>\n<th>Description</th>\n<th>Amount</th>\n</tr>\n</thead>\n"
        "<tbody>\n<tr>\n<td>03/09</td>\n<td>NORTHWIND SUPPLY</td>\n<td>75.10</td>\n</tr>\n</tbody>\n</table>\n"
        "<p>--- Page 2 ---</p>\n<p>Total deposits <em>2</em> items 1,550.00 &lt;500 limit\n"
        "Ending balance $2,000.00</p>"
    )


@pytest.mark.parametrize("markup", [
    "<img src=x onerror=\"document.title='INJECTED'\">",
    "<script>document.title='INJECTED'</script>",
    "<svg onload=\"document.title='INJECTED'\"></svg>",
    "<iframe src=\"https://example.invalid\"></iframe>",
    "<a href=\"https://example.invalid\">Statement checks passed</a>",
    "<div style=\"position:fixed;inset:0;background:white\">Statement checks passed</div>",
    "<!-- --><img src=x onerror=\"document.title='INJECTED'\">",
    "<form action=\"https://example.invalid\"><input name=a></form>",
])
@pytest.mark.parametrize("where", ["own line", "inline", "in a visual table"])
def test_markup_in_statement_text_is_shown_as_text(markup, where):
    if where == "own line":
        page = f"03/02 SAMPLE DEPOSIT 10.00\n\n{markup}\n\nEnding balance $10.00"
    elif where == "inline":
        page = f"03/02 SAMPLE DEPOSIT {markup} 10.00"
    else:
        page = f"<table><tr><td>03/02</td><td>SAMPLE {markup}</td><td>10.00</td></tr></table>"
    body = _body(markdown_to_html(f"--- Page 1 ---\n\n{page}", title="x"))
    for tag in ("<img", "<script", "<svg", "<iframe", "<a ", "<div", "<form", "<input", "<!--"):
        assert tag not in body.lower(), (tag, body)
    assert "&lt;" in body


def test_a_visual_ocr_table_still_renders_as_a_table():
    """The exact, attribute-free table markup the visual-OCR rung prints passes through; every line break spelling
    becomes `<br>`; entities are kept."""
    md = ("<table><thead><tr><th>Date</th><th>Description</th></tr></thead><tbody>"
          "<tr><td>03/02</td><td>CONTOSO &amp; SONS<br>A<br/>B<br />C</td></tr></tbody>"
          "<tfoot><tr><td>Total</td><td>10.00</td></tr></tfoot></table>")
    assert render_fragment(md) == (
        "<table><thead><tr><th>Date</th><th>Description</th></tr></thead><tbody>"
        "<tr><td>03/02</td><td>CONTOSO &amp; SONS<br>A<br>B<br>C</td></tr></tbody>"
        "<tfoot><tr><td>Total</td><td>10.00</td></tr></tfoot></table>")


# Final review of the audit, finding 2: the passthrough used to take any tag-shaped text whose first word was a table
# tag name, in any case, and drop the rest of it, so statement text lost what it printed between the brackets.
@pytest.mark.parametrize("text, shown", [
    ("01/02 DEPOSIT <TD SAMPLE BANK> 100.00", "<p>01/02 DEPOSIT &lt;TD SAMPLE BANK&gt; 100.00</p>"),
    ("01/02 PAYMENT <BR CONTOSO REF 1234> 50.00", "<p>01/02 PAYMENT &lt;BR CONTOSO REF 1234&gt; 50.00</p>"),
    ("01/02 TRANSFER <TR NORTHWIND> 25.00", "<p>01/02 TRANSFER &lt;TR NORTHWIND&gt; 25.00</p>"),
])
def test_statement_text_shaped_like_a_table_tag_keeps_its_words(text, shown):
    assert render_fragment(text) == shown


@pytest.mark.parametrize("tag", [
    '<td onclick="document.title=1">', '<th colspan="2">', '<table border="1">', "<tr class=x>", "<td >",
    "<TD>", "<Table>", "</TR>", "<BR>", "</br>", "<br >", "<br clear=all>", "<tbody\n>",
])
def test_a_table_tag_with_anything_more_or_in_capitals_is_shown_as_text(tag):
    body = render_fragment(f"<table><tr><td>03/02</td><td>SAMPLE {tag} FABRIKAM</td></tr></table>")
    assert body.startswith("<table><tr><td>03/02</td><td>SAMPLE &lt;") and body.endswith(
        " FABRIKAM</td></tr></table>")
    for name in ("onclick", "colspan", "border", "class", "clear"):
        if name in tag:
            assert f"{name}=" in body  # shown, not dropped
    assert body.count("<td>") == 2 and body.count("<tr>") == 1 and body.count("<br>") == 0


def test_angle_bracket_text_is_shown_not_hidden():
    """Before EXP-1 a browser hid `<SUPPLY>` and `<REF 1234>` as unknown tags; the analyst now sees them."""
    body = render_fragment("NORTHWIND <SUPPLY> ORDER <REF 1234> AND <500")
    assert body == "<p>NORTHWIND &lt;SUPPLY&gt; ORDER &lt;REF 1234&gt; AND &lt;500</p>"


def test_markup_in_code_text_displays_once_escaped():
    assert render_fragment("    memo <b>SAMPLE</b> & co") == "<pre><code>memo &lt;b&gt;SAMPLE&lt;/b&gt; &amp; co\n</code></pre>"
    assert render_fragment("ref `<b>` x") == "<p>ref <code>&lt;b&gt;</code> x</p>"


def test_a_hostile_source_name_cannot_close_the_header_comment():
    """The upload gate refuses `-->` in a file name, but `--!>` also closes an HTML comment: such a header is shown as
    text rather than kept as a comment."""
    md = ("<!-- source: a--!><img src=x onerror=alert(1)>b.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
          "\n\n\n\n--- Page 1 ---\n\nSAMPLE")
    body = _body(markdown_to_html(md, title="x"))
    assert "<img" not in body
    assert "<!--" not in body


def test_the_report_page_carries_its_content_security_policy():
    from ocr.render import REPORT_CSP_META

    page = markdown_to_html("SAMPLE", title="x")
    head = page.split("</head>", 1)[0]
    assert head.count(REPORT_CSP_META) == 1
    assert head.index('<meta charset="utf-8">') < head.index(REPORT_CSP_META)
    assert "sandbox" not in REPORT_CSP_META  # a meta tag cannot carry sandbox
