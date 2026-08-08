from __future__ import annotations

import re
import unicodedata
from datetime import date
from itertools import takewhile

from .money import parse_french_amount, parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import group_rows
from .td_can import _MONTHS, normalize_mojibake

_PERIOD_RE = re.compile(
    r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s+to\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)
_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_DATE_START_RE = re.compile(r"^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", re.IGNORECASE)
_MONEY_RE = re.compile(r"(?<![#\w])-?\$?[\d,]+\.\d{2}(?!\w)")
_PAGE_RE = re.compile(r"^\d+ of \d+$", re.IGNORECASE)
#: The cents group every printed amount ends with, in either locale
#: (`1,234.56` / `1 234,56`). Stripping it leaves the integer part, which is
#: what tells a price from a reference number.
_CENTS_TAIL_RE = re.compile(r"[.,]\d{2}\)?$")
_NON_DIGIT_RE = re.compile(r"\D")


def _date_from(day: str, mon: str, *, default_year: int) -> str:
    return date(default_year, _MONTHS[mon[:3].upper()], int(day)).isoformat()


def _is_printed_price(token: str) -> bool:
    """False for a money-SHAPED token that the grid does not print as money.

    A printed price never carries a leading zero, so `00314.06` beside an
    amount is a reference number the description happens to end with, not a
    second money cell. `0.45` keeps its single leading zero and stays money.
    """
    body = token.strip().lstrip("(").lstrip("-").lstrip("$").strip()
    digits = _NON_DIGIT_RE.sub("", _CENTS_TAIL_RE.sub("", body))
    return not (len(digits) > 1 and digits[0] == "0")


def _grid_cells(line: str, pattern: re.Pattern[str]) -> list[re.Match]:
    """The money cells the activity grid prints on one physical line.

    Three kinds of money-shaped token are printed inside a description cell
    rather than in a money column, and each is recognised by the mark the
    statement prints beside it, never by its value:

    * the operand of `@` — the "at unit price" marker (`4 Drs @ 2.50 10.00`
      prints a rate and then the fee);
    * a percentage operand (`@ RBP+05.00%P.A`);
    * a reference number, which a printed price never resembles because a
      price carries no leading zero.
    """
    cells = []
    for match in pattern.finditer(line):
        if not _is_printed_price(match.group(0)):
            continue
        if line[match.end():match.end() + 1] == "%":
            continue
        before = line[:match.start()].rstrip()
        if before.endswith("$"):
            before = before[:-1].rstrip()
        if before.endswith("@"):
            continue
        cells.append(match)
    return cells


