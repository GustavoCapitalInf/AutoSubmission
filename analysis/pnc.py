"""PNC — one reader, four printed product skins.

The bank prints the same statement four ways. `Business Checking` and
`Treasury Enterprise Plan` are the same page furniture with a different product
line; `PNC Core Commercial Checking` moves the Activity Detail out from under an
`Activity Detail` heading and restates each section's item count and total on
the section's own heading line; the consumer `Virtual Wallet With Performance
Spend` prints the same restatement as a sentence (`There were <n> ... totaling
$x.`) and itemizes directly under the two direction headings instead of under
sub-sections. What does NOT change across the four is the evidence this reader
stands on, and that is why they are one reader rather than four:

* a period sentence, `For the [Pp]eriod mm/dd/yyyy to mm/dd/yyyy`;
* a `Balance Summary` grid whose four columns are beginning, credits, debits
  and ending, printed as ONE physical line;
* dated rows in the `mm/dd <amount> <description>` column group (and cheques in
  their own `mm/dd <number> <amount>` group);
* the bank's own INDEX of what it itemized — either a `Description Items
  Amount` table with a per-category item count and total, or the same two
  figures restated on each section's heading line;
* an end-of-day balance grid (`Daily Balance`, `Daily Balance Detail` or
  `Ledger Balance`).

The last two are identities, and this module treats them as such: a document
whose rows do not reproduce the bank's own index of them, or whose ledger does
not reproduce the bank's own end-of-day balances, is DECLINED rather than
published short. Measured over the 45 archive documents this reader claimed
before the widening, both identities hold on all 41 it published and fail on
all 4 it withheld — so neither gate costs a document that was right, and both
refuse every document that was not.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import iso_from_month_day_strict
from .holder_name import first_page, holder_from_name, page_lines
from .money import parse_money, read_money
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction

#: The four product lines PNC prints as the statement's own title. The list is
#: doing two jobs deliberately: it is the detection marker for "this is a PNC
#: statement of a product this reader can read", and it is where
#: `account_name` comes from. Keeping them one list is what stops the reader
#: claiming a fifth skin it cannot name — a Virtual Wallet variant this list
#: does not carry is left unclaimed rather than published under a guess.
_PRODUCTS = (
    "PNC Core Commercial Checking",
    "Virtual Wallet With Performance Spend",
    "Treasury Enterprise Plan",
    "Business Checking",
)

#: The Activity Detail sections that print the `Date posted / Amount /
#: Transaction description / Reference number` column group, and the direction
#: each one is printed under.
#:
#: PNC prints its own index of this list — see `_printed_index`. This dict must
#: cover it, because the list is doing two jobs at once: it is also the list of
#: SECTION BOUNDARIES, so a section missing from it is not merely unread — it
#: is swallowed by the section printed above it, taking that section's sign and
#: gluing its own heading and column header onto the last description.
#:
#: Every name here prints on ONE side of the index. The four that print on BOTH
#: sides are in `_UNSIGNED_SECTIONS` and take their direction from the group
#: heading above them instead, because a name that is a credit category and a
#: debit category cannot have a sign of its own.
_SECTION_SIGNS = {
    "Deposits": 1,
    "ATM Deposits and Additions": 1,
    "ACH Additions": 1,
    "ACH Credits": 1,
    "National Lockbox": 1,
    "Funds Transfer In": 1,
    "Funds Transfers In": 1,
    "Other Additions": 1,
    "Other Credits": 1,
    "Fee Refunds": 1,
    "Debit Card Purchases": -1,
    "POS Purchases": -1,
    "ATM/Misc. Debit Card Transactions": -1,
    "Banking/Debit Card Withdrawals and Purchases": -1,
    "Online and Electronic Banking Deductions": -1,
    "ACH Deductions": -1,
    "ACH Debits": -1,
    "Funds Transfer Out": -1,
    "Funds Transfers Out": -1,
    "Returned Items": -1,
    "Service Charges and Fees": -1,
    "Other Deductions": -1,
    "Other Debits": -1,
}
#: The categories the commercial index prints on BOTH sides. `Investments 0
#: .00` stands under `Deposits and Other Credits` and again under `Checks and
#: Other Debits` on the same page, so the NAME cannot carry the direction and
#: guessing one would sign a whole section wrongly the first time a bank
#: itemizes it. They take the sign of the group heading they are printed
#: under, and a document that itemizes one with no group heading in force is
#: declined.
_UNSIGNED_SECTIONS = frozenset({
    "Trade Services", "Investments", "Zero Balance Transfers", "Adjustments",
})
#: The two umbrella headings of each direction, in the two spellings PNC uses
#: (`Additions/Deductions` on the retail and treasury skins, `Credits/Debits`
#: on the commercial one). They close whatever section stands above them and
#: they set the direction for the sections below them. On the consumer skin
#: they also ITEMIZE — the rows are printed directly under the umbrella with no
#: sub-section at all — so a group heading is a section too, with its own sign.
_GROUP_SIGNS = {
    "Deposits and Other Additions": 1,
    "Deposits and Other Credits": 1,
    "Checks and Other Deductions": -1,
    "Checks and Other Debits": -1,
}
#: Cheques are itemized in their own section under a different column group
#: (`Date posted / Check number / Amount / Reference number`), so the heading is
#: a section boundary like the others but its rows are read by `_parse_checks`.
_CHECKS_HEADING = "Checks and Substitute Checks"
#: One section, two printed spellings. The index says `Checks` where the detail
#: heading says `Checks and Substitute Checks`, and the wire sections are
#: printed in the plural in the index and in the singular in one of the two
#: detail headings — `Funds Transfers In` indexing `Funds Transfer In`, while
#: the outgoing side prints the plural in BOTH places. So the table is applied
#: to EVERY section name, from the index and from the detail alike, rather than
#: mapping one side onto the other: two names of one section become one key
#: wherever they are read, which is the only form of the table that cannot go
#: stale when a skin spells a heading the other way. A spelling table, not a
#: direction one; every entry is a pair of names printed on one document's page.
_SECTION_ALIASES = {
    "Checks": _CHECKS_HEADING,
    "Funds Transfers In": "Funds Transfer In",
    "Funds Transfers Out": "Funds Transfer Out",
}
#: The order the ledger is PUBLISHED in. It is the reader's own section order
#: rather than the printed one, and deliberately so: widening the section list
#: must not be able to reorder a ledger that was already published, and nothing
#: downstream reads the published order (`analysis/adb.py` sorts by date,
#: `analysis/reconcile.py` sums). Every new name was inserted beside its
#: neighbour of the same direction, so the relative order of the names that were
#: here before the widening is unchanged.
_EMISSION_ORDER = (
    *_SECTION_SIGNS,
    *sorted(_UNSIGNED_SECTIONS),
    *_GROUP_SIGNS,
    _CHECKS_HEADING,
)
#: `04/21 1100 * 50.28` — date, check number, optional sequence-gap marker,
#: amount. Several column groups are printed per physical line. The Reference
#: number that follows carries no decimal point, so it cannot be read as money.
_CHECK_ROW_RE = re.compile(r"(\d{2}/\d{2})\s+(\d+)\s*(\*?)\s+(\d[\d,]*\.\d{2}|\.\d{2})")
#: The space thousands separators `analysis/money.py` already surveys — its
#: format axes list `1 234.56` (:17) and `EITHER_MINUS_SPACED` (:214) exists to
#: strip them — written out as the ASCII space plus the two no-break spaces a
#: PDF text layer emits in its place.
_THOUSANDS_SPACE = "\u0020\u00a0\u202f"
#: A C0 control byte is not printed content. The flattening of some PNC prints
#: emits one where the column gap between a section's name and its `- continued`
#: marker belongs (`Other Additions <NUL>- continued`), and a heading grammar
#: written with `\s` — which does not match a control byte — then fails to
#: recognise the continuation heading and silently drops every page of that
#: section after the first. Substituting a SPACE puts the column gap back, and
#: every other character keeps its position, so nothing else moves.
#:
#: A SPACE IS NOT NEUTRAL HERE, and an earlier version of this comment claimed
#: it was ("a space can only separate two tokens, never join them"). It can
#: join them: this module reads a space between digit groups as a THOUSANDS
#: SEPARATOR (`_THOUSANDS_SPACE`), so `1<NUL>234.56` would normalise to
#: `1 234.56` and be read as one figure a thousand times the tail — a figure
#: the paper may never have printed. That is the shape the repair doctrine is
#: about, and it is the one direction the substitution must not be allowed to
#: take. `_DIGIT_ADJACENT_CONTROL` below is the guard, and it fails CLOSED.
#: The class is spelled ONCE and both patterns are built from it, so the two
#: can never drift — and so neither re-spells a byte range beside a `\d`, where
#: the layer-wide calendar scan reads the `00` of `\x00` as a pinned day.
_CONTROL_CLASS = r"[\x00-\x08\x0b\x0c\x0e-\x1f]"
_CONTROL_BYTE = re.compile(_CONTROL_CLASS)
#: A control byte standing next to a digit, on either side. Where one does, the
#: document is DECLINED rather than normalised.
#:
#: Refusing rather than splitting, and why: the two readings of
#: `1<NUL>234.56` are one grouped figure and two separate tokens, and the text
#: layer carries no evidence for either. Joining invents a figure; splitting
#: publishes the `234.56` tail of a figure that may have been a thousand times
#: larger, which is the silent truncation `_SUMMARY_MONEY_RE`'s boundary guard
#: exists to make impossible. Neither reading is available, so the document is
#: not read.
#:
#: Measured over this card's 58-document population: 10 control bytes, every
#: one a NUL, and **0 of them adjacent to a digit** — so the guard costs no
#: document today and the continuation-heading repair that earns the withheld
#: mover is untouched. It is a bound on what the substitution may do, written
#: before the archive prints the shape rather than after.
_DIGIT_ADJACENT_CONTROL = re.compile(
    rf"\d{_CONTROL_CLASS}|{_CONTROL_CLASS}\d")

#: A Balance Summary figure. PNC drops the leading zero on a sub-dollar amount,
#: so a balance of eighty-seven cents is printed `.87` — and a `\b` before the
#: point does not match after a space, which is how the old pattern skipped such
#: a figure and then read the NEXT one (the average ledger balance) as the
#: closing balance. The boundary here is "not preceded by a digit, comma or
#: point", which is a statement about the grid rather than about word
#: characters.
#:
#: The body is a FLATTENED grid, so one space character does two jobs: it
#: separates the columns, and in a figure printed `1 000.00` it groups the
#: thousands. What tells the two apart is not the character but what stands to
#: its left — a complete `.dd` figure ENDS a column, so a space after one is a
#: column gap; anywhere else a digit run adjoining a `<space><3 digits>` group
#: is the head of one figure rather than the whole of two.
#:
#: Both halves of that rule are load-bearing, and they fail in opposite
#: directions. Without the grouped integer part `1 000.00` cannot match whole.
#: Without the boundary guard the match that DOES fit — the `000.00` tail — is
#: a silent truncation of it, and a truncated summary is not caught downstream:
#: all four columns truncate together, so every printed identity still closes
#: and the statement publishes approved with each figure wrong by the same
#: thousand. The guard makes the fragment unmatchable, so a figure this parser
#: cannot read whole is not read as a smaller one. What turns that refusal into
#: a REFUSAL rather than a shift is `_grid_row`: the summary is read from the
#: grid's own row, so a missing figure leaves that row a column short instead
#: of moving the reader on to the next four figures printed below it.
_SUMMARY_MONEY_RE = re.compile(
    rf"(?<![\d.,])"
    rf"(?:(?<=\.\d\d[{_THOUSANDS_SPACE}])|(?<![\d][{_THOUSANDS_SPACE}]))"
    rf"(?:\d[\d,]*(?:[{_THOUSANDS_SPACE}]\d{{3}})*)?\.\d{{2}}-?"
)
#: Any printed figure, INCLUDING the truncated fragments the pattern above
#: refuses. Used only to count figures on a line — to find the grid's row —
#: and never to read a value, so its tolerance costs nothing.
_ANY_FIGURE_RE = re.compile(r"(?<![\d.,])(?:\d[\d,]*)?\.\d{2}-?")

#: The same printed figure where a label rather than a column position finds it,
#: so the two readings of the Balance Summary block cannot disagree about what a
#: figure is. Not optional-integer: these lines print a labelled balance.
_LABELLED_FIGURE = rf"\d[\d,]*(?:[{_THOUSANDS_SPACE}]\d{{3}})*\.\d{{2}}"

#: Horizontal whitespace. A heading occupies ONE printed line, so every part of
#: the heading grammar below is written with this rather than `\s`, which would
#: let a heading's tail run onto the next line and take a row with it.
_H = r"[^\S\n]"
#: PNC prints a section's continuation heading at the top of each further page.
_CONTINUED = rf"(?:{_H}*-{_H}*continued|{_H}+continued on next page)?"
#: The two forms in which a section restates its OWN item count and total on
#: its heading line: `<n> transactions for a total of $x` on the commercial and
#: treasury skins, `There were <n> ... totaling $x.` on the consumer one. A
#: section may print several of the sentence form (the consumer skin's
#: `Banking/Debit Card Withdrawals and Purchases` prints three, one per
#: category it merges), so the tail admits a run of them.
_COUNT_RESTATEMENT = rf"{_H}+\d[\d,]*{_H}+transactions?{_H}+for a total of{_H}+\$[\d,]*\.\d{{2}}"
_PROSE_RESTATEMENT = (rf"{_H}+There were{_H}+\d[\d,]*{_H}+[^$\n]*?totaling{_H}+"
                      rf"\$[\d,]*\.\d{{2}}\.?")
#: The column header PNC prints inline after a consumer-skin heading.
_COLUMN_HEADER = rf"(?:{_H}+Date(?:{_H}+posted)?{_H}+Amount{_H}+Description)?"
#: PNC prints the cheque section's gap-marker footnote on the same line as its
#: heading, so that suffix is furniture rather than a different heading.
_GAP_FOOTNOTE = rf"(?:{_H}*\*{_H}*Gap in check sequence)?"
#: A row of the described column group, used as a LOOKAHEAD: on the consumer
#: skin the first row of a section is printed on the heading's own line, so the
#: heading ends either at the end of its line or where its first row begins.
#: Either way a heading still owns its line — a row's description can never
#: open a section, because the name has to stand at the START of a line.
_ROW_AHEAD = r"(?=\s+\d{2}/\d{2}\s+(?:\d[\d,]*\.\d{2}|\.\d{2})\s)"

_ALL_SECTION_NAMES = sorted(
    {*_SECTION_SIGNS, *_UNSIGNED_SECTIONS, *_GROUP_SIGNS, _CHECKS_HEADING},
    key=len, reverse=True)
_HEADING_LINE = re.compile(
    r"(?im)^" + _H + r"*(?P<name>"
    + "|".join(re.escape(name) for name in _ALL_SECTION_NAMES) + r")"
    + _CONTINUED
    + rf"(?:{_COUNT_RESTATEMENT}|{_PROSE_RESTATEMENT})*"
    + _COLUMN_HEADER + _GAP_FOOTNOTE
    + rf"(?:{_H}*$|{_ROW_AHEAD})"
)
#: The first word of the column-header block a section prints over its rows.
#: PNC breaks that block across lines in several ways (`Date posted` alone, or
#: `Date` and `posted` on separate lines, or the whole run and the first row on
#: ONE line), so the test is the first token rather than the whole shape.
_COLUMN_TOKEN = re.compile(
    r"(?i)^[ \t]*(?:date|posted|amount|transaction|description|reference|number|check)\b")
#: The end-of-day balance ladder, under each of the three names PNC gives it.
_GRID_HEADING = re.compile(
    r"(?im)^" + _H + r"*(?P<name>Daily Balance Detail|Daily Balance|Ledger Balance)"
    + _CONTINUED + _H + r"*$")
#: A grid cell: a day and its end-of-day balance, `04/01 1,000.00`. An
#: overdrawn day is printed with a TRAILING minus, `04/03 1,000.00-`, which is
#: the reason this pattern captures the sign separately instead of letting the
#: money grammar decide.
_GRID_CELL = re.compile(r"(\d{2}/\d{2})\s+(\d[\d,]*\.\d{2}|\.\d{2})(-?)")
#: A line that closes whatever block stands above it without opening a section:
#: the service-detail appendix, the page break, and the statement footer.
_BLOCK_CLOSER = re.compile(
    r"(?im)^" + _H + r"*(?:Detail of Services Used\b|Activity Detail" + _H + r"*$"
    r"|---" + _H + r"*Page\b|Member FDIC\b)")
#: The bank's index of the sections it itemized, and the per-direction `Total`
#: row that closes each half of it.
_INDEX_TABLE = re.compile(r"Description\s+Items\s+Amount(?P<body>.*?)"
                          r"(?=Description\s+Items\s+Amount|\n\s*\n|$)", re.DOTALL)
_INDEX_ROW = re.compile(r"([A-Z][A-Za-z/.&' ]+?)\s+(\d+)\s+(\d[\d,]*\.\d{2}|\.\d{2})")
#: The same two figures where a section restates them on its own heading line.
_HEADING_COUNT_RE = re.compile(r"(\d[\d,]*)\s+transactions?\s+for a total of\s+\$([\d,]*\.\d{2})")
_HEADING_PROSE_RE = re.compile(r"There were\s+(\d[\d,]*)\s+[^$\n]*?totaling\s+\$([\d,]*\.\d{2})")
#: The block the Balance Summary grid is printed in ends where the next printed
#: block begins. Naming them all — rather than the two the retail skin happens
#: to print next — is what lets the grid be bounded on every skin, including the
#: commercial one, which prints neither `Activity Detail` nor an overdraft
#: summary anywhere in the document.
_SUMMARY_BLOCK_END = re.compile(
    r"(?im)^" + _H + r"*(?:Overdraft and Returned Item Fee Summary|Transaction Summary"
    r"|Interest Summary|Activity Detail|Description\s+Items\s+Amount"
    r"|Daily Balance|Ledger Balance|"
    + "|".join(re.escape(name) for name in sorted(_GROUP_SIGNS, key=len, reverse=True))
    + r")")

#: Two figures agree when they agree to the cent.
_TOLERANCE = 0.005


def _money(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    # A figure read whole from the grid can carry the space thousands separator
    # the patterns above admit. `parse_money` removes `$`, `,` and `*` but not
    # spaces, and it SEARCHES rather than anchors, so it would read `1 000.00`
    # as one dollar — the same truncation by a different route.
    for space in _THOUSANDS_SPACE:
        value = value.replace(space, "")
    if value.startswith("."):
        value = "0" + value
    return parse_money(value)


def _period(markdown: str) -> tuple[str, str] | None:
    """`For the Period` on the business and treasury skins, `For the period` on
    the commercial and consumer ones — the same printed sentence, two casings."""
    m = re.search(
        r"For the [Pp]eriod\s+(\d{2})/(\d{2})/(\d{4})\s+to\s+(\d{2})/(\d{2})/(\d{4})",
        markdown)
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    try:
        return (
            date(int(sy), int(sm), int(sd)).isoformat(),
            date(int(ey), int(em), int(ed)).isoformat(),
        )
    except ValueError:
        return None


def _grid_row(body: str) -> str | None:
    """The Balance Summary's four-column row, which is one printed line.

    The block between the `Balance Summary` heading and whichever block is
    printed next is, on many statements, far more than the grid: the
    `Description Items Amount` index and the entire daily-balance ladder can be
    inside it. Scanning all of that for figures and taking the first four worked
    only because the grid is printed first — and it left the reader standing
    over a region of numbers that are not summary columns at all, where an item
    count beside an amount (`Debit Card Purchases 7 202.05`) or a date beside a
    ledger balance (`02/11 953.78`) reads as one figure.

    So the grid is bounded to the line that prints it. On every Balance Summary
    block in the archive the four columns are the first four figures of a single
    physical line, and nothing below that line is read.

    The row is LOCATED by a permissive figure count and READ with
    `_SUMMARY_MONEY_RE`. That split is the whole point: a figure the strict
    pattern refuses still counts towards finding the row, so the row is found
    and comes up a column short and the statement fails closed. Locating by the
    strict count instead would skip the grid and settle on the next line with
    four figures in it — a daily-balance ladder read as a summary, which is a
    silent approval standing exactly where the refusal belongs.
    """
    for line in body.splitlines():
        if len(_ANY_FIGURE_RE.findall(line)) >= 4:
            return line
    return None


def _summary_amounts(text: str) -> tuple[float, float, float, float] | None:
    summary = re.search(r"Balance Summary(?P<body>.*)", text, re.DOTALL | re.IGNORECASE)
    if not summary:
        return None
    body = summary.group("body")
    end = _SUMMARY_BLOCK_END.search(body)
    if end:
        body = body[: end.start()]
    row = _grid_row(body)
    if row is None:
        return None
    amounts = _SUMMARY_MONEY_RE.findall(row)
    if len(amounts) < 4:
        return None
    values = [_money(amount) for amount in amounts[:4]]
    if any(value is None for value in values):
        return None
    return values[0], abs(values[1]), abs(values[2]), values[3]  # type: ignore[return-value]


def _average_balance(text: str) -> tuple[float, str] | None:
    """The bank's own average balance, and the label it printed it under.

    The average is printed in the same Balance Summary block and in the same
    figure format as the four columns above it, so it reads the same figure
    grammar. Reading it with a narrower one would mean a document whose columns
    this parser now reads whole could still publish a truncated average beside
    them. The consumer skin labels it `Average monthly balance`; the others
    label it `Average ledger`. Both are the bank's stated average, and the
    label travels with the figure so a reader downstream can tell which.
    """
    for label, pattern in (
        ("Average ledger",
         rf"Average ledger\s+Average collected\s+balance\s+({_LABELLED_FIGURE})"),
        ("Average ledger", rf"Average ledger.*?balance\s+({_LABELLED_FIGURE})"),
        ("Average monthly balance",
         rf"Average monthly balance.*?\s({_LABELLED_FIGURE})"),
    ):
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            value = read_money(m.group(1), _money)
            if value is not None:
                return abs(value), label
    return None


def _product(markdown: str) -> str | None:
    """The product line the statement titles itself with.

    The EARLIEST of the printed product names, because the title is printed
    first: a treasury statement also prints `Business Checking` further down,
    in the relationship-pricing table that names the other accounts the balance
    requirement was met against, and taking any other member of the list would
    publish that account's product as this account's. Two archive documents
    were published under the wrong product name for exactly that reason before
    this read existed.
    """
    found = [(markdown.find(product), product)
             for product in _PRODUCTS if product in markdown]
    return min(found)[1] if found else None


#: Audit B9 (I13): the line PNC titles its account summary with: the holder's name in capitals, the product in title
#: case, then 'Summary Account number'.
_SUMMARY_TITLE = re.compile(r"^(?P<line>[^\n]*?)Summary Account number", re.MULTILINE)


#: Audit B9 review round 1 (I13): the words a PNC product prints (its product lines' words and the product words a
#: summary title adds to them), which name no holder.
_PRODUCT_WORDS = frozenset(word.upper() for product in _PRODUCTS for word in product.split()) | frozenset({
    "PNC", "ANALYSIS", "PLUS", "ACCOUNT", "SAVINGS", "INTEREST", "MONEY", "MARKET", "PREMIER", "SELECT",
})


def _without_product(words: list[str]) -> list[str]:
    """Audit B9 review round 1 (I13): the summary title's capitals without a product printed in capitals after the
    name ('CONTOSO TRADING LLC TREASURY ENTERPRISE PLAN'); none at all when every word is a product's word."""
    if all(word.upper() in _PRODUCT_WORDS for word in words):
        return []
    for product in _PRODUCTS:
        tail = product.upper().split()
        if len(words) > len(tail) and [word.upper() for word in words[-len(tail):]] == tail:
            return words[:-len(tail)]
    return words


