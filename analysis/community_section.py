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


#: The printed summary grid. Its four rows are read ONE AT A TIME, by each
#: row's own printed label, rather than as one fixed sequence.
#:
#: The platform prints this grid in two arrangements. The common one is a
#: single column of four rows in the order opening / credits / debits /
#: closing. The other is two columns, and its right-hand column interleaves
#: UNDATED statistics rows between the rows of the left one::
#:
#:     02/28/2026 Balance Last Statement $19,816.18 Minimum Balance $5,871.60
#:     10 Credit(s) This Period $106,636.53 Average Ledger Balance $25,262.90
#:     24 Debit(s) This Period $87,613.05 Average Available Balance $21,851.25
#:     03/31/2026 Balance This Statement $38,839.66
#:
#: One ordered regex can only read the first arrangement. Reading each row by
#: its own label reads both, and never has to be told which one it is looking
#: at - which is the difference between a platform reader and a per-layout one.
#:
#: The rule that separates a balance row from a statistic is STRUCTURAL and is
#: the platform's own: **a summary balance row carries the date it is a balance
#: ON; a statistic carries no date.** `Minimum Balance` and `Average Ledger
#: Balance` are balances by name and are excluded by that rule alone, with no
#: list of their names anywhere in this file. Of the dated rows, the first is
#: the opening and the last is the closing, because that is the only ordering
#: the grid has.
_SUMMARY_HEADER_RE = re.compile(r"Account Summary Date Description Amount", re.IGNORECASE)

#: Where the summary block ends. Each alternative is the printed name or grid
#: header of the block that follows it, so the boundary is the document's own
#: furniture rather than a character distance.
_SUMMARY_END_RE = re.compile(
    r"(?:Date Description Amount"
    r"|Account Activity"
    r"|Checks Cleared"
    r"|Daily Balances"
    r"|Interest Summary"
    r"|Overdraft and Returned Item Fees"
    r"|Service Charge Summary)",
    re.IGNORECASE,
)

#: A dated balance row: the date it is a balance on, a label naming it, and the
#: figure. The label is bounded to a few words so it cannot swallow a sentence,
#: and it must contain the word the platform names these rows by - checked in
#: `_balance_rows` rather than spelled into a list of the four wordings this
#: archive happens to print (`Beginning Balance`, `Beginning Statement
#: Balance`, `Statement Beginning Balance`, `Balance Last Statement`).
_BALANCE_ROW_RE = re.compile(
    r"(" + _DATE + r")\s+([A-Za-z][A-Za-z ]{2,34}?)\s+(" + _SIGNED_MONEY + r")"
)

#: The period's two count rows. The CREDIT total keeps the unsigned pattern;
#: the DEBIT total may print a leading minus.
#:
#: That asymmetry is the platform's, not a convenience. These totals are
#: magnitudes whose direction is the row they are printed on, and where an
#: issuer prints the direction on the figure as well it can only ever be the
#: debit that carries it - a credit total that reduced the balance would
#: contradict the row it is printed on, and refusing to read one is right.
#: Measured over the 115 archive documents: no credit total carries a sign,
#: one debit total does (`106 Debit(s) This Period -$372,804.35`, whose
#: summary identity closes on the MAGNITUDE). So the minus is consumed and the
#: magnitude published, and a signed credit total still fails the match
#: outright - which is what `test_the_totals_are_magnitudes_and_a_signed_total_
#: is_not_invented` pins.
_COUNT_ROW_RE = re.compile(
    r"(\d+)\s+Credit\(s\) This Period\s+(" + _MONEY + r")"
    r"|(\d+)\s+Debit\(s\) This Period\s+(-?" + _MONEY + r")",
    re.IGNORECASE,
)


class _Summary:
    """The four figures the summary grid prints, and the counts beside them."""

    __slots__ = (
        "start_date", "beginning", "credit_count", "credits",
        "debit_count", "debits", "end_date", "ending",
    )

    def __init__(self, start_date, beginning, credit_count, credits,
                 debit_count, debits, end_date, ending):
        self.start_date = start_date
        self.beginning = beginning
        self.credit_count = credit_count
        self.credits = credits
        self.debit_count = debit_count
        self.debits = debits
        self.end_date = end_date
        self.ending = ending


