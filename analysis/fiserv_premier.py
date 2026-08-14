"""The Fiserv Premier `Statement of Account`, parenthesised-counts issue.

Fiserv Premier is a core banking platform, not a bank: the same printed
template is issued by many institutions, and the registry already holds three
parsers for banks that run on it (`linkbank`, `capital_one`,
`farmers_merchants`), each keyed on its own issuer's furniture. This module is
deliberately narrower than "Fiserv": it reads the **parenthesised-counts**
issue of the summary block,

    Previous Balance $4,778.62 Average Ledger $3,220.98
    Deposits/Credits (28) $17,321.67 Average Collected $3,220.98
    Checks/Debits (60) $17,224.89 Service Charge $0.00
    Interest Paid $0.00 Ending Balance $4,875.40

which is disjoint from the leading-counts issue those three parsers read
(`26 Deposits/Credits 221,708.70`). The disjointness is measured, not assumed —
see the anti-collision note below and `tests/test_fiserv_premier.py`.

**Detection.** The counts clause on its own is not usable evidence. Written the
obvious way it is a bare digit run in front of a label, and the digit run it
finds on a Wells Fargo statement is the last three digits of the balance
printed to the left of `Deposits/Credits` — which matched 216 of the 236
Wells Fargo documents in the stratified probe. The conjunction this module
registers therefore *requires* the opening-balance clause (`Previous Balance`,
which no Wells Fargo layout prints) alongside the counts clause and the
template's own `Statement of Account` heading. Each of the three is necessary;
the scoring rule makes that literal, since one missing required marker caps the
score below the claim threshold no matter how much else fires.

**The issuer is read off the document.** The template prints only a domain in
its customer-service block, so the bank's name is recovered structurally: the
statement's return address is reprinted in the disclosure directory beside the
name of the division that owns it, and the name is the text in front of it.
A document whose directory does not resolve to exactly one name is refused —
this parser will not name a bank the page does not.

**Two ledger shapes**, both gated on the summary's own counts and totals:
a single `Transaction Activity` grid carrying a running balance, whose chain is
walked from the opening balance to the closing one; and separate
`Credit Transactions` / `Debit Transactions` sections with no balance column,
where the counts and totals are the whole of the evidence.
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_within_period
from .money import PARENS_OR_LEADING_MINUS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

#: `$1,234.56`, `-$1,234.56`, `1,234.56`, `.56`.
_MONEY = r"-?\$?-?(?:[\d,]+\.\d{2}|\.\d{2})"

#: Detection runs over `detection_text`, which is upper-cased; parsing runs
#: over the document as printed. These two are used by detection only, so they
#: are case-insensitive rather than assuming either.
_COUNTS_CREDIT_RE = re.compile(r"DEPOSITS/CREDITS\s*\(\d+\)", re.IGNORECASE)
_COUNTS_DEBIT_RE = re.compile(r"CHECKS/DEBITS\s*\(\d+\)", re.IGNORECASE)

_SUMMARY_RE = re.compile(
    r"Previous Balance\s+(" + _MONEY + r")"
    r"(?:\s+Average Ledger\s+(" + _MONEY + r"))?"
    r"\s+Deposits/Credits\s*\((\d+)\)\s*(" + _MONEY + r")"
    r"(?:\s+Average Collected\s+(" + _MONEY + r"))?"
    r"\s+Checks/Debits\s*\((\d+)\)\s*(" + _MONEY + r")"
    r"(?:\s+Service Charge\s+(" + _MONEY + r"))?"
    r"(?:\s+Interest Paid\s+(" + _MONEY + r"))?"
    r"\s+(?:Ending|Current) Balance\s+(" + _MONEY + r")"
)

_PERIOD_RE = re.compile(
    r"Statement Dates\s+(\d{1,2})/(\d{1,2})/(\d{2})\s+to\s+"
    r"(\d{1,2})/(\d{1,2})/(\d{2})\s*\((\d+)\s*days?\)"
)
_TITLE_RE = re.compile(r"Account Title:\s*(.+?)\s*$", re.MULTILINE)
_PRODUCT_RE = re.compile(r"^(.+?)\s+-\s+(X+\d+)\s*$", re.MULTILINE)

#: The statement's own return address, printed at the top of page one.
_RETURN_RE = re.compile(
    r"^(PO Box \d+|\d+ [A-Z][^\n,]{3,40})\s+([A-Za-z .'\-]+),\s*[A-Z]{2}\s+\d{5}",
    re.MULTILINE,
)

_PAGE_RE = re.compile(r"^--- Page \d+")
_ACTIVITY_RE = re.compile(r"^Transaction Activity\s+Date\s+Description\s+Debits\s+Credits\s+Balance\b(.*)$")
_CREDIT_RE = re.compile(r"^Credit Transactions\s+Date\s+Description\s+Amount\b(.*)$")
_DEBIT_RE = re.compile(r"^Debit Transactions\s+Date\s+Description\s+Amount\b(.*)$")

#: `3/02 DESCRIPTION -$17.39 $423.43` — amount then running balance.
_ACTIVITY_ROW_RE = re.compile(
    r"(?<![\d/])(\d{1,2}/\d{1,2})\s+(.+?)\s+(-?\$" + r"[\d,]*\.\d{2})\s+(-?\$[\d,]*\.\d{2})(?=\s|$)"
)
#: `4/01 DESCRIPTION $145.35` — one amount, direction fixed by the section.
#:
#: The description is OPTIONAL because the cheque recap printed at the foot of
#: the debit section identifies its items by number, and an item drawn without
#: one prints as a bare `2/26 $20.00`. It is also `[^$]` rather than `.`: with
#: an unconstrained description the engine happily spans a bare pair into the
#: next row's amount and silently merges two postings into one.
_PLAIN_ROW_RE = re.compile(
    r"(?<![\d/])(\d{1,2}/\d{1,2})\s+(?:([^$]+?)\s+)?(-?\$[\d,]*\.\d{2})(?=\s|$)"
)

_TOLERANCE = 0.005


def _money(value: str | None) -> float | None:
    return parse_amount(value, PARENS_OR_LEADING_MINUS)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    required("statement_of_account", lambda t: "STATEMENT OF ACCOUNT" in t),
    # THE ANTI-COLLISION CLAUSE, and it is required rather than corroborating:
    # the counts clause alone reaches 216 of 236 Wells Fargo documents, and no
    # Wells Fargo layout prints an opening balance under this name.
    required("opening_balance", lambda t: "PREVIOUS BALANCE" in t),
    required(
        "parenthesised_counts",
        lambda t: bool(_COUNTS_CREDIT_RE.search(t)) and bool(_COUNTS_DEBIT_RE.search(t)),
    ),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def _issuer(markdown: str) -> str | None:
    """The division that issued this statement, read off the printed page.

    The customer-service block carries a domain but no name. The disclosure
    directory carries both, for every division of the group, so the statement's
    own return address is what selects the right row of it.
    """
    ret = _RETURN_RE.search(markdown)
    if ret is None:
        return None
    anchor = f"{ret.group(1)} {ret.group(2)}"
    named = re.compile(r"([A-Z][A-Za-z.&'\- ]{2,40}?)\s+" + re.escape(anchor))
    candidates = {
        name.strip()
        for name in (m.group(1) for m in named.finditer(markdown))
        # The text layer emits runs of one repeated glyph as page furniture.
        if len(set(name.strip().replace(" ", ""))) > 1
    }
    return candidates.pop() if len(candidates) == 1 else None


def _summary(markdown: str):
    m = _SUMMARY_RE.search(markdown)
    if m is None:
        return None
    (
        previous, _average_ledger, credit_count, credits, _average_collected,
        debit_count, debits, service_charge, interest, closing,
    ) = m.groups()
    values = {
        "previous": _money(previous),
        "credits": _money(credits),
        "debits": _money(debits),
        "closing": _money(closing),
        "service_charge": _money(service_charge) if service_charge else 0.0,
        "interest": _money(interest) if interest else 0.0,
        "average": _money(_average_ledger) if _average_ledger else None,
    }
    if any(v is None for k, v in values.items() if k != "average"):
        return None
    values["credit_count"] = int(credit_count)
    values["debit_count"] = int(debit_count)
    return values


#: The `Daily Balance` recap is printed inside the last ledger section rather
#: than after it, and its `date amount` pairs are row-shaped. It is a printed
#: recap, not posting detail, so it TERMINATES the ledger — the same structural
#: bound the section headings provide everywhere else in this template.
_DAILY_BALANCE_RE = re.compile(r"Daily Balance\s+Date\s+Amount")
#: `4/01 $3,174.46`, with no description between the two — which is exactly what
#: distinguishes a recap pair from a posting row.
_DAILY_PAIR_RE = re.compile(r"(?<![\d/])(\d{1,2}/\d{1,2})\s+(-?\$[\d,]*\.\d{2})(?![\d.,])")


def _sections(markdown: str) -> dict[str, str]:
    gathered: dict[str, list[str]] = {"activity": [], "credit": [], "debit": []}
    current: str | None = None
    for line in markdown.splitlines():
        line = line.rstrip()
        if _PAGE_RE.match(line):
            current = None
            continue
        for name, pattern in (
            ("activity", _ACTIVITY_RE), ("credit", _CREDIT_RE), ("debit", _DEBIT_RE),
        ):
            head = pattern.match(line)
            if head:
                current = name
                if head.group(1).strip():
                    gathered[name].append(head.group(1).strip())
                break
        else:
            if current is not None:
                gathered[current].append(line)

    sections = {name: " ".join(lines) for name, lines in gathered.items()}
    recap: list[str] = []
    for name, text in list(sections.items()):
        cut = _DAILY_BALANCE_RE.search(text)
        if cut:
            sections[name] = text[: cut.start()]
            recap.append(text[cut.end():])
    sections["daily"] = " ".join(recap)
    return sections



def _activity_rows(text: str, start: date, end: date, opening: float):
    """The single-grid shape: every row's balance must continue the chain."""
    rows: list[Transaction] = []
    running = opening
    for m in _ACTIVITY_ROW_RE.finditer(text):
        amount = _money(m.group(3))
        balance = _money(m.group(4))
        posted = iso_within_period(m.group(1), start, end)
        if amount is None or balance is None or posted is None:
            return None
        if abs(round(running + amount, 2) - balance) > _TOLERANCE:
            return None
        running = balance
        rows.append(
            Transaction(
                date=posted,
                description=re.sub(r"\s+", " ", m.group(2)).strip(),
                amount=amount,
                direction="credit" if amount >= 0 else "debit",
                running_balance=balance,
            )
        )
    return rows