#: Audit round 2, R2-B05 (R04 part 2): page 1's block fallback: the enclosure count line, which the holder's mailing
#: block follows, the online-banking panel PNC prints beside it (run onto the name line by a reading), and a street line
#: (a house number or a post-office box) under the name.
_ENCLOSURES_LINE = re.compile(r"^Number of enclosures:\s*\d+$", re.IGNORECASE)
_ONLINE_BANKING_PANEL = re.compile(r"\s+PNC Online Banking\b.*$", re.IGNORECASE)
_STREET_LINE = re.compile(r"^(?:\d+[A-Z]?|P\.? ?O\.? BOX)\b", re.IGNORECASE)


def _holder_name(markdown: str) -> str | None:
    """Audit B9 (I13): the holder's name before the product on PNC's summary title line, or (audit round 2, R2-B05: R04
    part 2) where that reads none, page 1's mailing block (_mailing_block_holder_name)."""
    return _summary_title_holder_name(markdown) or _mailing_block_holder_name(markdown)


def _mailing_block_holder_name(markdown: str) -> str | None:
    """Audit round 2, R2-B05 (R04 part 2): page 1's block fallback: the line after the enclosure count, without the
    online-banking panel run onto it, read when the next line opens on a street; None otherwise. A product printed in
    capitals is never the name (_without_product)."""
    lines = page_lines(first_page(markdown))
    for index, line in enumerate(lines[:-2]):
        if not _ENCLOSURES_LINE.match(line):
            continue
        name = _ONLINE_BANKING_PANEL.sub("", lines[index + 1])
        words = _without_product(name.split())
        if not words or not _STREET_LINE.match(lines[index + 2]):
            return None
        return holder_from_name(" ".join(words))
    return None


