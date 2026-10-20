from __future__ import annotations

import re
from datetime import date

from .holder_name import NO_READING, HolderReading, first_page, page_lines, read_address_block, read_address_line
from .money import STRICT_EITHER_MINUS_OR_PLUS_SPACED, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    return parse_amount(value, STRICT_EITHER_MINUS_OR_PLUS_SPACED)


def _is_date(line: str) -> bool:
    return re.fullmatch(r"\d{2}-\d{2}", line) is not None


def _parse_period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(r"Statement Period\s+(\d{2})/(\d{2})/(\d{2})\s+-\s+(\d{2})/(\d{2})/(\d{2})", markdown)
    if not m:
        return None
    sm, sd, sy, em, ed, ey = [int(part) for part in m.groups()]
    start = date(2000 + sy, sm, sd)
    end = date(2000 + ey, em, ed)
    return start.isoformat(), end.isoformat(), end.year


#: The table in which the statement declares every account it covers. It is
#: the parser's map of the document.
_SUMMARY_HEADING = "Summary of your deposit accounts"

#: A deposit product's name, as the summary table prints it on its own line.
#: The HEAD NOUN carries the kind: Navy Federal names its deposit products
#: "<qualifier> Checking" and "<qualifier> Savings". Reading the head noun is
#: what makes this a reader of the product LINE rather than a reader of one
#: product - "Business Checking" was previously written into the parser as a
#: structural anchor, which silently restricted it to the business issue of a
#: statement the credit union also prints for retail members ("EveryDay
#: Checking", "e-Checking"). Same layout, same grid, different word.
_PRODUCT_LINE_RE = re.compile(r"[A-Za-z][A-Za-z0-9&'./ -]{0,30}?(?:Checking|Savings)")
_ACCOUNT_LINE_RE = re.compile(r"(\d{6,})(?:\s|$)")

#: The transaction grid's printed column header. It matters here because the
#: text extractor sometimes merges a section's caption onto the end of it, so
#: "the caption is at the start of its line" and "the caption follows this
#: header" are the same structural position seen twice. The tokens are the
#: ones `_line_is_noise` already knows as grid furniture.
_GRID_HEADER = (
    r"(?:Date\s+Transaction Detail\s+Amount\(\$\)\s+Balance\(\$\)\s+)?"
)

#: Any account's section heading, "<product> - <account>", on its own line.
#: One account's section ends where the next one's begins, whatever product
#: that next one is - including products that never appear in the deposit
#: table at all, such as a credit line.
_SECTION_HEADING_RE = re.compile(r"(?m)^[A-Za-z][A-Za-z0-9&'./ -]{0,30}\s+-\s+\d{4,}\s*$")


def _deposit_accounts(markdown: str) -> list[tuple[str, str]]:
    """[(product, account)] in the order the summary table declares them."""
    start = markdown.find(_SUMMARY_HEADING)
    if start < 0:
        return []
    region = markdown[start + len(_SUMMARY_HEADING):]
    # The table ends at its own cross-account Totals row; the remittance
    # notice bounds a statement that prints no Totals.
    stops = [i for i in (region.find("\nTotals"), region.find("REMITTANCE")) if i > 0]
    if stops:
        region = region[:min(stops)]
    accounts: list[tuple[str, str]] = []
    product: str | None = None
    for raw_line in region.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        name = _PRODUCT_LINE_RE.fullmatch(line)
        if name:
            product = name.group(0)
            continue
        # An account number opens its row; the accounts that follow a product
        # name without repeating it belong to that same product.
        account = _ACCOUNT_LINE_RE.match(line)
        if account and product:
            accounts.append((product, account.group(1)))
    return accounts


