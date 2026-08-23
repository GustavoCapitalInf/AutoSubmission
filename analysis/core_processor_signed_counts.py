"""A core processor's SIGNED-COUNTS `Statement of Account`, read as a sibling.

W3 §COREISS2, census rank 5 (`business_classic_statement_of_account`, n=8).
This is the printed issue whose summary strip states each direction's count in
parentheses and its total with an explicit SIGN::

    Statement Date: <m/d/yy>
    Return Service Requested Primary Account <holder> XXXXXX0000
    Statement of Account <PRODUCT> Account Title: <holder>
    Beginning Balance<NBSP><m/dd/yy> $ <fig>
    Summary
    Credits (N) +$<fig>  Interest Paid +$<fig>  Debits (M) -$<fig>
    Ending Balance<NBSP><m/dd/yy> $ <fig>

then `Deposits & Credits`, `Debits & Withdrawals` and `Checks in Number Order`
as posting sections, a SECOND `Summary` carrying the bank's own statistics
(`Average Ledger Bal`, `Days in the Statement Period`, `Average Collected Bal`,
`Service Charge(s)`, `Images Included`), and a `Daily Balance Information`
grid printed as a flat run of `m/dd <fig>` pairs.

SIBLING, NOT AN EXTENSION OF `fiserv_premier` - the ruling and its evidence
---------------------------------------------------------------------------
The census filed this family as "fiserv_premier's parenthesised-counts issue",
and `fiserv_premier` really does near-miss it (0.125 on all eight, measured
live). It is nevertheless a sibling registration, and the reason is that
`fiserv_premier` declares THREE required markers and this issue prints only
one of them. Measured over the 3,396 documents of the OCR artifact store:

======================================  =========  ======  ======
marker                                  archive    this 8  fiserv
======================================  =========  ======  ======
`STATEMENT OF ACCOUNT`                        333       8      14
`PREVIOUS BALANCE`                            311       0      14
`DEPOSITS/CREDITS (N)`                         14       0      14
`CREDITS (N) +$` and `DEBITS (N) -$`            8       8       0
======================================  =========  ======  ======

`PREVIOUS BALANCE` is not an incidental label there: `fiserv_premier`'s own
docstring records it as the ANTI-COLLISION clause that keeps 216 Wells Fargo
documents out of that registration. Extending would mean deleting two of three
required markers, one of them that clause - which is not what §FISERV3 did when
it read a third printed issue (that card kept all three markers and widened
only the period WORDING and the ledger VOCABULARY behind them). Nor is the
resemblance more than the shared heading: not one summary label survives
(`Previous Balance` -> a DATED `Beginning Balance`, unsigned totals -> signed
totals, `Average Ledger` -> `Average Ledger Bal`), the section vocabulary is
disjoint (`Transaction Activity` / `Credit Transactions` / `Debit
Transactions` / `Deposits` / `Other Credits` / `Checks Cleared` there,
`Deposits & Credits` / `Debits & Withdrawals` / `Checks in Number Order`
here), and this issue is the only cohort of the four that prints its debits
with a TRAILING minus.

The two registrations are therefore DISJOINT BY CONSTRUCTION rather than by
precedence - no `supersedes` edge and no band, the relationship
`core_processor_counted` has to `core_processor_daily`. Measured: the two
marker sets intersect on 0 of 3,396 documents.

WHAT THE DOCUMENT HAS TO PROVE BEFORE ANYTHING IS PUBLISHED
------------------------------------------------------------
Five printed facts, all of them, exactly:

1. the summary's own identity, `beginning + credits + interest - debits
   - service charge == ending`;
2. the printed length equals the inclusive calendar span between the two DATED
   balances - the period's only admissible source (see `_period`);
3. the row count in each direction equals the count the summary prints, with
   the `Checks in Number Order` grid counted on the DEBIT side;
4. the row total in each direction equals the total the summary prints, same
   partition;
5. the printed `Daily Balance Information` grid reproduces the ledger day by
   day, ends on the closing balance, and prints every day the ledger posts on.

They are five independent printings of one period, so a dropped row, a
duplicated row or a mis-read amount breaks at least two of them.

THE SIGN IS THE DIRECTION, AND POSITION IS NEVER THE AMOUNT
------------------------------------------------------------
A debit prints its amount with a trailing minus and nothing else in this
template does. That is load-bearing rather than decorative, because a
correction row in this family embeds two money tokens INSIDE its description
before its own amount (measured: one row, one document) - so "the first money
token on the line" and "the last money token on the line" both read the wrong
figure, and only the trailing-minus filter survives. `_DEBIT_ROW_RE`'s
description class can therefore cross a money token ONLY when that token does
not carry the marker, which is what keeps a description out of the next row's
amount. It is a bound, not an impossibility: if a wrapped amount is lost
before the row is read - a page break falling between a descriptor and its
amount - the description CAN reach the following row's trailing-minus token
and merge two postings. Both constructed cases refuse, on the printed count
and on the printed total, so the failure is fail-closed rather than
unreachable.

L-1: this template statements ONE account, and the count gate is what proves
it. A second account section would carry its own summary strip and its own
postings; the strip this reader reads is the first, and the extra postings
then miss both printed counts and the document refuses. The account MASK is
published only when the header furniture prints exactly one (`_account`),
which is a label decision, not the L-1 gate.

CURRENCY: the schema default, deliberately. This template prints no
institution - no masthead, no FDIC line, no PO box, no web address - so there
is no ISSUER jurisdiction to default from, and the ratified doctrine makes a
jurisdiction default affirmative evidence rather than an absence rule. The
addressee's own postal address is evidence about the customer, not about the
account's denomination. The family is named as a future mover if an issuer
packet is ever built for it (W3 §COREISS2).
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day_year, iso_within_period
from .money import EITHER_MINUS_PADDED, MINUS_CLASS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction

#: `1,234.56` and the bare sub-dollar `.56` this template prints for a zero
#: fee. Explicit `[0-9]`, never `\d`: `\d` is Unicode-aware and this archive
#: really does carry look-alike codepoints, and a money grammar that reads one
#: as a digit publishes a figure the bank never printed.
_FIG = r"(?:[0-9][0-9,]*)?\.[0-9]{2}"
#: The same, admitting this template's negative marker - a TRAILING minus.
_SIGNED_FIG = _FIG + MINUS_CLASS + r"?"
#: `m/dd`, and not one character of a longer date or number.
_DAY = r"(?<![0-9/])([0-9]{1,2}/[0-9]{1,2})(?![0-9/])"

_TOLERANCE = 0.005


def _money(value: str | None) -> float | None:
    return parse_amount(value, EITHER_MINUS_PADDED)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


#: The summary strip, on upper-cased detection text. The lookbehind is what
#: makes the label BARE: `DEPOSITS/CREDITS (28)` contains `CREDITS (28)`, and
#: that clause belongs to `fiserv_premier`'s registration, not to this one.
_MARK_CREDITS_RE = re.compile(r"(?<![/A-Z])CREDITS\s*\([0-9]+\)\s*\+\$")
_MARK_DEBITS_RE = re.compile(r"(?<![/A-Z])DEBITS\s*\([0-9]+\)\s*" + MINUS_CLASS + r"\$")
#: The two balances, each printed WITH its own date. Required, because the
#: period has no other admissible source in this template.
_MARK_BEGIN_RE = re.compile(r"BEGINNING BALANCE\s+[0-9]{1,2}/[0-9]{1,2}/[0-9]{2}\b")
_MARK_END_RE = re.compile(r"ENDING BALANCE\s+[0-9]{1,2}/[0-9]{1,2}/[0-9]{2}\b")

DETECTION_MARKERS = (
    required("statement_of_account", lambda t: "STATEMENT OF ACCOUNT" in t),
    required(
        "signed_parenthesised_counts",
        lambda t: bool(_MARK_CREDITS_RE.search(t)) and bool(_MARK_DEBITS_RE.search(t)),
    ),
    required(
        "dated_period_balances",
        lambda t: bool(_MARK_BEGIN_RE.search(t)) and bool(_MARK_END_RE.search(t)),
    ),
)

detect = make_detector(DETECTION_MARKERS, detection_text)

#: `Beginning Balance<NBSP>7/02/26 $ 1,234.17`. The label and its date are
#: separated by U+00A0 on every document of this family, not by a space -
#: `\s` covers both and neither is asserted.
_BEGIN_RE = re.compile(
    r"Beginning Balance\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2})\s+\$\s*(" + _SIGNED_FIG + r")"
)
_END_RE = re.compile(
    r"Ending Balance\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2})\s+\$\s*(" + _SIGNED_FIG + r")"
)
#: `Credits (3) +$1,326.43 Interest Paid +$.00 Debits (4) -$731.66`.
#: The signs are matched as literal furniture and the magnitudes are read by
#: `money.py`: the direction is the label's, never the token's.
_SUMMARY_RE = re.compile(
    r"Credits\s*\(([0-9]+)\)\s*\+\$(" + _FIG + r")"
    r"\s+Interest Paid\s*\+\$(" + _FIG + r")"
    r"\s+Debits\s*\(([0-9]+)\)\s*" + MINUS_CLASS + r"\$(" + _FIG + r")"
)
#: The SECOND `Summary`: the bank's own statistics, printed after the ledger.
#: It carries the printed period LENGTH and the bank's own average, and its
#: heading is what terminates the ledger.
_STATS_RE = re.compile(
    r"Summary\s+Average Ledger Bal\s+\$(" + _SIGNED_FIG + r")"
    r"\s+Interest Paid\s+\$(" + _FIG + r")"
    r"\s+Days in the Statement Period\s+([0-9]+)"
    r"\s+Average Collected Bal\s+\$(" + _SIGNED_FIG + r")"
    r"\s+Service Charge\(s\)\s+\$(" + _FIG + r")"
)

_PAGE_RE = re.compile(r"^--- Page [0-9]+")
#: A bare page footer, printed inside a section rather than after it.
_FOOTER_RE = re.compile(r"^Page [0-9]+\s*$")
#: The three posting sections, by direction. `Checks in Number Order` is a
#: POSTING section here and not a recap: its items are inside the printed
#: `Debits (M)` count and total, and the arithmetic proves it - dropping the
#: section leaves every document of this family short by 9 to 19 items.
_SECTION_HEAD_RES = (
    ("credit", re.compile(r"^Deposits & Credits\s+Date\s+Description\s+Amount\b(.*)$")),
    ("debit", re.compile(r"^Debits & Withdrawals\s+Date\s+Description\s+Amount\b(.*)$")),
    ("check", re.compile(r"^Checks in Number Order\s+Date\s+Check Number\s+Amount\b(.*)$")),
)
#: The bare column header this template RE-DECLARES at the top of every
#: continuation page, carrying no section name. It is the only thing that
#: reopens a section across a page break: a page break SUSPENDS the section,
#: and prose or a check-image page that declares nothing stays outside it.
_CONTINUATION_RE = re.compile(r"^Date\s+(?:Description|Check Number)\s+Amount\b(.*)$")
#: What ENDS the ledger, and cannot be resumed. Everything after it - the
#: statistics, the daily grid, the check-image pages that restate every cheque
#: - is evidence or furniture, never posting detail.
_LEDGER_END_RE = re.compile(r"^Summary\s+Average Ledger Bal\b")
_DAILY_HEAD_RE = re.compile(r"^Daily Balance Information\b(.*)$")

#: `7/03 BETA INBOUND CCD CO#... TRACE # - ... $306.29` - one amount, direction
#: fixed by the section, and a description that cannot cross a `$` at all. The
#: negative lookahead is what refuses a trailing-minus token here: a debit
#: printed under the credit heading is a document this reader does not
#: understand, and the count gate then says so.
_CREDIT_ROW_RE = re.compile(
    _DAY + r" ([^$]+?) \$(" + _FIG + r")(?![0-9,.]|" + MINUS_CLASS + r")"
)
#: `7/02 SAMPLE ANALYSIS CHARGE $103.71-`, and the correction row
#: `7/03 FR... CK DEP AS $412.09 S/B$304.80 $107.29-`. The description may cross
#: a money token ONLY when that token carries no trailing minus, which bounds
#: it out of the next row's amount on every input this archive prints. Where
#: a wrapped amount goes missing the bound can still be crossed and two
#: postings merge - fail-closed, not impossible: the printed count and the
#: printed total both refuse the document.
_DEBIT_ROW_RE = re.compile(
    _DAY + r" ((?:\$" + _FIG + r"(?!" + MINUS_CLASS + r")|[^$])+?) "
    r"\$(" + _FIG + MINUS_CLASS + r")(?![0-9,.])"
)
#: `7/06 4408* $311.53` - date, cheque number, amount; `*` marks a gap in the
#: cheque sequence and is printed, so it is published. A cheque already posted
#: in the ledger prints `-See above-` instead of an amount and is EXCLUDED from
#: the printed debit count; it matches nothing here, which is the same answer.
_CHECK_ROW_RE = re.compile(
    _DAY + r" ([0-9]{1,7}\*?) \$(" + _FIG + r")(?![0-9,.])"
)
#: `7/02 1,647.77` - a date and a balance with NO `$` between them, which is
#: exactly what distinguishes a grid pair from a posting row. Read only inside
#: the grid section, never document-wide.
_DAILY_PAIR_RE = re.compile(_DAY + r" (" + _SIGNED_FIG + r")(?![0-9,.])")

#: The product phrase, bounded on BOTH sides by the template's own labels, so
#: nothing has to be enumerated for it to be read. Horizontal whitespace only:
#: `\s` spans the newline, and a heading on one line with `Account Title:` on
#: the next would then read the whole intervening line as a product name.
_PRODUCT_RE = re.compile(
    r"^Statement of Account[^\S\n]+(\S.*?)[^\S\n]+Account Title:", re.MULTILINE
)
_TITLE_RE = re.compile(r"Account Title:\s*(.+?)\s*$", re.MULTILINE)
#: The account mask, taken only from the two lines that LABEL it. A masked
#: number printed inside a posting's description belongs to another
#: instrument, so an unlabelled mask is not evidence about this statement.
_ACCOUNT_RES = (
    re.compile(r"^Account Number:\s*(X+[0-9]+)\s*$", re.MULTILINE),
    re.compile(
        r"^Return Service Requested Primary Account\b.*?(X+[0-9]+)\s*$", re.MULTILINE
    ),
)


def _period(markdown: str):
    """`(start, end, days, opening, closing)`, or None.

    The period comes from the two DATED balances and from nothing else. The
    template also prints a `Statement Date:` at the top of page one, and that
    date is NOT the period end: measured over this family, the two disagree on
    four of eight documents and the periods do not align to calendar months, so
    a reader that trusts it re-bounds every row and re-bases the average daily
    balance while every count and total still reconciles.

    The printed length (`Days in the Statement Period`) is required to equal
    the inclusive calendar span the two dates describe. That is two independent
    reads of one fact, so disagreement means one of them was misread.
    """
    begin, end = _BEGIN_RE.search(markdown), _END_RE.search(markdown)
    stats = _STATS_RE.search(markdown)
    if begin is None or end is None or stats is None:
        return None
    try:
        start_iso = iso_from_month_day_year(begin.group(1))
        end_iso = iso_from_month_day_year(end.group(1))
    except ValueError:
        return None
    start, last_day = date.fromisoformat(start_iso), date.fromisoformat(end_iso)
    opening, closing = _money(begin.group(2)), _money(end.group(2))
    if opening is None or closing is None:
        return None
    days = int(stats.group(3))
    if last_day < start or (last_day - start).days + 1 != days:
        return None
    return start, last_day, days, opening, closing


def _sections(markdown: str) -> dict[str, str]:
    """The three posting sections and the printed daily grid, by name."""
    gathered: dict[str, list[str]] = {"credit": [], "debit": [], "check": [], "daily": []}
    current: str | None = None
    suspended: str | None = None
    ledger_closed = False
    for line in markdown.splitlines():
        line = line.rstrip()
        if _PAGE_RE.match(line) or _FOOTER_RE.match(line):
            if current is not None and current != "daily":
                suspended = current
            current = None
            continue
        if _LEDGER_END_RE.match(line):
            current, suspended, ledger_closed = None, None, True
            continue
        if ledger_closed:
            head = _DAILY_HEAD_RE.match(line)
            if head:
                current = "daily"
                if head.group(1).strip():
                    gathered["daily"].append(head.group(1).strip())
            elif current == "daily":
                # The grid runs on until the first line that is not all pairs.
                remainder = _DAILY_PAIR_RE.sub("", line).strip()
                if line.strip() and not remainder:
                    gathered["daily"].append(line.strip())
                else:
                    current = None
            continue
        for name, pattern in _SECTION_HEAD_RES:
            head = pattern.match(line)
            if head:
                current, suspended = name, None
                if head.group(1).strip():
                    gathered[name].append(head.group(1).strip())
                break
        else:
            resumed = _CONTINUATION_RE.match(line)
            if resumed:
                if current is None:
                    current, suspended = suspended, None
                if current is not None and resumed.group(1).strip():
                    gathered[current].append(resumed.group(1).strip())
            elif current is not None:
                gathered[current].append(line)
    return {name: " ".join(lines) for name, lines in gathered.items()}


def _rows(text: str, pattern: re.Pattern[str], start: date, end: date, sign: int):
    """The postings of one section, or None - refusing the whole document.

    A row this grammar cannot read is never dropped quietly: every row of this
    ledger sits inside a printed count, a printed total and a printed daily
    balance, so the honest answer to an unreadable one is the refusal the
    caller's gates would reach anyway, reached here without a wrong figure.

    Whitespace is normalized FIRST, which is what makes the row patterns exact:
    this template pushes a long descriptor's amount onto the FOLLOWING physical
    line and concatenates two short postings onto ONE, so a line-based read
    fails in both directions and the section has to be one token stream.
    """
    text = " ".join(text.split())
    rows: list[Transaction] = []
    for match in pattern.finditer(text):
        amount = _money(match.group(3))
        posted = iso_within_period(match.group(1), start, end)
        if amount is None or posted is None:
            return None
        rows.append(
            Transaction(
                date=posted,
                description=re.sub(r"\s+", " ", match.group(2) or "").strip(),
                amount=sign * abs(amount),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return rows


def _daily_grid(text: str, start: date, end: date):
    """The printed grid as `(iso, balance)` pairs, in the order printed."""
    printed: list[tuple[str, float]] = []
    for token, value in _DAILY_PAIR_RE.findall(" ".join(text.split())):
        posted = iso_within_period(token, start, end)
        balance = _money(value)
        if posted is None or balance is None:
            return None
        printed.append((posted, balance))
    return printed or None


def _grid_agrees(printed, transactions, opening: float, closing: float) -> bool:
    """Does the grid reproduce the ledger, day by day?

    The third oracle, and the only one that binds a row to a DAY: the counts
    and the totals gate the ledger as a whole, and a ledger whose rows sit on
    the wrong days satisfies both while producing a wrong average daily
    balance. Walked from the opening balance, each printed day must equal the
    opening plus every row filed on or before it, the last must be the closing
    balance, and no row may fall on a day the grid does not print.
    """
    if [day for day, _ in printed] != sorted(day for day, _ in printed):
        return False
    moved: dict[str, float] = {}
    for txn in transactions:
        moved[txn.date] = round(moved.get(txn.date, 0.0) + txn.amount, 2)
    running = opening
    for day, balance in printed:
        running = round(running + moved.pop(day, 0.0), 2)
        if abs(running - balance) > _TOLERANCE:
            return False
    return not moved and abs(running - closing) <= _TOLERANCE


def _account(markdown: str) -> tuple[str | None, str | None]:
    """`(account_name, account_number)` - the product, and the printed mask.

    The product phrase is bounded on both sides by the template's own labels
    (`Statement of Account <phrase> Account Title:`), so nothing has to be
    enumerated for it to be read, and the holder printed after `Account
    Title:` is the name of last resort.

    The mask is published only when the header furniture prints exactly one:
    two different masks under an account label is a document naming two
    accounts, and labelling it with one of them would be a statement about
    neither.
    """
    named = _PRODUCT_RE.search(markdown)
    titled = _TITLE_RE.search(markdown)
    product = named.group(1).strip() if named else ""
    holder = titled.group(1).strip() if titled else ""
    masks = {mask for pattern in _ACCOUNT_RES for mask in pattern.findall(markdown)}
    return (product or holder or None), (masks.pop() if len(masks) == 1 else None)


def parse_core_processor_signed_counts_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    summary = _SUMMARY_RE.search(markdown)
    stats = _STATS_RE.search(markdown)
    if period is None or summary is None or stats is None:
        return None
    start, end, days, opening, closing = period

    credit_count, debit_count = int(summary.group(1)), int(summary.group(4))
    credits, interest = _money(summary.group(2)), _money(summary.group(3))
    debits = _money(summary.group(5))
    average, service_charge = _money(stats.group(1)), _money(stats.group(5))
    if None in (credits, interest, debits, average, service_charge):
        return None

    # The summary closes on itself before a row is read. The fee terms are
    # treated as SEPARATE from the two transaction totals - every document of
    # this family prints both as zero, so the corpus does not corroborate that
    # reading and it is kept because getting it wrong fails CLOSED: a charge
    # already inside the debit total would be subtracted twice, the identity
    # would miss, and the document would refuse rather than publish a wrong
    # opening or closing balance.
    walked = opening + abs(credits) + abs(interest) - abs(debits) - abs(service_charge)
    if abs(walked - closing) > _TOLERANCE:
        return None

    sections = _sections(markdown)
    credit_rows = _rows(sections["credit"], _CREDIT_ROW_RE, start, end, 1)
    debit_rows = _rows(sections["debit"], _DEBIT_ROW_RE, start, end, -1)
    check_rows = _rows(sections["check"], _CHECK_ROW_RE, start, end, -1)
    if credit_rows is None or debit_rows is None or check_rows is None:
        return None
    debit_rows = debit_rows + check_rows
    if not credit_rows and not debit_rows:
        return None

    # The summary's own counts and totals are the gate on the rows, partitioned
    # by the SECTION each row was printed under.
    if len(credit_rows) != credit_count or len(debit_rows) != debit_count:
        return None
    if abs(sum(t.amount for t in credit_rows) - abs(credits)) > _TOLERANCE:
        return None
    if abs(sum(-t.amount for t in debit_rows) - abs(debits)) > _TOLERANCE:
        return None

    printed = _daily_grid(sections["daily"], start, end)
    transactions = sorted(credit_rows + debit_rows, key=lambda txn: txn.date)
    if printed is None or not _grid_agrees(printed, transactions, opening, closing):
        return None

    account_name, account_number = _account(markdown)
    return Statement(
        bank=None,
        account_name=account_name,
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
        bank_reported_average_balance=average,
        bank_reported_average_label="Average Ledger Bal",
        stated_service_charge=abs(service_charge),
        stated_interest_paid=abs(interest),
        stated_daily_balances=[
            StatementDailyBalance(date=day, balance=balance) for day, balance in printed
        ],
        transactions=transactions,
    )
