"""The Scotiabank Business Account statement.

**A THIRD printed issue of this template exists and is deliberately NOT read**
(W3 §DECLINESG, card SCOTIA-NOBAL). Three archive documents declare the same
`Date Description Withdrawals/Debits ($) Deposits/Credits ($) Balance ($)`
grid, print the same `Account Details:` heading and the same account-level
`No. of Debits …` strip — and then print **no balance anywhere in the
document**. Measured on all three:

* the `BALANCE FORWARD` row prints its label and no figure, so the opening
  balance this reader walks from does not exist and `prev_balance` stays None;
* every posting row prints exactly ONE money cell, where the two read issues
  print two (amount and balance);
* the count identity says what that one cell is: the printed rows number
  exactly the account-level strip's debits plus credits (135 = 97 + 38,
  114 = 69 + 45, 129 = 92 + 37), and the printed cells SUM to exactly the
  strip's two printed totals added together, to the cent, on all three. Every
  printed value is a row AMOUNT; the `Balance ($)` column is declared in the
  header and empty in every row;
* the only line in the whole document containing the word `balance` is that
  column header.

So the refusal at the end of `parse_scotiabank_statement` is honest and this is
not a vocabulary gap. The ceiling was measured rather than argued: with every
printed value taken as the row's amount the three land
`withheld` / `withheld_adb`, never `validated` — there is no opening balance,
no closing balance and no daily balance, and the canonical ADB is a
calendar-day average OF balances. Recovering the lost DIRECTION is tractable
(each page prints its own debit and credit counts and totals, so the page's
values are a subset-sum with a uniqueness requirement — §SCAN-NEXT's method),
but it buys the integrity flags and not the verdict. This belongs to the
geometry rung, beside §DECLINESD's D6.1: a column that the header declares and
the text layer has lost.
"""
from __future__ import annotations

import re

from .date_tokens import date_refusal, iso_or_none, parsed_datetime
from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")

# The `Account Details` posting table declares its own columns. That printed
# header, and the footer/section boundary that closes it, are the structural
# bounds of everything this parser is allowed to read as a posting.
#
# A Scotiabank PDF is a bundle of statements for one account: `Business
# Account` carries the ledger, while `Service Charge` and `Deposit Interest`
# are separate printed statements in the same file. The `Deposit Interest`
# sheet is a DAILY-YIELD ledger — one dated row per calendar day, carrying
# that day's closing balance and the interest it earned — and it declares a
# different grid (`Date Closing Balance ($) Yield/Rate Calculated Interest
# ($)`). Splitting the whole document on dates therefore turned 28 daily
# yield rows into 28 fabricated postings on a statement whose own summary
# said four. Binding rows to this header excludes them by construction,
# without a blocklist of section names to keep up to date.
_TABLE_HEADER = re.compile(
    r"Date\s+Description\s+Withdrawals/Debits\s*\(\$\)\s+"
    r"Deposits/Credits\s*\(\$\)\s+Balance\s*\(\$\)",
    re.IGNORECASE,
)
_TABLE_CLOSE = re.compile(
    r"\bNo\.\s*of\s+Debits\b|\bStatement\s+Of:|\bPlease\s+examine\b"
    r"|\bUncollected\s+fees\b|---\s+Page\b",
    re.IGNORECASE,
)

#: Every Scotiabank grid announces itself the same way: a `Date`-led run of
#: column labels reaching a `($)` money column. The posting table is the one
#: whose labels are `Description ... Balance ($)`; `Deposit Interest` declares
#: `Date Closing Balance ($) Yield/Rate Calculated Interest ($)`.
#:
#: A table therefore ends where the NEXT table declares its own columns, and
#: not only at `_TABLE_CLOSE`. Two things go wrong without this bound, both
#: on sections that never print a closing token: a trailing posting table
#: swallows the daily-yield sheet that follows it, and — because each header
#: opens a span independently — an unclosed span runs THROUGH the next
#: header, so every row of the following page is read twice.
_ANY_TABLE_HEADER = re.compile(r"\bDate\s+[A-Za-z][A-Za-z/&. ]*?\(\$\)", re.IGNORECASE)

# A printed balance is a currency value: two decimal places, optional
# thousands grouping, and the trailing minus this bank prints for an
# overdraft. A merchant reference number never takes this shape, which is
# what keeps `MRCH FIRST DATA CANADA(K)` continuation lines — an 11-digit
# reference printed AFTER the balance cell — from being read as a balance in
# the tens of billions and having the amounts back-solved from it.
_BALANCE_TOKEN = re.compile(r"\$?\d[\d,]*\.\d{2}-?")

