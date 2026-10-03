from __future__ import annotations

import re
from datetime import datetime

from .date_tokens import parsed_datetime
from .holder_name import first_page, holder_from_name, page_lines
from .money import STRICT_LEADING_SIGN, STRICT_UNSIGNED, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .sibling_omission import SectionLedger, evidence_class, publish_omissions


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


#: The one printed date format this platform's paper uses. Named once so the
#: five readers below cannot drift, and so the refusal law has a single seam.
_DATE_FORMAT = "%m/%d/%Y"


def _strptime(value: str, reader: str) -> datetime:
    """`_DATE_FORMAT` applied to a printed cell, refusing without quoting it.

    `reader` is this module's own symbol name, concatenated onto the module's:
    both halves are source symbols, so nothing read out of a document can reach
    the refusal message (W3 §PRIVACY3).
    """
    return parsed_datetime(value, _DATE_FORMAT, reader="community_section." + reader)


def _iso(value: str) -> str:
    """The printed date cell as ISO.

    Through `date_tokens.parsed_datetime` rather than `datetime.strptime`
    directly: `strptime`'s own ValueError is
    ``time data '<the printed date>' does not match format '...'`` and would
    carry the cell across an exception boundary (W3 §PRIVACY3). Control flow is
    unchanged — the same cells raise, with the same class.
    """
    return _strptime(value, "_iso").date().isoformat()


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
    r"(?<![A-Za-z])((?:[A-Za-z]+ )?(Credits|Debits|Deposits))"
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


