"""The Huntington National Bank sectioned business deposit statement.

The layout in one paragraph
---------------------------
One physical line carries the whole account summary (``Beginning Balance`` ...
``Ending Balance``) as label/figure pairs; the period, the day count and the
service-charge-cycle averages follow it on their own lines. Activity is then
printed as named, direction-bearing SECTIONS — ``Deposits (+)``,
``Other Credits (+)``, ``Checks (-)``, ``Other Debits (-)`` — each headed by
its own name, its account number and its own column header, and each repeated
verbatim when it continues after a page break. Fees are itemised in
``Service Charge Detail`` and totalled in ``Service Charge Summary``, and the
period closes with ``Balance Activity``: the bank's own end-of-day balance for
every day it posted anything.

What makes this layout readable is that **the bank prints its own answer four
times over**, so nothing here has to be inferred:

* the summary identity — ``beginning + credits - debits - service charges``;
* the per-direction subtotals, which the sections must add up to;
* the service-charge total, which the itemised fees must net to;
* ``Balance Activity``, an end-of-day balance that the published ledger has to
  reproduce day by day.

`_validate` runs all four and returns ``None`` if any one of them misses. That
is the whole safety argument: this parser cannot publish a ledger that the
statement itself contradicts.

Two conventions of the print are load-bearing and neither is guessed:

**Negatives are printed as a TRAILING minus** (``$2,693.10-``), a mainframe
convention this issuer uses for balances everywhere — the summary's opening and
closing figures, the service-charge-cycle averages and every cell of
``Balance Activity``. It is the only negative marker the layout has, so an
overdrawn statement read without it comes out sign-flipped and still sums
correctly against a sign-flipped closing balance. Six documents of this
issuer's family in the surveyed archive open or close overdrawn, and twelve
print at least one negative daily balance.

**``Service Charge Detail`` prints two money columns** — ``Service Charge (-)``
and ``Waives and Discounts (+)`` — and the flattened text layer keeps no trace
of which column a figure stood in: a charge and a waiver are both
``date amount description``.

What the text layer keeps is the reading ORDER: the charge column is read down
first and the waiver column after it, so the waivers are a SUFFIX of the rows.
That fixes the SHAPE of the split but not where it starts, and the document
answers that itself — ``Service Charge Summary`` states the two column totals
separately. **The boundary is therefore the cut at which the rows before it sum
to the stated charges AND the rows after it sum to the stated waivers, and it
is taken only when exactly one cut satisfies both.** No cut, or more than one,
means the document does not determine the split and this parser does not guess
it: it returns ``None``. That block's own identity (charges − waivers == the
stated total) is checked first, so a misread of the arbiter cannot license a
mis-split.

A first design instead placed the boundary where the printed dates stop
ascending, on the argument that each column's dates ascend and the second
restarts earlier. **It was rejected on measurement and is not what ships**: the
regression only exists when the first waiver predates the last charge, and on
FIVE documents of this folder it does not, so a waiver was booked as a charge
and the fee total came out by twice its amount. Dates are still what prove the
split is right — every fee row has to land on the day ``Balance Activity``
prints — but they are not what locates it.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from .dates import resolve_year
from .money import STRICT_UNSIGNED, pad_leading_decimal, parse_amount
from .parser_registry import excluding, make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction

#: A figure as this issuer prints it: optional ``$``, thousands grouped with
#: commas, two decimals, and the trailing minus that is this layout's only
#: negative marker. Sub-dollar figures are printed without their leading zero
#: (``.60``), so the integer part is optional — but the comma grouping is not,
#: which is what keeps a bare reference number from being read as money. The
#: sign is captured separately rather than folded into the token, so the
#: magnitude goes through the shared strict parser.
_FIGURE = r"\$?(?:\d{1,3}(?:,\d{3})*)?\.\d{2}-?"
_FIGURE_RE = re.compile(rf"^({_FIGURE})$")

#: A posting date. The issuer prints ``MM/DD`` in every activity column; the
#: year is never printed beside it and is resolved from the statement period.
_DAY = r"\d{2}/\d{2}"
_DAY_RE = re.compile(rf"^{_DAY}$")

#: ``Statement Activity From: 02/01/26 to 02/28/26``. The only place the period
#: is printed with its year, and the source of every transaction's year.
_PERIOD_RE = re.compile(
    r"Statement Activity From:\s*(\d{2}/\d{2}/\d{2})\s*to\s*(\d{2}/\d{2}/\d{2})"
)
_DAYS_RE = re.compile(r"Days in Statement Period\s+(\d+)")

#: The product line: ``Huntington Business Checking 100 Account: -------5638``.
#: The account name is the issuer's own product name, whatever it is; only the
#: issuer word and the account-number furniture are fixed.
_PRODUCT_RE = re.compile(r"^(Huntington [A-Za-z0-9 ]+?)\s+Account:\s*-*(\d+)\s*$", re.M)

#: A transaction section: its name, its printed direction, its account.
_SECTION_RE = re.compile(
    r"^(Deposits|Other Credits|Checks|Other Debits)\s*\((\+|-)\)\s*"
    r"Account\s*:\s*-*(\d+)\s*$"
)
#: The non-transaction blocks. Each ends whatever section preceded it.
_BLOCK_RE = re.compile(
    r"^(Service Charge Detail|Service Charge Summary|Balance Activity|Daily Balance"
    r"|Business Overdraft Protection Account|Business Overdraft Protection Activity)"
    r"\s*Account\s*:\s*-*(\d+)\s*$"
)
#: The column header the issuer prints under every section and block heading.
_COLUMN_HEADER_RE = re.compile(
    r"^Date\s+(?:Amount|Balance|Service Charge)\b|^Date\s+Balance\s+Date\b"
)

#: The heading of a SECOND account presented on the same statement — a
#: Business Overdraft Protection line of credit, with its own summary, its own
#: advances and payments and its own daily balance table. Matching it is what
#: makes `parse_huntington_statement` decline: see the L-1 note there.
#:
#: Scope, stated honestly: this keys on the heading of the second-account
#: product this issuer sells today. Another such product under a different
#: heading would not be caught here (recorded as a carried finding).
_LINE_OF_CREDIT_RE = re.compile(
    r"^Business Overdraft Protection Account\s+Account\s*:", re.M
)

#: Labels of the summary line, longest first so that ``Other Credits`` cannot
#: consume the ``Credits (+)`` that precedes it. Every one is issuer furniture:
#: the printed name of a row of this issuer's own summary grid.
_SUMMARY_LABELS = (
    "Beginning Balance",
    "Ending Balance",
    "Credits (+)",
    "Debits (-)",
    "Total Service Charges (-)",
    "Regular Deposits",
    "Electronic Deposits",
    "Wire Transfer Credits",
    "Interest Earned",
    "Other Credits",
    "Regular Checks Paid",
    "Electronic Withdrawals",
    "Wire Transfer Debits",
    "Service Charges",
    "Other Debits",
    "Fees",
)
_SUMMARY_PAIR_RE = re.compile(
    "(" + "|".join(re.escape(label) for label in
                   sorted(_SUMMARY_LABELS, key=len, reverse=True)) + r")\s+(" + _FIGURE + ")"
)

#: Rows of the ``Service Charge Summary`` block: the fee section's own account.
#: Longest first, so ``Credits - Previous Month Charges (+)`` is never read as
#: the ``Other Credits (+)`` that can follow it on the same line.
_SERVICE_SUMMARY_LABELS = (
    "Previous Month Service Charges (-)",
    "Credits - Previous Month Charges (+)",
    "Net Service Charges",
    "Other Charges (-)",
    "Other Credits (+)",
    "Total Service Charges (-)",
)
_SERVICE_SUMMARY_PAIR_RE = re.compile(
    "(" + "|".join(re.escape(label) for label in
                   sorted(_SERVICE_SUMMARY_LABELS, key=len, reverse=True))
    + r")\s+(" + _FIGURE + ")"
)
#: What was charged, and what was given back. ``Net Service Charges`` is an
#: intermediate the block prints between them and is deliberately in neither:
#: adding it would count the previous month's charges twice.
_FEE_CHARGE_PARTS = ("Previous Month Service Charges (-)", "Other Charges (-)")
_FEE_WAIVER_PARTS = ("Credits - Previous Month Charges (+)", "Other Credits (+)")

#: The credit-side and debit-side components of the summary's own totals. The
#: bank prints only the ones that apply, so these are read as "whichever of
#: these are present", never as a required set.
_CREDIT_PARTS = (
    "Regular Deposits", "Electronic Deposits", "Wire Transfer Credits",
    "Other Credits", "Interest Earned",
)
_DEBIT_PARTS = (
    "Regular Checks Paid", "Electronic Withdrawals", "Wire Transfer Debits",
    "Other Debits", "Fees", "Service Charges",
)

#: Exact-cents comparison. Every check in this module is against a figure the
#: bank itself printed, so there is nothing for a tolerance to absorb: a penny
#: of drift means the ledger is not the statement's.
_EXACT = 0.005


def _figure(token: str) -> float | None:
    """A printed figure, signed by its trailing minus."""
    negative = token.endswith("-")
    magnitude = parse_amount(
        pad_leading_decimal(token.rstrip("-").lstrip("$")), STRICT_UNSIGNED
    )
    if magnitude is None:
        return None
    return round(-magnitude if negative else magnitude, 2)


def _lines(markdown: str) -> list[str]:
    return [line.strip() for line in markdown.splitlines()]


# ----------------------------------------------------------------- detection

def detection_text(markdown: str) -> str:
    return markdown.upper()


DETECTION_MARKERS = (
    # The issuer names itself in the return address of every statement page.
    # On its own this is not evidence: a statement of ANOTHER bank that records
    # an ATM withdrawal at a Huntington branch prints the name too (R4-3), and
    # the surveyed archive contains exactly that.
    required("issuer_name", lambda t: "THE HUNTINGTON NATIONAL BANK" in t),
    # ...so the claim rests on this issuer's own summary grid, whose first two
    # cells are printed adjacent on one line. That is the layout, not the name.
    required(
        "summary_grid",
        lambda t: re.search(r"BEGINNING BALANCE\s+\$?[\d,]+\.\d{2}-?\s+CREDITS \(\+\)", t)
        is not None,
    ),
    # The service-mark footer this issuer prints on every page of its own
    # statements. Corroboration only: it is furniture, and furniture changes.
    required(
        "issuer_footer",
        lambda t: "HUNTINGTON BANCSHARES INCORPORATED" in t,
    ),
    # A text layer whose money has lost its decimals cannot be read as money at
    # all, and this layout's every check is arithmetic.
    excluding("no_figures", lambda t: re.search(r"\d\.\d{2}", t) is None),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


# ------------------------------------------------------------------ the read

def _summary(lines: list[str]) -> dict[str, float] | None:
    """The label/figure pairs of the account summary line.

    The whole grid arrives as one physical line and its cells are ordered
    differently between products, so it is read by label and never by position.
    """
    for line in lines:
        if "Beginning Balance" not in line or "Ending Balance" not in line:
            continue
        found: dict[str, float] = {}
        for match in _SUMMARY_PAIR_RE.finditer(line):
            value = _figure(match.group(2))
            if value is None:
                return None
            # First printing wins: the grid states each of its rows once.
            found.setdefault(match.group(1), value)
        return found
    return None


def _period(text: str) -> tuple[date, date] | None:
    match = _PERIOD_RE.search(text)
    if match is None:
        return None
    try:
        start = datetime.strptime(match.group(1), "%m/%d/%y").date()
        end = datetime.strptime(match.group(2), "%m/%d/%y").date()
    except ValueError:
        return None
    return (start, end) if start <= end else None


def _posting_date(day: str, start: date, end: date) -> date | None:
    """``MM/DD`` resolved into the statement period.

    The year is never printed beside a posting date on this layout.
    `dates.resolve_year` is the platform's rule for choosing it, and a date it
    places OUTSIDE the period is refused here rather than published: this
    layout prints its activity sections per statement period, so a row dated
    outside one means the read went wrong.
    """
    parts = day.split("/")
    if len(parts) != 2:
        return None
    month, day_of_month = int(parts[0]), int(parts[1])
    year = resolve_year(month, day_of_month, start, end)
    if year is None:
        return None
    try:
        posted = date(year, month, day_of_month)
    except ValueError:
        return None
    return posted if start <= posted <= end else None


def _row_groups(line: str) -> list[tuple[str, str, str]]:
    """``(day, figure, tail)`` for every posting group printed on one line.

    The deposit and cheque columns are printed two-up — ``Date Amount Serial #
    Type Date Amount Serial # Type`` — so one physical line can carry several
    rows. A group opens only where the print can open one: a bare ``MM/DD``
    immediately followed by a figure. Everything up to the next such pair is
    that row's own tail.
    """
    tokens = line.split()
    groups: list[tuple[str, str, str]] = []
    index = 0
    while index < len(tokens):
        if not (
            _DAY_RE.match(tokens[index])
            and index + 1 < len(tokens)
            and _FIGURE_RE.match(tokens[index + 1])
        ):
            index += 1
            continue
        end = index + 2
        while end < len(tokens):
            if (
                _DAY_RE.match(tokens[end])
                and end + 1 < len(tokens)
                and _FIGURE_RE.match(tokens[end + 1])
            ):
                break
            end += 1
        groups.append((tokens[index], tokens[index + 1], " ".join(tokens[index + 2:end])))
        index = end
    return groups


def _blocks(lines: list[str]) -> list[tuple[str, int, list[str]]]:
    """``(name, sign, body)`` for every section and block, in printed order.

    A heading opens a block and the next heading closes it. Any line that is
    not a heading, not the block's column header and not a posting row closes
    it too: page furniture, legal notices and the issuer's footer are all
    refused by not being read rather than by being named.
    """
    blocks: list[tuple[str, int, list[str]]] = []
    name: str | None = None
    sign = 0
    body: list[str] = []
    expect_header = False

    def flush() -> None:
        nonlocal name, body
        if name is not None:
            blocks.append((name, sign, body))
        name, body = None, []

    for line in lines:
        if not line:
            continue
        section = _SECTION_RE.match(line)
        if section:
            flush()
            name, sign = f"{section.group(1)} ({section.group(2)})", (
                1 if section.group(2) == "+" else -1
            )
            expect_header = True
            continue
        block = _BLOCK_RE.match(line)
        if block:
            flush()
            name, sign = block.group(1), 0
            expect_header = True
            continue
        if name is None:
            continue
        if expect_header and _COLUMN_HEADER_RE.match(line):
            expect_header = False
            continue
        expect_header = False
        if _belongs_to(name, line):
            body.append(line)
        else:
            flush()
    flush()
    return blocks


def _belongs_to(name: str, line: str) -> bool:
    """Is this line content of the block it follows, or the furniture after it?

    Every block but one is a grid of dated rows, so carrying a posting group is
    what makes a line part of it. ``Service Charge Summary`` is the exception:
    it is a row of label/figure pairs with no dates at all, so it is recognised
    by its own printed labels.
    """
    if name == "Service Charge Summary":
        return _SERVICE_SUMMARY_PAIR_RE.search(line) is not None
    return bool(_row_groups(line))


def _transactions(
    blocks: list[tuple[str, int, list[str]]], start: date, end: date
) -> list[Transaction] | None:
    """Every row of every transaction section, signed by its section."""
    txns: list[Transaction] = []
    for name, sign, body in blocks:
        if sign == 0:
            continue
        for line in body:
            for day, figure, tail in _row_groups(line):
                posted = _posting_date(day, start, end)
                amount = _figure(figure)
                # A transaction figure is a magnitude in a direction-bearing
                # column; a trailing minus there would mean the column and the
                # figure disagree, and this layout never prints one.
                if posted is None or amount is None or amount < 0:
                    return None
                txns.append(
                    Transaction(
                        date=posted.isoformat(),
                        description=tail.strip() or name,
                        amount=round(sign * amount, 2),
                        direction="credit" if sign > 0 else "debit",
                    )
                )
    return txns


def _service_charge_summary(blocks: list[tuple[str, int, list[str]]]) -> tuple[float, float] | None:
    """``(charges, waivers)`` as ``Service Charge Summary`` states them.

    The block is the fee section's own account: what was charged, what was
    given back, and the net. It is read because it is the only place the
    document says which of the two columns of ``Service Charge Detail`` a
    figure belongs to — see `_service_charges`. Its own identity
    (charges - waivers == the stated total) is checked here, so a
    mis-read of this block cannot silently license a mis-split.
    """
    for name, _sign, body in blocks:
        if name != "Service Charge Summary":
            continue
        line = " ".join(body)
        found: dict[str, float] = {}
        for match in _SERVICE_SUMMARY_PAIR_RE.finditer(line):
            value = _figure(match.group(2))
            if value is None:
                return None
            found.setdefault(match.group(1), value)
        total = found.get("Total Service Charges (-)")
        if total is None:
            return None
        charges = round(
            sum(found.get(label, 0.0) for label in _FEE_CHARGE_PARTS), 2
        )
        waivers = round(
            sum(found.get(label, 0.0) for label in _FEE_WAIVER_PARTS), 2
        )
        if abs(round(charges - waivers, 2) - total) > _EXACT:
            return None
        return charges, waivers
    return None


def _service_charges(
    blocks: list[tuple[str, int, list[str]]], start: date, end: date
) -> tuple[list[Transaction], float] | None:
    """The itemised fees, split back into their two printed columns.

    ``Service Charge Detail`` sets charges under ``Service Charge (-)`` and
    waivers under ``Waives and Discounts (+)``, and the flattened text keeps no
    trace of which column a figure stood in. It does keep the reading order:
    the charge column is read down first and the waiver column after it, so the
    waivers are a SUFFIX of the rows — the question is only where it starts.

    The document answers that itself. ``Service Charge Summary`` states the two
    column totals separately, so the boundary is the position at which the rows
    before it sum to the stated charges and the rows after it sum to the stated
    waivers. If no position satisfies both, or more than one does, the split is
    not determined by the document and this parser does not guess it.
    """
    rows: list[tuple[date, float, str]] = []
    for name, _sign, body in blocks:
        if name != "Service Charge Detail":
            continue
        for line in body:
            for day, figure, tail in _row_groups(line):
                posted = _posting_date(day, start, end)
                amount = _figure(figure)
                # A figure in either fee column is a magnitude; the column is
                # what carries the direction, and neither column prints a sign.
                if posted is None or amount is None or amount < 0:
                    return None
                rows.append((posted, amount, tail.strip()))
    if not rows:
        return [], 0.0

    stated = _service_charge_summary(blocks)
    if stated is None:
        return None
    charges, waivers = stated

    boundaries = [
        cut
        for cut in range(len(rows) + 1)
        if abs(round(sum(amount for _d, amount, _t in rows[:cut]), 2) - charges) <= _EXACT
        and abs(round(sum(amount for _d, amount, _t in rows[cut:]), 2) - waivers) <= _EXACT
    ]
    if len(boundaries) != 1:
        return None
    cut = boundaries[0]

    txns: list[Transaction] = []
    for index, (posted, amount, tail) in enumerate(rows):
        charge = index < cut
        txns.append(
            Transaction(
                date=posted.isoformat(),
                description=tail or ("Service charge" if charge else "Service charge waiver"),
                amount=round(-amount if charge else amount, 2),
                direction="debit" if charge else "credit",
            )
        )
    return txns, round(charges - waivers, 2)


def _daily_balances(
    blocks: list[tuple[str, int, list[str]]], start: date, end: date
) -> list[tuple[date, float]] | None:
    """``Balance Activity``: the bank's own end-of-day balance, by day.

    The table opens with the CLOSING balance of the previous period, which is
    dated outside this statement and is therefore not one of this period's
    daily balances.
    """
    out: list[tuple[date, float]] = []
    for name, _sign, body in blocks:
        if name != "Balance Activity":
            continue
        for line in body:
            tokens = line.split()
            index = 0
            while index + 1 < len(tokens):
                if not (_DAY_RE.match(tokens[index]) and _FIGURE_RE.match(tokens[index + 1])):
                    index += 1
                    continue
                balance = _figure(tokens[index + 1])
                if balance is None:
                    return None
                posted = _posting_date(tokens[index], start, end)
                if posted is not None:
                    out.append((posted, balance))
                index += 2
    return out


# ----------------------------------------------------------------- the proof

def _validate(
    summary: dict[str, float],
    section_txns: list[Transaction],
    fee_txns: list[Transaction],
    service_net: float,
    balances: list[tuple[date, float]],
) -> bool:
    """Every check the statement makes available. All four must hold.

    None of these is a tolerance on our own arithmetic: each compares the
    published ledger against a figure this document printed.
    """
    beginning = summary.get("Beginning Balance")
    ending = summary.get("Ending Balance")
    credits = summary.get("Credits (+)")
    debits = summary.get("Debits (-)")
    if beginning is None or ending is None or credits is None or debits is None:
        return False
    charges = summary.get("Total Service Charges (-)", 0.0)

    # 1. The summary identity, entirely between figures the bank printed.
    #
    #    Stated honestly: given checks 3 and 4 this is REDUNDANT, and no
    #    document can isolate it. Check 3 pins the published credit and debit
    #    sums to `credits` and `debits` and the fee net to `charges`; check 4
    #    pins `beginning + every published row == ending`; substituting the
    #    first into the second yields exactly this equation. It is kept because
    #    it is the one check that states the bank's own summary identity
    #    directly, so it still holds if either of the others is ever narrowed —
    #    and a mutation test will report it as unkillable, which is the truth
    #    rather than a gap in the fixtures.
    if abs(round(beginning + credits - debits - charges, 2) - ending) > _EXACT:
        return False

    # 2. Each printed total is the sum of the components printed beneath it.
    #    A product prints only the components that apply, so a total with no
    #    components printed is not checked here — the section sums below cover
    #    it.
    for total, parts in ((credits, _CREDIT_PARTS), (debits, _DEBIT_PARTS)):
        present = [summary[label] for label in parts if label in summary]
        if present and abs(round(sum(present), 2) - total) > _EXACT:
            return False

    # 3. The sections add up to the totals, and the fees net to the fee total.
    #    Service-charge rows are excluded from the section sums: where the bank
    #    states them separately they are not inside ``Debits (-)``, and where it
    #    folds them in it itemises no separate detail and `service_net` is 0.
    section_credits = round(sum(t.amount for t in section_txns if t.amount > 0), 2)
    section_debits = round(-sum(t.amount for t in section_txns if t.amount < 0), 2)
    if abs(section_credits - credits) > _EXACT or abs(section_debits - debits) > _EXACT:
        return False
    if abs(service_net - charges) > _EXACT:
        return False

    # 4. The published ledger reproduces the bank's own end-of-day balance on
    #    every day it printed one. This is what proves the DATES, and with them
    #    the average daily balance; the sums above cannot see a misdated row.
    if not balances:
        return False
    running = beginning
    index = 0
    ordered = sorted(section_txns + fee_txns, key=lambda t: t.date)
    for day, printed in balances:
        while index < len(ordered) and date.fromisoformat(ordered[index].date) <= day:
            running = round(running + ordered[index].amount, 2)
            index += 1
        if abs(running - printed) > _EXACT:
            return False
    while index < len(ordered):
        running = round(running + ordered[index].amount, 2)
        index += 1
    return abs(running - ending) <= _EXACT


def _stated_service_charge(summary: dict[str, float]) -> float | None:
    """The period's total service charge, as the bank states it.

    Two printings, and this issuer uses one or the other: a separate
    ``Total Service Charges (-)`` row outside ``Debits (-)``, or ``Fees`` and
    ``Service Charges`` as components inside it. `reconcile` accepts the
    summary identity either way, so both are published as the same field.

    A PRINTED ZERO is a stated figure and is published as 0.00. Reading it as
    "absent" would say the bank never stated a service charge on a statement
    that stated it was nothing — which is a different claim, and the one an
    `or` chain silently makes.
    """
    total = summary.get("Total Service Charges (-)")
    if total is not None:
        return total
    parts = [summary[label] for label in ("Fees", "Service Charges") if label in summary]
    return round(sum(parts), 2) if parts else None


def parse_huntington_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    # A Business Overdraft Protection line of credit is a SECOND account, with
    # its own summary, its own advances and payments and its own daily balance
    # table, printed on the same statement as the deposit account. The schema
    # carries one account per statement (L-1), so publishing this document
    # would mean publishing one of its two accounts and silently dropping the
    # other. Refused here, at parse, so the document is reported as a
    # recognised layout we decline rather than as a bank nobody has seen.
    if _LINE_OF_CREDIT_RE.search(markdown):
        return None

    lines = _lines(markdown)
    period = _period(markdown)
    summary = _summary(lines)
    if period is None or summary is None:
        return None
    start, end = period

    blocks = _blocks(lines)
    txns = _transactions(blocks, start, end)
    fees = _service_charges(blocks, start, end)
    balances = _daily_balances(blocks, start, end)
    if txns is None or fees is None or balances is None:
        return None
    fee_txns, service_net = fees
    if not txns and not fee_txns:
        return None
    if not _validate(summary, txns, fee_txns, service_net, balances):
        return None
    txns = sorted(txns + fee_txns, key=lambda t: t.date)

    product = _PRODUCT_RE.search(markdown)
    days = _DAYS_RE.search(markdown)
    return Statement(
        bank="Huntington National Bank",
        account_name=product.group(1) if product else None,
        account_number=product.group(2) if product else None,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        beginning_balance=summary["Beginning Balance"],
        ending_balance=summary["Ending Balance"],
        days_in_period=int(days.group(1)) if days else None,
        stated_total_credits=summary["Credits (+)"],
        stated_total_debits=summary["Debits (-)"],
        # The issuer prints no instance count beside either total, so both
        # stated counts stay unset. Deriving them from the ledger would
        # manufacture the oracle the platform checks the ledger against.
        stated_service_charge=_stated_service_charge(summary),
        # `Average Ledger Balance` is deliberately NOT published as the bank's
        # stated average: this statement prints it under the footnote "the
        # above balances correspond to the service charge cycle for this
        # account", which is not the statement period. See the cell record.
        stated_daily_balances=[
            StatementDailyBalance(date=day.isoformat(), balance=balance)
            for day, balance in balances
        ],
        transactions=txns,
    )
