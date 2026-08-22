"""BMO Canada "Business Banking statement" — the four-column ledger layout.

A different printed document from the one `analysis/bmo.py` reads. That parser
knows BMO's `ACCOUNT SUMMARY TOTALS` block and a `Date | Description |
Withdrawal | Deposit | Balance` grid. This layout prints neither: its summary is
a one-row grid headed `Summary of account`, and its ledger columns are
`Amounts debited from your account ($)` and `Amounts credited to your
account ($)`. The two marker sets are disjoint on every document either has been
measured against, so neither registration can claim the other's documents and no
`supersedes` edge is needed (W3_TRACKA_LOG §BMO-LAYOUTS).

The French-language edition of the same printed statement is the same grid with
the same four summary columns, French headings and FR-CA money (`7 227,65`). It
is registered separately — `bmo_ca_business_french`, the precedent being
`rbc_french` — because the evidence a document is that edition is a different
set of printed headings, not a translation applied at parse time.

**What the document asserts about itself.** Three independent printings, and
this parser is built on all three rather than on any one of them:

1. the `Summary of account` row — `opening - debited + credited = closing`;
2. the ledger's own `Closing totals` row, which re-prints the debited and
   credited totals under the columns they belong to;
3. `Number of items processed`, the debit and credit row counts.

**Direction comes from the printed Balance column, never from wording.** The
flattened text layer keeps one money cell per row plus the balance, and which of
the two money columns that cell stood in is not recoverable from the character
stream. It is recoverable from the grid: the balance BMO prints on the row is
the balance after the row, so the movement between two consecutive printed
balances is the row's signed amount. The printed amount is still what this
parser publishes — the balance movement only orients it — so a row whose
magnitude disagrees with the balance movement produces a continuity break that
the fail-closed gate sees, instead of a fabricated ledger that always
reconciles.
"""
from __future__ import annotations

import re
from datetime import date

from .dates import resolve_year
from .money import parse_french_amount, parse_grouped_float
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace, group_rows
from .td_can import normalize_mojibake

_MONTHS_EN = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
#: The month names BMO prints in the French edition, abbreviated as the Date
#: column abbreviates them. `juil` and `juin` share a prefix, so the table is
#: keyed on the first four characters rather than the first three.
_MONTHS_FR = {
    "janv": 1, "fév": 2, "fev": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "août": 8, "aout": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12,
    "dec": 12,
}
_MONTHS_FR_FULL = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}

#: Inter-word spacing is a property of the text layer, not of the printed
#: statement: some BMO PDFs render the same furniture as `Forthe period ending
#: April30, 2026`. Every space in these patterns is therefore optional. No money
#: or date TOKEN is relaxed — only the gaps between words — so a document read
#: this way still has to satisfy the printed ledger identity to survive the
#: fail-closed gate.
_PERIOD_END_EN = re.compile(
    r"For\s*the\s+period\s+ending\s+([A-Za-z]+)\s*(\d{1,2})\s*,\s*(\d{4})",
    re.IGNORECASE,
)
_PERIOD_END_FR = re.compile(
    r"P.riode\s*termin.e\s*le\s*(\d{1,2})(?:er)?\s*([A-Za-zéûôà]+)\s+(\d{4})",
    re.IGNORECASE,
)

#: A printed money cell in either edition: `1,234.56` / `-1,234.56` /
#: `1 234,56` / `-1 531,25`. Not anchored to a column — the flattened text has
#: no columns — so callers take the cells a row prints in printed order.
#: The lookbehind and the `(?!\d)` tail are what keep an account number out of
#: the money columns: `# 0262 1994-203 7 227,65` prints its number in the same
#: run of digits and spaces an FR-CA amount uses, and only "starts at a group
#: boundary, ends at the cents" separates the two.
_MONEY_EN = re.compile(r"(?<![\d.,])-?\$?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?!\d)")
_MONEY_FR = re.compile(r"(?<![\d.,-])-?\d{1,3}(?:[ \u00a0\u202f]\d{3})*,\d{2}(?!\d)")

_DATE_EN = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*(\d{1,2})\b",
    re.IGNORECASE,
)
_DATE_FR = re.compile(
    r"^(\d{1,2})(?:er)?\s*"
    r"(janv|f[ée]v|mars|avr|mai|juin|juil|ao[ûu]t|sept|oct|nov|d[ée]c)[a-zéû.]*\s+",
    re.IGNORECASE,
)


