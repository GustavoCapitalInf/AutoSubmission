from __future__ import annotations

import math
import re
from bisect import bisect_left
from functools import lru_cache
from statistics import median
from typing import NamedTuple, TypedDict

from .column_grid import find_columns, page_words, read_rows
from .document import StatementMarkdown


class _UnreadableTextLayer(Exception):
    """A page's text layer could not be extracted at all.

    MuPDF raises out of ``page.get_text(...)`` on structurally malformed
    documents — `FzErrorFormat: code=7: cycle in resources` is the class GEOM-1
    found on four archive documents, and on one and the same corrupt page
    `get_text("text")`/`("dict")` raise a builtin `RuntimeError` while
    `("blocks")`/`("words")` raise `pymupdf.mupdf.FzErrorFormat`, which does NOT
    descend from RuntimeError. Every `page.get_text` call IN THIS MODULE goes
    through `_page_text`, which converts those into THIS exception; each rung
    catches it and returns None.

    "In this module" is the exact scope and not a whole-path guarantee:
    `parse_native_woodforest` reaches MuPDF through
    `ocr/column_grid.py::page_words`, which is outside this guard and answers an
    unreadable page with an empty word list rather than a refusal (W3 §RUNGSEAM
    RS6.3). It is unreachable for this class today only because that rung gates
    on `_native_pages` first.

    Two properties matter and are the reason the conversion is a distinct class
    rather than a bare `except Exception` around each rung:

    * a rung refuses ONLY because the document's text layer is unreadable — a
      defect in a rung's own row logic, and a mistake in how a rung CALLS
      `get_text` (a misspelled keyword raises `TypeError`, an unknown mode
      raises `AssertionError`), still escape, loudly. `_page_text` catches only
      the classes MuPDF was measured to raise;
    * a refusal is whole-document. A partial read (skip the bad page, keep the
      rest) would hand a parser a statement with pages silently missing, and
      `parse_native_pdf_text`'s quorum gate would happily accept it.
    """


@lru_cache(maxsize=1)
def _mupdf_text_errors() -> tuple[type[BaseException], ...]:
    """The exception classes MuPDF raises out of `page.get_text`.

    Measured on the four crash documents rather than guessed (W3 §RUNGSEAM
    RS3.2): `RuntimeError` plus the `FzErrorBase` family, which is a sibling of
    RuntimeError and not a subclass, so both have to be named. Resolved lazily
    because this module deliberately imports PyMuPDF inside functions.

    If the `FzErrorBase` attribute ever moves, this returns the `RuntimeError`
    alone and the guard silently narrows — so
    `tests/test_native_text_unreadable.py` asserts the family IS resolved here
    instead of letting that pass unnoticed.
    """
    errors: list[type[BaseException]] = [RuntimeError]
    base = None
    for module_name in ("pymupdf.mupdf", "fitz.mupdf"):
        try:
            module = __import__(module_name, fromlist=["FzErrorBase"])
        except Exception:  # noqa: BLE001 - absence is the only thing that matters
            continue
        candidate = getattr(module, "FzErrorBase", None)
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            base = candidate
            break
    if base is not None and not issubclass(base, RuntimeError):
        errors.append(base)
    return tuple(errors)


def _page_text(page, *args, **kwargs):
    """``page.get_text(...)``, with MuPDF's failure made into a refusal."""
    try:
        return page.get_text(*args, **kwargs)
    except _mupdf_text_errors() as exc:
        raise _UnreadableTextLayer(f"{type(exc).__name__}: {exc}") from exc


class _PageRead(NamedTuple):
    """What the block extraction produced, and why it produced nothing.

    `refusal` is set only when MuPDF could not read the text layer, and it is
    the reason string, not a flag: without it a structurally corrupt PDF is
    indistinguishable from an ordinary scan everywhere downstream, which is the
    diagnostic the pre-guard crash used to supply by escaping.
    """

    pages: tuple[str, ...] | None
    refusal: str | None


@lru_cache(maxsize=4)
def _native_pages_cached(pdf_bytes: bytes) -> _PageRead:
    """The block extraction itself, memoised on the document's own bytes.

    The ladder in `native_statement` asks several extractors in turn and most of
    them start by reading the same page text, so an un-memoised
    `_native_pages` is re-extracted once per rung the document falls through —
    on every native-text document in the archive, every discovery run. Four
    entries is enough: the ladder works one document at a time. It is also what
    makes `text_layer_refusal` free: a caller asking why the ladder returned
    nothing hits this cache rather than re-reading the document.

    A TUPLE is returned inside `_PageRead`, and `_native_pages` copies it into a
    fresh list per call. `parse_native_navy_federal` and this module's Woodforest
    reader both append their structured block to `pages[0]`, and handing out the
    cached object would let one caller's edit become the next caller's input.
    """
    try:
        import fitz
    except Exception:
        return _PageRead(None, None)

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return _PageRead(None, None)

    pages: list[str] = []
    try:
        for number, page in enumerate(doc, start=1):
            lines: list[str] = []
            blocks = sorted(
                _page_text(page, "blocks"), key=lambda b: (round(b[1], 1), round(b[0], 1))
            )
            for block in blocks:
                text = " ".join(part.strip() for part in str(block[4]).splitlines() if part.strip())
                if text:
                    lines.append(text)
            pages.append("\n".join(lines))
    except _UnreadableTextLayer as refused:
        return _PageRead(None, f"page {number} {refused}")
    return _PageRead(tuple(pages), None)


def _native_pages(pdf_bytes: bytes) -> list[str] | None:
    pages = _native_pages_cached(pdf_bytes).pages
    return None if pages is None else list(pages)


def text_layer_refusal(pdf_bytes: bytes) -> str | None:
    """Why MuPDF could not read this PDF's text layer, or None if it could.

    The ladder answers `None` for a document it cannot read and for a document
    with nothing to read, which is correct — both mean "no native text" — but
    it makes a structurally corrupt PDF look like an ordinary scan. This is the
    channel for the difference: a caller that got `None` from
    `native_statement` and wants to say WHY asks here, and the answer is served
    from the same memoised read the ladder already did.

    A refusal is only ever raised by the extraction itself; a PDF that fails to
    open, or a missing PyMuPDF, answers None here as it always did.
    """
    return _native_pages_cached(pdf_bytes).refusal


_NAVY_ROW_DATE_RE = re.compile(r"^(\d{2}-\d{2})\s+(.*)$")
_NAVY_AMOUNT_BALANCE_RE = re.compile(
    r"^(.*?)([\d,]+\.\d{2})\s*(-)?\s+([\d,]+\.\d{2})\s*(-)?\s*$"
)
_NAVY_PERIOD_RE = re.compile(r"\d{2}/\d{2}/\d{2}\s+-\s+\d{2}/\d{2}/\d{2}")


class _NavyPendingRow(TypedDict):
    date: str
    description: list[str]
    amount: str | None
    balance: str | None