def _summary_region(text: str) -> str | None:
    """The printed summary grid alone, cut at the block that follows it."""
    header = _SUMMARY_HEADER_RE.search(text)
    if not header:
        return None
    end = _SUMMARY_END_RE.search(text, header.end())
    return text[header.end():end.start() if end else len(text)]


def _balance_rows(region: str) -> list[tuple[str, str]]:
    """`(date, figure)` for every DATED balance row, in printed order."""
    return [
        (match.group(1), match.group(3))
        for match in _BALANCE_ROW_RE.finditer(region)
        if "balance" in match.group(2).lower()
    ]


def _summary(block: str) -> _Summary | None:
    """The summary grid of `block`, or None when it is not fully printed.

    Fail-closed by construction: a grid missing either balance row, or either
    printed count, yields None rather than a partially-filled summary. Every
    downstream check compares the published ledger against these figures, so a
    summary with a hole in it would weaken the gate instead of failing it.
    """
    region = _summary_region(_clean(block))
    if region is None:
        return None

    balances = _balance_rows(region)
    if len(balances) < 2:
        return None
    (start_date, beginning), (end_date, ending) = balances[0], balances[-1]

    counts: dict[str, tuple[str, str]] = {}
    for match in _COUNT_ROW_RE.finditer(region):
        if match.group(1) is not None:
            counts.setdefault("credit", (match.group(1), match.group(2)))
        else:
            # `lstrip("-")` and not `abs()`: the figure stays the string the
            # bank printed, and `_money` - which admits no sign - is what turns
            # it into a number, so a minus can never reach the published total.
            counts.setdefault("debit", (match.group(3), match.group(4).lstrip("-")))
    if "credit" not in counts or "debit" not in counts:
        return None

    return _Summary(
        start_date, beginning, counts["credit"][0], counts["credit"][1],
        counts["debit"][0], counts["debit"][1], end_date, ending,
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


#: The trailer a section prints under its last row: `N item(s) totaling $X`.
#:
#: It is an ORACLE, not a row. It carries no date of its own, so it lands in
#: the final dated row's chunk, and this reader takes the LAST money in a chunk
#: as the amount - so left in place it silently republishes the section's TOTAL
#: as its last transaction's amount. On a section of 18 items totaling
#: $40,458.87 that is a four-figure error on one row that still leaves the row
#: count right, which is precisely the kind of defect a count check cannot see.
#:
#: Cut here, at the one place a row's text is turned into money, rather than in
#: `_clean`: `_section_oracle_disagrees` reads these same trailers as an
#: independent check on what this function captured, and a scrub would delete
#: the evidence that check depends on.
_SECTION_TRAILER_RE = re.compile(r"\s*\d+\s+item\(s\) totaling\s+" + _MONEY, re.IGNORECASE)


def _dated_amount_rows(body: str, *, sign: int, year: int) -> list[Transaction]:
    text = _clean(body)
    dates = list(re.finditer(r"\b" + _DATE + r"\b", text))
    txns: list[Transaction] = []
    for i, match in enumerate(dates):
        end = dates[i + 1].start() if i + 1 < len(dates) else len(text)
        chunk = _SECTION_TRAILER_RE.sub(" ", text[match.start():end]).strip()
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


#: Sub-layout J-B. Instead of naming a section per direction, this arrangement
#: prints ONE `Account Activity` ledger with a running balance, and the
#: direction of a row is the direction its balance moved. The two money columns
#: are headed differently by different issuers (`Debits Credits`,
#: `Withdrawal Deposit`), so the header is matched as *two column words before
#: `Balance`* rather than by either pair of names.
_ACTIVITY_HEADER_RE = re.compile(
    r"Account Activity(?:\s+\(continued\))?\s+(?:Post\s+)?Date\s+Description\s+"
    r"[A-Za-z]+\s+[A-Za-z]+\s+Balance",
    re.IGNORECASE,
)

#: The blocks that can follow the activity ledger, each named by its own
#: printed heading - the same discipline `_SECTION_END_RE` uses.
_ACTIVITY_END_RE = re.compile(
    r"\s+(?:Checks Cleared|Daily Balances|Overdraft and Returned Item Fees"
    r"|Service Charge Summary|Interest Summary|Thank you)",
    re.IGNORECASE,
)


def _activity_rows(block: str, *, year: int) -> list[Transaction]:
    """The J-B running-balance ledger, signed by the balance it moved to.

    Returns `[]` for a document that does not print this arrangement, and -
    deliberately - for one whose balance chain does not close. The chain IS the
    direction evidence here: a row whose printed balance does not equal the
    previous balance plus the signed amount means the row was mis-read, and
    guessing its direction from a keyword would publish that mis-read with a
    plausible sign on it.
    """
    text = _clean(block)
    header = _ACTIVITY_HEADER_RE.search(text)
    if not header:
        return []
    end = _ACTIVITY_END_RE.search(text, header.end())
    body = text[header.end():end.start() if end else len(text)]

    txns: list[Transaction] = []
    previous: float | None = None
    for part in re.split(r"(?=\b" + _DATE + r"\s)", body):
        match = re.match(r"(" + _DATE + r")\s+(.*)", part.strip(), re.DOTALL)
        if not match:
            continue
        rest = _SECTION_TRAILER_RE.sub(" ", match.group(2))
        monies = list(re.finditer(_SIGNED_MONEY, rest))
        if len(monies) < 2:
            # One figure is the opening or closing balance row the ledger
            # prints as a bookend; it is not a posting. Its balance still
            # anchors the chain the postings are checked against.
            if len(monies) == 1 and previous is None:
                previous = _balance(monies[0].group())
            continue
        amount = _money(monies[-2].group())
        balance = _balance(monies[-1].group())
        if amount is None or balance is None:
            return []
        if datetime.strptime(match.group(1), "%m/%d/%Y").year != year:
            return []
        if previous is None:
            return []
        signed = amount if balance >= previous else -amount
        if abs(round(previous + signed, 2) - round(balance, 2)) > 0.01:
            return []
        description = re.sub(r"\s+", " ", rest[:monies[-2].start()]).strip()
        txns.append(
            Transaction(
                date=_iso(match.group(1)),
                description=description,
                amount=round(signed, 2),
                direction="credit" if signed >= 0 else "debit",
                running_balance=balance,
            )
        )
        previous = balance
    return txns


def _section_oracle_disagrees(block: str, txns_by_section: list[list[Transaction]]) -> bool:
    """Does any section's printed `N item(s) totaling $X` trailer disagree?

    An INDEPENDENT oracle, and the only per-section one this platform prints:
    the summary grid checks the whole direction, so a row that landed in the
    wrong section of the right direction is invisible to it and visible here.
    Sections that print no trailer are simply not checked - absent evidence is
    never read as agreement.
    """
    # A section broken by a page break is reprinted as `<name> (continued)`,
    # and `_sections` - rightly - treats each printed header as its own run.
    # The trailer, though, is printed ONCE, under the last of those runs, and
    # counts the whole section. So the rows are accumulated across runs and
    # compared when the trailer appears, rather than run by run: comparing the
    # whole section's printed count against the tail end of it would report
    # every page-broken section as a disagreement.
    pending: list[Transaction] = []
    for (_sign, body), captured in zip(_sections(block), txns_by_section):
        pending.extend(captured)
        trailer = _SECTION_TRAILER_RE.search(_clean(body))
        if not trailer:
            continue
        printed = re.match(r"\s*(\d+)\s+item\(s\) totaling\s+(" + _MONEY + r")",
                           trailer.group(), re.IGNORECASE)
        if not printed:
            continue
        total = _money(printed.group(2))
        if total is None:
            return True
        if int(printed.group(1)) != len(pending):
            return True
        if abs(round(sum(abs(t.amount) for t in pending), 2) - total) > 0.02:
            return True
        pending = []
    return False


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
    start_date, end_date = summary.start_date, summary.end_date
    beginning, ending = summary.beginning, summary.ending
    credits, debits = summary.credits, summary.debits
    credit_count, debit_count = summary.credit_count, summary.debit_count
    start_year = datetime.strptime(start_date, "%m/%d/%Y").year
    end_year = datetime.strptime(end_date, "%m/%d/%Y").year
    if start_year != end_year:
        return None

    # Which of the two arrangements this account printed is decided by whether
    # it printed per-direction SECTIONS, not by whether the first reading
    # happened to return something. `Checks Cleared` is printed by both
    # arrangements, so testing "did we capture anything at all" would let a
    # single cheque row mask an entire J-B ledger - which is what it did on
    # eleven archive documents before this was written as a layout choice.
    by_section: list[list[Transaction]] = [
        _dated_amount_rows(body, sign=sign, year=end_year)
        for sign, body in _sections(block)
    ]
    section_rows = [txn for rows in by_section for txn in rows]
    if section_rows:
        if _section_oracle_disagrees(block, by_section):
            return None
        txns = section_rows + _check_rows(block, year=end_year)
    else:
        # Sub-layout J-B: one `Account Activity` ledger carrying every posting
        # this account made, cheques included, each signed by the balance it
        # moved to. Adding `_check_rows` here would publish those cheques twice.
        txns = _activity_rows(block, year=end_year)
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
    # Counted by the COLUMN the bank printed the row in, not by the sign of its
    # amount. The platform posts genuine zero-amount rows (a returned ACH of
    # $0.00, printed under `Deposits` and counted by the bank as one credit);
    # such a row is on exactly one side of the bank's count and on NEITHER side
    # of a sign test, so a sign-keyed count rejects a document whose ledger is
    # in fact complete. `reconcile` states the same rule for the same reason.
    credit_rows = sum(1 for t in stmt.transactions if t.direction == "credit")
    debit_rows = sum(1 for t in stmt.transactions if t.direction == "debit")
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


# ===========================================================================
# The platform itself, registered without naming an issuer
# ===========================================================================
#
# Mission Valley and Dakota West above are two issuers on a CORE PROCESSOR's
# statement, not two banks with similar layouts, and the archive prints the
# same template under twenty-two different issuers. Registering it per issuer
# would mean a new registration, a new marker pair and a new fixture for each
# one, forever, and would leave every issuer nobody has met yet unread.
#
# So this registration keys on the TEMPLATE'S OWN FURNITURE and reads the
# issuer OUT OF THE DOCUMENT. That is the mission_valley product-label lesson
# applied one level up: publish what the document prints, rather than what a
# constant in this file says it should print.

#: The template's own summary grid header. Measured over the 3,367 archive
#: documents that have offline text: it appears in 115 of them and every one is
#: this platform - no near misses, nothing else prints this exact grid. Paired
#: with the printed period counts below, which is what keeps a document that
#: merely quotes the phrase from claiming (R4-3, and the two-required-marker
#: invariant in tests/test_parser_conformance.py).
_PLATFORM_GRID = "account summary date description amount"

_PERIOD_COUNT_RE = re.compile(r"\d+\s+Credit\(s\) This Period", re.IGNORECASE)

PLATFORM_DETECTION_MARKERS = (
    required("summary_grid", lambda t: _PLATFORM_GRID in _clean(t).lower()),
    required("period_counts", lambda t: bool(_PERIOD_COUNT_RE.search(_clean(t)))),
)

detect_platform = make_detector(PLATFORM_DETECTION_MARKERS)

#: How this template identifies its issuer: a domain printed under a label that
#: says it is the bank's own. The LABEL is the whole point. Five of the 115
#: archive documents print no labelled domain, and four of those five DO print
#: bare domains - `walmart.com`, `apple.com`, `gosq.com` - inside transaction
#: descriptions. Reading "the first domain in the document" would publish a
#: merchant as the issuer on exactly those documents, so the label is required
#: and a document without one is declined rather than guessed at.
_ISSUER_RE = re.compile(
    r"(?:Online(?:\s+(?:Access|Banking))?|Web\s?site|Internet\s+Banking"
    r"|Visit(?:\s+us)?(?:\s+at)?)"
    r"[:\s]+((?:www\.)?(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,10})\b",
    re.IGNORECASE,
)


#: The masthead: everything the statement prints before it starts listing
#: accounts. The issuer's own contact block lives here, and the disclosures
#: that cite OTHER institutions do not - a statement of this template quotes
#: its state regulator (`Website: www.dob.texas.gov`) in the fine print further
#: down, and reading the whole document would see two labelled domains and be
#: unable to say which was the bank.
_MASTHEAD_END_RE = re.compile(r"Summary of Accounts|Account Summary Date Description Amount",
                              re.IGNORECASE)


def _issuer(markdown: str) -> str | None:
    """The issuer this document names as its own, or None.

    Case and the `www.` prefix are normalised away because a domain is
    case-insensitive and `www.` is not part of the name - the same issuer
    prints `Website Columbiabankonline.com` on one statement and
    `Online www.columbiabankonline.com` on another. Nothing else is
    transformed: the published string is the name the bank printed.

    Two DIFFERENT labelled domains in the masthead means the document does not
    identify one issuer, and this returns None rather than picking one.
    """
    text = _clean(markdown)
    end = _MASTHEAD_END_RE.search(text)
    masthead = text[:end.start()] if end else text
    found = {
        match.group(1).lower().removeprefix("www.")
        for match in _ISSUER_RE.finditer(masthead)
    }
    return found.pop() if len(found) == 1 else None


#: An account section of this template: the product name and account number the
#: statement prints as a heading, immediately followed by that account's own
#: summary grid. Anchoring on the grid is what makes this structural - a
#: `(continued)` reprint of the same heading on a later page carries no grid, so
#: it is not mistaken for a second account, and no list of product names is
#: needed to recognise one.
#: Some issuers print something between the heading and the grid - the
#: account's marketing tier (`... - XXXXXX3138 Rogue Business Checking Basic
#: Account Summary ...`) or its joint owners (`... - XXXXXX8073 Joint Owner
#: -Samuel D Dorner;Joint Owner -Mckinsy Dorner Account Summary ...`).
#:
#: The gap is allowed, but it may contain NO DIGIT. That single restriction is
#: what makes it safe rather than merely tolerant: every account number on this
#: template is a digit run, so a gap without digits cannot span another
#: account's heading, and the pattern therefore cannot pair a heading with a
#: grid belonging to a different account no matter how long the gap grows.
#: A product name STARTS with a word and may then contain short numbers
#: (`BUSINESS 150 CHECKING`). Spelling it as a token sequence rather than as a
#: run of permitted characters is what keeps the left edge honest, because a
#: regex matches leftmost-first and this heading is preceded on the page by
#: figures and furniture:
#:
#: * a class admitting `/` and long digit runs let the name begin in the page
#:   header - four documents published `tal Statement Ending 01/31/2026
#:   Business Checking` as their account name;
#: * allowing a NUMBER to open the name let it begin inside the money printed
#:   just before it - `$1,034.78 BASIC BUSINESS CHECKING` became
#:   `78 BASIC BUSINESS CHECKING`.
#:
#: With this shape neither is reachable: no token can be a date (`01/31/2026`
#: contains `/`), none can be a masked account number (`XXXXXX6909` is letters
#: glued to four digits), and none can be the tail of an amount.
_NAME_WORD = r"[A-Za-z][A-Za-z&'.-]*"
_NAME_TOKEN = r"(?:" + _NAME_WORD + r"|\d{1,3})"
_PLATFORM_ACCOUNT_RE = re.compile(
    r"(" + _NAME_WORD + r"(?: " + _NAME_TOKEN + r"){0,7}?)\s*-\s*([X\d]{4,})\s+"
    r"(?:[A-Za-z][^\d$]{0,72}?\s+)?"
    r"Account Summary Date Description Amount",
    re.IGNORECASE,
)


def _account_blocks(markdown: str) -> list[tuple[str, str, str]]:
    """`(product, account_number, block)` for every account the document prints."""
    text = _clean(markdown)
    matches = list(_PLATFORM_ACCOUNT_RE.finditer(text))
    blocks = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group(1).strip(), match.group(2), text[match.start():end]))
    return blocks


def parse_community_section_statement(markdown: str) -> Statement | None:
    """Any issuer's statement on this core-processor template.

    Declines - rather than guesses - in three named situations, each of which
    is a fact about the document and not a gap in this reader:

    * the document names no single issuer (`_issuer`);
    * more than one of its accounts has activity. The `Statement` schema holds
      ONE account (MASTER_PLAN L-1), and this template is used by credit unions
      that print a membership share, a checking account and a savings account
      side by side. Publishing the busiest one silently would report a subset
      of the customer's money as though it were all of it. Where exactly one
      account posted anything the others are dormant bookends, and reading that
      one is reading the document;
    * the ledger does not reproduce every figure the summary grid printed -
      the gate `_parse_sectioned_statement` already applies.
    """
    if not detect_platform(markdown).claims:
        return None
    issuer = _issuer(markdown)
    if issuer is None:
        return None

    parsed: list[Statement] = []
    for product, number, block in _account_blocks(markdown):
        stmt = _parse_sectioned_statement(
            block, bank=issuer, account_name=product, account_number_pattern=None
        )
        if stmt is not None and stmt.transactions:
            stmt.account_number = number
            parsed.append(stmt)

    if len(parsed) != 1:
        return None
    return parsed[0]
