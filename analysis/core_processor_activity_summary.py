"""A core processor's `Activity Summary` running-balance statement.

W3 §COREISS2, census rank 11 (`poplar_bluff_activity_summary_running`, n=6).
The printed issue whose summary is a boxed `Activity Summary` and whose ledger
carries a per-row running balance::

    Statement of Account  Statement Dates: <m/dd/yy> thru <m/dd/yy>
    Page:  <n>  of  <m>
    Activity Summary
    Account Number <number>  Days in Cycle <n>
        Average Ledger Balance $<fig>  Avg Collected Balance $<fig>
    <PRODUCT>  Beginning Balance $<fig>  <n> Deposits/Credits $<fig>
        <m> Checks/Debits $<fig>  Service Charge $<fig>  Interest Paid $<fig>
        Balance this Statement $<fig>
    Statement Balance $<fig>
    Debits $<fig>
    Credits $<fig>
    Account Activity
    Date Description Amount Balance

SIBLING, NOT AN EXTENSION - the ruling and its evidence
--------------------------------------------------------
Three registrations already read a LEADING-counts `<n> Deposits/Credits`
summary: `linkbank`, `farmers_merchants` and `capital_one`. All three are
ISSUER-keyed (`linkbank` requires the domain `LINKBANK.COM`), and this family
prints no institution at all - a PO box, a telephone and nothing else - so
there is no issuer to key on and no issuer registration to extend.
`fiserv_premier` is the other candidate the census names, and it is the wrong
one twice over: it declares `PREVIOUS BALANCE` and `DEPOSITS/CREDITS (N)` as
required markers, this family prints neither, and its module docstring
records the LEADING-counts issue as deliberately DISJOINT from the
parenthesised one it reads. Measured over the 3,396 documents of the OCR
artifact store:

=====================================  ========  =======
marker                                  archive   this 6
=====================================  ========  =======
`PREVIOUS BALANCE`                          311        0
`BALANCE LAST STATEMENT`                     46        0
`DEPOSITS/CREDITS (N)`                       14        0
`BALANCE THIS STATEMENT`                     55        6
`ACTIVITY SUMMARY` (own line)                58        6
`DAYS IN CYCLE <n>`                          48        6
this registration's conjunction               6        6
=====================================  ========  =======

`DAYS IN CYCLE` is the anti-collision clause and it is required rather than
corroborating. The archive's large leading-counts cohort prints its period
LENGTH as `Days in the statement period` (303 documents) beside a `Previous
Balance` or a `Balance Last Statement`; this issue prints `Days in Cycle`
inside an `Activity Summary` box beside a `Beginning Balance`, and the two
vocabularies do not meet on a single document.

WHAT THE DOCUMENT HAS TO PROVE BEFORE ANYTHING IS PUBLISHED
------------------------------------------------------------
Six printed facts, all of them, exactly:

1. `Days in Cycle` equals the inclusive calendar span of the printed
   `Statement Dates` - two independent reads of the ADB denominator;
2. the summary's own identity, `beginning + credits - debits - service charge
   + interest == balance this statement`;
3. the RESTATED trio (`Statement Balance` / `Debits` / `Credits`, printed a
   second time under the box) equals the trio inside the box;
4. the row count in each direction equals the count the summary prints;
5. the row total in each direction equals the total the summary prints;
6. the running-balance chain walks from the printed beginning balance to the
   printed closing balance with no break - every row's own printed balance
   must be the previous balance plus that row's amount.

The chain is what makes this reader immune to the two duplicating regions this
template prints after its ledger. A `Checks in Number Order` grid and an
unheaded image index both restate cheque rows that are already postings, and a
reader that swept the document for date-and-amount pairs would count them
twice; here the ledger is cut at the grid's own banner AND any double-counted
row would break the chain at the row after it.

THE SIGN IS INSIDE THE AMOUNT TOKEN, AND IT LEADS
--------------------------------------------------
A debit prints `-$1,234.56` and a negative running balance prints `-$1,234.56`
- the minus is before the sigil, not after it. A reader anchored on `\\$` loses
exactly the overdraft rows, which is the one tokenizer trap in this family.
`_ROW_RE` therefore takes the sign as part of the money token and lets
`money.py` read it; the direction is the sign's, because this ledger prints
one undivided section rather than one section per direction.

A ZERO-amount row would carry no sign and this ledger has no column to recover
a direction from, so it is refused rather than filed under a guessed side: a
mis-filed row would still satisfy the total gate while breaking a count.

L-1: the `Activity Summary` box is per account, so exactly one box is
required. A document printing two boxes statements two accounts, and
publishing the first while dropping the second is what the single-account
schema forbids.

CURRENCY: the schema default, deliberately - this template prints no
institution NAME, only a post-office box and a telephone number, so there is
no issuer identity to take a jurisdiction default from and the ratified
doctrine makes a jurisdiction default affirmative evidence rather than an
absence rule. Named as a future mover if an issuer packet is ever built
(W3 §COREISS2).
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day_year, iso_within_period
from .money import EITHER_MINUS_PADDED, MINUS_CLASS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

#: `$1,234.56`, `-$1,234.56`, `$.56`. Explicit `[0-9]` rather than `\d`: `\d`
#: is Unicode-aware and admits look-alike digits from other scripts, and a
#: money grammar that reads one as a digit publishes a figure nobody printed.
_CASH = MINUS_CLASS + r"?\$(?:[0-9][0-9,]*)?\.[0-9]{2}"
#: The unsigned form the summary box prints.
_FIG = r"(?:[0-9][0-9,]*)?\.[0-9]{2}"

_TOLERANCE = 0.005


def _money(value: str | None) -> float | None:
    return parse_amount(value, EITHER_MINUS_PADDED)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


#: The box, on upper-cased detection text: its own heading, and the cycle
#: length that is this template's word for the period.
_MARK_BOX_RE = re.compile(r"^ACTIVITY SUMMARY\s*$", re.MULTILINE)
_MARK_CYCLE_RE = re.compile(r"DAYS IN CYCLE\s+[0-9]+")
#: The product line's own summary grammar: both counts LEADING their labels,
#: closed by this template's name for the closing balance.
_MARK_CREDITS_RE = re.compile(r"(?<![/A-Z])[0-9]+\s+DEPOSITS/CREDITS\s+\$")
_MARK_DEBITS_RE = re.compile(r"(?<![/A-Z])[0-9]+\s+CHECKS/DEBITS\s+\$")
_MARK_CLOSING_RE = re.compile(r"BALANCE THIS STATEMENT")

DETECTION_MARKERS = (
    required("statement_of_account", lambda t: "STATEMENT OF ACCOUNT" in t),
    required(
        "activity_summary_box",
        lambda t: bool(_MARK_BOX_RE.search(t)) and bool(_MARK_CYCLE_RE.search(t)),
    ),
    required(
        "leading_counts_closing_balance",
        lambda t: bool(_MARK_CREDITS_RE.search(t))
        and bool(_MARK_DEBITS_RE.search(t))
        and bool(_MARK_CLOSING_RE.search(t)),
    ),
)

detect = make_detector(DETECTION_MARKERS, detection_text)

#: `Statement Dates:  4/01/26 thru 4/30/26` - a single-digit month is printed
#: right-aligned, so the run of spaces is real and `\s+` is not decoration.
_PERIOD_RE = re.compile(
    r"Statement Dates:\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2})"
    r"\s+thru\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2})"
)
#: The box's own row. `findall` rather than `search`, because how MANY of these
#: a document prints is the L-1 question.
_BOX_RE = re.compile(
    r"Account Number\s+([0-9]+)\s+Days in Cycle\s+([0-9]+)"
    r"\s+Average Ledger Balance\s+\$(" + _FIG + r")"
    r"\s+Avg Collected Balance\s+\$(" + _FIG + r")"
)
#: The product line: the product phrase, then the six printed figures. The
#: phrase is bounded on the right by the template's own `Beginning Balance`
#: label and on the left by the start of the line, so nothing is enumerated.
_PRODUCT_RE = re.compile(
    r"^(.*?)\s+Beginning Balance\s+\$(" + _FIG + r")"
    r"\s+([0-9]+)\s+Deposits/Credits\s+\$(" + _FIG + r")"
    r"\s+([0-9]+)\s+Checks/Debits\s+\$(" + _FIG + r")"
    r"\s+Service Charge\s+\$(" + _FIG + r")"
    r"\s+Interest Paid\s+\$(" + _FIG + r")"
    r"\s+Balance this Statement\s+\$(" + _FIG + r")\s*$",
    re.MULTILINE,
)
#: The same three figures, printed a SECOND time under the box. A free second
#: reading of the closing balance and both totals, and it is required.
_RESTATED_RE = re.compile(
    r"^Statement Balance\s+(" + _CASH + r")\s*$\s*"
    r"^Debits\s+(" + _CASH + r")\s*$\s*"
    r"^Credits\s+(" + _CASH + r")\s*$",
    re.MULTILINE,
)

_PAGE_RE = re.compile(r"^--- Page [0-9]+")
#: The ledger banner, and the banner it re-prints on every continuation page.
_LEDGER_HEAD_RE = re.compile(r"^Account Activity(?:\s+\(Continued\))?\s*$")
#: The column header, re-declared under every banner.
_LEDGER_COLUMNS_RE = re.compile(r"^Date\s+Description\s+Amount\s+Balance\s*$")
#: What ENDS the ledger. Everything after it - the cheque grid and the trailing
#: image index - RESTATES rows that are already postings.
_LEDGER_END_RE = re.compile(r"^Checks in Number Order\s*$")
#: `4/01 DDA REGULAR DEPOSIT $6,764.00 $47,427.99`. The two money tokens taken
#: are the LAST two on the line — the running balance is always last and the
#: amount always second-to-last — and it is the END-OF-LINE ANCHOR that makes
#: that true, not the greedy `(.*)`. Measured (W3 §COREISS2 mutant N14):
#: replacing `(.*)` with `(.*?)` changes nothing on any input, because a
#: non-greedy description still has to grow until two money tokens reach the
#: end of the line. Recorded so the next reader does not believe the
#: greediness is doing work it is not.
_ROW_RE = re.compile(
    r"^([0-9]{1,2}/[0-9]{1,2})\s+(.*)\s+(" + _CASH + r")\s+(" + _CASH + r")\s*$"
)


def _period(markdown: str):
    """`(start, end, days)`, or None when the two printings disagree.

    `Days in Cycle` and the `Statement Dates` range are two independent reads
    of the same fact, and that fact is the denominator of the canonical
    calendar-day average daily balance. Requiring them to agree is what stops a
    misread date silently re-basing the average while every count and total
    still reconciles.
    """
    printed = _PERIOD_RE.search(markdown)
    box = _BOX_RE.findall(markdown)
    if printed is None or len(box) != 1:
        return None
    try:
        start = date.fromisoformat(iso_from_month_day_year(printed.group(1)))
        end = date.fromisoformat(iso_from_month_day_year(printed.group(2)))
    except ValueError:
        return None
    days = int(box[0][1])
    if end < start or (end - start).days + 1 != days:
        return None
    return start, end, days


def _ledger(markdown: str) -> list[str]:
    """The posting lines, in printed order.

    One transaction is exactly one printed line in this template, so the
    ledger is gathered as LINES rather than as a token stream. A page break
    suspends the region and only the template's own re-printed banner or
    column header resumes it, which keeps the disclosure page and the
    account-reconciliation worksheet - both of which print bare `$` tokens -
    outside the ledger without either being named.
    """
    lines: list[str] = []
    inside = False
    closed = False
    for line in markdown.splitlines():
        line = line.rstrip()
        if closed:
            continue
        if _LEDGER_END_RE.match(line):
            closed = True
            continue
        if _LEDGER_HEAD_RE.match(line) or _LEDGER_COLUMNS_RE.match(line):
            inside = True
            continue
        if _PAGE_RE.match(line):
            inside = False
            continue
        if inside:
            lines.append(line)
    return lines


def _rows(lines, start: date, end: date, opening: float):
    """The postings, walked against their own printed running balances.

    Returns None - refusing the whole document - rather than dropping a row it
    cannot read: every row here sits inside a printed count, a printed total
    and a printed balance chain, so a row this grammar cannot read is a
    document this reader does not understand.

    Lines that are not postings are skipped rather than refused, and that is
    safe precisely because the chain is checked: the template emits a bare
    imaging sequence number once per physical page and sometimes lands it
    BETWEEN two rows, so "every line in the region is a row" is false, while
    "every row's balance continues the chain" is exactly true.
    """
    rows: list[Transaction] = []
    running = opening
    for line in lines:
        match = _ROW_RE.match(line)
        if match is None:
            continue
        amount = _money(match.group(3))
        balance = _money(match.group(4))
        posted = iso_within_period(match.group(1), start, end)
        if amount is None or balance is None or posted is None:
            return None
        # No sign, no direction: this ledger prints one undivided section, so
        # there is no column to recover a zero row's side from.
        if amount == 0:
            return None
        if abs(round(running + amount, 2) - balance) > _TOLERANCE:
            return None
        running = balance
        rows.append(
            Transaction(
                date=posted,
                description=re.sub(r"\s+", " ", match.group(2)).strip(),
                amount=amount,
                direction="credit" if amount > 0 else "debit",
                running_balance=balance,
            )
        )
    return rows


def parse_core_processor_activity_summary_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    product = _PRODUCT_RE.search(markdown)
    restated = _RESTATED_RE.search(markdown)
    box = _BOX_RE.findall(markdown)
    if period is None or product is None or restated is None:
        return None
    start, end, days = period
    account_number, _cycle, average, _collected = box[0]

    opening = _money(product.group(2))
    credit_count, debit_count = int(product.group(3)), int(product.group(5))
    credits, debits = _money(product.group(4)), _money(product.group(6))
    service_charge, interest = _money(product.group(7)), _money(product.group(8))
    closing = _money(product.group(9))
    average_ledger = _money(average)
    figures = (opening, credits, debits, service_charge, interest, closing, average_ledger)
    if any(value is None for value in figures):
        return None

    # The two printings of the closing balance and of both totals must agree
    # before either is used. They are printed by the same processor from the
    # same fields, so disagreement means one of the two was misread.
    for printed, second in (
        (closing, _money(restated.group(1))),
        (debits, _money(restated.group(2))),
        (credits, _money(restated.group(3))),
    ):
        if second is None or abs(abs(second) - abs(printed)) > _TOLERANCE:
            return None

    # The summary closes on itself before a row is read. The fee terms are
    # treated as SEPARATE from the two transaction totals: every document of
    # this family prints both as zero, so the corpus does not corroborate the
    # reading, and it is kept because getting it wrong fails CLOSED - a charge
    # already inside the debit total would be subtracted twice and the identity
    # would miss, refusing the document instead of publishing a wrong balance.
    walked = opening + abs(credits) - abs(debits) - abs(service_charge) + abs(interest)
    if abs(walked - closing) > _TOLERANCE:
        return None

    transactions = _rows(_ledger(markdown), start, end, opening)
    if not transactions:
        return None
    if abs(transactions[-1].running_balance - closing) > _TOLERANCE:
        return None

    credit_rows = [txn for txn in transactions if txn.direction == "credit"]
    debit_rows = [txn for txn in transactions if txn.direction == "debit"]
    if len(credit_rows) != credit_count or len(debit_rows) != debit_count:
        return None
    if abs(sum(txn.amount for txn in credit_rows) - abs(credits)) > _TOLERANCE:
        return None
    if abs(sum(-txn.amount for txn in debit_rows) - abs(debits)) > _TOLERANCE:
        return None

    return Statement(
        bank=None,
        account_name=product.group(1).strip() or None,
        account_number=account_number,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=days,
        beginning_balance=opening,
        ending_balance=closing,
        stated_total_credits=abs(credits),
        stated_total_debits=abs(debits),
        stated_credit_count=credit_count,
        stated_debit_count=debit_count,
        bank_reported_average_balance=average_ledger,
        bank_reported_average_label="Average Ledger Balance",
        stated_service_charge=abs(service_charge),
        stated_interest_paid=abs(interest),
        transactions=transactions,
    )
