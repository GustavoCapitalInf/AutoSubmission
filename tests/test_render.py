from ocr.render import markdown_to_html


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
