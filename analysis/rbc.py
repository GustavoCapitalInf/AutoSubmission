from __future__ import annotations

import re
from datetime import date

from .schema import Statement, Transaction
from .td_can import _MONTHS, _parse_money

_PERIOD_RE = re.compile(
    r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s+to\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)
_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_DATE_START_RE = re.compile(r"^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", re.IGNORECASE)
_MONEY_RE = re.compile(r"(?<![#\w])-?\$?[\d,]+\.\d{2}(?!\w)")


def _date_from(day: str, mon: str, *, default_year: int) -> str:
    return date(default_year, _MONTHS[mon[:3].upper()], int(day)).isoformat()


def _money_matches(line: str) -> list[re.Match]:
    return list(_MONEY_RE.finditer(line))


def _is_credit(desc: str) -> bool:
    text = desc.upper()
    return (
        "MRCH" in text
        or text.startswith("ATM DEPOSIT")
        or text.startswith("E-TRANSFER RECEIVED")
        or text.startswith("ONLINE TRANSFER RECEIVED")
        or text.startswith("ROYAL FOREIGN EXCHANGE DEPOSIT")
        or text.startswith("COMMERCIAL LOANS")
        or "FUNDS TRANSFER CREDIT" in text
        or text.startswith("BR TO BR")
        or "RETURNED NSF" in text
        or "ITEM RETURNED NSF" in text
    )


def _is_debit(desc: str) -> bool:
    text = desc.upper()
    return any(key in text for key in (
        "MONTHLY FEE",
        "TRANSACTION FEE",
        "CASH DEPOSITED FEE",
        "ONLINE BANKING PAYMENT",
        "ONLINE BANKING TRANSFER",
        "ONLINE TRANSFER SENT",
        "E-TRANSFER SENT",
        "INTERAC PURCHASE",
        "CONTACTLESS INTERAC",
        "CHEQUE -",
        "INSURANCE ",
        "BILL PAYMENT",
        "EQUIPMENT RENT",
        "BUSINESS PAD",
        "FUNDIFI CANADA",
        "2313833 ONTARIO",
    ))


