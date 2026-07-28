from __future__ import annotations

import re
from datetime import date

from .schema import Statement, Transaction

_MONTHS = {
    "jan": 1,
    "fev": 2,
    "fév": 2,
    "mar": 3,
    "avr": 4,
    "mai": 5,
    "jun": 6,
    "juin": 6,
    "jul": 7,
    "juil": 7,
    "aou": 8,
    "aoû": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "déc": 12,
}
_MONEY_RE = re.compile(r"(?<![A-Za-z0-9])-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2}(?![A-Za-z0-9])")


def _money(value: str) -> float:
    return round(float(value.replace(" ", "").replace(",", ".")), 2)


def _money_candidates(value: str) -> list[tuple[float, int]]:
    candidates = [(_money(value), 0)]
    if " " in value:
        tail_start = value.rfind(" ") + 1
        candidates.append((_money(value[tail_start:]), tail_start))
    return candidates


def _month(token: str) -> int:
    key = token.lower()[:4] if token.lower().startswith("juil") else token.lower()[:3]
    return _MONTHS[key]


def _summary(markdown: str) -> tuple[float, float, float, float] | None:
    money = r"(-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2})"
    beginning = re.search(r"Solde d'ouverture.*?" + money + r"\s*\$", markdown, re.IGNORECASE)
    debits = re.search(r"Retraits\s*-\s*" + money, markdown, re.IGNORECASE)
    credits = re.search(r"D.p.ts\s*\+\s*" + money, markdown, re.IGNORECASE)
    ending = re.search(r"Solde de cl.ture.*?=\s*" + money + r"\s*\$", markdown, re.IGNORECASE)
    if not beginning or not debits or not credits or not ending:
        return None
    return _money(beginning.group(1)), _money(credits.group(1)), _money(debits.group(1)), _money(ending.group(1))


def _activity_lines(markdown: str) -> list[str]:
    start = markdown.find("Date Description Retraits")
    if start == -1:
        return []
    end = markdown.find("Solde de cl", start)
    if end == -1:
        return []
    lines: list[str] = []
    for raw in markdown[start:end].splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if "Date Description Retraits" in line:
            marker = "Solde ($)"
            idx = line.find(marker)
            line = line[idx + len(marker):].strip() if idx != -1 else ""
            if not line:
                continue
        if (
            "suite" in line
            or re.fullmatch(r"\d+ de \d+", line)
            or line.startswith(("10774F", "Relev", "Num", "Transit"))
        ):
            continue
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"\s+(?=\d{1,2}\s+[A-Za-zÃ©Ã‰Ã»Ã¼Ã´ÃöÃàÃâ]{3,4}\b)", "\n", text)
    return text.splitlines()


def _parse_transactions(markdown: str, *, year: int, beginning: float) -> list[Transaction]:
    rows: list[Transaction] = []
    current_date: str | None = None
    prev_balance = beginning
    for line in _activity_lines(markdown):
        dm = re.match(r"^(\d{1,2})\s+([A-Za-zÃ©Ã‰Ã»Ã¼ÃôÃöÃàÃâ]{3,4})\s+(.*)$", line)
        if dm:
            current_date = date(year, _month(dm.group(2)), int(dm.group(1))).isoformat()
            remaining = dm.group(3).strip()
        else:
            remaining = line.strip()
        remaining = re.sub(
            r"^Solde d'ouverture\s+-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2}\s*\$?\s+\d{1,2}\s+\w+\s+",
            "",
            remaining,
        )
        remaining = re.sub(
            r"^Solde report\w+\s+-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2}\s*\$?\s*",
            "",
            remaining,
        )
        while current_date is not None:
            tokens = list(_MONEY_RE.finditer(remaining))
            if len(tokens) < 2:
                break
            found: tuple[int, int, float, float, float, int] | None = None
            for balance_index in range(1, len(tokens)):
                balance = _money(tokens[balance_index].group(0))
                delta = round(balance - prev_balance, 2)
                for amount_index in range(balance_index - 1, -1, -1):
                    for candidate, offset in _money_candidates(tokens[amount_index].group(0)):
                        if abs(abs(delta) - candidate) <= 0.02:
                            found = (amount_index, balance_index, candidate, balance, delta, offset)
                            break
                    if found:
                        break
                if found:
                    break
            if not found:
                return []
            amount_index, balance_index, _candidate, balance, delta, offset = found
            amount_token = tokens[amount_index]
            amount_start = amount_token.start() + offset
            desc = remaining[:amount_start].strip()
            if not desc:
                return []
            rows.append(
                Transaction(
                    date=current_date,
                    description=re.sub(r"\s+", " ", desc),
                    amount=delta,
                    direction="credit" if delta > 0 else "debit",
                    running_balance=balance,
                )
            )
            prev_balance = balance
            remaining = remaining[tokens[balance_index].end():].strip()
    return rows


def parse_cibc_french_statement(markdown: str) -> Statement | None:
    if "CIBC" not in markdown or not re.search(r"D.tail de vos op.rations", markdown):
        return None
    period = re.search(r"Du\s+(\d{1,2})\s+(\w+)\s+au\s+(\d{1,2})\s+(\w+)\s+(\d{4})", markdown)
    summary = _summary(markdown)
    if not period or summary is None:
        return None
    start_day, start_month, end_day, end_month, year_text = period.groups()
    year = int(year_text)
    beginning, credits, debits, ending = summary
    stmt = Statement(
        bank="CIBC",
        currency="CAD",
        period_start=date(year, _month(start_month), int(start_day)).isoformat(),
        period_end=date(year, _month(end_month), int(end_day)).isoformat(),
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
    )
    acct = re.search(r"Num.ro de compte\s*:?\s*([0-9-]+)", markdown)
    if acct:
        stmt.account_number = acct.group(1)

    txns = _parse_transactions(markdown, year=year, beginning=beginning)
    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - credits) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - debits) > 0.02:
        return None
    if abs((txns[-1].running_balance or 0.0) - ending) > 0.02:
        return None
    stmt.transactions = txns
    return stmt
