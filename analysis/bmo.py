from __future__ import annotations

import calendar
import re
from datetime import date

from .dates import resolve_year
from .money import money_refusal, parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace

_ROW_RE = re.compile(
    r"(\d{1,2}/\d{1,2})\s+(.*?)\s+\$\s*(\d[\d,]*\.\d{2})\s+"
    r"\$\s*(\d[\d,]*\.\d{2})(?=\s+\d{1,2}/\d{1,2}|\s+Page\s+\d+\b|\s*$)",
    re.IGNORECASE,
)
# Only used when contradictory printed balances make column direction
# impossible to infer. A valid BMO ledger is oriented from balance continuity.
_WITHDRAWAL_KEYS = (
    "LABORATORY SERVICES",
    "OFFICE SUPPLIES",
    "MEDICAL EQUIPMENT RENTAL",
    "PHARMACY SERVICES",
    "UTILITIES",
    "INSURANCE PREMIUM",
    "MEDICAL SUPPLIES",
    "OFFICE LEASE",
    "EQUIPMENT MAINTENANCE",
    "DIAGNOSTIC TESTING",
    "LAB ANALYSIS",
    "STERILIZATION",
    "DIGITAL X-RAY",
    "MEDICATION REFILL",
)


def _amount(value: str) -> float:
    """The printed cell as a number, refusing rather than inventing one.

    The refusal names this reader and the token's SHAPE, never the cell
    (`money._refusal`, W3 §MONEYPRIV; this site is §PRIVACY3's). Control flow is
    unchanged: the same tokens raise, with the same class, at the same line.
    """
    cleaned = value.replace("$", "").strip()
    parsed = parse_money(cleaned)
    if parsed is None:
        raise money_refusal("bmo._amount", value)
    return parsed


def _is_withdrawal(description: str) -> bool:
    upper = description.upper()
    return any(key in upper for key in _WITHDRAWAL_KEYS)