def _read_grid_rows(entries, *, pattern, to_amount, opening_label, closing_label):
    """Rows read off the printed grid rather than off the physical lines.

    `entries` is the activity section as `(text, date, opens_a_date_group)`,
    with the Date column already consumed by the caller. Returns the rows and
    the balance the table's own opening row prints.

    Two structural rules do all the work, and both come from the printed
    column order `... | Cheques & Debits | Deposits & Credits | Balance`:

    1. **A lone money cell is an amount; two money cells with nothing between
       them are one row's amount and its running balance.** Balance is the
       last column and is never printed without an amount beside it, so the
       pairing is decided by adjacency in the grid, not by which token comes
       last on a line. This is what makes a row carrying TWO money cells
       readable at all, and it is deliberately blind to the values: a balance
       smaller than its own amount is still the balance.
    2. **A row ends at its amount cell**, so text that follows one begins the
       next row. That reads a compressed line (several printed rows emitted on
       one physical line) and a wrapped row (one printed row spread over
       several physical lines) with the same rule, and it needs no whitelist
       of description wordings.

    The one line-level fact that survives: an amount printed alone on its line
    is vertically centred between two description lines, so a following
    description-only line continues THAT row instead of opening a new one.

    Rule 1 — where a row starts — is `tables.group_rows` (W3 §GROUPER): a
    printed posting date opens a row here, and so does the table's own opening
    balance row, which prints no date. The entries a page footer or a header
    block would contribute never reach this function; the caller drops them.
    """
    entries = list(entries)
    rows: list[dict] = []
    opening: float | None = None
    description: list[str] = []
    #: the row the most recent cell closed, while it can still take a balance
    open_row: dict | None = None
    centred_amount = False
    # Case-insensitive matching, not `.upper()` plus an index: upper-casing can
    # change a string's length, and these two labels are used to CUT a line.
    opens = re.compile(re.escape(opening_label), re.IGNORECASE)
    closes = re.compile(re.escape(closing_label), re.IGNORECASE)

    def starts_row(entry) -> bool:
        text, _, opens_group = entry
        return bool(opens_group) or bool(opens.match(text))

    groups = group_rows(entries, starts_row=starts_row)
    #: Whatever the table prints above its first row start already stands
    #: inside that row: unlike a section heading in a Chase block, there is no
    #: furniture here for the caller to have left behind.
    head = list(takewhile(lambda entry: not starts_row(entry), entries))
    if head:
        groups.insert(0, head)

    stopped = False
    for group in groups:
        # A new posting date closes whatever was pending: a description
        # with no amount cell under it never became a row.
        description = []
        open_row = None
        centred_amount = False
        for text, tx_date, _ in group:
            if not text:
                continue
            stop = closes.search(text)
            if stop:
                text = text[:stop.start()].strip()
                if not text:
                    stopped = True
                    break
            cells = _grid_cells(text, pattern)
            if opens.match(text):
                if cells:
                    opening = to_amount(cells[-1].group(0))
                description, open_row, centred_amount = [], None, False
                continue
            if not cells:
                if open_row is not None and centred_amount:
                    open_row["description"] = f"{open_row['description']} {text}".strip()
                else:
                    description.append(text)
                centred_amount = False
                continue

            cells_only = (
                not text[:cells[0].start()].strip()
                and not text[cells[-1].end():].strip()
                and all(not text[a.end():b.start()].strip() for a, b in zip(cells, cells[1:]))
            )
            position = 0
            for match in cells:
                gap = text[position:match.start()].strip()
                if gap:
                    description.append(gap)
                    open_row = None
                value = to_amount(match.group(0))
                if open_row is not None and open_row["balance"] is None:
                    open_row["balance"] = value
                    open_row = None
                else:
                    row = {
                        "date": tx_date,
                        "description": " ".join(description).strip(),
                        "abs_amount": abs(value),
                        "amount": -abs(value),
                        "balance": None,
                    }
                    description = []
                    rows.append(row)
                    open_row = row
                position = match.end()
            tail = text[position:].strip()
            if tail:
                description.append(tail)
                open_row = None
            centred_amount = cells_only
        if stopped:
            break

    return rows, opening


def _column_split_signs(amounts: list[int], delta: int) -> list[int] | None:
    """Signs from the printed column order: the credit set is a prefix.

    Inside one balance block RBC prints the Deposits & Credits column above the
    Cheques & Debits column, so the credits are the rows before a single split
    point. Because every amount is positive the prefix total is strictly
    increasing, so at most ONE split reproduces the printed delta — the
    assignment is unique whenever it exists, with nothing to choose between.
    """
    total = sum(amounts)
    running = 0
    for split in range(len(amounts) + 1):
        if 2 * running - total == delta:
            return [1] * split + [-1] * (len(amounts) - split)
        if split < len(amounts):
            running += amounts[split]
    return None