def _navy_transaction_rows(doc, account: str) -> tuple[list[str], list[str]]:
    """Recover Navy Federal's primary checking rows from the PDF's geometry.

    Generic block sorting loses row ownership because the date/description and
    amount/balance columns have slightly different baselines. Layout-sorted text
    preserves that ownership, including descriptions and amounts that wrap onto
    the next line or page.
    """
    rows: list[str] = []
    source_dates: list[str] = []
    pending: _NavyPendingRow | None = None
    active = False
    began = False

    def flush() -> None:
        nonlocal pending
        if pending is None:
            return
        amount = pending.get("amount")
        balance = pending.get("balance")
        if amount is not None and balance is not None:
            description = re.sub(
                r"\s+",
                " ",
                " ".join(pending["description"]),
            ).strip()
            description = description.replace("|", "/") or "Navy Federal transaction"
            rows.append(
                "NFCU_TX|{account}|{date}|{amount}|{balance}|{description}".format(
                    account=account,
                    date=pending["date"],
                    amount=amount,
                    balance=balance,
                    description=description,
                )
            )
        pending = None

    for page in doc:
        for raw_line in _page_text(page, "text", sort=True).splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue

            if line.startswith(f"Business Checking - {account}"):
                active = True
                continue
            if not active:
                continue
            if line.startswith(("Mbr Business Savings", "Bus Money Mkt Savings", "Savings")):
                flush()
                active = False
                continue
            if (
                line.startswith(
                    (
                        "Page ",
                        "Statement Period",
                        "Access No.",
                        "Statement of Account",
                        "For ",
                        "(Continued",
                        "Date Transaction Detail",
                    )
                )
                or _NAVY_PERIOD_RE.fullmatch(line)
            ):
                continue

            dated = _NAVY_ROW_DATE_RE.match(line)
            if dated:
                txn_date, remainder = dated.groups()
                if "Beginning Balance" in remainder:
                    flush()
                    began = True
                    continue
                if "Ending Balance" in remainder:
                    flush()
                    active = False
                    continue
                if not began:
                    continue
                flush()
                source_dates.append(txn_date)
                pending = {
                    "date": txn_date,
                    "description": [],
                    "amount": None,
                    "balance": None,
                }
                line = remainder

            if pending is None:
                continue

            values = _NAVY_AMOUNT_BALANCE_RE.match(line)
            if values and pending["amount"] is None:
                description, amount, _amount_negative, balance, balance_negative = values.groups()
                if description.strip():
                    pending["description"].append(description.strip())
                pending["amount"] = amount
                pending["balance"] = f"-{balance}" if balance_negative else balance
            elif not line.startswith(
                ("Average Daily Balance", "Items Paid", "Amount($)", "Balance($)")
            ):
                pending["description"].append(line)

    flush()
    return rows, source_dates


def parse_native_navy_federal(
    pdf_bytes: bytes, source_file: str = ""
) -> StatementMarkdown | None:
    """Native Navy Federal extraction with explicit, layout-aware ledger rows."""
    try:
        import fitz
    except Exception:
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    try:
        full_text = "\n".join(_page_text(page, "text", sort=True) or "" for page in doc)
    except _UnreadableTextLayer:
        return None
    upper = full_text.upper()
    if (
        "NAVY FEDERAL" not in upper
        or "SUMMARY OF YOUR DEPOSIT ACCOUNTS" not in upper
        or "BUSINESS CHECKING" not in upper
    ):
        return None
    account_match = re.search(r"Business Checking\s+(\d{6,})", full_text)
    if account_match is None:
        return None

    try:
        rows, source_dates = _navy_transaction_rows(doc, account_match.group(1))
    except _UnreadableTextLayer:
        return None
    pages = _native_pages(pdf_bytes)
    if not pages or not rows:
        return None

    structured = [
        "<!--",
        "SOURCE_POSTING_DATES_BEGIN",
        *(f"SOURCE_POSTING_DATE|{value}" for value in source_dates),
        "SOURCE_POSTING_DATES_END",
        "NFCU_NATIVE_TRANSACTIONS_BEGIN",
        *rows,
        "NFCU_NATIVE_TRANSACTIONS_END",
        "-->",
    ]
    pages[0] = pages[0] + "\n" + "\n".join(structured)
    return StatementMarkdown(
        source_file=source_file,
        model="native-pdf-text+navy-federal-layout",
        pages=pages,
    )


#: Woodforest's activity grid, by the names the bank prints above it.
_WF_GRID_LABELS = ("date", "credits", "debits", "balance", "description")
#: `MM-DD`, the only thing the Date column carries.
_WF_ANCHOR_RE = re.compile(r"\d{2}-\d{2}")
#: A printed money cell. The layout sets a trailing minus on overdrawn figures.
_WF_MONEY_RE = re.compile(r"-?[\d,]+\.\d{2}-?")
#: The printed headings that close the activity table. Each opens a different
#: block — cleared cheques, the account's own statistics, the daily balance
#: ladder, the reconciliation worksheet — and none of them is a posting row.
#: `Checks Cleared` is here because its rows DO look like postings: a date in
#: the Date column and an amount whose right edge lands in the Debits column,
#: with no balance beside it. The grid must end where the bank says it ends.
_WF_GRID_END = (
    "checks cleared",
    "account summary",
    "daily closing balance summary",
    "account reconciliation",
)
#: The `Summary of Accounts` region: its printed heading, and the two printed
#: labels that close it.
_WF_SUMMARY_OPEN = "summary of accounts"
_WF_SUMMARY_CLOSE = ("transactions",)
#: One account's summary row as the bank prints it: a product label ending in
#: the account number, then BALANCE FORWARD, TOTAL DEBITS, TOTAL CREDITS and
#: CLOSING BALANCE in that printed order.
_WF_SUMMARY_ROW_RE = re.compile(
    r"^(?P<label>.*?\d{6,})\s+(?P<figures>-?[\d,]+\.\d{2}(?:\s+-?[\d,]+\.\d{2}){3})$"
)

_WF_BEGIN = "WOODFOREST_GEOMETRY_BEGIN"
_WF_END = "WOODFOREST_GEOMETRY_END"


def _wf_lines(words) -> list[tuple[float, str]]:
    """Words grouped into visual lines, as `(baseline, text)`, top to bottom.

    Used only to find the printed labels that OPEN and CLOSE a region — the
    grid header, `Summary of Accounts`, `Checks Cleared`. Postings are read by
    `read_rows`, which does not group into lines at all, because on this
    layout a row and a visual line are not the same thing.
    """
    if not words:
        return []
    tolerance = max(1.0, median(word.height for word in words) * 0.6)
    ordered = sorted(words, key=lambda w: (w.mid_y, w.x0))
    groups: list[list] = [[ordered[0]]]
    for word in ordered[1:]:
        if abs(word.mid_y - groups[-1][-1].mid_y) <= tolerance:
            groups[-1].append(word)
        else:
            groups.append([word])
    lines: list[tuple[float, str]] = []
    for group in groups:
        group.sort(key=lambda w: w.x0)
        lines.append((group[0].mid_y, " ".join(w.text for w in group)))
    return lines