def _summary_title_holder_name(markdown: str) -> str | None:
    """Audit B9 (I13): the holder's name before the product on PNC's summary title line: its leading words that print no
    lower-case letter, without a designation or a contact after the name. None when the line prints no name (only the
    product). Review round 1: a product printed in capitals is never the name (_without_product)."""
    for match in _SUMMARY_TITLE.finditer(markdown):
        words: list[str] = []
        for word in match.group("line").split():
            if any(character.islower() for character in word):
                break
            words.append(word)
        words = _without_product(words)
        if words:
            return holder_from_name(" ".join(words))
    return None


def _opens_a_section(text: str, match: "re.Match[str]") -> bool:
    """Whether a line SHAPED like a heading is one, from its own context.

    A heading's name is also ordinary English, and a description that wraps
    onto its own line can be exactly a section's name — at which point a
    grammar that reads any such line as a heading opens a section that is not
    there, cuts the row's description at the wrap, and hands the remainder to a
    section the bank never printed. Neither printed identity can see it: the
    row is still booked, on its own day, for its own amount, so the count and
    the total are unchanged. Only the description moves, which is why the rule
    is here rather than downstream.

    So a heading has to carry evidence that it IS one. Either it says so on its
    own line — a continuation marker, its printed item count and total, or the
    inline column header (with or without its first row after it) — or the line
    under it begins the section's column-header block, or is itself a heading
    (a direction umbrella standing over its first sub-section).

    A row printed under the line is deliberately NOT a qualifier, and that is
    measured rather than assumed: over this card's 58-document population
    **not one** of the 1,157 heading matches needs it (686 qualify on their own
    line, 365 have a column header under them, 106 another heading, none left
    over). Admitting it would have cost the whole rule — a wrapped description
    is followed by the next row more often than by anything else.

    What it does NOT reach, said rather than left to be found: a wrapped
    description line that is exactly a section name AND is immediately followed
    by a real heading still opens a section. That needs the row grammar's own
    span, not the line's neighbours.
    """
    name = match.group("name")
    whole = match.group(0)
    if whole[whole.index(name) + len(name):].strip():
        return True
    for line in text[match.end():].splitlines():
        if not line.strip():
            continue
        return bool(_COLUMN_TOKEN.match(line) or _HEADING_LINE.match(line))
    return False