def _subset_signs(amounts: list[int], delta: int, *, max_rows: int = 24,
                  max_states: int = 200_000) -> list[int] | None:
    """Signs from the printed delta when the credits are not a prefix.

    Same evidence, no ordering assumption: find a credit subset whose total is
    `(delta + sum)/2`. Reachability is computed suffix-first so the walk can
    take the earliest admissible row as a credit — the printed column order
    again, used only to make the choice deterministic where several subsets
    reproduce the same delta (which happens when equal amounts sit on both
    sides and every candidate publishes the identical credit/debit totals).
    Bounded in both rows and states so it is total: past the bound it refuses.
    """
    if len(amounts) > max_rows:
        return None
    total = sum(amounts)
    wanted = delta + total
    if wanted % 2 or wanted < 0 or wanted // 2 > total:
        return None
    wanted //= 2

    reachable: list[set[int]] = [set() for _ in range(len(amounts) + 1)]
    reachable[len(amounts)] = {0}
    for index in range(len(amounts) - 1, -1, -1):
        sums = set(reachable[index + 1])
        for value in reachable[index + 1]:
            if value + amounts[index] <= wanted:
                sums.add(value + amounts[index])
        if len(sums) > max_states:
            return None
        reachable[index] = sums
    if wanted not in reachable[0]:
        return None

    signs = []
    remaining = wanted
    for index, amount in enumerate(amounts):
        if amount <= remaining and (remaining - amount) in reachable[index + 1]:
            signs.append(1)
            remaining -= amount
        else:
            signs.append(-1)
    return signs


def _solve_from_printed_balances(rows: list[dict], opening: float | None) -> None:
    """Assign every row's direction from the statement's own running balances.

    The text layer does not carry which activity column an amount was printed
    in, so the sign is read off the arithmetic the bank printed: across the
    rows between two printed balances the signed amounts must reproduce the
    delta. Rows in a block the chain cannot close keep the direction their
    transaction type implies and the document then fails the platform's
    coverage and ledger checks — the signs are never invented to make the
    arithmetic work.
    """
    previous = opening
    segment: list[dict] = []
    for row in rows:
        segment.append(row)
        if row["balance"] is None or previous is None:
            continue
        amounts = [round(item["abs_amount"] * 100) for item in segment]
        delta = round(row["balance"] * 100) - round(previous * 100)
        signs = _column_split_signs(amounts, delta)
        if signs is None:
            signs = _subset_signs(amounts, delta)
        if signs is not None:
            for item, sign in zip(segment, signs):
                item["amount"] = round(sign * item["abs_amount"], 2)
        previous = row["balance"]
        segment = []


def _is_credit(desc: str) -> bool:
    text = desc.upper()
    return (
        "MRCH" in text
        or text.startswith("ATM DEPOSIT")
        or text.startswith("E-TRANSFER RECEIVED")
        or text.startswith("ONLINE TRANSFER RECEIVED")
        or text.startswith("ROYAL FOREIGN EXCHANGE DEPOSIT")
        or text.startswith("COMMERCIAL LOANS")
        or "FUNDS TRANSFER CREDIT" in text
        or text.startswith("BR TO BR")
        or "RETURNED NSF" in text
        or "ITEM RETURNED NSF" in text
    )


def _is_debit(desc: str) -> bool:
    # Generic banking transaction types only. Counterparty names are never
    # sign evidence (R-1 item 7: the two memorized counterparty entries were
    # removed; rows not matching a credit type default to debit below, and
    # printed running balances drive the sign solver, so behaviour is
    # unchanged - see R1_HARDCODE_LOG.md).
    text = desc.upper()
    return any(key in text for key in (
        "MONTHLY FEE",
        "TRANSACTION FEE",
        "CASH DEPOSITED FEE",
        "ONLINE BANKING PAYMENT",
        "ONLINE BANKING TRANSFER",
        "ONLINE TRANSFER SENT",
        "E-TRANSFER SENT",
        "INTERAC PURCHASE",
        "CONTACTLESS INTERAC",
        "CHEQUE -",
        "INSURANCE ",
        "BILL PAYMENT",
        "EQUIPMENT RENT",
        "BUSINESS PAD",
    ))


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


def french_detection_text(markdown: str) -> str:
    """As above, after repairing double-encoded accents."""
    return normalize_mojibake(markdown).upper()


DETECTION_MARKERS = (
    required("bank_name", lambda t: "ROYAL BANK OF CANADA" in t),
    required("activity_section", lambda t: "ACCOUNT ACTIVITY DETAILS" in t),
)

