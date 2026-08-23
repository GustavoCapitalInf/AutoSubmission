"""Bank OZK checking, where the DIRECTION of a row is not printed — W3 §FROSTOZK.

WHAT THE ARCHIVE HOLDS. Eight documents, two accounts, four consecutive months
each, every month's printed `CURRENT STATEMENT BALANCE` the next month's
printed `PREVIOUS STATEMENT BALANCE`.

THE CARD IS THE DIRECTION OF A ROW. `OTHER TRANSACTIONS` prints two adjacent
money columns headed `DEBITS` and `CREDITS`, and the PDF's text layer
collapses both to the same position — the whole table arrives as ONE physical
line with no column and no row breaks. Direction is therefore absent from the
text, and it is worse than absent: identically-worded rows land on BOTH sides
of the ledger within a single statement, so a description vocabulary would not
degrade here, it would systematically INVERT real postings. Nothing local can
recover it.

WHAT RECOVERS IT IS ARITHMETIC THE BANK PRINTED TWICE. Every document prints a
`BALANCE BY DATE` grid — an end-of-day balance for each day the account
moved — and a four-line sentence summary carrying both counts and both totals.
The reader:

1. reads the summary and refuses unless `previous + credits - debits ==
   current`, and unless the printed `NUMBER OF DAYS IN THIS STATEMENT PERIOD`
   equals the span from the day after the previous statement's as-of date
   through this one's. That second equality is what makes the period PRINTED
   rather than inferred — the document states the two endpoints and then
   states the length, and this reader publishes the period only when the two
   statements agree;
2. splits the flattened table into rows on `MM/DD` tokens the printed period
   can place uniquely, and refuses any date-shaped token it cannot;
3. solves each day as a subset-sum against that day's printed balance step:
   the signed row amounts of the day must reproduce
   `balance(day) - balance(previous day)` exactly. Cheques are known debits
   and seed the day;
4. where a day admits more than one sign assignment — and one archive
   document has such a day — the printed CREDIT COUNT is a cross-day
   constraint that selects between them. The reader enumerates the global
   solutions under that constraint and publishes only when there is EXACTLY
   ONE. Two solutions is a refusal, not a coin toss.

WHAT THE PRINTED TOTALS DO AND DO NOT CHECK, because an earlier draft of this
docstring overstated it and the review was right to say so. Each day's credit
sum is `(residual + S) / 2` — a figure fixed by the printed balances and
IDENTICAL for every sign assignment of that day — so the totals cannot
discriminate between two assignments and are not a check on DIRECTION at all.
What they check, against a figure that came from the summary block rather than
from the grid, is the ROW SPLIT and the GRID READING: a row lost, a row
invented, or a grid cell misread by an arbitrary amount moves them.

The residue that leaves is named rather than papered over: a grid cell misread
by EXACTLY twice some row's amount moves that row across the ledger and leaves
every oracle intact — the day still solves, both totals still reproduce, the
counts still agree. Nothing here can see it. It needs a misreading of one
printed figure into another printed figure's double, which is not a shape the
text layer produces, and it is recorded in W3 §FZ11 as a carried risk.

THE PRINTED SHAPE. Every figure, name, account number and date below and in
`tests/test_bank_ozk.py` is INVENTED, and the fixture's period deliberately
sits in a year the archive does not contain. A CHECKED claim, not a promise —
W3 §FZ10.3 records the scan, the inert first version of it, and the literals
its repair found, two of which were in this module's own comments::

    SAMPLE CHECKING* ACCOUNT - 000000
    PREVIOUS STATEMENT BALANCE AS OF 07/30/27: 100.00 PLUS 1 DEPOSITS AND
    OTHER CREDITS: 50.00 LESS 1 CHECKS AND OTHER DEBITS: 20.00 CURRENT
    STATEMENT BALANCE AS OF 08/31/27: 130.00 NUMBER OF DAYS IN THIS
    STATEMENT PERIOD: 32
    OTHER TRANSACTIONS DATE DESCRIPTION DEBITS CREDITS 08/03 SAMPLE IN 50.00
    08/04 SAMPLE OUT 20.00
    BALANCE BY DATE
    DATE AMOUNT            DATE AMOUNT 08/03 150.00 08/04 130.00

WHAT THIS READER REFUSES: a summary whose arithmetic does not close; a printed
day count that contradicts the two as-of dates; a `MM/DD` token the period
cannot place uniquely; a row with no readable amount; a row dated on a day the
`BALANCE BY DATE` grid does not carry; a grid day with no rows, a repeated
grid date, or a grid whose last cell is not the printed current balance; a day
whose balance step no sign assignment reproduces; and — the one that matters —
a document whose global solve is not unique.

WHAT IT DOES NOT DO. It does not read a description for meaning, and it holds
no fee, merchant or lender vocabulary: the only words this module knows are
the bank's own printed section and summary headings and its customer-service
address block.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import iso_unique_in_period
from .money import STRICT_LEADING_SIGN, STRICT_UNSIGNED, parse_amount
from .parser_registry import corroborating, make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import unique_match

# ---------------------------------------------------------------------------
# Printed money
# ---------------------------------------------------------------------------

#: An ordinary printed amount. Bounded on the left so a reference number
#: cannot be read as one.
_CENTS = r"\d[\d,]{0,15}\.\d{2}"
_AMOUNT_RE = re.compile(_CENTS)
#: A grid balance, which prints its minus in front when the day is overdrawn.
_SIGNED_RE = re.compile(r"-?" + _CENTS)
#: An amount the document prints INSIDE a description, marked by the currency
#: symbol the ledger's own money column never carries. Masked out before a
#: row's amount is read, because a description that quotes a figure would
#: otherwise supply one.
_QUOTED_RE = re.compile(r"\$-?" + _CENTS)


def _cents(token: str, *, signed: bool = False) -> int | None:
    value = parse_amount(token, STRICT_LEADING_SIGN if signed else STRICT_UNSIGNED)
    return None if value is None else int(round(value * 100))


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

#: The institution's own customer-service block, printed on every document of
#: the family. Institution furniture — a post box and a toll-free number — and
#: the only issuer evidence two of the eight documents carry at all.
_SERVICE_CENTRE_RE = re.compile(
    r"P\.?O\.? BOX 196\s+OZARK,\s*AR\s*72949", re.IGNORECASE
)
_SERVICE_PHONE_RE = re.compile(r"800-274-4482")

#: The four-line sentence summary, which is also the document's arithmetic
#: oracle. Captured whole so that detection and parsing read one grammar.
_SUMMARY_RE = re.compile(
    r"PREVIOUS STATEMENT BALANCE AS OF\s+(\d{2}/\d{2}/\d{2}):\s*(" + _CENTS + r")"
    r"\s+PLUS\s+(\d{1,5})\s+DEPOSITS AND OTHER CREDITS:\s*(" + _CENTS + r")"
    r"\s+LESS\s+(\d{1,5})\s+CHECKS AND OTHER DEBITS:\s*(" + _CENTS + r")"
    r"\s+CURRENT STATEMENT BALANCE AS OF\s+(\d{2}/\d{2}/\d{2}):\s*(" + _CENTS + r")"
    r"\s+NUMBER OF DAYS IN THIS STATEMENT PERIOD:\s*(\d{1,4})"
)

#: The two grids, by their own headings.
_DAILY_HEAD_RE = re.compile(r"^BALANCE BY DATE\s*$", re.MULTILINE)
_OTHER_HEAD_RE = re.compile(r"OTHER TRANSACTIONS\s+DATE\s+DESCRIPTION\s+DEBITS\s+CREDITS")
_CHECK_HEAD_RE = re.compile(r"CHECK TRANSACTIONS(?:\s+SERIAL\s+DATE\s+AMOUNT)+")
#: The product banner. The product name varies by account, so the SHAPE is
#: what is read and no product name is memorised. Deliberately unanchored: on
#: half the family the banner is flattened onto the tail of a disclosure
#: paragraph rather than printed on its own line.
_BANNER_RE = re.compile(r"([A-Z][A-Z /]*[A-Z])\*\s+ACCOUNT\s+-\s+(\d{4,})")

#: The account number the header block prints on its own label. Read as well as
#: the banner's so the two can be required to agree: a file carrying two
#: different account numbers holds more than one account and the `Statement`
#: schema holds one (MASTER_PLAN L-1).
#:
#: `[ \t]` and not `\s`: the last sheet prints the label with its value on the
#: NEXT line, and a run of digits on the next line is a cheque serial rather
#: than an account — `\s` crosses the newline and reads it as one.
_ACCOUNT_RE = re.compile(r"Account Number:[ \t]*(\d{4,})")


def _has_service_centre(text: str) -> bool:
    return (
        _SERVICE_CENTRE_RE.search(text) is not None
        and _SERVICE_PHONE_RE.search(text) is not None
    )


def _has_summary(text: str) -> bool:
    return _SUMMARY_RE.search(text) is not None


def _has_daily_grid(text: str) -> bool:
    return _DAILY_HEAD_RE.search(text) is not None


DETECTION_MARKERS = (
    required("ozk_service_centre", _has_service_centre),
    required("plus_less_sentence_summary", _has_summary),
    required("balance_by_date_grid", _has_daily_grid),
    corroborating("product_account_banner", lambda text: _BANNER_RE.search(text) is not None),
)

detect = make_detector(DETECTION_MARKERS)


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------

#: Where a flattened region stops. Every one of these is a heading or a page
#: marker the platform's own text layer emits, never document content.
_REGION_STOPS = (
    "OTHER TRANSACTIONS",
    "CHECK TRANSACTIONS",
    "BALANCE BY DATE",
    "PAGE ",
    "PLEASE SEE REVERSE",
    "PAYER FEDERAL ID",
    "INTEREST EARNED THIS STATEMENT",
    "Suggestions to help you",
    "--- Page ",
)


def _regions(text: str, head: re.Pattern[str]) -> list[str]:
    """Every run of text `head` opens, up to whatever heading closes it."""
    out: list[str] = []
    for match in head.finditer(text):
        rest = text[match.end():]
        cut = len(rest)
        for stop in _REGION_STOPS:
            index = rest.find(stop)
            if index != -1:
                cut = min(cut, index)
        out.append(rest[:cut])
    return out


#: A row's leading date. Bounded on both sides so a date-shaped fragment of a
#: longer token cannot open a row: `05/2028` inside a description fails the
#: right-hand guard, and the `07/02` of `31/07/02` fails the left-hand one.
_ROW_DATE_RE = re.compile(r"(?<![\d/])(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])(?!\d)")


# ---------------------------------------------------------------------------
# The per-day solve
# ---------------------------------------------------------------------------

#: Budgets, and all three are refusals rather than partial answers: this reader
#: would rather decline a document than publish one side of an unsolved ledger.
#:
#: They are also what makes the enumeration TOTAL. Subset-sum is exponential in
#: the worst case, and a parser that can be made to run for an hour on a
#: printing nobody has seen is a denial-of-service dressed as thoroughness. The
#: row cap additionally bounds the recursion depth, so a pathological day
#: cannot reach `RecursionError` — an exception is not an answer, and a
#: refusal is. The busiest day of the archive family carries 15 rows.
_MAX_DAY_ROWS = 64
_MAX_DAY_NODES = 200_000
_MAX_DAY_SOLUTIONS = 64
#: The same discipline over the CROSS-DAY search. It aborts as soon as two
#: global solutions exist, so the expensive shape is a document with one
#: solution or none and a wide tree; this bounds that too.
_MAX_GLOBAL_NODES = 200_000


def _day_solutions(amounts: list[int], residual: int) -> list[frozenset[int]] | None:
    """Every set of row indices that can be the day's CREDITS, or None.

    The day's signed rows must come to `residual`, so with `S` the sum of the
    magnitudes the credits must come to exactly `(residual + S) / 2`. `None`
    when the enumeration exceeds its budget — which is a refusal, distinct
    from the empty list, which means the day's printed step is unreachable.
    """
    if len(amounts) > _MAX_DAY_ROWS:
        return None
    total = sum(amounts)
    doubled = residual + total
    if doubled < 0 or doubled > 2 * total or doubled % 2:
        return []
    target = doubled // 2
    suffix = [0] * (len(amounts) + 1)
    for index in range(len(amounts) - 1, -1, -1):
        suffix[index] = suffix[index + 1] + amounts[index]

    solutions: list[frozenset[int]] = []
    overflow = False
    nodes = 0

    def walk(index: int, accumulated: int, chosen: list[int]) -> None:
        nonlocal overflow, nodes
        if overflow:
            return
        nodes += 1
        if nodes > _MAX_DAY_NODES:
            overflow = True
            return
        if index == len(amounts):
            if accumulated == target:
                if len(solutions) == _MAX_DAY_SOLUTIONS:
                    overflow = True
                    return
                solutions.append(frozenset(chosen))
            return
        if accumulated > target or accumulated + suffix[index] < target:
            return
        chosen.append(index)
        walk(index + 1, accumulated + amounts[index], chosen)
        chosen.pop()
        walk(index + 1, accumulated, chosen)

    walk(0, 0, [])
    return None if overflow else solutions


def _unique_global(
    per_day: list[list[frozenset[int]]], counts: list[list[int]], credit_count: int
) -> list[frozenset[int]] | None:
    """The one choice of day solutions whose credit rows come to `credit_count`.

    None when there is none, or when there is more than one: an ambiguous
    ledger is refused rather than resolved by preference. Every day is
    enumerated — the printed count is a CROSS-DAY constraint, so a day that is
    locally ambiguous can only be settled by what the other days need.
    """
    lows = [0] * (len(per_day) + 1)
    highs = [0] * (len(per_day) + 1)
    for index in range(len(per_day) - 1, -1, -1):
        lows[index] = lows[index + 1] + min(counts[index])
        highs[index] = highs[index + 1] + max(counts[index])

    found: list[list[frozenset[int]]] = []
    nodes = 0
    overflow = False

    def walk(index: int, accumulated: int, chosen: list[frozenset[int]]) -> None:
        nonlocal nodes, overflow
        if overflow or len(found) > 1:
            return
        nodes += 1
        if nodes > _MAX_GLOBAL_NODES:
            overflow = True
            return
        if index == len(per_day):
            if accumulated == credit_count:
                found.append(list(chosen))
            return
        remaining = credit_count - accumulated
        if remaining < lows[index] or remaining > highs[index]:
            return
        for solution in per_day[index]:
            chosen.append(solution)
            walk(index + 1, accumulated + len(solution), chosen)
            chosen.pop()
            if overflow or len(found) > 1:
                return

    walk(0, 0, [])
    if overflow:
        return None
    return found[0] if len(found) == 1 else None


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

_AVERAGE_RE = re.compile(r"(AVERAGE LEDGER BALANCE):\s*(" + _CENTS + r")")
_INTEREST_RE = re.compile(r"INTEREST PAID THIS PERIOD:\s*(" + _CENTS + r")")


def _as_of(token: str) -> date | None:
    try:
        return date(2000 + int(token[6:8]), int(token[0:2]), int(token[3:5]))
    except ValueError:
        return None


class _Row:
    """One posting: the day it landed on, its magnitude in cents, its words."""

    __slots__ = ("day", "cents", "description")

    def __init__(self, day: str, cents: int, description: str) -> None:
        self.day = day
        self.cents = cents
        self.description = description


def _rows(text: str, start: date, end: date) -> tuple[list[_Row], list[_Row]] | None:
    """(cheques, other postings), or None if any row could not be read."""
    cheques: list[_Row] = []
    for region in _regions(text, _CHECK_HEAD_RE):
        for match in re.finditer(
            r"(?<![\d/.])(\d{2,8})\*?\s+(\d{2}/\d{2})\s+(" + _CENTS + r")", region
        ):
            iso = iso_unique_in_period(
                int(match.group(2)[0:2]), int(match.group(2)[3:5]), start=start, end=end
            )
            cents = _cents(match.group(3))
            if iso is None or cents is None:
                return None
            cheques.append(_Row(iso, cents, f"CHECK {match.group(1)}"))

    others: list[_Row] = []
    for region in _regions(text, _OTHER_HEAD_RE):
        spans = list(_ROW_DATE_RE.finditer(region))
        for index, match in enumerate(spans):
            end_of_row = spans[index + 1].start() if index + 1 < len(spans) else len(region)
            segment = " ".join(region[match.end(): end_of_row].split())
            iso = iso_unique_in_period(
                int(match.group(1)), int(match.group(2)), start=start, end=end
            )
            if iso is None:
                # A date-shaped token the printed period cannot place is not a
                # row this reader may guess at, and it is not description text
                # either: it may be a row whose date was mangled. Fail closed.
                return None
            masked = _QUOTED_RE.sub(lambda hit: " " * len(hit.group(0)), segment)
            amounts = list(_AMOUNT_RE.finditer(masked))
            if not amounts:
                return None
            cents = _cents(amounts[-1].group(0))
            if cents is None:
                return None
            others.append(_Row(iso, cents, segment))
    return cheques, others


def parse_bank_ozk_statement(markdown: str) -> Statement | None:
    """One Bank OZK checking statement, or None."""
    summary = unique_match(markdown, _SUMMARY_RE)
    if summary is None:
        return None
    (previous_as_of, previous, credit_count, credit_total,
     debit_count, debit_total, current_as_of, current, printed_days) = summary.groups()

    opening, closing = _as_of(previous_as_of), _as_of(current_as_of)
    if opening is None or closing is None or opening >= closing:
        return None
    start, end = opening + timedelta(days=1), closing
    # The period is PRINTED, and this is the proof: the bank states both
    # endpoints and then states the length, and the two have to agree before
    # either is published.
    if (end - start).days + 1 != int(printed_days):
        return None

    figures = {
        "previous": _cents(previous),
        "credits": _cents(credit_total),
        "debits": _cents(debit_total),
        "current": _cents(current),
    }
    if any(value is None for value in figures.values()):
        return None
    # The fail-fast: a mis-read summary is rejected before a row is parsed.
    if figures["previous"] + figures["credits"] - figures["debits"] != figures["current"]:
        return None
    credits_expected, debits_expected = int(credit_count), int(debit_count)

    grid: dict[str, int] = {}
    for region in _regions(markdown, _DAILY_HEAD_RE):
        # The column head, dropped so its own `DATE`/`AMOUNT` words cannot be
        # read as data. `[-1]` takes the text after the LAST head, which on a
        # region carrying two heads would discard the cells under the first.
        # No document of this family prints two (measured: 0 dates dropped on
        # all 8), and the direction of the residue is fail-closed — a dropped
        # grid day loses its rows' step and the day-solve refuses the document
        # rather than publishing a short ledger.
        region = region.split("DATE AMOUNT")[-1]
        for match in _ROW_DATE_RE.finditer(region):
            iso = iso_unique_in_period(
                int(match.group(1)), int(match.group(2)), start=start, end=end
            )
            balance = _SIGNED_RE.match(region[match.end():].lstrip())
            if iso is None or balance is None:
                return None
            value = _cents(balance.group(0), signed=True)
            if value is None or (iso in grid and grid[iso] != value):
                return None
            grid[iso] = value
    if not grid:
        return None
    walk = sorted(grid.items())
    if walk[-1][1] != figures["current"]:
        return None

    read = _rows(markdown, start, end)
    if read is None:
        return None
    cheques, others = read
    if len(cheques) + len(others) != credits_expected + debits_expected:
        return None
    if any(row.day not in grid for row in cheques + others):
        return None

    by_day: dict[str, tuple[list[_Row], list[_Row]]] = {
        day: ([], []) for day, _ in walk
    }
    for row in cheques:
        by_day[row.day][0].append(row)
    for row in others:
        by_day[row.day][1].append(row)

    per_day: list[list[frozenset[int]]] = []
    counts: list[list[int]] = []
    balance = figures["previous"]
    for day, printed_balance in walk:
        known, unknown = by_day[day]
        if not known and not unknown:
            return None
        residual = printed_balance - balance + sum(row.cents for row in known)
        solutions = _day_solutions([row.cents for row in unknown], residual)
        if not solutions:
            return None
        per_day.append(solutions)
        counts.append(sorted({len(solution) for solution in solutions}))
        balance = printed_balance

    chosen = _unique_global(per_day, counts, credits_expected)
    if chosen is None:
        return None

    transactions: list[Transaction] = []
    captured_credits = captured_debits = 0
    for (day, _), solution in zip(walk, chosen):
        known, unknown = by_day[day]
        for row in known:
            captured_debits += row.cents
            transactions.append(
                Transaction(date=day, description=row.description,
                            amount=round(-row.cents / 100, 2), direction="debit")
            )
        for index, row in enumerate(unknown):
            credit = index in solution
            if credit:
                captured_credits += row.cents
            else:
                captured_debits += row.cents
            transactions.append(
                Transaction(
                    date=day,
                    description=row.description,
                    amount=round((row.cents if credit else -row.cents) / 100, 2),
                    direction="credit" if credit else "debit",
                )
            )
    # The independent check on the whole solve. Each day's credit sum was fixed
    # by the DAILY GRID; these two figures came from the SUMMARY BLOCK, and
    # nothing this reader did makes them agree.
    if captured_credits != figures["credits"] or captured_debits != figures["debits"]:
        return None

    # The account, from the two places the document prints it. Both must be
    # present and both must agree: a second account number is a second account,
    # and this schema publishes one (MASTER_PLAN L-1).
    banner = unique_match(markdown, _BANNER_RE)
    if banner is None:
        return None
    labelled = {match.group(1) for match in _ACCOUNT_RE.finditer(markdown)}
    if labelled != {banner.group(2)}:
        return None

    stmt = Statement(
        bank="Bank OZK",
        account_name=banner.group(1),
        account_number=banner.group(2),
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=int(printed_days),
        beginning_balance=round(figures["previous"] / 100, 2),
        ending_balance=round(figures["current"] / 100, 2),
        stated_total_credits=round(figures["credits"] / 100, 2),
        stated_total_debits=round(figures["debits"] / 100, 2),
        stated_credit_count=credits_expected,
        stated_debit_count=debits_expected,
        # §CURRENCY. No document of this family prints a currency code. The
        # institution is unambiguously US — an Arkansas post box, a US
        # toll-free service number, a US payer federal ID on the interest
        # block — so the class is the one that says the denomination was
        # asserted from the issuer and read from nothing
        # (CURRENCY_DOCTRINE §B; `analysis/schema.py`).
        currency="USD",
        currency_source="institution_default",
    )
    average = unique_match(markdown, _AVERAGE_RE)
    if average is not None:
        value = _cents(average.group(2))
        if value is not None:
            # Evidence, never the platform's ADB: the doctrine publishes the
            # bank's own average beside the calendar-day one and never as it.
            stmt.bank_reported_average_balance = round(value / 100, 2)
            stmt.bank_reported_average_label = average.group(1)
    interest = unique_match(markdown, _INTEREST_RE)
    if interest is not None:
        value = _cents(interest.group(1))
        if value is not None:
            stmt.stated_interest_paid = round(value / 100, 2)
    stmt.stated_daily_balances = [
        StatementDailyBalance(date=day, balance=round(value / 100, 2))
        for day, value in walk
    ]
    stmt.transactions = transactions
    return stmt