def _activity_body(markdown: str) -> str:
    """The region the itemized sections are printed in.

    Three skins print an `Activity Detail` heading over it. The commercial skin
    prints none: its detail begins at the first direction group heading printed
    AFTER the ledger grid, the two group headings above that being the column
    headers of the index table rather than the detail's own umbrellas. Bounding
    the region matters in both directions — the index table and the summary
    labels use the same words as the group headings, and reading them as
    section openers would put the index's own figures in the ledger.
    """
    anchor = re.search(r"(?im)^" + _H + r"*Activity Detail" + _H + r"*$", markdown)
    if anchor is None:
        grid = _GRID_HEADING.search(markdown)
        if grid is None:
            return ""
        group = _HEADING_LINE.search(markdown, grid.end())
        while group is not None and not (group.group("name") in _GROUP_SIGNS
                                         and _opens_a_section(markdown, group)):
            group = _HEADING_LINE.search(markdown, group.end())
        if group is None:
            return ""
        start = group.start()
    else:
        start = anchor.end()
    body = markdown[start:]
    tail = re.search(r"(?im)^" + _H + r"*(?:Detail of Services Used|Member FDIC)\b", body)
    return body[: tail.start()] if tail else body


def _posts(amount: float) -> bool:
    """Whether an Activity Detail row is a POSTING rather than furniture.

    A posting is a movement of money, and the Activity Detail also carries
    dated lines that state a fact about the period instead of moving anything —
    an overdraft-fee notice, a period marker. Those print in the same column
    group as a posting and the row grammar cannot tell them apart: PNC prints
    genuine sub-dollar amounts with the leading zero dropped (`02/02 .82 ACH
    Credit ...` — 54 such postings in the archive), so `.dd` has to stay
    readable, and a `.00` line then satisfies the row pattern exactly as a
    posting does.

    What separates them is the figure itself: a row that moves nothing is not a
    posting. That is also the only reading a downstream check could ever
    recover, because such a row is invisible to every identity the fail-closed
    gate applies — it adds zero to both the ledger sum and the section total,
    so a fabricated one leaves beginning + activity == ending intact. PNC
    discloses no per-direction count oracle (`analysis/count_semantics.py`
    SECTION_LEVEL_ORACLES), so the row count cannot catch it either. The
    refusal has to happen here or nowhere.

    Structural, not a vocabulary: nothing here reads the description, so a
    furniture wording this parser has never seen is refused on the same
    grounds, and a real posting is never refused for how it is worded.
    """
    return amount != 0