class _Edition:
    """The printed vocabulary of one language edition of this statement.

    Held as data rather than as two copies of the parser: the grid, the summary
    identity and the direction rule are identical in both editions, and only the
    words BMO prints and the way it writes money differ.
    """

    def __init__(self, *, bank, period_end, opening_label, closing_label,
                 items_label, ledger_heading, money_re, date_re, to_amount,
                 account_label, name_label):
        self.bank = bank
        self.period_end = period_end
        self.opening_label = opening_label
        self.closing_label = closing_label
        self.items_label = items_label
        self.ledger_heading = ledger_heading
        self.money_re = money_re
        self.date_re = date_re
        self.to_amount = to_amount
        self.account_label = account_label
        self.name_label = name_label


def _month_en(token: str) -> int | None:
    return _MONTHS_EN.get(token[:3].lower())


def _month_fr(token: str) -> int | None:
    key = token.lower().rstrip(".")
    if key in _MONTHS_FR_FULL:
        return _MONTHS_FR_FULL[key]
    return _MONTHS_FR.get(key[:4]) or _MONTHS_FR.get(key[:3])


EN = _Edition(
    bank="BMO",
    period_end=_PERIOD_END_EN,
    opening_label=re.compile(r"^Opening\s*balance\b", re.IGNORECASE),
    closing_label=re.compile(r"^Closing\s*totals\b", re.IGNORECASE),
    items_label=re.compile(r"^Number\s*of\s*items\s*processed", re.IGNORECASE),
    ledger_heading=re.compile(r"Transaction details", re.IGNORECASE),
    money_re=_MONEY_EN,
    date_re=_DATE_EN,
    to_amount=lambda token: parse_grouped_float(token.replace("$", "")),
    account_label=re.compile(r"^(?P<label>[A-Za-z][A-Za-z &'/.-]{2,40}?)\s*#\s*"),
    name_label=re.compile(r"Business name:\s*(?P<name>[^\n]+?)\s*$", re.MULTILINE),
)

FR = _Edition(
    bank="BMO",
    period_end=_PERIOD_END_FR,
    opening_label=re.compile(r"^Solde\s*d'ouverture\b", re.IGNORECASE),
    closing_label=re.compile(
        r"^Tota(?:l|ux)\s*[àa]\s*la\s*fermeture\b", re.IGNORECASE
    ),
    # The glyph between `art` and `cles` is not always a clean `i` in the text
    # layer, so the label is matched around it rather than through it.
    items_label=re.compile(r"^Nombre\s*d.\s*art.cles\s*trait.s", re.IGNORECASE),
    ledger_heading=re.compile(r"D.tails des transactions", re.IGNORECASE),
    money_re=_MONEY_FR,
    date_re=_DATE_FR,
    to_amount=lambda token: parse_french_amount(
        token.replace(" ", " ").replace(" ", " ")
    ),
    account_label=re.compile(r"^(?P<label>Compte[A-Za-zÀ-ÿ &'/.-]{0,40}?)\s*#\s*"),
    name_label=re.compile(
        r"Nom de l'entreprise\s*:\s*(?P<name>[^\n]+?)\s*$", re.MULTILINE
    ),
)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return normalize_mojibake(markdown).upper()


#: Issuer furniture only (R-4b): BMO's own domain as printed in the page footer,
#: BMO's own title for this statement, its summary heading, and the two column
#: headings of the ledger grid this parser reads. No customer data, no amount,
#: no date, and nothing keyed on a document in the corpus.
DETECTION_MARKERS = (
    required("issuer_domain", lambda t: "BMO.COM" in t),
    required("statement_title", lambda t: "BUSINESS BANKING STATEMENT" in t),
    required("summary_heading", lambda t: "SUMMARY OF ACCOUNT" in t),
    # The printed column headings of the four-column ledger. `analysis/bmo.py`'s
    # layout prints `Withdrawal Deposit Balance` instead, which is what keeps
    # the two registrations disjoint.
    required(
        "ledger_columns",
        lambda t: "AMOUNTS DEBITED" in t and "AMOUNTS CREDITED" in t,
    ),
)

FRENCH_DETECTION_MARKERS = (
    required("issuer_domain", lambda t: "BMO.COM" in t),
    required(
        "statement_title",
        lambda t: "SERVICES BANCAIRES AUX ENTREPRISES" in t,
    ),
    required("summary_heading", lambda t: "SOMMAIRE DE VOTRE COMPTE" in t),
    required(
        "ledger_columns",
        lambda t: "MONTANTS DÉDUITS" in t and "MONTANTS AJOUTÉS" in t,
    ),
)

detect = make_detector(DETECTION_MARKERS, detection_text)
detect_french = make_detector(FRENCH_DETECTION_MARKERS, detection_text)


# ---------------------------------------------------------------------------
# Reading the printed grid
# ---------------------------------------------------------------------------