# The amount column additionally appears with its trailing zeros stripped:
# this layout prints $25.00 as `25`, $2,500.00 as `2,500` and $34.90 as
# `34.9`.
_AMOUNT_TOKEN = re.compile(r"\$?\d[\d,]*(?:\.\d{1,2})?-?")

#: A bare integer with no thousands separator is dollars only while it is
#: short enough to be a printed amount. Longer unseparated runs are reference
#: numbers, account-number fragments and years, none of which are money.
_BARE_INTEGER_DIGITS = 3


def _is_balance_cell(token: str) -> bool:
    return bool(_BALANCE_TOKEN.fullmatch(token))


def _is_amount_cell(token: str) -> bool:
    if not _AMOUNT_TOKEN.fullmatch(token):
        return False
    core = token.strip("$-")
    if "." in core or "," in core:
        return True
    return len(core) <= _BARE_INTEGER_DIGITS


def _amount_value(token: str) -> float | None:
    """The printed amount cell as a number.

    `analysis.money.parse_money` requires two or three decimal places, so the
    trailing zeros this bank strips are restored before handing the token
    over. Padding the printed form at the call site is the division money.py
    documents: the engine is shared, the format stays with the bank.
    """
    core = token.strip("$")
    sign = "-" if core.endswith("-") else ""
    core = core.rstrip("-")
    if "." in core:
        whole, _, fraction = core.partition(".")
        core = f"{whole}.{(fraction + '00')[:2]}"
    else:
        core = f"{core}.00"
    return parse_money(core + sign)


def _posting_tables(markdown: str) -> list[str]:
    """The `Account Details` posting tables, in document order.

    Each span runs from its own column header to whichever comes first: the
    token that closes the table, or the point at which the next table — of
    any kind — declares its columns. Spans can therefore never overlap and
    never absorb a neighbouring sheet.
    """
    text = re.sub(r"\s+", " ", markdown)
    tables = []
    for header in _TABLE_HEADER.finditer(text):
        start = header.end()
        bounds = [len(text)]
        close = _TABLE_CLOSE.search(text, start)
        if close is not None:
            bounds.append(close.start())
        following = _ANY_TABLE_HEADER.search(text, start)
        if following is not None:
            bounds.append(following.start())
        tables.append(text[start:min(bounds)])
    return tables


