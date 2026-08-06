"""Deterministic parser for TD Canada statement tables.

TD Canada's OCR output is usually a usable HTML table, but rowspans can shift a
date or amount into the neighboring row. This parser handles the common TD CAD
layout directly instead of asking the generic extractor to infer it.
"""
from __future__ import annotations

import re
from datetime import date

from .money import parse_money, parse_money_tokens, strip_currency
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import CELL_RE, clean_cell

_TABLE_RE = re.compile(r"<table>.*?</table>", re.IGNORECASE | re.DOTALL)
_ROW_RE = re.compile(r"<tr.*?>.*?</tr>", re.IGNORECASE | re.DOTALL)
_PERIOD_RE = re.compile(
    r"\b([A-Z]{3})\s*(\d{1,2})/(\d{2})\s*-\s*([A-Z]{3})\s*(\d{1,2})/(\d{2})\b",
    re.IGNORECASE,
)
_DATE_TOKEN_RE = re.compile(r"\b([A-Z]{3})(\d{1,2})\b", re.IGNORECASE)
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


#: Back-compat alias. `analysis/pipeline.py` still imports `_parse_money` from
#: this module; that import moves to `analysis.money` in R-3, which owns the
#: dispatch seam. R-2 does not edit pipeline.py.
_parse_money = parse_money

#: Signature sequences that only occur when UTF-8 bytes were mis-decoded as
#: cp1252/latin-1 ("mojibake"). Written as escapes on purpose: source code
#: never carries raw mojibake byte sequences (R-1 item 11).
_MOJIBAKE_MARKERS = ("\u00c3", "\u00e2\u20ac", "\u00c2")
#: Targeted fallback for mixed content where the full-text reversal fails.
_MOJIBAKE_TABLE = {
    "\u00e2\u20ac\u201d": "\u2014",  # em dash
    "\u00e2\u20ac\u201c": "\u2013",  # en dash
    "\u00e2\u20ac\u02dc": "\u2018",  # left single quote
    "\u00e2\u20ac\u2122": "\u2019",  # right single quote
    "\u00c3\u2021": "\u00c7",  # C-cedilla (upper)
    "\u00c3\u2030": "\u00c9",  # E-acute (upper)
    "\u00c3\u00a9": "\u00e9",  # e-acute
    "\u00c3\u00a8": "\u00e8",  # e-grave
    "\u00c3\u00aa": "\u00ea",  # e-circumflex
    "\u00c3\u00a7": "\u00e7",  # c-cedilla
    "\u00c3\u00a0": "\u00e0",  # a-grave
    "\u00c3\u00b4": "\u00f4",  # o-circumflex
    "\u00c3\u00ae": "\u00ee",  # i-circumflex
    "\u00c2\u00a0": " ",  # doubly-encoded NBSP
}


def normalize_mojibake(text: str) -> str:
    """Repair double-encoded (UTF-8 read as cp1252) text; NBSP becomes space.

    R-1 item 11: parsers normalize encoding FIRST and then match real
    characters - regexes never carry mojibake byte sequences. Clean text
    passes through unchanged, so already-correct sources are untouched.
    """
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return text.replace("\u00a0", " ")
    try:
        repaired = text.encode("cp1252", errors="strict").decode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError):
        repaired = text
        for wrong, right in _MOJIBAKE_TABLE.items():
            repaired = repaired.replace(wrong, right)
    return repaired.replace("\u00a0", " ")


def _tables(markdown: str) -> list[list[list[str]]]:
    parsed = []
    for table in _TABLE_RE.findall(markdown):
        rows = []
        for row in _ROW_RE.findall(table):
            cells = [clean_cell(c) for c in CELL_RE.findall(row)]
            if cells:
                rows.append(cells)
        if rows:
            parsed.append(rows)
    return parsed


def _parse_summary_count_amount(value: str | None) -> tuple[int, float] | None:
    if not value:
        return None
    text = strip_currency(value)
    m = re.search(r"\b(\d+)\s+(\d+(?:\.\d{2})?)\b", text)
    if not m:
        return None
    return int(m.group(1)), round(float(m.group(2)), 2)


def _summary_count_amount(cells: list[str], label: str) -> tuple[int, float] | None:
    label = label.upper()
    for i, cell in enumerate(cells):
        if label not in cell.upper():
            continue
        direct = _parse_summary_count_amount(cell)
        if direct:
            return direct
        nums: list[str] = []
        for later in cells[i + 1:]:
            nums.extend(re.findall(r"\d[\d,]*(?:\.\d{2})?", later))
        if len(nums) >= 2:
            return int(nums[0].replace(",", "")), round(float(nums[1].replace(",", "")), 2)
    return None