def _checking_account(markdown: str) -> tuple[str, str] | None:
    """The one checking product this statement is about, or None.

    None has two causes and both are refusals, not errors. No checking
    product: there is nothing this parser publishes. More than one checking
    PRODUCT: the statement covers two different checking accounts and the
    single-account extraction schema (L-1) has no way to say so - publishing
    either one as "the" account would present half a statement as the whole
    of it. The reading is accepted only when the transaction detail confirms
    it by printing the same product and account as a section HEADING, so the
    product name rests on two independent printings, not one.

    The confirmation is POSITION-anchored, not a substring test. A bare
    `f"{product} - {account}" in markdown` is satisfied by any prose that
    happens to mention the pair, so it would confirm a reading the document
    never printed as a heading - the whole point of asking for a second
    printing.

    A heading occupies one of exactly two positions, and both are the caption
    of a transaction grid: the start of its own line, or immediately after the
    grid's column header on the line the extractor merged it into
    (`Date Transaction Detail Amount($) Balance($) Business Checking - 1234`).
    What may FOLLOW it is left open - a continuation marker, a stray column
    word - because that is downstream of the caption and varies. What may
    precede it is the whole test, and a sentence cannot precede it.

    Note this is deliberately NOT `_SECTION_HEADING_RE`, the whole-line pattern
    used for section boundaries below. Requiring the heading to BE the entire
    line is too strong: it refuses three documents in the cohort whose caption
    the extractor merged into the column-header line, all three of which
    validate. That is measured, not assumed - see the W3 log, DC10.3.
    """
    checking = [
        (product, account)
        for product, account in _deposit_accounts(markdown)
        if product.lower().endswith("checking")
    ]
    if len({product for product, _ in checking}) != 1:
        return None
    product, account = checking[0]
    heading = f"{product} - {account}"
    confirmed = re.search(
        r"(?m)^" + _GRID_HEADER + re.escape(heading) + r"(?!\d)", markdown
    )
    return (product, account) if confirmed else None


def _summary(markdown: str) -> tuple[str, str, float, float, float, float] | None:
    product_account = _checking_account(markdown)
    if product_account is None:
        return None
    product, account = product_account
    flat = re.sub(r"\s+", " ", markdown)
    m = re.search(
        re.escape(product) + r"\s+" + re.escape(account) + r"\s+"
        r"(\$?[\d,]+\.\d{2}-?)\s+(\$?[\d,]+\.\d{2})\s+"
        r"(\$?[\d,]+\.\d{2})\s+(\$?[\d,]+\.\d{2}-?)\s+\$?[\d,]+\.\d{2}",
        flat,
    )
    if not m:
        return None
    beginning, credits, debits, ending = m.groups()
    parsed = (_money(beginning), _money(credits), _money(debits), _money(ending))
    if any(value is None for value in parsed):
        return None
    return (product, account, *parsed)  # type: ignore[return-value]


def _average_balance(markdown: str) -> float | None:
    m = re.search(r"Average Daily Balance - Current Cycle:\s+\$?([\d,]+\.\d{2}-?)", markdown)
    return _money(m.group(1)) if m else None


def _checking_section(markdown: str, product: str, account: str) -> str:
    heading = f"{product} - {account}"
    start = markdown.find(heading)
    if start < 0:
        return ""
    # This account's section runs to wherever the NEXT account's section
    # begins. Reading that boundary from the document's own headings replaces
    # a list of the sibling products one issue of this statement happens to
    # print ("Mbr Business Savings", "Bus Money Mkt Savings", "Checking
    # Line"), which named none of the products a retail member's statement
    # carries and so let a savings section be read as part of the checking
    # one.
    candidates = [markdown.find("Disclosure", start)]
    for match in _SECTION_HEADING_RE.finditer(markdown, start):
        if match.group(0).strip() != heading:
            candidates.append(match.start())
            break
    stops = [idx for idx in candidates if idx > start]
    end = min(stops) if stops else len(markdown)
    return markdown[start:end]


def _line_is_noise(line: str, heading: str) -> bool:
    return (
        line.startswith("---")
        or line.startswith("Page ")
        or line.startswith("Statement Period")
        or line.startswith("Access No")
        or line.startswith("For ")
        or line.startswith("(Continued")
        or line == heading
        or line in {"Date", "Transaction Detail", "Amount($)", "Balance($)", "Items Paid", "Item"}
        or line.startswith("Average Daily Balance")
        # Audit round 2, R2-B06 (R21 part B): the page header the generic block text glues into the last row before
        # a page break, the statement's title and the joint owners' label (its value: _without_noise).
        or line.startswith("Statement of Account")
        or line.startswith("Joint Owner")
    )


#: Audit round 2, R2-B06 (R21 part B): the joint owners' label printed with no value, which prints on the next line.
_JOINT_OWNER_LABEL_RE = re.compile(r"Joint Owner\(s\):?")


def _without_noise(lines: list[str], heading: str) -> list[str]:
    """The section's lines without the grid's and the page's furniture (`_line_is_noise`). Audit round 2, R2-B06 (R21
    part B): nor the joint owners' value 'NONE' on the line after their bare label."""
    return [
        line
        for index, line in enumerate(lines)
        if not _line_is_noise(line, heading)
        and not (line == "NONE" and index > 0 and _JOINT_OWNER_LABEL_RE.fullmatch(lines[index - 1]))
    ]