def _rows_of(chunk: str, *, year: int, sign: int) -> list[Transaction]:
    chunk = re.sub(
        r"(?im)^\s*(?:Date posted|Date|Amount|Transaction description|Description"
        r"|Reference|number)\s*$", " ", chunk)
    chunk = re.sub(r"\s+", " ", chunk).strip()
    txns: list[Transaction] = []
    rows = re.split(r"\s+(?=\d{2}/\d{2}\s+(?:\d[\d,]*\.\d{2}|\.\d{2})\s)", chunk)
    for row in rows:
        m = re.match(r"^(\d{2}/\d{2})\s+(\d[\d,]*\.\d{2}|\.\d{2})\s+(.+?)\s*$", row)
        if not m:
            continue
        txn_date = iso_from_month_day_strict(m.group(1), year)
        amount = _money(m.group(2))
        if txn_date is None or amount is None or not _posts(amount):
            continue
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=txn_date,
            description=re.sub(r"\s+", " ", m.group(3)).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def _check_rows(chunk: str, *, year: int) -> list[Transaction]:
    """The `Checks and Substitute Checks` section, which prints its own column
    group: `Date posted | Check number | Amount | Reference number`."""
    chunk = re.sub(
        r"(?im)^\s*(?:Date posted|Date|Check number|Check|Amount|Transaction"
        r"|Reference|number|posted)\s*$", " ", chunk)
    chunk = re.sub(r"\s+", " ", chunk).strip()
    txns: list[Transaction] = []
    for mmdd, number, marker, amount in _CHECK_ROW_RE.findall(chunk):
        txn_date = iso_from_month_day_strict(mmdd, year)
        value = _money(amount)
        if txn_date is None or value is None or not _posts(value):
            continue
        txns.append(Transaction(
            date=txn_date,
            description=f"Check {number}{marker}",
            amount=round(-abs(value), 2),
            direction="debit",
            running_balance=None,
        ))
    return txns


