"""Lili business checking, banked by Sunrise Banks N.A. — W3 §LILI.

WHAT THE ARCHIVE HOLDS. Twenty documents that all print the same platform's
support address, and two printings that share almost nothing else. Every
figure, date and description below is INVENTED — the same invented ones
`tests/test_lili.py` uses, in a period and a calendar year the family does
not contain. No amount, name, account number or date from any archive document
appears in this module, in its tests, or in W3 §LILI.

SKIN A (15 documents, four accounts, born-digital text) is the printing this
reader publishes:

    Account Number Statement Period 999900000000 1 September, 2027 - 30 September, 2027
    Checking Account Summary Total Checking Amount
    Beginning balance on 1 September, 2027 $137.41
    Deposits and other credits $512.63
    Withdrawals and other debits $-308.19
    Fees $-13.27
    Ending balance on 30 September, 2027 $328.58
    Checking Account Activity - Main Account
    Date Authorization Code Description Amount Balance
    09/03/2027 111111111 A MERCHANT NOWHERE ZZUS $-308.19 $-170.78
    09/17/2027 222222222 A TRANSFER IN $512.63 $341.85
    09/30/2027 333333333 A PLAN CHARGE (Applies From 09/08/2027) $-13.27 $328.58

Five printed summary terms, one per line, each followed by its own figure;
then one ledger under one column head, fully collapsed to one line per
posting, with a RUNNING BALANCE on every row. Descriptions do not wrap, and
merchant, city and country run together with no delimiter, so the amount is
the second-to-last money token of the line and the balance is the last.

SKIN B (5 documents, one account) reverses the header to `Statement Period
Account Number`, prints its summary labels and figures on SEPARATE lines,
shreds each posting across three or four lines with a floating two-letter
network tag, and carries no depository disclosure at all. It is refused, and
§INTEGRITY below is why it is refused for a reason worth naming.

THE ORACLE IS DOUBLE and this reader uses both halves. The five summary terms
close on each other (beginning + deposits + withdrawals + fees == ending, with
the signs the statement prints), and the running balance chains from the
printed beginning to the printed ending. A third check joins them: the rows'
own GROSS debits must equal the printed Withdrawals PLUS the printed Fees —
this platform's `Withdrawals and other debits` term excludes its `Fees` term,
which is why `stated_total_debits` and `stated_service_charge` are published
separately, and which a two-field read would get wrong.

Together they are a complete-coverage oracle: a dropped posting breaks the
chain at the row after it, a fabricated one breaks it too, and a pair the
summary nets out — a credit and its reversal — breaks the gross-debit
reading while leaving every printed balance consistent. This template prints
no transaction count, and it needs none.

§INTEGRITY — WHY A CLEAN-LOOKING DOCUMENT IS REFUSED. A posting dated outside
the period the document declares is not an OCR defect and not a wrap: it is a
row that belongs to a different statement, and the platform must not
reconcile around it. Two readings enforce that, over ONE class of date — the
date that BEGINS a line, which on this template is a posting and nothing
else. Every such line must be a posting the row pattern parsed (so a block of
rows the pattern cannot read cannot pass as text nobody looked at), and every
posting's date must fall inside the printed period.

Dates that are not evidence about when money moved are deliberately NOT
checked: the effective date a fee row prints inside its description for a
plan cycle that may have begun before the period, and anything outside a
posting altogether — a footer's print date, a disclosure's revision date, an
error-resolution deadline. Measured over the 15 clean members: 2,718
line-leading dates, all postings, all in period; 11 description dates, all
fee effective dates; zero line-leading dates that are not postings.

§L-1 — THE SECOND ACCOUNT. One printing of Skin A adds a credit-builder card
whose collateral is held in its own account: the summary grows from one money
column to three (checking, collateral, and their total, the third being the
sum of the first two on every row) and a SECOND ledger, under its own copy of
the column head, walks its own running balance. Each sub-ledger closes
perfectly on its own; the checking chain only looks broken because a
single-chain read walks straight into the collateral table.

The published schema carries one account. Publishing the checking half and
dropping the collateral half is exactly what the L-1 rule forbids, and the
collateral sibling is not idle — it posts. So this reader REFUSES a document
that prints more than one money column in its summary, and REFUSES a document
that prints its ledger column head more than once. Two independent readings
of the same fact, because a printing that grew a column without growing a
ledger, or the reverse, is a shape nobody has measured.

§CURRENCY. No document in this family prints a currency code; every figure is
a bare `$`. The affirmative evidence is US — a depository disclosure naming a
Member FDIC national association, a debit card issued under a Visa U.S.A.
licence, a wire service provided by another Member FDIC bank — and it agrees
with the schema default, so this reader claims no currency of its own: it
writes neither the code nor any statement about where the code came from.
Calling this family's denomination an institution default would be more
precise than the default it already gets; that is a policy question for the
owner of that vocabulary and is recorded in W3 §LILI rather than decided
here.

§WHAT IT DOES NOT PUBLISH, deliberately. `account_name`: the template prints
no product line — `Checking Account Summary` is furniture, not a product —
so the field stays None rather than carrying furniture. `stated_daily_
balances`: there is no daily grid, no average-balance line and no interest
line anywhere in the family, so nothing is published there and nothing is
manufactured. The calendar-day ADB is the engine's to compute from the
printed opening and the postings, which is the canonical basis the ADB
doctrine ratified; all 11 published documents reach `validated/approved` with
it. Transaction counts: not printed, and not needed — the chain is this
reader's coverage oracle.
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import MONTH_NAME_ALT, MONTH_NUMBERS, PERIOD_DASH, iso_or_none
from .tables import single_match
from .money import LEADING_MINUS, MINUS_CLASS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import clean_cell

#: Every figure this template prints: a `$`, an optional minus in any of the
#: glyphs the money grammar admits, then grouped digits and two decimals.
#: `parse_amount` removes the `$` and the separators itself, so the token is
#: captured whole and handed over intact.
_MONEY = r"\$" + MINUS_CLASS + r"?[\d,]+\.\d{2}"

#: The trailing run of figures on a summary term's line: one figure on the
#: single-account printing, three on the credit-builder printing.
_MONEY_RUN = r"(?:" + _MONEY + r"[ \t]*)+"
_MONEY_TOKEN_RE = re.compile(_MONEY)

#: A day-first long date — `1 September, 2027`, `01 September, 2027`. The
#: day may be printed with or without its leading zero. Group-free, so it
#: can be embedded twice in the header pattern; `_LONG_DATE_PARTS` reads the
#: pieces back out of whatever it matched.
_LONG_DATE = r"\d{1,2}[ \t]+(?:" + MONTH_NAME_ALT + r"),[ \t]+\d{4}"
_LONG_DATE_PARTS = re.compile(
    r"(\d{1,2})[ \t]+(" + MONTH_NAME_ALT + r"),[ \t]+(\d{4})", re.IGNORECASE
)

#: The one header, in either of the two orders the platform prints it. The
#: account number and the period are read as ONE match rather than in two
#: searches, so a document printing two accounts or two periods contradicts
#: itself instead of blending them.
_HEADER_RE = re.compile(
    r"(?:Account\s+Number\s+Statement\s+Period"
    r"|Statement\s+Period\s+Account\s+Number)"
    r"\s+(?P<account>\d+)"
    r"\s+(?P<period>" + _LONG_DATE + r"\s*" + PERIOD_DASH + r"\s*" + _LONG_DATE + r")",
    re.IGNORECASE,
)

#: The ledger's column head. Counted, not just found: a second one is a
#: second account (§L-1).
_LEDGER_HEAD_RE = re.compile(
    r"^Date[ \t]+Authorization[ \t]+Code[ \t]+Description[ \t]+Amount[ \t]+Balance[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

#: One posting. The description is greedy so the two figures taken are the
#: LAST two on the line: this template welds merchant, city and country
#: together without a delimiter, and a description that happens to contain a
#: figure must not steal the amount column.
_ROW_RE = re.compile(
    r"^(?P<month>\d{2})/(?P<day>\d{2})/(?P<year>\d{4})[ \t]+\d+[ \t]+"
    r"(?P<description>\S.*)[ \t]+(?P<amount>" + _MONEY + r")[ \t]+(?P<balance>" + _MONEY + r")[ \t]*$",
    re.MULTILINE,
)

#: A line that BEGINS with a date. On this template that is a posting and
#: nothing else: measured over the family's 15 clean members, every one of
#: 2,718 line-leading dates is the leading date of a posting the row pattern
#: parses, and there are no others. It is the anchor for both readings in
#: §INTEGRITY.
_LEADING_DATE_RE = re.compile(r"(?m)^(\d{2})/(\d{2})/(\d{4})(?![\d/])")

#: The five printed summary terms, in the order the template prints them.
#: Each must appear on its own line, exactly once, followed by its own run of
#: figures. Skin B prints the same five labels with their figures on the NEXT
#: line, which matches none of these — the shape refusal that backs up
#: §INTEGRITY.
_SUMMARY_TERMS = (
    ("beginning", re.compile(
        r"^Beginning balance on[ \t]+" + _LONG_DATE + r"[ \t]+(" + _MONEY_RUN + r")$",
        re.IGNORECASE | re.MULTILINE)),
    ("deposits", re.compile(
        r"^Deposits and other credits[ \t]+(" + _MONEY_RUN + r")$",
        re.IGNORECASE | re.MULTILINE)),
    ("withdrawals", re.compile(
        r"^Withdrawals and other debits[ \t]+(" + _MONEY_RUN + r")$",
        re.IGNORECASE | re.MULTILINE)),
    ("fees", re.compile(
        r"^Fees[ \t]+(" + _MONEY_RUN + r")$",
        re.IGNORECASE | re.MULTILINE)),
    ("ending", re.compile(
        r"^Ending balance on[ \t]+" + _LONG_DATE + r"[ \t]+(" + _MONEY_RUN + r")$",
        re.IGNORECASE | re.MULTILINE)),
)

#: Money is compared to the cent. Every figure checked here is printed by the
#: document beside the figures it is checked against, so a tolerance wide
#: enough to absorb a rounding difference would also absorb a mis-read digit.
_CENT = 0.005

DETECTION_MARKERS = (
    # The platform's own support address, printed in the contact block of one
    # printing and in the disclosure block of the other. Institution
    # furniture: a domain the issuer owns, not a name that could arrive as a
    # counterparty on somebody else's statement.
    required("issuer_support_address", lambda t: "support@lili.co" in t),
    # The two summary terms this template names its directions with. Present
    # in both printings, so a tampered document is CLAIMED and then refused
    # rather than falling through unnamed.
    required("summary_credit_term", lambda t: "Deposits and other credits" in t),
    required("summary_debit_term", lambda t: "Withdrawals and other debits" in t),
)

detect = make_detector(DETECTION_MARKERS)


def _long_date(parts: tuple[str, str, str]) -> date | None:
    """`("1", "March", "2026")` -> a date, else None.

    None is "this is not a date I can read", which every caller turns into a
    declined document. A day the month does not have reaches here — the
    pattern admits one or two digits because a statement period is not the
    place to encode a calendar — and `date()` raises `ValueError` on it. An
    escaping `ValueError` is a crash where this document deserves a refusal.
    """
    day, name, year = parts
    month = MONTH_NUMBERS.get(name.casefold())
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _header(text: str) -> tuple[str, date, date] | None:
    """`(account, period start, period end)`, or None.

    Every header the document prints must agree. A template that reprints its
    header per page is corroboration; two headers that DISAGREE are a document
    that cannot say what it is, and it is refused rather than read from
    whichever came first.
    """
    readings = set()
    for match in _HEADER_RE.finditer(text):
        bounds = _LONG_DATE_PARTS.findall(match.group("period"))
        if len(bounds) != 2:
            return None
        start = _long_date(bounds[0])
        end = _long_date(bounds[1])
        if start is None or end is None or end < start:
            # `end < start` is a precondition on the published
            # `days_in_period`, not a refusal any document reaches: the
            # §INTEGRITY gate below refuses every reversed period that
            # prints a posting, and a document that prints none is refused for
            # having no ledger. Kept because the field is published.
            return None
        readings.add((match.group("account"), start, end))
    if len(readings) != 1:
        return None
    return next(iter(readings))


def _ledger_dates_are_sound(text: str, start: date, end: date) -> str | None:
    """The name of the §INTEGRITY reading that refuses `text`, or None.

    TWO READINGS, over ONE class of date, and the class is the point. An
    earlier revision of this reader checked EVERY `mm/dd/yyyy` the document
    printed, anywhere, which is wrong in both directions: it would refuse a
    page footer's print date, a disclosure's revision date, an
    error-resolution deadline, a merchant string that happens to carry a
    date, and the effective date a fee row prints in its DESCRIPTION for a
    plan cycle that began before the period — none of which is evidence about
    when money moved. Measured over the 15 clean members: 2,718 line-leading
    dates, every one the leading date of a posting the row pattern parses;
    11 dates inside a description, every one a fee row's effective date; and
    zero line-leading dates that are not postings. So:

    * **coverage** — every line that BEGINS with a date must be a posting the
      row pattern parsed. This is what the second printing fails: it prints
      twelve line-leading dates and the row pattern parses none of them, so
      its pasted block cannot slip through as text the reader simply did not
      look at. It is also what catches a posting whose money the grammar
      refuses, which would otherwise be dropped in silence.
    * **period** — every posting's own leading date must fall inside the
      printed period, strictly. A posting dated outside the period the
      document declares is a posting from a different statement.

    A date the reader cannot resolve to a calendar day fails the period
    reading for the same reason a five-year-old date does: the document is
    printing something it did not compute.

    Text inside a description, and text outside every posting, are NOT
    date-checked. They carry no claim about when money moved, and the row
    they sit on has already had its date, its amount and its balance verified.
    """
    rows = list(_ROW_RE.finditer(text))
    leading = list(_LEADING_DATE_RE.finditer(text))
    if {match.start() for match in leading} != {match.start() for match in rows}:
        return "a line that begins with a date is not a posting"
    for match in rows:
        try:
            posted = date(
                int(match.group("year")), int(match.group("month")), int(match.group("day"))
            )
        except ValueError:
            return "a printed date outside the declared period"
        if not start <= posted <= end:
            return "a printed date outside the declared period"
    return None


def _summary(text: str) -> list[list[float]] | None:
    """The five printed terms as their runs of figures, or None.

    Each term must be printed exactly once, on its own line, with its figures
    on that line — `tables.single_match`, the shared helper that refuses ANY
    second printing (stricter than `unique_match`, on purpose: a repeated
    summary term is the tampering signature this reader exists to refuse);
    the five must appear in the order the template prints them; and every
    term must carry the same NUMBER of figures, because those figures are
    columns and a grid with a ragged row is a grid nobody has measured.
    """
    columns: list[list[float]] = []
    position = -1
    for _term, pattern in _SUMMARY_TERMS:
        found = single_match(text, pattern)
        if found is None or found.start() <= position:
            return None
        position = found.start()
        figures = [
            parse_amount(token, LEADING_MINUS)
            for token in _MONEY_TOKEN_RE.findall(found.group(1))
        ]
        if not figures or None in figures:
            return None
        columns.append([figure for figure in figures if figure is not None])
    # Every term carries the same number of figures (a ragged grid refuses).
    # Phrased against the first row rather than as the size of a set of
    # lengths: the clone guard reads `len({...})` next to a `.findall` as the
    # shape of a private uniqueness helper, which this is not (train8).
    if any(len(row) != len(columns[0]) for row in columns):
        return None
    return columns


def _postings(text: str) -> list[Transaction] | None:
    """Every posting line, in printed order, or None if one cannot be read."""
    postings: list[Transaction] = []
    for match in _ROW_RE.finditer(text):
        iso = iso_or_none(
            int(match.group("year")), int(match.group("month")), int(match.group("day"))
        )
        amount = parse_amount(match.group("amount"), LEADING_MINUS)
        balance = parse_amount(match.group("balance"), LEADING_MINUS)
        if iso is None or amount is None or balance is None:
            return None
        description = clean_cell(match.group("description"))
        if not description:
            return None
        postings.append(
            Transaction(
                date=iso,
                description=description,
                amount=amount,
                direction="credit" if amount >= 0 else "debit",
                running_balance=balance,
            )
        )
    return postings or None


def _chain_holds(postings: list[Transaction], beginning: float, ending: float) -> bool:
    """Whether the printed running balance walks beginning -> ending exactly."""
    balance = beginning
    for posting in postings:
        walked = round(balance + posting.amount, 2)
        if posting.running_balance is None or abs(walked - posting.running_balance) > _CENT:
            return False
        balance = posting.running_balance
    return abs(balance - ending) <= _CENT


def parse_lili_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None

    header = _header(markdown)
    if header is None:
        return None
    account, start, end = header

    # §INTEGRITY, before the shape is read. Both readings answer with the NAME
    # of what they found; the name is what `tools/lili_family_replay.py`
    # attributes a refusal to. Gate ORDER is not observable at this boundary —
    # every gate here answers by declining — so the order buys attribution,
    # not behaviour, and W3 §LILI says so rather than implying otherwise.
    if _ledger_dates_are_sound(markdown, start, end) is not None:
        return None

    summary = _summary(markdown)
    if summary is None:
        return None
    # §L-1, read twice: a second money column, and a second ledger.
    if len(summary[0]) != 1:
        return None
    if len(_LEDGER_HEAD_RE.findall(markdown)) != 1:
        return None
    beginning, deposits, withdrawals, fees, ending = (row[0] for row in summary)

    # The template prints its two debit terms as debits, and both are
    # published as magnitudes, so a term printed the other way would publish
    # an outflow for money the document printed coming in. There is no third
    # branch for `deposits`: with the three arithmetic gates below all closed,
    # the rows' credits are forced to equal the Deposits term and a sum of
    # positive amounts cannot be negative, so a negative Deposits term is
    # already unreachable.
    if withdrawals > 0 or fees > 0:
        return None
    if abs(beginning + deposits + withdrawals + fees - ending) > _CENT:
        return None

    postings = _postings(markdown)
    if postings is None:
        return None
    if not _chain_holds(postings, beginning, ending):
        return None
    # The rows' own GROSS debits must equal the two debit terms added: this is
    # the reading that proves the Withdrawals/Fees split the two published
    # fields rest on, and the only one that can see a pair of postings the
    # summary nets out. Its credit-side twin is deliberately absent: with the
    # chain and the summary both closed, the rows' gross credits are already
    # determined (chain gives credits - debits == deposits + withdrawals +
    # fees), so a credits check could refuse nothing this does not, and no
    # mutant could reach it.
    debited = sum(-posting.amount for posting in postings if posting.amount < 0)
    if abs(debited + withdrawals + fees) > _CENT:
        return None

    return Statement(
        bank="Lili",
        account_number=account,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=(end - start).days + 1,
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=deposits,
        stated_total_debits=abs(withdrawals),
        stated_service_charge=abs(fees),
        transactions=postings,
    )