def _split_rows(table: str) -> list[str]:
    text = re.sub(r"(?<!^)(?=\d{2}/\d{2}/\d{4}\s)", "\n", table)
    return [row.strip() for row in text.splitlines() if _DATE_RE.search(row)]


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    # "SCOTIABANK" alone matches an incoming-wire description in all three
    # Santander statements, so pair it with the issuer's legal name, which
    # Scotiabank prints in its own trademark footer.
    required("bank_name", lambda t: "SCOTIABANK" in t),
    required("issuer_identity", lambda t: "THE BANK OF NOVA SCOTIA" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_scotiabank_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    upper = markdown.upper()
    if not detect(markdown).claims:
        return None
    if "ACCOUNT DETAILS" not in upper and "WITHDRAWALS/DEBITS" not in upper:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Scotiabank"
    stmt.currency = "CAD"
    stmt.currency_source = "institution_default"

    acct = re.search(r"Business Account\s+([0-9 ]{8,})", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = re.sub(r"\s+", " ", acct.group(1)).strip()
    period = re.search(r"Business Account\s+[0-9 ]+\s+([A-Za-z]{3}\s+\d{1,2}\s+\d{4})\s+([A-Za-z]{3}\s+\d{1,2}\s+\d{4})", markdown)
    if period:
        for attr, raw in (("period_start", period.group(1)), ("period_end", period.group(2))):
            # RAISE-PRIVACY-3 (#HYGIENE8), W3 §PRIVACY3 P10 item 4: an
            # escaping `strptime` whose ValueError quotes the printed period.
            parsed = parsed_datetime(
                raw, "%b %d %Y", reader="scotia.period").date()
            setattr(stmt, attr, parsed.isoformat())

    # The account-level grid, which is printed once above `Account Details`
    # and states whole-direction figures. The per-page footers repeat the same
    # labels for that page alone, so this must stay a first-match search:
    # count_semantics records scotiabank as comparable in both directions on
    # the strength of these being the whole-period figures.
    summary = re.search(
        r"No\. of Debits Total Amount - Debits No\. of Credits Total Amount\s+-\s+Credits\s+"
        r"(?P<debit_count>\d+)\s+\$(?P<debits>[\d,]+\.\d{2})\s+"
        r"(?P<credit_count>\d+)\s+\$(?P<credits>[\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    if summary:
        stmt.stated_debit_count = int(summary.group("debit_count"))
        stmt.stated_total_debits = parse_money(summary.group("debits"))
        stmt.stated_credit_count = int(summary.group("credit_count"))
        stmt.stated_total_credits = parse_money(summary.group("credits"))

    txns: list[Transaction] = []
    prev_balance: float | None = None
    #: Dated rows the posting tables actually printed, `BALANCE FORWARD`
    #: excluded because it is the table's opening bound and not a posting.
    #: This is what separates "the bank printed no activity" from "activity
    #: was printed and this parser could not read it" — the two are
    #: indistinguishable from an empty `txns` alone.
    printed_rows = 0
    for table in _posting_tables(markdown):
        for row in _split_rows(table):
            m = _DATE_RE.search(row)
            if not m:
                continue
            # REVIEW MAJOR-2, the "site 6" class: `_DATE_RE`'s
            # `(\d{2})/(\d{2})/(\d{4})` proves three digit runs and nothing
            # more, so a posting row printed `13/40/2031` reaches `date()`,
            # whose ValueError echoes the printed month, day and year.
            # Funnelled through `iso_or_none` and refused from OUTSIDE the
            # funnel; the class stays `ValueError`, so the document refuses
            # exactly as it refused before.
            tx_date = iso_or_none(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            if tx_date is None:
                raise date_refusal("scotia.posting_row", m.group(0))
            rest = row[m.end():].strip()
            if rest.upper().startswith("BALANCE FORWARD"):
                opening = [t for t in rest.split() if _is_balance_cell(t)]
                if opening:
                    stmt.beginning_balance = parse_money(opening[-1])
                    prev_balance = stmt.beginning_balance
                continue

            printed_rows += 1
            tokens = rest.split()
            balance_at = next(
                (i for i in range(len(tokens) - 1, -1, -1) if _is_balance_cell(tokens[i])),
                None,
            )
            if balance_at is None or prev_balance is None:
                continue
            amount_at = next(
                (i for i in range(balance_at - 1, -1, -1) if _is_amount_cell(tokens[i])),
                None,
            )
            #: A row whose printed amount cell cannot be located is dropped
            #: rather than published with a back-solved one. Dropping loses
            #: the amount, so the ledger stops reconciling and the document is
            #: withheld: fail closed.
            if amount_at is None:
                continue

            balance = parse_money(tokens[balance_at])
            printed = _amount_value(tokens[amount_at])
            if balance is None or printed is None:
                continue
            desc = " ".join(tokens[:amount_at]).strip()
            if not desc:
                continue

            #: The printed money cell is the amount of record. The balance
            #: column supplies only the DIRECTION, because this layout
            #: flattens `Withdrawals/Debits ($)` and `Deposits/Credits ($)`
            #: into one printed value whose column is lost in extraction.
            #:
            #: Where the two disagree the disagreement is published, not
            #: resolved: the printed magnitude ships, the printed balance
            #: ships, and `analysis.reconcile` sees a running-balance
            #: continuity break and a ledger-sum mismatch. Assigning the
            #: balance delta here instead — which is what this parser used to
            #: do — made `sum_delta` and `continuity_breaks` re-derive the
            #: parser's own arithmetic, so they were 0 on every document by
            #: construction and the fail-closed gate had nothing to check.
            magnitude = abs(printed)
            amount = round(magnitude if balance >= prev_balance else -magnitude, 2)
            txns.append(Transaction(
                date=tx_date,
                description=desc,
                amount=amount,
                direction="credit" if amount > 0 else "debit",
                running_balance=balance,
            ))
            prev_balance = balance

    if not txns:
        #: A period with no activity is a statement, not a parse failure —
        #: but only when the bank says so. It must have printed zero
        #: instances AND zero totals in both directions and an opening
        #: balance: then the closing balance is the opening balance, on the
        #: bank's own evidence. An empty ledger on any other document means
        #: the detail was not read, and that still refuses.
        #: The posting tables must also be EMPTY of dated rows. An empty
        #: `txns` on its own cannot tell "the bank printed no activity" from
        #: "rows were printed and every one of them was refused", and
        #: publishing the second as a zero-activity statement would assert
        #: that nothing happened on a document that says otherwise.
        printed_zero_activity = (
            printed_rows == 0
            and stmt.stated_debit_count == 0
            and stmt.stated_credit_count == 0
            and stmt.stated_total_debits == 0.0
            and stmt.stated_total_credits == 0.0
        )
        if not printed_zero_activity or stmt.beginning_balance is None:
            return None
        if stmt.ending_balance is None:
            stmt.ending_balance = stmt.beginning_balance
        stmt.transactions = []
        return stmt
    if stmt.ending_balance is None:
        stmt.ending_balance = txns[-1].running_balance
    stmt.transactions = txns
    return stmt
