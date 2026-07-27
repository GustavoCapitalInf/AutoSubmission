from __future__ import annotations

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
