from __future__ import annotations

import re
from datetime import date, datetime

from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")

# The `Account Details` posting table declares its own columns. That printed
# header, and the footer/section boundary that closes it, are the structural
# bounds of everything this parser is allowed to read as a posting.
#
# A Scotiabank PDF is a bundle of statements for one account: `Business
# Account` carries the ledger, while `Service Charge` and `Deposit Interest`
# are separate printed statements in the same file. The `Deposit Interest`
# sheet is a DAILY-YIELD ledger — one dated row per calendar day, carrying
# that day's closing balance and the interest it earned — and it declares a
# different grid (`Date Closing Balance ($) Yield/Rate Calculated Interest
# ($)`). Splitting the whole document on dates therefore turned 28 daily
# yield rows into 28 fabricated postings on a statement whose own summary
# said four. Binding rows to this header excludes them by construction,
# without a blocklist of section names to keep up to date.
_TABLE_HEADER = re.compile(
    r"Date\s+Description\s+Withdrawals/Debits\s*\(\$\)\s+"
    r"Deposits/Credits\s*\(\$\)\s+Balance\s*\(\$\)",
    re.IGNORECASE,
)
_TABLE_CLOSE = re.compile(
    r"\bNo\.\s*of\s+Debits\b|\bStatement\s+Of:|\bPlease\s+examine\b"
    r"|\bUncollected\s+fees\b|---\s+Page\b",
    re.IGNORECASE,
)

# A printed balance is a currency value: two decimal places, optional
# thousands grouping, and the trailing minus this bank prints for an
# overdraft. A merchant reference number never takes this shape, which is
# what keeps `MRCH FIRST DATA CANADA(K)` continuation lines — an 11-digit
# reference printed AFTER the balance cell — from being read as a balance in
# the tens of billions and having the amounts back-solved from it.
_BALANCE_TOKEN = re.compile(r"\$?\d[\d,]*\.\d{2}-?")

# The amount column additionally appears with its trailing zeros stripped:
# this layout prints $25.00 as `25`, $2,500.00 as `2,500` and $34.90 as
# `34.9`.
_AMOUNT_TOKEN = re.compile(r"\$?\d[\d,]*(?:\.\d{1,2})?-?")

#: A bare integer with no thousands separator is dollars only while it is
#: short enough to be a printed amount. Longer unseparated runs are reference
#: numbers, account-number fragments and years, none of which are money.
_BARE_INTEGER_DIGITS = 3


def _is_balance_cell(token: str) -> bool:
    return bool(_BALANCE_TOKEN.fullmatch(token))


def _is_amount_cell(token: str) -> bool:
    if not _AMOUNT_TOKEN.fullmatch(token):
        return False
    core = token.strip("$-")
    if "." in core or "," in core:
        return True
    return len(core) <= _BARE_INTEGER_DIGITS


def _amount_value(token: str) -> float | None:
    """The printed amount cell as a number.

    `analysis.money.parse_money` requires two or three decimal places, so the
    trailing zeros this bank strips are restored before handing the token
    over. Padding the printed form at the call site is the division money.py
    documents: the engine is shared, the format stays with the bank.
    """
    core = token.strip("$")
    sign = "-" if core.endswith("-") else ""
    core = core.rstrip("-")
    if "." in core:
        whole, _, fraction = core.partition(".")
        core = f"{whole}.{(fraction + '00')[:2]}"
    else:
        core = f"{core}.00"
    return parse_money(core + sign)


def _posting_tables(markdown: str) -> list[str]:
    """The `Account Details` posting tables, in document order."""
    text = re.sub(r"\s+", " ", markdown)
    tables = []
    for header in _TABLE_HEADER.finditer(text):
        close = _TABLE_CLOSE.search(text, header.end())
        tables.append(text[header.end():close.start() if close else len(text)])
    return tables