def _cells(line: str, edition: _Edition) -> list[re.Match]:
    """The money cells one physical line prints, in printed order.

    A description can contain a money-shaped token — a unit price (`13 ITMS AT
    1.25`), an exchange rate operand (`AT1.3285 HC $0.00, 5.00`). Those stand to
    the LEFT of the grid's money columns and are therefore never among the last
    two cells on the line, which is the only property this parser relies on.

    Matches, not strings: the amount `200.00` also occurs INSIDE the balance
    `1,200.00` printed beside it, so where a cell stands has to come from the
    match rather than from searching the line for its text again.
    """
    return list(edition.money_re.finditer(line))


def _summary_row(text: str, edition: _Edition) -> tuple[str, str, list[float]] | None:
    """The `Summary of account` row: label, account number, four money cells.

    The row prints `opening | total debited | total credited | closing` under a
    heading whose own words the flattening scatters, so the row is found by its
    shape — an account label, its number, and exactly the four money cells the
    grid has columns for — rather than by re-finding the heading.
    """
    for raw in text.splitlines():
        line = compact_whitespace(raw)
        match = edition.account_label.match(line)
        if not match:
            continue
        rest = line[match.end():]
        cells = _cells(rest, edition)
        if len(cells) != 4:
            continue
        try:
            amounts = [edition.to_amount(cell.group(0)) for cell in cells]
        except ValueError:
            continue
        # The account number is whatever the row prints between the `#` and its
        # first money column.
        number = compact_whitespace(rest[: cells[0].start()])
        return match.group("label").strip(), number, amounts
    return None


def _ledger_lines(markdown: str, edition: _Edition) -> list[str]:
    """The physical lines that stand inside the transaction-details grid.

    Everything above the first ledger heading is the address block and the
    summary; page furniture (`Page 1 of 2`, `continued`, the repeated column
    headings, the per-account sub-headings) prints no Date column and no money
    pair, so it is dropped by the row grammar rather than by a list of the
    wordings BMO uses for it.
    """
    lines = [compact_whitespace(raw) for raw in markdown.splitlines()]
    start = None
    for index, line in enumerate(lines):
        if edition.ledger_heading.search(line):
            start = index + 1
            break
    if start is None:
        return []
    return [line for line in lines[start:] if line]


def _read_rows(lines: list[str], edition: _Edition) -> list[list[str]]:
    """Group the physical lines into the rows the grid prints (§GROUPER rule 1).

    A row starts where the Date column starts one. The `Closing totals` row ends
    the grid: it is the printed section total, not a posting, and everything
    after it — the item counts, the page footer, the legal block — belongs to no
    row.
    """
    def closes(line: str) -> bool:
        return bool(edition.closing_label.match(_strip_date(line, edition)))

    return group_rows(
        lines,
        starts_row=lambda line: bool(edition.date_re.match(line)) and not closes(line),
        ends_row=closes,
    )


def _period_end(text: str, edition: _Edition) -> date | None:
    match = edition.period_end.search(text)
    if not match:
        return None
    try:
        if edition is FR:
            day, month_token, year = match.group(1), match.group(2), match.group(3)
            month = _month_fr(month_token)
        else:
            month_token, day, year = match.group(1), match.group(2), match.group(3)
            month = _month_en(month_token)
        if month is None:
            return None
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _row_date(line: str, edition: _Edition) -> tuple[int, int] | None:
    match = edition.date_re.match(line)
    if not match:
        return None
    if edition is FR:
        day, month = int(match.group(1)), _month_fr(match.group(2))
    else:
        month, day = _month_en(match.group(1)), int(match.group(2))
    if month is None:
        return None
    return month, day


def _strip_date(line: str, edition: _Edition) -> str:
    match = edition.date_re.match(line)
    return line[match.end():].strip() if match else line