#: This platform writes an overdrawn balance with a TRAILING minus, and the
#: extracted text carries it either detached in its own column ("136.51 -")
#: or attached to the figure ("136.51-"). Both are the same printed balance,
#: so the separator is optional - the file's own beginning-balance anchor
#: already reads the attached form, and a balance the reader cannot see stops
#: the walk at the first overdrawn day.
_TRAILING_MINUS = r"(?:\s*(-))?"


def _amount_balance(line: str) -> tuple[float, float] | None:
    m = re.fullmatch(r"([\d,]+\.\d{2})\s+([\d,]+\.\d{2})" + _TRAILING_MINUS, line)
    if m:
        amount = _money(m.group(1))
        balance = _money(m.group(2) + (m.group(3) or ""))
        if amount is not None and balance is not None:
            return amount, balance
    return None


def _separate_amount_balance(lines: list[str], idx: int) -> tuple[float, float, int] | None:
    if idx + 1 >= len(lines):
        return None
    if not re.fullmatch(r"[\d,]+\.\d{2}", lines[idx]):
        return None
    if not re.fullmatch(r"[\d,]+\.\d{2}" + _TRAILING_MINUS, lines[idx + 1]):
        return None
    amount = _money(lines[idx])
    balance = _money(lines[idx + 1])
    if amount is None or balance is None:
        return None
    return amount, balance, idx + 2


def _consume_following_date_desc(lines: list[str], idx: int) -> tuple[str, str, int] | None:
    if idx >= len(lines) or not _is_date(lines[idx]):
        return None
    txn_date = lines[idx]
    idx += 1
    parts: list[str] = []
    while idx < len(lines):
        line = lines[idx]
        if (
            _is_date(line)
            or line == "-"
            or "Ending Balance" in line
            or _amount_balance(line) is not None
            or re.fullmatch(r"[\d,]+\.\d{2}" + _TRAILING_MINUS, line)
        ):
            break
        parts.append(line)
        idx += 1
    return txn_date, " ".join(parts), idx


def _parse_native_transactions(
    markdown: str, account: str, *, year: int, beginning: float
) -> list[Transaction] | None:
    txns: list[Transaction] = []
    prev_balance = beginning
    for line in markdown.splitlines():
        if not line.startswith("NFCU_TX|"):
            continue
        parts = line.split("|", 5)
        if len(parts) != 6 or parts[1] != account:
            continue
        _, _, txn_date, printed_amount, printed_balance, description = parts
        if not _is_date(txn_date):
            return None
        amount = _money(printed_amount)
        balance = _money(printed_balance)
        if amount is None or balance is None:
            return None
        signed = round(balance - prev_balance, 2)
        if abs(abs(signed) - abs(amount)) > 0.01:
            return None
        txns.append(
            Transaction(
                date=date(year, int(txn_date[:2]), int(txn_date[3:])).isoformat(),
                description=re.sub(r"\s+", " ", description).strip()
                or "Navy Federal transaction",
                amount=signed,
                direction="credit" if signed >= 0 else "debit",
                running_balance=balance,
            )
        )
        prev_balance = balance
    return txns or None


def _parse_transactions(section: str, heading: str, *, year: int, beginning: float) -> list[Transaction] | None:
    lines = _without_noise([line.strip() for line in section.splitlines() if line.strip()], heading)

    idx = 0
    while idx < len(lines):
        if (
            re.fullmatch(r"[\d,]+\.\d{2}-?", lines[idx])
            and idx + 2 < len(lines)
            and _is_date(lines[idx + 1])
            and lines[idx + 2] == "Beginning Balance"
        ):
            parsed_beginning = _money(lines[idx])
            if parsed_beginning is None or abs(parsed_beginning - beginning) > 0.01:
                return None
            idx += 3
            break
        idx += 1
    else:
        return None

    # Audit round 2, R2-B06 (R03): the lookahead reading first; the line reader below only where it does not fit.
    rows = _rows_by_lookahead(_ledger_tokens(lines, idx))
    if rows is not None:
        txns = _ledger_transactions(rows, year=year, beginning=beginning)
        if txns is not None:
            return txns
    return _parse_transactions_by_line(lines, idx, year=year, beginning=beginning)


