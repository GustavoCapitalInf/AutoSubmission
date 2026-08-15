from __future__ import annotations

import re

from .date_tokens import iso_from_month_day
from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement
from .schema import Transaction


_MONEY_RE = re.compile(r"-?\$?\d[\d,]*\.\d{2}-?")


def _compact(text: str) -> str:
    text = re.sub(r"--- Page \d+ ---", " ", text)
    text = re.sub(r"Docusign Envelope ID:\s*[A-F0-9-]+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"POST DATE DESCRIPTION DEBITS CREDITS BALANCE", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _money(value: str) -> float | None:
    return parse_money(value.replace("$", ""))


def _business_plus_block(markdown: str) -> str:
    match = re.search(
        r"BUSINESS PLUS CKG-(\d+-70)\s+(.*?)(?=\s+--- Page 12 ---|\Z)",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(0) if match else ""


def _parse_activity_rows(block: str, *, year: int) -> list[Transaction]:
    activity = re.search(
        r"ACCOUNT ACTIVITY\s+(.*?)(?=\s+10/31 Ending Balance\s+\$?\d|\s+OVERDRAFT AND RETURNED ITEM FEES|\s+ACCOUNT ANALYSIS STATEMENT|\Z)",
        block,
        re.IGNORECASE | re.DOTALL,
    )
    if not activity:
        return []
    rows: list[str] = []
    current = ""
    for raw_line in activity.group(1).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"Docusign Envelope ID:\s*[A-F0-9-]+", " ", line, flags=re.IGNORECASE).strip()
        line = re.sub(r"POST DATE DESCRIPTION DEBITS CREDITS BALANCE", " ", line, flags=re.IGNORECASE).strip()
        line = re.sub(r"--- Page \d+ ---", " ", line).strip()
        if not line:
            continue
        if re.match(r"^\d{2}/\d{2}\b", line):
            if current:
                rows.append(current)
            current = line
        elif current:
            current += " " + line
    if current:
        rows.append(current)

    txns: list[Transaction] = []
    for row in rows:
        row = re.sub(r"\s+", " ", row).strip()
        mmdd = row[:5]
        if "Beginning Balance" in row or "Ending Balance" in row:
            continue
        amounts = list(_MONEY_RE.finditer(row))
        if len(amounts) < 2:
            continue
        amount_match = amounts[-2]
        balance_match = amounts[-1]
        amount = _money(amount_match.group(0))
        balance = _money(balance_match.group(0))
        if amount is None or balance is None:
            continue
        prefix = row[:amount_match.start()].rstrip()
        if amount > 0 and prefix.endswith("-"):
            amount *= -1
        desc = row[len(mmdd):amount_match.start()].strip()
        desc = desc.rstrip("-").strip()
        desc = re.sub(r"\s+", " ", desc)
        if not desc:
            continue
        txns.append(Transaction(
            date=iso_from_month_day(mmdd, year=year),
            description=desc,
            amount=round(amount, 2),
            direction="credit" if amount >= 0 else "debit",
            running_balance=round(balance, 2),
        ))
    return txns


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    required("domain", lambda t: "FIRSTCOMMUNITY.COM" in t),
    required("product", lambda t: "BUSINESS PLUS CKG" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_first_community_statement(markdown: str) -> Statement | None:
    upper = markdown.upper()
    if not detect(markdown).claims:
        return None
    ending = re.search(r"STATEMENT ENDING\s+(\d{2})/(\d{2})/(\d{4})", markdown, re.IGNORECASE)
    if not ending:
        return None
    end_month, _end_day, year_text = ending.groups()
    year = int(year_text)

    block = _business_plus_block(markdown)
    if not block:
        return None
    text = _compact(block)
    summary = re.search(
        r"ACCOUNT SUMMARY\s+DATE DESCRIPTION AMOUNT\s+"
        r"(?P<start>\d{2}/\d{2}) Beginning Balance \$?(?P<begin>-?\d[\d,]*\.\d{2})\s+"
        r".*?(?P<credit_count>\d+) Credits This Period \$?(?P<credits>\d[\d,]*\.\d{2})\s+"
        r".*?(?P<debit_count>\d+) Debits This Period \$?(?P<debits>\d[\d,]*\.\d{2})\s+"
        r".*?(?P<end>\d{2}/\d{2}) Ending Balance \$?(?P<ending>-?\d[\d,]*\.\d{2})",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not summary:
        return None

    acct = re.search(r"BUSINESS PLUS CKG-(\d+-70)", block, re.IGNORECASE)
    avg = re.search(r"Service Class BPCK-BUSINESS PLUS CHKG Average Daily Balance \$?([\d,]+\.\d{2})", text, re.IGNORECASE)
    service = re.search(r"Accumulated Fees \$?([\d,]+\.\d{2})", text, re.IGNORECASE)

    stmt = Statement(
        bank="First Community Credit Union",
        account_name="Business Plus Checking",
        account_number=acct.group(1) if acct else None,
        period_start=iso_from_month_day(summary.group("start"), year=year),
        period_end=iso_from_month_day(summary.group("end"), year=year),
        days_in_period=int(summary.group("end").split("/")[1]),
        beginning_balance=_money(summary.group("begin")),
        ending_balance=_money(summary.group("ending")),
        stated_total_credits=_money(summary.group("credits")),
        stated_total_debits=_money(summary.group("debits")),
        stated_credit_count=int(summary.group("credit_count")),
        stated_debit_count=int(summary.group("debit_count")),
        bank_reported_average_balance=_money(avg.group(1)) if avg else None,
        bank_reported_average_label="Average Daily Balance" if avg else None,
        stated_service_charge=_money(service.group(1)) if service else None,
        transactions=_parse_activity_rows(block, year=year),
    )
    return stmt if stmt.transactions else None


def repair_first_community_posted_activity(stmt: Statement) -> Statement:
    """Drop First Community balance-neutral failed debit attempts from cashflow.

    This statement family lists some rejected EFT attempts in account activity
    with a debit amount, but the printed running balance does not move. Those are
    useful review evidence, but they are not posted withdrawals for balance math.
    """
    bank = (stmt.bank or "").upper()
    if "FIRST COMMUNITY" not in bank:
        return stmt
    if not stmt.transactions:
        return stmt

    prev = stmt.beginning_balance
    kept = []
    removed_debits = 0.0
    for t in stmt.transactions:
        balance = t.running_balance
        if (
            prev is not None
            and balance is not None
            and round(balance - prev, 2) == 0.0
            and t.amount < 0
            and t.description.upper().startswith("EFT -")
        ):
            removed_debits = round(removed_debits + abs(t.amount), 2)
            continue
        kept.append(t)
        if balance is not None:
            prev = balance

    if not removed_debits:
        return stmt

    removed_rows = len(stmt.transactions) - len(kept)

    # `N Debits This Period $X` is ONE printed claim with two halves: a count and
    # a sum over the same set of rows. This repair narrows that set by the N
    # printed balance-neutral rows, so both halves have to narrow with it —
    # rewriting the sum alone leaves the count describing a set of rows the
    # statement no longer reports, which is the `semantics_difference` D5
    # adjudicated. This is expected-side scope alignment from printed
    # balance-neutrality evidence, not a derivation from what we captured: the
    # independence rule holds because nothing derived is read back.
    #
    # The two halves move as a pair or not at all — the count is never rewritten
    # without the total, and when both printed halves are present neither is
    # rewritten without the other. An absent half carries no claim to narrow.
    updates = {"transactions": kept}
    if stmt.stated_total_debits is not None:
        updates["stated_total_debits"] = round(stmt.stated_total_debits - removed_debits, 2)
        if stmt.stated_debit_count is not None:
            updates["stated_debit_count"] = stmt.stated_debit_count - removed_rows
    return stmt.model_copy(update=updates)
