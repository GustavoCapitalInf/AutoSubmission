"""The Symitar member statement — one PDF, several of a member's accounts.

The document is a MEMBER statement, not an account statement: it prints an
`ACCOUNT SUMMARY` naming every account the member holds and then one section
per account. Two things follow from that.

**Only the deposit accounts are ledgers this schema can carry.** A member's
loan facilities are printed in the same document under a different grid
(`Date Amount Fees Interest Principal Balance Description`) with their own
payment and interest columns. They are not deposit ledgers and contribute no
transaction here; a section is read only when it prints the deposit grid.

**A dormant sibling is not a second ledger, but a second ACTIVE one is.** Most
members hold a share/membership account that prints `No Transactions This
Period` beside a beginning balance equal to its ending balance. Declining a
document because such an account exists would fail-close a perfectly readable
statement, so dormant deposit siblings are skipped. Where TWO deposit accounts
genuinely post, the single-account extraction schema cannot represent the
document (L-1) and it is declined rather than published under one account's
name.

**A sibling that posted only its own dividend printed no member activity
either** (W3 §DECLINESG). The platform declares dormancy two ways and this
reader now reads both. `No Transactions This Period` is the first. The second
is a section whose every posting is a dividend the credit union credited to
the account — the yield the account itself earned, which this platform names
in its OWN equation row as a column separate from `Credits / Deposits`
(`_EQUATION_HEADER_RE`), so "a dividend is not a deposit" is the platform's
taxonomy and not this reader's. It is not read off the word alone:
`_yield_only` also requires the section's own arithmetic to close and its last
printed balance to equal the ending balance the document's own `ACCOUNT
SUMMARY` states for that account, and — where the section prints the
platform's six-figure equation row — the platform's own `Dividends` column to
account for every skipped posting with its `Credits / Deposits` column at
zero. The skip fails closed on any of them.

**Both idle-declarations are published SILENTLY today.** Neither the
dormant skip nor the yield-only skip leaves any trace in the payload that a
deposit section existed and was not published — the schema has no field and
the integrity-flag vocabulary has no member. That visible surface is
SIBLING-OMISSION-SURFACE (batch 8), which owns both together. The rule also
carries no materiality bound: a five-dollar sibling and a five-hundred-thousand
-dollar sibling are skipped alike, because a size bound in a parser would be
exactly the statement-specific constant R-1 forbids. The cost of not reading it was measured: four
consecutive statements of one member, whose money-market share account holds
about five dollars, differ only in whether that account earned a cent — the
month it earned nothing published, and the three months it earned $0.01 were
refused as two-ledger documents.

The per-account oracle differs between the platform's two issues and both are
read:

* the six-figure equation row — `Beginning Balance + Credits/Deposits +
  Dividends - Debits/Withdrawals = Ending Balance` (with YTD Dividends printed
  sixth) — which states the account's whole arithmetic; and
* where no equation row is printed, the account's entry in the document's own
  `ACCOUNT SUMMARY`, which states its ending balance.

Amount and balance are printed BEFORE the description in both issues, and the
amount carries its own sign, so the running balance is a cross-check here
rather than the sign oracle it has to be on layouts that print neither.
"""
from __future__ import annotations

import re
from datetime import date

from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

_MONEY = r"-?\$?\s?-?[\d,]+\.\d{2}"

#: The deposit grid. `Posting Date` and `Date` are the two issues' wordings for
#: the same column.
_DEPOSIT_GRID_RE = re.compile(
    r"(?:Posting\s+)?Date\s+Deposit\s+Withdrawal\s+Balance\s+Description", re.IGNORECASE
)
#: The loan grid. A section printing this is a credit facility, not a deposit
#: ledger, and is never read for transactions.
_LOAN_GRID_RE = re.compile(
    r"Date\s+Amount\s+Fees\s+Interest\s+Principal\s+Balance\s+Description", re.IGNORECASE
)
_ACCOUNT_SUMMARY_RE = re.compile(
    r"^[^\S\n]*ACCOUNT[^\S\n]+SUMMARY[^\S\n]*$", re.IGNORECASE | re.MULTILINE
)