def _wf_summary_rows(pages_words: list[list]) -> list[str]:
    """The `Summary of Accounts` rows, recovered as whole printed lines.

    Flattening splits this row: on three archive documents the CLOSING BALANCE
    is emitted on a line of its own, so a reader that requires the four
    figures together finds no account at all and the document is declined —
    not because the bank printed nothing, but because the text layer broke one
    printed line into two.

    Every row in the region is returned, never just the first. The
    single-account guard downstream exists to fail CLOSED on a multi-account
    document, and a guard that counts only what it happened to find first
    fails open instead.
    """
    rows: list[str] = []
    # `inside` deliberately survives the page boundary. `_accounts` says why in
    # its own docstring: a summary block whose rows are split by a page break
    # is exactly the case the single-account guard exists for, and a reader
    # that closed the region at the end of a page would see one account on a
    # two-account document and let it through. A guard that fails open is
    # worse than no guard. The region is closed only by the labels the bank
    # prints to close it.
    inside = False
    for words in pages_words:
        for _y, text in _wf_lines(words):
            line = re.sub(r"\s+", " ", text).strip()
            lowered = line.lower()
            if not inside:
                if lowered.startswith(_WF_SUMMARY_OPEN):
                    inside = True
                continue
            if lowered in _WF_SUMMARY_CLOSE or lowered.startswith("date credits debits balance"):
                inside = False
                continue
            match = _WF_SUMMARY_ROW_RE.match(line)
            if match:
                rows.append(f"{match.group('label')} {match.group('figures')}")
    return rows


def _wf_grid_rows(pages_words: list[list]) -> tuple[list[str], list[str]]:
    """Every posting row with the money column the bank printed it in.

    Returns `(rows, refusals)`. A non-empty refusal list means some part of
    the grid did not read unambiguously, and the caller emits nothing at all:
    a partially geometry-read ledger mixed with a text-read one would be a
    reading no instrument could check.
    """
    rows: list[str] = []
    refusals: list[str] = []
    for number, words in enumerate(pages_words, start=1):
        headers = find_columns(words, _WF_GRID_LABELS)
        if not headers:
            continue
        columns = headers[0]
        stop_y = None
        for baseline, text in _wf_lines(words):
            if baseline <= columns.y:
                continue
            lowered = re.sub(r"\s+", " ", text).strip().lower()
            if any(lowered.startswith(marker) for marker in _WF_GRID_END):
                stop_y = baseline if stop_y is None else min(stop_y, baseline)
        page_rows, page_refusals = read_rows(
            words,
            columns,
            page=number,
            anchor="date",
            anchor_pattern=_WF_ANCHOR_RE,
            cell_pattern=_WF_MONEY_RE,
            cell_columns=("credits", "debits", "balance"),
            free_text="description",
            stop_y=stop_y,
        )
        refusals.extend(f"p{item.page} {item.reason}: {item.detail}" for item in page_refusals)
        for row in page_rows:
            credit = row.one("credits")
            debit = row.one("debits")
            balance = row.one("balance")
            if balance is None:
                # Not a posting row: the grid prints a balance on every one.
                # `Checks Cleared` is already excluded by its printed heading;
                # anything else reaching here is skipped, and the ledger then
                # answers to the bank's own totals either way.
                continue
            if (credit is None) == (debit is None):
                refusals.append(
                    f"p{row.page} amount_column_undecided: row {row.anchor!r} prints "
                    f"{'both' if credit is not None else 'neither'} money column"
                )
                continue
            rows.append("WOODFOREST_TX|{date}|{credit}|{debit}|{balance}|{description}".format(
                date=row.anchor,
                credit=credit or "",
                debit=debit or "",
                balance=balance,
                description=re.sub(r"\s+", " ", row.free_text).replace("|", "/").strip(),
            ))
    return rows, refusals


def parse_native_woodforest(pdf_bytes: bytes, source_file: str = "") -> StatementMarkdown | None:
    """Woodforest native text, plus the two facts flattening destroys.

    The grid prints `Date Credits Debits Balance Description`, and which of
    the two adjacent money columns a magnitude stood in is written NOWHERE
    else in the row — `analysis/woodforest.py` says so in its own docstring and
    recovers direction from the running balance instead, which works only
    while every balance reads. On three archive documents from one account the
    text layer emits each row's cells out of column order (description,
    balance, date, amount, and not consistently), so the row reader finds
    almost nothing; on two of those it also breaks the summary row in half.

    This extractor adds a structured block carrying (a) the summary rows as
    single printed lines and (b) each posting with its printed money column.
    The flattened page text is left exactly as it was, so detection — which
    reads the markdown, not this block — is unchanged, and a parser that
    ignores the block reads what it read before.

    Nothing here is published on its own: the block is evidence for
    `analysis/woodforest.py`, which still has to reconcile it against the
    bank's printed totals and balance chain before anything reaches a report.
    """
    try:
        import fitz
    except Exception:
        return None

    # The cheap test first, and it matters: this rung sits in the ladder every
    # native-text document passes through, so reading word boxes before
    # knowing whose statement it is would add a second full text extraction to
    # all ~3,300 of them for the sake of 18.
    pages = _native_pages(pdf_bytes)
    if not pages:
        return None
    upper = "\n".join(pages).upper()
    if "WOODFOREST" not in upper or "DATE CREDITS DEBITS BALANCE DESCRIPTION" not in upper:
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None
    try:
        pages_words = [page_words(page) for page in doc]
    except Exception:
        return None
    finally:
        try:
            doc.close()
        except Exception:
            pass

    grid_rows, refusals = _wf_grid_rows(pages_words)
    if refusals or not grid_rows:
        return None
    summary_rows = _wf_summary_rows(pages_words)
    if not summary_rows:
        return None

    block = [
        "<!--",
        _WF_BEGIN,
        *(f"WOODFOREST_SUMMARY|{row}" for row in summary_rows),
        *grid_rows,
        _WF_END,
        "-->",
    ]
    pages = list(pages)
    pages[0] = pages[0] + "\n" + "\n".join(block)
    return StatementMarkdown(
        source_file=source_file,
        model="native-pdf-text+woodforest-columns",
        pages=pages,
    )