def _parse(markdown: str, edition: _Edition) -> Statement | None:
    text = normalize_mojibake(markdown)

    period_end = _period_end(text, edition)
    if period_end is None:
        return None

    summary = _summary_row(text, edition)
    if summary is None:
        return None
    label, number, (opening, debited, credited, closing) = summary

    # The Canadian editions of this layout print no denomination anywhere;
    # the reader asserts it from the institution and owes the evidence.
    stmt = Statement(bank=edition.bank, currency="CAD", currency_source="institution_default")
    stmt.account_number = number
    name = edition.name_label.search(text)
    stmt.account_name = name.group("name").strip() if name else label
    stmt.beginning_balance = opening
    stmt.ending_balance = closing
    stmt.stated_total_debits = debited
    stmt.stated_total_credits = credited

    # The item counts print under the two money columns, and a column with
    # nothing in it prints no count: a statement with no credits prints ONE
    # number on this line, not two. Reading the line's numbers and pairing them
    # with the totals the columns carry is what tells the two cases apart —
    # taking "the first two digit runs" splits a two-digit count in half.
    for raw in text.splitlines():
        line = compact_whitespace(raw)
        if not edition.items_label.match(line):
            continue
        printed = [int(token) for token in re.findall(r"\d+", line)]
        if len(printed) == 2:
            stmt.stated_debit_count, stmt.stated_credit_count = printed
        elif len(printed) == 1 and bool(debited) != bool(credited):
            stmt.stated_debit_count = printed[0] if debited else 0
            stmt.stated_credit_count = 0 if debited else printed[0]
        break

    lines = _ledger_lines(text, edition)
    if not lines:
        return None
    groups = _read_rows(lines, edition)
    if not groups:
        return None

    # The grid's own opening row dates the balance the summary states, and that
    # date is where the period this parser reports begins: it is the only start
    # the document prints. Its year is the latest one that does not put the row
    # after the period's end.
    opening_row = None
    for group in groups:
        if edition.opening_label.search(_strip_date(group[0], edition)):
            opening_row = group[0]
            break
    period_start = None
    if opening_row is not None:
        parts = _row_date(opening_row, edition)
        if parts is not None:
            month, day = parts
            for year in (period_end.year, period_end.year - 1):
                try:
                    candidate = date(year, month, day)
                except ValueError:
                    continue
                if candidate <= period_end:
                    period_start = candidate
                    break
    if period_start is None:
        return None
    stmt.period_start = period_start.isoformat()
    stmt.period_end = period_end.isoformat()

    transactions: list[Transaction] = []
    previous = opening
    for group in groups:
        head = group[0]
        parts = _row_date(head, edition)
        if parts is None:
            continue
        body = _strip_date(head, edition).strip()
        if edition.opening_label.match(body):
            continue
        cells = _cells(body, edition)
        if len(cells) < 2:
            # The grid wrapped this row: its money cells are printed under it,
            # not beside it. Only then are the continuation lines read, so a
            # page footer that follows a complete row cannot reach the columns.
            body = " ".join([body, *group[1:]]).strip()
            cells = _cells(body, edition)
        if len(cells) < 2:
            continue
        try:
            amount = edition.to_amount(cells[-2].group(0))
            balance = edition.to_amount(cells[-1].group(0))
        except ValueError:
            continue
        description = compact_whitespace(body[: cells[-2].start()])
        if not description:
            continue
        month, day = parts
        year = resolve_year(month, day, period_start, period_end)
        if year is None:
            continue
        try:
            posted = date(year, month, day)
        except ValueError:
            continue
        # Direction from the printed Balance column: the movement between the
        # previous printed balance and this row's is the row's signed amount.
        # The MAGNITUDE published is still the one BMO printed, so a row this
        # rule reads wrongly breaks continuity instead of balancing itself.
        movement = round(balance - previous, 2)
        signed = -abs(amount) if movement < 0 else abs(amount)
        previous = balance
        transactions.append(Transaction(
            date=posted.isoformat(),
            description=description,
            amount=round(signed, 2),
            direction="credit" if signed > 0 else "debit",
            running_balance=balance,
        ))

    stmt.transactions = transactions
    return stmt


def parse_bmo_ca_business_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    return _parse(markdown, EN)


def parse_bmo_ca_business_french_statement(markdown: str) -> Statement | None:
    if not detect_french(markdown).claims:
        return None
    return _parse(markdown, FR)


def closing_totals_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """The ledger's `Closing totals` row re-prints the summary's two totals.

    Registered as this parser's `integrity_check`, so a document whose two
    printings of the same figure disagree is reported as contradicting itself
    rather than silently reconciled to whichever the parser happened to read.
    """
    text = normalize_mojibake(markdown)
    edition = FR if FR.closing_label.search(text) else EN
    contradictions: list[str] = []
    for line in (compact_whitespace(raw) for raw in text.splitlines()):
        if not edition.closing_label.match(_strip_date(line, edition)):
            continue
        cells = _cells(line, edition)
        if len(cells) < 2:
            continue
        try:
            debited = edition.to_amount(cells[-2].group(0))
            credited = edition.to_amount(cells[-1].group(0))
        except ValueError:
            continue
        if (
            stmt.stated_total_debits is not None
            and abs(stmt.stated_total_debits - debited) > 0.01
        ) or (
            stmt.stated_total_credits is not None
            and abs(stmt.stated_total_credits - credited) > 0.01
        ):
            contradictions.append(
                "the summary of account and the ledger's closing totals state "
                "different period totals"
            )
        break
    return contradictions