#: The two issues' section headings: `Free Business Checking ( ID 0210 )` and
#: `Business Checking (Account #xxxxxx9247)`, each re-printed with
#: `(Continued)` after a page break.
_SECTION_RE = re.compile(
    r"^[^\S\n]*(?P<name>.{1,60}?)[^\S\n]*"
    r"\([^\S\n]*(?:ID[^\S\n]*(?P<id>\d+)|Account[^\S\n]*#[^\S\n]*(?P<masked>[x\d]+))[^\S\n]*\)"
    r"(?P<continued>[^\S\n]*\(Continued\))?[^\S\n]*$",
    re.IGNORECASE | re.MULTILINE,
)

#: The six-figure equation row's header and its figures.
_EQUATION_HEADER_RE = re.compile(
    r"Beginning\s+Balance\s+Credits\s*/\s*Deposits\s+Dividends\s+"
    r"Debits\s*/\s*Withdrawals\s+Ending\s+Balance\s+YTD\s+Dividends",
    re.IGNORECASE,
)
#: ...and the six figures printed under it, in that order. Anchored at the
#: start of what follows the header so the row is read as the header's own
#: figures rather than found anywhere later in the section.
_EQUATION_VALUES_RE = re.compile(
    r"^\s*(%s)\s+(%s)\s+(%s)\s+(%s)\s+(%s)\s+(%s)(?![\d.,])" % ((_MONEY,) * 6)
)

#: `03/01/26 $ 10,600.59 Beginning Balance` / `05/01 5.00 Beginning Balance`.
_OPENING_RE = re.compile(
    r"(?<![\d/])(\d{2}/\d{2}(?:/\d{2,4})?)\s+(%s)\s+Beginning\s+Balance" % _MONEY,
    re.IGNORECASE,
)
_DORMANT_RE = re.compile(r"No\s+Transactions\s+This\s+Period", re.IGNORECASE)

#: A posting the credit union credited to the account as the yield the account
#: itself earned. ANCHORED at the start of the description, which is where this
#: platform prints the posting type on every row (`ACH …`, `Card purchase …`,
#: `Point of Sale Withdrawal …`, `Dividend Deposit …`): measured over the whole
#: claimed family, all 880 postings begin with a posting-type word and exactly
#: three begin with `Dividend`. Anchoring is what keeps a description that
#: merely MENTIONS the word — a merchant trading as `DIVIDEND …`, which is a
#: real lender name — from being read as the account's own yield.
_DIVIDEND_RE = re.compile(r"Dividends?\b", re.IGNORECASE)

#: A posting: the Date column, then the signed amount cell, then the Balance
#: cell. Requiring both money cells straight after the date is what keeps a
#: date printed inside a description from opening a row.
#:
#: LATENT, recorded rather than fixed: the money alternatives here are
#: $-blind, while the opening and closing rows this layout prints DO carry the
#: symbol (`05/01/26 $ 1,000.00 Beginning Balance`). A posting row that ever
#: printed `$` would therefore not open a row and would be swallowed into the
#: previous row's description. It cannot happen in the surveyed population:
#: across all 7 family documents, the number of dated `$` amounts that are not
#: a Beginning/Ending Balance row is **zero**. Left as-is because widening the
#: pattern to admit `$` would make the opening row itself match as a posting,
#: which is the more dangerous of the two errors.
_ROW_RE = re.compile(
    r"(?<![\d/])(\d{2}/\d{2}(?:/\d{2,4})?)\s+(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})(?![\d.,])"
)

#: `01/01/26 - 01/31/26` and `05/01/26 thru 05/31/26`.
_PERIOD_RE = re.compile(
    r"(\d{2}/\d{2}/\d{2,4})\s*(?:-|thru|through)\s*(\d{2}/\d{2}/\d{2,4})", re.IGNORECASE
)