def _split_rows(table: str) -> list[str]:
    text = re.sub(r"(?<!^)(?=\d{2}/\d{2}/\d{4}\s)", "\n", table)
    return [row.strip() for row in text.splitlines() if _DATE_RE.search(row)]


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    # "SCOTIABANK" alone matches an incoming-wire description in all three
    # Santander statements, so pair it with the issuer's legal name, which
    # Scotiabank prints in its own trademark footer.
    required("bank_name", lambda t: "SCOTIABANK" in t),
    required("issuer_identity", lambda t: "THE BANK OF NOVA SCOTIA" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_scotiabank_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    upper = markdown.upper()
    if not detect(markdown).claims:
        return None
    if "ACCOUNT DETAILS" not in upper and "WITHDRAWALS/DEBITS" not in upper:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Scotiabank"
    stmt.currency = "CAD"

    acct = re.search(r"Business Account\s+([0-9 ]{8,})", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = re.sub(r"\s+", " ", acct.group(1)).strip()
    period = re.search(r"Business Account\s+[0-9 ]+\s+([A-Za-z]{3}\s+\d{1,2}\s+\d{4})\s+([A-Za-z]{3}\s+\d{1,2}\s+\d{4})", markdown)
    if period:
        for attr, raw in (("period_start", period.group(1)), ("period_end", period.group(2))):
            parsed = datetime.strptime(raw, "%b %d %Y").date()
            setattr(stmt, attr, parsed.isoformat())

    # The account-level grid, which is printed once above `Account Details`
    # and states whole-direction figures. The per-page footers repeat the same
    # labels for that page alone, so this must stay a first-match search:
    # count_semantics records scotiabank as comparable in both directions on
    # the strength of these being the whole-period figures.
    summary = re.search(
        r"No\. of Debits Total Amount - Debits No\. of Credits Total Amount\s+-\s+Credits\s+"
        r"(?P<debit_count>\d+)\s+\$(?P<debits>[\d,]+\.\d{2})\s+"
        r"(?P<credit_count>\d+)\s+\$(?P<credits>[\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    if summary:
        stmt.stated_debit_count = int(summary.group("debit_count"))
        stmt.stated_total_debits = parse_money(summary.group("debits"))
        stmt.stated_credit_count = int(summary.group("credit_count"))
        stmt.stated_total_credits = parse_money(summary.group("credits"))

    txns: list[Transaction] = []
    prev_balance: float | None = None
    for table in _posting_tables(markdown):
        for row in _split_rows(table):
            m = _DATE_RE.search(row)
            if not m:
                continue
            tx_date = date(int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat()
            rest = row[m.end():].strip()
            if rest.upper().startswith("BALANCE FORWARD"):
                opening = [t for t in rest.split() if _is_balance_cell(t)]
                if opening:
                    stmt.beginning_balance = parse_money(opening[-1])
                    prev_balance = stmt.beginning_balance
                continue

            tokens = rest.split()
            balance_at = next(
                (i for i in range(len(tokens) - 1, -1, -1) if _is_balance_cell(tokens[i])),
                None,
            )
            if balance_at is None or prev_balance is None:
                continue
            amount_at = next(
                (i for i in range(balance_at - 1, -1, -1) if _is_amount_cell(tokens[i])),
                None,
            )
            #: A row whose printed amount cell cannot be located is dropped
            #: rather than published with a back-solved one. Dropping loses
            #: the amount, so the ledger stops reconciling and the document is
            #: withheld: fail closed.
            if amount_at is None:
                continue

            balance = parse_money(tokens[balance_at])
            printed = _amount_value(tokens[amount_at])
            if balance is None or printed is None:
                continue
            desc = " ".join(tokens[:amount_at]).strip()
            if not desc:
                continue

            #: The printed money cell is the amount of record. The balance
            #: column supplies only the DIRECTION, because this layout
            #: flattens `Withdrawals/Debits ($)` and `Deposits/Credits ($)`
            #: into one printed value whose column is lost in extraction.
            #:
            #: Where the two disagree the disagreement is published, not
            #: resolved: the printed magnitude ships, the printed balance
            #: ships, and `analysis.reconcile` sees a running-balance
            #: continuity break and a ledger-sum mismatch. Assigning the
            #: balance delta here instead — which is what this parser used to
            #: do — made `sum_delta` and `continuity_breaks` re-derive the
            #: parser's own arithmetic, so they were 0 on every document by
            #: construction and the fail-closed gate had nothing to check.
            magnitude = abs(printed)
            amount = round(magnitude if balance >= prev_balance else -magnitude, 2)
            txns.append(Transaction(
                date=tx_date,
                description=desc,
                amount=amount,
                direction="credit" if amount > 0 else "debit",
                running_balance=balance,
            ))
            prev_balance = balance

    if not txns:
        #: A period with no activity is a statement, not a parse failure —
        #: but only when the bank says so. It must have printed zero
        #: instances AND zero totals in both directions and an opening
        #: balance: then the closing balance is the opening balance, on the
        #: bank's own evidence. An empty ledger on any other document means
        #: the detail was not read, and that still refuses.
        printed_zero_activity = (
            stmt.stated_debit_count == 0
            and stmt.stated_credit_count == 0
            and stmt.stated_total_debits == 0.0
            and stmt.stated_total_credits == 0.0
        )
        if not printed_zero_activity or stmt.beginning_balance is None:
            return None
        if stmt.ending_balance is None:
            stmt.ending_balance = stmt.beginning_balance
        stmt.transactions = []
        return stmt
    if stmt.ending_balance is None:
        stmt.ending_balance = txns[-1].running_balance
    stmt.transactions = txns
    return stmt
