from __future__ import annotations

import re
from functools import lru_cache
from statistics import median
from typing import TypedDict

from .column_grid import find_columns, page_words, read_rows
from .document import StatementMarkdown


@lru_cache(maxsize=4)
def _native_pages_cached(pdf_bytes: bytes) -> tuple[str, ...] | None:
    """The block extraction itself, memoised on the document's own bytes.

    The ladder in `ocr/pipeline.py` asks several extractors in turn and most of
    them start by reading the same page text, so an un-memoised
    `_native_pages` is re-extracted once per rung the document falls through —
    on every native-text document in the archive, every discovery run. Four
    entries is enough: the ladder works one document at a time.

    A TUPLE is returned, and `_native_pages` copies it into a fresh list per
    call. `parse_native_navy_federal` and this module's Woodforest reader both
    append their structured block to `pages[0]`, and handing out the cached
    object would let one caller's edit become the next caller's input.
    """
    try:
        import fitz
    except Exception:
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    pages: list[str] = []
    for page in doc:
        lines: list[str] = []
        blocks = sorted(page.get_text("blocks"), key=lambda b: (round(b[1], 1), round(b[0], 1)))
        for block in blocks:
            text = " ".join(part.strip() for part in str(block[4]).splitlines() if part.strip())
            if text:
                lines.append(text)
        pages.append("\n".join(lines))
    return tuple(pages)


def _native_pages(pdf_bytes: bytes) -> list[str] | None:
    pages = _native_pages_cached(pdf_bytes)
    return None if pages is None else list(pages)


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
        for raw_line in page.get_text("text", sort=True).splitlines():
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

    full_text = "\n".join(page.get_text("text", sort=True) or "" for page in doc)
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

    rows, source_dates = _navy_transaction_rows(doc, account_match.group(1))
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
    for block in page.get_text("dict").get("blocks", []):
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
    for page in doc:
        rows.extend(_fc_rows(page))
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

    pages = [page.get_text("text", sort=True) or "" for page in doc]
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

    full_text = "\n".join(page.get_text("text") or "" for page in doc).upper()
    if "WELLS FARGO" not in full_text or "TRANSACTION HISTORY" not in full_text:
        return None

    pages: list[str] = []
    for page in doc:
        lines: list[str] = []
        blocks = sorted(page.get_text("blocks"), key=lambda b: (round(b[1], 1), round(b[0], 1)))
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
    return StatementMarkdown(source_file=source_file, model="native-pdf-text+wells", pages=pages)


def _wells_rows(page) -> list[str]:
    import re

    words = page.get_text("words")
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