def _captured_sections(markdown: str, *, year: int) -> dict[str, list[Transaction]] | None:
    """Every itemized section of the Activity Detail, by the name it is printed
    under, in one pass over the region.

    One pass rather than one scan per known heading, because the two questions
    the old shape asked separately — "where does this section start" and "where
    does the next section start" — have to be answered from the same list of
    headings or a section can open inside another one. Returns `None` when the
    document itemizes a both-sided category with no direction printed anywhere
    above it, which is the one case where the paper does not say which way the
    money moved.
    """
    body = _activity_body(markdown)
    if not body:
        return {}
    marks: list[tuple[int, int, str | None]] = []
    for match in _HEADING_LINE.finditer(body):
        if _opens_a_section(body, match):
            marks.append((match.start(), match.end(), match.group("name")))
    for pattern in (_BLOCK_CLOSER, _GRID_HEADING):
        for match in pattern.finditer(body):
            marks.append((match.start(), match.end(), None))
    marks.sort()

    captured: dict[str, list[Transaction]] = {}
    group_sign: int | None = None
    for index, (_start, end, name) in enumerate(marks):
        stop = marks[index + 1][0] if index + 1 < len(marks) else len(body)
        if name is None:
            # A closer ends the section above it and opens nothing. It does NOT
            # clear the direction: PNC reprints a section's continuation
            # heading after a page break but not always the umbrella above it,
            # so the direction the bank printed is still in force on the next
            # page.
            continue
        if name in _GROUP_SIGNS:
            sign: int | None = _GROUP_SIGNS[name]
        elif name == _CHECKS_HEADING:
            sign = -1
        elif name in _UNSIGNED_SECTIONS:
            # The running direction, and nothing else. The consumer skin prints
            # no `Checks and Other Deductions` umbrella at all — its deduction
            # sections simply follow the additions — so the direction in force
            # is the last one the paper STATED, whether it stated it as an
            # umbrella or as a section whose own name carries a side.
            sign = group_sign
        else:
            sign = _SECTION_SIGNS[name]
        if sign is None:
            return None
        group_sign = sign
        chunk = body[end:stop]
        rows = (_check_rows(chunk, year=year) if name == _CHECKS_HEADING
                else _rows_of(chunk, year=year, sign=sign))
        captured.setdefault(_SECTION_ALIASES.get(name, name), []).extend(rows)
    return captured