def parse_rbc_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    upper = markdown.upper()
    french = _parse_rbc_french_statement(markdown, base=base)
    if french is not None:
        return french
    if "ROYAL BANK OF CANADA" not in upper or "ACCOUNT ACTIVITY DETAILS" not in upper:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Royal Bank of Canada"
    rows: list[dict] = []
    default_year: int | None = None
    in_activity = False
    current_date: str | None = None

    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        u = line.upper()

        pm = _PERIOD_RE.search(line)
        if pm:
            sm, sd, sy, em, ed, ey = pm.groups()
            stmt.period_start = date(int(sy), _MONTH_NAMES[sm.lower()], int(sd)).isoformat()
            stmt.period_end = date(int(ey), _MONTH_NAMES[em.lower()], int(ed)).isoformat()
            default_year = int(ey)

        account = re.search(r"Account number:\s*([0-9 -]+)", line, re.IGNORECASE)
        if account:
            stmt.account_number = account.group(1).strip()

        m = re.search(r"Opening balance on .*?(-?\$?[\d,]+\.\d{2}|\$-?[\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.beginning_balance = _parse_money(m.group(1))
        m = re.search(r"Closing balance on .*?(-?\$?[\d,]+\.\d{2}|\$-?[\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.ending_balance = _parse_money(m.group(1))
        m = re.search(r"Total deposits & credits \((\d+)\)\s*\+?\s*([\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.stated_credit_count = int(m.group(1))
            stmt.stated_total_credits = _parse_money(m.group(2))
        m = re.search(r"Total cheques & debits \((\d+)\)\s*-?\s*([\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.stated_debit_count = int(m.group(1))
            stmt.stated_total_debits = _parse_money(m.group(2))

        if "DATE DESCRIPTION CHEQUES & DEBITS" in u:
            in_activity = True
            continue
        if in_activity and (u.startswith("CLOSING BALANCE") or u.startswith("ACCOUNT FEES:")):
            in_activity = False
            continue
        if not in_activity or default_year is None:
            continue
        if u.startswith(("OPENING BALANCE", "BUSINESS ACCOUNT STATEMENT", "ACCOUNT ACTIVITY DETAILS")):
            continue

        dm = _DATE_START_RE.match(line)
        if dm:
            # Record the posting date the moment it is seen. RBC puts the date on
            # the first line of each group, and that line often carries no amount
            # because the description wraps ("03 Feb Royal Foreign Exchange
            # deposit" / "Reference 0521... 90.00"). Tracking the date separately
            # from row creation is what keeps the following rows on the right day
            # — deriving it from rows[-1] instead silently folded whole posting
            # dates into the previous one and corrupted the daily ledger.
            current_date = _date_from(dm.group(1), dm.group(2), default_year=default_year)
            rest = line[dm.end():].strip()
            if _DATE_START_RE.match(rest):
                rest = rest[_DATE_START_RE.match(rest).end():].strip()
        elif rows or current_date is not None:
            fee_breakdown = re.match(r"^\d+\s+Crs\s+@\s+\d+\.\d{2}\s+([\d,]+\.\d{2})$", line, re.IGNORECASE)
            if fee_breakdown and rows and rows[-1]["description"].upper().startswith("REGULAR TRANSACTION FEE"):
                rows[-1]["abs_amount"] = abs(_parse_money(fee_breakdown.group(1)) or rows[-1]["abs_amount"])
                rows[-1]["amount"] = -rows[-1]["abs_amount"]
                continue
            rest = line
        else:
            continue

        tx_date = current_date if current_date is not None else (rows[-1]["date"] if rows else None)
        if tx_date is None:
            continue

        amounts = _money_matches(rest)
        if not amounts:
            continue
        has_date = bool(dm)
        has_balance = len(amounts) >= 2 and amounts[-1].end() == len(rest) and "TRANSACTION FEE" not in rest.upper()
        amount_match = amounts[-2] if has_balance else amounts[-1]
        amount = abs(_parse_money(amount_match.group(0)) or 0.0)
        running_balance = _parse_money(amounts[-1].group(0)) if has_balance else None
        desc = rest[:amount_match.start()].strip()
        if not desc:
            continue
        if _is_credit(desc):
            signed = amount
        elif _is_debit(desc):
            signed = -amount
        else:
            signed = -amount
        rows.append({
            "date": tx_date,
            "description": desc,
            "abs_amount": amount,
            "amount": round(signed, 2),
            "balance": running_balance,
        })

    if not rows:
        return None
    prev_balance = stmt.beginning_balance
    segment: list[dict] = []
    for row in rows:
        segment.append(row)
        if row["balance"] is None or prev_balance is None:
            continue
        _solve_segment(segment, round(row["balance"] - prev_balance, 2))
        prev_balance = row["balance"]
        segment = []

    transactions = [
        Transaction(
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            direction="credit" if row["amount"] > 0 else "debit",
            running_balance=row["balance"],
        )
        for row in rows
    ]
    stmt.transactions = transactions
    return stmt


_FR_DATE_RE = re.compile(r"^(\d{1,2})\s+([^\s]+)\s+(.*)$", re.IGNORECASE)
_FR_MONEY_RE = re.compile(r"(?<![A-Za-z0-9])\(?-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2}\)?")


def _money_fr(text: str) -> float:
    neg = text.strip().startswith("(") and text.strip().endswith(")")
    value = float(text.strip("()").replace(" ", "").replace(",", "."))
    return round(-value if neg else value, 2)


def _fr_money_matches(text: str) -> list[re.Match]:
    return list(_FR_MONEY_RE.finditer(text))


def _fr_year(month_token: str, *, start_year: int, end_year: int) -> int:
    return end_year if "JAN" in month_token.upper() else start_year


def _fr_month(month_token: str) -> int:
    upper = month_token.upper()
    if upper.startswith("JAN"):
        return 1
    if "C" in upper or "D" in upper:
        return 12
    raise ValueError(f"unsupported RBC French month: {month_token}")


def _fr_initial_sign(desc: str, amount: float) -> float:
    text = desc.upper()
    if any(key in text for key in ("REÃ‡U", "REÇU", "ANNUL", "DÃ‰P", "DÉP", "RABAIS")):
        return amount
    return -amount


def _solve_segment(rows: list[dict], expected: float) -> None:
    amounts = [row["abs_amount"] for row in rows]
    initial = [1 if row["amount"] > 0 else -1 for row in rows]
    best: tuple[int, list[int]] | None = None

    def rec(i: int, total: float, signs: list[int]) -> None:
        nonlocal best
        if best is not None and sum(1 for a, b in zip(signs, initial[:len(signs)]) if a != b) >= best[0]:
            return
        if i == len(amounts):
            if round(total, 2) == round(expected, 2):
                flips = sum(1 for a, b in zip(signs, initial) if a != b)
                if best is None or flips < best[0]:
                    best = (flips, signs[:])
            return
        rec(i + 1, round(total + amounts[i], 2), signs + [1])
        rec(i + 1, round(total - amounts[i], 2), signs + [-1])

    if len(rows) <= 16:
        rec(0, 0.0, [])
    if best is None:
        return
    for row, sign in zip(rows, best[1]):
        row["amount"] = round(sign * row["abs_amount"], 2)


def _parse_rbc_french_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    upper = markdown.upper()
    if "BANQUE ROYALE" not in upper or "DATE DESCRIPTION RETRAITS" not in upper:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Banque Royale du Canada"
    stmt.currency = "CAD"

    period = re.search(r"Du\s+\d+\s+\S+\s+(\d{4})\s+au\s+\d+\s+\S+\s+(\d{4})", markdown, re.IGNORECASE)
    start_year, end_year = (2025, 2026)
    if period:
        start_year, end_year = int(period.group(1)), int(period.group(2))
        stmt.period_start = date(start_year, 12, 2).isoformat()
        stmt.period_end = date(end_year, 1, 2).isoformat()

    acct = re.search(r"numÃ©ro de compte\s*:\s*([0-9-]+)", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)

    m = re.search(r"solde d'ouverture.*?([\d ]+,\d{2})\s*\$", markdown, re.IGNORECASE)
    if m:
        stmt.beginning_balance = _money_fr(m.group(1))
    m = re.search(r"Total des d.*?compte\s*\+\s*([\d ]+,\d{2})", markdown, re.IGNORECASE)
    if m:
        stmt.stated_total_credits = _money_fr(m.group(1))
    m = re.search(r"Total des retraits.*?-\s*([\d ]+,\d{2})", markdown, re.IGNORECASE)
    if m:
        stmt.stated_total_debits = _money_fr(m.group(1))
    m = re.search(r"solde de cl.*?=\s*([\d ]+,\d{2})\s*\$", markdown, re.IGNORECASE)
    if m:
        stmt.ending_balance = _money_fr(m.group(1))

    rows: list[dict] = []
    current_date: str | None = None
    in_activity = False
    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        u = line.upper()
        if "DATE DESCRIPTION RETRAITS" in u:
            in_activity = True
            continue
        if in_activity and (u.startswith("SOLDE DE CL") or u.startswith("VOTRE LIMITE")):
            break
        if not in_activity or u.startswith(("DOCUSIGN", "RELEV", "BANQUE ROYALE", "DU ", "RBPDA", "*3", "DATE DESCRIPTION")):
            continue
        if re.fullmatch(r"\d+ de \d+", line):
            continue
        if u.startswith("SOLDE D'OUVERTURE"):
            vals = _fr_money_matches(line)
            if vals:
                stmt.beginning_balance = _money_fr(vals[-1].group(0))
            continue

        dm = _FR_DATE_RE.match(line)
        if dm:
            day, month_token, rest = dm.groups()
            try:
                current_date = date(
                    _fr_year(month_token, start_year=start_year, end_year=end_year),
                    _fr_month(month_token),
                    int(day),
                ).isoformat()
            except ValueError:
                continue
        else:
            rest = line
        if current_date is None:
            continue
        amounts = _fr_money_matches(rest)
        if not amounts:
            continue
        has_balance = len(amounts) >= 2 and amounts[-1].end() == len(rest)
        amount_match = amounts[-2] if has_balance else amounts[-1]
        balance = _money_fr(amounts[-1].group(0)) if has_balance else None
        abs_amount = abs(_money_fr(amount_match.group(0)))
        desc = rest[:amount_match.start()].strip()
        if not desc:
            continue
        rows.append({
            "date": current_date,
            "description": desc,
            "abs_amount": abs_amount,
            "amount": _fr_initial_sign(desc, abs_amount),
            "balance": balance,
        })

    prev_balance = stmt.beginning_balance
    segment: list[dict] = []
    for row in rows:
        segment.append(row)
        if row["balance"] is None or prev_balance is None:
            continue
        _solve_segment(segment, round(row["balance"] - prev_balance, 2))
        prev_balance = row["balance"]
        segment = []

    transactions = [
        Transaction(
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            direction="credit" if row["amount"] > 0 else "debit",
            running_balance=row["balance"],
        )
        for row in rows
    ]
    if not transactions:
        return None
    stmt.transactions = transactions
    return stmt
