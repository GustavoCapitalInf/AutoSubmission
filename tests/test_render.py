from PIL import Image

from ocr.render import (
    markdown_to_html, promote_headers, render_fragment, rendered_skeleton,
    render_boxed, REGION_COLORS,
)


def test_render_boxed_wraps_regions_with_colored_labels():
    raw = ("<|det|>title [10,10,90,40]<|/det|>ROYAL BANK OF CANADA"
           "<|det|>text [10,50,90,80]<|/det|>P.O. BOX 4047")
    out = render_boxed([raw])
    assert out.count('class="region"') == 2
    # region type label + its color both present
    assert '>title<' in out and '>text<' in out
    assert f"border-color:{REGION_COLORS['title']}" in out
    assert f"border-color:{REGION_COLORS['text']}" in out
    assert "ROYAL BANK OF CANADA" in out
    assert "P.O. BOX 4047" in out
    # det tags themselves are gone from the rendered output
    assert "<|det|>" not in out


def test_render_boxed_page_separator_and_plain_start():
    # No complete region tag yet -> still renders the partial text (no crash).
    out = render_boxed(["Just some text so far"])
    assert "Page 1" in out
    assert "Just some text so far" in out


def test_render_boxed_embeds_picture_region_when_image_given():
    img = Image.new("RGB", (1000, 1000), (200, 50, 50))
    raw = "<|det|>image [100,100,400,400]<|/det|>"
    out = render_boxed([raw], page_images=[img])
    assert '<img class="doc-image" src="data:image/png;base64,' in out


def test_rendered_skeleton_supports_region_toggle():
    skel = rendered_skeleton()
    assert "body.hide-regions .region" in skel
    assert ".region-tag" in skel


def test_render_fragment_has_no_page_wrapper():
    frag = render_fragment("# Hello\n\nSome text.")
    assert "<h1>Hello</h1>" in frag
    assert "<!DOCTYPE html>" not in frag
    assert "<html" not in frag.lower()


def test_rendered_skeleton_has_styled_live_root():
    skel = rendered_skeleton()
    assert '<div id="live-root"></div>' in skel
    assert "<style>" in skel
    assert "<!DOCTYPE html>" in skel


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