def _parse_period(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    m = _PERIOD_RE.search(value.upper())
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    start = date(2000 + int(sy), _MONTHS[sm], int(sd))
    end = date(2000 + int(ey), _MONTHS[em], int(ed))
    return start.isoformat(), end.isoformat()


def _date_tokens(value: str | None, *, default_year: int) -> list[str]:
    if not value:
        return []
    text = value.upper().replace("OCTS", "OCT").replace("SEPS", "SEP")
    out = []
    for mon, day, yy in re.findall(r"\b([A-Z]{3})\s*(\d{1,2})(?:/(\d{2}))?\b", text):
        if mon not in _MONTHS:
            continue
        year = 2000 + int(yy) if yy else default_year
        out.append(date(year, _MONTHS[mon], int(day)).isoformat())
    return out


def _native_date_token(value: str) -> str | None:
    text = value.upper().replace("OCTS", "OCT").replace("SEPS", "SEP")
    return text if _DATE_TOKEN_RE.fullmatch(text) and text[:3] in _MONTHS else None


def _native_date_to_iso(value: str, *, default_year: int) -> str:
    m = _DATE_TOKEN_RE.fullmatch(value.upper())
    if not m:
        raise ValueError(value)
    return date(default_year, _MONTHS[m.group(1).upper()], int(m.group(2))).isoformat()


def _looks_like_money(value: str | None) -> bool:
    return bool(parse_money_tokens(value))


def _tx(date_value: str, description: str, amount: float, balance: float | None = None) -> Transaction:
    return Transaction(
        date=date_value,
        description=re.sub(r"\s+", " ", description).strip(),
        amount=round(amount, 2),
        direction="credit" if amount > 0 else "debit",
        running_balance=balance,
    )


def _credit_like(description: str) -> bool:
    """Generic banking-language credit signals only (no merchant names)."""
    text = description.upper()
    return any(word in text for word in ("PAY", "DEPOSIT", "CREDIT", "E-TRANSFER CR"))


#: TD prints a transaction-type code as the trailing token of native ledger
#: descriptions. Sign is determined by these structural codes (R-1 item 8 -
#: previously merchant-name lists decided sign):
#:   MSP  merchant services payment (settlement deposit)  -> credit
#:   CLN  commercial loan disbursement                     -> credit
#:   PAY  direct-deposit payment received                  -> credit
#:   GST  government tax remittance/refund                 -> credit
#:   BUS  business pre-authorized debit                    -> debit
_NATIVE_CREDIT_CODES = {"MSP", "CLN", "PAY", "GST"}
_NATIVE_DEBIT_CODES = {"BUS"}


def _native_credit_like(description: str) -> bool:
    """Sign from TD's own transaction codes, never from counterparty names."""
    text = description.upper()
    if "TFR-FR" in text:          # transfer from another account
        return True
    if "TFR-TO" in text:          # transfer to another account
        return False
    if text.startswith("SEND E-TFR"):
        return False
    if text.startswith("E-TRANSFER"):
        return True
    tokens = text.split()
    if tokens:
        if tokens[-1] in _NATIVE_DEBIT_CODES:
            return False
        if tokens[-1] in _NATIVE_CREDIT_CODES:
            return True
    return False


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


def _table_layout_present(markdown: str) -> bool:
    """The TD table layout, as the pre-R-3 guard tested for it.

    The bank-name test does not depend on the table being iterated, but the
    surrounding `any(...)` means an empty table list still fails: this parser
    reads tables, so a document with none is not its document.
    """
    tables = _tables(markdown)
    return any(
        "THE TORONTO-DOMINION BANK" in markdown.upper()
        or "BUSINESS CHEQUING ACCOUNT - CAD" in " ".join(sum(table, []))
        for table in tables
    )


NATIVE_DETECTION_MARKERS = (
    required("bank_name", lambda t: "THE TORONTO-DOMINION BANK" in t),
    required("native_header", lambda t: "DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE" in t),
)

DETECTION_MARKERS = (
    required("table_layout", _table_layout_present),
)

detect_native = make_detector(NATIVE_DETECTION_MARKERS, detection_text)
detect = make_detector(DETECTION_MARKERS)


def _parse_native_td_canada(markdown: str, base: Statement | None = None) -> Statement | None:
    if not detect_native(markdown).claims:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "TD Canada Trust"
    stmt.currency = "CAD"
    stmt.beginning_balance = None
    stmt.ending_balance = None
    stmt.stated_total_credits = None
    stmt.stated_total_debits = None
    stmt.stated_credit_count = None
    stmt.stated_debit_count = None
    stmt.stated_average_balance = None
    transactions: list[Transaction] = []
    in_ledger = False
    default_year: int | None = None

    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        upper = line.upper()
        period = _parse_period(line)
        if period:
            stmt.period_start, stmt.period_end = period
            default_year = int(stmt.period_end[:4])
        account = re.search(r"\b\d{4}-\d{6,}\b", line)
        if account:
            stmt.account_number = account.group(0)
        if "BUSINESS CHEQUING" in upper:
            stmt.account_name = "BUSINESS CHEQUING ACCOUNT - CAD"
        if upper.startswith("MONTHLY AVER. CR. BAL."):
            avg = parse_money(line)
            if avg is not None:
                stmt.stated_average_balance = abs(avg)
        if upper.startswith("CREDITS "):
            credit = _parse_summary_count_amount(line)
            if credit:
                stmt.stated_credit_count = (stmt.stated_credit_count or 0) + credit[0]
                stmt.stated_total_credits = round((stmt.stated_total_credits or 0.0) + credit[1], 2)
        if upper.startswith("DEBITS "):
            debit = _parse_summary_count_amount(line)
            if debit:
                stmt.stated_debit_count = (stmt.stated_debit_count or 0) + debit[0]
                stmt.stated_total_debits = round((stmt.stated_total_debits or 0.0) + debit[1], 2)

        if upper.startswith("DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE"):
            in_ledger = True
            continue
        if in_ledger and upper.startswith("0 CHQS ENCLOSED"):
            in_ledger = False
            continue
        if not in_ledger or default_year is None:
            continue

        tokens = line.split()
        date_index = next((i for i, token in enumerate(tokens) if _native_date_token(token)), None)
        if date_index is None:
            continue

        tx_date = _native_date_to_iso(tokens[date_index], default_year=default_year)
        balance = parse_money(tokens[date_index + 1]) if date_index + 1 < len(tokens) else None
        if upper.startswith("BALANCE FORWARD"):
            if stmt.beginning_balance is None and balance is not None:
                stmt.beginning_balance = balance
            continue

        amount_index = None
        amount = None
        for i in range(date_index - 1, -1, -1):
            parsed = parse_money(tokens[i])
            if parsed is not None and "." in tokens[i]:
                amount_index = i
                amount = abs(parsed)
                break
        if amount_index is None or amount is None:
            continue
        desc = " ".join(tokens[:amount_index])
        if not desc:
            continue
        signed = amount if _native_credit_like(desc) else -amount
        transactions.append(_tx(tx_date, desc, signed))
        if balance is not None:
            stmt.ending_balance = balance

    if not transactions:
        return None
    stmt.transactions = transactions
    return stmt


def parse_td_canada_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    native = _parse_native_td_canada(markdown, base)
    if native is not None:
        return native

    if not detect(markdown).claims:
        return None

    tables = _tables(markdown)
    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "TD Canada Trust"
    stmt.currency = "CAD"
    stmt.beginning_balance = None
    stmt.ending_balance = None
    stmt.stated_total_credits = None
    stmt.stated_total_debits = None
    stmt.stated_credit_count = None
    stmt.stated_debit_count = None
    stmt.stated_average_balance = None
    transactions: list[Transaction] = []
    pending_credit: tuple[float, str] | None = None

    for rows in tables:
        default_year = None
        in_ledger = False
        for cells in rows:
            joined = " ".join(cells)
            if "BUSINESS CHEQUING ACCOUNT" in joined.upper():
                stmt.account_name = next((c for c in cells if "BUSINESS CHEQUING ACCOUNT" in c.upper()), stmt.account_name)
                for c in cells:
                    period = _parse_period(c)
                    if period:
                        stmt.period_start, stmt.period_end = period
                        default_year = int(stmt.period_end[:4])
                continue
            account = next((c for c in cells if re.fullmatch(r"\d{4}-\d{6,}", c)), None)
            if account:
                stmt.account_number = account

            if "DESCRIPTION" in joined.upper() and "CHEQUE/DEBIT" in joined.upper():
                in_ledger = True
                if default_year is None and stmt.period_end:
                    default_year = int(stmt.period_end[:4])
                continue

            upper = joined.upper()
            if not joined or upper == "-":
                continue
            if upper.startswith("MONTHLY AVER. CR. BAL."):
                avg = next((parse_money(c) for c in cells if parse_money(c) is not None), None)
                if avg is not None:
                    stmt.stated_average_balance = abs(avg)
                credit = _summary_count_amount(cells, "CREDITS")
                if credit:
                    stmt.stated_credit_count = (stmt.stated_credit_count or 0) + credit[0]
                    stmt.stated_total_credits = round((stmt.stated_total_credits or 0.0) + credit[1], 2)
                continue
            if "CREDITS" in upper:
                credit = _summary_count_amount(cells, "CREDITS")
                if credit:
                    stmt.stated_credit_count = (stmt.stated_credit_count or 0) + credit[0]
                    stmt.stated_total_credits = round((stmt.stated_total_credits or 0.0) + credit[1], 2)
                continue
            if "DEBITS" in upper:
                debit = _summary_count_amount(cells, "DEBITS")
                if debit:
                    stmt.stated_debit_count = (stmt.stated_debit_count or 0) + debit[0]
                    stmt.stated_total_debits = round((stmt.stated_total_debits or 0.0) + debit[1], 2)
                continue
            if not in_ledger:
                continue
            if upper.startswith("0 CHQS ENCLOSED"):
                in_ledger = False
                continue
            if not in_ledger:
                continue

            if len(cells) < 4:
                continue
            desc, debit_cell, credit_cell, date_cell = cells[:4]
            balance_cell = cells[4] if len(cells) >= 5 else ""
            if default_year is None:
                if not stmt.period_end:
                    # No printed period evidence anywhere - rows cannot be
                    # dated; skip instead of assuming a year (R-1 item 8/9
                    # class: the previous "2025" fallback invented dates).
                    continue
                default_year = int(stmt.period_end[:4])

            if desc.upper().startswith("BALANCE FORWARD"):
                bal = parse_money(balance_cell)
                if bal is not None and stmt.beginning_balance is None:
                    stmt.beginning_balance = bal
                rest = desc[len("BALANCE FORWARD"):].strip()
                dates = _date_tokens(date_cell, default_year=default_year)
                credits = parse_money_tokens(credit_cell)
                if rest and credits and len(dates) >= 2 and len(rest.split()) <= 6:
                    transactions.append(_tx(dates[-1], rest, abs(credits[0])))
                continue

            dates = _date_tokens(date_cell, default_year=default_year)
            balance = parse_money(balance_cell)
            if _looks_like_money(date_cell):
                shifted_dates = _date_tokens(balance_cell, default_year=default_year)
                if shifted_dates:
                    shifted_amount = abs(parse_money_tokens(date_cell)[0])
                    if parse_money_tokens(debit_cell) or parse_money_tokens(credit_cell):
                        pending_credit = (shifted_amount, shifted_dates[0])
                    elif _credit_like(desc):
                        # Column-shifted amount with no printed column evidence:
                        # emit only on a generic credit signal; otherwise skip
                        # the row (fail closed) rather than guess a sign from
                        # counterparty names (R-1 item 8).
                        transactions.append(_tx(shifted_dates[0], desc, shifted_amount))
                    dates = dates or shifted_dates
                    balance = None

            if pending_credit and not parse_money_tokens(debit_cell) and not parse_money_tokens(credit_cell):
                amount, d = pending_credit
                transactions.append(_tx(d, desc, amount, balance))
                pending_credit = None
                continue

            if not dates:
                continue

            debits = [abs(v) for v in parse_money_tokens(debit_cell)]
            credits = [abs(v) for v in parse_money_tokens(credit_cell)]
            if debits:
                split_dates = dates if len(dates) == len(debits) else [dates[0]] * len(debits)
                for i, amount in enumerate(debits):
                    rb = balance if i == len(debits) - 1 else None
                    transactions.append(_tx(split_dates[i], desc, -amount, rb))
            if credits:
                # Trust the bank's printed DEPOSIT/CREDIT column. Reconciliation
                # against the stated summary fails closed downstream if the
                # extraction misplaced an amount (R-1 item 8 - merchant-name
                # sign overrides removed).
                transactions.append(_tx(dates[0], desc, credits[0], balance if not debits else None))

    if not transactions:
        return None

    if stmt.ending_balance is None:
        for t in reversed(transactions):
            if t.running_balance is not None:
                stmt.ending_balance = t.running_balance
                break

    # TD Canada prints sparse balances at selected row-group endings, not a full
    # daily closing-balance series. Use them to verify/locate the ending balance,
    # then suppress derived ADB/min/max/negative-day analytics.
    transactions = [t.model_copy(update={"running_balance": None}) for t in transactions]
    stmt.transactions = transactions
    return stmt


#: Public entry point for the native-text TD Canada layout, registered in its
#: own right by R-3. `parse_td_canada_statement` still tries it first until the
#: pipeline switches to registry dispatch.
parse_native_td_canada_statement = _parse_native_td_canada