#: Audit round 2, R2-B06 (R03): the compatibility path's tokens. A money pair (P), a date with the description lines
#: printed after it (G), and a description line with no date before it (D).
_PAIR_TOKEN, _GROUP_TOKEN, _LINE_TOKEN = "P", "G", "D"
_LONE_MONEY_RE = re.compile(r"[\d,]+\.\d{2}" + _TRAILING_MINUS)


def _ledger_tokens(lines: list[str], idx: int) -> list[tuple]:
    """Audit round 2, R2-B06 (R03): the ledger after the Beginning Balance anchor, up to the Ending Balance line, as
    tokens: ("P", amount, balance) for a money pair (one line or two, a detached '-' after it skipped), ("G", date,
    [lines]) for a date and the description lines after it, ("D", line) for a description line with no date before it.
    A money figure printed right above the Ending Balance's own date, equal to the last pair's balance, is that balance
    printed amount-first and no description line."""
    tokens: list[tuple] = []
    while idx < len(lines):
        line = lines[idx]
        if "Ending Balance" in line:
            break
        if line == "-":
            idx += 1
            continue
        if _is_date(line):
            tokens.append((_GROUP_TOKEN, line, []))
            idx += 1
            continue
        pair = _amount_balance(line)
        next_idx = idx + 1
        if pair is None:
            separate = _separate_amount_balance(lines, idx)
            if separate is not None:
                amount, balance, next_idx = separate
                pair = amount, balance
        if pair is not None:
            tokens.append((_PAIR_TOKEN, *pair))
            idx = next_idx
            continue
        if _is_ending_balance_figure(lines, idx, tokens):
            idx += 1
            continue
        if tokens and tokens[-1][0] == _GROUP_TOKEN:
            tokens[-1][2].append(line)
        else:
            tokens.append((_LINE_TOKEN, line))
        idx += 1
    return tokens


def _is_ending_balance_figure(lines: list[str], idx: int, tokens: list[tuple]) -> bool:
    """Audit round 2, R2-B06 (R03): a lone money figure followed by the Ending Balance's date and label, equal to the
    last pair's balance."""
    if not _LONE_MONEY_RE.fullmatch(lines[idx]) or idx + 2 >= len(lines):
        return False
    if not _is_date(lines[idx + 1]) or "Ending Balance" not in lines[idx + 2]:
        return False
    pairs = [token for token in tokens if token[0] == _PAIR_TOKEN]
    figure = _money(lines[idx])
    return bool(pairs) and figure is not None and abs(figure - pairs[-1][2]) <= 0.01


