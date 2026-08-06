from __future__ import annotations

import re
import unicodedata
from datetime import date

from .money import parse_french_amount, parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .td_can import _MONTHS, normalize_mojibake

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
    # Generic banking transaction types only. Counterparty names are never
    # sign evidence (R-1 item 7: the two memorized counterparty entries were
    # removed; rows not matching a credit type default to debit below, and
    # printed running balances drive the sign solver, so behaviour is
    # unchanged - see R1_HARDCODE_LOG.md).
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
    ))


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


def french_detection_text(markdown: str) -> str:
    """As above, after repairing double-encoded accents."""
    return normalize_mojibake(markdown).upper()


DETECTION_MARKERS = (
    required("bank_name", lambda t: "ROYAL BANK OF CANADA" in t),
    required("activity_section", lambda t: "ACCOUNT ACTIVITY DETAILS" in t),
)

FRENCH_DETECTION_MARKERS = (
    required("bank_name", lambda t: "BANQUE ROYALE" in t),
    required("activity_header", lambda t: "DATE DESCRIPTION RETRAITS" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)
detect_french = make_detector(FRENCH_DETECTION_MARKERS, french_detection_text)


def parse_rbc_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    upper = markdown.upper()
    french = _parse_rbc_french_statement(markdown, base=base)
    if french is not None:
        return french
    if not detect(markdown).claims:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Royal Bank of Canada"
    rows: list[dict] = []
    default_year: int | None = None
    in_activity = False
    current_date: str | None = None
    pending_description: list[str] = []

    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        u = line.upper()

        if line.startswith("--- Page"):
            in_activity = False
            pending_description = []
            continue

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
            stmt.beginning_balance = parse_money(m.group(1))
        m = re.search(r"Closing balance on .*?(-?\$?[\d,]+\.\d{2}|\$-?[\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.ending_balance = parse_money(m.group(1))
        m = re.search(r"Total deposits & credits \((\d+)\)\s*\+?\s*([\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.stated_credit_count = int(m.group(1))
            stmt.stated_total_credits = parse_money(m.group(2))
        m = re.search(r"Total cheques & debits \((\d+)\)\s*-?\s*([\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.stated_debit_count = int(m.group(1))
            stmt.stated_total_debits = parse_money(m.group(2))

        if "DATE DESCRIPTION CHEQUES & DEBITS" in u:
            in_activity = True
            pending_description = []
            continue
        if in_activity and (u.startswith("CLOSING BALANCE") or u.startswith("ACCOUNT FEES:")):
            in_activity = False
            pending_description = []
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
            pending_description = []
        elif rows or current_date is not None:
            fee_breakdown = re.match(r"^\d+\s+Crs\s+@\s+\d+\.\d{2}\s+([\d,]+\.\d{2})$", line, re.IGNORECASE)
            if fee_breakdown and rows and rows[-1]["description"].upper().startswith("REGULAR TRANSACTION FEE"):
                rows[-1]["abs_amount"] = abs(parse_money(fee_breakdown.group(1)) or rows[-1]["abs_amount"])
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
            if rest:
                pending_description.append(rest)
            continue
        has_date = bool(dm)
        has_balance = len(amounts) >= 2 and amounts[-1].end() == len(rest) and "TRANSACTION FEE" not in rest.upper()
        amount_match = amounts[-2] if has_balance else amounts[-1]
        amount = abs(parse_money(amount_match.group(0)) or 0.0)
        running_balance = parse_money(amounts[-1].group(0)) if has_balance else None
        desc = rest[:amount_match.start()].strip()
        if pending_description:
            desc = " ".join([*pending_description, desc]).strip()
            pending_description = []
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
#: Full French month names; tokens resolve by unambiguous prefix, so every
#: month works, not only December/January (R-1 item 7).
_FR_MONTH_NAMES = {
    "JANVIER": 1, "FEVRIER": 2, "MARS": 3, "AVRIL": 4, "MAI": 5, "JUIN": 6,
    "JUILLET": 7, "AOUT": 8, "SEPTEMBRE": 9, "OCTOBRE": 10, "NOVEMBRE": 11,
    "DECEMBRE": 12,
}
_FR_PERIOD_RE = re.compile(
    r"Du\s+(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})\s+au\s+(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})",
    re.IGNORECASE,
)


def _money_fr(text: str) -> float:
    return parse_french_amount(text, parens=True)


def _fr_money_matches(text: str) -> list[re.Match]:
    return list(_FR_MONEY_RE.finditer(text))


def _fr_month(month_token: str) -> int | None:
    """Resolve a (possibly abbreviated) French month token; None if ambiguous."""
    decomposed = unicodedata.normalize("NFKD", month_token)
    token = "".join(c for c in decomposed if c.isalpha()).upper()
    if not token:
        return None
    matches = {
        number
        for name, number in _FR_MONTH_NAMES.items()
        if name.startswith(token)
    }
    return matches.pop() if len(matches) == 1 else None


def _fr_transaction_date(
    day: int, month: int, *, period_start: date, period_end: date
) -> date | None:
    """The unique in-period date for a day/month pair, else None (fail closed).

    Replaces the hardcoded start-year/end-year December/January mapping
    (R-1 item 7): year choice is evidence-based - the date must fall inside
    the printed statement period, whatever months it spans.
    """
    candidates = []
    for year in {period_start.year, period_end.year}:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if period_start <= candidate <= period_end:
            candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


def _fr_initial_sign(desc: str, amount: float) -> float:
    # Real accented characters only - the text is mojibake-normalized first
    # (R-1 item 11). The printed-balance sign solver has the final word.
    text = desc.upper()
    if any(key in text for key in ("REÇU", "ANNUL", "DÉP", "RABAIS")):
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
    markdown = normalize_mojibake(markdown)
    upper = markdown.upper()
    if not detect_french(markdown).claims:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Banque Royale du Canada"
    stmt.currency = "CAD"

    # The full printed period line is required - day, month, and year for
    # both bounds. No default years, no hardcoded month/day (R-1 item 7:
    # previously Dec/Jan-only with (2025, 2026) fallbacks).
    period = _FR_PERIOD_RE.search(markdown)
    if not period:
        return None
    start_day, start_token, start_year, end_day, end_token, end_year = period.groups()
    start_month = _fr_month(start_token)
    end_month = _fr_month(end_token)
    if start_month is None or end_month is None:
        return None
    try:
        period_start = date(int(start_year), start_month, int(start_day))
        period_end = date(int(end_year), end_month, int(end_day))
    except ValueError:
        return None
    if period_end < period_start:
        return None
    stmt.period_start = period_start.isoformat()
    stmt.period_end = period_end.isoformat()

    # NOTE (R-1 item 7/11): the previous account-number regex carried a
    # mojibake label and could never match the real text, so no account was
    # ever extracted here. Extraction stays deliberately absent to keep the
    # audited corpus surface identical; enabling it is proposed in
    # R1_HARDCODE_LOG.md for an Ocean-approved re-baseline.

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
            month = _fr_month(month_token)
            if month is None:
                continue
            resolved = _fr_transaction_date(
                int(day), month, period_start=period_start, period_end=period_end
            )
            if resolved is None:
                continue
            current_date = resolved.isoformat()
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


#: Public entry point for the French-language RBC layout, registered in its
#: own right by R-3. `parse_rbc_statement` still tries it first until the
#: pipeline switches to registry dispatch.
parse_rbc_french_statement = _parse_rbc_french_statement