def _printed_index(markdown: str) -> dict[str, set[tuple[int, float]]]:
    """The bank's own index of what it itemized: section -> what it CLAIMS.

    Two printed forms, kept together because they say the same thing about the
    same section. The `Description Items Amount` table lists every category
    with its item count and total; a section heading that restates its own
    count and total says it for that section alone, and the consumer skin
    merges several categories into one section by printing one sentence each —
    so those are summed, which is what the section's own rows add up to.

    The table is printed once PER DIRECTION — measured: exactly two tables on
    every archive document that prints one, and the only names that appear in
    both are the four both-sided categories — so a name's table claims are
    SUMMED. The section's rows are its rows whichever side the bank listed them
    on, and a category listed with three items on one side and none on the
    other is one section of three items.

    A section's claims are a SET, so the several restatements a section prints
    (one per continuation page) collapse to one, and a document that states two
    DIFFERENT claims for one section is refused rather than silently reduced to
    whichever was read last: no capture can satisfy two contradictory claims,
    which is the fail-closed reading of a bank contradicting itself.

    `Total` is dropped: it is the per-direction sum of the rows above it, which
    the Balance Summary already states and `analysis/reconcile.py` already
    compares. Keeping it here would compare one figure twice and call it two
    identities.
    """
    entries: dict[str, set[tuple[int, float]]] = {}
    tabled: dict[str, tuple[int, float]] = {}
    for table in _INDEX_TABLE.finditer(markdown):
        body = table.group("body")
        # The index is a BLOCK, and it ends where the next one begins. Without
        # that bound the last table on a page runs to the end of the document
        # and reads the Activity Detail's own figures as index rows.
        for bound in (_GRID_HEADING, _BLOCK_CLOSER, _HEADING_LINE):
            cut = bound.search(body)
            if cut:
                body = body[: cut.start()]
        for name, items, amount in _INDEX_ROW.findall(body):
            name = _SECTION_ALIASES.get(name.strip(), name.strip())
            # Every figure here is a capture group the pattern already matched,
            # so a reader that answers None has REFUSED it rather than found it
            # absent. `read_money` raises on that, and the dispatch boundary
            # turns the raise into a declined document — where dropping the row
            # would drop the bank's CLAIM about that section and let a capture
            # nobody checked stand in for it.
            value = read_money(amount, _money)
            was = tabled.get(name, (0, 0.0))
            tabled[name] = (was[0] + int(items), round(was[1] + (value or 0.0), 2))
    for name, claim in tabled.items():
        entries.setdefault(name, set()).add(claim)
    for line in markdown.splitlines():
        found = _HEADING_COUNT_RE.findall(line) or _HEADING_PROSE_RE.findall(line)
        head = _HEADING_LINE.match(line)
        if not found or head is None:
            continue
        name = _SECTION_ALIASES.get(head.group("name"), head.group("name"))
        restated = [read_money(amount, _money) for _count, amount in found]
        entries.setdefault(name, set()).add((
            sum(int(count.replace(",", "")) for count, _ in found),
            round(sum(value or 0.0 for value in restated), 2),
        ))
    entries.pop("Total", None)
    return entries