FRENCH_DETECTION_MARKERS = (
    required("bank_name", lambda t: "BANQUE ROYALE" in t),
    required("activity_header", lambda t: "DATE DESCRIPTION RETRAITS" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)
detect_french = make_detector(FRENCH_DETECTION_MARKERS, french_detection_text)


def parse_rbc_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    upper = markdown.upper()
    french = _parse_rbc_french_statement(markdown, base=base)
    if french is not None:
        return french
    if not detect(markdown).claims:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Royal Bank of Canada"
    entries: list[tuple[str, str, bool]] = []
    default_year: int | None = None
    in_activity = False
    current_date: str | None = None

    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        u = line.upper()

        if line.startswith("--- Page"):
            in_activity = False
            continue

        pm = _PERIOD_RE.search(line)
        if pm:
            sm, sd, sy, em, ed, ey = pm.groups()
            stmt.period_start = date(int(sy), _MONTH_NAMES[sm.lower()], int(sd)).isoformat()
            stmt.period_end = date(int(ey), _MONTH_NAMES[em.lower()], int(ed)).isoformat()
            default_year = int(ey)

        account = re.search(r"Account number:\s*([0-9 -]+)", line, re.IGNORECASE)
        if account:
            stmt.account_number = account.group(1).strip()

        m = re.search(r"Opening balance on .*?(-?\$?[\d,]+\.\d{2}|\$-?[\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.beginning_balance = parse_money(m.group(1))
        m = re.search(r"Closing balance on .*?(-?\$?[\d,]+\.\d{2}|\$-?[\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.ending_balance = parse_money(m.group(1))
        m = re.search(r"Total deposits & credits \((\d+)\)\s*\+?\s*([\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.stated_credit_count = int(m.group(1))
            stmt.stated_total_credits = parse_money(m.group(2))
        m = re.search(r"Total cheques & debits \((\d+)\)\s*-?\s*([\d,]+\.\d{2})", line, re.IGNORECASE)
        if m:
            stmt.stated_debit_count = int(m.group(1))
            stmt.stated_total_debits = parse_money(m.group(2))

        if "DATE DESCRIPTION CHEQUES & DEBITS" in u:
            in_activity = True
            continue
        if in_activity and (u.startswith("CLOSING BALANCE") or u.startswith("ACCOUNT FEES:")):
            in_activity = False
            continue
        if not in_activity or default_year is None:
            continue
        if u.startswith(("BUSINESS ACCOUNT STATEMENT", "ACCOUNT ACTIVITY DETAILS")):
            continue
        # The printed page footer is grid furniture. It is dropped BEFORE the
        # Date column is read, because `<n> of <m>` and its French counterpart
        # `<n> de <m>` are shaped exactly like a day plus a month token.
        if _PAGE_RE.match(line):
            continue

        dm = _DATE_START_RE.match(line)
        if dm:
            # Record the posting date the moment it is seen. RBC puts the date on
            # the first line of each group, and that line often carries no amount
            # because the description wraps ("03 Feb Royal Foreign Exchange
            # deposit" / "Reference 0521... 90.00"). Tracking the date separately
            # from row creation is what keeps the following rows on the right day
            # — deriving it from rows[-1] instead silently folded whole posting
            # dates into the previous one and corrupted the daily ledger.
            current_date = _date_from(dm.group(1), dm.group(2), default_year=default_year)
            line = line[dm.end():].strip()
            repeated = _DATE_START_RE.match(line)
            if repeated:
                line = line[repeated.end():].strip()
        elif current_date is None and not line.upper().startswith("OPENING BALANCE"):
            continue
        entries.append((line, current_date, bool(dm)))

    rows, table_opening = _read_grid_rows(
        entries,
        pattern=_MONEY_RE,
        to_amount=lambda token: parse_money(token) or 0.0,
        opening_label="OPENING BALANCE",
        closing_label="CLOSING BALANCE",
    )
    rows = [row for row in rows if row["description"] and row["date"]]
    for row in rows:
        # The initial reading is the row's printed transaction type, and it is
        # only ever the fallback: the printed balance chain below overrules it
        # wherever the chain closes. Rows in a block the chain cannot close
        # keep this reading, which is what makes such a block fail the bank's
        # own stated totals instead of being repaired into agreement.
        if _is_credit(row["description"]):
            signed = row["abs_amount"]
        elif _is_debit(row["description"]):
            signed = -row["abs_amount"]
        else:
            signed = -row["abs_amount"]
        row["amount"] = round(signed, 2)

    if not rows:
        return None
    if stmt.beginning_balance is None:
        stmt.beginning_balance = table_opening
    _solve_from_printed_balances(rows, stmt.beginning_balance)

    transactions = [
        Transaction(
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            direction="credit" if row["amount"] > 0 else "debit",
            running_balance=row["balance"],
        )
        for row in rows
    ]
    stmt.transactions = transactions
    return stmt


_FR_DATE_RE = re.compile(r"^(\d{1,2})\s+([^\s]+)\s+(.*)$", re.IGNORECASE)
_FR_MONEY_RE = re.compile(r"(?<![A-Za-z0-9])\(?-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2}\)?")
_FR_PAGE_RE = re.compile(r"^\d+ de \d+$", re.IGNORECASE)
#: Full French month names; tokens resolve by unambiguous prefix, so every
#: month works, not only December/January (R-1 item 7).
_FR_MONTH_NAMES = {
    "JANVIER": 1, "FEVRIER": 2, "MARS": 3, "AVRIL": 4, "MAI": 5, "JUIN": 6,
    "JUILLET": 7, "AOUT": 8, "SEPTEMBRE": 9, "OCTOBRE": 10, "NOVEMBRE": 11,
    "DECEMBRE": 12,
}
_FR_PERIOD_RE = re.compile(
    r"Du\s+(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})\s+au\s+(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})",
    re.IGNORECASE,
)


def _money_fr(text: str) -> float:
    return parse_french_amount(text, parens=True)


def _fr_month(month_token: str) -> int | None:
    """Resolve a (possibly abbreviated) French month token; None if ambiguous."""
    decomposed = unicodedata.normalize("NFKD", month_token)
    token = "".join(c for c in decomposed if c.isalpha()).upper()
    if not token:
        return None
    matches = {
        number
        for name, number in _FR_MONTH_NAMES.items()
        if name.startswith(token)
    }
    return matches.pop() if len(matches) == 1 else None


def _fr_transaction_date(
    day: int, month: int, *, period_start: date, period_end: date
) -> date | None:
    """The unique in-period date for a day/month pair, else None (fail closed).

    Replaces the hardcoded start-year/end-year December/January mapping
    (R-1 item 7): year choice is evidence-based - the date must fall inside
    the printed statement period, whatever months it spans.
    """
    candidates = []
    for year in {period_start.year, period_end.year}:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if period_start <= candidate <= period_end:
            candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


def _fr_initial_sign(desc: str, amount: float) -> float:
    # Real accented characters only - the text is mojibake-normalized first
    # (R-1 item 11). The printed-balance sign solver has the final word.
    text = desc.upper()
    if any(key in text for key in ("REÇU", "ANNUL", "DÉP", "RABAIS")):
        return amount
    return -amount


def _parse_rbc_french_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    markdown = normalize_mojibake(markdown)
    upper = markdown.upper()
    if not detect_french(markdown).claims:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Banque Royale du Canada"
    stmt.currency = "CAD"

    # The full printed period line is required - day, month, and year for
    # both bounds. No default years, no hardcoded month/day (R-1 item 7:
    # previously Dec/Jan-only with (2025, 2026) fallbacks).
    period = _FR_PERIOD_RE.search(markdown)
    if not period:
        return None
    start_day, start_token, start_year, end_day, end_token, end_year = period.groups()
    start_month = _fr_month(start_token)
    end_month = _fr_month(end_token)
    if start_month is None or end_month is None:
        return None
    try:
        period_start = date(int(start_year), start_month, int(start_day))
        period_end = date(int(end_year), end_month, int(end_day))
    except ValueError:
        return None
    if period_end < period_start:
        return None
    stmt.period_start = period_start.isoformat()
    stmt.period_end = period_end.isoformat()

    # NOTE (R-1 item 7/11): the previous account-number regex carried a
    # mojibake label and could never match the real text, so no account was
    # ever extracted here. Extraction stays deliberately absent to keep the
    # audited corpus surface identical; enabling it is proposed in
    # R1_HARDCODE_LOG.md for an Ocean-approved re-baseline.

    m = re.search(r"solde d'ouverture.*?([\d ]+,\d{2})\s*\$", markdown, re.IGNORECASE)
    if m:
        stmt.beginning_balance = _money_fr(m.group(1))
    m = re.search(r"Total des d.*?compte\s*\+\s*([\d ]+,\d{2})", markdown, re.IGNORECASE)
    if m:
        stmt.stated_total_credits = _money_fr(m.group(1))
    m = re.search(r"Total des retraits.*?-\s*([\d ]+,\d{2})", markdown, re.IGNORECASE)
    if m:
        stmt.stated_total_debits = _money_fr(m.group(1))
    m = re.search(r"solde de cl.*?=\s*([\d ]+,\d{2})\s*\$", markdown, re.IGNORECASE)
    if m:
        stmt.ending_balance = _money_fr(m.group(1))

    entries: list[tuple[str, str, bool]] = []
    current_date: str | None = None
    in_activity = False
    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        u = line.upper()
        if line.startswith("--- Page"):
            # Symmetric with the English layout: a page break leaves the
            # activity table and the reprinted column header re-enters it, so
            # the page's own header block never reaches the grid reader.
            in_activity = False
            continue
        if "DATE DESCRIPTION RETRAITS" in u:
            in_activity = True
            continue
        if in_activity and (u.startswith("SOLDE DE CL") or u.startswith("VOTRE LIMITE")):
            break
        if not in_activity or u.startswith(("DOCUSIGN", "RELEV", "BANQUE ROYALE", "DU ", "RBPDA", "*3", "DATE DESCRIPTION")):
            continue
        # See the English loop: the page footer is dropped before the Date
        # column is read, because `<n> de <m>` is shaped like a French date.
        if _FR_PAGE_RE.match(line):
            continue

        dm = _FR_DATE_RE.match(line)
        if dm:
            day, month_token, rest = dm.groups()
            month = _fr_month(month_token)
            if month is None:
                continue
            resolved = _fr_transaction_date(
                int(day), month, period_start=period_start, period_end=period_end
            )
            if resolved is None:
                continue
            current_date = resolved.isoformat()
            line = rest.strip()
        elif current_date is None and not u.startswith("SOLDE D'OUVERTURE"):
            continue
        entries.append((line, current_date, bool(dm)))

    # Same grid, same two structural rules: the French layout prints
    # `Retraits ($) | Dépôts ($) | Solde ($)`, so a row carries the same two
    # money cells and the same missing column-of-origin. It is a first-class
    # family of this parser, not an exception to it.
    rows, table_opening = _read_grid_rows(
        entries,
        pattern=_FR_MONEY_RE,
        to_amount=_money_fr,
        opening_label="SOLDE D'OUVERTURE",
        closing_label="SOLDE DE CL",
    )
    rows = [row for row in rows if row["description"] and row["date"]]
    for row in rows:
        row["amount"] = _fr_initial_sign(row["description"], row["abs_amount"])
    if table_opening is not None:
        stmt.beginning_balance = table_opening
    _solve_from_printed_balances(rows, stmt.beginning_balance)

    transactions = [
        Transaction(
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            direction="credit" if row["amount"] > 0 else "debit",
            running_balance=row["balance"],
        )
        for row in rows
    ]
    if not transactions:
        return None
    stmt.transactions = transactions
    return stmt


#: Public entry point for the French-language RBC layout, registered in its
#: own right by R-3. `parse_rbc_statement` still tries it first until the
#: pipeline switches to registry dispatch.
parse_rbc_french_statement = _parse_rbc_french_statement
