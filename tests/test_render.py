from ocr.render import markdown_to_html, promote_headers


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