def _plain_rows(text: str, start: date, end: date, sign: int):
    rows: list[Transaction] = []
    for m in _PLAIN_ROW_RE.finditer(text):
        amount = _money(m.group(3))
        posted = iso_within_period(m.group(1), start, end)
        if amount is None or posted is None:
            return None
        rows.append(
            Transaction(
                date=posted,
                description=re.sub(r"\s+", " ", m.group(2) or "").strip(),
                amount=sign * abs(amount),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return rows


def parse_fiserv_premier_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    summary = _summary(markdown)
    period = _PERIOD_RE.search(markdown)
    issuer = _issuer(markdown)
    if summary is None or period is None or issuer is None:
        return None

    sm, sd, sy, em, ed, ey, days = (int(part) for part in period.groups())
    try:
        start = date(2000 + sy, sm, sd)
        end = date(2000 + ey, em, ed)
    except ValueError:
        return None
    if end < start:
        return None

    # The summary closes on itself before any row is read.
    #
    # The fee terms are treated as SEPARATE from the two transaction totals —
    # a service charge is not inside `Checks/Debits`, interest is not inside
    # `Deposits/Credits`. Every document of this family in the archive prints
    # both as zero, so that reading is not corroborated by the corpus; it is
    # kept because getting it wrong fails CLOSED. A charge that is in fact
    # already inside the debit total would be subtracted twice here, the
    # identity would miss, and the document would be refused rather than
    # published with a wrong opening or closing balance.
    walked = (
        summary["previous"]
        + abs(summary["credits"])
        - abs(summary["debits"])
        - abs(summary["service_charge"])
        + abs(summary["interest"])
    )
    if abs(walked - summary["closing"]) > _TOLERANCE:
        return None

    sections = _sections(markdown)
    if sections["activity"]:
        if sections["credit"] or sections["debit"]:
            return None  # two ledger shapes in one document: not understood
        transactions = _activity_rows(
            sections["activity"], start, end, summary["previous"]
        )
        if transactions is None:
            return None
        if abs((transactions[-1].running_balance if transactions else summary["previous"])
               - summary["closing"]) > _TOLERANCE:
            return None
    elif sections["credit"] or sections["debit"]:
        credits = _plain_rows(sections["credit"], start, end, 1)
        debits = _plain_rows(sections["debit"], start, end, -1)
        if credits is None or debits is None:
            return None
        transactions = credits + debits
    else:
        return None

    if not transactions:
        return None

    # The summary's own counts and totals are the gate on the rows.
    credit_rows = [t for t in transactions if t.amount > 0]
    debit_rows = [t for t in transactions if t.amount < 0]
    if len(credit_rows) != summary["credit_count"]:
        return None
    if len(debit_rows) != summary["debit_count"]:
        return None
    if abs(sum(t.amount for t in credit_rows) - abs(summary["credits"])) > _TOLERANCE:
        return None
    if abs(sum(-t.amount for t in debit_rows) - abs(summary["debits"])) > _TOLERANCE:
        return None

    # Only the split-section shape is re-ordered, because its credits and debits
    # are printed in two separate runs. The single-grid shape is left in the
    # order the document printed it: its rows carry running balances whose chain
    # was verified in exactly that order, and re-ordering them would publish a
    # balance sequence the document does not show.
    if all(txn.running_balance is None for txn in transactions):
        transactions.sort(key=lambda txn: txn.date)
    title = _TITLE_RE.search(markdown)
    product = _PRODUCT_RE.search(markdown)
    return Statement(
        bank=issuer,
        account_name=(product.group(1).strip() if product
                      else title.group(1).strip() if title else None),
        account_number=product.group(2) if product else None,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=days,
        beginning_balance=summary["previous"],
        ending_balance=summary["closing"],
        stated_total_credits=abs(summary["credits"]),
        stated_total_debits=abs(summary["debits"]),
        stated_credit_count=summary["credit_count"],
        stated_debit_count=summary["debit_count"],
        stated_average_balance=summary["average"],
        stated_service_charge=abs(summary["service_charge"]),
        stated_interest_paid=abs(summary["interest"]),
        transactions=transactions,
    )