def parse_native_pdf_text(pdf_bytes: bytes, source_file: str = "") -> StatementMarkdown | None:
    """Return native text for selectable-text PDFs when there is enough text.

    This is a fast first pass for digitally generated bank statements. Scanned
    PDFs still fall through to OCR.
    """
    pages = _native_pages(pdf_bytes)
    if not pages:
        return None
    total_chars = sum(len(p.strip()) for p in pages)
    text_pages = sum(1 for p in pages if len(p.strip()) >= 200)
    if total_chars < 500 or text_pages < max(1, len(pages) // 2):
        return None
    return StatementMarkdown(source_file=source_file, model="native-pdf-text", pages=pages)


# ---------------------------------------------------------------------------
# First Citizens Bank / Central Bank Operations - DAC02
# ---------------------------------------------------------------------------
#
# This layout prints its credit and debit detail as a three-column table —
# `Date`, `Description`, `Amount` — and the generic block reader above destroys
# it. `_native_pages` joins the LINES INSIDE a block with a single space, and
# MuPDF returns the whole description column as one block, so 71 printed
# descriptions arrive as one string with nothing marking where one ends and the
# next begins. The dates and amounts survive, because they are their own blocks
# and pair positionally, which is why `analysis/first_citizens.py` can close a
# statement to the cent while labelling every posting `Other Debit`
# (W3 §FIRSTCIT FI6 / FI14.1: twelve description-keyed production metrics read
# zero on 35 of 35 documents, `verified_revenue_*` among them).
#
# Nothing is lost in the PDF, only in the join: each printed line is a separate
# line inside the block, and each carries its own bounding box. This extractor
# recovers row ownership the way the `+wells` and `+navy-federal` extractors do
# — by geometry — and reports it ADDITIVELY. The generic pages are reused
# unchanged (they are literally `parse_native_pdf_text`'s own list), so every
# oracle, audit and parser that reads this document's text sees the same bytes
# it saw before, plus one appended block of rows at the end.
#
# Every rule below is read off the page rather than remembered:
#
#   * a TABLE is a band whose three cells say `Date`, `Description`, `Amount`;
#     the band immediately above it names the section. The deposits, cheque and
#     daily-balance grids print a different header (`Date Amount Date Amount
#     ...`, `Check No. Date Amount ...`, `Date Balance ...`) and are therefore
#     never read here at all;
#   * that header band is also the column RULER — the x of `Date`, the x of
#     `Description` and the right edge of `Amount` come from the document;
#   * a ROW is a band holding a `MM-DD` in the date column and a money cell
#     ending at the amount column's right edge. A description that contains a
#     date (`ACH Batch  03-13 Seq # 5041`) cannot be mistaken for one, because
#     the date is identified by its COLUMN, not by its shape;
#   * a WRAPPED description is a lone cell in the description column, within one
#     row pitch of the row above, and it joins that row. It cannot bleed across
#     rows (a row band is never lone), out of the table (`Total` prints a money
#     cell too, so it is not lone) or into the next section (a heading prints at
#     the date column's x, not the description column's).
#
# Anything that does not satisfy all of it ends the table, and a document from
# which no row is recovered is not claimed at all — the ladder falls through to
# the generic rung and the result is byte-identical to today's.

_FC_MMDD_RE = re.compile(r"\d{2}-\d{2}")
_FC_MONEY_RE = re.compile(r"\d[\d,]*\.\d{2}")

#: Printed rows sit ~9pt apart and a description's baseline is ~1.3pt above the
#: date and amount it belongs to, so cells within 3pt of each other print on one
#: row. Column positions are compared much more tightly: the columns are laid
#: out by the same template on every page.
_FC_BAND_TOLERANCE = 3.0
_FC_COLUMN_TOLERANCE = 1.0

#: The generic table vocabulary this bank prints above its described sections.
_FC_COLUMN_HEADER = ("date", "description", "amount")

FC_ROWS_BEGIN = "FC_NATIVE_TRANSACTIONS"
FC_ROWS_END = "FC_NATIVE_TRANSACTIONS_END"
FC_ROW_PREFIX = "FC_TX"

#: The signature of the family, and the same two structural facts
#: `analysis/first_citizens.py` detects on: the processing centre or the bank's
#: own name, plus the printed control record.
_FC_ISSUER_MARKERS = ("First Citizens", "Central Bank Operations")
_FC_SUMMARY_MARKERS = (
    "Your Account(s) At A Glance",
    "Statement Period Days Average Ledger Balance",
)


def _fc_bands(page) -> list[list[tuple[float, float, float, str, float]]]:
    """Every printed line on the page, grouped into the row it prints on.

    A cell is `(y-centre, x0, x1, text, height)`; a band is the cells sharing a
    row, ordered left to right. The height is the printed line box, which is
    what bounds a wrapped continuation in a table too short to measure its own
    row pitch (`_fc_rows`).
    """
    cells: list[tuple[float, float, float, str, float]] = []
    for block in _page_text(page, "dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if not text:
                continue
            x0, y0, x1, y1 = line["bbox"]
            cells.append(((y0 + y1) / 2.0, x0, x1, text, y1 - y0))
    cells.sort()
    bands: list[list[tuple[float, float, float, str, float]]] = []
    for cell in cells:
        if bands and abs(cell[0] - bands[-1][0][0]) <= _FC_BAND_TOLERANCE:
            bands[-1].append(cell)
        else:
            bands.append([cell])
    return [sorted(band, key=lambda cell: cell[1]) for band in bands]


def _fc_is_column_header(band: list[tuple[float, float, float, str, float]]) -> bool:
    return len(band) == 3 and tuple(
        cell[3].strip().lower() for cell in band
    ) == _FC_COLUMN_HEADER


def _fc_posting(
    band: list[tuple[float, float, float, str, float]],
    date_x0: float,
    description_x0: float,
    amount_x1: float,
) -> tuple[str, str, str] | None:
    """`(MM-DD, amount, description)` when this band prints one posting."""
    if not 2 <= len(band) <= 3:
        return None
    first, last = band[0], band[-1]
    if abs(first[1] - date_x0) > _FC_COLUMN_TOLERANCE:
        return None
    if abs(last[2] - amount_x1) > _FC_COLUMN_TOLERANCE:
        return None
    if _FC_MMDD_RE.fullmatch(first[3]) is None:
        return None
    if _FC_MONEY_RE.fullmatch(last[3]) is None:
        return None
    description = ""
    if len(band) == 3:
        middle = band[1]
        if abs(middle[1] - description_x0) > _FC_COLUMN_TOLERANCE:
            return None
        description = middle[3]
    return first[3], last[3], description


def _fc_render(section: str, date: str, amount: str, description: str) -> str | None:
    """One reported row, or nothing when a field would corrupt the encoding."""
    fields = (FC_ROW_PREFIX, section, date, amount, description)
    if any("|" in field for field in fields):
        return None
    return "|".join(fields)


def _fc_rows(page) -> list[str]:
    """Every posting the page prints in a `Date / Description / Amount` table."""
    bands = _fc_bands(page)
    rows: list[str] = []
    index = 0
    while index < len(bands):
        header = bands[index]
        index += 1
        if not _fc_is_column_header(header):
            continue
        # The band directly above the ruler names the section. A table the page
        # does not name is not read: nothing here guesses which section a run of
        # postings belongs to.
        if index < 2 or len(bands[index - 2]) != 1:
            continue
        section = bands[index - 2][0][3]
        date_x0, description_x0, amount_x1 = header[0][1], header[1][1], header[2][2]

        # The window a wrapped line has to fall inside, and where it comes from.
        # NOT from the header: the header sits a header-height above the first
        # row (measured 13.33-13.98pt against a 9.00-9.18pt row pitch), so
        # seeding the window from it opens ~1.6 pitches on the first row of
        # every table and would swallow a stray printed a whole line low. The
        # window is the table's OWN row pitch once two rows have set it, and
        # until then the row's own printed line box — which on this layout is
        # taller than the pitch (10.00-12.30pt) and still well short of the
        # header gap, so it admits every wrapped line measured (8.82-8.97pt)
        # and reaches no further than one printed line.
        pitch: float | None = None
        previous_y = header[0][0]
        current: list[str] | None = None
        current_height = 0.0
        table: list[list[str]] = []

        while index < len(bands):
            band = bands[index]
            gap = band[0][0] - previous_y
            posting = _fc_posting(band, date_x0, description_x0, amount_x1)
            if posting is not None:
                if table:  # a row-to-row gap; the header-to-first-row one is not
                    pitch = gap if pitch is None else min(pitch, gap)
                current = [posting[0], posting[1], posting[2]]
                current_height = band[0][4]
                table.append(current)
                previous_y = band[0][0]
                index += 1
                continue
            window = pitch + 1.0 if pitch is not None else current_height
            if (
                current is not None
                and len(band) == 1
                and abs(band[0][1] - description_x0) <= _FC_COLUMN_TOLERANCE
                and 0.0 < gap <= window
            ):
                current[2] = f"{current[2]} {band[0][3]}"
                previous_y = band[0][0]
                index += 1
                continue
            break

        for date, amount, description in table:
            rendered = _fc_render(section, date, amount, description.strip())
            if rendered is not None:
                rows.append(rendered)
    return rows


def parse_native_first_citizens(
    pdf_bytes: bytes, source_file: str = ""
) -> StatementMarkdown | None:
    """Native First Citizens text with the description column's rows recovered.

    Purely additive: the pages are `parse_native_pdf_text`'s own, so the same
    gate decides whether this document has usable native text at all and the
    generic text is preserved byte for byte. The recovered rows are appended to
    the last printed page, after everything the document prints, where no
    section any reader bounds can reach them.
    """
    base = parse_native_pdf_text(pdf_bytes, source_file=source_file)
    if base is None:
        return None
    full_text = "\n".join(base.pages)
    if not any(marker in full_text for marker in _FC_ISSUER_MARKERS):
        return None
    if not any(marker in full_text for marker in _FC_SUMMARY_MARKERS):
        return None

    try:
        import fitz
    except Exception:
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    rows: list[str] = []
    try:
        for page in doc:
            rows.extend(_fc_rows(page))
    except _UnreadableTextLayer:
        return None
    if not rows:
        return None

    pages = list(base.pages)
    printed = [index for index, page in enumerate(pages) if page.strip()]
    if not printed:
        return None
    last = printed[-1]
    pages[last] = "\n".join([pages[last], FC_ROWS_BEGIN, *rows, FC_ROWS_END])
    return StatementMarkdown(
        source_file=source_file,
        model="native-pdf-text+first-citizens-layout",
        pages=pages,
    )


def parse_native_desjardins(pdf_bytes: bytes, source_file: str = "") -> StatementMarkdown | None:
    """Return layout-preserved native text for Desjardins statements.

    Generic block extraction collapses Desjardins' amount columns into the
    description stream. PyMuPDF's sorted text preserves enough spacing and row
    continuation to parse the ledger deterministically.
    """
    try:
        import fitz
    except Exception:
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    try:
        pages = [_page_text(page, "text", sort=True) or "" for page in doc]
    except _UnreadableTextLayer:
        return None
    full_text = "\n".join(pages).upper()
    if (
        "CAISSE DESJARDINS" not in full_text
        or "STATEMENT OF ACCOUNT" not in full_text
        or "DESJARDINS CORPORATE BUILD-UP ACCOUNT" not in full_text
    ):
        return None
    if sum(len(page.strip()) for page in pages) < 500:
        return None
    return StatementMarkdown(source_file=source_file, model="native-pdf-text+desjardins-layout", pages=pages)


def parse_native_td_canada(pdf_bytes: bytes, source_file: str = "") -> StatementMarkdown | None:
    """Return native text for selectable-text TD Canada PDFs.

    TD Canada statements in this corpus are text PDFs. OCR can collapse their
    dense transaction pages, while native text blocks preserve one ledger row per
    block, so prefer this path when the markers are present.
    """
    pages = _native_pages(pdf_bytes)
    if not pages:
        return None

    full_text = "\n".join(pages).upper()
    if (
        "THE TORONTO-DOMINION BANK" not in full_text
        or "BUSINESS CHEQUING" not in full_text
        or "DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE" not in full_text
    ):
        return None
    return StatementMarkdown(source_file=source_file, model="native-pdf-text", pages=pages)


def parse_native_wells_fargo(pdf_bytes: bytes, source_file: str = "") -> StatementMarkdown | None:
    try:
        import fitz
    except Exception:
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    try:
        full_text = "\n".join(_page_text(page, "text") or "" for page in doc).upper()
    except _UnreadableTextLayer:
        return None
    if "WELLS FARGO" not in full_text or "TRANSACTION HISTORY" not in full_text:
        return None

    pages: list[str] = []
    try:
        for page in doc:
            lines: list[str] = []
            blocks = sorted(
                _page_text(page, "blocks"), key=lambda b: (round(b[1], 1), round(b[0], 1))
            )
            for block in blocks:
                text = " ".join(part.strip() for part in str(block[4]).splitlines() if part.strip())
                if text:
                    lines.append(text)

            rows = _wells_rows(page)
            if rows:
                lines.append("WF_NATIVE_TRANSACTIONS")
                lines.extend(rows)
                lines.append("WF_NATIVE_TRANSACTIONS_END")
            pages.append("\n".join(lines))
    except _UnreadableTextLayer:
        return None
    return StatementMarkdown(source_file=source_file, model="native-pdf-text+wells", pages=pages)


def _wells_rows(page) -> list[str]:
    import re

    words = _page_text(page, "words")
    cutoff_y = 735.0
    for x0, y0, x1, y1, text, *_ in words:
        if text.lower() in {"items", "account", "important", "totals", "the", "summary", "monthly"}:
            line_words = [
                t for xx0, yy0, xx1, yy1, t, *_ in words
                if abs(yy0 - y0) < 2.0 and 30 <= xx0 <= 590
            ]
            line = " ".join(line_words).lower()
            if (
                "items returned unpaid" in line
                or "account transaction fees" in line
                or "important account information" in line
                or line.startswith("totals ")
                or line.startswith("the ending daily balance")
                or line.startswith("summary of checks written")
                or line.startswith("monthly service fee summary")
            ):
                cutoff_y = min(cutoff_y, y0)
    line_map: dict[float, list[tuple[float, str]]] = {}
    for x0, y0, x1, y1, text, *_ in words:
        if not (130 <= y0 < cutoff_y and 45 <= x0 <= 585):
            continue
        key = round(y0 / 3.0) * 3.0
        line_map.setdefault(key, []).append((x0, text))

    rows: list[str] = []
    current: dict[str, str | None] | None = None

    def flush() -> None:
        nonlocal current
        if current and current.get("date") and current.get("description"):
            rows.append(
                "WF_TX|{date}|{description}|{credit}|{debit}|{balance}".format(
                    date=current.get("date") or "",
                    description=re.sub(r"\s+", " ", current.get("description") or "").strip(),
                    credit=current.get("credit") or "",
                    debit=current.get("debit") or "",
                    balance=current.get("balance") or "",
                )
            )
        current = None

    for y in sorted(line_map):
        words_line = sorted(line_map[y])
        text = " ".join(t for _, t in words_line)
        if not text or text.startswith((
            "Date ",
            "Check ",
            "Number ",
            "Description ",
            "Deposits/",
            "Withdrawals/",
            "Ending ",
            "Totals ",
            "The Ending Daily Balance",
        )):
            continue
        date = next((t for x, t in words_line if x < 95 and re.fullmatch(r"\d{1,2}/\d{1,2}", t)), None)
        desc = " ".join(t for x, t in words_line if 135 <= x < 395)
        credit = " ".join(t for x, t in words_line if 395 <= x < 452 and re.search(r"\d", t))
        debit = " ".join(t for x, t in words_line if 452 <= x < 520 and re.search(r"\d", t))
        balance = " ".join(t for x, t in words_line if x >= 520 and re.search(r"\d|-", t))

        if date:
            flush()
            current = {"date": date, "description": desc, "credit": credit, "debit": debit, "balance": balance}
        elif current and desc:
            current["description"] = ((current.get("description") or "") + " " + desc).strip()
            if credit and not current.get("credit"):
                current["credit"] = credit
            if debit and not current.get("debit"):
                current["debit"] = debit
            if balance:
                current["balance"] = balance
    flush()
    return rows


# ---------------------------------------------------------------------------
# The printed row: giving a described ledger back the column flattening welds
# ---------------------------------------------------------------------------
#
# `_native_pages` reads MuPDF BLOCKS and joins the lines inside a block with a
# single space. A block is MuPDF's grouping, not a printed row, so where one
# block's lines are printed on several rows that join welds tokens from
# different rows into one line — and no reader can find the boundary again,
# because there is nothing in the text to find. Measured with
# `tools/desccols_census.py` over the run of record's 3,380 documents: 3,156 of
# the 3,189 that hold native text weld at least one line. The weld is the
# flattening's default, not a family.
#
# On MOST documents the weld is harmless: an address paragraph welds its own
# lines and nobody else's. It becomes a wrong ANSWER only on a described ledger
# grid, where the layer emits the grid cells and the description cells as two
# streams and flushes one against the other, so a row's span (its date to its
# amount) comes to hold another posting's merchant text. W3 §DESCATTRIB
# measured that harm and closed it by REFUSING to publish a welded span; the
# text it refused is still in the document, and this rung is how it comes back
# — by reading the printed rows out of the line boxes the flattening threw
# away, so a row's description is its own by construction rather than by a
# rule over a welded string.
#
# WHAT IS EMITTED. One line per printed ROW, its cells in printed reading
# order; every line of the page that is not inside a repaired grid is emitted
# exactly as `_native_pages` emits it, in the same place. So a page with no
# repairable grid is byte-identical, and on a page with one, only the grid's
# own lines move.
#
# THE GATES, and why each is here. All of them fail CLOSED: a region that does
# not satisfy every one is left exactly as the flattening left it, and a
# document where nothing is repaired is not claimed at all, so the ladder falls
# through to the generic rung and the result is byte-identical to today's.
#
#   G1  an ANCHOR column. A row STARTS at a band whose leftmost cell shares an
#       x with the region's first band; a band indented strictly to the right
#       of it CONTINUES the row above. A band that starts to the LEFT ends the
#       region — the page has moved on to something else.
#   G2  at least three row starts. Two bands are not a grid, they are a
#       coincidence, and this rung has no business rewriting a coincidence.
#   G3  at least three rows carry a money cell, and those cells' right edges
#       agree: a printed right-aligned money column, which is what makes the
#       region a ledger rather than an indented paragraph.
#   G4  at least three rows carry a DESCRIPTIVE cell — one that is neither the
#       row's anchor nor its money. Without one there is no description and
#       nothing to give back.
#   G5  the region actually WELDS: some block spans more than one of its bands
#       and carries a descriptive cell. Without this the flattening already
#       prints one line per row and the repair would be a no-op that rotated
#       every affected document's cache key for nothing.
#   G6  no block has lines both inside and outside the region. A block that
#       straddles the boundary cannot be half re-serialised and half left
#       alone, and guessing which half is which is exactly the kind of repair
#       this platform refuses. The whole DOCUMENT is refused. G6 is REDUNDANT
#       with G7 and is kept for the fast, comprehensible refusal rather than
#       for correctness: measured, removing it alone changes no answer,
#       because a half-serialised block either duplicates or drops tokens and
#       G7 then refuses the page. `tools/desccols_mutate.py` records that as a
#       surviving mutant on purpose, with the pair mutated together to show
#       what they hold between them.
#   G7  TOKEN CONSERVATION. The page's whitespace-separated tokens must be the
#       same multiset before and after. Only line boundaries and within-line
#       order may move; nothing may be invented, dropped or altered. The check
#       is on the emitted text, so it is a proof rather than an argument.
#   G8  the money cell is the row's LAST printed cell. This is the gate that
#       decides whether the repair can help at all, and it is worth stating in
#       full: a reader's span runs from a row's date to the first figure after
#       it, so the description is recoverable only where the amount is printed
#       after everything else the row says. Where a template prints the amount
#       on the row's first line and the merchant detail BELOW it, re-serialising
#       moves the detail no closer to the span, changes the document's text for
#       no gain, and — measured on this archive — costs one document its
#       daily-balance grid. Templates of that shape are declined here.
#
#       It also subsumes the multi-column case entirely, which is why there is
#       no separate gate for one. A balance ladder or a cheque list printed
#       side by side carries several money cells per row, and a row's FIRST
#       money can only be its LAST printed cell when it is the only one — so
#       G8 excludes the whole class. An explicit `at most one money cell per
#       row` gate was written first and `tools/desccols_mutate.py` proved it
#       changed no answer; it is deleted, and the equivalence is pinned as a
#       test over every arrangement of up to five cells.
#   G9  no line of the region is REPEATED PAGE FURNITURE — text another page
#       of the same document prints at the same band position. A repaired row
#       carries every cell printed on its band left of its money, so a running
#       header, a footer or a column caption that happens to sit on a
#       posting's band would be folded into that posting's description, and
#       the card's own WORD-box oracle cannot see it: that oracle reads a row's
#       truth from the words printed between its date and its amount, which is
#       exactly where the absorbed line lands. So the shape is refused rather
#       than described. The refusal is the REGION's — the ledger it sits in
#       falls back to the flattening's own lines, in place, and no line is
#       repaired, dropped or moved.
#  G10  no line of the region lies horizontally outside the ledger's own
#       columns — left of the anchor column or right of the widest money edge.
#       The same reasoning one axis over: what sits beside a ledger is not part
#       of a row of it, and a row that reaches past its own money column is not
#       the arrangement this rung reads.
#
# Nothing above names an institution, a product or a merchant: the region is
# found by where the ink is, and the same code reads any bank that prints a
# described ledger in this arrangement.

#: A printed money cell, in the shared money grammar's plainest printed form.
#: It is used to CLASS a cell, never to read a figure — nothing in this module
#: parses a number.
_ROW_MONEY_RE = re.compile(r"-?\$?(?:[0-9][0-9,]*\.[0-9]{2}|\.[0-9]{2})-?$")

#: How far apart two cells' left edges may be and still be the same column.
#: The same reasoning as `_FC_COLUMN_TOLERANCE`: a template lays its columns
#: out identically on every page, so a column is tight, and only the ROW
#: grouping needs to be generous.
_ROW_COLUMN_TOLERANCE = 1.0

#: Two bands are not a grid. Three printed rows are the smallest thing this
#: rung will call one.
_ROW_GRID_MINIMUM = 3


class _PrintedLine(NamedTuple):
    """One printed line, with the block MuPDF grouped it into."""

    block: int
    top: float
    bottom: float
    left: float
    right: float
    text: str


def _line_box(line: object) -> tuple[float, float, float, float] | None:
    """A printed line's box as four finite numbers, or None if it is malformed.

    `line["bbox"]` unguarded raised three different exceptions out of this
    module — `KeyError`, `ValueError: not enough values to unpack` and
    `TypeError: unsupported operand type(s) for -` — for a missing key, a box
    of three numbers and a box of strings. The wave rule is that a refusal is
    an answer and an exception is not, so every one of those shapes is a
    refusal here (the page keeps the flattening's own text). A box that is not
    four FINITE numbers, or that is inverted or has no height, is refused for
    the same reason: the band arithmetic below subtracts these, and a
    degenerate box makes its answer meaningless rather than wrong-looking.
    """
    if not isinstance(line, dict):
        return None
    bbox = line.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    numbers: list[float] = []
    for value in bbox:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        numbers.append(number)
    x0, y0, x1, y1 = numbers
    if x1 < x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _printed_lines(page) -> list[_PrintedLine] | None:
    """Every printed line of the page with its box, or None to REFUSE the page.

    None is the answer for a page whose `get_text("dict")` is not the shape
    MuPDF documents: a block, line or span that is not a mapping, a missing
    `blocks`, `lines` or `spans` key, a line with no spans at all, or a box
    `_line_box` refuses. The caller answers None with the flattening's own
    text for that page, so a malformed page is left exactly as today rather
    than crashing the OCR stage for that document. It is not reachable on
    today's PyMuPDF — the archive run exercised this path on every native-text
    document and raised nothing — and that is precisely the case the
    fail-closed rule exists for.

    A line whose spans print only whitespace is NOT malformed: it is a blank
    printed line, skipped exactly as the flattening skips it, and G7 refuses
    the page if that skip were ever to lose a token.
    """
    read = _page_text(page, "dict")
    if not isinstance(read, dict):
        return None
    blocks = read.get("blocks")
    if not isinstance(blocks, (list, tuple)):
        return None
    lines: list[_PrintedLine] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            return None
        if block.get("type") != 0:
            continue
        block_lines = block.get("lines")
        if not isinstance(block_lines, (list, tuple)):
            return None
        for line in block_lines:
            box = _line_box(line)
            if box is None:
                return None
            spans = line.get("spans")
            if not isinstance(spans, (list, tuple)) or not spans:
                return None
            pieces: list[str] = []
            for span in spans:
                if not isinstance(span, dict):
                    return None
                piece = span.get("text", "")
                if not isinstance(piece, str):
                    return None
                pieces.append(piece)
            text = "".join(pieces).strip()
            if not text:
                continue
            x0, y0, x1, y1 = box
            lines.append(_PrintedLine(index, y0, y1, x0, x1, text))
    return lines


def _shares_a_band(top: float, bottom: float,
                   other_top: float, other_bottom: float) -> bool:
    """Do two printed boxes sit on the same row of a page?

    An OVERLAP test — at least half the shorter box — rather than a point
    tolerance, because a tolerance is a constant nobody can justify across type
    sizes and this has to hold for a template nobody has seen. This is the ONE
    definition of a band in this module: `_row_bands` applies it down a page
    and `_repeated_furniture` applies it across pages, so "the same band
    position" means the same thing in both places.
    """
    return (min(bottom, other_bottom) - max(top, other_top)
            >= 0.5 * min(bottom - top, other_bottom - other_top))


def _row_bands(lines: list[_PrintedLine]) -> list[list[int]]:
    """The lines grouped into the printed rows they share, top to bottom.

    The band's extent only ever NARROWS to the lines already in it, so one tall
    outlier cannot chain a band into the row below it.
    """
    order = sorted(range(len(lines)), key=lambda i: (lines[i].top, lines[i].left))
    bands: list[list[int]] = []
    top = bottom = None
    for position in order:
        line = lines[position]
        if top is None or not _shares_a_band(top, bottom, line.top, line.bottom):
            bands.append([position])
            top, bottom = line.top, line.bottom
        else:
            bands[-1].append(position)
            top, bottom = max(top, line.top), min(bottom, line.bottom)
    return [sorted(band, key=lambda p: lines[p].left) for band in bands]


def _repeated_furniture(
    pages: list[list[_PrintedLine] | None],
) -> list[frozenset[int]]:
    """Which of each page's lines are REPEATED PAGE FURNITURE, page by page.

    A line is furniture here when ANOTHER page of the same document prints the
    same text at the same band position: the running header, the running
    footer, the column caption a template repeats down the document. Same text,
    same band — `_shares_a_band` applied across pages rather than down one, so
    the rule that groups a row is the rule that recognises a repeat and there
    is no second tolerance to justify.

    This is a detection of a SHAPE, not of a vocabulary: nothing here names a
    bank, a caption or a phrase, and a document whose pages print nothing twice
    marks nothing.

    Bounded rather than quadratic: the occurrences of one text are sorted by
    their top edge and only the window that can possibly overlap is scanned,
    because a box that starts below another's bottom cannot share its band.
    """
    where: dict[str, list[tuple[float, float, int]]] = {}
    for index, lines in enumerate(pages):
        for line in lines or ():
            where.setdefault(line.text, []).append((line.top, line.bottom, index))
    tallest: dict[str, float] = {}
    for text, seen in where.items():
        seen.sort()
        tallest[text] = max(bottom - top for top, bottom, _page in seen)

    marked: list[frozenset[int]] = []
    for index, lines in enumerate(pages):
        found: set[int] = set()
        for position, line in enumerate(lines or ()):
            seen = where[line.text]
            window = bisect_left(seen, (line.top - tallest[line.text], -math.inf, -1))
            for top, bottom, other in seen[window:]:
                if top >= line.bottom:
                    break
                if other != index and _shares_a_band(line.top, line.bottom, top, bottom):
                    found.add(position)
                    break
        marked.append(frozenset(found))
    return marked


def _candidate_regions(lines, bands) -> list[tuple[int, list[int]]]:
    """`(end band, [row-start band, ...])` for each run G1/G2 admit."""
    lead = [lines[band[0]].left for band in bands]
    regions: list[tuple[int, list[int]]] = []
    index = 0
    while index < len(bands):
        if len(bands[index]) < 2:
            index += 1
            continue
        anchor = lead[index]
        starts, end = [index], index + 1
        while end < len(bands):
            if abs(lead[end] - anchor) <= _ROW_COLUMN_TOLERANCE:
                if len(bands[end]) < 2:
                    break
                starts.append(end)
            elif lead[end] < anchor:
                break
            end += 1
        if len(starts) >= _ROW_GRID_MINIMUM:
            regions.append((end, starts))
            index = end
        else:
            index += 1
    return regions


def _described_rows(lines, bands, end: int, starts: list[int],
                    furniture: frozenset[int] = frozenset()) -> list[list[int]] | None:
    """The region's rows, or None where G3/G4/G8/G9/G10 refuse it."""
    rows = []
    for order, start in enumerate(starts):
        stop = starts[order + 1] if order + 1 < len(starts) else end
        rows.append([p for band in range(start, stop) for p in bands[band]])

    edges, described = [], 0
    for row in rows:
        money = [p for p in row if _ROW_MONEY_RE.match(lines[p].text)]
        if money:
            if money[0] != row[-1]:
                return None                                    # G8
            edges.append(lines[money[0]].right)
        if any(p != row[0] and p not in money for p in row):
            described += 1
    if len(edges) < _ROW_GRID_MINIMUM or described < _ROW_GRID_MINIMUM:
        return None                                            # G3 / G4
    common = max(edges, key=lambda edge: sum(
        1 for other in edges if abs(other - edge) <= _ROW_COLUMN_TOLERANCE))
    if sum(1 for edge in edges
           if abs(edge - common) <= _ROW_COLUMN_TOLERANCE) < _ROW_GRID_MINIMUM:
        return None                                            # G3
    if any(position in furniture for row in rows for position in row):
        return None                                            # G9
    left = min(lines[row[0]].left for row in rows)
    right = max(edges)
    if any(lines[position].right < left - _ROW_COLUMN_TOLERANCE
           or lines[position].left > right + _ROW_COLUMN_TOLERANCE
           for row in rows for position in row):
        return None                                            # G10
    return rows


def _printed_row_page(page, flattened: str,
                      furniture: frozenset[int] = frozenset()) -> str | None:
    """The page with its described ledgers re-read by row, or None to refuse.

    Returns `flattened` UNCHANGED when the page holds nothing this rung may
    repair, which is the fallback the whole design rests on — and that is also
    the answer for a page with no printed lines at all and for one whose boxes
    `_printed_lines` refuses as malformed.

    `furniture` is the page's repeated-furniture positions (G9), which only a
    whole DOCUMENT can know; a caller with one page in hand passes none and
    gets the other nine gates.
    """
    return _printed_row_text(_printed_lines(page), flattened, furniture)


def _printed_row_text(lines: list[_PrintedLine] | None, flattened: str,
                      furniture: frozenset[int] = frozenset()) -> str | None:
    """`_printed_row_page` on lines already read, so a page is read once."""
    if not lines:
        return flattened
    bands = _row_bands(lines)
    blocks: dict[int, list[int]] = {}
    for position, line in enumerate(lines):
        blocks.setdefault(line.block, []).append(position)
    band_of = {p: index for index, band in enumerate(bands) for p in band}

    regions = []
    for end, starts in _candidate_regions(lines, bands):
        rows = _described_rows(lines, bands, end, starts, furniture)
        if rows is None:
            continue
        members = {p for row in rows for p in row}
        anchors = {row[0] for row in rows}
        welded = False
        for positions in blocks.values():
            inside = [p for p in positions if p in members]
            if not inside:
                continue
            if len(inside) != len(positions):
                return None                                    # G6
            if len({band_of[p] for p in inside}) > 1 and any(
                    p not in anchors and not _ROW_MONEY_RE.match(lines[p].text)
                    for p in inside):
                welded = True                                  # G5
        if welded:
            regions.append(rows)
    if not regions:
        return flattened

    claimed = {p for rows in regions for row in rows for p in row}
    units = [(round(min(lines[p].top for p in positions), 1),
              round(min(lines[p].left for p in positions), 1),
              " ".join(lines[p].text for p in positions))
             for positions in blocks.values() if positions[0] not in claimed]
    units.extend((round(min(lines[p].top for p in row), 1),
                  round(min(lines[p].left for p in row), 1),
                  " ".join(lines[p].text for p in row))
                 for rows in regions for row in rows)
    units.sort()
    text = "\n".join(unit[2] for unit in units)
    if sorted(text.split()) != sorted(flattened.split()):
        return None                                            # G7
    return text


def parse_native_printed_rows(
    pdf_bytes: bytes, source_file: str = ""
) -> StatementMarkdown | None:
    """Native text whose described ledger rows are read from the line boxes.

    The pages start as `parse_native_pdf_text`'s own, so the same quorum
    decides whether the document has usable native text at all and every page
    this rung does not repair is preserved byte for byte. A document where no
    page changes is NOT claimed — it falls through to the generic rung, whose
    answer it would have reproduced exactly.
    """
    base = parse_native_pdf_text(pdf_bytes, source_file=source_file)
    if base is None:
        return None
    try:
        import fitz
    except Exception:
        return None
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    pages = list(base.pages)
    try:
        # Read every page's boxes ONCE, then decide. G9 asks whether a line
        # repeats at the same band on another page, which no single page can
        # answer — and reading each page twice to ask it would pay the dict
        # read, this rung's whole cost, a second time on every native-text
        # document in the archive.
        printed = [_printed_lines(page) for page in document]
        if len(printed) > len(pages):
            return None
        furniture = _repeated_furniture(printed)
        for index, lines in enumerate(printed):
            repaired = _printed_row_text(lines, pages[index], furniture[index])
            if repaired is None:
                return None
            pages[index] = repaired
    except _UnreadableTextLayer:
        return None
    except Exception:  # noqa: BLE001 — a refusal is an answer, an exception is not
        # `_page_text` converts the exception classes MuPDF raises TODAY; this
        # rung reads `get_text("dict")` on every native-text document in the
        # archive, so a future binding that raises a class outside that family
        # would crash the OCR stage for the document instead of falling
        # through to the generic rung. Refusing is always available and always
        # correct here: the caller's next rung reproduces today's answer.
        return None
    finally:
        # Closed like `parse_native_woodforest` does: this rung opens a second
        # handle on every native-text document in the archive, and a sweep that
        # leaks one per document is a sweep that runs out of them.
        try:
            document.close()
        except Exception:  # noqa: BLE001 — a close failure is not an answer
            pass
    if pages == list(base.pages):
        return None
    return StatementMarkdown(source_file=source_file,
                             model="native-pdf-text+printed-rows", pages=pages)


# ---------------------------------------------------------------------------
# The native-text rung ladder — the one copy
# ---------------------------------------------------------------------------


def native_statement(pdf_bytes: bytes, source_file: str = "") -> StatementMarkdown | None:
    """The native-text rung: bank-specific layouts first, generic text last.

    THIS IS THE LADDER. Every consumer imports this function; none composes its
    own. `ocr/pipeline.py` binds it as `_native_statement`, and the five
    oracle/cache consumers (`adb_debug.py`, `adb_forensic_audit.py`,
    `balance_forensic_audit.py`, `build_corpus_cache.py`,
    `deterministic_coverage_audit.py`) bind it under the names their call sites
    already used. `tests/test_native_rung_parity.py` asserts all six names are
    THIS object and that no module composes rungs itself.

    Why one copy, in the words of the two drifts that paid for it:

    * O-1: the ladder existed twice — inline in `ocr/pipeline.py` and privately
      in `webapp/worker.py` — and the two had drifted in rung ORDER.
    * GEOM-1 (batch 4): production gained `parse_native_woodforest` while the
      five oracle copies did not, so the forensic oracles would have read
      Woodforest documents with the generic rung while production read
      geometry. An oracle that reads different bytes than production is not an
      oracle. Batch 4 wired all six by hand and pinned them with an AST drift
      guard; this function removes the thing the guard was watching.

    Order is behaviour, not taste: each bank-specific rung claims only the
    documents whose printed markers it recognises, and the generic rung claims
    everything with enough native text — so it must stay last. The extractors
    are called, never modified.

    Returns None when no rung claims the document, INCLUDING when the PDF's
    text layer cannot be read at all (`_UnreadableTextLayer`); the caller's
    next stage — local Tesseract, then visual OCR — decides what happens next.
    """
    return (
        parse_native_navy_federal(pdf_bytes, source_file=source_file)
        or parse_native_td_canada(pdf_bytes, source_file=source_file)
        or parse_native_wells_fargo(pdf_bytes, source_file=source_file)
        or parse_native_woodforest(pdf_bytes, source_file=source_file)
        or parse_native_desjardins(pdf_bytes, source_file=source_file)
        or parse_native_first_citizens(pdf_bytes, source_file=source_file)
        or parse_native_printed_rows(pdf_bytes, source_file=source_file)
        or parse_native_pdf_text(pdf_bytes, source_file=source_file)
    )