# Line structure is evidence here — the section headings and the
# `ACCOUNT SUMMARY` label are whole lines — so every pattern is anchored with
# re.MULTILINE and tolerates the leading and trailing spaces a collapsing pass
# would have stripped. Declaring no normalization keeps the registry from
# building a whole-document copy on every detect (RFC risk 7).
#: The section heading's own identifier, without the product name in front of
#: it. Detection asks only whether the document prints one; `_SECTION_RE` —
#: whose leading lazy match is what makes it expensive to scan a whole document
#: with — is applied per line during parsing, where the name is needed.
_SECTION_MARK_RE = re.compile(
    r"\([^\S\n]*(?:ID[^\S\n]*\d+|Account[^\S\n]*#[^\S\n]*[x\d]+)[^\S\n]*\)", re.IGNORECASE
)

DETECTION_MARKERS = (
    required("account_summary", lambda t: bool(_ACCOUNT_SUMMARY_RE.search(t))),
    required("deposit_grid", lambda t: bool(_DEPOSIT_GRID_RE.search(t))),
    required("account_section", lambda t: bool(_SECTION_MARK_RE.search(t))),
)

detect = make_detector(DETECTION_MARKERS)


def _money(token: str) -> float | None:
    return parse_money(token.replace("$", "").replace(" ", ""))


def _date(token: str, *, start: date, end: date) -> str | None:
    """`MM/DD/YY` as printed, or `MM/DD` resolved against the printed period."""
    parts = token.split("/")
    month, day = int(parts[0]), int(parts[1])
    if len(parts) == 3:
        year = int(parts[2])
        year += 2000 if year < 100 else 0
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    best: list[tuple[int, date]] = []
    for year in {start.year, end.year}:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate < start:
            distance = (start - candidate).days
        elif candidate > end:
            distance = (candidate - end).days
        else:
            distance = 0
        best.append((distance, candidate))
    if not best:
        return None
    best.sort()
    if len(best) > 1 and best[0][0] == best[1][0]:
        return None
    return best[0][1].isoformat()


class _Section:
    def __init__(self, name: str, key: str) -> None:
        self.name = name
        self.key = key
        self.lines: list[str] = []
        self.is_deposit = False
        self.is_loan = False

    @property
    def text(self) -> str:
        return " ".join(self.lines)


def _sections(lines: list[str]) -> list[_Section]:
    """The document's per-account sections, continuations folded together."""
    found: list[_Section] = []
    by_key: dict[str, _Section] = {}
    current: _Section | None = None
    for line in lines:
        heading = _SECTION_RE.match(line)
        if heading and not _DEPOSIT_GRID_RE.search(line) and not _LOAN_GRID_RE.search(line):
            key = (heading.group("id") or heading.group("masked") or "").lower()
            name = heading.group("name").strip()
            if key in by_key:
                current = by_key[key]
            else:
                current = _Section(name, key)
                by_key[key] = current
                found.append(current)
            continue
        if current is None:
            continue
        if _LOAN_GRID_RE.search(line):
            current.is_loan = True
        if _DEPOSIT_GRID_RE.search(line):
            current.is_deposit = True
        current.lines.append(line)
    return found


def _account_summary_balances(lines: list[str]) -> dict[str, float]:
    """`ACCOUNT SUMMARY`'s own ending balance per account id, where the issue
    prints the id beside the name (`0210 Free Business Checking $ 15,217.20`)."""
    balances: dict[str, float] = {}
    for index, line in enumerate(lines):
        if not _ACCOUNT_SUMMARY_RE.match(line):
            continue
        for candidate in lines[index + 1:index + 4]:
            for match in re.finditer(r"(\d{4})\s+[A-Za-z][^$]*?\$\s*(-?[\d,]+\.\d{2})", candidate):
                value = _money(match.group(2))
                if value is not None:
                    balances[match.group(1)] = value
        break
    return balances


