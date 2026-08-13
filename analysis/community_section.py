from __future__ import annotations

import re
from datetime import datetime

from .money import STRICT_LEADING_SIGN, STRICT_UNSIGNED, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction


_DATE = r"\d{2}/\d{2}/\d{4}"
_MONEY = r"\$[\d,]+\.\d{2}"
#: A *balance* is the only figure this platform prints with a sign: an
#: overdrawn period prints `-$1,234.56` for the opening and/or closing balance.
#: The period's credit and debit totals are magnitudes whose direction is the
#: row they are printed on, so they deliberately keep the unsigned pattern -
#: widening them would let a mis-read minus become a negative period total.
_SIGNED_MONEY = r"-?\$[\d,]+\.\d{2}"


def _money(value: str | None) -> float | None:
    return parse_amount(value, STRICT_UNSIGNED)


def _balance(value: str | None) -> float | None:
    return parse_amount(value, STRICT_LEADING_SIGN)


def _iso(value: str) -> str:
    return datetime.strptime(value, "%m/%d/%Y").date().isoformat()


def _clean(text: str) -> str:
    text = re.sub(r"--- Page \d+ ---", " ", text)
    text = re.sub(r"\b[A-F0-9]{32}\b \d{8} [A-Za-z ]+", " ", text)
    # Page headers on this statement platform are single lines ending in
    # "Page N of M" (holder name / account / "Statement Ending <date>").
    # Scrub them by that structural marker, never by customer name
    # (R-1 item 4 - replaced a literal holder-name scrub list).
    text = re.sub(r"(?m)^[^\n]{0,120}?Page \d+ of \d+", " ", text)
    text = re.sub(r"Account Number:\s*[X0-9]+", " ", text)
    text = re.sub(r"(?:Business Checking|Small Business Checking) - [X0-9]+ \(continued\)", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _account_block(markdown: str, account_heading: str | None = None) -> str:
    if not account_heading:
        return markdown
    start = markdown.find(account_heading)
    if start == -1:
        return ""
    return markdown[start:]


def _summary(block: str):
    return re.search(
        r"Account Summary Date Description Amount\s+"
        r"(" + _DATE + r") Beginning (?:Statement )?Balance (" + _SIGNED_MONEY + r")\s+"
        r"(\d+) Credit\(s\) This Period (" + _MONEY + r")\s+"
        r"(\d+) Debit\(s\) This Period (" + _MONEY + r")\s+"
        r"(" + _DATE + r") Ending (?:Statement )?Balance (" + _SIGNED_MONEY + r")",
        _clean(block),
        re.IGNORECASE | re.DOTALL,
    )


#: A transaction section on this platform is introduced by its own name
#: followed by the printed column header `Date Description Amount`, and the
#: **head noun of that name carries the direction**: the processor names its
#: sections `<qualifier> Credits` / `<qualifier> Debits`, plus the unqualified
#: `Deposits`.
#:
#: Reading the head noun rather than a list of whole section names is what
#: makes this a platform reader instead of a per-product one. A statement that
#: prints a qualifier this code has never seen is still read correctly, and
#: `Account Summary` - which prints the *identical* grid header - is excluded
#: structurally, because "Summary" is not a direction noun, rather than by
#: being named in a stop list. The lookbehind keeps the noun from matching
#: inside a longer word.
#:
#: A section reprinted after a page break repeats its name with `(continued)`,
#: and the whitespace around it is whatever the page break left behind, so the
#: reprint marker is separated by `\s+` like the grid header itself rather than
#: by a literal space.
_SECTION_RE = re.compile(
    r"(?<![A-Za-z])(?:[A-Za-z]+ )?(Credits|Debits|Deposits)"
    r"(?:\s+\(continued\))?\s+Date Description Amount",
    re.IGNORECASE,
)

#: The non-transaction blocks that can follow the last transaction section.
#: Each is guarded by the first word of its own grid header, so none of these
#: words can end a section from inside a transaction description.
_SECTION_END_RE = re.compile(
    r"\s+(?:Checks Cleared|Daily Balances|Overdraft|Service Charge Summary|Thank you)"
    r"\s+(?:Date|Check|Total)",
    re.IGNORECASE,
)

_CREDIT_NOUNS = frozenset({"credits", "deposits"})


def _sections(text: str) -> list[tuple[int, str]]:
    """`(sign, body)` for every transaction section, in printed order.

    A section runs from its own grid header to the next section's header, so
    rows always land in the section that printed them; the last one runs to
    whichever non-transaction block follows it.
    """
    matches = list(_SECTION_RE.finditer(text))
    sections: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        limit = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        end = _SECTION_END_RE.search(text, start, limit)
        sign = 1 if match.group(1).lower() in _CREDIT_NOUNS else -1
        sections.append((sign, text[start:end.start() if end else limit]))
    return sections


def _dated_amount_rows(body: str, *, sign: int, year: int) -> list[Transaction]:
    text = _clean(body)
    dates = list(re.finditer(r"\b" + _DATE + r"\b", text))
    txns: list[Transaction] = []
    for i, match in enumerate(dates):
        end = dates[i + 1].start() if i + 1 < len(dates) else len(text)
        chunk = text[match.start():end].strip()
        amounts = list(re.finditer(_MONEY, chunk))
        if not amounts:
            continue
        amount_match = amounts[-1]
        desc = re.sub(r"\s+", " ", chunk[len(match.group()):amount_match.start()]).strip()
        amount = _money(amount_match.group())
        if amount is None:
            continue
        if datetime.strptime(match.group(), "%m/%d/%Y").year != year:
            return []
        txns.append(
            Transaction(
                date=_iso(match.group()),
                description=desc,
                amount=round(sign * amount, 2),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return txns


def _check_rows(block: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for section in re.finditer(
        r"Checks Cleared\s+(.*?)(?=\s+(?:Daily Balances|Overdraft and Returned Item Fees|Service Charge Summary|Thank you)|$)",
        block,
        re.IGNORECASE | re.DOTALL,
    ):
        body = _clean(section.group(1))
        for match in re.finditer(r"(\d+\*?)\s+(" + _DATE + r")\s+(" + _MONEY + r")", body):
            amount = _money(match.group(3))
            if amount is None:
                continue
            if datetime.strptime(match.group(2), "%m/%d/%Y").year != year:
                return []
            txns.append(
                Transaction(
                    date=_iso(match.group(2)),
                    description=f"Check {match.group(1)}",
                    amount=round(-amount, 2),
                    direction="debit",
                )
            )
    return txns


def _daily_balances(block: str) -> dict[str, float]:
    start = re.search(r"Daily Balances\b(.*?)(?:Overdraft and Returned Item Fees|Service Charge Summary|Thank you|$)", block, re.IGNORECASE | re.DOTALL)
    if not start:
        return {}
    balances: dict[str, float] = {}
    for match in re.finditer(r"(" + _DATE + r")\s+(" + _MONEY + r")", _clean(start.group(1))):
        amount = _money(match.group(2))
        if amount is not None:
            balances[_iso(match.group(1))] = amount
    return balances


def _apply_daily_balances(txns: list[Transaction], balances: dict[str, float]) -> list[Transaction]:
    if not balances:
        return txns
    last_index: dict[str, int] = {}
    for i, txn in enumerate(txns):
        last_index[txn.date] = i
    updated = list(txns)
    for txn_date, balance in balances.items():
        idx = last_index.get(txn_date)
        if idx is not None:
            updated[idx] = updated[idx].model_copy(update={"running_balance": balance})
    return updated


def _parse_sectioned_statement(
    markdown: str,
    *,
    bank: str,
    account_name: str,
    account_heading: str | None = None,
    account_number_pattern: str | None = None,
) -> Statement | None:
    block = _account_block(markdown, account_heading)
    if not block:
        return None
    summary = _summary(block)
    if not summary:
        return None
    start_date, beginning, credit_count, credits, debit_count, debits, end_date, ending = summary.groups()
    start_year = datetime.strptime(start_date, "%m/%d/%Y").year
    end_year = datetime.strptime(end_date, "%m/%d/%Y").year
    if start_year != end_year:
        return None

    txns: list[Transaction] = []
    for sign, body in _sections(block):
        txns.extend(_dated_amount_rows(body, sign=sign, year=end_year))
    txns.extend(_check_rows(block, year=end_year))
    if not txns:
        return None
    txns.sort(key=lambda t: t.date)

    stmt = Statement(
        bank=bank,
        account_name=account_name,
        account_number=None,
        period_start=_iso(start_date),
        period_end=_iso(end_date),
        days_in_period=(datetime.strptime(end_date, "%m/%d/%Y").date() - datetime.strptime(start_date, "%m/%d/%Y").date()).days + 1,
        beginning_balance=_balance(beginning),
        ending_balance=_balance(ending),
        stated_total_credits=_money(credits),
        stated_total_debits=_money(debits),
        stated_credit_count=int(credit_count),
        stated_debit_count=int(debit_count),
        transactions=_apply_daily_balances(txns, _daily_balances(block)),
    )
    if account_number_pattern:
        acct = re.search(account_number_pattern, block, re.IGNORECASE)
        if acct:
            stmt.account_number = acct.group(1)

    credit_total = round(sum(t.amount for t in stmt.transactions if t.amount > 0), 2)
    debit_total = round(sum(abs(t.amount) for t in stmt.transactions if t.amount < 0), 2)
    credit_rows = sum(1 for t in stmt.transactions if t.amount > 0)
    debit_rows = sum(1 for t in stmt.transactions if t.amount < 0)
    if (
        abs(credit_total - (stmt.stated_total_credits or 0.0)) > 0.02
        or abs(debit_total - (stmt.stated_total_debits or 0.0)) > 0.02
        or credit_rows != stmt.stated_credit_count
        or debit_rows != stmt.stated_debit_count
    ):
        return None
    return stmt


MISSION_VALLEY_DETECTION_MARKERS = (
    required("bank_name", lambda t: "Mission Valley Bank" in t),
    # R4-3: the name alone matches a statement that merely pays the bank.
    required("issuer_domain", lambda t: "MISSIONVALLEYBANK.COM" in t.upper()),
)

DAKOTA_WEST_DETECTION_MARKERS = (
    required("domain", lambda t: "dakotawestcu.com" in t.lower()),
    # R4-3: the domain alone matches a statement that merely cites it.
    required("issuer_footer", lambda t: "DAKOTA WEST CREDIT UNION" in t.upper()),
)

detect_mission_valley = make_detector(MISSION_VALLEY_DETECTION_MARKERS)
detect_dakota_west = make_detector(DAKOTA_WEST_DETECTION_MARKERS)


def parse_mission_valley_statement(markdown: str) -> Statement | None:
    # Bank marker only - the customer-name gate is gone (R-1 item 4).
    if not detect_mission_valley(markdown).claims:
        return None
    return _parse_sectioned_statement(
        markdown,
        bank="Mission Valley Bank",
        account_name="Business Checking",
        account_number_pattern=r"Business Checking\s*-\s*([X0-9]+)",
    )


#: Section headings of this platform: "<product> (Checking|Savings) - <acct>"
#: on its own line ("(continued)" reprints are deliberately excluded).
_ACCOUNT_HEADING_RE = re.compile(
    r"^([A-Z][A-Za-z ]*?(?:Checking|Savings)) - (\d+)$", re.MULTILINE
)


def parse_dakota_west_statement(markdown: str) -> Statement | None:
    """Parse the busiest account section of a Dakota West statement.

    Account sections are discovered from the document's own headings and the
    section with the most transactions is selected (primary-account
    semantics), replacing the previous gate on one literal account number
    (R-1 item 5).
    """
    if not detect_dakota_west(markdown).claims:
        return None
    headings: list[tuple[str, str, int]] = []   # (heading, product, start)
    for match in _ACCOUNT_HEADING_RE.finditer(markdown):
        heading = match.group(0)
        if all(heading != seen for seen, _, _ in headings):
            headings.append((heading, match.group(1), match.start()))
    if not headings:
        return None

    best: Statement | None = None
    for index, (heading, product, start) in enumerate(headings):
        # Truncate at the next different account's heading so one section's
        # summary can never be attributed to another account.
        later_starts = [s for _, _, s in headings if s > start]
        block = markdown[start:min(later_starts)] if later_starts else markdown[start:]
        stmt = _parse_sectioned_statement(
            block,
            bank="Dakota West Credit Union",
            account_name=product,
            account_number_pattern=re.escape(product) + r"\s*-\s*(\d+)",
        )
        if stmt is not None and (
            best is None or len(stmt.transactions) > len(best.transactions)
        ):
            best = stmt
    return best