def _rows_by_lookahead(tokens: list[tuple]) -> list[tuple[float, float, str, str]] | None:
    """Audit round 2, R2-B06 (R03): the tokens read with one token of lookahead, as [(amount, balance, date, text)].

    A pair followed by a date group is one row with that group's date and text (the amount-first arrangement: the
    generic block text sorts a row's money cells above its own date). A date group followed by a pair, then any lone
    description lines, is one row with the group's date and text plus those lines (the date-first arrangement, and its
    wrap lines). A last date group with no text is the Ending Balance's date. None when the reading does not fit: a
    pair with no date group after it, a date group with no pair after it, or a description line that opens a row."""
    if tokens and tokens[-1][0] == _GROUP_TOKEN and not tokens[-1][2]:
        tokens = tokens[:-1]
    rows: list[tuple[float, float, str, str]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if token[0] == _PAIR_TOKEN:
            if following is None or following[0] != _GROUP_TOKEN:
                return None
            rows.append((token[1], token[2], following[1], " ".join(following[2])))
            index += 2
        elif token[0] == _GROUP_TOKEN:
            if following is None or following[0] != _PAIR_TOKEN:
                return None
            parts = list(token[2])
            index += 2
            while index < len(tokens) and tokens[index][0] == _LINE_TOKEN:
                parts.append(tokens[index][1])
                index += 1
            rows.append((following[1], following[2], token[1], " ".join(parts)))
        else:
            return None
    return rows


def _ledger_transactions(
    rows: list[tuple[float, float, str, str]], *, year: int, beginning: float
) -> list[Transaction] | None:
    """Audit round 2, R2-B06 (R03): the lookahead reading's rows walked by balance (the line reader's check), or None
    where a pair's amount is not its balance step."""
    prev_balance = beginning
    txns: list[Transaction] = []
    for amount, balance, txn_date, text in rows:
        signed = round(balance - prev_balance, 2)
        if abs(abs(signed) - abs(amount)) > 0.01:
            return None
        txns.append(
            Transaction(
                date=date(year, int(txn_date[:2]), int(txn_date[3:])).isoformat(),
                description=re.sub(r"\s+", " ", text).strip() or "Navy Federal transaction",
                amount=signed,
                direction="credit" if signed >= 0 else "debit",
                running_balance=balance,
            )
        )
        prev_balance = balance
    return txns


def _parse_transactions_by_line(
    lines: list[str], idx: int, *, year: int, beginning: float
) -> list[Transaction] | None:
    """The line reader: each pair takes the date and the description read before it (a credit with neither takes the
    group after it). Audit round 2, R2-B06 (R03): run only where the lookahead reading does not fit, unchanged."""
    prev_balance = beginning
    current_date: str | None = None
    desc_parts: list[str] = []
    txns: list[Transaction] = []

    while idx < len(lines):
        line = lines[idx]
        if _is_date(line):
            current_date = line
            desc_parts = []
            idx += 1
            continue
        if line == "-":
            idx += 1
            continue
        if "Ending Balance" in line:
            break

        pair = _amount_balance(line)
        next_idx = idx + 1
        if pair is None:
            separate = _separate_amount_balance(lines, idx)
            if separate is not None:
                amount, balance, next_idx = separate
                pair = amount, balance

        if pair is not None:
            amount, balance = pair
            if next_idx < len(lines) and lines[next_idx] == "-":
                next_idx += 1
            signed = round(balance - prev_balance, 2)
            if abs(abs(signed) - abs(amount)) > 0.01:
                return None

            txn_date = current_date
            description = " ".join(desc_parts).strip()
            # Compatibility path for OCR text without native layout markers.
            # Digitally generated Navy Federal PDFs use the coordinate-aware rows
            # above, where date and description ownership is explicit.
            #
            # ONLY where this row has nothing of its own to lose. The branch
            # exists for the arrangement that prints a credit's date and
            # description AFTER its amount pair, so the row reaches this point
            # with neither. Where the row already carries both - the date
            # printed above it and the description read into `desc_parts` -
            # taking the next row's date and description instead does not
            # relabel one row, it shifts the whole ledger by one: this row is
            # published on the NEXT row's day under the next row's
            # description, the next row inherits that same day with an empty
            # description, and the day this row was actually printed on is
            # never posted at all. `posting_dates_cover_source` sees exactly
            # that - a printed posting date no transaction carries - on three
            # of the four withheld documents in this family.
            if signed > 0 and (txn_date is None or not description):
                following = _consume_following_date_desc(lines, next_idx)
                if following is not None:
                    txn_date, description, next_idx = following
                    current_date = txn_date
            if txn_date is None:
                return None
            description = re.sub(r"\s+", " ", description).strip() or "Navy Federal transaction"
            txns.append(
                Transaction(
                    date=date(year, int(txn_date[:2]), int(txn_date[3:])).isoformat(),
                    description=description,
                    amount=signed,
                    direction="credit" if signed >= 0 else "debit",
                    running_balance=balance,
                )
            )
            prev_balance = balance
            desc_parts = []
            idx = next_idx
            continue

        desc_parts.append(line)
        idx += 1

    return txns


DETECTION_MARKERS = (
    required("bank_name", lambda t: "Navy Federal" in t),
    required("section", lambda t: "Summary of your deposit accounts" in t),
)

detect = make_detector(DETECTION_MARKERS)

#: Audit B9 (I13): the mailing block Navy Federal prints after its 'Questions about this Statement?' heading: the
#: holder's name, its street and its city, state and ZIP, with the toll-free panel's lines between them.
_QUESTIONS_HEADING = re.compile(r"^Questions about this Statement\?[ \t]*$", re.MULTILINE)
_SERVICE_PANEL_LINE = re.compile(
    r"^(?:Toll-free in the U\.S\..*|For toll-free numbers when overseas,?|visit|navyfederal\.org/overseas/?"
    r"|Collect internationally.*)$",
    re.IGNORECASE,
)
_CITY_STATE_ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\s*$")
#: The mailing block's lines (the name, two address lines and a wrapped name or a care-of line at most).
_MAILING_BLOCK_LINES = 6


#: Audit round 2, R2-B05 (R04 part 2): page 1's mail-routing code line ('#AAAAAAA #000000AAAA#000AAA00A'), which the
#: holder's name and address follow, run on after it or as a block with the panel's lines between, and the panel lines
#: such a block can interleave (the routing number, the questions heading).
_MAIL_CODE_LINE = re.compile(r"^#[A-Z0-9]+ #[A-Z0-9]+#[A-Z0-9]+(?:\s+(?P<rest>\S.*))?$")
_PAGE_ONE_PANEL_LINE = re.compile(r"^(?:Routing Number:.*|Questions about this Statement\?.*)$", re.IGNORECASE)


def _holder_reading(markdown: str) -> HolderReading:
    """Audit B9 (I13): the holder's name, the first line of the mailing block after the 'Questions about this
    Statement?' heading (the toll-free panel's lines aside), read when the block closes on a city, state and ZIP within
    _MAILING_BLOCK_LINES lines. `account_name` keeps the parser's product. Audit round 2, R2-B05 (R04 part 2): where
    that reads none, page 1's block after the mail-routing code (_page_one_holder_reading). Owner ruling 2026-10-02
    (Q10), audit round 2, R2-OW10: with the account title the reading's own block or line prints."""
    reading = _questions_block_holder_reading(markdown)
    return reading if reading.name else _page_one_holder_reading(markdown)


def _page_one_holder_reading(markdown: str) -> HolderReading:
    """Audit round 2, R2-B05 (R04 part 2): page 1's block fallback where the questions heading reads no holder: the
    name after the mail-routing code line, before the address it runs on into (when that closes on a state and ZIP), or
    the first line of the block after it (the panel's lines aside) when the block closes on a state and ZIP within
    _MAILING_BLOCK_LINES lines; NO_READING otherwise."""
    lines = page_lines(first_page(markdown))
    for index, line in enumerate(lines):
        code = _MAIL_CODE_LINE.match(line)
        if code is None:
            continue
        rest = code.group("rest")
        if rest:
            return read_address_line(rest) if _CITY_STATE_ZIP.search(rest) else NO_READING
        block: list[str] = []
        for following in lines[index + 1:]:
            if _SERVICE_PANEL_LINE.match(following) or _PAGE_ONE_PANEL_LINE.match(following):
                continue
            block.append(following)
            if _CITY_STATE_ZIP.search(following):
                return read_address_block(block)
            if len(block) >= _MAILING_BLOCK_LINES:
                break
        return NO_READING
    return NO_READING


def _questions_block_holder_reading(markdown: str) -> HolderReading:
    """Audit B9 (I13): the holder's name from the mailing block after the questions heading (_holder_reading)."""
    heading = _QUESTIONS_HEADING.search(markdown)
    if heading is None:
        return NO_READING
    block: list[str] = []
    for raw in markdown[heading.end():].splitlines():
        line = raw.strip()
        if not line or _SERVICE_PANEL_LINE.match(line):
            continue
        block.append(line)
        if _CITY_STATE_ZIP.search(line):
            return read_address_block(block)
        if len(block) >= _MAILING_BLOCK_LINES:
            break
    return NO_READING


def parse_navy_federal_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _parse_period(markdown)
    summary = _summary(markdown)
    if period is None or summary is None:
        return None
    start, end, year = period
    product, account, beginning, credits, debits, ending_balance = summary
    section = _checking_section(markdown, product, account)
    if not section:
        return None
    if "NFCU_NATIVE_TRANSACTIONS_BEGIN" in markdown:
        txns = _parse_native_transactions(markdown, account, year=year, beginning=beginning)
    else:
        txns = _parse_transactions(
            section, f"{product} - {account}", year=year, beginning=beginning
        )
    if not txns:
        return None
    if abs(sum(tx.amount for tx in txns if tx.amount > 0) - credits) > 0.01:
        return None
    if abs(-sum(tx.amount for tx in txns if tx.amount < 0) - debits) > 0.01:
        return None
    if abs((txns[-1].running_balance or 0.0) - ending_balance) > 0.01:
        return None

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    printed_average = _average_balance(section)
    holder = _holder_reading(markdown)
    stmt = Statement(
        bank="Navy Federal Credit Union",
        account_name=product,
        holder_name=holder.name,
        account_title=holder.title,
        account_number=account,
        period_start=start,
        period_end=end,
        days_in_period=(end_date - start_date).days + 1,
        beginning_balance=beginning,
        ending_balance=ending_balance,
        stated_total_credits=credits,
        stated_total_debits=debits,
        bank_reported_average_balance=printed_average,
        bank_reported_average_label=(
            "Average Daily Balance - Current Cycle" if printed_average is not None else None
        ),
        transactions=txns,
    )
    return stmt