def _yield_only(
    rows: list[dict],
    opening: float | None,
    closing: float | None,
    equation: list[float] | None,
) -> bool:
    """Whether a deposit sibling printed no MEMBER activity.

    Conditions, and all of them must hold, because a rule that rested on the
    first alone would be a posting-type vocabulary deciding whether a ledger
    exists:

    1. every posting is a dividend the platform named as one (`_DIVIDEND_RE`,
       anchored) **and is a CREDIT** — yield is paid INTO the account, so a
       debit under this description is not the account earning anything and
       the reader has no account of what it is;
    2. the section's own arithmetic closes — the opening balance plus every
       posting equals the last balance the section printed;
    3. that last balance equals the ending balance the DOCUMENT states for
       this account elsewhere (its equation row, or its `ACCOUNT SUMMARY`);
    4. **where the section prints the platform's six-figure equation row, the
       platform's own `Dividends` column must account for every skipped
       posting, and its `Credits / Deposits` column must be zero.** That is
       the bank's own arithmetic deciding the section holds yield and no
       member deposits — not a threshold this reader invented — and it is what
       closes the outside-party hole below wherever the row is printed.

    Any of them failing means the section is a ledger this reader has not
    accounted for, and the document is then a two-ledger document and refuses
    at the L-1 gate exactly as before. Over-refusing costs a document;
    under-refusing publishes one account's statement while another account's
    activity goes unmentioned, so the asymmetry is deliberate.

    **THE SKIP IS SILENT, AND THIS RULE DOES NOT CLOSE THAT.** Nothing in the
    published payload says a deposit section existed and was not published:
    the extraction schema has no field for it and the pipeline's
    integrity-flag vocabulary has no member for it. The same is already true
    of the `No Transactions This Period` skip this module has always
    performed — this rule adds a second way to reach that silence, it does not
    create it. The visible surface is **SIBLING-OMISSION-SURFACE (batch 8)**,
    which owns both idle-declarations together because adding it moves
    already-validated documents across several parsers.

    **THE RULE HAS NO MATERIALITY BOUND, BY DESIGN.** A sibling holding five
    dollars and a sibling holding five hundred thousand are skipped alike;
    condition 4 bounds *arithmetic consistency*, not size. A size bound would
    be a statement-specific constant inside a parser, which the R-1 guard
    exists to forbid. The honest bound is the disclosure, not a number.

    **The residual hole, named rather than left to be discovered.** The anchor
    reads the platform's posting type, and on this corpus every description
    begins with one (880 of 880). A description that instead began with a
    counterparty whose NAME starts with the word — `Dividend Reinvestment ACME
    BROKERAGE`, say — would be read as this account's own yield. The direction
    clause makes the common shape of that harmless (such a counterparty is
    being PAID), and condition 4 refuses it outright wherever the equation row
    prints, because an outside credit lands in the platform's
    `Credits / Deposits` column. **Where the equation row is NOT printed — the
    issue all three archive movers belong to — the hole stays reachable and
    its consequence is silent**: an outside dividend-named credit standing as
    the sibling's only posting, leaving the section's walk and the document's
    stated closing balance intact, would skip the section with no published
    trace. No archive document of this family prints one. Widening or
    narrowing the keyword class is a measurement, not a guess.
    """
    if not rows or opening is None or closing is None:
        return False
    if not all(
        _DIVIDEND_RE.match(row["description"]) and row["amount"] > 0 for row in rows
    ):
        return False
    last = rows[-1]["balance"]
    total = sum(row["amount"] for row in rows)
    if abs(round(opening + total - last, 2)) > 0.005:
        return False
    if equation is not None:
        # The platform's own `Dividends` column must account for every posting
        # skipped here, and its `Credits / Deposits` column must be zero.
        if abs(round(equation[2] - total, 2)) > 0.005:
            return False
        if abs(round(equation[1], 2)) > 0.005:
            return False
    return abs(round(last - closing, 2)) <= 0.005