def _matches_the_printed_index(
    captured: dict[str, list[Transaction]], printed: dict[str, set[tuple[int, float]]]
) -> bool:
    """Every category the bank indexed, reproduced row for row and cent for cent.

    The index is the bank's own statement of what its detail sections contain,
    so a reader that captures a different number of rows, or a different total,
    in a category the bank named has misread that section — whether it dropped
    a continuation page, swallowed a section into its neighbour, or read one
    section's rows twice. The check runs in both directions: a category printed
    and not reproduced fails, and so does a section this reader itemizes that
    the index does not print at all, because rows in an unindexed section are
    rows the bank did not say were there.

    Applied only when an index is printed. Every one of the 58 documents this
    reader claims prints one — the table alone on 50, the per-section
    restatement alone on 4, both on 4, neither on none — so the check is
    never vacuous on the surveyed population. A statement that printed
    neither would be read as before, with the Balance Summary totals as its
    only row oracle.
    """
    if not printed:
        return True
    for name, claims in printed.items():
        rows = captured.get(name, [])
        captured_total = sum(abs(row.amount) for row in rows)
        for items, total in claims:
            if len(rows) != items or abs(captured_total - total) > _TOLERANCE:
                return False
    return all(not rows or name in printed for name, rows in captured.items())


def _printed_daily_grid(markdown: str, *, year: int) -> dict[str, float] | None:
    """The end-of-day balance ladder, date -> balance.

    Returns `None` when the ladder prints one date twice with two different
    balances, which is not a ladder this reader can read against anything.
    Every block under a grid heading is collected — the ladder runs over
    several pages on the longer statements, and each page reprints the heading
    with a continuation marker.
    """
    grid: dict[str, float] = {}
    for heading in _GRID_HEADING.finditer(markdown):
        stop = len(markdown)
        for pattern in (_HEADING_LINE, _BLOCK_CLOSER, _GRID_HEADING):
            nxt = pattern.search(markdown, heading.end())
            if nxt and nxt.start() < stop:
                stop = nxt.start()
        for mmdd, amount, minus in _GRID_CELL.findall(markdown[heading.end():stop]):
            day = iso_from_month_day_strict(mmdd, year)
            value = _money(amount)
            if day is None or value is None:
                continue
            value = -value if minus else value
            if day in grid and abs(grid[day] - value) > _TOLERANCE:
                return None
            grid[day] = value
    return grid


def _matches_the_printed_grid(
    grid: dict[str, float], txns: list[Transaction], *,
    beginning: float, start: str, end: str,
) -> bool:
    """The ledger walked day by day against the bank's own end-of-day balances.

    An independent second opinion, and the only one that can see a row on the
    wrong DAY: the printed index and the Balance Summary are both invariant
    under moving a row from one day to another, because neither the count nor
    the total changes. Walking the ledger and comparing every day the bank
    printed is what makes that visible.

    What it bounds, said exactly: a row moved between two days the ladder
    prints, or onto one, changes at least one printed cell and is refused. A
    row moved ACROSS a stretch the ladder does not print — PNC prints a cell
    for every day the account moved, so that stretch is a weekend or a holiday
    — changes no printed cell and is invisible here. This check is a bound on
    misdating, not a proof of its absence.

    Every printed cell must fall inside the printed period; a ladder cell the
    period does not contain is a page from another statement and fails the
    document.
    """
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    moved: dict[str, float] = {}
    for txn in txns:
        moved[txn.date] = round(moved.get(txn.date, 0.0) + txn.amount, 2)
    carry = round(beginning, 2)
    walked: dict[str, float] = {}
    day = first
    while day <= last:
        iso = day.isoformat()
        carry = round(carry + moved.get(iso, 0.0), 2)
        walked[iso] = carry
        day += timedelta(days=1)
    for iso, balance in grid.items():
        if iso not in walked or abs(walked[iso] - balance) > _TOLERANCE:
            return False
    return True


DETECTION_MARKERS = (
    required("bank_name", lambda t: "PNC Bank" in t or "PNC.com" in t),
    required("product", lambda t: any(product in t for product in _PRODUCTS)),
    required("section", lambda t: "Balance Summary" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_pnc_statement(markdown: str) -> Statement | None:
    """Any of PNC's four printed product skins.

    Declines — rather than publishes short — in five named situations, each a
    fact about the document rather than a gap in this reader:

    * it prints no period sentence, or no readable four-column Balance Summary
      row (including a row one of whose figures cannot be read WHOLE);
    * it itemizes a both-sided category with no direction printed over it, or
      one whose direction contradicts the group heading above it;
    * it itemizes nothing at all;
    * its rows do not reproduce the bank's own printed index of them;
    * its ledger does not reproduce the bank's own end-of-day balance ladder.
    """
    if _DIGIT_ADJACENT_CONTROL.search(markdown):
        return None
    markdown = _CONTROL_BYTE.sub(" ", markdown)
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    summary = _summary_amounts(markdown)
    if period is None or summary is None:
        return None
    year = int(period[1][:4])
    beginning, credits, debits, ending = summary
    captured = _captured_sections(markdown, year=year)
    if captured is None:
        return None
    txns = [row for name in _EMISSION_ORDER for row in captured.get(name, [])]
    if not txns:
        return None
    if not _matches_the_printed_index(captured, _printed_index(markdown)):
        return None
    grid = _printed_daily_grid(markdown, year=year)
    if grid is None:
        return None
    if grid and not _matches_the_printed_grid(
            grid, txns, beginning=beginning, start=period[0], end=period[1]):
        return None

    average = _average_balance(markdown)
    stmt = Statement(
        bank="PNC Bank",
        account_name=_product(markdown),
        holder_name=_holder_name(markdown),
        period_start=period[0],
        period_end=period[1],
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
        bank_reported_average_balance=average[0] if average else None,
        bank_reported_average_label=average[1] if average else None,
    )
    acct = re.search(r"(?:Primary )?Account Number:\s*([X0-9-]+)", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    stmt.transactions = txns
    stmt.stated_daily_balances = [
        StatementDailyBalance(date=day, balance=balance)
        for day, balance in sorted(grid.items())
    ]
    return stmt