def _statement_period(text: str) -> tuple[date, date] | None:
    match = re.search(
        r"Statement Period:\s*([A-Za-z]+)\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        month = list(calendar.month_name).index(match.group(1).title())
        year = int(match.group(2))
    except ValueError:
        return None
    start = date(year, month, 1)
    return start, date(year, month, calendar.monthrange(year, month)[1])


def _account_name(markdown: str, text: str) -> str | None:
    for raw_line in markdown.splitlines():
        line = compact_whitespace(raw_line)
        match = re.match(
            r"(?P<name>.+?)\s+\d+\s+\S.*?\bAccount Number:",
            line,
            re.IGNORECASE,
        )
        if match:
            return match.group("name").strip()
    match = re.search(
        r"Customer Service:\s*[\d() +.-]+\s+(?P<name>.+?)\s+\d+\s+\S.*?"
        r"\bAccount Number:",
        text,
        re.IGNORECASE,
    )
    return match.group("name").strip() if match else None


def _signed_amount(
    description: str,
    amount: float,
    running_balance: float,
    previous_balance: float | None,
) -> float:
    if previous_balance is not None:
        credit_matches = abs(previous_balance + amount - running_balance) <= 0.01
        debit_matches = abs(previous_balance - amount - running_balance) <= 0.01
        if credit_matches != debit_matches:
            return amount if credit_matches else -amount
    return -amount if _is_withdrawal(description) else amount


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    required("bank_name", lambda t: "BMO" in t or "BANK OF MONTREAL" in t),
    # "BMO" is three characters and matches inside opaque reference ids
    # ("BMOZ000RIJ8B" in a Chase Zelle row) and wire beneficiaries in Wells
    # Fargo, RBC and Citizens statements. Require BMO's own summary heading
    # too (R3_DETECTION_FINDING.md).
    required("summary_section", lambda t: "ACCOUNT SUMMARY TOTALS" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_bmo_statement(markdown: str) -> Statement | None:
    upper = markdown.upper()
    if not detect(markdown).claims:
        return None
    if "TRANSACTION DETAILS" not in upper or "ACCOUNT SUMMARY" not in upper:
        return None

    text = compact_whitespace(markdown)
    period = _statement_period(text)
    if period is None:
        return None
    period_start, period_end = period
    currency = re.search(r"Currency:\s*([A-Z]{3})\b", text, re.IGNORECASE)
    stmt = Statement(
        bank="BMO",
        currency=currency.group(1).upper() if currency else "CAD",
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
    )

    acct = re.search(r"Account Number:\s*([0-9]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    stmt.account_name = _account_name(markdown, text)

    sm = re.search(
        r"Opening Balance\s+\$\s*(?P<begin>\d[\d,]*\.\d{2})\s+"
        r"Total Deposits\s+\$\s*(?P<credits>\d[\d,]*\.\d{2})\s+"
        r"Total Withdrawals\s+\$\s*(?P<debits>\d[\d,]*\.\d{2})\s+"
        r"Interest Earned\s+\$\s*(?P<interest>\d[\d,]*\.\d{2})\s+"
        r"Fees and Charges\s+\$\s*-?(?P<fees>\d[\d,]*\.\d{2})\s+"
        r"Closing Balance\s+\$\s*(?P<ending>\d[\d,]*\.\d{2})",
        text,
        re.IGNORECASE,
    )
    if sm:
        stmt.beginning_balance = _amount(sm.group("begin"))
        stmt.ending_balance = _amount(sm.group("ending"))
        stmt.stated_total_credits = _amount(sm.group("credits"))
        stmt.stated_total_debits = _amount(sm.group("debits"))
        stmt.stated_interest_paid = _amount(sm.group("interest"))
        stmt.stated_service_charge = _amount(sm.group("fees"))

    details = re.search(
        r"Transaction Details\s+Date\s+Description\s+Withdrawal\s+Deposit\s+Balance\s+"
        r"(.*?)(?=\s+Account Summary Totals\b|\s+Important Information\b|$)",
        text,
        re.IGNORECASE,
    )
    if not details:
        return stmt if stmt.account_number else None

    block = details.group(1)
    txns: list[Transaction] = []
    previous_balance = stmt.beginning_balance
    for mmdd, raw_desc, raw_amount, raw_balance in _ROW_RE.findall(block):
        desc = compact_whitespace(raw_desc)
        if not desc:
            continue
        amount = abs(_amount(raw_amount))
        balance = _amount(raw_balance)
        amount = _signed_amount(desc, amount, balance, previous_balance)
        month, day = (int(part) for part in mmdd.split("/"))
        year = resolve_year(month, day, period_start, period_end)
        if year is None:
            continue
        try:
            transaction_date = date(year, month, day)
        except ValueError:
            continue
        previous_balance = balance
        txns.append(Transaction(
            date=transaction_date.isoformat(),
            description=desc,
            amount=round(amount, 2),
            direction="credit" if amount > 0 else "debit",
            running_balance=balance,
        ))

    stmt.transactions = txns
    return stmt


def summary_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """BMO prints a second summary block; report where the two disagree.

    Registered as this parser's `integrity_check`, so it runs when - and only
    when - a BMO statement is on the table. Before R-3 it lived in
    analysis/pipeline.py behind a `stmt.bank == "BMO"` literal, which is the
    kind of bank knowledge the orchestrator should not carry.
    """
    text = " ".join(markdown.split())

    contradictions: list[str] = []
    secondary = re.search(
        r"Account Summary Totals\s+(.*?)(?:Important Information|Page 2 of 2|$)",
        text,
        re.IGNORECASE,
    )
    secondary_text = secondary.group(1) if secondary else ""

    def secondary_amount(label: str) -> float | None:
        if not secondary_text:
            return None
        m = re.search(
            label + r"\s+\$?\s*(-?\d[\d,]*\.\d{2})",
            secondary_text,
            re.IGNORECASE,
        )
        if not m:
            return None
        return parse_money(m.group(1))

    page_total_deposits = secondary_amount(r"Total Deposits")
    if (
        stmt.stated_total_credits is not None
        and page_total_deposits is not None
        and abs(stmt.stated_total_credits - page_total_deposits) > 0.01
    ):
        contradictions.append(
            "conflicting bank-stated deposit totals across summary sections"
        )

    page_total_withdrawals = secondary_amount(r"Total Withdrawals")
    page_interest = secondary_amount(r"Interest Earned")
    page_fees = secondary_amount(r"Service Fees")
    page_final = secondary_amount(r"Final Balance")
    if (
        stmt.beginning_balance is not None
        and page_total_deposits is not None
        and page_total_withdrawals is not None
        and page_final is not None
    ):
        base = (
            stmt.beginning_balance
            + page_total_deposits
            - page_total_withdrawals
            + (page_interest or 0.0)
        )
        # Some statements include fees in withdrawals; others list them separately.
        residuals = [base - page_final]
        if page_fees is not None:
            residuals.append(base - page_fees - page_final)
        if min(abs(residual) for residual in residuals) > 1.0:
            contradictions.append(
                "secondary bank-stated summary does not reconcile to the opening and final balances"
            )
    return contradictions