def parse_symitar_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    """The Symitar member statement, read on its one active deposit account."""
    if not detect(markdown).claims:
        return None

    lines = [re.sub(r"[^\S\n]+", " ", raw).strip() for raw in markdown.splitlines()]
    lines = [line for line in lines if line and not line.startswith("--- Page")]

    period = _PERIOD_RE.search(" ".join(lines))
    if not period:
        return None
    try:
        bounds = []
        for token in period.groups():
            month, day, year = (int(part) for part in token.split("/"))
            bounds.append(date(year + 2000 if year < 100 else year, month, day))
        start, end = bounds
    except ValueError:
        return None
    if end < start:
        return None

    sections = _sections(lines)
    deposits = [s for s in sections if s.is_deposit and not s.is_loan]
    if not deposits:
        return None

    summary_balances = _account_summary_balances(lines)

    active: list[tuple[_Section, list[dict], float | None, list[float] | None]] = []
    for section in deposits:
        text = section.text
        opening_match = _OPENING_RE.search(text)
        opening = _money(opening_match.group(2)) if opening_match else None

        equation: list[float] | None = None
        header = _EQUATION_HEADER_RE.search(text)
        if header:
            values = _EQUATION_VALUES_RE.match(text[header.end():])
            if values:
                parsed = [_money(values.group(i)) for i in range(1, 7)]
                if None not in parsed:
                    equation = parsed

        rows: list[dict] = []
        # The opening row prints a balance where a posting prints its amount,
        # so it is consumed before the postings are read.
        body = text[opening_match.end():] if opening_match else text
        hits = list(_ROW_RE.finditer(body))
        for index, match in enumerate(hits):
            posted = _date(match.group(1), start=start, end=end)
            amount = _money(match.group(2))
            balance = _money(match.group(3))
            if posted is None or amount is None or balance is None:
                # A row the grid printed but this reader cannot resolve is a
                # hole in the ledger, and a hole must refuse the document
                # rather than shrink it silently — the same convention
                # `woodforest._postings` follows. Dropping it would publish a
                # ledger the bank never printed and leave the balance walk to
                # notice, which it does not always do.
                return None
            stop = hits[index + 1].start() if index + 1 < len(hits) else len(body)
            rows.append(
                {
                    "date": posted,
                    "amount": amount,
                    "balance": balance,
                    "description": body[match.end():stop].strip(),
                }
            )
        if not rows:
            continue
        # The account's ending balance as the DOCUMENT states it, read the same
        # way it is read for the account this parser goes on to publish, so the
        # two can never disagree about where that figure comes from.
        stated_closing = equation[4] if equation else summary_balances.get(section.key)
        if _yield_only(rows, opening, stated_closing, equation):
            continue
        active.append((section, rows, opening, equation))

    # Zero active deposit accounts: nothing to publish. Two or more: the
    # single-account schema cannot carry the document (L-1). A section skipped
    # as yield-only above is not counted here, and a document whose ONLY
    # deposit section is yield-only therefore refuses rather than publishing a
    # ledger of dividends.
    if len(active) != 1:
        return None
    section, rows, opening, equation = active[0]

    closing = equation[4] if equation else summary_balances.get(section.key)
    if opening is None or closing is None:
        return None
    if equation and abs(round(equation[0] - opening, 2)) > 0.005:
        # The account's two printed opening balances disagree; the document
        # contradicts itself and is not published.
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Symitar Credit Union"
    stmt.account_name = section.name
    stmt.account_number = section.key or None
    stmt.period_start = start.isoformat()
    stmt.period_end = end.isoformat()
    stmt.currency = "USD"
    stmt.currency_source = "institution_default"
    stmt.beginning_balance = opening
    stmt.ending_balance = closing
    if equation:
        # Dividends are credited to the account and post as their own rows, so
        # the stated credit total is the two credit columns the row prints.
        stmt.stated_total_credits = round(equation[1] + equation[2], 2)
        stmt.stated_total_debits = equation[3]

    stmt.transactions = [
        Transaction(
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            direction="credit" if row["amount"] > 0 else "debit",
            running_balance=row["balance"],
        )
        for row in rows
    ]
    return stmt
