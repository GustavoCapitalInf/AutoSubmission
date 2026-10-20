from ocr.document import StatementMarkdown


def test_to_markdown_provenance_and_separators():
    doc = StatementMarkdown(source_file="x.pdf", model="m", pages=["# A", "# B"])
    md = doc.to_markdown()
    assert md.startswith("<!-- source: x.pdf | pages: 2 | model: m | empty: 0 -->")
    assert "--- Page 1 ---" in md and "--- Page 2 ---" in md
    assert "# A" in md and "# B" in md


def test_to_markdown_marks_empty_pages():
    doc = StatementMarkdown(source_file="x.pdf", model="m", pages=["# A", "   "])
    md = doc.to_markdown()
    assert "empty: 1" in md
    assert "--- Page 2 (empty) ---" in md
