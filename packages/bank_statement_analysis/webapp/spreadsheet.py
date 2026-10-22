"""Spreadsheet encoding for the downloads: each cell's formula escaping and the XLSX workbook. It reads rows and
knows nothing of a statement or a package."""
from __future__ import annotations

import io
import re
import zipfile
from datetime import UTC, datetime
from math import isfinite

from spreadsheet_safety import FORMULA_LEAD, NUMERIC_CELL, escape_formula


# The formula-injection rule (R-24) lives in `spreadsheet_safety`, which `batch.py` shares; these names stay
# importable from here.
_FORMULA_LEAD = FORMULA_LEAD
_NUMERIC_CELL = NUMERIC_CELL
_escape_formula = escape_formula


def escaped_rows(rows: list[tuple[str, str, object]]) -> list[tuple]:
    return [tuple(_escape_formula(cell) for cell in row) for row in rows]


#: Characters XML 1.0 forbids in a document (C0 controls other than tab, LF and CR; U+FFFE and U+FFFF) and lone
#: surrogates, which UTF-8 cannot encode. One of them in a cell made sheet1.xml ill-formed (the whole workbook
#: refused to open), and a lone surrogate made the download raise.
_XML_FORBIDDEN = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]")


def _xml_escape(value: object) -> str:
    """Text for an XLSX inline string (its only caller is `_xlsx_cell`). Each character XML forbids becomes U+FFFD, the
    replacement character: SUBSTITUTED, never deleted, so a leading control can never let a formula lead start the
    cell after `_escape_formula` has looked at it, and the cell keeps its length in UTF-16 units. The CSV and the JSON
    downloads keep the text as read."""
    return (
        _XML_FORBIDDEN.sub("�", str(value))
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


#: The most characters a spreadsheet cell holds (Excel's limit, counted in UTF-16 units).
XLSX_CELL_LIMIT = 32767


def _xlsx_text(value: object) -> str:
    """An inline string's text: the value, or, when it holds more than XLSX_CELL_LIMIT UTF-16 units (a character
    outside the Basic Multilingual Plane counts two, as Excel counts it), a pointer naming its length. Never cut: a
    cell over the limit makes Excel refuse the file at load, and its repair truncates the cell. The CSV and the JSON
    download keep such a value whole."""
    text = str(value)
    units = len(text.encode("utf-16-le", "surrogatepass")) // 2
    if units > XLSX_CELL_LIMIT:
        return f"Not shown: {units:,} characters, over the spreadsheet cell limit; see the JSON download."
    return text


def _xlsx_cell(ref: str, value: object) -> str:
    """One cell, typed: a bool is a boolean cell (checked first: a bool is an int), a finite int or float a number, so
    SUM and a pivot add the money; anything else, NaN, inf and every numeric-looking string included (a masked account
    number, a leading-zero reference), is an inline string. An inline string is never a formula; its text keeps
    `_escape_formula`'s apostrophe, which a Save As CSV carries on, so the cell stays inert when the sheet is written
    back out as text. A text over the spreadsheet cell limit is replaced whole by a pointer (`_xlsx_text`)."""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and isfinite(value):
        return f'<c r="{ref}"><v>{value!r}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(_xlsx_text(value))}</t></is></c>'


def _xlsx_column(index: int) -> str:
    """A 1-based column number as its spreadsheet letters (1 -> A, 27 -> AA)."""
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _xlsx_sheet(rows: list[tuple]) -> str:
    def cell(col: int, row: int, value: object) -> str:
        return _xlsx_cell(f"{_xlsx_column(col)}{row}", value)

    sheet_rows = ['<row r="1">' + cell(1, 1, "section") + cell(2, 1, "field") + cell(3, 1, "value") + "</row>"]
    for idx, row in enumerate(rows, start=2):
        # A table block (the posted credits, the package ledger) writes one row per item, each value in its own
        # column.
        sheet_rows.append(
            f'<row r="{idx}">' + "".join(cell(col, idx, value) for col, value in enumerate(row, start=1)) + "</row>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(sheet_rows) + "</sheetData></worksheet>"
    )


def rows_xlsx(rows: list[tuple[str, str, object]]) -> bytes:
    rows = escaped_rows(rows)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        z.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Extracted Data" sheetId="1" r:id="rId1"/></sheets></workbook>""")
        z.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""")
        z.writestr("xl/worksheets/sheet1.xml", _xlsx_sheet(rows))
        z.writestr("docProps/core.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dcterms="http://purl.org/dc/terms/">
<dcterms:created>{datetime.now(UTC).isoformat()}</dcterms:created></cp:coreProperties>""")
    return out.getvalue()