def _sections(text: str) -> list[tuple[str, int, str]]:
    """`(name, sign, body)` for every transaction section, in printed order.

    A section runs from its own grid header to the next section's header, so
    rows always land in the section that printed them; the last one runs to
    whichever non-transaction block follows it.

    `name` is the section's printed name WITHOUT its `(continued)` marker, so
    the runs a page break split apart can be recognised as one section again
    by whoever needs that - which `_section_oracle_disagrees` does, and the
    row reader deliberately does not.
    """
    matches = list(_SECTION_RE.finditer(text))
    sections: list[tuple[str, int, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        limit = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        end = _SECTION_END_RE.search(text, start, limit)
        sign = 1 if match.group(2).lower() in _CREDIT_NOUNS else -1
        name = " ".join(match.group(1).split()).lower()
        sections.append((name, sign, text[start:end.start() if end else limit]))
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

#: Audit B10 (review round 1): the headings that end a credit's printed tail
#: (`_printed_tail`) when the layer prints them on the row's own line: a
#: transaction section's grid header, a non-transaction block's header, and
#: the account's continued heading (the one `_clean` removes).
_TAIL_HEADING_RE = re.compile(
    "|".join((
        _SECTION_RE.pattern,
        _SECTION_END_RE.pattern,
        r"(?:Small Business Checking|Business Checking) - [X0-9]+ \(continued\)",
    )),
    re.IGNORECASE,
)


def _dated_amount_rows(
    body: str, *, sign: int, year: int, printed: str | None = None,
) -> list[Transaction]:
    text = _clean(body)
    dates = list(re.finditer(r"\b" + _DATE + r"\b", text))
    txns: list[Transaction] = []
    # Audit B10 (I05, I14): where in the printed text the next credit is looked
    # for (`_printed_tail`).
    cursor = 0
    source = printed if printed is not None else body
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
        if sign > 0 and amount > 0:
            # Audit B10 (I05, I14): this platform prints a credit's payer AFTER
            # its amount, on the row's own printed line (`ACH Credit $X <payer>
            # <entry> <receiver>`, Falcon's `International IWT $X Falcon
            # Internati Wires <sender>`). A debit keeps its label until the
            # owner admits the debit readings (G7), and so does the $0.00
            # returned ACH the platform prints under Deposits (B10 review,
            # round 1): only a published credit reads its payer.
            tail, cursor = _printed_tail(source, chunk[: amount_match.end()], cursor)
            desc = re.sub(r"\s+", " ", f"{desc} {tail}").strip()
        if _strptime(match.group(), "_dated_amount_rows").year != year:
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


def _printed_tail(source: str, row: str, cursor: int) -> tuple[str, int]:
    """Audit B10 (I05, I14): what the statement printed after a credit's amount
    on the row's own printed line, and where to look for the next row.

    The rows are read on `_clean`'s text, which has collapsed every line break,
    and the line break is what bounds a row's own text on this platform: the
    rows of a page print run together on one line, and the page's furniture (a
    reconciliation form, an error-resolution notice, the next page's
    `<product> - <account> (continued)` heading) follows on lines of its own.
    So the row — its date, label and amount, as `_clean` read them — is found
    again in the printed text `source` (the document, or the block, with its
    line breaks), at or after `cursor` so two identical rows are read in order,
    and its tail is the rest of that printed line up to the next row's date, a
    section trailer, or a heading the layer printed on the same line (B10
    review, round 1: the next section's grid header, a non-transaction block's
    header such as Daily Balances, the account's continued heading). A row not
    found prints no tail (fail closed)."""
    pattern = r"\s+".join(re.escape(token) for token in row.split())
    found = re.compile(pattern).search(source, cursor) if pattern else None
    if found is None:
        return "", cursor
    line = source[found.end():].split("\n", 1)[0]
    for stop_at in (_TAIL_HEADING_RE, re.compile(r"\b" + _DATE + r"\b"), _SECTION_TRAILER_RE):
        stop = stop_at.search(line)
        if stop is not None:
            line = line[: stop.start()]
    return re.sub(r"\s+", " ", line).strip(), found.end()


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
            if _strptime(match.group(2), "_check_rows").year != year:
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


#: THE GRID'S OWN REGION, anchored on the grid's printed COLUMN HEADER and not
#: on the two words that head it.
#:
#: The words `Daily Balances` also open this platform's daily-balance METHOD
#: DISCLOSURE ("To get daily balances, we take the beginning balance ..."),
#: which most of these documents print BEFORE the ledger. A region opened
#: there runs through the whole account block - the summary, the check listing,
#: every section - down to the grid, and `(<date>) (<money>)` then matches
#: things that are not grid cells at all: a check row prints its number, its
#: date and its amount adjacent, which is exactly the shape of a grid cell.
#:
#: Measured over the 106 documents of this family the run of record resolves
#: (`tools/withheldgrids_grid_repeats.py`), the wide region produces 129 cells
#: that give one day a DIFFERENT balance than another cell for the same day -
#: resolved last-wins, silently, on 10 documents including all four of the
#: grid-lift movers. Anchored on the column header, that count is 0 and the
#: resulting grid is IDENTICAL on all 106: the anchor removes only cells that
#: were being overwritten anyway. That is why the contradiction below can be a
#: refusal rather than a crash the archive walks into.
#:
#: The anchor is REQUIRED, not a preference with a fallback: a document that
#: prints no grid must not acquire one from the disclosure paragraph.
_DAILY_BALANCE_GRID = re.compile(
    r"Daily Balances\b[\s\S]{0,40}?Date\s+Amount\b(.*?)"
    r"(?:Overdraft and Returned Item Fees|Service Charge Summary|Thank you|$)",
    re.IGNORECASE | re.DOTALL,
)


def _grid_contradiction() -> ValueError:
    """The refusal for a grid that gives one day two different balances.

    Built like every other refusal in this module (`_strptime`): the message is
    source symbols and a measured fact, never a cell. There is nothing to
    interpolate here at all - which day, and which two balances, are precisely
    the customer's money (W3 §PRIVACY3).
    """
    return ValueError(
        "community_section._daily_balances refused a printed daily-balance "
        "grid: one day is given two different end-of-day balances"
    )


def _daily_balances(block: str) -> dict[str, float]:
    """The printed `Daily Balances` grid, as `{iso date: end-of-day balance}`.

    Read SIGNED. A balance is the one figure this platform prints with a sign
    (see `_SIGNED_MONEY`), and an overdrawn day is printed `-$1,234.56`. The
    unsigned pattern did not merely lose that sign: the minus sits between the
    date and the `$`, so `date whitespace money` did not match at all and the
    DAY was dropped from the grid entirely. Measured over the seven archive
    documents that print this grid, that silently removed 1 to 4 days from
    each of four of them - and a day missing here is a day whose printed
    end-of-day balance never reaches `analysis/adb.py`, which is what left
    those four withheld on `running_balances_support_daily_ledger`.

    A REPEATED DAY IS NOT RESOLVED BY POSITION. `balances[iso] = amount` used
    to make the last cell win, silently, which is the one place this reader
    CHOSE instead of reading (the review's MINOR-8, and the ADB doctrine's
    "read what is printed, refuse on a contradiction"). A grid legitimately
    prints a day twice - continued across a page break - and printing the same
    balance twice is one printed fact printed twice, so it is one cell. Two
    DIFFERENT balances for one day is the document contradicting itself, and
    the answer to a contradiction is a refusal, not the later of the two.
    """
    start = _DAILY_BALANCE_GRID.search(block)
    if not start:
        return {}
    balances: dict[str, float] = {}
    for match in re.finditer(r"(" + _DATE + r")\s+(" + _SIGNED_MONEY + r")", _clean(start.group(1))):
        amount = _balance(match.group(2))
        if amount is None:
            continue
        iso = _iso(match.group(1))
        if iso in balances and balances[iso] != amount:
            raise _grid_contradiction()
        balances[iso] = amount
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
        if _strptime(match.group(1), "_activity_rows").year != year:
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
    A section that prints no trailer is genuinely not checked - absent
    evidence is never read as agreement, and never read as evidence about a
    DIFFERENT section either.
    """
    # A section broken by a page break is reprinted as `<name> (continued)`,
    # and `_sections` - rightly - treats each printed header as its own run.
    # The trailer, though, is printed ONCE, under the last of those runs, and
    # counts the whole section. So rows accumulate across the runs of ONE
    # section and are compared when its trailer appears: comparing a whole
    # section's printed count against the tail end of it would report every
    # page-broken section as a disagreement.
    #
    # The accumulator resets on a change of section NAME. Without that reset
    # the docstring above was false: where a trailer-less section is followed
    # by one that prints a trailer, section A's rows were folded into section
    # B's comparison and the document was refused on evidence about a section
    # the bank had said nothing about. A false REFUSAL rather than a false
    # acceptance, but a fail-closed bug is still a bug, and it made the only
    # per-section oracle unusable on the mixed layouts.
    pending: list[Transaction] = []
    pending_name: str | None = None
    for (name, _sign, body), captured in zip(_sections(block), txns_by_section):
        if pending_name is not None and name != pending_name:
            pending = []
        pending_name = name
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
    #: `None` where the document is on this template but names no issuer. The
    #: schema has always allowed it (`analysis/schema.py`: `bank: str | None`);
    #: what changed is that this reader now uses it instead of refusing a
    #: document whose arithmetic it has fully checked (W3 §JHA J9.2).
    bank: str | None,
    account_name: str,
    account_heading: str | None = None,
    account_number_pattern: str | None = None,
    #: The calling parse attempt's record of the sections it did not publish.
    #: REQUIRED and given no default on purpose: this function is called once
    #: per printed ACCOUNT BLOCK by three entry points, so it is the one place
    #: that can tell a sibling admitted on printed evidence from a sibling
    #: dropped for the absence of rows — and a caller that was allowed to omit
    #: the argument would be allowed to lose that distinction silently, which is
    #: the whole defect L1-C17 exists to close.
    ledger: SectionLedger,
    #: Audit B10 (I05, I14): the document as printed, line breaks kept, when
    #: `markdown` is a block the caller has already passed through `_clean`
    #: (the platform reader's `_account_blocks`): what a credit printed after
    #: its amount is bounded by its printed line (`_printed_tail`).
    printed: str | None = None,
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
    start_year = _strptime(start_date, "_parse_sectioned_statement").year
    end_year = _strptime(end_date, "_parse_sectioned_statement").year
    if start_year != end_year:
        return None

    # Which of the two arrangements this account printed is decided by whether
    # it printed per-direction SECTIONS, not by whether the first reading
    # happened to return something. `Checks Cleared` is printed by both
    # arrangements, so testing "did we capture anything at all" would let a
    # single cheque row mask an entire J-B ledger - which is what it did on
    # eleven archive documents before this was written as a layout choice.
    by_section: list[list[Transaction]] = [
        _dated_amount_rows(body, sign=sign, year=end_year, printed=printed)
        for _name, sign, body in _sections(block)
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
        # ABSENCE IS NOT A GROUND (L1-C17). This line used to be the whole
        # decision: a printed account block that parsed no row was dropped
        # because it parsed no row, and nothing downstream could tell that from
        # a block the document never printed. What may admit it is what the
        # PAPER printed, and this template prints the answer in the summary grid
        # `_summary` has already read fail-closed — its own opening, its own
        # closing, and the four instance figures. The block's text is offered
        # too, so a dormancy declaration in either ratified wording is read
        # here as readily as on the platforms that print one.
        #
        # The verdict is recorded, not acted on: this function reads ONE account
        # block and a document's fate is its caller's to decide.
        ledger.record(
            account_name,
            evidence_class(
                text=block,
                opening=_balance(beginning),
                closing=_balance(ending),
                credit_total=_money(credits),
                debit_total=_money(debits),
                credit_count=credit_count,
                debit_count=debit_count,
            ),
        )
        return None
    txns.sort(key=lambda t: t.date)

    stmt = Statement(
        bank=bank,
        account_name=account_name,
        account_number=None,
        period_start=_iso(start_date),
        period_end=_iso(end_date),
        days_in_period=(_strptime(end_date, "_parse_sectioned_statement").date()
                        - _strptime(start_date, "_parse_sectioned_statement").date()).days + 1,
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
    ledger = SectionLedger()
    stmt = _parse_sectioned_statement(
        markdown,
        bank="Mission Valley Bank",
        account_name="Business Checking",
        account_number_pattern=r"Business Checking\s*-\s*([X0-9]+)",
        ledger=ledger,
    )
    # `ledger.refused` is a section dropped with NO printed evidence of its
    # empty state; the document fails closed. It is checked here rather than
    # assumed unreachable because this entry point reads the whole document as
    # one block, and "the only block" is exactly the account a reader may not
    # dismiss on absence.
    if stmt is None or ledger.refused:
        return None
    publish_omissions(ledger.omissions)
    stmt.holder_name = _mission_valley_holder_name(markdown)
    return stmt


#: Audit round 2, R2-B05 (R04 part 2): Mission Valley's page-1 header line, the holder's name and the page counter
#: ('CONTOSO TRADING INC Page 1 of 4').
_MISSION_VALLEY_HOLDER_LINE = re.compile(r"^(?P<name>\S.*?)\s+Page 1 of \d+$", re.IGNORECASE)


def _mission_valley_holder_name(markdown: str) -> str | None:
    """Audit round 2, R2-B05 (R04 part 2): the holder's name Mission Valley prints before page 1's page counter (the
    mailing line below it can print a location between the name and the street, so it is not read); None without that
    line. `account_name` keeps the product."""
    for line in page_lines(first_page(markdown)):
        match = _MISSION_VALLEY_HOLDER_LINE.match(line)
        if match is not None:
            return holder_from_name(match.group("name"))
    return None


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
    ledger = SectionLedger()
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
            ledger=ledger,
        )
        if stmt is not None and (
            best is None or len(stmt.transactions) > len(best.transactions)
        ):
            best = stmt
    # A heading this document printed whose block parsed no row and printed no
    # evidence of an empty state is an account this reader cannot account for,
    # and the document is refused. (The derived selection above — "the section
    # with the most transactions" — is a DIFFERENT defect, L1-C18, and is not
    # touched here.)
    if best is None or ledger.refused:
        return None
    publish_omissions(ledger.omissions)
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

#: This registration's normalization, registered as registry data so the
#: collapse runs ONCE per document instead of once per marker.
#:
#: It is not a micro-optimisation. `_clean` rewrites the whole document, and a
#: full registry sweep runs every marker of every registration over all 3,500
#: discovery documents; cleaning per marker made this one registration cost
#: about 13% of a sweep whose budget the wave is already close to spending.
#: `make_detector` and `Registration` both take the same callable, so the
#: module's `detect_platform` and the registry's detection stay one
#: computation (tests/test_parser_registry_entries.py asserts exactly that).
detection_text = _clean

PLATFORM_DETECTION_MARKERS = (
    required("summary_grid", lambda t: _PLATFORM_GRID in t.lower()),
    required("period_counts", lambda t: bool(_PERIOD_COUNT_RE.search(t))),
)

detect_platform = make_detector(PLATFORM_DETECTION_MARKERS, detection_text)

#: How this template identifies its issuer: a domain printed beside a label
#: naming it as somewhere to reach the bank, on ONE PRINTED LINE.
#:
#: Two guards, and it is worth being exact about which does the work, because
#: the reviewer of this cell built a document that got `walmart.com` published
#: as the issuer when the comment here overstated the second one:
#:
#: * the SCOPE is the guard. Only the masthead is read (`_masthead_lines`), so
#:   the merchant domains this platform's customers spend money at -
#:   `walmart.com`, `apple.com`, `gosq.com`, which four of the five
#:   issuer-less archive documents really do print - are out of range because
#:   they appear in transaction descriptions.
#: * the LABEL is corroborating, not decisive. `Online` and `Visit` are
#:   ordinary words and can occur in the holder's own address block, which is
#:   inside the masthead.
#:
#: The line restriction is what closes the gap between the two. `_clean`
#: collapses newlines, so a label ending one printed line and an unrelated
#: domain beginning the next became adjacent and matched; the issuer's real
#: contact block prints both on the same line. Matching per printed line costs
#: nothing on the archive and removes the construction.
_ISSUER_RE = re.compile(
    r"(?:Online(?:\s+(?:Access|Banking))?|Web\s?site|Internet\s+Banking"
    r"|Visit(?:\s+us)?(?:\s+at)?)"
    r"[: \t]+((?:www\.)?(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,10})\b",
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


def _masthead_lines(markdown: str) -> list[str]:
    """The statement's top block, ONE PRINTED LINE AT A TIME.

    Deliberately not `_clean`ed: this is the one read in the module that needs
    the printed line breaks intact, because a label and a domain being on the
    same line is part of the evidence (see `_ISSUER_RE`). The page-header
    scrub `_clean` performs is not needed here - a page header cannot be in
    the masthead, which ends before the first account.

    NOTE FOR THE NEXT EDITOR OF THIS SCOPE (D5). The masthead is the TOP of
    the document, so it is also where the OCR layer's
    `<!-- source: <filename> ... -->` comment sits. A filename is
    operator-supplied metadata and on this archive a folder-derived guess, and
    `_ISSUER_RE` would happily read one: a file called
    `Visit bankname.com statement.pdf` puts a label and a domain on one line
    inside this scope. Nothing is wrong today, because every production path
    reaches a parser through `analysis.pipeline.analyze_markdown`, which
    applies `parser_registry.admissible_text` at its single parse seam (W3
    FILENAME-BOUNDARY) - the comment is gone before this function ever sees
    it. What that means in practice: this function's safety depends on a
    guarantee made ELSEWHERE, so a direct call to
    `parse_community_section_statement` with raw markdown - a test, a script,
    a future caller that bypasses the pipeline - is outside it. Widening the
    masthead scope, or relaxing `_ISSUER_RE`'s label, widens that exposure
    too; strip the comment here as well if this ever grows a direct caller.
    """
    end = _MASTHEAD_END_RE.search(markdown)
    return (markdown[:end.start()] if end else markdown).splitlines()


def _masthead_domains(markdown: str) -> set[str]:
    """Every labelled domain the masthead prints, normalised.

    Case and the `www.` prefix are normalised away because a domain is
    case-insensitive and `www.` is not part of the name - the same issuer
    prints `Website Columbiabankonline.com` on one statement and
    `Online www.columbiabankonline.com` on another. Nothing else is
    transformed: the published string is the name the bank printed.

    The SET is returned rather than a single answer because its three sizes
    are three different facts about the document, and only the caller can
    weigh them - see `parse_community_section_statement`.
    """
    return {
        match.group(1).lower().removeprefix("www.")
        for line in _masthead_lines(markdown)
        for match in _ISSUER_RE.finditer(line)
    }


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

    Declines - rather than guesses - in two named situations, each of which
    is a fact about the document and not a gap in this reader:

    * the masthead names MORE THAN ONE labelled domain - see below;
    * more than one of its accounts has activity. The `Statement` schema holds
      ONE account (MASTER_PLAN L-1), and this template is used by credit unions
      that print a membership share, a checking account and a savings account
      side by side. Publishing the busiest one silently would report a subset
      of the customer's money as though it were all of it. Where exactly one
      account posted anything AND every other block printed evidence of its own
      empty state (L1-C17), the others are dormant bookends and reading that one
      is reading the document. A block that posted nothing and declared nothing
      is not a bookend — it is an account this reader cannot account for, and
      since batch 9 it refuses the document rather than disappearing from it;

    and refuses through `_parse_sectioned_statement`'s own gate whenever the
    ledger does not reproduce every figure the summary grid printed.

    **The issuer is a separate fact from the ledger** (Gustavo's ruling,
    2026-08-14, W3 §JHA J9.2). The three sizes of `_masthead_domains` are three
    different findings and are answered differently:

    ``1``
        the document names its issuer; that name is published, exactly as
        before. 110 archive documents, unmoved.
    ``0``
        the document names NO issuer. The template is recognised and the
        ledger closes against every printed figure, so the statement is
        published with ``bank=None`` - an honest absence rather than a refusal
        of a document we did in fact read. `Statement.bank` is `str | None`
        and every consumer already renders the absence (the dashboard shows
        "Unknown bank", the report titles itself "Bank Statement"). What is
        NOT done here is inference: not from the filename, not from the
        folder, not from template similarity, not from a merchant domain in a
        transaction description - four of these five documents really do print
        `walmart.com` and the like, and "the first domain in the document"
        would publish a merchant as the bank. 5 archive documents.
    ``2 or more``
        the document contradicts ITSELF about its issuer, which is not the
        same finding as printing nothing. An unknown issuer is a gap in the
        document; two labelled domains in the masthead is a gap in our reading
        of it - the most likely cause is that `_MASTHEAD_END_RE` did not find
        this layout's first account and the scope ran on into the fine print.
        Publishing `bank=None` would file our own defect as the document's
        honest silence. No archive document is in this class (measured: 0 of
        115), so there is nothing here to prove a publication rule against,
        and fail-closed is what an unproven class gets.
    """
    if not detect_platform(markdown).claims:
        return None
    domains = _masthead_domains(markdown)
    if len(domains) > 1:
        return None
    issuer = domains.pop() if domains else None

    parsed: list[Statement] = []
    ledger = SectionLedger()
    for product, number, block in _account_blocks(markdown):
        stmt = _parse_sectioned_statement(
            block, bank=issuer, account_name=product, account_number_pattern=None,
            ledger=ledger, printed=markdown,
        )
        if stmt is not None and stmt.transactions:
            stmt.account_number = number
            parsed.append(stmt)

    # "Where exactly one account posted anything the others are dormant
    # bookends" — the docstring above said that, and until batch 9 nothing
    # checked it. `ledger.refused` is the check: a bookend is an account the
    # PAPER declared empty, and a block that declared nothing is not one.
    if len(parsed) != 1 or ledger.refused:
        return None
    publish_omissions(ledger.omissions)
    return parsed[0]
