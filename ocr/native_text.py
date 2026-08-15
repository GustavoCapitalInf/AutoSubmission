from __future__ import annotations

import re
from typing import TypedDict

from .column_grid import find_columns, page_words, read_rows
from .document import StatementMarkdown


def _native_pages(pdf_bytes: bytes) -> list[str] | None:
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
    return pages


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
    """Words grouped into visual lines, as `(baseline, text)`, top to bottom."""
    if not words:
        return []
    from statistics import median

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
    for words in pages_words:
        inside = False
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

    pages = _native_pages(pdf_bytes)
    if not pages:
        return None
    upper = "\n".join(pages).upper()
    if "WOODFOREST" not in upper or "DATE CREDITS DEBITS BALANCE DESCRIPTION" not in upper:
        return None

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
