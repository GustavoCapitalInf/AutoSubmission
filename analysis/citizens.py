from __future__ import annotations

import re
from datetime import date

from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import section_between

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _money(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip().replace("$", "")
    if value.startswith("."):
        value = "0" + value
    return parse_money(value)


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(
        r"Beginning\s+([A-Za-z]+)\s+(\d{2}),\s+(\d{4})\s+through\s+([A-Za-z]+)\s+(\d{2}),\s+(\d{4})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    start_month = _MONTHS.get(sm.lower())
    end_month = _MONTHS.get(em.lower())
    if not start_month or not end_month:
        return None
    return (
        date(int(sy), start_month, int(sd)).isoformat(),
        date(int(ey), end_month, int(ed)).isoformat(),
    )


#: The arithmetic marker between a `Balance Calculation` label and its figure,
#: and the furniture the scan leaves beside the block heading. Both are ink,
#: not information: the strip is a five-row LABELLED grid whose rows are
#: `Previous Balance`, `Checks`, `Debits`, `Deposits & Credit` and `Current
#: Balance`, and the `-` / `+` / `=` glyphs restate the arithmetic the labels
#: already state. Three of the four scanned statements in the archive print
#: `Checks .` and `Debits .` — the subtraction marker resolved as a leader dot
#: — and a fourth prints `Balance Calculation _ -`, a rule fragment between the
#: heading and its first row. Requiring the exact glyph declined all four.
#:
#: What makes widening it safe is NOT the shape of the glyph. It is that this
#: reader now requires the strip's own arithmetic to close
#: (:func:`_summary`): `previous - checks - debits + deposits == current`, to
#: the cent. A strip whose figures were misread cannot satisfy that, so the
#: separator can be treated as furniture without the figures being trusted on
#: the strength of a dot.
#:
#: The class is "ink that is neither a letter nor a figure" — spaces, rules,
#: dots, dashes and the underscore a photographed column rule so often becomes
#: — bounded to four glyphs and never crossing a line break.
_MARKER = r"[^\nA-Za-z0-9]{0,4}"


def _summary(markdown: str) -> tuple[float, float, float, float, float] | None:
    m = re.search(
        r"Balance Calculation" + _MARKER + r"\s+"
        r"Previous Balance\s+(-?[\d,]+\.?\d{0,2}|-\.\d{2}|\.\d{2})\s+"
        r"Checks\s*" + _MARKER + r"\s*([\d,]+\.?\d{0,2}|\.\d{2})\s+"
        r"Debits\s*" + _MARKER + r"\s*([\d,]+\.?\d{0,2}|\.\d{2})\s+"
        r"Deposits\s+&\s+Credit\s+\+\s+([\d,]+\.?\d{0,2}|\.\d{2})\s+"
        r"Current Balance\s+=\s+(-?[\d,]+\.?\d{0,2}|-\.\d{2}|\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    beginning, checks, debits, credits, ending = (_money(value) for value in m.groups())
    if None in {beginning, checks, debits, credits, ending}:
        return None
    # The strip's own identity, and the reason the markers above may be read as
    # furniture. It is the document's arithmetic about itself, not a tolerance:
    # five figures that do not add up are five figures at least one of which
    # was misread, and this parser then has no summary it can publish.
    if abs(beginning - checks - debits + credits - ending) > 0.01:  # type: ignore[operator]
        return None
    return beginning, checks, debits, credits, ending  # type: ignore[return-value]


def _average_balance(markdown: str) -> float | None:
    m = re.search(
        r"average daily checking balance used to qualify this statement period is:\s+\$?([\d,]+)",
        markdown,
        re.IGNORECASE,
    )
    return _money(m.group(1)) if m else None


def _account(markdown: str) -> str | None:
    m = re.search(r"Business Advisor Checking for\s+([X\d-]+)", markdown, re.IGNORECASE)
    return m.group(1) if m else None


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def _parse_inline_rows(
    text: str, *, year: int, sign: int, cents_comma: bool = False
) -> list[Transaction]:
    compact = re.sub(r"\s+", " ", text)
    compact = re.sub(r"^(?:Total (?:Debits|Deposits & Credits)|Other Debits(?: \(Continued\))?|Date Amount Description|\+\s*[\d,]+\.\d{2}|-\s*[\d,]+\.\d{2})\s+", "", compact, flags=re.IGNORECASE)
    # A row begins where the date column begins, and the amount that follows it
    # ends at its cents. The boundary used to require WHITESPACE after those
    # cents, which made a single stray glyph - a column rule the scan resolves
    # as a full stop, `1,633.47.` - weld two printed rows into one: the second
    # row's amount disappears into the first row's description and the ledger
    # is short by it, silently. `(?!\d)` says the same thing about the token
    # that matters (nothing may EXTEND the cents) without making the ink that
    # follows part of the test. Sixty-two rows across the four scanned
    # statements in the archive print that trailing glyph.
    point = r"[.,]" if cents_comma else r"\."
    _amount = r"(?:\d[\d,]*" + point + r"\d{2}|\.\d{2})(?!\d)"
    rows = re.split(r"\s+(?=\d{2}/\d{2}\s+" + _amount + r")", compact)
    txns: list[Transaction] = []
    for row in rows:
        m = re.match(
            r"^(\d{2})/(\d{2})\s+(\d[\d,]*" + point + r"\d{2}|\.\d{2})(?!\d)\W?\s+(.+?)\s*$",
            row.strip(),
        )
        if not m:
            continue
        month, day, amount_raw, desc = m.groups()
        if cents_comma:
            # The final comma is the decimal point, and the reason is the
            # token's own shape rather than a preference: a thousands group is
            # THREE digits, so `44,50` cannot be one. See `_rows_the_total_agrees_with`
            # for the evidence that admits this reading at all.
            amount_raw = re.sub(r",(\d{2})$", r".\1", amount_raw)
        amount = _money(amount_raw)
        if amount is None:
            continue
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=date(year, int(month), int(day)).isoformat(),
            description=re.sub(r"\s+", " ", desc).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
        ))
    return txns


def _rows_the_total_agrees_with(
    text: str, *, year: int, sign: int, printed_total: float | None
) -> list[Transaction]:
    """One section's rows, read strictly first and loosely only on evidence.

    A photographed statement sometimes prints an amount's decimal point as a
    comma — `44,50` where the bank set `44.50`. Reading every such token that
    way would be a tolerance, and a dangerous one: the same shape with a
    THREE-digit tail (`29,444,311`) is a different accident entirely, and
    guessing at it would publish a figure off by a factor of a thousand.

    So the loose reading is never taken on its own authority. The section's
    rows are read with the strict grammar; if their sum already equals the
    total the bank prints for that section, that is the answer. Only when it
    falls short is the section re-read admitting the two-digit comma tail, and
    that re-read is adopted only if it makes the sum equal the printed total
    EXACTLY. The document's own arithmetic is what accepts the reading, and a
    re-read that lands anywhere other than the printed figure is discarded
    whole — including a re-read that overshoots it.
    """
    strict = _parse_inline_rows(text, year=year, sign=sign)
    if printed_total is None:
        return strict
    if abs(sum(abs(txn.amount) for txn in strict) - printed_total) <= 0.01:
        return strict
    relaxed = _parse_inline_rows(text, year=year, sign=sign, cents_comma=True)
    if abs(sum(abs(txn.amount) for txn in relaxed) - printed_total) <= 0.01:
        return relaxed
    return strict


def _debits_section(markdown: str) -> str:
    """Every debit the statement prints, not just the first sub-section.

    `Debits` is a CONTAINER: the bank subdivides it into `ATM/Purchases` and
    `Other Debits`, each repeating under a `(Continued)` heading on every page
    it spills onto. Reading from `Other Debits` — a sub-section heading — to
    `Deposits & Credits` therefore started AFTER any `ATM/Purchases` rows and
    silently dropped them. Measured on the four `STATEMENTS_*-7816` statements
    in the archive, that lost between 2,845.68 and 12,686.52 of printed debits
    per statement and left every one of them failing reconciliation.

    The container heading is the one that carries the electronic-cheque
    footnote; sub-section and `(Continued)` headings carry no dated rows of
    their own, so taking the whole container adds sub-sections without
    double-counting anything. The narrower slice remains as a fallback for a
    layout that prints no container heading at all.
    """
    container = section_between(markdown, r"(?m)^Debits\s+\*\*", r"Deposits & Credits")
    if container.strip():
        return container
    # The container heading is ONE LINE of print, and on a photographed
    # statement one line can be lost outright: an archive scan renders it
    # `sevathie * f Total Debits`, with the right-hand total column welded into
    # the wreckage. Falling straight through to the `Other Debits` sub-section
    # then starts the read AFTER the `ATM/Purchases` sub-section and drops
    # every row in it - the same defect the container heading was introduced to
    # fix, reappearing whenever the heading itself does not survive.
    #
    # So the fallback ladder descends by STRUCTURE rather than by one name: the
    # container's first sub-section heading opens the same span the container
    # would have opened, because the container's own heading line carries no
    # dated rows. `Other Debits` remains the last rung, for a layout that
    # prints no ATM sub-section at all.
    first_subsection = section_between(
        markdown, r"(?im)^\s*ATM\s*/\s*Purchases\s*$", r"Deposits & Credits"
    )
    if first_subsection.strip():
        return first_subsection
    return section_between(markdown, r"Other Debits\s+", r"Deposits & Credits")


#: Where the cheque grid really ends: the next CONTAINER, never page
#: furniture. `Please See Additional Information on Next Page` used to close
#: it, which meant a cheque grid continuing under `Checks (Cont.)` on the
#: following page was cut off at the page break — the same "a boundary inside
#: the section is not the end of it" defect as the debits container above, and
#: worth 8,310.98 and 2,306.38 of unread cheques on two archive statements.
_CHECKS_END = r"(?:Total Debits|Debits\s+\*\*|Deposits & Credits|Current Balance)"

#: The credit grid's own column header opens it. `Date Amount _ Description`
#: is the same header as `Date Amount Description` with a column rule between
#: two of its labels, which is what a photograph of a ruled table looks like.
_CREDITS_START = r"Deposits & Credits.*?Date Amount\W{0,3}\s*Description\s+"

#: ...and the two-column footer closes it. The footer prints `Daily Balance`
#: over the grid on the left and `Current Balance = <figure>` on the right, and
#: which of the two a reader meets FIRST is a property of the reading order,
#: not of the statement: the digital text layer emits the right-hand column
#: first and the OCR of the same page emits the left-hand one first. Naming
#: only one order made the section's end unreachable on every scanned
#: statement in the archive, `section_between` returned "" and
#: `credit_coverage` was 0.000 on all four - the ledger published no credits at
#: all while the summary reconciled, which is the most misleading shape a
#: publication can have. Both orders are the same printed footer.
_CREDITS_END = r"(?:Current Balance\s+Daily Balance|Daily Balance\s+Current Balance)"


def _checks_the_total_agrees_with(
    markdown: str, *, year: int, period: tuple[str, str], printed_total: float | None
) -> list[Transaction]:
    """The cheque grid, widened only as far as its own printed total allows.

    Two glyphs of the grid do not always survive a photograph: the decimal
    point of an amount (`2,549,33`) and the solidus of a date (`0519`). Both
    readings are structural rather than tolerant — a thousands group is three
    digits, and a four-digit date cell is `mmdd` — but neither is taken on that
    argument alone. The strict grid is read first; the widened grid replaces it
    only when the widened rows sum to the `Total Checks` figure the same page
    prints, EXACTLY. A slash-less date is additionally required to land inside
    the statement's own period, so a widened read can never pick up the next
    cheque NUMBER as a date.
    """
    strict = _parse_checks(markdown, year=year)
    if printed_total is None:
        return strict
    if abs(sum(abs(txn.amount) for txn in strict) - printed_total) <= 0.01:
        return strict
    widened = _parse_checks(markdown, year=year, period=period)
    if abs(sum(abs(txn.amount) for txn in widened) - printed_total) <= 0.01:
        return widened
    return strict


def _parse_checks(
    markdown: str, *, year: int, period: tuple[str, str] | None = None
) -> list[Transaction]:
    # The grid is opened by its own COLUMN HEADER, not by the right-hand
    # summary column that happens to be printed beside its first rows.
    # `Total Checks` and the figure under it belong to a narrow column running
    # down the page's right edge, and a photograph reads that column's cells
    # out at the END of whichever grid row they sit beside - so anchoring on
    # `Total Checks` started the section one or two printed rows late. Measured
    # on the four scanned statements in the archive: two cheques lost on one of
    # them, worth 10,200.00 of the 32,571.20 the same page states as the total.
    # `Check # Amount Date` is the grid's own header and it precedes every row.
    section = section_between(
        markdown, r"Check\s*#\s*Amount\s*Date", _CHECKS_END
    ) or section_between(markdown, r"Checks .*?Total Checks\s+", _CHECKS_END)
    txns: list[Transaction] = []
    # The out-of-sequence footnote marker is a glyph the statement itself
    # explains ("checks that are present out of numeric sequence are denoted
    # with an asterisk"), and a photograph resolves that asterisk as `*`, `"`
    # or nothing. It is a footnote about the SEQUENCE, never part of the
    # number, so one non-digit glyph is allowed to stand between the cheque
    # number and its amount rather than the row being dropped. The asterisk
    # itself stays INSIDE the captured number, exactly as before, because it is
    # published in the row's description and moving it would move an audited
    # field on every statement that prints one.
    point = r"[.,]" if period is not None else r"\."
    solidus = r"/?" if period is not None else r"/"
    for check_no, amount_raw, month, day in re.findall(
        r"(\d+\*?)\W{0,2}\s+([\d,]+" + point + r"\d{2}|\.\d{2})\s+(\d{2})" + solidus + r"(\d{2})",
        section,
    ):
        amount = _money(re.sub(r",(\d{2})$", r".\1", amount_raw) if period else amount_raw)
        if amount is None:
            continue
        try:
            posted = date(year, int(month), int(day))
        except ValueError:
            continue
        if period is not None and not (
            date.fromisoformat(period[0]) <= posted <= date.fromisoformat(period[1])
        ):
            # A slash-less date cell is only a date if it IS one: without this
            # the widened pattern would happily read the next cheque's NUMBER
            # as `39/78`.
            continue
        txns.append(Transaction(
            date=posted.isoformat(),
            description=f"Check {check_no}",
            amount=-abs(amount),
            direction="debit",
        ))
    return txns


DETECTION_MARKERS = (
    required("domain", lambda t: "citizensbank.com" in t.lower()),
    # The printed summary this parser reads, not the name of one product. The
    # marker it replaces — `Business Advisor Checking` — is one of at least
    # three products the bank prints on this identical layout (the archive also
    # holds `Business Green Checking` and `Clearly Better Business Checking`),
    # and naming one of them declined 8 statements this parser reconciles to
    # the cent. `Balance Calculation` is the block `_summary` parses, so the
    # detector now claims exactly what the parser can read.
    required("balance_calculation", lambda t: "Balance Calculation" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_citizens_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    summary = _summary(markdown)
    if period is None or summary is None:
        return None
    start, end = period
    year = int(end[:4])
    beginning, printed_checks, printed_debits, credits, ending = summary
    # NOT rounded. `_summary` used to return this sum already formed and the
    # published field carries its float artefact (one archive statement
    # publishes `147530.16999999998`); rounding it here would move an audited
    # figure on a document this card has no business touching. The artefact is
    # real and is reported rather than silently corrected.
    debits = printed_checks + printed_debits
    printed_average = _average_balance(markdown)
    stmt = Statement(
        bank="Citizens Bank",
        account_name="Business Advisor Checking",
        account_number=_account(markdown),
        period_start=start,
        period_end=end,
        days_in_period=_days(start, end),
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
        bank_reported_average_balance=printed_average,
        bank_reported_average_label=(
            "average daily checking balance used to qualify this statement period is"
            if printed_average is not None
            else None
        ),
    )
    debits_text = _debits_section(markdown)
    credits_text = section_between(markdown, _CREDITS_START, _CREDITS_END)
    txns = _checks_the_total_agrees_with(
        markdown, year=year, period=(start, end), printed_total=printed_checks)
    txns.extend(_rows_the_total_agrees_with(
        debits_text, year=year, sign=-1, printed_total=printed_debits))
    txns.extend(_rows_the_total_agrees_with(
        credits_text, year=year, sign=1, printed_total=credits))
    if not txns:
        return None
    stmt.transactions = txns
    return stmt
